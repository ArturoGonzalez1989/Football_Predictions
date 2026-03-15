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
  // Per-match log health (live only)
  log_status?: "ok" | "error" | "init" | "creating" | "unknown"
  log_minute?: number
  log_score?: string
  log_ts?: string
  log_msg?: string
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

export interface DriverProgress {
  game: string
  stage: "pending" | "chrome_init" | "loading_url" | "accepting_cookies" | "ready" | "capturing" | "live" | "error"
  pct: number
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
  drivers_progress?: Record<string, DriverProgress>
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
  if (!res.ok) {
    let detail = `API error: ${res.status}`
    try { const body = await res.json(); if (body.detail) detail = body.detail } catch { /* ignore */ }
    throw new Error(detail)
  }
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

export interface StatsCoverage {
  fields: { name: string; coverage_pct: number }[]
}

export interface GapAnalysis {
  avg_gaps: number
  max_gaps: number
  distribution: { gap_count: number; match_count: number }[]
}

export interface OddsCoverageMatch {
  match_id: string
  name: string
  start_time: string | null
  kickoff_time: string | null
  coverage_pct: number
  rows_with_odds: number
  total_rows: number
  outlier_count: number
  min_back_home: number | null
  max_back_home: number | null
  gap_count: number
  avg_gap_size: number
}

export interface OddsCoverage {
  avg_coverage: number
  total_matches: number
  no_odds: number
  partial_odds: number
  good_odds: number
  total_outlier_matches: number
  bins: { label: string; count: number }[]
  matches: OddsCoverageMatch[]
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
  entry_conditions?: Record<string, any>
  thresholds?: Record<string, string>
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
  status: "pending" | "won" | "lost" | "cashout"
  result?: string
  pl?: number
  // Live enrichment (pending bets only)
  live_score?: string
  live_minute?: number | null
  live_status?: string
  would_win_now?: boolean
  potential_pl?: number
  // Cashout recommendation / auto-cashout
  suggest_cashout?: boolean
  cashout_lay_current?: number
  cashout_threshold?: number
  cashout_pl?: number
}

export interface PlacedBetsResponse {
  total: number
  pending: number
  won: number
  lost: number
  cashout: number
  total_pl: number
  bets: PlacedBet[]
}

// ── Cartera configuration (single source of truth) ─────────────────────
export interface CarteraConfig {
  /** Strategy configs — all 32 strategies keyed by registry key */
  strategies?: Record<string, { enabled?: boolean; minuteMin?: number; minuteMax?: number; [key: string]: any }>
  bankroll_mode: string
  flat_stake?: number
  initial_bankroll?: number
  stake_pct?: number
  active_preset: string | null
  risk_filter: string
  min_duration: {
    back_draw_00: number
    xg_underperformance: number
    odds_drift: number
    goal_clustering: number
    pressure_cooker: number
    [key: string]: number
  }
  adjustments: {
    enabled: boolean
    dedup: boolean
    max_odds: number
    min_odds: number
    drift_min_minute: number
    slippage_pct: number
    conflict_filter: boolean
    allow_contrarias?: boolean
    stability?: number
    global_minute_min?: number | null
    global_minute_max?: number | null
    cashout_minute: number | null
    cashout_pct?: number
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
  bulkDeleteMatches: (ids: string[]) => post<{ results: { match_id: string; ok: boolean; error: string | null }[]; deleted: number; failed: number }>("/matches/bulk-delete", { match_ids: ids }),
  refreshMatches: () => post<{ clean: { ok: boolean; output: string } | null; find: { ok: boolean; output: string } | null }>("/system/refresh-matches"),
  startScraper: () => post<{ ok: boolean; message: string; pid: number | null }>("/system/scraper/start"),
  stopScraper: () => post<{ ok: boolean; message: string }>("/system/scraper/stop"),
  restartBackend: () => post<{ ok: boolean; message: string; old_pid?: number; new_pid?: number }>("/system/backend/restart"),
  restartFrontend: () => post<{ ok: boolean; message: string; pid?: number }>("/system/frontend/restart"),
  cleanupChrome: () => post<{ ok: boolean; killed: number; protected: number; message: string }>("/system/chrome/cleanup"),

  // Quality endpoints
  getQualityOverview: () => get<QualityOverview>("/analytics/quality/overview"),
  getStatsCoverage: () => get<StatsCoverage>("/analytics/quality/stats-coverage"),
  getGapAnalysis: () => get<GapAnalysis>("/analytics/quality/gaps"),
  getOddsCoverage: () => get<OddsCoverage>("/analytics/quality/odds-coverage"),
  clearAnalyticsCache: () => post<{ status: string; message: string }>("/analytics/cache/clear"),

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
  getManualBets: () => get<PlacedBetsResponse>("/bets/manual"),
  clearBets: () => del<{ status: string; message: string }>("/bets/clear"),
  resolveBet: (id: number, result: "won" | "lost") => post<{ ok: boolean; bet_id: number; result: string }>(`/bets/${id}/resolve?result=${result}`, {}),
  addToManualPaper: (betId: number) => post<{ ok: boolean; manual_bet_id: number }>(`/bets/${betId}/add-to-manual`, {}),

  // Cartera configuration
  getConfig: () => get<CarteraConfig>("/config/cartera"),
  saveConfig: (config: CarteraConfig) => put<{ status: string }>("/config/cartera", config),

  // Auto-open bet in browser
  openBet: (matchUrl: string) => post<{ ok: boolean }>("/analytics/open-bet", { match_url: matchUrl }),

}
