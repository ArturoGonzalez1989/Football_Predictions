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
    # #1 — BACK Over 2.5 from 2-Goal Lead (min=55-78, goal_diff>=2, SoT>=3, odds=1.5-8)
    "over25_2goal": {
        "m_min": 55, "m_max": 78, "goal_diff_min": 2,
        "sot_total_min": 3, "odds_min": 1.5, "odds_max": 8.0,
    },
    # #2 — BACK Under 3.5 Low-xG Late (3 goles min=65-78, xG<2.0)
    "under35_late": {
        "m_min": 65, "m_max": 78, "goals_exact": 3, "xg_max": 2.0,
    },
    # #3  — LAY O4.5 V3 Tight (min=55-75, goals<=1, odds<=15)
    "lay_over45_v3": {
        "m_min": 55, "m_max": 75, "goals_max": 1, "odds_max": 15,
    },
    # #4 — BACK Draw xG Convergence (H14; min=60-80, xg_diff<=0.5)
    "draw_xg_conv": {
        "m_min": 60, "m_max": 80, "xg_diff_max": 0.5,
    },
    # #5 — BACK Over 0.5 Possession Extreme (H32; min=30-50, poss>=58%)
    "poss_extreme": {
        "m_min": 30, "m_max": 50, "poss_min": 58,
    },
    # #6 — BACK Longshot Resistente (H35; min=65-90, xg_longshot>=0.2, odds=1.3-8)
    "longshot": {
        "m_min": 65, "m_max": 90, "xg_min": 0.2, "odds_min": 1.3, "odds_max": 8.0,
    },
    # #7 — BACK CS 0-0 Early (H37; edge en odds [7-9), min=28-30, xG<1.5, SoT<=3)
    "cs_00": {
        "m_min": 28, "m_max": 30, "xg_max": 1.5, "sot_max": 3,
        "odds_min": 7.0, "odds_max": 9.0,
    },
    # #8 — BACK Over 2.5 from Two Goals (H39; min=50-60, odds<=4.0)
    "over25_2goals": {
        "m_min": 50, "m_max": 60, "odds_max": 4.0,
    },
    # #9 — BACK Correct Score 2-1/1-2 (H49; min=70-80, no odds cap)
    "cs_close": {
        "m_min": 70, "m_max": 80,
    },
    # #10 — BACK Correct Score 1-0/0-1 (H53; min=68-85, no odds cap)
    "cs_one_goal": {
        "m_min": 68, "m_max": 85,
    },
    # #11 — BACK Draw at 1-1 (H58; min=70-85, odds>1.5)
    "draw_11": {
        "m_min": 70, "m_max": 85, "odds_min": 1.5,
    },
    # #12 — BACK Underdog Leading Late (H59; min=55-80, ud_pre>=2.0, max_lead=1)
    "ud_leading": {
        "m_min": 55, "m_max": 80, "ud_min_pre_odds": 2.0, "max_lead": 1,
    },
    # #13 — BACK Under 3.5 Three-Goal Lid (H66; min=68-82, xg_max=3.0)
    "under35_3goals": {
        "m_min": 68, "m_max": 82, "xg_max": 3.0,
    },
    # #14 — BACK Away Favourite Leading Late (H67; min=65-85, max_lead=1, odds<=5.0)
    "away_fav_leading": {
        "m_min": 65, "m_max": 85, "max_lead": 1, "odds_max": 5.0,
    },
    # #15 — BACK Home Favourite Leading Late (H70; min=65-85, maxLead=3, favMax=2.5)
    "home_fav_leading": {
        "m_min": 65, "m_max": 85, "max_lead": 3, "fav_max": 2.5,
    },
    # #16 — BACK Under 4.5 Three Goals Low xG (H71; min=65-85, xG<2.0)
    "under45_3goals": {
        "m_min": 65, "m_max": 85, "xg_max": 2.0,
    },
    # #17 — BACK CS 1-1 Late (H77; min=75-90, odds_max=8.0)
    "cs_11": {
        "m_min": 75, "m_max": 90, "odds_max": 8.0,
    },
    # #18 — BACK CS 2-0/0-2 Late (H79; min=75-90, odds_max=10.0)
    "cs_20": {
        "m_min": 75, "m_max": 90, "odds_max": 10.0,
    },
    # #19 — BACK CS Big Lead Late (H81; 3-0/0-3/3-1/1-3, min=70-85, odds_max=8.0)
    "cs_big_lead": {
        "m_min": 70, "m_max": 85, "odds_max": 8.0,
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
