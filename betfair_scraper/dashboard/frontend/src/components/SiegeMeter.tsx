/**
 * SiegeMeter — Dual pressure gauge showing which team is "besieging" the other.
 *
 * When PressureIndex > threshold AND that team isn't winning:
 *   → GOL INMINENTE / VALUE alert
 */

import { useMemo } from "react"
import { Flame, AlertTriangle } from "lucide-react"
import type { Capture } from "../lib/api"
import { computeCurrentPressure } from "../lib/trading"

interface SiegeMeterProps {
  captures: Capture[]
  homeName: string
  awayName: string
}

const ALERT_THRESHOLD = 12

export function SiegeMeter({ captures, homeName, awayName }: SiegeMeterProps) {
  const pressure = useMemo(
    () => computeCurrentPressure(captures, 10),
    [captures],
  )

  if (!pressure) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-[#0c1222] p-4">
        <div className="text-xs text-zinc-600 text-center">
          Waiting for capture data...
        </div>
      </div>
    )
  }

  const maxVal = Math.max(pressure.home, pressure.away, ALERT_THRESHOLD, 1)

  const homeBarPct = (pressure.home / maxVal) * 100
  const awayBarPct = (pressure.away / maxVal) * 100

  // Alert logic: high pressure AND not winning
  const homeAlert =
    pressure.home >= ALERT_THRESHOLD &&
    pressure.homeScore <= pressure.awayScore
  const awayAlert =
    pressure.away >= ALERT_THRESHOLD &&
    pressure.awayScore <= pressure.homeScore

  const homeScoreStr = `${pressure.homeScore}`
  const awayScoreStr = `${pressure.awayScore}`

  return (
    <div className="rounded-xl border border-zinc-800 bg-[#0c1222] p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Flame className="w-4 h-4 text-orange-500" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Siege Meter
          </span>
        </div>
        <span className="text-[10px] text-zinc-600 font-mono">
          last 10 min &middot; min {pressure.minute}'
        </span>
      </div>

      {/* Score */}
      <div className="flex items-center justify-center gap-3">
        <span className="text-sm font-medium text-zinc-400 truncate max-w-[120px]">
          {homeName}
        </span>
        <span className="text-xl font-bold font-mono text-zinc-100 tabular-nums">
          {homeScoreStr} — {awayScoreStr}
        </span>
        <span className="text-sm font-medium text-zinc-400 truncate max-w-[120px]">
          {awayName}
        </span>
      </div>

      {/* Divergent Bars */}
      <div className="space-y-2">
        {/* Home bar → goes left to right */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px]">
            <span className={homeAlert ? "text-orange-400 font-bold" : "text-cyan-400 font-medium"}>
              {homeName}
            </span>
            <span className={`font-mono tabular-nums ${homeAlert ? "text-orange-400" : "text-zinc-400"}`}>
              {pressure.home.toFixed(1)}
            </span>
          </div>
          <div className="relative h-5 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800">
            {/* Threshold marker */}
            <div
              className="absolute top-0 bottom-0 w-px bg-zinc-600 z-10"
              style={{ left: `${(ALERT_THRESHOLD / maxVal) * 100}%` }}
            />
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${
                homeAlert
                  ? "bg-gradient-to-r from-orange-600 to-red-500 shadow-[0_0_12px_rgba(249,115,22,0.5)]"
                  : "bg-gradient-to-r from-cyan-900 to-cyan-500"
              }`}
              style={{ width: `${clamp(homeBarPct, 0, 100)}%` }}
            />
          </div>
        </div>

        {/* Away bar → goes left to right */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px]">
            <span className={awayAlert ? "text-orange-400 font-bold" : "text-fuchsia-400 font-medium"}>
              {awayName}
            </span>
            <span className={`font-mono tabular-nums ${awayAlert ? "text-orange-400" : "text-zinc-400"}`}>
              {pressure.away.toFixed(1)}
            </span>
          </div>
          <div className="relative h-5 bg-zinc-900 rounded-full overflow-hidden border border-zinc-800">
            <div
              className="absolute top-0 bottom-0 w-px bg-zinc-600 z-10"
              style={{ left: `${(ALERT_THRESHOLD / maxVal) * 100}%` }}
            />
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${
                awayAlert
                  ? "bg-gradient-to-r from-orange-600 to-red-500 shadow-[0_0_12px_rgba(249,115,22,0.5)]"
                  : "bg-gradient-to-r from-fuchsia-900 to-fuchsia-500"
              }`}
              style={{ width: `${clamp(awayBarPct, 0, 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Alert Banner */}
      {(homeAlert || awayAlert) && (
        <div className="flex items-center gap-2 rounded-lg bg-orange-500/10 border border-orange-500/30 px-3 py-2 animate-pulse">
          <AlertTriangle className="w-4 h-4 text-orange-400 shrink-0" />
          <div className="text-xs">
            <span className="text-orange-400 font-bold uppercase">
              GOL INMINENTE / VALUE
            </span>
            <span className="text-orange-300/80 ml-2">
              {homeAlert ? homeName : awayName} pressing hard but{" "}
              {homeAlert
                ? pressure.homeScore < pressure.awayScore
                  ? "losing"
                  : "drawing"
                : pressure.awayScore < pressure.homeScore
                  ? "losing"
                  : "drawing"}
            </span>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center justify-between text-[9px] text-zinc-600">
        <span>
          PI = ΔDangAtk×1 + ΔShotsOT×3 + ΔCorners×2 + ΔShotsOff×1
        </span>
        <span>Alert ≥ {ALERT_THRESHOLD}</span>
      </div>
    </div>
  )
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v))
}
