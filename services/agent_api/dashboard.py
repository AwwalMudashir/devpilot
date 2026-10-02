import asyncio

from services.mcp_server.database import supabase
from services.mcp_server.github_client import github_get


def list_projects_data() -> list[dict]:
    return (
        supabase.table("projects")
        .select("id,name,description,github_owner,github_repo,created_at")
        .order("created_at", desc=True)
        .execute()
        .data
    )


def get_project_data(project_id: str) -> dict:
    rows = (
        supabase.table("projects")
        .select("id,name,description,github_owner,github_repo,created_at")
        .eq("id", project_id)
        .limit(1)
        .execute()
        .data
    )

    if not rows:
        raise ValueError("Project not found")

    return rows[0]


def get_project_summary_data(project_id: str) -> dict:
    project = get_project_data(project_id)
    tasks = (
        supabase.table("tasks")
        .select("status")
        .eq("project_id", project_id)
        .execute()
        .data
    )

    counts = {"todo": 0, "in_progress": 0, "blocked": 0, "done": 0}
    for task in tasks:
        status = task.get("status")
        if status in counts:
            counts[status] += 1

    return {"project": project, "task_counts": counts}


def get_project_tasks_data(project_id: str) -> list[dict]:
    get_project_data(project_id)
    return (
        supabase.table("tasks")
        .select("id,title,description,status,priority,due_date")
        .eq("project_id", project_id)
        .order("due_date")
        .execute()
        .data
    )


async def get_project_activity_data(project_id: str) -> dict:
    project = get_project_data(project_id)
    owner = project.get("github_owner")
    repo = project.get("github_repo")

    if not owner or not repo:
        raise ValueError("Project does not have a GitHub repository configured")

    commits_data, issues_data, pulls_data = await asyncio.gather(
        github_get(f"/repos/{owner}/{repo}/commits", params={"per_page": 10}),
        github_get(
            f"/repos/{owner}/{repo}/issues",
            params={"state": "open", "per_page": 30},
        ),
        github_get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "open", "per_page": 20},
        ),
    )

    commits = [
        {
            "sha": item["sha"][:7],
            "message": item["commit"]["message"].splitlines()[0],
            "author": item["commit"]["author"]["name"],
            "date": item["commit"]["author"]["date"],
            "url": item["html_url"],
        }
        for item in commits_data
    ]
    issues = [
        {
            "number": item["number"],
            "title": item["title"],
            "labels": [label["name"] for label in item["labels"]],
            "url": item["html_url"],
        }
        for item in issues_data
        if "pull_request" not in item
    ]
    pull_requests = [
        {
            "number": item["number"],
            "title": item["title"],
            "author": item["user"]["login"],
            "url": item["html_url"],
        }
        for item in pulls_data
    ]

    return {
        "commits": commits,
        "open_issues": issues,
        "open_pull_requests": pull_requests,
    }
