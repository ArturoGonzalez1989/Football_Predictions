import { useState, useEffect } from "react"
import { api, type PlacedBetsResponse, type PlacedBet } from "../lib/api"

function exportBetsToExcel(bets: PlacedBet[]) {
  const headers = [
    "ID", "Fecha UTC", "Fecha Local", "Dia Semana", "Hora",
    "Match ID", "Partido", "URL Betfair",
    "Estrategia ID", "Estrategia", "Tipo Apuesta",
    "Minuto Entrada", "Score Entrada", "Recomendacion",
    "Side", "Mercado", "Seleccion",
    "Cuota Entrada", "Cuota Minima", "Cuota Valida", "Margen Cuota %",
    "Stake", "Ganancia Potencial", "Riesgo",
    "Estado", "Resultado", "P/L", "ROI Apuesta %",
    "EV Esperado", "Confianza",
    "WR Historico %", "ROI Historico %", "Muestra N",
    "Score Final", "Minuto Final",
    "Cuota Lay Actual", "P/L Cashout",
    "Notas",
  ]

  const rows = bets.map(b => {
    const backOdds = Number(b.back_odds) || 0
    const minOdds = Number(b.min_odds) || 0
    const oddsValid = backOdds > 0 && minOdds > 0 && backOdds >= minOdds ? "SI" : (backOdds === 0 ? "?" : "NO")
    const oddsMargin = backOdds > 0 && minOdds > 0 ? ((backOdds - minOdds) / minOdds * 100).toFixed(1) : ""
    const stake = Number(b.stake) || 0
    const potentialProfit = backOdds > 0 ? ((backOdds - 1) * stake).toFixed(2) : ""
    const pl = b.pl != null ? Number(b.pl) : null
    const roiBet = pl != null && stake > 0 ? (pl / stake * 100).toFixed(1) : ""

    // Parse recommendation into side/market/selection
    const rec = (b.recommendation || "").toUpperCase()
    const side = rec.startsWith("BACK") ? "Back" : rec.startsWith("LAY") ? "Lay" : ""
    const recRest = rec.replace(/^(BACK|LAY)\s+/, "").replace(/\s+@.*/, "")
    let market = ""
    let selection = ""
    if (recRest.includes("DRAW") || recRest.includes("HOME") || recRest.includes("AWAY")) {
      market = "Match Odds"
      selection = recRest.includes("DRAW") ? "Empate" : recRest.includes("HOME") ? "Local" : "Visitante"
    } else if (recRest.startsWith("OVER") || recRest.startsWith("UNDER")) {
      const goals = recRest.replace(/^(OVER|UNDER)\s*/, "")
      market = `Mas/Menos ${goals} Goles`
      selection = recRest.startsWith("OVER") ? `Mas ${goals}` : `Menos ${goals}`
    } else if (recRest.startsWith("CS")) {
      market = "Resultado Correcto"
      selection = recRest.replace("CS ", "")
    }

    // Parse date
    const ts = b.timestamp_utc ? new Date(b.timestamp_utc + "Z") : null
    const fechaLocal = ts ? ts.toLocaleString("es-ES") : ""
    const diaSemana = ts ? ["Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"][ts.getDay()] : ""
    const hora = ts ? ts.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : ""

    return [
      b.id,
      b.timestamp_utc,
      fechaLocal,
      diaSemana,
      hora,
      b.match_id,
      b.match_name,
      b.match_url,
      b.strategy,
      b.strategy_name,
      b.bet_type,
      b.minute,
      b.score,
      b.recommendation,
      side,
      market,
      selection,
      backOdds > 0 ? backOdds.toFixed(2) : "",
      minOdds > 0 ? minOdds.toFixed(2) : "",
      oddsValid,
      oddsMargin,
      stake.toFixed(2),
      potentialProfit,
      stake.toFixed(2),
      b.status,
      b.result ?? "",
      pl != null ? pl.toFixed(2) : "",
      roiBet,
      b.expected_value != null ? Number(b.expected_value).toFixed(3) : "",
      b.confidence ?? "",
      b.win_rate_historical != null ? Number(b.win_rate_historical).toFixed(1) : "",
      b.roi_historical != null ? Number(b.roi_historical).toFixed(1) : "",
      b.sample_size ?? "",
      b.live_score ?? b.result ?? "",
      b.live_minute ?? "",
      b.cashout_lay_current != null ? Number(b.cashout_lay_current).toFixed(2) : "",
      b.cashout_pl != null ? Number(b.cashout_pl).toFixed(2) : "",
      b.notes ?? "",
    ]
  })

  // Build XML Spreadsheet (opens natively in Excel without dependencies)
  const esc = (v: unknown) => String(v ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")
  const isNum = (v: unknown) => typeof v === "number" || (typeof v === "string" && v !== "" && !isNaN(Number(v)) && !/^\d{4}-/.test(v))

  let xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
  xml += '<?mso-application progid="Excel.Sheet"?>\n'
  xml += '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"\n'
  xml += ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">\n'
  xml += '<Styles>\n'
  xml += '  <Style ss:ID="header"><Font ss:Bold="1" ss:Size="10"/><Interior ss:Color="#F2F2F2" ss:Pattern="Solid"/></Style>\n'
  xml += '  <Style ss:ID="won"><Interior ss:Color="#D5F5E3" ss:Pattern="Solid"/></Style>\n'
  xml += '  <Style ss:ID="lost"><Interior ss:Color="#FADBD8" ss:Pattern="Solid"/></Style>\n'
  xml += '  <Style ss:ID="pending"><Interior ss:Color="#FEF9E7" ss:Pattern="Solid"/></Style>\n'
  xml += '  <Style ss:ID="cashout"><Interior ss:Color="#FDE9D9" ss:Pattern="Solid"/></Style>\n'
  xml += '</Styles>\n'
  xml += '<Worksheet ss:Name="Apuestas">\n'
  xml += `<Table ss:ExpandedColumnCount="${headers.length}" ss:ExpandedRowCount="${rows.length + 1}">\n`

  // Header row
  xml += '<Row ss:StyleID="header">'
  for (const h of headers) {
    xml += `<Cell><Data ss:Type="String">${esc(h)}</Data></Cell>`
  }
  xml += '</Row>\n'

  // Data rows
  for (let i = 0; i < rows.length; i++) {
    const status = bets[i].status
    const style = status === "won" ? ' ss:StyleID="won"' : status === "lost" ? ' ss:StyleID="lost"' : status === "cashout" ? ' ss:StyleID="cashout"' : status === "pending" ? ' ss:StyleID="pending"' : ""
    xml += `<Row${style}>`
    for (const cell of rows[i]) {
      if (isNum(cell) && cell !== "") {
        xml += `<Cell><Data ss:Type="Number">${cell}</Data></Cell>`
      } else {
        xml += `<Cell><Data ss:Type="String">${esc(cell)}</Data></Cell>`
      }
    }
    xml += '</Row>\n'
  }

  xml += '</Table>\n'

  // Summary sheet
  const totalBets = bets.length
  const wonBets = bets.filter(b => b.status === "won").length
  const lostBets = bets.filter(b => b.status === "lost").length
  const cashoutBets = bets.filter(b => b.status === "cashout").length
  const pendingBets = bets.filter(b => b.status === "pending").length
  const totalPL = bets.reduce((s, b) => s + (Number(b.pl) || 0), 0)
  const totalStake = bets.filter(b => b.status !== "pending").reduce((s, b) => s + (Number(b.stake) || 0), 0)
  const wr = totalBets - pendingBets > 0 ? (wonBets / (totalBets - pendingBets) * 100).toFixed(1) : "0"
  const roi = totalStake > 0 ? (totalPL / totalStake * 100).toFixed(1) : "0"
  const strategies = [...new Set(bets.map(b => b.strategy_name))].sort()

  xml += '</Worksheet>\n'
  xml += '<Worksheet ss:Name="Resumen">\n'
  xml += '<Table>\n'
  xml += '<Row ss:StyleID="header"><Cell><Data ss:Type="String">Metrica</Data></Cell><Cell><Data ss:Type="String">Valor</Data></Cell></Row>\n'
  const summaryRows: [string, string | number][] = [
    ["Total Apuestas", totalBets],
    ["Pendientes", pendingBets],
    ["Ganadas", wonBets],
    ["Perdidas", lostBets],
    ["Cashout", cashoutBets],
    ["Win Rate %", wr],
    ["P/L Total", totalPL.toFixed(2)],
    ["Stake Total (resueltas)", totalStake.toFixed(2)],
    ["ROI %", roi],
    ["Estrategias Activas", strategies.length],
    ["Estrategias", strategies.join(", ")],
    ["Exportado", new Date().toLocaleString("es-ES")],
  ]
  for (const [k, v] of summaryRows) {
    const t = isNum(v) ? "Number" : "String"
    xml += `<Row><Cell><Data ss:Type="String">${esc(k)}</Data></Cell><Cell><Data ss:Type="${t}">${esc(v)}</Data></Cell></Row>\n`
  }
  xml += '</Table>\n'
  xml += '</Worksheet>\n'
  xml += '</Workbook>'

  const blob = new Blob([xml], { type: "application/vnd.ms-excel" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  const ts2 = new Date().toISOString().slice(0, 16).replace("T", "_").replace(":", "")
  a.href = url
  a.download = `apuestas_paper_${ts2}.xls`
  a.click()
  URL.revokeObjectURL(url)
}

export function PlacedBetsView() {
  const [data, setData] = useState<PlacedBetsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [resolving, setResolving] = useState<number | null>(null)

  const reload = async () => {
    try {
      const auto = await api.getPlacedBets()
      setData(auto)
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

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const auto = await api.getPlacedBets()
        setData(auto)
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
            onClick={() => exportBetsToExcel(bets)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 text-sm transition-colors"
            title="Exportar todas las apuestas a Excel con detalle completo"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            Exportar Excel
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

function PendingBetRow({ bet, resolving, onResolve }: {
  bet: PlacedBet
  resolving: number | null
  onResolve: (id: number, result: "won" | "lost") => Promise<void>
}) {
  const favorable = bet.would_win_now === true
  const borderColor = favorable ? "border-green-500/30" : "border-red-500/30"
  const bgColor = favorable ? "bg-green-900/10" : "bg-red-900/10"
  const isResolving = resolving === bet.id
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

          {/* Open in Betfair button */}
          {bet.match_url && <OpenBetButton matchUrl={bet.match_url} recommendation={bet.recommendation} matchName={bet.match_name} />}

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

function OpenBetButton({ matchUrl, recommendation, matchName }: { matchUrl: string; recommendation?: string; matchName?: string }) {
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "err">("idle")
  const handleClick = async () => {
    setStatus("loading")
    try {
      await api.openBet(matchUrl, recommendation, matchName)
      setStatus("ok")
      setTimeout(() => setStatus("idle"), 2000)
    } catch {
      window.open(matchUrl, "_blank")
      setStatus("err")
      setTimeout(() => setStatus("idle"), 2000)
    }
  }
  const label = status === "loading" ? "..." : status === "ok" ? "✓" : status === "err" ? "↗" : "Abrir"
  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={status === "loading"}
      title={status === "err" ? "Bot falló — abierto en pestaña" : "Abrir en Betfair vía bot"}
      className="px-2.5 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-60 bg-green-600 hover:bg-green-500 text-white"
    >
      {label}
    </button>
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
