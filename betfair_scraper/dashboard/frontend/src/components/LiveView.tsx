import { useState } from "react"
import { api, type Match, type SystemStatus as SystemStatusType } from "../lib/api"
import { MatchCard } from "./MatchCard"
import { SystemStatus } from "./SystemStatus"

interface LiveViewProps {
  liveMatches: Match[]
  system: SystemStatusType | null
  onRefresh: () => void
}

export function LiveView({ liveMatches, system, onRefresh }: LiveViewProps) {
  const [refreshing, setRefreshing] = useState(false)
  const [refreshResult, setRefreshResult] = useState<string | null>(null)

  const totalCaptures = liveMatches.reduce((sum, m) => sum + m.capture_count, 0)
  const stalledCount = liveMatches.filter(
    (m) => m.last_capture_ago_seconds != null && m.last_capture_ago_seconds > 600
  ).length

  // Freshness buckets
  const freshCount = liveMatches.filter(
    (m) => m.last_capture_ago_seconds != null && m.last_capture_ago_seconds < 60
  ).length
  const laggyCount = liveMatches.filter(
    (m) => m.last_capture_ago_seconds != null && m.last_capture_ago_seconds >= 60 && m.last_capture_ago_seconds < 180
  ).length
  const slowCount = liveMatches.filter(
    (m) => m.last_capture_ago_seconds != null && m.last_capture_ago_seconds >= 180 && m.last_capture_ago_seconds < 600
  ).length
  // Average cycle time
  const matchesWithCapture = liveMatches.filter((m) => m.last_capture_ago_seconds != null)
  const avgCycleSeconds = matchesWithCapture.length > 0
    ? Math.round(matchesWithCapture.reduce((sum, m) => sum + m.last_capture_ago_seconds!, 0) / matchesWithCapture.length)
    : null

  async function handleRefreshMatches() {
    setRefreshing(true)
    setRefreshResult(null)
    try {
      const res = await api.refreshMatches()
      const parts: string[] = []
      if (res.clean?.output) parts.push(res.clean.output)
      if (res.find?.output) parts.push(res.find.output)
      setRefreshResult(parts.join("\n") || "Done")
      onRefresh()
    } catch {
      setRefreshResult("Error connecting to backend")
    } finally {
      setRefreshing(false)
      setTimeout(() => setRefreshResult(null), 10000)
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-lg font-semibold text-zinc-100">En Vivo</h1>
        <div className="flex items-center gap-3">
          {system?.auto_refresh_enabled && (
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-blue-400 animate-pulse-dot" />
                Auto-refresh every {system.refresh_interval_minutes}m
              </span>
              {system.is_refreshing && (
                <span className="text-blue-400 font-medium">(Running...)</span>
              )}
            </div>
          )}
          <button
            type="button"
            onClick={handleRefreshMatches}
            disabled={refreshing || system?.is_refreshing}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20 transition-colors cursor-pointer disabled:opacity-50"
          >
            <svg className={`w-3.5 h-3.5 ${refreshing || system?.is_refreshing ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {refreshing || system?.is_refreshing ? "Searching..." : "Find Matches"}
          </button>
        </div>
      </div>

      {refreshResult && (
        <div className="mb-4 rounded-lg bg-zinc-800/60 border border-zinc-700 p-3 text-xs text-zinc-300 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
          {refreshResult}
        </div>
      )}

      {/* Top stats row */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-4">
        <MetricCard label="Live" value={liveMatches.length} color={liveMatches.length > 0 ? "green" : "zinc"} />
        <MetricCard label="Captures" value={totalCaptures} color="blue" />
        <MetricCard label="Stalled" value={stalledCount} color={stalledCount > 0 ? "red" : "green"} />
        <MetricCard label="Avg Cycle" value={avgCycleSeconds != null ? `${avgCycleSeconds}s` : "—"} color={avgCycleSeconds != null && avgCycleSeconds <= 60 ? "green" : avgCycleSeconds != null && avgCycleSeconds <= 120 ? "yellow" : "red"} />
        <MetricCard label="No Data" value={liveMatches.filter((m) => m.capture_count === 0).length} color={liveMatches.some((m) => m.capture_count === 0) ? "red" : "green"} />
        <MetricCard label="Min Cap" value={matchesWithCapture.length > 0 ? Math.min(...matchesWithCapture.map((m) => m.capture_count)) : 0} color="zinc" />
      </div>

      {/* Freshness bar */}
      {liveMatches.length > 0 && (
        <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900/50 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Capture Freshness</span>
            <span className="text-[10px] text-zinc-600">{liveMatches.length} matches</span>
          </div>
          <div className="flex h-3 rounded-full overflow-hidden bg-zinc-800">
            {freshCount > 0 && (
              <div className="bg-green-500 transition-all duration-500" style={{ width: `${(freshCount / liveMatches.length) * 100}%` }} title={`< 1m: ${freshCount}`} />
            )}
            {laggyCount > 0 && (
              <div className="bg-yellow-500 transition-all duration-500" style={{ width: `${(laggyCount / liveMatches.length) * 100}%` }} title={`1-3m: ${laggyCount}`} />
            )}
            {slowCount > 0 && (
              <div className="bg-orange-500 transition-all duration-500" style={{ width: `${(slowCount / liveMatches.length) * 100}%` }} title={`3-10m: ${slowCount}`} />
            )}
            {stalledCount > 0 && (
              <div className="bg-red-500 transition-all duration-500" style={{ width: `${(stalledCount / liveMatches.length) * 100}%` }} title={`> 10m: ${stalledCount}`} />
            )}
            {liveMatches.filter((m) => m.last_capture_ago_seconds == null).length > 0 && (
              <div className="bg-zinc-600 transition-all duration-500" style={{ width: `${(liveMatches.filter((m) => m.last_capture_ago_seconds == null).length / liveMatches.length) * 100}%` }} title="No data" />
            )}
          </div>
          <div className="flex items-center gap-4 mt-2 text-[10px]">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-green-500" /> &lt;1m: {freshCount}</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-yellow-500" /> 1-3m: {laggyCount}</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-orange-500" /> 3-10m: {slowCount}</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-500" /> &gt;10m: {stalledCount}</span>
            {liveMatches.some((m) => m.last_capture_ago_seconds == null) && (
              <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-zinc-600" /> No data: {liveMatches.filter((m) => m.last_capture_ago_seconds == null).length}</span>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-3">
          {liveMatches.length > 0 ? (
            <div className="space-y-3">
              {liveMatches.map((m) => (
                <MatchCard key={m.match_id} match={m} onDelete={onRefresh} />
              ))}
            </div>
          ) : (
            <div className="text-center py-16 text-zinc-500">
              <p className="text-lg mb-1">No hay partidos en vivo</p>
              <p className="text-sm">Los partidos aparecerán cuando estén en juego</p>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <SystemStatus status={system} onRefresh={onRefresh} />
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, color }: { label: string; value: number | string; color: string }) {
  const colors: Record<string, string> = {
    green: "text-green-400", blue: "text-blue-400",
    red: "text-red-400", zinc: "text-zinc-400",
    yellow: "text-yellow-400", orange: "text-orange-400",
  }
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3">
      <div className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</div>
      <div className={`text-2xl font-bold font-mono mt-0.5 ${colors[color] ?? colors.zinc}`}>{value}</div>
    </div>
  )
}
