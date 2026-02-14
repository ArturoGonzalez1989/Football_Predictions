import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  BarChart,
  Bar,
  Cell,
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

  // Calculate momentum deltas (changes between consecutive captures)
  const chartData = data.minutes.map((min, i) => {
    if (i === 0) {
      return {
        minute: min,
        net: 0,
        homeGain: 0,
        awayGain: 0,
      }
    }

    const homePrev = data.momentum.home[i - 1] ?? 0
    const homeCurr = data.momentum.home[i] ?? 0
    const awayPrev = data.momentum.away[i - 1] ?? 0
    const awayCurr = data.momentum.away[i] ?? 0

    const homeDelta = homeCurr - homePrev
    const awayDelta = awayCurr - awayPrev

    // Net momentum: positive = home gained more, negative = away gained more
    const net = homeDelta - awayDelta

    return {
      minute: min,
      net,
      homeGain: homeDelta,
      awayGain: awayDelta,
    }
  })

  // Custom tooltip to show details
  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload.length) return null

    const data = payload[0].payload
    return (
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-2 text-[11px]">
        <div className="font-medium text-zinc-300 mb-1">Minute {data.minute}′</div>
        <div className="space-y-0.5">
          <div className="text-blue-400">Home: +{data.homeGain.toFixed(1)}</div>
          <div className="text-orange-400">Away: +{data.awayGain.toFixed(1)}</div>
          <div className={`font-medium ${data.net > 0 ? "text-blue-400" : "text-orange-400"}`}>
            {data.net > 0 ? "Home dominance" : "Away dominance"}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
          Momentum (Instantaneous)
        </h4>
        <span className="text-[10px] text-zinc-600">
          {data.data_points} periods
        </span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
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
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="net" radius={[2, 2, 0, 0]}>
            {chartData.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.net >= 0 ? "#3b82f6" : "#f97316"}
                opacity={0.8}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex items-center justify-center gap-4 text-[10px] text-zinc-500">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-blue-500/80 rounded-sm" />
          <span>Home dominance</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 bg-orange-500/80 rounded-sm" />
          <span>Away dominance</span>
        </div>
      </div>
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
