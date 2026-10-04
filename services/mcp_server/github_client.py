import asyncio
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import jwt
import truststore
from dotenv import load_dotenv

from services.mcp_server.database import supabase


load_dotenv()
truststore.inject_into_ssl()

BASE_URL = "https://api.github.com"
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID", "")
GITHUB_APP_CLIENT_ID = os.getenv("GITHUB_APP_CLIENT_ID", "")
GITHUB_APP_CLIENT_SECRET = os.getenv("GITHUB_APP_CLIENT_SECRET", "")
GITHUB_APP_PRIVATE_KEY_PATH = os.getenv(
    "GITHUB_APP_PRIVATE_KEY_PATH",
    "secrets/github-app.pem",
)

API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "DevPilot",
}

_token_cache: dict[int, tuple[str, datetime]] = {}
_token_locks: dict[int, asyncio.Lock] = {}


class GitHubConfigurationError(RuntimeError):
    pass


def _required(value: str, name: str) -> str:
    if not value:
        raise GitHubConfigurationError(f"{name} is missing")
    return value


def _read_private_key() -> str:
    configured_path = Path(GITHUB_APP_PRIVATE_KEY_PATH)
    candidates = [configured_path]
    if not configured_path.is_absolute():
        repository_root = Path(__file__).resolve().parents[2]
        candidates.append(repository_root / configured_path)

    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")

    raise GitHubConfigurationError(
        "The GitHub App private key could not be found"
    )


def create_app_jwt() -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "iat": int((now - timedelta(seconds=60)).timestamp()),
            "exp": int((now + timedelta(minutes=9)).timestamp()),
            "iss": _required(GITHUB_APP_ID, "GITHUB_APP_ID"),
        },
        _read_private_key(),
        algorithm="RS256",
    )


async def github_request(
    method: str,
    path: str,
    *,
    token: str,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> Any:
    headers = {
        **API_HEADERS,
        "Authorization": f"Bearer {token}",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(
            method,
            f"{BASE_URL}{path}",
            headers=headers,
            params=params,
            json=json,
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return None
        return response.json()


async def github_app_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> Any:
    return await github_request(
        method,
        path,
        token=create_app_jwt(),
        params=params,
        json=json,
    )


async def get_installation_token(installation_id: int) -> str:
    cached = _token_cache.get(installation_id)
    now = datetime.now(timezone.utc)
    if cached and cached[1] > now + timedelta(minutes=2):
        return cached[0]

    lock = _token_locks.setdefault(installation_id, asyncio.Lock())
    async with lock:
        cached = _token_cache.get(installation_id)
        if cached and cached[1] > now + timedelta(minutes=2):
            return cached[0]

        data = await github_app_request(
            "POST",
            f"/app/installations/{installation_id}/access_tokens",
        )
        token = data["token"]
        expires_at = datetime.fromisoformat(
            data["expires_at"].replace("Z", "+00:00")
        )
        _token_cache[installation_id] = (token, expires_at)
        return token


def clear_installation_token(installation_id: int) -> None:
    _token_cache.pop(installation_id, None)


def get_project_installation_id(project_id: str) -> int:
    rows = (
        supabase.table("projects")
        .select("github_installation_id")
        .eq("id", project_id)
        .is_("github_access_revoked_at", "null")
        .limit(1)
        .execute()
        .data
    )
    if not rows or not rows[0].get("github_installation_id"):
        raise ValueError("Project no longer has GitHub access")
    return int(rows[0]["github_installation_id"])


async def github_get_for_project(
    project_id: str,
    path: str,
    params: dict[str, Any] | None = None,
) -> Any:
    installation_id = await asyncio.to_thread(
        get_project_installation_id,
        project_id,
    )
    token = await get_installation_token(installation_id)
    return await github_request("GET", path, token=token, params=params)


async def list_installation_repositories(
    installation_id: int,
) -> list[dict[str, Any]]:
    token = await get_installation_token(installation_id)
    repositories: list[dict[str, Any]] = []

    for page in range(1, 11):
        data = await github_request(
            "GET",
            "/installation/repositories",
            token=token,
            params={"per_page": 100, "page": page},
        )
        batch = data.get("repositories", [])
        repositories.extend(batch)
        if len(batch) < 100:
            break

    return repositories


async def exchange_oauth_code(code: str, redirect_uri: str) -> str:
    payload = {
        "client_id": _required(
            GITHUB_APP_CLIENT_ID,
            "GITHUB_APP_CLIENT_ID",
        ),
        "client_secret": _required(
            GITHUB_APP_CLIENT_SECRET,
            "GITHUB_APP_CLIENT_SECRET",
        ),
        "code": code,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={
                "Accept": "application/json",
                "User-Agent": "DevPilot",
            },
            data=payload,
        )
        response.raise_for_status()
        data = response.json()

    if data.get("error"):
        raise ValueError(data.get("error_description") or data["error"])
    access_token = data.get("access_token")
    if not access_token:
        raise ValueError("GitHub did not return a user access token")
    return access_token


async def get_authenticated_github_user(token: str) -> dict[str, Any]:
    return await github_request("GET", "/user", token=token)


async def list_user_installations(token: str) -> list[dict[str, Any]]:
    installations: list[dict[str, Any]] = []
    for page in range(1, 11):
        data = await github_request(
            "GET",
            "/user/installations",
            token=token,
            params={"per_page": 100, "page": page},
        )
        batch = data.get("installations", [])
        installations.extend(batch)
        if len(batch) < 100:
            break
    return installations


async def get_installation(installation_id: int) -> dict[str, Any]:
    return await github_app_request(
        "GET",
        f"/app/installations/{installation_id}",
    )


async def validate_github_app() -> dict[str, Any]:
    return await github_app_request("GET", "/app")
