import { cn } from "../lib/utils"

interface GapAnalysisProps {
  gaps: number[]
  totalGaps: number
  matchMinute: number | null
}

export function GapAnalysis({ gaps, totalGaps, matchMinute }: GapAnalysisProps) {
  if (!matchMinute) return null

  const maxMin = matchMinute
  const gapSet = new Set(gaps)

  const blocks = Array.from({ length: maxMin }, (_, i) => i + 1)

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between px-1">
        <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
          Capture Timeline
        </h4>
        {totalGaps > 0 ? (
          <span className="text-[10px] text-yellow-400">
            {totalGaps} gaps detected
          </span>
        ) : (
          <span className="text-[10px] text-green-400">
            No gaps
          </span>
        )}
      </div>
      <div className="flex gap-px flex-wrap">
        {blocks.map((min) => (
          <div
            key={min}
            title={`Minute ${min}${gapSet.has(min) ? " (MISSING)" : ""}`}
            className={cn(
              "h-3 rounded-sm transition-colors",
              gapSet.has(min) ? "bg-yellow-500/60" : "bg-green-500/40",
              blocks.length > 60 ? "w-1" : "w-1.5"
            )}
          />
        ))}
      </div>
      <div className="flex justify-between text-[10px] text-zinc-600 px-1">
        <span>0′</span>
        <span>45′</span>
        <span>{maxMin}′</span>
      </div>
    </div>
  )
}
