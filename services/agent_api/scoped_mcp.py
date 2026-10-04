from types import SimpleNamespace
from typing import Any

from agents.mcp import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import (
    CallToolResult,
    GetPromptResult,
    ListPromptsResult,
)

from services.mcp_server.server import mcp as devpilot_mcp


class ProjectScopedMCPServer(MCPServer):
    """In-process MCP adapter with immutable user and project scope."""

    def __init__(
        self,
        *,
        project_id: str,
        user_id: str,
        require_approval: Any = None,
    ) -> None:
        super().__init__(require_approval=require_approval)
        self.headers = {
            "x-devpilot-project-id": project_id,
            "x-devpilot-user-id": user_id,
        }
        self._tools = None

    @property
    def name(self) -> str:
        return "DevPilot MCP"

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.cleanup()

    async def connect(self) -> None:
        return None

    async def cleanup(self) -> None:
        self._tools = None

    def _context(self) -> Context:
        request = SimpleNamespace(headers=self.headers)
        request_context = SimpleNamespace(request=request)
        return Context(
            request_context=request_context,
            mcp_server=devpilot_mcp,
        )

    async def list_tools(self, run_context=None, agent=None):
        if self._tools is None:
            self._tools = await devpilot_mcp.list_tools()
        return self._tools

    @property
    def cached_tools(self):
        return self._tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None,
        meta: dict[str, Any] | None = None,
    ) -> CallToolResult:
        return await devpilot_mcp.call_tool(
            tool_name,
            arguments or {},
            context=self._context(),
        )

    async def list_prompts(self) -> ListPromptsResult:
        prompts = await devpilot_mcp.list_prompts()
        return ListPromptsResult(prompts=prompts)

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> GetPromptResult:
        return await devpilot_mcp.get_prompt(
            name,
            arguments,
            context=self._context(),
        )
