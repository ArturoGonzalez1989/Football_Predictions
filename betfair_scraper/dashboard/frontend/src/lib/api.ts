const BASE = "/api"

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export interface Match {
  name: string
  url: string
  match_id: string
  start_time: string | null
  status: "live" | "upcoming" | "finished"
  match_minute: number | null
  capture_count: number
  last_capture: string | null
  last_capture_ago_seconds: number | null
  csv_exists: boolean
}

export interface MatchesGrouped {
  live: Match[]
  upcoming: Match[]
  finished: Match[]
}

export interface Capture {
  timestamp: string
  minuto: string
  goles_local: string
  goles_visitante: string
  xg_local: string
  xg_visitante: string
  posesion_local: string
  posesion_visitante: string
  corners_local: string
  corners_visitante: string
  tiros_local: string
  tiros_visitante: string
  tiros_puerta_local: string
  tiros_puerta_visitante: string
  shots_off_target_local: string
  shots_off_target_visitante: string
  blocked_shots_local: string
  blocked_shots_visitante: string
  saves_local: string
  saves_visitante: string
  dangerous_attacks_local: string
  dangerous_attacks_visitante: string
  fouls_conceded_local: string
  fouls_conceded_visitante: string
  goal_kicks_local: string
  goal_kicks_visitante: string
  throw_ins_local: string
  throw_ins_visitante: string
  tarjetas_amarillas_local: string
  tarjetas_amarillas_visitante: string
  tarjetas_rojas_local: string
  tarjetas_rojas_visitante: string
  total_passes_local: string
  total_passes_visitante: string
  big_chances_local: string
  big_chances_visitante: string
  attacks_local: string
  attacks_visitante: string
  tackles_local: string
  tackles_visitante: string
  momentum_local: string
  momentum_visitante: string
  opta_points_local: string
  opta_points_visitante: string
  touches_box_local: string
  touches_box_visitante: string
  shooting_accuracy_local: string
  shooting_accuracy_visitante: string
  free_kicks_local: string
  free_kicks_visitante: string
  offsides_local: string
  offsides_visitante: string
  substitutions_local: string
  substitutions_visitante: string
  injuries_local: string
  injuries_visitante: string
  time_in_dangerous_attack_pct_local: string
  time_in_dangerous_attack_pct_visitante: string
}

export interface MatchDetail {
  match_id: string
  rows: number
  captures: Capture[]
  quality: number
  gaps: number[]
  total_gaps: number
}

export interface MomentumData {
  match_id: string
  data_points: number
  minutes: number[]
  momentum: { home: (number | null)[]; away: (number | null)[] }
  xg: { home: (number | null)[]; away: (number | null)[] }
  possession: { home: (number | null)[]; away: (number | null)[] }
}

export interface SystemStatus {
  running: boolean
  pid: number | null
  uptime_seconds: number | null
  memory_mb: number | null
  chrome_processes: number
  last_log: string | null
  last_log_lines: string[]
  auto_refresh_enabled?: boolean
  refresh_interval_minutes?: number
  is_refreshing?: boolean
}

async function post<T>(path: string, body?: any): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export interface OddsTimeline {
  minute: number | null
  // Match Odds
  back_home: number | null
  lay_home: number | null
  back_draw: number | null
  lay_draw: number | null
  back_away: number | null
  lay_away: number | null
  // Over/Under 0.5
  back_over05: number | null
  lay_over05: number | null
  back_under05: number | null
  lay_under05: number | null
  // Over/Under 1.5
  back_over15: number | null
  lay_over15: number | null
  back_under15: number | null
  lay_under15: number | null
  // Over/Under 2.5
  back_over25: number | null
  lay_over25: number | null
  back_under25: number | null
  lay_under25: number | null
  // Over/Under 3.5
  back_over35: number | null
  lay_over35: number | null
  back_under35: number | null
  lay_under35: number | null
  // Over/Under 4.5
  back_over45: number | null
  lay_over45: number | null
  back_under45: number | null
  lay_under45: number | null
  volumen_matched: number | null
}

export interface MatchFull {
  match_id: string
  rows: number
  final_stats: Record<string, number | string | null>
  opening_odds: Record<string, number | null>
  closing_odds: Record<string, number | null>
  odds_timeline: OddsTimeline[]
  volume_matched: number | null
  first_capture: string
  last_capture: string
}

export interface AllCaptures {
  match_id: string
  rows: number
  captures: Capture[]
}

export interface QualityOverview {
  avg_quality: number
  total_matches: number
  quality_ranges: { range: string; count: number }[]
  bins: { label: string; count: number; matches: string[] }[]
}

export interface QualityDistribution {
  bins: { label: string; count: number; matches: string[] }[]
}

export interface StatsCoverage {
  fields: { name: string; coverage_pct: number }[]
}

export interface GapAnalysis {
  avg_gaps: number
  max_gaps: number
  distribution: { gap_count: number; match_count: number }[]
}

export interface LowQualityMatch {
  match_id: string
  name: string
  quality: number
  total_captures: number
  gap_count: number
}

export interface MomentumPatterns {
  avg_swing: number
  comeback_frequency: number
  top_swings: { match_id: string; name: string; swing: number }[]
}

export interface XgAccuracy {
  correlation: number
  avg_accuracy: number
  scatter_data: { xg: number; actual: number; match_id: string; team: string }[]
}

export interface OddsMovements {
  avg_drift: number
  drift_by_minute: { minute: number; avg_drift: number }[]
  top_movements: { match_id: string; name: string; movement: number; drift_pct: number }[]
}

export interface OverUnderAnalysis {
  hit_rates: { line: string; hit_rate: number }[]
  minute_probabilities: { minute: number; probability: number }[]
}

export interface StatCorrelations {
  matrix: { stat1: string; stat2: string; correlation: number }[]
  top_correlations: { pair: string; value: number }[]
}

export interface StrategyBet {
  match: string
  match_id: string
  minuto: number | null
  back_draw: number | null
  xg_total: number | null
  xg_max: number | null
  sot_total: number | null
  poss_diff: number | null
  shots_total: number | null
  bfed_prematch: number | null
  ft_score: string
  won: boolean
  pl: number
  passes_v2: boolean
  passes_v15: boolean
  passes_v2r: boolean
}

export interface StrategySummaryBlock {
  bets: number
  wins: number
  win_pct: number
  pl: number
  roi: number
}

export interface StrategyBackDraw00 {
  total_matches: number
  with_trigger: number
  summary: {
    base: StrategySummaryBlock
    v15: StrategySummaryBlock
    v2: StrategySummaryBlock
    v2r: StrategySummaryBlock
  }
  bets: StrategyBet[]
}

export interface StrategyXGBet {
  match: string
  match_id: string
  minuto: number | null
  score_at_trigger: string
  team: "home" | "away"
  team_xg: number | null
  team_goals: number
  xg_excess: number | null
  back_over_odds: number | null
  over_line: string
  sot_team: number | null
  poss_team: number | null
  shots_team: number | null
  ft_score: string
  won: boolean
  pl: number
  passes_v2: boolean
}

export interface StrategyXGUnderperformance {
  total_matches: number
  with_trigger: number
  summary: {
    base: StrategySummaryBlock
    v2: StrategySummaryBlock
  }
  bets: StrategyXGBet[]
}

export interface StrategyOddsDriftBet {
  match: string
  match_id: string
  minuto: number | null
  score_at_trigger: string
  team: "home" | "away"
  goal_diff: number
  odds_before: number
  back_odds: number
  drift_pct: number
  sot_team: number | null
  poss_team: number | null
  shots_team: number | null
  ft_score: string
  won: boolean
  pl: number
  passes_v2: boolean
  passes_v3: boolean
  passes_v4: boolean
}

export interface StrategyOddsDrift {
  total_matches: number
  with_trigger: number
  summary: {
    v1: StrategySummaryBlock
    v2: StrategySummaryBlock
    v3: StrategySummaryBlock
    v4: StrategySummaryBlock
  }
  bets: StrategyOddsDriftBet[]
}

export interface StrategyGoalClusteringBet {
  match: string
  match_id: string
  minuto: number
  score: string
  sot_max: number
  over_odds: number | null
  ft_score: string
  won: boolean
  pl: number
  timestamp_utc: string
}

export interface StrategyGoalClustering {
  total_matches: number
  total_goal_events: number
  summary: {
    total_bets: number
    wins: number
    win_rate: number
    total_pl: number
    roi: number
  }
  bets: StrategyGoalClusteringBet[]
}

export interface StrategyPressureCookerBet {
  match: string
  match_id: string
  minuto: number
  score: string
  back_over_odds: number | null
  over_line: string
  ft_score: string
  won: boolean
  pl: number
  sot_delta: number
  corners_delta: number
  shots_delta: number
  timestamp_utc: string
}

export interface StrategyPressureCooker {
  total_matches: number
  draws_65_75: number
  summary: {
    total_bets: number
    wins: number
    win_rate: number
    total_pl: number
    roi: number
  }
  bets: StrategyPressureCookerBet[]
}

export interface StrategyTardeAsiaBet {
  match: string
  match_id: string
  minuto: number
  score: string
  back_over_odds: number | null
  over_line: string
  ft_score: string
  won: boolean
  pl: number
  liga: string
  hora_local: string
  timestamp_utc: string
}

export interface StrategyTardeAsia {
  total_matches: number
  tarde_asia_matches: number
  summary: {
    total_bets: number
    wins: number
    win_rate: number
    total_pl: number
    roi: number
  }
  bets: StrategyTardeAsiaBet[]
}

export interface StrategyMomentumXGBet {
  match: string
  match_id: string
  minuto: number
  score_at_trigger: string
  dominant_team: string
  sot_ratio: number
  xg_underperf: number
  back_odds: number
  ft_score: string
  won: boolean
  pl: number
  timestamp_utc: string
}

export interface StrategyMomentumXG {
  total_matches: number
  momentum_triggers: number
  summary: {
    total_bets: number
    wins: number
    win_rate: number
    total_pl: number
    roi: number
  }
  bets: StrategyMomentumXGBet[]
}

export interface CarteraBet {
  match: string
  match_id: string
  minuto: number | null
  ft_score: string
  won: boolean
  pl: number
  strategy: string
  strategy_label: string
  timestamp_utc: string
  back_draw?: number | null
  back_over_odds?: number | null
  over_line?: string
  team?: string
  xg_excess?: number | null
  passes_v2?: boolean
  passes_v15?: boolean
  passes_v2r?: boolean
  passes_v3?: boolean
  // odds drift fields
  back_odds?: number | null
  drift_pct?: number | null
  goal_diff?: number | null
  passes_v4?: boolean
  passes_v5?: boolean
  passes_v6?: boolean
  // synthetic attribute fields
  synth_xg_dominance?: number | null
  synth_pressure_index_v?: number | null
  synth_momentum_gap?: number | null
  synth_xg_remaining?: number | null
  // risk assessment fields
  risk_level?: "none" | "medium" | "high"
  risk_reason?: string
  time_remaining?: number
  deficit?: number
  // geographic fields
  País?: string
  Liga?: string
}

export interface Cartera {
  total_bets: number
  flat: { pl: number; roi: number; cumulative: number[] }
  managed: {
    initial_bankroll: number
    bankroll_pct: number
    final_bankroll: number
    pl: number
    roi: number
    cumulative: number[]
  }
  by_strategy: {
    back_draw_00: StrategySummaryBlock
    xg_underperformance: StrategySummaryBlock
    odds_drift: StrategySummaryBlock
  }
  bets: CarteraBet[]
}

export interface BettingSignal {
  match_id: string
  match_name: string
  match_url: string
  strategy: string
  strategy_name: string
  minute: number
  score: string
  recommendation: string
  back_odds: number | null
  confidence: "high" | "medium" | "low"
  entry_conditions: Record<string, any>
  thresholds: Record<string, string>
  // Enhanced fields (when available)
  min_odds?: number
  expected_value?: number
  odds_favorable?: boolean
  win_rate_historical?: number
  roi_historical?: number
  sample_size?: number
  description?: string
  // Risk assessment
  risk_info?: {
    has_risk: boolean
    risk_level: "none" | "medium" | "high"
    risk_reason: string
    time_remaining: number
    deficit: number
  }
  // Signal duration / maturity
  signal_age_minutes?: number
  min_duration_caps?: number
  is_mature?: boolean
}

export interface AvailableStrategy {
  id: string
  name: string
  sample_size: number
}

export interface BettingSignals {
  total_signals: number
  live_matches: number
  signals: BettingSignal[]
  available_strategies?: AvailableStrategy[]
}

export interface WatchlistCondition {
  label: string
  met: boolean
  current?: string
  target?: string
}

export interface WatchlistItem {
  match_id: string
  match_name: string
  match_url: string
  minute: number
  score: string
  strategy: string
  version: string
  conditions: WatchlistCondition[]
  met: number
  total: number
  proximity: number
}

export interface PlaceBetRequest {
  match_id: string
  match_name: string
  match_url: string
  strategy: string
  strategy_name: string
  minute: number
  score: string
  recommendation: string
  back_odds: number | null
  min_odds?: number
  expected_value?: number
  confidence: string
  win_rate_historical?: number
  roi_historical?: number
  sample_size?: number
  // User input fields
  bet_type: "paper" | "real"
  stake: number
  notes?: string
}

export interface PlacedBet {
  id: number
  timestamp_utc: string
  match_id: string
  match_name: string
  match_url: string
  strategy: string
  strategy_name: string
  minute: number
  score: string
  recommendation: string
  back_odds: number | null
  min_odds?: number
  expected_value?: number
  confidence: string
  win_rate_historical?: number
  roi_historical?: number
  sample_size?: number
  bet_type: "paper" | "real"
  stake: number
  notes?: string
  status: "pending" | "won" | "lost"
  result?: string
  pl?: number
  // Live enrichment (pending bets only)
  live_score?: string
  live_minute?: number | null
  live_status?: string
  would_win_now?: boolean
  potential_pl?: number
}

export interface PlacedBetsResponse {
  total: number
  pending: number
  won: number
  lost: number
  total_pl: number
  bets: PlacedBet[]
}

// ── Cartera configuration (single source of truth) ─────────────────────
export interface CarteraConfig {
  versions: {
    draw: string
    xg: string
    drift: string
    clustering: string
    pressure: string
    tarde_asia: string
    momentum_xg: string
  }
  bankroll_mode: string
  active_preset: string | null
  risk_filter: string
  min_duration: {
    draw: number
    xg: number
    drift: number
    clustering: number
    pressure: number
  }
  adjustments: {
    enabled: boolean
    dedup: boolean
    max_odds: number
    min_odds: number
    drift_min_minute: number
    slippage_pct: number
    conflict_filter: boolean
    cashout_minute: number | null
  }
}

async function put<T>(path: string, body: any): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export const api = {
  getMatches: () => get<MatchesGrouped>("/matches"),
  getMatchDetail: (id: string) => get<MatchDetail>(`/matches/${id}`),
  getMatchMomentum: (id: string) => get<MomentumData>(`/matches/${id}/momentum`),
  getMatchFull: (id: string) => get<MatchFull>(`/matches/${id}/full`),
  getAllCaptures: (id: string) => get<AllCaptures>(`/matches/${id}/all-captures`),
  getSystemStatus: () => get<SystemStatus>("/system/status"),
  deleteMatch: (id: string) => del<{ match_id: string; deleted_from_csv: boolean; deleted_data: boolean }>(`/matches/${id}`),
  refreshMatches: () => post<{ clean: { ok: boolean; output: string } | null; find: { ok: boolean; output: string } | null }>("/system/refresh-matches"),
  startScraper: () => post<{ ok: boolean; message: string; pid: number | null }>("/system/scraper/start"),
  stopScraper: () => post<{ ok: boolean; message: string }>("/system/scraper/stop"),
  restartBackend: () => post<{ ok: boolean; message: string; old_pid?: number; new_pid?: number }>("/system/backend/restart"),
  restartFrontend: () => post<{ ok: boolean; message: string; pid?: number }>("/system/frontend/restart"),

  // Quality endpoints
  getQualityOverview: () => get<QualityOverview>("/analytics/quality/overview"),
  getQualityDistribution: () => get<QualityDistribution>("/analytics/quality/distribution"),
  getStatsCoverage: () => get<StatsCoverage>("/analytics/quality/stats-coverage"),
  getGapAnalysis: () => get<GapAnalysis>("/analytics/quality/gaps"),
  getLowQualityMatches: (threshold: number) => get<{ threshold: number; matches: LowQualityMatch[] }>(`/analytics/quality/low-quality-matches?threshold=${threshold}`),

  // Insights endpoints
  getMomentumPatterns: () => get<MomentumPatterns>("/analytics/insights/momentum-patterns"),
  getXgAccuracy: () => get<XgAccuracy>("/analytics/insights/xg-accuracy"),
  getOddsMovements: () => get<OddsMovements>("/analytics/insights/odds-movements"),
  getOverUnderAnalysis: () => get<OverUnderAnalysis>("/analytics/insights/over-under"),
  getStatCorrelations: () => get<StatCorrelations>("/analytics/insights/correlations"),

  // Strategy tracking endpoints
  getStrategyBackDraw00: () => get<StrategyBackDraw00>("/analytics/strategies/back-draw-00"),
  getStrategyXGUnderperformance: () => get<StrategyXGUnderperformance>("/analytics/strategies/xg-underperformance"),
  getStrategyOddsDrift: () => get<StrategyOddsDrift>("/analytics/strategies/odds-drift"),
  getStrategyGoalClustering: () => get<StrategyGoalClustering>("/analytics/strategies/goal-clustering"),
  getStrategyPressureCooker: () => get<StrategyPressureCooker>("/analytics/strategies/pressure-cooker"),
  getStrategyTardeAsia: () => get<StrategyTardeAsia>("/analytics/strategies/tarde-asia"),
  getStrategyMomentumXGV1: () => get<StrategyMomentumXG>("/analytics/strategies/momentum-xg-v1"),
  getStrategyMomentumXGV2: () => get<StrategyMomentumXG>("/analytics/strategies/momentum-xg-v2"),
  getCartera: (cashoutMinute?: number) =>
    get<Cartera>(cashoutMinute !== undefined
      ? `/analytics/strategies/cartera?cashout_minute=${cashoutMinute}`
      : "/analytics/strategies/cartera"),

  // Betting signals
  getBettingSignals: (versions?: Record<string, string>, minDur?: Record<string, number>) => {
    const params: Record<string, string> = { ...(versions ?? {}) }
    if (minDur) {
      for (const [k, v] of Object.entries(minDur)) params[`${k}_min_dur`] = String(v)
    }
    const qs = new URLSearchParams(params).toString()
    return get<BettingSignals>(`/analytics/signals/betting-opportunities${qs ? `?${qs}` : ""}`)
  },
  getWatchlist: (versions?: Record<string, string>) => {
    if (!versions) return get<WatchlistItem[]>("/analytics/signals/watchlist")
    const params = new URLSearchParams(versions).toString()
    return get<WatchlistItem[]>(`/analytics/signals/watchlist?${params}`)
  },

  // Placed bets tracking
  placeBet: (bet: PlaceBetRequest) => post<PlacedBet>("/bets/place", bet),
  getPlacedBets: () => get<PlacedBetsResponse>("/bets/placed"),

  // Cartera configuration
  getConfig: () => get<CarteraConfig>("/config/cartera"),
  saveConfig: (config: CarteraConfig) => put<{ status: string }>("/config/cartera", config),
}
