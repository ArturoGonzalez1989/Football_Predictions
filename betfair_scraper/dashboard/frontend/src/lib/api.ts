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

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "POST" })
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
}
