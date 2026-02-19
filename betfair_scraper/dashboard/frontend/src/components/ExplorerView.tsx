import { useState, useEffect } from "react"
import { api, type ExplorationRun, type ExplorerResult } from "../lib/api"
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from "recharts"

// ── Constantes ────────────────────────────────────────────────────────────────

const TARGET_COLORS: Record<string, string> = {
  // Back — colores vivos
  draw:             "#06b6d4",
  over_05:          "#22c55e",
  over_15:          "#84cc16",
  over_25:          "#eab308",
  under_15:         "#10b981",
  under_25:         "#14b8a6",
  over_35:          "#ef4444",
  home_win:         "#3b82f6",
  away_win:         "#f97316",
  btts:             "#a855f7",
  // Lay — tonos más oscuros del mismo color base
  lay_draw:         "#0e7490",
  lay_home:         "#1d4ed8",
  lay_away:         "#c2410c",
  lay_over_05:      "#166534",
  lay_over_15:      "#3f6212",
  lay_over_25:      "#92400e",
  lay_under_15:     "#065f46",
  lay_under_25:     "#115e59",
  lay_over_35:      "#7f1d1d",
  lay_score_actual: "#6d28d9",
}

const TARGET_LABELS: Record<string, string> = {
  // Back
  draw:             "Empate",
  over_05:          "Over 0.5",
  over_15:          "Over 1.5",
  over_25:          "Over 2.5",
  under_15:         "Under 1.5",
  under_25:         "Under 2.5",
  over_35:          "Over 3.5",
  home_win:         "Victoria Local",
  away_win:         "Victoria Visitante",
  btts:             "BTTS",
  // Lay
  lay_draw:         "Lay Empate",
  lay_home:         "Lay Local",
  lay_away:         "Lay Visitante",
  lay_over_05:      "Lay Over 0.5",
  lay_over_15:      "Lay Over 1.5",
  lay_over_25:      "Lay Over 2.5",
  lay_under_15:     "Lay Under 1.5",
  lay_under_25:     "Lay Under 2.5",
  lay_over_35:      "Lay Over 3.5",
  lay_score_actual: "Lay Score Actual",
}

const ALL_TARGETS = Object.keys(TARGET_LABELS)

type SortCol = keyof Pick<ExplorerResult, "minute" | "n_matches" | "win_rate" | "avg_odds" | "ev_pct" | "total_pl">

// ── Subcomponentes ────────────────────────────────────────────────────────────

function ProfitableRow({ result, rank }: { result: ExplorerResult; rank: number }) {
  const evPct = result.ev_pct * 100
  const color = TARGET_COLORS[result.target] ?? "#52525b"
  return (
    <div
      className="flex items-center gap-3 px-4 py-2 hover:bg-zinc-800/30 transition-colors"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      <span className="text-[10px] text-zinc-600 w-5 text-right shrink-0">#{rank}</span>
      <span className="text-xs text-zinc-300 truncate flex-1 min-w-0">{result.condition}</span>
      <span
        className="text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0 whitespace-nowrap"
        style={{ backgroundColor: color + "25", color }}
      >
        {TARGET_LABELS[result.target] ?? result.target}
      </span>
      <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0
        ${result.bet_type === "lay" ? "bg-orange-500/15 text-orange-400" : "bg-blue-500/15 text-blue-400"}`}>
        {result.bet_type === "lay" ? "LAY" : "BACK"}
      </span>
      <span className="text-[10px] text-zinc-500 shrink-0">{result.minute}'</span>
      <span className="text-[10px] text-zinc-600 shrink-0 tabular-nums">N:{result.n_matches}</span>
      <span className="text-[10px] text-zinc-500 shrink-0 tabular-nums w-9 text-right">
        {(result.win_rate * 100).toFixed(0)}%
      </span>
      <span className="text-xs font-bold tabular-nums shrink-0 w-16 text-right text-emerald-400">
        +{evPct.toFixed(1)}%
      </span>
      <span className={`text-[10px] tabular-nums shrink-0 w-14 text-right
        ${result.total_pl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
        {result.total_pl >= 0 ? "+" : ""}{result.total_pl.toFixed(0)}€
      </span>
    </div>
  )
}

function SortHeader({
  col,
  label,
  current,
  dir,
  onSort,
}: {
  col: SortCol
  label: string
  current: SortCol
  dir: "asc" | "desc"
  onSort: (col: SortCol) => void
}) {
  const active = col === current
  return (
    <th
      className={`px-3 py-2 text-right text-[10px] uppercase tracking-wide cursor-pointer select-none whitespace-nowrap
        ${active ? "text-blue-400" : "text-zinc-500 hover:text-zinc-300"}`}
      onClick={() => onSort(col)}
    >
      {label} {active ? (dir === "desc" ? "↓" : "↑") : ""}
    </th>
  )
}

// ── Componente principal ──────────────────────────────────────────────────────

export function ExplorerView() {
  const [run, setRun] = useState<ExplorationRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filtros
  const [minBets, setMinBets] = useState(5)
  const [minEVFilter, setMinEVFilter] = useState(-999)   // mostrar todo por defecto
  const [targetFilter, setTargetFilter] = useState("all")
  const [betTypeFilter, setBetTypeFilter] = useState<"all" | "back" | "lay">("all")
  const [minuteMin, setMinuteMin] = useState(15)
  const [minuteMax, setMinuteMax] = useState(80)
  const [sortCol, setSortCol] = useState<SortCol>("ev_pct")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")

  // Carga inicial
  useEffect(() => {
    api.getExplorerResults()
      .then(data => setRun(data))
      .catch(() => setRun(null))
      .finally(() => setLoading(false))
  }, [])

  const handleRun = async () => {
    setRunning(true)
    setError(null)
    try {
      const data = await api.runExploration(minBets)
      setRun(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al ejecutar el explorador")
    } finally {
      setRunning(false)
    }
  }

  const handleSort = (col: SortCol) => {
    if (col === sortCol) {
      setSortDir(d => d === "desc" ? "asc" : "desc")
    } else {
      setSortCol(col)
      setSortDir("desc")
    }
  }

  // Resultados filtrados + ordenados
  const filtered: ExplorerResult[] = (run?.results ?? [])
    .filter(r =>
      r.n_matches >= minBets &&
      r.ev_pct * 100 >= minEVFilter &&
      (targetFilter === "all" || r.target === targetFilter) &&
      (betTypeFilter === "all" || (r.bet_type ?? "back") === betTypeFilter) &&
      r.minute >= minuteMin &&
      r.minute <= minuteMax
    )
    .sort((a, b) => {
      const dir = sortDir === "desc" ? -1 : 1
      const aVal = a[sortCol] as number ?? 0
      const bVal = b[sortCol] as number ?? 0
      return dir * (aVal - bVal)
    })

  // Todas las combinaciones EV > 0, ordenadas por EV% desc (respeta filtros activos)
  const profitable = filtered
    .filter(r => r.ev_pct > 0)
    .sort((a, b) => b.ev_pct - a.ev_pct)

  // Datos del scatter agrupados por target
  const scatterByTarget: Record<string, { x: number; y: number; z: number; cond: string; wr: number }[]> = {}
  for (const r of filtered) {
    if (!scatterByTarget[r.target]) scatterByTarget[r.target] = []
    scatterByTarget[r.target].push({
      x: r.minute,
      y: Math.round(r.ev_pct * 1000) / 10,  // EV%
      z: Math.min(r.n_matches, 60),           // cap visual
      cond: r.condition,
      wr: Math.round(r.win_rate * 1000) / 10,
    })
  }

  const runAt = run?.run_at ? new Date(run.run_at).toLocaleString("es-ES") : null

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center h-64">
        <div className="text-zinc-500 text-sm">Cargando explorador...</div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Explorador de Estrategias</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Grid search exhaustivo: todos los minutos × condiciones × resultados posibles
          </p>
          {run && (
            <p className="text-xs text-zinc-600 mt-0.5">
              {run.n_total_matches} partidos analizados · {run.n_results} combinaciones evaluadas
              {runAt && ` · Ejecutado ${runAt}`}
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={handleRun}
          disabled={running}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors
            ${running
              ? "bg-zinc-800 text-zinc-500 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-500 text-white cursor-pointer"
            }`}
        >
          {running ? (
            <>
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
              </svg>
              Ejecutando...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {run ? "Re-ejecutar" : "Ejecutar Exploración"}
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {!run && !running && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-12 text-center">
          <div className="text-4xl mb-3">🔍</div>
          <div className="text-zinc-400 font-medium mb-1">No hay resultados todavía</div>
          <div className="text-zinc-600 text-sm">
            Haz clic en "Ejecutar Exploración" para analizar todos los partidos históricos
          </div>
        </div>
      )}

      {run && (
        <>
          {/* Combinaciones rentables */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
            <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center justify-between">
              <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                Combinaciones Rentables (EV+)
              </h2>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">
                {profitable.length} oportunidades
              </span>
            </div>
            <div className="overflow-y-auto max-h-80 divide-y divide-zinc-800/50">
              {profitable.length === 0 ? (
                <div className="px-4 py-6 text-center text-zinc-600 text-xs">
                  Ninguna combinación con EV positivo con los filtros actuales
                </div>
              ) : (
                profitable.map((r, i) => (
                  <ProfitableRow key={`${r.minute}-${r.condition_id}-${r.target}`} result={r} rank={i + 1} />
                ))
              )}
            </div>
          </div>

          {/* Filtros */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
            <div className="flex flex-wrap gap-4 items-end">
              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Min apuestas</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range" min={3} max={30} step={1} value={minBets}
                    onChange={e => setMinBets(Number(e.target.value))}
                    className="w-24 accent-blue-500"
                  />
                  <span className="text-sm text-zinc-300 w-4 text-right">{minBets}</span>
                </div>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Min EV%</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range" min={-50} max={30} step={1} value={minEVFilter}
                    onChange={e => setMinEVFilter(Number(e.target.value))}
                    className="w-24 accent-blue-500"
                  />
                  <span className="text-sm text-zinc-300 w-8 text-right">
                    {minEVFilter <= -50 ? "—" : `${minEVFilter}%`}
                  </span>
                </div>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Tipo</span>
                <div className="flex rounded overflow-hidden border border-zinc-700 text-xs">
                  {(["all", "back", "lay"] as const).map(t => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setBetTypeFilter(t)}
                      className={`px-3 py-1.5 font-medium transition-colors cursor-pointer
                        ${betTypeFilter === t
                          ? "bg-blue-600 text-white"
                          : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"}`}
                    >
                      {t === "all" ? "Todos" : t === "back" ? "Back" : "Lay"}
                    </button>
                  ))}
                </div>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Target</span>
                <select
                  value={targetFilter}
                  onChange={e => setTargetFilter(e.target.value)}
                  className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-sm text-zinc-300"
                >
                  <option value="all">Todos</option>
                  {ALL_TARGETS
                    .filter(t => betTypeFilter === "all" || (betTypeFilter === "lay" ? t.startsWith("lay_") : !t.startsWith("lay_")))
                    .map(t => (
                      <option key={t} value={t}>{TARGET_LABELS[t]}</option>
                    ))}
                </select>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Minuto min</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range" min={15} max={80} step={5} value={minuteMin}
                    onChange={e => setMinuteMin(Math.min(Number(e.target.value), minuteMax - 5))}
                    className="w-24 accent-blue-500"
                  />
                  <span className="text-sm text-zinc-300 w-4">{minuteMin}'</span>
                </div>
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Minuto max</span>
                <div className="flex items-center gap-2">
                  <input
                    type="range" min={15} max={80} step={5} value={minuteMax}
                    onChange={e => setMinuteMax(Math.max(Number(e.target.value), minuteMin + 5))}
                    className="w-24 accent-blue-500"
                  />
                  <span className="text-sm text-zinc-300 w-4">{minuteMax}'</span>
                </div>
              </label>

              <div className="text-xs text-zinc-600 ml-auto self-end">
                {filtered.length} combinaciones
              </div>
            </div>
          </div>

          {/* Scatter chart */}
          {filtered.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide mb-3">
                EV% por Minuto (tamaño = N apuestas)
              </h2>
              <ResponsiveContainer width="100%" height={280}>
                <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    type="number" dataKey="x" domain={[10, 85]}
                    label={{ value: "Minuto", position: "insideBottom", offset: -10, fill: "#71717a", fontSize: 11 }}
                    tick={{ fill: "#71717a", fontSize: 11 }}
                  />
                  <YAxis
                    type="number" dataKey="y"
                    label={{ value: "EV%", angle: -90, position: "insideLeft", fill: "#71717a", fontSize: 11 }}
                    tick={{ fill: "#71717a", fontSize: 11 }}
                    tickFormatter={v => `${v}%`}
                  />
                  <ZAxis type="number" dataKey="z" range={[30, 500]} />
                  <ReferenceLine y={0} stroke="#52525b" strokeDasharray="4 2" />
                  <Tooltip
                    cursor={{ strokeDasharray: "3 3" }}
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null
                      const d = payload[0]?.payload as { x: number; y: number; z: number; cond: string; wr: number }
                      return (
                        <div className="bg-zinc-800 border border-zinc-700 rounded p-2 text-xs text-zinc-200 max-w-xs">
                          <div className="font-medium mb-1">{d.cond}</div>
                          <div>Minuto: {d.x}' · EV: {d.y > 0 ? "+" : ""}{d.y.toFixed(1)}%</div>
                          <div>Win rate: {d.wr.toFixed(1)}% · N: {d.z}</div>
                        </div>
                      )
                    }}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                    formatter={(value) => TARGET_LABELS[value] ?? value}
                  />
                  {ALL_TARGETS.filter(t => targetFilter === "all" || t === targetFilter).map(target => {
                    const data = scatterByTarget[target] ?? []
                    if (data.length === 0) return null
                    return (
                      <Scatter
                        key={target}
                        name={target}
                        data={data}
                        fill={TARGET_COLORS[target]}
                        fillOpacity={0.7}
                      />
                    )
                  })}
                </ScatterChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Tabla de resultados */}
          {filtered.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
              <div className="px-4 py-2 border-b border-zinc-800 flex items-center justify-between">
                <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                  Tabla de combinaciones
                </h2>
                <span className="text-[10px] text-zinc-600">
                  Mostrando {Math.min(filtered.length, 150)} de {filtered.length}
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-zinc-800">
                      <SortHeader col="minute"    label="Min"       current={sortCol} dir={sortDir} onSort={handleSort} />
                      <th className="px-3 py-2 text-left text-[10px] uppercase tracking-wide text-zinc-500">Condición</th>
                      <th className="px-3 py-2 text-left text-[10px] uppercase tracking-wide text-zinc-500">Target</th>
                      <th className="px-3 py-2 text-left text-[10px] uppercase tracking-wide text-zinc-500">Tipo</th>
                      <SortHeader col="n_matches" label="N"         current={sortCol} dir={sortDir} onSort={handleSort} />
                      <SortHeader col="win_rate"  label="WR%"       current={sortCol} dir={sortDir} onSort={handleSort} />
                      <SortHeader col="avg_odds"  label="Odds"      current={sortCol} dir={sortDir} onSort={handleSort} />
                      <SortHeader col="ev_pct"    label="EV%"       current={sortCol} dir={sortDir} onSort={handleSort} />
                      <SortHeader col="total_pl"  label="P/L total" current={sortCol} dir={sortDir} onSort={handleSort} />
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.slice(0, 150).map((r, i) => {
                      const evPct = r.ev_pct * 100
                      const winPct = r.win_rate * 100
                      const isPos = evPct >= 0
                      return (
                        <tr
                          key={i}
                          className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                        >
                          <td className="px-3 py-2 text-right font-mono text-zinc-400">{r.minute}'</td>
                          <td className="px-3 py-2 text-zinc-300 max-w-[220px] truncate" title={r.condition}>
                            {r.condition}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
                              style={{
                                backgroundColor: TARGET_COLORS[r.target] + "30",
                                color: TARGET_COLORS[r.target],
                              }}
                            >
                              {TARGET_LABELS[r.target] ?? r.target}
                            </span>
                          </td>
                          <td className="px-3 py-2">
                            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded
                              ${r.bet_type === "lay"
                                ? "bg-orange-500/15 text-orange-400"
                                : "bg-blue-500/15 text-blue-400"}`}
                            >
                              {r.bet_type === "lay" ? "LAY" : "BACK"}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right text-zinc-400 font-mono">{r.n_matches}</td>
                          <td className="px-3 py-2 text-right text-zinc-300 font-mono">{winPct.toFixed(1)}%</td>
                          <td className="px-3 py-2 text-right text-zinc-300 font-mono">
                            {r.avg_odds?.toFixed(2) ?? "—"}
                          </td>
                          <td className={`px-3 py-2 text-right font-mono font-semibold ${isPos ? "text-emerald-400" : "text-red-400"}`}>
                            {isPos ? "+" : ""}{evPct.toFixed(1)}%
                          </td>
                          <td className={`px-3 py-2 text-right font-mono ${r.total_pl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {r.total_pl >= 0 ? "+" : ""}{r.total_pl.toFixed(1)}€
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {filtered.length === 0 && (
            <div className="rounded-lg border border-zinc-800 p-8 text-center text-zinc-500 text-sm">
              Ninguna combinación cumple los filtros actuales. Prueba a bajar el mínimo de apuestas.
            </div>
          )}
        </>
      )}
    </div>
  )
}
