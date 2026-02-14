/**
 * MomentumSwings — Real-time detection of momentum shifts with sparklines.
 *
 * Instead of showing static totals, this detects moments where a team's
 * attacking output rate spikes relative to the previous window.
 */

import { useMemo } from "react"
import { TrendingUp, Zap } from "lucide-react"
import type { Capture } from "../lib/api"
import { detectMomentumSwings, type MomentumSwingEvent } from "../lib/trading"

interface MomentumSwingsProps {
  captures: Capture[]
  homeName: string
  awayName: string
}

export function MomentumSwings({ captures, homeName, awayName }: MomentumSwingsProps) {
  const swings = useMemo(() => detectMomentumSwings(captures), [captures])

  if (swings.length === 0) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-[#0c1222] p-4">
        <div className="flex items-center gap-2 mb-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Momentum Swings
          </span>
        </div>
        <div className="text-xs text-zinc-600 text-center py-3">
          No significant momentum shifts detected yet
        </div>
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-zinc-800 bg-[#0c1222] p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Momentum Swings
          </span>
        </div>
        <span className="text-[10px] text-zinc-600 font-mono">
          {swings.length} event{swings.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Events list */}
      <div className="space-y-1.5 max-h-64 overflow-y-auto">
        {swings.map((swing, i) => (
          <SwingRow
            key={`${swing.minute}-${swing.team}-${swing.metric}-${i}`}
            swing={swing}
            teamName={swing.team === "home" ? homeName : awayName}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="text-[9px] text-zinc-600">
        Detects when a team's attack rate doubles vs the previous 5-capture window
      </div>
    </div>
  )
}

function SwingRow({ swing, teamName }: { swing: MomentumSwingEvent; teamName: string }) {
  const isHome = swing.team === "home"
  const accentColor = isHome ? "cyan" : "fuchsia"

  return (
    <div className="flex items-center gap-3 rounded-lg bg-zinc-900/60 border border-zinc-800/50 px-3 py-2 hover:bg-zinc-800/40 transition-colors">
      {/* Minute badge */}
      <div className="shrink-0 w-11 text-center">
        <span className="text-[10px] font-mono font-bold text-zinc-300">
          {swing.minute}'
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <TrendingUp className={`w-3 h-3 text-${accentColor}-400 shrink-0`} style={{ color: isHome ? "#22d3ee" : "#e879f9" }} />
          <span className="text-[11px] font-medium truncate" style={{ color: isHome ? "#22d3ee" : "#e879f9" }}>
            {teamName}
          </span>
          <span className="text-[10px] text-zinc-500 truncate">
            {swing.metric}
          </span>
        </div>
        <div className="text-[10px] text-zinc-500 mt-0.5">
          Rate{" "}
          <span className="text-emerald-400 font-bold">
            +{swing.changePct}%
          </span>{" "}
          vs previous window
        </div>
      </div>

      {/* Sparkline */}
      <div className="shrink-0 w-16 h-6">
        <Sparkline data={swing.sparkline} color={isHome ? "#22d3ee" : "#e879f9"} />
      </div>
    </div>
  )
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null

  const max = Math.max(...data, 1)
  const min = Math.min(...data, 0)
  const range = max - min || 1

  const w = 64
  const h = 24
  const padY = 2

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w
    const y = h - padY - ((v - min) / range) * (h - padY * 2)
    return `${x},${y}`
  })

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
      <polyline
        points={points.join(" ")}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Dot on last point */}
      {data.length > 0 && (() => {
        const lastX = w
        const lastY = h - padY - ((data[data.length - 1] - min) / range) * (h - padY * 2)
        return <circle cx={lastX} cy={lastY} r={2} fill={color} />
      })()}
    </svg>
  )
}
