const API_BASE_URL = (
  process.env.NEXT_PUBLIC_AGENT_API_URL || "http://localhost:8000"
).replace(/\/$/, "")

export type TaskStatus = "todo" | "in_progress" | "blocked" | "done"
export type TaskPriority = "low" | "medium" | "high" | "critical"

export type Project = {
  id: string
  name: string
  description: string | null
  github_owner: string | null
  github_repo: string | null
  created_at?: string
}

export type ProjectSummary = {
  project: Project
  task_counts: Record<TaskStatus, number>
}

export type ProjectTask = {
  id: string
  title: string
  description: string | null
  status: TaskStatus
  priority: TaskPriority
  due_date: string | null
}

export type Commit = {
  sha: string
  message: string
  author: string
  date: string
  url: string
}

export type GitHubIssue = {
  number: number
  title: string
  labels: string[]
  url: string
}

export type PullRequest = {
  number: number
  title: string
  author: string
  url: string
}

export type ProjectActivity = {
  commits: Commit[]
  open_issues: GitHubIssue[]
  open_pull_requests: PullRequest[]
}

export type ApprovalRequest = {
  request_id: string
  tool_name: string
  title: string
  description: string
  arguments: Record<string, unknown>
}

export type ChatResult = {
  status: "completed" | "approval_required"
  answer: string | null
  approval_id: string | null
  approvals: ApprovalRequest[]
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers
    }
  })

  if (!response.ok) {
    let message = "The request could not be completed"

    try {
      const data = await response.json()
      if (typeof data.detail === "string") message = data.detail
    } catch {
      message = response.statusText || message
    }

    throw new ApiError(message, response.status)
  }

  return response.json() as Promise<T>
}

export function getProjects() {
  return request<Project[]>("/projects")
}

export function getProjectSummary(projectId: string) {
  return request<ProjectSummary>(`/projects/${projectId}/summary`)
}

export function getProjectTasks(projectId: string) {
  return request<ProjectTask[]>(`/projects/${projectId}/tasks`)
}

export function getProjectActivity(projectId: string) {
  return request<ProjectActivity>(`/projects/${projectId}/activity`)
}

export async function askDevPilot(message: string, projectId: string) {
  return request<ChatResult>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, project_id: projectId })
  })
}

export function decideDevPilotApproval(
  approvalId: string,
  requestId: string,
  decision: "approve" | "reject"
) {
  return request<ChatResult>(`/chat/approvals/${approvalId}`, {
    method: "POST",
    body: JSON.stringify({ request_id: requestId, decision })
  })
}
