import { useState, useEffect } from "react"
import { api, type PlacedBetsResponse, type PlacedBet } from "../lib/api"

function exportBetsToCSV(bets: PlacedBet[]) {
  const headers = [
    "id", "fecha_utc", "partido", "estrategia", "tipo_apuesta",
    "minuto_entrada", "score_entrada", "recomendacion",
    "cuota_entrada", "cuota_minima", "cuota_valida",
    "stake", "estado", "resultado", "pl",
    "ev_esperado", "confianza", "wr_historico", "roi_historico", "muestra",
  ]

  const rows = bets.map(b => {
    const backOdds = Number(b.back_odds) || 0
    const minOdds = Number(b.min_odds) || 0
    const oddsValid = backOdds > 0 && minOdds > 0 && backOdds >= minOdds ? "SI" : (backOdds === 0 ? "?" : "NO")
    return [
      b.id,
      b.timestamp_utc,
      `"${b.match_name}"`,
      `"${b.strategy_name}"`,
      b.bet_type,
      b.minute,
      b.score,
      `"${b.recommendation}"`,
      backOdds > 0 ? backOdds.toFixed(2) : "",
      minOdds > 0 ? minOdds.toFixed(2) : "",
      oddsValid,
      Number(b.stake).toFixed(2),
      b.status,
      b.result ?? "",
      b.pl != null ? Number(b.pl).toFixed(2) : "",
      b.expected_value != null ? Number(b.expected_value).toFixed(2) : "",
      b.confidence ?? "",
      b.win_rate_historical != null ? `${b.win_rate_historical}%` : "",
      b.roi_historical != null ? `${b.roi_historical}%` : "",
      b.sample_size ?? "",
    ].join(",")
  })

  const csv = [headers.join(","), ...rows].join("\n")
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  const ts = new Date().toISOString().slice(0, 16).replace("T", "_").replace(":", "")
  a.href = url
  a.download = `apuestas_paper_${ts}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export function PlacedBetsView() {
  const [data, setData] = useState<PlacedBetsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [resolving, setResolving] = useState<number | null>(null)
  const [addingManual, setAddingManual] = useState<number | null>(null)
  // Key: `${match_id}::${recommendation}` — mirrors backend dedup logic
  const [manualKeys, setManualKeys] = useState<Set<string>>(new Set())
  const [addManualError, setAddManualError] = useState<number | null>(null)

  const manualKey = (b: PlacedBet) => `${b.match_id}::${b.recommendation}`

  const reload = async () => {
    try {
      const [auto, manual] = await Promise.all([api.getPlacedBets(), api.getManualBets()])
      setData(auto)
      setManualKeys(new Set(manual.bets.map(manualKey)))
    } catch { /* ignore */ }
  }

  const handleResolve = async (id: number, result: "won" | "lost") => {
    setResolving(id)
    try {
      await api.resolveBet(id, result)
      await reload()
    } catch { /* ignore */ } finally {
      setResolving(null)
    }
  }

  const handleAddToManual = async (bet: PlacedBet) => {
    setAddingManual(bet.id)
    setAddManualError(null)
    try {
      await api.addToManualPaper(bet.id)
      setManualKeys(prev => new Set(prev).add(manualKey(bet)))
    } catch (err) {
      const msg = err instanceof Error ? err.message : ""
      // 409 = already added (treat as success)
      if (msg.includes("409")) {
        setManualKeys(prev => new Set(prev).add(manualKey(bet)))
      } else {
        setAddManualError(bet.id)
        setTimeout(() => setAddManualError(null), 2500)
      }
    } finally {
      setAddingManual(null)
    }
  }

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [auto, manual] = await Promise.all([api.getPlacedBets(), api.getManualBets()])
        setData(auto)
        setManualKeys(new Set(manual.bets.map(manualKey)))
      } catch {
        /* silently ignore */
      } finally {
        setLoading(false)
      }
    }
    fetchAll()
    const id = setInterval(fetchAll, 15000)
    return () => clearInterval(id)
  }, [])

  if (loading) {
    return <div className="p-6 text-zinc-400">Cargando apuestas...</div>
  }

  const bets = data?.bets ?? []
  const pending = bets.filter((b) => b.status === "pending")
  const cashed = bets.filter((b) => b.status === "cashout")
  const resolved = bets.filter((b) => b.status === "won" || b.status === "lost")

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Mis Apuestas</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Seguimiento de apuestas registradas desde Senales
          </p>
        </div>
        {bets.length > 0 && (
          <button
            type="button"
            onClick={() => exportBetsToCSV(bets)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 text-sm transition-colors"
            title="Exportar todas las apuestas a CSV para análisis"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Exportar CSV
          </button>
        )}
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <StatCard label="Total" value={data?.total ?? 0} />
        <StatCard label="Pendientes" value={data?.pending ?? 0} color="text-amber-400" />
        <StatCard label="Ganadas" value={data?.won ?? 0} color="text-green-400" />
        <StatCard label="Perdidas" value={data?.lost ?? 0} color="text-red-400" />
        <StatCard label="Cashout" value={data?.cashout ?? 0} color="text-orange-400" />
        <StatCard
          label="P/L Total"
          value={`${(data?.total_pl ?? 0) >= 0 ? "+" : ""}${(data?.total_pl ?? 0).toFixed(2)}`}
          color={(data?.total_pl ?? 0) >= 0 ? "text-green-400" : "text-red-400"}
        />
      </div>

      {/* Pending bets (live) */}
      {pending.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-amber-400 mb-3 uppercase tracking-wide">
            En juego ({pending.length})
          </h2>
          <div className="space-y-2">
            {pending.map((b) => (
              <PendingBetRow
                key={b.id}
                bet={b}
                resolving={resolving}
                onResolve={handleResolve}
                addingManual={addingManual}
                isManualAdded={manualKeys.has(manualKey(b))}
                hasManualError={addManualError === b.id}
                onAddToManual={handleAddToManual}
              />
            ))}
          </div>
        </section>
      )}

      {/* Cashed-out bets */}
      {cashed.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-orange-400 mb-3 uppercase tracking-wide">
            Cashout automático ({cashed.length})
          </h2>
          <div className="space-y-2">
            {cashed.map((b) => (
              <CashedBetRow key={b.id} bet={b} />
            ))}
          </div>
        </section>
      )}

      {/* Resolved bets */}
      {resolved.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-zinc-400 mb-3 uppercase tracking-wide">
            Finalizadas ({resolved.length})
          </h2>
          <div className="space-y-2">
            {resolved.map((b) => (
              <ResolvedBetRow key={b.id} bet={b} />
            ))}
          </div>
        </section>
      )}

      {/* Empty state */}
      {bets.length === 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-10 text-center">
          <div className="text-zinc-500 text-sm">
            No hay apuestas registradas.
            <br />
            <span className="text-zinc-600">
              Ve a <span className="text-amber-400">Senales</span> y pulsa{" "}
              <span className="text-blue-400">Add Bet</span> en cualquier senal para empezar.
            </span>
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

function PendingBetRow({ bet, resolving, onResolve, addingManual, isManualAdded, hasManualError, onAddToManual }: {
  bet: PlacedBet
  resolving: number | null
  onResolve: (id: number, result: "won" | "lost") => Promise<void>
  addingManual: number | null
  isManualAdded: boolean
  hasManualError: boolean
  onAddToManual: (bet: PlacedBet) => Promise<void>
}) {
  const favorable = bet.would_win_now === true
  const borderColor = favorable ? "border-green-500/30" : "border-red-500/30"
  const bgColor = favorable ? "bg-green-900/10" : "bg-red-900/10"
  const isResolving = resolving === bet.id
  const isAddingManual = addingManual === bet.id
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

          {/* Cashout alert */}
          {bet.suggest_cashout && (
            <div
              className="flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/40 min-w-[64px]"
              title={`Lay actual ${bet.cashout_lay_current} ≥ umbral ${bet.cashout_threshold} (entrada ${odds.toFixed(2)} +20%) — considera hacer lay para limitar pérdidas`}
            >
              <span className="text-amber-400 font-bold text-xs animate-pulse">⚡ CO</span>
              <span className="text-amber-300 font-mono text-[10px]">{bet.cashout_lay_current?.toFixed(2)}</span>
            </div>
          )}

          {/* Add to manual paper button */}
          <button
            type="button"
            disabled={isAddingManual || isManualAdded}
            onClick={() => onAddToManual(bet)}
            className={`px-2 py-1.5 text-[10px] font-bold rounded border transition-colors cursor-pointer disabled:opacity-40 ${
              hasManualError
                ? "bg-red-500/20 border-red-500/40 text-red-300"
                : isManualAdded
                  ? "bg-violet-500/20 border-violet-500/40 text-violet-300"
                  : "bg-zinc-800 border-zinc-600 text-zinc-400 hover:bg-violet-500/15 hover:border-violet-500/40 hover:text-violet-300"
            }`}
            title="Añadir esta apuesta a tu paper manual"
          >
            {isAddingManual ? "…" : hasManualError ? "ERROR" : isManualAdded ? "✓ MI PAPER" : "+ MI PAPER"}
          </button>

          {/* Manual resolve buttons */}
          <div className="flex flex-col gap-1">
            <button
              type="button"
              disabled={isResolving}
              onClick={() => onResolve(bet.id, "won")}
              className="px-2 py-1 text-[10px] font-bold rounded bg-green-500/15 border border-green-500/30 text-green-400 hover:bg-green-500/25 transition-colors cursor-pointer disabled:opacity-40"
            >
              {isResolving ? "…" : "WON"}
            </button>
            <button
              type="button"
              disabled={isResolving}
              onClick={() => onResolve(bet.id, "lost")}
              className="px-2 py-1 text-[10px] font-bold rounded bg-red-500/15 border border-red-500/30 text-red-400 hover:bg-red-500/25 transition-colors cursor-pointer disabled:opacity-40"
            >
              {isResolving ? "…" : "LOST"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function CashedBetRow({ bet }: { bet: PlacedBet }) {
  const pl = Number(bet.pl) || 0
  const odds = Number(bet.back_odds) || 0

  return (
    <div className="border border-orange-500/25 bg-orange-900/5 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-zinc-300 truncate">{bet.match_name}</span>
            <TypeBadge type={bet.bet_type} />
            <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold bg-orange-500/15 text-orange-400">
              CO AUTO
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            <span>{bet.strategy_name}</span>
            <span className="text-zinc-700">|</span>
            <span>{bet.recommendation}</span>
            <span className="text-zinc-700">|</span>
            <span>Entrada @ {odds.toFixed(2)}</span>
            {bet.cashout_lay_current != null && (
              <>
                <span className="text-zinc-700">|</span>
                <span className="text-orange-400">Lay CO @ {bet.cashout_lay_current.toFixed(2)}</span>
              </>
            )}
          </div>
        </div>
        <div className={`text-lg font-bold font-mono ${pl >= 0 ? "text-green-400" : "text-red-400"}`}>
          {pl >= 0 ? "+" : ""}{pl.toFixed(2)}
        </div>
      </div>
    </div>
  )
}

function ResolvedBetRow({ bet }: { bet: PlacedBet }) {
  const won = bet.status === "won"
  const borderColor = won ? "border-green-500/20" : "border-red-500/20"
  const bgColor = won ? "bg-green-900/5" : "bg-red-900/5"
  const pl = Number(bet.pl) || 0

  return (
    <div className={`border rounded-lg p-4 ${borderColor} ${bgColor}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-zinc-300 truncate">{bet.match_name}</span>
            <TypeBadge type={bet.bet_type} />
            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-bold ${
              won ? "bg-green-500/15 text-green-400" : "bg-red-500/15 text-red-400"
            }`}>
              {won ? "WON" : "LOST"}
            </span>
          </div>
          <div className="flex items-center gap-3 text-xs text-zinc-500">
            <span>{bet.strategy_name}</span>
            <span className="text-zinc-700">|</span>
            <span>{bet.recommendation}</span>
            <span className="text-zinc-700">|</span>
            <span>Score: {bet.live_score ?? bet.score}</span>
          </div>
        </div>
        <div className={`text-lg font-bold font-mono ${pl >= 0 ? "text-green-400" : "text-red-400"}`}>
          {pl >= 0 ? "+" : ""}{pl.toFixed(2)}
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
