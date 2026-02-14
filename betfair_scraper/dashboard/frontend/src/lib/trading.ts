/**
 * Trading Intelligence Utilities
 *
 * Pure functions to transform raw capture/odds data into actionable signals.
 * All stats in Capture are cumulative strings — we parse and compute deltas.
 */

import type { Capture, OddsTimeline } from "./api"

// ─── Helpers ─────────────────────────────────────────────────────────────────

function num(v: string | undefined | null): number | null {
  if (!v || v === "—" || v === "?" || v === "N/A" || v.trim() === "") return null
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : null
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v))
}

// ─── Pressure Index ──────────────────────────────────────────────────────────

export interface PressureSnapshot {
  minute: number
  home: number
  away: number
}

/**
 * Compute PressureIndex over a sliding window.
 *
 * PressureIndex = Δ dangerous_attacks×1 + Δ shots_on_target×3
 *               + Δ corners×2         + Δ shots_off_target×1
 *
 * Because CSV stores cumulative totals, we compute the *delta* between
 * the edges of the window.
 */
function capturePressureFields(c: Capture) {
  return {
    dangerous_attacks_home: num(c.dangerous_attacks_local) ?? 0,
    dangerous_attacks_away: num(c.dangerous_attacks_visitante) ?? 0,
    shots_on_target_home: num(c.tiros_puerta_local) ?? 0,
    shots_on_target_away: num(c.tiros_puerta_visitante) ?? 0,
    corners_home: num(c.corners_local) ?? 0,
    corners_away: num(c.corners_visitante) ?? 0,
    shots_off_target_home: num(c.shots_off_target_local) ?? 0,
    shots_off_target_away: num(c.shots_off_target_visitante) ?? 0,
  }
}

function pressureFromFields(
  current: ReturnType<typeof capturePressureFields>,
  baseline: ReturnType<typeof capturePressureFields>,
) {
  const dHome =
    (current.dangerous_attacks_home - baseline.dangerous_attacks_home) * 1 +
    (current.shots_on_target_home - baseline.shots_on_target_home) * 3 +
    (current.corners_home - baseline.corners_home) * 2 +
    (current.shots_off_target_home - baseline.shots_off_target_home) * 1

  const dAway =
    (current.dangerous_attacks_away - baseline.dangerous_attacks_away) * 1 +
    (current.shots_on_target_away - baseline.shots_on_target_away) * 3 +
    (current.corners_away - baseline.corners_away) * 2 +
    (current.shots_off_target_away - baseline.shots_off_target_away) * 1

  return { home: Math.max(0, dHome), away: Math.max(0, dAway) }
}

/**
 * Current PressureIndex for the last `windowMinutes` (default 10).
 * Returns { home, away, homeScore, awayScore, minute }.
 */
export function computeCurrentPressure(
  captures: Capture[],
  windowMinutes = 10,
) {
  if (captures.length < 2) return null

  const sorted = [...captures].sort(
    (a, b) => (num(a.minuto) ?? 0) - (num(b.minuto) ?? 0),
  )

  const latest = sorted[sorted.length - 1]
  const latestMin = num(latest.minuto) ?? 0
  const windowStart = latestMin - windowMinutes

  // Find the capture closest to windowStart
  let baselineIdx = 0
  for (let i = sorted.length - 1; i >= 0; i--) {
    const m = num(sorted[i].minuto) ?? 0
    if (m <= windowStart) {
      baselineIdx = i
      break
    }
  }

  const baseline = capturePressureFields(sorted[baselineIdx])
  const current = capturePressureFields(latest)
  const pressure = pressureFromFields(current, baseline)

  return {
    ...pressure,
    homeScore: num(latest.goles_local) ?? 0,
    awayScore: num(latest.goles_visitante) ?? 0,
    minute: latestMin,
  }
}

/**
 * Full PressureIndex timeline (for the PriceVsReality chart).
 * Computes a rolling 10-minute PressureIndex at each capture point.
 */
export function computePressureTimeline(
  captures: Capture[],
  windowMinutes = 10,
): PressureSnapshot[] {
  if (captures.length < 2) return []

  const sorted = [...captures].sort(
    (a, b) => (num(a.minuto) ?? 0) - (num(b.minuto) ?? 0),
  )

  const timeline: PressureSnapshot[] = []
  const fields = sorted.map(capturePressureFields)

  for (let i = 0; i < sorted.length; i++) {
    const minute = num(sorted[i].minuto) ?? 0
    const windowStart = minute - windowMinutes

    // Find baseline
    let bIdx = 0
    for (let j = i; j >= 0; j--) {
      const m = num(sorted[j].minuto) ?? 0
      if (m <= windowStart) {
        bIdx = j
        break
      }
    }

    const pressure = pressureFromFields(fields[i], fields[bIdx])
    timeline.push({ minute, ...pressure })
  }

  return timeline
}

// ─── Price vs Reality: Divergence Zones ──────────────────────────────────────

export interface DivergencePoint {
  minute: number
  pressureHome: number
  oddsHome: number | null
  isDivergence: boolean
}

/**
 * Build the merged timeline for the PriceVsReality chart.
 * A divergence zone exists when:
 *   - home pressure is rising (above average)
 *   - AND home odds are also rising (market losing faith)
 * i.e. the "antinatural" scenario.
 */
export function buildDivergenceTimeline(
  pressureTimeline: PressureSnapshot[],
  oddsTimeline: OddsTimeline[],
): DivergencePoint[] {
  if (!pressureTimeline.length || !oddsTimeline.length) return []

  // Build a map minute → odds
  const oddsMap = new Map<number, number>()
  for (const o of oddsTimeline) {
    if (o.minute != null && o.back_home != null) {
      oddsMap.set(o.minute, o.back_home)
    }
  }

  // Interpolate odds for pressure minutes
  const allOddsMinutes = [...oddsMap.keys()].sort((a, b) => a - b)

  function interpolateOdds(minute: number): number | null {
    if (oddsMap.has(minute)) return oddsMap.get(minute)!
    if (allOddsMinutes.length === 0) return null
    // Nearest
    let closest = allOddsMinutes[0]
    for (const m of allOddsMinutes) {
      if (Math.abs(m - minute) < Math.abs(closest - minute)) closest = m
    }
    if (Math.abs(closest - minute) <= 3) return oddsMap.get(closest)!
    return null
  }

  // Avg pressure for threshold
  const avgPressure =
    pressureTimeline.reduce((s, p) => s + p.home, 0) /
    (pressureTimeline.length || 1)

  // Compute opening odds for drift detection
  const openingOdds = oddsTimeline.find((o) => o.back_home != null)?.back_home

  const result: DivergencePoint[] = []
  for (const p of pressureTimeline) {
    const odds = interpolateOdds(p.minute)
    // Divergence: pressure above avg AND odds drifting up from opening
    const pressureHigh = p.home > avgPressure && p.home > 3
    const oddsDrifting =
      odds != null && openingOdds != null && odds > openingOdds * 1.03
    result.push({
      minute: p.minute,
      pressureHome: p.home,
      oddsHome: odds,
      isDivergence: pressureHigh && oddsDrifting,
    })
  }

  return result
}

// ─── Momentum Swings ─────────────────────────────────────────────────────────

export interface MomentumSwingEvent {
  minute: number
  team: "home" | "away"
  metric: string
  changePct: number
  description: string
  sparkline: number[] // last 5 data points for mini chart
}

/**
 * Detect momentum swings by computing rate-of-change of key metrics.
 * We look for moments where a team's production rate increases
 * significantly vs the previous window.
 */
export function detectMomentumSwings(captures: Capture[]): MomentumSwingEvent[] {
  if (captures.length < 6) return []

  const sorted = [...captures].sort(
    (a, b) => (num(a.minuto) ?? 0) - (num(b.minuto) ?? 0),
  )

  // Extract metric time series
  type MetricDef = {
    key: string
    label: string
    homeKey: keyof Capture
    awayKey: keyof Capture
  }

  const metrics: MetricDef[] = [
    { key: "dangerous_attacks", label: "Dangerous Attacks", homeKey: "dangerous_attacks_local", awayKey: "dangerous_attacks_visitante" },
    { key: "shots_on_target", label: "Shots on Target", homeKey: "tiros_puerta_local", awayKey: "tiros_puerta_visitante" },
    { key: "corners", label: "Corners", homeKey: "corners_local", awayKey: "corners_visitante" },
    { key: "attacks", label: "Attacks", homeKey: "attacks_local", awayKey: "attacks_visitante" },
  ]

  const events: MomentumSwingEvent[] = []
  const windowSize = 5 // Compare 5-capture windows

  for (const metric of metrics) {
    for (const side of ["home", "away"] as const) {
      const key = side === "home" ? metric.homeKey : metric.awayKey
      const values = sorted.map((c) => num(c[key]) ?? 0)

      // Compute deltas (per-capture increments)
      const deltas: number[] = []
      for (let i = 1; i < values.length; i++) {
        deltas.push(Math.max(0, values[i] - values[i - 1]))
      }

      // Sliding window comparison
      for (let i = windowSize * 2; i < deltas.length; i++) {
        const prevWindow = deltas.slice(i - windowSize * 2, i - windowSize)
        const currWindow = deltas.slice(i - windowSize, i)

        const prevRate = prevWindow.reduce((a, b) => a + b, 0)
        const currRate = currWindow.reduce((a, b) => a + b, 0)

        // Significant swing: current window rate >= 2x previous AND meaningful absolute value
        if (prevRate > 0 && currRate >= prevRate * 2 && currRate >= 3) {
          const changePct = Math.round(((currRate - prevRate) / prevRate) * 100)
          const minute = num(sorted[i].minuto) ?? 0

          // Build sparkline from the last 5 delta values
          const sparkline = deltas.slice(Math.max(0, i - 5), i)

          events.push({
            minute,
            team: side,
            metric: metric.label,
            changePct,
            description: `${metric.label} rate +${changePct}% vs prev ${windowSize} caps`,
            sparkline,
          })
        }
      }
    }
  }

  // Sort by minute descending (most recent first), deduplicate close events
  events.sort((a, b) => b.minute - a.minute)

  // Deduplicate: keep only one event per team per minute window (±2 min)
  const deduped: MomentumSwingEvent[] = []
  for (const e of events) {
    const isDupe = deduped.some(
      (d) => d.team === e.team && Math.abs(d.minute - e.minute) <= 2 && d.metric === e.metric,
    )
    if (!isDupe) deduped.push(e)
  }

  return deduped.slice(0, 15) // Top 15 events
}
