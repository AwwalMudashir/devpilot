"use client"

import { FormEvent, useEffect, useState } from "react"
import { Icon } from "@/components/Icon"
import {
  createProjectTask,
  type ProjectTask,
  type TaskPriority
} from "@/lib/api"

export function TaskCreateDialog({
  projectId,
  projectName,
  onClose,
  onCreated
}: {
  projectId: string
  projectName: string
  onClose: () => void
  onCreated: (task: ProjectTask) => void
}) {
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [priority, setPriority] = useState<TaskPriority>("medium")
  const [dueDate, setDueDate] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !submitting) onClose()
    }

    document.addEventListener("keydown", handleKeyDown)
    return () => document.removeEventListener("keydown", handleKeyDown)
  }, [onClose, submitting])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const cleanTitle = title.trim()
    if (!cleanTitle || submitting) return

    setSubmitting(true)
    setError(null)
    try {
      const task = await createProjectTask(projectId, {
        title: cleanTitle,
        description: description.trim() || null,
        priority,
        due_date: dueDate || null
      })
      onCreated(task)
      onClose()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The task could not be created")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="dialogBackdrop" onMouseDown={(event) => {
      if (event.currentTarget === event.target && !submitting) onClose()
    }}>
      <section aria-labelledby="task-dialog-title" aria-modal="true" className="taskDialog" role="dialog">
        <div className="taskDialogHeader">
          <div>
            <span className="dialogEyebrow">New task</span>
            <h2 id="task-dialog-title">Add work to {projectName}</h2>
          </div>
          <button aria-label="Close task form" disabled={submitting} onClick={onClose} type="button">
            <Icon name="x" size={18} />
          </button>
        </div>

        <form onSubmit={submit}>
          <label className="formField">
            <span>Title</span>
            <input
              autoFocus
              maxLength={160}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="What needs to be done?"
              required
              value={title}
            />
          </label>

          <label className="formField">
            <span>Description <small>Optional</small></span>
            <textarea
              maxLength={2000}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Add context, acceptance criteria, or useful links"
              rows={4}
              value={description}
            />
          </label>

          <div className="taskFormRow">
            <label className="formField">
              <span>Priority</span>
              <select onChange={(event) => setPriority(event.target.value as TaskPriority)} value={priority}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </label>
            <label className="formField">
              <span>Due date <small>Optional</small></span>
              <input onChange={(event) => setDueDate(event.target.value)} type="date" value={dueDate} />
            </label>
          </div>

          {error && <p className="dialogError" role="alert">{error}</p>}

          <div className="taskDialogActions">
            <button disabled={submitting} onClick={onClose} type="button">Cancel</button>
            <button className="primaryButton" disabled={!title.trim() || submitting} type="submit">
              <Icon name="plus" size={16} />
              {submitting ? "Creating..." : "Create task"}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
