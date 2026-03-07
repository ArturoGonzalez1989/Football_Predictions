"""
SD (Strategy Designer) approved strategies — configs and evaluator.

Approved configs from strategies/sd_strategy_tracker.md (2026-03-03).
19 strategies validated and approved for notebook/backtest integration.

Key difference vs _eval_combo() in the notebook:
  - Uses minStability=1 (SD strategies are one-shot triggers, not continuous signals)
  - Returns same dict format as _eval_combo() for full compatibility
"""

import math


# ---------------------------------------------------------------------------
# Approved configs per strategy (from sd_strategy_tracker.md)
# Keys must match what the _apply_sd_* filter functions expect (sd_filters.py)
# ---------------------------------------------------------------------------

SD_APPROVED_CONFIGS: dict = {
    # #1 — LAY Over 4.5 Late Shield (optimized: min=65-75, goals<=2, odds<=8)
    # odds_max reducido de 15 a 8: liability -(odds-1) demasiado alta en odds>8
    # (loss a odds=15 borra 14.7 wins; odds>8 implica <12.5% prob Over4.5 → filtrar)
    "lay_over45": {
        "m_min": 65, "m_max": 75, "goals_max": 2, "odds_max": 8, "xg_max": 999,
    },
    # #2 — BACK Leader Stat Domination (min=55-70, sot>=4, rival<=1)
    "leader_dom": {
        "m_min": 55, "m_max": 70, "sot_min": 4, "sot_max_rival": 1,
    },
    # #3 — BACK Over 2.5 from 2-Goal Lead (min=55-78, goal_diff>=2, SoT>=3, odds=1.5-8)
    "over25_2goal": {
        "m_min": 55, "m_max": 78, "goal_diff_min": 2,
        "sot_total_min": 3, "odds_min": 1.5, "odds_max": 8.0,
    },
    # #4 — BACK Over 2.5 Confluence (H23 tied + Clustering; min=50-70, SoT>=4)
    "confluence": {
        "m_min": 50, "m_max": 70, "sot_total_min": 4,
    },
    # #5 — BACK Draw After Equalizer (equalizador min=58-85, odds=2.0-15.0)
    "draw_eq": {
        "m_min": 58, "m_max": 85, "odds_min": 2.0, "odds_max": 15.0,
    },
    # #6 — BACK Under 2.5 Scoreless Late (0-0 min=64-80, xG<2.0)
    "under25_scl": {
        "m_min": 64, "m_max": 80, "xg_max": 2.0,
    },
    # #7 — BACK Under 3.5 Low-xG Late (3 goles min=65-78, xG<2.0)
    "under35_late": {
        "m_min": 65, "m_max": 78, "goals_exact": 3, "xg_max": 2.0,
    },
    # #8 — BACK Draw Late Stalemate (empatado con goles min=70-90, xG_residual>=-0.5, odds>=2.5)
    # odds_min=2.5: ROI negativo en odds<2.5 según reporte sd_report_draw_late_stalemate.md
    "draw_stl": {
        "m_min": 70, "m_max": 90, "xg_res_min": -0.5, "odds_min": 2.5,
    },
    # #9  — LAY O4.5 V3 Tight (min=55-75, goals<=1, odds<=15)
    "lay_over45_v3": {
        "m_min": 55, "m_max": 75, "goals_max": 1, "odds_max": 15,
    },
    # #10 — LAY O4.5 V2+V4 (min=62-75, goals<=2, odds<=15, xG<2.0)
    "lay_over45_v2v4": {
        "m_min": 62, "m_max": 75, "goals_max": 2, "odds_max": 15, "xg_max": 2.0,
    },
    # #11 — LAY O4.5 Late entry (min=68-78, goals<=2, odds<=10)
    # odds_max alineado con max_odds global del portfolio (10.0) para backtest pesimista:
    # solo evaluamos bets que realmente pasarían el filtro del combo.
    "lay_over45_late": {
        "m_min": 68, "m_max": 78, "goals_max": 2, "odds_max": 10,
    },
    # #12 — BACK Draw xG Convergence (H14; min=60-80, xg_diff<=0.5)
    "draw_xg_conv": {
        "m_min": 60, "m_max": 80, "xg_diff_max": 0.5,
    },
    # #13 — Corner+SoT -> Over 2.5 (H19; min=45-75, SoT>=4, corners>=5)
    "corner_sot": {
        "m_min": 45, "m_max": 75, "sot_min": 4, "corners_min": 5,
    },
    # #14 — BACK Over 2.5 V4 +xG (goal_diff>=2, SoT>=3, xG>=0.5, odds=1.5-8)
    "over25_2goal_v4": {
        "m_min": 55, "m_max": 78, "goal_diff_min": 2,
        "sot_total_min": 3, "xg_min": 0.5,
    },
    # #15 — BACK Over 3.5 FH Goals (H21; min=45-60, goals>=2)
    "over35_fh": {
        "m_min": 45, "m_max": 60, "goals_min": 2,
    },
    # #16 — BACK Over 2.5 from 1-1 (H23; tied 1-1+, sot_total>=4, min=50-70)
    "over25_11": {
        "m_min": 50, "m_max": 70, "sot_total_min": 4,
    },
    # #17 — BACK Over 0.5 Possession Extreme (H32; min=30-50, poss>=58%)
    "poss_extreme": {
        "m_min": 30, "m_max": 50, "poss_min": 58,
    },
    # #18 — BACK Longshot Resistente (H35; min=65-90, xg_longshot>=0.2, odds=1.3-8)
    "longshot": {
        "m_min": 65, "m_max": 90, "xg_min": 0.2, "odds_min": 1.3, "odds_max": 8.0,
    },
    # #19 — BACK CS 0-0 Early (H37; edge en odds [7-9), min=28-30, xG<1.5, SoT<=3)
    "cs_00": {
        "m_min": 28, "m_max": 30, "xg_max": 1.5, "sot_max": 3,
        "odds_min": 7.0, "odds_max": 9.0,
    },
    # #20 — BACK Over 2.5 from Two Goals (H39; min=50-60, odds<=4.0)
    "over25_2goals": {
        "m_min": 50, "m_max": 60, "odds_max": 4.0,
    },
    # #21 — LAY Over 2.5 Scoreless Late (H41; 0-0 min=60-70, layMax=20)
    "lay_over25_scl": {
        "m_min": 60, "m_max": 70, "lay_max": 20.0,
    },
    # #22 — LAY Over 1.5 Scoreless Fortress (H44; 0-0 min=68-78, layMax=8)
    "lay_over15_scl": {
        "m_min": 68, "m_max": 78, "lay_max": 8.0,
    },
    # #23 — BACK Under 2.5 One-Goal Late (H46; 1 goal min=75-85, xG<2.0, SoT<=6)
    "under25_1goal": {
        "m_min": 75, "m_max": 85, "xg_max": 2.0, "sot_max": 6,
    },
    # #24 — LAY Under 2.5 Tied at 1-1 (H48; 1-1 min=55-65, layMax=2.5)
    "lay_under25_11": {
        "m_min": 55, "m_max": 65, "lay_max": 2.5,
    },
    # #25 — BACK Correct Score 2-1/1-2 (H49; min=70-80, no odds cap)
    "cs_close": {
        "m_min": 70, "m_max": 80,
    },
    # #26 — BACK Correct Score 1-0/0-1 (H53; min=68-85, no odds cap)
    "cs_one_goal": {
        "m_min": 68, "m_max": 85,
    },
    # #27 — BACK Draw at 1-1 (H58; min=70-85, odds>1.5)
    "draw_11": {
        "m_min": 70, "m_max": 85, "odds_min": 1.5,
    },
    # #28 — BACK Underdog Leading Late (H59; min=55-80, ud_pre>=2.0, max_lead=1)
    "ud_leading": {
        "m_min": 55, "m_max": 80, "ud_min_pre_odds": 2.0, "max_lead": 1,
    },
    # #29 — BACK Under 3.5 Three-Goal Lid (H66; min=68-82, xg_max=3.0)
    "under35_3goals": {
        "m_min": 68, "m_max": 82, "xg_max": 3.0,
    },
    # #30 — BACK Away Favourite Leading Late (H67; min=65-85, max_lead=1, odds<=5.0)
    "away_fav_leading": {
        "m_min": 65, "m_max": 85, "max_lead": 1, "odds_max": 5.0,
    },
    # #31 — BACK Home Favourite Leading Late (H70; min=65-85, maxLead=3, favMax=2.5)
    "home_fav_leading": {
        "m_min": 65, "m_max": 85, "max_lead": 3, "fav_max": 2.5,
    },
    # #32 — BACK Under 4.5 Three Goals Low xG (H71; min=65-85, xG<2.0)
    "under45_3goals": {
        "m_min": 65, "m_max": 85, "xg_max": 2.0,
    },
}


# ---------------------------------------------------------------------------
# Helper functions (mirrors notebook patterns)
# ---------------------------------------------------------------------------

def _wilson_ci(wins: int, total: int) -> tuple:
    """Wilson score confidence interval (95%)."""
    if total == 0:
        return 0.0, 100.0
    z = 1.96
    p = wins / total
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return round((center - spread) * 100, 1), round((center + spread) * 100, 1)


def _compute_max_dd(bets: list) -> float:
    """Maximum flat-stake drawdown from a list of bet dicts."""
    running = 0.0
    peak = 0.0
    max_dd = 0.0
    for b in bets:
        running += b.get("pl", 0)
        if running > peak:
            peak = running
        dd = peak - running
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ---------------------------------------------------------------------------
# Main evaluator
# ---------------------------------------------------------------------------

def eval_sd(
    bets: list,
    adj: dict,
    min_bets: int = 10,
    min_roi: float = 1.0,
    min_ic95_low: float = 0.0,
) -> "dict | None":
    """
    Evaluate SD strategy bets.

    Identical to _eval_combo() in the notebook except:
      - stability is always forced to 1 (SD triggers are one-shot, not continuous)

    Args:
        bets:          List of bet dicts (output of _apply_sd_* filter functions)
        adj:           Realistic adjustment dict (G_ADJ from the notebook).
                       minStability will be overridden to 1.
        min_bets:      Minimum N to consider valid (default 10). Use G_MIN_BETS_SD
                       (dynamic, scales with dataset size: max(15, n_partidos//25)).
        min_roi:       Minimum flat ROI% to consider valid (default 1.0)
        min_ic95_low:  Minimum Wilson IC95 lower bound % (default 0.0 = disabled).
                       Use IC95_MIN_LOW from global-config for statistical confidence gate.

    Returns:
        Dict with keys: N, WR%, IC95, IC95_low, P/L, ROI%, Max DD, Score
        Or None if bets don't pass the gates.
    """
    try:
        from utils.csv_reader import _apply_realistic_adj  # noqa: PLC0415
    except ImportError:
        # Fallback: _apply_realistic_adj not available (should not happen in notebook)
        _apply_realistic_adj = None  # type: ignore[assignment]

    # Override stability: SD strategies are one-shot triggers
    sd_adj = {**adj, "minStability": 1}

    if _apply_realistic_adj is not None:
        bets = _apply_realistic_adj(bets, sd_adj)

    if len(bets) < min_bets:
        return None

    wins = sum(1 for b in bets if b.get("won", False))
    total = len(bets)
    flat_pl = sum(b.get("pl", 0) for b in bets)
    flat_roi = flat_pl / total * 100

    if flat_roi < min_roi:
        return None

    ci_l, ci_h = _wilson_ci(wins, total)

    if ci_l < min_ic95_low:
        return None

    max_dd = _compute_max_dd(bets)
    win_pct = wins / total * 100
    score = round(win_pct * flat_roi / max(max_dd, 1) * math.log(total + 1), 3)

    return {
        "N": total,
        "WR%": round(win_pct, 1),
        "IC95": f"[{ci_l:.1f}–{ci_h:.1f}]",
        "IC95_low": ci_l,
        "P/L": round(flat_pl, 2),
        "ROI%": round(flat_roi, 1),
        "Max DD": round(max_dd, 2),
        "Score": score,
    }
