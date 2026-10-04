import os
import unittest
from types import SimpleNamespace
from uuid import uuid4

from services.mcp_server import server
from services.mcp_server.database import supabase


def project_context(project_id, user_id):
    request = SimpleNamespace(headers={
        "x-devpilot-project-id": project_id,
        "x-devpilot-user-id": user_id,
    })
    return SimpleNamespace(
        request_context=SimpleNamespace(request=request),
    )


@unittest.skipUnless(
    os.getenv("RUN_DEVPILOT_INTEGRATION_TESTS") == "1",
    "Set RUN_DEVPILOT_INTEGRATION_TESTS=1 to test against Supabase",
)
class ProjectScopeIntegrationTests(unittest.TestCase):
    def test_task_actions_remain_in_selected_nondefault_project(self):
        users = (
            supabase.table("devpilot_users")
            .select("id")
            .limit(1)
            .execute()
            .data
        )
        self.assertTrue(users, "A connected DevPilot user is required")
        user_id = users[0]["id"]

        projects = (
            supabase.table("projects")
            .select("id,name,created_at")
            .eq("user_id", user_id)
            .is_("github_access_revoked_at", "null")
            .order("created_at")
            .execute()
            .data
        )
        self.assertGreaterEqual(len(projects), 2)
        default_project = projects[0]
        selected_project = projects[-1]
        selected_context = project_context(selected_project["id"], user_id)
        default_context = project_context(default_project["id"], user_id)
        title = f"DevPilot scope test {uuid4().hex}"
        created_id = None

        try:
            created = server.create_task(
                title,
                selected_context,
                priority="high",
            )
            created_id = created["id"]
            self.assertEqual(
                created["project_id"],
                selected_project["id"],
            )

            selected_tasks = server.get_project_tasks(selected_context)
            self.assertIn(
                created_id,
                [task["id"] for task in selected_tasks],
            )

            wrong_project_rows = (
                supabase.table("tasks")
                .select("id")
                .eq("project_id", default_project["id"])
                .eq("title", title)
                .execute()
                .data
            )
            self.assertEqual(wrong_project_rows, [])

            updated = server.update_task_status(
                created_id,
                "in_progress",
                selected_context,
            )
            self.assertEqual(updated["status"], "in_progress")

            with self.assertRaisesRegex(ValueError, "active project"):
                server.update_task_status(
                    created_id,
                    "done",
                    default_context,
                )
        finally:
            if created_id:
                (
                    supabase.table("tasks")
                    .delete()
                    .eq("id", created_id)
                    .execute()
                )


if __name__ == "__main__":
    unittest.main()
