import { useState, useEffect, useCallback } from "react"

interface Alert {
  level: "critical" | "warning"
  category: string
  message: string
  detail?: string
}

interface AlertsResponse {
  timestamp: string
  total: number
  critical: number
  warning: number
  alerts: Alert[]
}

export default function AlertsView() {
  const [data, setData] = useState<AlertsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAlerts = useCallback(async () => {
    try {
      const r = await fetch("/api/alerts")
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const json = await r.json()
      setData(json)
      setError(null)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAlerts()
    const interval = setInterval(fetchAlerts, 30000)
    return () => clearInterval(interval)
  }, [fetchAlerts])

  if (loading) {
    return <div className="p-6 text-zinc-400">Cargando alertas...</div>
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 text-red-400">
          Error conectando con backend: {error}
        </div>
      </div>
    )
  }

  const indicatorClass =
    (data?.critical ?? 0) > 0
      ? "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)] animate-pulse"
      : (data?.warning ?? 0) > 0
        ? "bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]"
        : "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]"

  const statusText =
    (data?.critical ?? 0) > 0
      ? `${data!.critical} alerta(s) crítica(s), ${data!.warning} aviso(s)`
      : (data?.warning ?? 0) > 0
        ? `${data!.warning} aviso(s)`
        : "Sistema OK — sin alertas"

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-lg font-semibold text-zinc-100">Sistema de Alertas</h2>

      {/* Status bar */}
      <div className="flex items-center gap-3 bg-zinc-800/50 rounded-lg px-4 py-3">
        <div className={`w-3 h-3 rounded-full ${indicatorClass}`} />
        <span className="text-sm text-zinc-300">{statusText}</span>
        <span className="ml-auto text-xs text-zinc-500">
          {new Date().toLocaleTimeString()}
        </span>
      </div>

      {/* Alert list */}
      {data?.alerts.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-3 text-green-500">✓</div>
          <div className="text-green-400">Todo funcionando correctamente</div>
        </div>
      ) : (
        <div className="space-y-2">
          {data?.alerts.map((a, i) => (
            <div
              key={i}
              className={`rounded-lg px-4 py-3 border-l-4 ${
                a.level === "critical"
                  ? "bg-red-950/30 border-red-500"
                  : "bg-amber-950/30 border-amber-500"
              }`}
            >
              <div className="flex items-center gap-2 flex-wrap">
                <span
                  className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded ${
                    a.level === "critical"
                      ? "bg-red-500/20 text-red-400"
                      : "bg-amber-500/20 text-amber-400"
                  }`}
                >
                  {a.level}
                </span>
                <span className="text-[10px] bg-zinc-700/50 text-zinc-400 px-2 py-0.5 rounded">
                  {a.category}
                </span>
                <span className="text-sm text-zinc-200">{a.message}</span>
              </div>
              {a.detail && (
                <div className="text-xs text-zinc-500 mt-1">{a.detail}</div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="text-center text-xs text-zinc-600">
        Auto-refresh cada 30s
      </div>
    </div>
  )
}
