import hashlib
import hmac
import os
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.agent_api.github_auth import (
    create_oauth_state,
    verify_oauth_state,
)
from services.agent_api.github_webhooks import verify_webhook_signature
from services.agent_api.main import app
from services.mcp_server.server import app as mcp_app


class GitHubSecurityTests(unittest.TestCase):
    def test_oauth_state_accepts_original_and_rejects_tampering(self):
        state = create_oauth_state()
        verify_oauth_state(state, state)

        with self.assertRaises(HTTPException):
            verify_oauth_state(f"{state}x", state)

    def test_webhook_signature_accepts_valid_hmac(self):
        body = b'{"action":"created"}'
        secret = os.environ["GITHUB_APP_WEBHOOK_SECRET"]
        signature = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        verify_webhook_signature(body, signature)

        with self.assertRaises(HTTPException):
            verify_webhook_signature(body, "sha256=invalid")

    def test_oauth_start_uses_github_and_httponly_cookie(self):
        client = TestClient(app)
        response = client.get("/auth/github/start", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.headers["location"].startswith(
                "https://github.com/login/oauth/authorize"
            )
        )
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("SameSite=lax", response.headers["set-cookie"])

    def test_mcp_rejects_requests_without_internal_secret(self):
        client = TestClient(mcp_app)
        response = client.get("/mcp")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
