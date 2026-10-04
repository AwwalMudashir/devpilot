# DevPilot

DevPilot is a project intelligence dashboard and AI assistant for GitHub repositories. A user connects through a GitHub App, chooses which repositories DevPilot may access, and receives a separate workspace for each selected repository.

Each workspace combines repository activity, GitHub issues, pull requests, DevPilot tasks, and a project-scoped assistant. The assistant can read project data and propose task changes. Every write action requires explicit approval before it is applied.

## What DevPilot does

- Connects users through a GitHub App OAuth flow
- Imports exactly the repositories selected during installation
- Creates a separate dashboard and assistant conversation for each project
- Shows task counts, task details, commits, open issues, and pull requests
- Creates tasks manually or through the assistant
- Updates task status and descriptions through an approval workflow
- Stores the latest 40 chat messages per user and project
- Removes repository access automatically when GitHub sends an installation webhook

## System architecture

```text
Browser
  |
  | HTTPS and HTTP-only session cookie
  v
Next.js frontend
  |
  | /api/devpilot/* rewrite
  v
FastAPI Agent API
  |-- GitHub OAuth and installation sync
  |-- Dashboard and task endpoints
  |-- Chat history and approval continuation
  |-- GitHub webhook verification
  |
  |-- Groq API for model inference
  |-- GitHub API through installation tokens
  |-- In-process, project-scoped MCP tools
  v
Supabase PostgreSQL
```

The browser only communicates with the Next.js origin. Next.js rewrites `/api/devpilot/*` requests to the Agent API. This keeps the OAuth and session cookies on the same origin as the frontend.

The Agent API is the application boundary. It authenticates the user, verifies project ownership, supplies an immutable project scope to the MCP tools, and performs all privileged Supabase and GitHub operations.

## Repository structure

```text
devpilot/
|-- database/                 Supabase migrations
|-- frontend/                 Next.js application
|   |-- app/                  App Router entry point and global styles
|   |-- components/           Dashboard, authentication, task, and chat UI
|   |-- lib/api.ts            Typed frontend API client
|   `-- next.config.ts        Agent API rewrite configuration
|-- services/
|   |-- agent_api/            FastAPI application and assistant orchestration
|   `-- mcp_server/           Project tools, GitHub client, and database client
|-- tests/                    Unit, security, scope, and integration tests
|-- .env.example              Backend environment variable template
`-- README.md
```

## Major modules

### Frontend

| Module | Responsibility |
|---|---|
| `frontend/app/page.tsx` | Renders the DevPilot application entry point |
| `frontend/components/DevPilotApp.tsx` | Loads the current session and selects the signed-in or signed-out experience |
| `frontend/components/ConnectGitHub.tsx` | Explains DevPilot and starts the GitHub connection flow |
| `frontend/components/Dashboard.tsx` | Coordinates projects, metrics, tasks, activity, and assistant layout |
| `frontend/components/ProjectPicker.tsx` | Searches and switches between installed repositories |
| `frontend/components/AgentChat.tsx` | Loads project chat history, sends messages, and renders approvals |
| `frontend/components/TaskCreateDialog.tsx` | Provides manual task creation |
| `frontend/components/MarkdownMessage.tsx` | Safely renders assistant Markdown |
| `frontend/lib/api.ts` | Defines frontend types and calls the same-origin `/api/devpilot` routes |
| `frontend/next.config.ts` | Proxies frontend API requests to `AGENT_API_URL` |

### Agent API

| Module | Responsibility |
|---|---|
| `services/agent_api/main.py` | Defines FastAPI routes, chat execution, and approval continuation |
| `services/agent_api/agent.py` | Configures the Groq-backed DevPilot agent and its response rules |
| `services/agent_api/scoped_mcp.py` | Runs MCP tools in process with fixed user and project headers |
| `services/agent_api/approvals.py` | Stores short-lived approval state and identifies protected write tools |
| `services/agent_api/chat_history.py` | Loads, saves, scopes, and trims project conversations |
| `services/agent_api/dashboard.py` | Reads project summaries, tasks, and GitHub activity for the dashboard |
| `services/agent_api/github_auth.py` | Handles OAuth state, HTTP-only sessions, installations, and repository sync |
| `services/agent_api/github_webhooks.py` | Verifies webhook signatures and processes access changes |
| `services/agent_api/schemas.py` | Defines validated API request and response models |

### MCP and integrations

| Module | Responsibility |
|---|---|
| `services/mcp_server/server.py` | Defines project-scoped read and write tools available to the assistant |
| `services/mcp_server/github_client.py` | Creates GitHub App JWTs and installation tokens, then calls the GitHub API |
| `services/mcp_server/database.py` | Creates the shared server-side Supabase client |

The production Agent API uses `ProjectScopedMCPServer`, so a separate MCP network service is not required. The HTTP MCP app in `server.py` remains available for controlled internal use and requires `MCP_INTERNAL_SECRET`.

## Main application flows

### GitHub connection

1. The frontend opens `/api/devpilot/auth/github/start`.
2. The Agent API creates signed OAuth state and stores it in an HTTP-only cookie.
3. GitHub authorizes the user and returns to the configured callback.
4. The Agent API exchanges the code, identifies the user, and creates a hashed server-side session.
5. GitHub displays its installation screen, where the user selects all repositories or specific repositories.
6. DevPilot requests an installation token and imports only repositories available to that installation.

### Dashboard loading

1. The browser requests the authenticated user's projects.
2. Every project query includes the user ID and ignores revoked repositories.
3. Selecting a project loads only that project's summary, tasks, repository activity, and chat history.
4. The selected project ID is passed into the Agent API and is never chosen by the language model.

### Assistant request

1. The browser sends a message with the active project ID.
2. The Agent API verifies that the project belongs to the signed-in user.
3. The latest 40 messages for that user and project are loaded from Supabase.
4. `ProjectScopedMCPServer` fixes the user and project scope for every tool call.
5. Groq runs the DevPilot agent with the saved conversation and available MCP tools.
6. The final user and assistant messages are saved back to the same project conversation.

### Write approval

The following assistant tools require approval:

- `create_task`
- `update_task_status`
- `update_task_description`

When the model requests one of these tools, execution pauses and the frontend shows the proposed arguments. Approving resumes the saved agent state and executes the tool. Rejecting resumes the state with a rejection result and prevents the change.

Pending approvals are held in memory for ten minutes. A process restart or free-host cold restart removes pending approvals, but completed tasks and chat messages remain in Supabase.

### Repository access changes

GitHub sends signed `installation` and `installation_repositories` events to `/github/webhook`. DevPilot verifies the HMAC signature, rejects duplicate delivery IDs, updates the installation, and marks projects as revoked when repository access is removed.

## Project isolation and security

- The model never supplies a project ID to an MCP tool
- The Agent API derives user identity from an HTTP-only session cookie
- Project queries verify both `project_id` and `user_id`
- Task updates also filter by the active project ID
- GitHub private keys, client secrets, Supabase server keys, and Groq keys stay on the backend
- GitHub installation tokens are short-lived and cached only in memory
- OAuth state is signed and expires after ten minutes
- Session tokens are hashed before storage
- GitHub webhook bodies are verified with HMAC-SHA256
- Repository removals are reflected through verified webhooks

## Database

DevPilot uses Supabase PostgreSQL. The foundational schema contains `projects`, `tasks`, and `project_documents`. The migrations in this repository extend that schema:

| Migration | Purpose |
|---|---|
| `database/001_github_app_auth.sql` | Adds users, sessions, installations, ownership, and webhook delivery records |
| `database/002_project_chat_history.sql` | Adds project-scoped chat messages and the 40-message retention trigger |

Run the migrations in numeric order through the Supabase SQL Editor. The service-role or secret key must only be configured on the backend.

## Environment variables

Copy `.env.example` to `.env` for local backend development.

### Required backend values

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Authenticates model requests |
| `SUPABASE_URL` | Identifies the Supabase project |
| `SUPABASE_SERVICE_ROLE_KEY` | Gives the backend server access to protected tables |
| `GITHUB_APP_ID` | Identifies the GitHub App for signed app JWTs |
| `GITHUB_APP_SLUG` | Builds the GitHub App installation URL |
| `GITHUB_APP_CLIENT_ID` | Starts GitHub user authorization |
| `GITHUB_APP_CLIENT_SECRET` | Exchanges OAuth codes for user tokens |
| `GITHUB_APP_PRIVATE_KEY_PATH` | Points to the GitHub App PEM file |
| `GITHUB_APP_WEBHOOK_SECRET` | Verifies GitHub webhook signatures |
| `APP_SESSION_SECRET` | Signs OAuth state and hashes session tokens |
| `FRONTEND_URL` | Defines the trusted frontend origin |
| `GITHUB_CALLBACK_URL` | Must exactly match a GitHub App callback URL |

### Optional backend values

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI-compatible model endpoint |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Model used by the DevPilot agent |
| `MCP_INTERNAL_SECRET` | `APP_SESSION_SECRET` | Protects the optional standalone HTTP MCP endpoint |

### Frontend value

Create `frontend/.env.local`:

```env
AGENT_API_URL=http://127.0.0.1:8000
```

`AGENT_API_URL` is read by Next.js on the server to build the `/api/devpilot` rewrite. It should be the Agent API origin without `/api/devpilot`, `/health`, or a trailing slash.

## Local development

### Prerequisites

- Python 3.13
- Node.js 20 or newer
- A Supabase project with the schema and migrations applied
- A GitHub App with OAuth, repository permissions, and active webhooks
- A Groq API key

### Start the Agent API

From the repository root in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r services\requirements.txt
uvicorn services.agent_api.main:app --reload --host 127.0.0.1 --port 8000
```

Verify it at `http://127.0.0.1:8000/health`.
The endpoint accepts both `GET` and `HEAD`, so it can be used by browser checks,
Render health checks, and uptime monitors.

### Start the frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

The local GitHub callback is:

```text
http://localhost:3000/api/devpilot/auth/github/callback
```

## Testing

Run backend unit tests from the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_chat_history tests.test_project_scope tests.test_github_security -v
```

Run the frontend checks:

```powershell
cd frontend
npm run lint
npm run build
```

The live assistant integration test is opt-in because it creates temporary Supabase records and calls the configured model:

```powershell
$env:RUN_DEVPILOT_AGENT_TESTS = "1"
$env:DEVPILOT_AGENT_TEST_URL = "http://localhost:3000/api/devpilot"
.\.venv\Scripts\python.exe -m unittest tests.test_agent_task_integration -v
```

## Deployment

A simple production deployment uses:

- Vercel for `frontend/`
- Render for the FastAPI Agent API
- The existing hosted Supabase project

Render configuration from the repository root:

```text
Build command: pip install -r services/requirements.txt
Start command: uvicorn services.agent_api.main:app --host 0.0.0.0 --port $PORT
Health check: /health
```

Upload the GitHub PEM as a Render secret file named `github-app.pem` and set:

```text
GITHUB_APP_PRIVATE_KEY_PATH=/etc/secrets/github-app.pem
```

Set Vercel's `AGENT_API_URL` to the Render service origin, then redeploy Vercel so the production rewrite is rebuilt.

Production URL mapping:

```text
GitHub homepage:       https://<frontend-domain>
GitHub callback:       https://<frontend-domain>/api/devpilot/auth/github/callback
GitHub webhook:        https://<agent-api-domain>/github/webhook
Render FRONTEND_URL:   https://<frontend-domain>
Render callback URL:   https://<frontend-domain>/api/devpilot/auth/github/callback
Vercel AGENT_API_URL:  https://<agent-api-domain>
```

## Operational notes

- Render free services may sleep when idle, so the first request after inactivity can be slow
- Chat history and completed task changes survive restarts because they are stored in Supabase
- Pending approval state does not survive an Agent API restart
- Environment variable changes on Vercel require a redeploy
- GitHub callback URLs must match exactly
- The GitHub webhook must be active and use the same secret configured on the Agent API

