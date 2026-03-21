import React, { useState, useEffect, useRef, useCallback } from "react"
import { api, type BettingSignals, type BettingSignal, type WatchlistItem, type CarteraConfig } from "../lib/api"
import { playSignalAlert } from "../lib/sounds"
// ── Strategy enable/disable combo ────────────────────────────────────────────
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
    draw: combo.draw === "off" ? "off" : "on",
    xg: combo.xg === "off" ? "off" : "on",
    drift: combo.drift === "off" ? "off" : "on",
    clustering: combo.clustering === "off" ? "off" : "on",
    pressure: combo.pressure === "off" ? "off" : "on",
    momentum: combo.momentumXG === "off" ? "off" : "on",
  }
}

const DEFAULT_COMBO: VersionCombo = {
  draw: "off", xg: "on", drift: "on", clustering: "on", pressure: "on", tardeAsia: "off", momentumXG: "off", br: "fixed"
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
// Keys use legacy short names for API query params compatibility
export type MinDurConfig = { draw: number; xg: number; drift: number; clustering: number; pressure: number }
const DEFAULT_MIN_DUR: MinDurConfig = { draw: 2, xg: 3, drift: 2, clustering: 4, pressure: 4 }

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
  const [autoOpenBets, setAutoOpenBets] = useState(false)
  const prevSignalKeys = useRef<Set<string> | null>(null)
  // Track auto-opened browser tabs to avoid duplicates across polling cycles
  const autoOpenedRef = useRef<Set<string>>(new Set())
  // On first fetch, pre-populate autoRegistered with already-mature signals so we don't retroactively register them
  const firstFetchDoneRef = useRef(false)
  const autoOpenBetsRef = useRef(false)
  autoOpenBetsRef.current = autoOpenBets
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
    api.getConfig()
      .then((cfg) => {
        setActiveConfig(cfg)
        activeConfigRef.current = cfg
        const initBr = cfg.initial_bankroll ?? 100
        if (cfg.initial_bankroll != null) setBankroll(cfg.initial_bankroll)
        if (cfg.stake_pct != null) setStakePct(cfg.stake_pct)
        if ((cfg as any).stake_fixed != null) setStakeFixed((cfg as any).stake_fixed)
        if ((cfg as any).stake_mode === "fixed") setStakeMode("fixed")
        const effBr = Math.max(1, Math.round(initBr * 100) / 100)
        setEffectiveBankroll(effBr)
        effectiveBankrollRef.current = effBr
        const s = cfg.strategies ?? {}
        const newCombo: VersionCombo = {
          draw: s.back_draw_00?.enabled ? "on" : "off",
          xg: s.xg_underperformance?.enabled ? "on" : "off",
          drift: s.odds_drift?.enabled ? "on" : "off",
          clustering: s.goal_clustering?.enabled ? "on" : "off",
          pressure: s.pressure_cooker?.enabled ? "on" : "off",
          tardeAsia: s.tarde_asia?.enabled ? "on" : "off",
          momentumXG: s.momentum_xg?.enabled ? "on" : "off",
          br: cfg.bankroll_mode as any,
        }
        const newMinDur: MinDurConfig = {
          draw: cfg.min_duration.back_draw_00 ?? 1,
          xg: cfg.min_duration.xg_underperformance ?? 2,
          drift: cfg.min_duration.odds_drift ?? 2,
          clustering: cfg.min_duration.goal_clustering ?? 4,
          pressure: cfg.min_duration.pressure_cooker ?? 2,
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

      // Auto-open browser: open Betfair match URL for each new mature+favorable signal
      // Paper bet placement is handled exclusively by the backend background task (run_paper_auto_place)
      const allMature = (data.signals || []).filter(s => s.is_mature === true)
      const matureSignals = allMature.filter(s => s.odds_favorable === true)
      if (!firstFetchDoneRef.current) {
        firstFetchDoneRef.current = true
        allMature.forEach(s => {
          autoOpenedRef.current.add(signalMarketKey(s.match_id, s.recommendation))
        })
      } else {
        if (autoOpenBetsRef.current) {
          for (const sig of matureSignals) {
            const key = signalMarketKey(sig.match_id, sig.recommendation)
            if (autoOpenedRef.current.has(key)) continue
            if (!sig.match_url) continue
            autoOpenedRef.current.add(key)
            api.openBet(sig.match_url).catch(() => {})
          }
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
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-xs text-zinc-500">Partidos en vivo</div>
            <div className="text-lg font-bold text-blue-400">{liveMatches}</div>
          </div>
          <div className="text-right">
            <div className="text-xs text-zinc-500">Señales activas</div>
            <div className="text-lg font-bold text-green-400">{activeSignals.length}</div>
          </div>
          {/* Auto-open toggle */}
          <button
            type="button"
            onClick={() => setAutoOpenBets(v => {
              if (!v) autoOpenedRef.current = new Set() // reset so existing signals re-evaluate on next cycle
              return !v
            })}
            title={autoOpenBets ? "Auto-abrir activo: abre Betfair al detectar señal" : "Auto-abrir desactivado"}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs font-medium transition-colors ${
              autoOpenBets
                ? "bg-amber-500/15 border-amber-500/40 text-amber-400 hover:bg-amber-500/25"
                : "bg-zinc-900 border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600"
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${autoOpenBets ? "bg-amber-400 animate-pulse" : "bg-zinc-600"}`} />
            Auto-abrir
          </button>
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

      {/* Signals two-column layout + Watchlist sidebar */}
      {(() => {
        // Conflict detection — shared across both columns
        const matchesWithXGUnderf = new Set(
          activeSignals.filter(s => s.strategy === "xg_underperformance").map(s => s.match_id)
        )
        const matchesWithMomXG = new Set(
          activeSignals.filter(s => s.strategy === "momentum_xg").map(s => s.match_id)
        )
        const conflictMatchIds = new Set(
          [...matchesWithXGUnderf].filter(id => matchesWithMomXG.has(id))
        )
        const maturingSignals = activeSignals.filter(s => s.is_mature !== true)
        const matureSignals = activeSignals.filter(s => s.is_mature === true)

        return (
          <div className="flex gap-4">
            {/* Column 1 — Maturing */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-3">
                <span className="w-2 h-2 rounded-full bg-amber-400/70 shrink-0" />
                <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">En maduración</h2>
                <span className="text-[10px] text-zinc-600">confirmación pendiente</span>
                {maturingSignals.length > 0 && (
                  <span className="ml-auto text-[10px] font-mono text-zinc-500">{maturingSignals.length}</span>
                )}
              </div>
              {maturingSignals.length === 0 ? (
                <div className="bg-zinc-900/20 border border-zinc-800/40 border-dashed rounded-lg p-6 text-center">
                  <div className="text-zinc-700 text-xs">Sin señales madurando</div>
                  {activeSignals.length === 0 && (
                    <div className="text-zinc-600 text-xs mt-1">
                      Monitoreando {liveMatches} {liveMatches === 1 ? "partido" : "partidos"} en vivo
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {maturingSignals.map((signal, idx) => (
                    <SignalCard
                      key={`${signal.match_id}-${signal.strategy}-${idx}`}
                      signal={signal}
                      hasConflict={conflictMatchIds.has(signal.match_id) && signal.strategy === "momentum_xg"}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Column 2 — Mature / Active */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-3">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse shrink-0" />
                <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Activas</h2>
                <span className="text-[10px] text-zinc-600">señales confirmadas</span>
                {matureSignals.length > 0 && (
                  <span className="ml-auto text-[10px] font-mono text-green-500">{matureSignals.length}</span>
                )}
              </div>
              {matureSignals.length === 0 ? (
                <div className="bg-zinc-900/20 border border-zinc-800/40 border-dashed rounded-lg p-6 text-center">
                  <div className="text-zinc-700 text-xs">Sin señales activas</div>
                </div>
              ) : (
                <div className="space-y-3">
                  {matureSignals.map((signal, idx) => (
                    <SignalCard
                      key={`${signal.match_id}-${signal.strategy}-${idx}`}
                      signal={signal}
                      hasConflict={conflictMatchIds.has(signal.match_id) && signal.strategy === "momentum_xg"}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Watchlist sidebar */}
            <div className="w-64 shrink-0">
              <WatchlistSidebar items={watchlist} />
            </div>
          </div>
        )
      })()}

      {/* Active Strategy Criteria */}
      <ActiveCriteriaBlock activeConfig={activeConfig} />
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
  const xgMax = cfg.xgMax ?? cfg.xg_max
  if (xgMax != null && xgMax < 5)             c.push(`xG < ${xgMax}`)
  if (cfg.xg_diff_max != null)                c.push(`xG diff ≤ ${cfg.xg_diff_max}`)
  const sotMin = cfg.sotMin ?? cfg.sot_min
  if (sotMin != null && sotMin > 0)           c.push(`SoT ≥ ${sotMin}`)
  const gdMin = cfg.goalDiffMin ?? cfg.goal_diff_min
  if (gdMin != null && gdMin > 0)             c.push(`GD ≥ ${gdMin}`)
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

function OpenBetButton({ matchUrl, isFavorable, recommendation, matchName }: { matchUrl: string; isFavorable: boolean; recommendation?: string; matchName?: string }) {
  const [status, setStatus] = useState<"idle" | "loading" | "ok" | "err">("idle")
  const handleClick = async () => {
    setStatus("loading")
    try {
      await api.openBet(matchUrl, recommendation, matchName)
      setStatus("ok")
      setTimeout(() => setStatus("idle"), 2000)
    } catch {
      // fallback: open directly in browser tab
      window.open(matchUrl, "_blank")
      setStatus("err")
      setTimeout(() => setStatus("idle"), 2000)
    }
  }
  const label = status === "loading" ? "..." : status === "ok" ? "✓" : status === "err" ? "↗" : "Abrir Bot"
  const cls = isFavorable ? "bg-green-600 hover:bg-green-500 text-white" : "bg-zinc-700 hover:bg-zinc-600 text-zinc-300"
  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={status === "loading"}
      title={status === "err" ? "Bot falló — abierto en pestaña" : "Abrir en Betfair vía bot"}
      className={`px-2.5 py-1.5 text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5 disabled:opacity-60 ${cls}`}
    >
      {status === "idle" && (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
        </svg>
      )}
      {label}
    </button>
  )
}

function SignalCard({ signal, hasConflict = false }: { signal: BettingSignal; hasConflict?: boolean }) {
  const [expanded, setExpanded] = React.useState(false)
  const isMature = signal.is_mature === true
  const isFavorable = signal.odds_favorable === true
  const isUnfavorable = signal.odds_favorable === false
const riskLevel = signal.risk_info?.risk_level || "none"

  let cardBorderColor: string
  let cardBgColor: string
  if (riskLevel === "high") {
    cardBorderColor = "border-red-500/40"; cardBgColor = "bg-red-500/5"
  } else if (riskLevel === "medium") {
    cardBorderColor = "border-orange-500/40"; cardBgColor = "bg-orange-500/5"
  } else {
    cardBorderColor = "border-zinc-700/40"; cardBgColor = "bg-zinc-800/20"
  }

  const verdictColor = isFavorable ? "text-green-400" : isUnfavorable ? "text-red-400" : "text-yellow-400"
  const verdictText = isFavorable ? "APOSTAR" : isUnfavorable ? "NO APOSTAR" : "VERIFICAR"

  return (
    <div className={`border rounded-lg ${cardBorderColor} ${cardBgColor}`}>
      {/* Compact main row */}
      <div className="flex items-center gap-3 px-3 py-2.5">
        {/* Verdict */}
        <div className={`text-sm font-bold uppercase shrink-0 w-24 ${verdictColor}`}>{verdictText}</div>

        {/* Match + strategy */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-sm font-semibold text-zinc-100 truncate">{signal.match_name}</span>
            <span className="text-xs px-1.5 py-0 rounded bg-zinc-800 text-zinc-400">{signal.score}</span>
            <span className="text-xs text-zinc-500">Min {signal.minute}'</span>
            <SignalAgeBadge ageMinutes={signal.signal_age_minutes} minDurationCaps={signal.min_duration_caps} isMature={signal.is_mature} />
            {hasConflict && (
              <span className="text-[10px] px-1.5 py-0 rounded-full font-bold bg-red-900/40 text-red-400 border border-red-500/40" title="Par tóxico: MomXG + xG Underperf tuvieron 0% WR">⚠ Conflicto</span>
            )}
            {riskLevel !== "none" && (
              <span className={`text-[10px] px-1.5 py-0 rounded-full font-bold border ${riskLevel === "high" ? "bg-red-900/40 text-red-400 border-red-500/40" : "bg-orange-900/30 text-orange-400 border-orange-500/40"}`}>
                {riskLevel === "high" ? "🔴" : "🟠"} Riesgo
              </span>
            )}
            {(signal.data_warnings?.length ?? 0) > 0 && (
              <span className="text-[10px] px-1.5 py-0 rounded-full font-bold bg-red-900/40 text-red-400 border border-red-500/40" title={signal.data_warnings!.join(" | ")}>
                Datos
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-zinc-500">{signal.strategy_name}</span>
            <span className="text-xs font-mono text-zinc-300">{signal.recommendation}</span>
            {signal.min_odds != null && (
              <span className="text-xs text-zinc-500">
                mín: <span className="text-zinc-400">{signal.min_odds === 0 ? "0" : signal.min_odds.toFixed(2)}</span>
              </span>
            )}
            {signal.win_rate_historical ? (
              <span className="text-[10px] text-zinc-500">
                WR {signal.win_rate_historical}%
                {signal.expected_value != null && signal.expected_value !== 0 && (
                  <span className={signal.expected_value >= 0 ? " text-green-500" : " text-red-500"}>
                    {" "}· EV {signal.expected_value >= 0 ? "+" : ""}{signal.expected_value.toFixed(3)}
                  </span>
                )}
              </span>
            ) : null}
            {isMature && (
              <span className="inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0 rounded-full font-semibold bg-blue-500/15 text-blue-400 border border-blue-500/30">
                <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                Paper auto
              </span>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1.5 shrink-0">
          <OpenBetButton matchUrl={signal.match_url} isFavorable={isFavorable} recommendation={signal.recommendation} matchName={signal.match_name} />
          <a
            href={signal.match_url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-2.5 py-1.5 text-xs font-semibold rounded-lg transition-colors bg-[#FFD200] hover:bg-[#FFE040] text-black"
            title="Abrir partido en Betfair"
          >
            Betfair
          </a>
          <button
            type="button"
            onClick={() => setExpanded(v => !v)}
            className="p-1.5 rounded text-zinc-600 hover:text-zinc-400 transition-colors"
            title={expanded ? "Ocultar detalles" : "Ver detalles"}
          >
            <svg className={`w-4 h-4 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Expandable details */}
      {expanded && (
        <div className="border-t border-zinc-800 px-3 py-3 space-y-3">
          {/* Risk warning */}
          {signal.risk_info?.has_risk && (
            <div className={`p-2.5 rounded border text-xs ${riskLevel === "high" ? "bg-red-900/30 border-red-500/40 text-red-300/80" : "bg-orange-900/20 border-orange-500/30 text-orange-300/80"}`}>
              <span className="font-semibold">{riskLevel === "high" ? "🔴 Alto Riesgo" : "🟠 Riesgo Medio"}:</span>{" "}
              {signal.risk_info.risk_reason}{" "}
              <span className="text-zinc-400">({signal.risk_info.time_remaining} min restantes)</span>
            </div>
          )}
          {/* Data quality warnings */}
          {(signal.data_warnings?.length ?? 0) > 0 && (
            <div className="p-2.5 rounded border bg-red-900/20 border-red-500/30 text-xs text-red-300/80">
              <span className="font-semibold">Calidad de datos:</span>
              <ul className="mt-1 space-y-0.5">
                {signal.data_warnings!.map((w, i) => (
                  <li key={i}>· {w}</li>
                ))}
              </ul>
            </div>
          )}
          {/* Historical + conditions */}
          <div className="grid grid-cols-2 gap-3">
            {signal.win_rate_historical ? (
              <div>
                <div className="text-xs text-zinc-500 mb-1.5">Rendimiento Histórico</div>
                <div className="flex gap-4 text-xs">
                  <div><span className="text-zinc-500">WR </span><span className="font-bold text-zinc-100">{signal.win_rate_historical}%</span></div>
                  <div><span className="text-zinc-500">ROI </span><span className="font-bold text-green-400">+{signal.roi_historical}%</span></div>
                  <div title={`Ganancia media por €1 apostado en backtest (${signal.sample_size} apuestas)`}>
                    <span className="text-zinc-500">+€/€ </span>
                    <span className="font-bold text-emerald-400">+{((signal.roi_historical ?? 0) / 100).toFixed(2)}</span>
                  </div>
                  {signal.expected_value != null && signal.expected_value !== 0 && (
                    <div title="Valor esperado por €1 apostado con las cuotas actuales (WR histórico × cuota actual, neto de comisión 5%)">
                      <span className="text-zinc-500">EV </span>
                      <span className={`font-bold ${signal.expected_value >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {signal.expected_value >= 0 ? "+" : ""}{signal.expected_value.toFixed(3)}
                      </span>
                    </div>
                  )}
                  <div><span className="text-zinc-500">N </span><span className="font-mono text-zinc-300">{signal.sample_size}</span></div>
                </div>
              </div>
            ) : null}
            <div>
              <div className="text-xs text-zinc-500 mb-1.5">Condiciones</div>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                {Object.entries(signal.entry_conditions).map(([k, v]) => (
                  <span key={k} className="text-xs"><span className="text-zinc-500">{formatConditionKey(k)}</span> <span className="font-mono text-zinc-300">{formatConditionValue(v)}</span></span>
                ))}
              </div>
            </div>
          </div>
          <div>
            <div className="text-xs text-zinc-500 mb-1.5">Umbrales</div>
            <div className="flex flex-wrap gap-x-3 gap-y-0.5">
              {Object.entries(signal.thresholds).map(([k, v]) => (
                <span key={k} className="text-xs"><span className="text-zinc-500">{formatConditionKey(k)}</span> <span className="font-mono text-zinc-300">{String(v)}</span></span>
              ))}
            </div>
          </div>
        </div>
      )}
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
