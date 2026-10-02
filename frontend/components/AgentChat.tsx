"use client"

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react"
import { askDevPilot } from "@/lib/api"
import { Icon } from "@/components/Icon"

type Message = {
  id: string
  role: "user" | "assistant"
  text: string
}

const suggestions = [
  "What is blocking this project?",
  "What changed in the repository recently?",
  "Which tasks should I handle next?"
]

export function AgentChat({
  projectId,
  projectName
}: {
  projectId: string
  projectName: string
}) {
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messageEndRef = useRef<HTMLDivElement>(null)
  const messageIdRef = useRef(0)

  useEffect(() => {
    if (messages.length === 0 && !loading) return
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function sendMessage(question: string) {
    const cleanQuestion = question.trim()
    if (!cleanQuestion || loading) return

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
      const answer = await askDevPilot(cleanQuestion, projectId)
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${++messageIdRef.current}`,
          role: "assistant",
          text: answer
        }
      ])
    } catch (requestError) {
      const message = requestError instanceof Error
        ? requestError.message
        : "DevPilot could not answer right now"
      setError(message)
    } finally {
      setLoading(false)
    }
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
              <div className="messageLabel">
                {message.role === "user" ? "You" : "DevPilot"}
              </div>
              <p>{message.text}</p>
            </article>
          ))
        )}

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
            disabled={loading}
            maxLength={2000}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about this project"
            rows={2}
            value={input}
          />
          <button
            aria-label="Send message"
            className="sendButton"
            disabled={!input.trim() || loading}
            type="submit"
          >
            <Icon name="arrowUp" size={18} />
          </button>
        </div>
        <p>Enter to send, Shift + Enter for a new line</p>
      </form>
    </section>
  )
}
