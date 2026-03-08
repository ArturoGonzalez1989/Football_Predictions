"""
api/simulate.py — Signal Simulation endpoint.

Replays a historical match CSV row by row through detect_betting_signals,
producing a minute-by-minute timeline of signal activations, deactivations
and goals. Lets the user verify that live logic matches backtest.
"""
import builtins
import re
from pathlib import Path
from unittest.mock import patch

from fastapi import APIRouter, HTTPException
from api.config import load_config
from api.analytics import _apply_realistic_adjustments
import utils.csv_reader as csv_reader
from utils.csv_reader import _to_float, _read_csv_rows, _get_all_finished_matches

router = APIRouter(prefix="/api/simulate", tags=["simulate"])

# In-memory cache so re-running the same match is instant
_sim_cache: dict = {}

STRATEGY_LABELS: dict[str, str] = {
    "back_draw_00":      "Back Empate 0-0",
    "xg_underperformance": "xG Underperformance",
    "odds_drift":        "Odds Drift Contrarian",
    "goal_clustering":   "Goal Clustering",
    "pressure_cooker":   "Pressure Cooker",
    "momentum_xg_v1":   "Momentum xG v1",
    "momentum_xg_v2":   "Momentum xG v2",
    "tarde_asia":        "Tarde Asia",
}

# Min-duration thresholds in minutes per strategy family (1 capture ≈ 0.5 min)
_MIN_DUR_DEFAULT_MINS: dict[str, float] = {
    "draw": 1.0, "xg": 1.5, "drift": 1.0,
    "clustering": 2.0, "pressure": 2.0, "momentum": 0.5,
}

_COMMISSION = 0.05


def _get_lay_col(recommendation: str) -> str | None:
    """Map recommendation to its lay CSV column (same logic as bets.py)."""
    rec = recommendation.upper()
    if "DRAW" in rec or "EMPATE" in rec:
        return "lay_draw"
    if "HOME" in rec or "LOCAL" in rec:
        return "lay_home"
    if "AWAY" in rec or "VISITANTE" in rec:
        return "lay_away"
    return None  # OVER/UNDER bets have no lay column → no auto-cashout


def _calc_bet_outcome(recommendation: str, final_score: str,
                      odds: float | None, stake: float) -> dict | None:
    """Calculate win/loss and net P/L for a matured signal."""
    if not recommendation or not final_score or not odds:
        return None
    try:
        gl, gv = (int(x) for x in final_score.split("-"))
        total = gl + gv
        rec = recommendation.upper()
        won: bool | None = None
        if "OVER" in rec:
            m = re.search(r"(\d+\.?\d*)", rec)
            if m:
                won = total > float(m.group(1))
        elif "UNDER" in rec:
            m = re.search(r"(\d+\.?\d*)", rec)
            if m:
                won = total < float(m.group(1))
        elif "DRAW" in rec or "EMPATE" in rec:
            won = gl == gv
        elif "AWAY" in rec or "VISITANTE" in rec:
            won = gv > gl
        elif "HOME" in rec or "LOCAL" in rec:
            won = gl > gv
        if won is None:
            return None
        pl = round((odds - 1) * stake * (1 - _COMMISSION), 2) if won else round(-stake, 2)
        return {"won": won, "pl": pl}
    except Exception:
        return None


def _family(strategy: str) -> str:
    if "draw"      in strategy: return "draw"
    if "momentum"  in strategy: return "momentum"
    if "xg"        in strategy or "underperformance" in strategy: return "xg"
    if "drift"     in strategy: return "drift"
    if "clustering" in strategy: return "clustering"
    if "pressure"  in strategy: return "pressure"
    return "draw"


def _build_versions(config: dict) -> dict:
    """Build versions dict from config — mirrors analytics.py exactly."""
    s   = config.get("strategies", {})
    md  = config.get("min_duration", {})
    draw_s  = s.get("draw", {})
    xg_s    = s.get("xg", {})
    drift_s = s.get("drift", {})
    cl_s    = s.get("clustering", {})
    pr_s    = s.get("pressure", {})
    mom_s   = s.get("momentum_xg", {})
    ta_s    = s.get("tarde_asia", {})
    return {
        "draw":                  draw_s.get("version", "v1") if draw_s.get("enabled", True) else "off",
        "draw_xg_max":           str(draw_s.get("xgMax", 0.6)),
        "draw_poss_max":         str(draw_s.get("possMax", 25)),
        "draw_shots_max":        str(draw_s.get("shotsMax", 20)),
        "draw_minute_min":       str(draw_s.get("minuteMin", 30)),
        "draw_minute_max":       str(draw_s.get("minuteMax", 90)),
        "draw_xg_dom_asym":      str(draw_s.get("xgDomAsym", False)).lower(),
        "xg":                    xg_s.get("version", "base") if xg_s.get("enabled", True) else "off",
        "xg_sot_min":            str(xg_s.get("sotMin", 0)),
        "xg_xg_excess_min":      str(xg_s.get("xgExcessMin", 0.5)),
        "xg_minute_min":         str(xg_s.get("minuteMin", 0)),
        "xg_minute_max":         str(xg_s.get("minuteMax", 90)),
        "drift":                 drift_s.get("version", "v1") if drift_s.get("enabled", True) else "off",
        "drift_threshold":       str(drift_s.get("driftMin", 30)),
        "drift_odds_max":        str(drift_s.get("oddsMax", 999)),
        "drift_goal_diff_min":   str(drift_s.get("goalDiffMin", 0)),
        "drift_minute_min":      str(drift_s.get("minuteMin", 0)),
        "drift_minute_max":      str(drift_s.get("minuteMax", 90)),
        "drift_mom_gap_min":     str(drift_s.get("momGapMin", 0)),
        "clustering":            cl_s.get("version", "v2") if cl_s.get("enabled", True) else "off",
        "clustering_sot_min":    str(cl_s.get("sotMin", 3)),
        "clustering_minute_min": str(cl_s.get("minuteMin", 0)),
        "clustering_minute_max": str(cl_s.get("minuteMax", 60)),
        "clustering_xg_rem_min": str(cl_s.get("xgRemMin", 0)),
        "pressure":              pr_s.get("version", "v1") if pr_s.get("enabled", True) else "off",
        "pressure_minute_min":   str(pr_s.get("minuteMin", 0)),
        "pressure_minute_max":   str(pr_s.get("minuteMax", 90)),
        "momentum":              mom_s.get("version", "v1"),
        "momentum_minute_min":   str(mom_s.get("minuteMin", 0)),
        "momentum_minute_max":   str(mom_s.get("minuteMax", 90)),
        "tarde_asia":            "v1" if ta_s.get("enabled", False) else "off",
        "tarde_asia_minute_min": str(ta_s.get("minuteMin", 0)),
        "tarde_asia_minute_max": str(ta_s.get("minuteMax", 90)),
        "draw_min_dur":          str(md.get("draw", 2)),
        "xg_min_dur":            str(md.get("xg", 3)),
        "drift_min_dur":         str(md.get("drift", 2)),
        "clustering_min_dur":    str(md.get("clustering", 4)),
        "pressure_min_dur":      str(md.get("pressure", 4)),
        "momentum_min_dur":      "1",
    }


def _detect_at_row(partial_rows: list, match_id: str, match_name: str,
                   csv_path: Path, versions: dict) -> list[dict]:
    """Run detect_betting_signals on a partial row slice via mock injection.

    Patches placed_bets.csv open to FileNotFoundError so detect_betting_signals
    treats placed_bets_keys as empty and doesn't suppress signals for matches
    that already have bets recorded (which is the case for all historical matches).
    """
    fake_games = [{"match_id": match_id, "name": match_name, "status": "live", "url": ""}]
    _real_open = builtins.open

    def _open_no_placed_bets(path, *args, **kwargs):
        if "placed_bets.csv" in str(path):
            raise FileNotFoundError("simulation: ignore placed_bets")
        return _real_open(path, *args, **kwargs)

    try:
        with (
            patch.object(csv_reader, "load_games",        return_value=fake_games),
            patch.object(csv_reader, "_resolve_csv_path", return_value=csv_path),
            patch.object(csv_reader, "_read_csv_rows",    return_value=partial_rows),
            patch("builtins.open", side_effect=_open_no_placed_bets),
        ):
            result = csv_reader.detect_betting_signals(versions)
            return result.get("signals", [])
    except Exception as exc:
        print(f"[simulate] _detect_at_row error at match={match_id}: {exc!r}")
        return []


def _run_simulation(match: dict, versions: dict, min_dur: dict,
                    flat_stake: float = 1.0, cashout_pct: float = 50.0,
                    adj: dict | None = None, risk_filter: str = "all") -> dict:
    match_id   = match["match_id"]
    match_name = match["name"]
    csv_path   = Path(match["csv_path"])

    # Prefer pre-processed rows from cache (normalized halftime minutes + cleaned odds).
    all_rows = match.get("rows") or _read_csv_rows(csv_path)
    if not all_rows:
        return {"error": "No rows found in CSV"}

    # Remove rows with anomalous minute=0 that appear mid-match (empty minuto field).
    # These cause draw/other strategies with minuteMin>0 to falsely deactivate.
    max_min_seen = 0.0
    filtered: list = []
    for r in all_rows:
        m = _to_float(r.get("minuto", "")) or 0.0
        if m < 1.0 and max_min_seen > 10.0:
            continue  # anomalous zero-minute row after match has started
        max_min_seen = max(max_min_seen, m)
        filtered.append(r)
    all_rows = filtered

    last = all_rows[-1]
    ft_gl = int(_to_float(last.get("goles_local", "")) or 0)
    ft_gv = int(_to_float(last.get("goles_visitante", "")) or 0)
    final_score = f"{ft_gl}-{ft_gv}"

    timeline: list[dict] = []
    prev_active: dict[str, dict] = {}
    prev_score: str | None = None
    fire_minute: dict[str, float] = {}    # strategy → minute it first fired
    active_since_row: dict[str, int] = {}  # strategy → row index of activation

    # Min-duration thresholds in minutes (min_dur captures × 0.5 min/capture)
    mat_mins: dict[str, float] = {
        fam: float(min_dur.get(fam, 2)) * 0.5
        for fam in ("draw", "xg", "drift", "clustering", "pressure", "momentum")
    }
    matured: set[str] = set()       # strategies currently in their mature state (cleared on signal_off)
    placed_strats: set[str] = set() # strategies that have EVER placed a bet (never cleared → dedup)
    matured_bets: dict[str, dict] = {}  # strat → {recommendation, odds, minute}

    # Cashout tracking: after maturity, monitor lay odds each row.
    # Only DRAW/HOME/AWAY have lay columns; OVER/UNDER never trigger auto-cashout.
    # Formula from bets.py: trigger when lay_now >= entry_back * (1 + cashout_pct/100)
    #                       cashout_pl = stake * (entry_back / lay_now - 1)
    pending_cashouts: dict[str, dict] = {}  # strat → {entry_back, lay_col, stake}
    cashed_out: dict[str, dict] = {}        # strat → {pl, minute, lay_now}

    # Cycle tracking: one entry per activation/deactivation pair (handles re-fires)
    activation_log: list[dict] = []    # completed + still-active cycles
    current_cycle: dict[str, dict] = {}  # strat → open cycle data

    for i, row in enumerate(all_rows):
        minute = _to_float(row.get("minuto", "")) or 0.0
        gl = int(_to_float(row.get("goles_local", "")) or 0)
        gv = int(_to_float(row.get("goles_visitante", "")) or 0)
        score = f"{gl}-{gv}"

        events: list[dict] = []

        # ── Goal event ─────────────────────────────────────────────────────────
        if prev_score is not None and score != prev_score:
            events.append({
                "type": "goal",
                "score_before": prev_score,
                "score_after":  score,
            })

        # ── Auto-cashout monitoring ─────────────────────────────────────────────
        # Mirrors run_auto_cashout() from bets.py: lay_now >= entry_back * (1 + pct/100)
        for strat, co in list(pending_cashouts.items()):
            lay_now = _to_float(row.get(co["lay_col"]))
            if lay_now and lay_now > 1.0:
                threshold = co["entry_back"] * (1.0 + cashout_pct / 100.0)
                if lay_now >= threshold:
                    co_pl = round(co["stake"] * (co["entry_back"] / lay_now - 1), 2)
                    cashed_out[strat] = {"pl": co_pl, "minute": minute, "lay_now": lay_now}
                    del pending_cashouts[strat]
                    if strat in current_cycle:
                        current_cycle[strat]["cashout"]        = True
                        current_cycle[strat]["cashout_pl"]     = co_pl
                        current_cycle[strat]["cashout_minute"] = minute
                    events.append({
                        "type":          "cashout",
                        "strategy":      strat,
                        "strategy_name": STRATEGY_LABELS.get(strat, strat),
                        "cashout_pl":    co_pl,
                        "lay_now":       round(lay_now, 2),
                        "entry_back":    co["entry_back"],
                    })

        # ── Run detection on rows[:i+1] ────────────────────────────────────────
        signals = _detect_at_row(all_rows[:i + 1], match_id, match_name, csv_path, versions)
        curr_active: dict[str, dict] = {s["strategy"]: s for s in signals}

        # ── Signal activations ─────────────────────────────────────────────────
        for strat, sig in curr_active.items():
            if strat not in prev_active:
                fire_minute[strat]       = minute
                active_since_row[strat]  = i
                # Open a new cycle for this activation
                current_cycle[strat] = {
                    "strategy":             strat,
                    "strategy_name":        STRATEGY_LABELS.get(strat, strat),
                    "first_fire_minute":    minute,
                    "still_active_at_end":  False,
                    "matured":              False,
                    "final_recommendation": sig.get("recommendation", ""),
                    "final_odds":           sig.get("back_odds") or sig.get("odds"),
                }
                events.append({
                    "type":           "signal_on",
                    "strategy":       strat,
                    "strategy_name":  STRATEGY_LABELS.get(strat, strat),
                    "recommendation": sig.get("recommendation", ""),
                    "odds":           sig.get("back_odds") or sig.get("odds"),
                    "details": {
                        k: v for k, v in sig.items()
                        if k in ("xg_total", "drift_pct", "sot_team", "poss_team",
                                 "goal_diff", "over_line", "ev", "confidence",
                                 "score_at_trigger")
                        and v is not None
                    },
                })

        # ── Maturity transitions ───────────────────────────────────────────────
        # Step 1: collect candidates that have met min-duration requirement
        candidates: list[tuple[str, dict, float]] = []
        for strat, sig in curr_active.items():
            # placed_strats mirrors paper trading placed_bets_keys: once a bet is placed
            # for this strategy in this match, no second bet is allowed (even on re-fire).
            if strat in fire_minute and strat not in matured and strat not in placed_strats:
                fam    = _family(strat)
                needed = mat_mins.get(fam, 1.0)
                age    = minute - fire_minute[strat]
                if age >= needed:
                    candidates.append((strat, sig, age))

        # Step 2: apply realistic adjustments to filter candidates (mirrors live system)
        if candidates and adj:
            # Build enriched copies with simulation-based signal_age_minutes
            enriched: list[dict] = []
            for strat, sig, age in candidates:
                sc = dict(sig)
                sc["signal_age_minutes"] = age  # use simulation tracking, not wall-clock
                enriched.append(sc)
            filtered_enr, _ = _apply_realistic_adjustments(enriched, adj, risk_filter)
            passing = {sc["strategy"] for sc in filtered_enr}
            candidates = [(strat, sig, age) for strat, sig, age in candidates if strat in passing]

        # Step 3: process candidates that passed all adjustments
        for strat, sig, age in candidates:
            matured.add(strat)
            placed_strats.add(strat)  # permanent dedup: won't bet again even on re-fire
            bet_odds = sig.get("back_odds") or sig.get("odds")
            bet_rec  = sig.get("recommendation", "")
            matured_bets[strat] = {
                "recommendation": bet_rec,
                "odds":           bet_odds,
                "minute":         minute,
            }
            # Register for cashout monitoring (DRAW/HOME/AWAY only; OVER/UNDER never cash out)
            lay_col = _get_lay_col(bet_rec)
            if lay_col and bet_odds:
                pending_cashouts[strat] = {
                    "entry_back": bet_odds,
                    "lay_col":    lay_col,
                    "stake":      flat_stake,
                }
            # Mark current cycle as matured
            if strat in current_cycle:
                current_cycle[strat]["matured"]              = True
                current_cycle[strat]["bet_minute"]           = minute
                current_cycle[strat]["bet_odds"]             = bet_odds
                current_cycle[strat]["bet_recommendation"]   = bet_rec
            events.append({
                "type":           "signal_mature",
                "strategy":       strat,
                "strategy_name":  STRATEGY_LABELS.get(strat, strat),
                "recommendation": bet_rec,
                "odds":           bet_odds,
                "active_minutes": round(age, 1),
            })

        # ── Signal deactivations ───────────────────────────────────────────────
        for strat in list(prev_active):
            if strat not in curr_active:
                age = round(minute - fire_minute.get(strat, minute), 1)
                events.append({
                    "type":          "signal_off",
                    "strategy":      strat,
                    "strategy_name": STRATEGY_LABELS.get(strat, strat),
                    "active_minutes": age,
                    "matured":       strat in matured,
                })
                # Close cycle and move to log
                if strat in current_cycle:
                    activation_log.append(current_cycle.pop(strat))
                fire_minute.pop(strat, None)
                active_since_row.pop(strat, None)
                matured.discard(strat)

        if events:
            timeline.append({
                "row_idx":           i,
                "minute":            round(minute, 1),
                "score":             score,
                "odds": {
                    "home": _to_float(row.get("back_home", "")),
                    "away": _to_float(row.get("back_away", "")),
                    "draw": _to_float(row.get("back_draw", "")),
                },
                "xg": {
                    "local":    _to_float(row.get("xg_local", "")),
                    "visitante": _to_float(row.get("xg_visitante", "")),
                },
                "active_strategies": list(curr_active.keys()),
                "events": events,
            })

        prev_active = curr_active
        prev_score  = score

    # ── Build summary from activation cycles ───────────────────────────────────
    # Close any still-open cycles (active at end of match)
    for strat, sig in prev_active.items():
        if strat in current_cycle:
            current_cycle[strat]["still_active_at_end"]  = True
            current_cycle[strat]["final_recommendation"] = sig.get("recommendation")
            current_cycle[strat]["final_odds"]           = sig.get("back_odds") or sig.get("odds")
            activation_log.append(current_cycle.pop(strat))

    summary = activation_log

    # ── Compute outcomes for matured bets ──────────────────────────────────────
    # Cashout takes priority over win/loss for DRAW/HOME/AWAY bets that were triggered.
    matured_outcomes: dict[str, dict] = {}
    for strat, bet in matured_bets.items():
        if strat in cashed_out:
            co = cashed_out[strat]
            matured_outcomes[strat] = {
                "won":            None,  # not applicable: bet was cashed out
                "pl":             co["pl"],
                "cashout":        True,
                "cashout_minute": co["minute"],
                "cashout_lay":    co["lay_now"],
            }
        else:
            outcome = _calc_bet_outcome(bet["recommendation"], final_score, bet["odds"], flat_stake)
            if outcome:
                matured_outcomes[strat] = outcome

    # Retroactively annotate signal_mature events with outcome (cashout or win/loss)
    for entry in timeline:
        for ev in entry["events"]:
            if ev["type"] == "signal_mature" and ev["strategy"] in matured_outcomes:
                o = matured_outcomes[ev["strategy"]]
                if not o.get("cashout"):
                    ev.update({"won": o["won"], "pl": o["pl"]})

    # Enrich summary items with outcome
    for item in summary:
        strat = item["strategy"]
        if item["matured"] and strat in matured_outcomes:
            o = matured_outcomes[strat]
            item["pl"] = o["pl"]
            if o.get("cashout"):
                item["cashout"]        = True
                item["cashout_minute"] = o.get("cashout_minute")
                item["cashout_lay"]    = o.get("cashout_lay")
            else:
                item["won"] = o["won"]

    total_pl = round(sum(o["pl"] for o in matured_outcomes.values()), 2)

    return {
        "match_id":      match_id,
        "match_name":    match_name,
        "final_score":   final_score,
        "total_rows":    len(all_rows),
        "n_bets_placed": len(matured_outcomes),
        "total_pl":      total_pl,
        "timeline":      timeline,
        "summary":       sorted(summary, key=lambda s: s["first_fire_minute"]),
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/matches")
def list_simulatable_matches():
    """List all historical matches available for simulation, with date."""
    try:
        matches = _get_all_finished_matches()
        result = []
        for m in matches:
            if not (m.get("csv_path") and Path(m["csv_path"]).exists()):
                continue
            # Extract YYYY-MM-DD from kickoff_time (first en_juego timestamp) or start_time
            date_str: str | None = None
            for field in ("kickoff_time", "start_time"):
                ts = m.get(field)
                if ts:
                    try:
                        date_str = str(ts)[:10]
                        break
                    except Exception:
                        pass
            result.append({
                "match_id": m["match_id"],
                "name":     m["name"],
                "date":     date_str,
            })
        return sorted(result, key=lambda m: (m.get("date") or "", m["name"]))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/invalidate/{match_id}")
def invalidate_cache(match_id: str):
    """Clear cached simulation for a match (force re-run)."""
    _sim_cache.pop(match_id, None)
    return {"ok": True}


@router.get("/run/{match_id}")
def run_simulation(match_id: str):
    """
    Run row-by-row signal simulation for a historical match.
    Returns a timeline of signal activations, deactivations, goals, and maturity events.
    Results are cached in memory until invalidated.
    """
    if match_id in _sim_cache:
        return _sim_cache[match_id]

    matches = _get_all_finished_matches()
    match   = next((m for m in matches if m["match_id"] == match_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Match '{match_id}' not found")
    if not match.get("csv_path") or not Path(match["csv_path"]).exists():
        raise HTTPException(status_code=404, detail="CSV file not found for this match")

    config       = load_config()
    versions     = _build_versions(config)
    min_dur      = config.get("min_duration", {})
    flat_stake   = float(config.get("flat_stake", 1.0))
    adj          = config.get("adjustments", {})
    cashout_pct  = float(adj.get("cashout_pct", 50.0))
    risk_filter  = config.get("risk_filter", "all")

    result = _run_simulation(match, versions, min_dur, flat_stake, cashout_pct, adj, risk_filter)

    if "error" not in result:
        _sim_cache[match_id] = result

    return result
