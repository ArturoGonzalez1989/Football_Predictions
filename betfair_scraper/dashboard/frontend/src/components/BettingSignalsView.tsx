import { useState, useEffect, useRef, useCallback } from "react"
import { api, type BettingSignals, type BettingSignal, type WatchlistItem, type CarteraConfig } from "../lib/api"
import { playSignalAlert } from "../lib/sounds"
// ── Version combo types (inlined from removed cartera.ts) ────────────────────
interface VersionCombo {
  draw: string
  xg: string
  drift: string
  clustering: string
  pressure: string
  tardeAsia: string
  momentumXG: string
  br: string
}

function comboToSignalVersions(combo: VersionCombo): Record<string, string> {
  return {
    draw: combo.draw,
    xg: combo.xg,
    drift: combo.drift,
    clustering: combo.clustering,
    pressure: combo.pressure,
    momentum: combo.momentumXG ?? "v1",
  }
}

const DEFAULT_COMBO: VersionCombo = {
  draw: "v2r", xg: "base", drift: "v1", clustering: "v2", pressure: "v1", tardeAsia: "off", momentumXG: "off", br: "fixed"
}


// ── Market-based dedup key ────────────────────────────────────────────────────
// Mirrors cartera.ts betMarketKey() logic so live registration and backtest
// analysis use the same discriminator: 1 bet per match per MARKET, not per strategy.
function signalMarketKey(matchId: string, recommendation: string): string {
  const rec = (recommendation ?? "").toUpperCase()
  if (rec.includes("DRAW")) return `${matchId}:draw`
  if (rec.includes("HOME")) return `${matchId}:home`
  if (rec.includes("AWAY")) return `${matchId}:away`
  const m = rec.match(/OVER\s+(\d+\.?\d*)/)
  if (m) return `${matchId}:over_${m[1]}`
  return `${matchId}:unknown`
}

// Recommended min durations — overridden by backend config on load
export type MinDurConfig = { draw: number; xg: number; drift: number; clustering: number; pressure: number }
const DEFAULT_MIN_DUR: MinDurConfig = { draw: 1, xg: 2, drift: 2, clustering: 4, pressure: 2 }

export function BettingSignalsView() {
  const [signals, setSignals] = useState<BettingSignals | null>(null)
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [combo, setCombo] = useState<VersionCombo>(DEFAULT_COMBO)
  const [minDur, setMinDur] = useState<MinDurConfig>(DEFAULT_MIN_DUR)
  const [activeConfig, setActiveConfig] = useState<CarteraConfig | null>(null)
  const [bankroll, setBankroll] = useState<number>(100)
  const [stakePct, setStakePct] = useState<number>(1)
  const [stakeFixed, setStakeFixed] = useState<number>(2)
  const [stakeMode, setStakeMode] = useState<"pct" | "fixed">("pct")
  const [effectiveBankroll, setEffectiveBankroll] = useState<number>(100)
  const [stakeConfigSaved, setStakeConfigSaved] = useState(false)
  const prevSignalKeys = useRef<Set<string> | null>(null)
  // Track auto-registered paper bets to avoid duplicates across polling cycles
  const autoRegisteredRef = useRef<Set<string>>(new Set())
  // On first fetch, pre-populate autoRegistered with already-mature signals so we don't retroactively register them
  const firstFetchDoneRef = useRef(false)
  const activeConfigRef = useRef<CarteraConfig | null>(null)
  const effectiveBankrollRef = useRef<number>(100)
  const comboRef = useRef(combo)
  comboRef.current = combo
  const minDurRef = useRef(minDur)
  minDurRef.current = minDur
  const configLoadedRef = useRef(false)

  // Load config from backend on mount (single source of truth)
  useEffect(() => {
    if (configLoadedRef.current) return
    configLoadedRef.current = true
    Promise.all([api.getConfig(), api.getManualBets().catch(() => null)])
      .then(([cfg, manualData]) => {
        setActiveConfig(cfg)
        activeConfigRef.current = cfg
        const initBr = cfg.initial_bankroll ?? 100
        if (cfg.initial_bankroll != null) setBankroll(cfg.initial_bankroll)
        if (cfg.stake_pct != null) setStakePct(cfg.stake_pct)
        if ((cfg as any).stake_fixed != null) setStakeFixed((cfg as any).stake_fixed)
        if ((cfg as any).stake_mode === "fixed") setStakeMode("fixed")
        // Effective bankroll = initial + cumulative P/L from resolved manual bets
        const manualPL = (manualData?.bets ?? [])
          .filter(b => b.status !== "pending" && b.pl != null)
          .reduce((sum, b) => sum + (b.pl ?? 0), 0)
        const effBr = Math.max(1, Math.round((initBr + manualPL) * 100) / 100)
        setEffectiveBankroll(effBr)
        effectiveBankrollRef.current = effBr
        const v = cfg.versions ?? {}
        const s = cfg.strategies ?? {}
        const newCombo: VersionCombo = {
          draw: (v.draw || (s.draw?.enabled === false ? "off" : "v1")) as any,
          xg: (v.xg || (s.xg?.enabled === false ? "off" : "base")) as any,
          drift: (v.drift || (s.drift?.enabled === false ? "off" : "v1")) as any,
          clustering: (v.clustering || (s.clustering?.enabled === false ? "off" : "v2")) as any,
          pressure: (v.pressure || (s.pressure?.enabled === false ? "off" : "v1")) as any,
          tardeAsia: (v.tarde_asia || (s.tarde_asia?.enabled ? "v1" : "off")) as any,
          momentumXG: (s.momentum_xg?.version || v.momentum_xg || "off") as any,
          br: cfg.bankroll_mode as any,
        }
        const newMinDur: MinDurConfig = {
          draw: cfg.min_duration.draw ?? 1,
          xg: cfg.min_duration.xg ?? 2,
          drift: cfg.min_duration.drift ?? 2,
          clustering: cfg.min_duration.clustering ?? 4,
          pressure: cfg.min_duration.pressure ?? 2,
        }
        setCombo(newCombo)
        comboRef.current = newCombo
        setMinDur(newMinDur)
        minDurRef.current = newMinDur
      })
      .catch(() => { /* backend unreachable — keep defaults */ })
  }, [])

  const fetchSignals = useCallback(async () => {
    try {
      const versions = comboToSignalVersions(comboRef.current)
      const [data, wl] = await Promise.all([
        api.getBettingSignals(versions, minDurRef.current),
        api.getWatchlist(versions),
      ])
      setSignals(data)
      setWatchlist(wl)
      setError(null)

      // Check for NEW signals (alert sound)
      const currentKeys = new Set(
        (data.signals || []).map((s) => `${s.match_id}:${s.strategy}`)
      )
      if (prevSignalKeys.current !== null) {
        const hasNew = [...currentKeys].some((k) => !prevSignalKeys.current!.has(k))
        if (hasNew) playSignalAlert()
      }
      prevSignalKeys.current = currentKeys

      // Auto-register mature signals as paper bets — ONLY when odds are favorable (green, not red)
      // On first fetch, mark ALL mature signals (favorable or not) as already seen to avoid retroactive registration
      const allMature = (data.signals || []).filter(s => s.is_mature === true)
      const matureSignals = allMature.filter(s => s.odds_favorable === true)
      if (!firstFetchDoneRef.current) {
        firstFetchDoneRef.current = true
        allMature.forEach(s => autoRegisteredRef.current.add(signalMarketKey(s.match_id, s.recommendation)))
      } else {
        const cfg = activeConfigRef.current
        const bl = effectiveBankrollRef.current
        const pct = cfg?.stake_pct ?? 1
        const stake = (cfg as any)?.stake_mode === "fixed"
          ? Math.max(0.01, (cfg as any)?.stake_fixed ?? 2)
          : Math.max(0.01, Math.round(bl * pct / 100 * 100) / 100)
        // Conflict filter: skip Momentum XG when xG Underperf is also mature for the same match (0% WR pair)
        const matureXGUnderperf = new Set(
          matureSignals.filter(s => s.strategy === "xg_underperformance").map(s => s.match_id)
        )
        for (const sig of matureSignals) {
          if ((sig.strategy === "momentum_xg_v1" || sig.strategy === "momentum_xg_v2")
              && matureXGUnderperf.has(sig.match_id)) {
            continue
          }
          const key = signalMarketKey(sig.match_id, sig.recommendation)
          if (autoRegisteredRef.current.has(key)) continue
          autoRegisteredRef.current.add(key)
          api.placeBet({
          match_id: sig.match_id,
          match_name: sig.match_name,
          match_url: sig.match_url,
          strategy: sig.strategy,
          strategy_name: sig.strategy_name,
          minute: sig.minute,
          score: sig.score,
          recommendation: sig.recommendation,
          back_odds: sig.back_odds,
          min_odds: sig.min_odds,
          expected_value: sig.expected_value,
          confidence: sig.confidence,
          win_rate_historical: sig.win_rate_historical,
          roi_historical: sig.roi_historical,
          sample_size: sig.sample_size,
          entry_conditions: sig.entry_conditions,
          thresholds: sig.thresholds,
          bet_type: "paper",
          stake,
          notes: "Auto-registrado",
          }).catch((err) => {
            // 409 = duplicate (backend dedup) — keep in set to avoid retrying
            // Any other error: remove from set so it retries next cycle
            if (!String(err?.message).includes("409")) {
              autoRegisteredRef.current.delete(key)
            }
          })
        }
      }
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

  // Re-fetch when combo or minDur changes
  useEffect(() => {
    fetchSignals()
  }, [combo, minDur]) // eslint-disable-line react-hooks/exhaustive-deps

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

      {/* Stake config box */}
      <div className="flex items-center gap-3 mb-6 px-4 py-3 bg-zinc-900/50 border border-zinc-800 rounded-lg flex-wrap">
        <span className="text-xs text-zinc-500 font-medium uppercase tracking-wide shrink-0">Stake</span>

        {/* Mode toggle */}
        <div className="flex items-center rounded-md border border-zinc-700 overflow-hidden shrink-0">
          <button
            type="button"
            onClick={() => setStakeMode("pct")}
            className={`px-2.5 py-1 text-xs font-medium transition-colors ${stakeMode === "pct" ? "bg-zinc-600 text-zinc-100" : "bg-zinc-800 text-zinc-500 hover:text-zinc-300"}`}
          >
            %
          </button>
          <button
            type="button"
            onClick={() => setStakeMode("fixed")}
            className={`px-2.5 py-1 text-xs font-medium transition-colors ${stakeMode === "fixed" ? "bg-zinc-600 text-zinc-100" : "bg-zinc-800 text-zinc-500 hover:text-zinc-300"}`}
          >
            €
          </button>
        </div>

        {stakeMode === "pct" ? (
          <>
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-zinc-500">Bankroll</span>
              <input
                type="number"
                min={1}
                step={10}
                value={bankroll}
                title="Bankroll inicial en euros"
                placeholder="100"
                onChange={e => setBankroll(Math.max(1, Number(e.target.value)))}
                className="w-24 px-2 py-1 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-100 focus:outline-none focus:border-zinc-500"
              />
              <span className="text-xs text-zinc-600">€</span>
            </div>
            {!isNaN(effectiveBankroll) && effectiveBankroll !== bankroll && (
              <div className="flex items-center gap-1">
                <span className="text-xs text-zinc-600">→</span>
                <span className={`text-xs font-mono font-bold ${effectiveBankroll > bankroll ? "text-green-400" : "text-red-400"}`}>
                  {effectiveBankroll.toFixed(2)}€
                </span>
              </div>
            )}
            <span className="text-zinc-700">×</span>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={0.1}
                max={100}
                step={0.5}
                value={stakePct}
                title="Stake en % del bankroll"
                placeholder="1"
                onChange={e => setStakePct(Math.max(0.1, Math.min(100, Number(e.target.value))))}
                className="w-16 px-2 py-1 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-100 focus:outline-none focus:border-zinc-500"
              />
              <span className="text-xs text-zinc-500">%</span>
            </div>
            <span className="text-zinc-700">=</span>
            <span className="text-sm font-bold text-amber-400">
              {Math.max(0.01, Math.round((isNaN(effectiveBankroll) ? bankroll : effectiveBankroll) * stakePct / 100 * 100) / 100).toFixed(2)} €/apuesta
            </span>
          </>
        ) : (
          <>
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={0.01}
                step={0.5}
                value={stakeFixed}
                title="Stake fijo por apuesta"
                placeholder="2"
                onChange={e => setStakeFixed(Math.max(0.01, Number(e.target.value)))}
                className="w-20 px-2 py-1 text-xs bg-zinc-800 border border-zinc-700 rounded text-zinc-100 focus:outline-none focus:border-zinc-500"
              />
              <span className="text-sm font-bold text-amber-400">€/apuesta</span>
            </div>
          </>
        )}

        <button
          type="button"
          onClick={async () => {
            if (!activeConfig) return
            const updated = {
              ...activeConfig,
              initial_bankroll: bankroll,
              stake_pct: stakePct,
              bankroll_mode: stakeMode === "pct" ? "pct" : "fixed",
              stake_mode: stakeMode,
              stake_fixed: stakeFixed,
            } as CarteraConfig & { stake_mode: string; stake_fixed: number }
            await api.saveConfig(updated as CarteraConfig)
            setActiveConfig(updated as CarteraConfig)
            activeConfigRef.current = updated as CarteraConfig
            setStakeConfigSaved(true)
            setTimeout(() => setStakeConfigSaved(false), 2000)
          }}
          className="ml-auto px-3 py-1 text-xs font-bold rounded bg-zinc-700 border border-zinc-600 text-zinc-300 hover:bg-zinc-600 transition-colors"
        >
          {stakeConfigSaved ? "✓ Guardado" : "Guardar"}
        </button>
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
              {(() => {
                // Detect conflict: matches where both momentum_xg AND xg_underperformance fire
                const matchesWithXGUnderf = new Set(
                  activeSignals.filter(s => s.strategy === "xg_underperformance").map(s => s.match_id)
                )
                const matchesWithMomXG = new Set(
                  activeSignals.filter(s => s.strategy === "momentum_xg_v1" || s.strategy === "momentum_xg_v2").map(s => s.match_id)
                )
                const conflictMatchIds = new Set(
                  [...matchesWithXGUnderf].filter(id => matchesWithMomXG.has(id))
                )
                return activeSignals.map((signal, idx) => {
                  const hasConflict = conflictMatchIds.has(signal.match_id) &&
                    (signal.strategy === "momentum_xg_v1" || signal.strategy === "momentum_xg_v2")
                  return (
                    <SignalCard key={`${signal.match_id}-${signal.strategy}-${idx}`} signal={signal} hasConflict={hasConflict} />
                  )
                })
              })()}
            </div>
          )}

          {/* Active Strategy Criteria (read from saved cartera config) */}
          <ActiveCriteriaBlock activeConfig={activeConfig} />
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

// ── Strategy label/color map — covers all strategies in cartera_config.json ──
const STRATEGY_LABELS: Record<string, { label: string; color: string }> = {
  // Legacy 7
  draw:                 { label: "Back Empate 0-0",       color: "text-cyan-400" },
  xg:                   { label: "xG Underperf.",         color: "text-amber-400" },
  drift:                { label: "Odds Drift",            color: "text-emerald-400" },
  clustering:           { label: "Goal Clustering (v1)",  color: "text-rose-400" },
  pressure:             { label: "Pressure Cooker (v1)",  color: "text-orange-400" },
  tarde_asia:           { label: "Tarde Asia",            color: "text-sky-400" },
  momentum_xg:          { label: "Momentum xG",           color: "text-violet-400" },
  // New strategies
  over25_2goal:         { label: "Back Over 2.5 2G lead", color: "text-lime-400" },
  under35_late:         { label: "Back Under 3.5 late",   color: "text-teal-400" },
  longshot:             { label: "Back Longshot",         color: "text-pink-400" },
  cs_close:             { label: "Back CS Close",         color: "text-indigo-400" },
  cs_one_goal:          { label: "Back CS 1-0/0-1",       color: "text-amber-300" },
  ud_leading:           { label: "Back Underdog Lead",    color: "text-red-300" },
  home_fav_leading:     { label: "Back Home Fav.",        color: "text-blue-400" },
  cs_20:                { label: "Back CS 2-0/0-2",       color: "text-cyan-300" },
  cs_big_lead:          { label: "Back CS Big Lead",      color: "text-emerald-300" },
  goal_clustering:      { label: "Goal Clustering",       color: "text-rose-400" },
  pressure_cooker:      { label: "Pressure Cooker",       color: "text-orange-400" },
  draw_xg_conv:         { label: "Back Draw xG Conv",     color: "text-cyan-400" },
  cs_00:                { label: "Back CS 0-0",           color: "text-zinc-400" },
  over25_2goals:        { label: "Back Over 2.5 2G",      color: "text-zinc-400" },
  cs_11:                { label: "Back CS 1-1",           color: "text-zinc-400" },
  lay_over45_v3:        { label: "LAY Over 4.5 v3",       color: "text-red-400" },
  poss_extreme:         { label: "Back Poss. Extreme",    color: "text-purple-400" },
  draw_11:              { label: "Back Draw 1-1",         color: "text-cyan-300" },
  under35_3goals:       { label: "Back Under 3.5 3G",     color: "text-teal-300" },
  away_fav_leading:     { label: "Back Away Fav.",        color: "text-sky-400" },
  under45_3goals:       { label: "Back Under 4.5 3G",     color: "text-teal-400" },
  draw_equalizer:       { label: "Back Draw Equalizer",   color: "text-cyan-400" },
  draw_22:              { label: "Back Draw 2-2",         color: "text-cyan-300" },
  lay_over45_blowout:   { label: "LAY Over 4.5 Blowout",  color: "text-red-400" },
  over35_early_goals:   { label: "Back Over 3.5 Early",   color: "text-lime-300" },
  lay_draw_away_leading:{ label: "LAY Draw Away Lead",    color: "text-red-400" },
  lay_cs11:             { label: "LAY CS 1-1",            color: "text-red-300" },
}

function strategyCriteria(cfg: Record<string, any>): string[] {
  const c: string[] = []
  const mMin = cfg.minuteMin ?? cfg.m_min ?? 0
  const mMax = cfg.minuteMax ?? cfg.m_max ?? 90
  if (mMin > 0 || mMax < 90) c.push(`Min ${mMin}–${mMax < 90 ? mMax : "FT"}`)
  if (cfg.xgMax != null && cfg.xgMax < 5)     c.push(`xG < ${cfg.xgMax}`)
  if (cfg.xg_diff_max != null)                c.push(`xG diff ≤ ${cfg.xg_diff_max}`)
  if (cfg.sotMin != null && cfg.sotMin > 0)   c.push(`SoT ≥ ${cfg.sotMin}`)
  if (cfg.goalDiffMin != null && cfg.goalDiffMin > 0) c.push(`GD ≥ ${cfg.goalDiffMin}`)
  if (cfg.goals_min != null)                  c.push(`G ${cfg.goals_min}–${cfg.goals_max ?? "+"}`)
  if (cfg.poss_min != null)                   c.push(`Pos ≥ ${cfg.poss_min}%`)
  if (cfg.fav_max != null)                    c.push(`Fav ≤ ${cfg.fav_max}`)
  if (cfg.max_lead != null)                   c.push(`Ventaja ≤ ${cfg.max_lead}G`)
  if (cfg.odds_min != null && cfg.odds_max != null) c.push(`Odds ${cfg.odds_min}–${cfg.odds_max}`)
  else if (cfg.odds_min != null)              c.push(`Odds ≥ ${cfg.odds_min}`)
  else if (cfg.odds_max != null && cfg.odds_max < 30) c.push(`Odds ≤ ${cfg.odds_max}`)
  return c
}

// ── ActiveCriteriaBlock ───────────────────────────────────────────────────────
function ActiveCriteriaBlock({ activeConfig }: { activeConfig: CarteraConfig | null }) {
  const strategies = activeConfig?.strategies ?? {}
  const activeKeys = Object.keys(strategies).filter(k => strategies[k]?.enabled !== false)
  const adj = activeConfig?.adjustments

  return (
    <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-zinc-300">
          Cartera activa
          <span className="text-zinc-600 font-normal ml-2 text-[10px]">{activeKeys.length} activas</span>
        </h3>
        <span className="text-[10px] text-zinc-600">
          Configura en{" "}
          <span className="text-zinc-400">Strategies → Cartera de Estrategias</span>
        </span>
      </div>

      <div className="space-y-1.5">
        {activeKeys.map(k => {
          const meta = STRATEGY_LABELS[k] ?? { label: k, color: "text-zinc-400" }
          const criteria = strategyCriteria(strategies[k] ?? {})
          return (
            <div key={k} className="flex items-start gap-2">
              <span className={`text-[11px] font-semibold min-w-[170px] shrink-0 ${meta.color}`}>
                {meta.label}
              </span>
              <div className="flex-1 flex flex-wrap items-center gap-y-0.5">
                {criteria.map((c, i) => (
                  <span key={i} className="text-[11px] text-zinc-400">
                    {i > 0 && <span className="text-zinc-700 mx-1">·</span>}
                    {c}
                  </span>
                ))}
              </div>
            </div>
          )
        })}

      </div>

      {/* Risk filter + realistic mode */}
      {activeConfig && (
        <div className="mt-3 pt-2.5 border-t border-zinc-800/60 space-y-1.5">
          {/* Risk filter */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-zinc-500 font-medium min-w-[110px]">Filtro de riesgo:</span>
            {(() => {
              const rf = activeConfig.risk_filter
              const labels: Record<string, { label: string; color: string }> = {
                all:       { label: "Todas las apuestas", color: "text-zinc-400" },
                no_risk:   { label: "Sin riesgo",         color: "text-emerald-400" },
                with_risk: { label: "Con riesgo",         color: "text-amber-400" },
                medium:    { label: "Riesgo medio",       color: "text-amber-400" },
                high:      { label: "Alto riesgo",        color: "text-red-400" },
              }
              const { label, color } = labels[rf] ?? { label: rf, color: "text-zinc-400" }
              return <span className={`text-[10px] font-medium ${color}`}>{label}</span>
            })()}
          </div>

          {/* Realistic mode */}
          <div className="flex items-start gap-2">
            <span className="text-[10px] text-zinc-500 font-medium min-w-[110px] pt-px">Modo realista:</span>
            {adj?.enabled ? (
              <div className="flex flex-wrap gap-x-2 gap-y-0.5">
                <span className="text-[10px] text-blue-400 font-medium">ON</span>
                {adj.min_odds != null && <span className="text-[10px] text-zinc-500">· Odds mín {adj.min_odds}</span>}
                {adj.max_odds != null && <span className="text-[10px] text-zinc-500">· Odds máx {adj.max_odds}</span>}
                {adj.slippage_pct > 0 && <span className="text-[10px] text-zinc-500">· Slippage {adj.slippage_pct}%</span>}
                {adj.dedup && <span className="text-[10px] text-zinc-500">· Dedup</span>}
                {adj.conflict_filter && <span className="text-[10px] text-zinc-500">· Anti-conflicto</span>}
                {adj.allow_contrarias === false && <span className="text-[10px] text-zinc-500">· Sin contrarias</span>}
                {(adj.stability ?? 1) > 1 && <span className="text-[10px] text-zinc-500">· Estab. ≥ {adj.stability}</span>}
                {adj.drift_min_minute != null && adj.drift_min_minute > 0 && <span className="text-[10px] text-zinc-500">· Drift mín min {adj.drift_min_minute}</span>}
                {(adj.global_minute_min != null || adj.global_minute_max != null) && (
                  <span className="text-[10px] text-zinc-500">
                    · Rango min {adj.global_minute_min ?? 0}–{adj.global_minute_max ?? 90}
                  </span>
                )}
                {adj.cashout_minute != null && <span className="text-[10px] text-zinc-500">· Cash-out min {adj.cashout_minute}</span>}
                {adj.cashout_pct != null && <span className="text-[10px] text-cyan-600">· CO umbral {adj.cashout_pct}%</span>}
              </div>
            ) : (
              <span className="text-[10px] text-zinc-600">OFF — sin filtros adicionales</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function SignalCard({ signal, hasConflict = false }: { signal: BettingSignal; hasConflict?: boolean }) {

  const isMature = signal.is_mature === true

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

  return (
    <div className={`border rounded-lg p-4 ${cardBorderColor} ${cardBgColor}`}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
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
            <SignalAgeBadge
              ageMinutes={signal.signal_age_minutes}
              minDurationCaps={signal.min_duration_caps}
              isMature={signal.is_mature}
            />
            {hasConflict && (
              <span
                className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-bold bg-red-900/40 text-red-400 border border-red-500/40"
                title="Par toxico detectado: MomXG + xG Underperf en el mismo partido tuvieron 0% WR historicamente. No apostar ambos."
              >
                ⚠ Conflicto
              </span>
            )}
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
              <div className="flex flex-col items-end gap-1.5">
                {isMature && (
                  <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/30">
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    Paper auto
                  </span>
                )}
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
  )
}

// eslint-disable-next-line @typescript-eslint/no-unused-vars

function SignalAgeBadge({
  ageMinutes,
  minDurationCaps,
  isMature,
}: {
  ageMinutes?: number
  minDurationCaps?: number
  isMature?: boolean
}) {
  if (ageMinutes === undefined || ageMinutes === null) return null

  const age = Math.round(ageMinutes)
  const minDur = minDurationCaps ?? 1

  // Color + label based on maturity
  let badgeClass: string
  let icon: string
  let title: string

  if (isMature) {
    badgeClass = "bg-green-500/15 text-green-400 border border-green-500/30"
    icon = "●"
    title = `Señal estable: lleva ${age} min activa (umbral: ${minDur} min)`
  } else if (age >= Math.ceil(minDur * 0.5)) {
    // halfway there
    badgeClass = "bg-amber-500/15 text-amber-400 border border-amber-500/30"
    icon = "◑"
    title = `Señal madurando: ${age} min activa, umbral ${minDur} min`
  } else {
    badgeClass = "bg-zinc-700/50 text-zinc-500 border border-zinc-600/30"
    icon = "○"
    title = `Señal reciente: ${age} min activa, umbral ${minDur} min`
  }

  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full font-medium ${badgeClass}`}
      title={title}
    >
      <span className="text-[8px]">{icon}</span>
      {age === 0 ? "<1 min" : `${age} min`}
    </span>
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
