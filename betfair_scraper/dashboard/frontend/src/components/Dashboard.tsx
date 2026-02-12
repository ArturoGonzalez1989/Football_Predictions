import { useState, useEffect, useCallback } from "react"
import { api, type Match, type SystemStatus as SystemStatusType } from "../lib/api"
import { LiveView } from "./LiveView"
import { FinishedView } from "./FinishedView"

type View = "live" | "finished"

export function Dashboard() {
  const [view, setView] = useState<View>("live")
  const [matches, setMatches] = useState<Match[]>([])
  const [system, setSystem] = useState<SystemStatusType | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [m, s] = await Promise.all([
        api.getMatches(),
        api.getSystemStatus(),
      ])
      setMatches(m)
      setSystem(s)
      setLastRefresh(new Date())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection error")
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 10000)
    return () => clearInterval(interval)
  }, [refresh])

  const liveMatches = matches.filter((m) => m.status === "live")
  const upcomingMatches = matches.filter((m) => m.status === "upcoming")
  const finishedMatches = matches.filter((m) => m.status === "finished")

  return (
    <div className="min-h-screen bg-[var(--bg)] flex">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 border-r border-zinc-800 bg-zinc-900/60 flex flex-col sticky top-0 h-screen">
        <div className="p-4 border-b border-zinc-800">
          <div className="text-lg font-bold tracking-tight">
            <span className="text-blue-400">Furbo</span>
            <span className="text-zinc-400 font-normal ml-1">Monitor</span>
          </div>
          <span className="text-[10px] text-zinc-600">v1.0</span>
        </div>

        <nav className="flex-1 p-2 space-y-1">
          <NavItem
            active={view === "live"}
            onClick={() => setView("live")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <circle cx="12" cy="12" r="3" strokeWidth={2} />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.24 7.76a6 6 0 010 8.49m-8.48-.01a6 6 0 010-8.49m11.31-2.82a10 10 0 010 14.14m-14.14 0a10 10 0 010-14.14" />
              </svg>
            }
            label="En Vivo"
            badge={liveMatches.length + upcomingMatches.length > 0 ? liveMatches.length + upcomingMatches.length : undefined}
            badgeColor={liveMatches.length > 0 ? "green" : "blue"}
          />
          <NavItem
            active={view === "finished"}
            onClick={() => setView("finished")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            label="Finalizados"
            badge={finishedMatches.length > 0 ? finishedMatches.length : undefined}
            badgeColor="zinc"
          />
        </nav>

        <div className="p-3 border-t border-zinc-800 text-[10px] text-zinc-600">
          Updated {lastRefresh.toLocaleTimeString()}
          <button
            type="button"
            onClick={refresh}
            className="ml-2 text-zinc-500 hover:text-zinc-200 transition-colors cursor-pointer"
          >
            Refresh
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0">
        {error && (
          <div className="m-4 rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400">
            {error} - Make sure the backend is running on port 8000
          </div>
        )}

        {view === "live" && (
          <LiveView
            liveMatches={liveMatches}
            upcomingMatches={upcomingMatches}
            allMatches={matches}
            system={system}
            onRefresh={refresh}
          />
        )}

        {view === "finished" && (
          <FinishedView
            matches={finishedMatches}
            onRefresh={refresh}
          />
        )}
      </main>
    </div>
  )
}

function NavItem({
  active,
  onClick,
  icon,
  label,
  badge,
  badgeColor = "zinc",
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
  badge?: number
  badgeColor?: string
}) {
  const badgeColors: Record<string, string> = {
    green: "bg-green-500/20 text-green-400",
    blue: "bg-blue-500/20 text-blue-400",
    red: "bg-red-500/20 text-red-400",
    zinc: "bg-zinc-700 text-zinc-400",
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors cursor-pointer ${
        active
          ? "bg-zinc-800 text-zinc-100"
          : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
      }`}
    >
      {icon}
      <span className="flex-1 text-left">{label}</span>
      {badge !== undefined && (
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full ${badgeColors[badgeColor] ?? badgeColors.zinc}`}>
          {badge}
        </span>
      )}
    </button>
  )
}
