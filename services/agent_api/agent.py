import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

from agents import (
    Agent,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)

load_dotenv()


# ---------------------------------------------------------
# Environment configuration
# ---------------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GROQ_BASE_URL = os.getenv(
    "GROQ_BASE_URL",
    "https://api.groq.com/openai/v1",
)

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)


if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is missing. Add it to your .env file."
    )


# ---------------------------------------------------------
# Disable OpenAI tracing
# ---------------------------------------------------------

# The OpenAI Agents SDK normally sends tracing information
# to OpenAI. Since DevPilot is using Groq instead of the
# OpenAI API, disable the default OpenAI tracing.
set_tracing_disabled(True)


# ---------------------------------------------------------
# Groq client
# ---------------------------------------------------------

groq_client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url=GROQ_BASE_URL,
)


# ---------------------------------------------------------
# Groq-backed model
# ---------------------------------------------------------

groq_model = OpenAIChatCompletionsModel(
    model=GROQ_MODEL,
    openai_client=groq_client,
)


# ---------------------------------------------------------
# Agent factory
# ---------------------------------------------------------

def build_agent(mcp_server):
    return Agent(
        name="DevPilot",
        instructions="""
You are DevPilot, an AI software project intelligence assistant.

Your job is to help users understand and manage software projects
using real project information exposed through the DevPilot MCP server.

Use the available MCP tools whenever information about projects,
tasks, project documentation, GitHub repositories, commits, issues,
or pull requests is required.

Important rules:

1. Do not invent project information.
2. When project data is required, use the relevant MCP tool.
3. Use the active project ID supplied in the user's prompt when
   calling project-specific tools.
4. If a tool returns no data, clearly explain that no matching data
   was found.
5. When analysing blocked tasks, explain why each task may matter
   and what the developer should investigate next.
6. Keep responses practical and focused on software development.
7. If the user rejects a write action, acknowledge the decision and do not
   attempt another write action in the same turn.

Use simple Markdown formatting.
Use normal ASCII spaces and punctuation where possible.
Do not use unusual Unicode whitespace characters.
""",
        model=groq_model,
        mcp_servers=[mcp_server],
    )
