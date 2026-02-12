import type { Capture } from "../lib/api"

interface CaptureTableProps {
  captures: Capture[]
}

// Definición de todas las columnas posibles con sus labels
const ALL_COLUMNS: Array<{ key: keyof Capture; label: string; color?: string }> = [
  { key: "minuto", label: "Min", color: "text-zinc-300" },
  { key: "goles_local", label: "Goles L", color: "text-white font-semibold" },
  { key: "goles_visitante", label: "Goles V", color: "text-white font-semibold" },
  { key: "xg_local", label: "xG L", color: "text-blue-400" },
  { key: "xg_visitante", label: "xG V", color: "text-blue-400" },
  { key: "posesion_local", label: "Pos% L", color: "text-purple-400" },
  { key: "posesion_visitante", label: "Pos% V", color: "text-purple-400" },
  { key: "corners_local", label: "Corners L", color: "text-yellow-400" },
  { key: "corners_visitante", label: "Corners V", color: "text-yellow-400" },
  { key: "tiros_local", label: "Shots L", color: "text-zinc-300" },
  { key: "tiros_visitante", label: "Shots V", color: "text-zinc-300" },
  { key: "tiros_puerta_local", label: "On Target L", color: "text-green-400" },
  { key: "tiros_puerta_visitante", label: "On Target V", color: "text-green-400" },
  { key: "shots_off_target_local", label: "Off Target L", color: "text-zinc-400" },
  { key: "shots_off_target_visitante", label: "Off Target V", color: "text-zinc-400" },
  { key: "blocked_shots_local", label: "Blocked L", color: "text-red-400" },
  { key: "blocked_shots_visitante", label: "Blocked V", color: "text-red-400" },
  { key: "saves_local", label: "Saves L", color: "text-cyan-400" },
  { key: "saves_visitante", label: "Saves V", color: "text-cyan-400" },
  { key: "dangerous_attacks_local", label: "Dang Att L", color: "text-orange-400" },
  { key: "dangerous_attacks_visitante", label: "Dang Att V", color: "text-orange-400" },
  { key: "fouls_conceded_local", label: "Fouls L", color: "text-amber-400" },
  { key: "fouls_conceded_visitante", label: "Fouls V", color: "text-amber-400" },
  { key: "goal_kicks_local", label: "GK L", color: "text-zinc-400" },
  { key: "goal_kicks_visitante", label: "GK V", color: "text-zinc-400" },
  { key: "throw_ins_local", label: "Throw L", color: "text-zinc-400" },
  { key: "throw_ins_visitante", label: "Throw V", color: "text-zinc-400" },
  { key: "tarjetas_amarillas_local", label: "Yellow L", color: "text-yellow-300" },
  { key: "tarjetas_amarillas_visitante", label: "Yellow V", color: "text-yellow-300" },
  { key: "tarjetas_rojas_local", label: "Red L", color: "text-red-500" },
  { key: "tarjetas_rojas_visitante", label: "Red V", color: "text-red-500" },
  { key: "total_passes_local", label: "Passes L", color: "text-zinc-400" },
  { key: "total_passes_visitante", label: "Passes V", color: "text-zinc-400" },
  { key: "big_chances_local", label: "Big Ch L", color: "text-green-500" },
  { key: "big_chances_visitante", label: "Big Ch V", color: "text-green-500" },
  { key: "attacks_local", label: "Attacks L", color: "text-orange-300" },
  { key: "attacks_visitante", label: "Attacks V", color: "text-orange-300" },
  { key: "tackles_local", label: "Tackles L", color: "text-zinc-400" },
  { key: "tackles_visitante", label: "Tackles V", color: "text-zinc-400" },
  { key: "momentum_local", label: "Mom L", color: "text-pink-400" },
  { key: "momentum_visitante", label: "Mom V", color: "text-pink-400" },
  { key: "opta_points_local", label: "Opta L", color: "text-blue-300" },
  { key: "opta_points_visitante", label: "Opta V", color: "text-blue-300" },
  { key: "touches_box_local", label: "Touch Box L", color: "text-zinc-400" },
  { key: "touches_box_visitante", label: "Touch Box V", color: "text-zinc-400" },
  { key: "shooting_accuracy_local", label: "Shot Acc% L", color: "text-green-300" },
  { key: "shooting_accuracy_visitante", label: "Shot Acc% V", color: "text-green-300" },
  { key: "free_kicks_local", label: "Free Kicks L", color: "text-zinc-400" },
  { key: "free_kicks_visitante", label: "Free Kicks V", color: "text-zinc-400" },
  { key: "offsides_local", label: "Offsides L", color: "text-yellow-400" },
  { key: "offsides_visitante", label: "Offsides V", color: "text-yellow-400" },
  { key: "substitutions_local", label: "Subs L", color: "text-blue-300" },
  { key: "substitutions_visitante", label: "Subs V", color: "text-blue-300" },
  { key: "injuries_local", label: "Injuries L", color: "text-red-300" },
  { key: "injuries_visitante", label: "Injuries V", color: "text-red-300" },
  { key: "time_in_dangerous_attack_pct_local", label: "Dang Att% L", color: "text-orange-300" },
  { key: "time_in_dangerous_attack_pct_visitante", label: "Dang Att% V", color: "text-orange-300" },
]

export function CaptureTable({ captures }: CaptureTableProps) {
  if (!captures.length) {
    return (
      <p className="text-zinc-500 text-xs text-center py-4">
        No captures yet
      </p>
    )
  }

  // Filtrar columnas que tienen al menos un valor no vacío en las 10 capturas
  const visibleColumns = ALL_COLUMNS.filter(col => {
    if (col.key === "minuto" || col.key === "timestamp") return true // Siempre mostrar minuto
    return captures.some(c => {
      const val = c[col.key]
      return val && val.trim() !== "" && val !== "?" && val !== "N/A"
    })
  })

  return (
    <div className="space-y-1">
      <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
        Latest Captures
      </h4>
      <div className="overflow-x-auto -mx-4 px-4">
        <table className="w-full text-xs whitespace-nowrap">
          <thead>
            <tr className="text-zinc-500 text-[10px] uppercase tracking-wider">
              {visibleColumns.map((col, i) => (
                <th
                  key={col.key}
                  className={`text-left py-1.5 px-2 font-medium ${
                    i === 0 ? "sticky left-0 z-10 bg-zinc-900 border-r border-zinc-800" : ""
                  }`}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {captures.map((c, i) => (
              <tr
                key={i}
                className="border-t border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
              >
                {visibleColumns.map((col, colIdx) => (
                  <td
                    key={col.key}
                    className={`py-1.5 px-2 font-mono ${col.color || "text-zinc-300"} ${
                      colIdx === 0 ? "sticky left-0 z-10 bg-zinc-900 border-r border-zinc-800" : ""
                    }`}
                  >
                    {c[col.key] || "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
