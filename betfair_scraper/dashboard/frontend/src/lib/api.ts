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
  back_home: number | null
  back_draw: number | null
  back_away: number | null
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

export const api = {
  getMatches: () => get<Match[]>("/matches"),
  getMatchDetail: (id: string) => get<MatchDetail>(`/matches/${id}`),
  getMatchMomentum: (id: string) => get<MomentumData>(`/matches/${id}/momentum`),
  getMatchFull: (id: string) => get<MatchFull>(`/matches/${id}/full`),
  getSystemStatus: () => get<SystemStatus>("/system/status"),
  deleteMatch: (id: string) => del<{ match_id: string; deleted_from_csv: boolean; deleted_data: boolean }>(`/matches/${id}`),
  refreshMatches: () => post<{ clean: { ok: boolean; output: string } | null; find: { ok: boolean; output: string } | null }>("/system/refresh-matches"),
  startScraper: () => post<{ ok: boolean; message: string; pid: number | null }>("/system/scraper/start"),
  stopScraper: () => post<{ ok: boolean; message: string }>("/system/scraper/stop"),
  restartBackend: () => post<{ ok: boolean; message: string; old_pid?: number; new_pid?: number }>("/system/backend/restart"),
  restartFrontend: () => post<{ ok: boolean; message: string; pid?: number }>("/system/frontend/restart"),
}
