"use client"

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react"
import {
  askDevPilot,
  decideDevPilotApproval,
  getProjectChatMessages,
  type ApprovalRequest,
  type ChatResult
} from "@/lib/api"
import { Icon } from "@/components/Icon"
import { MarkdownMessage } from "@/components/MarkdownMessage"

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

const MAX_CHAT_MESSAGES = 40

function keepLatestMessages(messages: Message[]) {
  return messages.slice(-MAX_CHAT_MESSAGES)
}

export function AgentChat({
  projectId,
  projectName,
  onProjectUpdated,
  expanded = false,
  onToggleExpanded,
  composeRequest
}: {
  projectId: string
  projectName: string
  onProjectUpdated?: () => void
  expanded?: boolean
  onToggleExpanded?: () => void
  composeRequest?: { id: number; text: string } | null
}) {
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null)
  const [resolvingRequestId, setResolvingRequestId] = useState<string | null>(null)
  const messageListRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const messageIdRef = useRef(0)

  useEffect(() => {
    let active = true

    void getProjectChatMessages(projectId)
      .then((history) => {
        if (!active) return
        setMessages(history.map((message) => ({
          id: `history-${message.id}`,
          role: message.role,
          text: message.content
        })))
      })
      .catch((historyError) => {
        if (!active) return
        setError(
          historyError instanceof Error
            ? historyError.message
            : "This project conversation could not be loaded"
        )
      })
      .finally(() => {
        if (active) setLoadingHistory(false)
      })

    return () => { active = false }
  }, [projectId])

  useEffect(() => {
    if (messages.length === 0 && !loading && !pendingApproval && !loadingHistory) return
    const messageList = messageListRef.current
    if (!messageList) return

    messageList.scrollTo({
      top: messageList.scrollHeight,
      behavior: "smooth"
    })
  }, [messages, loading, pendingApproval, loadingHistory])

  useEffect(() => {
    if (!composeRequest) return
    const frame = requestAnimationFrame(() => {
      setInput(composeRequest.text)
      inputRef.current?.focus()
    })
    return () => cancelAnimationFrame(frame)
  }, [composeRequest])

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
    setMessages((current) => keepLatestMessages([
      ...current,
      {
        id: `assistant-${++messageIdRef.current}`,
        role: "assistant",
        text: result.answer || "Done"
      }
    ]))
  }

  async function sendMessage(question: string) {
    const cleanQuestion = question.trim()
    if (!cleanQuestion || loading || loadingHistory || pendingApproval) return

    const userMessage: Message = {
      id: `user-${++messageIdRef.current}`,
      role: "user",
      text: cleanQuestion
    }

    setInput("")
    setError(null)
    setMessages((current) => keepLatestMessages([...current, userMessage]))
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
      setMessages((current) => keepLatestMessages([
        ...current,
        {
          id: `event-${++messageIdRef.current}`,
          role: "event",
          text: decision === "approve" ? "Action approved" : "Action rejected"
        }
      ]))
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
    <section
      className={`assistantPanel${expanded ? " assistantPanel-expanded" : ""}`}
      id="assistant"
      aria-label="DevPilot assistant"
    >
      <div className="assistantHeader">
        <div className="assistantIdentity">
          <span className="assistantMark"><Icon name="bot" size={19} /></span>
          <div>
            <div className="assistantTitleRow">
              <h2>Ask DevPilot</h2>
              <span className="statusDot" aria-label="Ready" />
            </div>
            <p>Project chat, latest 40 messages</p>
          </div>
        </div>
        {onToggleExpanded && (
          <button
            aria-label={expanded ? "Restore dashboard view" : "Maximize assistant"}
            aria-pressed={expanded}
            className="assistantSizeButton"
            onClick={onToggleExpanded}
            title={expanded ? "Restore dashboard view" : "Maximize assistant"}
            type="button"
          >
            <Icon name={expanded ? "minimize" : "maximize"} size={18} />
          </button>
        )}
      </div>

      <div
        aria-busy={loading || loadingHistory}
        aria-live="polite"
        className="messageList"
        ref={messageListRef}
      >
        {loadingHistory ? (
          <div className="chatHistoryLoading" role="status">
            <Icon className="spinning" name="refresh" size={19} />
            <span>Loading this project&apos;s conversation</span>
          </div>
        ) : messages.length === 0 ? (
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
              {message.role === "assistant" ? (
                <div className="messageBody">
                  <MarkdownMessage>{message.text}</MarkdownMessage>
                </div>
              ) : (
                <p>{message.text}</p>
              )}
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
                <p className="approvalScope">Project: {projectName}</p>
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
      </div>

      <form className="chatComposer" onSubmit={submit}>
        <div className="composerField">
          <textarea
            aria-label="Message DevPilot"
            disabled={loadingHistory || pendingApproval !== null || resolvingRequestId !== null}
            maxLength={2000}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              loadingHistory
                ? "Loading conversation"
                : pendingApproval
                  ? "Review the pending action first"
                  : "Ask about this project"
            }
            ref={inputRef}
            rows={1}
            value={input}
          />
          <button
            aria-label="Send message"
            className="sendButton"
            disabled={
              !input.trim()
              || loading
              || loadingHistory
              || pendingApproval !== null
              || resolvingRequestId !== null
            }
            type="submit"
          >
            <Icon name="arrowUp" size={18} />
          </button>
        </div>
        <p>
          {loadingHistory
            ? "Loading the latest messages for this project"
            : pendingApproval
            ? "Approve or reject the action to continue"
            : "Enter to send, Shift + Enter for a new line"}
        </p>
      </form>
    </section>
  )
}
