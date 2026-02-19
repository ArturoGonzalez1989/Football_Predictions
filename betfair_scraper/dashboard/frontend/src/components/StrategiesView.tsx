import { useState, useEffect, useRef } from "react"
import { api, type Cartera, type CarteraBet, type CarteraConfig } from "../lib/api"
import {
  type DrawVersion, type XGCarteraVersion, type DriftCarteraVersion,
  type ClusteringCarteraVersion, type PressureCarteraVersion, type TardeAsiaVersion, type MomentumXGVersion,
  type BankrollMode, type PresetKey,
  PRESETS, DRAW_VERSIONS, XG_CARTERA_VERSIONS, DRIFT_CARTERA_VERSIONS,
  CLUSTERING_CARTERA_VERSIONS, PRESSURE_CARTERA_VERSIONS, TARDE_ASIA_VERSIONS, MOMENTUM_XG_VERSIONS, BANKROLL_MODES,
  round2,
  filterDrawBets, filterXGBets, filterDriftBets, filterClusteringBets, filterPressureBets, filterTardeAsiaBets, filterMomentumXGBets,
  simulateCartera, findBestCombo, getBetOdds,
  type RealisticAdjustments, DEFAULT_ADJUSTMENTS,
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

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      try {
        const data = await api.getCartera()
        setCartera(data)
      } catch (e) {
        console.error("Error loading cartera:", e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

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

      <CarteraTab data={cartera} />
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
  return {
    drawVer: (cfg.versions.draw || "v1") as DrawVersion,
    xgVer: (cfg.versions.xg || "base") as XGCarteraVersion,
    driftVer: (cfg.versions.drift || "v1") as DriftCarteraVersion,
    clusteringVer: (cfg.versions.clustering || "v2") as ClusteringCarteraVersion,
    pressureVer: (cfg.versions.pressure || "v1") as PressureCarteraVersion,
    tardeAsiaVer: (cfg.versions.tarde_asia || "off") as TardeAsiaVersion,
    momentumXGVer: (cfg.versions.momentum_xg || "off") as MomentumXGVersion,
    brMode: (cfg.bankroll_mode || "fixed") as BankrollMode,
    activePreset: (cfg.active_preset || null) as PresetKey,
    riskFilter: (cfg.risk_filter || "all") as RiskFilter,
    realistic: cfg.adjustments.enabled ?? false,
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

function CarteraTab({ data }: { data: Cartera }) {
  const [drawVer, setDrawVer] = useState<DrawVersion>(savedState?.drawVer || "v1")
  const [xgVer, setXgVer] = useState<XGCarteraVersion>(savedState?.xgVer || "base")
  const [driftVer, setDriftVer] = useState<DriftCarteraVersion>(savedState?.driftVer || "v1")
  const [clusteringVer, setClusteringVer] = useState<ClusteringCarteraVersion>(savedState?.clusteringVer || "v2")
  const [pressureVer, setPressureVer] = useState<PressureCarteraVersion>(savedState?.pressureVer || "v1")
  const [tardeAsiaVer, setTardeAsiaVer] = useState<TardeAsiaVersion>(savedState?.tardeAsiaVer || "off")
  const [momentumXGVer, setMomentumXGVer] = useState<MomentumXGVersion>(savedState?.momentumXGVer || "off")
  const [brMode, setBrMode] = useState<BankrollMode>(savedState?.brMode || "fixed")
  const [activePreset, setActivePreset] = useState<PresetKey>(savedState?.activePreset || null)
  const [realistic, setRealistic] = useState(savedState?.realistic || false)
  const [adjDedup, setAdjDedup] = useState(savedState?.adjDedup !== undefined ? savedState.adjDedup : true)
  const [adjMaxOdds, setAdjMaxOdds] = useState(savedState?.adjMaxOdds || 6.0)
  const [adjMinOdds, setAdjMinOdds] = useState(savedState?.adjMinOdds || 1.15)
  const [adjDriftMinMin, setAdjDriftMinMin] = useState(savedState?.adjDriftMinMin || 15)
  const [adjSlippage, setAdjSlippage] = useState(savedState?.adjSlippage || 2)
  const [adjConflictFilter, setAdjConflictFilter] = useState(savedState?.adjConflictFilter !== undefined ? savedState.adjConflictFilter : true)
  const [adjCashout, setAdjCashout] = useState<boolean>(savedState?.adjCashout ?? false)
  const [adjCashoutMinute, setAdjCashoutMinute] = useState<number>(savedState?.adjCashoutMinute ?? 70)
  const [riskFilter, setRiskFilter] = useState<RiskFilter>(savedState?.riskFilter || "all")
  const [minDur, setMinDur] = useState<MinDurConfig>(savedState?.minDur || DEFAULT_MIN_DUR)
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle")
  const configLoadedRef = useRef(false)

  // Load config from backend on mount (overrides localStorage if backend has saved config)
  useEffect(() => {
    if (configLoadedRef.current) return
    configLoadedRef.current = true
    api.getConfig()
      .then(cfg => {
        const s = configToState(cfg)
        setDrawVer(s.drawVer)
        setXgVer(s.xgVer)
        setDriftVer(s.driftVer)
        setClusteringVer(s.clusteringVer)
        setPressureVer(s.pressureVer)
        setTardeAsiaVer(s.tardeAsiaVer)
        setMomentumXGVer(s.momentumXGVer)
        setBrMode(s.brMode)
        setActivePreset(s.activePreset)
        setRiskFilter(s.riskFilter)
        setRealistic(s.realistic)
        setAdjDedup(s.adjDedup)
        setAdjMaxOdds(s.adjMaxOdds)
        setAdjMinOdds(s.adjMinOdds)
        setAdjDriftMinMin(s.adjDriftMinMin)
        setAdjSlippage(s.adjSlippage)
        setAdjConflictFilter(s.adjConflictFilter)
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
  }

  /** Build CarteraConfig from current component state */
  const buildConfig = (): CarteraConfig => ({
    versions: {
      draw: drawVer,
      xg: xgVer,
      drift: driftVer,
      clustering: clusteringVer,
      pressure: pressureVer,
      tarde_asia: tardeAsiaVer,
      momentum_xg: momentumXGVer,
    },
    bankroll_mode: brMode,
    active_preset: activePreset,
    risk_filter: riskFilter,
    min_duration: minDur,
    adjustments: {
      enabled: realistic,
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
          drawVer, xgVer, driftVer, clusteringVer, pressureVer, tardeAsiaVer, momentumXGVer,
          brMode, activePreset, realistic, adjDedup, adjMaxOdds, adjMinOdds, adjDriftMinMin,
          adjSlippage, adjConflictFilter, adjCashout, adjCashoutMinute, riskFilter, minDur,
        }))
        setSaveStatus("saved")
        setTimeout(() => setSaveStatus("idle"), 2000)
      })
      .catch(() => setSaveStatus("error"))
  }

  // Reset filters to defaults and save to backend
  const resetFilters = () => {
    setDrawVer("v1")
    setXgVer("base")
    setDriftVer("v1")
    setClusteringVer("v2")
    setPressureVer("v1")
    setTardeAsiaVer("off")
    setMomentumXGVer("off")
    setBrMode("fixed")
    setActivePreset(null)
    setRealistic(false)
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
    localStorage.removeItem(STORAGE_KEY)
  }

  // Use CO-adjusted data when CO is active, otherwise original data
  const { managed, bets } = (adjCashout && coData) ? coData : data

  const applyPreset = (key: Exclude<PresetKey, null>) => {
    const combo = findBestCombo(bets, managed.initial_bankroll, key, riskFilter)
    setDrawVer(combo.draw)
    setXgVer(combo.xg)
    setDriftVer(combo.drift)
    setClusteringVer(combo.clustering)
    setPressureVer(combo.pressure)
    setTardeAsiaVer(combo.tardeAsia)
    setMomentumXGVer(combo.momentumXG)
    setBrMode(combo.br)
    setActivePreset(key)
  }

  // Filter bets by selected versions, then re-sort chronologically
  const drawBets = filterDrawBets(bets, drawVer)
  const xgBets = filterXGBets(bets, xgVer)
  const driftBets = filterDriftBets(bets, driftVer)
  const clusteringBets = filterClusteringBets(bets, clusteringVer)
  const pressureBets = filterPressureBets(bets, pressureVer)
  const tardeAsiaBets = filterTardeAsiaBets(bets, tardeAsiaVer)
  const momentumXGBets = filterMomentumXGBets(bets, momentumXGVer)
  const rawBets = [...drawBets, ...xgBets, ...driftBets, ...clusteringBets, ...pressureBets, ...tardeAsiaBets, ...momentumXGBets].sort((a, b) =>
    (a.timestamp_utc || "").localeCompare(b.timestamp_utc || "")
  )

  // Apply realistic adjustments if enabled
  const currentAdj: RealisticAdjustments = realistic
    ? { dedup: adjDedup, maxOdds: adjMaxOdds, minOdds: adjMinOdds, driftMinMinute: adjDriftMinMin, slippagePct: adjSlippage, conflictFilter: adjConflictFilter }
    : DEFAULT_ADJUSTMENTS
  let filteredBets = realistic ? applyRealisticAdjustments(rawBets, currentAdj) : rawBets
  const removedCount = rawBets.length - filteredBets.length

  // Apply risk filter
  filteredBets = filterByRisk(filteredBets, riskFilter)

  // Calculate risk breakdown for analysis
  const riskBreakdown = analyzeRiskBreakdown(filteredBets)

  const handleDownloadCSV = () => {
    const csv = generateCarteraCSV(filteredBets)
    const timestamp = new Date().toISOString().split('T')[0]
    const presetLabel = activePreset ? `_${activePreset}` : ''
    const realisticLabel = realistic ? '_realista' : ''
    downloadCSV(`cartera${presetLabel}${realisticLabel}_${timestamp}.csv`, csv)
  }

  // Recalculate simulations
  const sim = simulateCartera(filteredBets, managed.initial_bankroll, brMode)
  // Also calculate ideal sim for comparison when realistic mode is on
  const idealSim = realistic ? simulateCartera(rawBets, managed.initial_bankroll, brMode) : null

  // Per-strategy stats
  const stratConfigs = [
    { key: "back_draw_00", label: "Back Empate 0-0", bgClass: "bg-cyan-500", active: drawVer !== "off", verLabel: drawVer !== "off" ? DRAW_VERSIONS.find(v => v.key === drawVer)!.label : "" },
    { key: "xg_underperformance", label: "xG Underperformance", bgClass: "bg-amber-500", active: xgVer !== "off", verLabel: xgVer !== "off" ? XG_CARTERA_VERSIONS.find(v => v.key === xgVer)!.label : "" },
    { key: "odds_drift", label: "Odds Drift", bgClass: "bg-emerald-500", active: driftVer !== "off", verLabel: driftVer !== "off" ? DRIFT_CARTERA_VERSIONS.find(v => v.key === driftVer)!.label : "" },
    { key: "goal_clustering", label: "Goal Clustering", bgClass: "bg-rose-500", active: clusteringVer !== "off", verLabel: clusteringVer !== "off" ? CLUSTERING_CARTERA_VERSIONS.find(v => v.key === clusteringVer)!.label : "" },
    { key: "pressure_cooker", label: "Pressure Cooker", bgClass: "bg-orange-500", active: pressureVer !== "off", verLabel: pressureVer !== "off" ? PRESSURE_CARTERA_VERSIONS.find(v => v.key === pressureVer)!.label : "" },
    { key: "tarde_asia", label: "Tarde Asia", bgClass: "bg-blue-500", active: tardeAsiaVer !== "off", verLabel: tardeAsiaVer !== "off" ? TARDE_ASIA_VERSIONS.find(v => v.key === tardeAsiaVer)!.label : "" },
    { key: "momentum_xg", label: "Momentum x xG", bgClass: "bg-violet-500", active: momentumXGVer !== "off", verLabel: momentumXGVer !== "off" ? MOMENTUM_XG_VERSIONS.find(v => v.key === momentumXGVer)!.label : "" },
  ]

  const stratStats = stratConfigs.filter(s => s.active).map(s => {
    // For momentum_xg, match both v1 and v2 strategy keys
    const sBets = filteredBets.filter(b =>
      s.key === "momentum_xg"
        ? (b.strategy === "momentum_xg_v1" || b.strategy === "momentum_xg_v2")
        : b.strategy === s.key
    )
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
              {realistic && removedCount > 0 && <span className="text-yellow-600/80 ml-1.5">· {removedCount} eliminadas por modo realista</span>}
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
        {/* 3-column control grid: Presets | Risk+Bankroll | Realistic */}
        <div className="grid grid-cols-3 gap-6 pb-5 mb-5 border-b border-zinc-800">
          {/* Col 1: Presets */}
          <div>
            <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2.5">Presets</div>
            <div className="flex flex-col gap-1.5">
              {PRESETS.map(p => (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => applyPreset(p.key)}
                  className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-[11px] font-medium transition-all text-left ${
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

          {/* Col 2: Risk Filter + Bankroll */}
          <div className="space-y-4">
            <div>
              <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2.5">Filtro de Riesgo</div>
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
            <div>
              <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2.5">Gestión Bankroll</div>
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

          {/* Col 3: Modo Realista */}
          <div>
            <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2.5">Modo Realista</div>
            <div className="flex items-center gap-2.5 mb-2">
              <button
                type="button"
                onClick={() => setRealistic(!realistic)}
                title="Activar modo realista"
                className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ${realistic ? "bg-yellow-500" : "bg-zinc-700"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${realistic ? "translate-x-5" : ""}`} />
              </button>
              <span className={`text-xs font-medium ${realistic ? "text-yellow-400" : "text-zinc-500"}`}>
                {realistic ? "ON" : "OFF"}
              </span>
              {realistic && (
                <button
                  type="button"
                  onClick={() => { setAdjDedup(true); setAdjMaxOdds(6.0); setAdjMinOdds(1.15); setAdjDriftMinMin(15); setAdjSlippage(2); setAdjConflictFilter(true) }}
                  className="text-[10px] text-yellow-600 hover:text-yellow-400 transition-colors ml-1"
                >
                  reset
                </button>
              )}
            </div>
            <p className="text-[10px] text-zinc-600">
              {realistic
                ? (removedCount > 0 ? `${removedCount} apuestas filtradas de ${rawBets.length}` : `Sin filtros aplicados (${rawBets.length})`)
                : "Simulación ideal sin ajustes de ejecución"}
            </p>
          </div>
        </div>

        {/* Realistic Adjustments — full-width row, only when enabled */}
        {realistic && (
          <div className="grid grid-cols-7 gap-2.5 pb-5 mb-5 border-b border-zinc-800">
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">Dedup</span>
                <button
                  type="button"
                  onClick={() => setAdjDedup(!adjDedup)}
                  title="Deduplicar apuestas"
                  className={`relative w-8 h-4 rounded-full transition-colors ${adjDedup ? "bg-yellow-500" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${adjDedup ? "translate-x-4" : ""}`} />
                </button>
              </div>
              <p className="text-[9px] text-zinc-600 leading-tight">1 apuesta / mercado</p>
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
              <p className="text-[9px] text-zinc-600 leading-tight">Excluye odds &lt; X</p>
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
              <p className="text-[9px] text-zinc-600 leading-tight">Excluye odds &gt; X</p>
            </div>
            <div className="bg-zinc-800/40 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-zinc-400 font-medium">Drift Min'</span>
                <input
                  type="number"
                  value={adjDriftMinMin}
                  onChange={e => setAdjDriftMinMin(parseInt(e.target.value) || 15)}
                  step="5"
                  min="5"
                  max="45"
                  title="Minuto minimo drift"
                  className="w-12 bg-zinc-900 border border-zinc-700 rounded px-1 py-0.5 text-[10px] text-yellow-400 text-right"
                />
              </div>
              <p className="text-[9px] text-zinc-600 leading-tight">Drift &lt; min X excluido</p>
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
              <p className="text-[9px] text-zinc-600 leading-tight">Reduce odds X%</p>
            </div>
            <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-2.5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-red-400/80 font-medium">Anti-conf</span>
                <button
                  type="button"
                  onClick={() => setAdjConflictFilter(!adjConflictFilter)}
                  title="Filtrar par toxico MomXG + xGUnderperf"
                  className={`relative w-8 h-4 rounded-full transition-colors ${adjConflictFilter ? "bg-red-600" : "bg-zinc-700"}`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${adjConflictFilter ? "translate-x-4" : ""}`} />
                </button>
              </div>
              <p className="text-[9px] text-red-900/80 leading-tight">MomXG+xGUnd=0%WR</p>
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
                <p className="text-[9px] text-cyan-900/80 leading-tight">Lay perdedoras ~min70</p>
              )}
            </div>
          </div>
        )}

        {/* Ideal vs Realistic comparison */}
        {realistic && idealSim && (
          <div className="mb-5 bg-yellow-500/5 border border-yellow-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-bold text-yellow-500 uppercase tracking-wider">Comparación Ideal vs Realista</span>
            </div>
            <div className="grid grid-cols-4 gap-4 text-center">
              <div>
                <div className="text-[10px] text-zinc-500 mb-0.5">Apuestas</div>
                <div className="text-xs text-zinc-400">{idealSim.total} → <span className="text-yellow-400 font-medium">{sim.total}</span></div>
              </div>
              <div>
                <div className="text-[10px] text-zinc-500 mb-0.5">Win Rate</div>
                <div className="text-xs text-zinc-400">{idealSim.winPct}% → <span className="text-yellow-400 font-medium">{sim.winPct}%</span></div>
              </div>
              <div>
                <div className="text-[10px] text-zinc-500 mb-0.5">P/L Flat</div>
                <div className="text-xs text-zinc-400">{idealSim.flatPl >= 0 ? "+" : ""}{idealSim.flatPl.toFixed(0)} → <span className={`font-medium ${sim.flatPl >= 0 ? "text-green-400" : "text-red-400"}`}>{sim.flatPl >= 0 ? "+" : ""}{sim.flatPl.toFixed(0)}</span></div>
              </div>
              <div>
                <div className="text-[10px] text-zinc-500 mb-0.5">ROI Flat</div>
                <div className="text-xs text-zinc-400">{idealSim.flatRoi >= 0 ? "+" : ""}{idealSim.flatRoi.toFixed(1)}% → <span className={`font-medium ${sim.flatRoi >= 0 ? "text-green-400" : "text-red-400"}`}>{sim.flatRoi >= 0 ? "+" : ""}{sim.flatRoi.toFixed(1)}%</span></div>
              </div>
            </div>
          </div>
        )}

        {/* Estrategias y Versiones */}
        <div>
          <div className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-3">Estrategias y Versiones</div>
          <div className="space-y-2">

            {/* Back Empate */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="w-2 h-2 rounded-full bg-cyan-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Back Empate</span>
              <div className="flex gap-1.5 flex-wrap">
                {DRAW_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setDrawVer(v.key === drawVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                      drawVer === v.key
                        ? v.key === "off" ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600" : "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
              {drawVer !== "off" && (
                <>
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => updateMinDur({ ...minDur, draw: opt })}
                        title={`${opt} capturas${opt === DEFAULT_MIN_DUR.draw ? " (recomendado)" : ""}`}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${
                          minDur.draw === opt
                            ? "bg-amber-500/25 text-amber-400 border border-amber-500/40"
                            : opt === DEFAULT_MIN_DUR.draw
                              ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40"
                              : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* xG Underperformance */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">xG Underperf</span>
              <div className="flex gap-1.5 flex-wrap">
                {XG_CARTERA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setXgVer(v.key === xgVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                      xgVer === v.key
                        ? v.key === "off" ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600" : "bg-amber-500/20 text-amber-400 border border-amber-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
              {xgVer !== "off" && (
                <>
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => updateMinDur({ ...minDur, xg: opt })}
                        title={`${opt} capturas${opt === DEFAULT_MIN_DUR.xg ? " (recomendado)" : ""}`}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${
                          minDur.xg === opt
                            ? "bg-amber-500/25 text-amber-400 border border-amber-500/40"
                            : opt === DEFAULT_MIN_DUR.xg
                              ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40"
                              : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Odds Drift */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Odds Drift</span>
              <div className="flex gap-1.5 flex-wrap">
                {DRIFT_CARTERA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setDriftVer(v.key === driftVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                      driftVer === v.key
                        ? v.key === "off" ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600" : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
              {driftVer !== "off" && (
                <>
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => updateMinDur({ ...minDur, drift: opt })}
                        title={`${opt} capturas${opt === DEFAULT_MIN_DUR.drift ? " (recomendado)" : ""}`}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${
                          minDur.drift === opt
                            ? "bg-amber-500/25 text-amber-400 border border-amber-500/40"
                            : opt === DEFAULT_MIN_DUR.drift
                              ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40"
                              : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Goal Clustering */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="w-2 h-2 rounded-full bg-rose-500 shrink-0" />
              <span className="text-xs text-zinc-400 w-28 shrink-0">Goal Clustering</span>
              <div className="flex gap-1.5 flex-wrap">
                {CLUSTERING_CARTERA_VERSIONS.map(v => (
                  <button
                    key={v.key}
                    type="button"
                    onClick={() => { setClusteringVer(v.key === clusteringVer && v.key !== "off" ? "off" : v.key); setActivePreset(null) }}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                      clusteringVer === v.key
                        ? v.key === "off" ? "bg-zinc-700/50 text-zinc-500 border border-zinc-600" : "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                        : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                    }`}
                    title={v.desc}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
              {clusteringVer !== "off" && (
                <>
                  <span className="text-zinc-700/50 mx-0.5 shrink-0">·</span>
                  <span className="text-[10px] text-zinc-600 shrink-0">min</span>
                  <div className="flex gap-1">
                    {MIN_DUR_OPTIONS.map(opt => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => updateMinDur({ ...minDur, clustering: opt })}
                        title={`${opt} capturas${opt === DEFAULT_MIN_DUR.clustering ? " (recomendado)" : ""}`}
                        className={`w-5 h-5 rounded text-[10px] font-bold transition-all ${
                          minDur.clustering === opt
                            ? "bg-amber-500/25 text-amber-400 border border-amber-500/40"
                            : opt === DEFAULT_MIN_DUR.clustering
                              ? "bg-zinc-800/80 text-amber-600 border border-amber-700/30 hover:border-amber-500/40"
                              : "bg-zinc-800/50 text-zinc-600 border border-zinc-700/50 hover:text-zinc-400"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </>
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

      {/* Time + Score Risk Analysis */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-zinc-300">Análisis de Riesgo Tiempo + Marcador</h2>
            <p className="text-[10px] text-zinc-500 mt-0.5">Comparativa de rendimiento según limitación de tiempo y déficit</p>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
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
                    formatter={(value: number, name: string) => {
                      if (name === "pl") return [`${value.toFixed(2)} EUR`, "P/L"]
                      if (name === "roi") return [`${value.toFixed(1)}%`, "ROI"]
                      if (name === "winRate") return [`${value.toFixed(1)}%`, "Win Rate"]
                      return [value, name]
                    }}
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
                  <th className="text-left py-2 px-1.5 text-xs font-medium text-zinc-500">Tipo</th>
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
