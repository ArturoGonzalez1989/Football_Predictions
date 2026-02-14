/**
 * PriceVsReality — Divergence chart showing Pressure Index vs Odds.
 *
 * Green line (left Y): Rolling PressureIndex (performance reality)
 * Yellow line (right Y, inverted): Home back odds (market price)
 * Shaded magenta zones: Divergence = "ENTRY ZONE"
 */

import { useMemo } from "react"
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import { Crosshair } from "lucide-react"
import type { Capture, OddsTimeline } from "../lib/api"
import {
  computePressureTimeline,
  buildDivergenceTimeline,
  type DivergencePoint,
} from "../lib/trading"

interface PriceVsRealityProps {
  captures: Capture[]
  oddsTimeline: OddsTimeline[]
  homeName: string
}

export function PriceVsReality({ captures, oddsTimeline, homeName }: PriceVsRealityProps) {
  const data = useMemo(() => {
    const pressure = computePressureTimeline(captures, 10)
    return buildDivergenceTimeline(pressure, oddsTimeline)
  }, [captures, oddsTimeline])

  const entryZones = useMemo(() => {
    // Find contiguous divergence zones
    const zones: { start: number; end: number }[] = []
    let zoneStart: number | null = null
    for (const p of data) {
      if (p.isDivergence && zoneStart === null) {
        zoneStart = p.minute
      } else if (!p.isDivergence && zoneStart !== null) {
        zones.push({ start: zoneStart, end: p.minute })
        zoneStart = null
      }
    }
    if (zoneStart !== null && data.length > 0) {
      zones.push({ start: zoneStart, end: data[data.length - 1].minute })
    }
    return zones
  }, [data])

  if (data.length < 5) {
    return (
      <div className="rounded-xl border border-zinc-800 bg-[#0c1222] p-4">
        <div className="text-xs text-zinc-600 text-center">
          Not enough data for divergence analysis
        </div>
      </div>
    )
  }

  // Calculate domains
  const pressureValues = data.map((d) => d.pressureHome)
  const oddsValues = data.filter((d) => d.oddsHome != null).map((d) => d.oddsHome!)
  const maxPressure = Math.max(...pressureValues, 1)
  const minOdds = oddsValues.length ? Math.min(...oddsValues) : 1
  const maxOdds = oddsValues.length ? Math.max(...oddsValues) : 5

  // Prepare chart data with divergence shading
  const chartData = data.map((d) => ({
    minute: d.minute,
    pressure: d.pressureHome,
    odds: d.oddsHome,
    // For shading divergence zones
    entryZone: d.isDivergence ? maxPressure : null,
  }))

  return (
    <div className="rounded-xl border border-zinc-800 bg-[#0c1222] p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Price vs Reality
          </span>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span className="text-zinc-500">Pressure ({homeName})</span>
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span className="text-zinc-500">Odds (inverted)</span>
          </span>
          {entryZones.length > 0 && (
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-fuchsia-500" />
              <span className="text-fuchsia-400 font-medium">Entry Zone</span>
            </span>
          )}
        </div>
      </div>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={chartData} margin={{ top: 10, right: 10, bottom: 10, left: -10 }}>
          <defs>
            <linearGradient id="entryZoneGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#d946ef" stopOpacity={0.25} />
              <stop offset="100%" stopColor="#d946ef" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis
            dataKey="minute"
            tick={{ fill: "#64748b", fontSize: 10 }}
            axisLine={{ stroke: "#1e293b" }}
            tickLine={false}
            label={{ value: "Match Minute", position: "insideBottom", offset: -5, fill: "#475569", fontSize: 10 }}
          />
          <YAxis
            yAxisId="pressure"
            tick={{ fill: "#64748b", fontSize: 10 }}
            axisLine={{ stroke: "#1e293b" }}
            tickLine={false}
            domain={[0, Math.ceil(maxPressure * 1.2)]}
          />
          <YAxis
            yAxisId="odds"
            orientation="right"
            reversed
            tick={{ fill: "#64748b", fontSize: 10 }}
            axisLine={{ stroke: "#1e293b" }}
            tickLine={false}
            domain={[Math.floor(minOdds * 0.9 * 10) / 10, Math.ceil(maxOdds * 1.1 * 10) / 10]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#0f172a",
              border: "1px solid #1e293b",
              borderRadius: 8,
              fontSize: 11,
            }}
            formatter={(value: number, name: string) => {
              if (name === "pressure") return [`${value.toFixed(1)}`, "Pressure Index"]
              if (name === "odds") return [value ? `${value.toFixed(2)}` : "—", "Back Odds"]
              return [null, null]
            }}
            labelFormatter={(label) => `Minute ${label}'`}
          />

          {/* Entry zone shading */}
          <Area
            yAxisId="pressure"
            dataKey="entryZone"
            fill="url(#entryZoneGrad)"
            stroke="none"
            isAnimationActive={false}
          />

          {/* Reference lines for entry zones */}
          {entryZones.map((z, i) => (
            <ReferenceLine
              key={`zone-start-${i}`}
              x={z.start}
              yAxisId="pressure"
              stroke="#d946ef"
              strokeDasharray="4 4"
              strokeWidth={1}
              label={{
                value: i === 0 ? "ENTRY" : "",
                position: "top",
                fill: "#d946ef",
                fontSize: 9,
              }}
            />
          ))}

          {/* Pressure line */}
          <Line
            yAxisId="pressure"
            type="monotone"
            dataKey="pressure"
            stroke="#34d399"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 3, fill: "#34d399" }}
          />

          {/* Odds line */}
          <Line
            yAxisId="odds"
            type="monotone"
            dataKey="odds"
            stroke="#fbbf24"
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={{ r: 3, fill: "#fbbf24" }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Entry zone callout */}
      {entryZones.length > 0 && (
        <div className="flex items-center gap-2 rounded-lg bg-fuchsia-500/10 border border-fuchsia-500/30 px-3 py-2">
          <Crosshair className="w-3.5 h-3.5 text-fuchsia-400 shrink-0" />
          <span className="text-[11px] text-fuchsia-300">
            <span className="font-bold">{entryZones.length} Entry Zone{entryZones.length > 1 ? "s" : ""}</span>
            {" "}detected — Odds drifting while {homeName} dominates
          </span>
        </div>
      )}

      {/* Legend */}
      <div className="text-[9px] text-zinc-600">
        Divergence = Pressure ↑ + Odds ↑ (market undervaluing team performance)
      </div>
    </div>
  )
}
