interface StatsBarProps {
  label: string
  homeValue: string | number
  awayValue: string | number
  homeColor?: string
  awayColor?: string
}

export function StatsBar({
  label,
  homeValue,
  awayValue,
  homeColor = "#3b82f6",
  awayColor = "#ef4444",
}: StatsBarProps) {
  const hNum = typeof homeValue === "number" ? homeValue : parseFloat(homeValue) || 0
  const aNum = typeof awayValue === "number" ? awayValue : parseFloat(awayValue) || 0
  const total = hNum + aNum
  const homePct = total > 0 ? (hNum / total) * 100 : 50

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-10 text-right font-mono text-zinc-300">{homeValue}</span>
      <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden flex">
        <div
          className="h-full rounded-l-full transition-all duration-500"
          style={{ width: `${homePct}%`, backgroundColor: homeColor }}
        />
        <div
          className="h-full rounded-r-full transition-all duration-500"
          style={{ width: `${100 - homePct}%`, backgroundColor: awayColor }}
        />
      </div>
      <span className="w-10 text-left font-mono text-zinc-300">{awayValue}</span>
      <span className="w-20 text-zinc-500 text-[10px] uppercase tracking-wider">{label}</span>
    </div>
  )
}
