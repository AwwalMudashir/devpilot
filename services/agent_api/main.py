import os
import json
import asyncio
import logging
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from postgrest.exceptions import APIError

from agents import RunState, Runner
from services.agent_api.agent import build_agent
from services.agent_api.approvals import approval_store
from services.agent_api.chat_history import (
    build_agent_conversation,
    list_project_chat_messages,
    load_chat_history_safely,
    save_chat_message_safely,
)
from services.agent_api.dashboard import (
    create_project_task_data,
    get_project_data,
    get_project_activity_data,
    get_project_summary_data,
    get_project_tasks_data,
    list_projects_data,
)
from services.agent_api.github_auth import (
    FRONTEND_URL,
    GITHUB_CALLBACK_URL,
    OAUTH_STATE_COOKIE,
    SESSION_COOKIE,
    clear_oauth_state_cookie,
    clear_session_cookie,
    create_oauth_state,
    create_session,
    delete_session,
    get_user_for_session,
    require_user,
    set_oauth_state_cookie,
    set_session_cookie,
    sync_installation_for_user,
    upsert_user,
    verify_oauth_state,
)
from services.agent_api.github_webhooks import process_github_webhook
from services.agent_api.schemas import (
    ApprovalDecisionRequest,
    ApprovalRequest,
    ChatHistoryMessage,
    ChatRequest,
    ChatResponse,
    TaskCreateRequest,
)
from services.agent_api.scoped_mcp import ProjectScopedMCPServer
from services.mcp_server.database import supabase
from services.mcp_server.github_client import (
    exchange_oauth_code,
    get_authenticated_github_user,
    list_user_installations,
)


load_dotenv()

logger = logging.getLogger(__name__)

GITHUB_APP_SLUG = os.getenv("GITHUB_APP_SLUG", "")
GITHUB_APP_CLIENT_ID = os.getenv("GITHUB_APP_CLIENT_ID", "")

WRITE_TOOL_NAMES = ["create_task", "update_task_status"]


# FastAPI application
app = FastAPI(
    title="DevPilot Agent API",
    version="1.0.0",
)


# CORS

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted({
        FRONTEND_URL,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_mcp_server(
    project_id: str,
    user_id: str,
) -> ProjectScopedMCPServer:
    return ProjectScopedMCPServer(
        project_id=project_id,
        user_id=user_id,
        require_approval={
            "always": {"tool_names": WRITE_TOOL_NAMES}
        },
    )


def get_raw_value(raw_item: Any, name: str) -> Any:
    if isinstance(raw_item, dict):
        return raw_item.get(name)
    return getattr(raw_item, name, None)


def get_tool_arguments(raw_item: Any) -> dict[str, Any]:
    arguments = get_raw_value(raw_item, "arguments")
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def describe_approval(tool_name: str) -> tuple[str, str]:
    if tool_name == "create_task":
        return "Create task", "Add this task to the selected project"
    if tool_name == "update_task_status":
        return "Update task status", "Change the status of this task"
    return "Review action", "Review this project change before it runs"


async def build_chat_response(
    result,
    project_id: str,
    user_id: str,
) -> ChatResponse:
    if not result.interruptions:
        answer = result.final_output
        return ChatResponse(
            status="completed",
            answer=str(answer) if answer is not None else "Done",
        )

    state = result.to_state()
    approval_id, request_ids = await approval_store.create(
        state_json=state.to_json(),
        project_id=project_id,
        user_id=user_id,
        interruption_count=len(result.interruptions),
    )
    approvals = []
    for request_id, interruption in zip(request_ids, result.interruptions):
        tool_name = interruption.tool_name or "project_action"
        title, description = describe_approval(tool_name)
        approvals.append(
            ApprovalRequest(
                request_id=request_id,
                tool_name=tool_name,
                title=title,
                description=description,
                arguments=get_tool_arguments(interruption.raw_item),
            )
        )

    return ChatResponse(
        status="approval_required",
        approval_id=approval_id,
        approvals=approvals,
    )



# Health endpoint
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "devpilot-agent-api",
    }


@app.get("/auth/github")
@app.get("/auth/github/start")
def start_github_connection():
    if not GITHUB_APP_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="GITHUB_APP_CLIENT_ID is missing",
        )
    state_value = create_oauth_state()
    authorize_url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={quote(GITHUB_APP_CLIENT_ID, safe='')}"
        f"&redirect_uri={quote(GITHUB_CALLBACK_URL, safe='')}"
        f"&state={quote(state_value, safe='')}"
    )
    response = RedirectResponse(authorize_url, status_code=302)
    set_oauth_state_cookie(response, state_value)
    return response


def github_install_url() -> str:
    if not GITHUB_APP_SLUG:
        raise HTTPException(
            status_code=503,
            detail="GITHUB_APP_SLUG is missing",
        )
    return (
        f"https://github.com/apps/{quote(GITHUB_APP_SLUG, safe='')}"
        "/installations/new"
    )


@app.get("/auth/github/install")
def install_github_app(user: dict = Depends(require_user)):
    return RedirectResponse(github_install_url(), status_code=302)


@app.get("/auth/github/manage")
async def manage_github_installation(user: dict = Depends(require_user)):
    links = await asyncio.to_thread(
        lambda: (
            supabase.table("user_installations")
            .select("installation_id")
            .eq("user_id", user["id"])
            .limit(1)
            .execute()
            .data
        )
    )
    if not links:
        return RedirectResponse(github_install_url(), status_code=302)
    installation_id = int(links[0]["installation_id"])
    return RedirectResponse(
        f"https://github.com/settings/installations/{installation_id}",
        status_code=302,
    )


@app.get("/auth/github/callback")
async def github_callback(
    request: Request,
    code: str,
    state: str | None = None,
):
    current_session_token = request.cookies.get(SESSION_COOKIE)
    current_user = None
    if state:
        verify_oauth_state(
            state,
            request.cookies.get(OAUTH_STATE_COOKIE),
        )
    elif current_session_token:
        current_user = await asyncio.to_thread(
            get_user_for_session,
            current_session_token,
        )
    if not state and not current_user:
        raise HTTPException(
            status_code=400,
            detail="The GitHub connection request is invalid or expired",
        )

    user_token = await exchange_oauth_code(code, GITHUB_CALLBACK_URL)
    github_user, installations = await asyncio.gather(
        get_authenticated_github_user(user_token),
        list_user_installations(user_token),
    )
    if (
        current_user
        and int(current_user["github_user_id"]) != int(github_user["id"])
    ):
        raise HTTPException(
            status_code=403,
            detail="The GitHub account does not match this DevPilot session",
        )
    user = await asyncio.to_thread(upsert_user, github_user)

    for installation in installations:
        await sync_installation_for_user(user["id"], installation)

    destination = FRONTEND_URL if installations else github_install_url()
    response = RedirectResponse(destination, status_code=303)
    if state:
        clear_oauth_state_cookie(response)
    if not current_user:
        session_token = await asyncio.to_thread(create_session, user["id"])
        set_session_cookie(response, session_token)
    return response


@app.get("/auth/session")
async def auth_session(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return {"authenticated": False, "user": None}
    user = await asyncio.to_thread(get_user_for_session, token)
    if not user:
        response = Response(
            content=json.dumps({"authenticated": False, "user": None}),
            media_type="application/json",
        )
        clear_session_cookie(response)
        return response
    return {"authenticated": True, "user": user}


@app.post("/auth/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await asyncio.to_thread(delete_session, token)
    response = Response(
        content=json.dumps({"status": "signed_out"}),
        media_type="application/json",
    )
    clear_session_cookie(response)
    return response


@app.post("/github/webhook")
async def github_webhook(request: Request):
    body = await request.body()
    return await process_github_webhook(
        body,
        request.headers.get("x-hub-signature-256"),
        request.headers.get("x-github-delivery"),
        request.headers.get("x-github-event"),
    )


@app.get("/projects")
def list_projects(user: dict = Depends(require_user)):
    try:
        return list_projects_data(user["id"])
    except Exception as error:
        logger.exception("Project listing failed")
        raise HTTPException(
            status_code=502,
            detail="Project data is unavailable",
        ) from error


@app.post("/projects/sync")
async def sync_projects(user: dict = Depends(require_user)):
    try:
        links = await asyncio.to_thread(
            lambda: (
                supabase.table("user_installations")
                .select("installation_id")
                .eq("user_id", user["id"])
                .execute()
                .data
            )
        )
        results = await asyncio.gather(
            *(
                sync_installation_for_user(
                    user["id"],
                    int(link["installation_id"]),
                )
                for link in links
            ),
            return_exceptions=True,
        )
        if links and all(isinstance(result, Exception) for result in results):
            raise RuntimeError("No GitHub installation could be synchronized")
        return await asyncio.to_thread(list_projects_data, user["id"])
    except Exception as error:
        logger.exception("Project synchronization failed")
        raise HTTPException(
            status_code=502,
            detail="GitHub repositories could not be synchronized",
        ) from error


@app.get("/projects/{project_id}/summary")
def project_summary(
    project_id: str,
    user: dict = Depends(require_user),
):
    try:
        return get_project_summary_data(project_id, user["id"])
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Project summary is unavailable",
        ) from error


@app.get("/projects/{project_id}/tasks")
def project_tasks(
    project_id: str,
    user: dict = Depends(require_user),
):
    try:
        return get_project_tasks_data(project_id, user["id"])
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Project tasks are unavailable",
        ) from error


@app.post("/projects/{project_id}/tasks")
def create_project_task(
    project_id: str,
    body: TaskCreateRequest,
    user: dict = Depends(require_user),
):
    try:
        return create_project_task_data(
            project_id,
            user["id"],
            body.model_dump(),
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="The task could not be created",
        ) from error


@app.get("/projects/{project_id}/activity")
async def project_activity(
    project_id: str,
    user: dict = Depends(require_user),
):
    try:
        return await get_project_activity_data(project_id, user["id"])
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Repository activity is unavailable",
        ) from error


@app.get(
    "/projects/{project_id}/chat/messages",
    response_model=list[ChatHistoryMessage],
)
async def project_chat_messages(
    project_id: str,
    user: dict = Depends(require_user),
):
    try:
        return await asyncio.to_thread(
            list_project_chat_messages,
            project_id,
            user["id"],
        )
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except APIError as error:
        logger.exception("Project chat history database request failed")
        if error.code == "PGRST205":
            raise HTTPException(
                status_code=503,
                detail=(
                    "Chat history storage is not ready. "
                    "Apply database/002_project_chat_history.sql."
                ),
            ) from error
        raise HTTPException(
            status_code=502,
            detail="This project conversation could not be loaded. Try again.",
        ) from error
    except Exception as error:
        logger.exception("Project chat history could not be listed")
        raise HTTPException(
            status_code=502,
            detail="This project conversation could not be loaded. Try again.",
        ) from error


# Chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: dict = Depends(require_user),
):
    try:
        project = await asyncio.to_thread(
            get_project_data,
            body.project_id,
            user["id"],
        )
        history = await asyncio.to_thread(
            load_chat_history_safely,
            body.project_id,
            user["id"],
        )
        async with create_mcp_server(body.project_id, user["id"]) as server:
            agent = build_agent(server)
            conversation = build_agent_conversation(
                project,
                history,
                body.message,
            )
            result = await Runner.run(agent, conversation)
            response = await build_chat_response(
                result,
                body.project_id,
                user["id"],
            )
            await asyncio.to_thread(
                save_chat_message_safely,
                body.project_id,
                user["id"],
                "user",
                body.message,
            )
            if response.status == "completed" and response.answer:
                await asyncio.to_thread(
                    save_chat_message_safely,
                    body.project_id,
                    user["id"],
                    "assistant",
                    response.answer,
                )
            return response
    except Exception as error:
        logger.exception("Chat request failed")
        raise HTTPException(
            status_code=502,
            detail="DevPilot could not complete the request",
        ) from error


@app.post("/chat/approvals/{approval_id}", response_model=ChatResponse)
async def resolve_chat_approval(
    approval_id: str,
    body: ApprovalDecisionRequest,
    user: dict = Depends(require_user),
):
    pending = await approval_store.take(approval_id)
    if pending is None:
        raise HTTPException(
            status_code=410,
            detail="This approval has expired or was already handled",
        )
    if pending.user_id != user["id"]:
        raise HTTPException(status_code=404, detail="Approval request not found")

    interruption_index = pending.request_indexes.get(body.request_id)
    if interruption_index is None:
        raise HTTPException(status_code=404, detail="Approval request not found")

    try:
        async with create_mcp_server(
            pending.project_id,
            user["id"],
        ) as server:
            agent = build_agent(server)
            state = await RunState.from_json(agent, pending.state_json)
            interruptions = state.get_interruptions()
            if interruption_index >= len(interruptions):
                raise ValueError("Approval state no longer matches the request")

            interruption = interruptions[interruption_index]
            if body.decision == "approve":
                state.approve(interruption)
            else:
                state.reject(
                    interruption,
                    rejection_message=(
                        "The user rejected this action in the DevPilot interface. "
                        "Do not retry another write action in this turn."
                    ),
                )

            result = await Runner.run(agent, state)
            response = await build_chat_response(
                result,
                pending.project_id,
                user["id"],
            )
            if response.status == "completed" and response.answer:
                await asyncio.to_thread(
                    save_chat_message_safely,
                    pending.project_id,
                    user["id"],
                    "assistant",
                    response.answer,
                )
            return response
    except Exception as error:
        logger.exception("Approval continuation failed")
        raise HTTPException(
            status_code=502,
            detail=(
                "The approval could not be resumed safely. "
                "Refresh the project before trying again."
            ),
        ) from error
