import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  async rewrites() {
    const agentApiUrl = (
      process.env.AGENT_API_URL ||
      process.env.NEXT_PUBLIC_AGENT_API_URL ||
      "http://localhost:8000"
    ).replace(/\/$/, "")

    return [
      {
        source: "/api/devpilot/:path*",
        destination: `${agentApiUrl}/:path*`
      }
    ]
  }
}

export default nextConfig
