import asyncio
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response, status

from services.mcp_server.database import supabase
from services.mcp_server.github_client import (
    get_installation,
    list_installation_repositories,
)


load_dotenv()

SESSION_COOKIE = "devpilot_session"
OAUTH_STATE_COOKIE = "devpilot_oauth_state"
SESSION_DAYS = 7
OAUTH_STATE_MINUTES = 10

APP_SESSION_SECRET = os.getenv("APP_SESSION_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
GITHUB_CALLBACK_URL = os.getenv(
    "GITHUB_CALLBACK_URL",
    f"{FRONTEND_URL}/api/devpilot/auth/github/callback",
)


def require_session_secret() -> str:
    if len(APP_SESSION_SECRET) < 32:
        raise RuntimeError(
            "APP_SESSION_SECRET must contain at least 32 characters"
        )
    return APP_SESSION_SECRET


def secure_cookies() -> bool:
    return GITHUB_CALLBACK_URL.startswith("https://")


def create_oauth_state() -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "type": "github_oauth_state",
            "nonce": secrets.token_urlsafe(24),
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(minutes=OAUTH_STATE_MINUTES)).timestamp()
            ),
        },
        require_session_secret(),
        algorithm="HS256",
    )


def verify_oauth_state(state: str, cookie_state: str | None) -> None:
    if not cookie_state or not hmac.compare_digest(state, cookie_state):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The GitHub connection request is invalid or expired",
        )
    try:
        payload = jwt.decode(
            state,
            require_session_secret(),
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The GitHub connection request is invalid or expired",
        ) from error
    if payload.get("type") != "github_oauth_state":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The GitHub connection request is invalid",
        )


def set_oauth_state_cookie(response: Response, state_value: str) -> None:
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state_value,
        max_age=OAUTH_STATE_MINUTES * 60,
        httponly=True,
        secure=secure_cookies(),
        samesite="lax",
        path="/",
    )


def clear_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(
        OAUTH_STATE_COOKIE,
        httponly=True,
        secure=secure_cookies(),
        samesite="lax",
        path="/",
    )


def _session_hash(token: str) -> str:
    return hmac.new(
        require_session_secret().encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def upsert_user(github_user: dict[str, Any]) -> dict[str, Any]:
    rows = (
        supabase.table("devpilot_users")
        .upsert(
            {
                "github_user_id": github_user["id"],
                "github_login": github_user["login"],
                "github_name": github_user.get("name"),
                "avatar_url": github_user.get("avatar_url"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="github_user_id",
        )
        .execute()
        .data
    )
    if not rows:
        raise RuntimeError("The GitHub user could not be saved")
    return rows[0]


def upsert_installation(installation: dict[str, Any]) -> dict[str, Any]:
    account = installation.get("account") or {}
    rows = (
        supabase.table("github_installations")
        .upsert(
            {
                "id": installation["id"],
                "account_id": account["id"],
                "account_login": account["login"],
                "account_type": account.get("type", "User"),
                "repository_selection": installation.get(
                    "repository_selection",
                    "selected",
                ),
                "permissions": installation.get("permissions") or {},
                "suspended_at": installation.get("suspended_at"),
                "deleted_at": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="id",
        )
        .execute()
        .data
    )
    if not rows:
        raise RuntimeError("The GitHub installation could not be saved")
    return rows[0]


def link_user_installation(user_id: str, installation_id: int) -> None:
    (
        supabase.table("user_installations")
        .upsert(
            {
                "user_id": user_id,
                "installation_id": installation_id,
            },
            on_conflict="user_id,installation_id",
        )
        .execute()
    )


def _repository_payload(
    user_id: str,
    installation_id: int,
    repository: dict[str, Any],
) -> dict[str, Any]:
    owner = repository.get("owner") or {}
    return {
        "user_id": user_id,
        "github_installation_id": installation_id,
        "github_repo_id": repository["id"],
        "github_owner": owner.get("login"),
        "github_repo": repository["name"],
        "github_full_name": repository.get("full_name"),
        "github_private": bool(repository.get("private")),
        "github_default_branch": repository.get("default_branch"),
        "github_access_revoked_at": None,
        "name": repository["name"],
        "description": repository.get("description"),
    }


def save_selected_repositories(
    user_id: str,
    installation_id: int,
    repositories: list[dict[str, Any]],
) -> None:
    existing = (
        supabase.table("projects")
        .select("id,github_repo_id")
        .eq("user_id", user_id)
        .eq("github_installation_id", installation_id)
        .execute()
        .data
    )
    existing_by_repo_id = {
        int(project["github_repo_id"]): project
        for project in existing
        if project.get("github_repo_id") is not None
    }
    selected_repo_ids: set[int] = set()

    for repository in repositories:
        repo_id = int(repository["id"])
        selected_repo_ids.add(repo_id)
        payload = _repository_payload(user_id, installation_id, repository)
        project = existing_by_repo_id.get(repo_id)
        if project:
            (
                supabase.table("projects")
                .update(payload)
                .eq("id", project["id"])
                .execute()
            )
        else:
            supabase.table("projects").insert(payload).execute()

    revoked_at = datetime.now(timezone.utc).isoformat()
    for repo_id, project in existing_by_repo_id.items():
        if repo_id not in selected_repo_ids:
            (
                supabase.table("projects")
                .update({"github_access_revoked_at": revoked_at})
                .eq("id", project["id"])
                .execute()
            )


async def sync_installation_for_user(
    user_id: str,
    installation: dict[str, Any] | int,
) -> list[dict[str, Any]]:
    installation_data = (
        await get_installation(installation)
        if isinstance(installation, int)
        else installation
    )
    installation_id = int(installation_data["id"])
    repositories = await list_installation_repositories(installation_id)
    await asyncio.to_thread(upsert_installation, installation_data)
    await asyncio.to_thread(
        link_user_installation,
        user_id,
        installation_id,
    )
    await asyncio.to_thread(
        save_selected_repositories,
        user_id,
        installation_id,
        repositories,
    )
    return repositories


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    supabase.table("devpilot_sessions").insert({
        "user_id": user_id,
        "token_hash": _session_hash(token),
        "expires_at": expires_at.isoformat(),
    }).execute()
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=secure_cookies(),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        httponly=True,
        secure=secure_cookies(),
        samesite="lax",
        path="/",
    )


def get_user_for_session(token: str) -> dict[str, Any] | None:
    rows = (
        supabase.table("devpilot_sessions")
        .select("id,user_id,expires_at")
        .eq("token_hash", _session_hash(token))
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return None

    session = rows[0]
    expires_at = datetime.fromisoformat(
        session["expires_at"].replace("Z", "+00:00")
    )
    if expires_at <= datetime.now(timezone.utc):
        (
            supabase.table("devpilot_sessions")
            .delete()
            .eq("id", session["id"])
            .execute()
        )
        return None

    users = (
        supabase.table("devpilot_users")
        .select("id,github_user_id,github_login,github_name,avatar_url")
        .eq("id", session["user_id"])
        .limit(1)
        .execute()
        .data
    )
    return users[0] if users else None


def delete_session(token: str) -> None:
    (
        supabase.table("devpilot_sessions")
        .delete()
        .eq("token_hash", _session_hash(token))
        .execute()
    )


async def require_user(request: Request) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Connect GitHub to continue",
        )
    user = await asyncio.to_thread(get_user_for_session, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Connect GitHub again.",
        )
    return user
