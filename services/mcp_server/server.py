from mcp.server import MCPServer
from typing import Literal
from services.mcp_server.database import supabase
from datetime import date
from services.mcp_server.github_client import github_get



mcp = MCPServer("DevPilot MCP")
Status = Literal["todo", "in_progress", "blocked", "done"]
Priority = Literal["low", "medium", "high", "critical"]


@mcp.tool()
def ping() -> dict:
    """Check whether the DevPilot MCP server is healthy."""
    return {"status": "ok", "service": "devpilot-mcp"}


@mcp.tool()
def get_project_tasks( project_id: str, status: Status | None = None) -> list[dict]:
    """Return tasks for a project. Optionally filter by task status."""
    query = (
        supabase.table("tasks")
        .select("id,title,description,status,priority,due_date")
        .eq("project_id", project_id)
        .order("due_date")
    )

    if status is not None:
        query = query.eq("status", status)

    return query.execute().data


@mcp.tool()
def get_overdue_tasks(project_id: str) -> list[dict]:
    """Return incomplete project tasks whose due date is before today."""
    return (
        supabase.table("tasks")
        .select("id,title,status,priority,due_date")
        .eq("project_id", project_id)
        .lt("due_date", date.today().isoformat())
        .neq("status", "done")
        .order("due_date")
        .execute()
        .data
    )


@mcp.tool()
def create_task(
    project_id: str,
    title: str,
    description: str | None = None,
    priority: Priority = "medium",
    due_date: str | None = None,
) -> dict:
    """Create a task for a project and return the created record."""
    payload = {
        "project_id": project_id,
        "title": title,
        "description": description,
        "priority": priority,
        "due_date": due_date,
    }
    rows = supabase.table("tasks").insert(payload).execute().data
    return rows[0]


@mcp.tool()
def update_task_status(task_id: str, status: Status) -> dict:
    """Update the status of an existing project task."""
    rows = (
        supabase.table("tasks")
        .update({"status": status})
        .eq("id", task_id)
        .execute()
        .data
    )
    if not rows:
        raise ValueError("Task not found")
    return rows[0]


@mcp.tool()
def get_project_summary(project_id: str) -> dict:
    """Return project details and task counts grouped by status."""
    project_rows = (
        supabase.table("projects")
        .select("id,name,description,github_owner,github_repo")
        .eq("id", project_id)
        .limit(1)
        .execute()
        .data
    )

    if not project_rows:
        raise ValueError("Project not found")

    tasks = (
        supabase.table("tasks")
        .select("status")
        .eq("project_id", project_id)
        .execute()
        .data
    )

    counts = {"todo": 0, "in_progress": 0, "blocked": 0, "done": 0}
    for task in tasks:
        counts[task["status"]] += 1

    return {"project": project_rows[0], "task_counts": counts}


def get_repo_for_project(project_id: str) -> tuple[str, str]:
    rows = (
        supabase.table("projects")
        .select("github_owner,github_repo")
        .eq("id", project_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows or not rows[0].get("github_owner"):
        raise ValueError("Project does not have a GitHub repository configured")
    return rows[0]["github_owner"], rows[0]["github_repo"]


@mcp.tool()
async def get_recent_commits(project_id: str, limit: int = 10) -> list[dict]:
    """Return recent commits for the GitHub repository linked to a project."""
    owner, repo = get_repo_for_project(project_id)
    data = await github_get(
        f"/repos/{owner}/{repo}/commits",
        params={"per_page": min(limit, 30)},
    )
    return [
        {
            "sha": item["sha"][:7],
            "message": item["commit"]["message"].splitlines()[0],
            "author": item["commit"]["author"]["name"],
            "date": item["commit"]["author"]["date"],
            "url": item["html_url"],
        }
        for item in data
    ]


@mcp.tool()
async def get_open_issues(project_id: str, limit: int = 20) -> list[dict]:
    """Return open GitHub issues for the project repository."""
    owner, repo = get_repo_for_project(project_id)
    data = await github_get(
        f"/repos/{owner}/{repo}/issues",
        params={"state": "open", "per_page": min(limit, 50)},
    )
    # GitHub's Issues API can also return pull requests.
    issues = [item for item in data if "pull_request" not in item]
    return [
        {
            "number": item["number"],
            "title": item["title"],
            "labels": [label["name"] for label in item["labels"]],
            "url": item["html_url"],
        }
        for item in issues
    ]


@mcp.tool()
async def get_open_pull_requests(project_id: str) -> list[dict]:
    """Return currently open pull requests for the project repository."""
    owner, repo = get_repo_for_project(project_id)
    data = await github_get(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": "open", "per_page": 20},
    )
    return [
        {
            "number": pr["number"],
            "title": pr["title"],
            "author": pr["user"]["login"],
            "url": pr["html_url"],
        }
        for pr in data
    ]


def load_document(project_id: str, kind: str) -> str:
    rows = (
        supabase.table("project_documents")
        .select("content")
        .eq("project_id", project_id)
        .eq("kind", kind)
        .limit(1)
        .execute()
        .data
    )
    return rows[0]["content"] if rows else "Document not found."

@mcp.resource(
    "project://{project_id}/requirements",
    mime_type="text/markdown",
)
def project_requirements(project_id: str) -> str:
    """Read the project requirements document."""
    return load_document(project_id, "requirements")

@mcp.resource(
    "project://{project_id}/architecture",
    mime_type="text/markdown",
)
def project_architecture(project_id: str) -> str:
    """Read the project architecture document."""
    return load_document(project_id, "architecture")


@mcp.tool()
def search_project_docs(project_id: str, query: str) -> list[dict]:
    """Search stored project documents for a keyword or short phrase."""
    rows = (
        supabase.table("project_documents")
        .select("kind,title,content")
        .eq("project_id", project_id)
        .ilike("content", f"%{query}%")
        .limit(5)
        .execute()
        .data
    )
    return [
        {
            "kind": row["kind"],
            "title": row["title"],
            "excerpt": row["content"][:1000],
        }
        for row in rows
    ]



app = mcp.streamable_http_app()
