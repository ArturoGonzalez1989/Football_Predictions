import { cn } from "../lib/utils"

interface StatusBadgeProps {
  status: "live" | "upcoming" | "finished"
  minute?: number | null
}

export function StatusBadge({ status, minute }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide uppercase",
        status === "live" && "bg-red-500/15 text-red-400",
        status === "upcoming" && "bg-blue-500/15 text-blue-400",
        status === "finished" && "bg-zinc-500/15 text-zinc-400"
      )}
    >
      {status === "live" && (
        <span className="h-1.5 w-1.5 rounded-full bg-red-400 animate-pulse-dot" />
      )}
      {status === "live" && `LIVE ${minute ?? ""}′`}
      {status === "upcoming" && "UPCOMING"}
      {status === "finished" && "FINISHED"}
    </span>
  )
}
