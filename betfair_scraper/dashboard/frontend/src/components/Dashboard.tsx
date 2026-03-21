import { useState, useEffect, useCallback } from "react"
import { api, type MatchesGrouped, type SystemStatus as SystemStatusType } from "../lib/api"
import { isSoundEnabled, setSoundEnabled } from "../lib/sounds"
import { BettingSignalsView } from "./BettingSignalsView"
import { LiveView } from "./LiveView"
import { UpcomingView } from "./UpcomingView"
import { DataQualityView } from "./DataQualityView"
import { PlacedBetsView } from "./PlacedBetsView"
import { AnalyticsView } from "./AnalyticsView"
import AlertsView from "./AlertsView"
import { BacktestView } from "./BacktestView"
import { ScriptsView } from "./ScriptsView"
import { TestCasesView } from "./TestCasesView"

type View = "signals" | "bets" | "live" | "upcoming" | "quality" | "analytics" | "alerts" | "backtest" | "scripts" | "test-cases"

export function Dashboard() {
  const [view, setView] = useState<View>("signals")
  const [matches, setMatches] = useState<MatchesGrouped>({ live: [], upcoming: [], finished: [] })
  const [system, setSystem] = useState<SystemStatusType | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [error, setError] = useState<string | null>(null)
  const [soundOn, setSoundOn] = useState(isSoundEnabled)
  const [alertCounts, setAlertCounts] = useState<{ critical: number; warning: number } | null>(null)

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const r = await fetch("/api/alerts")
        if (r.ok) {
          const d = await r.json()
          setAlertCounts({ critical: d.critical ?? 0, warning: d.warning ?? 0 })
        }
      } catch { /* ignore */ }
    }
    fetchAlerts()
    const interval = setInterval(fetchAlerts, 30000)
    return () => clearInterval(interval)
  }, [])


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
            active={view === "signals"}
            onClick={() => setView("signals")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            }
            label="Señales"
            badgeColor="amber"
          />
          <NavItem
            active={view === "bets"}
            onClick={() => setView("bets")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            }
            label="Apuestas"
            badgeColor="blue"
          />
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
            badge={matches.live.length > 0 ? matches.live.length : undefined}
            badgeColor="green"
          />
          <NavItem
            active={view === "upcoming"}
            onClick={() => setView("upcoming")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            label="Próximos"
            badge={matches.upcoming.length > 0 ? matches.upcoming.length : undefined}
            badgeColor="blue"
          />

          <div className="border-t border-zinc-800 my-2" />

          <NavItem
            active={view === "quality"}
            onClick={() => setView("quality")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            }
            label="Data Quality"
          />

          <NavItem
            active={view === "analytics"}
            onClick={() => setView("analytics")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            }
            label="Paper Dashboard"
          />

          <NavItem
            active={view === "backtest"}
            onClick={() => setView("backtest")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            }
            label="Backtest"
          />

          <NavItem
            active={view === "alerts"}
            onClick={() => setView("alerts")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
            }
            label="Alertas"
            badge={
              (alertCounts?.critical ?? 0) > 0 ? alertCounts!.critical :
              (alertCounts?.warning ?? 0) > 0 ? alertCounts!.warning :
              undefined
            }
            badgeColor={(alertCounts?.critical ?? 0) > 0 ? "red" : "amber"}
          />

          <div className="border-t border-zinc-800 my-2" />

          <NavItem
            active={view === "scripts"}
            onClick={() => setView("scripts")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            }
            label="Scripts"
          />
          <NavItem
            active={view === "test-cases"}
            onClick={() => setView("test-cases")}
            icon={
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
              </svg>
            }
            label="Test Cases"
          />
        </nav>

        <div className="p-3 border-t border-zinc-800 text-[10px] text-zinc-600 flex items-center justify-between">
          <span>
            Updated {lastRefresh.toLocaleTimeString()}
            <button
              type="button"
              onClick={refresh}
              className="ml-2 text-zinc-500 hover:text-zinc-200 transition-colors cursor-pointer"
            >
              Refresh
            </button>
          </span>
          <button
            type="button"
            title={soundOn ? "Silenciar alertas" : "Activar alertas"}
            onClick={() => { const next = !soundOn; setSoundOn(next); setSoundEnabled(next) }}
            className={`p-1 rounded transition-colors cursor-pointer ${soundOn ? "text-zinc-400 hover:text-zinc-200" : "text-zinc-700 hover:text-zinc-500"}`}
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {soundOn ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.536 8.464a5 5 0 010 7.072M17.95 6.05a8 8 0 010 11.9M11 5L6 9H2v6h4l5 4V5z" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707A1 1 0 0112 5v14a1 1 0 01-1.707.707L5.586 15zM17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2" />
              )}
            </svg>
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

        <div className={view !== "signals" ? "hidden" : ""}><BettingSignalsView /></div>
        <div className={view !== "bets" ? "hidden" : ""}><PlacedBetsView /></div>
        <div className={view !== "live" ? "hidden" : ""}>
          <LiveView liveMatches={matches.live} system={system} onRefresh={refresh} />
        </div>
        <div className={view !== "upcoming" ? "hidden" : ""}><UpcomingView matches={matches.upcoming} /></div>
        <div className={view !== "quality" ? "hidden" : ""}><DataQualityView /></div>
        <div className={view !== "analytics" ? "hidden" : ""}><AnalyticsView /></div>
        <div className={view !== "alerts" ? "hidden" : ""}><AlertsView /></div>
        <div className={view !== "backtest" ? "hidden" : ""}><BacktestView /></div>
        <div className={view !== "scripts" ? "hidden" : ""}><ScriptsView /></div>
        <div className={view !== "test-cases" ? "hidden" : ""}><TestCasesView /></div>
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
    amber: "bg-amber-500/20 text-amber-400",
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
