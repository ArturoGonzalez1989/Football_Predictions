import { useState, useEffect } from "react"
import { api, type Match, type MatchFull, type MomentumData, type AllCaptures, type Capture, type OddsTimeline } from "../lib/api"
import { MomentumChart, XgChart } from "./MomentumChart"
import { StatsBar } from "./StatsBar"
import { SiegeMeter } from "./SiegeMeter"
import { PriceVsReality } from "./PriceVsReality"
import { MomentumSwings } from "./MomentumSwings"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts"

// ── All Captures column definitions ──────────────────────────────────────────

type CaptureCol = {
  label: string
  oddsCol?: boolean
  render: (cap: Capture, odds: OddsTimeline | undefined) => string
}
type ColGroup = { id: string; label: string; cols: CaptureCol[] }

const CAPTURE_GROUPS: ColGroup[] = [
  { id: "xg", label: "xG", cols: [
    { label: "xG H",     render: c => c.xg_local || "-" },
    { label: "xG A",     render: c => c.xg_visitante || "-" },
  ]},
  { id: "poss", label: "Posesión", cols: [
    { label: "Pos H",    render: c => c.posesion_local || "-" },
    { label: "Pos A",    render: c => c.posesion_visitante || "-" },
  ]},
  { id: "shots", label: "Tiros", cols: [
    { label: "Shots H",  render: c => c.tiros_local || "-" },
    { label: "Shots A",  render: c => c.tiros_visitante || "-" },
    { label: "OnTgt H",  render: c => c.tiros_puerta_local || "-" },
    { label: "OnTgt A",  render: c => c.tiros_puerta_visitante || "-" },
    { label: "Blk H",    render: c => c.blocked_shots_local || "-" },
    { label: "Blk A",    render: c => c.blocked_shots_visitante || "-" },
  ]},
  { id: "corners", label: "Córners", cols: [
    { label: "Cor H",    render: c => c.corners_local || "-" },
    { label: "Cor A",    render: c => c.corners_visitante || "-" },
  ]},
  { id: "bigch", label: "Big Ch", cols: [
    { label: "Big Ch H", render: c => c.big_chances_local || "-" },
    { label: "Big Ch A", render: c => c.big_chances_visitante || "-" },
  ]},
  { id: "passes", label: "Pases", cols: [
    { label: "Pass H",   render: c => c.total_passes_local || "-" },
    { label: "Pass A",   render: c => c.total_passes_visitante || "-" },
    { label: "Tack H",   render: c => c.tackles_local || "-" },
    { label: "Tack A",   render: c => c.tackles_visitante || "-" },
  ]},
  { id: "attacks", label: "Ataques", cols: [
    { label: "Att H",    render: c => c.attacks_local || "-" },
    { label: "Att A",    render: c => c.attacks_visitante || "-" },
    { label: "DngAtt H", render: c => c.dangerous_attacks_local || "-" },
    { label: "DngAtt A", render: c => c.dangerous_attacks_visitante || "-" },
  ]},
  { id: "cards", label: "Faltas/TJ", cols: [
    { label: "Fouls H",  render: c => c.fouls_conceded_local || "-" },
    { label: "Fouls A",  render: c => c.fouls_conceded_visitante || "-" },
    { label: "YC H",     render: c => c.tarjetas_amarillas_local || "-" },
    { label: "YC A",     render: c => c.tarjetas_amarillas_visitante || "-" },
    { label: "RC H",     render: c => c.tarjetas_rojas_local || "-" },
    { label: "RC A",     render: c => c.tarjetas_rojas_visitante || "-" },
  ]},
  { id: "momentum", label: "Momentum", cols: [
    { label: "Mom H",    render: c => { const v = parseFloat(c.momentum_local); return isNaN(v) ? "-" : v.toFixed(0) } },
    { label: "Mom A",    render: c => { const v = parseFloat(c.momentum_visitante); return isNaN(v) ? "-" : v.toFixed(0) } },
  ]},
  { id: "extra", label: "Extra", cols: [
    { label: "Saves H",   render: c => c.saves_local || "-" },
    { label: "Saves A",   render: c => c.saves_visitante || "-" },
    { label: "Offside H", render: c => c.offsides_local || "-" },
    { label: "Offside A", render: c => c.offsides_visitante || "-" },
    { label: "OptaPts H", render: c => c.opta_points_local || "-" },
    { label: "OptaPts A", render: c => c.opta_points_visitante || "-" },
  ]},
  { id: "odds1x2", label: "Cuotas 1X2", cols: [
    { label: "B.Home",   render: (_, o) => o?.back_home?.toFixed(2) ?? "-",   oddsCol: true },
    { label: "L.Home",   render: (_, o) => o?.lay_home?.toFixed(2) ?? "-",    oddsCol: true },
    { label: "B.Draw",   render: (_, o) => o?.back_draw?.toFixed(2) ?? "-",   oddsCol: true },
    { label: "L.Draw",   render: (_, o) => o?.lay_draw?.toFixed(2) ?? "-",    oddsCol: true },
    { label: "B.Away",   render: (_, o) => o?.back_away?.toFixed(2) ?? "-",   oddsCol: true },
    { label: "L.Away",   render: (_, o) => o?.lay_away?.toFixed(2) ?? "-",    oddsCol: true },
  ]},
  { id: "oddsou", label: "Cuotas O/U", cols: [
    { label: "B.O0.5",   render: (_, o) => o?.back_over05?.toFixed(2) ?? "-",  oddsCol: true },
    { label: "B.O1.5",   render: (_, o) => o?.back_over15?.toFixed(2) ?? "-",  oddsCol: true },
    { label: "B.O2.5",   render: (_, o) => o?.back_over25?.toFixed(2) ?? "-",  oddsCol: true },
    { label: "B.O3.5",   render: (_, o) => o?.back_over35?.toFixed(2) ?? "-",  oddsCol: true },
    { label: "B.U1.5",   render: (_, o) => o?.back_under15?.toFixed(2) ?? "-", oddsCol: true },
    { label: "B.U2.5",   render: (_, o) => o?.back_under25?.toFixed(2) ?? "-", oddsCol: true },
  ]},
]

// ── FinishedView ──────────────────────────────────────────────────────────────

interface FinishedViewProps {
  matches: Match[]
  onRefresh: () => void
  initialMatchId?: string
}

// Extract "YYYY-MM-DD" from a start_time string (local date)
function matchDate(startTime: string | undefined | null): string {
  if (!startTime) return ""
  const d = new Date(startTime)
  return isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-CA") // "YYYY-MM-DD"
}

function fmtDateChip(isoDate: string): string {
  const d = new Date(isoDate + "T12:00:00")
  return d.toLocaleDateString("es-ES", { day: "numeric", month: "short" }) // "18 feb"
}

export function FinishedView({ matches, onRefresh, initialMatchId }: FinishedViewProps) {
  const [selectedId, setSelectedId] = useState<string | null>(initialMatchId ?? null)
  const [full, setFull] = useState<MatchFull | null>(null)
  const [momentum, setMomentum] = useState<MomentumData | null>(null)
  const [allCaptures, setAllCaptures] = useState<AllCaptures | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [dateFilter, setDateFilter] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState("")

  // Unique dates sorted descending
  const availableDates = Array.from(
    new Set(matches.map(m => matchDate(m.start_time)).filter(Boolean))
  ).sort((a, b) => b.localeCompare(a))

  const visibleMatches = matches.filter(m => {
    if (dateFilter && matchDate(m.start_time) !== dateFilter) return false
    if (searchQuery && !m.name.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  useEffect(() => {
    if (!selectedId) { setFull(null); setMomentum(null); setAllCaptures(null); return }
    setLoading(true)
    Promise.all([
      api.getMatchFull(selectedId),
      api.getMatchMomentum(selectedId),
      api.getAllCaptures(selectedId),
    ]).then(([f, m, a]) => {
      setFull(f)
      setMomentum(m)
      setAllCaptures(a)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [selectedId])

  // Navigate to initialMatchId when it changes (e.g. deep-link from Explorer)
  useEffect(() => {
    if (!initialMatchId) return
    setDateFilter(null)      // show all dates so the match is visible
    setSearchQuery("")        // clear search so the match is visible
    setSelectedId(initialMatchId)
  }, [initialMatchId])

  // Auto-select first visible match
  useEffect(() => {
    if (!selectedId && visibleMatches.length > 0) setSelectedId(visibleMatches[0].match_id)
  }, [visibleMatches, selectedId])

  // When filter changes, clear selection if no longer visible
  useEffect(() => {
    if (selectedId && !visibleMatches.find(m => m.match_id === selectedId)) {
      setSelectedId(visibleMatches[0]?.match_id ?? null)
    }
  }, [dateFilter])

  const selected = matches.find(m => m.match_id === selectedId)

  const handleDelete = async (matchId: string) => {
    setDeleting(true)
    try {
      await api.deleteMatch(matchId)
      if (selectedId === matchId) setSelectedId(null)
      onRefresh()
    } catch { /* ignore */ }
    setDeleting(false)
    setConfirmDelete(null)
  }

  return (
    <div className="flex h-screen">
      {/* Match list panel */}
      <div className="w-72 shrink-0 border-r border-zinc-800 overflow-y-auto">
        <div className="p-4 border-b border-zinc-800 space-y-2">
          <h1 className="text-lg font-semibold text-zinc-100">Finalizados</h1>
          <div className="flex items-center gap-2">
            <select
              value={dateFilter ?? ""}
              onChange={e => setDateFilter(e.target.value || null)}
              title="Filtrar por fecha"
              className="flex-1 px-2 py-1 rounded bg-zinc-800 border border-zinc-700 text-xs text-zinc-300 focus:outline-none focus:border-zinc-500"
            >
              <option value="">Todas las fechas ({matches.length})</option>
              {availableDates.map(d => (
                <option key={d} value={d}>{fmtDateChip(d)} — {matches.filter(m => matchDate(m.start_time) === d).length} partidos</option>
              ))}
            </select>
          </div>
          <div className="relative">
            <input
              type="text"
              placeholder="Buscar equipo…"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-7 pr-7 py-1 rounded bg-zinc-800 border border-zinc-700 text-xs text-zinc-300 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
            />
            <span className="absolute left-2 top-1/2 -translate-y-1/2 text-zinc-600 text-xs pointer-events-none">🔍</span>
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300 text-xs leading-none"
              >
                ✕
              </button>
            )}
          </div>
        </div>
        {visibleMatches.length === 0 ? (
          <div className="p-6 text-center text-zinc-500 text-sm">
            No hay partidos para esta fecha
          </div>
        ) : (
          <div className="divide-y divide-zinc-800/50">
            {visibleMatches.map(m => {
              const [home, away] = m.name.split(" - ")
              return (
                <div key={m.match_id} className={`relative group ${selectedId === m.match_id ? "bg-zinc-800/50" : "hover:bg-zinc-800/30"}`}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(m.match_id)}
                    className="w-full text-left p-3 cursor-pointer"
                  >
                    <div className="text-sm font-medium text-zinc-200 truncate">
                      {home} <span className="text-zinc-500">vs</span> {away}
                    </div>
                    <div className="flex items-center gap-2 mt-1 text-[11px] text-zinc-500">
                      <span>{m.capture_count} captures</span>
                      {m.start_time && (
                        <span>{new Date(m.start_time).toLocaleDateString()}</span>
                      )}
                    </div>
                  </button>
                  {/* Delete */}
                  <div className="absolute right-2 top-2">
                    {confirmDelete === m.match_id ? (
                      <div className="flex items-center gap-1 bg-zinc-900 rounded px-1">
                        <button type="button" onClick={() => handleDelete(m.match_id)} disabled={deleting}
                          className="text-[10px] text-red-400 hover:text-red-300 cursor-pointer disabled:opacity-50">
                          {deleting ? "..." : "Yes"}
                        </button>
                        <button type="button" onClick={() => setConfirmDelete(null)}
                          className="text-[10px] text-zinc-400 hover:text-zinc-200 cursor-pointer">No</button>
                      </div>
                    ) : (
                      <button type="button" onClick={() => setConfirmDelete(m.match_id)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/10 text-zinc-600 hover:text-red-400 transition-all cursor-pointer"
                        title="Delete match">
                        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Detail panel */}
      <div className="flex-1 overflow-y-auto">
        {!selected ? (
          <div className="flex items-center justify-center h-full text-zinc-500">
            Select a match to view details
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center h-full text-zinc-500">
            Loading match data...
          </div>
        ) : full && full.rows > 0 ? (
          <MatchDetail match={selected} full={full} momentum={momentum} allCaptures={allCaptures} />
        ) : full ? (
          <div className="flex items-center justify-center h-full text-zinc-500">
            No capture data available for this match
          </div>
        ) : null}
      </div>
    </div>
  )
}

function MatchDetail({ match, full, momentum, allCaptures }: { match: Match; full: MatchFull; momentum: MomentumData | null; allCaptures: AllCaptures | null }) {
  const [home, away] = match.name.split(" - ")
  const s = full.final_stats ?? {}
  const golesH = String(s.goles_local ?? "?")
  const golesA = String(s.goles_visitante ?? "?")

  // All Captures column visibility
  const [visGroups, setVisGroups] = useState<Set<string>>(
    () => new Set(["xg", "poss", "shots", "corners", "bigch", "attacks", "cards", "odds1x2"])
  )
  const toggleGroup = (id: string) => setVisGroups(prev => {
    const next = new Set(prev)
    next.has(id) ? next.delete(id) : next.add(id)
    return next
  })
  // Returns the most recent OddsTimeline entry at or before `min`
  const getOddsAt = (min: number): OddsTimeline | undefined => {
    let best: OddsTimeline | undefined
    for (const ot of (full.odds_timeline ?? [])) {
      if (ot.minute == null || ot.minute > min) continue
      if (!best || ot.minute > best.minute!) best = ot
    }
    return best
  }
  const visibleCols = CAPTURE_GROUPS.filter(g => visGroups.has(g.id)).flatMap(g => g.cols)

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-zinc-100">
            {home} <span className="text-zinc-500 mx-2">vs</span> {away}
          </h2>
          <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
            {match.start_time && <span>{new Date(match.start_time).toLocaleString()}</span>}
            <span>{full.rows} captures</span>
            <a href={match.url} target="_blank" rel="noopener noreferrer"
              className="text-blue-400 hover:text-blue-300">
              Betfair &rarr;
            </a>
          </div>
        </div>
        <div className="text-4xl font-bold font-mono text-zinc-100">
          {golesH} <span className="text-zinc-600">-</span> {golesA}
        </div>
      </div>

      {/* Key Stats */}
      <section className="space-y-2">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Statistics</h3>
        <div className="space-y-1">
          <StatsBar label="xG" homeValue={fmt(s.xg_local)} awayValue={fmt(s.xg_visitante)} />
          <StatsBar label="Possession" homeValue={fmt(s.posesion_local)} awayValue={fmt(s.posesion_visitante)} />
          <StatsBar label="Shots" homeValue={fmt(s.tiros_local)} awayValue={fmt(s.tiros_visitante)} />
          <StatsBar label="On Target" homeValue={fmt(s.tiros_puerta_local)} awayValue={fmt(s.tiros_puerta_visitante)} />
          <StatsBar label="Corners" homeValue={fmt(s.corners_local)} awayValue={fmt(s.corners_visitante)} />
          <StatsBar label="Big Chances" homeValue={fmt(s.big_chances_local)} awayValue={fmt(s.big_chances_visitante)} />
          <StatsBar label="Passes" homeValue={fmt(s.total_passes_local)} awayValue={fmt(s.total_passes_visitante)} />
          <StatsBar label="Fouls" homeValue={fmt(s.fouls_conceded_local)} awayValue={fmt(s.fouls_conceded_visitante)} />
          <StatsBar label="Tackles" homeValue={fmt(s.tackles_local)} awayValue={fmt(s.tackles_visitante)} />
          <StatsBar label="Saves" homeValue={fmt(s.saves_local)} awayValue={fmt(s.saves_visitante)} />
          <StatsBar label="Yellows" homeValue={fmt(s.tarjetas_amarillas_local)} awayValue={fmt(s.tarjetas_amarillas_visitante)} />
          <StatsBar label="Reds" homeValue={fmt(s.tarjetas_rojas_local)} awayValue={fmt(s.tarjetas_rojas_visitante)} />
          <StatsBar label="Attacks" homeValue={fmt(s.attacks_local)} awayValue={fmt(s.attacks_visitante)} />
          <StatsBar label="Dang. Attacks" homeValue={fmt(s.dangerous_attacks_local)} awayValue={fmt(s.dangerous_attacks_visitante)} />
        </div>
      </section>

      {/* ── Trading Intelligence ── */}
      {allCaptures && allCaptures.captures.length >= 5 && (
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <div className="h-px flex-1 bg-gradient-to-r from-cyan-500/40 to-transparent" />
            <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest">
              Trading Intelligence
            </span>
            <div className="h-px flex-1 bg-gradient-to-l from-fuchsia-500/40 to-transparent" />
          </div>

          <SiegeMeter
            captures={allCaptures.captures}
            homeName={home ?? "Home"}
            awayName={away ?? "Away"}
          />

          {full.odds_timeline && full.odds_timeline.length > 0 && (
            <PriceVsReality
              captures={allCaptures.captures}
              oddsTimeline={full.odds_timeline}
              homeName={home ?? "Home"}
            />
          )}

          <MomentumSwings
            captures={allCaptures.captures}
            homeName={home ?? "Home"}
            awayName={away ?? "Away"}
          />
        </section>
      )}

      {/* Momentum */}
      <MomentumChart data={momentum} />

      {/* xG */}
      <XgChart data={momentum} />

      {/* Odds */}
      <section className="space-y-3">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Odds</h3>
        <div className="grid grid-cols-3 gap-3">
          <OddsCard label="Home" opening={full.opening_odds?.back_home} closing={full.closing_odds?.back_home} />
          <OddsCard label="Draw" opening={full.opening_odds?.back_draw} closing={full.closing_odds?.back_draw} />
          <OddsCard label="Away" opening={full.opening_odds?.back_away} closing={full.closing_odds?.back_away} />
        </div>

        {/* Over/Under */}
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {(["15", "25", "35"] as const).map(g => (
            <div key={g} className="rounded-lg bg-zinc-800/50 p-2.5 text-xs">
              <div className="text-zinc-500 text-[10px] uppercase mb-1">O/U {g[0]}.{g[1]}</div>
              <div className="flex justify-between">
                <span className="text-green-400">O: {fmtOdds(full.closing_odds?.[`back_over${g}`])}</span>
                <span className="text-red-400">U: {fmtOdds(full.closing_odds?.[`back_under${g}`])}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Volume */}
        {full.volume_matched && (
          <div className="text-xs text-zinc-500">
            Volume matched: <span className="text-zinc-300 font-mono">{full.volume_matched.toLocaleString()}</span>
          </div>
        )}
      </section>

      {/* Odds Timeline */}
      {(full.odds_timeline?.length ?? 0) > 5 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Odds Movement</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={full.odds_timeline} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="minute"
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
                tickFormatter={(v) => v != null ? `${v}'` : ""}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
                domain={["auto", "auto"]}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
                labelFormatter={(v) => v != null ? `Minute ${v}'` : "Pre-match"}
              />
              <Line type="monotone" dataKey="back_home" stroke="#3b82f6" strokeWidth={2} name="Home" dot={false} connectNulls />
              <Line type="monotone" dataKey="back_draw" stroke="#a1a1aa" strokeWidth={1.5} name="Draw" dot={false} connectNulls />
              <Line type="monotone" dataKey="back_away" stroke="#ef4444" strokeWidth={2} name="Away" dot={false} connectNulls />
              <Legend iconType="line" wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }} />
            </LineChart>
          </ResponsiveContainer>
        </section>
      )}

      {/* All Captures Table */}
      {allCaptures && allCaptures.captures.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
            All Captures ({allCaptures.captures.length} rows)
          </h3>

          {/* Column group toggles */}
          <div className="flex flex-wrap gap-1.5 pb-1">
            {CAPTURE_GROUPS.map(g => {
              const on = visGroups.has(g.id)
              const isOdds = g.id.startsWith("odds")
              return (
                <button key={g.id} type="button" onClick={() => toggleGroup(g.id)}
                  className={`text-[10px] px-2 py-0.5 rounded font-medium transition-colors cursor-pointer border
                    ${on
                      ? isOdds
                        ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                        : "bg-blue-500/15 text-blue-300 border-blue-500/30"
                      : "bg-zinc-800 text-zinc-600 border-zinc-700 hover:text-zinc-400"
                    }`}
                >
                  {on ? "✓" : "+"} {g.label}
                </button>
              )
            })}
          </div>

          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 overflow-hidden">
            <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-zinc-800 z-10">
                  <tr className="border-b border-zinc-700">
                    <th className="px-3 py-2 text-left font-semibold text-zinc-300 sticky left-0 bg-zinc-800 z-20">Min</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Score</th>
                    {visibleCols.map((col, ci) => (
                      <th key={ci} className={`px-2 py-2 text-center font-semibold whitespace-nowrap text-[10px]
                        ${col.oddsCol ? "text-amber-400/80" : "text-zinc-400"}`}>
                        {col.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {allCaptures.captures.map((cap, idx) => {
                    const min = parseFloat(cap.minuto)
                    const odds = isNaN(min) ? undefined : getOddsAt(min)
                    return (
                      <tr key={idx} className="hover:bg-zinc-800/30">
                        <td className="px-3 py-1.5 font-mono text-zinc-100 sticky left-0 bg-zinc-900/95">{cap.minuto || "-"}</td>
                        <td className="px-3 py-1.5 text-center font-mono text-zinc-100 whitespace-nowrap">
                          {cap.goles_local || "0"} - {cap.goles_visitante || "0"}
                        </td>
                        {visibleCols.map((col, ci) => (
                          <td key={ci} className={`px-2 py-1.5 text-center font-mono
                            ${col.oddsCol ? "text-amber-300/80" : "text-zinc-300"}`}>
                            {col.render(cap, odds)}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}

function OddsCard({ label, opening, closing }: { label: string; opening: number | null | undefined; closing: number | null | undefined }) {
  const diff = opening && closing ? closing - opening : null
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3">
      <div className="text-[10px] text-zinc-500 uppercase tracking-wider">{label}</div>
      <div className="text-xl font-bold font-mono text-zinc-100 mt-0.5">
        {fmtOdds(closing)}
      </div>
      {opening != null && (
        <div className="text-[10px] text-zinc-600 mt-0.5">
          Open: {fmtOdds(opening)}
          {diff != null && diff !== 0 && (
            <span className={diff > 0 ? "text-red-400 ml-1" : "text-green-400 ml-1"}>
              {diff > 0 ? "+" : ""}{diff.toFixed(2)}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

function fmt(v: unknown): string {
  if (v == null) return "-"
  return String(v)
}

function fmtOdds(v: number | null | undefined): string {
  if (v == null) return "-"
  return v.toFixed(2)
}
