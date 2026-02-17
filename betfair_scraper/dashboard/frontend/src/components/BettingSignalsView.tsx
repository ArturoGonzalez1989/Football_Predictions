import { useState, useEffect, useRef, useCallback } from "react"
import { api, type BettingSignals, type BettingSignal, type PlaceBetRequest, type WatchlistItem } from "../lib/api"
import { playSignalAlert } from "../lib/sounds"
import { type VersionCombo, comboToSignalVersions } from "../lib/cartera"

// Separate storage key for manual signal configuration (independent from cartera presets)
const SIGNALS_CONFIG_KEY = "furbo_signals_manual_config"

const DEFAULT_COMBO: VersionCombo = {
  draw: "v15", xg: "v3", drift: "v1", clustering: "v2", pressure: "v1", tardeAsia: "off", momentumXG: "v1", br: "fixed"
}

function loadManualCombo(): VersionCombo {
  try {
    const stored = localStorage.getItem(SIGNALS_CONFIG_KEY)
    if (stored) return JSON.parse(stored)
  } catch { /* ignore */ }
  return DEFAULT_COMBO
}

function saveManualCombo(combo: VersionCombo) {
  try {
    localStorage.setItem(SIGNALS_CONFIG_KEY, JSON.stringify(combo))
  } catch { /* ignore */ }
}

const VERSION_LABELS: Record<string, Record<string, string>> = {
  draw: { v1: "V1", v15: "V1.5", v2r: "V2r", v2: "V2", off: "OFF" },
  xg: { base: "V1", v2: "V2", v3: "V3", off: "OFF" },
  drift: { v1: "V1", v2: "V2", v3: "V3", v4: "V4", v5: "V5", off: "OFF" },
  clustering: { v2: "V2", v3: "V3", off: "OFF" },
  pressure: { v1: "V1", off: "OFF" },
  tardeAsia: { v1: "V1", off: "OFF" },
  momentumXG: { v1: "V1", v2: "V2", off: "OFF" },
}

const STRATEGY_NAMES: Record<string, string> = {
  draw: "Empate", xg: "xG Underp.", drift: "Odds Drift", clustering: "Goal Clust.", pressure: "Pressure C.", tardeAsia: "Tarde Asia", momentumXG: "Mom. x xG"
}

export function BettingSignalsView() {
  const [signals, setSignals] = useState<BettingSignals | null>(null)
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [combo, setCombo] = useState<VersionCombo>(loadManualCombo)
  const prevSignalKeys = useRef<Set<string> | null>(null)
  const comboRef = useRef(combo)
  comboRef.current = combo
  const modalOpenRef = useRef(false)

  // Update combo and save to localStorage
  const updateCombo = useCallback((newCombo: VersionCombo) => {
    setCombo(newCombo)
    comboRef.current = newCombo
    saveManualCombo(newCombo)
  }, [])

  const fetchSignals = useCallback(async () => {
    try {
      const versions = comboToSignalVersions(comboRef.current)
      const [data, wl] = await Promise.all([
        api.getBettingSignals(versions),
        api.getWatchlist(versions),
      ])
      // Don't update signals while user has Add Bet modal open
      if (modalOpenRef.current) return
      setSignals(data)
      setWatchlist(wl)
      setError(null)

      // Check for NEW signals
      const currentKeys = new Set(
        (data.signals || []).map((s) => `${s.match_id}:${s.strategy}`)
      )
      if (prevSignalKeys.current !== null) {
        const hasNew = [...currentKeys].some((k) => !prevSignalKeys.current!.has(k))
        if (hasNew) playSignalAlert()
      }
      prevSignalKeys.current = currentKeys
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch signals")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSignals()
    const interval = setInterval(fetchSignals, 10000)
    return () => clearInterval(interval)
  }, [fetchSignals])

  // Re-fetch when combo changes
  useEffect(() => {
    fetchSignals()
  }, [combo]) // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-zinc-400">Cargando señales...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="text-red-400">Error: {error}</div>
      </div>
    )
  }

  const activeSignals = signals?.signals || []
  const liveMatches = signals?.live_matches || 0

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Señales de Apuesta</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Oportunidades detectadas en tiempo real según tu cartera de estrategias
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-xs text-zinc-500">Partidos en vivo</div>
            <div className="text-lg font-bold text-blue-400">{liveMatches}</div>
          </div>
          <div className="text-right">
            <div className="text-xs text-zinc-500">Señales activas</div>
            <div className="text-lg font-bold text-green-400">{activeSignals.length}</div>
          </div>
        </div>
      </div>

      {/* Main content + Watchlist sidebar */}
      <div className="flex gap-6">
        {/* Main column */}
        <div className="flex-1 min-w-0 space-y-6">
          {/* Active Signals */}
          {activeSignals.length === 0 ? (
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-8 text-center">
              <div className="text-zinc-500 text-sm">
                No hay señales de apuesta activas en este momento.
                <br />
                El sistema está monitoreando {liveMatches} {liveMatches === 1 ? "partido" : "partidos"} en vivo.
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {activeSignals.map((signal, idx) => (
                <SignalCard key={`${signal.match_id}-${signal.strategy}-${idx}`} signal={signal} modalOpenRef={modalOpenRef} />
              ))}
            </div>
          )}

          {/* Manual Strategy Configuration */}
          <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-zinc-300">Configuración de Estrategias</h3>
              <button
                type="button"
                onClick={() => updateCombo(DEFAULT_COMBO)}
                className="text-[10px] text-zinc-500 hover:text-zinc-300 transition-colors"
                title="Resetear a configuración por defecto"
              >
                Resetear
              </button>
            </div>

            {/* Manual version selectors */}
            <div className="space-y-2.5">
              {Object.entries(STRATEGY_NAMES).map(([key, name]) => {
                const currentVer = combo[key as keyof VersionCombo] as string
                const versions = VERSION_LABELS[key] || {}

                return (
                  <div key={key} className="flex items-center justify-between gap-3">
                    <span className="text-xs text-zinc-400 min-w-[90px]">{name}:</span>
                    <div className="flex gap-1.5">
                      {Object.entries(versions).map(([verKey, verLabel]) => {
                        const isActive = currentVer === verKey
                        const isOff = verKey === "off"
                        return (
                          <button
                            key={verKey}
                            type="button"
                            onClick={() => updateCombo({ ...combo, [key]: verKey })}
                            className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${
                              isActive
                                ? isOff
                                  ? "bg-red-500/20 text-red-400 border border-red-500/30"
                                  : "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                                : isOff
                                  ? "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:border-red-500/30 hover:text-red-400"
                                  : "bg-zinc-800/50 text-zinc-500 border border-zinc-700/50 hover:border-blue-500/30 hover:text-zinc-300"
                            }`}
                            title={`${name} ${verLabel}`}
                          >
                            {verLabel}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Info hint */}
            <div className="mt-3 pt-3 border-t border-zinc-800">
              <p className="text-[10px] text-zinc-600">
                💡 Configura manualmente las versiones de cada estrategia. Para análisis histórico con presets automáticos, ve a Insights → Cartera.
              </p>
            </div>
          </div>
        </div>

        {/* Watchlist sidebar */}
        <div className="w-72 shrink-0">
          <WatchlistSidebar items={watchlist} />
        </div>
      </div>
    </div>
  )
}

function WatchlistSidebar({ items }: { items: WatchlistItem[] }) {
  return (
    <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg overflow-hidden">
      <div className="px-3 py-2.5 border-b border-zinc-800 flex items-center justify-between">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Radar</h3>
        <span className="text-[10px] text-zinc-600">{items.length} cerca</span>
      </div>

      {items.length === 0 ? (
        <div className="p-4 text-center text-zinc-600 text-xs">
          Ningún partido cerca de una señal
        </div>
      ) : (
        <div className="divide-y divide-zinc-800/50 max-h-[calc(100vh-220px)] overflow-y-auto">
          {items.map((item, idx) => (
            <WatchlistCard key={`${item.match_id}-${item.strategy}-${idx}`} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

function WatchlistCard({ item }: { item: WatchlistItem }) {
  return (
    <div className="px-3 py-2.5 hover:bg-zinc-800/30 transition-colors">
      {/* Match name + proximity */}
      <div className="flex items-center justify-between mb-1.5">
        <a
          href={item.match_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs font-medium text-zinc-200 hover:text-blue-400 transition-colors truncate mr-2"
        >
          {item.match_name}
        </a>
        <span className={`text-[10px] font-bold shrink-0 ${
          item.proximity >= 75 ? "text-yellow-400" : item.proximity >= 50 ? "text-zinc-400" : "text-zinc-600"
        }`}>
          {item.proximity}%
        </span>
      </div>

      {/* Strategy + score context */}
      <div className="flex items-center gap-1.5 mb-1.5">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">
          {item.strategy} {item.version}
        </span>
        <span className="text-[10px] text-zinc-600">
          {item.score} · Min {item.minute}'
        </span>
      </div>

      {/* Condition pills */}
      <div className="flex flex-wrap gap-1">
        {item.conditions.map((c, i) => (
          <span
            key={i}
            className={`text-[10px] px-1.5 py-0.5 rounded ${
              c.met
                ? "bg-green-500/10 text-green-500"
                : "bg-zinc-800/80 text-zinc-500"
            }`}
            title={c.met ? `${c.label}: ${c.current}` : `${c.label}: ${c.current ?? '?'} (necesita ${c.target})`}
          >
            {c.met ? "✓" : "○"} {c.label}
          </span>
        ))}
      </div>
    </div>
  )
}

function SignalCard({ signal, modalOpenRef }: { signal: BettingSignal; modalOpenRef: React.RefObject<boolean> }) {
  const [showModal, setShowModalRaw] = useState(false)
  const setShowModal = (v: boolean) => {
    setShowModalRaw(v)
    modalOpenRef.current = v
  }
  const [betType, setBetType] = useState<"paper" | "real">("paper")
  const [stake, setStake] = useState(10)
  const [notes, setNotes] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  // Determine card colors based on risk level (overrides confidence)
  const riskLevel = signal.risk_info?.risk_level || "none"

  let cardBorderColor: string
  let cardBgColor: string

  if (riskLevel === "high") {
    cardBorderColor = "border-red-500/40"
    cardBgColor = "bg-red-500/10"
  } else if (riskLevel === "medium") {
    cardBorderColor = "border-orange-500/40"
    cardBgColor = "bg-orange-500/10"
  } else {
    // No risk - use confidence colors
    const confidenceColors = {
      high: { border: "border-green-500/20", bg: "bg-green-500/10" },
      medium: { border: "border-yellow-500/20", bg: "bg-yellow-500/10" },
      low: { border: "border-orange-500/20", bg: "bg-orange-500/10" },
    }
    const colors = confidenceColors[signal.confidence]
    cardBorderColor = colors.border
    cardBgColor = colors.bg
  }

  const handleAddBet = async () => {
    try {
      setSaving(true)

      // Check for duplicate bets on the same match
      const placedBetsResponse = await api.getPlacedBets()
      const existingBets = placedBetsResponse.bets || []

      const duplicatesOnMatch = existingBets.filter(
        (bet) => bet.match_id === signal.match_id
      )

      if (duplicatesOnMatch.length > 0) {
        // Parse bet type from recommendation
        const parseBetType = (rec: string) => {
          const r = rec.toUpperCase()
          if (r.includes("DRAW")) return "DRAW"
          if (r.includes("OVER")) {
            const m = r.match(/OVER\s+(\d+\.?\d*)/)
            return m ? `OVER_${m[1]}` : "OVER"
          }
          if (r.includes("UNDER")) {
            const m = r.match(/UNDER\s+(\d+\.?\d*)/)
            return m ? `UNDER_${m[1]}` : "UNDER"
          }
          if (r.includes("HOME")) return "HOME"
          if (r.includes("AWAY")) return "AWAY"
          return "OTHER"
        }

        const currentBetType = parseBetType(signal.recommendation)

        // Check if same bet type exists
        const sameBetType = duplicatesOnMatch.find((bet) => {
          const existingBetType = parseBetType(bet.recommendation || "")
          return existingBetType === currentBetType
        })

        if (sameBetType) {
          // BLOCK: Same match + same bet type
          alert(
            `⚠️ APUESTA DUPLICADA BLOQUEADA\n\n` +
              `Ya tienes una apuesta ${currentBetType} en este partido:\n` +
              `• ${sameBetType.strategy_name}\n` +
              `• ${sameBetType.recommendation}\n` +
              `• Añadida: ${sameBetType.timestamp_utc?.slice(0, 16)}\n\n` +
              `No se permite apostar dos veces al mismo mercado en el mismo partido.`
          )
          setSaving(false)
          return
        }

        // WARN: Same match but different bet type
        const confirmed = window.confirm(
          `⚠️ ADVERTENCIA: Ya tienes ${duplicatesOnMatch.length} apuesta(s) en este partido:\n\n` +
            duplicatesOnMatch
              .map(
                (bet) =>
                  `• ${bet.strategy_name} - ${bet.recommendation} (${bet.timestamp_utc?.slice(0, 16)})`
              )
              .join("\n") +
            `\n\n¿Seguro que quieres añadir otra apuesta en el mismo partido?`
        )

        if (!confirmed) {
          setSaving(false)
          return
        }
      }

      const betRequest: PlaceBetRequest = {
        match_id: signal.match_id,
        match_name: signal.match_name,
        match_url: signal.match_url,
        strategy: signal.strategy,
        strategy_name: signal.strategy_name,
        minute: signal.minute,
        score: signal.score,
        recommendation: signal.recommendation,
        back_odds: signal.back_odds,
        min_odds: signal.min_odds,
        expected_value: signal.expected_value,
        confidence: signal.confidence,
        win_rate_historical: signal.win_rate_historical,
        roi_historical: signal.roi_historical,
        sample_size: signal.sample_size,
        bet_type: betType,
        stake: stake,
        notes: notes || undefined,
      }

      await api.placeBet(betRequest)
      setSaveSuccess(true)
      setTimeout(() => {
        setShowModal(false)
        setSaveSuccess(false)
        setNotes("")
      }, 1500)
    } catch (error) {
      console.error("Error guardando apuesta:", error)
      alert("Error al guardar la apuesta")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className={`border rounded-lg p-4 ${cardBorderColor} ${cardBgColor}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <a
              href={signal.match_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-zinc-100 hover:text-blue-400 transition-colors"
            >
              {signal.match_name}
            </a>
            <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
              {signal.score}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400">
              Min {signal.minute}'
            </span>
          </div>
          <div className="text-xs text-zinc-500">{signal.strategy_name}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-zinc-500 mb-1">Confianza</div>
          <div className={`text-sm font-bold uppercase ${signal.confidence === 'high' ? 'text-green-400' : signal.confidence === 'medium' ? 'text-yellow-400' : 'text-orange-400'}`}>
            {signal.confidence}
          </div>
        </div>
      </div>

      {/* Risk Warning */}
      {signal.risk_info && signal.risk_info.has_risk && (
        <div className={`mb-3 p-3 rounded border ${
          signal.risk_info.risk_level === "high"
            ? "bg-red-900/30 border-red-500/40"
            : "bg-orange-900/20 border-orange-500/30"
        }`}>
          <div className="flex items-start gap-2">
            <div className="text-lg mt-0.5">
              {signal.risk_info.risk_level === "high" ? "🔴" : "🟠"}
            </div>
            <div className="flex-1">
              <div className={`font-semibold text-sm mb-1 ${
                signal.risk_info.risk_level === "high" ? "text-red-400" : "text-orange-400"
              }`}>
                {signal.risk_info.risk_level === "high" ? "Señal de Alto Riesgo" : "Señal de Riesgo Medio"}
              </div>
              <div className={`text-xs ${
                signal.risk_info.risk_level === "high" ? "text-red-300/80" : "text-orange-300/80"
              }`}>
                {signal.risk_info.risk_reason}
              </div>
              <div className="flex gap-3 mt-2 text-[10px] text-zinc-400">
                <span>Tiempo restante: {signal.risk_info.time_remaining} min</span>
                {signal.risk_info.deficit > 0 && (
                  <span>Déficit: {signal.risk_info.deficit} gol{signal.risk_info.deficit > 1 ? 'es' : ''}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* GO/NO-GO Decision — always show min_odds guidance */}
      {(() => {
        const hasOdds = signal.back_odds != null
        const isFavorable = signal.odds_favorable === true
        const isUnfavorable = signal.odds_favorable === false
        // No odds data at all — show min_odds guidance
        const isUnknown = !hasOdds

        const bgClass = isFavorable
          ? 'bg-green-900/20 border-green-500/30'
          : isUnfavorable
            ? 'bg-red-900/20 border-red-500/30'
            : 'bg-yellow-900/10 border-yellow-500/20'

        return (
          <div className={`mb-3 p-3 rounded border ${bgClass}`}>
            <div className="flex items-center justify-between">
              <div>
                {/* Verdict */}
                {isFavorable && (
                  <>
                    <div className="text-xl font-bold text-green-400">APOSTAR</div>
                    {signal.expected_value != null && (
                      <div className="text-xs text-zinc-400 mt-0.5">
                        EV: +{signal.expected_value.toFixed(2)} EUR / 10 EUR apuesta
                      </div>
                    )}
                  </>
                )}
                {isUnfavorable && (
                  <>
                    <div className="text-xl font-bold text-red-400">NO APOSTAR</div>
                    <div className="text-xs text-red-400/70 mt-0.5">
                      Cuota {signal.back_odds?.toFixed(2)} por debajo del mínimo {signal.min_odds?.toFixed(2)}
                    </div>
                  </>
                )}
                {isUnknown && (
                  <>
                    <div className="text-lg font-bold text-yellow-400">VERIFICAR CUOTA</div>
                    <div className="text-xs text-zinc-400 mt-0.5">
                      No se pudo leer la cuota del mercado — comprueba en Betfair
                    </div>
                  </>
                )}

                {/* Min odds badge — always visible */}
                {signal.min_odds && (
                  <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-zinc-800 border border-zinc-700">
                    <span className="text-xs text-zinc-400">Cuota mínima:</span>
                    <span className="text-sm font-bold text-zinc-100">{signal.min_odds.toFixed(2)}</span>
                    {hasOdds && (
                      <>
                        <span className="text-zinc-600 mx-0.5">|</span>
                        <span className="text-xs text-zinc-400">Actual:</span>
                        <span className={`text-sm font-bold ${isFavorable ? 'text-green-400' : 'text-red-400'}`}>
                          {signal.back_odds?.toFixed(2)}
                        </span>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Action buttons */}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowModal(true)}
                  className={`px-4 py-2 font-semibold rounded-lg transition-colors flex items-center gap-2 shrink-0 ${
                    isUnfavorable
                      ? 'bg-zinc-700 hover:bg-zinc-600 text-zinc-400'
                      : 'bg-blue-600 hover:bg-blue-500 text-white'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  <span>Add Bet</span>
                </button>
                <a
                  href={signal.match_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`px-4 py-2 font-semibold rounded-lg transition-colors flex items-center gap-2 shrink-0 ${
                    isFavorable
                      ? 'bg-green-600 hover:bg-green-500 text-white'
                      : 'bg-zinc-700 hover:bg-zinc-600 text-zinc-300'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                  <span>Ir al partido</span>
                </a>
              </div>
            </div>
          </div>
        )
      })()}

      {/* Recommendation & Odds Analysis */}
      <div className="mb-3 p-3 bg-zinc-900/60 rounded border border-zinc-700">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <div className="text-xs text-zinc-500 mb-1">Recomendación</div>
            <div className="text-lg font-bold text-zinc-100">{signal.recommendation}</div>
          </div>
          {signal.min_odds && signal.back_odds && (
            <div>
              <div className="text-xs text-zinc-500 mb-1">Análisis de Cuota</div>
              <div className="text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-zinc-400">Actual:</span>
                  <span className="font-bold text-zinc-100">{signal.back_odds.toFixed(2)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-zinc-400">Mínima:</span>
                  <span className="font-mono text-zinc-300">{signal.min_odds.toFixed(2)}</span>
                  {signal.back_odds >= signal.min_odds && (
                    <span className="text-green-400 text-xs">
                      (+{(((signal.back_odds - signal.min_odds) / signal.min_odds) * 100).toFixed(0)}%)
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Historical Performance */}
      {signal.win_rate_historical && (
        <div className="mb-3 p-3 bg-zinc-900/30 rounded border border-zinc-800">
          <div className="text-xs text-zinc-500 mb-2">Rendimiento Histórico</div>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <div>
              <div className="text-xs text-zinc-500">Win Rate</div>
              <div className="font-bold text-zinc-100">{signal.win_rate_historical}%</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">ROI</div>
              <div className="font-bold text-green-400">+{signal.roi_historical}%</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">Muestra</div>
              <div className="font-mono text-zinc-300">{signal.sample_size} apuestas</div>
            </div>
          </div>
          {signal.description && (
            <div className="mt-2 text-xs text-zinc-400 italic">{signal.description}</div>
          )}
        </div>
      )}

      {/* Entry Conditions */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-zinc-500 mb-1">Condiciones Actuales</div>
          <div className="space-y-1">
            {Object.entries(signal.entry_conditions).map(([key, value]) => (
              <div key={key} className="text-xs">
                <span className="text-zinc-400">{formatConditionKey(key)}:</span>{" "}
                <span className="text-zinc-200 font-mono">{formatConditionValue(value)}</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1">Umbrales</div>
          <div className="space-y-1">
            {Object.entries(signal.thresholds).map(([key, value]) => (
              <div key={key} className="text-xs">
                <span className="text-zinc-400">{formatConditionKey(key)}:</span>{" "}
                <span className="text-zinc-300 font-mono">{value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>

      {/* Modal para añadir apuesta */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-zinc-100">Registrar Apuesta</h3>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="text-zinc-400 hover:text-zinc-200 transition-colors"
                aria-label="Cerrar modal"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {saveSuccess ? (
              <div className="py-8 text-center">
                <div className="text-green-400 text-5xl mb-3">✓</div>
                <div className="text-lg font-semibold text-green-400">Apuesta registrada!</div>
              </div>
            ) : (
              <>
                {/* Match info */}
                <div className="mb-4 p-3 bg-zinc-800/50 rounded border border-zinc-700">
                  <div className="text-sm text-zinc-400 mb-1">Partido</div>
                  <div className="font-semibold text-zinc-100">{signal.match_name}</div>
                  <div className="text-sm text-zinc-400 mt-1">{signal.recommendation}</div>
                  {signal.back_odds && (
                    <div className="text-sm text-zinc-300 mt-1">Cuota: {signal.back_odds.toFixed(2)}</div>
                  )}
                  {signal.min_odds && (
                    <div className="text-sm text-zinc-500 mt-1">Cuota mínima: {signal.min_odds.toFixed(2)}</div>
                  )}
                </div>

                {/* Odds warning */}
                {signal.odds_favorable === false && (
                  <div className="mb-4 p-3 bg-red-900/20 border border-red-500/30 rounded text-sm">
                    <div className="font-semibold text-red-400 mb-1">Cuota por debajo del mínimo</div>
                    <div className="text-red-400/70 text-xs">
                      La cuota actual ({signal.back_odds?.toFixed(2)}) es menor que la mínima rentable ({signal.min_odds?.toFixed(2)}).
                      Apostar aquí tiene EV negativo. Solo registra si la cuota real en Betfair supera {signal.min_odds?.toFixed(2)}.
                    </div>
                  </div>
                )}
                {signal.back_odds == null && signal.min_odds && (
                  <div className="mb-4 p-3 bg-yellow-900/10 border border-yellow-500/20 rounded text-sm">
                    <div className="font-semibold text-yellow-400 mb-1">Verifica la cuota antes de apostar</div>
                    <div className="text-yellow-400/70 text-xs">
                      Asegúrate de que la cuota en Betfair sea al menos {signal.min_odds.toFixed(2)} para que la apuesta sea rentable.
                    </div>
                  </div>
                )}

                {/* Bet Type */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-zinc-300 mb-2">Tipo de Apuesta</label>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setBetType("paper")}
                      className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                        betType === "paper"
                          ? "bg-blue-600 text-white"
                          : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                      }`}
                    >
                      Paper Trading
                    </button>
                    <button
                      type="button"
                      onClick={() => setBetType("real")}
                      className={`flex-1 py-2 px-4 rounded-lg font-medium transition-colors ${
                        betType === "real"
                          ? "bg-green-600 text-white"
                          : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                      }`}
                    >
                      Real
                    </button>
                  </div>
                </div>

                {/* Stake */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-zinc-300 mb-2">
                    Stake (EUR)
                  </label>
                  <input
                    type="number"
                    value={stake}
                    onChange={(e) => setStake(parseFloat(e.target.value) || 0)}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-100 focus:outline-none focus:border-blue-500"
                    min="0"
                    step="0.01"
                  />
                </div>

                {/* Notes */}
                <div className="mb-6">
                  <label className="block text-sm font-medium text-zinc-300 mb-2">
                    Notas (opcional)
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-zinc-100 focus:outline-none focus:border-blue-500 resize-none"
                    rows={3}
                    placeholder="Añade notas sobre esta apuesta..."
                  />
                </div>

                {/* Actions */}
                <div className="flex gap-3">
                  <button
                    type="button"
                    onClick={() => setShowModal(false)}
                    disabled={saving}
                    className="flex-1 py-2 px-4 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg font-medium transition-colors disabled:opacity-50"
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    onClick={handleAddBet}
                    disabled={saving}
                    className="flex-1 py-2 px-4 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {saving ? (
                      <>
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        <span>Guardando...</span>
                      </>
                    ) : (
                      "Registrar Apuesta"
                    )}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </>
  )
}

function formatConditionKey(key: string): string {
  const labels: Record<string, string> = {
    xg_total: "xG Total",
    possession_diff: "Dif. Posesión",
    total_shots: "Tiros Totales",
    team: "Equipo",
    xg_excess: "xG Excess",
    shots_on_target: "Tiros a Puerta",
    odds_before: "Cuota Antes",
    odds_now: "Cuota Ahora",
    drift_pct: "Drift %",
    goal_minute: "Gol en Min",
    sot_max: "Tiros Puerta Máx",
    total_goals: "Goles Totales",
    minute_range: "Rango Minutos",
    sot_max_threshold: "Mín. Tiros Puerta",
  }
  return labels[key] || key
}

function formatConditionValue(value: any): string {
  if (typeof value === "number") {
    return value.toFixed(2)
  }
  return String(value)
}
