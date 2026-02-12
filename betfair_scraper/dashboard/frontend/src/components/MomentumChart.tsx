import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Area,
  AreaChart,
} from "recharts"
import type { MomentumData } from "../lib/api"

interface MomentumChartProps {
  data: MomentumData | null
  loading?: boolean
}

export function MomentumChart({ data, loading }: MomentumChartProps) {
  if (loading) {
    return (
      <div className="h-52 flex items-center justify-center text-zinc-500 text-sm">
        Loading momentum data...
      </div>
    )
  }

  if (!data || data.data_points === 0) {
    return (
      <div className="h-52 flex items-center justify-center text-zinc-500 text-sm">
        No momentum data available yet
      </div>
    )
  }

  const chartData = data.minutes.map((min, i) => ({
    minute: min,
    home: data.momentum.home[i],
    away: data.momentum.away[i],
  }))

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
          Momentum
        </h4>
        <span className="text-[10px] text-zinc-600">
          {data.data_points} data points
        </span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="gradHome" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="gradAway" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="minute"
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={{ stroke: "#27272a" }}
            tickLine={false}
            tickFormatter={(v) => `${v}′`}
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={{ stroke: "#27272a" }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#18181b",
              border: "1px solid #27272a",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(v) => `Minute ${v}′`}
          />
          <Area
            type="monotone"
            dataKey="home"
            stroke="#3b82f6"
            strokeWidth={2}
            fill="url(#gradHome)"
            name="Home"
            dot={false}
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="away"
            stroke="#ef4444"
            strokeWidth={2}
            fill="url(#gradAway)"
            name="Away"
            dot={false}
            connectNulls
          />
          <Legend
            iconType="line"
            wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

interface XgChartProps {
  data: MomentumData | null
}

export function XgChart({ data }: XgChartProps) {
  if (!data || data.data_points === 0) return null

  const chartData = data.minutes.map((min, i) => ({
    minute: min,
    home: data.xg.home[i],
    away: data.xg.away[i],
  }))

  return (
    <div className="space-y-1">
      <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
        xG Timeline
      </h4>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="minute"
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={{ stroke: "#27272a" }}
            tickLine={false}
            tickFormatter={(v) => `${v}′`}
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10 }}
            axisLine={{ stroke: "#27272a" }}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#18181b",
              border: "1px solid #27272a",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(v) => `Minute ${v}′`}
          />
          <Line
            type="stepAfter"
            dataKey="home"
            stroke="#3b82f6"
            strokeWidth={2}
            name="Home xG"
            dot={false}
            connectNulls
          />
          <Line
            type="stepAfter"
            dataKey="away"
            stroke="#ef4444"
            strokeWidth={2}
            name="Away xG"
            dot={false}
            connectNulls
          />
          <Legend
            iconType="line"
            wrapperStyle={{ fontSize: 11, color: "#a1a1aa" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
