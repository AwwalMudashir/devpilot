import asyncio
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import HTTPException, status

from services.agent_api.github_auth import (
    sync_installation_for_user,
    upsert_installation,
)
from services.mcp_server.database import supabase
from services.mcp_server.github_client import clear_installation_token


load_dotenv()

GITHUB_APP_WEBHOOK_SECRET = os.getenv("GITHUB_APP_WEBHOOK_SECRET", "")


def verify_webhook_signature(body: bytes, signature: str | None) -> None:
    if not GITHUB_APP_WEBHOOK_SECRET:
        raise RuntimeError("GITHUB_APP_WEBHOOK_SECRET is missing")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The GitHub webhook signature is missing",
        )
    expected = "sha256=" + hmac.new(
        GITHUB_APP_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The GitHub webhook signature is invalid",
        )


def delivery_was_processed(delivery_id: str) -> bool:
    rows = (
        supabase.table("github_webhook_deliveries")
        .select("delivery_id")
        .eq("delivery_id", delivery_id)
        .limit(1)
        .execute()
        .data
    )
    return bool(rows)


def record_delivery(
    delivery_id: str,
    event_name: str,
    action: str | None,
) -> None:
    supabase.table("github_webhook_deliveries").insert({
        "delivery_id": delivery_id,
        "event_name": event_name,
        "action": action,
    }).execute()


def installation_user_ids(installation_id: int) -> list[str]:
    rows = (
        supabase.table("user_installations")
        .select("user_id")
        .eq("installation_id", installation_id)
        .execute()
        .data
    )
    return [str(row["user_id"]) for row in rows]


def revoke_installation_projects(installation_id: int) -> None:
    (
        supabase.table("projects")
        .update({
            "github_access_revoked_at": datetime.now(
                timezone.utc
            ).isoformat(),
        })
        .eq("github_installation_id", installation_id)
        .execute()
    )


def revoke_repositories(
    installation_id: int,
    repositories: list[dict[str, Any]],
) -> None:
    revoked_at = datetime.now(timezone.utc).isoformat()
    for repository in repositories:
        (
            supabase.table("projects")
            .update({"github_access_revoked_at": revoked_at})
            .eq("github_installation_id", installation_id)
            .eq("github_repo_id", repository["id"])
            .execute()
        )


def update_installation_status(
    installation_id: int,
    *,
    suspended_at: str | None = None,
    deleted_at: str | None = None,
) -> None:
    (
        supabase.table("github_installations")
        .update({
            "suspended_at": suspended_at,
            "deleted_at": deleted_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", installation_id)
        .execute()
    )


async def sync_linked_users(
    installation_id: int,
    installation: dict[str, Any],
) -> None:
    user_ids = await asyncio.to_thread(
        installation_user_ids,
        installation_id,
    )
    for user_id in user_ids:
        await sync_installation_for_user(user_id, installation)


async def process_github_webhook(
    body: bytes,
    signature: str | None,
    delivery_id: str | None,
    event_name: str | None,
) -> dict[str, Any]:
    verify_webhook_signature(body, signature)
    if not delivery_id or not event_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub webhook headers are incomplete",
        )
    if await asyncio.to_thread(delivery_was_processed, delivery_id):
        return {"status": "already_processed"}

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The GitHub webhook body is invalid",
        ) from error

    action = payload.get("action")
    installation = payload.get("installation") or {}
    installation_id = installation.get("id")

    if event_name == "installation" and installation_id:
        installation_id = int(installation_id)
        clear_installation_token(installation_id)

        if action == "deleted":
            await asyncio.to_thread(
                update_installation_status,
                installation_id,
                deleted_at=datetime.now(timezone.utc).isoformat(),
            )
            await asyncio.to_thread(
                revoke_installation_projects,
                installation_id,
            )
        elif action == "suspend":
            await asyncio.to_thread(
                update_installation_status,
                installation_id,
                suspended_at=installation.get("suspended_at")
                or datetime.now(timezone.utc).isoformat(),
            )
            await asyncio.to_thread(
                revoke_installation_projects,
                installation_id,
            )
        else:
            await asyncio.to_thread(upsert_installation, installation)
            await sync_linked_users(installation_id, installation)

    if event_name == "installation_repositories" and installation_id:
        installation_id = int(installation_id)
        clear_installation_token(installation_id)
        removed = payload.get("repositories_removed") or []
        if removed:
            await asyncio.to_thread(
                revoke_repositories,
                installation_id,
                removed,
            )
        await asyncio.to_thread(upsert_installation, installation)
        await sync_linked_users(installation_id, installation)

    await asyncio.to_thread(
        record_delivery,
        delivery_id,
        event_name,
        action,
    )
    return {"status": "accepted"}
