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
import { api, type QualityOverview, type StatsCoverage, type GapAnalysis, type LowQualityMatch } from "../lib/api"

export function DataQualityView() {
  const [overview, setOverview] = useState<QualityOverview | null>(null)
  const [coverage, setCoverage] = useState<StatsCoverage | null>(null)
  const [gaps, setGaps] = useState<GapAnalysis | null>(null)
  const [lowQuality, setLowQuality] = useState<LowQualityMatch[]>([])
  const [threshold, setThreshold] = useState(50)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [o, c, g, lq] = await Promise.all([
          api.getQualityOverview(),
          api.getStatsCoverage(),
          api.getGapAnalysis(),
          api.getLowQualityMatches(threshold),
        ])
        setOverview(o)
        setCoverage(c)
        setGaps(g)
        setLowQuality(lq.matches)
      } catch (err) {
        console.error("Failed to load quality data:", err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [threshold])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-zinc-500">
        Loading quality analytics...
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100 mb-1">Data Quality</h1>
        <p className="text-sm text-zinc-500">
          Analyze data quality metrics for finished matches
        </p>
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
