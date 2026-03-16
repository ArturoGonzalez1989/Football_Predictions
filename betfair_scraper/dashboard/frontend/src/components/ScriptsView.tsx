import { useState, useCallback } from "react"

interface Script {
  id: string
  label: string
  description: string
  endpoint: string
}

const SCRIPTS: Script[] = [
  {
    id: "crossref",
    label: "Crossref Telegram ↔ BT",
    description: "Compara las señales de Telegram con las apuestas del backtest y genera el informe HTML.",
    endpoint: "/api/scripts/crossref-telegram",
  },
  {
    id: "bt-export",
    label: "BT Export (CSV + XLSX)",
    description: "Regenera el CSV y Excel del backtest a partir de la config actual (bt_optimizer --phase export).",
    endpoint: "/api/scripts/bt-export",
  },
]

type ScriptStatus = "idle" | "launched" | "error"

export function ScriptsView() {
  const [statuses, setStatuses] = useState<Record<string, ScriptStatus>>(
    Object.fromEntries(SCRIPTS.map(s => [s.id, "idle"]))
  )

  const run = useCallback(async (script: Script) => {
    setStatuses(prev => ({ ...prev, [script.id]: "idle" }))
    try {
      const res = await fetch(script.endpoint, { method: "POST" })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.ok === false) {
        console.error("Script error:", data.error ?? res.status)
        setStatuses(prev => ({ ...prev, [script.id]: "error" }))
      } else {
        setStatuses(prev => ({ ...prev, [script.id]: "launched" }))
      }
    } catch (e) {
      console.error("Script fetch error:", e)
      setStatuses(prev => ({ ...prev, [script.id]: "error" }))
    }
    setTimeout(() => setStatuses(prev => ({ ...prev, [script.id]: "idle" })), 4000)
  }, [])

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-100">Scripts</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          Lanza scripts auxiliares en una ventana de terminal. Al terminar, pulsa cualquier tecla para cerrarla.
        </p>
      </div>

      <div className="space-y-3">
        {SCRIPTS.map(script => {
          const status = statuses[script.id]
          return (
            <div key={script.id} className="flex items-center gap-4 bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-4">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-zinc-100">{script.label}</div>
                <div className="text-xs text-zinc-500 mt-0.5">{script.description}</div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                {status === "launched" && (
                  <span className="text-xs text-green-400 font-medium">✓ Lanzado</span>
                )}
                {status === "error" && (
                  <span className="text-xs text-red-400 font-medium">Error</span>
                )}
                <button
                  type="button"
                  onClick={() => run(script)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-medium transition-colors cursor-pointer"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  Ejecutar
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
