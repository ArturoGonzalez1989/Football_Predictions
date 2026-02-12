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
  goles: string
  xg: string
  posesion: string
  corners: string
  tiros: string
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
}
