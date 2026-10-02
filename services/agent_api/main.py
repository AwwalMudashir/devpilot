import os
import json
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents import RunState, Runner
from agents.mcp import MCPServerStreamableHttp

from services.agent_api.agent import build_agent
from services.agent_api.approvals import approval_store
from services.agent_api.dashboard import (
    get_project_activity_data,
    get_project_summary_data,
    get_project_tasks_data,
    list_projects_data,
)
from services.agent_api.schemas import (
    ApprovalDecisionRequest,
    ApprovalRequest,
    ChatRequest,
    ChatResponse,
)


load_dotenv()

MCP_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://127.0.0.1:8001/mcp",
)

WRITE_TOOL_NAMES = ["create_task", "update_task_status"]


# FastAPI application
app = FastAPI(
    title="DevPilot Agent API",
    version="1.0.0",
)


# CORS

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def create_mcp_server() -> MCPServerStreamableHttp:
    return MCPServerStreamableHttp(
        name="DevPilot MCP",
        params={
            "url": MCP_URL,
            "timeout": 15,
        },
        require_approval={
            "always": {"tool_names": WRITE_TOOL_NAMES}
        },
        cache_tools_list=True,
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


async def build_chat_response(result, project_id: str) -> ChatResponse:
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


@app.get("/projects")
def list_projects():
    try:
        return list_projects_data()
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Project data is unavailable",
        ) from error


@app.get("/projects/{project_id}/summary")
def project_summary(project_id: str):
    try:
        return get_project_summary_data(project_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Project summary is unavailable",
        ) from error


@app.get("/projects/{project_id}/tasks")
def project_tasks(project_id: str):
    try:
        return get_project_tasks_data(project_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Project tasks are unavailable",
        ) from error


@app.get("/projects/{project_id}/activity")
async def project_activity(project_id: str):
    try:
        return await get_project_activity_data(project_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="Repository activity is unavailable",
        ) from error


# Chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    try:
        async with create_mcp_server() as server:
            agent = build_agent(server)
            prompt = (
                f"Active project ID: {body.project_id}\n\n"
                f"User request:\n{body.message}"
            )
            result = await Runner.run(agent, prompt)
            return await build_chat_response(result, body.project_id)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="DevPilot could not complete the request",
        ) from error


@app.post("/chat/approvals/{approval_id}", response_model=ChatResponse)
async def resolve_chat_approval(
    approval_id: str,
    body: ApprovalDecisionRequest,
):
    pending = await approval_store.take(approval_id)
    if pending is None:
        raise HTTPException(
            status_code=410,
            detail="This approval has expired or was already handled",
        )

    interruption_index = pending.request_indexes.get(body.request_id)
    if interruption_index is None:
        raise HTTPException(status_code=404, detail="Approval request not found")

    try:
        async with create_mcp_server() as server:
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
            return await build_chat_response(result, pending.project_id)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "The approval could not be resumed safely. "
                "Refresh the project before trying again."
            ),
        ) from error
