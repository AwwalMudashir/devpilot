"use client"

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react"
import {
  askDevPilot,
  decideDevPilotApproval,
  type ApprovalRequest,
  type ChatResult
} from "@/lib/api"
import { Icon } from "@/components/Icon"

type Message = {
  id: string
  role: "user" | "assistant" | "event"
  text: string
}

type PendingApproval = {
  approvalId: string
  approvals: ApprovalRequest[]
}

const suggestions = [
  "What is blocking this project?",
  "What changed in the repository recently?",
  "Which tasks should I handle next?"
]

export function AgentChat({
  projectId,
  projectName,
  onProjectUpdated
}: {
  projectId: string
  projectName: string
  onProjectUpdated?: () => void
}) {
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null)
  const [resolvingRequestId, setResolvingRequestId] = useState<string | null>(null)
  const messageEndRef = useRef<HTMLDivElement>(null)
  const messageIdRef = useRef(0)

  useEffect(() => {
    if (messages.length === 0 && !loading && !pendingApproval) return
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading, pendingApproval])

  function handleChatResult(result: ChatResult) {
    if (result.status === "approval_required") {
      if (!result.approval_id || result.approvals.length === 0) {
        throw new Error("The approval request is incomplete")
      }
      setPendingApproval({
        approvalId: result.approval_id,
        approvals: result.approvals
      })
      return
    }

    setPendingApproval(null)
    setMessages((current) => [
      ...current,
      {
        id: `assistant-${++messageIdRef.current}`,
        role: "assistant",
        text: result.answer || "Done"
      }
    ])
  }

  async function sendMessage(question: string) {
    const cleanQuestion = question.trim()
    if (!cleanQuestion || loading || pendingApproval) return

    const userMessage: Message = {
      id: `user-${++messageIdRef.current}`,
      role: "user",
      text: cleanQuestion
    }

    setInput("")
    setError(null)
    setMessages((current) => [...current, userMessage])
    setLoading(true)

    try {
      const result = await askDevPilot(cleanQuestion, projectId)
      handleChatResult(result)
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message
        : "DevPilot could not answer right now"
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  async function decideApproval(
    approval: ApprovalRequest,
    decision: "approve" | "reject"
  ) {
    if (!pendingApproval || resolvingRequestId) return

    setResolvingRequestId(approval.request_id)
    setError(null)

    try {
      const result = await decideDevPilotApproval(
        pendingApproval.approvalId,
        approval.request_id,
        decision
      )
      setMessages((current) => [
        ...current,
        {
          id: `event-${++messageIdRef.current}`,
          role: "event",
          text: decision === "approve" ? "Action approved" : "Action rejected"
        }
      ])
      if (decision === "approve") onProjectUpdated?.()
      handleChatResult(result)
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message
        : "The approval could not be completed"
      setPendingApproval(null)
      setError(message)
      if (decision === "approve") onProjectUpdated?.()
    } finally {
      setResolvingRequestId(null)
    }
  }

  function formatArgument(value: unknown) {
    if (typeof value === "string") return value.replaceAll("_", " ")
    if (value === null || value === undefined || value === "") return "Not set"
    return String(value)
  }

  function formatArgumentName(name: string) {
    return name
      .replaceAll("_", " ")
      .replace(/^./, (letter) => letter.toUpperCase())
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void sendMessage(input)
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      void sendMessage(input)
    }
  }

  return (
    <section className="assistantPanel" id="assistant" aria-label="DevPilot assistant">
      <div className="assistantHeader">
        <div className="assistantIdentity">
          <span className="assistantMark"><Icon name="bot" size={19} /></span>
          <div>
            <div className="assistantTitleRow">
              <h2>Ask DevPilot</h2>
              <span className="statusDot" aria-label="Ready" />
            </div>
            <p>Answers use the selected project&apos;s live data</p>
          </div>
        </div>
      </div>

      <div className="messageList" aria-live="polite">
        {messages.length === 0 ? (
          <div className="chatWelcome">
            <span className="chatWelcomeIcon"><Icon name="spark" size={22} /></span>
            <h3>What do you need to know?</h3>
            <p>
              Ask about {projectName}&apos;s tasks, blockers, commits, issues, or project notes.
            </p>
            <div className="suggestionList">
              {suggestions.map((suggestion) => (
                <button
                  className="suggestionButton"
                  key={suggestion}
                  onClick={() => void sendMessage(suggestion)}
                  type="button"
                >
                  <span>{suggestion}</span>
                  <Icon name="arrowUp" size={16} />
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <article className={`message message-${message.role}`} key={message.id}>
              {message.role !== "event" && (
                <div className="messageLabel">
                  {message.role === "user" ? "You" : "DevPilot"}
                </div>
              )}
              <p>{message.text}</p>
            </article>
          ))
        )}

        {pendingApproval && pendingApproval.approvals.map((approval) => (
          <article className="approvalCard" key={approval.request_id}>
            <div className="approvalHeader">
              <span className="approvalIcon"><Icon name="circleAlert" size={18} /></span>
              <div>
                <span>Approval required</span>
                <h3>{approval.title}</h3>
                <p>{approval.description}</p>
              </div>
            </div>

            <dl className="approvalDetails">
              {Object.entries(approval.arguments)
                .filter(([name]) => name !== "project_id")
                .map(([name, value]) => (
                  <div key={name}>
                    <dt>{formatArgumentName(name)}</dt>
                    <dd>{formatArgument(value)}</dd>
                  </div>
                ))}
            </dl>

            <div className="approvalActions">
              <button
                className="rejectButton"
                disabled={resolvingRequestId !== null}
                onClick={() => void decideApproval(approval, "reject")}
                type="button"
              >
                Reject
              </button>
              <button
                className="approveButton"
                disabled={resolvingRequestId !== null}
                onClick={() => void decideApproval(approval, "approve")}
                type="button"
              >
                {resolvingRequestId === approval.request_id ? "Applying..." : "Approve action"}
              </button>
            </div>
          </article>
        ))}

        {loading && (
          <div className="thinkingState" role="status">
            <span /><span /><span />
            <span className="srOnly">DevPilot is checking the project</span>
          </div>
        )}

        {error && (
          <div className="chatError" role="alert">
            <Icon name="circleAlert" size={17} />
            <span>{error}</span>
          </div>
        )}
        <div ref={messageEndRef} />
      </div>

      <form className="chatComposer" onSubmit={submit}>
        <div className="composerField">
          <textarea
            aria-label="Message DevPilot"
            disabled={loading || pendingApproval !== null || resolvingRequestId !== null}
            maxLength={2000}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={pendingApproval ? "Review the pending action first" : "Ask about this project"}
            rows={2}
            value={input}
          />
          <button
            aria-label="Send message"
            className="sendButton"
            disabled={!input.trim() || loading || pendingApproval !== null || resolvingRequestId !== null}
            type="submit"
          >
            <Icon name="arrowUp" size={18} />
          </button>
        </div>
        <p>
          {pendingApproval
            ? "Approve or reject the action to continue"
            : "Enter to send, Shift + Enter for a new line"}
        </p>
      </form>
    </section>
  )
}
