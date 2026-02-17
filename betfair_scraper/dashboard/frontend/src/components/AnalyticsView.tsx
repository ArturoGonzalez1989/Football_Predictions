import { useState, useEffect } from "react"
import { api, type PlacedBetsResponse, type PlacedBet } from "../lib/api"

export function AnalyticsView() {
  const [data, setData] = useState<PlacedBetsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetch = async () => {
      try {
        setData(await api.getPlacedBets())
      } catch {
        /* silently ignore */
      } finally {
        setLoading(false)
      }
    }
    fetch()
    const id = setInterval(fetch, 30000)
    return () => clearInterval(id)
  }, [])

  if (loading) {
    return <div className="p-6 text-zinc-400">Cargando analytics...</div>
  }

  const bets = data?.bets ?? []
  const resolvedBets = bets.filter((b) => b.status !== "pending")

  // Sort chronologically (oldest first)
  const sortedBets = [...resolvedBets].sort((a, b) => {
    const timeA = new Date(a.timestamp_utc || 0).getTime()
    const timeB = new Date(b.timestamp_utc || 0).getTime()
    return timeA - timeB
  })

  // Calculate metrics
  const stats = calculateStats(sortedBets)
  const strategyPerf = calculateStrategyPerformance(sortedBets)
  const marketPerf = calculateMarketPerformance(sortedBets)
  const riskMetrics = calculateRiskMetrics(sortedBets)
  const plHistory = calculatePLHistory(sortedBets)

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Analytics Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Análisis detallado de rendimiento y métricas de riesgo
        </p>
      </div>

      {/* P/L Chart */}
      <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wide">
          📈 P/L Acumulado
        </h2>
        <PLChart data={plHistory} />
      </section>

      {/* Strategy & Market Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Strategy Performance */}
        <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wide">
            🎯 Rendimiento por Estrategia
          </h2>
          <div className="space-y-2">
            {strategyPerf.map((strat) => (
              <StrategyCard key={strat.name} {...strat} />
            ))}
          </div>
        </section>

        {/* Market Performance */}
        <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wide">
            📊 Rendimiento por Mercado
          </h2>
          <div className="space-y-2">
            {marketPerf.map((market) => (
              <MarketCard key={market.name} {...market} />
            ))}
          </div>
        </section>
      </div>

      {/* Risk Metrics */}
      <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wide">
          ⚠️ Control de Riesgo
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <RiskMetric
            label="Racha Actual"
            value={riskMetrics.currentStreak}
            color={riskMetrics.currentStreakType === "win" ? "green" : "red"}
          />
          <RiskMetric
            label="Max Drawdown"
            value={`${riskMetrics.maxDrawdown.toFixed(2)} EUR`}
            color="red"
          />
          <RiskMetric
            label="Profit Factor"
            value={riskMetrics.profitFactor.toFixed(2)}
            color={riskMetrics.profitFactor > 2 ? "green" : riskMetrics.profitFactor > 1 ? "amber" : "red"}
          />
          <RiskMetric
            label="Sharpe Ratio"
            value={riskMetrics.sharpeRatio.toFixed(2)}
            color={riskMetrics.sharpeRatio > 1.5 ? "green" : riskMetrics.sharpeRatio > 0.5 ? "amber" : "red"}
          />
        </div>

        {/* Streaks */}
        <div className="mt-4 grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-zinc-500 mb-1">Racha más larga (Victorias)</div>
            <div className="text-lg font-bold text-green-400">
              {riskMetrics.longestWinStreak} bets
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500 mb-1">Racha más larga (Derrotas)</div>
            <div className="text-lg font-bold text-red-400">
              {riskMetrics.longestLossStreak} bets
            </div>
          </div>
        </div>
      </section>

      {/* Recent Form */}
      <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wide">
          🕐 Forma Reciente (Últimas 10 apuestas)
        </h2>
        <RecentForm bets={sortedBets.slice(-10)} />
      </section>

      {/* Historial Table */}
      <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wide">
          📋 Historial ({sortedBets.length})
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-zinc-500 border-b border-zinc-800">
                <th className="text-left py-2 px-2">Partido</th>
                <th className="text-left py-2 px-2">Estrategia</th>
                <th className="text-left py-2 px-2">Apuesta</th>
                <th className="text-center py-2 px-2">Tipo</th>
                <th className="text-right py-2 px-2">Stake</th>
                <th className="text-right py-2 px-2">Odds</th>
                <th className="text-center py-2 px-2">Resultado</th>
                <th className="text-right py-2 px-2">P/L</th>
              </tr>
            </thead>
            <tbody>
              {[...sortedBets].reverse().map((bet) => (
                <HistorialRow key={bet.id} bet={bet} />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Summary Stats */}
      <section className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wide">
          📋 Estadísticas Generales
        </h2>
        <div className="space-y-4">
          {/* Rendimiento */}
          <div>
            <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Rendimiento</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatItem label="ROI Global" value={`${stats.roi.toFixed(1)}%`} />
              <StatItem label="Win Rate" value={`${stats.winRate.toFixed(1)}%`} />
              <StatItem label="P/L Total" value={`${stats.totalPL >= 0 ? "+" : ""}${stats.totalPL.toFixed(2)} EUR`} />
              <StatItem label="Ganancia por € Apostado" value={`€${stats.profitPerEuro.toFixed(3)}`} />
            </div>
          </div>

          {/* Volumen */}
          <div>
            <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Volumen</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatItem label="Total de Apuestas" value={stats.totalBets.toString()} />
              <StatItem label="Stake Total" value={`${stats.totalStake.toFixed(0)} EUR`} />
              <StatItem label="Stake Promedio" value={`${stats.avgStake.toFixed(2)} EUR`} />
              <StatItem label="Cuota Promedio" value={stats.avgOdds.toFixed(2)} />
            </div>
          </div>

          {/* Extremos */}
          <div>
            <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Detalle</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatItem label="P/L Promedio" value={`${stats.avgPL >= 0 ? "+" : ""}${stats.avgPL.toFixed(2)} EUR`} />
              <StatItem label="Expectativa" value={`${stats.expectancy >= 0 ? "+" : ""}${stats.expectancy.toFixed(2)} EUR`} />
              <StatItem label="Mejor Apuesta" value={`+${stats.bestBet.toFixed(2)} EUR`} />
              <StatItem label="Peor Apuesta" value={`${stats.worstBet.toFixed(2)} EUR`} />
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}

// Utility functions
function calculateStats(bets: PlacedBet[]) {
  const totalBets = bets.length
  const totalStake = bets.reduce((sum, b) => sum + Number(b.stake), 0)
  const totalPL = bets.reduce((sum, b) => sum + (Number(b.pl) || 0), 0)
  const avgOdds = bets.reduce((sum, b) => sum + (Number(b.back_odds) || 0), 0) / Math.max(bets.length, 1)
  const avgPL = totalPL / Math.max(bets.length, 1)
  const avgStake = totalStake / Math.max(bets.length, 1)
  const roi = totalStake > 0 ? (totalPL / totalStake) * 100 : 0

  // Win Rate
  const wins = bets.filter(b => b.result === "won").length
  const winRate = totalBets > 0 ? (wins / totalBets) * 100 : 0

  // Ganancia por euro apostado
  const profitPerEuro = totalStake > 0 ? totalPL / totalStake : 0

  // Expectativa (ganancia esperada por apuesta)
  const winningBets = bets.filter(b => b.result === "won")
  const losingBets = bets.filter(b => b.result === "lost")
  const avgWin = winningBets.length > 0
    ? winningBets.reduce((sum, b) => sum + (Number(b.pl) || 0), 0) / winningBets.length
    : 0
  const avgLoss = losingBets.length > 0
    ? losingBets.reduce((sum, b) => sum + (Number(b.pl) || 0), 0) / losingBets.length
    : 0
  const expectancy = (winRate / 100) * avgWin + ((100 - winRate) / 100) * avgLoss

  // Mejor y peor apuesta
  const plValues = bets.map(b => Number(b.pl) || 0)
  const bestBet = plValues.length > 0 ? Math.max(...plValues) : 0
  const worstBet = plValues.length > 0 ? Math.min(...plValues) : 0

  return {
    totalBets,
    totalStake,
    totalPL,
    avgOdds,
    avgPL,
    avgStake,
    roi,
    winRate,
    profitPerEuro,
    expectancy,
    bestBet,
    worstBet
  }
}

function calculateStrategyPerformance(bets: PlacedBet[]) {
  const byStrategy: Record<string, PlacedBet[]> = {}

  bets.forEach((bet) => {
    const strat = bet.strategy_name || "Unknown"
    if (!byStrategy[strat]) byStrategy[strat] = []
    byStrategy[strat].push(bet)
  })

  return Object.entries(byStrategy).map(([name, stratBets]) => {
    const wins = stratBets.filter((b) => b.result === "won").length
    const total = stratBets.length
    const winRate = (wins / total) * 100
    const pl = stratBets.reduce((sum, b) => sum + (Number(b.pl) || 0), 0)
    const stake = stratBets.reduce((sum, b) => sum + Number(b.stake), 0)
    const roi = (pl / stake) * 100

    return { name, bets: total, winRate, pl, roi }
  }).sort((a, b) => b.roi - a.roi)
}

function calculateMarketPerformance(bets: PlacedBet[]) {
  const byMarket: Record<string, PlacedBet[]> = {}

  bets.forEach((bet) => {
    const market = parseBetType(bet.recommendation || "")
    if (!byMarket[market]) byMarket[market] = []
    byMarket[market].push(bet)
  })

  return Object.entries(byMarket).map(([name, marketBets]) => {
    const wins = marketBets.filter((b) => b.result === "won").length
    const total = marketBets.length
    const winRate = (wins / total) * 100
    const pl = marketBets.reduce((sum, b) => sum + (Number(b.pl) || 0), 0)

    return { name, bets: total, winRate, pl }
  }).sort((a, b) => b.pl - a.pl)
}

function calculateRiskMetrics(bets: PlacedBet[]) {
  let currentStreak = 0
  let currentStreakType: "win" | "loss" | "none" = "none"
  let longestWinStreak = 0
  let longestLossStreak = 0
  let tempWinStreak = 0
  let tempLossStreak = 0
  let maxDrawdown = 0
  let peak = 0
  let cumPL = 0

  bets.forEach((bet) => {
    const pl = Number(bet.pl) || 0
    cumPL += pl

    // Track drawdown
    if (cumPL > peak) peak = cumPL
    const drawdown = peak - cumPL
    if (drawdown > maxDrawdown) maxDrawdown = drawdown

    // Track streaks
    if (bet.result === "won") {
      tempWinStreak++
      tempLossStreak = 0
      if (tempWinStreak > longestWinStreak) longestWinStreak = tempWinStreak
    } else if (bet.result === "lost") {
      tempLossStreak++
      tempWinStreak = 0
      if (tempLossStreak > longestLossStreak) longestLossStreak = tempLossStreak
    }
  })

  // Current streak (from last bet)
  const lastBets = bets.slice(-10)
  for (let i = lastBets.length - 1; i >= 0; i--) {
    const result = lastBets[i].result
    if (i === lastBets.length - 1) {
      currentStreakType = result === "won" ? "win" : "loss"
      currentStreak = 1
    } else if ((currentStreakType === "win" && result === "won") ||
               (currentStreakType === "loss" && result === "lost")) {
      currentStreak++
    } else {
      break
    }
  }

  // Profit factor: total wins / total losses
  const totalWins = bets.filter(b => b.result === "won").reduce((sum, b) => sum + (Number(b.pl) || 0), 0)
  const totalLosses = Math.abs(bets.filter(b => b.result === "lost").reduce((sum, b) => sum + (Number(b.pl) || 0), 0))
  const profitFactor = totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? 999 : 0

  // Sharpe ratio (simplified): avg return / std dev of returns
  const returns = bets.map(b => Number(b.pl) || 0)
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length
  const stdDev = Math.sqrt(variance)
  const sharpeRatio = stdDev > 0 ? avgReturn / stdDev : 0

  return {
    currentStreak: `${currentStreakType === "win" ? "+" : "-"}${currentStreak}`,
    currentStreakType,
    longestWinStreak,
    longestLossStreak,
    maxDrawdown,
    profitFactor,
    sharpeRatio,
  }
}

function calculatePLHistory(bets: PlacedBet[]) {
  let cumPL = 0
  return bets.map((bet) => {
    cumPL += Number(bet.pl) || 0
    return {
      timestamp: bet.timestamp_utc || "",
      pl: cumPL,
    }
  })
}

function parseBetType(recommendation: string): string {
  if (!recommendation) return "Unknown"
  const rec = recommendation.toUpperCase()
  if (rec.includes("DRAW") || rec.includes("EMPATE")) return "Empate"
  if (rec.includes("OVER")) {
    const match = rec.match(/OVER\s+(\d+\.?\d*)/)
    return match ? `Over ${match[1]}` : "Over"
  }
  if (rec.includes("UNDER")) return "Under"
  if (rec.includes("HOME") || rec.includes("LOCAL")) return "Local"
  if (rec.includes("AWAY") || rec.includes("VISITANTE")) return "Visitante"
  return "Other"
}

// Components
function PLChart({ data }: { data: { timestamp: string; pl: number }[] }) {
  if (data.length === 0) {
    return <div className="text-sm text-zinc-500 text-center py-8">No hay datos suficientes</div>
  }

  const maxPL = Math.max(...data.map((d) => d.pl), 0)
  const minPL = Math.min(...data.map((d) => d.pl), 0)
  const range = maxPL - minPL || 1

  return (
    <div className="relative h-48">
      {/* Y-axis labels */}
      <div className="absolute left-0 top-0 bottom-0 w-12 flex flex-col justify-between text-[10px] text-zinc-500">
        <div>+{maxPL.toFixed(0)}</div>
        <div>0</div>
        <div>{minPL.toFixed(0)}</div>
      </div>

      {/* Chart area */}
      <div className="ml-12 h-full flex items-end gap-1">
        {data.map((point, i) => {
          const height = ((point.pl - minPL) / range) * 100
          const isPositive = point.pl >= 0

          return (
            <div
              key={i}
              className="flex-1 min-w-[2px] relative group"
              style={{ height: `${Math.max(height, 2)}%` }}
            >
              <div
                className={`w-full h-full rounded-t ${
                  isPositive ? "bg-green-500/60" : "bg-red-500/60"
                } group-hover:opacity-100 transition-opacity`}
              />
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 opacity-0 group-hover:opacity-100 bg-zinc-800 text-white text-[10px] px-2 py-1 rounded whitespace-nowrap pointer-events-none">
                {point.pl >= 0 ? "+" : ""}{point.pl.toFixed(2)} EUR
                <br />
                {point.timestamp.slice(11, 16)}
              </div>
            </div>
          )
        })}
      </div>

      {/* Zero line */}
      <div
        className="absolute left-12 right-0 border-t border-zinc-700 pointer-events-none"
        style={{ bottom: `${((0 - minPL) / range) * 100}%` }}
      />
    </div>
  )
}

function StrategyCard({ name, bets, winRate, pl, roi }: {
  name: string
  bets: number
  winRate: number
  pl: number
  roi: number
}) {
  return (
    <div className="bg-zinc-800/50 rounded p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-medium text-zinc-200">{name}</div>
        <div className="text-xs text-zinc-500">{bets} bets</div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-zinc-500">WR</div>
          <div className={`font-bold ${winRate >= 60 ? "text-green-400" : winRate >= 50 ? "text-amber-400" : "text-red-400"}`}>
            {winRate.toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-zinc-500">P/L</div>
          <div className={`font-bold ${pl >= 0 ? "text-green-400" : "text-red-400"}`}>
            {pl >= 0 ? "+" : ""}{pl.toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-zinc-500">ROI</div>
          <div className={`font-bold ${roi >= 50 ? "text-green-400" : roi >= 0 ? "text-amber-400" : "text-red-400"}`}>
            {roi.toFixed(1)}%
          </div>
        </div>
      </div>
    </div>
  )
}

function MarketCard({ name, bets, winRate, pl }: {
  name: string
  bets: number
  winRate: number
  pl: number
}) {
  return (
    <div className="bg-zinc-800/50 rounded p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-medium text-zinc-200">{name}</div>
        <div className="text-xs text-zinc-500">{bets} bets</div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-zinc-500">Win Rate</div>
          <div className={`font-bold ${winRate >= 60 ? "text-green-400" : winRate >= 50 ? "text-amber-400" : "text-red-400"}`}>
            {winRate.toFixed(1)}%
          </div>
        </div>
        <div>
          <div className="text-zinc-500">P/L</div>
          <div className={`font-bold ${pl >= 0 ? "text-green-400" : "text-red-400"}`}>
            {pl >= 0 ? "+" : ""}{pl.toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  )
}

function RiskMetric({ label, value, color }: {
  label: string
  value: string
  color: "green" | "amber" | "red" | "zinc"
}) {
  const colorClasses = {
    green: "text-green-400",
    amber: "text-amber-400",
    red: "text-red-400",
    zinc: "text-zinc-400",
  }

  return (
    <div>
      <div className="text-[10px] text-zinc-500 uppercase tracking-wide mb-1">{label}</div>
      <div className={`text-xl font-bold ${colorClasses[color]}`}>{value}</div>
    </div>
  )
}

function RecentForm({ bets }: { bets: PlacedBet[] }) {
  if (bets.length === 0) {
    return <div className="text-sm text-zinc-500">No hay apuestas recientes</div>
  }

  return (
    <div className="flex items-center gap-1">
      {bets.map((bet, i) => (
        <div
          key={i}
          className={`w-8 h-8 rounded flex items-center justify-center text-xs font-bold ${
            bet.result === "won"
              ? "bg-green-500/20 text-green-400"
              : "bg-red-500/20 text-red-400"
          }`}
          title={`${bet.match_name}: ${bet.result === "won" ? "WIN" : "LOSS"} (${bet.pl} EUR)`}
        >
          {bet.result === "won" ? "W" : "L"}
        </div>
      ))}
    </div>
  )
}

function HistorialRow({ bet }: { bet: PlacedBet }) {
  const won = bet.status === "won"
  const pl = Number(bet.pl) || 0
  const odds = Number(bet.back_odds) || 0
  const betType = parseBetType(bet.recommendation || "")

  return (
    <tr className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
      <td className="py-2 px-2">
        <a
          href={bet.match_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-zinc-200 hover:text-blue-400 transition-colors"
        >
          {bet.match_name}
        </a>
        <div className="text-[10px] text-zinc-600">{bet.timestamp_utc?.slice(0, 16)}</div>
      </td>
      <td className="py-2 px-2 text-zinc-400">{bet.strategy_name}</td>
      <td className="py-2 px-2 text-zinc-300 text-sm">{betType}</td>
      <td className="py-2 px-2 text-center">
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
          bet.bet_type === "paper" ? "bg-blue-500/15 text-blue-400" : "bg-green-500/15 text-green-400"
        }`}>
          {bet.bet_type === "paper" ? "PAPER" : "REAL"}
        </span>
      </td>
      <td className="py-2 px-2 text-right font-mono text-zinc-300">{Number(bet.stake).toFixed(0)}</td>
      <td className="py-2 px-2 text-right font-mono text-zinc-300">{odds.toFixed(2)}</td>
      <td className="py-2 px-2 text-center">
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
          won ? "bg-green-500/15 text-green-400" : "bg-red-500/15 text-red-400"
        }`}>
          {won ? "WIN" : "LOSS"}
        </span>
      </td>
      <td className={`py-2 px-2 text-right font-mono font-bold ${pl >= 0 ? "text-green-400" : "text-red-400"}`}>
        {pl >= 0 ? "+" : ""}{pl.toFixed(2)}
      </td>
    </tr>
  )
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-zinc-500 mb-1">{label}</div>
      <div className="text-lg font-bold text-zinc-100">{value}</div>
    </div>
  )
}
