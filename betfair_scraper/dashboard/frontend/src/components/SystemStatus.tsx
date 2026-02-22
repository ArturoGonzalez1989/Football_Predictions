import { useState } from "react"
import { api, type SystemStatus as SystemStatusType, type DriverProgress } from "../lib/api"
import { cn } from "../lib/utils"

const STAGE_LABEL: Record<DriverProgress["stage"], string> = {
  pending:           "Pendiente",
  chrome_init:       "Iniciando Chrome",
  loading_url:       "Cargando URL",
  accepting_cookies: "Cookies",
  ready:             "Driver listo",
  capturing:         "Primera captura",
  live:              "En vivo",
  error:             "Error",
}

const STAGE_COLOR: Record<DriverProgress["stage"], string> = {
  pending:           "bg-zinc-600",
  chrome_init:       "bg-blue-500",
  loading_url:       "bg-blue-400",
  accepting_cookies: "bg-violet-400",
  ready:             "bg-amber-400",
  capturing:         "bg-orange-400",
  live:              "bg-green-500",
  error:             "bg-red-500",
}

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
      await api.stopScraper()
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

  async function handleRestartBackend() {
    if (!confirm("¿Reiniciar el backend del dashboard? El proceso uvicorn se matará y relanzará con el código nuevo.")) {
      return
    }
    setActing(true)
    setMessage(null)
    try {
      await api.restartBackend()
      setMessage({ text: "Backend cerrándose... esperando nuevo proceso", ok: true })
    } catch {
      // Expected: connection drops when backend kills itself
    }

    // Poll until the new backend is ready (up to 30 seconds)
    setMessage({ text: "Esperando nuevo backend...", ok: true })
    let ready = false
    for (let i = 0; i < 30; i++) {
      await new Promise(r => setTimeout(r, 1000))
      try {
        const res = await fetch("/api/health")
        if (res.ok) {
          ready = true
          break
        }
      } catch {
        // Still starting up
      }
      setMessage({ text: `Esperando nuevo backend... (${i + 1}s)`, ok: true })
    }

    if (ready) {
      setMessage({ text: "Backend reiniciado correctamente", ok: true })
      onRefresh()
    } else {
      setMessage({ text: "Backend no respondió en 30s - verifica manualmente", ok: false })
    }
    setActing(false)
    setTimeout(() => setMessage(null), 8000)
  }

  async function handleCleanupChrome() {
    setActing(true)
    setMessage(null)
    try {
      const res = await api.cleanupChrome()
      setMessage({ text: res.message, ok: res.ok })
      onRefresh()
    } catch {
      setMessage({ text: "Error conectando con backend", ok: false })
    }
    setActing(false)
    setTimeout(() => setMessage(null), 8000)
  }

  async function handleRestartFrontend() {
    if (!confirm("¿Reiniciar el frontend del dashboard? La página se recargará automáticamente.")) {
      return
    }
    setActing(true)
    setMessage(null)
    try {
      const res = await api.restartFrontend()
      setMessage({ text: res.message, ok: res.ok })
      // Wait for frontend to restart, then reload page
      setMessage({ text: "Frontend reiniciado - recargando página...", ok: true })
      setTimeout(() => window.location.reload(), 4000)
    } catch {
      setMessage({ text: "Error reiniciando frontend", ok: false })
      setActing(false)
    }
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

  // Progreso por partido: solo mostrar si hay drivers que aún no están en "live"
  const progress = status.drivers_progress ?? {}
  const progressEntries = Object.entries(progress)
  const initializingDrivers = progressEntries.filter(([, d]) => d.stage !== "live")
  const liveCount = progressEntries.filter(([, d]) => d.stage === "live").length
  const totalCount = progressEntries.length
  const showProgress = totalCount > 0

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

      {/* Backend controls */}
      <div className="border-t border-zinc-800 pt-3 space-y-2">
        <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Backend & Frontend</div>
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            onClick={handleRestartBackend}
            disabled={acting}
            className="flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors cursor-pointer disabled:opacity-50"
          >
            <svg className={`w-3 h-3 ${acting ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {acting ? "..." : "Backend"}
          </button>
          <button
            type="button"
            onClick={handleRestartFrontend}
            disabled={acting}
            className="flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20 hover:bg-purple-500/20 transition-colors cursor-pointer disabled:opacity-50"
          >
            <svg className={`w-3 h-3 ${acting ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {acting ? "..." : "Frontend"}
          </button>
        </div>
      </div>

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
        <div className={cn(
          "rounded-lg p-2.5",
          status.chrome_processes >= 100
            ? "bg-red-500/10 border border-red-500/30"
            : status.chrome_processes >= 30
              ? "bg-amber-500/10 border border-amber-500/30"
              : "bg-zinc-800/50"
        )}>
          <div className="flex items-center justify-between">
            <div className="text-zinc-500 text-[10px] uppercase tracking-wider">Chrome</div>
            {status.chrome_processes >= 30 && (
              <button
                type="button"
                onClick={handleCleanupChrome}
                disabled={acting}
                title="Matar procesos Chrome huérfanos (no hijos del scraper)"
                className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25 transition-colors cursor-pointer disabled:opacity-50"
              >
                <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                Limpiar
              </button>
            )}
          </div>
          <div className="flex items-baseline gap-1.5 mt-0.5">
            <span className={cn(
              "font-mono font-bold text-lg",
              status.chrome_processes >= 100 ? "text-red-400"
                : status.chrome_processes >= 30 ? "text-amber-400"
                : "text-zinc-200"
            )}>
              {status.chrome_processes}
            </span>
            <span className="text-zinc-500 text-[10px]">procs</span>
            {status.chrome_processes >= 100 && (
              <span className="text-red-400 text-[10px] font-medium animate-pulse">⚠ excesivo</span>
            )}
            {status.chrome_processes >= 30 && status.chrome_processes < 100 && (
              <span className="text-amber-400 text-[10px] font-medium">↑ alto</span>
            )}
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

      {/* ── Driver init progress ── */}
      {showProgress && (
        <div className="border-t border-zinc-800 pt-3 space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">
              Init progreso
            </div>
            <span className={cn(
              "text-[11px] font-mono font-medium",
              liveCount === totalCount ? "text-green-400" : "text-amber-400"
            )}>
              {liveCount}/{totalCount} live
            </span>
          </div>

          {/* Barra global */}
          <div className="w-full h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div
              className="h-full rounded-full bg-green-500 transition-all duration-500"
              style={{ width: `${totalCount > 0 ? (liveCount / totalCount) * 100 : 0}%` }}
            />
          </div>

          {/* Lista de drivers aún inicializando */}
          {initializingDrivers.length > 0 && (
            <div className="space-y-1.5 max-h-52 overflow-y-auto pr-0.5">
              {initializingDrivers.map(([matchId, d]) => (
                <div key={matchId} className="space-y-0.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] text-zinc-400 truncate flex-1" title={d.game}>
                      {d.game}
                    </span>
                    <span className={cn(
                      "text-[10px] font-medium shrink-0 px-1.5 py-0.5 rounded",
                      d.stage === "error"
                        ? "text-red-400 bg-red-500/10"
                        : "text-zinc-400 bg-zinc-800"
                    )}>
                      {STAGE_LABEL[d.stage] ?? d.stage}
                    </span>
                    <span className="text-[10px] font-mono text-zinc-500 w-8 text-right shrink-0">
                      {d.pct}%
                    </span>
                  </div>
                  <div className="w-full h-1 rounded-full bg-zinc-800 overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all duration-500", STAGE_COLOR[d.stage] ?? "bg-zinc-500")}
                      style={{ width: `${d.pct}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {initializingDrivers.length === 0 && totalCount > 0 && (
            <div className="text-[11px] text-green-400 font-medium text-center py-1">
              ✓ Todos los partidos capturando
            </div>
          )}
        </div>
      )}
    </div>
  )
}
