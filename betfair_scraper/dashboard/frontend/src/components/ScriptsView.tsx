import { useState } from "react"

interface Script {
  id: string
  label: string
  description: string
  command: string
}

const SCRIPTS: Script[] = [
  {
    id: "crossref",
    label: "Crossref Telegram ↔ BT",
    description: "Compara las señales de Telegram con las apuestas del backtest y genera el informe HTML.",
    command: "cd C:\\Users\\agonz\\OneDrive\\Documents\\Proyectos\\Furbo && python auxiliar/crossref_telegram_bt.py",
  },
  {
    id: "bt-export",
    label: "BT Export (CSV + XLSX)",
    description: "Regenera el CSV y Excel del backtest a partir de la config actual.",
    command: "cd C:\\Users\\agonz\\OneDrive\\Documents\\Proyectos\\Furbo && python scripts/bt_optimizer.py --phase export",
  },
]

export function ScriptsView() {
  const [copied, setCopied] = useState<string | null>(null)

  const copy = (id: string, command: string) => {
    navigator.clipboard.writeText(command)
    setCopied(id)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-zinc-100">Scripts</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          Copia el comando y ejecútalo en una terminal PowerShell.
        </p>
      </div>

      <div className="space-y-3">
        {SCRIPTS.map(script => (
          <div key={script.id} className="bg-zinc-900 border border-zinc-800 rounded-xl px-5 py-4 space-y-3">
            <div>
              <div className="text-sm font-medium text-zinc-100">{script.label}</div>
              <div className="text-xs text-zinc-500 mt-0.5">{script.description}</div>
            </div>

            <div className="flex items-center gap-2">
              <code className="flex-1 text-xs text-zinc-300 bg-zinc-950 border border-zinc-700 rounded-lg px-3 py-2 font-mono truncate">
                {script.command}
              </code>
              <button
                type="button"
                onClick={() => copy(script.id, script.command)}
                className="shrink-0 flex items-center gap-1.5 px-3 py-2 bg-zinc-700 hover:bg-zinc-600 text-zinc-200 rounded-lg text-xs font-medium transition-colors cursor-pointer"
              >
                {copied === script.id ? (
                  <>
                    <svg className="w-3.5 h-3.5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    <span className="text-green-400">Copiado</span>
                  </>
                ) : (
                  <>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    Copiar
                  </>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
