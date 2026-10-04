from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    project_id: str = Field(min_length=1)


class ApprovalRequest(BaseModel):
    request_id: str
    tool_name: str
    title: str
    description: str
    arguments: dict[str, Any]


class ChatResponse(BaseModel):
    status: Literal["completed", "approval_required"]
    answer: str | None = None
    approval_id: str | None = None
    approvals: list[ApprovalRequest] = Field(default_factory=list)


class ChatHistoryMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class ApprovalDecisionRequest(BaseModel):
    request_id: str = Field(min_length=1)
    decision: Literal["approve", "reject"]


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    due_date: str | None = None


