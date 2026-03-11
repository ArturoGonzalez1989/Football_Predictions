"""
Strategy analysis, backtest, and live signal detection for Betfair Exchange.

Data-loading utilities are in csv_loader.py (imported below).
"""

import csv
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote, unquote

# ── Re-export all data-loading utilities from csv_loader ─────────────────────
from .csv_loader import (
    BASE_DIR, GAMES_CSV, DATA_DIR, CORRUPTED_OVER_MATCHES,
    STAT_COLUMNS, ODDS_COLUMNS, ALL_STAT_COLUMNS,
    _to_float, _median, _resolve_csv_path, _match_id_from_url,
    _read_csv_rows, _normalize_halftime_minutes, _read_csv_summary,
    _final_match_minute, _final_result_row,
    _check_min_dur, _count_odds_stability, _lookback_val, _compute_synthetic_at_trigger,
    _clean_odds_outliers,
    _calculate_match_quality, _calculate_match_gaps, _calculate_gap_segments,
    clear_analytics_cache, _get_cached_finished_data, _get_all_finished_matches, _cached_result,
    _result_cache, _result_cache_time,
    load_games, delete_match, load_all_captures, load_match_detail,
    load_momentum_data, load_all_stats, load_match_full,
)

# ── GR8: Shared trigger-detection helpers (in strategy_triggers.py) ─────────
from .strategy_triggers import (
    _detect_tarde_asia_liga,
    _detect_momentum_dominant,
    _detect_draw_filters,
    _detect_xg_underperf_candidates,
    _detect_odds_drift_trigger,
    _detect_goal_clustering_trigger,
    _detect_pressure_cooker_trigger,
    _detect_back_draw_00_trigger,
    _detect_xg_underperformance_trigger,
    _detect_momentum_xg_trigger,
    _detect_tarde_asia_trigger,
    _detect_over25_2goal_trigger,
    _detect_under35_late_trigger,
    _detect_lay_over45_v3_trigger,
    _detect_draw_xg_conv_trigger,
    _detect_poss_extreme_trigger,
    _detect_longshot_trigger,
    _detect_cs_00_trigger,
    _detect_over25_2goals_trigger,
    _detect_cs_close_trigger,
    _detect_cs_one_goal_trigger,
    _detect_draw_11_trigger,
    _detect_ud_leading_trigger,
    _detect_under35_3goals_trigger,
    _detect_away_fav_leading_trigger,
    _detect_home_fav_leading_trigger,
    _detect_under45_3goals_trigger,
    _detect_cs_11_trigger,
    _detect_cs_20_trigger,
    _detect_cs_big_lead_trigger,
    _get_over_odds_field,
)


@_cached_result("quality_distribution")
def analyze_quality_distribution() -> dict:
    """Aggregate quality metrics across all finished matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "avg_quality": 0,
            "total_matches": 0,
            "quality_ranges": [],
            "bins": []
        }

    qualities = []
    bins_data = {
        "0-20": [], "20-40": [], "40-60": [], "60-80": [], "80-100": []
    }

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        quality = _calculate_match_quality(rows)
        qualities.append(quality)

        # Classify into bins
        if quality < 20:
            bins_data["0-20"].append(match["match_id"])
        elif quality < 40:
            bins_data["20-40"].append(match["match_id"])
        elif quality < 60:
            bins_data["40-60"].append(match["match_id"])
        elif quality < 80:
            bins_data["60-80"].append(match["match_id"])
        else:
            bins_data["80-100"].append(match["match_id"])

    avg_quality = round(sum(qualities) / len(qualities), 1) if qualities else 0

    # Quality ranges count
    quality_ranges = [
        {"range": "0-20%", "count": len(bins_data["0-20"])},
        {"range": "20-40%", "count": len(bins_data["20-40"])},
        {"range": "40-60%", "count": len(bins_data["40-60"])},
        {"range": "60-80%", "count": len(bins_data["60-80"])},
        {"range": "80-100%", "count": len(bins_data["80-100"])},
    ]

    # Bins for histogram
    bins = [
        {"label": "0-20%", "count": len(bins_data["0-20"]), "matches": bins_data["0-20"]},
        {"label": "20-40%", "count": len(bins_data["20-40"]), "matches": bins_data["20-40"]},
        {"label": "40-60%", "count": len(bins_data["40-60"]), "matches": bins_data["40-60"]},
        {"label": "60-80%", "count": len(bins_data["60-80"]), "matches": bins_data["60-80"]},
        {"label": "80-100%", "count": len(bins_data["80-100"]), "matches": bins_data["80-100"]},
    ]

    return {
        "avg_quality": avg_quality,
        "total_matches": len(finished_matches),
        "quality_ranges": quality_ranges,
        "bins": bins
    }


@_cached_result("gaps_distribution")
def analyze_gaps_distribution() -> dict:
    """Analyze capture gaps across all matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "avg_gaps": 0,
            "max_gaps": 0,
            "distribution": []
        }

    all_gaps = []
    gap_counts = {}

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        gaps = _calculate_match_gaps(rows)
        all_gaps.append(gaps)

        # Count matches by gap count
        gap_counts[gaps] = gap_counts.get(gaps, 0) + 1

    avg_gaps = round(sum(all_gaps) / len(all_gaps), 1) if all_gaps else 0
    max_gaps = max(all_gaps) if all_gaps else 0

    # Distribution
    distribution = [
        {"gap_count": gap, "match_count": count}
        for gap, count in sorted(gap_counts.items())
    ]

    return {
        "avg_gaps": avg_gaps,
        "max_gaps": max_gaps,
        "distribution": distribution
    }


@_cached_result("stats_coverage")
def analyze_stats_coverage() -> dict:
    """Calculate coverage percentage for each stat field actually used by active strategies."""
    # Stats and odds that gate or feed into signal detection across all active strategies:
    # Back Empate V2R:    xg + posesion + tiros     → back_draw
    # xG Underperf BASE: xg + tiros_puerta          → back_over*
    # Goal Clustering V2: tiros_puerta              → back_over*
    # Pressure Cooker V1: (score-based)             → back_over*
    # Tarde Asia V1:      (time/league)             → back_over25
    # Odds Drift V1:      (odds-only)               → back_home / back_away
    # Momentum × xG V1:  xg + tiros_puerta          → back_home / back_away
    # Synthetic attrs (pressure_index, momentum_gap, opta_gap): corners, momentum, opta_points
    STRATEGY_STAT_COLUMNS = [
        # --- Stats ---
        "xg_local", "xg_visitante",
        "posesion_local", "posesion_visitante",
        "tiros_local", "tiros_visitante",
        "tiros_puerta_local", "tiros_puerta_visitante",
        "corners_local", "corners_visitante",
        "momentum_local", "momentum_visitante",
        "opta_points_local", "opta_points_visitante",
        # --- Cuotas (mercados en los que se apuesta) ---
        "back_draw",                                          # Back Empate
        "back_home", "back_away",                            # Odds Drift, Momentum xG
        "back_over05", "back_over15", "back_over25",         # Over markets
        "back_over35", "back_over45",                        # Over markets (alta goleada)
    ]

    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {"fields": []}

    # Count non-null values for each stat column
    field_counts = {col: {"filled": 0, "total": 0} for col in STRATEGY_STAT_COLUMNS}

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        for row in rows:
            # Only count in-play rows
            estado = row.get("estado_partido", "").strip()
            if estado in ("pre_partido", ""):
                continue
            for col in STRATEGY_STAT_COLUMNS:
                field_counts[col]["total"] += 1
                val = row.get(col, "")
                if val and val.strip() not in ("", "N/A", "None"):
                    field_counts[col]["filled"] += 1

    # Calculate coverage percentage
    fields = []
    for col, counts in field_counts.items():
        coverage_pct = round(counts["filled"] / counts["total"] * 100, 1) if counts["total"] > 0 else 0
        fields.append({
            "name": col,
            "coverage_pct": coverage_pct
        })

    # Sort by coverage (lowest first to highlight problems)
    fields.sort(key=lambda x: x["coverage_pct"])

    return {"fields": fields}
def analyze_odds_coverage() -> dict:
    """Analyze odds scraping coverage across all finished matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "avg_coverage": 0,
            "total_matches": 0,
            "no_odds": 0,
            "partial_odds": 0,
            "good_odds": 0,
            "total_outlier_matches": 0,
            "bins": [],
            "matches": [],
        }

    match_list = []
    coverages = []

    for match in finished_matches:
        # Only include matches with at least one 'finalizado' row.
        # Many matches revert to 'pre_partido' or 'en_juego' as their last row
        # after Betfair closes the market, so we can't rely on the last row alone.
        _rows = match.get("rows", [])
        if not any(r.get("estado_partido", "").strip() == "finalizado" for r in _rows):
            continue

        # Use precomputed stats from cache (raw rows before outlier cleaning)
        total         = match.get("raw_total_rows", len(match.get("rows") or []))
        with_odds     = match.get("raw_with_odds", 0)
        # Coverage = rows_with_odds out of 90 expected match minutes (capped at 100%).
        # Using total_rows as denominator was misleading: 1 row with odds / 1 total = 100%
        # even when 90 minutes of data are missing.
        pct           = round(min(with_odds / 90 * 100, 100.0), 1)
        outlier_count = match.get("back_home_outliers", 0)

        raw_min_bh = match.get("min_back_home")
        raw_max_bh = match.get("max_back_home")
        coverages.append(pct)
        match_list.append({
            "match_id":       match["match_id"],
            "name":           match["name"],
            "start_time":     match.get("start_time"),
            "kickoff_time":   match.get("kickoff_time"),
            "coverage_pct":   pct,
            "rows_with_odds": with_odds,
            "total_rows":     total,
            "outlier_count":  outlier_count,
            "min_back_home":  round(raw_min_bh, 2) if raw_min_bh is not None else None,
            "max_back_home":  round(raw_max_bh, 2) if raw_max_bh is not None else None,
            "gap_count":      match.get("gap_count", 0),
            "avg_gap_size":   match.get("avg_gap_size", 0.0),
        })

    # Sort by coverage ascending (worst first), then by outlier_count descending
    match_list.sort(key=lambda x: (x["coverage_pct"], -x["outlier_count"]))

    avg_coverage = round(sum(coverages) / len(coverages), 1) if coverages else 0
    no_odds = sum(1 for p in coverages if p == 0)
    partial_odds = sum(1 for p in coverages if 0 < p < 80)
    good_odds = sum(1 for p in coverages if p >= 80)

    bins = [
        {"label": "0%",    "count": sum(1 for p in coverages if p == 0)},
        {"label": "1-25%", "count": sum(1 for p in coverages if 0 < p <= 25)},
        {"label": "26-50%","count": sum(1 for p in coverages if 25 < p <= 50)},
        {"label": "51-75%","count": sum(1 for p in coverages if 50 < p <= 75)},
        {"label": "76-99%","count": sum(1 for p in coverages if 75 < p < 100)},
        {"label": "100%",  "count": sum(1 for p in coverages if p == 100)},
    ]

    return {
        "avg_coverage": avg_coverage,
        "total_matches": len(finished_matches),
        "no_odds": no_odds,
        "partial_odds": partial_odds,
        "good_odds": good_odds,
        "bins": bins,
        "matches": match_list,
        "total_outlier_matches": sum(1 for m in match_list if m["outlier_count"] > 0),
    }


@_cached_result("momentum_patterns")
def analyze_strategy_back_draw_00(min_dur: int = 1) -> dict:
    """Analyze the 'Back Draw at 0-0 from min 30' strategy across all finished matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {"total_matches": 0, "with_trigger": 0, "bets": [], "summary": {}}

    bets = []
    matches_with_data = 0

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows or len(rows) < 5:
            continue

        matches_with_data += 1

        # Find first row where min >= 30 and score is 0-0, then check persistence
        trigger_row = None
        trigger_idx = None
        for ri, row in enumerate(rows):
            minuto = _to_float(row.get("minuto", ""))
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            if minuto is not None and gl is not None and gv is not None:
                if minuto >= 30 and int(gl) == 0 and int(gv) == 0:
                    # Check persistence: score must stay 0-0 for min_dur consecutive rows
                    def _still_00(r):
                        _gl = _to_float(r.get("goles_local", ""))
                        _gv = _to_float(r.get("goles_visitante", ""))
                        return _gl is not None and _gv is not None and int(_gl) == 0 and int(_gv) == 0
                    entry_row = _check_min_dur(rows, ri, min_dur, _still_00)
                    if entry_row is not None:
                        trigger_row = entry_row
                        trigger_idx = rows.index(entry_row)
                    break

        if trigger_row is None:
            continue

        # Extract in-play data at trigger
        back_draw = _to_float(trigger_row.get("back_draw", ""))
        xg_l = _to_float(trigger_row.get("xg_local", ""))
        xg_v = _to_float(trigger_row.get("xg_visitante", ""))
        xg_total = ((xg_l or 0) + (xg_v or 0)) if (xg_l is not None or xg_v is not None) else None
        xg_max = max(xg_l or 0, xg_v or 0) if (xg_l is not None or xg_v is not None) else None

        sot_l = _to_float(trigger_row.get("tiros_puerta_local", ""))
        sot_v = _to_float(trigger_row.get("tiros_puerta_visitante", ""))
        sot_total = (int(sot_l or 0) + int(sot_v or 0)) if (sot_l is not None or sot_v is not None) else None

        poss_l = _to_float(trigger_row.get("posesion_local", ""))
        poss_v = _to_float(trigger_row.get("posesion_visitante", ""))
        poss_diff = abs((poss_l or 50) - (poss_v or 50)) if (poss_l is not None or poss_v is not None) else None

        shots_l = _to_float(trigger_row.get("tiros_local", ""))
        shots_v = _to_float(trigger_row.get("tiros_visitante", ""))
        shots_total = (int(shots_l or 0) + int(shots_v or 0)) if (shots_l is not None or shots_v is not None) else None

        minuto_trigger = _to_float(trigger_row.get("minuto", ""))
        bfed = _to_float(trigger_row.get("BFED", "")) or _to_float(trigger_row.get("bfed_prematch", ""))

        # Final result — use last row with valid scores (skip trailing pre_partido rows)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))
        if gl_final is None or gv_final is None:
            continue

        draw_won = int(gl_final) == int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Stability + conservative odds (min in window)
        _stab_count, _cons_odds = _count_odds_stability(rows, trigger_idx, "back_draw", back_draw or 0)

        # P/L calculation (stake 10, 5% commission on winnings)
        stake = 10
        if draw_won and back_draw:
            pl = round((back_draw - 1) * stake * 0.95, 2)
            pl_conservative = round((_cons_odds - 1) * stake * 0.95, 2)
        else:
            pl = -stake
            pl_conservative = -stake

        # Check strategy filters via shared GR9 helper.
        # DRAW_PARAMS thresholds per version (aligned with optimize.py DRAW_PARAMS):
        #   v15: xg<0.6, poss<25   — V1.5
        #   v2:  xg<0.5, poss<20, shots<8
        #   v2r: xg<0.6, poss<20, shots<8  (relaxed xg vs v2)
        synth = _compute_synthetic_at_trigger(rows, trigger_idx)
        xg_dom = synth.get("xg_dominance")
        press_v = synth.get("pressure_index_v")

        opta_l_tr = _to_float(trigger_row.get("opta_points_local", ""))
        opta_v_tr = _to_float(trigger_row.get("opta_points_visitante", ""))
        opta_gap = abs(opta_l_tr - opta_v_tr) if (opta_l_tr is not None and opta_v_tr is not None) else None

        # Compute v2r/v3/v4 using _detect_draw_filters (v2r thresholds)
        _draw_flags_v2r = _detect_draw_filters(
            xg_total=xg_total, poss_diff=poss_diff, shots_total=shots_total,
            opta_gap=opta_gap, xg_dom=xg_dom, synth_pressure_v=press_v,
            cfg={"xg_max": 0.6, "poss_max": 20.0, "shots_max": 8.0},
        )
        passes_v15 = _draw_flags_v2r["passes_v15"]
        passes_v2r = _draw_flags_v2r["passes_v2r"]
        passes_v3  = _draw_flags_v2r["passes_v3"]
        passes_v4  = _draw_flags_v2r["passes_v4"]

        # V2 uses xg<0.5 threshold (slightly stricter than v2r's 0.6)
        _draw_flags_v2 = _detect_draw_filters(
            xg_total=xg_total, poss_diff=poss_diff, shots_total=shots_total,
            opta_gap=opta_gap, xg_dom=xg_dom, synth_pressure_v=press_v,
            cfg={"xg_max": 0.5, "poss_max": 20.0, "shots_max": 8.0},
        )
        passes_v2 = _draw_flags_v2["passes_v2r"]  # v2r flag with v2 thresholds

        bets.append({
            "strategy": "back_draw_00",
            "match": match["name"],
            "match_id": match["match_id"],
            "minuto": minuto_trigger,
            "back_draw": round(back_draw, 2) if back_draw else None,
            "lay_trigger": _to_float(trigger_row.get("lay_draw", "")) or None,
            "xg_total": round(xg_total, 2) if xg_total is not None else None,
            "xg_max": round(xg_max, 2) if xg_max is not None else None,
            "sot_total": sot_total,
            "poss_diff": round(poss_diff, 1) if poss_diff is not None else None,
            "shots_total": shots_total,
            "bfed_prematch": bfed,
            "ft_score": ft_score,
            "won": draw_won,
            "pl": pl,
            "pl_conservative": pl_conservative,
            "conservative_odds": round(_cons_odds, 2),
            "passes_v2": passes_v2,
            "passes_v15": passes_v15,
            "passes_v2r": passes_v2r,
            "passes_v3": passes_v3,
            "passes_v4": passes_v4,
            "synth_xg_dominance": xg_dom,
            "synth_pressure_index_v": press_v,
            "stability_count": _stab_count,
            "timestamp_utc": trigger_row.get("timestamp_utc", ""),
            "País": trigger_row.get("País", "Desconocido"),
            "Liga": trigger_row.get("Liga", "Desconocida"),
        })

    # Summary stats helper
    def _make_summary(subset):
        n = len(subset)
        w = sum(1 for b in subset if b["won"])
        pl = sum(b["pl"] for b in subset)
        return {
            "bets": n,
            "wins": w,
            "win_pct": round(w / n * 100, 1) if n else 0,
            "pl": round(pl, 2),
            "roi": round(pl / (n * 10) * 100, 1) if n else 0,
        }

    return {
        "total_matches": matches_with_data,
        "with_trigger": len(bets),
        "summary": {
            "base": _make_summary(bets),
            "v15": _make_summary([b for b in bets if b["passes_v15"]]),
            "v2": _make_summary([b for b in bets if b["passes_v2"]]),
            "v2r": _make_summary([b for b in bets if b["passes_v2r"]]),
            "v4": _make_summary([b for b in bets if b.get("passes_v4")]),
        },
        "bets": bets,
    }


# ── xG Underperformance Strategy ────────────────────────────────────────



def calculate_time_score_risk(
    strategy: str,
    minute: float,
    home_score: int,
    away_score: int,
    dominant_team: str
) -> dict:
    """
    Calcula el nivel de riesgo de una apuesta basándose en tiempo restante y marcador.

    Solo aplica a estrategias de resultado final (momentum_xg, odds_drift) cuando el
    equipo sobre el que apostamos va perdiendo.

    Reglas de riesgo:
    - HIGH: Quedan <20 min y el equipo va perdiendo ≥2 goles
    - HIGH: Quedan <15 min y el equipo va perdiendo ≥1 gol
    - MEDIUM: Quedan <25 min y el equipo va perdiendo ≥2 goles
    - MEDIUM: Quedan <20 min y el equipo va perdiendo ≥1 gol
    - NONE: Otros casos

    Args:
        strategy: Nombre de la estrategia (e.g., "momentum_xg_v1", "odds_drift")
        minute: Minuto actual del partido
        home_score: Goles del equipo local
        away_score: Goles del equipo visitante
        dominant_team: "Home"/"Local" o "Away"/"Visitante"

    Returns:
        {
            "has_risk": bool,
            "risk_level": "none" | "medium" | "high",
            "risk_reason": str,
            "time_remaining": int,
            "deficit": int
        }
    """
    # Solo aplica a estrategias de resultado final
    strategy_lower = strategy.lower()
    if not any(s in strategy_lower for s in ["momentum_xg", "odds_drift"]):
        return {
            "has_risk": False,
            "risk_level": "none",
            "risk_reason": "",
            "time_remaining": int(90 - minute),
            "deficit": 0
        }

    time_remaining = 90 - minute

    # Calcular déficit del equipo sobre el que apostamos
    dominant_lower = dominant_team.lower()
    if dominant_lower in ["home", "local"]:
        deficit = away_score - home_score
    else:
        deficit = home_score - away_score

    # Si no va perdiendo, no hay riesgo
    if deficit <= 0:
        return {
            "has_risk": False,
            "risk_level": "none",
            "risk_reason": "",
            "time_remaining": int(time_remaining),
            "deficit": deficit
        }

    # Evaluar nivel de riesgo
    risk_level = "none"
    risk_reason = ""

    # RIESGO ALTO
    if time_remaining < 20 and deficit >= 2:
        risk_level = "high"
        risk_reason = f"ALTO RIESGO: Quedan {int(time_remaining)} min para remontar {deficit} goles. Probabilidad muy baja."
    elif time_remaining < 15 and deficit >= 1:
        risk_level = "high"
        risk_reason = f"ALTO RIESGO: Quedan {int(time_remaining)} min para remontar {deficit} gol. Tiempo muy ajustado."

    # RIESGO MEDIO
    elif time_remaining < 25 and deficit >= 2:
        risk_level = "medium"
        risk_reason = f"RIESGO MEDIO: Quedan {int(time_remaining)} min para remontar {deficit} goles. Complicado pero posible."
    elif time_remaining < 20 and deficit >= 1:
        risk_level = "medium"
        risk_reason = f"RIESGO MEDIO: Quedan {int(time_remaining)} min para remontar {deficit} gol. Tiempo limitado."

    has_risk = risk_level != "none"

    return {
        "has_risk": has_risk,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "time_remaining": int(time_remaining),
        "deficit": deficit
    }


def analyze_strategy_xg_underperformance(min_dur: int = 1) -> dict:
    """Analyze the 'xG Underperformance - Back Over' strategy across all finished matches.

    Trigger: team xG - goals >= 0.5 AND team is currently LOSING.
    Bet: Back Over (total_goals_at_trigger + 0.5).
    """
    finished_matches = _get_all_finished_matches()
    if not finished_matches:
        return {"total_matches": 0, "with_trigger": 0, "bets": [], "summary": {}}

    bets = []
    matches_with_xg = 0

    for match in finished_matches:
        # Skip matches with corrupted Over/Under odds
        if match["match_id"] in CORRUPTED_OVER_MATCHES:
            continue

        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows or len(rows) < 5:
            continue

        # Final result — use last row with valid scores (skip trailing pre_partido rows)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))
        if gl_final is None or gv_final is None:
            continue
        ft_gl, ft_gv = int(gl_final), int(gv_final)
        ft_total = ft_gl + ft_gv
        ft_score = f"{ft_gl}-{ft_gv}"

        # Check match has xG data
        has_xg = any(_to_float(r.get("xg_local")) is not None for r in rows)
        if not has_xg:
            continue
        matches_with_xg += 1

        # One trigger per team per match
        triggered = {"home": False, "away": False}
        # BT superset config: permissive threshold (0.3) so _filter_xg can apply
        # the config-level threshold in the notebook/reconcile pipeline.
        _xg_bt_cfg = {"xg_excess_min": 0.3, "sot_min": 0, "minute_max": 90, "minute_min": 15}

        for ri, row in enumerate(rows):
            minuto = _to_float(row.get("minuto", ""))
            if minuto is None or minuto < 15:
                continue

            xg_h = _to_float(row.get("xg_local", ""))
            xg_a = _to_float(row.get("xg_visitante", ""))
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            gl_i, gv_i = int(gl), int(gv)

            # Use shared GR9 helper to detect candidates for both teams
            candidates = _detect_xg_underperformance_trigger(rows, ri, _xg_bt_cfg)

            for cand in candidates:
                team = cand["team"]
                if triggered[team]:
                    continue

                xg_excess = cand["xg_excess"]
                total_at_trigger = cand["total_goals"]
                score_at_trigger = cand["score_at_trigger"]
                over_field = cand["over_field"]
                team_xg = xg_h if team == "home" else xg_a
                team_goals = gl_i if team == "home" else gv_i

                # Check persistence: signal must hold for min_dur consecutive rows.
                # Re-verify via the shared helper at confirmation row (mirrors LIVE
                # stability: signal must still be present after min_dur captures).
                entry_row = row
                if min_dur > 1:
                    end_idx = ri + min_dur - 1
                    if end_idx >= len(rows):
                        continue  # not enough rows remaining
                    entry_row = rows[end_idx]
                    # Re-run helper at confirmation row to verify signal persists
                    _gl_e = _to_float(entry_row.get("goles_local", ""))
                    _gv_e = _to_float(entry_row.get("goles_visitante", ""))
                    _min_e = _to_float(entry_row.get("minuto", ""))
                    confirm_cands = _detect_xg_underperformance_trigger(rows, end_idx, _xg_bt_cfg)
                    # Check same team still qualifies at confirmation row
                    confirm_ok = any(c["team"] == team for c in confirm_cands)
                    if not confirm_ok:
                        continue  # signal broke — team no longer qualifies
                    # Update trigger data from confirmation row
                    confirm_cand = next(c for c in confirm_cands if c["team"] == team)
                    gl_i = int(_gl_e) if _gl_e is not None else gl_i
                    gv_i = int(_gv_e) if _gv_e is not None else gv_i
                    if _min_e is not None:
                        minuto = _min_e
                    xg_excess = confirm_cand["xg_excess"]
                    total_at_trigger = gl_i + gv_i
                    score_at_trigger = f"{gl_i}-{gv_i}"
                    over_field = confirm_cand["over_field"]

                # Get back odds from entry row
                back_over = _to_float(entry_row.get(over_field, "")) if over_field else None

                # SKIP: no registra apuesta si no hay cuota válida (evita won=1 con pl=-10)
                # Note: do NOT set triggered=True here; allow retry on next rows when odds appear
                if not back_over or back_over <= 1:
                    continue

                # Valid bet found — mark team as triggered to prevent duplicate bets
                triggered[team] = True

                # Team stats at entry row
                sfx = "_local" if team == "home" else "_visitante"
                sot_t = _to_float(entry_row.get(f"tiros_puerta{sfx}", ""))
                sot_int = int(sot_t) if sot_t is not None else None
                poss_t = _to_float(entry_row.get(f"posesion{sfx}", ""))
                shots_t = _to_float(entry_row.get(f"tiros{sfx}", ""))
                shots_int = int(shots_t) if shots_t is not None else None

                # Win = at least 1 more goal scored
                more_goals = ft_total > total_at_trigger

                passes_v2 = sot_int is not None and sot_int >= 2
                passes_v3 = passes_v2 and minuto < 70  # V3: V2 + entrada temprana

                _entry_idx = (ri + min_dur - 1) if min_dur > 1 else ri
                _stab_xg, _cons_xg = _count_odds_stability(rows, _entry_idx, over_field or "back_over25", back_over or 0)
                pl = round((back_over - 1) * 10 * 0.95, 2) if more_goals else -10
                pl_conservative = round((_cons_xg - 1) * 10 * 0.95, 2) if more_goals else -10
                bets.append({
                    "strategy": "xg_underperformance",
                    "match": match["name"],
                    "match_id": match["match_id"],
                    "minuto": minuto,
                    "score_at_trigger": score_at_trigger,
                    "team": team,
                    "team_xg": round(team_xg, 2),
                    "team_goals": team_goals,
                    "xg_excess": round(xg_excess, 2),
                    "back_over_odds": round(back_over, 2) if back_over else None,
                    "lay_trigger": _to_float(entry_row.get(over_field.replace("back_", "lay_"), "")) or None if over_field else None,
                    "over_line": f"Over {total_at_trigger + 0.5}",
                    "sot_team": sot_int,
                    "poss_team": round(poss_t, 1) if poss_t is not None else None,
                    "shots_team": shots_int,
                    "ft_score": ft_score,
                    "won": more_goals,
                    "pl": pl,
                    "pl_conservative": pl_conservative,
                    "conservative_odds": round(_cons_xg, 2),
                    "passes_v2": passes_v2,
                    "passes_v3": passes_v3,
                    "stability_count": _stab_xg,
                    "timestamp_utc": entry_row.get("timestamp_utc", ""),
                    "País": entry_row.get("País", "Desconocido"),
                    "Liga": entry_row.get("Liga", "Desconocida"),
                })

    def _make_summary(subset):
        n = len(subset)
        w = sum(1 for b in subset if b["won"])
        total_pl = sum(b["pl"] for b in subset)
        return {
            "bets": n, "wins": w,
            "win_pct": round(w / n * 100, 1) if n else 0,
            "pl": round(total_pl, 2),
            "roi": round(total_pl / (n * 10) * 100, 1) if n else 0,
        }

    return {
        "total_matches": matches_with_xg,
        "with_trigger": len(bets),
        "summary": {
            "base": _make_summary(bets),
            "v2": _make_summary([b for b in bets if b["passes_v2"]]),
            "v3": _make_summary([b for b in bets if b["passes_v3"]]),
        },
        "bets": bets,
    }


# ── Odds Drift Contrarian Strategy ──────────────────────────────────────

def analyze_strategy_odds_drift(min_dur: int = 1) -> dict:
    """Analyze the 'Odds Drift Contrarian' strategy across all finished matches.

    Trigger: team's back odds increase >30% within 10 min AND team is currently WINNING.
    Bet: Back that team to win (Match Odds market).
    Versions:
      - V1 (base): drift >30% + winning
      - V2: V1 + goal advantage >= 2
      - V3: V1 + drift >= 100%
      - V4: V1 + odds <= 5 + minute > 45
    """
    finished_matches = _get_all_finished_matches()
    if not finished_matches:
        return {"total_matches": 0, "with_trigger": 0, "bets": [], "summary": {}}

    DRIFT_MIN = 0.30
    LOOKBACK_MIN = 10        # Fixed lookback in minutes — matches live detect_betting_signals
    MIN_MINUTE = 0
    MAX_MINUTE = 90
    MIN_ODDS = 1.01
    MAX_ODDS = 1000.0
    COMMISSION = 0.05
    STAKE = 10
    SCORE_CONFIRM_MIN = 3    # Min captures with same score in last 6 rows — matches live

    bets = []
    total_matches = 0

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows or len(rows) < 10:
            continue

        last_row = rows[-1]
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))
        if gl_final is None or gv_final is None:
            continue
        ft_gl, ft_gv = int(gl_final), int(gv_final)
        ft_score = f"{ft_gl}-{ft_gv}"
        total_matches += 1

        # BT superset drift cfg: permissive (DRIFT_MIN=30% = base threshold)
        _drift_bt_cfg = {
            "drift_min_pct": DRIFT_MIN * 100,  # 30.0
            "lookback_min":  LOOKBACK_MIN,
            "score_confirm": SCORE_CONFIRM_MIN,
            "min_minute":    MIN_MINUTE,
            "max_minute":    MAX_MINUTE,
            "max_odds":      MAX_ODDS,
            "goal_diff_min": 0,
        }

        triggered = {"home": False, "away": False}

        for curr_ri, curr_row in enumerate(rows):
            if triggered["home"] and triggered["away"]:
                break

            # Use shared GR9 helper to check drift trigger at this row
            trig = _detect_odds_drift_trigger(rows, curr_ri, _drift_bt_cfg)
            if trig is None:
                continue

            team    = trig["team"]
            curr_min = trig["minuto"]
            odds_now = trig["odds_now"]
            odds_before = trig["odds_before"]
            drift   = trig["drift_pct"] / 100.0   # back to 0-1 scale for version flags
            gl_i    = trig["gl_i"]
            gv_i    = trig["gv_i"]
            goal_diff = trig["goal_diff"]

            if triggered[team]:
                continue

            # Min duration persistence: team must stay winning AND drift trigger
            # must persist for min_dur rows.  This mirrors LIVE behavior where
            # analytics.py's stability post-filter requires the signal to be
            # present across multiple consecutive captures before placing the bet.
            if min_dur > 1:
                confirm_idx = curr_ri + min_dur - 1
                if confirm_idx >= len(rows):
                    continue  # not enough rows remaining
                # Check team stays winning in every intermediate row
                persist_ok = True
                for pi in range(curr_ri + 1, confirm_idx + 1):
                    pr = rows[pi]
                    pg = _to_float(pr.get("goles_local" if team == "home" else "goles_visitante", ""))
                    po = _to_float(pr.get("goles_visitante" if team == "home" else "goles_local", ""))
                    if pg is None or po is None or int(pg) <= int(po):
                        persist_ok = False
                        break
                if not persist_ok:
                    continue
                # Re-verify the drift trigger at the confirmation row (like LIVE
                # stability: signal must still be present after min_dur captures).
                confirm_trig = _detect_odds_drift_trigger(rows, confirm_idx, _drift_bt_cfg)
                if confirm_trig is None or confirm_trig["team"] != team:
                    continue
                # Use confirmation row data (odds at placement time, not trigger time)
                odds_now = confirm_trig["odds_now"]
                drift = confirm_trig["drift_pct"] / 100.0
                curr_min = confirm_trig["minuto"]

            triggered[team] = True
            score_at = f"{gl_i}-{gv_i}"

            # Check if team wins the match
            if team == "home":
                won = ft_gl > ft_gv
            else:
                won = ft_gv > ft_gl

            _drift_odds_col = "back_home" if team == "home" else "back_away"
            _stab_drift, _cons_drift = _count_odds_stability(rows, curr_ri, _drift_odds_col, odds_now or 0)
            if won:
                pl = round((odds_now - 1) * STAKE * (1 - COMMISSION), 2)
                pl_conservative = round((_cons_drift - 1) * STAKE * (1 - COMMISSION), 2)
            else:
                pl = -STAKE
                pl_conservative = -STAKE

            # Stats at trigger
            sfx = "_local" if team == "home" else "_visitante"
            sot_t = _to_float(curr_row.get(f"tiros_puerta{sfx}", ""))
            poss_t = _to_float(curr_row.get(f"posesion{sfx}", ""))
            shots_t = _to_float(curr_row.get(f"tiros{sfx}", ""))

            # Version filters (pre-computed flags; filterDriftBets also applies these via raw values)
            passes_v2 = goal_diff >= 2
            passes_v3 = drift >= 1.0  # drift >= 100%
            passes_v4 = odds_now <= 5.0 and curr_min > 45
            passes_v5 = odds_now <= 5.0

            # V6: V5 + momentum gap > 200
            synth = _compute_synthetic_at_trigger(rows, curr_ri)
            mom_gap = synth.get("momentum_gap")
            passes_v6 = passes_v5 and mom_gap is not None and mom_gap > 200

            # Risk calculation
            risk_info = calculate_time_score_risk(
                strategy="odds_drift",
                minute=curr_min,
                home_score=gl_i,
                away_score=gv_i,
                dominant_team=team
            )

            _drift_lay_col = "lay_home" if team == "home" else "lay_away"
            bets.append({
                "match": match["name"],
                "match_id": match["match_id"],
                "minuto": curr_min,
                "score_at_trigger": score_at,
                "team": team,
                "goal_diff": goal_diff,
                "odds_before": round(odds_before, 2),
                "back_odds": round(odds_now, 2),
                "lay_trigger": _to_float(curr_row.get(_drift_lay_col, "")) or None,
                "drift_pct": round(drift * 100, 1),
                "sot_team": int(sot_t) if sot_t is not None else None,
                "poss_team": round(poss_t, 1) if poss_t is not None else None,
                "shots_team": int(shots_t) if shots_t is not None else None,
                "ft_score": ft_score,
                "won": won,
                "pl": pl,
                "pl_conservative": pl_conservative,
                "conservative_odds": round(_cons_drift, 2),
                "passes_v2": passes_v2,
                "passes_v3": passes_v3,
                "passes_v4": passes_v4,
                "passes_v5": passes_v5,
                "passes_v6": passes_v6,
                "synth_momentum_gap": mom_gap,
                "stability_count": _stab_drift,
                "timestamp_utc": curr_row.get("timestamp_utc", ""),
                "risk_level": risk_info["risk_level"],
                "risk_reason": risk_info["risk_reason"],
                "time_remaining": risk_info["time_remaining"],
                "deficit": risk_info["deficit"],
                "País": curr_row.get("País", "Desconocido"),
                "Liga": curr_row.get("Liga", "Desconocida"),
            })

    def _make_summary(subset):
        n = len(subset)
        w = sum(1 for b in subset if b["won"])
        total_pl = sum(b["pl"] for b in subset)
        return {
            "bets": n, "wins": w,
            "win_pct": round(w / n * 100, 1) if n else 0,
            "pl": round(total_pl, 2),
            "roi": round(total_pl / (n * 10) * 100, 1) if n else 0,
        }

    return {
        "total_matches": total_matches,
        "with_trigger": len(bets),
        "summary": {
            "v1": _make_summary(bets),
            "v2": _make_summary([b for b in bets if b["passes_v2"]]),
            "v3": _make_summary([b for b in bets if b["passes_v3"]]),
            "v4": _make_summary([b for b in bets if b["passes_v4"]]),
            "v5": _make_summary([b for b in bets if b["passes_v5"]]),
        },
        "bets": bets,
    }


# ── Cartera (Portfolio) ─────────────────────────────────────────────────

def analyze_cartera() -> dict:
    """Combined portfolio view of all strategies with flat and managed bankroll simulations."""
    import json as _json
    from api.config import load_config as _load_config
    cfg = _load_config()
    md = cfg.get("min_duration", {})

    # Manual cache key including min_duration values
    cache_key = f"cartera_{_json.dumps(md, sort_keys=True)}"
    if cache_key in _result_cache:
        return _result_cache[cache_key]

    draw_data = analyze_strategy_back_draw_00(min_dur=md.get("draw", 1))
    xg_data = analyze_strategy_xg_underperformance(min_dur=md.get("xg", 2))
    drift_data = analyze_strategy_odds_drift(min_dur=md.get("drift", 2))
    clustering_data = analyze_strategy_goal_clustering(min_dur=md.get("clustering", 4))
    pressure_data = analyze_strategy_pressure_cooker(min_dur=md.get("pressure", 2))
    tarde_asia_data = analyze_strategy_tarde_asia(min_dur=1)
    momentum_xg_v1_data = analyze_strategy_momentum_xg(version="v1", min_dur=1)
    momentum_xg_v2_data = analyze_strategy_momentum_xg(version="v2", min_dur=1)

    all_bets = []
    for b in draw_data.get("bets", []):
        all_bets.append({**b, "strategy": "back_draw_00", "strategy_label": "Back Empate"})
    for b in xg_data.get("bets", []):
        all_bets.append({**b, "strategy": "xg_underperformance", "strategy_label": "xG Underperf"})
    for b in drift_data.get("bets", []):
        all_bets.append({**b, "strategy": "odds_drift", "strategy_label": "Odds Drift"})
    for b in clustering_data.get("bets", []):
        all_bets.append({**b, "strategy": "goal_clustering", "strategy_label": "Goal Clustering"})
    for b in pressure_data.get("bets", []):
        all_bets.append({**b, "strategy": "pressure_cooker", "strategy_label": "Pressure Cooker"})
    for b in tarde_asia_data.get("bets", []):
        all_bets.append({**b, "strategy": "tarde_asia", "strategy_label": "Tarde Asia"})
    for b in momentum_xg_v1_data.get("bets", []):
        all_bets.append({**b, "strategy": "momentum_xg_v1", "strategy_label": "Momentum x xG V1"})
    for b in momentum_xg_v2_data.get("bets", []):
        all_bets.append({**b, "strategy": "momentum_xg_v2", "strategy_label": "Momentum x xG V2"})

    all_bets.sort(key=lambda x: x.get("timestamp_utc", ""))

    # Flat staking: 10 EUR per bet
    flat_cum = []
    flat_total = 0
    for b in all_bets:
        flat_total += b["pl"]
        flat_cum.append(round(flat_total, 2))

    # Managed bankroll: 500 EUR initial, 2% per bet
    initial_bankroll = 500
    pct = 0.02
    bankroll = initial_bankroll
    managed_cum = []
    managed_pls = []
    for b in all_bets:
        bet_size = round(bankroll * pct, 2)
        odds = b.get("back_draw") or b.get("back_over_odds") or b.get("over_odds") or 1
        if b["won"] and odds and odds > 1:
            profit = round((odds - 1) * bet_size * 0.95, 2)
        else:
            profit = -bet_size
        bankroll += profit
        managed_pls.append(profit)
        managed_cum.append(round(bankroll - initial_bankroll, 2))

    n = len(all_bets)
    flat_pl = round(sum(b["pl"] for b in all_bets), 2)
    managed_pl = managed_cum[-1] if managed_cum else 0

    def _strat_summary(subset):
        nn = len(subset)
        ww = sum(1 for b in subset if b["won"])
        pp = sum(b["pl"] for b in subset)
        return {"bets": nn, "wins": ww,
                "win_pct": round(ww / nn * 100, 1) if nn else 0,
                "pl": round(pp, 2),
                "roi": round(pp / (nn * 10) * 100, 1) if nn else 0}

    result = {
        "total_bets": n,
        "flat": {
            "pl": flat_pl,
            "roi": round(flat_pl / (n * 10) * 100, 1) if n else 0,
            "cumulative": flat_cum,
        },
        "managed": {
            "initial_bankroll": initial_bankroll,
            "bankroll_pct": round(pct * 100, 1),
            "final_bankroll": round(bankroll, 2),
            "pl": managed_pl,
            "roi": round(managed_pl / initial_bankroll * 100, 1) if initial_bankroll else 0,
            "cumulative": managed_cum,
        },
        "by_strategy": {
            "back_draw_00": _strat_summary([b for b in all_bets if b["strategy"] == "back_draw_00"]),
            "xg_underperformance": _strat_summary([b for b in all_bets if b["strategy"] == "xg_underperformance"]),
            "odds_drift": _strat_summary([b for b in all_bets if b["strategy"] == "odds_drift"]),
            "goal_clustering": _strat_summary([b for b in all_bets if b["strategy"] == "goal_clustering"]),
            "pressure_cooker": _strat_summary([b for b in all_bets if b["strategy"] == "pressure_cooker"]),
            "tarde_asia": _strat_summary([b for b in all_bets if b["strategy"] == "tarde_asia"]),
            "momentum_xg": _strat_summary([b for b in all_bets if b["strategy"] in ("momentum_xg_v1", "momentum_xg_v2")]),
        },
        "bets": all_bets,
    }
    _result_cache[cache_key] = result
    return result


# ── Cash-out simulation ─────────────────────────────────────────────────

_OVER_CO_COLS: dict[str, tuple[str, str]] = {
    "0.5": ("back_over05", "lay_over05"),
    "1.5": ("back_over15", "lay_over15"),
    "2.5": ("back_over25", "lay_over25"),
    "3.5": ("back_over35", "lay_over35"),
    "4.5": ("back_over45", "lay_over45"),
}


def _co_market_cols(bet: dict, strategy: str) -> tuple[str, str, float]:
    """Return (back_col, lay_col, back_odds) for the bet's market."""
    if strategy == "back_draw_00":
        return "back_draw", "lay_draw", bet.get("back_draw") or 0.0

    if strategy in ("xg_underperformance", "goal_clustering", "pressure_cooker", "tarde_asia"):
        over_line = bet.get("over_line", "")
        m = re.search(r"(\d+\.?\d+)", over_line or "")
        key = m.group(1) if m else ""
        bc, lc = _OVER_CO_COLS.get(key, ("", ""))
        return bc, lc, bet.get("back_over_odds") or 0.0

    if strategy == "odds_drift":
        team = bet.get("team", "")
        bc = "back_home" if team == "home" else "back_away"
        lc = "lay_home" if team == "home" else "lay_away"
        return bc, lc, bet.get("back_odds") or 0.0

    if strategy in ("momentum_xg_v1", "momentum_xg_v2"):
        dt = bet.get("dominant_team", "")
        bc = "back_home" if dt == "Local" else "back_away"
        lc = "lay_home" if dt == "Local" else "lay_away"
        return bc, lc, bet.get("back_odds") or 0.0

    return "", "", 0.0


def _get_trigger_score(rows: list, trigger_min: float) -> tuple:
    """Devuelve (goles_local, goles_visitante) en el CSV justo en trigger_min."""
    gl = gv = 0
    for row in rows:
        m = _to_float(row.get("minuto", ""))
        if m is not None and m <= trigger_min:
            g1 = _to_float(row.get("goles_local", ""))
            g2 = _to_float(row.get("goles_visitante", ""))
            if g1 is not None: gl = g1
            if g2 is not None: gv = g2
        else:
            break
    return gl, gv


def _is_adverse_goal(row: dict, strategy: str, team: str, gl_trigger: float, gv_trigger: float) -> bool:
    """True si en este row se ha producido un gol adverso para la apuesta.
    Solo aplica a apuestas de match odds (draw, home, away).
    Over bets: ningún gol es adverso (más goles = mejor para Over).
    """
    gl = _to_float(row.get("goles_local", "")) or 0
    gv = _to_float(row.get("goles_visitante", "")) or 0
    if strategy == "back_draw_00":
        return (gl + gv) > (gl_trigger + gv_trigger)  # cualquier gol perjudica el empate
    if strategy in ("momentum_xg_v1", "momentum_xg_v2"):
        if team == "Local": return gv > gv_trigger    # rival (visitante) marcó
        if team == "Away":  return gl > gl_trigger    # rival (local) marcó
    if strategy == "odds_drift":
        if team == "home":  return gv > gv_trigger    # visitante marcó
        if team == "away":  return gl > gl_trigger    # local marcó
    return False  # Over bets: nunca adverso


def _co_is_corrupted(row: dict, back_col: str, lay_col: str) -> bool:
    """True if row shows market suspension artifacts (inverted or extreme spread)."""
    bk = _to_float(row.get(back_col, ""))
    lk = _to_float(row.get(lay_col, ""))
    if bk is None or lk is None or bk <= 1.0 or lk <= 1.0:
        return True
    if lk < bk:
        return True  # inverted = suspension
    return (lk - bk) / bk > 0.5  # >50% spread = suspension


def _co_calc_pl(back_odds: float, lay_odds: float, stake: float = 10.0) -> float:
    """Cash-out P&L. Applies 5% Betfair commission only on profits."""
    gross = stake * (back_odds / lay_odds - 1)
    return round(gross * 0.95, 2) if gross > 0 else round(gross, 2)


def _config_label(config: dict) -> str:
    parts = []
    if config.get("cashout_lay_pct") is not None:
        parts.append(f"Fijo {config['cashout_lay_pct']}%")
    if config.get("adaptive_early_pct") is not None:
        parts.append(
            f"Adapt. {config['adaptive_early_pct']}%→{config['adaptive_late_pct']}% @{config['adaptive_split_min']}m"
        )
    if config.get("adverse_goal_stop"):
        parts.append("Gol adverso")
    if config.get("trailing_stop_pct") is not None:
        parts.append(f"Trailing {config['trailing_stop_pct']}%")
    return " + ".join(parts) if parts else "Sin CO"


def _simulate_config(
    bets: list,
    match_csv_cache: dict,
    *,
    cashout_lay_pct: float = None,
    adaptive_early_pct: float = None,
    adaptive_late_pct: float = None,
    adaptive_split_min: int = 70,
    adverse_goal_stop: bool = False,
    trailing_stop_pct: float = None,
) -> tuple:
    """Fast inner simulation loop for grid search. Uses pre-loaded CSV cache.
    Returns (pl_net, rescued_count, penalized_count, co_applied_count).
    """
    pl_total = 0.0
    rescued = penalized = co_applied = 0

    for bet in bets:
        strategy = bet.get("strategy", "")
        match_id = bet.get("match_id", "")
        trigger_min = bet.get("minuto") or 0
        original_pl = bet.get("pl", 0) or 0
        stake = bet.get("stake", 1.0) or 1.0

        back_col, lay_col, back_odds = _co_market_cols(bet, strategy)
        if not back_col or not lay_col or not back_odds:
            pl_total += original_pl
            continue

        rows = match_csv_cache.get(match_id, [])
        if not rows:
            pl_total += original_pl
            continue

        gl_trigger = gv_trigger = 0
        if adverse_goal_stop:
            gl_trigger, gv_trigger = _get_trigger_score(rows, trigger_min)
        team = bet.get("team") or bet.get("dominant_team")
        trail_min_lay = None
        best_row = None

        for row in rows:
            m = _to_float(row.get("minuto", ""))
            if m is None or m <= trigger_min:
                continue
            if _co_is_corrupted(row, back_col, lay_col):
                continue

            lay_val = _to_float(row.get(lay_col, ""))
            triggered = False

            if cashout_lay_pct is not None and lay_val:
                if lay_val >= back_odds * (1.0 + cashout_lay_pct / 100.0):
                    triggered = True

            if not triggered and adaptive_early_pct is not None and adaptive_late_pct is not None and lay_val:
                pct = adaptive_early_pct if m < adaptive_split_min else adaptive_late_pct
                if lay_val >= back_odds * (1.0 + pct / 100.0):
                    triggered = True

            if not triggered and adverse_goal_stop:
                if _is_adverse_goal(row, strategy, team, gl_trigger, gv_trigger):
                    triggered = True

            if trailing_stop_pct is not None and lay_val:
                if trail_min_lay is None or lay_val < trail_min_lay:
                    trail_min_lay = lay_val
                if not triggered:
                    if lay_val >= trail_min_lay * (1.0 + trailing_stop_pct / 100.0):
                        triggered = True

            if triggered:
                best_row = row
                break

        if best_row is None:
            pl_total += original_pl
            continue

        lay_odds = _to_float(best_row.get(lay_col, ""))
        if not lay_odds or lay_odds <= 1.0:
            pl_total += original_pl
            continue

        co_pl = _co_calc_pl(back_odds, lay_odds, stake)
        pl_total += co_pl
        co_applied += 1

        if original_pl < 0 and co_pl > original_pl:
            rescued += 1
        elif original_pl > 0 and co_pl < original_pl:
            penalized += 1

    return round(pl_total, 2), rescued, penalized, co_applied


def optimize_cashout_cartera(cartera_data: dict, top_n: int = 10) -> dict:
    """Grid search over CO modes to find best configuration.
    Reads each match CSV only once for efficiency.
    Returns top_n configs ranked by P/L net, plus other sorting options.
    """
    bets = cartera_data.get("bets", [])
    if not bets:
        return {"base_pl": 0.0, "results": []}

    # Build config grid
    configs: list[dict] = []

    # 1. Solo Fijo
    for pct in [5, 10, 15, 20, 25, 30, 40, 50]:
        configs.append({"cashout_lay_pct": pct})

    # 2. Solo Adaptativo
    for early in [15, 20, 25, 30]:
        for late in [5, 8, 12]:
            for split in [60, 70, 80]:
                configs.append({
                    "adaptive_early_pct": early,
                    "adaptive_late_pct": late,
                    "adaptive_split_min": split,
                })

    # 3. Solo Gol adverso
    configs.append({"adverse_goal_stop": True})

    # 4. Solo Trailing
    for trail in [5, 10, 15, 20, 25, 30]:
        configs.append({"trailing_stop_pct": trail})

    # 5. Gol adverso + Trailing
    for trail in [5, 10, 15, 20]:
        configs.append({"adverse_goal_stop": True, "trailing_stop_pct": trail})

    # 6. Fijo + Gol adverso
    for pct in [10, 15, 20, 25, 30]:
        configs.append({"cashout_lay_pct": pct, "adverse_goal_stop": True})

    # 7. Trailing + Fijo
    for pct in [15, 20, 25]:
        for trail in [10, 15, 20]:
            configs.append({"cashout_lay_pct": pct, "trailing_stop_pct": trail})

    # 8. Trailing + Gol adverso + Fijo
    for pct in [15, 20]:
        for trail in [10, 15]:
            configs.append({"cashout_lay_pct": pct, "adverse_goal_stop": True, "trailing_stop_pct": trail})

    # Pre-load all match CSVs (each read only once)
    match_csv_cache: dict = {}
    for bet in bets:
        match_id = bet.get("match_id", "")
        if match_id and match_id not in match_csv_cache:
            try:
                csv_path = _resolve_csv_path(match_id)
                match_csv_cache[match_id] = _read_csv_rows(csv_path)
            except Exception:
                match_csv_cache[match_id] = []

    base_pl = round(sum(b.get("pl", 0) or 0 for b in bets), 2)

    results = []
    for config in configs:
        pl_net, rescued, penalized, co_applied = _simulate_config(bets, match_csv_cache, **config)
        total_co = rescued + penalized
        rescue_ratio = round(rescued / total_co, 2) if total_co > 0 else 0.0
        results.append({
            "config": config,
            "label": _config_label(config),
            "pl_net": pl_net,
            "pl_improvement": round(pl_net - base_pl, 2),
            "rescued": rescued,
            "penalized": penalized,
            "co_applied": co_applied,
            "rescue_ratio": rescue_ratio,
        })

    results.sort(key=lambda x: x["pl_net"], reverse=True)
    return {
        "base_pl": base_pl,
        "total_configs_tested": len(configs),
        "results": results[:top_n],
    }


def simulate_cashout_cartera(
    cartera_data: dict,
    cashout_minute: int = None,
    *,
    cashout_lay_pct: float = None,
    adaptive_early_pct: float = None,
    adaptive_late_pct: float = None,
    adaptive_split_min: int = 70,
    adverse_goal_stop: bool = False,
    trailing_stop_pct: float = None,
) -> dict:
    """Apply cashout simulation to cartera data for ALL bets (winners and losers).

    cashout_minute == -1 → "Pesimista": worst lay odds in the full period
      (trigger_min, 90] — most conservative, models bad execution timing.
    cashout_minute > 0  → "Minuto": row closest to that minute (original).
    cashout_lay_pct     → "Lay%": first row where lay >= entry_back * (1 + lay_pct/100).
    adaptive_early_pct / adaptive_late_pct → "Adaptativo": threshold holgado antes de
      adaptive_split_min, ajustado después.
    adverse_goal_stop   → "Gol adverso": CO en el primer gol que perjudica la apuesta
      (solo back_draw_00, odds_drift, momentum_xg — Over bets ignoradas).
    trailing_stop_pct   → "Trailing": stop se mueve con el mínimo lay visto; dispara
      cuando lay sube trailing_stop_pct% sobre ese mínimo.

    Modos combinables: si varios están activos, gana el primero en dispararse.
    CO is applied unconditionally when triggered — no look-ahead bias.
    Winning bets where threshold is crossed will have their P/L reduced (premature exit).
    Returns a deep copy of cartera_data with modified pl values and
    recomputed cumulative arrays and strategy summaries.
    """
    import copy
    result = copy.deepcopy(cartera_data)
    bets = result.get("bets", [])
    stake = 10.0
    co_count = 0
    pessimistic = cashout_minute is not None and cashout_minute == -1

    # Determine if any new-style mode is active
    new_modes_active = (
        cashout_lay_pct is not None
        or (adaptive_early_pct is not None and adaptive_late_pct is not None)
        or adverse_goal_stop
        or trailing_stop_pct is not None
    )

    for bet in bets:

        strategy = bet.get("strategy", "")
        match_id = bet.get("match_id", "")
        trigger_min = bet.get("minuto") or 0

        back_col, lay_col, back_odds = _co_market_cols(bet, strategy)
        if not back_col or not lay_col or not back_odds:
            continue

        try:
            csv_path = _resolve_csv_path(match_id)
            rows = _read_csv_rows(csv_path)
        except Exception:
            continue
        if not rows:
            continue

        if new_modes_active:
            # Multi-mode combinable search: primero en dispararse gana
            gl_trigger, gv_trigger = _get_trigger_score(rows, trigger_min)
            team = bet.get("team") or bet.get("dominant_team")
            trail_min_lay = None
            best_row = None

            for row in rows:
                m = _to_float(row.get("minuto", ""))
                if m is None or m <= trigger_min:
                    continue
                if _co_is_corrupted(row, back_col, lay_col):
                    continue

                lay_val = _to_float(row.get(lay_col, ""))
                triggered = False

                # Modo 1: Fijo %
                if cashout_lay_pct is not None and lay_val:
                    if lay_val >= back_odds * (1.0 + cashout_lay_pct / 100.0):
                        triggered = True

                # Modo 2: Adaptativo (umbral diferente antes/después del split_min)
                if not triggered and adaptive_early_pct is not None and adaptive_late_pct is not None and lay_val:
                    pct = adaptive_early_pct if m < adaptive_split_min else adaptive_late_pct
                    if lay_val >= back_odds * (1.0 + pct / 100.0):
                        triggered = True

                # Modo 3: Gol adverso
                if not triggered and adverse_goal_stop:
                    if _is_adverse_goal(row, strategy, team, gl_trigger, gv_trigger):
                        triggered = True

                # Modo 4: Trailing stop (actualizar mínimo, luego comprobar trail)
                if trailing_stop_pct is not None and lay_val:
                    if trail_min_lay is None or lay_val < trail_min_lay:
                        trail_min_lay = lay_val
                    if not triggered:
                        trail_threshold = trail_min_lay * (1.0 + trailing_stop_pct / 100.0)
                        if lay_val >= trail_threshold:
                            triggered = True

                if triggered:
                    best_row = row
                    break

        elif pessimistic:
            # Worst lay odds (highest) in full post-signal window — conservative
            best_row = None
            worst_lay = -1.0
            for row in rows:
                m = _to_float(row.get("minuto", ""))
                if m is None or m <= trigger_min:
                    continue
                if _co_is_corrupted(row, back_col, lay_col):
                    continue
                lay_val = _to_float(row.get(lay_col, ""))
                if lay_val and lay_val > worst_lay:
                    worst_lay = lay_val
                    best_row = row
        else:
            # Closest row to cashout_minute, strictly after trigger (original)
            best_row = None
            best_dist = float("inf")
            for row in rows:
                m = _to_float(row.get("minuto", ""))
                if m is None or m <= trigger_min:
                    continue
                if _co_is_corrupted(row, back_col, lay_col):
                    continue
                dist = abs(m - cashout_minute)
                if dist < best_dist:
                    best_dist = dist
                    best_row = row

        if best_row is None:
            continue

        lay_odds = _to_float(best_row.get(lay_col, ""))
        if not lay_odds or lay_odds <= 1.0:
            continue

        co_pl = _co_calc_pl(back_odds, lay_odds, stake)
        # Apply unconditionally — threshold crossed means CO executed, regardless of outcome
        bet["pl"] = co_pl
        bet["cashout_applied"] = True
        bet["cashout_minute_actual"] = _to_float(best_row.get("minuto", ""))
        bet["cashout_lay_odds"] = round(lay_odds, 2)
        co_count += 1

    # Recompute flat cumulative
    bets.sort(key=lambda x: x.get("timestamp_utc", ""))
    flat_total = 0.0
    flat_cum = []
    for b in bets:
        flat_total += b["pl"]
        flat_cum.append(round(flat_total, 2))

    n = len(bets)
    flat_pl = round(sum(b["pl"] for b in bets), 2)
    result["flat"]["pl"] = flat_pl
    result["flat"]["roi"] = round(flat_pl / (n * stake) * 100, 1) if n else 0
    result["flat"]["cumulative"] = flat_cum

    # Recompute managed bankroll
    initial_bankroll = result["managed"].get("initial_bankroll", 500)
    pct = result["managed"].get("bankroll_pct", 2.0) / 100.0
    bankroll = initial_bankroll
    managed_cum = []
    for b in bets:
        bet_size = round(bankroll * pct, 2)
        if b.get("cashout_applied"):
            # CO takes priority over won/lost — threshold was crossed, we exited early
            profit = round(b["pl"] / stake * bet_size, 2)
        elif b.get("won", False):
            odds = b.get("back_draw") or b.get("back_over_odds") or b.get("back_odds") or 1
            profit = round((odds - 1) * bet_size * 0.95, 2) if odds and odds > 1 else -bet_size
        else:
            profit = -bet_size
        bankroll += profit
        managed_cum.append(round(bankroll - initial_bankroll, 2))

    result["managed"]["final_bankroll"] = round(bankroll, 2)
    result["managed"]["pl"] = managed_cum[-1] if managed_cum else 0
    result["managed"]["roi"] = round(
        (managed_cum[-1] if managed_cum else 0) / initial_bankroll * 100, 1
    )
    result["managed"]["cumulative"] = managed_cum

    # Recompute by_strategy summaries
    def _s(subset):
        nn = len(subset)
        ww = sum(1 for b in subset if b["won"])
        pp = sum(b["pl"] for b in subset)
        return {
            "bets": nn, "wins": ww,
            "win_pct": round(ww / nn * 100, 1) if nn else 0,
            "pl": round(pp, 2),
            "roi": round(pp / (nn * stake) * 100, 1) if nn else 0,
        }

    result["by_strategy"]["back_draw_00"] = _s([b for b in bets if b["strategy"] == "back_draw_00"])
    result["by_strategy"]["xg_underperformance"] = _s([b for b in bets if b["strategy"] == "xg_underperformance"])
    result["by_strategy"]["odds_drift"] = _s([b for b in bets if b["strategy"] == "odds_drift"])
    result["by_strategy"]["goal_clustering"] = _s([b for b in bets if b["strategy"] == "goal_clustering"])
    result["by_strategy"]["pressure_cooker"] = _s([b for b in bets if b["strategy"] == "pressure_cooker"])
    result["by_strategy"]["tarde_asia"] = _s([b for b in bets if b["strategy"] == "tarde_asia"])
    result["by_strategy"]["momentum_xg"] = _s(
        [b for b in bets if b["strategy"] in ("momentum_xg_v1", "momentum_xg_v2")]
    )

    result["cashout_mode"] = "lay_pct" if cashout_lay_pct is not None else "minute"
    result["cashout_lay_pct"] = cashout_lay_pct
    result["cashout_minute"] = cashout_minute
    result["cashout_applied_count"] = co_count
    result["cashout_mode_params"] = {
        "cashout_lay_pct": cashout_lay_pct,
        "adaptive_early_pct": adaptive_early_pct,
        "adaptive_late_pct": adaptive_late_pct,
        "adaptive_split_min": adaptive_split_min,
        "adverse_goal_stop": adverse_goal_stop,
        "trailing_stop_pct": trailing_stop_pct,
    }
    return result


# ── Signal log state (in-memory, persists across API calls within process) ──────
# Key: (match_id, strategy) → {minute, back_odds, score, timestamp}
_signal_state: dict[tuple[str, str], dict] = {}

_SIGNAL_LOG_HEADERS = [
    "event_type",
    "timestamp_utc",
    "match_id", "match_name", "match_url",
    "strategy", "strategy_name",
    "minute", "score",
    "recommendation", "back_odds", "min_odds", "expected_value",
    "confidence", "win_rate_historical", "roi_historical", "sample_size",
    "conditions",
    # Lifecycle columns (new)
    "first_detected_minute", "first_detected_odds",
    "signal_age_minutes", "odds_vs_first_pct",
]

_ODDS_CHANGE_THRESHOLD = 0.05  # 5% change triggers an odds_update event

# ── In-memory cache for signals_log first-seen timestamps ──
# Avoids re-reading the entire CSV (7k+ lines) on every detect_betting_signals call.
_first_seen_cache: dict[tuple, datetime] = {}
_first_seen_cache_loaded = False


def _load_first_seen_cache() -> dict[tuple, datetime]:
    """Load first-seen map from signals_log.csv once, then return cached version."""
    global _first_seen_cache, _first_seen_cache_loaded
    if _first_seen_cache_loaded:
        return _first_seen_cache
    log_file = Path(__file__).parent.parent.parent / "signals_log.csv"
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    mid = row.get("match_id", "").strip()
                    strat = row.get("strategy", "").strip()
                    ts = row.get("timestamp_utc", "").strip()
                    if mid and strat and ts and (mid, strat) not in _first_seen_cache:
                        try:
                            _first_seen_cache[(mid, strat)] = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            pass
        except Exception:
            pass
    _first_seen_cache_loaded = True
    return _first_seen_cache


def _update_first_seen_cache(match_id: str, strategy: str, timestamp: datetime):
    """Update in-memory cache when a new signal is written to the log."""
    key = (match_id, strategy)
    if key not in _first_seen_cache:
        _first_seen_cache[key] = timestamp


def _write_signal_log_row(row: dict):
    """Write a single row to signals_log.csv, creating headers if needed."""
    import csv as _csv
    from pathlib import Path as _Path

    log_file = _Path(__file__).parent.parent.parent / "signals_log.csv"
    file_exists = log_file.exists()

    # If file exists but uses old format (no event_type column), migrate it first
    if file_exists:
        with open(log_file, "r", encoding="utf-8") as f:
            first_line = f.readline()
        if "event_type" not in first_line:
            _migrate_signals_log(log_file)

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=_SIGNAL_LOG_HEADERS, extrasaction="ignore")
        if not log_file.exists() or not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in _SIGNAL_LOG_HEADERS})

    # Keep in-memory cache in sync
    mid = row.get("match_id", "").strip()
    strat = row.get("strategy", "").strip()
    ts_str = row.get("timestamp_utc", "").strip()
    if mid and strat and ts_str:
        try:
            _update_first_seen_cache(mid, strat, datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S"))
        except (ValueError, Exception):
            pass


def _migrate_signals_log(log_file):
    """Add new lifecycle columns to existing signals_log.csv (backward compat)."""
    import csv as _csv
    import shutil

    backup = str(log_file) + ".bak"
    shutil.copy2(log_file, backup)

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        old_rows = list(_csv.DictReader(f))

    with open(log_file, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=_SIGNAL_LOG_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for r in old_rows:
            # Map old column order: old CSV didn't have event_type as first col
            migrated = {k: r.get(k, "") for k in _SIGNAL_LOG_HEADERS}
            migrated["event_type"] = migrated.get("event_type") or "first_detection"
            writer.writerow(migrated)


def _build_log_row(signal: dict, event_type: str, state: dict | None = None) -> dict:
    """Build a log row dict from a signal and optional prior state."""
    from datetime import datetime as _dt

    match_id = signal.get("match_id", "")
    strategy = signal.get("strategy", "")
    minute = signal.get("minute", "")
    back_odds = signal.get("back_odds", "")

    first_minute = state["minute"] if state else minute
    first_odds = state["back_odds"] if state else back_odds

    try:
        age = round(float(minute) - float(first_minute), 1) if minute and first_minute else ""
    except (TypeError, ValueError):
        age = ""

    try:
        if back_odds and first_odds and float(first_odds) > 0:
            odds_pct = round((float(back_odds) / float(first_odds) - 1) * 100, 1)
        else:
            odds_pct = ""
    except (TypeError, ValueError):
        odds_pct = ""

    return {
        "event_type": event_type,
        "timestamp_utc": _dt.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "match_id": match_id,
        "match_name": signal.get("match_name", ""),
        "match_url": signal.get("match_url", ""),
        "strategy": strategy,
        "strategy_name": signal.get("strategy_name", ""),
        "minute": minute,
        "score": signal.get("score", ""),
        "recommendation": signal.get("recommendation", ""),
        "back_odds": back_odds,
        "min_odds": signal.get("min_odds", ""),
        "expected_value": signal.get("expected_value", ""),
        "confidence": signal.get("confidence", ""),
        "win_rate_historical": signal.get("win_rate_historical", ""),
        "roi_historical": signal.get("roi_historical", ""),
        "sample_size": signal.get("sample_size", ""),
        "conditions": str(signal.get("entry_conditions", "")),
        "first_detected_minute": first_minute,
        "first_detected_odds": first_odds,
        "signal_age_minutes": age,
        "odds_vs_first_pct": odds_pct,
    }


def _log_signal_to_csv(signal: dict):
    """Event-based signal logger.

    Writes a row to signals_log.csv on:
    - first_detection: first time (match_id, strategy) is seen
    - score_change:    goal scored while signal is active
    - odds_update:     back_odds moved ≥5% from last logged value
    """
    match_id = signal.get("match_id", "")
    strategy = signal.get("strategy", "")
    key = (match_id, strategy)

    current_score = str(signal.get("score", ""))
    current_odds_raw = signal.get("back_odds", "")
    try:
        current_odds = float(current_odds_raw) if current_odds_raw else None
    except (TypeError, ValueError):
        current_odds = None

    if key not in _signal_state:
        # First detection
        row = _build_log_row(signal, "first_detection", state=None)
        _write_signal_log_row(row)
        _signal_state[key] = {
            "minute": signal.get("minute", ""),
            "back_odds": current_odds_raw,
            "score": current_score,
        }
        return

    prev = _signal_state[key]
    prev_score = prev.get("score", "")
    prev_odds_raw = prev.get("back_odds", "")
    try:
        prev_odds = float(prev_odds_raw) if prev_odds_raw else None
    except (TypeError, ValueError):
        prev_odds = None

    # Check for score change (goal)
    if current_score != prev_score:
        row = _build_log_row(signal, "score_change", state=prev)
        _write_signal_log_row(row)
        _signal_state[key] = {
            "minute": signal.get("minute", ""),
            "back_odds": current_odds_raw,
            "score": current_score,
        }
        return

    # Check for significant odds movement (≥5%)
    if current_odds and prev_odds and prev_odds > 0:
        change = abs(current_odds / prev_odds - 1)
        if change >= _ODDS_CHANGE_THRESHOLD:
            row = _build_log_row(signal, "odds_update", state=prev)
            _write_signal_log_row(row)
            _signal_state[key] = {
                "minute": _signal_state[key]["minute"],  # keep first_detected_minute reference
                "back_odds": current_odds_raw,
                "score": current_score,
            }


def _log_signal_ends(current_signal_keys: set[tuple[str, str]]):
    """Log signal_end for signals that were active last call but are gone now."""
    from datetime import datetime as _dt

    gone_keys = set(_signal_state.keys()) - current_signal_keys
    for key in gone_keys:
        prev = _signal_state.pop(key)
        match_id, strategy = key
        # Build a minimal end-signal row from stored state
        end_row = {
            "event_type": "signal_end",
            "timestamp_utc": _dt.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "match_id": match_id,
            "match_name": "",
            "match_url": "",
            "strategy": strategy,
            "strategy_name": "",
            "minute": prev.get("minute", ""),
            "score": prev.get("score", ""),
            "recommendation": "",
            "back_odds": prev.get("back_odds", ""),
            "first_detected_minute": prev.get("minute", ""),
            "first_detected_odds": prev.get("back_odds", ""),
            "signal_age_minutes": "",
            "odds_vs_first_pct": "",
        }
        _write_signal_log_row(end_row)


def detect_betting_signals(versions: dict | None = None) -> dict:
    """
    Detect live betting opportunities based on portfolio strategies.

    Args:
        versions: Dict with version per strategy, e.g.:
            {"draw": "v2r", "xg": "v2", "drift": "v1", "clustering": "v2", "pressure": "v1"}
            Version "off" disables that strategy. None = default versions.
    """
    if versions is None:
        versions = {"draw": "v2r", "xg": "v3", "drift": "v1", "clustering": "v2", "pressure": "v1"}

    # --- Minimum duration config (from historical duration analysis) ---
    # Recommended minimums: draw=1 (no benefit), xg=2, drift=2, clustering=4, pressure=2, momentum=1
    _DEFAULT_MIN_DUR = {"draw": 1, "xg": 2, "drift": 2, "clustering": 4, "pressure": 2, "momentum": 1, "tarde_asia": 1}
    min_dur_map = {
        family: int(versions.get(f"{family}_min_dur", _DEFAULT_MIN_DUR[family]))
        for family in _DEFAULT_MIN_DUR
    }
    # SD min_duration: read from full min_duration dict passed by analytics.py
    _full_min_dur = versions.get("_min_duration", {})
    for _md_key, _md_val in _full_min_dur.items():
        if _md_key.startswith("sd_") and _md_key not in min_dur_map:
            min_dur_map[_md_key] = int(_md_val)

    # --- Strategy thresholds from cartera_config (single source of truth) ---
    # These flow from analytics.py → here, ensuring live detector == historical analysis.
    _drift_base_pct     = float(versions.get("drift_threshold", 30))       # cartera.ts default: 30%
    _drift_odds_max     = float(versions.get("drift_odds_max", 999))        # cartera.ts v1 default: Infinity
    _drift_goal_diff_min = int(versions.get("drift_goal_diff_min", 0))      # cartera.ts v1 default: 0
    _drift_minute_min   = int(versions.get("drift_minute_min", 0))          # cartera.ts v1 default: 0
    _drift_minute_max   = int(versions.get("drift_minute_max", 90))         # cartera.ts v1 default: 90 (no filter)
    _drift_mom_gap_min  = float(versions.get("drift_mom_gap_min", 0))       # cartera.ts v6 default: 200
    _clustering_min_max = int(versions.get("clustering_minute_max", 90))    # default: 90 (no filter; config overrides)
    _clustering_xg_rem  = float(versions.get("clustering_xg_rem_min", 0))  # default: 0 (no filter; config overrides)
    _clustering_sot     = int(versions.get("clustering_sot_min", 3))        # default: 3 (original)
    _xg_minute_max      = int(versions.get("xg_minute_max", 90))            # default: 90 (no filter; config overrides)
    _xg_sot_min         = int(versions.get("xg_sot_min", 0))               # default: 0 (no filter)
    _xg_excess_min      = float(versions.get("xg_xg_excess_min", 0.5))     # default: 0.5 (original)
    _draw_xg_max        = float(versions.get("draw_xg_max", 1.0))           # cartera.ts v2r default: 0.6
    _draw_poss_max      = float(versions.get("draw_poss_max", 100))         # cartera.ts v2r default: 20
    _draw_shots_max     = float(versions.get("draw_shots_max", 20))         # cartera.ts v2r default: 8
    _draw_minute_min    = int(versions.get("draw_minute_min", 30))          # default 30 (strategy intrinsic min)
    _draw_minute_max    = int(versions.get("draw_minute_max", 90))
    _xg_minute_min      = int(versions.get("xg_minute_min", 0))
    _clustering_min_min = int(versions.get("clustering_minute_min", 0))
    _pressure_minute_min = int(versions.get("pressure_minute_min", 0))
    _pressure_minute_max = int(versions.get("pressure_minute_max", 90))
    _pressure_xg_sum_min = float(versions.get("pressure_xg_sum_min", 0))
    _momentum_minute_min = int(versions.get("momentum_minute_min", 0))
    _momentum_minute_max = int(versions.get("momentum_minute_max", 90))

    # --- Load first-seen timestamps from in-memory cache (loaded once from signals_log.csv) ---
    first_seen_map = _load_first_seen_cache()

    def _get_strategy_family(strategy_key: str) -> str:
        # SD strategies: use their own key for min_duration lookup
        if strategy_key.startswith("sd_"):
            return strategy_key
        if "draw" in strategy_key:
            return "draw"
        if "momentum" in strategy_key:
            return "momentum"
        if "xg" in strategy_key or "underperformance" in strategy_key:
            return "xg"
        if "drift" in strategy_key:
            return "drift"
        if "clustering" in strategy_key:
            return "clustering"
        if "pressure" in strategy_key:
            return "pressure"
        if "tarde_asia" in strategy_key:
            return "tarde_asia"
        return "draw"

    # Strategy metadata (from historical backtesting in cartera_final.md)
    STRATEGY_META = {
        "back_draw_00": {
            "win_rate": 0.571,  # 57.1% from backtest
            "avg_odds": 6.5,    # Average back draw odds
            "roi": 0.502,       # 50.2% ROI
            "sample_size": 7,
            "description": "Partidos trabados sin goles ni ocasiones"
        },
        "xg_underperformance": {
            "win_rate": 0.727,  # 72.7% from backtest
            "avg_odds": 2.2,    # Average over odds
            "roi": 0.247,       # 24.7% ROI
            "sample_size": 11,
            "description": "Equipo perdiendo pero atacando intensamente"
        },
        "odds_drift_contrarian": {
            "win_rate": 0.667,  # 66.7% from backtest
            "avg_odds": 2.5,    # Average odds
            "roi": 1.423,       # 142.3% ROI
            "sample_size": 27,
            "description": "Mercado abandona al equipo ganador erróneamente"
        },
        "goal_clustering": {
            "win_rate": 0.750,  # 75.0% from backtest
            "avg_odds": 2.3,    # Average over odds
            "roi": 0.727,       # 72.7% ROI
            "sample_size": 44,
            "description": "Después de un gol, alta probabilidad de más goles"
        },
        "pressure_cooker": {
            "win_rate": 0.812,  # 81.2% from backtest (empates 1-1+)
            "avg_odds": 2.1,    # Average over odds
            "roi": 0.819,       # 81.9% ROI
            "sample_size": 16,
            "description": "Empates con goles (1-1+) entre min 65-75 tienden a romper"
        },
        "momentum_xg": {
            "win_rate": 0.667,  # 66.7% from backtest (Ultra Relajadas)
            "avg_odds": 2.4,    # Average back odds for dominant team
            "roi": 0.522,       # 52.2% ROI
            "sample_size": 12,
            "description": "Equipo dominante (SoT ratio >1.1x) con xG no convertido tiende a ganar"
        }
    }

    def calculate_min_odds(win_rate: float) -> float:
        """Calculate minimum profitable odds based on win rate (break-even + margin)."""
        if win_rate <= 0:
            return 999.0
        # Break-even odds = 1 / win_rate
        # Add 10% margin for commission (5%) + variance
        return (1.0 / win_rate) * 1.10

    def calculate_ev(odds: float, win_rate: float, stake: float = 10.0) -> float:
        """Calculate expected value considering 5% commission."""
        if odds is None or odds <= 1.0:
            return 0.0
        profit_if_win = (odds - 1.0) * stake * 0.95  # 5% commission
        loss_if_lose = stake
        ev = (win_rate * profit_if_win) - ((1 - win_rate) * loss_if_lose)
        return ev

    def is_odds_favorable(current_odds: float, min_odds: float) -> bool:
        """Check if current odds meet minimum threshold."""
        if current_odds is None or min_odds is None:
            return False
        return current_odds >= min_odds

    def _extract_bet_market(recommendation: str) -> tuple[str, str] | None:
        """Extract (market_group, outcome) from a recommendation string.

        Returns e.g. ("match_odds", "DRAW") or ("over_under", "OVER"),
        or None if not parseable.
        """
        rec = recommendation.upper().strip()
        if rec.startswith("BACK DRAW"):
            return ("match_odds", "DRAW")
        elif rec.startswith("BACK HOME"):
            return ("match_odds", "HOME")
        elif rec.startswith("BACK AWAY"):
            return ("match_odds", "AWAY")
        elif "OVER" in rec:
            return ("over_under", "OVER")
        elif "UNDER" in rec:
            return ("over_under", "UNDER")
        return None

    # HOME↔AWAY reversals are allowed (historically profitable: +175 EUR on 10 pairs, 80% net+)
    # DRAW vs HOME/AWAY are blocked (fundamentally contradictory)
    # OVER vs UNDER are blocked (mutually exclusive)
    _REVERSAL_ALLOWED = {("HOME", "AWAY"), ("AWAY", "HOME")}

    def _has_conflict(match_id: str, recommendation: str,
                      match_outcomes: dict[str, dict[str, str]]) -> str | None:
        """Check if a signal conflicts with an existing bet on the same match.

        Returns a description of the conflict, or None if no conflict.
        HOME↔AWAY reversals are allowed (Odds Drift pattern).
        """
        market = _extract_bet_market(recommendation)
        if market is None:
            return None
        group, outcome = market
        existing = match_outcomes.get(match_id, {})
        if group in existing and existing[group] != outcome:
            pair = (existing[group], outcome)
            if pair in _REVERSAL_ALLOWED:
                return None  # HOME↔AWAY reversal — allowed
            return f"Conflicto: ya existe {existing[group]} en {group}, nueva señal es {outcome}"
        return None

    def _register_outcome(match_id: str, recommendation: str,
                          match_outcomes: dict[str, dict[str, str]]) -> None:
        """Register a bet outcome so future signals can check for conflicts."""
        market = _extract_bet_market(recommendation)
        if market is None:
            return
        group, outcome = market
        if match_id not in match_outcomes:
            match_outcomes[match_id] = {}
        match_outcomes[match_id][group] = outcome

    games = load_games()
    live_matches = [g for g in games if g["status"] == "live"]

    # Load placed bets to exclude already-bet signals
    placed_bets_keys: set[tuple[str, str]] = set()
    # Track bet outcomes per match for conflict detection
    match_outcomes: dict[str, dict[str, str]] = {}
    try:
        placed_csv = Path(__file__).parent.parent.parent.parent / "placed_bets.csv"
        if placed_csv.exists():
            with open(placed_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    mid = row.get("match_id", "").strip()
                    strat = row.get("strategy", "").strip()
                    rec = row.get("recommendation", "").strip()
                    status = row.get("status", "").strip().lower()
                    if mid and strat:
                        placed_bets_keys.add((mid, strat))
                    # Only track outcomes for active (pending) bets
                    if mid and rec and status in ("pending", ""):
                        _register_outcome(mid, rec, match_outcomes)
    except Exception:
        pass

    signals = []

    for match in live_matches:
        match_id = match["match_id"]
        csv_path = _resolve_csv_path(match_id)

        if not csv_path.exists():
            continue

        rows = _read_csv_rows(csv_path)
        if not rows:
            continue

        # Get latest capture
        latest = rows[-1]

        minuto = _to_float(latest.get("minuto", ""))
        if minuto is None:
            continue

        _raw_gl = _to_float(latest.get("goles_local", ""))
        _raw_gv = _to_float(latest.get("goles_visitante", ""))
        goals_data_ok = _raw_gl is not None and _raw_gv is not None
        goles_local = _raw_gl if _raw_gl is not None else 0
        goles_visitante = _raw_gv if _raw_gv is not None else 0
        xg_local = _to_float(latest.get("xg_local", ""))
        xg_visitante = _to_float(latest.get("xg_visitante", ""))
        posesion_local = _to_float(latest.get("posesion_local", ""))
        posesion_visitante = _to_float(latest.get("posesion_visitante", ""))
        tiros_local = _to_float(latest.get("tiros_local", "")) or 0
        tiros_visitante = _to_float(latest.get("tiros_visitante", "")) or 0
        tiros_puerta_local = _to_float(latest.get("tiros_puerta_local", "")) or 0
        tiros_puerta_visitante = _to_float(latest.get("tiros_puerta_visitante", "")) or 0
        back_draw = _to_float(latest.get("back_draw", ""))
        back_home = _to_float(latest.get("back_home", ""))
        back_away = _to_float(latest.get("back_away", ""))

        draw_ver = versions.get("draw", "v2r")
        xg_ver = versions.get("xg", "v2")
        drift_ver = versions.get("drift", "v1")
        clustering_ver = versions.get("clustering", "v2")
        pressure_ver = versions.get("pressure", "v1")

        # === STRATEGY 1: Back Empate (version-specific conditions) ===
        # goals_data_ok guards against scraper not capturing goal data (None→0 would cause false 0-0 triggers)
        # _draw_minute_min is configurable (default 30 = strategy intrinsic minimum)
        # NOTE: xg_local/xg_visitante may be None for leagues without xG coverage.
        # _filter_draw in optimize.py silently passes bets with null xG (short-circuit in xg_max check).
        # We mirror that behavior here: null xG is treated as passing the xG filter (no disqualification).
        if draw_ver != "off" and (minuto >= _draw_minute_min and
            goals_data_ok and
            goles_local == 0 and goles_visitante == 0):

            # xg_total: None if xG data unavailable (league without xG coverage).
            # _filter_draw behavior: null xG passes the xg_max filter (short-circuit).
            # Mirror that here: treat None xG as passing (matches _filter_draw null-xG behavior).
            xg_total = (xg_local + xg_visitante) if (xg_local is not None and xg_visitante is not None) else None
            tiros_total = tiros_local + tiros_visitante
            poss_diff = abs((posesion_local or 50) - (posesion_visitante or 50))

            # Version-specific filters via shared GR9 helper
            # Uses config-level thresholds (single source of truth from cartera_config).
            # Sentinel values: xg_max>=1.0=off, poss_max>=100=off, shots_max>=20=off.
            xg_dom_live = (xg_local / xg_total) if xg_total and xg_total > 0 else None
            _live_opta_gap = None  # opta data not available in live (not scraped in real-time)
            _draw_flags = _detect_draw_filters(
                xg_total=xg_total,
                poss_diff=poss_diff,
                shots_total=float(tiros_total),
                opta_gap=_live_opta_gap,
                xg_dom=xg_dom_live,
                synth_pressure_v=None,  # synth not computed in LIVE path (performance)
                cfg={"xg_max": _draw_xg_max, "poss_max": _draw_poss_max, "shots_max": _draw_shots_max},
            )

            thresholds = {}
            if _draw_xg_max   < 1.0:  thresholds["xg_total"]       = f"< {_draw_xg_max}"
            if _draw_poss_max < 100:  thresholds["possession_diff"] = f"< {_draw_poss_max}%"
            if _draw_shots_max < 20:  thresholds["total_shots"]     = f"< {_draw_shots_max}"

            passes = True
            if draw_ver == "v1":
                pass  # No extra filters
            elif draw_ver == "v15":
                passes = _draw_flags["passes_v15"]
            elif draw_ver in ("v2r", "v2"):
                passes = _draw_flags["passes_v2r"]
            elif draw_ver == "v3":
                passes = _draw_flags["passes_v3"]
                thresholds["xg_dominance"] = "> 55% o < 45%"
            elif draw_ver == "v4":
                passes = _draw_flags["passes_v4"]
                thresholds["opta_gap"] = "<= 10"

            # minuteMax gate (upper bound — configurable, default: no limit)
            if passes and _draw_minute_max < 90 and minuto >= _draw_minute_max:
                passes = False

            if passes and back_draw is not None:
                meta = STRATEGY_META["back_draw_00"]
                min_odds = calculate_min_odds(meta["win_rate"])
                ev = calculate_ev(back_draw, meta["win_rate"])
                odds_ok = is_odds_favorable(back_draw, min_odds)

                signal = {
                    "match_id": match_id,
                    "match_name": match["name"],
                    "match_url": match["url"],
                    "strategy": f"back_draw_00_{draw_ver}",
                    "strategy_name": f"Back Empate 0-0 ({draw_ver.upper()})",
                    "minute": int(minuto),
                    "score": f"{int(goles_local)}-{int(goles_visitante)}",
                    "recommendation": f"BACK DRAW @ {back_draw:.2f}" if back_draw else "BACK DRAW",
                    "back_odds": back_draw,
                    "min_odds": round(min_odds, 2),
                    "expected_value": round(ev, 2),
                    "odds_favorable": odds_ok,
                    "confidence": "high" if odds_ok else "medium",
                    "win_rate_historical": round(meta["win_rate"] * 100, 1),
                    "roi_historical": round(meta["roi"] * 100, 1),
                    "sample_size": meta["sample_size"],
                    "description": meta["description"],
                    "entry_conditions": {
                        "xg_total": round(xg_total, 2) if xg_total is not None else None,
                        "possession_diff": round(poss_diff, 1),
                        "total_shots": int(tiros_total)
                    },
                    "thresholds": thresholds or {"version": draw_ver}
                }
                if (match_id, signal["strategy"]) not in placed_bets_keys:
                    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                    if conflict:
                        signal["blocked"] = conflict
                    else:
                        signals.append(signal)
                        _log_signal_to_csv(signal)
                        _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 2: xG Underperformance (version-specific) ===
        # Skip if match has corrupted Over/Under odds
        # Use shared GR9 helper to detect underperforming teams. The helper handles:
        #   - null xG check, losing team check, xg_excess threshold, sot_min, minute gate
        # Version-specific cfg is built from cartera_config values (_xg_* vars).
        if match_id not in CORRUPTED_OVER_MATCHES and xg_ver != "off":
            # Build version-specific cfg for the helper
            if xg_ver == "v3":
                _xg_live_cfg = {
                    "xg_excess_min": _xg_excess_min,
                    "sot_min":       max(2, _xg_sot_min),
                    "minute_max":    _xg_minute_max if _xg_minute_max < 90 else 70,
                    "minute_min":    max(15, _xg_minute_min),
                }
            elif xg_ver == "v2":
                _xg_live_cfg = {
                    "xg_excess_min": _xg_excess_min,
                    "sot_min":       max(2, _xg_sot_min),
                    "minute_max":    _xg_minute_max,
                    "minute_min":    max(15, _xg_minute_min),
                }
            else:  # "base"
                _xg_live_cfg = {
                    "xg_excess_min": _xg_excess_min,
                    "sot_min":       _xg_sot_min,
                    "minute_max":    _xg_minute_max,
                    "minute_min":    max(15, _xg_minute_min),
                }

            xg_candidates = _detect_xg_underperformance_trigger(rows, len(rows) - 1, _xg_live_cfg)

            for cand in xg_candidates:
                team_label  = cand["team"].capitalize()   # "home" → "Home"
                xg_excess   = cand["xg_excess"]
                sot_team    = cand["sot_team"]
                over_field  = cand["over_field"]
                over_odds   = cand["back_over"]
                total_goles = cand["total_goals"]
                over_line   = total_goles + 0.5

                if over_odds is None:
                    continue  # No signal without odds data

                xg_thresholds = {"xg_excess": f">= {_xg_excess_min}"}
                if xg_ver in ("v2", "v3"):
                    xg_thresholds["shots_on_target"] = f">= {_xg_live_cfg['sot_min']}"
                if xg_ver == "v3":
                    xg_thresholds["minute"] = f"< {_xg_live_cfg['minute_max']}"

                meta = STRATEGY_META["xg_underperformance"]
                min_odds = calculate_min_odds(meta["win_rate"])
                ev = calculate_ev(over_odds, meta["win_rate"])
                odds_ok = is_odds_favorable(over_odds, min_odds)
                signal = {
                    "match_id": match_id,
                    "match_name": match["name"],
                    "match_url": match["url"],
                    "strategy": f"xg_underperformance_{xg_ver}",
                    "strategy_name": f"xG Underperformance ({xg_ver.upper()})",
                    "minute": int(minuto),
                    "score": f"{int(goles_local)}-{int(goles_visitante)}",
                    "recommendation": f"BACK Over {over_line}",
                    "back_odds": round(over_odds, 2) if over_odds else None,
                    "min_odds": round(min_odds, 2),
                    "expected_value": round(ev, 2) if ev is not None else None,
                    "odds_favorable": odds_ok,
                    "confidence": "high" if odds_ok else ("medium" if odds_ok is None else "low"),
                    "win_rate_historical": round(meta["win_rate"] * 100, 1),
                    "roi_historical": round(meta["roi"] * 100, 1),
                    "sample_size": meta["sample_size"],
                    "description": meta["description"],
                    "entry_conditions": {
                        "team": team_label,
                        "xg_excess": round(xg_excess, 2),
                        "shots_on_target": int(sot_team)
                    },
                    "thresholds": xg_thresholds
                }
                if (match_id, signal["strategy"]) not in placed_bets_keys:
                    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                    if conflict:
                        signal["blocked"] = conflict
                    else:
                        signals.append(signal)
                        _log_signal_to_csv(signal)
                        _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 3: Odds Drift Contrarian (version-specific) ===
        # Use shared GR9 helper _detect_odds_drift_trigger to evaluate all conditions at latest row.
        # The helper handles: min_minute, max_minute, score_confirm, lookback, same-score check,
        # drift calculation, max_odds, goal_diff_min.
        if drift_ver != "off":
            _drift_live_cfg = {
                "drift_min_pct":  _drift_base_pct,
                "lookback_min":   10,
                "score_confirm":  3,
                "min_minute":     _drift_minute_min,
                "max_minute":     _drift_minute_max,
                "max_odds":       _drift_odds_max,
                "goal_diff_min":  _drift_goal_diff_min,
            }
            drift_trig = _detect_odds_drift_trigger(rows, len(rows) - 1, _drift_live_cfg)

            if drift_trig is not None:
                team_label  = drift_trig["team"].capitalize()   # "home" → "Home"
                odds_before = drift_trig["odds_before"]
                odds_now    = drift_trig["odds_now"]
                drift_pct_val = drift_trig["drift_pct"]
                goal_diff   = drift_trig["goal_diff"]

                # Version-specific additional filters (applied after base drift check)
                drift_passes = True
                drift_thresholds = {"drift_pct": f">= {_drift_base_pct:.0f}%"}
                if drift_ver == "v1":
                    pass  # base drift only; goal_diff_min and max_odds already handled by helper
                elif drift_ver == "v2":
                    drift_passes = goal_diff >= 2
                    drift_thresholds["goal_diff"] = ">= 2"
                elif drift_ver == "v3":
                    drift_passes = drift_pct_val >= 100
                    drift_thresholds["drift_pct"] = ">= 100%"
                elif drift_ver == "v4":
                    drift_passes = minuto > 45 and odds_now <= 5.0
                    drift_thresholds["minute"] = "> 45"
                    drift_thresholds["odds"] = "<= 5.0"
                elif drift_ver == "v5":
                    drift_passes = odds_now <= 5.0
                    drift_thresholds["odds"] = "<= 5.0"
                elif drift_ver == "v6":
                    drift_passes = odds_now <= 5.0
                    drift_thresholds["odds"] = "<= 5.0"
                    if drift_passes and _drift_mom_gap_min > 0:
                        _synth_v6 = _compute_synthetic_at_trigger(rows, len(rows) - 1)
                        _mom_gap_v6 = _synth_v6.get("momentum_gap")
                        drift_passes = _mom_gap_v6 is not None and _mom_gap_v6 >= _drift_mom_gap_min
                        drift_thresholds["mom_gap"] = f">= {_drift_mom_gap_min:.0f}"

                if drift_passes:
                    meta = STRATEGY_META["odds_drift_contrarian"]
                    min_odds = calculate_min_odds(meta["win_rate"])
                    ev = calculate_ev(odds_now, meta["win_rate"])
                    odds_ok = is_odds_favorable(odds_now, min_odds)

                    # Calcular riesgo por tiempo + marcador
                    risk_info = calculate_time_score_risk(
                        strategy=f"odds_drift_{drift_ver}",
                        minute=minuto,
                        home_score=int(goles_local),
                        away_score=int(goles_visitante),
                        dominant_team=team_label
                    )

                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": f"odds_drift_contrarian_{drift_ver}",
                        "strategy_name": f"Odds Drift Contrarian ({drift_ver.upper()})",
                        "minute": int(minuto),
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "recommendation": f"BACK {team_label.upper()} @ {odds_now:.2f}",
                        "back_odds": odds_now,
                        "min_odds": round(min_odds, 2),
                        "expected_value": round(ev, 2),
                        "odds_favorable": odds_ok,
                        "confidence": "high" if odds_ok else "medium",
                        "win_rate_historical": round(meta["win_rate"] * 100, 1),
                        "roi_historical": round(meta["roi"] * 100, 1),
                        "sample_size": meta["sample_size"],
                        "description": meta["description"],
                        "entry_conditions": {
                            "team": team_label,
                            "odds_before": round(odds_before, 2),
                            "odds_now": round(odds_now, 2),
                            "drift_pct": round(drift_pct_val, 1)
                        },
                        "thresholds": drift_thresholds,
                        "risk_info": risk_info
                    }
                    if (match_id, signal["strategy"]) not in placed_bets_keys:
                        conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                        if conflict:
                            signal["blocked"] = conflict
                        # Block signals with time/score risk
                        elif risk_info["risk_level"] != "none":
                            signal["blocked"] = f"Riesgo {risk_info['risk_level']}: {risk_info['risk_reason']}"
                        else:
                            signals.append(signal)
                            _log_signal_to_csv(signal)
                            _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 4: Goal Clustering (version-specific) ===
        # Skip if match has corrupted Over/Under odds
        # Uses _detect_goal_clustering_trigger (GR9 shared helper) for consistent BT/LIVE logic.
        _cluster_min = max(15, _clustering_min_min)
        # entry_buffer: allows the trigger to keep firing past max_minute so the signal
        # can mature before the window closes. Formula: live_min_dur + PAPER_REACTION_DELAY(1) + 2.
        # The GOAL must still occur within max_minute; only the current-row check is relaxed.
        # With min_duration_live.clustering=1: buffer=1+3=4 → window extends to minuteMax+4.
        _cl_entry_buffer = int(versions.get("clustering_min_dur", 4)) + 3
        _cl_live_cfg = {
            "sot_min":      _clustering_sot,
            "min_minute":   _cluster_min,
            "max_minute":   _clustering_min_max,
            "entry_buffer": _cl_entry_buffer,
            "xg_rem_min":   _clustering_xg_rem,
        }
        if match_id not in CORRUPTED_OVER_MATCHES and clustering_ver != "off":
            cl_trig = _detect_goal_clustering_trigger(rows, len(rows) - 1, _cl_live_cfg)
            if cl_trig is not None:
                cl_over_odds = _to_float(latest.get(cl_trig["over_field"], ""))
                if cl_over_odds is not None:
                    total_actual = cl_trig["total_goals"]
                    over_line    = total_actual + 0.5

                    meta     = STRATEGY_META["goal_clustering"]
                    min_odds = calculate_min_odds(meta["win_rate"])
                    cl_ev    = calculate_ev(cl_over_odds, meta["win_rate"])
                    cl_odds_ok = is_odds_favorable(cl_over_odds, min_odds)

                    cl_thresholds = {"minute_range": f"{_cluster_min}-{int(_clustering_min_max)}"}
                    if _clustering_sot > 0:
                        cl_thresholds["sot_max"] = f">= {_clustering_sot}"
                    if _clustering_min_max < 90:
                        cl_thresholds["minute"] = f"< {int(_clustering_min_max)}"

                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": f"goal_clustering_{clustering_ver}",
                        "strategy_name": f"Goal Clustering ({clustering_ver.upper()})",
                        "minute": int(minuto),
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "recommendation": f"BACK Over {over_line}",
                        "back_odds": round(cl_over_odds, 2),
                        "min_odds": round(min_odds, 2),
                        "expected_value": round(cl_ev, 2) if cl_ev is not None else None,
                        "odds_favorable": cl_odds_ok,
                        "confidence": "high" if cl_odds_ok else ("medium" if cl_odds_ok is None else "low"),
                        "win_rate_historical": round(meta["win_rate"] * 100, 1),
                        "roi_historical": round(meta["roi"] * 100, 1),
                        "sample_size": meta["sample_size"],
                        "description": meta["description"],
                        "entry_conditions": {
                            "goal_minute": cl_trig["goal_minute"],
                            "sot_max":     cl_trig["sot_max"],
                            "total_goals": total_actual,
                        },
                        "thresholds": cl_thresholds,
                    }
                    if (match_id, signal["strategy"]) not in placed_bets_keys:
                        conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                        if conflict:
                            signal["blocked"] = conflict
                        else:
                            signals.append(signal)
                            _log_signal_to_csv(signal)
                            _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 5: Pressure Cooker (version-specific) ===
        # Skip if match has corrupted Over/Under odds
        # Uses _detect_pressure_cooker_trigger (GR9 shared helper) for consistent BT/LIVE logic.
        _press_min = _pressure_minute_min if _pressure_minute_min > 0 else 65
        _press_max = _pressure_minute_max if _pressure_minute_max < 90 else 75
        _pc_live_cfg = {
            "min_minute":    _press_min,
            "max_minute":    _press_max,
            "score_confirm": 2,
            "xg_sum_min":    _pressure_xg_sum_min,
        }
        if match_id not in CORRUPTED_OVER_MATCHES and pressure_ver != "off":
            pc_trig = _detect_pressure_cooker_trigger(rows, len(rows) - 1, _pc_live_cfg)
            if pc_trig is not None:
                over_odds = _to_float(latest.get(pc_trig["over_field"], ""))
                if over_odds is None:
                    pass  # No signal without odds data
                else:
                    total_goals = pc_trig["total_goals"]
                    meta     = STRATEGY_META["pressure_cooker"]
                    min_odds = calculate_min_odds(meta["win_rate"])

                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": f"pressure_cooker_{pressure_ver}",
                        "strategy_name": f"Pressure Cooker ({pressure_ver.upper()})",
                        "minute": int(minuto),
                        "score": f"{pc_trig['gl']}-{pc_trig['gv']}",
                        "recommendation": f"BACK Over {total_goals + 0.5}",
                        "back_odds": round(over_odds, 2),
                        "min_odds": round(min_odds, 2),
                        "expected_value": round(calculate_ev(over_odds, meta["win_rate"]), 2),
                        "odds_favorable": is_odds_favorable(over_odds, min_odds),
                        "confidence": "medium",  # EN PRUEBA - muestra insuficiente
                        "win_rate_historical": round(meta["win_rate"] * 100, 1),
                        "roi_historical": round(meta["roi"] * 100, 1),
                        "sample_size": meta["sample_size"],
                        "description": meta["description"],
                        "entry_conditions": {
                            "score":       f"{pc_trig['gl']}-{pc_trig['gv']}",
                            "total_goals": total_goals,
                            "over_odds":   round(over_odds, 2),
                        },
                        "thresholds": {
                            "minute_range": f"{int(_press_min)}-{int(_press_max)}",
                            "min_score":    "1-1+",
                        },
                    }
                    if (match_id, signal["strategy"]) not in placed_bets_keys:
                        conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                        if conflict:
                            signal["blocked"] = conflict
                        else:
                            signals.append(signal)
                            _log_signal_to_csv(signal)
                            _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 6: Momentum Dominante x xG ===
        momentum_ver = versions.get("momentum", "v1")
        if momentum_ver != "off" and xg_local is not None and xg_visitante is not None:
            # Config según versión (keys aligned with _detect_momentum_dominant signature)
            if momentum_ver == "v2":
                mom_cfg = {"sot_min": 1, "sot_ratio_min": 1.05, "xg_underperf_min": 0.1,
                           "min_m": 5, "max_m": 85, "min_odds": 1.3, "max_odds": 8.0,
                           # legacy keys kept for threshold labels in signal output
                           "ratio": 1.05, "xg": 0.1, "odds_min": 1.3, "odds_max": 8.0}
            else:  # v1
                mom_cfg = {"sot_min": 1, "sot_ratio_min": 1.1, "xg_underperf_min": 0.15,
                           "min_m": 10, "max_m": 80, "min_odds": 1.4, "max_odds": 6.0,
                           # legacy keys kept for threshold labels in signal output
                           "ratio": 1.1, "xg": 0.15, "odds_min": 1.4, "odds_max": 6.0}

            # Check minute range: use config if set, else version default (soft default, no hard clamp)
            mom_actual_min = _momentum_minute_min if _momentum_minute_min > 0 else mom_cfg["min_m"]
            mom_actual_max = _momentum_minute_max if _momentum_minute_max < 90 else mom_cfg["max_m"]
            if not (mom_actual_min <= minuto <= mom_actual_max):
                pass  # Skip
            else:
                # Calculate xG underperformance
                xg_underperf_local = xg_local - goles_local
                xg_underperf_visitante = xg_visitante - goles_visitante

                # Dominant team detection via shared GR8 helper
                dominant_team, back_odds, sot_ratio_used = _detect_momentum_dominant(
                    sot_local=tiros_puerta_local,
                    sot_visitante=tiros_puerta_visitante,
                    xg_underperf_local=xg_underperf_local,
                    xg_underperf_visitante=xg_underperf_visitante,
                    back_home=back_home,
                    back_away=back_away,
                    cfg=mom_cfg,
                )

                if dominant_team is not None and back_odds is not None:
                    xg_underperf = xg_underperf_local if dominant_team == "Home" else xg_underperf_visitante
                    meta = STRATEGY_META["momentum_xg"]
                    min_odds = calculate_min_odds(meta["win_rate"])
                    ev = calculate_ev(back_odds, meta["win_rate"])
                    odds_ok = is_odds_favorable(back_odds, min_odds)

                    # Calcular riesgo por tiempo + marcador
                    risk_info = calculate_time_score_risk(
                        strategy=f"momentum_xg_{momentum_ver}",
                        minute=minuto,
                        home_score=int(goles_local),
                        away_score=int(goles_visitante),
                        dominant_team=dominant_team
                    )

                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": f"momentum_xg_{momentum_ver}",
                        "strategy_name": f"Momentum Dominante x xG ({momentum_ver.upper()})",
                        "minute": int(minuto),
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "recommendation": f"BACK {dominant_team.upper()} @ {back_odds:.2f}",
                        "back_odds": round(back_odds, 2),
                        "min_odds": round(min_odds, 2),
                        "expected_value": round(ev, 2),
                        "odds_favorable": odds_ok,
                        "confidence": "high" if odds_ok else "medium",
                        "win_rate_historical": round(meta["win_rate"] * 100, 1),
                        "roi_historical": round(meta["roi"] * 100, 1),
                        "sample_size": meta["sample_size"],
                        "description": meta["description"],
                        "entry_conditions": {
                            "dominant_team": dominant_team,
                            "sot_ratio": round(sot_ratio_used, 2),
                            "xg_underperf": round(xg_underperf, 2),
                            "sot_home": int(tiros_puerta_local),
                            "sot_away": int(tiros_puerta_visitante)
                        },
                        "thresholds": {
                            "sot_min": f">= {mom_cfg['sot_min']}",
                            "sot_ratio": f">= {mom_cfg['ratio']}x",
                            "xg_underperf": f"> {mom_cfg['xg']}",
                            "minute_range": f"{mom_cfg['min_m']}-{mom_cfg['max_m']}",
                            "odds_range": f"{mom_cfg['odds_min']}-{mom_cfg['odds_max']}"
                        },
                        "risk_info": risk_info
                    }
                    if (match_id, signal["strategy"]) not in placed_bets_keys:
                        conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                        if conflict:
                            signal["blocked"] = conflict
                        # Block signals with time/score risk
                        elif risk_info["risk_level"] != "none":
                            signal["blocked"] = f"Riesgo {risk_info['risk_level']}: {risk_info['risk_reason']}"
                        else:
                            signals.append(signal)
                            _log_signal_to_csv(signal)
                            _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 7: Tarde Asia (Back Over 2.5 — ligas asiáticas/europeas con alta frecuencia goleadora) ===
        # Trigger: partidos de ligas objetivo (Bundesliga, Ligue 1/2, Eredivisie, J-League, K-League, etc.)
        # en los primeros 15 minutos, con cuota Over 2.5 disponible.
        # League detection: same logic as analyze_strategy_tarde_asia (URL + team names).
        # NOTE: No hay filtro de hora UTC — analyze_strategy_tarde_asia tampoco filtra por hora
        # (comentario en línea 4923: "Por simplicidad, no filtramos por hora").
        tarde_asia_ver = versions.get("tarde_asia", versions.get("tardeAsia", "off"))
        if tarde_asia_ver not in ("off", "") and minuto is not None and minuto <= 15:
            _ta_over25 = _to_float(latest.get("back_over25", ""))
            if _ta_over25 and _ta_over25 > 1.0 and goals_data_ok:
                # League detection via shared GR8 helper (normalizes hyphens→spaces,
                # handles both display names and hyphenated match IDs correctly).
                _liga_ta = _detect_tarde_asia_liga(
                    match.get("name", ""), match.get("url", ""), match_id
                )

                if _liga_ta != "Unknown":
                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": f"tarde_asia_{tarde_asia_ver}",
                        "strategy_name": f"Tarde Asia ({tarde_asia_ver.upper()})",
                        "minute": int(minuto),
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "recommendation": "BACK Over 2.5",
                        "back_odds": round(_ta_over25, 2),
                        "min_odds": 1.5,
                        "expected_value": round(calculate_ev(_ta_over25, 0.60), 2),
                        "odds_favorable": _ta_over25 >= 1.5,
                        "confidence": "medium",
                        "win_rate_historical": 60.0,
                        "roi_historical": 15.0,
                        "sample_size": 100,
                        "description": "Back Over 2.5 en ligas con alta frecuencia goleadora",
                        "entry_conditions": {
                            "liga": _liga_ta,
                            "over25_odds": round(_ta_over25, 2),
                            "minute": int(minuto)
                        },
                        "thresholds": {
                            "minute": "<= 15",
                            "league": _liga_ta
                        }
                    }
                    if (match_id, signal["strategy"]) not in placed_bets_keys:
                        conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                        if conflict:
                            signal["blocked"] = conflict
                        else:
                            signals.append(signal)
                            _log_signal_to_csv(signal)
                            _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === SD STRATEGIES (from strategy-designer agent) ===
        # Each SD strategy is a one-shot trigger: check current state, emit signal if conditions met.
        # Config lives in cartera_config.json under strategies.sd_*
        # SD strategies use versions dict keys: sd_<name>_enabled, sd_<name>_m_min, etc.
        sd_configs = versions.get("_sd_configs", {})
        _gl = int(goles_local)
        _gv = int(goles_visitante)
        _total_goals = _gl + _gv
        _goal_diff = abs(_gl - _gv)
        _sot_total = int(tiros_puerta_local + tiros_puerta_visitante)
        _xg_total = (xg_local + xg_visitante) if (xg_local is not None and xg_visitante is not None) else None
        _m = int(minuto) if minuto is not None else 0

        def _sd_signal(strategy_key, strategy_name, recommendation, odds, description, entry_cond):
            """Helper to build and emit an SD signal."""
            sig = {
                "match_id": match_id,
                "match_name": match["name"],
                "match_url": match["url"],
                "strategy": strategy_key,
                "strategy_name": strategy_name,
                "minute": _m,
                "score": f"{_gl}-{_gv}",
                "recommendation": recommendation,
                "back_odds": round(odds, 2) if odds else None,
                "min_odds": 1.21,
                "expected_value": 0,
                "odds_favorable": True,
                "confidence": "medium",
                "win_rate_historical": 0,
                "roi_historical": 0,
                "sample_size": 0,
                "description": description,
                "entry_conditions": entry_cond,
                "thresholds": {},
            }
            if (match_id, sig["strategy"]) not in placed_bets_keys:
                conflict = _has_conflict(match_id, sig["recommendation"], match_outcomes)
                if conflict:
                    sig["blocked"] = conflict
                else:
                    signals.append(sig)
                    _log_signal_to_csv(sig)
                    _register_outcome(match_id, sig["recommendation"], match_outcomes)

        # --- SD: BACK Over 2.5 from 2-Goal Lead ---
        _sd_cfg = sd_configs.get("sd_over25_2goal", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_over25_2goal_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _sd_signal("sd_over25_2goal", "SD BACK O2.5 2-Goal Lead",
                           f"BACK OVER 2.5 @ {_trig['back_over25']:.2f}", _trig["back_over25"],
                           "Back Over 2.5 when a team leads by 2+ goals with SoT activity",
                           {"goal_diff": _trig.get("goal_diff"), "sot_total": _trig.get("sot_total"),
                            "odds": round(_trig["back_over25"], 2)})

        # --- SD: BACK Under 3.5 Late ---
        _sd_cfg = sd_configs.get("sd_under35_late", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_under35_late_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _sd_signal("sd_under35_late", "SD BACK U3.5 Late",
                           f"BACK UNDER 3.5 @ {_trig['back_under35']:.2f}", _trig["back_under35"],
                           "Back Under 3.5 when exactly 3 goals scored and xG is low",
                           {"total_goals": _trig.get("total_goals_trigger"),
                            "xg_total": round(_trig["xg_total"], 2) if _trig.get("xg_total") is not None else None})

        # --- SD: BACK Longshot Leading ---
        _sd_cfg = sd_configs.get("sd_longshot", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_longshot_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _ls_odds = _trig.get("back_home") or _trig.get("back_away")
                _ls_team = _trig.get("longshot_team")
                _team_label = "HOME" if _ls_team == "local" else "AWAY"
                _sd_signal("sd_longshot", "SD BACK Longshot Leading",
                           f"BACK {_team_label} @ {_ls_odds:.2f}", _ls_odds,
                           "Back the pre-match longshot when they are leading late",
                           {"longshot_team": _ls_team, "odds": round(_ls_odds, 2),
                            "xg_longshot": round(_trig["xg_longshot"], 2) if _trig.get("xg_longshot") is not None else None})

        # --- SD: BACK CS 2-1/1-2 (Close Game) ---
        _sd_cfg = sd_configs.get("sd_cs_close", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_cs_close_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _score = _trig["trigger_score"]
                _col = f"back_rc_{_score.replace('-', '_')}"
                _cs_odds = _trig.get(_col)
                if _cs_odds:
                    _sd_signal("sd_cs_close", "SD BACK CS Close",
                               f"BACK CS {_score} @ {_cs_odds:.2f}", _cs_odds,
                               "Back current Correct Score at close game (2-1 / 1-2)",
                               {"score": _score, "cs_odds": round(_cs_odds, 2)})

        # --- SD: BACK CS 1-0/0-1 (One Goal) ---
        _sd_cfg = sd_configs.get("sd_cs_one_goal", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_cs_one_goal_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _score = _trig["trigger_score"]
                _col = f"back_rc_{_score.replace('-', '_')}"
                _cs_odds = _trig.get(_col)
                if _cs_odds:
                    _sd_signal("sd_cs_one_goal", "SD BACK CS One-Goal",
                               f"BACK CS {_score} @ {_cs_odds:.2f}", _cs_odds,
                               "Back current Correct Score at 1-0 / 0-1",
                               {"score": _score, "cs_odds": round(_cs_odds, 2)})

        # --- SD: BACK Underdog Leading Late ---
        _sd_cfg = sd_configs.get("sd_ud_leading", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_ud_leading_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _ud_odds = _trig.get("back_home") or _trig.get("back_away")
                _ud_team = _trig.get("ud_team")
                _sd_signal("sd_ud_leading", "SD BACK Underdog Leading",
                           f"BACK {'HOME' if _ud_team == 'local' else 'AWAY'} @ {_ud_odds:.2f}", _ud_odds,
                           "Back the underdog when they are leading late",
                           {"ud_team": _ud_team, "pre_odds": round(_trig["ud_pre_odds"], 2),
                            "current_odds": round(_ud_odds, 2)})

        # --- SD: BACK Home Favourite Leading Late ---
        _sd_cfg = sd_configs.get("sd_home_fav_leading", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_home_fav_leading_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _home_odds = _trig["back_home"]
                _sd_signal("sd_home_fav_leading", "SD BACK Home Fav Leading",
                           f"BACK HOME @ {_home_odds:.2f}", _home_odds,
                           "Back home favourite when leading late",
                           {"home_pre_odds": round(_trig["home_pre_odds"], 2),
                            "current_odds": round(_home_odds, 2), "lead": _trig.get("lead")})

        # --- SD: BACK CS 2-0/0-2 Late ---
        _sd_cfg = sd_configs.get("sd_cs_20", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_cs_20_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _score = _trig["trigger_score"]
                _col = f"back_rc_{_score.replace('-', '_')}"
                _cs_odds = _trig.get(_col)
                if _cs_odds:
                    _sd_signal("sd_cs_20", "SD BACK CS 2-0/0-2",
                               f"BACK CS {_score} @ {_cs_odds:.2f}", _cs_odds,
                               "Back current Correct Score at 2-0 / 0-2",
                               {"score": _score, "cs_odds": round(_cs_odds, 2)})

        # --- SD: BACK CS Big Lead (3-0/0-3/3-1/1-3) ---
        _sd_cfg = sd_configs.get("sd_cs_big_lead", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_cs_big_lead_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _score = _trig["trigger_score"]
                _col = f"back_rc_{_score.replace('-', '_')}"
                _cs_odds = _trig.get(_col)
                if _cs_odds:
                    _sd_signal("sd_cs_big_lead", "SD BACK CS Big Lead",
                               f"BACK CS {_score} @ {_cs_odds:.2f}", _cs_odds,
                               "Back current Correct Score at big lead (3-0/0-3/3-1/1-3)",
                               {"score": _score, "cs_odds": round(_cs_odds, 2)})

        # --- SD (disabled): LAY Over 4.5 V3 ---
        _sd_cfg = sd_configs.get("sd_lay_over45_v3", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_lay_over45_v3_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _lay_odds = _trig["lay_over45"]
                _sd_signal("sd_lay_over45_v3", "SD LAY Over 4.5 V3",
                           f"LAY OVER 4.5 @ {_lay_odds:.2f}", _lay_odds,
                           "Lay Over 4.5 tight: goals<=1, tight minute window",
                           {"total_goals": _trig.get("total_goals_trigger"), "odds": round(_lay_odds, 2)})

        # --- SD (disabled): BACK Draw xG Convergence ---
        _sd_cfg = sd_configs.get("sd_draw_xg_conv", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_draw_xg_conv_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _draw_odds = _trig["back_draw"]
                _sd_signal("sd_draw_xg_conv", "SD BACK Draw xG Convergence",
                           f"BACK DRAW @ {_draw_odds:.2f}", _draw_odds,
                           "Back Draw when xG converges in tied match",
                           {"xg_diff": _trig.get("xg_diff"), "score": _trig.get("score_at_trigger"),
                            "odds": round(_draw_odds, 2)})

        # --- SD (disabled): BACK Over 0.5 Possession Extreme ---
        _sd_cfg = sd_configs.get("sd_poss_extreme", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_poss_extreme_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _over05_odds = _trig["back_over05"]
                _sd_signal("sd_poss_extreme", "SD BACK Over 0.5 Poss Extreme",
                           f"BACK OVER 0.5 @ {_over05_odds:.2f}", _over05_odds,
                           "Back Over 0.5 when possession is extremely one-sided at 0-0",
                           {"poss_max": _trig.get("poss_max"), "odds": round(_over05_odds, 2)})

        # --- SD (disabled): BACK CS 0-0 Early ---
        _sd_cfg = sd_configs.get("sd_cs_00", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_cs_00_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _cs00_odds = _trig["back_rc_0_0"]
                _sd_signal("sd_cs_00", "SD BACK CS 0-0 Early",
                           f"BACK CS 0-0 @ {_cs00_odds:.2f}", _cs00_odds,
                           "Back CS 0-0 in early window with low xG and SoT",
                           {"xg_total": _trig.get("xg_total"), "sot_total": _trig.get("sot_total"),
                            "odds": round(_cs00_odds, 2)})

        # --- SD (disabled): BACK Over 2.5 from Two Goals ---
        _sd_cfg = sd_configs.get("sd_over25_2goals", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_over25_2goals_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _o25_odds = _trig["back_over25"]
                _sd_signal("sd_over25_2goals", "SD BACK O2.5 Two Goals",
                           f"BACK OVER 2.5 @ {_o25_odds:.2f}", _o25_odds,
                           "Back Over 2.5 when exactly 2 goals scored in stable row",
                           {"total_goals": _trig.get("total_goals_trigger"), "odds": round(_o25_odds, 2)})

        # --- SD (disabled): BACK Draw at 1-1 ---
        _sd_cfg = sd_configs.get("sd_draw_11", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_draw_11_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _draw11_odds = _trig["back_draw"]
                _sd_signal("sd_draw_11", "SD BACK Draw 1-1",
                           f"BACK DRAW @ {_draw11_odds:.2f}", _draw11_odds,
                           "Back Draw when score is exactly 1-1 late",
                           {"odds": round(_draw11_odds, 2)})

        # --- SD (disabled): BACK Under 3.5 Three-Goal Lid ---
        _sd_cfg = sd_configs.get("sd_under35_3goals", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_under35_3goals_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _u35_odds = _trig["back_under35"]
                _sd_signal("sd_under35_3goals", "SD BACK U3.5 3-Goal Lid",
                           f"BACK UNDER 3.5 @ {_u35_odds:.2f}", _u35_odds,
                           "Back Under 3.5 when exactly 3 goals and low xG",
                           {"xg_total": _trig.get("xg_total"), "odds": round(_u35_odds, 2)})

        # --- SD (disabled): BACK Away Favourite Leading Late ---
        _sd_cfg = sd_configs.get("sd_away_fav_leading", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_away_fav_leading_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _away_odds = _trig["back_away"]
                _sd_signal("sd_away_fav_leading", "SD BACK Away Fav Leading",
                           f"BACK AWAY @ {_away_odds:.2f}", _away_odds,
                           "Back away favourite when leading late",
                           {"away_pre_odds": round(_trig["away_pre_odds"], 2),
                            "lead": _trig.get("lead"), "odds": round(_away_odds, 2)})

        # --- SD (disabled): BACK Under 4.5 Three Goals Low xG ---
        _sd_cfg = sd_configs.get("sd_under45_3goals", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_under45_3goals_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _u45_odds = _trig["back_under45"]
                _sd_signal("sd_under45_3goals", "SD BACK U4.5 3-Goals Low xG",
                           f"BACK UNDER 4.5 @ {_u45_odds:.2f}", _u45_odds,
                           "Back Under 4.5 when exactly 3 goals and xG < threshold",
                           {"xg_total": _trig.get("xg_total"), "odds": round(_u45_odds, 2)})

        # --- SD (disabled): BACK CS 1-1 Late ---
        _sd_cfg = sd_configs.get("sd_cs_11", {})
        if _sd_cfg.get("enabled") and goals_data_ok:
            _trig = _detect_cs_11_trigger(rows, len(rows) - 1, _sd_cfg)
            if _trig:
                _cs11_odds = _trig["back_rc_1_1"]
                _sd_signal("sd_cs_11", "SD BACK CS 1-1 Late",
                           f"BACK CS 1-1 @ {_cs11_odds:.2f}", _cs11_odds,
                           "Back CS 1-1 late in the game",
                           {"odds": round(_cs11_odds, 2)})

    # --- Enrich signals with age and maturity info ---
    _now = datetime.utcnow()
    for _sig in signals:
        _key = (_sig["match_id"], _sig["strategy"])
        _first_seen = first_seen_map.get(_key)
        if _first_seen:
            _age_mins = (_now - _first_seen).total_seconds() / 60.0
        else:
            _age_mins = 0.0
        _family = _get_strategy_family(_sig["strategy"])
        _min_dur = min_dur_map.get(_family, 1)
        _sig["signal_age_minutes"] = round(_age_mins, 1)
        _sig["min_duration_caps"] = _min_dur
        _sig["is_mature"] = _age_mins >= _min_dur

    # --- Log signal_end for signals that disappeared this cycle ---
    current_keys = {(s["match_id"], s["strategy"]) for s in signals}
    _log_signal_ends(current_keys)

    return {
        "total_signals": len(signals),
        "live_matches": len(live_matches),
        "signals": signals,
        "active_versions": versions
    }


def detect_watchlist(versions: dict | None = None) -> list:
    """
    Detect matches that are close to triggering a signal but don't yet meet all conditions.
    Returns a list of watchlist items sorted by proximity (highest first).
    """
    if versions is None:
        versions = {"draw": "v2r", "xg": "v3", "drift": "v1", "clustering": "v2", "pressure": "v1"}

    games = load_games()
    live_matches = [g for g in games if g["status"] == "live"]
    watchlist = []

    for match in live_matches:
        match_id = match["match_id"]
        csv_path = _resolve_csv_path(match_id)
        if not csv_path.exists():
            continue
        rows = _read_csv_rows(csv_path)
        if not rows:
            continue

        latest = rows[-1]
        minuto = _to_float(latest.get("minuto", ""))
        if minuto is None:
            continue

        gl = _to_float(latest.get("goles_local", "")) or 0
        gv = _to_float(latest.get("goles_visitante", "")) or 0
        xg_l = _to_float(latest.get("xg_local", ""))
        xg_v = _to_float(latest.get("xg_visitante", ""))
        pos_l = _to_float(latest.get("posesion_local", ""))
        pos_v = _to_float(latest.get("posesion_visitante", ""))
        tiros_l = _to_float(latest.get("tiros_local", "")) or 0
        tiros_v = _to_float(latest.get("tiros_visitante", "")) or 0
        sot_l = _to_float(latest.get("tiros_puerta_local", "")) or 0
        sot_v = _to_float(latest.get("tiros_puerta_visitante", "")) or 0
        back_draw = _to_float(latest.get("back_draw", ""))
        back_home = _to_float(latest.get("back_home", ""))
        back_away = _to_float(latest.get("back_away", ""))

        draw_ver = versions.get("draw", "v2r")
        xg_ver = versions.get("xg", "v2")
        drift_ver = versions.get("drift", "v1")
        clustering_ver = versions.get("clustering", "v2")
        pressure_ver = versions.get("pressure", "v1")

        match_info = {"match_id": match_id, "match_name": match["name"],
                      "match_url": match["url"], "minute": int(minuto),
                      "score": f"{int(gl)}-{int(gv)}"}

        # --- DRAW watchlist ---
        if draw_ver != "off" and gl == 0 and gv == 0:
            conds = []
            conds.append({"label": "Score 0-0", "met": True})
            conds.append({"label": "Min >= 30", "met": minuto >= 30,
                          "current": f"Min {int(minuto)}", "target": "30"})
            if xg_l is not None and xg_v is not None:
                xg_total = xg_l + xg_v
                poss_diff = abs((pos_l or 50) - (pos_v or 50))
                tiros_total = tiros_l + tiros_v
                if draw_ver in ("v15", "v2r", "v2", "v3", "v4"):
                    limit = 0.5 if draw_ver == "v2" else 0.6
                    conds.append({"label": f"xG < {limit}", "met": xg_total < limit,
                                  "current": f"{xg_total:.2f}", "target": str(limit)})
                if draw_ver in ("v15", "v2r", "v2", "v3", "v4"):
                    pd_limit = 25 if draw_ver in ("v15", "v3") else 20
                    conds.append({"label": f"Pos. diff < {pd_limit}%", "met": poss_diff < pd_limit,
                                  "current": f"{poss_diff:.0f}%", "target": f"{pd_limit}%"})
                if draw_ver in ("v2r", "v2", "v4"):
                    conds.append({"label": "Tiros < 8", "met": tiros_total < 8,
                                  "current": str(int(tiros_total)), "target": "8"})
                if draw_ver == "v3":
                    xg_dom = (xg_l / xg_total) if xg_total > 0 else None
                    xg_dom_ok = xg_dom is not None and (xg_dom > 0.55 or xg_dom < 0.45)
                    conds.append({"label": "Dominancia xG asimétrica", "met": xg_dom_ok,
                                  "current": f"{xg_dom:.0%}" if xg_dom else "n/a", "target": ">55% o <45%"})
                if draw_ver == "v4":
                    opta_gap_live = abs(opta_l - opta_v) if opta_l is not None and opta_v is not None else None
                    conds.append({"label": "Opta gap <= 10", "met": opta_gap_live is not None and opta_gap_live <= 10,
                                  "current": f"{opta_gap_live:.1f}" if opta_gap_live is not None else "n/a", "target": "10"})

            met = sum(1 for c in conds if c["met"])
            total = len(conds)
            if 0 < met < total:
                watchlist.append({**match_info, "strategy": "Empate 0-0",
                                  "version": draw_ver.upper(), "conditions": conds,
                                  "met": met, "total": total, "proximity": round(met / total * 100)})

        # --- XG UNDERPERFORMANCE watchlist ---
        if xg_ver != "off" and xg_l is not None and xg_v is not None:
            for team_label, xg_t, goals_t, goals_o, sot_t in [
                ("Home", xg_l, gl, gv, sot_l), ("Away", xg_v, gv, gl, sot_v)]:
                xg_excess = xg_t - goals_t
                conds = []
                conds.append({"label": "Equipo perdiendo", "met": goals_t < goals_o})
                conds.append({"label": "xG excess >= 0.5", "met": xg_excess >= 0.5,
                              "current": f"{xg_excess:.2f}", "target": "0.50"})
                conds.append({"label": "Min >= 15", "met": minuto >= 15,
                              "current": f"Min {int(minuto)}", "target": "15"})
                if xg_ver in ("v2", "v3"):
                    conds.append({"label": "SoT >= 2", "met": sot_t >= 2,
                                  "current": str(int(sot_t)), "target": "2"})
                if xg_ver == "v3":
                    conds.append({"label": "Min < 70", "met": minuto < 70,
                                  "current": f"Min {int(minuto)}", "target": "70"})

                met = sum(1 for c in conds if c["met"])
                total = len(conds)
                if met >= 2 and met < total:
                    watchlist.append({**match_info, "strategy": f"xG Underp. ({team_label})",
                                      "version": xg_ver.upper(), "conditions": conds,
                                      "met": met, "total": total, "proximity": round(met / total * 100)})

        # --- ODDS DRIFT watchlist ---
        if drift_ver != "off" and gl != gv:
            goal_diff = abs(int(gl) - int(gv))
            target_minute = minuto - 10
            hist_row = None
            for row in reversed(rows):
                rm = _to_float(row.get("minuto", ""))
                if rm is not None and rm <= target_minute:
                    hist_row = row
                    break

            if hist_row:
                if gl > gv:
                    odds_before = _to_float(hist_row.get("back_home", ""))
                    odds_now = back_home
                else:
                    odds_before = _to_float(hist_row.get("back_away", ""))
                    odds_now = back_away

                if odds_before and odds_now and odds_before > 0:
                    drift_pct_val = ((odds_now - odds_before) / odds_before) * 100
                    conds = []
                    conds.append({"label": "Equipo ganando", "met": True})
                    conds.append({"label": "Drift >= 25%", "met": drift_pct_val >= 25,
                                  "current": f"{drift_pct_val:.0f}%", "target": "25%"})
                    if drift_ver == "v1":
                        conds.append({"label": "Score 1-0", "met": goal_diff == 1 and (gl + gv) == 1,
                                      "current": f"{int(gl)}-{int(gv)}", "target": "1-0"})
                    elif drift_ver == "v2":
                        conds.append({"label": "Dif. goles >= 2", "met": goal_diff >= 2,
                                      "current": str(goal_diff), "target": "2"})
                    elif drift_ver == "v3":
                        conds.append({"label": "Drift >= 100%", "met": drift_pct_val >= 100,
                                      "current": f"{drift_pct_val:.0f}%", "target": "100%"})
                    elif drift_ver == "v4":
                        conds.append({"label": "2a parte", "met": minuto > 45,
                                      "current": f"Min {int(minuto)}", "target": "46"})
                        conds.append({"label": "Odds <= 5", "met": odds_now <= 5.0,
                                      "current": f"{odds_now:.2f}", "target": "5.00"})
                    elif drift_ver == "v5":
                        conds.append({"label": "Odds <= 5", "met": odds_now <= 5.0,
                                      "current": f"{odds_now:.2f}", "target": "5.00"})

                    met = sum(1 for c in conds if c["met"])
                    total = len(conds)
                    if met >= 1 and met < total:
                        watchlist.append({**match_info, "strategy": "Odds Drift",
                                          "version": drift_ver.upper(), "conditions": conds,
                                          "met": met, "total": total, "proximity": round(met / total * 100)})

        # --- GOAL CLUSTERING watchlist ---
        if clustering_ver != "off":
            sot_max = max(sot_l, sot_v)
            # Check for recent goal
            recent_goal = False
            for i in range(len(rows) - 1, max(0, len(rows) - 4), -1):
                if i > 0:
                    curr_gl = (_to_float(rows[i].get("goles_local", "")) or 0)
                    curr_gv = (_to_float(rows[i].get("goles_visitante", "")) or 0)
                    prev_gl = (_to_float(rows[i-1].get("goles_local", "")) or 0)
                    prev_gv = (_to_float(rows[i-1].get("goles_visitante", "")) or 0)
                    if (int(curr_gl) + int(curr_gv)) > (int(prev_gl) + int(prev_gv)):
                        recent_goal = True
                        break

            conds = []
            conds.append({"label": "Gol reciente", "met": recent_goal})
            conds.append({"label": "Min 15-80", "met": 15 <= minuto <= 80,
                          "current": f"Min {int(minuto)}", "target": "15-80"})
            conds.append({"label": "SoT max >= 3", "met": sot_max >= 3,
                          "current": str(int(sot_max)), "target": "3"})
            if clustering_ver == "v3":
                conds.append({"label": "Min < 75", "met": minuto < 75,
                              "current": f"Min {int(minuto)}", "target": "75"})

            met = sum(1 for c in conds if c["met"])
            total = len(conds)
            if met >= 1 and met < total:
                watchlist.append({**match_info, "strategy": "Goal Clustering",
                                  "version": clustering_ver.upper(), "conditions": conds,
                                  "met": met, "total": total, "proximity": round(met / total * 100)})

        # --- PRESSURE COOKER watchlist ---
        if pressure_ver != "off":
            total_goals = int(gl) + int(gv)
            is_draw = gl == gv
            has_goals = total_goals >= 2
            conds = []
            conds.append({"label": "Empate", "met": is_draw})
            conds.append({"label": "Score >= 1-1", "met": has_goals,
                          "current": f"{int(gl)}-{int(gv)}", "target": "1-1+"})
            conds.append({"label": "Min 65-75", "met": 65 <= minuto <= 75,
                          "current": f"Min {int(minuto)}", "target": "65-75"})

            met = sum(1 for c in conds if c["met"])
            total = len(conds)
            if met >= 1 and met < total:
                watchlist.append({**match_info, "strategy": "Pressure Cooker",
                                  "version": pressure_ver.upper(), "conditions": conds,
                                  "met": met, "total": total, "proximity": round(met / total * 100)})

    # Sort by proximity descending
    watchlist.sort(key=lambda x: x["proximity"], reverse=True)
    return watchlist


def analyze_strategy_goal_clustering(min_dur: int = 1) -> dict:
    """
    Analiza Goal Clustering V2: Tras gol + SoT max >= 3

    Trigger: Gol recién marcado (min 15-80) + algún equipo tiene >= 3 SoT
    Apuesta: Back Over (total_actual + 0.5)

    Returns:
        {
            "total_matches": int,
            "total_goal_events": int,
            "summary": {
                "total_bets": int,
                "wins": int,
                "win_rate": float,
                "total_pl": float,
                "roi": float
            },
            "bets": [...]
        }
    """
    finished = _get_all_finished_matches()

    results = {
        "total_matches": 0,
        "total_goal_events": 0,
        "bets": []
    }

    for match_data in finished:
        results["total_matches"] += 1
        match_id = match_data["match_id"]
        match_name = match_data["name"]
        csv_path = _resolve_csv_path(match_id)

        # Skip matches with corrupted Over/Under odds
        if match_id in CORRUPTED_OVER_MATCHES:
            continue

        if not csv_path.exists():
            continue

        rows = _normalize_halftime_minutes(_read_csv_rows(csv_path))
        if len(rows) < 10:
            continue

        # Resultado final — usar última fila con scores válidos (evitar filas pre_partido al final)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))

        if gl_final is None or gv_final is None:
            continue

        total_final = int(gl_final) + int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Rastrear goles para detectar nuevos
        prev_total = None  # None = aún no hemos procesado ninguna fila válida
        # NOTE: bet_placed flag removed — generate ALL qualifying goal events per match
        # so that notebook filters (xg_rem_min etc.) can select the appropriate one.
        # Dedup in _apply_realistic_adj / _apply_realistic_adj ensures only the first
        # qualifying trigger fires in live trading.

        # BT superset cfg: permissive (sot_min=2, 15-91 min, no xg_rem filter)
        # max_minute=91 because helper uses >= (exclusive), so 91 includes min=90
        _cl_bt_cfg = {"sot_min": 2, "min_minute": 15, "max_minute": 91, "xg_rem_min": 0}

        for idx, row in enumerate(rows):
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))

            if gl is None or gv is None:
                continue

            total_now = int(gl) + int(gv)

            # Inicializar prev_total en la primera fila válida
            if prev_total is None:
                prev_total = total_now
                continue

            minuto = _to_float(row.get("minuto", ""))

            # ¿Hubo un gol nuevo? (prev_total tracking for BT)
            if total_now > prev_total:
                results["total_goal_events"] += 1

                # Use shared GR9 helper to validate the trigger conditions at this row.
                # The helper's lookback also detects the goal (consistent with LIVE).
                # Superset: sot>=2, min 15-90 (notebook filters m_max via config).
                trig = _detect_goal_clustering_trigger(rows, idx, _cl_bt_cfg)
                if trig is not None and minuto is not None and 15 <= minuto <= 90:
                    goal_minute_bt = trig["goal_minute"]
                    sot_max = trig["sot_max"]
                    total_goals_bt = trig["total_goals"]
                    over_field = trig["over_field"]

                    # Min duration: wait min_dur rows before entering
                    entry_row = row
                    if min_dur > 1:
                        end_idx = idx + min_dur - 1
                        if end_idx >= len(rows):
                            # Actualizar prev_total y continuar
                            prev_total = total_now
                            continue
                        # Re-verify trigger at confirmation row.  The helper's
                        # 3-row lookback may no longer reach the goal row when
                        # min_dur >= 4, so scan backwards from end_idx until we
                        # find a row where the trigger still fires (sot may have
                        # increased since the goal row — matches LIVE behaviour).
                        confirm_trig = None
                        for _ci in range(end_idx, idx - 1, -1):
                            confirm_trig = _detect_goal_clustering_trigger(rows, _ci, _cl_bt_cfg)
                            if confirm_trig is not None:
                                break
                        if confirm_trig is not None and confirm_trig["sot_max"] > sot_max:
                            sot_max = confirm_trig["sot_max"]
                            over_field = confirm_trig["over_field"]
                        entry_row = rows[end_idx]

                    # Obtener cuotas Over
                    over_odds = _to_float(entry_row.get(over_field, ""))

                    # SKIP si no hay cuota disponible (evita P/L = 0)
                    if not over_odds or over_odds <= 0:
                        # Actualizar prev_total y continuar
                        prev_total = total_now
                        continue

                    # Target: al menos 1 gol más
                    target = total_goals_bt + 1
                    over_won = total_final >= target

                    # Version filters
                    passes_v3 = minuto < 60  # V3: entrada temprana

                    # V4: xG remaining > 0.8 (100% WR in backtest)
                    synth = _compute_synthetic_at_trigger(rows, idx)
                    xg_rem = synth.get("xg_remaining")
                    passes_v4 = xg_rem is not None and xg_rem > 0.8

                    # Guardar bet (solo si hay cuota válida)
                    _gc_entry_idx = (idx + min_dur - 1) if min_dur > 1 else idx
                    _stab_gc, _cons_gc = _count_odds_stability(rows, _gc_entry_idx, over_field, over_odds or 0)
                    pl = round((over_odds - 1) * 10 * 0.95, 2) if over_won else -10
                    pl_conservative = round((_cons_gc - 1) * 10 * 0.95, 2) if over_won else -10
                    results["bets"].append({
                        "strategy": "goal_clustering",
                        "match": match_name,
                        "match_id": match_id,
                        "minuto": int(minuto),
                        "score": f"{int(gl)}-{int(gv)}",
                        "score_at_trigger": f"{int(gl)}-{int(gv)}",
                        "sot_max": sot_max,
                        "back_over_odds": round(over_odds, 2),
                        "lay_trigger": _to_float(entry_row.get(over_field.replace("back_", "lay_"), "")) or None,
                        "over_line": f"Over {total_goals_bt + 0.5}",
                        "ft_score": ft_score,
                        "won": over_won,
                        "pl": pl,
                        "pl_conservative": pl_conservative,
                        "conservative_odds": round(_cons_gc, 2),
                        "passes_v3": passes_v3,
                        "passes_v4": passes_v4,
                        "synth_xg_remaining": xg_rem,
                        "stability_count": _stab_gc,
                        "timestamp_utc": entry_row.get("timestamp_utc", ""),
                        "País": entry_row.get("País", "Desconocido"),
                        "Liga": entry_row.get("Liga", "Desconocida"),
                    })

            # Actualizar prev_total SIEMPRE (dentro o fuera del rango de minutos)
            prev_total = total_now

    # Calcular summary
    total_bets = len(results["bets"])
    wins = sum(1 for b in results["bets"] if b["won"])
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    total_pl = sum(b["pl"] for b in results["bets"])
    total_stake = total_bets * 10
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    v3_bets = [b for b in results["bets"] if b.get("passes_v3")]
    v3_n = len(v3_bets)
    v3_wins = sum(1 for b in v3_bets if b["won"])

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }
    results["summary_v3"] = {
        "total_bets": v3_n,
        "wins": v3_wins,
        "win_rate": round(v3_wins / v3_n * 100, 1) if v3_n > 0 else 0,
        "total_pl": round(sum(b["pl"] for b in v3_bets), 2),
        "roi": round(sum(b["pl"] for b in v3_bets) / (v3_n * 10) * 100, 1) if v3_n > 0 else 0,
    }

    return results


def analyze_strategy_pressure_cooker(min_dur: int = 1) -> dict:
    """
    Pressure Cooker V1: Back Over en empates con goles (min 65-75)

    Trigger: Empate 1-1+ entre min 65-75
    Apuesta: Back Over (total_actual + 0.5)
    Excluye: Empates 0-0

    Returns:
        {
            "total_matches": int,
            "draws_65_75": int,
            "summary": {...},
            "bets": [...]
        }
    """
    finished = _get_all_finished_matches()
    from api.config import load_config as _load_config
    _pressure_cfg = _load_config().get("strategies", {}).get("pressure", {})
    _xg_sum_min_bt = float(_pressure_cfg.get("xg_sum_min", 0))

    results = {
        "total_matches": 0,
        "draws_65_75": 0,
        "bets": []
    }

    for match_data in finished:
        results["total_matches"] += 1
        match_id = match_data["match_id"]
        match_name = match_data["name"]
        csv_path = _resolve_csv_path(match_id)

        if not csv_path.exists():
            continue

        rows = _normalize_halftime_minutes(_read_csv_rows(csv_path))
        if len(rows) < 20:
            continue

        # Resultado final — usar última fila con scores válidos (evitar filas pre_partido al final)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))

        if gl_final is None or gv_final is None:
            continue

        # Verificar que el partido finalizo (minuto >= 85)
        last_min = _final_match_minute(rows)
        if last_min is None or last_min < 85:
            continue

        total_final = int(gl_final) + int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Buscar primera fila con empate 1-1+ entre min 65-75 via shared GR9 helper
        # BT superset cfg: 65-75 min range (hardcoded strategy window), confirm>=2 via last-6-rows
        _pc_bt_cfg = {"min_minute": 65, "max_minute": 75, "score_confirm": 2, "xg_sum_min": _xg_sum_min_bt}
        trigger_found = False
        for idx, row in enumerate(rows):
            if trigger_found:
                break

            # Use shared GR9 helper for trigger detection
            trig = _detect_pressure_cooker_trigger(rows, idx, _pc_bt_cfg)
            if trig is None:
                continue

            # Min duration: wait min_dur rows and re-verify trigger persists.
            # This mirrors LIVE behavior where analytics.py's stability
            # post-filter requires the signal to still be present after
            # min_dur captures before placing the bet.
            entry_row = row
            if min_dur > 1:
                end_idx = idx + min_dur - 1
                if end_idx >= len(rows):
                    continue  # not enough rows remaining
                # Re-verify trigger at confirmation row
                confirm_trig = _detect_pressure_cooker_trigger(rows, end_idx, _pc_bt_cfg)
                if confirm_trig is None:
                    continue  # trigger disappeared — ephemeral signal
                # Use confirmation data (reflects state at bet placement time)
                trig = confirm_trig
                entry_row = rows[end_idx]

            trigger_found = True
            total_goals = trig["total_goals"]
            over_field   = trig["over_field"]
            gl           = trig["gl"]
            gv           = trig["gv"]
            minuto       = trig["minuto"]
            actual_min   = int(minuto)

            results["draws_65_75"] += 1

            # Obtener cuotas Over from entry row
            over_odds = _to_float(entry_row.get(over_field, ""))

            if not over_odds or over_odds <= 1:
                continue

            # Calcular deltas de momentum (informativo)
            # Buscar fila ~10 min antes
            past_row = None
            for r in rows:
                m = _to_float(r.get("minuto", ""))
                if m is not None and actual_min - 12 <= m <= actual_min - 8:
                    past_row = r

            sot_delta = 0
            corners_delta = 0
            shots_delta = 0
            if past_row:
                sot_now = (_to_float(entry_row.get("tiros_puerta_local", "")) or 0) + (_to_float(entry_row.get("tiros_puerta_visitante", "")) or 0)
                sot_past = (_to_float(past_row.get("tiros_puerta_local", "")) or 0) + (_to_float(past_row.get("tiros_puerta_visitante", "")) or 0)
                sot_delta = sot_now - sot_past

                corners_now = (_to_float(entry_row.get("corners_local", "")) or 0) + (_to_float(entry_row.get("corners_visitante", "")) or 0)
                corners_past = (_to_float(past_row.get("corners_local", "")) or 0) + (_to_float(past_row.get("corners_visitante", "")) or 0)
                corners_delta = corners_now - corners_past

                shots_now = (_to_float(entry_row.get("tiros_local", "")) or 0) + (_to_float(entry_row.get("tiros_visitante", "")) or 0)
                shots_past = (_to_float(past_row.get("tiros_local", "")) or 0) + (_to_float(past_row.get("tiros_visitante", "")) or 0)
                shots_delta = shots_now - shots_past

            # Resultado
            won = total_final > total_goals
            over_line = f"Over {total_goals + 0.5}"

            _pc_entry_idx = (idx + min_dur - 1) if min_dur > 1 else idx
            _stab_pc, _cons_pc = _count_odds_stability(rows, _pc_entry_idx, over_field or "back_over25", over_odds or 0)
            pl = round((over_odds - 1) * 10 * 0.95, 2) if won else -10
            pl_conservative = round((_cons_pc - 1) * 10 * 0.95, 2) if won else -10

            results["bets"].append({
                "match": match_name,
                "match_id": match_id,
                "minuto": actual_min,
                "score": f"{int(gl)}-{int(gv)}",
                "back_over_odds": round(over_odds, 2),
                "lay_trigger": _to_float(entry_row.get(over_field.replace("back_", "lay_"), "")) or None if over_field else None,
                "over_line": over_line,
                "ft_score": ft_score,
                "won": won,
                "pl": pl,
                "pl_conservative": pl_conservative,
                "conservative_odds": round(_cons_pc, 2),
                "sot_delta": int(sot_delta),
                "corners_delta": int(corners_delta),
                "shots_delta": int(shots_delta),
                "stability_count": _stab_pc,
                "timestamp_utc": entry_row.get("timestamp_utc", ""),
                "País": entry_row.get("País", "Desconocido"),
                "Liga": entry_row.get("Liga", "Desconocida"),
            })

    # Calcular summary
    total_bets = len(results["bets"])
    wins = sum(1 for b in results["bets"] if b["won"])
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    total_pl = sum(b["pl"] for b in results["bets"])
    total_stake = total_bets * 10
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }

    return results


def analyze_strategy_tarde_asia(min_dur: int = 1) -> dict:
    """
    Tarde Asia High Scoring V1: Back Over 2.5 en partidos tarde de Asia/Alemania/Francia

    Trigger: Partidos entre 14-20h de ligas asiáticas, Bundesliga, Ligue 1/2
    Apuesta: Back Over 2.5 desde el inicio
    Estado: OFF - Solo tracking, no activa señales

    Returns:
        {
            "total_matches": int,
            "tarde_asia_matches": int,
            "summary": {...},
            "bets": [...]
        }
    """
    finished = _get_all_finished_matches()

    results = {
        "total_matches": 0,
        "tarde_asia_matches": 0,
        "bets": []
    }

    for match_data in finished:
        results["total_matches"] += 1
        match_id = match_data["match_id"]
        match_name = match_data["name"]
        csv_path = _resolve_csv_path(match_id)

        if not csv_path.exists():
            continue

        rows = _normalize_halftime_minutes(_read_csv_rows(csv_path))
        if len(rows) < 20:
            continue

        # Resultado final — usar última fila con scores válidos (evitar filas pre_partido al final)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))

        if gl_final is None or gv_final is None:
            continue

        # Verificar que el partido finalizó
        last_min = _final_match_minute(rows)
        if last_min is None or last_min < 85:
            continue

        total_final = int(gl_final) + int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Detectar liga usando el helper compartido GR8
        # _detect_tarde_asia_liga normaliza guiones→espacios, cubriendo tanto
        # nombres de display ("Al Hilal") como match_ids con guiones ("al-hilal-...").
        match_url = match_data.get("url", "")
        liga_match = _detect_tarde_asia_liga(match_name, match_url, match_id)

        # Verificar si es liga objetivo
        if liga_match == "Unknown":
            continue

        # Obtener hora UTC de primera fila
        # NOTA: Por simplicidad, no filtramos por hora (necesitaríamos timezone del partido)
        # En producción, esto vendría de metadata con timezone local
        first_row = rows[0]
        timestamp_utc = first_row.get("timestamp_utc", "")

        # Extraer hora UTC (solo para display, no filtramos por hora)
        hora_local = "Unknown"
        if timestamp_utc and "T" in timestamp_utc:
            try:
                hora_part = timestamp_utc.split("T")[1].split(":")[0]
                hora_int = int(hora_part)
                hora_local = f"{hora_int:02d}:00 UTC"
            except:
                hora_local = "N/A"

        # Si llegamos aquí, es un partido tarde de liga objetivo
        results["tarde_asia_matches"] += 1

        # Buscar primera fila con cuotas Over 2.5
        bet_placed = False
        for idx, row in enumerate(rows):
            if bet_placed:
                break

            minuto = _to_float(row.get("minuto", ""))
            if minuto is None or minuto > 15:  # Solo primeros 15 min
                continue

            # Obtener cuota Over 2.5
            over_25_odds = _to_float(row.get("back_over25", ""))
            if not over_25_odds or over_25_odds <= 1:
                continue

            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue

            # Min duration: wait min_dur rows before entering
            if min_dur > 1:
                end_idx = idx + min_dur - 1
                if end_idx >= len(rows):
                    continue  # not enough rows remaining
                row = rows[end_idx]
                _min_e = _to_float(row.get("minuto", ""))
                if _min_e is not None:
                    minuto = _min_e

            # Colocar apuesta
            bet_placed = True
            actual_min = int(minuto)
            score_at_trigger = f"{int(gl)}-{int(gv)}"

            # Resultado
            won = total_final > 2.5
            stake = 10
            _ta_entry_idx = (idx + min_dur - 1) if min_dur > 1 else idx
            _stab_ta, _cons_ta = _count_odds_stability(rows, _ta_entry_idx, "back_over25", over_25_odds or 0)
            pl = round((over_25_odds - 1) * stake * 0.95, 2) if won else -stake
            pl_conservative = round((_cons_ta - 1) * stake * 0.95, 2) if won else -stake

            results["bets"].append({
                "match": match_name,
                "match_id": match_id,
                "minuto": actual_min,
                "score": score_at_trigger,
                "back_over_odds": round(over_25_odds, 2),
                "lay_trigger": _to_float(row.get("lay_over25", "")) or None,
                "over_line": "Over 2.5",
                "ft_score": ft_score,
                "won": won,
                "pl": pl,
                "pl_conservative": pl_conservative,
                "conservative_odds": round(_cons_ta, 2),
                "liga": liga_match,
                "hora_local": hora_local,
                "stability_count": _stab_ta,
                "timestamp_utc": row.get("timestamp_utc", ""),
                "País": row.get("País", "Desconocido"),
                "Liga": row.get("Liga", "Desconocida"),
            })

    # Calcular summary
    total_bets = len(results["bets"])
    wins = sum(1 for b in results["bets"] if b["won"])
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    total_pl = sum(b["pl"] for b in results["bets"])
    total_stake = total_bets * 10
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }

    return results




def analyze_strategy_momentum_xg(version: str = "v1", min_dur: int = 1) -> dict:
    """
    Momentum Dominante x xG: BACK equipo con dominancia en tiros a puerta pero xG no convertido

    Concepto: Equipo dominante con xG alto pero pocos goles indica regresión a la media → apostar a que ganará.

    Versiones disponibles:
    - v1 (ULTRA RELAJADAS): SoT >=1, ratio >=1.1x, xG underperf >0.15, Min 10-80, Odds 1.4-6.0
      → 66.7% WR, 52.2% ROI (12 triggers)
    - v2 (MÁXIMAS): SoT >=1, ratio >=1.05x, xG underperf >0.1, Min 5-85, Odds 1.3-8.0
      → 60% WR, 68.7% ROI (15 triggers)

    Apuesta: BACK equipo dominante (Home o Away)

    Args:
        version: "v1" (ultra relajadas, más consistente) o "v2" (máximas, mayor ROI)

    Returns:
        {
            "total_matches": int,
            "momentum_triggers": int,
            "summary": {...},
            "bets": [...],
            "version": str
        }
    """
    # Configuración según versión
    if version == "v2":
        # V2 MÁXIMAS: Mayor ROI pero menos consistente
        config = {
            "sot_min": 1,
            "sot_ratio_min": 1.05,
            "xg_underperf_min": 0.1,
            "min_minute": 0,
            "max_minute": 90,
            "min_odds": 1.3,
            "max_odds": 8.0,
            "label": "MÁXIMAS"
        }
    else:  # v1 por defecto
        # V1 ULTRA RELAJADAS: Más consistente (66.7% WR)
        config = {
            "sot_min": 1,
            "sot_ratio_min": 1.1,
            "xg_underperf_min": 0.15,
            "min_minute": 0,
            "max_minute": 90,
            "min_odds": 1.4,
            "max_odds": 6.0,
            "label": "ULTRA RELAJADAS"
        }

    finished = _get_all_finished_matches()

    results = {
        "total_matches": 0,
        "momentum_triggers": 0,
        "bets": []
    }

    for match_data in finished:
        results["total_matches"] += 1
        match_id = match_data["match_id"]
        match_name = match_data["name"]
        csv_path = _resolve_csv_path(match_id)

        if not csv_path.exists():
            continue

        rows = _normalize_halftime_minutes(_read_csv_rows(csv_path))
        if len(rows) < 20:
            continue

        # Resultado final — usar última fila con scores válidos (evitar filas pre_partido al final)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))

        if gl_final is None or gv_final is None:
            continue

        # Verificar que finalizó
        last_min = _final_match_minute(rows)
        if last_min is None or last_min < 85:
            continue

        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Buscar trigger de momentum dominante
        bet_placed = False
        for idx, row in enumerate(rows):
            if bet_placed:
                break

            if row.get("estado_partido") != "en_juego":
                continue

            minuto = _to_float(row.get("minuto", ""))
            if minuto is None or minuto < config["min_minute"] or minuto > config["max_minute"]:
                continue

            # Stats necesarias
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            xg_local = _to_float(row.get("xg_local", ""))
            xg_visitante = _to_float(row.get("xg_visitante", ""))
            sot_local = _to_float(row.get("tiros_puerta_local", ""))
            sot_visitante = _to_float(row.get("tiros_puerta_visitante", ""))
            back_home_odds = _to_float(row.get("back_home", ""))
            back_away_odds = _to_float(row.get("back_away", ""))

            # Validar datos mínimos (alineado con live: solo xG requerido, goles default 0)
            if xg_local is None or xg_visitante is None:
                continue
            if gl is None:
                gl = 0
            if gv is None:
                gv = 0
            if sot_local is None:
                sot_local = 0
            if sot_visitante is None:
                sot_visitante = 0

            # Calcular xG underperformance
            xg_underperf_local = xg_local - gl
            xg_underperf_visitante = xg_visitante - gv

            # Determinar equipo dominante via helper GR8 compartido
            dominant_team, back_odds, sot_ratio_used = _detect_momentum_dominant(
                sot_local=sot_local,
                sot_visitante=sot_visitante,
                xg_underperf_local=xg_underperf_local,
                xg_underperf_visitante=xg_underperf_visitante,
                back_home=back_home_odds,
                back_away=back_away_odds,
                cfg=config,
            )
            # BT uses lowercase "home"/"away"; normalise to match rest of BT code
            if dominant_team == "Home":
                dominant_team = "home"
            elif dominant_team == "Away":
                dominant_team = "away"

            if dominant_team is None:
                continue

            # Min duration: wait min_dur rows before entering
            if min_dur > 1:
                end_idx = idx + min_dur - 1
                if end_idx >= len(rows):
                    continue  # not enough rows remaining
                row = rows[end_idx]
                _min_e = _to_float(row.get("minuto", ""))
                if _min_e is not None:
                    minuto = _min_e

            # Trigger encontrado
            bet_placed = True
            results["momentum_triggers"] += 1

            # Verificar resultado
            if dominant_team == "home":
                won = gl_final > gv_final
                team_label = "Local"
                xg_underperf = xg_underperf_local
            else:
                won = gv_final > gl_final
                team_label = "Visitante"
                xg_underperf = xg_underperf_visitante

            # Calcular P/L con cuota conservadora (mínimo en ventana de estabilidad)
            stake = 10
            _mx_odds_col = "back_home" if dominant_team == "home" else "back_away"
            _mx_entry_idx = (idx + min_dur - 1) if min_dur > 1 else idx
            _stab_mx, _cons_mx = _count_odds_stability(rows, _mx_entry_idx, _mx_odds_col, back_odds or 0)
            pl = round((back_odds - 1) * stake * 0.95, 2) if won else -stake
            pl_conservative = round((_cons_mx - 1) * stake * 0.95, 2) if won else -stake

            # Calcular riesgo por tiempo + marcador
            risk_info = calculate_time_score_risk(
                strategy=f"momentum_xg_{version}",
                minute=minuto,
                home_score=int(gl),
                away_score=int(gv),
                dominant_team=dominant_team
            )

            _mx_lay_col = "lay_home" if dominant_team == "home" else "lay_away"
            results["bets"].append({
                "match": match_name,
                "match_id": match_id,
                "minuto": int(minuto),
                "score_at_trigger": f"{int(gl)}-{int(gv)}",
                "dominant_team": team_label,
                "sot_ratio": round(sot_ratio_used, 2),
                "xg_underperf": round(xg_underperf, 2),
                "back_odds": round(back_odds, 2),
                "lay_trigger": _to_float(row.get(_mx_lay_col, "")) or None,
                "ft_score": ft_score,
                "won": won,
                "pl": pl,
                "pl_conservative": pl_conservative,
                "conservative_odds": round(_cons_mx, 2),
                "stability_count": _stab_mx,
                "timestamp_utc": row.get("timestamp_utc", ""),
                "risk_level": risk_info["risk_level"],
                "risk_reason": risk_info["risk_reason"],
                "time_remaining": risk_info["time_remaining"],
                "deficit": risk_info["deficit"],
                "País": row.get("País", "Desconocido"),
                "Liga": row.get("Liga", "Desconocida"),
            })

    # Calcular summary
    total_bets = len(results["bets"])
    wins = sum(1 for b in results["bets"] if b["won"])
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    total_pl = sum(b["pl"] for b in results["bets"])
    total_stake = total_bets * 10
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }

    results["version"] = version
    results["config_label"] = config["label"]

    return results
