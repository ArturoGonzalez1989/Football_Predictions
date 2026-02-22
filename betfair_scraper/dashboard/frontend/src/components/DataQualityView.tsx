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
import { api, type QualityOverview, type StatsCoverage, type GapAnalysis, type OddsCoverage } from "../lib/api"

type OddsSortKey = "name" | "kickoff_time" | "coverage_pct" | "rows_with_odds" | "total_rows" | "outlier_count" | "gap_count" | "avg_gap_size"

export function DataQualityView({ onNavigateToMatch }: { onNavigateToMatch?: (matchId: string) => void }) {
  const [overview, setOverview] = useState<QualityOverview | null>(null)
  const [coverage, setCoverage] = useState<StatsCoverage | null>(null)
  const [gaps, setGaps] = useState<GapAnalysis | null>(null)
  const [oddsCoverage, setOddsCoverage] = useState<OddsCoverage | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)
  const [confirmDelete, setConfirmDelete] = useState<{ match_id: string; name: string } | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [confirmBulk, setConfirmBulk] = useState(false)
  const [bulkDeleting, setBulkDeleting] = useState(false)
  const [bulkResult, setBulkResult] = useState<{ deleted: number; failed: number; firstError?: string } | null>(null)
  const [sortKey, setSortKey] = useState<OddsSortKey>("kickoff_time")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")

  const handleSort = (key: OddsSortKey) => {
    if (sortKey === key) {
      setSortDir(d => d === "asc" ? "desc" : "asc")
    } else {
      setSortKey(key)
      setSortDir("asc")
    }
  }

  const handleRefresh = async () => {
    await api.clearAnalyticsCache()
    setSelected(new Set())
    setRefreshKey(k => k + 1)
  }

  const handleDelete = async () => {
    if (!confirmDelete) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await api.deleteMatch(confirmDelete.match_id)
      setSelected(prev => { const s = new Set(prev); s.delete(confirmDelete.match_id); return s })
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

  const handleBulkDelete = async () => {
    setBulkDeleting(true)
    try {
      const res = await api.bulkDeleteMatches(Array.from(selected))
      const firstError = res.results?.find((r: any) => !r.ok)?.error ?? undefined
      setBulkResult({ deleted: res.deleted, failed: res.failed, firstError })
      setSelected(new Set())
      setConfirmBulk(false)
      await api.clearAnalyticsCache()
      setRefreshKey(k => k + 1)
    } catch (e) {
      setBulkResult({ deleted: 0, failed: selected.size })
      setConfirmBulk(false)
    } finally {
      setBulkDeleting(false)
    }
  }

  const toggleSelect = (id: string) => {
    setSelected(prev => {
      const s = new Set(prev)
      s.has(id) ? s.delete(id) : s.add(id)
      return s
    })
  }

  const toggleSelectAll = (allIds: string[]) => {
    if (allIds.every(id => selected.has(id))) {
      setSelected(prev => { const s = new Set(prev); allIds.forEach(id => s.delete(id)); return s })
    } else {
      setSelected(prev => { const s = new Set(prev); allIds.forEach(id => s.add(id)); return s })
    }
  }

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [o, c, g, oc] = await Promise.all([
          api.getQualityOverview(),
          api.getStatsCoverage(),
          api.getGapAnalysis(),
          api.getOddsCoverage(),
        ])
        setOverview(o)
        setCoverage(c)
        setGaps(g)
        setOddsCoverage(oc)
      } catch (err) {
        console.error("Failed to load quality data:", err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [refreshKey])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-zinc-500">
        Loading quality analytics...
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl">
      {/* Single delete confirmation modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-sm font-semibold text-zinc-100 mb-1">Eliminar partido</h3>
            <p className="text-xs text-zinc-400 mb-1">¿Seguro que quieres eliminar el CSV de:</p>
            <p className="text-sm font-medium text-zinc-200 mb-4 truncate">{confirmDelete.name}</p>
            <p className="text-xs text-zinc-500 mb-4">Se eliminará el archivo de datos. Esta acción no se puede deshacer.</p>
            {deleteError && (
              <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-xs text-red-400">
                {deleteError}
              </div>
            )}
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => { setConfirmDelete(null); setDeleteError(null) }} disabled={deleting}
                className="px-3 py-1.5 text-xs rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer disabled:opacity-40">
                Cancelar
              </button>
              <button type="button" onClick={handleDelete} disabled={deleting}
                className="px-3 py-1.5 text-xs rounded-lg bg-red-600 hover:bg-red-500 text-white font-medium transition-colors cursor-pointer disabled:opacity-40">
                {deleting ? "Eliminando…" : "Eliminar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk delete confirmation modal */}
      {confirmBulk && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 w-full max-w-sm shadow-2xl">
            <h3 className="text-sm font-semibold text-zinc-100 mb-1">Eliminar {selected.size} partidos</h3>
            <p className="text-xs text-zinc-400 mb-4">
              Se eliminarán los CSVs de <span className="text-zinc-200 font-medium">{selected.size} partidos</span> seleccionados. Esta acción no se puede deshacer.
            </p>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setConfirmBulk(false)} disabled={bulkDeleting}
                className="px-3 py-1.5 text-xs rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer disabled:opacity-40">
                Cancelar
              </button>
              <button type="button" onClick={handleBulkDelete} disabled={bulkDeleting}
                className="px-3 py-1.5 text-xs rounded-lg bg-red-600 hover:bg-red-500 text-white font-medium transition-colors cursor-pointer disabled:opacity-40">
                {bulkDeleting ? "Eliminando…" : `Eliminar ${selected.size} partidos`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk result toast */}
      {bulkResult && (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-1 px-4 py-3 rounded-xl bg-zinc-800 border border-zinc-700 shadow-2xl text-xs max-w-sm">
          <div className="flex items-center gap-3">
            {bulkResult.deleted > 0 && <span className="text-emerald-400 font-medium">✓ {bulkResult.deleted} eliminados</span>}
            {bulkResult.failed > 0 && <span className="text-red-400">{bulkResult.failed} fallidos</span>}
            <button type="button" onClick={() => setBulkResult(null)} className="text-zinc-500 hover:text-zinc-300 cursor-pointer ml-auto">✕</button>
          </div>
          {bulkResult.firstError && (
            <span className="text-zinc-400 text-[10px] break-all">{bulkResult.firstError}</span>
          )}
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
              Cobertura de scraping de cuotas (back_home) por partido. Se calcula como filas con cuota / 90 minutos esperados (máx 100%). 0% = sin ninguna cuota capturada.
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

          {/* Match table */}
          {(oddsCoverage?.matches ?? []).length > 0 && (() => {
            const allIds = oddsCoverage!.matches.map(m => m.match_id)
            const allSelected = allIds.every(id => selected.has(id))
            const someSelected = allIds.some(id => selected.has(id))

            const sortedMatches = [...oddsCoverage!.matches].sort((a, b) => {
              let av: string | number, bv: string | number
              if (sortKey === "name") { av = a.name; bv = b.name }
              else if (sortKey === "kickoff_time") { av = a.kickoff_time ?? a.start_time ?? ""; bv = b.kickoff_time ?? b.start_time ?? "" }
              else { av = (a as Record<string, unknown>)[sortKey] as number ?? 0; bv = (b as Record<string, unknown>)[sortKey] as number ?? 0 }
              if (av < bv) return sortDir === "asc" ? -1 : 1
              if (av > bv) return sortDir === "asc" ? 1 : -1
              return 0
            })

            const SortIcon = ({ col }: { col: OddsSortKey }) =>
              sortKey === col
                ? <span className="ml-0.5 text-zinc-300">{sortDir === "asc" ? "↑" : "↓"}</span>
                : <span className="ml-0.5 text-zinc-700">↕</span>

            const Th = ({ col, label, align = "right" }: { col: OddsSortKey; label: string; align?: "left" | "right" }) => (
              <th
                className={`py-2 px-3 text-xs font-medium text-zinc-500 hover:text-zinc-300 cursor-pointer select-none transition-colors text-${align}`}
                onClick={() => handleSort(col)}
              >
                {label}<SortIcon col={col} />
              </th>
            )

            const lowQualityIds = oddsCoverage!.matches
              .filter(m => m.gap_count >= 60)
              .map(m => m.match_id)

            return (
            <div className="space-y-3">
              {/* Bulk action bar */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-xs text-zinc-500">
                    {selected.size > 0
                      ? <span className="text-zinc-300">{selected.size} seleccionados</span>
                      : `${oddsCoverage!.matches.length} partidos`}
                  </span>
                  {lowQualityIds.length > 0 && (
                    <button
                      type="button"
                      title="Seleccionar todos los partidos con ≥ 60 gaps (datos insuficientes)"
                      onClick={() => setSelected(prev => {
                        const s = new Set(prev)
                        lowQualityIds.forEach(id => s.add(id))
                        return s
                      })}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs bg-zinc-800 border border-zinc-700 text-orange-400 hover:text-orange-300 hover:border-zinc-500 transition-colors cursor-pointer"
                    >
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                      </svg>
                      Seleccionar ≥60 gaps ({lowQualityIds.length})
                    </button>
                  )}
                </div>
                {selected.size > 0 && (
                  <button
                    type="button"
                    onClick={() => setConfirmBulk(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-red-600 hover:bg-red-500 text-white font-medium transition-colors cursor-pointer"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Eliminar {selected.size} seleccionados
                  </button>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-zinc-800">
                      <th className="py-2 pl-3 pr-2 w-8">
                        <input
                          type="checkbox"
                          title="Seleccionar todos"
                          aria-label="Seleccionar todos"
                          checked={allSelected}
                          ref={el => { if (el) el.indeterminate = someSelected && !allSelected }}
                          onChange={() => toggleSelectAll(allIds)}
                          className="rounded border-zinc-600 bg-zinc-800 text-red-500 cursor-pointer accent-red-500"
                        />
                      </th>
                      <Th col="name" label="Partido" align="left" />
                      <Th col="kickoff_time" label="Fecha" />
                      <Th col="coverage_pct" label="Cobertura" />
                      <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Rango 1X</th>
                      <Th col="rows_with_odds" label="Filas c/cuota" />
                      <Th col="total_rows" label="Total filas" />
                      <Th col="outlier_count" label="Anomalías" />
                      <Th col="gap_count" label="Gaps" />
                      <Th col="avg_gap_size" label="Avg gap" />
                      {onNavigateToMatch && <th className="py-2 px-2"><span className="sr-only">Ver</span></th>}
                      <th className="py-2 px-2"><span className="sr-only">Eliminar</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedMatches.map((match) => {
                      const hasRange = match.min_back_home !== null && match.max_back_home !== null
                      const rangeRatio = hasRange ? match.max_back_home! / match.min_back_home! : 1
                      const isSelected = selected.has(match.match_id)
                      const isLowQuality = match.gap_count >= 60
                      return (
                      <tr key={match.match_id}
                        className={`border-b border-zinc-800/50 transition-colors ${isSelected ? "bg-red-500/5" : isLowQuality ? "bg-orange-500/5" : "hover:bg-zinc-800/30"}`}
                      >
                        <td className="py-2.5 pl-3 pr-2">
                          <input
                            type="checkbox"
                            title={`Seleccionar ${match.name}`}
                            aria-label={`Seleccionar ${match.name}`}
                            checked={isSelected}
                            onChange={() => toggleSelect(match.match_id)}
                            className="rounded border-zinc-600 bg-zinc-800 cursor-pointer accent-red-500"
                          />
                        </td>
                        <td className="py-2.5 px-3 text-zinc-300 max-w-xs truncate">{match.name}</td>
                        <td className="py-2.5 px-3 text-right tabular-nums text-zinc-500 text-xs whitespace-nowrap">
                          {(() => {
                            const raw = match.kickoff_time ?? match.start_time
                            if (!raw) return <span className="text-zinc-700">—</span>
                            const d = new Date(raw)
                            const date = d.toLocaleDateString("es-ES", { day: "2-digit", month: "2-digit", year: "2-digit" })
                            const time = match.kickoff_time
                              ? d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })
                              : null
                            return <>{date}{time && <span className="ml-1 text-zinc-600">{time}</span>}</>
                          })()}
                        </td>
                        <td className="py-2.5 px-3 text-right">
                          <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                            match.coverage_pct === 0
                              ? "bg-red-500/20 text-red-400"
                              : match.coverage_pct < 50
                                ? "bg-orange-500/20 text-orange-400"
                                : match.coverage_pct < 80
                                  ? "bg-yellow-500/20 text-yellow-400"
                                  : "bg-emerald-500/20 text-emerald-400"
                          }`}>
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
                            <button type="button" title="Ver en Finalizados" onClick={() => onNavigateToMatch(match.match_id)}
                              className="text-zinc-600 hover:text-blue-400 transition-colors cursor-pointer text-xs">
                              ↗
                            </button>
                          </td>
                        )}
                        <td className="py-2.5 px-2">
                          <button type="button" title="Eliminar CSV de este partido"
                            onClick={() => setConfirmDelete({ match_id: match.match_id, name: match.name })}
                            className="text-zinc-700 hover:text-red-400 transition-colors cursor-pointer">
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
            </div>
            )
          })()}
        </div>
      )}

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
