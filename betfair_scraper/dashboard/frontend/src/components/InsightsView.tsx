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
  Area,
  LineChart,
  Legend,
  ReferenceArea,
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
  type StrategyXGUnderperformance,
  type StrategyXGBet,
  type StrategyOddsDrift,
  type StrategyOddsDriftBet,
  type StrategyGoalClustering,
  type StrategyGoalClusteringBet,
  type StrategyPressureCooker,
  type StrategyPressureCookerBet,
  type Cartera,
  type CarteraBet,
} from "../lib/api"
import { SiegeMeter } from "./SiegeMeter"
import { PriceVsReality } from "./PriceVsReality"
import { MomentumSwings } from "./MomentumSwings"

type Tab = "strategies" | "trading" | "momentum" | "xg" | "odds" | "overunder" | "correlations"

export function InsightsView() {
  const [activeTab, setActiveTab] = useState<Tab>("strategies")
  const [momentum, setMomentum] = useState<MomentumPatterns | null>(null)
  const [strategyDraw, setStrategyDraw] = useState<StrategyBackDraw00 | null>(null)
  const [strategyXG, setStrategyXG] = useState<StrategyXGUnderperformance | null>(null)
  const [strategyDrift, setStrategyDrift] = useState<StrategyOddsDrift | null>(null)
  const [strategyGoalClustering, setStrategyGoalClustering] = useState<StrategyGoalClustering | null>(null)
  const [strategyPressureCooker, setStrategyPressureCooker] = useState<StrategyPressureCooker | null>(null)
  const [cartera, setCartera] = useState<Cartera | null>(null)
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
        const results = await Promise.allSettled([
          api.getMomentumPatterns(),
          api.getXgAccuracy(),
          api.getOddsMovements(),
          api.getOverUnderAnalysis(),
          api.getStatCorrelations(),
          api.getMatches(),
          api.getStrategyBackDraw00(),
          api.getStrategyXGUnderperformance(),
          api.getStrategyOddsDrift(),
          api.getStrategyGoalClustering(),
          api.getStrategyPressureCooker(),
          api.getCartera(),
        ])
        const val = <T,>(r: PromiseSettledResult<T>): T | null => r.status === "fulfilled" ? r.value : null
        const m = val(results[0])
        const x = val(results[1])
        const o = val(results[2])
        const ou = val(results[3])
        const c = val(results[4])
        const allMatches = val(results[5])
        const sd = val(results[6])
        const sxg = val(results[7])
        const sdr = val(results[8])
        const sgc = val(results[9])
        const spc = val(results[10])
        const cart = val(results[11])
        // Log any failures
        results.forEach((r, i) => { if (r.status === "rejected") console.warn(`Insights API call #${i} failed:`, r.reason) })
        if (m) setMomentum(m)
        if (x) setXg(x)
        if (o) setOdds(o)
        if (ou) setOverUnder(ou)
        if (c) setCorrelations(c)
        if (sd) setStrategyDraw(sd)
        if (sxg) setStrategyXG(sxg)
        if (sdr) setStrategyDrift(sdr)
        if (sgc) setStrategyGoalClustering(sgc)
        if (spc) setStrategyPressureCooker(spc)
        if (cart) setCartera(cart)
        // Only matches with CSV data
        if (allMatches) {
          const flat = [...allMatches.live, ...allMatches.upcoming, ...allMatches.finished]
          const withData = flat.filter(m => m.csv_exists && m.capture_count >= 5)
          setMatches(withData)
          if (withData.length > 0) {
            const best = withData.reduce((a, b) => a.capture_count > b.capture_count ? a : b)
            setSelectedMatchId(best.match_id)
          }
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
      {activeTab === "strategies" && (
        <StrategiesContainer
          strategyDraw={strategyDraw}
          strategyXG={strategyXG}
          strategyDrift={strategyDrift}
          strategyGoalClustering={strategyGoalClustering}
          strategyPressureCooker={strategyPressureCooker}
          cartera={cartera}
        />
      )}
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

// CSV Download helpers
function downloadCSV(filename: string, csvContent: string) {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function generateCarteraCSV(bets: CarteraBet[]): string {
  const headers = [
    'match', 'match_id', 'csv_file', 'timestamp_utc', 'strategy', 'minuto', 'score', 'ft_score', 'won', 'pl',
    // Odds
    'back_draw', 'back_over_odds', 'over_line', 'back_odds', 'drift_pct',
    // Stats
    'xg_total', 'xg_excess', 'poss_diff', 'shots_total', 'sot_total', 'sot_max',
    // Validation columns
    'passes_v15', 'passes_v2r', 'passes_v2', 'passes_v3', 'passes_v4',
    'team', 'goal_diff'
  ].join(',')

  const rows = bets.map(b => {
    const csvFile = `${b.match_id}.csv`
    const strategy = b.strategy_label || b.strategy || ''

    return [
      `"${b.match}"`, b.match_id, csvFile, b.timestamp_utc || '', strategy,
      b.minuto ?? '', b.score_at_trigger || '', b.ft_score, b.won ? 1 : 0, b.pl,
      b.back_draw ?? '', b.back_over_odds ?? (b as any).over_odds ?? '', b.over_line || '', b.back_odds ?? '', b.drift_pct ?? '',
      b.xg_total ?? '', b.xg_excess ?? '', b.poss_diff ?? '', b.shots_total ?? '', b.sot_total ?? '', b.sot_max ?? '',
      b.passes_v15 ? 1 : 0, b.passes_v2r ? 1 : 0, b.passes_v2 ? 1 : 0, b.passes_v3 ? 1 : 0, b.passes_v4 ? 1 : 0,
      b.team || '', b.goal_diff ?? ''
    ].join(',')
  })

  return [headers, ...rows].join('\n')
}

function generateBackDrawCSV(bets: StrategyBet[]): string {
  const headers = [
    'match', 'match_id', 'csv_file', 'timestamp_utc', 'minuto', 'score',
    'back_draw', 'xg_total', 'xg_max', 'poss_diff', 'shots_total', 'sot_total',
    'bfed_prematch', 'ft_score', 'won', 'pl',
    // Validation columns (1/0)
    'cumple_minuto_30', 'cumple_score_00', 'cumple_xg_bajo_06', 'cumple_xg_bajo_05',
    'cumple_poss_equilibrada_25', 'cumple_poss_equilibrada_20',
    'cumple_tiros_bajos', 'passes_v1', 'passes_v15', 'passes_v2r', 'passes_v2'
  ].join(',')

  const rows = bets.map(b => {
    const csvFile = `${b.match_id}.csv`
    const minuto = b.minuto ?? ''
    const xgTotal = b.xg_total ?? ''
    const xgMax = b.xg_max ?? ''
    const possDiff = b.poss_diff ?? ''
    const shotsTotal = b.shots_total ?? ''
    const sotTotal = b.sot_total ?? ''

    // Validation flags
    const cumpleMinuto30 = (b.minuto && b.minuto >= 30) ? 1 : 0
    const cumpleScore00 = 1 // Always true for this strategy trigger
    const cumpleXgBajo06 = (b.xg_total !== null && b.xg_total < 0.6) ? 1 : 0
    const cumpleXgBajo05 = (b.xg_total !== null && b.xg_total < 0.5) ? 1 : 0
    const cumplePossEq25 = (b.poss_diff !== null && b.poss_diff < 25) ? 1 : 0
    const cumplePossEq20 = (b.poss_diff !== null && b.poss_diff < 20) ? 1 : 0
    const cumpleTirosBajos = (b.shots_total !== null && b.shots_total < 8) ? 1 : 0

    return [
      `"${b.match}"`, b.match_id, csvFile, b.timestamp_utc || '',
      minuto, '0-0', b.back_draw ?? '', xgTotal, xgMax, possDiff, shotsTotal, sotTotal,
      b.bfed_prematch ?? '', b.ft_score, b.won ? 1 : 0, b.pl,
      cumpleMinuto30, cumpleScore00, cumpleXgBajo06, cumpleXgBajo05,
      cumplePossEq25, cumplePossEq20, cumpleTirosBajos,
      b.passes_v2 ? 1 : 0, b.passes_v15 ? 1 : 0, b.passes_v2r ? 1 : 0, b.passes_v2 ? 1 : 0
    ].join(',')
  })

  return [headers, ...rows].join('\n')
}

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

type StrategySubTab = "draw" | "xg" | "drift" | "clustering" | "pressure" | "cartera"

function StrategiesContainer({
  strategyDraw,
  strategyXG,
  strategyDrift,
  strategyGoalClustering,
  strategyPressureCooker,
  cartera,
}: {
  strategyDraw: StrategyBackDraw00 | null
  strategyXG: StrategyXGUnderperformance | null
  strategyDrift: StrategyOddsDrift | null
  strategyGoalClustering: StrategyGoalClustering | null
  strategyPressureCooker: StrategyPressureCooker | null
  cartera: Cartera | null
}) {
  const [sub, setSub] = useState<StrategySubTab>("draw")

  const subTabs: { key: StrategySubTab; label: string; color: string }[] = [
    { key: "draw", label: "Back Empate 0-0", color: "cyan" },
    { key: "xg", label: "xG Underperf", color: "amber" },
    { key: "drift", label: "Odds Drift", color: "emerald" },
    { key: "clustering", label: "Goal Clustering", color: "rose" },
    { key: "pressure", label: "Pressure Cooker", color: "orange" },
    { key: "cartera", label: "Cartera", color: "purple" },
  ]

  const colorMapActive: Record<string, string> = {
    cyan: "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40",
    amber: "bg-amber-500/20 text-amber-400 border border-amber-500/40",
    emerald: "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40",
    rose: "bg-rose-500/20 text-rose-400 border border-rose-500/40",
    orange: "bg-orange-500/20 text-orange-400 border border-orange-500/40",
    purple: "bg-purple-500/20 text-purple-400 border border-purple-500/40",
  }

  const colorMapInactive: Record<string, string> = {
    cyan: "bg-cyan-500/5 text-cyan-500/60 border border-cyan-500/20 hover:border-cyan-500/30",
    amber: "bg-amber-500/5 text-amber-500/60 border border-amber-500/20 hover:border-amber-500/30",
    emerald: "bg-emerald-500/5 text-emerald-500/60 border border-emerald-500/20 hover:border-emerald-500/30",
    rose: "bg-rose-500/5 text-rose-500/60 border border-rose-500/20 hover:border-rose-500/30",
    orange: "bg-orange-500/5 text-orange-500/60 border border-orange-500/20 hover:border-orange-500/30",
    purple: "bg-purple-500/5 text-purple-500/60 border border-purple-500/20 hover:border-purple-500/30",
  }

  return (
    <div className="space-y-4">
      {/* Sub-tab navigation */}
      <div className="flex gap-1.5 bg-zinc-900/50 border border-zinc-800 rounded-xl p-1.5">
        {subTabs.map(t => (
          <button
            key={t.key}
            type="button"
            onClick={() => setSub(t.key)}
            className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
              sub === t.key
                ? colorMapActive[t.color]
                : colorMapInactive[t.color]
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {sub === "draw" && strategyDraw && <StrategyDrawTab data={strategyDraw} />}
      {sub === "draw" && !strategyDraw && (
        <div className="text-center py-12 text-zinc-500 text-sm">No hay datos de Back Empate 0-0.</div>
      )}
      {sub === "xg" && strategyXG && <StrategyXGTab data={strategyXG} />}
      {sub === "xg" && !strategyXG && (
        <div className="text-center py-12 text-zinc-500 text-sm">No hay datos de xG Underperformance.</div>
      )}
      {sub === "drift" && strategyDrift && <StrategyDriftTab data={strategyDrift} />}
      {sub === "drift" && !strategyDrift && (
        <div className="text-center py-12 text-zinc-500 text-sm">No hay datos de Odds Drift.</div>
      )}
      {sub === "clustering" && strategyGoalClustering && <GoalClusteringTab data={strategyGoalClustering} />}
      {sub === "clustering" && !strategyGoalClustering && (
        <div className="text-center py-12 text-zinc-500 text-sm">No hay datos de Goal Clustering.</div>
      )}
      {sub === "pressure" && strategyPressureCooker && <PressureCookerTab data={strategyPressureCooker} />}
      {sub === "pressure" && !strategyPressureCooker && (
        <div className="text-center py-12 text-zinc-500 text-sm">No hay datos de Pressure Cooker.</div>
      )}
      {sub === "cartera" && cartera && <CarteraTab data={cartera} />}
      {sub === "cartera" && !cartera && (
        <div className="text-center py-12 text-zinc-500 text-sm">No hay datos de cartera.</div>
      )}
    </div>
  )
}

type XGVersion = "base" | "v2"

const XG_VERSIONS: { key: XGVersion; label: string; desc: string }[] = [
  { key: "base", label: "V1 - Base", desc: "xG ex>=0.5 + Perdiendo" },
  { key: "v2", label: "V2", desc: "V1 + SoT>=2" },
]

function StrategyXGTab({ data }: { data: StrategyXGUnderperformance }) {
  const { summary, bets, total_matches, with_trigger } = data
  const [version, setVersion] = useState<XGVersion>("base")

  const filteredBets = version === "v2" ? bets.filter(b => b.passes_v2) : bets
  const stats = summary[version]

  const cumPl = filteredBets.reduce<{ match: string; pl: number; cumPl: number }[]>((acc, b) => {
    const prev = acc.length > 0 ? acc[acc.length - 1].cumPl : 0
    const shortName = b.match.length > 20 ? b.match.slice(0, 18) + "..." : b.match
    acc.push({ match: shortName, pl: b.pl, cumPl: round2(prev + b.pl) })
    return acc
  }, [])

  const activeV = XG_VERSIONS.find(v => v.key === version)!

  return (
    <div className="space-y-6">
      {/* Header + Version Selector */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-base font-semibold text-zinc-200">xG Underperformance - Back Over</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Cuando xG - goles &gt;= 0.5 y equipo va perdiendo, Back Over (total+0.5). Stake 10 EUR, com. 5%.
            </p>
          </div>
          <span className="text-[10px] text-zinc-600 font-mono">
            {total_matches} partidos analizados
          </span>
        </div>
        <div className="flex gap-2 flex-wrap">
          {XG_VERSIONS.map(v => (
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
          description={version === "base" ? `${total_matches > 0 ? Math.round(with_trigger / total_matches * 100) : 0}% de los partidos` : `${with_trigger > 0 ? Math.round(stats.bets / with_trigger * 100) : 0}% de los triggers`}
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
          value={activeV.label}
          description={activeV.desc}
        />
      </div>

      {/* Cumulative P/L Chart */}
      {cumPl.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">P/L Acumulado ({activeV.label})</h2>
          <p className="text-xs text-zinc-500 mb-4">
            {version === "base"
              ? "Todos los triggers: xG excess >= 0.5 + equipo perdiendo."
              : "Solo triggers con SoT >= 2."
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
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Detalle de apuestas ({activeV.label})</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Cada fila es un trigger: equipo con xG excess &gt;= 0.5 que va perdiendo.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-2 text-xs font-medium text-zinc-500">Partido</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Min</th>
                  <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">Score</th>
                  <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">Team</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">xG</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Exc</th>
                  <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">Over</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Odds</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">SoT</th>
                  <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">FT</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">P/L</th>
                </tr>
              </thead>
              <tbody>
                {filteredBets.map((b, i) => (
                  <tr
                    key={`${b.match_id}-${i}`}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                  >
                    <td className="py-2 px-2 text-zinc-300 text-xs max-w-[160px] truncate" title={b.match}>{b.match}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.minuto ?? "-"}</td>
                    <td className="py-2 px-2 text-center text-zinc-400 text-xs">{b.score_at_trigger}</td>
                    <td className="py-2 px-2 text-center text-xs">
                      <span className={b.team === "home" ? "text-blue-400" : "text-amber-400"}>
                        {b.team === "home" ? "H" : "A"}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.team_xg?.toFixed(2) ?? "-"}</td>
                    <td className="py-2 px-2 text-right text-cyan-400 text-xs font-medium">{b.xg_excess?.toFixed(2) ?? "-"}</td>
                    <td className="py-2 px-2 text-center text-zinc-400 text-xs">{b.over_line || "-"}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{(b.back_over_odds ?? (b as any).over_odds)?.toFixed(2) ?? "-"}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.sot_team ?? "-"}</td>
                    <td className="py-2 px-2 text-center text-xs">
                      <span className={b.won ? "text-green-400" : "text-red-400"}>{b.ft_score}</span>
                    </td>
                    <td className="py-2 px-2 text-right text-xs font-medium">
                      <span className={b.pl >= 0 ? "text-green-400" : "text-red-400"}>
                        {b.pl >= 0 ? "+" : ""}{b.pl.toFixed(2)}
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
          {version === "base"
            ? "Ningun partido finalizado cumple el trigger (xG excess >= 0.5 + perdiendo)."
            : "Ningun partido finalizado cumple V2 (xG excess >= 0.5 + perdiendo + SoT >= 2)."
          }
        </div>
      )}
    </div>
  )
}

// ── Odds Drift Contrarian Strategy Tab ──────────────────────────────

type DriftVersion = "v1" | "v2" | "v3" | "v4"

const DRIFT_VERSIONS: { key: DriftVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1 - Base", desc: "Drift >30% + va ganando" },
  { key: "v2", label: "V2 - 2+ goles", desc: "V1 + ventaja 2+ goles" },
  { key: "v3", label: "V3 - Drift extremo", desc: "V1 + drift >= 100%" },
  { key: "v4", label: "V4 - 2a parte", desc: "V1 + odds<=5 + min>45" },
]

function StrategyDriftTab({ data }: { data: StrategyOddsDrift }) {
  const { summary, bets, total_matches, with_trigger } = data
  const [version, setVersion] = useState<DriftVersion>("v1")

  const filteredBets = version === "v1" ? bets
    : version === "v2" ? bets.filter(b => b.passes_v2)
    : version === "v3" ? bets.filter(b => b.passes_v3)
    : bets.filter(b => b.passes_v4)
  const stats = summary[version]

  // Cumulative P/L
  let cumPl = 0
  const cumData = filteredBets.map((b, i) => {
    cumPl = round2(cumPl + b.pl)
    return { idx: i + 1, pl: b.pl, cumPl }
  })

  return (
    <div className="space-y-6">
      {/* Version Selector */}
      <div className="flex gap-2 flex-wrap">
        {DRIFT_VERSIONS.map(v => (
          <button
            key={v.key}
            type="button"
            onClick={() => setVersion(v.key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              version === v.key
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                : "bg-zinc-800/50 text-zinc-500 border border-zinc-700/50 hover:text-zinc-300"
            }`}
            title={v.desc}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          title="Partidos analizados"
          value={total_matches}
          description={`${with_trigger} triggers detectados`}
        />
        <MetricCard
          title="Apuestas"
          value={stats.bets}
          description={`${stats.win_pct}% WR (${stats.wins}/${stats.bets})`}
        />
        <MetricCard
          title="P/L Flat"
          value={`${stats.pl >= 0 ? "+" : ""}${stats.pl.toFixed(2)} EUR`}
          description={`ROI: ${stats.roi >= 0 ? "+" : ""}${stats.roi}% (10 EUR/apuesta)`}
        />
        <MetricCard
          title="Regla"
          value={DRIFT_VERSIONS.find(v => v.key === version)!.label}
          description={DRIFT_VERSIONS.find(v => v.key === version)!.desc}
        />
      </div>

      {/* Cumulative P/L Chart */}
      {cumData.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">P/L Acumulado - Odds Drift ({DRIFT_VERSIONS.find(v => v.key === version)!.label})</h2>
          <p className="text-xs text-zinc-500 mb-4">Stake 10 EUR flat, comision 5%.</p>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={cumData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="idx" tick={{ fill: "#71717a", fontSize: 11 }} axisLine={{ stroke: "#27272a" }}
                label={{ value: "Apuesta #", position: "insideBottom", offset: -2, fill: "#52525b", fontSize: 10 }} />
              <YAxis tick={{ fill: "#71717a", fontSize: 11 }} axisLine={{ stroke: "#27272a" }} tickLine={false} />
              <Tooltip
                contentStyle={{ backgroundColor: "#18181b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
                formatter={(value: number, name: string) => [
                  `${value.toFixed(2)} EUR`,
                  name === "cumPl" ? "Acumulado" : "P/L",
                ]}
                labelFormatter={(l) => `Apuesta #${l}`}
              />
              <ReferenceLine y={0} stroke="#52525b" strokeDasharray="3 3" />
              <Bar dataKey="pl" fill="#10b981" radius={[2, 2, 0, 0]}>
                {cumData.map((d, i) => (
                  <Cell key={i} fill={d.pl >= 0 ? "#10b981" : "#ef4444"} fillOpacity={0.6} />
                ))}
              </Bar>
              <Line type="monotone" dataKey="cumPl" stroke="#34d399" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Detail Table */}
      {filteredBets.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Detalle de triggers</h2>
          <p className="text-xs text-zinc-500 mb-4">{filteredBets.length} apuestas ({version.toUpperCase()})</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-left py-2 px-2 text-xs font-medium text-zinc-500">Partido</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Min</th>
                  <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">Score</th>
                  <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">Team</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">GD</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Drift</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">Odds</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">SoT</th>
                  <th className="text-center py-2 px-2 text-xs font-medium text-zinc-500">FT</th>
                  <th className="text-right py-2 px-2 text-xs font-medium text-zinc-500">P/L</th>
                </tr>
              </thead>
              <tbody>
                {filteredBets.map((b, i) => (
                  <tr key={`${b.match_id}-${b.team}-${i}`}
                    className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                    <td className="py-2 px-2 text-zinc-300 text-xs max-w-[180px] truncate" title={b.match}>{b.match}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.minuto ?? "-"}</td>
                    <td className="py-2 px-2 text-center text-xs text-zinc-400">{b.score_at_trigger}</td>
                    <td className="py-2 px-2 text-center text-xs">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        b.team === "home" ? "bg-blue-500/15 text-blue-400" : "bg-orange-500/15 text-orange-400"
                      }`}>
                        {b.team === "home" ? "H" : "A"}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right text-xs text-emerald-400">+{b.goal_diff}</td>
                    <td className="py-2 px-2 text-right text-xs text-yellow-400">{b.drift_pct}%</td>
                    <td className="py-2 px-2 text-right text-zinc-300 text-xs">{b.back_odds.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right text-zinc-400 text-xs">{b.sot_team ?? "-"}</td>
                    <td className="py-2 px-2 text-center text-xs">
                      <span className={b.won ? "text-green-400" : "text-red-400"}>{b.ft_score}</span>
                    </td>
                    <td className="py-2 px-2 text-right text-xs font-medium">
                      <span className={b.pl >= 0 ? "text-green-400" : "text-red-400"}>
                        {b.pl >= 0 ? "+" : ""}{b.pl.toFixed(2)}
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
          Ningun partido finalizado cumple el trigger para {DRIFT_VERSIONS.find(v => v.key === version)!.label}.
        </div>
      )}
    </div>
  )
}

type DrawVersion = "v1" | "v15" | "v2r" | "v2" | "off"
type XGCarteraVersion = "base" | "v2" | "off"

const DRAW_VERSIONS: { key: DrawVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1", desc: "Base" },
  { key: "v15", label: "V1.5", desc: "xG<0.6+PD<25%" },
  { key: "v2r", label: "V2r", desc: "xG<0.6+PD<20%+Sh<8" },
  { key: "v2", label: "V2", desc: "xG<0.5+PD<20%+Sh<8" },
  { key: "off", label: "OFF", desc: "" },
]

const XG_CARTERA_VERSIONS: { key: XGCarteraVersion; label: string; desc: string }[] = [
  { key: "base", label: "V1", desc: "Base" },
  { key: "v2", label: "V2", desc: "SoT>=2" },
  { key: "off", label: "OFF", desc: "" },
]

function filterDrawBets(bets: CarteraBet[], version: DrawVersion): CarteraBet[] {
  if (version === "off") return []
  const drawBets = bets.filter(b => b.strategy === "back_draw_00")
  if (version === "v1") return drawBets
  if (version === "v15") return drawBets.filter(b => b.passes_v15)
  if (version === "v2r") return drawBets.filter(b => b.passes_v2r)
  if (version === "v2") return drawBets.filter(b => b.passes_v2)
  return drawBets
}

function filterXGBets(bets: CarteraBet[], version: XGCarteraVersion): CarteraBet[] {
  if (version === "off") return []
  const xgBets = bets.filter(b => b.strategy === "xg_underperformance")
  if (version === "base") return xgBets
  if (version === "v2") return xgBets.filter(b => b.passes_v2)
  return xgBets
}

type DriftCarteraVersion = "v1" | "v2" | "v3" | "v4" | "off"

const DRIFT_CARTERA_VERSIONS: { key: DriftCarteraVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1", desc: "Base" },
  { key: "v2", label: "V2", desc: "2+ goles" },
  { key: "v3", label: "V3", desc: "Drift>=100%" },
  { key: "v4", label: "V4", desc: "2a parte" },
  { key: "off", label: "OFF", desc: "" },
]

function filterDriftBets(bets: CarteraBet[], version: DriftCarteraVersion): CarteraBet[] {
  if (version === "off") return []
  const driftBets = bets.filter(b => b.strategy === "odds_drift")
  if (version === "v1") return driftBets
  if (version === "v2") return driftBets.filter(b => b.passes_v2)
  if (version === "v3") return driftBets.filter(b => b.passes_v3)
  if (version === "v4") return driftBets.filter(b => b.passes_v4)
  return driftBets
}

type ClusteringCarteraVersion = "v2" | "off"

const CLUSTERING_CARTERA_VERSIONS: { key: ClusteringCarteraVersion; label: string; desc: string }[] = [
  { key: "v2", label: "V2", desc: "SoT max>=3" },
  { key: "off", label: "OFF", desc: "" },
]

function filterClusteringBets(bets: CarteraBet[], version: ClusteringCarteraVersion): CarteraBet[] {
  if (version === "off") return []
  const clusteringBets = bets.filter(b => b.strategy === "goal_clustering")
  return clusteringBets
}

type PressureCarteraVersion = "v1" | "off"

const PRESSURE_CARTERA_VERSIONS: { key: PressureCarteraVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1", desc: "Empate 1-1+ min 65-75" },
  { key: "off", label: "OFF", desc: "" },
]

function filterPressureBets(bets: CarteraBet[], version: PressureCarteraVersion): CarteraBet[] {
  if (version === "off") return []
  return bets.filter(b => b.strategy === "pressure_cooker")
}

interface DrawdownInfo {
  maxDd: number
  peak: number
  trough: number
  peakIdx: number
  troughIdx: number
  ddPct: number // % of peak lost
}

function calcMaxDrawdown(cumulative: number[]): DrawdownInfo {
  let peak = 0
  let peakIdx = -1
  let maxDd = 0
  let ddPeak = 0
  let ddTrough = 0
  let ddPeakIdx = 0
  let ddTroughIdx = 0
  for (let i = 0; i < cumulative.length; i++) {
    const v = cumulative[i]
    if (v > peak) { peak = v; peakIdx = i }
    const dd = peak - v
    if (dd > maxDd) {
      maxDd = dd
      ddPeak = peak
      ddTrough = v
      ddPeakIdx = peakIdx
      ddTroughIdx = i
    }
  }
  const ddPct = ddPeak > 0 ? round2(maxDd / ddPeak * 100) : 0
  return {
    maxDd: round2(maxDd), peak: round2(ddPeak), trough: round2(ddTrough),
    peakIdx: ddPeakIdx, troughIdx: ddTroughIdx, ddPct,
  }
}

function calcWorstStreak(bets: CarteraBet[]): { losses: number; from: number; to: number; plLost: number } {
  let maxStreak = 0
  let maxFrom = 0
  let maxTo = 0
  let cur = 0
  let curFrom = 0
  let curPl = 0
  let maxPl = 0
  for (let i = 0; i < bets.length; i++) {
    if (bets[i].pl < 0) {
      if (cur === 0) { curFrom = i; curPl = 0 }
      cur++
      curPl += bets[i].pl
      if (cur > maxStreak) { maxStreak = cur; maxFrom = curFrom; maxTo = i; maxPl = curPl }
    } else {
      cur = 0
      curPl = 0
    }
  }
  return { losses: maxStreak, from: maxFrom + 1, to: maxTo + 1, plLost: round2(maxPl) }
}

type BankrollMode = "fixed" | "kelly" | "half_kelly" | "dd_protection" | "variable"

const BANKROLL_MODES: { key: BankrollMode; label: string; desc: string }[] = [
  { key: "fixed", label: "Fijo 2%", desc: "Apuesta siempre el 2% del bankroll" },
  { key: "kelly", label: "Kelly", desc: "WR rolling, max 8% del bankroll por apuesta" },
  { key: "half_kelly", label: "Half-Kelly", desc: "Kelly/2 rolling, max 4% del bankroll" },
  { key: "dd_protection", label: "Proteccion DD", desc: "2% base, 1% si cae >5%, 0.5% si cae >10% del pico" },
  { key: "variable", label: "Variable", desc: "3% xG / 1.5% Draw" },
]

function getBetOdds(b: CarteraBet): number {
  return b.back_draw ?? b.back_over_odds ?? (b as any).over_odds ?? b.back_odds ?? 2.0
}

function simulateCartera(bets: CarteraBet[], bankrollInit: number, mode: BankrollMode) {
  const FLAT_STAKE = 10
  const KELLY_MIN_BETS = 5 // minimum bets before Kelly kicks in (use fixed 2% before)

  let flatCum = 0
  let bankroll = bankrollInit
  let peakBankroll = bankrollInit
  const flatCumArr: number[] = []
  const managedCumArr: number[] = []
  const betDetails: { stake: number; plManaged: number; bankrollAfter: number }[] = []
  let flatWins = 0
  let managedPl = 0
  let rollingWins = 0 // track wins seen so far for rolling Kelly

  for (let i = 0; i < bets.length; i++) {
    const b = bets[i]
    // Flat (always 10 EUR)
    flatCum = round2(flatCum + b.pl)
    flatCumArr.push(flatCum)
    if (b.won) flatWins++

    // Rolling win rate: only from PREVIOUS bets (not current or future)
    const rollingWR = i > 0 ? rollingWins / i : 0.5

    // Calculate stake % based on mode
    const odds = getBetOdds(b)
    const bNet = Math.max(odds - 1, 0.01)
    let stakePct: number

    switch (mode) {
      case "fixed":
        stakePct = 0.02
        break
      case "kelly": {
        if (i < KELLY_MIN_BETS) {
          stakePct = 0.02 // conservative until enough data
        } else {
          const f = (rollingWR * bNet - (1 - rollingWR)) / bNet
          stakePct = Math.max(0, Math.min(f, 0.08)) // cap 8% - realistic for sports betting
        }
        break
      }
      case "half_kelly": {
        if (i < KELLY_MIN_BETS) {
          stakePct = 0.01 // half of conservative
        } else {
          const f = (rollingWR * bNet - (1 - rollingWR)) / bNet
          stakePct = Math.max(0, Math.min(f / 2, 0.04)) // cap 4%
        }
        break
      }
      case "dd_protection": {
        const ddFromPeak = peakBankroll > 0 ? (peakBankroll - bankroll) / peakBankroll : 0
        if (ddFromPeak > 0.10) stakePct = 0.005
        else if (ddFromPeak > 0.05) stakePct = 0.01
        else stakePct = 0.02
        break
      }
      case "variable":
        stakePct = b.strategy === "odds_drift" ? 0.025 : b.strategy === "xg_underperformance" ? 0.03 : b.strategy === "pressure_cooker" ? 0.02 : 0.015
        break
    }

    const stake = round2(bankroll * stakePct)
    const ratio = stake / FLAT_STAKE
    const managedBetPl = round2(b.pl * ratio)
    bankroll = round2(bankroll + managedBetPl)
    if (bankroll > peakBankroll) peakBankroll = bankroll
    managedPl = round2(managedPl + managedBetPl)
    managedCumArr.push(round2(bankroll - bankrollInit))
    betDetails.push({ stake, plManaged: managedBetPl, bankrollAfter: bankroll })

    // Update rolling wins AFTER using it (so bet i uses WR from bets 0..i-1)
    if (b.won) rollingWins++
  }

  const totalStaked = bets.length * FLAT_STAKE
  const flatDd = calcMaxDrawdown(flatCumArr)
  const managedDd = calcMaxDrawdown(managedCumArr)
  const worstStreak = calcWorstStreak(bets)

  return {
    total: bets.length,
    wins: flatWins,
    winPct: bets.length > 0 ? round2(flatWins / bets.length * 100) : 0,
    flatPl: flatCum,
    flatRoi: totalStaked > 0 ? round2(flatCum / totalStaked * 100) : 0,
    flatCumulative: flatCumArr,
    flatMaxDd: flatDd,
    managedPl,
    managedRoi: bankrollInit > 0 ? round2(managedPl / bankrollInit * 100) : 0,
    managedFinalBankroll: bankroll,
    managedCumulative: managedCumArr,
    managedMaxDd: managedDd,
    worstStreak,
    betDetails,
  }
}

type PresetKey = "max_roi" | "max_pl" | "max_wr" | "min_dd" | "max_bets" | null

const PRESETS: { key: Exclude<PresetKey, null>; label: string; icon: string; desc: string }[] = [
  { key: "max_roi", label: "Max ROI", icon: "%", desc: "Busca la combinacion de versiones que maximiza el retorno porcentual sobre lo apostado" },
  { key: "max_pl", label: "Max P/L", icon: "$", desc: "Maximiza el beneficio absoluto en EUR" },
  { key: "max_wr", label: "Max WR", icon: "W", desc: "Maximiza el porcentaje de acierto (con ligero bonus por mayor muestra)" },
  { key: "min_dd", label: "Min DD", icon: "D", desc: "Minimiza el drawdown relativo al P/L, tambien explora modo DD-protection de bankroll" },
  { key: "max_bets", label: "Max Datos", icon: "#", desc: "Selecciona todas las V1 para maximizar el tamano de muestra" },
]

interface VersionCombo {
  draw: DrawVersion; xg: XGCarteraVersion; drift: DriftCarteraVersion; clustering: ClusteringCarteraVersion; pressure: PressureCarteraVersion; br: BankrollMode
}

function evaluateCombo(bets: CarteraBet[], combo: VersionCombo, bankrollInit: number) {
  const drawBets = filterDrawBets(bets, combo.draw)
  const xgBets = filterXGBets(bets, combo.xg)
  const driftBets = filterDriftBets(bets, combo.drift)
  const clusteringBets = filterClusteringBets(bets, combo.clustering)
  const pressureBets = filterPressureBets(bets, combo.pressure)
  const filtered = [...drawBets, ...xgBets, ...driftBets, ...clusteringBets, ...pressureBets].sort((a, b) =>
    (a.timestamp_utc || "").localeCompare(b.timestamp_utc || "")
  )
  if (filtered.length === 0) return null
  const sim = simulateCartera(filtered, bankrollInit, combo.br)
  return { ...sim, combo, filtered }
}

function findBestCombo(bets: CarteraBet[], bankrollInit: number, criterion: Exclude<PresetKey, null>): VersionCombo {
  // For max_bets, just return all V1
  if (criterion === "max_bets") return { draw: "v1", xg: "base", drift: "v1", clustering: "v2", pressure: "v1", br: "fixed" }

  const drawOpts: DrawVersion[] = ["v1", "v15", "v2r", "v2"]
  const xgOpts: XGCarteraVersion[] = ["base", "v2"]
  const driftOpts: DriftCarteraVersion[] = ["v1", "v2", "v3", "v4"]
  const clusteringOpts: ClusteringCarteraVersion[] = ["v2", "off"]
  const pressureOpts: PressureCarteraVersion[] = ["v1", "off"]
  const brOpts: BankrollMode[] = criterion === "min_dd" ? ["dd_protection", "fixed", "half_kelly"] : ["fixed"]

  let best: VersionCombo = { draw: "v1", xg: "base", drift: "v1", clustering: "v2", pressure: "v1", br: "fixed" }
  let bestScore = -Infinity

  for (const draw of drawOpts) {
    for (const xg of xgOpts) {
      for (const drift of driftOpts) {
        for (const clustering of clusteringOpts) {
          for (const pressure of pressureOpts) {
            for (const br of brOpts) {
              const combo = { draw, xg, drift, clustering, pressure, br }
              const result = evaluateCombo(bets, combo, bankrollInit)
              if (!result || result.total < 3) continue

              let score: number
              switch (criterion) {
                case "max_roi": score = result.flatRoi; break
                case "max_pl": score = result.flatPl; break
                case "max_wr": score = result.winPct + result.total * 0.01; break // slight bonus for more bets
                case "min_dd": {
                  const ddPenalty = result.managedMaxDd.maxDd
                  score = result.managedPl - ddPenalty * 2 + result.winPct * 0.5
                  break
                }
                default: score = result.flatPl
              }
              if (score > bestScore) { bestScore = score; best = combo }
            }
          }
        }
      }
    }
  }
  return best
}

function CarteraTab({ data }: { data: Cartera }) {
  const { managed, bets } = data
  const [drawVer, setDrawVer] = useState<DrawVersion>("v1")
  const [xgVer, setXgVer] = useState<XGCarteraVersion>("base")
  const [driftVer, setDriftVer] = useState<DriftCarteraVersion>("v1")
  const [clusteringVer, setClusteringVer] = useState<ClusteringCarteraVersion>("v2")
  const [pressureVer, setPressureVer] = useState<PressureCarteraVersion>("v1")
  const [brMode, setBrMode] = useState<BankrollMode>("fixed")
  const [activePreset, setActivePreset] = useState<PresetKey>(null)

  const applyPreset = (key: Exclude<PresetKey, null>) => {
    const combo = findBestCombo(bets, managed.initial_bankroll, key)
    setDrawVer(combo.draw)
    setXgVer(combo.xg)
    setDriftVer(combo.drift)
    setClusteringVer(combo.clustering)
    setPressureVer(combo.pressure)
    setBrMode(combo.br)
    setActivePreset(key)
  }

  // Filter bets by selected versions, then re-sort chronologically
  const drawBets = filterDrawBets(bets, drawVer)
  const xgBets = filterXGBets(bets, xgVer)
  const driftBets = filterDriftBets(bets, driftVer)
  const clusteringBets = filterClusteringBets(bets, clusteringVer)
  const pressureBets = filterPressureBets(bets, pressureVer)
  const filteredBets = [...drawBets, ...xgBets, ...driftBets, ...clusteringBets, ...pressureBets].sort((a, b) =>
    (a.timestamp_utc || "").localeCompare(b.timestamp_utc || "")
  )

  const handleDownloadCSV = () => {
    const csv = generateCarteraCSV(filteredBets)
    const timestamp = new Date().toISOString().split('T')[0]
    const presetLabel = activePreset ? `_${activePreset}` : ''
    downloadCSV(`cartera${presetLabel}_${timestamp}.csv`, csv)
  }

  // Recalculate simulations
  const sim = simulateCartera(filteredBets, managed.initial_bankroll, brMode)

  // Per-strategy stats
  const stratConfigs = [
    { key: "back_draw_00", label: "Back Empate 0-0", bgClass: "bg-cyan-500", active: drawVer !== "off", verLabel: drawVer !== "off" ? DRAW_VERSIONS.find(v => v.key === drawVer)!.label : "" },
    { key: "xg_underperformance", label: "xG Underperformance", bgClass: "bg-amber-500", active: xgVer !== "off", verLabel: xgVer !== "off" ? XG_CARTERA_VERSIONS.find(v => v.key === xgVer)!.label : "" },
    { key: "odds_drift", label: "Odds Drift", bgClass: "bg-emerald-500", active: driftVer !== "off", verLabel: driftVer !== "off" ? DRIFT_CARTERA_VERSIONS.find(v => v.key === driftVer)!.label : "" },
    { key: "goal_clustering", label: "Goal Clustering", bgClass: "bg-rose-500", active: clusteringVer !== "off", verLabel: clusteringVer !== "off" ? CLUSTERING_CARTERA_VERSIONS.find(v => v.key === clusteringVer)!.label : "" },
    { key: "pressure_cooker", label: "Pressure Cooker", bgClass: "bg-orange-500", active: pressureVer !== "off", verLabel: pressureVer !== "off" ? PRESSURE_CARTERA_VERSIONS.find(v => v.key === pressureVer)!.label : "" },
  ]

  const stratStats = stratConfigs.filter(s => s.active).map(s => {
    const sBets = filteredBets.filter(b => b.strategy === s.key)
    const wins = sBets.filter(b => b.won).length
    const pl = round2(sBets.reduce((sum, b) => sum + b.pl, 0))
    const staked = sBets.length * 10
    return {
      ...s,
      bets: sBets.length,
      wins,
      winPct: sBets.length > 0 ? round2(wins / sBets.length * 100) : 0,
      pl,
      roi: staked > 0 ? round2(pl / staked * 100) : 0,
    }
  })

  // Chart data with running peak for drawdown visualization
  const chartData: { idx: number; flat: number; managed: number; managedPeak: number }[] = []
  let runPeak = -Infinity
  for (let i = 0; i < filteredBets.length; i++) {
    const managed = sim.managedCumulative[i] ?? 0
    if (managed > runPeak) runPeak = managed
    chartData.push({
      idx: i + 1,
      flat: sim.flatCumulative[i] ?? 0,
      managed,
      managedPeak: runPeak,
    })
  }

  const activeLabels = stratConfigs.filter(s => s.active).map(s => `${s.label} (${s.verLabel})`)
  const selLabel = activeLabels.length === 5 ? "Todas las estrategias" : activeLabels.length >= 3 ? `${activeLabels.length} estrategias` : activeLabels.length === 2 ? "2 estrategias" : activeLabels[0] || "Ninguna"

  return (
    <div className="space-y-6">
      {/* Strategy Selector */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-zinc-200">Cartera de Estrategias</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Elige estrategias, versiones y modo de gestion de bankroll.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-[10px] text-zinc-600 font-mono">
              {filteredBets.length} apuestas filtradas / {bets.length} totales
            </span>
            <button
              type="button"
              onClick={handleDownloadCSV}
              className="px-3 py-1.5 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 text-purple-400 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5"
              title="Descargar CSV completo con todas las apuestas filtradas"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Descargar CSV
            </button>
          </div>
        </div>
        {/* Optimization Presets */}
        <div className="mb-4">
          <div className="flex flex-wrap gap-2 mb-2">
            {PRESETS.map(p => (
              <button
                key={p.key}
                type="button"
                onClick={() => applyPreset(p.key)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all ${
                  activePreset === p.key
                    ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm shadow-indigo-500/10"
                    : "bg-zinc-800/50 text-zinc-500 border border-zinc-700/50 hover:text-zinc-300 hover:border-zinc-600"
                }`}
                title={p.desc}
              >
                <span className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold ${
                  activePreset === p.key ? "bg-indigo-500/30 text-indigo-300" : "bg-zinc-700/50 text-zinc-500"
                }`}>{p.icon}</span>
                {p.label}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-0.5">
            {PRESETS.map(p => (
              <div key={p.key} className={`text-[10px] leading-4 ${activePreset === p.key ? "text-indigo-400" : "text-zinc-600"}`}>
                <span className="font-medium">{p.label} ({p.icon})</span> — {p.desc}
              </div>
            ))}
          </div>
        </div>
        <div className="space-y-3">
          {/* Back Empate versions */}
          <div>
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Back Empate</span>
              <div className="flex gap-1.5 flex-wrap">
                {DRAW_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setDrawVer(v.key === drawVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                      drawVer === v.key
                        ? v.key === "off"
                          ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600"
                          : "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </div>
            {drawVer !== "off" && (
              <div className="ml-[140px] mt-1.5 text-[10px] text-cyan-400/70">
                {drawVer === "v1" && "→ Trigger: 0-0 al min 30+"}
                {drawVer === "v15" && "→ Trigger: 0-0 min 30+ | Filtros: xG combinado <0.6 + Posesion Dominante <25%"}
                {drawVer === "v2r" && "→ Trigger: 0-0 min 30+ | Filtros: xG <0.6 + PD <20% + Tiros <8"}
                {drawVer === "v2" && "→ Trigger: 0-0 min 30+ | Filtros: xG <0.5 + PD <20% + Tiros <8"}
              </div>
            )}
          </div>
          {/* xG Underperformance versions */}
          <div>
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">xG Underperf</span>
              <div className="flex gap-1.5 flex-wrap">
                {XG_CARTERA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setXgVer(v.key === xgVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                      xgVer === v.key
                        ? v.key === "off"
                          ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600"
                          : "bg-amber-500/20 text-amber-400 border border-amber-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </div>
            {xgVer !== "off" && (
              <div className="ml-[140px] mt-1.5 text-[10px] text-amber-400/70">
                {xgVer === "base" && "→ Trigger: Equipo PERDIENDO + xG_equipo - goles_equipo >= 0.5 (min 15+) | Apuesta: Back Over (total+0.5)"}
                {xgVer === "v2" && "→ Trigger: Equipo PERDIENDO + xG_equipo - goles_equipo >= 0.5 (min 15+) | Filtro: Tiros a puerta >= 2 | Apuesta: Back Over (total+0.5)"}
              </div>
            )}
          </div>
          {/* Odds Drift versions */}
          <div>
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Odds Drift</span>
              <div className="flex gap-1.5 flex-wrap">
                {DRIFT_CARTERA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setDriftVer(v.key === driftVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                      driftVer === v.key
                        ? v.key === "off"
                          ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600"
                          : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </div>
            {driftVer !== "off" && (
              <div className="ml-[140px] mt-1.5 text-[10px] text-emerald-400/70">
                {driftVer === "v1" && "→ Trigger: Equipo ganando 1-0 + drift odds >= 25% | Apuesta: Back equipo (mantiene ventaja)"}
                {driftVer === "v2" && "→ Trigger: V1 + Total goles al trigger >= 2 | Apuesta: Back equipo"}
                {driftVer === "v3" && "→ Trigger: V1 + Drift >= 100% | Apuesta: Back equipo"}
                {driftVer === "v4" && "→ Trigger: V1 + Minuto >= 45 (2a parte) | Apuesta: Back equipo"}
              </div>
            )}
          </div>
          {/* Goal Clustering versions */}
          <div>
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Goal Clustering</span>
              <div className="flex gap-1.5 flex-wrap">
                {CLUSTERING_CARTERA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setClusteringVer(v.key === clusteringVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                      clusteringVer === v.key
                        ? v.key === "off"
                          ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600"
                          : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </div>
            {clusteringVer !== "off" && (
              <div className="ml-[140px] mt-1.5 text-[10px] text-rose-400/70">
                {clusteringVer === "v2" && "→ Trigger: Gol reciente (min 15-80) + SoT max >= 3 | Apuesta: Back Over (total+0.5)"}
              </div>
            )}
          </div>
          {/* Pressure Cooker versions */}
          <div>
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-orange-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Pressure Cooker</span>
              <div className="flex gap-1.5 flex-wrap">
                {PRESSURE_CARTERA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setPressureVer(v.key === pressureVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                      pressureVer === v.key
                        ? v.key === "off"
                          ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600"
                          : "bg-orange-500/20 text-orange-400 border border-orange-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </div>
            {pressureVer !== "off" && (
              <div className="ml-[140px] mt-1.5 text-[10px] text-orange-400/70">
                {pressureVer === "v1" && "→ Trigger: Empate 1-1+ entre min 65-75 | Apuesta: Back Over (total+0.5)"}
              </div>
            )}
          </div>
          {/* Bankroll mode */}
          <div className="pt-2 mt-2 border-t border-zinc-800/50">
            <div className="flex items-center gap-3">
              <span className="w-2.5 h-2.5 rounded-full bg-purple-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Gestion</span>
              <div className="flex gap-1.5 flex-wrap">
                {BANKROLL_MODES.map(m => (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => { setBrMode(m.key); setActivePreset(null) }}
                    className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all ${
                      brMode === m.key
                        ? "bg-purple-500/20 text-purple-400 border border-purple-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={m.desc}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <MetricCard
          title="Apuestas"
          value={`${sim.total}`}
          description={`${sim.winPct}% WR (${sim.wins}/${sim.total})`}
        />
        <MetricCard
          title="P/L Flat"
          value={`${sim.flatPl >= 0 ? "+" : ""}${sim.flatPl.toFixed(2)} EUR`}
          description={`ROI: ${sim.flatRoi >= 0 ? "+" : ""}${sim.flatRoi.toFixed(1)}% (10 EUR/apuesta)`}
        />
        <MetricCard
          title="P/L Gestion"
          value={`${sim.managedPl >= 0 ? "+" : ""}${sim.managedPl.toFixed(2)} EUR`}
          description={`ROI: ${sim.managedRoi >= 0 ? "+" : ""}${sim.managedRoi.toFixed(1)}% | ${BANKROLL_MODES.find(m => m.key === brMode)!.label} | ${sim.managedFinalBankroll.toFixed(0)}/${managed.initial_bankroll} EUR`}
        />
      </div>

      {/* Risk metrics */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-zinc-300 mb-4">Riesgo</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Max Drawdown Flat */}
          <div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Max Drawdown Flat</div>
            <div className={`text-xl font-bold ${sim.flatMaxDd.maxDd > 0 ? "text-red-400" : "text-zinc-100"}`}>
              {sim.flatMaxDd.maxDd > 0 ? `-${sim.flatMaxDd.maxDd.toFixed(2)} EUR` : "0.00 EUR"}
            </div>
            {sim.flatMaxDd.maxDd > 0 && (
              <div className="text-[11px] text-zinc-500 mt-1 space-y-0.5">
                <div>De +{sim.flatMaxDd.peak.toFixed(0)} cayo a +{sim.flatMaxDd.trough.toFixed(0)} ({sim.flatMaxDd.ddPct.toFixed(0)}% devuelto)</div>
                <div>Apuestas #{sim.flatMaxDd.peakIdx + 1} a #{sim.flatMaxDd.troughIdx + 1}</div>
              </div>
            )}
          </div>
          {/* Max Drawdown Managed */}
          <div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Max Drawdown Gestion</div>
            <div className={`text-xl font-bold ${sim.managedMaxDd.maxDd > 0 ? "text-red-400" : "text-zinc-100"}`}>
              {sim.managedMaxDd.maxDd > 0 ? `-${sim.managedMaxDd.maxDd.toFixed(2)} EUR` : "0.00 EUR"}
            </div>
            {sim.managedMaxDd.maxDd > 0 && (
              <div className="text-[11px] text-zinc-500 mt-1 space-y-0.5">
                <div>Bankroll de {round2(managed.initial_bankroll + sim.managedMaxDd.peak)} cayo a {round2(managed.initial_bankroll + sim.managedMaxDd.trough)} EUR</div>
                <div>Apuestas #{sim.managedMaxDd.peakIdx + 1} a #{sim.managedMaxDd.troughIdx + 1} | Nunca bajo de {managed.initial_bankroll} EUR</div>
              </div>
            )}
          </div>
          {/* Worst streak */}
          <div>
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1">Peor racha perdedora</div>
            <div className={`text-xl font-bold ${sim.worstStreak.losses > 0 ? "text-red-400" : "text-zinc-100"}`}>
              {sim.worstStreak.losses} fallos seguidos
            </div>
            {sim.worstStreak.losses > 0 && (
              <div className="text-[11px] text-zinc-500 mt-1 space-y-0.5">
                <div>Apuestas #{sim.worstStreak.from} a #{sim.worstStreak.to}</div>
                <div>Impacto flat: {sim.worstStreak.plLost.toFixed(2)} EUR</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Cumulative P/L Chart */}
      {chartData.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">P/L Acumulado - {selLabel}</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Flat (10 EUR) vs {BANKROLL_MODES.find(m => m.key === brMode)!.label} ({managed.initial_bankroll} EUR bankroll).
          </p>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="idx"
                tick={{ fill: "#71717a", fontSize: 11 }}
                axisLine={{ stroke: "#27272a" }}
                label={{ value: "Apuesta #", position: "insideBottom", offset: -2, fill: "#52525b", fontSize: 10 }}
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
                formatter={(value: number, name: string) => {
                  if (name === "managedPeak") return [`${value.toFixed(2)} EUR`, "Pico gestion"]
                  if (name === "flat") return [`${value.toFixed(2)} EUR`, "Flat (10 EUR)"]
                  if (name === "managed") {
                    const point = chartData.find(d => Math.abs(d.managed - value) < 0.01)
                    const dd = point ? round2(point.managedPeak - point.managed) : 0
                    const modeLabel = BANKROLL_MODES.find(m => m.key === brMode)!.label
                    return [`${value.toFixed(2)} EUR${dd > 0.01 ? ` (DD: -${dd.toFixed(2)})` : ""}`, modeLabel]
                  }
                  return [`${value.toFixed(2)} EUR`, name]
                }}
                labelFormatter={(label) => `Apuesta #${label}`}
              />
              <Legend
                verticalAlign="top"
                height={28}
                formatter={(value) => {
                  if (value === "flat") return "Flat (10 EUR)"
                  if (value === "managed") return BANKROLL_MODES.find(m => m.key === brMode)!.label
                  if (value === "managedPeak") return "Pico gestion (DD)"
                  return value
                }}
                wrapperStyle={{ fontSize: 11 }}
              />
              <ReferenceLine y={0} stroke="#52525b" strokeDasharray="3 3" />
              {/* Max drawdown zone: shaded rectangle between peak and trough bets */}
              {sim.managedMaxDd.maxDd > 0 && (
                <ReferenceArea
                  x1={sim.managedMaxDd.peakIdx + 1}
                  x2={sim.managedMaxDd.troughIdx + 1}
                  y1={sim.managedMaxDd.peak}
                  y2={sim.managedMaxDd.trough}
                  fill="#ef4444"
                  fillOpacity={0.12}
                  stroke="#ef4444"
                  strokeOpacity={0.3}
                  strokeDasharray="4 4"
                  label={{ value: `Max DD: -${sim.managedMaxDd.maxDd.toFixed(0)}`, position: "insideTop", fill: "#ef4444", fontSize: 10, opacity: 0.7 }}
                />
              )}
              <Line type="monotone" dataKey="flat" stroke="#3b82f6" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="managed" stroke="#a855f7" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="managedPeak" stroke="#ef4444" strokeWidth={1} dot={false} strokeDasharray="4 4" strokeOpacity={0.4} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Strategy Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {stratStats.map(s => (
          <div key={s.key} className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className={`w-2.5 h-2.5 rounded-full ${s.bgClass}`} />
              <span className="text-sm font-medium text-zinc-200">{s.label}</span>
              <span className="text-[10px] text-zinc-500 font-mono">{s.verLabel}</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-lg font-bold text-zinc-100">{s.bets}</div>
                <div className="text-[10px] text-zinc-500">Apuestas</div>
              </div>
              <div>
                <div className="text-lg font-bold text-zinc-100">{s.winPct}%</div>
                <div className="text-[10px] text-zinc-500">Win Rate</div>
              </div>
              <div>
                <div className={`text-lg font-bold ${s.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {s.pl >= 0 ? "+" : ""}{s.pl}
                </div>
                <div className="text-[10px] text-zinc-500">P/L (ROI: {s.roi}%)</div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Combined Bets Table */}
      {filteredBets.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Historial de apuestas (cronologico)</h2>
          <p className="text-xs text-zinc-500 mb-4">
            {selLabel} | {BANKROLL_MODES.find(m => m.key === brMode)!.label} - ordenadas por fecha.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-center py-2 px-1.5 text-xs font-medium text-zinc-500">#</th>
                  <th className="text-left py-2 px-1.5 text-xs font-medium text-zinc-500">Fecha</th>
                  <th className="text-left py-2 px-1.5 text-xs font-medium text-zinc-500">Estrategia</th>
                  <th className="text-left py-2 px-1.5 text-xs font-medium text-zinc-500">Partido</th>
                  <th className="text-right py-2 px-1.5 text-xs font-medium text-zinc-500">Min</th>
                  <th className="text-right py-2 px-1.5 text-xs font-medium text-zinc-500">Odds</th>
                  <th className="text-center py-2 px-1.5 text-xs font-medium text-zinc-500">FT</th>
                  <th className="text-right py-2 px-1.5 text-xs font-medium text-zinc-500">P/L Flat</th>
                  <th className="text-right py-2 px-1.5 text-xs font-medium text-zinc-500">Acum. Flat</th>
                  <th className="text-right py-2 px-1.5 text-xs font-medium text-zinc-500">Stake</th>
                  <th className="text-right py-2 px-1.5 text-xs font-medium text-zinc-500">P/L Gestion</th>
                  <th className="text-right py-2 px-1.5 text-xs font-medium text-zinc-500">Acum. Gestion</th>
                  <th className="text-right py-2 px-1.5 text-xs font-medium text-zinc-500">Bankroll</th>
                </tr>
              </thead>
              <tbody>
                {filteredBets.map((b, i) => {
                  const det = sim.betDetails[i]
                  const odds = getBetOdds(b)
                  return (
                    <tr
                      key={`${b.match_id}-${b.strategy}-${i}`}
                      className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                    >
                      <td className="py-2 px-1.5 text-center text-xs text-zinc-600">{i + 1}</td>
                      <td className="py-2 px-1.5 text-xs text-zinc-500 whitespace-nowrap">
                        {b.timestamp_utc ? (() => {
                          const d = new Date(b.timestamp_utc)
                          return isNaN(d.getTime()) ? "-" : `${d.getDate().toString().padStart(2, "0")}/${(d.getMonth() + 1).toString().padStart(2, "0")} ${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`
                        })() : "-"}
                      </td>
                      <td className="py-2 px-1.5 text-xs">
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          b.strategy === "back_draw_00"
                            ? "bg-cyan-500/15 text-cyan-400"
                            : b.strategy === "odds_drift"
                            ? "bg-emerald-500/15 text-emerald-400"
                            : b.strategy === "goal_clustering"
                            ? "bg-rose-500/15 text-rose-400"
                            : b.strategy === "pressure_cooker"
                            ? "bg-orange-500/15 text-orange-400"
                            : "bg-amber-500/15 text-amber-400"
                        }`}>
                          {b.strategy_label}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-zinc-300 text-xs max-w-[160px] truncate" title={b.match}>{b.match}</td>
                      <td className="py-2 px-1.5 text-right text-zinc-400 text-xs">{b.minuto ?? "-"}</td>
                      <td className="py-2 px-1.5 text-right text-zinc-400 text-xs">{odds.toFixed(2)}</td>
                      <td className="py-2 px-1.5 text-center text-xs">
                        <span className={b.won ? "text-green-400" : "text-red-400"}>{b.ft_score}</span>
                      </td>
                      <td className="py-2 px-1.5 text-right text-xs font-medium">
                        <span className={b.pl >= 0 ? "text-green-400" : "text-red-400"}>
                          {b.pl >= 0 ? "+" : ""}{b.pl.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-right text-xs font-mono">
                        <span className={(sim.flatCumulative[i] ?? 0) >= 0 ? "text-blue-400" : "text-red-400"}>
                          {(sim.flatCumulative[i] ?? 0) >= 0 ? "+" : ""}{(sim.flatCumulative[i] ?? 0).toFixed(2)}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-right text-xs text-purple-400">{det?.stake.toFixed(2) ?? "-"}</td>
                      <td className="py-2 px-1.5 text-right text-xs font-medium">
                        <span className={(det?.plManaged ?? 0) >= 0 ? "text-green-400" : "text-red-400"}>
                          {det ? `${det.plManaged >= 0 ? "+" : ""}${det.plManaged.toFixed(2)}` : "-"}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-right text-xs font-mono">
                        <span className={(sim.managedCumulative[i] ?? 0) >= 0 ? "text-purple-400" : "text-red-400"}>
                          {(sim.managedCumulative[i] ?? 0) >= 0 ? "+" : ""}{(sim.managedCumulative[i] ?? 0).toFixed(2)}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-right text-xs text-purple-300 font-mono">{det?.bankrollAfter.toFixed(0) ?? "-"}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {filteredBets.length === 0 && (
        <div className="text-center py-12 text-zinc-500 text-sm">
          No hay apuestas en la cartera.
        </div>
      )}
    </div>
  )
}

function PressureCookerTab({ data }: { data: StrategyPressureCooker }) {
  const { summary, bets, total_matches, draws_65_75 } = data

  const sortedBets = [...bets].sort((a, b) => (a.timestamp_utc || "").localeCompare(b.timestamp_utc || ""))
  const cumulativeBets = sortedBets.map((bet, idx) => ({
    idx: idx + 1,
    pl: sortedBets.slice(0, idx + 1).reduce((sum, b) => sum + b.pl, 0),
  }))

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="bg-gradient-to-br from-orange-500/10 to-amber-500/10 border border-orange-500/30 rounded-2xl p-6">
        <h2 className="text-xl font-bold text-orange-400 mb-3">Pressure Cooker V1</h2>
        <p className="text-zinc-400 text-sm">
          Back Over (score+0.5) en empates con goles (1-1, 2-2...) entre min 65-75. Excluye 0-0.
        </p>
        <p className="text-zinc-500 text-xs mt-2">
          Estado: EN PRUEBA - Muestra insuficiente, acumulando datos para validacion.
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-5 gap-3">
        <MetricCard title="Partidos" value={total_matches} description="Partidos analizados" />
        <MetricCard title="Empates 65-75" value={draws_65_75} description="Candidatos detectados" />
        <MetricCard
          title="Win Rate"
          value={`${summary.win_rate}%`}
          description={`${summary.wins}/${summary.total_bets} apuestas ganadas`}
        />
        <MetricCard title="P/L Total" value={`${summary.total_pl >= 0 ? "+" : ""}${summary.total_pl.toFixed(2)}`} description="Stake 10 EUR" />
        <MetricCard title="ROI" value={`${summary.roi >= 0 ? "+" : ""}${summary.roi}%`} description="Retorno sobre inversion" />
      </div>

      {/* Chart */}
      {cumulativeBets.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-zinc-300 mb-4">P/L Acumulado</h3>
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={cumulativeBets}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
              <XAxis dataKey="idx" stroke="#71717a" tick={{ fontSize: 11 }} />
              <YAxis stroke="#71717a" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #3f3f46",
                  borderRadius: "8px",
                  fontSize: "11px",
                }}
              />
              <Bar dataKey="pl" fill="#f97316" opacity={0.6} />
              <Line type="monotone" dataKey="pl" stroke="#fb923c" strokeWidth={2} dot={false} />
              <ReferenceLine y={0} stroke="#71717a" strokeDasharray="3 3" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Bets Table */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-zinc-800">
          <h3 className="text-sm font-semibold text-zinc-300">
            Detalle de Apuestas ({bets.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-zinc-900/80 text-zinc-500 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 text-left">#</th>
                <th className="px-4 py-3 text-left">Partido</th>
                <th className="px-4 py-3 text-center">Min</th>
                <th className="px-4 py-3 text-center">Score</th>
                <th className="px-4 py-3 text-center">Over Odds</th>
                <th className="px-4 py-3 text-center">Over Line</th>
                <th className="px-4 py-3 text-center">SoT Δ10</th>
                <th className="px-4 py-3 text-center">Shots Δ10</th>
                <th className="px-4 py-3 text-center">FT</th>
                <th className="px-4 py-3 text-center">P/L</th>
                <th className="px-4 py-3 text-center">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {sortedBets.map((b, i) => (
                <tr key={i} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="px-4 py-2 text-zinc-500">{i + 1}</td>
                  <td className="px-4 py-2 text-zinc-300 truncate max-w-[180px]">{b.match}</td>
                  <td className="px-4 py-2 text-center text-zinc-400">{b.minuto}'</td>
                  <td className="px-4 py-2 text-center text-zinc-300 font-medium">{b.score}</td>
                  <td className="px-4 py-2 text-center text-orange-400 font-medium">{b.back_over_odds?.toFixed(2) ?? "-"}</td>
                  <td className="px-4 py-2 text-center text-zinc-400">{b.over_line}</td>
                  <td className="px-4 py-2 text-center text-zinc-400">{b.sot_delta}</td>
                  <td className="px-4 py-2 text-center text-zinc-400">{b.shots_delta}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={b.won ? "text-green-400" : "text-red-400"}>{b.ft_score}</span>
                  </td>
                  <td className={`px-4 py-2 text-center font-medium ${b.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                    {b.pl >= 0 ? "+" : ""}{b.pl.toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${b.won ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
                      {b.won ? "W" : "L"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function GoalClusteringTab({ data }: { data: StrategyGoalClustering }) {
  const { summary, bets, total_matches, total_goal_events } = data

  // Calcular P/L acumulado para el chart
  const cumulativeBets = bets
    .sort((a, b) => (a.timestamp_utc || "").localeCompare(b.timestamp_utc || ""))
    .map((bet, idx) => ({
      idx: idx + 1,
      pl: bets.slice(0, idx + 1).reduce((sum, b) => sum + b.pl, 0),
    }))

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="bg-gradient-to-br from-rose-500/10 to-pink-500/10 border border-rose-500/30 rounded-2xl p-6">
        <h2 className="text-xl font-bold text-rose-400 mb-3">Goal Clustering V2</h2>
        <p className="text-zinc-400 text-sm">
          Apostar a Over (total+0.5) inmediatamente después de un gol cuando hay intensidad de juego (SoT max ≥ 3)
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard title="Triggers" value={total_goal_events} description="Eventos de gol detectados" />
        <MetricCard
          title="Win Rate"
          value={`${summary.win_rate}%`}
          description={`${summary.wins}/${summary.total_bets} apuestas ganadas`}
        />
        <MetricCard title="P/L Total" value={`€${summary.total_pl.toFixed(2)}`} description="Beneficio total (stake 10 EUR)" />
        <MetricCard title="ROI" value={`${summary.roi}%`} description="Retorno sobre inversión" />
      </div>

      {/* Chart */}
      {cumulativeBets.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-zinc-300 mb-4">P/L Acumulado</h3>
          <ResponsiveContainer width="100%" height={250}>
            <ComposedChart data={cumulativeBets}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
              <XAxis dataKey="idx" stroke="#71717a" tick={{ fontSize: 11 }} />
              <YAxis stroke="#71717a" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #3f3f46",
                  borderRadius: "8px",
                  fontSize: "11px",
                }}
              />
              <Bar dataKey="pl" fill="#f43f5e" opacity={0.6} />
              <Line type="monotone" dataKey="pl" stroke="#fb7185" strokeWidth={2} dot={false} />
              <ReferenceLine y={0} stroke="#71717a" strokeDasharray="3 3" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Bets Table */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-zinc-800">
          <h3 className="text-sm font-semibold text-zinc-300">
            Detalle de Apuestas ({bets.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-zinc-900/80 text-zinc-500 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-3 text-left">#</th>
                <th className="px-4 py-3 text-left">Partido</th>
                <th className="px-4 py-3 text-center">Min</th>
                <th className="px-4 py-3 text-center">Score</th>
                <th className="px-4 py-3 text-center">SoT Max</th>
                <th className="px-4 py-3 text-center">Over Odds</th>
                <th className="px-4 py-3 text-center">FT</th>
                <th className="px-4 py-3 text-center">P/L</th>
                <th className="px-4 py-3 text-center">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {bets.map((bet, i) => (
                <tr
                  key={i}
                  className={`hover:bg-zinc-800/30 transition-colors ${
                    bet.won ? "bg-emerald-500/5" : "bg-red-500/5"
                  }`}
                >
                  <td className="px-4 py-3 text-zinc-500">{i + 1}</td>
                  <td className="px-4 py-3 text-zinc-300">{bet.match}</td>
                  <td className="px-4 py-3 text-center text-zinc-400">{bet.minuto}</td>
                  <td className="px-4 py-3 text-center font-mono text-zinc-300">{bet.score}</td>
                  <td className="px-4 py-3 text-center text-rose-400">{bet.sot_max}</td>
                  <td className="px-4 py-3 text-center font-mono text-zinc-300">
                    {bet.over_odds?.toFixed(2) || "N/A"}
                  </td>
                  <td className="px-4 py-3 text-center font-mono text-zinc-400">{bet.ft_score}</td>
                  <td
                    className={`px-4 py-3 text-center font-mono font-semibold ${
                      bet.pl > 0 ? "text-emerald-400" : bet.pl < 0 ? "text-red-400" : "text-zinc-500"
                    }`}
                  >
                    {bet.pl > 0 ? "+" : ""}
                    {bet.pl.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {bet.won ? (
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                        WIN
                      </span>
                    ) : (
                      <span className="inline-block px-2 py-0.5 rounded text-[10px] font-medium bg-red-500/20 text-red-400 border border-red-500/30">
                        LOSS
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
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
