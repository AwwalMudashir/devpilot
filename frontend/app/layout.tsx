import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = {
  title: "DevPilot | Project intelligence",
  description: "Project status, repository activity, and practical answers in one workspace"
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
