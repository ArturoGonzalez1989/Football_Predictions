import { useState, useEffect, useCallback } from "react"
import { api, type Match, type MatchDetail, type MomentumData, type MatchFull, type AllCaptures } from "../lib/api"
import { formatTimeTo } from "../lib/utils"
import { StatusBadge } from "./StatusBadge"
import { CaptureIndicator } from "./CaptureIndicator"
import { StatsBar } from "./StatsBar"
import { MomentumChart, XgChart } from "./MomentumChart"
import { OddsTable, OverUnderTable } from "./OddsChart"
import { CaptureTable } from "./CaptureTable"
import { GapAnalysis } from "./GapAnalysis"
import { SiegeMeter } from "./SiegeMeter"
import { PriceVsReality } from "./PriceVsReality"
import { MomentumSwings } from "./MomentumSwings"

interface MatchCardProps {
  match: Match
  onDelete?: () => void
}

export function MatchCard({ match, onDelete }: MatchCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [detail, setDetail] = useState<MatchDetail | null>(null)
  const [momentum, setMomentum] = useState<MomentumData | null>(null)
  const [fullData, setFullData] = useState<MatchFull | null>(null)
  const [allCaptures, setAllCaptures] = useState<AllCaptures | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const loadDetail = useCallback(async () => {
    if (!expanded) return
    setLoadingDetail(true)
    try {
      const [d, m, f, ac] = await Promise.all([
        api.getMatchDetail(match.match_id),
        api.getMatchMomentum(match.match_id),
        api.getMatchFull(match.match_id),
        api.getAllCaptures(match.match_id),
      ])
      setDetail(d)
      setMomentum(m)
      setFullData(f)
      setAllCaptures(ac)
    } catch {
      /* ignore */
    } finally {
      setLoadingDetail(false)
    }
  }, [expanded, match.match_id])

  useEffect(() => {
    loadDetail()
    if (expanded && match.status === "live") {
      const interval = setInterval(loadDetail, 15000)
      return () => clearInterval(interval)
    }
  }, [loadDetail, expanded, match.status])

  const [home, away] = match.name.split(" - ")

  // Parse last capture stats from detail
  const lastCapture = detail?.captures?.at(-1)

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 overflow-hidden transition-all hover:border-zinc-700">
      {/* Compact header - always visible */}
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex-1 min-w-0 text-left p-4 flex items-center justify-between gap-3 cursor-pointer hover:bg-zinc-800/30 transition-colors"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2.5 mb-1">
              <StatusBadge status={match.status} minute={match.match_minute} />
              <h3 className="text-sm font-semibold text-zinc-100 truncate">
                {home ?? match.name}
                <span className="text-zinc-500 mx-1.5">vs</span>
                {away}
              </h3>
            </div>
            <div className="flex items-center gap-3">
              <CaptureIndicator
                captureCount={match.capture_count}
                lastCaptureAgo={match.last_capture_ago_seconds}
              />
              {match.status === "upcoming" && match.start_time && (
                <span className="text-xs text-zinc-500">
                  Starts {formatTimeTo(match.start_time)}
                </span>
              )}
              {detail && (
                <span className="text-xs text-zinc-600">
                  Quality: {detail.quality}%
                </span>
              )}
            </div>
          </div>
          <svg
            className={`w-4 h-4 text-zinc-500 transition-transform shrink-0 ${expanded ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        <div className="flex items-center gap-1.5 pr-3">
          {confirmDelete ? (
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-red-400">Delete?</span>
              <button
                type="button"
                onClick={async () => {
                  setDeleting(true)
                  try {
                    await api.deleteMatch(match.match_id)
                    onDelete?.()
                  } catch { /* ignore */ }
                  setDeleting(false)
                  setConfirmDelete(false)
                }}
                disabled={deleting}
                className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors cursor-pointer disabled:opacity-50"
              >
                {deleting ? "..." : "Yes"}
              </button>
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700/50 text-zinc-400 hover:bg-zinc-700 transition-colors cursor-pointer"
              >
                No
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="p-1 rounded hover:bg-red-500/10 text-zinc-600 hover:text-red-400 transition-colors cursor-pointer"
              title="Stop tracking this match"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-zinc-800 p-4 space-y-5">
          {loadingDetail && !detail && (
            <div className="text-center text-zinc-500 text-sm py-6">Loading...</div>
          )}

          {/* Quick stats bars */}
          {lastCapture && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-medium text-zinc-400 uppercase tracking-wider px-1">
                Current Stats
              </h4>
              <div className="space-y-1">
                <StatsBar label="xG" homeValue={lastCapture.xg_local || "—"} awayValue={lastCapture.xg_visitante || "—"} />
                <StatsBar label="Poss %" homeValue={lastCapture.posesion_local || "—"} awayValue={lastCapture.posesion_visitante || "—"} />
                <StatsBar label="Corners" homeValue={lastCapture.corners_local || "—"} awayValue={lastCapture.corners_visitante || "—"} />
                <StatsBar label="Shots" homeValue={lastCapture.tiros_local || "—"} awayValue={lastCapture.tiros_visitante || "—"} />
              </div>
            </div>
          )}

          {/* ── Trading Intelligence ── */}
          {allCaptures && allCaptures.captures.length >= 5 && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 px-1">
                <div className="h-px flex-1 bg-gradient-to-r from-cyan-500/40 to-transparent" />
                <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest">
                  Trading Intelligence
                </span>
                <div className="h-px flex-1 bg-gradient-to-l from-fuchsia-500/40 to-transparent" />
              </div>

              <SiegeMeter
                captures={allCaptures.captures}
                homeName={home ?? "Home"}
                awayName={away ?? "Away"}
              />

              {fullData?.odds_timeline && fullData.odds_timeline.length > 0 && (
                <PriceVsReality
                  captures={allCaptures.captures}
                  oddsTimeline={fullData.odds_timeline}
                  homeName={home ?? "Home"}
                />
              )}

              <MomentumSwings
                captures={allCaptures.captures}
                homeName={home ?? "Home"}
                awayName={away ?? "Away"}
              />
            </div>
          )}

          {/* ── Classic Analytics ── */}

          {/* Momentum Chart */}
          <MomentumChart data={momentum} loading={loadingDetail && !momentum} />

          {/* xG Chart */}
          <XgChart data={momentum} />

          {/* Odds Table */}
          {fullData && fullData.odds_timeline && (
            <OddsTable
              data={fullData.odds_timeline}
              loading={loadingDetail && !fullData}
            />
          )}

          {/* Over/Under Table */}
          {fullData && fullData.odds_timeline && (
            <OverUnderTable
              data={fullData.odds_timeline}
              loading={loadingDetail && !fullData}
            />
          )}

          {/* Gap Analysis */}
          {detail && (
            <GapAnalysis
              gaps={detail.gaps}
              totalGaps={detail.total_gaps}
              matchMinute={match.match_minute}
            />
          )}

          {/* Capture Table */}
          {detail && <CaptureTable captures={detail.captures} />}

          {/* Link to Betfair */}
          <div className="flex justify-end pt-1">
            <a
              href={match.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
            >
              Open in Betfair &rarr;
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
