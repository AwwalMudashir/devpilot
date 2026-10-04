import unittest
from types import SimpleNamespace
from unittest.mock import patch

from services.agent_api import chat_history


class FakeChatQuery:
    def __init__(self, database):
        self.database = database
        self.operation = "select"
        self.columns = "*"
        self.filters = {}
        self.payload = None
        self.descending = False
        self.range_start = None
        self.range_end = None
        self.row_limit = None
        self.in_values = None

    def select(self, columns):
        self.operation = "select"
        self.columns = columns
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, name, value):
        self.filters[name] = value
        return self

    def in_(self, name, values):
        self.in_values = (name, set(values))
        return self

    def order(self, name, desc=False):
        self.descending = desc
        return self

    def limit(self, value):
        self.row_limit = value
        return self

    def range(self, start, end):
        self.range_start = start
        self.range_end = end
        return self

    def execute(self):
        if self.operation == "insert":
            self.database.sequence += 1
            row = {
                "id": f"message-{self.database.sequence}",
                "created_at": self.database.sequence,
                **self.payload,
            }
            self.database.messages.append(row)
            return SimpleNamespace(data=[dict(row)])

        matching = [
            row for row in self.database.messages
            if all(row.get(name) == value for name, value in self.filters.items())
        ]

        if self.operation == "delete":
            name, values = self.in_values
            deleted = [row for row in matching if row.get(name) in values]
            deleted_ids = {row["id"] for row in deleted}
            self.database.messages = [
                row for row in self.database.messages
                if row["id"] not in deleted_ids
            ]
            return SimpleNamespace(data=deleted)

        matching.sort(
            key=lambda row: row["created_at"],
            reverse=self.descending,
        )
        if self.range_start is not None:
            matching = matching[self.range_start:self.range_end + 1]
        if self.row_limit is not None:
            matching = matching[:self.row_limit]
        return SimpleNamespace(data=[dict(row) for row in matching])


class FakeChatDatabase:
    def __init__(self):
        self.messages = []
        self.sequence = 0

    def table(self, name):
        if name != "project_chat_messages":
            raise AssertionError(f"Unexpected table: {name}")
        return FakeChatQuery(self)


class ChatHistoryTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeChatDatabase()
        self.supabase_patch = patch.object(
            chat_history,
            "supabase",
            self.database,
        )
        self.project_patch = patch.object(
            chat_history,
            "get_project_data",
            return_value={"id": "project-a"},
        )
        self.supabase_patch.start()
        self.project_patch.start()

    def tearDown(self):
        self.project_patch.stop()
        self.supabase_patch.stop()

    def test_each_project_keeps_only_its_latest_40_messages(self):
        for index in range(45):
            chat_history.save_project_chat_message(
                "project-a",
                "user-a",
                "user" if index % 2 == 0 else "assistant",
                f"Project A message {index}",
            )
        for index in range(3):
            chat_history.save_project_chat_message(
                "project-b",
                "user-a",
                "user",
                f"Project B message {index}",
            )

        project_a = chat_history.list_project_chat_messages(
            "project-a",
            "user-a",
        )
        project_b = chat_history.list_project_chat_messages(
            "project-b",
            "user-a",
        )

        self.assertEqual(len(project_a), 40)
        self.assertEqual(project_a[0]["content"], "Project A message 5")
        self.assertEqual(project_a[-1]["content"], "Project A message 44")
        self.assertEqual(len(project_b), 3)
        self.assertEqual(project_b[0]["content"], "Project B message 0")

    def test_agent_context_uses_only_latest_40_messages(self):
        history = [
            {
                "role": "user" if index % 2 == 0 else "assistant",
                "content": f"Message {index}",
            }
            for index in range(45)
        ]
        project = {
            "name": "Project Alpha",
            "github_owner": "example",
            "github_repo": "alpha",
        }

        conversation = chat_history.build_agent_conversation(
            project,
            history,
            "What should I do next?",
        )

        self.assertEqual(len(conversation), 41)
        self.assertEqual(conversation[0]["content"], "Message 5")
        self.assertIn("Project Alpha", conversation[-1]["content"])
        self.assertIn("What should I do next?", conversation[-1]["content"])

    def test_invalid_role_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            chat_history.save_project_chat_message(
                "project-a",
                "user-a",
                "system",
                "Not allowed",
            )


if __name__ == "__main__":
    unittest.main()
