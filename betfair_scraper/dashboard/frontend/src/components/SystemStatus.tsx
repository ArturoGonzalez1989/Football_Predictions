import { useState } from "react"
import { api, type SystemStatus as SystemStatusType } from "../lib/api"
import { cn } from "../lib/utils"

interface SystemStatusProps {
  status: SystemStatusType | null
  onRefresh: () => void
}

export function SystemStatus({ status, onRefresh }: SystemStatusProps) {
  const [acting, setActing] = useState(false)
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null)

  async function handleStart() {
    setActing(true)
    setMessage(null)
    try {
      const res = await api.startScraper()
      setMessage({ text: res.message, ok: res.ok })
      onRefresh()
    } catch {
      setMessage({ text: "Failed to connect to backend", ok: false })
    }
    setActing(false)
    setTimeout(() => setMessage(null), 6000)
  }

  async function handleStop() {
    setActing(true)
    setMessage(null)
    try {
      const res = await api.stopScraper()
      setMessage({ text: res.message, ok: res.ok })
      onRefresh()
    } catch {
      setMessage({ text: "Failed to connect to backend", ok: false })
    }
    setActing(false)
    setTimeout(() => setMessage(null), 6000)
  }

  async function handleRestart() {
    setActing(true)
    setMessage(null)
    try {
      const stopRes = await api.stopScraper()
      // Wait a moment for processes to fully terminate
      await new Promise(r => setTimeout(r, 2000))
      const startRes = await api.startScraper()
      setMessage({ text: startRes.ok ? `Restarted (PID ${startRes.pid})` : startRes.message, ok: startRes.ok })
      onRefresh()
    } catch {
      setMessage({ text: "Failed to connect to backend", ok: false })
    }
    setActing(false)
    setTimeout(() => setMessage(null), 6000)
  }

  if (!status) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 text-zinc-500 text-sm">
        Loading system status...
      </div>
    )
  }

  const uptime = status.uptime_seconds
    ? `${Math.floor(status.uptime_seconds / 3600)}h ${Math.floor((status.uptime_seconds % 3600) / 60)}m`
    : "N/A"

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">System</h3>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 text-xs font-medium",
            status.running ? "text-green-400" : "text-red-400"
          )}
        >
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              status.running ? "bg-green-400 animate-pulse-dot" : "bg-red-400"
            )}
          />
          {status.running ? "Running" : "Stopped"}
        </span>
      </div>

      {/* Scraper controls */}
      <div className="flex gap-1.5">
        {!status.running ? (
          <button
            type="button"
            onClick={handleStart}
            disabled={acting}
            className="flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-green-500/10 text-green-400 border border-green-500/20 hover:bg-green-500/20 transition-colors cursor-pointer disabled:opacity-50"
          >
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
            {acting ? "Starting..." : "Start"}
          </button>
        ) : (
          <>
            <button
              type="button"
              onClick={handleStop}
              disabled={acting}
              className="flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors cursor-pointer disabled:opacity-50"
            >
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                <rect x="6" y="6" width="12" height="12" rx="1" />
              </svg>
              {acting ? "..." : "Stop"}
            </button>
            <button
              type="button"
              onClick={handleRestart}
              disabled={acting}
              className="flex-1 flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 hover:bg-yellow-500/20 transition-colors cursor-pointer disabled:opacity-50"
            >
              <svg className={`w-3 h-3 ${acting ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              {acting ? "..." : "Restart"}
            </button>
          </>
        )}
      </div>

      {/* Action feedback */}
      {message && (
        <div className={cn(
          "rounded-lg px-2.5 py-1.5 text-[11px] font-mono",
          message.ok ? "bg-green-500/10 text-green-400 border border-green-500/20" : "bg-red-500/10 text-red-400 border border-red-500/20"
        )}>
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-zinc-800/50 p-2.5">
          <div className="text-zinc-500 text-[10px] uppercase tracking-wider">PID</div>
          <div className="font-mono text-zinc-200 mt-0.5">
            {status.pid ?? "—"}
          </div>
        </div>
        <div className="rounded-lg bg-zinc-800/50 p-2.5">
          <div className="text-zinc-500 text-[10px] uppercase tracking-wider">Uptime</div>
          <div className="font-mono text-zinc-200 mt-0.5">{uptime}</div>
        </div>
        <div className="rounded-lg bg-zinc-800/50 p-2.5">
          <div className="text-zinc-500 text-[10px] uppercase tracking-wider">Memory</div>
          <div className="font-mono text-zinc-200 mt-0.5">
            {status.memory_mb ? `${status.memory_mb} MB` : "—"}
          </div>
        </div>
        <div className="rounded-lg bg-zinc-800/50 p-2.5">
          <div className="text-zinc-500 text-[10px] uppercase tracking-wider">Chrome</div>
          <div className="font-mono text-zinc-200 mt-0.5">
            {status.chrome_processes} procs
          </div>
        </div>
      </div>

      {status.last_log_lines.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider">
            Recent Logs
          </div>
          <div className="bg-black/40 rounded-lg p-2 max-h-40 overflow-y-auto font-mono text-[10px] leading-relaxed text-zinc-400 space-y-px">
            {status.last_log_lines.slice(-10).map((line, i) => (
              <div key={i} className="hover:text-zinc-200 transition-colors">
                {line}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
