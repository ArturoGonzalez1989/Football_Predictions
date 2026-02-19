import { useState, useEffect } from "react"
import { api, type Match, type MatchFull, type MomentumData, type AllCaptures } from "../lib/api"
import { MomentumChart, XgChart } from "./MomentumChart"
import { StatsBar } from "./StatsBar"
import { SiegeMeter } from "./SiegeMeter"
import { PriceVsReality } from "./PriceVsReality"
import { MomentumSwings } from "./MomentumSwings"
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts"

interface FinishedViewProps {
  matches: Match[]
  onRefresh: () => void
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

export function FinishedView({ matches, onRefresh }: FinishedViewProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [full, setFull] = useState<MatchFull | null>(null)
  const [momentum, setMomentum] = useState<MomentumData | null>(null)
  const [allCaptures, setAllCaptures] = useState<AllCaptures | null>(null)
  const [loading, setLoading] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [dateFilter, setDateFilter] = useState<string | null>(null)

  // Unique dates sorted descending
  const availableDates = Array.from(
    new Set(matches.map(m => matchDate(m.start_time)).filter(Boolean))
  ).sort((a, b) => b.localeCompare(a))

  const visibleMatches = dateFilter
    ? matches.filter(m => matchDate(m.start_time) === dateFilter)
    : matches

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
        <div className="p-4 border-b border-zinc-800 space-y-2.5">
          <div>
            <h1 className="text-lg font-semibold text-zinc-100">Finalizados</h1>
            <p className="text-xs text-zinc-500 mt-0.5">
              {visibleMatches.length}{dateFilter ? ` de ${matches.length}` : ""} partidos
            </p>
          </div>
          {availableDates.length > 1 && (
            <div className="flex flex-wrap gap-1">
              <button
                type="button"
                onClick={() => setDateFilter(null)}
                className={`px-2 py-0.5 rounded text-[10px] transition-colors ${!dateFilter ? "bg-zinc-600 text-zinc-100" : "bg-zinc-800 text-zinc-500 hover:text-zinc-300"}`}
              >Todas</button>
              {availableDates.map(d => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDateFilter(dateFilter === d ? null : d)}
                  className={`px-2 py-0.5 rounded text-[10px] transition-colors ${dateFilter === d ? "bg-blue-600/70 text-blue-100" : "bg-zinc-800 text-zinc-500 hover:text-zinc-300"}`}
                >{fmtDateChip(d)}</button>
              ))}
            </div>
          )}
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
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 overflow-hidden">
            <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-zinc-800 z-10">
                  <tr className="border-b border-zinc-700">
                    <th className="px-3 py-2 text-left font-semibold text-zinc-300 sticky left-0 bg-zinc-800">Min</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Score</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">xG H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">xG A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Poss H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Poss A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Shots H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Shots A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">On Tgt H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">On Tgt A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Corners H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Corners A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Big Ch H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Big Ch A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Passes H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Passes A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Attacks H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Attacks A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Dang Att H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Dang Att A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Fouls H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Fouls A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">YC H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">YC A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">RC H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">RC A</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Momentum H</th>
                    <th className="px-3 py-2 text-center font-semibold text-zinc-300">Momentum A</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {allCaptures.captures.map((cap, idx) => (
                    <tr key={idx} className="hover:bg-zinc-800/30">
                      <td className="px-3 py-2 font-mono text-zinc-100 sticky left-0 bg-zinc-900/95">{cap.minuto || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-100 whitespace-nowrap">
                        {cap.goles_local || "0"} - {cap.goles_visitante || "0"}
                      </td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.xg_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.xg_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.posesion_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.posesion_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.tiros_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.tiros_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.tiros_puerta_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.tiros_puerta_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.corners_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.corners_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.big_chances_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.big_chances_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.total_passes_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.total_passes_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.attacks_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.attacks_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.dangerous_attacks_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.dangerous_attacks_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.fouls_conceded_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.fouls_conceded_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.tarjetas_amarillas_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.tarjetas_amarillas_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.tarjetas_rojas_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.tarjetas_rojas_visitante || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.momentum_local || "-"}</td>
                      <td className="px-3 py-2 text-center font-mono text-zinc-300">{cap.momentum_visitante || "-"}</td>
                    </tr>
                  ))}
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
