import { useState, useEffect } from "react"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts"
import { api, type QualityOverview, type StatsCoverage, type GapAnalysis, type LowQualityMatch, type OddsCoverage } from "../lib/api"

export function DataQualityView({ onNavigateToMatch }: { onNavigateToMatch?: (matchId: string) => void }) {
  const [overview, setOverview] = useState<QualityOverview | null>(null)
  const [coverage, setCoverage] = useState<StatsCoverage | null>(null)
  const [gaps, setGaps] = useState<GapAnalysis | null>(null)
  const [lowQuality, setLowQuality] = useState<LowQualityMatch[]>([])
  const [oddsCoverage, setOddsCoverage] = useState<OddsCoverage | null>(null)
  const [threshold, setThreshold] = useState(50)
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)
  const [confirmDelete, setConfirmDelete] = useState<{ match_id: string; name: string } | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const handleRefresh = async () => {
    await api.clearAnalyticsCache()
    setRefreshKey(k => k + 1)
  }

  const handleDelete = async () => {
    if (!confirmDelete) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await api.deleteMatch(confirmDelete.match_id)
      setConfirmDelete(null)
      setDeleteError(null)
      await api.clearAnalyticsCache()
      setRefreshKey(k => k + 1)
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : "No se pudo eliminar el archivo.")
    } finally {
      setDeleting(false)
    }
  }

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [o, c, g, lq, oc] = await Promise.all([
          api.getQualityOverview(),
          api.getStatsCoverage(),
          api.getGapAnalysis(),
          api.getLowQualityMatches(threshold),
          api.getOddsCoverage(),
        ])
        setOverview(o)
        setCoverage(c)
        setGaps(g)
        setLowQuality(lq.matches)
        setOddsCoverage(oc)
      } catch (err) {
        console.error("Failed to load quality data:", err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [threshold, refreshKey])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-zinc-500">
        Loading quality analytics...
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl">
      {/* Delete confirmation modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-sm font-semibold text-zinc-100 mb-1">Eliminar partido</h3>
            <p className="text-xs text-zinc-400 mb-1">
              ¿Seguro que quieres eliminar el CSV de:
            </p>
            <p className="text-sm font-medium text-zinc-200 mb-4 truncate">{confirmDelete.name}</p>
            <p className="text-xs text-zinc-500 mb-4">
              Se eliminará el archivo de datos. Esta acción no se puede deshacer.
            </p>
            {deleteError && (
              <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
                {deleteError}
              </div>
            )}
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                onClick={() => { setConfirmDelete(null); setDeleteError(null) }}
                disabled={deleting}
                className="px-3 py-1.5 text-xs rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer disabled:opacity-40"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                className="px-3 py-1.5 text-xs rounded-lg bg-red-600 hover:bg-red-500 text-white font-medium transition-colors cursor-pointer disabled:opacity-40"
              >
                {deleting ? "Eliminando…" : "Eliminar"}
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100 mb-1">Data Quality</h1>
          <p className="text-sm text-zinc-500">
            Analyze data quality metrics for finished matches
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 hover:border-zinc-500 transition-colors disabled:opacity-40 cursor-pointer"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          title="Average Quality"
          value={`${overview?.avg_quality ?? 0}%`}
          description="Across all finished matches"
        />
        <MetricCard
          title="Total Matches"
          value={overview?.total_matches ?? 0}
          description="Finished matches analyzed"
        />
        <MetricCard
          title="Average Gaps"
          value={gaps?.avg_gaps ?? 0}
          description="Missing minutes per match"
        />
      </div>

      {/* Quality Distribution */}
      {overview && overview.bins.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Quality Distribution</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Muestra cuántos partidos caen en cada rango de calidad. Calidad = porcentaje de estadísticas capturadas correctamente. Verde = alta calidad, Rojo = baja calidad.
          </p>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={overview.bins} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="label"
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #27272a",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {overview.bins.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      index === 0
                        ? "#ef4444"
                        : index === 1
                          ? "#f97316"
                          : index === 2
                            ? "#eab308"
                            : index === 3
                              ? "#22c55e"
                              : "#10b981"
                    }
                    opacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Stats Coverage */}
      {coverage && coverage.fields.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Stats Coverage</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Porcentaje de cobertura de cada estadística en todos los partidos. Valores bajos indican que esa estadística no está disponible o no se captura correctamente.
          </p>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart
              data={coverage.fields}
              layout="vertical"
              margin={{ top: 5, right: 20, left: 100, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                type="number"
                domain={[0, 100]}
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
                width={95}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #27272a",
                  borderRadius: 8,
                  fontSize: 12,
                }}
                formatter={(value: number | undefined) => (value !== undefined ? `${value}%` : "N/A")}
              />
              <Bar dataKey="coverage_pct" radius={[0, 4, 4, 0]}>
                {coverage.fields.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={
                      entry.coverage_pct < 30
                        ? "#ef4444"
                        : entry.coverage_pct < 60
                          ? "#f97316"
                          : entry.coverage_pct < 80
                            ? "#eab308"
                            : "#10b981"
                    }
                    opacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Gap Analysis */}
      {gaps && gaps.distribution.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Gap Distribution</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Distribución de minutos faltantes en las capturas. "Gaps" son minutos sin datos capturados durante el partido. Menos gaps = mejor continuidad temporal.
          </p>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={gaps.distribution.slice(0, 20)} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="gap_count"
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
                label={{ value: "Missing Minutes", position: "insideBottom", offset: -5, fill: "#71717a", fontSize: 11 }}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
                label={{ value: "Matches", angle: -90, position: "insideLeft", fill: "#71717a", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #27272a",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="match_count" fill="#3b82f6" opacity={0.8} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ═══════ ODDS COVERAGE ═══════ */}
      {oddsCoverage && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 space-y-5">
          <div>
            <h2 className="text-sm font-semibold text-zinc-300 mb-1">Odds Coverage</h2>
            <p className="text-xs text-zinc-500">
              Cobertura de scraping de cuotas (back_home) por partido. 0% = sin ninguna cuota capturada — indica fallo de scraping. Puedes eliminar partidos problemáticos directamente desde aquí.
            </p>
          </div>

          {/* Summary pills */}
          <div className="flex flex-wrap gap-3">
            <div className="bg-zinc-800 rounded-lg px-4 py-2 text-center min-w-[100px]">
              <div className="text-xl font-bold text-zinc-100">{oddsCoverage.avg_coverage}%</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Cobertura media</div>
            </div>
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2 text-center min-w-[100px]">
              <div className="text-xl font-bold text-red-400">{oddsCoverage.no_odds}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Sin cuotas (0%)</div>
            </div>
            <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg px-4 py-2 text-center min-w-[100px]">
              <div className="text-xl font-bold text-orange-400">{oddsCoverage.partial_odds}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Parciales (&lt;80%)</div>
            </div>
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-4 py-2 text-center min-w-[100px]">
              <div className="text-xl font-bold text-emerald-400">{oddsCoverage.good_odds}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Buena (≥80%)</div>
            </div>
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-4 py-2 text-center min-w-[100px]">
              <div className="text-xl font-bold text-amber-400">{oddsCoverage.total_outlier_matches}</div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Con anomalías</div>
            </div>
          </div>

          {/* Histogram */}
          {oddsCoverage.bins.length > 0 && (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={oddsCoverage.bins} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "#71717a", fontSize: 11 }}
                  axisLine={{ stroke: "#27272a" }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: "#71717a", fontSize: 11 }}
                  axisLine={{ stroke: "#27272a" }}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #27272a",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(v: number) => [`${v} partidos`, "Partidos"]}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {oddsCoverage.bins.map((b, i) => (
                    <Cell
                      key={`oc-${i}`}
                      fill={
                        b.label === "0%"
                          ? "#ef4444"
                          : b.label === "1-25%" || b.label === "26-50%"
                            ? "#f97316"
                            : b.label === "51-75%"
                              ? "#eab308"
                              : "#10b981"
                      }
                      opacity={0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}

          {/* Match table — sorted worst first */}
          {(oddsCoverage?.matches ?? []).length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="text-left py-2 px-3 text-xs font-medium text-zinc-500">Partido</th>
                    <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Cobertura</th>
                    <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Rango 1X</th>
                    <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Filas c/cuota</th>
                    <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Total filas</th>
                    <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Anomalías</th>
                    <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Gaps</th>
                    <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Avg gap</th>
                    {onNavigateToMatch && <th className="py-2 px-2"><span className="sr-only">Ver</span></th>}
                    <th className="py-2 px-2"><span className="sr-only">Eliminar</span></th>
                  </tr>
                </thead>
                <tbody>
                  {oddsCoverage!.matches.map((match) => {
                    const hasRange = match.min_back_home !== null && match.max_back_home !== null
                    const rangeRatio = hasRange ? match.max_back_home! / match.min_back_home! : 1
                    return (
                    <tr key={match.match_id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                      <td className="py-2.5 px-3 text-zinc-300 max-w-xs truncate">{match.name}</td>
                      <td className="py-2.5 px-3 text-right">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                            match.coverage_pct === 0
                              ? "bg-red-500/20 text-red-400"
                              : match.coverage_pct < 50
                                ? "bg-orange-500/20 text-orange-400"
                                : match.coverage_pct < 80
                                  ? "bg-yellow-500/20 text-yellow-400"
                                  : "bg-emerald-500/20 text-emerald-400"
                          }`}
                        >
                          {match.coverage_pct}%
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        {hasRange ? (
                          <span className={rangeRatio > 4 ? "text-amber-400 font-medium" : "text-zinc-400"}>
                            {match.min_back_home!.toFixed(2)} – {match.max_back_home!.toFixed(2)}
                          </span>
                        ) : (
                          <span className="text-zinc-600">—</span>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-right text-zinc-400 tabular-nums">{match.rows_with_odds}</td>
                      <td className="py-2.5 px-3 text-right text-zinc-400 tabular-nums">{match.total_rows}</td>
                      <td className="py-2.5 px-3 text-right">
                        {match.outlier_count > 0
                          ? <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-amber-500/20 text-amber-400">⚠ {match.outlier_count}</span>
                          : <span className="text-zinc-600">—</span>
                        }
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        {match.gap_count > 0
                          ? <span className={match.gap_count > 20 ? "text-orange-400 font-medium" : "text-zinc-400"}>{match.gap_count}</span>
                          : <span className="text-zinc-600">0</span>
                        }
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums">
                        {match.gap_count > 0
                          ? <span className={match.avg_gap_size > 5 ? "text-orange-400 font-medium" : "text-zinc-500"}>{match.avg_gap_size.toFixed(1)} min</span>
                          : <span className="text-zinc-600">—</span>
                        }
                      </td>
                      {onNavigateToMatch && (
                        <td className="py-2.5 px-2">
                          <button
                            type="button"
                            title="Ver en Finalizados"
                            onClick={() => onNavigateToMatch(match.match_id)}
                            className="text-zinc-600 hover:text-blue-400 transition-colors cursor-pointer text-xs"
                          >
                            ↗
                          </button>
                        </td>
                      )}
                      <td className="py-2.5 px-2">
                        <button
                          type="button"
                          title="Eliminar CSV de este partido"
                          onClick={() => setConfirmDelete({ match_id: match.match_id, name: match.name })}
                          className="text-zinc-700 hover:text-red-400 transition-colors cursor-pointer"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Low Quality Matches */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-semibold text-zinc-300">Low Quality Matches</h2>
            <div className="flex items-center gap-2">
            <label htmlFor="quality-threshold" className="text-xs text-zinc-500">Threshold:</label>
            <input
              id="quality-threshold"
              type="number"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              min={0}
              max={100}
              className="w-16 px-2 py-1 text-xs rounded bg-zinc-800 border border-zinc-700 text-zinc-300"
            />
            <span className="text-xs text-zinc-500">%</span>
          </div>
          </div>
          <p className="text-xs text-zinc-500">
            Partidos con calidad por debajo del umbral seleccionado. Útil para identificar partidos con datos incompletos o problemáticos que pueden necesitar revisión.
          </p>
        </div>

        {lowQuality.length === 0 ? (
          <div className="text-center py-8 text-zinc-500 text-sm">
            No matches below {threshold}% quality threshold
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-3 text-xs font-medium text-zinc-500">Match</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Quality</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Captures</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Gaps</th>
                </tr>
              </thead>
              <tbody>
                {lowQuality.map((match) => (
                  <tr key={match.match_id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                    <td className="py-2.5 px-3 text-zinc-300">{match.name}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          match.quality < 20
                            ? "bg-red-500/20 text-red-400"
                            : match.quality < 40
                              ? "bg-orange-500/20 text-orange-400"
                              : "bg-yellow-500/20 text-yellow-400"
                        }`}
                      >
                        {match.quality}%
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right text-zinc-400">{match.total_captures}</td>
                    <td className="py-2.5 px-3 text-right text-zinc-400">{match.gap_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function MetricCard({
  title,
  value,
  description,
}: {
  title: string
  value: string | number
  description: string
}) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
      <div className="text-xs text-zinc-500 mb-1">{title}</div>
      <div className="text-2xl font-bold text-zinc-100 mb-0.5">{value}</div>
      <div className="text-xs text-zinc-600">{description}</div>
    </div>
  )
}
