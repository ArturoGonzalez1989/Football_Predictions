import type { OddsTimeline } from "../lib/api"

interface OddsTableProps {
  data: OddsTimeline[]
  loading?: boolean
}

export function OddsTable({ data, loading }: OddsTableProps) {
  if (loading) {
    return (
      <div className="h-52 flex items-center justify-center text-zinc-500 text-sm">
        Loading odds data...
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
        <div className="text-xs text-zinc-500 text-center">No odds data available yet</div>
      </div>
    )
  }

  // Filter out entries with no odds data and get last 10
  const oddsData = data
    .filter(d => d.back_home || d.back_draw || d.back_away)
    .slice(-10)
    .reverse()

  if (oddsData.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
        <div className="text-xs text-zinc-500 text-center">No odds data available yet</div>
      </div>
    )
  }

  const formatOdds = (value: number | null) => {
    if (!value) return "—"
    return value.toFixed(2)
  }

  const formatVolume = (value: number | null) => {
    if (!value) return "—"
    if (value >= 1000000) return `€${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `€${(value / 1000).toFixed(0)}k`
    return `€${value.toFixed(0)}`
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
          Últimas Cuotas (Últimos 10 minutos)
        </h4>
        <span className="text-[10px] text-zinc-600">
          {oddsData.length} captures
        </span>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead className="bg-zinc-800/50 border-b border-zinc-800">
              <tr>
                <th className="px-2 py-1.5 text-left font-medium text-zinc-400">Min</th>
                <th className="px-2 py-1.5 text-right font-medium text-blue-400">Home</th>
                <th className="px-2 py-1.5 text-right font-medium text-purple-400">Draw</th>
                <th className="px-2 py-1.5 text-right font-medium text-red-400">Away</th>
                <th className="px-2 py-1.5 text-right font-medium text-green-400">Volume</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {oddsData.map((row, idx) => (
                <tr
                  key={idx}
                  className="hover:bg-zinc-800/30 transition-colors"
                >
                  <td className="px-2 py-1.5 text-zinc-300 font-mono">
                    {row.minute ? `${row.minute}′` : "—"}
                  </td>
                  <td className="px-2 py-1.5 text-right text-blue-300 font-mono">
                    {formatOdds(row.back_home)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-purple-300 font-mono">
                    {formatOdds(row.back_draw)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-red-300 font-mono">
                    {formatOdds(row.back_away)}
                  </td>
                  <td className="px-2 py-1.5 text-right text-green-300 font-mono text-[10px]">
                    {formatVolume(row.volumen_matched)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
