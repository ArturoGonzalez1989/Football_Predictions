import { cn } from "../lib/utils"
import { formatTimeAgo } from "../lib/utils"

interface CaptureIndicatorProps {
  captureCount: number
  lastCaptureAgo: number | null | undefined
}

export function CaptureIndicator({ captureCount, lastCaptureAgo }: CaptureIndicatorProps) {
  const health =
    lastCaptureAgo == null ? "unknown"
    : lastCaptureAgo < 120 ? "good"
    : lastCaptureAgo < 600 ? "slow"
    : "stalled"

  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          health === "good" && "bg-green-400",
          health === "slow" && "bg-yellow-400",
          health === "stalled" && "bg-red-400",
          health === "unknown" && "bg-zinc-500"
        )}
      />
      <span className="text-zinc-400">
        {captureCount} captures
      </span>
      <span className="text-zinc-500">|</span>
      <span
        className={cn(
          health === "good" && "text-green-400",
          health === "slow" && "text-yellow-400",
          health === "stalled" && "text-red-400",
          health === "unknown" && "text-zinc-500"
        )}
      >
        {lastCaptureAgo != null ? formatTimeAgo(lastCaptureAgo) : "No data"}
      </span>
    </div>
  )
}
