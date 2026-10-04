import logging
from typing import Literal

from services.agent_api.dashboard import get_project_data
from services.mcp_server.database import supabase


logger = logging.getLogger(__name__)

MAX_CHAT_MESSAGES = 40
ChatRole = Literal["user", "assistant"]


def list_project_chat_messages(
    project_id: str,
    user_id: str,
) -> list[dict]:
    get_project_data(project_id, user_id)
    rows = (
        supabase.table("project_chat_messages")
        .select("id,role,content,created_at")
        .eq("project_id", project_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(MAX_CHAT_MESSAGES)
        .execute()
        .data
    )
    rows.reverse()
    return rows


def save_project_chat_message(
    project_id: str,
    user_id: str,
    role: ChatRole,
    content: str,
) -> dict:
    if role not in {"user", "assistant"}:
        raise ValueError("Unsupported chat message role")
    clean_content = content.strip()
    if not clean_content:
        raise ValueError("Chat messages cannot be empty")

    rows = (
        supabase.table("project_chat_messages")
        .insert({
            "project_id": project_id,
            "user_id": user_id,
            "role": role,
            "content": clean_content[:20000],
        })
        .execute()
        .data
    )
    if not rows:
        raise ValueError("Chat message could not be saved")

    stale_rows = (
        supabase.table("project_chat_messages")
        .select("id")
        .eq("project_id", project_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .range(MAX_CHAT_MESSAGES, MAX_CHAT_MESSAGES + 1000)
        .execute()
        .data
    )
    stale_ids = [row["id"] for row in stale_rows]
    if stale_ids:
        (
            supabase.table("project_chat_messages")
            .delete()
            .in_("id", stale_ids)
            .execute()
        )
    return rows[0]


def load_chat_history_safely(
    project_id: str,
    user_id: str,
) -> list[dict]:
    try:
        return list_project_chat_messages(project_id, user_id)
    except Exception:
        logger.exception("Project chat history could not be loaded")
        return []


def save_chat_message_safely(
    project_id: str,
    user_id: str,
    role: ChatRole,
    content: str,
) -> None:
    try:
        save_project_chat_message(project_id, user_id, role, content)
    except Exception:
        logger.exception("Project chat message could not be saved")


def build_agent_conversation(
    project: dict,
    history: list[dict],
    message: str,
) -> list[dict]:
    conversation = [
        {
            "role": item["role"],
            "content": item["content"],
        }
        for item in history[-MAX_CHAT_MESSAGES:]
        if item.get("role") in {"user", "assistant"}
        and item.get("content")
    ]
    conversation.append({
        "role": "user",
        "content": (
            "Active project context, enforced by the server:\n"
            f"- Name: {project['name']}\n"
            f"- Repository: "
            f"{project.get('github_owner')}/{project.get('github_repo')}\n\n"
            f"Current request:\n{message}"
        ),
    })
    return conversation
