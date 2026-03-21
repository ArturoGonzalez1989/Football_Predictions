import { useState, useEffect, useCallback } from "react"

interface SuiteResult {
  id: string
  label: string
  passed: number
  failed: number
  ok: boolean
  elapsed: number
  output: string
}

interface TestRun {
  timestamp: string
  total_passed: number
  total_failed: number
  all_ok: boolean
  suites: SuiteResult[]
  partial?: boolean
}

interface TestCasesData {
  suites: { id: string; label: string; file: string }[]
  last_run: TestRun | null
  history_count: number
  is_running: boolean
}

export function TestCasesView() {
  const [data, setData] = useState<TestCasesData | null>(null)
  const [running, setRunning] = useState(false)
  const [expandedSuite, setExpandedSuite] = useState<string | null>(null)
  const [history, setHistory] = useState<TestRun[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch("/api/test-cases")
      if (res.ok) {
        const d = await res.json()
        setData(d)
        if (d.is_running) setRunning(true)
        else setRunning(false)
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [fetchData])

  const runAll = async () => {
    setRunning(true)
    setError(null)
    try {
      // Start background run
      const res = await fetch("/api/test-cases/run-bg", { method: "POST" })
      if (!res.ok) {
        const d = await res.json()
        setError(d.error || "Failed to start")
        setRunning(false)
      }
      // Poll until done
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error")
      setRunning(false)
    }
  }

  const runSingle = async (suiteId: string) => {
    setRunning(true)
    setError(null)
    try {
      const res = await fetch(`/api/test-cases/run?suite_id=${suiteId}`, { method: "POST" })
      const d = await res.json()
      if (d.ok) {
        fetchData()
      } else {
        setError(d.error || "Failed")
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error")
    } finally {
      setRunning(false)
    }
  }

  const loadHistory = async () => {
    try {
      const res = await fetch("/api/test-cases/history?limit=10")
      if (res.ok) {
        const d = await res.json()
        setHistory(d.history || [])
        setShowHistory(true)
      }
    } catch { /* ignore */ }
  }

  const lastRun = data?.last_run
  const suiteResults = lastRun?.suites || []

  // Build a map of suite results by id for easy lookup
  const resultMap = new Map<string, SuiteResult>()
  for (const s of suiteResults) resultMap.set(s.id, s)

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffH = Math.floor(diffMs / 3600000)
    const diffM = Math.floor(diffMs / 60000)

    if (diffM < 1) return "just now"
    if (diffM < 60) return `${diffM}m ago`
    if (diffH < 24) return `${diffH}h ago`
    return d.toLocaleDateString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-100">Test Cases</h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            {lastRun
              ? `Last run: ${formatDate(lastRun.timestamp)} — ${lastRun.total_passed} passed, ${lastRun.total_failed} failed`
              : "No test runs yet"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {data && data.history_count > 0 && (
            <button
              type="button"
              onClick={loadHistory}
              className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 border border-zinc-700 hover:border-zinc-600 rounded-lg transition-colors cursor-pointer"
            >
              History ({data.history_count})
            </button>
          )}
          <button
            type="button"
            onClick={runAll}
            disabled={running}
            className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
              running
                ? "bg-zinc-700 text-zinc-400 cursor-not-allowed"
                : "bg-emerald-600 hover:bg-emerald-500 text-white"
            }`}
          >
            {running ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Running...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Run All
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Summary bar */}
      {lastRun && (
        <div className={`rounded-xl border px-5 py-3 flex items-center gap-4 ${
          lastRun.all_ok
            ? "bg-emerald-500/5 border-emerald-500/20"
            : "bg-red-500/5 border-red-500/20"
        }`}>
          <div className={`text-2xl font-bold ${lastRun.all_ok ? "text-emerald-400" : "text-red-400"}`}>
            {lastRun.all_ok ? "PASS" : "FAIL"}
          </div>
          <div className="flex-1 flex items-center gap-6 text-sm">
            <span className="text-emerald-400 font-mono">{lastRun.total_passed} passed</span>
            {lastRun.total_failed > 0 && (
              <span className="text-red-400 font-mono">{lastRun.total_failed} failed</span>
            )}
            <span className="text-zinc-500">{suiteResults.length} suites</span>
          </div>
          <span className="text-[10px] text-zinc-600 font-mono">
            {lastRun.timestamp ? new Date(lastRun.timestamp).toLocaleString("es-ES") : ""}
          </span>
        </div>
      )}

      {/* Suite cards */}
      <div className="space-y-2">
        {(data?.suites || []).map(suite => {
          const result = resultMap.get(suite.id)
          const isExpanded = expandedSuite === suite.id
          return (
            <div key={suite.id} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
              <div
                className="flex items-center gap-3 px-5 py-3 cursor-pointer hover:bg-zinc-800/50 transition-colors"
                onClick={() => setExpandedSuite(isExpanded ? null : suite.id)}
              >
                {/* Status indicator */}
                {result ? (
                  <div className={`w-2 h-2 rounded-full shrink-0 ${result.ok ? "bg-emerald-400" : "bg-red-400"}`} />
                ) : (
                  <div className="w-2 h-2 rounded-full shrink-0 bg-zinc-600" />
                )}

                {/* Suite name */}
                <span className="flex-1 text-sm font-medium text-zinc-200">{suite.label}</span>

                {/* Stats */}
                {result && (
                  <div className="flex items-center gap-3 text-xs font-mono">
                    <span className="text-emerald-400">{result.passed}P</span>
                    {result.failed > 0 && <span className="text-red-400">{result.failed}F</span>}
                    <span className="text-zinc-600">{result.elapsed}s</span>
                  </div>
                )}

                {/* Run single button */}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); runSingle(suite.id) }}
                  disabled={running}
                  className="shrink-0 p-1 text-zinc-600 hover:text-zinc-300 transition-colors cursor-pointer disabled:opacity-30"
                  title={`Run ${suite.label}`}
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  </svg>
                </button>

                {/* Expand arrow */}
                <svg className={`w-4 h-4 text-zinc-600 transition-transform ${isExpanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </div>

              {/* Expanded output */}
              {isExpanded && result && (
                <div className="border-t border-zinc-800 px-5 py-3">
                  <pre className="text-[11px] text-zinc-400 font-mono whitespace-pre-wrap max-h-80 overflow-auto leading-relaxed">
                    {result.output || "No output captured"}
                  </pre>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* History modal */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowHistory(false)}>
          <div className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-xl max-h-[70vh] overflow-auto p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-zinc-100">Run History</h3>
              <button type="button" onClick={() => setShowHistory(false)} className="text-zinc-500 hover:text-zinc-300 cursor-pointer">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="space-y-2">
              {history.map((run, i) => (
                <div key={i} className={`flex items-center gap-3 px-4 py-2.5 rounded-lg border ${
                  run.all_ok ? "border-emerald-500/10 bg-emerald-500/5" : "border-red-500/10 bg-red-500/5"
                }`}>
                  <div className={`w-2 h-2 rounded-full ${run.all_ok ? "bg-emerald-400" : "bg-red-400"}`} />
                  <span className="flex-1 text-xs text-zinc-300">
                    {new Date(run.timestamp).toLocaleString("es-ES")}
                  </span>
                  <span className="text-xs font-mono text-emerald-400">{run.total_passed}P</span>
                  {run.total_failed > 0 && (
                    <span className="text-xs font-mono text-red-400">{run.total_failed}F</span>
                  )}
                  <span className="text-xs text-zinc-500">{run.suites.length} suites</span>
                </div>
              ))}
              {history.length === 0 && (
                <p className="text-xs text-zinc-500 text-center py-4">No history yet</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
