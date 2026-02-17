import { useState, useEffect } from "react"
import { api, type PlacedBetsResponse, type PlacedBet } from "../lib/api"

export function PlacedBetsView() {
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
    const id = setInterval(fetch, 15000)
    return () => clearInterval(id)
  }, [])

  if (loading) {
    return <div className="p-6 text-zinc-400">Cargando apuestas...</div>
  }

  const bets = data?.bets ?? []
  const pending = bets.filter((b) => b.status === "pending")

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Mis Apuestas</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Seguimiento de apuestas registradas desde Senales
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Total" value={data?.total ?? 0} />
        <StatCard label="Pendientes" value={data?.pending ?? 0} color="text-amber-400" />
        <StatCard label="Ganadas" value={data?.won ?? 0} color="text-green-400" />
        <StatCard label="Perdidas" value={data?.lost ?? 0} color="text-red-400" />
        <StatCard
          label="P/L Total"
          value={`${(data?.total_pl ?? 0) >= 0 ? "+" : ""}${(data?.total_pl ?? 0).toFixed(2)}`}
          color={(data?.total_pl ?? 0) >= 0 ? "text-green-400" : "text-red-400"}
        />
      </div>

      {/* Pending bets (live) */}
      {pending.length > 0 ? (
        <section>
          <h2 className="text-sm font-semibold text-amber-400 mb-3 uppercase tracking-wide">
            En juego ({pending.length})
          </h2>
          <div className="space-y-2">
            {pending.map((b) => (
              <PendingBetRow key={b.id} bet={b} />
            ))}
          </div>
        </section>
      ) : (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-10 text-center">
          <div className="text-zinc-500 text-sm">
            {bets.length === 0 ? (
              <>
                No hay apuestas registradas.
                <br />
                <span className="text-zinc-600">
                  Ve a <span className="text-amber-400">Senales</span> y pulsa{" "}
                  <span className="text-blue-400">Add Bet</span> en cualquier senal para empezar.
                </span>
              </>
            ) : (
              <>
                No hay apuestas en juego.
                <br />
                <span className="text-zinc-600">
                  Ve a <span className="text-blue-400">Analytics</span> para ver el historial completo.
                </span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-3">
      <div className="text-[10px] text-zinc-500 uppercase tracking-wide">{label}</div>
      <div className={`text-xl font-bold mt-1 ${color ?? "text-zinc-100"}`}>{value}</div>
    </div>
  )
}

function PendingBetRow({ bet }: { bet: PlacedBet }) {
  const favorable = bet.would_win_now === true
  const borderColor = favorable ? "border-green-500/30" : "border-red-500/30"
  const bgColor = favorable ? "bg-green-900/10" : "bg-red-900/10"

  const odds = Number(bet.back_odds) || 0

  return (
    <div className={`border rounded-lg p-4 ${borderColor} ${bgColor}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <a
              href={bet.match_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-zinc-100 hover:text-blue-400 transition-colors truncate"
            >
              {bet.match_name}
            </a>
            <TypeBadge type={bet.bet_type} />
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-400">
            <span>{bet.strategy_name}</span>
            <span className="text-zinc-600">|</span>
            <span>{bet.recommendation}</span>
            <span className="text-zinc-600">|</span>
            <span>Stake: {Number(bet.stake).toFixed(0)} EUR @ {odds.toFixed(2)}</span>
          </div>
        </div>

        <div className="flex items-center gap-4 shrink-0 ml-4">
          {/* Live score */}
          <div className="text-center">
            <div className="text-[10px] text-zinc-500">Score actual</div>
            <div className="text-lg font-bold text-zinc-100 font-mono">
              {bet.live_score ?? bet.score}
            </div>
            {bet.live_minute != null && (
              <div className="text-[10px] text-zinc-500">Min {bet.live_minute}'</div>
            )}
          </div>

          {/* Entry score */}
          <div className="text-center">
            <div className="text-[10px] text-zinc-500">Entrada</div>
            <div className="text-sm font-mono text-zinc-400">{bet.score}</div>
            <div className="text-[10px] text-zinc-500">Min {bet.minute}'</div>
          </div>

          {/* Status */}
          <div className="text-center min-w-[80px]">
            <div className={`text-sm font-bold ${favorable ? "text-green-400" : "text-red-400"}`}>
              {favorable ? "FAVORABLE" : "EN CONTRA"}
            </div>
            <div className={`text-sm font-mono font-bold ${(bet.potential_pl ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
              {(bet.potential_pl ?? 0) >= 0 ? "+" : ""}{(bet.potential_pl ?? 0).toFixed(2)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function TypeBadge({ type }: { type: string }) {
  const isPaper = type === "paper"
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
      isPaper
        ? "bg-blue-500/15 text-blue-400"
        : "bg-green-500/15 text-green-400"
    }`}>
      {isPaper ? "PAPER" : "REAL"}
    </span>
  )
}
