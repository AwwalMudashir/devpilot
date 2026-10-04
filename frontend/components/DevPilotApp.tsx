"use client"

import { useEffect, useState } from "react"
import { ConnectGitHub } from "@/components/ConnectGitHub"
import { Dashboard } from "@/components/Dashboard"
import { Icon } from "@/components/Icon"
import {
  getAuthSession,
  signOut,
  type AuthUser
} from "@/lib/api"

type SessionState =
  | { status: "loading"; user: null }
  | { status: "signed_out"; user: null }
  | { status: "signed_in"; user: AuthUser }

export function DevPilotApp() {
  const [session, setSession] = useState<SessionState>({
    status: "loading",
    user: null
  })
  const [sessionError, setSessionError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    void getAuthSession()
      .then((result) => {
        if (!active) return
        if (result.authenticated && result.user) {
          setSession({ status: "signed_in", user: result.user })
        } else {
          setSession({ status: "signed_out", user: null })
        }
      })
      .catch((error) => {
        if (!active) return
        setSessionError(
          error instanceof Error
            ? error.message
            : "DevPilot could not check your session"
        )
        setSession({ status: "signed_out", user: null })
      })

    return () => { active = false }
  }, [])

  async function handleSignOut() {
    try {
      await signOut()
    } finally {
      window.localStorage.removeItem("devpilot:selected-project")
      setSession({ status: "signed_out", user: null })
    }
  }

  if (session.status === "loading") {
    return (
      <main className="authLoading" aria-label="Loading DevPilot">
        <span className="brandMark"><Icon name="command" size={22} /></span>
        <span className="authLoadingBar" />
      </main>
    )
  }

  if (session.status === "signed_out") {
    return <ConnectGitHub error={sessionError} />
  }

  return (
    <Dashboard
      onSignOut={() => void handleSignOut()}
      user={session.user}
    />
  )
}
