import type { CarteraBet } from "./api"

// ── Types ──────────────────────────────────────────────────────────────

export type DrawVersion = "v1" | "v15" | "v2r" | "v2" | "v3" | "off"
export type XGCarteraVersion = "base" | "v2" | "v3" | "off"
export type DriftCarteraVersion = "v1" | "v2" | "v3" | "v4" | "v5" | "v6" | "off"
export type ClusteringCarteraVersion = "v2" | "v3" | "v4" | "off"
export type PressureCarteraVersion = "v1" | "off"
export type TardeAsiaVersion = "v1" | "off"
export type MomentumXGVersion = "v1" | "v2" | "off"
export type BankrollMode = "fixed" | "kelly" | "half_kelly" | "dd_protection" | "variable" | "anti_racha"

export type PresetKey = "max_roi" | "max_pl" | "max_wr" | "min_dd" | "max_bets" | null

export interface VersionCombo {
  draw: DrawVersion
  xg: XGCarteraVersion
  drift: DriftCarteraVersion
  clustering: ClusteringCarteraVersion
  pressure: PressureCarteraVersion
  tardeAsia: TardeAsiaVersion
  momentumXG: MomentumXGVersion
  br: BankrollMode
}

// ── Constants ──────────────────────────────────────────────────────────

export const PRESETS: { key: Exclude<PresetKey, null>; label: string; icon: string; desc: string }[] = [
  { key: "max_roi", label: "Max ROI", icon: "%", desc: "Busca la combinacion de versiones que maximiza el retorno porcentual sobre lo apostado" },
  { key: "max_pl", label: "Max P/L", icon: "$", desc: "Maximiza el beneficio absoluto en EUR" },
  { key: "max_wr", label: "Max WR", icon: "W", desc: "Maximiza el porcentaje de acierto (con ligero bonus por mayor muestra)" },
  { key: "min_dd", label: "Min DD", icon: "D", desc: "Minimiza el drawdown relativo al P/L, tambien explora modo DD-protection de bankroll" },
  { key: "max_bets", label: "Max Datos", icon: "#", desc: "Selecciona todas las V1 para maximizar el tamano de muestra" },
]

export const DRAW_VERSIONS: { key: DrawVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1", desc: "Base" },
  { key: "v15", label: "V1.5", desc: "xG<0.6+PD<25%" },
  { key: "v2r", label: "V2r", desc: "xG<0.6+PD<20%+Sh<8" },
  { key: "v2", label: "V2", desc: "xG<0.5+PD<20%+Sh<8" },
  { key: "v3", label: "V3", desc: "V1.5+xGDom+LowPressV" },
  { key: "off", label: "OFF", desc: "" },
]

export const XG_CARTERA_VERSIONS: { key: XGCarteraVersion; label: string; desc: string }[] = [
  { key: "base", label: "V1", desc: "Base" },
  { key: "v2", label: "V2", desc: "SoT>=2" },
  { key: "v3", label: "V3", desc: "SoT>=2 + Min<70" },
  { key: "off", label: "OFF", desc: "" },
]

export const DRIFT_CARTERA_VERSIONS: { key: DriftCarteraVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1", desc: "Base" },
  { key: "v2", label: "V2", desc: "2+ goles" },
  { key: "v3", label: "V3", desc: "Drift>=100%" },
  { key: "v4", label: "V4", desc: "2a parte+Odds<=5" },
  { key: "v5", label: "V5", desc: "Odds<=5" },
  { key: "v6", label: "V6", desc: "V5+MomentumGap>200" },
  { key: "off", label: "OFF", desc: "" },
]

export const CLUSTERING_CARTERA_VERSIONS: { key: ClusteringCarteraVersion; label: string; desc: string }[] = [
  { key: "v2", label: "V2", desc: "SoT max>=3" },
  { key: "v3", label: "V3", desc: "SoT>=3 + Min<60" },
  { key: "v4", label: "V4", desc: "xG remaining>0.8" },
  { key: "off", label: "OFF", desc: "" },
]

export const PRESSURE_CARTERA_VERSIONS: { key: PressureCarteraVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1", desc: "Empate 1-1+ min 65-75" },
  { key: "off", label: "OFF", desc: "" },
]

export const TARDE_ASIA_VERSIONS: { key: TardeAsiaVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1", desc: "Tarde 14-20h + Liga Asia/Alemania/Francia" },
  { key: "off", label: "OFF", desc: "" },
]

export const MOMENTUM_XG_VERSIONS: { key: MomentumXGVersion; label: string; desc: string }[] = [
  { key: "v1", label: "V1", desc: "Ultra Relajadas" },
  { key: "v2", label: "V2", desc: "Máximas" },
  { key: "off", label: "OFF", desc: "" },
]

export const BANKROLL_MODES: { key: BankrollMode; label: string; desc: string }[] = [
  { key: "fixed", label: "Fijo 2%", desc: "Apuesta siempre el 2% del bankroll" },
  { key: "kelly", label: "Kelly", desc: "WR rolling, max 8% del bankroll por apuesta" },
  { key: "half_kelly", label: "Half-Kelly", desc: "Kelly/2 rolling, max 4% del bankroll" },
  { key: "dd_protection", label: "Proteccion DD", desc: "2% base, 1% si cae >5%, 0.5% si cae >10% del pico" },
  { key: "variable", label: "Variable", desc: "3% xG / 1.5% Draw" },
  { key: "anti_racha", label: "Anti-racha", desc: "2% base, 1% tras 1 fallo, 0.5% tras 2+ fallos consecutivos" },
]

// ── Helpers ─────────────────────────────────────────────────────────────

export function round2(n: number): number {
  return Math.round(n * 100) / 100
}

export function getBetOdds(b: CarteraBet): number {
  return b.back_draw ?? b.back_over_odds ?? (b as any).over_odds ?? b.back_odds ?? 2.0
}

/** Derive a short bet-type label from a CarteraBet, e.g. "Draw", "Away", "O 2.5" */
export function getBetType(b: CarteraBet): string {
  if (b.strategy === "back_draw_00") return "Draw"
  if (b.over_line) {
    // "Over 2.5" → "O 2.5"
    return b.over_line.replace("Over ", "O ")
  }
  if (b.team) return b.team  // "Home" or "Away"
  // Fallback: Over strategies without over_line — derive from score
  const isOverStrategy = b.strategy === "goal_clustering" || b.strategy === "pressure_cooker"
    || b.strategy === "tarde_asia" || b.strategy === "xg_underperformance"
  if (isOverStrategy) {
    const score = (b as any).score || (b as any).score_at_trigger || ""
    const parts = score.split("-")
    if (parts.length === 2) {
      const total = (parseInt(parts[0]) || 0) + (parseInt(parts[1]) || 0)
      return `O ${total + 0.5}`
    }
    return "Over"
  }
  return "-"
}

/** Deduplicate bets: if same match has the same bet type, keep only the first occurrence */
export function deduplicateBets(bets: CarteraBet[]): CarteraBet[] {
  const seen = new Set<string>()
  return bets.filter(b => {
    const key = `${b.match_id}::${getBetType(b)}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

// Min odds per strategy: (1 / win_rate) * 1.10
const MIN_ODDS_BY_STRATEGY: Record<string, number> = {
  back_draw_00: 1.93,       // 57.1% WR
  xg_underperformance: 1.51, // 72.7% WR
  odds_drift: 1.65,          // 66.7% WR
  goal_clustering: 1.73,     // 63.6% WR
  pressure_cooker: 1.83,     // 60.0% WR
  tarde_asia: 1.83,          // 60.0% WR estimado
  momentum_xg_v1: 1.65,      // 66.7% WR
  momentum_xg_v2: 1.83,      // 60.0% WR
}

function meetsMinOdds(b: CarteraBet): boolean {
  const odds = getBetOdds(b)
  const minOdds = MIN_ODDS_BY_STRATEGY[b.strategy] ?? 1.0
  return odds >= minOdds
}

// ── Strategy filter params (replaces discrete version selectors) ────────

export interface DrawFilterParams {
  enabled: boolean
  xgMax: number        // 1.0 = no filter (V1 base), 0.6 = V1.5/V2r, 0.5 = V2
  possMax: number      // 100 = no filter, 25 = V1.5, 20 = V2r/V2
  shotsMax: number     // 20 = no filter, 8 = V2r/V2
  xgDomAsym: boolean   // false = no filter, true = V3 xG-dominance asymmetry filter
}

export interface XGFilterParams {
  enabled: boolean
  sotMin: number    // 0 = no filter (base), 2 = V2+
  minuteMax: number // 90 = no filter, 70 = V3
}

export interface DriftFilterParams {
  enabled: boolean
  goalDiffMin: number  // 0 = no filter (V1), 2 = V2
  driftMin: number     // 30 = base trigger, 100 = V3
  oddsMax: number      // Infinity = no filter, 5 = V4/V5
  minuteMin: number    // 0 = no filter, 45 = V4
  momGapMin: number    // 0 = no filter, 200 = V6
}

export interface ClusteringFilterParams {
  enabled: boolean
  minuteMax: number  // 80 = base, 60 = V3
  xgRemMin: number   // 0 = no filter, 0.8 = V4
}

export const DEFAULT_DRAW_PARAMS: DrawFilterParams = { enabled: true, xgMax: 1.0, possMax: 100, shotsMax: 20, xgDomAsym: false }
export const DEFAULT_XG_PARAMS: XGFilterParams = { enabled: true, sotMin: 0, minuteMax: 90 }
export const DEFAULT_DRIFT_PARAMS: DriftFilterParams = { enabled: true, goalDiffMin: 0, driftMin: 30, oddsMax: Infinity, minuteMin: 0, momGapMin: 0 }
export const DEFAULT_CLUSTERING_PARAMS: ClusteringFilterParams = { enabled: true, minuteMax: 80, xgRemMin: 0 }

// ── Version → Params adapters (for preset system compatibility) ──────────

export function drawVersionToParams(v: DrawVersion): DrawFilterParams {
  if (v === "off")  return { ...DEFAULT_DRAW_PARAMS, enabled: false }
  if (v === "v1")   return { ...DEFAULT_DRAW_PARAMS, enabled: true }
  if (v === "v15")  return { enabled: true, xgMax: 0.6, possMax: 25, shotsMax: 20, xgDomAsym: false }
  if (v === "v2r")  return { enabled: true, xgMax: 0.6, possMax: 20, shotsMax: 8, xgDomAsym: false }
  if (v === "v2")   return { enabled: true, xgMax: 0.5, possMax: 20, shotsMax: 8, xgDomAsym: false }
  if (v === "v3")   return { enabled: true, xgMax: 0.6, possMax: 25, shotsMax: 20, xgDomAsym: true }
  return DEFAULT_DRAW_PARAMS
}

export function xgVersionToParams(v: XGCarteraVersion): XGFilterParams {
  if (v === "off")   return { ...DEFAULT_XG_PARAMS, enabled: false }
  if (v === "base")  return { ...DEFAULT_XG_PARAMS, enabled: true }
  if (v === "v2")    return { enabled: true, sotMin: 2, minuteMax: 90 }
  if (v === "v3")    return { enabled: true, sotMin: 2, minuteMax: 70 }
  return DEFAULT_XG_PARAMS
}

export function driftVersionToParams(v: DriftCarteraVersion): DriftFilterParams {
  if (v === "off")  return { ...DEFAULT_DRIFT_PARAMS, enabled: false }
  if (v === "v1")   return { ...DEFAULT_DRIFT_PARAMS, enabled: true }
  if (v === "v2")   return { enabled: true, goalDiffMin: 2, driftMin: 30, oddsMax: Infinity, minuteMin: 0, momGapMin: 0 }
  if (v === "v3")   return { enabled: true, goalDiffMin: 0, driftMin: 100, oddsMax: Infinity, minuteMin: 0, momGapMin: 0 }
  if (v === "v4")   return { enabled: true, goalDiffMin: 0, driftMin: 30, oddsMax: 5, minuteMin: 45, momGapMin: 0 }
  if (v === "v5")   return { enabled: true, goalDiffMin: 0, driftMin: 30, oddsMax: 5, minuteMin: 0, momGapMin: 0 }
  if (v === "v6")   return { enabled: true, goalDiffMin: 0, driftMin: 30, oddsMax: 5, minuteMin: 0, momGapMin: 200 }
  return DEFAULT_DRIFT_PARAMS
}

export function clusteringVersionToParams(v: ClusteringCarteraVersion): ClusteringFilterParams {
  if (v === "off")  return { ...DEFAULT_CLUSTERING_PARAMS, enabled: false }
  if (v === "v2")   return { ...DEFAULT_CLUSTERING_PARAMS, enabled: true }
  if (v === "v3")   return { enabled: true, minuteMax: 60, xgRemMin: 0 }
  if (v === "v4")   return { enabled: true, minuteMax: 80, xgRemMin: 0.8 }
  return DEFAULT_CLUSTERING_PARAMS
}

// ── Param-based filter functions ─────────────────────────────────────────

export function filterDrawBets(bets: CarteraBet[], p: DrawFilterParams): CarteraBet[] {
  if (!p.enabled) return []
  return bets.filter(b => {
    if (b.strategy !== "back_draw_00") return false
    if (p.xgMax < 1.0 && b.xg_total != null && b.xg_total >= p.xgMax) return false
    if (p.possMax < 100 && b.poss_diff != null && b.poss_diff >= p.possMax) return false
    if (p.shotsMax < 20 && b.shots_total != null && b.shots_total >= p.shotsMax) return false
    if (p.xgDomAsym && b.synth_xg_dominance != null) {
      if (b.synth_xg_dominance >= 0.45 && b.synth_xg_dominance <= 0.55) return false
    }
    return true
  })
}

export function filterXGBets(bets: CarteraBet[], p: XGFilterParams): CarteraBet[] {
  if (!p.enabled) return []
  return bets.filter(b => {
    if (b.strategy !== "xg_underperformance") return false
    if (p.sotMin > 0 && b.sot_team != null && b.sot_team < p.sotMin) return false
    if (p.minuteMax < 90 && b.minuto != null && b.minuto >= p.minuteMax) return false
    return true
  })
}

export function filterDriftBets(bets: CarteraBet[], p: DriftFilterParams): CarteraBet[] {
  if (!p.enabled) return []
  return bets.filter(b => {
    if (b.strategy !== "odds_drift") return false
    if (p.goalDiffMin > 0 && b.goal_diff != null && b.goal_diff < p.goalDiffMin) return false
    if (p.driftMin > 30 && b.drift_pct != null && b.drift_pct < p.driftMin) return false
    if (isFinite(p.oddsMax) && b.back_odds != null && b.back_odds > p.oddsMax) return false
    if (p.minuteMin > 0 && b.minuto != null && b.minuto <= p.minuteMin) return false
    if (p.momGapMin > 0 && b.synth_momentum_gap != null && b.synth_momentum_gap <= p.momGapMin) return false
    return true
  })
}

export function filterClusteringBets(bets: CarteraBet[], p: ClusteringFilterParams): CarteraBet[] {
  if (!p.enabled) return []
  return bets.filter(b => {
    if (b.strategy !== "goal_clustering") return false
    if (p.minuteMax < 80 && b.minuto != null && b.minuto >= p.minuteMax) return false
    if (p.xgRemMin > 0 && b.synth_xg_remaining != null && b.synth_xg_remaining < p.xgRemMin) return false
    return true
  })
}

export function filterPressureBets(bets: CarteraBet[], version: PressureCarteraVersion): CarteraBet[] {
  if (version === "off") return []
  return bets.filter(b => b.strategy === "pressure_cooker")
}

export function filterTardeAsiaBets(bets: CarteraBet[], version: TardeAsiaVersion): CarteraBet[] {
  if (version === "off") return []
  return bets.filter(b => b.strategy === "tarde_asia")
}

export function filterMomentumXGBets(bets: CarteraBet[], version: MomentumXGVersion): CarteraBet[] {
  if (version === "off") return []
  const momentumBets = bets.filter(b => b.strategy === "momentum_xg_v1" || b.strategy === "momentum_xg_v2")
  if (version === "v1") return momentumBets.filter(b => b.strategy === "momentum_xg_v1")
  if (version === "v2") return momentumBets.filter(b => b.strategy === "momentum_xg_v2")
  return momentumBets
}

// ── Drawdown & streaks ──────────────────────────────────────────────────

export interface DrawdownInfo {
  maxDd: number
  peak: number
  trough: number
  peakIdx: number
  troughIdx: number
  ddPct: number
}

export function calcMaxDrawdown(cumulative: number[]): DrawdownInfo {
  let peak = 0
  let peakIdx = -1
  let maxDd = 0
  let ddPeak = 0
  let ddTrough = 0
  let ddPeakIdx = 0
  let ddTroughIdx = 0
  for (let i = 0; i < cumulative.length; i++) {
    const v = cumulative[i]
    if (v > peak) { peak = v; peakIdx = i }
    const dd = peak - v
    if (dd > maxDd) {
      maxDd = dd
      ddPeak = peak
      ddTrough = v
      ddPeakIdx = peakIdx
      ddTroughIdx = i
    }
  }
  const ddPct = ddPeak > 0 ? round2(maxDd / ddPeak * 100) : 0
  return {
    maxDd: round2(maxDd), peak: round2(ddPeak), trough: round2(ddTrough),
    peakIdx: ddPeakIdx, troughIdx: ddTroughIdx, ddPct,
  }
}

export function calcWorstStreak(bets: CarteraBet[]): { losses: number; from: number; to: number; plLost: number } {
  let maxStreak = 0
  let maxFrom = 0
  let maxTo = 0
  let cur = 0
  let curFrom = 0
  let curPl = 0
  let maxPl = 0
  for (let i = 0; i < bets.length; i++) {
    if (bets[i].pl < 0) {
      if (cur === 0) { curFrom = i; curPl = 0 }
      cur++
      curPl += bets[i].pl
      if (cur > maxStreak) { maxStreak = cur; maxFrom = curFrom; maxTo = i; maxPl = curPl }
    } else {
      cur = 0
      curPl = 0
    }
  }
  return { losses: maxStreak, from: maxFrom + 1, to: maxTo + 1, plLost: round2(maxPl) }
}

// ── Simulation ──────────────────────────────────────────────────────────

export function simulateCartera(bets: CarteraBet[], bankrollInit: number, mode: BankrollMode) {
  const FLAT_STAKE = 10
  const KELLY_MIN_BETS = 5

  let flatCum = 0
  let bankroll = bankrollInit
  let peakBankroll = bankrollInit
  const flatCumArr: number[] = []
  const managedCumArr: number[] = []
  const betDetails: { stake: number; plManaged: number; bankrollAfter: number }[] = []
  let flatWins = 0
  let managedPl = 0
  let rollingWins = 0
  let consecutiveLosses = 0

  for (let i = 0; i < bets.length; i++) {
    const b = bets[i]
    flatCum = round2(flatCum + b.pl)
    flatCumArr.push(flatCum)
    if (b.won) flatWins++

    const rollingWR = i > 0 ? rollingWins / i : 0.5
    const odds = getBetOdds(b)
    const bNet = Math.max(odds - 1, 0.01)
    let stakePct: number

    switch (mode) {
      case "fixed":
        stakePct = 0.02
        break
      case "kelly": {
        if (i < KELLY_MIN_BETS) {
          stakePct = 0.02
        } else {
          const f = (rollingWR * bNet - (1 - rollingWR)) / bNet
          stakePct = Math.max(0, Math.min(f, 0.08))
        }
        break
      }
      case "half_kelly": {
        if (i < KELLY_MIN_BETS) {
          stakePct = 0.01
        } else {
          const f = (rollingWR * bNet - (1 - rollingWR)) / bNet
          stakePct = Math.max(0, Math.min(f / 2, 0.04))
        }
        break
      }
      case "dd_protection": {
        const ddFromPeak = peakBankroll > 0 ? (peakBankroll - bankroll) / peakBankroll : 0
        if (ddFromPeak > 0.10) stakePct = 0.005
        else if (ddFromPeak > 0.05) stakePct = 0.01
        else stakePct = 0.02
        break
      }
      case "variable":
        stakePct = b.strategy === "odds_drift" ? 0.025 : b.strategy === "xg_underperformance" ? 0.03 : b.strategy === "pressure_cooker" ? 0.02 : 0.015
        break
      case "anti_racha":
        if (consecutiveLosses >= 2) stakePct = 0.005
        else if (consecutiveLosses >= 1) stakePct = 0.01
        else stakePct = 0.02
        break
    }

    const stake = round2(bankroll * stakePct)
    const ratio = stake / FLAT_STAKE
    const managedBetPl = round2(b.pl * ratio)
    bankroll = round2(bankroll + managedBetPl)
    if (bankroll > peakBankroll) peakBankroll = bankroll
    managedPl = round2(managedPl + managedBetPl)
    managedCumArr.push(round2(bankroll - bankrollInit))
    betDetails.push({ stake, plManaged: managedBetPl, bankrollAfter: bankroll })

    if (b.won) { rollingWins++; consecutiveLosses = 0 } else { consecutiveLosses++ }
  }

  const totalStaked = bets.length * FLAT_STAKE
  const flatDd = calcMaxDrawdown(flatCumArr)
  const managedDd = calcMaxDrawdown(managedCumArr)
  const worstStreak = calcWorstStreak(bets)

  return {
    total: bets.length,
    wins: flatWins,
    winPct: bets.length > 0 ? round2(flatWins / bets.length * 100) : 0,
    flatPl: flatCum,
    flatRoi: totalStaked > 0 ? round2(flatCum / totalStaked * 100) : 0,
    flatCumulative: flatCumArr,
    flatMaxDd: flatDd,
    managedPl,
    managedRoi: bankrollInit > 0 ? round2(managedPl / bankrollInit * 100) : 0,
    managedFinalBankroll: bankroll,
    managedCumulative: managedCumArr,
    managedMaxDd: managedDd,
    worstStreak,
    betDetails,
  }
}

// ── Combo evaluation & optimization ────────────────────────────────────

export function evaluateCombo(bets: CarteraBet[], combo: VersionCombo, bankrollInit: number, riskFilter: RiskFilter = "all") {
  const drawBets = filterDrawBets(bets, drawVersionToParams(combo.draw))
  const xgBets = filterXGBets(bets, xgVersionToParams(combo.xg))
  const driftBets = filterDriftBets(bets, driftVersionToParams(combo.drift))
  const clusteringBets = filterClusteringBets(bets, clusteringVersionToParams(combo.clustering))
  const pressureBets = filterPressureBets(bets, combo.pressure)
  const tardeAsiaBets = filterTardeAsiaBets(bets, combo.tardeAsia)
  const momentumXGBets = filterMomentumXGBets(bets, combo.momentumXG)
  // Only include bets where odds >= strategy min_odds (EV positive)
  let filtered = [...drawBets, ...xgBets, ...driftBets, ...clusteringBets, ...pressureBets, ...tardeAsiaBets, ...momentumXGBets]
    .filter(meetsMinOdds)
    .sort((a, b) => (a.timestamp_utc || "").localeCompare(b.timestamp_utc || "")
  )

  // Apply risk filter
  filtered = filterByRisk(filtered, riskFilter)

  if (filtered.length === 0) return null
  const sim = simulateCartera(filtered, bankrollInit, combo.br)
  const riskBreakdown = analyzeRiskBreakdown(filtered)
  return { ...sim, combo, filtered, riskBreakdown }
}

// ── Per-strategy param optimizer ─────────────────────────────────────────

export interface OptimizeResult<P> {
  params: P
  roi: number
  pl: number
  wr: number
  nBets: number
  dd: number
}

/**
 * Build the combined filtered bet list from individual strategy params.
 * Used by the per-strategy optimizer to evaluate param combinations.
 */
export function buildCarteraBets(
  allBets: CarteraBet[],
  draw: DrawFilterParams,
  xg: XGFilterParams,
  drift: DriftFilterParams,
  clustering: ClusteringFilterParams,
  pressure: PressureCarteraVersion,
  tardeAsia: TardeAsiaVersion,
  momentumXG: MomentumXGVersion,
  riskFilter: RiskFilter = "all",
): CarteraBet[] {
  const combined = [
    ...filterDrawBets(allBets, draw),
    ...filterXGBets(allBets, xg),
    ...filterDriftBets(allBets, drift),
    ...filterClusteringBets(allBets, clustering),
    ...filterPressureBets(allBets, pressure),
    ...filterTardeAsiaBets(allBets, tardeAsia),
    ...filterMomentumXGBets(allBets, momentumXG),
  ]
    .filter(meetsMinOdds)
    .sort((a, b) => (a.timestamp_utc || "").localeCompare(b.timestamp_utc || ""))
  return filterByRisk(combined, riskFilter)
}

export function optimizeDrawParams(
  allBets: CarteraBet[],
  currentXG: XGFilterParams,
  currentDrift: DriftFilterParams,
  currentClustering: ClusteringFilterParams,
  currentPressure: PressureCarteraVersion,
  currentTardeAsia: TardeAsiaVersion,
  currentMomentumXG: MomentumXGVersion,
  bankrollInit: number,
  minBets = 5,
): OptimizeResult<DrawFilterParams>[] {
  const xgMaxOpts = [0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
  const possMaxOpts = [15, 20, 25, 30, 100]
  const shotsMaxOpts = [6, 8, 10, 20]
  const results: OptimizeResult<DrawFilterParams>[] = []

  for (const xgMax of xgMaxOpts) {
    for (const possMax of possMaxOpts) {
      for (const shotsMax of shotsMaxOpts) {
        const p: DrawFilterParams = { enabled: true, xgMax, possMax, shotsMax, xgDomAsym: false }
        const bets = buildCarteraBets(allBets, p, currentXG, currentDrift, currentClustering, currentPressure, currentTardeAsia, currentMomentumXG)
        if (bets.length < minBets) continue
        const sim = simulateCartera(bets, bankrollInit, "fixed")
        results.push({ params: p, roi: sim.flatRoi, pl: sim.flatPl, wr: sim.winPct, nBets: sim.total, dd: sim.flatMaxDd.ddPct })
      }
    }
  }

  return results.sort((a, b) => b.pl - a.pl).slice(0, 15)
}

export function optimizeXGParams(
  allBets: CarteraBet[],
  currentDraw: DrawFilterParams,
  currentDrift: DriftFilterParams,
  currentClustering: ClusteringFilterParams,
  currentPressure: PressureCarteraVersion,
  currentTardeAsia: TardeAsiaVersion,
  currentMomentumXG: MomentumXGVersion,
  bankrollInit: number,
  minBets = 5,
): OptimizeResult<XGFilterParams>[] {
  const sotMinOpts = [0, 1, 2, 3]
  const minuteMaxOpts = [60, 70, 80, 90]
  const results: OptimizeResult<XGFilterParams>[] = []

  for (const sotMin of sotMinOpts) {
    for (const minuteMax of minuteMaxOpts) {
      const p: XGFilterParams = { enabled: true, sotMin, minuteMax }
      const bets = buildCarteraBets(allBets, currentDraw, p, currentDrift, currentClustering, currentPressure, currentTardeAsia, currentMomentumXG)
      if (bets.length < minBets) continue
      const sim = simulateCartera(bets, bankrollInit, "fixed")
      results.push({ params: p, roi: sim.flatRoi, pl: sim.flatPl, wr: sim.winPct, nBets: sim.total, dd: sim.flatMaxDd.ddPct })
    }
  }

  return results.sort((a, b) => b.pl - a.pl).slice(0, 15)
}

export function optimizeDriftParams(
  allBets: CarteraBet[],
  currentDraw: DrawFilterParams,
  currentXG: XGFilterParams,
  currentClustering: ClusteringFilterParams,
  currentPressure: PressureCarteraVersion,
  currentTardeAsia: TardeAsiaVersion,
  currentMomentumXG: MomentumXGVersion,
  bankrollInit: number,
  minBets = 5,
): OptimizeResult<DriftFilterParams>[] {
  const goalDiffMinOpts = [0, 1, 2]
  const driftMinOpts = [30, 50, 100, 150]
  const oddsMaxOpts = [5, 7, 10, Infinity]
  const minuteMinOpts = [0, 30, 45]
  const results: OptimizeResult<DriftFilterParams>[] = []

  for (const goalDiffMin of goalDiffMinOpts) {
    for (const driftMin of driftMinOpts) {
      for (const oddsMax of oddsMaxOpts) {
        for (const minuteMin of minuteMinOpts) {
          const p: DriftFilterParams = { enabled: true, goalDiffMin, driftMin, oddsMax, minuteMin, momGapMin: 0 }
          const bets = buildCarteraBets(allBets, currentDraw, currentXG, p, currentClustering, currentPressure, currentTardeAsia, currentMomentumXG)
          if (bets.length < minBets) continue
          const sim = simulateCartera(bets, bankrollInit, "fixed")
          results.push({ params: p, roi: sim.flatRoi, pl: sim.flatPl, wr: sim.winPct, nBets: sim.total, dd: sim.flatMaxDd.ddPct })
        }
      }
    }
  }

  return results.sort((a, b) => b.pl - a.pl).slice(0, 15)
}

export function optimizeClusteringParams(
  allBets: CarteraBet[],
  currentDraw: DrawFilterParams,
  currentXG: XGFilterParams,
  currentDrift: DriftFilterParams,
  currentPressure: PressureCarteraVersion,
  currentTardeAsia: TardeAsiaVersion,
  currentMomentumXG: MomentumXGVersion,
  bankrollInit: number,
  minBets = 5,
): OptimizeResult<ClusteringFilterParams>[] {
  const minuteMaxOpts = [50, 60, 70, 80]
  const xgRemMinOpts = [0, 0.5, 0.8, 1.2]
  const results: OptimizeResult<ClusteringFilterParams>[] = []

  for (const minuteMax of minuteMaxOpts) {
    for (const xgRemMin of xgRemMinOpts) {
      const p: ClusteringFilterParams = { enabled: true, minuteMax, xgRemMin }
      const bets = buildCarteraBets(allBets, currentDraw, currentXG, currentDrift, p, currentPressure, currentTardeAsia, currentMomentumXG)
      if (bets.length < minBets) continue
      const sim = simulateCartera(bets, bankrollInit, "fixed")
      results.push({ params: p, roi: sim.flatRoi, pl: sim.flatPl, wr: sim.winPct, nBets: sim.total, dd: sim.flatMaxDd.ddPct })
    }
  }

  return results.sort((a, b) => b.pl - a.pl).slice(0, 15)
}

export function findBestCombo(bets: CarteraBet[], bankrollInit: number, criterion: Exclude<PresetKey, null>, riskFilter: RiskFilter = "all"): VersionCombo {
  if (criterion === "max_bets") return { draw: "v1", xg: "base", drift: "v1", clustering: "v2", pressure: "v1", tardeAsia: "v1", momentumXG: "v1", br: "fixed" }

  const drawOpts: DrawVersion[] = ["v1", "v15", "v2r", "v2", "v3"]
  const xgOpts: XGCarteraVersion[] = ["base", "v2", "v3"]
  const driftOpts: DriftCarteraVersion[] = ["v1", "v2", "v3", "v4", "v5", "v6"]
  const clusteringOpts: ClusteringCarteraVersion[] = ["v2", "v3", "v4", "off"]
  const pressureOpts: PressureCarteraVersion[] = ["v1", "off"]
  const tardeAsiaOpts: TardeAsiaVersion[] = ["v1", "off"]
  const momentumXGOpts: MomentumXGVersion[] = ["v1", "v2", "off"]
  const brOpts: BankrollMode[] = criterion === "min_dd" ? ["dd_protection", "fixed", "half_kelly", "anti_racha"] : ["fixed"]

  let best: VersionCombo = { draw: "v1", xg: "base", drift: "v1", clustering: "v2", pressure: "v1", tardeAsia: "off", momentumXG: "off", br: "fixed" }
  let bestScore = -Infinity

  for (const draw of drawOpts) {
    for (const xg of xgOpts) {
      for (const drift of driftOpts) {
        for (const clustering of clusteringOpts) {
          for (const pressure of pressureOpts) {
            for (const tardeAsia of tardeAsiaOpts) {
              for (const momentumXG of momentumXGOpts) {
                for (const br of brOpts) {
                  const combo = { draw, xg, drift, clustering, pressure, tardeAsia, momentumXG, br }
                  const result = evaluateCombo(bets, combo, bankrollInit, riskFilter)
                  if (!result || result.total < 3) continue

                  let score: number
                  switch (criterion) {
                    case "max_roi": score = result.flatRoi; break
                    case "max_pl": score = result.flatPl; break
                    case "max_wr": score = result.winPct + result.total * 0.01; break
                    case "min_dd": {
                      const ddPenalty = result.managedMaxDd.maxDd
                      score = result.managedPl - ddPenalty * 2 + result.winPct * 0.5
                      break
                    }
                    default: score = result.flatPl; break
                  }
                  if (score > bestScore) { bestScore = score; best = combo }
                }
              }
            }
          }
        }
      }
    }
  }
  return best
}

// ── Realistic adjustments ────────────────────────────────────────────

export interface RealisticAdjustments {
  dedup: boolean          // Deduplicar apuestas del mismo mercado en mismo partido
  maxOdds: number | null  // Excluir apuestas con odds > X (null = sin límite)
  minOdds: number | null  // Excluir apuestas con odds < X (null = sin límite)
  driftMinMinute: number | null  // Min minuto para drift (null = sin filtro)
  slippagePct: number     // % de slippage sobre odds (0 = sin slippage)
  conflictFilter: boolean // Eliminar MomXG cuando xG Underperf activa en mismo partido (par tóxico)
}

export const DEFAULT_ADJUSTMENTS: RealisticAdjustments = {
  dedup: false,
  maxOdds: null,
  minOdds: null,
  driftMinMinute: null,
  slippagePct: 0,
  conflictFilter: false,
}

export const REALISTIC_ADJUSTMENTS: RealisticAdjustments = {
  dedup: true,
  maxOdds: 6.0,
  minOdds: 1.15,
  driftMinMinute: 15,
  slippagePct: 2,
  conflictFilter: true,
}

/** Get the market key for deduplication (same match + same bet type = same bet) */
function betMarketKey(b: CarteraBet): string {
  if (b.strategy === "back_draw_00") return `${b.match_id}:draw`
  if (b.strategy === "odds_drift") return `${b.match_id}:back:${b.team ?? "unknown"}`
  // xG, Clustering, Pressure all bet Over — same over_line = same market
  return `${b.match_id}:over:${b.over_line ?? "unknown"}`
}

/**
 * Apply realistic adjustments to a sorted list of bets.
 * Returns a new array with adjustments applied (P/L recalculated where needed).
 */
export function applyRealisticAdjustments(
  bets: CarteraBet[],
  adj: RealisticAdjustments,
): CarteraBet[] {
  let result = [...bets]

  // 1. Filter drift by min minute
  if (adj.driftMinMinute != null) {
    result = result.filter(b =>
      b.strategy !== "odds_drift" || (b.minuto != null && b.minuto >= adj.driftMinMinute!)
    )
  }

  // 2. Filter by max odds
  if (adj.maxOdds != null) {
    result = result.filter(b => {
      const odds = getBetOdds(b)
      return odds <= adj.maxOdds!
    })
  }

  // 3. Filter by min value odds
  if (adj.minOdds != null) {
    result = result.filter(b => {
      const odds = getBetOdds(b)
      return odds >= adj.minOdds!
    })
  }

  // 4. Deduplication (keep first chronologically per market)
  if (adj.dedup) {
    const seen = new Set<string>()
    result = result.filter(b => {
      const key = betMarketKey(b)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
  }

  // 5. Conflict filter: remove MomXG bets from matches that also have xG Underperf
  //    (analysis showed MomXG + xGUnderperf pair: 4 matches, 0% WR, -100% ROI)
  if (adj.conflictFilter) {
    const matchesWithXGUnderperf = new Set(
      result
        .filter(b => b.strategy === "xg_underperformance")
        .map(b => b.match_id)
    )
    result = result.filter(b => {
      if (b.strategy === "momentum_xg_v1" || b.strategy === "momentum_xg_v2") {
        return !matchesWithXGUnderperf.has(b.match_id)
      }
      return true
    })
  }

  // 6. Apply slippage (reduce odds → recalculate P/L)
  if (adj.slippagePct > 0) {
    const factor = 1 - adj.slippagePct / 100
    result = result.map(b => {
      const originalOdds = getBetOdds(b)
      const adjustedOdds = round2(originalOdds * factor)
      // Recalculate P/L: if won → (adjustedOdds - 1) * 10 * 0.95, if lost → -10
      if (b.won) {
        const newPl = round2((adjustedOdds - 1) * 10 * 0.95)
        return { ...b, pl: newPl }
      }
      return b // losses stay at -10
    })
  }

  return result
}

// ── Combo → signal detection versions mapping ──────────────────────────

export function comboToSignalVersions(combo: VersionCombo): Record<string, string> {
  return {
    draw: combo.draw,
    xg: combo.xg,
    drift: combo.drift,
    clustering: combo.clustering,
    pressure: combo.pressure,
    momentum: combo.momentumXG ?? "v1",
  }
}

// ── Risk-based filtering and analysis ──────────────────────────────────

export type RiskFilter = "all" | "no_risk" | "with_risk" | "medium" | "high"

export function filterByRisk(bets: CarteraBet[], riskFilter: RiskFilter): CarteraBet[] {
  if (riskFilter === "all") return bets

  return bets.filter(b => {
    const risk = b.risk_level || "none"

    switch (riskFilter) {
      case "no_risk":
        return risk === "none"
      case "with_risk":
        return risk === "medium" || risk === "high"
      case "medium":
        return risk === "medium"
      case "high":
        return risk === "high"
      default:
        return true
    }
  })
}

export interface RiskBreakdown {
  no_risk: {
    count: number
    wins: number
    winPct: number
    pl: number
    roi: number
  }
  medium_risk: {
    count: number
    wins: number
    winPct: number
    pl: number
    roi: number
  }
  high_risk: {
    count: number
    wins: number
    winPct: number
    pl: number
    roi: number
  }
  combined_risk: {
    count: number
    wins: number
    winPct: number
    pl: number
    roi: number
  }
}

export function analyzeRiskBreakdown(bets: CarteraBet[]): RiskBreakdown {
  const STAKE = 10

  const noRiskBets = bets.filter(b => (b.risk_level || "none") === "none")
  const mediumRiskBets = bets.filter(b => b.risk_level === "medium")
  const highRiskBets = bets.filter(b => b.risk_level === "high")
  const combinedRiskBets = [...mediumRiskBets, ...highRiskBets]

  const calcStats = (subset: CarteraBet[]) => {
    const count = subset.length
    const wins = subset.filter(b => b.won).length
    const pl = round2(subset.reduce((sum, b) => sum + b.pl, 0))
    return {
      count,
      wins,
      winPct: count > 0 ? round2((wins / count) * 100) : 0,
      pl,
      roi: count > 0 ? round2((pl / (count * STAKE)) * 100) : 0
    }
  }

  return {
    no_risk: calcStats(noRiskBets),
    medium_risk: calcStats(mediumRiskBets),
    high_risk: calcStats(highRiskBets),
    combined_risk: calcStats(combinedRiskBets)
  }
}
