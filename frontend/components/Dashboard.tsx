"use client"

import { useEffect, useMemo, useState } from "react"
import { AgentChat } from "@/components/AgentChat"
import { Icon, type IconName } from "@/components/Icon"
import { ProjectPicker } from "@/components/ProjectPicker"
import { TaskCreateDialog } from "@/components/TaskCreateDialog"
import {
  getProjectActivity,
  getProjects,
  getProjectSummary,
  getProjectTasks,
  type AuthUser,
  type Project,
  type ProjectActivity,
  type ProjectSummary,
  type ProjectTask,
  type TaskStatus
} from "@/lib/api"

type TaskFilter = "all" | TaskStatus

const emptyActivity: ProjectActivity = {
  commits: [],
  open_issues: [],
  open_pull_requests: []
}

const statusLabels: Record<TaskStatus, string> = {
  todo: "To do",
  in_progress: "In progress",
  blocked: "Blocked",
  done: "Done"
}

const priorityLabels = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical"
}

function formatDate(value: string | null) {
  if (!value) return "No due date"

  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short"
  }).format(new Date(`${value}T00:00:00`))
}

function formatActivityDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric"
  }).format(new Date(value))
}

function MetricCard({
  icon,
  label,
  value,
  note,
  tone = "neutral"
}: {
  icon: IconName
  label: string
  value: number
  note: string
  tone?: "neutral" | "good" | "warning" | "info"
}) {
  return (
    <article className={`metricCard metric-${tone}`}>
      <div className="metricTopline">
        <span className="metricIcon"><Icon name={icon} size={18} /></span>
        <span className="metricLabel">{label}</span>
      </div>
      <strong>{value}</strong>
      <p>{note}</p>
    </article>
  )
}

function WorkspaceSkeleton() {
  return (
    <div className="dashboardSkeleton" aria-label="Loading project workspace">
      <div className="skeleton skeletonHeading" />
      <div className="skeletonMetrics">
        {[0, 1, 2, 3].map((item) => <div className="skeleton skeletonCard" key={item} />)}
      </div>
      <div className="skeleton skeletonPanel" />
    </div>
  )
}

export function Dashboard({
  onSignOut,
  user
}: {
  onSignOut: () => void
  user: AuthUser
}) {
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProjectId, setSelectedProjectId] = useState("")
  const [summary, setSummary] = useState<ProjectSummary | null>(null)
  const [tasks, setTasks] = useState<ProjectTask[]>([])
  const [activity, setActivity] = useState<ProjectActivity>(emptyActivity)
  const [taskFilter, setTaskFilter] = useState<TaskFilter>("all")
  const [loadingProjects, setLoadingProjects] = useState(true)
  const [loadingWorkspace, setLoadingWorkspace] = useState(false)
  const [projectError, setProjectError] = useState<string | null>(null)
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)
  const [activityError, setActivityError] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [taskDialogOpen, setTaskDialogOpen] = useState(false)
  const [chatExpanded, setChatExpanded] = useState(false)
  const [composeRequest, setComposeRequest] = useState<{ id: number; text: string } | null>(null)

  useEffect(() => {
    let active = true

    async function loadProjects() {
      try {
        const data = await getProjects()
        if (!active) return
        setProjects(data)
        if (data.length > 0) setLoadingWorkspace(true)
        setSelectedProjectId((current) => {
          if (current) return current
          const savedProjectId = window.localStorage.getItem("devpilot:selected-project")
          return data.find((project) => project.id === savedProjectId)?.id || data[0]?.id || ""
        })
      } catch (error) {
        if (!active) return
        setProjectError(error instanceof Error ? error.message : "Projects could not be loaded")
      } finally {
        if (active) setLoadingProjects(false)
      }
    }

    void loadProjects()
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!chatExpanded) return

    function restoreDashboard(event: KeyboardEvent) {
      if (event.key === "Escape") setChatExpanded(false)
    }

    window.addEventListener("keydown", restoreDashboard)
    return () => window.removeEventListener("keydown", restoreDashboard)
  }, [chatExpanded])

  async function loadWorkspace() {
    if (!selectedProjectId) return

    setLoadingWorkspace(true)
    setWorkspaceError(null)
    setActivityError(false)

    const [summaryResult, tasksResult, activityResult] = await Promise.allSettled([
      getProjectSummary(selectedProjectId),
      getProjectTasks(selectedProjectId),
      getProjectActivity(selectedProjectId)
    ])

    if (summaryResult.status === "fulfilled" && tasksResult.status === "fulfilled") {
      setSummary(summaryResult.value)
      setTasks(tasksResult.value)
      setLastUpdated(new Intl.DateTimeFormat("en", {
        hour: "numeric",
        minute: "2-digit"
      }).format(new Date()))
    } else {
      const reason = summaryResult.status === "rejected"
        ? summaryResult.reason
        : tasksResult.status === "rejected"
          ? tasksResult.reason
          : null
      setWorkspaceError(reason instanceof Error ? reason.message : "Project data could not be loaded")
    }

    if (activityResult.status === "fulfilled") {
      setActivity(activityResult.value)
    } else {
      setActivity(emptyActivity)
      setActivityError(true)
    }

    setLoadingWorkspace(false)
  }

  useEffect(() => {
    if (!selectedProjectId) return

    let active = true
    const requests = Promise.allSettled([
      getProjectSummary(selectedProjectId),
      getProjectTasks(selectedProjectId),
      getProjectActivity(selectedProjectId)
    ])

    void requests.then(([summaryResult, tasksResult, activityResult]) => {
      if (!active) return

      if (summaryResult.status === "fulfilled" && tasksResult.status === "fulfilled") {
        setSummary(summaryResult.value)
        setTasks(tasksResult.value)
        setLastUpdated(new Intl.DateTimeFormat("en", {
          hour: "numeric",
          minute: "2-digit"
        }).format(new Date()))
      } else {
        const reason = summaryResult.status === "rejected"
          ? summaryResult.reason
          : tasksResult.status === "rejected"
            ? tasksResult.reason
            : null
        setWorkspaceError(reason instanceof Error ? reason.message : "Project data could not be loaded")
      }

      if (activityResult.status === "fulfilled") {
        setActivity(activityResult.value)
      } else {
        setActivity(emptyActivity)
        setActivityError(true)
      }

      setLoadingWorkspace(false)
    })

    return () => { active = false }
  }, [selectedProjectId])

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === selectedProjectId) || summary?.project || null,
    [projects, selectedProjectId, summary]
  )

  const filteredTasks = useMemo(
    () => taskFilter === "all" ? tasks : tasks.filter((task) => task.status === taskFilter),
    [taskFilter, tasks]
  )

  const totalTasks = summary
    ? Object.values(summary.task_counts).reduce((total, count) => total + count, 0)
    : tasks.length
  const completion = totalTasks > 0
    ? Math.round(((summary?.task_counts.done || 0) / totalTasks) * 100)
    : 0

  function scrollToSection(id: string) {
    if (chatExpanded && id !== "assistant") {
      setChatExpanded(false)
      requestAnimationFrame(() => {
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
      })
      return
    }
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  function changeProject(projectId: string) {
    setLoadingWorkspace(true)
    setWorkspaceError(null)
    setActivityError(false)
    setSummary(null)
    setTasks([])
    setActivity(emptyActivity)
    setTaskFilter("all")
    setSelectedProjectId(projectId)
    window.localStorage.setItem("devpilot:selected-project", projectId)
  }

  function handleTaskCreated(task: ProjectTask) {
    setTasks((current) => [...current, task])
    setSummary((current) => current ? {
      ...current,
      task_counts: {
        ...current.task_counts,
        todo: current.task_counts.todo + 1
      }
    } : current)
    setTaskFilter("all")
  }

  function composeTaskWithDevPilot() {
    setComposeRequest({
      id: Date.now(),
      text: "Help me create a task for this project"
    })
    if (window.matchMedia("(max-width: 1320px)").matches) {
      document.getElementById("assistant")?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      })
    }
  }

  if (loadingProjects) return <WorkspaceSkeleton />

  if (projectError) {
    return (
      <main className="fullPageState">
        <div className="stateCard">
          <span className="stateIcon"><Icon name="circleAlert" size={24} /></span>
          <h1>DevPilot is not connected</h1>
          <p>{projectError}</p>
          <p className="stateHint">Start the Agent API on port 8000, then reload this page.</p>
          <button onClick={() => window.location.reload()} type="button">
            <Icon name="refresh" size={17} />
            Try again
          </button>
        </div>
      </main>
    )
  }

  if (!selectedProject) {
    return (
      <main className="fullPageState">
        <div className="stateCard">
          <span className="stateIcon"><Icon name="github" size={24} /></span>
          <h1>No repositories selected</h1>
          <p>Choose the GitHub repositories you want DevPilot to access.</p>
          <a className="stateAction" href="/api/devpilot/auth/github/manage">
            <Icon name="github" size={17} />
            Choose repositories
          </a>
          <button className="stateSecondaryAction" onClick={onSignOut} type="button">
            Sign out
          </button>
        </div>
      </main>
    )
  }

  const repositoryName = selectedProject.github_owner && selectedProject.github_repo
    ? `${selectedProject.github_owner}/${selectedProject.github_repo}`
    : "Repository not linked"

  return (
    <div className={`appShell${chatExpanded ? " chatFocus" : ""}`}>
      <aside className="sidebar">
        <div className="brand">
          <span className="brandMark"><Icon name="command" size={22} /></span>
          <div>
            <strong>DevPilot</strong>
            <span>Project intelligence</span>
          </div>
        </div>

        <div className="sidebarSection">
          <span className="sidebarLabel">Project</span>
          <ProjectPicker
            onChange={changeProject}
            projects={projects}
            selectedProjectId={selectedProjectId}
          />
        </div>

        <nav className="sideNav" aria-label="Workspace navigation">
          <button className="active" onClick={() => scrollToSection("overview")} type="button">
            <Icon name="dashboard" size={18} />
            Overview
          </button>
          <button onClick={() => scrollToSection("tasks")} type="button">
            <Icon name="tasks" size={18} />
            Tasks
            <span>{totalTasks}</span>
          </button>
          <button onClick={() => scrollToSection("activity")} type="button">
            <Icon name="branch" size={18} />
            Activity
          </button>
          <button onClick={() => scrollToSection("assistant")} type="button">
            <Icon name="message" size={18} />
            Assistant
          </button>
        </nav>

        <div className="sidebarFooter">
          <div className="accountSummary">
            <span className="accountInitial">
              {user.github_login.charAt(0).toUpperCase()}
            </span>
            <div>
              <strong>{user.github_name || user.github_login}</strong>
              <span>@{user.github_login}</span>
            </div>
            <button aria-label="Sign out" onClick={onSignOut} title="Sign out" type="button">
              <Icon name="logOut" size={17} />
            </button>
          </div>
        </div>
      </aside>

      <div className="mobileTopbar">
        <div className="brand compact">
          <span className="brandMark"><Icon name="command" size={20} /></span>
          <strong>DevPilot</strong>
        </div>
        <ProjectPicker
          compact
          onChange={changeProject}
          projects={projects}
          selectedProjectId={selectedProjectId}
        />
        <button
          aria-label="Sign out"
          className="mobileSignOut"
          onClick={onSignOut}
          title="Sign out"
          type="button"
        >
          <Icon name="logOut" size={18} />
        </button>
      </div>

      <main className="mainContent">
        <header className="pageHeader" id="overview">
          <div>
            <p className="eyebrow">Project overview</p>
            <h1>{selectedProject.name}</h1>
            <p className="projectDescription">
              {selectedProject.description || "No project description has been added yet."}
            </p>
          </div>
          <div className="headerActions">
            <div className="repositoryBadge">
              <Icon name="github" size={17} />
              <span>{repositoryName}</span>
            </div>
            <button
              aria-label="Refresh project data"
              className="refreshButton"
              disabled={loadingWorkspace}
              onClick={() => void loadWorkspace()}
              title="Refresh project data"
              type="button"
            >
              <Icon className={loadingWorkspace ? "spinning" : ""} name="refresh" size={18} />
            </button>
          </div>
        </header>

        {loadingWorkspace && !summary ? (
          <WorkspaceSkeleton />
        ) : workspaceError ? (
          <div className="inlineError" role="alert">
            <Icon name="circleAlert" size={19} />
            <div>
              <strong>Project data could not be loaded</strong>
              <p>{workspaceError}</p>
            </div>
            <button onClick={() => void loadWorkspace()} type="button">Retry</button>
          </div>
        ) : (
          <div className={`workspaceGrid${chatExpanded ? " workspaceGrid-chatExpanded" : ""}`}>
            <div className="dashboardColumn">
              <section className="metricGrid" aria-label="Project metrics">
                <MetricCard icon="list" label="Total tasks" note={`${completion}% complete`} value={totalTasks} />
                <MetricCard icon="check" label="Completed" note="Ready to close" tone="good" value={summary?.task_counts.done || 0} />
                <MetricCard
                  icon="circleAlert"
                  label="Blocked"
                  note={(summary?.task_counts.blocked || 0) > 0 ? "Needs attention" : "No blockers"}
                  tone="warning"
                  value={summary?.task_counts.blocked || 0}
                />
                <MetricCard
                  icon="github"
                  label="Open issues"
                  note={activityError ? "GitHub unavailable" : "From GitHub"}
                  tone="info"
                  value={activity.open_issues.length}
                />
              </section>

              <section className="contentPanel taskPanel" id="tasks">
                <div className="panelHeader">
                  <div>
                    <h2>Tasks</h2>
                    <p>Current work across the project</p>
                  </div>
                  <div className="panelHeaderActions">
                    <span className="panelCount">{filteredTasks.length} shown</span>
                    <button className="compactButton" onClick={() => setTaskDialogOpen(true)} type="button">
                      <Icon name="plus" size={15} />
                      New task
                    </button>
                  </div>
                </div>

                <div className="filterTabs" role="tablist" aria-label="Filter tasks">
                  {(["all", "in_progress", "blocked", "todo", "done"] as TaskFilter[]).map((filter) => (
                    <button
                      aria-selected={taskFilter === filter}
                      className={taskFilter === filter ? "active" : ""}
                      key={filter}
                      onClick={() => setTaskFilter(filter)}
                      role="tab"
                      type="button"
                    >
                      {filter === "all" ? "All" : statusLabels[filter]}
                    </button>
                  ))}
                </div>

                <div className="taskList">
                  {tasks.length === 0 ? (
                    <div className="emptyPanel taskEmptyState">
                      <span className="emptyPanelIcon"><Icon name="tasks" size={23} /></span>
                      <strong>No tasks yet</strong>
                      <p>Create the first task manually or ask DevPilot to prepare it with you.</p>
                      <div className="emptyTaskActions">
                        <button className="primaryButton" onClick={() => setTaskDialogOpen(true)} type="button">
                          <Icon name="plus" size={16} />
                          Create task
                        </button>
                        <button onClick={composeTaskWithDevPilot} type="button">
                          <Icon name="spark" size={16} />
                          Create with DevPilot
                        </button>
                      </div>
                    </div>
                  ) : filteredTasks.length === 0 ? (
                    <div className="emptyPanel">
                      <Icon name="check" size={22} />
                      <strong>No tasks in this view</strong>
                      <p>Choose another status to see more work.</p>
                    </div>
                  ) : (
                    filteredTasks.map((task) => (
                      <article className="taskRow" key={task.id}>
                        <span className={`taskState state-${task.status}`} aria-label={statusLabels[task.status]}>
                          {task.status === "done" && <Icon name="check" size={13} />}
                        </span>
                        <div className="taskDetails">
                          <h3>{task.title}</h3>
                          {task.description && <p>{task.description}</p>}
                          <div className="taskMeta">
                            <span className={`priority priority-${task.priority}`}>
                              {priorityLabels[task.priority]}
                            </span>
                            <span><Icon name="clock" size={14} /> {formatDate(task.due_date)}</span>
                          </div>
                        </div>
                        <span className={`statusLabel label-${task.status}`}>{statusLabels[task.status]}</span>
                      </article>
                    ))
                  )}
                </div>
              </section>

              <section className="contentPanel activityPanel" id="activity">
                <div className="panelHeader">
                  <div>
                    <h2>Recent activity</h2>
                    <p>Latest commits in the linked repository</p>
                  </div>
                  {selectedProject.github_owner && selectedProject.github_repo && (
                    <a
                      className="textLink"
                      href={`https://github.com/${selectedProject.github_owner}/${selectedProject.github_repo}`}
                      rel="noreferrer"
                      target="_blank"
                    >
                      Open repository <Icon name="external" size={14} />
                    </a>
                  )}
                </div>

                {activityError ? (
                  <div className="emptyPanel compactEmpty">
                    <Icon name="github" size={22} />
                    <strong>Repository activity is unavailable</strong>
                    <p>Check the GitHub token and repository settings.</p>
                  </div>
                ) : activity.commits.length === 0 ? (
                  <div className="emptyPanel compactEmpty">
                    <Icon name="branch" size={22} />
                    <strong>No recent commits</strong>
                    <p>New commits will appear here.</p>
                  </div>
                ) : (
                  <div className="activityList">
                    {activity.commits.slice(0, 5).map((commit) => (
                      <a className="activityRow" href={commit.url} key={commit.sha} rel="noreferrer" target="_blank">
                        <span className="activityIcon"><Icon name="branch" size={16} /></span>
                        <div>
                          <strong>{commit.message}</strong>
                          <p>{commit.author} committed on {formatActivityDate(commit.date)}</p>
                        </div>
                        <code>{commit.sha}</code>
                      </a>
                    ))}
                  </div>
                )}
              </section>

              <p className="lastUpdated">
                {lastUpdated ? `Last refreshed at ${lastUpdated}` : "Project data has not been refreshed"}
              </p>
            </div>

            <AgentChat
              composeRequest={composeRequest}
              expanded={chatExpanded}
              key={selectedProject.id}
              onProjectUpdated={() => void loadWorkspace()}
              onToggleExpanded={() => setChatExpanded((current) => !current)}
              projectId={selectedProject.id}
              projectName={selectedProject.name}
            />
          </div>
        )}
      </main>

      {taskDialogOpen && (
        <TaskCreateDialog
          onClose={() => setTaskDialogOpen(false)}
          onCreated={handleTaskCreated}
          projectId={selectedProject.id}
          projectName={selectedProject.name}
        />
      )}
    </div>
  )
}
