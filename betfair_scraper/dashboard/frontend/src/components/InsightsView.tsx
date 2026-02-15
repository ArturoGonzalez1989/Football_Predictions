import { useState, useEffect } from "react"
import {
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  Line,
  ComposedChart,
} from "recharts"
import {
  api,
  type Match,
  type AllCaptures,
  type MatchFull,
  type MomentumPatterns,
  type XgAccuracy,
  type OddsMovements,
  type OverUnderAnalysis,
  type StatCorrelations,
  type StrategyBackDraw00,
  type StrategyBet,
} from "../lib/api"
import { SiegeMeter } from "./SiegeMeter"
import { PriceVsReality } from "./PriceVsReality"
import { MomentumSwings } from "./MomentumSwings"

type Tab = "strategies" | "trading" | "momentum" | "xg" | "odds" | "overunder" | "correlations"

export function InsightsView() {
  const [activeTab, setActiveTab] = useState<Tab>("strategies")
  const [momentum, setMomentum] = useState<MomentumPatterns | null>(null)
  const [strategyDraw, setStrategyDraw] = useState<StrategyBackDraw00 | null>(null)
  const [xg, setXg] = useState<XgAccuracy | null>(null)
  const [odds, setOdds] = useState<OddsMovements | null>(null)
  const [overUnder, setOverUnder] = useState<OverUnderAnalysis | null>(null)
  const [correlations, setCorrelations] = useState<StatCorrelations | null>(null)
  const [loading, setLoading] = useState(true)

  // Trading tab state
  const [matches, setMatches] = useState<Match[]>([])
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null)
  const [tradingCaptures, setTradingCaptures] = useState<AllCaptures | null>(null)
  const [tradingFull, setTradingFull] = useState<MatchFull | null>(null)
  const [tradingLoading, setTradingLoading] = useState(false)

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const [m, x, o, ou, c, allMatches, sd] = await Promise.all([
          api.getMomentumPatterns(),
          api.getXgAccuracy(),
          api.getOddsMovements(),
          api.getOverUnderAnalysis(),
          api.getStatCorrelations(),
          api.getMatches(),
          api.getStrategyBackDraw00(),
        ])
        setMomentum(m)
        setXg(x)
        setOdds(o)
        setOverUnder(ou)
        setCorrelations(c)
        setStrategyDraw(sd)
        // Only matches with CSV data
        const flat = [...allMatches.live, ...allMatches.upcoming, ...allMatches.finished]
        const withData = flat.filter(m => m.csv_exists && m.capture_count >= 5)
        setMatches(withData)
        // Auto-select the match with most captures
        if (withData.length > 0) {
          const best = withData.reduce((a, b) => a.capture_count > b.capture_count ? a : b)
          setSelectedMatchId(best.match_id)
        }
      } catch (err) {
        console.error("Failed to load insights:", err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Load trading data when match selection changes
  useEffect(() => {
    if (!selectedMatchId) { setTradingCaptures(null); setTradingFull(null); return }
    setTradingLoading(true)
    Promise.all([
      api.getAllCaptures(selectedMatchId),
      api.getMatchFull(selectedMatchId),
    ]).then(([ac, f]) => {
      setTradingCaptures(ac)
      setTradingFull(f)
    }).catch(() => {}).finally(() => setTradingLoading(false))
  }, [selectedMatchId])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen text-zinc-500">
        Loading betting insights...
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100 mb-1">Insights</h1>
        <p className="text-sm text-zinc-500">
          Discover betting patterns and statistical correlations
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-zinc-800 overflow-x-auto">
        <TabButton
          active={activeTab === "strategies"}
          onClick={() => setActiveTab("strategies")}
          label="Strategies"
          accent
        />
        <TabButton
          active={activeTab === "trading"}
          onClick={() => setActiveTab("trading")}
          label="Trading Intelligence"
        />
        <TabButton
          active={activeTab === "momentum"}
          onClick={() => setActiveTab("momentum")}
          label="Momentum"
        />
        <TabButton
          active={activeTab === "xg"}
          onClick={() => setActiveTab("xg")}
          label="xG Accuracy"
        />
        <TabButton
          active={activeTab === "odds"}
          onClick={() => setActiveTab("odds")}
          label="Odds Movements"
        />
        <TabButton
          active={activeTab === "overunder"}
          onClick={() => setActiveTab("overunder")}
          label="Over/Under"
        />
        <TabButton
          active={activeTab === "correlations"}
          onClick={() => setActiveTab("correlations")}
          label="Correlations"
        />
      </div>

      {/* Tab Content */}
      {activeTab === "strategies" && strategyDraw && <StrategyDrawTab data={strategyDraw} />}
      {activeTab === "trading" && (
        <TradingTab
          matches={matches}
          selectedMatchId={selectedMatchId}
          onSelectMatch={setSelectedMatchId}
          captures={tradingCaptures}
          full={tradingFull}
          loading={tradingLoading}
        />
      )}
      {activeTab === "momentum" && momentum && <MomentumTab data={momentum} />}
      {activeTab === "xg" && xg && <XgTab data={xg} />}
      {activeTab === "odds" && odds && <OddsTab data={odds} />}
      {activeTab === "overunder" && overUnder && <OverUnderTab data={overUnder} />}
      {activeTab === "correlations" && correlations && <CorrelationsTab data={correlations} />}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  label,
  accent,
}: {
  active: boolean
  onClick: () => void
  label: string
  accent?: boolean
}) {
  const activeColor = accent ? "border-cyan-500 text-cyan-400" : "border-blue-500 text-blue-400"
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 whitespace-nowrap ${
        active
          ? activeColor
          : "border-transparent text-zinc-500 hover:text-zinc-300"
      }`}
    >
      {label}
    </button>
  )
}

function TradingTab({
  matches,
  selectedMatchId,
  onSelectMatch,
  captures,
  full,
  loading,
}: {
  matches: Match[]
  selectedMatchId: string | null
  onSelectMatch: (id: string) => void
  captures: AllCaptures | null
  full: MatchFull | null
  loading: boolean
}) {
  const selected = matches.find(m => m.match_id === selectedMatchId)
  const [home, away] = selected?.name.split(/\s*[-–]\s*|\s+vs\s+/i) ?? ["Home", "Away"]

  // Group matches by status
  const liveMatches = matches.filter(m => m.status === "live")
  const finishedMatches = matches.filter(m => m.status === "finished")

  return (
    <div className="space-y-6">
      {/* Match Selector */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-zinc-300">Select Match to Analyze</h2>
          <span className="text-[10px] text-zinc-600 font-mono">
            {matches.length} matches available
          </span>
        </div>
        <select
          aria-label="Select match to analyze"
          value={selectedMatchId ?? ""}
          onChange={e => onSelectMatch(e.target.value)}
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-cyan-500/50 focus:border-cyan-500/50"
        >
          {liveMatches.length > 0 && (
            <optgroup label="Live">
              {liveMatches.map(m => (
                <option key={m.match_id} value={m.match_id}>
                  {m.name} ({m.capture_count} captures, min {m.match_minute}')
                </option>
              ))}
            </optgroup>
          )}
          {finishedMatches.length > 0 && (
            <optgroup label="Finished">
              {finishedMatches.map(m => (
                <option key={m.match_id} value={m.match_id}>
                  {m.name} ({m.capture_count} captures)
                </option>
              ))}
            </optgroup>
          )}
        </select>
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-center py-8 text-zinc-500 text-sm">
          Loading trading data...
        </div>
      )}

      {/* Trading Components */}
      {!loading && captures && captures.captures.length >= 5 && (
        <div className="space-y-4">
          <SiegeMeter
            captures={captures.captures}
            homeName={home}
            awayName={away}
          />

          {full?.odds_timeline && full.odds_timeline.length > 0 && (
            <PriceVsReality
              captures={captures.captures}
              oddsTimeline={full.odds_timeline}
              homeName={home}
            />
          )}

          <MomentumSwings
            captures={captures.captures}
            homeName={home}
            awayName={away}
          />
        </div>
      )}

      {/* Not enough data */}
      {!loading && captures && captures.captures.length < 5 && (
        <div className="text-center py-8 text-zinc-500 text-sm">
          Not enough capture data for trading analysis (need at least 5 captures)
        </div>
      )}

      {/* No match selected */}
      {!loading && !captures && !selectedMatchId && (
        <div className="text-center py-8 text-zinc-500 text-sm">
          Select a match above to begin analysis
        </div>
      )}
    </div>
  )
}

function MomentumTab({ data }: { data: MomentumPatterns }) {
  return (
    <div className="space-y-6">
      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetricCard
          title="Average Momentum Swing"
          value={data.avg_swing.toFixed(1)}
          description="Maximum momentum change per match"
        />
        <MetricCard
          title="Comeback Frequency"
          value={`${data.comeback_frequency}%`}
          description="Matches with significant momentum shifts"
        />
      </div>

      {/* Top Swings Table */}
      {data.top_swings.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Top Momentum Swings</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Partidos con los mayores cambios de momentum durante el juego. Valores altos indican partidos muy disputados con vaivenes constantes en el dominio del juego.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-3 text-xs font-medium text-zinc-500">Match</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Max Swing</th>
                </tr>
              </thead>
              <tbody>
                {data.top_swings.map((swing) => (
                  <tr
                    key={swing.match_id}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="py-2.5 px-3 text-zinc-300">{swing.name}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span className="text-blue-400 font-medium">{swing.swing}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function XgTab({ data }: { data: XgAccuracy }) {
  return (
    <div className="space-y-6">
      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MetricCard
          title="Correlation Coefficient"
          value={data.correlation.toFixed(3)}
          description="xG vs Actual Goals"
        />
        <MetricCard
          title="Average Accuracy"
          value={data.avg_accuracy.toFixed(2)}
          description="Mean absolute difference"
        />
      </div>

      {/* Scatter Plot */}
      {data.scatter_data.length > 0 && (() => {
        // Calculate axis max for the diagonal line
        const maxXg = Math.max(...data.scatter_data.map((d) => d.xg))
        const maxActual = Math.max(...data.scatter_data.map((d) => d.actual))
        const axisMax = Math.ceil(Math.max(maxXg, maxActual, 3))
        // Diagonal reference line data (y = x)
        const diagonalData = [
          { xg: 0, perfect: 0 },
          { xg: axisMax, perfect: axisMax },
        ]

        return (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-zinc-300 mb-1">xG vs Actual Goals</h2>
            <p className="text-xs text-zinc-500 mb-4">
              Compara los goles esperados (xG) con los goles reales anotados. La línea diagonal indica precisión perfecta. Puntos por encima = sobre-rendimiento, por debajo = sub-rendimiento.
            </p>
            <ResponsiveContainer width="100%" height={400}>
              <ComposedChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis
                  type="number"
                  dataKey="xg"
                  domain={[0, axisMax]}
                  tick={{ fill: "#71717a", fontSize: 11 }}
                  axisLine={{ stroke: "#27272a" }}
                  label={{ value: "Expected Goals (xG)", position: "insideBottom", offset: -10, fill: "#71717a" }}
                />
                <YAxis
                  type="number"
                  domain={[0, axisMax]}
                  tick={{ fill: "#71717a", fontSize: 11 }}
                  axisLine={{ stroke: "#27272a" }}
                  label={{ value: "Actual Goals", angle: -90, position: "insideLeft", fill: "#71717a" }}
                />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  contentStyle={{
                    backgroundColor: "#18181b",
                    border: "1px solid #27272a",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                {/* Diagonal y=x reference line */}
                <Line
                  data={diagonalData}
                  type="linear"
                  dataKey="perfect"
                  stroke="#52525b"
                  strokeWidth={1}
                  strokeDasharray="6 4"
                  dot={false}
                  legendType="none"
                  tooltipType="none"
                  isAnimationActive={false}
                />
                {/* Scatter points */}
                <Scatter name="xG vs Goals" data={data.scatter_data} dataKey="actual" fill="#3b82f6" opacity={0.7} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )
      })()}
    </div>
  )
}

function OddsTab({ data }: { data: OddsMovements }) {
  return (
    <div className="space-y-6">
      {/* Metric Card */}
      <MetricCard
        title="Average Odds Drift"
        value={`${data.avg_drift.toFixed(1)}%`}
        description="Absolute % change from opening to closing"
      />

      {/* Top Movements Table */}
      {data.top_movements.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Biggest Odds Movements</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Partidos con los mayores cambios en las cuotas de apertura a cierre. Drift (↑) = cuotas subieron, Contraction (↓) = cuotas bajaron. Movimientos grandes pueden indicar información nueva o apuestas fuertes.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-3 text-xs font-medium text-zinc-500">Match</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Movement</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Direction</th>
                </tr>
              </thead>
              <tbody>
                {data.top_movements.map((movement) => (
                  <tr
                    key={movement.match_id}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="py-2.5 px-3 text-zinc-300">{movement.name}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span className="text-blue-400 font-medium">{movement.movement.toFixed(1)}%</span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <span
                        className={`text-xs font-medium ${
                          movement.drift_pct > 0 ? "text-green-400" : "text-red-400"
                        }`}
                      >
                        {movement.drift_pct > 0 ? "↑ Drift" : "↓ Contraction"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function OverUnderTab({ data }: { data: OverUnderAnalysis }) {
  return (
    <div className="space-y-6">
      {/* Hit Rates Chart */}
      {data.hit_rates.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Over/Under Hit Rates</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Porcentaje de veces que cada línea de goles totales fue superada. Ej: "Over 2.5" con 65% significa que en el 65% de partidos hubo más de 2.5 goles.
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={data.hit_rates} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="line"
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
                label={{ value: "Hit Rate (%)", angle: -90, position: "insideLeft", fill: "#71717a" }}
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
              <Bar dataKey="hit_rate" radius={[4, 4, 0, 0]}>
                {data.hit_rates.map((_, index) => (
                  <Cell key={`cell-${index}`} fill="#3b82f6" opacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Hit Rates Table */}
      {data.hit_rates.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Line Hit Rates Summary</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Resumen detallado de las tasas de acierto por línea. Útil para identificar qué líneas tienen mejor valor estadístico en tus partidos capturados.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-3 text-xs font-medium text-zinc-500">Line</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Hit Rate</th>
                </tr>
              </thead>
              <tbody>
                {data.hit_rates.map((rate) => (
                  <tr
                    key={rate.line}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="py-2.5 px-3 text-zinc-300">{rate.line}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          rate.hit_rate > 70
                            ? "bg-green-500/20 text-green-400"
                            : rate.hit_rate > 50
                              ? "bg-blue-500/20 text-blue-400"
                              : "bg-orange-500/20 text-orange-400"
                        }`}
                      >
                        {rate.hit_rate}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function CorrelationsTab({ data }: { data: StatCorrelations }) {
  return (
    <div className="space-y-6">
      {/* Top Correlations Chart */}
      {data.top_correlations.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Strongest Correlations</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Relaciones más fuertes entre estadísticas. Verde (positiva) = cuando una sube, la otra también. Rojo (negativa) = cuando una sube, la otra baja. Valores cerca de 1 o -1 = correlación fuerte.
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart
              data={data.top_correlations}
              layout="vertical"
              margin={{ top: 5, right: 20, left: 150, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                type="number"
                domain={[-1, 1]}
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
              />
              <YAxis
                type="category"
                dataKey="pair"
                tick={{ fill: "#71717a", fontSize: 10 }}
                axisLine={{ stroke: "#27272a" }}
                tickLine={false}
                width={145}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #27272a",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                {data.top_correlations.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={entry.value > 0 ? "#10b981" : "#ef4444"}
                    opacity={0.8}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Correlation Matrix Table */}
      {data.matrix.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Correlation Matrix</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Matriz completa de correlaciones entre todos los pares de estadísticas. Útil para entender relaciones entre métricas y encontrar patrones predictivos.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-3 text-xs font-medium text-zinc-500">Stat 1</th>
                  <th className="text-left py-2 px-3 text-xs font-medium text-zinc-500">Stat 2</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-zinc-500">Correlation</th>
                </tr>
              </thead>
              <tbody>
                {data.matrix.map((corr, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="py-2.5 px-3 text-zinc-400 text-xs">{corr.stat1}</td>
                    <td className="py-2.5 px-3 text-zinc-400 text-xs">{corr.stat2}</td>
                    <td className="py-2.5 px-3 text-right">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          Math.abs(corr.correlation) > 0.7
                            ? corr.correlation > 0
                              ? "bg-green-500/20 text-green-400"
                              : "bg-red-500/20 text-red-400"
                            : Math.abs(corr.correlation) > 0.4
                              ? "bg-blue-500/20 text-blue-400"
                              : "bg-zinc-700 text-zinc-400"
                        }`}
                      >
                        {corr.correlation.toFixed(3)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

type StrategyVersion = "v1" | "v15" | "v2r" | "v2"

const STRATEGY_VERSIONS: { key: StrategyVersion; label: string; desc: string; filterKey?: keyof StrategyBet }[] = [
  { key: "v1", label: "V1 — Base", desc: "0-0 min 30+" },
  { key: "v15", label: "V1.5", desc: "xG<0.6 + PD<25%", filterKey: "passes_v15" },
  { key: "v2r", label: "V2r", desc: "xG<0.6 + PD<20% + Sh<8", filterKey: "passes_v2r" },
  { key: "v2", label: "V2", desc: "xG<0.5 + PD<20% + Sh<8", filterKey: "passes_v2" },
]

function StrategyDrawTab({ data }: { data: StrategyBackDraw00 }) {
  const { summary, bets, total_matches, with_trigger } = data
  const [version, setVersion] = useState<StrategyVersion>("v1")

  const activeVersion = STRATEGY_VERSIONS.find(v => v.key === version)!
  const filteredBets = activeVersion.filterKey
    ? bets.filter(b => b[activeVersion.filterKey!])
    : bets
  const stats = summary[version] ?? summary.base

  // Cumulative P/L for filtered bets
  const cumPl = filteredBets.reduce<{ match: string; pl: number; cumPl: number }[]>((acc, b) => {
    const prev = acc.length > 0 ? acc[acc.length - 1].cumPl : 0
    const shortName = b.match.length > 20 ? b.match.slice(0, 18) + "..." : b.match
    acc.push({ match: shortName, pl: b.pl, cumPl: round2(prev + b.pl) })
    return acc
  }, [])

  const vLabel = activeVersion.label

  return (
    <div className="space-y-6">
      {/* Header + Version Selector */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-base font-semibold text-zinc-200">Back Empate 0-0 (min 30+)</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Stake fijo 10 EUR, comision Betfair 5%.
            </p>
          </div>
          <span className="text-[10px] text-zinc-600 font-mono">
            {total_matches} partidos analizados
          </span>
        </div>
        {/* Version selector */}
        <div className="flex gap-2 flex-wrap">
          {STRATEGY_VERSIONS.map(v => (
            <button
              key={v.key}
              type="button"
              onClick={() => setVersion(v.key)}
              className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                version === v.key
                  ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                  : "bg-zinc-800 text-zinc-500 border border-zinc-700 hover:text-zinc-300"
              }`}
            >
              {v.label}
              <span className="ml-1.5 text-[10px] opacity-70">{v.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          title="Triggers"
          value={`${stats.bets} / ${with_trigger}`}
          description={version === "v1" ? `${total_matches > 0 ? Math.round(with_trigger / total_matches * 100) : 0}% de los partidos` : `${with_trigger > 0 ? Math.round(stats.bets / with_trigger * 100) : 0}% de los triggers`}
        />
        <MetricCard
          title="Win Rate"
          value={stats.bets > 0 ? `${stats.win_pct}%` : "N/A"}
          description={stats.bets > 0 ? `${stats.wins}/${stats.bets} ganadas` : "Sin apuestas"}
        />
        <MetricCard
          title="P/L neto"
          value={stats.bets > 0 ? `${stats.pl >= 0 ? "+" : ""}${stats.pl} EUR` : "N/A"}
          description={stats.bets > 0 ? `ROI: ${stats.roi >= 0 ? "+" : ""}${stats.roi}%` : "Sin apuestas"}
        />
        <MetricCard
          title="Regla"
          value={vLabel}
          description={version === "v1" ? "Todos los triggers 0-0" : activeVersion.desc}
        />
      </div>

      {/* Cumulative P/L Chart */}
      {cumPl.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">P/L Acumulado ({vLabel})</h2>
          <p className="text-xs text-zinc-500 mb-4">
            {version === "v1"
              ? "Todos los triggers 0-0 al min 30+, stake 10 EUR."
              : `Solo triggers que cumplen ${activeVersion.desc}.`
            }
          </p>
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={cumPl} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="match" tick={false} axisLine={{ stroke: "#27272a" }} />
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
                formatter={(value: number, name: string) =>
                  name === "cumPl" ? [`${value} EUR`, "P/L acumulado"] : [`${value} EUR`, "Apuesta"]
                }
                labelFormatter={(label) => label}
              />
              <ReferenceLine y={0} stroke="#52525b" strokeDasharray="3 3" />
              <Bar dataKey="pl" radius={[2, 2, 0, 0]}>
                {cumPl.map((entry, i) => (
                  <Cell key={i} fill={entry.pl >= 0 ? "#10b981" : "#ef4444"} opacity={0.5} />
                ))}
              </Bar>
              <Line
                type="monotone"
                dataKey="cumPl"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Bets Detail Table */}
      {filteredBets.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Detalle de apuestas ({vLabel})</h2>
          <p className="text-xs text-zinc-500 mb-4">
            {version === "v1"
              ? "Cada fila es un trigger (0-0 al min 30+)."
              : `Solo apuestas que cumplen ${activeVersion.desc}.`
            }
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-2 text-xs font-medium text-zinc-500">Partido</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Min</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Back</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">xG</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">PD%</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Sh</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">SoT</th>
                  <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">FT</th>
                  {version === "v1" && <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">Mejor</th>}
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">P/L</th>
                </tr>
              </thead>
              <tbody>
                {filteredBets.map((b) => (
                  <tr
                    key={b.match_id}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="py-2 px-2 text-zinc-300 text-xs max-w-[180px] truncate" title={b.match}>{b.match}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.minuto ?? "-"}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.back_draw?.toFixed(2) ?? "-"}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.xg_total?.toFixed(2) ?? "-"}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.poss_diff != null ? `${b.poss_diff.toFixed(0)}%` : "-"}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.shots_total ?? "-"}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.sot_total ?? "-"}</td>
                    <td className="py-2 px-2 text-center text-xs">
                      <span className={b.won ? "text-green-400" : "text-red-400"}>{b.ft_score}</span>
                    </td>
                    {version === "v1" && (
                      <td className="py-2 px-2 text-center text-xs">
                        {b.passes_v2 ? (
                          <span className="text-green-400">V2</span>
                        ) : b.passes_v2r ? (
                          <span className="text-cyan-400">V2r</span>
                        ) : b.passes_v15 ? (
                          <span className="text-yellow-400">V1.5</span>
                        ) : (
                          <span className="text-zinc-600">-</span>
                        )}
                      </td>
                    )}
                    <td className="py-2 px-2 text-right text-xs font-medium">
                      <span className={b.pl >= 0 ? "text-green-400" : "text-red-400"}>
                        {b.pl >= 0 ? "+" : ""}{b.pl}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {filteredBets.length === 0 && (
        <div className="text-center py-12 text-zinc-500 text-sm">
          {version === "v1"
            ? "Ningun partido finalizado cumple el trigger (0-0 al min 30+)."
            : `Ningun partido finalizado cumple los filtros de ${activeVersion.label} (${activeVersion.desc}).`
          }
        </div>
      )}
    </div>
  )
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
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
