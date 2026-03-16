import { useState, useEffect, useMemo } from "react"

// ─── Types ─────────────────────────────────────────────────────────────────────

interface Kpis {
  total_bets: number; wins: number; win_rate: number; total_pl: number
  roi: number; max_dd: number; best_streak: number; worst_streak: number
  sharpe: number; profit_factor: number
}
interface CumulPoint  { won: boolean; pl: number; cumul_pl: number; strategy: string }
interface ByStrategy  { strategy: string; bets: number; wins: number; win_pct: number; pl: number; roi: number; pl_per_bet: number }
interface ByGroup     { name: string; bets: number; wins: number; win_pct: number; pl: number; roi: number }
interface MinuteBucket { bucket: string; minute: number; bets: number; pl: number }
interface OddsBucket  { bucket: string; bets: number; pl: number }
interface WeekdayRow  { day: string; bets: number; wins: number; win_pct: number; pl: number; roi: number }
interface HourRow     { hour: number; bets: number; pl: number }
interface MonthRow    { month: string; bets: number; pl: number }
interface DateRow     { date: string; bets: number; wins: number; win_pct: number; pl: number; roi: number }

interface OddsCalibRow { bucket: string; bets: number; actual_wr: number; implied_wr: number; edge: number }
interface StratDrawdownRow { strategy: string; max_dd: number; total_pl: number }
interface HeatmapCell { pl: number; bets: number; roi: number | null }
interface HeatmapRowData { strategy: string; values: HeatmapCell[] }
interface HeatmapData { leagues: string[]; rows: HeatmapRowData[] }

interface BtData {
  filename: string; total_matches: number; kpis: Kpis; cumul: CumulPoint[]
  by_strategy: ByStrategy[]; by_country: ByGroup[]; by_league: ByGroup[]
  by_minute: MinuteBucket[]; by_odds: OddsBucket[]; by_weekday: WeekdayRow[]
  by_hour: HourRow[]; by_month: MonthRow[]; by_date: DateRow[]
  strat_cumul: Record<string, number[]>
  strat_drawdown: StratDrawdownRow[]
  odds_calibration: OddsCalibRow[]
  heatmap: HeatmapData
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const wrColor  = (v: number) => v >= 70 ? "text-emerald-400" : v >= 50 ? "text-amber-400" : "text-red-400"
const roiColor = (v: number) => v >= 30 ? "text-emerald-400" : v >= 0  ? "text-amber-400" : "text-red-400"
const plColor  = (v: number) => v >= 0  ? "text-emerald-400" : "text-red-400"
const plSign   = (v: number) => v >= 0  ? `+${v.toFixed(2)}` : v.toFixed(2)

// ─── KPI Card ──────────────────────────────────────────────────────────────────

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-3">
      <div className="text-[10px] text-zinc-500 uppercase tracking-wide mb-1">{label}</div>
      <div className="text-xl font-bold text-zinc-100">{value}</div>
    </div>
  )
}

// ─── Last 7 Days widget ────────────────────────────────────────────────────────

function Last7Days({ data }: { data: DateRow[] }) {
  const last7 = data.slice(-7)
  if (!last7.length) return <div className="text-xs text-zinc-600 text-center py-3">Sin datos con timestamp</div>

  return (
    <div className="grid grid-cols-7 gap-2">
      {last7.map((d, i) => {
        const dateParts = d.date.slice(5) // "MM-DD"
        const isPos = d.pl >= 0
        return (
          <div key={i} className={`rounded-lg p-2.5 border ${isPos ? "bg-emerald-950/40 border-emerald-800/40" : "bg-red-950/40 border-red-800/40"}`}>
            <div className="text-[10px] text-zinc-400 font-medium mb-1.5">{dateParts}</div>
            <div className="text-xs text-zinc-500 mb-0.5">N</div>
            <div className="text-sm font-bold text-zinc-200 mb-1">{d.bets}</div>
            <div className="text-[10px] text-zinc-500">WR</div>
            <div className={`text-xs font-bold mb-1 ${wrColor(d.win_pct)}`}>{d.win_pct.toFixed(0)}%</div>
            <div className="text-[10px] text-zinc-500">ROI</div>
            <div className={`text-xs font-bold mb-1 ${roiColor(d.roi)}`}>{d.roi.toFixed(0)}%</div>
            <div className="text-[10px] text-zinc-500">P/L</div>
            <div className={`text-xs font-bold ${plColor(d.pl)}`}>{plSign(d.pl)}</div>
          </div>
        )
      })}
    </div>
  )
}

// ─── Cumulative P/L chart ──────────────────────────────────────────────────────

function PLChart({ data }: { data: CumulPoint[] }) {
  if (!data.length) return null
  const maxPL = Math.max(...data.map(d => d.cumul_pl), 0)
  const minPL = Math.min(...data.map(d => d.cumul_pl), 0)
  const range = maxPL - minPL || 1
  const zeroBottom = ((0 - minPL) / range) * 100

  return (
    <div className="relative h-40">
      <div className="absolute left-0 top-0 bottom-0 w-12 flex flex-col justify-between text-[10px] text-zinc-500 pointer-events-none select-none">
        <span>+{maxPL.toFixed(0)}</span><span>0</span><span>{minPL.toFixed(0)}</span>
      </div>
      <div className="ml-12 h-full flex items-end gap-px overflow-hidden">
        {data.map((p, i) => {
          const h = Math.max(((p.cumul_pl - minPL) / range) * 100, 1)
          const isPos = p.cumul_pl >= 0
          return (
            <div key={i} className="flex-1 min-w-[2px] relative group" style={{ height: `${h}%` }}>
              <div className={`w-full h-full rounded-t ${isPos ? "bg-emerald-500/70" : "bg-red-500/70"}`} />
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 opacity-0 group-hover:opacity-100 bg-zinc-800 text-white text-[10px] px-2 py-1 rounded whitespace-pre pointer-events-none z-10">
                {isPos ? "+" : ""}{p.cumul_pl.toFixed(2)} €
              </div>
            </div>
          )
        })}
      </div>
      <div className="absolute left-12 right-0 border-t border-zinc-600 pointer-events-none" style={{ bottom: `${zeroBottom}%` }} />
    </div>
  )
}

// ─── Generic bar chart (minute, odds, month, hour) ────────────────────────────
// Fix: bars are direct flex children of h-24 container so height% works.
// Labels are in a separate row below.

interface BarItem { label: string; value: number; isPos?: boolean }

function BarChart({ items, colorMode = "positive", showEveryN = 1 }: {
  items: BarItem[]
  colorMode?: "positive" | "pl"
  showEveryN?: number
}) {
  if (!items.length) return <div className="text-xs text-zinc-600 text-center py-4">Sin datos</div>
  const maxAbs = Math.max(...items.map(d => Math.abs(d.value)), 0.01)

  return (
    <div>
      {/* Bar row — direct children so height% works */}
      <div className="flex items-end gap-[2px] h-24">
        {items.map((d, i) => {
          const pct = Math.abs(d.value) / maxAbs * 100
          const isPos = colorMode === "pl" ? (d.isPos ?? d.value >= 0) : true
          const colorCls = colorMode === "pl"
            ? (isPos ? "bg-emerald-500/80" : "bg-red-500/80")
            : "bg-emerald-500/60 hover:bg-emerald-500/90"
          return (
            <div
              key={i}
              title={`${d.label}: ${d.value}`}
              className={`flex-1 min-w-[3px] rounded-t cursor-default transition-opacity ${colorCls}`}
              style={{ height: `${Math.max(pct, 2)}%` }}
            />
          )
        })}
      </div>
      {/* Label row */}
      <div className="flex gap-[2px] mt-1">
        {items.map((d, i) => (
          <div key={i} className="flex-1 text-center">
            {i % showEveryN === 0 && (
              <span className="text-[8px] text-zinc-600 leading-none">{d.label}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Sortable group table (País, Liga) ─────────────────────────────────────────

type SortField = "name" | "bets" | "win_pct" | "roi" | "pl"

function GroupTable({ data }: { data: ByGroup[] }) {
  const [sortCol, setSortCol] = useState<SortField>("pl")
  const [sortDir, setSortDir] = useState<1 | -1>(-1)

  const sorted = useMemo(() => [...data].sort((a, b) => {
    const av = a[sortCol] ?? 0; const bv = b[sortCol] ?? 0
    return typeof av === "string" ? av.localeCompare(String(bv)) * sortDir : (Number(av) - Number(bv)) * sortDir
  }), [data, sortCol, sortDir])

  function onSort(col: SortField) {
    if (col === sortCol) setSortDir(d => (d === -1 ? 1 : -1))
    else { setSortCol(col); setSortDir(-1) }
  }

  const TH = ({ col, label, left = false }: { col: SortField; label: string; left?: boolean }) => (
    <th onClick={() => onSort(col)}
      className={`text-[10px] text-zinc-400 uppercase tracking-wide px-2 py-1.5 cursor-pointer select-none hover:text-zinc-200 ${left ? "text-left" : "text-right"}`}>
      {label}{sortCol === col ? (sortDir === -1 ? " ↓" : " ↑") : ""}
    </th>
  )

  return (
    <div className="overflow-auto max-h-72">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-zinc-900">
          <tr><TH col="name" label="" left /><TH col="bets" label="N" /><TH col="win_pct" label="WR%" /><TH col="roi" label="ROI%" /><TH col="pl" label="P/L €" /></tr>
        </thead>
        <tbody>
          {sorted.slice(0, 20).map((row, i) => (
            <tr key={i} className="border-t border-zinc-800/50 hover:bg-zinc-800/30">
              <td className="px-2 py-1 text-zinc-300 max-w-[140px] truncate">{row.name}</td>
              <td className="px-2 py-1 text-right text-zinc-400">{row.bets}</td>
              <td className={`px-2 py-1 text-right font-medium ${wrColor(row.win_pct)}`}>{row.win_pct.toFixed(1)}%</td>
              <td className={`px-2 py-1 text-right font-medium ${roiColor(row.roi)}`}>{row.roi.toFixed(1)}%</td>
              <td className={`px-2 py-1 text-right font-bold ${plColor(row.pl)}`}>{plSign(row.pl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Strategy table with inline P/L bar ───────────────────────────────────────

type StratSortField = "strategy" | "bets" | "win_pct" | "roi" | "pl" | "pl_per_bet"

function StrategyTable({ data }: { data: ByStrategy[] }) {
  const [sortCol, setSortCol] = useState<StratSortField>("roi")
  const [sortDir, setSortDir] = useState<1 | -1>(-1)

  const sorted = useMemo(() => [...data].sort((a, b) => {
    const av = a[sortCol] ?? 0; const bv = b[sortCol] ?? 0
    return typeof av === "string" ? av.localeCompare(String(bv)) * sortDir : (Number(av) - Number(bv)) * sortDir
  }), [data, sortCol, sortDir])

  const maxAbsPl = Math.max(...data.map(d => Math.abs(d.pl)), 0.01)

  function onSort(col: StratSortField) {
    if (col === sortCol) setSortDir(d => (d === -1 ? 1 : -1))
    else { setSortCol(col); setSortDir(-1) }
  }

  const TH = ({ col, label, left = false }: { col: StratSortField; label: string; left?: boolean }) => (
    <th onClick={() => onSort(col)}
      className={`text-[10px] text-zinc-400 uppercase tracking-wide px-2 py-2 cursor-pointer select-none hover:text-zinc-200 ${left ? "text-left" : "text-right"}`}>
      {label}{sortCol === col ? (sortDir === -1 ? " ↓" : " ↑") : ""}
    </th>
  )

  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-zinc-900">
        <tr><TH col="strategy" label="Estrategia" left /><TH col="bets" label="N" /><TH col="win_pct" label="WR%" /><TH col="roi" label="ROI%" /><TH col="pl_per_bet" label="P/L bet" /><TH col="pl" label="P/L €" /></tr>
      </thead>
      <tbody>
        {sorted.map((row, i) => {
          const barPct = Math.abs(row.pl) / maxAbsPl * 100
          const isPos = row.pl >= 0
          const plb = row.pl_per_bet ?? 0
          return (
            <tr key={i} className="border-t border-zinc-800/50 hover:bg-zinc-800/30">
              <td className="px-2 py-1.5 text-zinc-200 font-medium">{row.strategy}</td>
              <td className="px-2 py-1.5 text-right text-zinc-400">{row.bets}</td>
              <td className={`px-2 py-1.5 text-right font-medium ${wrColor(row.win_pct)}`}>{row.win_pct.toFixed(1)}%</td>
              <td className={`px-2 py-1.5 text-right font-medium ${roiColor(row.roi)}`}>{row.roi.toFixed(1)}%</td>
              <td className={`px-2 py-1.5 text-right font-medium ${plColor(plb)}`}>{plb >= 0 ? "+" : ""}{plb.toFixed(3)}u</td>
              <td className="px-2 py-1.5 text-right">
                <div className="flex items-center justify-end gap-2">
                  <div className="w-16 h-1.5 bg-zinc-800 rounded overflow-hidden">
                    <div className={`h-full rounded ${isPos ? "bg-emerald-500" : "bg-red-500"}`} style={{ width: `${barPct}%` }} />
                  </div>
                  <span className={`font-bold w-14 text-right ${plColor(row.pl)}`}>{plSign(row.pl)}</span>
                </div>
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ─── Weekday table ─────────────────────────────────────────────────────────────

function WeekdayTable({ data }: { data: WeekdayRow[] }) {
  if (!data.length) return <div className="text-xs text-zinc-600 text-center py-4">Sin datos con timestamp</div>
  return (
    <table className="w-full text-xs">
      <thead>
        <tr>
          {["Día", "N", "WR%", "ROI%", "P/L €"].map(h => (
            <th key={h} className={`text-[10px] text-zinc-400 uppercase tracking-wide px-2 py-1.5 ${h === "Día" ? "text-left" : "text-right"}`}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, i) => (
          <tr key={i} className="border-t border-zinc-800/50 hover:bg-zinc-800/30">
            <td className="px-2 py-1 text-zinc-300 font-medium">{row.day}</td>
            <td className="px-2 py-1 text-right text-zinc-400">{row.bets}</td>
            <td className={`px-2 py-1 text-right ${wrColor(row.win_pct)}`}>{row.win_pct.toFixed(1)}%</td>
            <td className={`px-2 py-1 text-right ${roiColor(row.roi)}`}>{row.roi.toFixed(1)}%</td>
            <td className={`px-2 py-1 text-right font-bold ${plColor(row.pl)}`}>{plSign(row.pl)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// ─── Multi-line cumulative P/L per strategy ────────────────────────────────────

const STRAT_COLORS = [
  "#34d399","#60a5fa","#f59e0b","#f87171","#a78bfa",
  "#fb923c","#38bdf8","#4ade80","#e879f9","#fbbf24",
  "#2dd4bf","#818cf8","#f472b6","#a3e635","#facc15",
]

function MultiLineChart({ data }: { data: Record<string, number[]> }) {
  const [hovered, setHovered] = useState<string | null>(null)
  const entries = Object.entries(data)
  if (!entries.length) return <div className="text-xs text-zinc-600 text-center py-4">Sin datos</div>

  const W = 700, H = 140, PL = 36, PT = 8, PB = 4
  const allVals = entries.flatMap(([, s]) => s)
  const minV = Math.min(...allVals, 0)
  const maxV = Math.max(...allVals, 0)
  const range = maxV - minV || 1

  function tx(idx: number, total: number) { return PL + (idx / Math.max(total - 1, 1)) * (W - PL) }
  function ty(v: number) { return PT + (1 - (v - minV) / range) * (H - PT - PB) }
  const zeroY = ty(0)

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-36 overflow-visible">
        <line x1={PL} x2={W} y1={zeroY} y2={zeroY} stroke="#3f3f46" strokeWidth="1" strokeDasharray="4 2" />
        <text x={PL - 4} y={PT + 5} textAnchor="end" fontSize="8" fill="#71717a">{maxV.toFixed(0)}</text>
        <text x={PL - 4} y={H - PB} textAnchor="end" fontSize="8" fill="#71717a">{minV.toFixed(0)}</text>
        {entries.map(([strat, series], i) => {
          const color = STRAT_COLORS[i % STRAT_COLORS.length]
          const pts = series.map((v, j) => `${tx(j, series.length)},${ty(v)}`).join(" ")
          const dim = hovered !== null && hovered !== strat
          return (
            <polyline key={strat} points={pts} fill="none" stroke={color}
              strokeWidth={hovered === strat ? 2.5 : 1.2}
              opacity={dim ? 0.15 : 0.9}
              onMouseEnter={() => setHovered(strat)} onMouseLeave={() => setHovered(null)}
              className="cursor-pointer transition-opacity"
            />
          )
        })}
      </svg>
      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-2">
        {entries.map(([strat, series], i) => {
          const color = STRAT_COLORS[i % STRAT_COLORS.length]
          const last = series[series.length - 1] ?? 0
          return (
            <div key={strat} className="flex items-center gap-1 cursor-pointer"
              onMouseEnter={() => setHovered(strat)} onMouseLeave={() => setHovered(null)}>
              <div className="w-4 h-0.5 rounded" style={{ backgroundColor: color }} />
              <span className="text-[9px] text-zinc-400">{strat}</span>
              <span className={`text-[9px] font-bold ${last >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {last >= 0 ? "+" : ""}{last.toFixed(1)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Odds calibration: actual WR vs implied WR ────────────────────────────────

function OddsCalibrationChart({ data }: { data: OddsCalibRow[] }) {
  if (!data.length) return <div className="text-xs text-zinc-600 text-center py-4">Sin datos</div>
  const maxWr = Math.max(...data.flatMap(d => [d.actual_wr, d.implied_wr]), 1)

  return (
    <div>
      <div className="flex items-end gap-4 mb-2" style={{ height: "96px" }}>
        {data.map((d, i) => (
          <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
            <div className="w-full flex items-end justify-center gap-1" style={{ height: "80px" }}>
              <div className="w-5 bg-emerald-500/70 rounded-t transition-all"
                style={{ height: `${(d.actual_wr / maxWr) * 100}%` }}
                title={`WR Real: ${d.actual_wr}%`} />
              <div className="w-5 bg-amber-500/50 rounded-t transition-all"
                style={{ height: `${(d.implied_wr / maxWr) * 100}%` }}
                title={`WR Implícita: ${d.implied_wr}%`} />
            </div>
            <div className={`text-[9px] font-bold ${d.edge > 0 ? "text-emerald-400" : "text-red-400"}`}>
              {d.edge > 0 ? "+" : ""}{d.edge}%
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-3 text-[9px] text-zinc-400 mb-2">
        {data.map((d, i) => (
          <div key={i} className="flex-1 text-center text-zinc-500">{d.bucket}</div>
        ))}
      </div>
      <div className="flex gap-4 mt-1 text-[9px] text-zinc-400">
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-2 bg-emerald-500/70 rounded" /> WR Real</span>
        <span className="flex items-center gap-1"><span className="inline-block w-3 h-2 bg-amber-500/50 rounded" /> WR Implícita (1/odds)</span>
        <span className="ml-2 text-zinc-500">Edge = WR Real − WR Implícita</span>
      </div>
    </div>
  )
}

// ─── Max drawdown per strategy (horizontal bars) ──────────────────────────────

function DrawdownChart({ data }: { data: StratDrawdownRow[] }) {
  if (!data.length) return <div className="text-xs text-zinc-600 text-center py-4">Sin datos</div>
  const maxDD = Math.max(...data.map(d => d.max_dd), 0.01)

  return (
    <div className="space-y-1.5">
      {data.map((d, i) => {
        const pct = d.max_dd / maxDD * 100
        return (
          <div key={i} className="flex items-center gap-2">
            <div className="text-[9px] text-zinc-400 w-36 truncate text-right shrink-0" title={d.strategy}>{d.strategy}</div>
            <div className="flex-1 h-4 bg-zinc-800 rounded overflow-hidden">
              <div className="h-full bg-red-500/60 rounded flex items-center" style={{ width: `${pct}%` }}>
                <span className="text-[8px] text-red-200 px-1 truncate">{d.max_dd.toFixed(1)}</span>
              </div>
            </div>
            <span className={`text-[9px] font-bold w-12 text-right shrink-0 ${d.total_pl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {d.total_pl >= 0 ? "+" : ""}{d.total_pl.toFixed(1)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ─── Strategy × League heatmap ────────────────────────────────────────────────

function HeatmapChart({ data }: { data: HeatmapData }) {
  if (!data.rows.length) return <div className="text-xs text-zinc-600 text-center py-4">Sin datos</div>
  const allRois = data.rows.flatMap(r => r.values.map(v => v.roi)).filter((v): v is number => v !== null)
  const maxAbs = Math.max(...allRois.map(Math.abs), 1)

  function cellStyle(roi: number | null): React.CSSProperties {
    if (roi === null) return { backgroundColor: "rgba(39,39,42,0.4)" }
    const intensity = Math.min(Math.abs(roi) / maxAbs, 1)
    return roi > 0
      ? { backgroundColor: `rgba(52,211,153,${0.08 + intensity * 0.55})` }
      : { backgroundColor: `rgba(239,68,68,${0.08 + intensity * 0.55})` }
  }

  return (
    <div className="overflow-auto">
      <table className="text-[9px] border-collapse">
        <thead>
          <tr>
            <th className="text-zinc-500 px-2 py-1 text-right min-w-[120px]" />
            {data.leagues.map(lg => (
              <th key={lg} className="text-zinc-500 px-1 py-1 text-center min-w-[52px] max-w-[52px]" title={lg}>
                <span className="block truncate">{lg.length > 11 ? lg.slice(0, 10) + "…" : lg}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, i) => (
            <tr key={i}>
              <td className="text-zinc-400 px-2 py-0.5 text-right truncate max-w-[120px]" title={row.strategy}>
                {row.strategy.length > 17 ? row.strategy.slice(0, 16) + "…" : row.strategy}
              </td>
              {row.values.map((cell, j) => (
                <td key={j} className="px-1 py-0.5 text-center font-medium"
                  style={cellStyle(cell.roi)}
                  title={`${row.strategy} × ${data.leagues[j]}: N=${cell.bets}, P/L=${cell.pl}`}>
                  {cell.roi !== null
                    ? <span className={cell.roi >= 0 ? "text-emerald-200" : "text-red-200"}>{cell.roi > 0 ? "+" : ""}{cell.roi.toFixed(0)}%</span>
                    : <span className="text-zinc-700">—</span>
                  }
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-zinc-900/60 border border-zinc-800 rounded-lg p-4">
      <h2 className="text-xs font-semibold text-zinc-400 uppercase tracking-wide mb-3">{title}</h2>
      {children}
    </section>
  )
}

// ─── Main View ────────────────────────────────────────────────────────────────

export function BacktestView() {
  const [data, setData] = useState<BtData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch("/api/config/bt-results")
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [])

  if (loading) return <div className="p-6 text-zinc-400 animate-pulse">Cargando backtest...</div>
  if (error || !data) return <div className="p-6 text-red-400">Error cargando datos: {error}</div>

  const { kpis, cumul, by_strategy, by_country, by_league, by_minute, by_odds,
          by_weekday, by_hour, by_month, by_date, filename, total_matches,
          strat_cumul, strat_drawdown, odds_calibration, heatmap } = data

  // Transform data for BarChart
  const minuteItems: BarItem[] = by_minute.map(d => ({ label: d.bucket.split("-")[0], value: d.bets }))
  const oddsItems: BarItem[]   = by_odds.map(d => ({ label: d.bucket, value: d.bets }))
  const monthItems: BarItem[]  = by_month.map(d => ({ label: d.month.slice(5), value: d.pl, isPos: d.pl >= 0 }))
  const fullHours: BarItem[]   = Array.from({ length: 24 }, (_, h) => {
    const found = by_hour.find(d => d.hour === h)
    return { label: String(h), value: found ? found.pl : 0, isPos: (found?.pl ?? 0) >= 0 }
  })

  return (
    <div className="p-5 space-y-4 max-w-7xl">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">BackTest</h1>
        <p className="text-xs text-zinc-500 mt-0.5">{filename} · {total_matches} partidos · {kpis.total_bets} apuestas</p>
      </div>

      {/* KPI Grid row 1 */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
        <KpiCard label="Total Partidos" value={total_matches.toString()} />
        <KpiCard label="Total Apuestas" value={kpis.total_bets.toString()} />
        <KpiCard label="Win Rate" value={`${kpis.win_rate}%`} />
        <KpiCard label="ROI" value={`${kpis.roi.toFixed(1)}%`} />
        <KpiCard label="Flat P/L" value={`${kpis.total_pl >= 0 ? "+" : ""}${kpis.total_pl.toFixed(2)} €`} />
        <KpiCard label="Max Drawdown" value={`${kpis.max_dd.toFixed(2)} €`} />
      </div>

      {/* KPI Grid row 2 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <KpiCard label="Mejor Racha" value={`${kpis.best_streak} W`} />
        <KpiCard label="Peor Racha" value={`${kpis.worst_streak} L`} />
        <KpiCard label="Sharpe Ratio" value={kpis.sharpe.toFixed(2)} />
        <KpiCard label="Profit Factor" value={kpis.profit_factor.toFixed(2)} />
      </div>

      {/* Últimos 7 días */}
      <Section title="📊 Últimos 7 Días">
        <Last7Days data={by_date} />
      </Section>

      {/* P/L Acumulado */}
      <Section title="📈 P/L Acumulado (€)">
        <PLChart data={cumul} />
      </Section>

      {/* Estrategias */}
      <Section title="🎯 Rendimiento por Estrategia">
        <StrategyTable data={by_strategy} />
      </Section>

      {/* País + Liga */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Section title="🌍 Distribución por País"><GroupTable data={by_country} /></Section>
        <Section title="🏆 Distribución por Liga"><GroupTable data={by_league} /></Section>
      </div>

      {/* Minuto + Odds */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Section title="⏱ Distribución por Minuto de Trigger">
          <BarChart items={minuteItems} showEveryN={2} />
        </Section>
        <Section title="💹 Distribución de Odds">
          <BarChart items={oddsItems} />
        </Section>
      </div>

      {/* Día semana + Hora */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Section title="📅 Día de la Semana">
          <WeekdayTable data={by_weekday} />
        </Section>
        <Section title="🕐 P/L por Hora del Día (€)">
          <BarChart items={fullHours} colorMode="pl" showEveryN={6} />
        </Section>
      </div>

      {/* P/L Mensual */}
      <Section title="📆 P/L Mensual (€)">
        <BarChart items={monthItems} colorMode="pl" />
      </Section>

      {/* P/L acumulado por estrategia */}
      <Section title="📈 P/L Acumulado por Estrategia">
        <MultiLineChart data={strat_cumul ?? {}} />
      </Section>

      {/* Calibración WR real vs implícita */}
      <Section title="🎯 Calibración: WR Real vs WR Implícita por Odds">
        <OddsCalibrationChart data={odds_calibration ?? []} />
      </Section>

      {/* Max drawdown + Heatmap */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Section title="📉 Max Drawdown por Estrategia">
          <DrawdownChart data={strat_drawdown ?? []} />
        </Section>
        <Section title="🗺 ROI por Estrategia × Liga (Top 10)">
          <HeatmapChart data={heatmap ?? { leagues: [], rows: [] }} />
        </Section>
      </div>

    </div>
  )
}
