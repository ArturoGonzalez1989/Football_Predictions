import type { Capture } from "../lib/api"

interface CaptureTableProps {
  captures: Capture[]
}

export function CaptureTable({ captures }: CaptureTableProps) {
  if (!captures.length) {
    return (
      <p className="text-zinc-500 text-xs text-center py-4">
        No captures yet
      </p>
    )
  }

  return (
    <div className="space-y-1">
      <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
        Latest Captures
      </h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-zinc-500 text-[10px] uppercase tracking-wider">
              <th className="text-left py-1.5 px-2 font-medium">Min</th>
              <th className="text-left py-1.5 px-2 font-medium">Score</th>
              <th className="text-left py-1.5 px-2 font-medium">xG</th>
              <th className="text-left py-1.5 px-2 font-medium">Poss</th>
              <th className="text-left py-1.5 px-2 font-medium">Corners</th>
              <th className="text-left py-1.5 px-2 font-medium">Shots</th>
            </tr>
          </thead>
          <tbody>
            {captures.map((c, i) => (
              <tr
                key={i}
                className="border-t border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
              >
                <td className="py-1.5 px-2 font-mono text-zinc-300">
                  {c.minuto || "—"}
                </td>
                <td className="py-1.5 px-2 font-mono font-semibold text-white">
                  {c.goles}
                </td>
                <td className="py-1.5 px-2 font-mono text-blue-400">
                  {c.xg || "—"}
                </td>
                <td className="py-1.5 px-2 font-mono text-zinc-300">
                  {c.posesion || "—"}
                </td>
                <td className="py-1.5 px-2 font-mono text-zinc-300">
                  {c.corners || "—"}
                </td>
                <td className="py-1.5 px-2 font-mono text-zinc-300">
                  {c.tiros || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
