import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.agent_api.approvals import WRITE_TOOL_DETAILS, WRITE_TOOL_NAMES
from services.agent_api.scoped_mcp import ProjectScopedMCPServer
from services.mcp_server import server


class FakeQuery:
    def __init__(self, database, table_name):
        self.database = database
        self.table_name = table_name
        self.operation = "select"
        self.filters = {}
        self.payload = None

    def select(self, columns):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, name, value):
        self.filters[name] = value
        return self

    def is_(self, name, value):
        self.filters[name] = value
        return self

    def limit(self, value):
        return self

    def order(self, name):
        return self

    def execute(self):
        if self.table_name == "projects":
            allowed = (
                self.filters.get("id") == "project-b"
                and self.filters.get("user_id") == "user-b"
            )
            return SimpleNamespace(data=[{"id": "project-b"}] if allowed else [])

        if self.operation == "insert":
            created = {"id": "new-task", **self.payload}
            self.database.tasks[created["id"]] = created
            return SimpleNamespace(data=[created])

        matching = [
            task for task in self.database.tasks.values()
            if all(task.get(name) == value for name, value in self.filters.items())
        ]
        if self.operation == "update":
            for task in matching:
                task.update(self.payload)
            return SimpleNamespace(data=matching)
        return SimpleNamespace(data=matching)


class FakeSupabase:
    def __init__(self):
        self.tasks = {
            "task-a": {
                "id": "task-a",
                "project_id": "project-a",
                "title": "Project A task",
                "description": "Project A description",
                "status": "todo",
            },
            "task-b": {
                "id": "task-b",
                "project_id": "project-b",
                "title": "Project B task",
                "description": "Project B description",
                "status": "todo",
            },
        }

    def table(self, table_name):
        return FakeQuery(self, table_name)


def project_context(project_id="project-b", user_id="user-b"):
    request = SimpleNamespace(headers={
        "x-devpilot-project-id": project_id,
        "x-devpilot-user-id": user_id,
    })
    return SimpleNamespace(
        request_context=SimpleNamespace(request=request),
    )


class ProjectScopeTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeSupabase()
        self.context = project_context()
        self.patch = patch.object(server, "supabase", self.database)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_create_task_uses_header_project(self):
        created = server.create_task(
            "Scoped task",
            self.context,
            priority="high",
        )

        self.assertEqual(created["project_id"], "project-b")
        self.assertEqual(created["priority"], "high")

    def test_update_cannot_cross_project_boundary(self):
        with self.assertRaisesRegex(ValueError, "active project"):
            server.update_task_status(
                "task-a",
                "done",
                self.context,
            )

        self.assertEqual(self.database.tasks["task-a"]["status"], "todo")

    def test_update_changes_task_in_active_project(self):
        updated = server.update_task_status(
            "task-b",
            "in_progress",
            self.context,
        )

        self.assertEqual(updated["status"], "in_progress")

    def test_description_update_changes_task_in_active_project(self):
        updated = server.update_task_description(
            "task-b",
            "  Clarify the acceptance criteria  ",
            self.context,
        )

        self.assertEqual(
            updated["description"],
            "Clarify the acceptance criteria",
        )

    def test_description_update_cannot_cross_project_boundary(self):
        with self.assertRaisesRegex(ValueError, "active project"):
            server.update_task_description(
                "task-a",
                "This must not be applied",
                self.context,
            )

        self.assertEqual(
            self.database.tasks["task-a"]["description"],
            "Project A description",
        )

    def test_description_update_requires_meaningful_content(self):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            server.update_task_description(
                "task-b",
                "   ",
                self.context,
            )

    def test_description_update_requires_approval(self):
        self.assertIn("update_task_description", WRITE_TOOL_NAMES)
        self.assertEqual(
            WRITE_TOOL_DETAILS["update_task_description"][0],
            "Update task description",
        )

    def test_read_returns_only_active_project_tasks(self):
        tasks = server.get_project_tasks(self.context)

        self.assertEqual([task["id"] for task in tasks], ["task-b"])

    def test_tool_schemas_do_not_expose_project_id(self):
        tools = asyncio.run(server.mcp.list_tools())
        project_tools = [tool for tool in tools if tool.name != "ping"]

        for tool in project_tools:
            properties = tool.input_schema.get("properties", {})
            self.assertNotIn("project_id", properties, tool.name)

        description_tool = next(
            tool for tool in tools
            if tool.name == "update_task_description"
        )
        description_schema = description_tool.input_schema["properties"][
            "description"
        ]
        self.assertEqual(description_schema["minLength"], 1)
        self.assertEqual(description_schema["maxLength"], 2000)

    def test_agent_adapter_applies_immutable_project_scope(self):
        adapter = ProjectScopedMCPServer(
            project_id="project-b",
            user_id="user-b",
        )

        asyncio.run(adapter.call_tool(
            "create_task",
            {"title": "Adapter-scoped task", "priority": "critical"},
        ))

        created = self.database.tasks["new-task"]
        self.assertEqual(created["project_id"], "project-b")
        self.assertEqual(created["priority"], "critical")


if __name__ == "__main__":
    unittest.main()
