import type { ReactNode, SVGProps } from "react"

export type IconName =
  | "arrowUp"
  | "bot"
  | "branch"
  | "check"
  | "chevronDown"
  | "circleAlert"
  | "clock"
  | "command"
  | "dashboard"
  | "external"
  | "github"
  | "list"
  | "logOut"
  | "maximize"
  | "message"
  | "minimize"
  | "plus"
  | "refresh"
  | "search"
  | "spark"
  | "tasks"
  | "x"

type IconProps = SVGProps<SVGSVGElement> & {
  name: IconName
  size?: number
}

const paths: Record<IconName, ReactNode> = {
  arrowUp: <><path d="m7 11 5-5 5 5" /><path d="M12 18V6" /></>,
  bot: <><rect x="5" y="7" width="14" height="12" rx="3" /><path d="M9 12h.01M15 12h.01M9 16h6M12 7V4M9 4h6" /></>,
  branch: <><circle cx="6" cy="5" r="2" /><circle cx="18" cy="6" r="2" /><circle cx="6" cy="19" r="2" /><path d="M6 7v10M8 7c2 0 2 4 5 4h3" /></>,
  check: <><path d="m5 12 4 4L19 6" /></>,
  chevronDown: <><path d="m7 10 5 5 5-5" /></>,
  circleAlert: <><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  command: <><rect x="4" y="4" width="16" height="16" rx="4" /><path d="M8 9h8M8 13h5" /></>,
  dashboard: <><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></>,
  external: <><path d="M14 5h5v5M19 5l-8 8" /><path d="M19 14v3a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h3" /></>,
  github: <><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3.3-.4 6.8-1.6 6.8-7.4A5.8 5.8 0 0 0 19.3 3 5.4 5.4 0 0 0 19.1-.9S17.9-1.3 15 1a14 14 0 0 0-7 0C5.1-1.3 3.9-.9 3.9-.9A5.4 5.4 0 0 0 3.7 3a5.8 5.8 0 0 0-1.5 4.1c0 5.8 3.5 7 6.8 7.4A4.8 4.8 0 0 0 8 18v4" transform="translate(.5 1) scale(.96)" /><path d="M8 19c-3 .9-3-1.5-4-2" /></>,
  list: <><path d="M9 6h11M9 12h11M9 18h11" /><path d="M4 6h.01M4 12h.01M4 18h.01" /></>,
  logOut: <><path d="M10 5H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4" /><path d="m15 16 4-4-4-4M19 12H9" /></>,
  maximize: <><path d="M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5" /></>,
  message: <><path d="M20 15a4 4 0 0 1-4 4H8l-4 3V8a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4Z" /><path d="M8 10h8M8 14h5" /></>,
  minimize: <><path d="M8 3v5H3M16 3v5h5M21 16h-5v5M3 16h5v5" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  refresh: <><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 5v6h-6" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
  spark: <><path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2Z" /><path d="m6 14 .8 2.2L9 17l-2.2.8L6 20l-.8-2.2L3 17l2.2-.8Z" /><path d="m18 15 .6 1.4L20 17l-1.4.6L18 19l-.6-1.4L16 17l1.4-.6Z" /></>,
  tasks: <><path d="M9 6h11M9 12h11M9 18h11" /><path d="m3 6 1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2" /></>,
  x: <><path d="m6 6 12 12M18 6 6 18" /></>
}

export function Icon({ name, size = 20, ...props }: IconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      height={size}
      viewBox="0 0 24 24"
      width={size}
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      {...props}
    >
      {paths[name]}
    </svg>
  )
}
