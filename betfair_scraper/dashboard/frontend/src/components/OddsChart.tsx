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

  // Filter out entries with no odds data and get last 5 (menos porque hay más columnas)
  const oddsData = data
    .filter(d => d.back_home || d.lay_home || d.back_draw || d.lay_draw || d.back_away || d.lay_away)
    .slice(-5)
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
          <table className="w-full text-[10px]">
            <thead className="bg-zinc-800/50 border-b border-zinc-800">
              <tr>
                <th className="px-1.5 py-1.5 text-left font-medium text-zinc-400" rowSpan={2}>Min</th>
                <th className="px-1.5 py-1 text-center font-medium text-blue-400 border-b border-zinc-700" colSpan={2}>Home</th>
                <th className="px-1.5 py-1 text-center font-medium text-purple-400 border-b border-zinc-700" colSpan={2}>Draw</th>
                <th className="px-1.5 py-1 text-center font-medium text-red-400 border-b border-zinc-700" colSpan={2}>Away</th>
                <th className="px-1.5 py-1.5 text-right font-medium text-green-400" rowSpan={2}>Vol</th>
              </tr>
              <tr>
                <th className="px-1.5 py-1 text-right font-medium text-blue-300 text-[9px]">Back</th>
                <th className="px-1.5 py-1 text-right font-medium text-blue-300 text-[9px]">Lay</th>
                <th className="px-1.5 py-1 text-right font-medium text-purple-300 text-[9px]">Back</th>
                <th className="px-1.5 py-1 text-right font-medium text-purple-300 text-[9px]">Lay</th>
                <th className="px-1.5 py-1 text-right font-medium text-red-300 text-[9px]">Back</th>
                <th className="px-1.5 py-1 text-right font-medium text-red-300 text-[9px]">Lay</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {oddsData.map((row, idx) => (
                <tr
                  key={idx}
                  className="hover:bg-zinc-800/30 transition-colors"
                >
                  <td className="px-1.5 py-1.5 text-zinc-300 font-mono">
                    {row.minute ? `${row.minute}′` : "—"}
                  </td>
                  <td className="px-1.5 py-1.5 text-right text-blue-300 font-mono">
                    {formatOdds(row.back_home)}
                  </td>
                  <td className="px-1.5 py-1.5 text-right text-blue-200 font-mono">
                    {formatOdds(row.lay_home)}
                  </td>
                  <td className="px-1.5 py-1.5 text-right text-purple-300 font-mono">
                    {formatOdds(row.back_draw)}
                  </td>
                  <td className="px-1.5 py-1.5 text-right text-purple-200 font-mono">
                    {formatOdds(row.lay_draw)}
                  </td>
                  <td className="px-1.5 py-1.5 text-right text-red-300 font-mono">
                    {formatOdds(row.back_away)}
                  </td>
                  <td className="px-1.5 py-1.5 text-right text-red-200 font-mono">
                    {formatOdds(row.lay_away)}
                  </td>
                  <td className="px-1.5 py-1.5 text-right text-green-300 font-mono text-[9px]">
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

export function OverUnderTable({ data, loading }: OddsTableProps) {
  if (loading) {
    return (
      <div className="h-52 flex items-center justify-center text-zinc-500 text-sm">
        Loading Over/Under data...
      </div>
    )
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
        <div className="text-xs text-zinc-500 text-center">No Over/Under data available yet</div>
      </div>
    )
  }

  // Filter out entries with no over/under data and get last 5
  const oddsData = data
    .filter(d => d.back_over05 || d.back_over15 || d.back_over25 || d.back_over35 || d.back_over45)
    .slice(-5)
    .reverse()

  if (oddsData.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
        <div className="text-xs text-zinc-500 text-center">No Over/Under data available yet</div>
      </div>
    )
  }

  const formatOdds = (value: number | null) => {
    if (!value) return "—"
    return value.toFixed(2)
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
          Over/Under Goals
        </h4>
        <span className="text-[10px] text-zinc-600">
          {oddsData.length} captures
        </span>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-[9px]">
            <thead className="bg-zinc-800/50 border-b border-zinc-800">
              <tr>
                <th className="px-1 py-1.5 text-left font-medium text-zinc-400" rowSpan={3}>Min</th>
                <th className="px-1 py-0.5 text-center font-medium text-orange-400 border-b border-zinc-700" colSpan={4}>O/U 0.5</th>
                <th className="px-1 py-0.5 text-center font-medium text-cyan-400 border-b border-zinc-700" colSpan={4}>O/U 1.5</th>
                <th className="px-1 py-0.5 text-center font-medium text-teal-400 border-b border-zinc-700" colSpan={4}>O/U 2.5</th>
                <th className="px-1 py-0.5 text-center font-medium text-indigo-400 border-b border-zinc-700" colSpan={4}>O/U 3.5</th>
                <th className="px-1 py-0.5 text-center font-medium text-pink-400 border-b border-zinc-700" colSpan={4}>O/U 4.5</th>
              </tr>
              <tr>
                <th className="px-1 py-0.5 text-center font-medium text-orange-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Over</th>
                <th className="px-1 py-0.5 text-center font-medium text-orange-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Under</th>
                <th className="px-1 py-0.5 text-center font-medium text-cyan-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Over</th>
                <th className="px-1 py-0.5 text-center font-medium text-cyan-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Under</th>
                <th className="px-1 py-0.5 text-center font-medium text-teal-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Over</th>
                <th className="px-1 py-0.5 text-center font-medium text-teal-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Under</th>
                <th className="px-1 py-0.5 text-center font-medium text-indigo-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Over</th>
                <th className="px-1 py-0.5 text-center font-medium text-indigo-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Under</th>
                <th className="px-1 py-0.5 text-center font-medium text-pink-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Over</th>
                <th className="px-1 py-0.5 text-center font-medium text-pink-300 border-b border-zinc-700 text-[8px]" colSpan={2}>Under</th>
              </tr>
              <tr>
                <th className="px-1 py-0.5 text-right font-medium text-orange-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-orange-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-orange-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-orange-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-cyan-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-cyan-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-cyan-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-cyan-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-teal-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-teal-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-teal-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-teal-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-indigo-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-indigo-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-indigo-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-indigo-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-pink-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-pink-200 text-[7px]">L</th>
                <th className="px-1 py-0.5 text-right font-medium text-pink-200 text-[7px]">B</th>
                <th className="px-1 py-0.5 text-right font-medium text-pink-200 text-[7px]">L</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {oddsData.map((row, idx) => (
                <tr
                  key={idx}
                  className="hover:bg-zinc-800/30 transition-colors"
                >
                  <td className="px-1 py-1 text-zinc-300 font-mono">
                    {row.minute ? `${row.minute}′` : "—"}
                  </td>
                  {/* O/U 0.5 */}
                  <td className="px-1 py-1 text-right text-orange-300 font-mono">{formatOdds(row.back_over05)}</td>
                  <td className="px-1 py-1 text-right text-orange-200 font-mono">{formatOdds(row.lay_over05)}</td>
                  <td className="px-1 py-1 text-right text-orange-300 font-mono">{formatOdds(row.back_under05)}</td>
                  <td className="px-1 py-1 text-right text-orange-200 font-mono">{formatOdds(row.lay_under05)}</td>
                  {/* O/U 1.5 */}
                  <td className="px-1 py-1 text-right text-cyan-300 font-mono">{formatOdds(row.back_over15)}</td>
                  <td className="px-1 py-1 text-right text-cyan-200 font-mono">{formatOdds(row.lay_over15)}</td>
                  <td className="px-1 py-1 text-right text-cyan-300 font-mono">{formatOdds(row.back_under15)}</td>
                  <td className="px-1 py-1 text-right text-cyan-200 font-mono">{formatOdds(row.lay_under15)}</td>
                  {/* O/U 2.5 */}
                  <td className="px-1 py-1 text-right text-teal-300 font-mono">{formatOdds(row.back_over25)}</td>
                  <td className="px-1 py-1 text-right text-teal-200 font-mono">{formatOdds(row.lay_over25)}</td>
                  <td className="px-1 py-1 text-right text-teal-300 font-mono">{formatOdds(row.back_under25)}</td>
                  <td className="px-1 py-1 text-right text-teal-200 font-mono">{formatOdds(row.lay_under25)}</td>
                  {/* O/U 3.5 */}
                  <td className="px-1 py-1 text-right text-indigo-300 font-mono">{formatOdds(row.back_over35)}</td>
                  <td className="px-1 py-1 text-right text-indigo-200 font-mono">{formatOdds(row.lay_over35)}</td>
                  <td className="px-1 py-1 text-right text-indigo-300 font-mono">{formatOdds(row.back_under35)}</td>
                  <td className="px-1 py-1 text-right text-indigo-200 font-mono">{formatOdds(row.lay_under35)}</td>
                  {/* O/U 4.5 */}
                  <td className="px-1 py-1 text-right text-pink-300 font-mono">{formatOdds(row.back_over45)}</td>
                  <td className="px-1 py-1 text-right text-pink-200 font-mono">{formatOdds(row.lay_over45)}</td>
                  <td className="px-1 py-1 text-right text-pink-300 font-mono">{formatOdds(row.back_under45)}</td>
                  <td className="px-1 py-1 text-right text-pink-200 font-mono">{formatOdds(row.lay_under45)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
