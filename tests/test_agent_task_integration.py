import os
import unittest
from uuid import uuid4

import httpx

from services.agent_api.github_auth import (
    SESSION_COOKIE,
    create_session,
    delete_session,
)
from services.mcp_server.database import supabase


@unittest.skipUnless(
    os.getenv("RUN_DEVPILOT_AGENT_TESTS") == "1",
    "Set RUN_DEVPILOT_AGENT_TESTS=1 to test the live agent",
)
class AgentTaskIntegrationTests(unittest.TestCase):
    def test_agent_creates_and_updates_task_in_selected_project(self):
        users = (
            supabase.table("devpilot_users")
            .select("id")
            .limit(1)
            .execute()
            .data
        )
        self.assertTrue(users)
        user_id = users[0]["id"]
        default_projects = (
            supabase.table("projects")
            .select("id,name,created_at")
            .eq("user_id", user_id)
            .is_("github_access_revoked_at", "null")
            .order("created_at")
            .execute()
            .data
        )
        self.assertTrue(default_projects)
        default_project = default_projects[0]
        sandbox_suffix = uuid4().hex[:10]
        title = f"Agent scope test {uuid4().hex[:10]}"
        selected_project = None
        session_token = None
        created_id = None

        try:
            selected_project = (
                supabase.table("projects")
                .insert({
                    "name": f"Integration sandbox {sandbox_suffix}",
                    "description": "Temporary project used by the automated test",
                    "github_owner": "devpilot-test",
                    "github_repo": f"scope-sandbox-{sandbox_suffix}",
                    "user_id": user_id,
                })
                .execute()
                .data[0]
            )
            session_token = create_session(user_id)
            with httpx.Client(
                base_url=os.getenv(
                    "DEVPILOT_AGENT_TEST_URL",
                    "http://127.0.0.1:8002",
                ),
                cookies={SESSION_COOKIE: session_token},
                timeout=120,
            ) as client:
                create_result = client.post("/chat", json={
                    "project_id": selected_project["id"],
                    "message": (
                        f"Create a high-priority task titled '{title}'. "
                        "Use the description 'Verify project-scoped AI task "
                        "creation' and do not add a due date."
                    ),
                })
                self.assertEqual(create_result.status_code, 200)
                pending_create = create_result.json()
                self.assertEqual(pending_create["status"], "approval_required")
                approval = pending_create["approvals"][0]
                self.assertNotIn("project_id", approval["arguments"])

                create_completion = client.post(
                    f"/chat/approvals/{pending_create['approval_id']}",
                    json={
                        "request_id": approval["request_id"],
                        "decision": "approve",
                    },
                )
                self.assertEqual(create_completion.status_code, 200)
                completion_body = create_completion.json()
                self.assertEqual(completion_body["status"], "completed")
                self.assertGreaterEqual(len(completion_body["answer"]), 150)
                self.assertIn(
                    "Suggested next steps",
                    completion_body["answer"],
                )
                self.assertIn(
                    selected_project["name"].lower(),
                    completion_body["answer"].lower(),
                )

                created_rows = (
                    supabase.table("tasks")
                    .select("id,project_id,status")
                    .eq("project_id", selected_project["id"])
                    .eq("title", title)
                    .execute()
                    .data
                )
                self.assertEqual(len(created_rows), 1)
                created_id = created_rows[0]["id"]

                wrong_rows = (
                    supabase.table("tasks")
                    .select("id")
                    .eq("project_id", default_project["id"])
                    .eq("title", title)
                    .execute()
                    .data
                )
                self.assertEqual(wrong_rows, [])

                update_result = client.post("/chat", json={
                    "project_id": selected_project["id"],
                    "message": (
                        f"Change task {created_id} to in progress."
                    ),
                })
                self.assertEqual(update_result.status_code, 200)
                pending_update = update_result.json()
                self.assertEqual(pending_update["status"], "approval_required")
                update_approval = pending_update["approvals"][0]

                update_completion = client.post(
                    f"/chat/approvals/{pending_update['approval_id']}",
                    json={
                        "request_id": update_approval["request_id"],
                        "decision": "approve",
                    },
                )
                self.assertEqual(update_completion.status_code, 200)
                self.assertEqual(
                    update_completion.json()["status"],
                    "completed",
                )
                self.assertIn(
                    "Suggested next steps",
                    update_completion.json()["answer"],
                )

            updated_rows = (
                supabase.table("tasks")
                .select("status")
                .eq("id", created_id)
                .eq("project_id", selected_project["id"])
                .execute()
                .data
            )
            self.assertEqual(updated_rows[0]["status"], "in_progress")
        finally:
            if created_id:
                (
                    supabase.table("tasks")
                    .delete()
                    .eq("id", created_id)
                    .execute()
                )
            if session_token:
                delete_session(session_token)
            if selected_project:
                (
                    supabase.table("projects")
                    .delete()
                    .eq("id", selected_project["id"])
                    .execute()
                )


if __name__ == "__main__":
    unittest.main()
