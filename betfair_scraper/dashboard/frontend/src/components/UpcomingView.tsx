import { type Match } from "../lib/api"
import { MatchCard } from "./MatchCard"

interface UpcomingViewProps {
  matches: Match[]
}

export function UpcomingView({ matches }: UpcomingViewProps) {
  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-5">
        <h1 className="text-lg font-semibold text-zinc-100">Próximos Partidos</h1>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-6">
        <MetricCard label="Total" value={matches.length} color="blue" />
        <MetricCard
          label="En 1 hora"
          value={matches.filter((m) => {
            if (!m.start_time) return false
            const minutesUntil = (new Date(m.start_time).getTime() - Date.now()) / 60000
            return minutesUntil <= 60 && minutesUntil >= 0
          }).length}
          color="yellow"
        />
        <MetricCard
          label="Hoy"
          value={matches.filter((m) => {
            if (!m.start_time) return false
            const matchDate = new Date(m.start_time)
            const today = new Date()
            return (
              matchDate.getDate() === today.getDate() &&
              matchDate.getMonth() === today.getMonth() &&
              matchDate.getFullYear() === today.getFullYear()
            )
          }).length}
          color="zinc"
        />
      </div>

      {matches.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-12 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center mb-3">
            <svg className="w-6 h-6 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-sm text-zinc-500">No hay partidos próximos</p>
          <p className="text-xs text-zinc-700 mt-1">Los partidos aparecerán aquí cuando falten menos de 2 horas para su inicio</p>
        </div>
      ) : (
        <div className="space-y-3">
          {matches
            .sort((a, b) => {
              const aTime = a.start_time ? new Date(a.start_time).getTime() : 0
              const bTime = b.start_time ? new Date(b.start_time).getTime() : 0
              return aTime - bTime
            })
            .map((match) => (
              <MatchCard key={match.match_id} match={match} />
            ))}
        </div>
      )}
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: number
  color?: "zinc" | "green" | "blue" | "red" | "yellow"
}

function MetricCard({ label, value, color = "zinc" }: MetricCardProps) {
  const colorClasses = {
    zinc: "bg-zinc-800/60 border-zinc-700 text-zinc-300",
    green: "bg-emerald-500/10 border-emerald-500/20 text-emerald-400",
    blue: "bg-blue-500/10 border-blue-500/20 text-blue-400",
    red: "bg-red-500/10 border-red-500/20 text-red-400",
    yellow: "bg-yellow-500/10 border-yellow-500/20 text-yellow-400",
  }

  return (
    <div className={`rounded-lg border p-3 ${colorClasses[color]}`}>
      <div className="text-[10px] uppercase tracking-wider opacity-70 mb-1">{label}</div>
      <div className="text-2xl font-bold tabular-nums">{value}</div>
    </div>
  )
}
