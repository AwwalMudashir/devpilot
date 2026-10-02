import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents import Runner
from agents.mcp import MCPServerStreamableHttp

from services.agent_api.agent import build_agent
from services.agent_api.dashboard import (
    get_project_activity_data,
    get_project_summary_data,
    get_project_tasks_data,
    list_projects_data,
)
from services.agent_api.schemas import ChatRequest, ChatResponse


load_dotenv()

MCP_URL = os.getenv(
    "MCP_SERVER_URL",
    "http://127.0.0.1:8001/mcp",
)


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

    async with MCPServerStreamableHttp(
        name="DevPilot MCP",
        params={
            "url": MCP_URL,
            "timeout": 15,
        },
        require_approval={
            "always": {"tool_names": ["create_task", "update_task_status"]}
        },

        cache_tools_list=True,
    ) as server:

        agent = build_agent(server)

        prompt = (
            f"Active project ID: {body.project_id}\n\n"
            f"User request:\n{body.message}"
        )

        result = await Runner.run(
            agent,
            prompt,
        )

        return ChatResponse(
            answer=result.final_output
        )
