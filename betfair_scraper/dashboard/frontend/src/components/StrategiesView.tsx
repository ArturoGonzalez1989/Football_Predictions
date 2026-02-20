import { useState, useEffect, useRef } from "react"
import { api, type Cartera, type CarteraBet, type CarteraConfig } from "../lib/api"
import {
  type DrawVersion, type XGCarteraVersion, type DriftCarteraVersion,
  type ClusteringCarteraVersion, type PressureCarteraVersion, type TardeAsiaVersion, type MomentumXGVersion,
  type BankrollMode, type PresetKey,
  PRESETS, PRESSURE_CARTERA_VERSIONS, TARDE_ASIA_VERSIONS, MOMENTUM_XG_VERSIONS, BANKROLL_MODES,
  round2,
  type DrawFilterParams, type XGFilterParams, type DriftFilterParams, type ClusteringFilterParams,
  DEFAULT_DRAW_PARAMS, DEFAULT_XG_PARAMS, DEFAULT_DRIFT_PARAMS, DEFAULT_CLUSTERING_PARAMS,
  drawVersionToParams, xgVersionToParams, driftVersionToParams, clusteringVersionToParams,
  filterDrawBets, filterXGBets, filterDriftBets, filterClusteringBets, filterPressureBets, filterTardeAsiaBets, filterMomentumXGBets,
  simulateCartera, findBestCombo, getBetOdds,
  type OptimizeResult,
  optimizeDrawParams, optimizeXGParams, optimizeDriftParams, optimizeClusteringParams,
  type RealisticAdjustments,
  applyRealisticAdjustments,
  type RiskFilter, filterByRisk, analyzeRiskBreakdown,
} from "../lib/cartera"
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Line,
  ComposedChart,
  Legend,
  ReferenceArea,
  Bar,
  Cell,
} from "recharts"

export function StrategiesView() {
  const [cartera, setCartera] = useState<Cartera | null>(null)
  const [loading, setLoading] = useState(true)

  const loadCartera = async (cashoutMinute?: number) => {
    try {
      const data = await api.getCartera(cashoutMinute)
      setCartera(data)
    } catch (e) {
      console.error("Error loading cartera:", e)
    }
  }

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await loadCartera()
      setLoading(false)
    }
    load()
  }, [])

  const refreshCartera = async () => {
    await loadCartera()
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="flex items-center justify-center h-64">
          <div className="text-zinc-500 text-sm">Cargando estrategias...</div>
        </div>
      </div>
    )
  }

  if (!cartera) {
    return (
      <div className="p-8">
        <div className="text-center py-12 text-zinc-500 text-sm">
          No hay datos de cartera disponibles.
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Cartera de Estrategias</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Análisis y simulación de estrategias combinadas con gestión de bankroll
        </p>
      </div>

      <CarteraTab data={cartera} onRefresh={refreshCartera} />
    </div>
  )
}

// LocalStorage key — kept as fallback only (backend config is primary source of truth)
const STORAGE_KEY = "cartera_filters"

// Load saved state from localStorage (fallback when backend config not yet loaded)
const loadSavedState = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved)
  } catch (e) {
    console.error("Error loading saved filters:", e)
  }
  return null
}

const savedState = loadSavedState()

// Min duration config type (shared with BettingSignalsView)
type MinDurConfig = { draw: number; xg: number; drift: number; clustering: number; pressure: number }
const DEFAULT_MIN_DUR: MinDurConfig = { draw: 1, xg: 2, drift: 2, clustering: 4, pressure: 2 }
const MIN_DUR_OPTIONS = [1, 2, 3, 4, 5]

/** Convert backend CarteraConfig to local component state shape */
function configToState(cfg: CarteraConfig) {
  // Read strategy params (new format) or fall back to legacy versions → params conversion
  const s = cfg.strategies
  const v = cfg.versions

  const drawParams: DrawFilterParams = s?.draw
    ? { enabled: s.draw.enabled, xgMax: s.draw.xgMax, possMax: s.draw.possMax, shotsMax: s.draw.shotsMax, xgDomAsym: s.draw.xgDomAsym, minuteMin: s.draw.minuteMin ?? 0, minuteMax: s.draw.minuteMax ?? 90 }
    : drawVersionToParams((v?.draw || "v1") as DrawVersion)

  const xgParams: XGFilterParams = s?.xg
    ? { enabled: s.xg.enabled, sotMin: s.xg.sotMin, minuteMin: s.xg.minuteMin ?? 0, minuteMax: s.xg.minuteMax ?? 90 }
    : xgVersionToParams((v?.xg || "base") as XGCarteraVersion)

  const driftParams: DriftFilterParams = s?.drift
    ? { enabled: s.drift.enabled, goalDiffMin: s.drift.goalDiffMin, driftMin: s.drift.driftMin, oddsMax: s.drift.oddsMax, minuteMin: s.drift.minuteMin ?? 0, minuteMax: s.drift.minuteMax ?? 90, momGapMin: s.drift.momGapMin }
    : driftVersionToParams((v?.drift || "v1") as DriftCarteraVersion)

  const clusteringParams: ClusteringFilterParams = s?.clustering
    ? { enabled: s.clustering.enabled, minuteMin: s.clustering.minuteMin ?? 0, minuteMax: s.clustering.minuteMax ?? 90, xgRemMin: s.clustering.xgRemMin }
    : clusteringVersionToParams((v?.clustering || "v2") as ClusteringCarteraVersion)

  return {
    drawParams,
    xgParams,
    driftParams,
    clusteringParams,
    pressureVer: (s?.pressure?.enabled === false ? "off" : v?.pressure || "v1") as PressureCarteraVersion,
    tardeAsiaVer: (s?.tarde_asia?.enabled === true ? "v1" : v?.tarde_asia || "off") as TardeAsiaVersion,
    momentumXGVer: (s?.momentum_xg?.version || v?.momentum_xg || "off") as MomentumXGVersion,
    brMode: (cfg.bankroll_mode || "fixed") as BankrollMode,
    flatStake: cfg.flat_stake ?? 10,
    bankrollInit: cfg.initial_bankroll ?? 500,
    activePreset: (cfg.active_preset || null) as PresetKey,
    riskFilter: (cfg.risk_filter || "all") as RiskFilter,
    adjDedup: cfg.adjustments.dedup ?? true,
    adjMaxOdds: cfg.adjustments.max_odds ?? 6.0,
    adjMinOdds: cfg.adjustments.min_odds ?? 1.15,
    adjDriftMinMin: cfg.adjustments.drift_min_minute ?? 15,
    adjSlippage: cfg.adjustments.slippage_pct ?? 2,
    adjConflictFilter: cfg.adjustments.conflict_filter ?? true,
    adjCashout: cfg.adjustments.cashout_minute != null,
    adjCashoutMinute: cfg.adjustments.cashout_minute ?? 70,
    minDur: {
      draw: cfg.min_duration.draw ?? 1,
      xg: cfg.min_duration.xg ?? 2,
      drift: cfg.min_duration.drift ?? 2,
      clustering: cfg.min_duration.clustering ?? 4,
      pressure: cfg.min_duration.pressure ?? 2,
    },
  }
}

// CSV Helper Functions
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
    const strategy = (b as any).strategy_label || (b as any).strategy || ''

    return [
      `"${b.match}"`, b.match_id, csvFile, (b as any).timestamp_utc || '', strategy,
      (b as any).minuto ?? '', (b as any).score_at_trigger || '', (b as any).ft_score, b.won ? 1 : 0, b.pl,
      (b as any).back_draw ?? '', (b as any).back_over_odds ?? (b as any).over_odds ?? '', (b as any).over_line || '', (b as any).back_odds ?? '', (b as any).drift_pct ?? '',
      (b as any).xg_total ?? '', (b as any).xg_excess ?? '', (b as any).poss_diff ?? '', (b as any).shots_total ?? '', (b as any).sot_total ?? '', (b as any).sot_max ?? '',
      (b as any).passes_v15 ? 1 : 0, (b as any).passes_v2r ? 1 : 0, (b as any).passes_v2 ? 1 : 0, (b as any).passes_v3 ? 1 : 0, (b as any).passes_v4 ? 1 : 0,
      (b as any).team || '', (b as any).goal_diff ?? ''
    ].join(',')
  })

  return [headers, ...rows].join('\n')
}

// Helper function to get bet type/recommendation
function getBetType(bet: CarteraBet): string {
  const betAny = bet as any

  // Check for DRAW bets
  if (betAny.back_draw !== undefined && betAny.back_draw !== null) {
    return "DRAW"
  }

  // Check for OVER bets
  if (betAny.back_over_odds !== undefined && betAny.back_over_odds !== null && betAny.over_line) {
    return `OVER ${betAny.over_line}`
  }

  // Check for HOME/AWAY bets (from team or dominant_team field)
  const teamField = betAny.team || betAny.dominant_team
  if (teamField) {
    const team = String(teamField).toLowerCase().trim()
    if (team === "home" || team.includes("local")) {
      return "HOME"
    }
    if (team === "away" || team.includes("visit")) {
      return "AWAY"
    }
  }

  // Fallback: try to infer from strategy type
  if (bet.strategy === "back_draw_00") {
    return "DRAW"
  }

  if (bet.strategy.includes("goal_clustering") || bet.strategy.includes("pressure_cooker")) {
    return betAny.over_line ? `OVER ${betAny.over_line}` : "OVER"
  }

  if (bet.strategy.includes("xg_underperformance")) {
    return betAny.over_line ? `OVER ${betAny.over_line}` : "OVER"
  }

  return "-"
}

function CarteraTab({ data, onRefresh }: { data: Cartera; onRefresh: () => Promise<void> }) {
  const [drawParams, setDrawParams] = useState<DrawFilterParams>(savedState?.drawParams || DEFAULT_DRAW_PARAMS)
  const [xgParams, setXGParams] = useState<XGFilterParams>(savedState?.xgParams || DEFAULT_XG_PARAMS)
  const [driftParams, setDriftParams] = useState<DriftFilterParams>(savedState?.driftParams || DEFAULT_DRIFT_PARAMS)
  const [clusteringParams, setClusteringParams] = useState<ClusteringFilterParams>(savedState?.clusteringParams || DEFAULT_CLUSTERING_PARAMS)
  // Optimizer state
  const [optimizerOpen, setOptimizerOpen] = useState<string | null>(null)
  const [optimizerMinBets, setOptimizerMinBets] = useState(5)
  const [optimizerResults, setOptimizerResults] = useState<{ strategy: string; results: OptimizeResult<any>[] } | null>(null)
  const [pressureVer, setPressureVer] = useState<PressureCarteraVersion>(savedState?.pressureVer || "v1")
  const [tardeAsiaVer, setTardeAsiaVer] = useState<TardeAsiaVersion>(savedState?.tardeAsiaVer || "off")
  const [momentumXGVer, setMomentumXGVer] = useState<MomentumXGVersion>(savedState?.momentumXGVer || "off")
  const [brMode, setBrMode] = useState<BankrollMode>(savedState?.brMode || "fixed")
  const [flatStake, setFlatStake] = useState<number>(savedState?.flatStake ?? 10)
  const [showRiskAnalysis, setShowRiskAnalysis] = useState(false)
  const [showRiskMetrics, setShowRiskMetrics] = useState(false)
  const [bankrollInit, setBankrollInit] = useState<number>(savedState?.bankrollInit ?? 500)
  const [activePreset, setActivePreset] = useState<PresetKey>(savedState?.activePreset || null)
  const [adjDedup, setAdjDedup] = useState(savedState?.adjDedup !== undefined ? savedState.adjDedup : true)
  const [adjMaxOdds, setAdjMaxOdds] = useState(savedState?.adjMaxOdds || 6.0)
  const [adjMinOdds, setAdjMinOdds] = useState(savedState?.adjMinOdds || 1.15)
  const [adjDriftMinMin, setAdjDriftMinMin] = useState(savedState?.adjDriftMinMin || 15)
  const [adjSlippage, setAdjSlippage] = useState(savedState?.adjSlippage || 2)
  const [adjConflictFilter, setAdjConflictFilter] = useState(savedState?.adjConflictFilter !== undefined ? savedState.adjConflictFilter : true)
  const [adjStability, setAdjStability] = useState<number>(savedState?.adjStability ?? 1)
  const [adjConservativeOdds, setAdjConservativeOdds] = useState<boolean>(savedState?.adjConservativeOdds ?? false)
  const [adjCashout, setAdjCashout] = useState<boolean>(savedState?.adjCashout ?? false)
  const [adjCashoutMinute, setAdjCashoutMinute] = useState<number>(savedState?.adjCashoutMinute ?? 70)
  const [riskFilter, setRiskFilter] = useState<RiskFilter>(savedState?.riskFilter || "all")
  const [minDur, setMinDur] = useState<MinDurConfig>(savedState?.minDur || DEFAULT_MIN_DUR)
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const [histSort, setHistSort] = useState<{ col: string; dir: "asc" | "desc" }>({ col: "date", dir: "asc" })
  // Per-strategy minute range (version-based strategies)
  const [pressureMinuteMin, setPressureMinuteMin] = useState<number>(savedState?.pressureMinuteMin ?? 0)
  const [pressureMinuteMax, setPressureMinuteMax] = useState<number>(savedState?.pressureMinuteMax ?? 90)
  const [tardeAsiaMinuteMin, setTardeAsiaMinuteMin] = useState<number>(savedState?.tardeAsiaMinuteMin ?? 0)
  const [tardeAsiaMinuteMax, setTardeAsiaMinuteMax] = useState<number>(savedState?.tardeAsiaMinuteMax ?? 90)
  const [momentumMinuteMin, setMomentumMinuteMin] = useState<number>(savedState?.momentumMinuteMin ?? 0)
  const [momentumMinuteMax, setMomentumMinuteMax] = useState<number>(savedState?.momentumMinuteMax ?? 90)
  // Global minute range (Filtros Realistas — overrides all strategies when enabled)
  const [adjGlobalMinEnabled, setAdjGlobalMinEnabled] = useState<boolean>(savedState?.adjGlobalMinEnabled ?? false)
  const [adjGlobalMinMin, setAdjGlobalMinMin] = useState<number | null>(savedState?.adjGlobalMinMin ?? null)
  const [adjGlobalMinMax, setAdjGlobalMinMax] = useState<number | null>(savedState?.adjGlobalMinMax ?? null)
  const configLoadedRef = useRef(false)

  // Load config from backend on mount (overrides localStorage if backend has saved config)
  useEffect(() => {
    if (configLoadedRef.current) return
    configLoadedRef.current = true
    api.getConfig()
      .then(cfg => {
        const s = configToState(cfg)
        setDrawParams(s.drawParams)
        setXGParams(s.xgParams)
        setDriftParams(s.driftParams)
        setClusteringParams(s.clusteringParams)
        setPressureVer(s.pressureVer)
        setTardeAsiaVer(s.tardeAsiaVer)
        setMomentumXGVer(s.momentumXGVer)
        setBrMode(s.brMode)
        setFlatStake(s.flatStake)
        setBankrollInit(s.bankrollInit)
        setActivePreset(s.activePreset)
        setRiskFilter(s.riskFilter)
        setAdjDedup(s.adjDedup)
        setAdjMaxOdds(s.adjMaxOdds)
        setAdjMinOdds(s.adjMinOdds)
        setAdjDriftMinMin(s.adjDriftMinMin)
        setAdjSlippage(s.adjSlippage)
        setAdjConflictFilter(s.adjConflictFilter)
        if (s.adjStability != null) setAdjStability(s.adjStability)
        if (s.adjConservativeOdds != null) setAdjConservativeOdds(s.adjConservativeOdds)
        setAdjCashout(s.adjCashout)
        setAdjCashoutMinute(s.adjCashoutMinute)
        setMinDur(s.minDur)
      })
      .catch(() => { /* backend unreachable — keep localStorage values */ })
  }, [])

  // CO-adjusted cartera data (fetched from backend when adjCashout is on)
  const [coData, setCoData] = useState<Cartera | null>(null)
  const [coLoading, setCoLoading] = useState(false)

  useEffect(() => {
    if (!adjCashout) {
      setCoData(null)
      return
    }
    setCoLoading(true)
    api.getCartera(adjCashoutMinute)
      .then(d => setCoData(d))
      .catch(console.error)
      .finally(() => setCoLoading(false))
  }, [adjCashout, adjCashoutMinute])

  const updateMinDur = (newMinDur: MinDurConfig) => {
    setMinDur(newMinDur)
    // Build config with the new minDur (buildConfig() uses stale state here, so override min_duration directly)
    const config = buildConfig()
    config.min_duration = newMinDur
    api.saveConfig(config)
      .then(() => onRefresh())
      .catch(e => console.error("Error refreshing cartera after minDur change:", e))
  }

  /** Build CarteraConfig from current component state */
  const buildConfig = (): CarteraConfig => ({
    strategies: {
      draw: { enabled: drawParams.enabled, xgMax: drawParams.xgMax, possMax: drawParams.possMax, shotsMax: drawParams.shotsMax, xgDomAsym: drawParams.xgDomAsym },
      xg: { enabled: xgParams.enabled, sotMin: xgParams.sotMin, minuteMax: xgParams.minuteMax },
      drift: { enabled: driftParams.enabled, goalDiffMin: driftParams.goalDiffMin, driftMin: driftParams.driftMin, oddsMax: isFinite(driftParams.oddsMax) ? driftParams.oddsMax : 999, minuteMin: driftParams.minuteMin, momGapMin: driftParams.momGapMin },
      clustering: { enabled: clusteringParams.enabled, minuteMax: clusteringParams.minuteMax, xgRemMin: clusteringParams.xgRemMin },
      pressure: { enabled: pressureVer !== "off" },
      tarde_asia: { enabled: tardeAsiaVer !== "off" },
      momentum_xg: { version: momentumXGVer },
    },
    bankroll_mode: brMode,
    flat_stake: flatStake,
    initial_bankroll: bankrollInit,
    active_preset: activePreset,
    risk_filter: riskFilter,
    min_duration: minDur,
    adjustments: {
      enabled: true,
      dedup: adjDedup,
      max_odds: adjMaxOdds,
      min_odds: adjMinOdds,
      drift_min_minute: adjDriftMinMin,
      slippage_pct: adjSlippage,
      conflict_filter: adjConflictFilter,
      cashout_minute: adjCashout ? adjCashoutMinute : null,
    },
  })

  // Save config to backend (single source of truth) + localStorage as fallback
  const saveFilters = () => {
    const config = buildConfig()
    setSaveStatus("saving")
    api.saveConfig(config)
      .then(() => {
        // Keep localStorage in sync as fallback
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
          drawParams, xgParams, driftParams, clusteringParams,
          pressureVer, tardeAsiaVer, momentumXGVer,
          brMode, flatStake, bankrollInit, activePreset, adjDedup, adjMaxOdds, adjMinOdds, adjDriftMinMin,
          adjSlippage, adjConflictFilter, adjStability, adjConservativeOdds, adjCashout, adjCashoutMinute, riskFilter, minDur,
          pressureMinuteMin, pressureMinuteMax, tardeAsiaMinuteMin, tardeAsiaMinuteMax, momentumMinuteMin, momentumMinuteMax,
          adjGlobalMinEnabled, adjGlobalMinMin, adjGlobalMinMax,
        }))
        setSaveStatus("saved")
        setTimeout(() => setSaveStatus("idle"), 2000)
      })
      .catch(() => setSaveStatus("error"))
  }

  // Reset filters to defaults and save to backend
  const resetFilters = () => {
    setDrawParams({ ...DEFAULT_DRAW_PARAMS })
    setXGParams({ ...DEFAULT_XG_PARAMS })
    setDriftParams({ ...DEFAULT_DRIFT_PARAMS })
    setClusteringParams({ ...DEFAULT_CLUSTERING_PARAMS })
    setPressureVer("v1")
    setTardeAsiaVer("off")
    setMomentumXGVer("off")
    setBrMode("fixed")
    setActivePreset(null)
    setAdjDedup(true)
    setAdjMaxOdds(6.0)
    setAdjMinOdds(1.15)
    setAdjDriftMinMin(15)
    setAdjSlippage(2)
    setAdjConflictFilter(true)
    setAdjCashout(false)
    setAdjCashoutMinute(70)
    setRiskFilter("all")
    setMinDur({ ...DEFAULT_MIN_DUR })
    setPressureMinuteMin(0); setPressureMinuteMax(90)
    setTardeAsiaMinuteMin(0); setTardeAsiaMinuteMax(90)
    setMomentumMinuteMin(0); setMomentumMinuteMax(90)
    setAdjGlobalMinEnabled(false); setAdjGlobalMinMin(null); setAdjGlobalMinMax(null)
    localStorage.removeItem(STORAGE_KEY)
  }

  // Use CO-adjusted data when CO is active, otherwise original data
  const { bets } = (adjCashout && coData) ? coData : data

  const applyPreset = (key: Exclude<PresetKey, null>) => {
    const combo = findBestCombo(bets, bankrollInit, key, riskFilter)
    setDrawParams(drawVersionToParams(combo.draw))
    setXGParams(xgVersionToParams(combo.xg))
    setDriftParams(driftVersionToParams(combo.drift))
    setClusteringParams(clusteringVersionToParams(combo.clustering))
    setPressureVer(combo.pressure)
    setTardeAsiaVer(combo.tardeAsia)
    setMomentumXGVer(combo.momentumXG)
    setBrMode(combo.br)
    setActivePreset(key)
  }

  // Run per-strategy grid search optimizer
  const runOptimizer = (strategy: string) => {
    let results: OptimizeResult<any>[] = []
    if (strategy === "draw") {
      results = optimizeDrawParams(bets, xgParams, driftParams, clusteringParams, pressureVer, tardeAsiaVer, momentumXGVer, bankrollInit, optimizerMinBets)
    } else if (strategy === "xg") {
      results = optimizeXGParams(bets, drawParams, driftParams, clusteringParams, pressureVer, tardeAsiaVer, momentumXGVer, bankrollInit, optimizerMinBets)
    } else if (strategy === "drift") {
      results = optimizeDriftParams(bets, drawParams, xgParams, clusteringParams, pressureVer, tardeAsiaVer, momentumXGVer, bankrollInit, optimizerMinBets)
    } else if (strategy === "clustering") {
      results = optimizeClusteringParams(bets, drawParams, xgParams, driftParams, pressureVer, tardeAsiaVer, momentumXGVer, bankrollInit, optimizerMinBets)
    }
    setOptimizerResults({ strategy, results })
    setOptimizerOpen(strategy)
  }

  // Filter bets by strategy params, then re-sort chronologically
  const drawBets = filterDrawBets(bets, drawParams)
  const xgBets = filterXGBets(bets, xgParams)
  const driftBets = filterDriftBets(bets, driftParams)
  const clusteringBets = filterClusteringBets(bets, clusteringParams)
  const pressureBets = filterPressureBets(bets, pressureVer,
    (pressureMinuteMin > 0 || pressureMinuteMax < 90) ? { min: pressureMinuteMin, max: pressureMinuteMax } : undefined)
  const tardeAsiaBets = filterTardeAsiaBets(bets, tardeAsiaVer,
    (tardeAsiaMinuteMin > 0 || tardeAsiaMinuteMax < 90) ? { min: tardeAsiaMinuteMin, max: tardeAsiaMinuteMax } : undefined)
  const momentumXGBets = filterMomentumXGBets(bets, momentumXGVer,
    (momentumMinuteMin > 0 || momentumMinuteMax < 90) ? { min: momentumMinuteMin, max: momentumMinuteMax } : undefined)
  const rawBets = [...drawBets, ...xgBets, ...driftBets, ...clusteringBets, ...pressureBets, ...tardeAsiaBets, ...momentumXGBets].sort((a, b) =>
    (a.timestamp_utc || "").localeCompare(b.timestamp_utc || "")
  )

  // Apply realistic adjustments (always active — each filter controlled independently)
  const currentAdj: RealisticAdjustments = { dedup: adjDedup, maxOdds: adjMaxOdds, minOdds: adjMinOdds, driftMinMinute: null, slippagePct: adjSlippage, conflictFilter: adjConflictFilter, minStability: adjStability, conservativeOdds: adjConservativeOdds, globalMinuteMin: adjGlobalMinEnabled ? adjGlobalMinMin : null, globalMinuteMax: adjGlobalMinEnabled ? adjGlobalMinMax : null }
  let filteredBets = applyRealisticAdjustments(rawBets, currentAdj)
  const removedCount = rawBets.length - filteredBets.length

  // Apply risk filter
  filteredBets = filterByRisk(filteredBets, riskFilter)

  // Calculate risk breakdown for analysis
  const riskBreakdown = analyzeRiskBreakdown(filteredBets)

  const handleDownloadCSV = () => {
    const csv = generateCarteraCSV(filteredBets)
    const timestamp = new Date().toISOString().split('T')[0]
    const presetLabel = activePreset ? `_${activePreset}` : ''
    downloadCSV(`cartera${presetLabel}_${timestamp}.csv`, csv)
  }

  // Recalculate simulations
  const sim = simulateCartera(filteredBets, bankrollInit, brMode, flatStake)

  // Derived portfolio stats
  const activeDays = filteredBets.length > 0
    ? new Set(filteredBets.map(b => b.timestamp_utc.slice(0, 10))).size
    : 0
  const dailyProfit = activeDays > 0 ? round2(sim.flatPl / activeDays) : 0
  const betsPerDay = activeDays > 0 ? round2(filteredBets.length / activeDays) : 0
  const evPerBet = sim.total > 0 ? round2(sim.flatPl / sim.total) : 0
  const avgOdds = filteredBets.length > 0
    ? round2(filteredBets.reduce((s, b) => s + getBetOdds(b), 0) / filteredBets.length)
    : 0

  // Per-strategy stats
  const stratConfigs = [
    { key: "back_draw_00", label: "Back Empate 0-0", bgClass: "bg-cyan-500", active: drawParams.enabled },
    { key: "xg_underperformance", label: "xG Underperformance", bgClass: "bg-amber-500", active: xgParams.enabled },
    { key: "odds_drift", label: "Odds Drift", bgClass: "bg-emerald-500", active: driftParams.enabled },
    { key: "goal_clustering", label: "Goal Clustering", bgClass: "bg-rose-500", active: clusteringParams.enabled },
    { key: "pressure_cooker", label: "Pressure Cooker", bgClass: "bg-orange-500", active: pressureVer !== "off" },
    { key: "tarde_asia", label: "Tarde Asia", bgClass: "bg-blue-500", active: tardeAsiaVer !== "off" },
    { key: "momentum_xg", label: "Momentum x xG", bgClass: "bg-violet-500", active: momentumXGVer !== "off" },
  ]

  const stratStats = stratConfigs.filter(s => s.active).map(s => {
    // For momentum_xg, match both v1 and v2 strategy keys
    const sBets = filteredBets.filter(b =>
      s.key === "momentum_xg"
        ? (b.strategy === "momentum_xg_v1" || b.strategy === "momentum_xg_v2")
        : b.strategy === s.key
    )
    const wins = sBets.filter(b => b.won).length
    const pl = round2(sBets.reduce((sum, b) => sum + b.pl * flatStake / 10, 0))
    const staked = sBets.length * flatStake
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

  const activeLabels = stratConfigs.filter(s => s.active).map(s => s.label)
  const selLabel = activeLabels.length === 7 ? "Todas las estrategias" : activeLabels.length >= 3 ? `${activeLabels.length} estrategias` : activeLabels.length === 2 ? "2 estrategias" : activeLabels[0] || "Ninguna"

  return (
    <div className="space-y-6">
      {/* ============ PANEL DE CONTROL ============ */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-sm font-semibold text-zinc-200">Cartera de Estrategias</h2>
            <p className="text-[10px] text-zinc-500 mt-0.5">
              {filteredBets.length} apuestas filtradas / {bets.length} totales
              {removedCount > 0 && <span className="text-yellow-600/80 ml-1.5">· {removedCount} eliminadas por filtros realistas</span>}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={saveFilters}
              disabled={saveStatus === "saving"}
              className={`px-3 py-1.5 border rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
                saveStatus === "saved" ? "bg-green-500/20 border-green-500/50 text-green-300" :
                saveStatus === "error" ? "bg-red-500/20 border-red-500/50 text-red-300" :
                saveStatus === "saving" ? "bg-zinc-700/50 border-zinc-600 text-zinc-400" :
                "bg-green-500/10 hover:bg-green-500/20 border-green-500/30 text-green-400"
              }`}
              title="Guardar configuración — se usará en Señales, Cartera y Simulación"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={
                  saveStatus === "saved" ? "M5 13l4 4L19 7" :
                  saveStatus === "error" ? "M6 18L18 6M6 6l12 12" :
                  "M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"
                } />
              </svg>
              {saveStatus === "saving" ? "Guardando..." : saveStatus === "saved" ? "Guardado" : saveStatus === "error" ? "Error" : "Guardar"}
            </button>
            <button
              type="button"
              onClick={resetFilters}
              className="px-3 py-1.5 bg-orange-500/10 hover:bg-orange-500/20 border border-orange-500/30 text-orange-400 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5"
              title="Restablecer todos los filtros a valores por defecto"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Reset
            </button>
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
        {/* ── 2×2 Modular Control Cards ── */}
        <div className="grid grid-cols-2 gap-4 pb-5 mb-5 border-b border-zinc-800">
          {/* Card: PRESETS */}
          <div className="bg-zinc-900/40 rounded-xl border border-zinc-800 overflow-hidden">
            <div className="h-0.5 bg-cyan-500/40" />
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-bold text-cyan-500/70 uppercase tracking-widest">Presets</span>
                <span className="text-zinc-700 text-sm select-none">⠿</span>
              </div>
            <div className="flex flex-wrap gap-1.5">
              {PRESETS.map(p => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => applyPreset(p.key)}
                  className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all ${
                    activePreset === p.key
                      ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm shadow-indigo-500/10"
                      : "bg-zinc-800/50 text-zinc-500 border border-zinc-700/50 hover:text-zinc-300 hover:border-zinc-600"
                  }`}
                  title={p.desc}
                >
                  <span className={`w-4 h-4 rounded flex items-center justify-center text-[10px] font-bold shrink-0 ${
                    activePreset === p.key ? "bg-indigo-500/30 text-indigo-300" : "bg-zinc-700/50 text-zinc-500"
                  }`}>{p.icon}</span>
                  {p.label}
                </button>
              ))}
            </div>
          </div>
          </div>

          {/* Card: FILTRO DE RIESGO */}
          <div className="bg-zinc-900/40 rounded-xl border border-zinc-800 overflow-hidden">
            <div className="h-0.5 bg-red-500/40" />
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-bold text-red-500/70 uppercase tracking-widest">Filtro de Riesgo</span>
                <span className="text-zinc-700 text-sm select-none">⠿</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {[
                  { key: "all" as RiskFilter, label: "Todas", desc: "Mostrar todas las apuestas" },
                  { key: "no_risk" as RiskFilter, label: "Sin riesgo", desc: "Solo apuestas sin limitación de tiempo" },
                  { key: "with_risk" as RiskFilter, label: "Con riesgo", desc: "Apuestas con riesgo medio/alto" },
                  { key: "medium" as RiskFilter, label: "Riesgo medio", desc: "Solo riesgo medio" },
                  { key: "high" as RiskFilter, label: "Alto riesgo", desc: "Solo alto riesgo" },
                ].map(r => (
                  <button
                    key={r.key}
                    type="button"
                    onClick={() => { setRiskFilter(r.key); setActivePreset(null) }}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                      riskFilter === r.key
                        ? r.key === "all" ? "bg-zinc-700/70 text-zinc-300 border border-zinc-600"
                          : r.key === "high" ? "bg-red-500/20 text-red-400 border border-red-500/40"
                          : r.key === "medium" ? "bg-orange-500/20 text-orange-400 border border-orange-500/40"
                          : r.key === "with_risk" ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/40"
                          : "bg-green-500/20 text-green-400 border border-green-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={r.desc}
                  >
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Card: GESTIÓN BANKROLL */}
          <div className="bg-zinc-900/40 rounded-xl border border-zinc-800 overflow-hidden">
            <div className="h-0.5 bg-purple-500/40" />
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-bold text-purple-500/70 uppercase tracking-widest">Gestión Bankroll</span>
                <span className="text-zinc-700 text-sm select-none">⠿</span>
              </div>
              <div className="flex items-center gap-3 mb-2.5">
                <label className="flex items-center gap-1.5 text-[11px] text-zinc-400" title="Bankroll inicial para la simulación de gestión">
                  <span className="text-zinc-500">Bankroll</span>
                  <input
                    type="number"
                    min={10} max={100000} step={50}
                    value={bankrollInit}
                    onChange={e => setBankrollInit(Math.max(10, Number(e.target.value)))}
                    className="w-20 px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-200 text-[11px] text-right focus:outline-none focus:border-zinc-500"
                  />
                  <span className="text-zinc-500">€</span>
                </label>
                <label className="flex items-center gap-1.5 text-[11px] text-zinc-400" title="Stake fijo por apuesta para la simulación flat">
                  <span className="text-zinc-500">Stake</span>
                  <input
                    type="number"
                    min={1} max={10000} step={1}
                    value={flatStake}
                    onChange={e => setFlatStake(Math.max(1, Number(e.target.value)))}
                    className="w-16 px-1.5 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-zinc-200 text-[11px] text-right focus:outline-none focus:border-zinc-500"
                  />
                  <span className="text-zinc-500">€</span>
                </label>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {BANKROLL_MODES.map(m => (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => { setBrMode(m.key); setActivePreset(null) }}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
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

          {/* Card: FILTROS REALISTAS */}
          <div className="bg-zinc-900/40 rounded-xl border border-zinc-800 overflow-hidden">
            <div className="h-0.5 bg-emerald-500/40" />
            <div className="p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[10px] font-bold text-emerald-500/70 uppercase tracking-widest">Filtros Realistas</span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => { setAdjDedup(true); setAdjMaxOdds(6.0); setAdjMinOdds(1.15); setAdjDriftMinMin(15); setAdjSlippage(2); setAdjConflictFilter(true); setAdjStability(1); setAdjConservativeOdds(false); setAdjGlobalMinEnabled(false); setAdjGlobalMinMin(null); setAdjGlobalMinMax(null) }}
                    className="text-[10px] text-zinc-600 hover:text-zinc-400 transition-colors"
                  >
                    reset
                  </button>
                  <span className="text-zinc-700 text-sm select-none">⠿</span>
                </div>
              </div>
          <div className="grid grid-cols-5 gap-2">
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">Dedup</span>
                <button
                  type="button"
                  onClick={() => setAdjDedup(!adjDedup)}
                  title="Deduplicar apuestas — mismo mercado/partido = 1 apuesta"
                  className={`relative w-8 h-4 rounded-full transition-colors ${adjDedup ? "bg-yellow-500" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${adjDedup ? "translate-x-4" : ""}`} />
                </button>
              </div>
              <p className="text-[9px] text-zinc-600 leading-tight">Cuenta solo 1 señal por mercado aunque lleguen varias capturas seguidas</p>
            </div>
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">Min Odds</span>
                <input
                  type="number"
                  value={adjMinOdds}
                  onChange={e => setAdjMinOdds(parseFloat(e.target.value) || 1.15)}
                  step="0.05"
                  min="1.01"
                  max="2"
                  title="Min odds"
                  className="w-12 bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 text-[10px] text-yellow-400 text-right"
                />
              </div>
              <p className="text-[9px] text-zinc-600 leading-tight">Descarta cuotas muy bajas (poco valor esperado al apostar)</p>
            </div>
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">Max Odds</span>
                <input
                  type="number"
                  value={adjMaxOdds}
                  onChange={e => setAdjMaxOdds(parseFloat(e.target.value) || 6.0)}
                  step="0.5"
                  min="2"
                  max="20"
                  title="Max odds"
                  className="w-12 bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 text-[10px] text-yellow-400 text-right"
                />
              </div>
              <p className="text-[9px] text-zinc-600 leading-tight">Descarta cuotas altas (mayor ruido de mercado, peor liquidez)</p>
            </div>
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">Slippage</span>
                <div className="flex items-center gap-0.5">
                  <input
                    type="number"
                    value={adjSlippage}
                    onChange={e => setAdjSlippage(parseFloat(e.target.value) || 0)}
                    step="0.5"
                    min="0"
                    max="10"
                    title="Porcentaje de slippage"
                    className="w-10 bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 text-[10px] text-yellow-400 text-right"
                  />
                  <span className="text-[9px] text-zinc-500">%</span>
                </div>
              </div>
              <p className="text-[9px] text-zinc-600 leading-tight">Simula no conseguir la cuota exacta en el mercado real (recomendado: 2%)</p>
            </div>
            <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-red-400/80 font-medium">Anti-conf</span>
                <button
                  type="button"
                  onClick={() => setAdjConflictFilter(!adjConflictFilter)}
                  title="Filtrar par tóxico MomXG + xGUnderperf"
                  className={`relative w-8 h-4 rounded-full transition-colors ${adjConflictFilter ? "bg-red-600" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${adjConflictFilter ? "translate-x-4" : ""}`} />
                </button>
              </div>
              <p className="text-[9px] text-red-900/80 leading-tight">Elimina Momentum xG si xG Underperf actúa en el partido (0% WR histórico en esa combinación)</p>
            </div>
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">Estab.</span>
                <input
                  type="number"
                  value={adjStability}
                  onChange={e => setAdjStability(Math.max(1, parseInt(e.target.value) || 1))}
                  step="1"
                  min="1"
                  max="10"
                  title="Mín capturas consecutivas con cuota estable (1 = sin filtro)"
                  className="w-12 bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 text-[10px] text-yellow-400 text-right"
                />
              </div>
              <p className="text-[9px] text-zinc-600 leading-tight">Mín capturas consecutivas con cuota estable antes de señal (filtra picos puntuales)</p>
            </div>
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">P/L cons.</span>
                <button
                  type="button"
                  onClick={() => setAdjConservativeOdds(!adjConservativeOdds)}
                  title="Usar cuota mínima del periodo de estabilidad (más conservador)"
                  className={`relative w-8 h-4 rounded-full transition-colors ${adjConservativeOdds ? "bg-yellow-500" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${adjConservativeOdds ? "translate-x-4" : ""}`} />
                </button>
              </div>
              <p className="text-[9px] text-zinc-600 leading-tight">Calcula P/L con la cuota más baja del periodo estable (resultado más conservador)</p>
            </div>
            <div className="bg-cyan-950/20 border border-cyan-900/30 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-cyan-400/80 font-medium">Cash-out</span>
                <button
                  type="button"
                  onClick={() => setAdjCashout(!adjCashout)}
                  title="Simular cash-out en apuestas perdedoras"
                  className={`relative w-8 h-4 rounded-full transition-colors ${adjCashout ? "bg-cyan-600" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${adjCashout ? "translate-x-4" : ""}`} />
                </button>
              </div>
              {adjCashout ? (
                <div className="flex items-center gap-0.5 mt-1">
                  {[60, 70, 80].map(m => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setAdjCashoutMinute(m)}
                      className={`flex-1 text-[9px] px-1 py-0.5 rounded transition-colors ${adjCashoutMinute === m ? "bg-cyan-700 text-white" : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"}`}
                    >
                      {m}'
                    </button>
                  ))}
                  {coLoading && <span className="text-[9px] text-cyan-500 animate-pulse ml-1">...</span>}
                </div>
              ) : (
                <p className="text-[9px] text-cyan-900/80 leading-tight">Simula limitar pérdidas colocando un lay en apuestas que van perdiendo</p>
              )}
            </div>
            {/* Rango Min' global */}
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">Rango Min'</span>
                <button
                  type="button"
                  onClick={() => setAdjGlobalMinEnabled(v => !v)}
                  title="Activar/desactivar rango de minuto global"
                  className={`relative w-8 h-4 rounded-full transition-colors ${adjGlobalMinEnabled ? "bg-yellow-500" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${adjGlobalMinEnabled ? "translate-x-4" : ""}`} />
                </button>
              </div>
              {adjGlobalMinEnabled ? (
                <div className="flex items-center gap-1 mt-1">
                  <input
                    type="number"
                    min={0} max={89} step={5}
                    value={adjGlobalMinMin ?? ""}
                    placeholder="0"
                    onChange={e => setAdjGlobalMinMin(e.target.value === "" ? null : parseInt(e.target.value))}
                    className="w-12 bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 text-[10px] text-yellow-400 text-center"
                    title="Minuto mínimo global"
                  />
                  <span className="text-[9px] text-zinc-600">–</span>
                  <input
                    type="number"
                    min={1} max={90} step={5}
                    value={adjGlobalMinMax ?? ""}
                    placeholder="90"
                    onChange={e => setAdjGlobalMinMax(e.target.value === "" ? null : parseInt(e.target.value))}
                    className="w-12 bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 text-[10px] text-yellow-400 text-center"
                    title="Minuto máximo global"
                  />
                </div>
              ) : (
                <p className="text-[9px] text-zinc-600 leading-tight">Franja global · aplica a todas las estrategias, ignora rangos individuales</p>
              )}
            </div>
          </div>
            </div>
          </div>
        </div>

        {/* Estrategias y Versiones */}
        <div>
          <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-3">Estrategias y Versiones</div>
          <div className="space-y-2">

            {/* ── Back Empate ── params: xgMax, possMax, shotsMax */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  onClick={() => { setDrawParams(p => ({ ...p, enabled: !p.enabled })); setActivePreset(null) }}
                  className={`relative w-7 h-3.5 rounded-full transition-colors shrink-0 ${drawParams.enabled ? "bg-cyan-600" : "bg-zinc-700"}`}
                  title={drawParams.enabled ? "Desactivar Back Empate" : "Activar Back Empate"}
                >
                  <span className={`absolute top-0.5 left-0.5 w-2.5 h-2.5 rounded-full bg-white transition-transform ${drawParams.enabled ? "translate-x-3.5" : ""}`} />
                </button>
                <span className="w-2 h-2 rounded-full bg-cyan-500 shrink-0" />
                <span className="text-xs text-zinc-400 w-24 shrink-0">Back Empate</span>
                {drawParams.enabled && (<>
                  <span className="text-[10px] text-zinc-600 shrink-0">xG&lt;</span>
                  <input type="number" min={0.3} max={1.0} step={0.05}
                    value={drawParams.xgMax >= 1.0 ? "" : drawParams.xgMax}
                    placeholder="∞"
                    onChange={e => { setDrawParams(p => ({ ...p, xgMax: e.target.value === "" ? 1.0 : parseFloat(e.target.value) })); setActivePreset(null) }}
                    className="w-12 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[10px] text-zinc-600 shrink-0">Pos&lt;</span>
                  <input type="number" min={10} max={100} step={5}
                    value={drawParams.possMax >= 100 ? "" : drawParams.possMax}
                    placeholder="∞"
                    onChange={e => { setDrawParams(p => ({ ...p, possMax: e.target.value === "" ? 100 : parseFloat(e.target.value) })); setActivePreset(null) }}
                    className="w-12 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[10px] text-zinc-600 shrink-0">%</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">Tiros&lt;</span>
                  <input type="number" min={4} max={20} step={1}
                    value={drawParams.shotsMax >= 20 ? "" : drawParams.shotsMax}
                    placeholder="∞"
                    onChange={e => { setDrawParams(p => ({ ...p, shotsMax: e.target.value === "" ? 20 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-12 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[10px] text-zinc-600 shrink-0">Min'</span>
                  <input type="number" min={0} max={89} step={5}
                    value={drawParams.minuteMin === 0 ? "" : drawParams.minuteMin}
                    placeholder="0"
                    onChange={e => { setDrawParams(p => ({ ...p, minuteMin: e.target.value === "" ? 0 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[9px] text-zinc-600">–</span>
                  <input type="number" min={1} max={90} step={5}
                    value={drawParams.minuteMax >= 90 ? "" : drawParams.minuteMax}
                    placeholder="90"
                    onChange={e => { setDrawParams(p => ({ ...p, minuteMax: e.target.value === "" ? 90 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button key={opt} type="button" onClick={() => updateMinDur({ ...minDur, draw: opt })}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${minDur.draw === opt ? "bg-amber-500/25 text-amber-400 border border-amber-500/40" : opt === DEFAULT_MIN_DUR.draw ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40" : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"}`}
                      >{opt}</button>
                    ))}
                  </div>
                  <button type="button" onClick={() => runOptimizer("draw")}
                    title="Optimizar parámetros de Back Empate" className="ml-auto text-[10px] text-zinc-600 hover:text-amber-400 transition-colors">✦ opt</button>
                </>)}
              </div>
              {/* Optimizer results panel for Back Empate */}
              {optimizerOpen === "draw" && optimizerResults && (
                <OptimizerPanel
                  strategyKey="draw"
                  results={optimizerResults.results}
                  minBets={optimizerMinBets}
                  onChangeMinBets={n => { setOptimizerMinBets(n); runOptimizer("draw") }}
                  onApply={r => { setDrawParams(r.params as DrawFilterParams); setOptimizerOpen(null) }}
                  onClose={() => setOptimizerOpen(null)}
                  renderParams={r => {
                    const p = r.params as DrawFilterParams
                    return `xG<${p.xgMax >= 1.0 ? "∞" : p.xgMax} Pos<${p.possMax >= 100 ? "∞" : p.possMax}% Tiros<${p.shotsMax >= 20 ? "∞" : p.shotsMax}`
                  }}
                />
              )}
            </div>

            {/* ── xG Underperf ── params: sotMin, minuteMax */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  title={xgParams.enabled ? "Desactivar xG Underperf" : "Activar xG Underperf"}
                  onClick={() => { setXGParams(p => ({ ...p, enabled: !p.enabled })); setActivePreset(null) }}
                  className={`relative w-7 h-3.5 rounded-full transition-colors shrink-0 ${xgParams.enabled ? "bg-amber-600" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-2.5 h-2.5 rounded-full bg-white transition-transform ${xgParams.enabled ? "translate-x-3.5" : ""}`} />
                </button>
                <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                <span className="text-xs text-zinc-400 w-24 shrink-0">xG Underperf</span>
                {xgParams.enabled && (<>
                  <span className="text-[10px] text-zinc-600 shrink-0">SoT≥</span>
                  <input type="number" min={0} max={5} step={1}
                    title="SoT mínimo"
                    placeholder="0"
                    value={xgParams.sotMin}
                    onChange={e => { setXGParams(p => ({ ...p, sotMin: parseInt(e.target.value) || 0 })); setActivePreset(null) }}
                    className="w-12 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[10px] text-zinc-600 shrink-0">Min'</span>
                  <input type="number" min={0} max={89} step={5}
                    value={xgParams.minuteMin === 0 ? "" : xgParams.minuteMin}
                    placeholder="0"
                    onChange={e => { setXGParams(p => ({ ...p, minuteMin: e.target.value === "" ? 0 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[9px] text-zinc-600">–</span>
                  <input type="number" min={1} max={90} step={5}
                    value={xgParams.minuteMax >= 90 ? "" : xgParams.minuteMax}
                    placeholder="90"
                    onChange={e => { setXGParams(p => ({ ...p, minuteMax: e.target.value === "" ? 90 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button key={opt} type="button" onClick={() => updateMinDur({ ...minDur, xg: opt })}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${minDur.xg === opt ? "bg-amber-500/25 text-amber-400 border border-amber-500/40" : opt === DEFAULT_MIN_DUR.xg ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40" : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"}`}
                      >{opt}</button>
                    ))}
                  </div>
                  <button type="button" onClick={() => runOptimizer("xg")}
                    className="ml-auto text-[10px] text-zinc-600 hover:text-amber-400 transition-colors">✦ opt</button>
                </>)}
              </div>
              {optimizerOpen === "xg" && optimizerResults && (
                <OptimizerPanel
                  strategyKey="xg"
                  results={optimizerResults.results}
                  minBets={optimizerMinBets}
                  onChangeMinBets={n => { setOptimizerMinBets(n); runOptimizer("xg") }}
                  onApply={r => { setXGParams(r.params as XGFilterParams); setOptimizerOpen(null) }}
                  onClose={() => setOptimizerOpen(null)}
                  renderParams={r => {
                    const p = r.params as XGFilterParams
                    return `SoT≥${p.sotMin} Min<${p.minuteMax >= 90 ? "∞" : p.minuteMax}`
                  }}
                />
              )}
            </div>

            {/* ── Odds Drift ── params: driftMin, oddsMax, goalDiffMin, minuteMin */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  title={driftParams.enabled ? "Desactivar Odds Drift" : "Activar Odds Drift"}
                  onClick={() => { setDriftParams(p => ({ ...p, enabled: !p.enabled })); setActivePreset(null) }}
                  className={`relative w-7 h-3.5 rounded-full transition-colors shrink-0 ${driftParams.enabled ? "bg-emerald-600" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-2.5 h-2.5 rounded-full bg-white transition-transform ${driftParams.enabled ? "translate-x-3.5" : ""}`} />
                </button>
                <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                <span className="text-xs text-zinc-400 w-24 shrink-0">Odds Drift</span>
                {driftParams.enabled && (<>
                  <span className="text-[10px] text-zinc-600 shrink-0">Δ≥</span>
                  <input type="number" min={30} max={200} step={10}
                    value={driftParams.driftMin}
                    onChange={e => { setDriftParams(p => ({ ...p, driftMin: parseInt(e.target.value) || 30 })); setActivePreset(null) }}
                    className="w-12 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                    title="Drift mínimo %"
                  />
                  <span className="text-[10px] text-zinc-600 shrink-0">%</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">Cuota≤</span>
                  <input type="number" min={2} max={20} step={0.5}
                    value={isFinite(driftParams.oddsMax) ? driftParams.oddsMax : ""}
                    placeholder="∞"
                    onChange={e => { setDriftParams(p => ({ ...p, oddsMax: e.target.value === "" ? Infinity : parseFloat(e.target.value) })); setActivePreset(null) }}
                    className="w-12 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[10px] text-zinc-600 shrink-0">Goles≥</span>
                  <input type="number" min={0} max={4} step={1}
                    title="Goles diferencia mínima"
                    placeholder="0"
                    value={driftParams.goalDiffMin}
                    onChange={e => { setDriftParams(p => ({ ...p, goalDiffMin: parseInt(e.target.value) || 0 })); setActivePreset(null) }}
                    className="w-12 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[10px] text-zinc-600 shrink-0">Min'</span>
                  <input type="number" min={0} max={89} step={5}
                    value={driftParams.minuteMin === 0 ? "" : driftParams.minuteMin}
                    placeholder="0"
                    onChange={e => { setDriftParams(p => ({ ...p, minuteMin: e.target.value === "" ? 0 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[9px] text-zinc-600">–</span>
                  <input type="number" min={1} max={90} step={5}
                    value={driftParams.minuteMax >= 90 ? "" : driftParams.minuteMax}
                    placeholder="90"
                    onChange={e => { setDriftParams(p => ({ ...p, minuteMax: e.target.value === "" ? 90 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button key={opt} type="button" onClick={() => updateMinDur({ ...minDur, drift: opt })}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${minDur.drift === opt ? "bg-amber-500/25 text-amber-400 border border-amber-500/40" : opt === DEFAULT_MIN_DUR.drift ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40" : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"}`}
                      >{opt}</button>
                    ))}
                  </div>
                  <button type="button" onClick={() => runOptimizer("drift")}
                    className="ml-auto text-[10px] text-zinc-600 hover:text-amber-400 transition-colors">✦ opt</button>
                </>)}
              </div>
              {optimizerOpen === "drift" && optimizerResults && (
                <OptimizerPanel
                  strategyKey="drift"
                  results={optimizerResults.results}
                  minBets={optimizerMinBets}
                  onChangeMinBets={n => { setOptimizerMinBets(n); runOptimizer("drift") }}
                  onApply={r => { setDriftParams(r.params as DriftFilterParams); setOptimizerOpen(null) }}
                  onClose={() => setOptimizerOpen(null)}
                  renderParams={r => {
                    const p = r.params as DriftFilterParams
                    return `Δ≥${p.driftMin}% Cuota≤${isFinite(p.oddsMax) ? p.oddsMax : "∞"} Goles≥${p.goalDiffMin}`
                  }}
                />
              )}
            </div>

            {/* ── Goal Clustering ── params: minuteMax, xgRemMin */}
            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <button
                  type="button"
                  title={clusteringParams.enabled ? "Desactivar Goal Clustering" : "Activar Goal Clustering"}
                  onClick={() => { setClusteringParams(p => ({ ...p, enabled: !p.enabled })); setActivePreset(null) }}
                  className={`relative w-7 h-3.5 rounded-full transition-colors shrink-0 ${clusteringParams.enabled ? "bg-rose-600" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-2.5 h-2.5 rounded-full bg-white transition-transform ${clusteringParams.enabled ? "translate-x-3.5" : ""}`} />
                </button>
                <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" />
                <span className="text-xs text-zinc-400 w-24 shrink-0">Goal Clustering</span>
                {clusteringParams.enabled && (<>
                  <span className="text-[10px] text-zinc-600 shrink-0">Min'</span>
                  <input type="number" min={0} max={89} step={5}
                    value={clusteringParams.minuteMin === 0 ? "" : clusteringParams.minuteMin}
                    placeholder="0"
                    onChange={e => { setClusteringParams(p => ({ ...p, minuteMin: e.target.value === "" ? 0 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[9px] text-zinc-600">–</span>
                  <input type="number" min={1} max={90} step={5}
                    value={clusteringParams.minuteMax >= 90 ? "" : clusteringParams.minuteMax}
                    placeholder="90"
                    onChange={e => { setClusteringParams(p => ({ ...p, minuteMax: e.target.value === "" ? 90 : parseInt(e.target.value) })); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[10px] text-zinc-600 shrink-0">xGrem≥</span>
                  <input type="number" min={0} max={2} step={0.1}
                    value={clusteringParams.xgRemMin === 0 ? "" : clusteringParams.xgRemMin}
                    placeholder="0"
                    onChange={e => { setClusteringParams(p => ({ ...p, xgRemMin: e.target.value === "" ? 0 : parseFloat(e.target.value) })); setActivePreset(null) }}
                    className="w-12 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button key={opt} type="button" onClick={() => updateMinDur({ ...minDur, clustering: opt })}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${minDur.clustering === opt ? "bg-amber-500/25 text-amber-400 border border-amber-500/40" : opt === DEFAULT_MIN_DUR.clustering ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40" : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"}`}
                      >{opt}</button>
                    ))}
                  </div>
                  <button type="button" onClick={() => runOptimizer("clustering")}
                    className="ml-auto text-[10px] text-zinc-600 hover:text-amber-400 transition-colors">✦ opt</button>
                </>)}
              </div>
              {optimizerOpen === "clustering" && optimizerResults && (
                <OptimizerPanel
                  strategyKey="clustering"
                  results={optimizerResults.results}
                  minBets={optimizerMinBets}
                  onChangeMinBets={n => { setOptimizerMinBets(n); runOptimizer("clustering") }}
                  onApply={r => { setClusteringParams(r.params as ClusteringFilterParams); setOptimizerOpen(null) }}
                  onClose={() => setOptimizerOpen(null)}
                  renderParams={r => {
                    const p = r.params as ClusteringFilterParams
                    return `Min<${p.minuteMax >= 80 ? "∞" : p.minuteMax} xGrem≥${p.xgRemMin}`
                  }}
                />
              )}
            </div>

            {/* Pressure Cooker */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="w-2 h-2 rounded-full bg-orange-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Pressure Cooker</span>
              <div className="flex gap-1.5 flex-wrap">
                {PRESSURE_CARTERA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setPressureVer(v.key === pressureVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                      pressureVer === v.key
                        ? v.key === "off" ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600" : "bg-orange-500/20 text-orange-400 border border-orange-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
              {pressureVer !== "off" && (
                <>
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => updateMinDur({ ...minDur, pressure: opt })}
                        title={`${opt} capturas${opt === DEFAULT_MIN_DUR.pressure ? " (recomendado)" : ""}`}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${
                          minDur.pressure === opt
                            ? "bg-amber-500/25 text-amber-400 border border-amber-500/40"
                            : opt === DEFAULT_MIN_DUR.pressure
                              ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40"
                              : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                  <span className="text-[10px] text-zinc-600 shrink-0">Min'</span>
                  <input type="number" min={0} max={89} step={5}
                    value={pressureMinuteMin === 0 ? "" : pressureMinuteMin}
                    placeholder="0"
                    onChange={e => { setPressureMinuteMin(e.target.value === "" ? 0 : parseInt(e.target.value)); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                  <span className="text-[9px] text-zinc-600">–</span>
                  <input type="number" min={1} max={90} step={5}
                    value={pressureMinuteMax >= 90 ? "" : pressureMinuteMax}
                    placeholder="90"
                    onChange={e => { setPressureMinuteMax(e.target.value === "" ? 90 : parseInt(e.target.value)); setActivePreset(null) }}
                    className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                  />
                </>
              )}
            </div>

            {/* Tarde Asia */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Tarde Asia <span className="text-[9px] text-zinc-600">({tardeAsiaBets.length})</span></span>
              <div className="flex gap-1.5 flex-wrap">
                {TARDE_ASIA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setTardeAsiaVer(v.key === tardeAsiaVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                      tardeAsiaVer === v.key
                        ? v.key === "off" ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600" : "bg-blue-500/20 text-blue-400 border border-blue-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
              {tardeAsiaVer !== "off" && (<>
                <span className="text-[10px] text-zinc-600 shrink-0">Min'</span>
                <input type="number" min={0} max={89} step={5}
                  value={tardeAsiaMinuteMin === 0 ? "" : tardeAsiaMinuteMin}
                  placeholder="0"
                  onChange={e => { setTardeAsiaMinuteMin(e.target.value === "" ? 0 : parseInt(e.target.value)); setActivePreset(null) }}
                  className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                />
                <span className="text-[9px] text-zinc-600">–</span>
                <input type="number" min={1} max={90} step={5}
                  value={tardeAsiaMinuteMax >= 90 ? "" : tardeAsiaMinuteMax}
                  placeholder="90"
                  onChange={e => { setTardeAsiaMinuteMax(e.target.value === "" ? 90 : parseInt(e.target.value)); setActivePreset(null) }}
                  className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                />
              </>)}
            </div>

            {/* Momentum x xG */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="w-2 h-2 rounded-full bg-violet-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Momentum x xG <span className="text-[9px] text-zinc-600">({momentumXGBets.length})</span></span>
              <div className="flex gap-1.5 flex-wrap">
                {MOMENTUM_XG_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setMomentumXGVer(v.key === momentumXGVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                      momentumXGVer === v.key
                        ? v.key === "off" ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600" : "bg-violet-500/20 text-violet-400 border border-violet-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
              {momentumXGVer !== "off" && (<>
                <span className="text-[10px] text-zinc-600 shrink-0">Min'</span>
                <input type="number" min={0} max={89} step={5}
                  value={momentumMinuteMin === 0 ? "" : momentumMinuteMin}
                  placeholder="0"
                  onChange={e => { setMomentumMinuteMin(e.target.value === "" ? 0 : parseInt(e.target.value)); setActivePreset(null) }}
                  className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                />
                <span className="text-[9px] text-zinc-600">–</span>
                <input type="number" min={1} max={90} step={5}
                  value={momentumMinuteMax >= 90 ? "" : momentumMinuteMax}
                  placeholder="90"
                  onChange={e => { setMomentumMinuteMax(e.target.value === "" ? 90 : parseInt(e.target.value)); setActivePreset(null) }}
                  className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[10px] text-zinc-300 text-center"
                />
              </>)}
            </div>

          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          title="Apuestas"
          value={`${sim.total}`}
          description={`${sim.winPct}% WR (${sim.wins}/${sim.total})`}
        />
        <MetricCard
          title="P/L Flat"
          value={`${sim.flatPl >= 0 ? "+" : ""}${sim.flatPl.toFixed(2)} EUR`}
          description={`ROI: ${sim.flatRoi >= 0 ? "+" : ""}${sim.flatRoi.toFixed(1)}% (${flatStake} EUR/apuesta)`}
        />
        <MetricCard
          title="P/L Gestion"
          value={`${sim.managedPl >= 0 ? "+" : ""}${sim.managedPl.toFixed(2)} EUR`}
          description={`ROI: ${sim.managedRoi >= 0 ? "+" : ""}${sim.managedRoi.toFixed(1)}% | ${BANKROLL_MODES.find(m => m.key === brMode)!.label} | ${sim.managedFinalBankroll.toFixed(0)}/${bankrollInit} EUR`}
        />
        <MetricCard
          title="EV/apuesta"
          value={`${evPerBet >= 0 ? "+" : ""}${evPerBet.toFixed(2)} EUR`}
          description={`Ganancia media por señal ejecutada`}
        />
        <MetricCard
          title="Profit/día"
          value={`${dailyProfit >= 0 ? "+" : ""}${dailyProfit.toFixed(2)} EUR`}
          description={`${betsPerDay.toFixed(1)} apuestas/día · ${activeDays} días activos`}
        />
        <MetricCard
          title="Cuota media"
          value={`${avgOdds.toFixed(2)}`}
          description={`Break-even WR: ${avgOdds > 0 ? (100 / avgOdds).toFixed(1) : "—"}%  ·  Edge: ${avgOdds > 0 ? (sim.winPct - 100 / avgOdds).toFixed(1) : "—"}pp`}
        />
      </div>

      {/* Time + Score Risk Analysis */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <button
          type="button"
          onClick={() => setShowRiskAnalysis(v => !v)}
          className="w-full flex items-center justify-between group"
        >
          <div className="text-left">
            <h2 className="text-sm font-semibold text-zinc-300">Análisis de Riesgo Tiempo + Marcador</h2>
            <p className="text-[10px] text-zinc-500 mt-0.5">Comparativa de rendimiento según limitación de tiempo y déficit</p>
          </div>
          <span className={`text-zinc-500 group-hover:text-zinc-300 transition-transform duration-200 text-xs ml-4 ${showRiskAnalysis ? "rotate-180" : ""}`}>▼</span>
        </button>
        {showRiskAnalysis && (<><div className="mt-4 grid grid-cols-1 md:grid-cols-4 gap-3">
          {/* No Risk */}
          <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-xs font-semibold text-green-400">Sin Riesgo</span>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Apuestas:</span>
                <span className="text-zinc-300 font-medium">{riskBreakdown.no_risk.count}</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Win Rate:</span>
                <span className="text-green-400 font-medium">{riskBreakdown.no_risk.winPct.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">P/L:</span>
                <span className={`font-medium ${riskBreakdown.no_risk.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {riskBreakdown.no_risk.pl >= 0 ? "+" : ""}{riskBreakdown.no_risk.pl.toFixed(0)} EUR
                </span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">ROI:</span>
                <span className={`font-medium ${riskBreakdown.no_risk.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {riskBreakdown.no_risk.roi >= 0 ? "+" : ""}{riskBreakdown.no_risk.roi.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* Medium Risk */}
          <div className="bg-orange-500/5 border border-orange-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-orange-500" />
              <span className="text-xs font-semibold text-orange-400">Riesgo Medio</span>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Apuestas:</span>
                <span className="text-zinc-300 font-medium">{riskBreakdown.medium_risk.count}</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Win Rate:</span>
                <span className="text-orange-400 font-medium">{riskBreakdown.medium_risk.winPct.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">P/L:</span>
                <span className={`font-medium ${riskBreakdown.medium_risk.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {riskBreakdown.medium_risk.pl >= 0 ? "+" : ""}{riskBreakdown.medium_risk.pl.toFixed(0)} EUR
                </span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">ROI:</span>
                <span className={`font-medium ${riskBreakdown.medium_risk.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {riskBreakdown.medium_risk.roi >= 0 ? "+" : ""}{riskBreakdown.medium_risk.roi.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* High Risk */}
          <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <span className="text-xs font-semibold text-red-400">Alto Riesgo</span>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Apuestas:</span>
                <span className="text-zinc-300 font-medium">{riskBreakdown.high_risk.count}</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Win Rate:</span>
                <span className="text-red-400 font-medium">{riskBreakdown.high_risk.winPct.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">P/L:</span>
                <span className={`font-medium ${riskBreakdown.high_risk.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {riskBreakdown.high_risk.pl >= 0 ? "+" : ""}{riskBreakdown.high_risk.pl.toFixed(0)} EUR
                </span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">ROI:</span>
                <span className={`font-medium ${riskBreakdown.high_risk.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {riskBreakdown.high_risk.roi >= 0 ? "+" : ""}{riskBreakdown.high_risk.roi.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>

          {/* Combined Risk */}
          <div className="bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2 h-2 rounded-full bg-yellow-500" />
              <span className="text-xs font-semibold text-yellow-400">Total Con Riesgo</span>
            </div>
            <div className="space-y-1.5">
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Apuestas:</span>
                <span className="text-zinc-300 font-medium">{riskBreakdown.combined_risk.count}</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">Win Rate:</span>
                <span className="text-yellow-400 font-medium">{riskBreakdown.combined_risk.winPct.toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">P/L:</span>
                <span className={`font-medium ${riskBreakdown.combined_risk.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {riskBreakdown.combined_risk.pl >= 0 ? "+" : ""}{riskBreakdown.combined_risk.pl.toFixed(0)} EUR
                </span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-zinc-500">ROI:</span>
                <span className={`font-medium ${riskBreakdown.combined_risk.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {riskBreakdown.combined_risk.roi >= 0 ? "+" : ""}{riskBreakdown.combined_risk.roi.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        </div>
        {riskBreakdown.combined_risk.count > 0 && (
          <div className="mt-3 pt-3 border-t border-zinc-800">
            <div className="text-[10px] text-zinc-500 leading-relaxed">
              <span className="text-yellow-400 font-medium">Conclusión:</span> {
                riskBreakdown.no_risk.roi > riskBreakdown.combined_risk.roi
                  ? `Las apuestas sin riesgo tiempo/marcador tienen ${(riskBreakdown.no_risk.roi - riskBreakdown.combined_risk.roi).toFixed(1)}% mejor ROI. Considera filtrar señales con riesgo alto.`
                  : riskBreakdown.combined_risk.roi > riskBreakdown.no_risk.roi
                  ? `Las apuestas con riesgo tienen ${(riskBreakdown.combined_risk.roi - riskBreakdown.no_risk.roi).toFixed(1)}% mejor ROI. El sistema de detección de valor funciona incluso con limitación de tiempo.`
                  : `El rendimiento es similar entre apuestas con y sin riesgo.`
              }
            </div>
          </div>
        )}
        </>)}
      </div>

      {/* Risk metrics */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <button
          type="button"
          onClick={() => setShowRiskMetrics(v => !v)}
          className="w-full flex items-center justify-between group"
        >
          <h2 className="text-sm font-semibold text-zinc-300">Riesgo</h2>
          <span className={`text-zinc-500 group-hover:text-zinc-300 transition-transform duration-200 text-xs ml-4 ${showRiskMetrics ? "rotate-180" : ""}`}>▼</span>
        </button>
        {showRiskMetrics && <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
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
                <div>Bankroll de {round2(bankrollInit + sim.managedMaxDd.peak)} cayo a {round2(bankrollInit + sim.managedMaxDd.trough)} EUR</div>
                <div>Apuestas #{sim.managedMaxDd.peakIdx + 1} a #{sim.managedMaxDd.troughIdx + 1} | Nunca bajo de {bankrollInit} EUR</div>
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
        </div>}
      </div>

      {/* Cumulative P/L Chart */}
      {chartData.length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">P/L Acumulado - {selLabel}</h2>
          <p className="text-xs text-zinc-500 mb-4">
            Flat ({flatStake} EUR) vs {BANKROLL_MODES.find(m => m.key === brMode)!.label} ({bankrollInit} EUR bankroll).
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
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter={((value: number | undefined, name: string | undefined) => {
                  if (value == null) return ["—", name ?? ""]
                  if (name === "managedPeak") return [`${value.toFixed(2)} EUR`, "Pico gestion"]
                  if (name === "flat") return [`${value.toFixed(2)} EUR`, "Flat (10 EUR)"]
                  if (name === "managed") {
                    const point = chartData.find(d => Math.abs(d.managed - value) < 0.01)
                    const dd = point ? round2(point.managedPeak - point.managed) : 0
                    const modeLabel = BANKROLL_MODES.find(m => m.key === brMode)!.label
                    return [`${value.toFixed(2)} EUR${dd > 0.01 ? ` (DD: -${dd.toFixed(2)})` : ""}`, modeLabel]
                  }
                  return [`${value.toFixed(2)} EUR`, name ?? ""]
                }) as any}
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
              <span className="text-[10px] text-zinc-500 font-mono">{s.bets} bets</span>
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

      {/* Daily Performance Visualization */}
      {filteredBets.length > 0 && (() => {
        // Group bets by day
        const dailyData = new Map<string, { date: string, pl: number, stake: number, won: number, total: number }>()

        filteredBets.forEach(bet => {
          const betAny = bet as any
          const timestamp = betAny.timestamp_utc || ""
          if (!timestamp) return

          // Extract date (YYYY-MM-DD)
          const date = timestamp.split(" ")[0] || timestamp.split("T")[0]
          if (!date) return

          const pl = bet.pl || 0
          const stake = 10 // Default stake
          const won = bet.won ? 1 : 0

          if (!dailyData.has(date)) {
            dailyData.set(date, { date, pl: 0, stake: 0, won: 0, total: 0 })
          }

          const day = dailyData.get(date)!
          day.pl += pl
          day.stake += stake
          day.won += won
          day.total += 1
        })

        // Convert to array and sort by date
        const dailyArray = Array.from(dailyData.values()).sort((a, b) => a.date.localeCompare(b.date))

        // Calculate ROI for each day
        const chartData = dailyArray.map(day => ({
          date: day.date,
          pl: parseFloat(day.pl.toFixed(2)),
          roi: day.stake > 0 ? parseFloat(((day.pl / day.stake) * 100).toFixed(1)) : 0,
          winRate: day.total > 0 ? parseFloat(((day.won / day.total) * 100).toFixed(1)) : 0,
          bets: day.total
        }))

        if (chartData.length === 0) return null

        return (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-zinc-300 mb-1">Rendimiento Diario</h2>
            <p className="text-xs text-zinc-500 mb-4">
              P/L y ROI agregados por día
            </p>

            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    dataKey="date"
                    stroke="#52525b"
                    tick={{ fill: "#71717a", fontSize: 11 }}
                    tickFormatter={(date) => {
                      const parts = date.split("-")
                      return parts.length === 3 ? `${parts[2]}/${parts[1]}` : date
                    }}
                  />
                  <YAxis
                    yAxisId="left"
                    stroke="#52525b"
                    tick={{ fill: "#71717a", fontSize: 11 }}
                    label={{ value: "P/L (EUR)", angle: -90, position: "insideLeft", fill: "#71717a", fontSize: 11 }}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    stroke="#52525b"
                    tick={{ fill: "#71717a", fontSize: 11 }}
                    label={{ value: "ROI (%)", angle: 90, position: "insideRight", fill: "#71717a", fontSize: 11 }}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      border: "1px solid #27272a",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    formatter={((value: number | undefined, name: string | undefined) => {
                      if (value == null) return ["—", name ?? ""]
                      if (name === "pl") return [`${value.toFixed(2)} EUR`, "P/L"]
                      if (name === "roi") return [`${value.toFixed(1)}%`, "ROI"]
                      if (name === "winRate") return [`${value.toFixed(1)}%`, "Win Rate"]
                      return [value, name ?? ""]
                    }) as any}
                    labelFormatter={(label) => `Fecha: ${label}`}
                    content={({ active, payload }) => {
                      if (!active || !payload || !payload.length) return null
                      const data = payload[0].payload
                      return (
                        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                          <div className="text-xs text-zinc-400 mb-2">{data.date}</div>
                          <div className="space-y-1">
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">P/L:</span>
                              <span className={`text-sm font-semibold ${data.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {data.pl >= 0 ? "+" : ""}{data.pl.toFixed(2)} EUR
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">ROI:</span>
                              <span className={`text-sm font-semibold ${data.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {data.roi >= 0 ? "+" : ""}{data.roi.toFixed(1)}%
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">Win Rate:</span>
                              <span className="text-sm font-semibold text-blue-400">{data.winRate.toFixed(1)}%</span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">Apuestas:</span>
                              <span className="text-sm font-semibold text-zinc-300">{data.bets}</span>
                            </div>
                          </div>
                        </div>
                      )
                    }}
                  />
                  <ReferenceLine yAxisId="left" y={0} stroke="#52525b" strokeDasharray="3 3" />
                  <Bar yAxisId="left" dataKey="pl" fill="#a855f7" radius={[4, 4, 0, 0]}>
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.pl >= 0 ? "#10b981" : "#ef4444"} />
                    ))}
                  </Bar>
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="roi"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ fill: "#3b82f6", r: 3 }}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )
      })()}

      {/* Distribution by League */}
      {(() => {
        const leagueStats = new Map<string, { pl: number; stake: number; wins: number; total: number; pais: string }>()

        filteredBets.forEach((bet) => {
          const liga = bet.Liga || "Desconocida"
          const pais = bet.País || "Desconocido"
          const existing = leagueStats.get(liga) || { pl: 0, stake: 0, wins: 0, total: 0, pais }

          existing.pl += bet.pl ?? 0
          existing.stake += 10 // Fixed stake
          existing.total += 1
          if ((bet.pl ?? 0) > 0) {
            existing.wins += 1
          }

          leagueStats.set(liga, existing)
        })

        const leagueData = Array.from(leagueStats.entries())
          .map(([liga, stats]) => ({
            liga,
            pais: stats.pais,
            pl: round2(stats.pl),
            roi: stats.stake > 0 ? round2((stats.pl / stats.stake) * 100) : 0,
            winRate: stats.total > 0 ? round2((stats.wins / stats.total) * 100) : 0,
            bets: stats.total,
          }))
          .sort((a, b) => b.pl - a.pl) // Sort by P/L descending
          .slice(0, 15) // Top 15 leagues

        if (leagueData.length === 0) return null

        return (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-zinc-300 mb-1">Distribución por Liga</h2>
            <p className="text-xs text-zinc-500 mb-4">
              Top 15 ligas por P/L - rendimiento y volumen de apuestas
            </p>

            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  layout="vertical"
                  data={leagueData}
                  margin={{ top: 10, right: 30, left: 120, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    type="number"
                    stroke="#52525b"
                    tick={{ fill: "#71717a", fontSize: 11 }}
                  />
                  <YAxis
                    type="category"
                    dataKey="liga"
                    stroke="#52525b"
                    tick={{ fill: "#71717a", fontSize: 10 }}
                    width={110}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      border: "1px solid #27272a",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    content={({ active, payload }) => {
                      if (!active || !payload || !payload.length) return null
                      const data = payload[0].payload
                      return (
                        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                          <div className="text-xs font-semibold text-zinc-300 mb-1">{data.liga}</div>
                          <div className="text-xs text-zinc-500 mb-2">{data.pais}</div>
                          <div className="space-y-1">
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">P/L:</span>
                              <span className={`text-sm font-semibold ${data.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {data.pl >= 0 ? "+" : ""}{data.pl.toFixed(2)} EUR
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">ROI:</span>
                              <span className={`text-sm font-semibold ${data.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {data.roi >= 0 ? "+" : ""}{data.roi.toFixed(1)}%
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">Win Rate:</span>
                              <span className="text-sm font-semibold text-blue-400">{data.winRate.toFixed(1)}%</span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">Apuestas:</span>
                              <span className="text-sm font-semibold text-zinc-300">{data.bets}</span>
                            </div>
                          </div>
                        </div>
                      )
                    }}
                  />
                  <ReferenceLine x={0} stroke="#52525b" strokeDasharray="3 3" />
                  <Bar dataKey="pl" radius={[0, 4, 4, 0]}>
                    {leagueData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.pl >= 0 ? "#10b981" : "#ef4444"} />
                    ))}
                  </Bar>
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )
      })()}

      {/* Distribution by Country */}
      {(() => {
        const countryStats = new Map<string, { pl: number; stake: number; wins: number; total: number }>()

        filteredBets.forEach((bet) => {
          const pais = bet.País || "Desconocido"
          const existing = countryStats.get(pais) || { pl: 0, stake: 0, wins: 0, total: 0 }

          existing.pl += bet.pl ?? 0
          existing.stake += 10 // Fixed stake
          existing.total += 1
          if ((bet.pl ?? 0) > 0) {
            existing.wins += 1
          }

          countryStats.set(pais, existing)
        })

        const countryData = Array.from(countryStats.entries())
          .map(([pais, stats]) => ({
            pais,
            pl: round2(stats.pl),
            roi: stats.stake > 0 ? round2((stats.pl / stats.stake) * 100) : 0,
            winRate: stats.total > 0 ? round2((stats.wins / stats.total) * 100) : 0,
            bets: stats.total,
          }))
          .sort((a, b) => b.pl - a.pl) // Sort by P/L descending
          .slice(0, 15) // Top 15 countries

        if (countryData.length === 0) return null

        return (
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold text-zinc-300 mb-1">Distribución por País</h2>
            <p className="text-xs text-zinc-500 mb-4">
              Top 15 países por P/L - rendimiento y volumen de apuestas
            </p>

            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  layout="vertical"
                  data={countryData}
                  margin={{ top: 10, right: 30, left: 100, bottom: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis
                    type="number"
                    stroke="#52525b"
                    tick={{ fill: "#71717a", fontSize: 11 }}
                  />
                  <YAxis
                    type="category"
                    dataKey="pais"
                    stroke="#52525b"
                    tick={{ fill: "#71717a", fontSize: 10 }}
                    width={90}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#18181b",
                      border: "1px solid #27272a",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    content={({ active, payload }) => {
                      if (!active || !payload || !payload.length) return null
                      const data = payload[0].payload
                      return (
                        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
                          <div className="text-xs font-semibold text-zinc-300 mb-2">{data.pais}</div>
                          <div className="space-y-1">
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">P/L:</span>
                              <span className={`text-sm font-semibold ${data.pl >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {data.pl >= 0 ? "+" : ""}{data.pl.toFixed(2)} EUR
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">ROI:</span>
                              <span className={`text-sm font-semibold ${data.roi >= 0 ? "text-green-400" : "text-red-400"}`}>
                                {data.roi >= 0 ? "+" : ""}{data.roi.toFixed(1)}%
                              </span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">Win Rate:</span>
                              <span className="text-sm font-semibold text-blue-400">{data.winRate.toFixed(1)}%</span>
                            </div>
                            <div className="flex items-center justify-between gap-4">
                              <span className="text-xs text-zinc-500">Apuestas:</span>
                              <span className="text-sm font-semibold text-zinc-300">{data.bets}</span>
                            </div>
                          </div>
                        </div>
                      )
                    }}
                  />
                  <ReferenceLine x={0} stroke="#52525b" strokeDasharray="3 3" />
                  <Bar dataKey="pl" radius={[0, 4, 4, 0]}>
                    {countryData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.pl >= 0 ? "#10b981" : "#ef4444"} />
                    ))}
                  </Bar>
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )
      })()}

      {/* Combined Bets Table */}
      {filteredBets.length > 0 && (() => {
        const _sortedIdxs = filteredBets.map((_, i) => i)
        const _histMult = histSort.dir === "asc" ? 1 : -1
        _sortedIdxs.sort((a, b) => {
          const ba = filteredBets[a], bb = filteredBets[b]
          const da = sim.betDetails[a], db = sim.betDetails[b]
          switch (histSort.col) {
            case "date": return _histMult * ((ba.timestamp_utc ?? "") < (bb.timestamp_utc ?? "") ? -1 : 1)
            case "strategy": return _histMult * (ba.strategy_label ?? "").localeCompare(bb.strategy_label ?? "")
            case "type": return _histMult * getBetType(ba).localeCompare(getBetType(bb))
            case "match": return _histMult * (ba.match ?? "").localeCompare(bb.match ?? "")
            case "min": return _histMult * ((ba.minuto ?? 0) - (bb.minuto ?? 0))
            case "odds": return _histMult * (getBetOdds(ba) - getBetOdds(bb))
            case "ft": return _histMult * ((ba.won ? 1 : 0) - (bb.won ? 1 : 0))
            case "pl": return _histMult * (ba.pl - bb.pl)
            case "flatCum": return _histMult * ((sim.flatCumulative[a] ?? 0) - (sim.flatCumulative[b] ?? 0))
            case "stake": return _histMult * ((da?.stake ?? 0) - (db?.stake ?? 0))
            case "plManaged": return _histMult * ((da?.plManaged ?? 0) - (db?.plManaged ?? 0))
            case "managedCum": return _histMult * ((sim.managedCumulative[a] ?? 0) - (sim.managedCumulative[b] ?? 0))
            case "bankroll": return _histMult * ((da?.bankrollAfter ?? 0) - (db?.bankrollAfter ?? 0))
            case "co": return _histMult * ((ba.cashout_applied ? 1 : 0) - (bb.cashout_applied ? 1 : 0))
            default: return 0
          }
        })
        const sortedHistIndexes = _sortedIdxs

        const thSort = (col: string, align: "left" | "right" | "center" = "right") => {
          const active = histSort.col === col
          return (
            <th
              className={`text-${align} py-2 px-1.5 text-xs font-medium cursor-pointer select-none whitespace-nowrap ${active ? "text-blue-400" : "text-zinc-500 hover:text-zinc-300"}`}
              onClick={() => setHistSort(prev => prev.col === col ? { col, dir: prev.dir === "asc" ? "desc" : "asc" } : { col, dir: "asc" })}
            >
              {col === "date" ? "Fecha" : col === "strategy" ? "Estrategia" : col === "type" ? "Tipo" : col === "match" ? "Partido" : col === "min" ? "Min" : col === "odds" ? "Odds" : col === "ft" ? "FT" : col === "co" ? "CO" : col === "pl" ? "P/L Flat" : col === "flatCum" ? "Acum. Flat" : col === "stake" ? "Stake" : col === "plManaged" ? "P/L Gestion" : col === "managedCum" ? "Acum. Gestion" : "Bankroll"}
              <span className="ml-0.5">{active ? (histSort.dir === "asc" ? "▲" : "▼") : "⇅"}</span>
            </th>
          )
        }

        return (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-zinc-300 mb-1">Historial de apuestas</h2>
          <p className="text-xs text-zinc-500 mb-4">
            {selLabel} | {BANKROLL_MODES.find(m => m.key === brMode)!.label} — haz clic en una columna para ordenar.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800">
                  <th className="text-center py-2 px-1.5 text-xs font-medium text-zinc-500">#</th>
                  {thSort("date", "left")}
                  {thSort("strategy", "left")}
                  {thSort("type", "left")}
                  {thSort("match", "left")}
                  {thSort("min")}
                  {thSort("odds")}
                  {thSort("ft", "center")}
                  {adjCashout && thSort("co", "center")}
                  {thSort("pl")}
                  {thSort("flatCum")}
                  {thSort("stake")}
                  {thSort("plManaged")}
                  {thSort("managedCum")}
                  {thSort("bankroll")}
                </tr>
              </thead>
              <tbody>
                {sortedHistIndexes.map((origIdx) => {
                  const b = filteredBets[origIdx]
                  const det = sim.betDetails[origIdx]
                  const odds = getBetOdds(b)
                  return (
                    <tr
                      key={`${b.match_id}-${b.strategy}-${origIdx}`}
                      className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                    >
                      <td className="py-2 px-1.5 text-center text-xs text-zinc-600">{origIdx + 1}</td>
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
                      <td className="py-2 px-1.5 text-xs">
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/15 text-blue-400">
                          {getBetType(b)}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-zinc-300 text-xs max-w-[160px] truncate" title={b.match}>{b.match}</td>
                      <td className="py-2 px-1.5 text-right text-zinc-400 text-xs">{b.minuto ?? "-"}</td>
                      <td className="py-2 px-1.5 text-right text-zinc-400 text-xs">{odds.toFixed(2)}</td>
                      <td className="py-2 px-1.5 text-center text-xs">
                        <span className={b.won ? "text-green-400" : "text-red-400"}>{b.ft_score}</span>
                      </td>
                      {adjCashout && (
                        <td className="py-2 px-1.5 text-center text-xs">
                          {b.cashout_applied ? (() => {
                            const saved = (b.pl + 10) * flatStake / 10
                            return (
                              <span
                                className={`inline-flex flex-col items-center px-1.5 py-0.5 rounded text-[10px] font-medium leading-tight ${saved >= 0 ? "bg-cyan-500/20 text-cyan-400" : "bg-amber-500/20 text-amber-400"}`}
                                title={`Cash-out en min ~${b.cashout_minute_actual ?? "?"} · Lay ${b.cashout_lay_odds?.toFixed(2) ?? "?"}`}
                              >
                                <span>CO</span>
                                <span>{saved >= 0 ? "+" : ""}{saved.toFixed(2)}</span>
                              </span>
                            )
                          })() : <span className="text-zinc-700">—</span>}
                        </td>
                      )}
                      <td className="py-2 px-1.5 text-right text-xs font-medium">
                        <span className={b.pl >= 0 ? "text-green-400" : "text-red-400"}>
                          {b.pl >= 0 ? "+" : ""}{(b.pl * flatStake / 10).toFixed(2)}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-right text-xs font-mono">
                        <span className={(sim.flatCumulative[origIdx] ?? 0) >= 0 ? "text-blue-400" : "text-red-400"}>
                          {(sim.flatCumulative[origIdx] ?? 0) >= 0 ? "+" : ""}{(sim.flatCumulative[origIdx] ?? 0).toFixed(2)}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-right text-xs text-purple-400">{det?.stake.toFixed(2) ?? "-"}</td>
                      <td className="py-2 px-1.5 text-right text-xs font-medium">
                        <span className={(det?.plManaged ?? 0) >= 0 ? "text-green-400" : "text-red-400"}>
                          {det ? `${det.plManaged >= 0 ? "+" : ""}${det.plManaged.toFixed(2)}` : "-"}
                        </span>
                      </td>
                      <td className="py-2 px-1.5 text-right text-xs font-mono">
                        <span className={(sim.managedCumulative[origIdx] ?? 0) >= 0 ? "text-purple-400" : "text-red-400"}>
                          {(sim.managedCumulative[origIdx] ?? 0) >= 0 ? "+" : ""}{(sim.managedCumulative[origIdx] ?? 0).toFixed(2)}
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
      )
      })()}

      {filteredBets.length === 0 && (
        <div className="text-center py-12 text-zinc-500 text-sm">
          No hay apuestas en la cartera.
        </div>
      )}
    </div>
  )
}

// ── Optimizer Results Panel ───────────────────────────────────────────────

function OptimizerPanel({
  strategyKey: _strategyKey,
  results,
  minBets,
  onChangeMinBets,
  onApply,
  onClose,
  renderParams,
}: {
  strategyKey?: string
  results: OptimizeResult<any>[]
  minBets: number
  onChangeMinBets: (n: number) => void
  onApply: (r: OptimizeResult<any>) => void
  onClose: () => void
  renderParams: (r: OptimizeResult<any>) => string
}) {
  type SortKey = "roi" | "pl" | "wr" | "nBets"
  const [sortKey, setSortKey] = useState<SortKey>("pl")
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc")

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => d === "desc" ? "asc" : "desc")
    else { setSortKey(key); setSortDir("desc") }
  }

  const sorted = [...results].sort((a, b) => {
    const diff = a[sortKey] - b[sortKey]
    return sortDir === "desc" ? -diff : diff
  })

  const SortIndicator = ({ k }: { k: SortKey }) =>
    sortKey === k ? <span className="ml-0.5">{sortDir === "desc" ? "▼" : "▲"}</span> : null

  const COL_TITLES: Record<SortKey, string> = {
    roi: "ROI — Retorno sobre lo apostado (%). Mayor = más eficiente por unidad apostada.",
    pl: "P/L — Beneficio neto en EUR (suma de ganancias - pérdidas). Mayor = más dinero ganado.",
    wr: "WR — Win Rate: porcentaje de apuestas ganadas. Mayor = más aciertos.",
    nBets: "N — Número total de apuestas generadas con esta combinación de parámetros.",
  }

  const ColHeader = ({ k, label, className }: { k: SortKey; label: string; className?: string }) => (
    <button type="button" onClick={() => handleSort(k)} title={COL_TITLES[k]}
      className={`text-right text-[9px] uppercase tracking-wider transition-colors select-none ${sortKey === k ? "text-amber-400" : "text-zinc-600 hover:text-zinc-400"} ${className ?? ""}`}
    >{label}<SortIndicator k={k} /></button>
  )

  return (
    <div className="ml-9 bg-zinc-900/70 border border-amber-900/30 rounded-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-amber-500/80 font-semibold uppercase tracking-wider">Optimizador</span>
          <span className="text-[9px] text-zinc-600 shrink-0">mín bets</span>
          <input type="number" min={1} max={50} step={1} title="Mínimo de apuestas" placeholder="5"
            value={minBets}
            onChange={e => onChangeMinBets(parseInt(e.target.value) || 1)}
            className="w-10 px-1 py-0.5 rounded bg-zinc-800 border border-zinc-700 text-[9px] text-zinc-300 text-center"
          />
        </div>
        <button type="button" onClick={onClose} title="Cerrar" className="text-zinc-600 hover:text-zinc-400 text-[10px] transition-colors">✕</button>
      </div>
      {results.length === 0 ? (
        <div className="text-[10px] text-zinc-500 py-2">Sin combinaciones con ≥{minBets} apuestas</div>
      ) : (
        <div className="space-y-1">
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-x-3 pb-1 border-b border-zinc-800">
            <span className="text-[9px] text-zinc-600 uppercase tracking-wider">Params</span>
            <ColHeader k="roi" label="ROI" />
            <ColHeader k="pl" label="P/L" />
            <ColHeader k="wr" label="WR" />
            <ColHeader k="nBets" label="N" />
            <span />
          </div>
          {sorted.map((r, i) => (
            <div key={i} className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-x-3 items-center py-0.5 hover:bg-zinc-800/30 rounded">
              <span className="text-[9px] text-zinc-300 font-mono truncate">{renderParams(r)}</span>
              <span className={`text-[9px] text-right font-mono ${r.roi >= 0 ? "text-emerald-400" : "text-red-400"}`}>{r.roi >= 0 ? "+" : ""}{r.roi.toFixed(1)}%</span>
              <span className={`text-[9px] text-right font-mono ${r.pl >= 0 ? "text-emerald-400" : "text-red-400"}`}>{r.pl >= 0 ? "+" : ""}{r.pl.toFixed(1)}</span>
              <span className="text-[9px] text-right text-zinc-400">{r.wr.toFixed(0)}%</span>
              <span className="text-[9px] text-right text-zinc-500">{r.nBets}</span>
              <button type="button" onClick={() => onApply(r)}
                className="text-[9px] text-amber-600 hover:text-amber-400 transition-colors whitespace-nowrap">Aplicar</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
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
