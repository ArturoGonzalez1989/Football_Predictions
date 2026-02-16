import { useState, useEffect } from "react"
import { api, type BettingSignals, type BettingSignal, type PlaceBetRequest } from "../lib/api"

export function BettingSignalsView() {
  const [signals, setSignals] = useState<BettingSignals | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSignals = async () => {
      try {
        const data = await api.getBettingSignals()
        setSignals(data)
        setError(null)
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to fetch signals")
      } finally {
        setLoading(false)
      }
    }

    fetchSignals()
    const interval = setInterval(fetchSignals, 10000) // Refresh every 10s
    return () => clearInterval(interval)
  }, [])

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
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
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
            <SignalCard key={`${signal.match_id}-${signal.strategy}-${idx}`} signal={signal} />
          ))}
        </div>
      )}

      {/* Strategy Legend */}
      <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-zinc-300 mb-3">Estrategias de la Cartera</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs text-zinc-400">
          <div>
            <div className="font-semibold text-zinc-300 mb-1">Back Empate 0-0 (V2r)</div>
            <div>Trigger: 0-0 al min 30+</div>
            <div>Filtros: xG &lt;0.6, Posesión equilibrada, Tiros &lt;8</div>
          </div>
          <div>
            <div className="font-semibold text-zinc-300 mb-1">xG Underperformance (V2)</div>
            <div>Trigger: Equipo perdiendo + xG excess ≥0.5</div>
            <div>Filtro: Tiros a puerta ≥2</div>
          </div>
          <div>
            <div className="font-semibold text-zinc-300 mb-1">Odds Drift Contrarian (V1)</div>
            <div>Trigger: Equipo ganando 1-0 + drift ≥25%</div>
            <div>Apuesta: Back al ganador (mercado lo abandona)</div>
          </div>
          <div>
            <div className="font-semibold text-zinc-300 mb-1">Goal Clustering (V2)</div>
            <div>Trigger: Gol reciente (min 15-80) + SoT max ≥3</div>
            <div>Apuesta: Back Over (total+0.5)</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function SignalCard({ signal }: { signal: BettingSignal }) {
  const [showModal, setShowModal] = useState(false)
  const [betType, setBetType] = useState<"paper" | "real">("paper")
  const [stake, setStake] = useState(10)
  const [notes, setNotes] = useState("")
  const [saving, setSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  const confidenceColors = {
    high: "text-green-400 bg-green-500/10 border-green-500/20",
    medium: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
    low: "text-orange-400 bg-orange-500/10 border-orange-500/20",
  }

  const confidenceColor = confidenceColors[signal.confidence]

  const handleAddBet = async () => {
    try {
      setSaving(true)
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
      <div className={`border rounded-lg p-4 ${confidenceColor}`}>
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

      {/* GO/NO-GO Decision */}
      {signal.odds_favorable !== undefined && signal.back_odds && (
        <div className={`mb-3 p-3 rounded border ${
          signal.odds_favorable
            ? 'bg-green-900/20 border-green-500/30'
            : 'bg-red-900/20 border-red-500/30'
        }`}>
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-zinc-400 mb-1">Veredicto</div>
              <div className={`text-xl font-bold ${
                signal.odds_favorable ? 'text-green-400' : 'text-red-400'
              }`}>
                {signal.odds_favorable ? '✅ APOSTAR' : '❌ NO APOSTAR'}
              </div>
              {signal.odds_favorable && signal.expected_value && (
                <div className="text-xs text-zinc-400 mt-1">
                  EV: +{signal.expected_value.toFixed(2)} EUR por apuesta de 10 EUR
                </div>
              )}
              {!signal.odds_favorable && (
                <div className="text-xs text-zinc-400 mt-1">
                  Cuota insuficiente (EV negativo)
                </div>
              )}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setShowModal(true)}
                className="px-4 py-2 font-semibold rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors flex items-center gap-2 shrink-0"
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
                  signal.odds_favorable
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
      )}

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
                </div>

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
