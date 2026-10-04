"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { Icon } from "@/components/Icon"
import type { Project } from "@/lib/api"

export function ProjectPicker({
  projects,
  selectedProjectId,
  onChange,
  compact = false
}: {
  projects: Project[]
  selectedProjectId: string
  onChange: (projectId: string) => void
  compact?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const rootRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const selectedProject = projects.find((project) => project.id === selectedProjectId)
  const filteredProjects = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    if (!normalizedQuery) return projects

    return projects.filter((project) => (
      project.name.toLowerCase().includes(normalizedQuery) ||
      `${project.github_owner || ""}/${project.github_repo || ""}`
        .toLowerCase()
        .includes(normalizedQuery)
    ))
  }, [projects, query])

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false)
    }

    document.addEventListener("pointerdown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [])

  function selectProject(projectId: string) {
    onChange(projectId)
    setOpen(false)
  }

  function togglePicker() {
    const nextOpen = !open
    setOpen(nextOpen)
    if (!nextOpen) return
    setQuery("")
    requestAnimationFrame(() => searchRef.current?.focus())
  }

  return (
    <div className={`projectPicker${compact ? " projectPicker-compact" : ""}`} ref={rootRef}>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        className="projectPickerTrigger"
        onClick={togglePicker}
        type="button"
      >
        <span className="projectInitial">
          {selectedProject?.name.charAt(0).toUpperCase() || "P"}
        </span>
        <span className="projectPickerValue">
          <strong>{selectedProject?.name || "Select project"}</strong>
          {!compact && (
            <small>{selectedProject?.github_owner || `${projects.length} available`}</small>
          )}
        </span>
        <Icon className={open ? "pickerChevron open" : "pickerChevron"} name="chevronDown" size={15} />
      </button>

      {open && (
        <div className="projectPickerMenu">
          <div className="projectPickerSearch">
            <Icon name="search" size={15} />
            <input
              aria-label="Search projects"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search projects"
              ref={searchRef}
              value={query}
            />
          </div>
          <div className="projectPickerMeta">
            <span>{filteredProjects.length} projects</span>
            <span>GitHub</span>
          </div>
          <div className="projectPickerList" role="listbox">
            {filteredProjects.length === 0 ? (
              <p className="projectPickerEmpty">No matching projects</p>
            ) : filteredProjects.map((project) => {
              const active = project.id === selectedProjectId
              return (
                <button
                  aria-selected={active}
                  className={active ? "projectPickerOption active" : "projectPickerOption"}
                  key={project.id}
                  onClick={() => selectProject(project.id)}
                  role="option"
                  type="button"
                >
                  <span className="projectOptionInitial">
                    {project.name.charAt(0).toUpperCase()}
                  </span>
                  <span>
                    <strong>{project.name}</strong>
                    <small>{project.github_owner}/{project.github_repo}</small>
                  </span>
                  {active && <Icon name="check" size={15} />}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
