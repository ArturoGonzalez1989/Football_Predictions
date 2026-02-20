import { useState, useEffect } from "react"
import { api, type ExplorationRun, type ExplorerResult, type ExplorerMatchRow } from "../lib/api"

type AggResult = ExplorerResult & { minuteLabel: string }

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

export function ExplorerView({ onNavigateToMatch }: { onNavigateToMatch?: (matchId: string) => void }) {
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
  const [minuteGroup, setMinuteGroup] = useState<5 | 10 | 15 | 20>(5)
  const [hmMetric, setHmMetric] = useState<"ev" | "plBet" | "plTotal">("ev")

  // Filtros de tabla
  const [tableSearch, setTableSearch] = useState("")
  const [tableOnlyEV, setTableOnlyEV] = useState(false)
  const [tableMinWR, setTableMinWR] = useState(0)
  const [tableMaxOdds, setTableMaxOdds] = useState(999)

  // Expansión de partidos
  const [expandedKey, setExpandedKey] = useState<string | null>(null)
  const [matchCache, setMatchCache] = useState<Record<string, ExplorerMatchRow[] | "error">>({})
  const [loadingKey, setLoadingKey] = useState<string | null>(null)

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

  const handleExportTableCSV = () => {
    if (filteredAgg.length === 0) return
    const headers = [
      "minute_label","minute","condition","condition_id","target","bet_type",
      "n_matches","wins","win_rate","avg_odds","ev_pct","avg_pl_per_bet","total_pl"
    ]
    const rows = filteredAgg.map(r => [
      r.minuteLabel, r.minute, `"${r.condition.replace(/"/g, '""')}"`, r.condition_id,
      r.target, r.bet_type ?? "back", r.n_matches, r.wins ?? "",
      r.win_rate.toFixed(4), r.avg_odds?.toFixed(3) ?? "",
      r.ev_pct.toFixed(4), r.avg_pl_per_bet.toFixed(3), r.total_pl.toFixed(2)
    ])
    const csv = [headers.join(","), ...rows.map(r => r.join(","))].join("\n")
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `explorer_tabla_${minuteGroup}min_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleRowClick = async (r: AggResult) => {
    // Calcula los minutos reales del bucket
    const bucket = minuteGroup === 5
      ? [r.minute]
      : (minuteBuckets.find(b => b.start === r.minute)?.minutes ?? [r.minute])
    const key = `${r.condition_id}|${r.target}|${r.bet_type ?? "back"}|${bucket.join("_")}`

    // Colapsar si ya está abierta
    if (expandedKey === key) {
      setExpandedKey(null)
      return
    }
    setExpandedKey(key)

    // Usar caché si ya se cargó (incluye estado de error)
    if (key in matchCache) return

    setLoadingKey(key)
    try {
      const data = await api.getExplorerMatches(
        r.condition_id, r.target, bucket, r.bet_type ?? "back"
      )
      setMatchCache(prev => ({ ...prev, [key]: data.matches }))
    } catch {
      setMatchCache(prev => ({ ...prev, [key]: "error" }))
    } finally {
      setLoadingKey(null)
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

  // Agrupamiento de minutos en buckets
  const ALL_BASE_MINUTES = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
  const minuteBuckets: { label: string; start: number; minutes: number[] }[] = (() => {
    if (minuteGroup === 5) return ALL_BASE_MINUTES.map(m => ({ label: `${m}'`, start: m, minutes: [m] }))
    // Anclaje fijo por tipo de agrupamiento para que los rangos sean naturales en fútbol:
    // 10 min → 15-25, 25-35, ..., 75-85'
    // 15 min → 15-30, 30-45, ..., 75-90'
    // 20 min → 10-30, 30-50, 50-70, 70-90'  (periodos naturales del partido)
    const anchors: Record<number, number> = { 10: 15, 15: 15, 20: 10 }
    const anchor = anchors[minuteGroup] ?? ALL_BASE_MINUTES[0]
    const result: { label: string; start: number; minutes: number[] }[] = []
    let bucketStart = anchor
    while (bucketStart <= ALL_BASE_MINUTES[ALL_BASE_MINUTES.length - 1]) {
      const bucketEnd = bucketStart + minuteGroup
      const mins = ALL_BASE_MINUTES.filter(m => m >= bucketStart && m < bucketEnd)
      if (mins.length > 0) {
        result.push({
          label: `${bucketStart}-${bucketEnd}'`,
          start: bucketStart,
          minutes: mins,
        })
      }
      bucketStart = bucketEnd
    }
    return result
  })()

  // Aggregate filtered por bucket de minuto
  const filteredAgg: AggResult[] = minuteGroup === 5
    ? filtered.map(r => ({ ...r, minuteLabel: `${r.minute}'` }))
    : (() => {
        const acc: Record<string, AggResult> = {}
        for (const r of filtered) {
          const bucket = minuteBuckets.find(b => b.minutes.includes(r.minute))
          if (!bucket) continue
          const key = `${r.condition_id}|${r.target}|${r.bet_type ?? "back"}|${bucket.start}`
          if (!acc[key]) {
            acc[key] = { ...r, minute: bucket.start, minuteLabel: bucket.label }
          } else {
            const cur = acc[key]
            const prevN = cur.n_matches
            const newN = prevN + r.n_matches
            cur.wins = (cur.wins ?? 0) + (r.wins ?? 0)
            cur.n_matches = newN
            cur.win_rate = cur.wins / newN
            cur.avg_odds = ((cur.avg_odds ?? 1) * prevN + (r.avg_odds ?? 1) * r.n_matches) / newN
            cur.total_pl += r.total_pl
            cur.avg_pl_per_bet = cur.total_pl / newN
            cur.ev_pct = (r.bet_type ?? "back") === "lay"
              ? cur.win_rate * 0.95 - (1 - cur.win_rate) * ((cur.avg_odds ?? 1) - 1)
              : cur.win_rate * ((cur.avg_odds ?? 1) - 1) * 0.95 - (1 - cur.win_rate)
          }
        }
        return Object.values(acc).sort((a, b) => {
          const dir = sortDir === "desc" ? -1 : 1
          return dir * (((a[sortCol] as number) ?? 0) - ((b[sortCol] as number) ?? 0))
        })
      })()

  // Filtros adicionales de tabla
  const tableFiltered = filteredAgg.filter(r => {
    if (tableOnlyEV && r.ev_pct <= 0) return false
    if (tableMinWR > 0 && r.win_rate * 100 < tableMinWR) return false
    if (tableMaxOdds < 999 && (r.avg_odds ?? 0) > tableMaxOdds) return false
    if (tableSearch.trim()) {
      const q = tableSearch.trim().toLowerCase()
      if (!r.condition.toLowerCase().includes(q)) return false
    }
    return true
  })

  // Heatmap: EV% promedio de todas las condiciones por target × minuto
  const HM_TARGETS = ALL_TARGETS.filter(t =>
    betTypeFilter === "all" || (betTypeFilter === "lay" ? t.startsWith("lay_") : !t.startsWith("lay_"))
  )
  const hmAcc: Record<string, Record<number, { sumEv: number; sumPlBet: number; sumPlTotal: number; count: number }>> = {}
  for (const r of (run?.results ?? [])) {
    if (betTypeFilter !== "all" && (r.bet_type ?? "back") !== betTypeFilter) continue
    if (!hmAcc[r.target]) hmAcc[r.target] = {}
    if (!hmAcc[r.target][r.minute]) hmAcc[r.target][r.minute] = { sumEv: 0, sumPlBet: 0, sumPlTotal: 0, count: 0 }
    hmAcc[r.target][r.minute].sumEv += r.ev_pct
    hmAcc[r.target][r.minute].sumPlBet += r.avg_pl_per_bet ?? 0
    hmAcc[r.target][r.minute].sumPlTotal += r.total_pl
    hmAcc[r.target][r.minute].count++
  }
  const heatmap: Record<string, Record<number, { ev: number; plBet: number; plTotal: number }>> = {}
  for (const [target, minutes] of Object.entries(hmAcc)) {
    heatmap[target] = {}
    for (const [min, acc] of Object.entries(minutes)) {
      heatmap[target][Number(min)] = {
        ev: acc.sumEv / acc.count,
        plBet: acc.sumPlBet / acc.count,
        plTotal: acc.sumPlTotal / acc.count,
      }
    }
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
                {filteredAgg.length} combinaciones
              </div>
            </div>
          </div>

          {/* Heatmap */}
          {filteredAgg.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                    {hmMetric === "ev" ? "Heatmap EV% promedio — Minuto × Mercado"
                      : hmMetric === "plBet" ? "Heatmap P/L por apuesta — Minuto × Mercado"
                      : "Heatmap P/L total — Minuto × Mercado"}
                  </h2>
                  {/* Selector de métrica */}
                  <div className="flex rounded overflow-hidden border border-zinc-700 text-[10px]">
                    {(["ev", "plBet", "plTotal"] as const).map(m => (
                      <button key={m} type="button" onClick={() => setHmMetric(m)}
                        className={`px-2 py-1 font-medium transition-colors cursor-pointer
                          ${hmMetric === m ? "bg-zinc-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"}`}>
                        {m === "ev" ? "EV%" : m === "plBet" ? "P/L/bet" : "P/L total"}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Selector de agrupamiento de minutos */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-zinc-600 uppercase tracking-wide">Agrupar</span>
                  <div className="flex rounded overflow-hidden border border-zinc-700 text-[10px]">
                    {([5, 10, 15, 20] as const).map(g => (
                      <button key={g} type="button" onClick={() => setMinuteGroup(g)}
                        className={`px-2 py-1 font-medium transition-colors cursor-pointer
                          ${minuteGroup === g ? "bg-blue-600 text-white" : "bg-zinc-800 text-zinc-400 hover:text-zinc-200"}`}>
                        {g} min
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              <div className="overflow-x-auto">
                <p className="text-[10px] text-zinc-600 mb-2">
                  {hmMetric === "ev" ? "EV% promedio" : hmMetric === "plBet" ? "P/L medio por apuesta (€)" : "P/L total medio (€)"} de todas las condiciones para cada mercado × ventana de tiempo.
                  Verde = positivo · Rojo = negativo · Gris = sin datos.
                </p>
                <table className="text-[10px] font-mono border-separate border-spacing-0.5">
                  <thead>
                    <tr>
                      <th className="text-left text-zinc-600 pr-2 font-normal whitespace-nowrap">Mercado</th>
                      {minuteBuckets.map(b => (
                        <th key={b.start} className="text-zinc-600 font-normal text-center px-1 whitespace-nowrap">{b.label}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {HM_TARGETS.map(target => {
                      const rowData = heatmap[target] ?? {}
                      return (
                        <tr key={target}>
                          <td className="pr-2 py-0.5 whitespace-nowrap">
                            <span className="text-[10px] font-semibold" style={{ color: TARGET_COLORS[target] ?? "#71717a" }}>
                              {TARGET_LABELS[target] ?? target}
                            </span>
                          </td>
                          {minuteBuckets.map(bucket => {
                            const cells = bucket.minutes
                              .map(m => rowData[m])
                              .filter((c): c is { ev: number; plBet: number; plTotal: number } => c !== undefined)
                            const avgCell = cells.length > 0 ? {
                              ev: cells.reduce((s, c) => s + c.ev, 0) / cells.length,
                              plBet: cells.reduce((s, c) => s + c.plBet, 0) / cells.length,
                              plTotal: cells.reduce((s, c) => s + c.plTotal, 0) / cells.length,
                            } : undefined
                            const val = avgCell === undefined ? undefined
                              : hmMetric === "ev" ? avgCell.ev
                              : hmMetric === "plBet" ? avgCell.plBet
                              : avgCell.plTotal
                            const [t1, t2, t3, t4, t5] = hmMetric === "ev"
                              ? [0.15, 0.05, 0, -0.1, -0.3]
                              : hmMetric === "plBet"
                              ? [0.5, 0.1, 0, -0.5, -1.0]
                              : [20, 5, 0, -10, -30]
                            const bg = val === undefined ? "rgba(39,39,42,0.4)"
                              : val >= t1 ? "rgba(16,185,129,0.65)"
                              : val >= t2 ? "rgba(16,185,129,0.4)"
                              : val >= t3 ? "rgba(16,185,129,0.18)"
                              : val >= t4 ? "rgba(239,68,68,0.2)"
                              : val >= t5 ? "rgba(239,68,68,0.4)"
                              : "rgba(239,68,68,0.6)"
                            const textColor = val === undefined ? "#52525b" : val >= 0 ? "#6ee7b7" : "#fca5a5"
                            const display = val === undefined ? ""
                              : hmMetric === "ev" ? `${val >= 0 ? "+" : ""}${(val * 100).toFixed(0)}`
                              : `${val >= 0 ? "+" : ""}${val.toFixed(1)}`
                            const tip = val !== undefined
                              ? `${TARGET_LABELS[target]} @ ${bucket.label}: ${hmMetric === "ev" ? `EV ${val >= 0 ? "+" : ""}${(val * 100).toFixed(1)}%` : `P/L ${val >= 0 ? "+" : ""}${val.toFixed(2)}€`}`
                              : "Sin datos"
                            return (
                              <td key={bucket.start} className="text-center h-7 rounded-sm tabular-nums px-1"
                                style={{ backgroundColor: bg, color: textColor, minWidth: minuteGroup > 5 ? "3.5rem" : "2.5rem" }}
                                title={tip}>
                                {display}
                              </td>
                            )
                          })}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tabla de resultados */}
          {filteredAgg.length > 0 && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden">
              <div className="px-4 py-2 border-b border-zinc-800 flex items-center justify-between">
                <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wide">
                  Tabla de combinaciones
                </h2>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-zinc-600">
                    Mostrando {Math.min(tableFiltered.length, 150)} de {tableFiltered.length}
                  </span>
                  <button
                    type="button"
                    onClick={handleExportTableCSV}
                    className="flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 transition-colors cursor-pointer"
                    title="Descargar tabla completa como CSV"
                  >
                    ↓ CSV
                  </button>
                </div>
              </div>

              {/* Filtros de tabla */}
              <div className="px-4 py-2 border-b border-zinc-800 bg-zinc-950/40 flex flex-wrap items-center gap-3">
                {/* Búsqueda de condición */}
                <input
                  type="text"
                  placeholder="Buscar condición…"
                  value={tableSearch}
                  onChange={e => setTableSearch(e.target.value)}
                  className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-300 placeholder-zinc-600 w-40 focus:outline-none focus:border-zinc-500"
                />
                {/* Solo EV+ */}
                <button
                  type="button"
                  onClick={() => setTableOnlyEV(v => !v)}
                  className={`text-[10px] font-medium px-2 py-1 rounded border transition-colors cursor-pointer
                    ${tableOnlyEV
                      ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-400"
                      : "bg-zinc-800 border-zinc-700 text-zinc-400 hover:text-zinc-200"}`}
                >
                  Solo EV+
                </button>
                {/* Min WR% */}
                <label className="flex items-center gap-1.5">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wide">WR≥</span>
                  <input
                    type="range" min={0} max={80} step={5} value={tableMinWR}
                    onChange={e => setTableMinWR(Number(e.target.value))}
                    className="w-20 accent-blue-500"
                  />
                  <span className="text-[10px] text-zinc-300 w-6 text-right tabular-nums">
                    {tableMinWR > 0 ? `${tableMinWR}%` : "—"}
                  </span>
                </label>
                {/* Odds máx */}
                <label className="flex items-center gap-1.5">
                  <span className="text-[10px] text-zinc-500 uppercase tracking-wide">Odds≤</span>
                  <input
                    type="range" min={1} max={30} step={1} value={tableMaxOdds >= 999 ? 30 : tableMaxOdds}
                    onChange={e => setTableMaxOdds(Number(e.target.value) >= 30 ? 999 : Number(e.target.value))}
                    className="w-20 accent-blue-500"
                  />
                  <span className="text-[10px] text-zinc-300 w-6 text-right tabular-nums">
                    {tableMaxOdds >= 999 ? "—" : tableMaxOdds}
                  </span>
                </label>
                {/* Reset */}
                {(tableSearch || tableOnlyEV || tableMinWR > 0 || tableMaxOdds < 999) && (
                  <button
                    type="button"
                    onClick={() => { setTableSearch(""); setTableOnlyEV(false); setTableMinWR(0); setTableMaxOdds(999) }}
                    className="text-[10px] text-zinc-500 hover:text-zinc-300 cursor-pointer"
                  >
                    ✕ limpiar
                  </button>
                )}
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
                    {tableFiltered.slice(0, 150).map((r, i) => {
                      const evPct = r.ev_pct * 100
                      const winPct = r.win_rate * 100
                      const isPos = evPct >= 0
                      const bucket = minuteGroup === 5
                        ? [r.minute]
                        : (minuteBuckets.find(b => b.start === r.minute)?.minutes ?? [r.minute])
                      const rowKey = `${r.condition_id}|${r.target}|${r.bet_type ?? "back"}|${bucket.join("_")}`
                      const isExpanded = expandedKey === rowKey
                      const isLoading = loadingKey === rowKey
                      const matches = matchCache[rowKey]
                      return (
                        <>
                          <tr
                            key={i}
                            className={`border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors cursor-pointer select-none
                              ${isExpanded ? "bg-zinc-800/20" : ""}`}
                            onClick={() => handleRowClick(r)}
                          >
                            <td className="px-3 py-2 text-right font-mono text-zinc-400">
                              <span className="inline-flex items-center gap-1.5">
                                <span className="text-zinc-600 text-[9px]">{isExpanded ? "▼" : "▶"}</span>
                                {r.minuteLabel}
                              </span>
                            </td>
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
                          {isExpanded && (
                            <tr key={`${i}-detail`} className="border-b border-zinc-800">
                              <td colSpan={9} className="px-0 py-0 bg-zinc-950/60">
                                {isLoading ? (
                                  <div className="px-6 py-3 text-xs text-zinc-500">Cargando partidos...</div>
                                ) : matches === "error" ? (
                                  <div className="px-6 py-3 text-xs text-red-400/70">
                                    Error al cargar partidos — reinicia el backend e inténtalo de nuevo
                                  </div>
                                ) : !matches || matches.length === 0 ? (
                                  <div className="px-6 py-3 text-xs text-zinc-600">Sin partidos disponibles</div>
                                ) : (
                                  <div className="px-4 py-2">
                                    <table className="w-full text-[11px]">
                                      <thead>
                                        <tr className="text-zinc-600 uppercase tracking-wide text-[9px]">
                                          <th className="text-left py-1 pr-3 font-normal">Partido</th>
                                          <th className="text-center py-1 px-2 font-normal w-16">Marcador<br/>en min</th>
                                          <th className="text-center py-1 px-2 font-normal w-16">Resultado<br/>final</th>
                                          <th className="text-right py-1 px-2 font-normal w-12">Odds</th>
                                          <th className="text-center py-1 px-2 font-normal w-14">Resultado</th>
                                          <th className="text-right py-1 pl-2 font-normal w-14">P/L</th>
                                        </tr>
                                      </thead>
                                      <tbody className="divide-y divide-zinc-800/40">
                                        {(matches as ExplorerMatchRow[]).map((m, mi) => (
                                          <tr key={mi} className="hover:bg-zinc-800/20">
                                            <td className="py-1 pr-3 text-zinc-300 max-w-[240px]">
                                              <div className="flex items-center gap-1.5">
                                                <span className="truncate" title={m.match_name}>{m.match_name}</span>
                                                {onNavigateToMatch && (
                                                  <button
                                                    type="button"
                                                    onClick={(e) => { e.stopPropagation(); onNavigateToMatch(m.match_id) }}
                                                    title="Ver partido en Finalizados"
                                                    className="shrink-0 text-zinc-600 hover:text-blue-400 cursor-pointer transition-colors"
                                                  >
                                                    ↗
                                                  </button>
                                                )}
                                              </div>
                                            </td>
                                            <td className="py-1 px-2 text-center font-mono text-zinc-400">{m.score_at_checkpoint}</td>
                                            <td className="py-1 px-2 text-center font-mono text-zinc-400">{m.final_score}</td>
                                            <td className="py-1 px-2 text-right font-mono text-zinc-300">{m.odds?.toFixed(2) ?? "—"}</td>
                                            <td className="py-1 px-2 text-center">
                                              <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold
                                                ${m.won ? "bg-emerald-500/15 text-emerald-400" : "bg-red-500/15 text-red-400"}`}>
                                                {m.won ? "✓ ACIERTO" : "✗ FALLO"}
                                              </span>
                                            </td>
                                            <td className={`py-1 pl-2 text-right font-mono font-semibold
                                              ${m.pl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                              {m.pl >= 0 ? "+" : ""}{m.pl.toFixed(2)}€
                                            </td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </td>
                            </tr>
                          )}
                        </>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {filteredAgg.length === 0 && (
            <div className="rounded-lg border border-zinc-800 p-8 text-center text-zinc-500 text-sm">
              Ninguna combinación cumple los filtros actuales. Prueba a bajar el mínimo de apuestas.
            </div>
          )}
        </>
      )}
    </div>
  )
}
