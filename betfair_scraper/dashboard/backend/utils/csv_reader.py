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
    _detect_draw_equalizer_trigger,
    _detect_draw_22_trigger,
    _detect_lay_over45_blowout_trigger,
    _detect_over35_early_goals_trigger,
    _detect_lay_draw_away_leading_trigger,
    _detect_lay_cs11_trigger,
    _get_over_odds_field,
)


def _sd_fixed(odds_field: str, rec: str, entry_keys: list) -> callable:
    """Factory for SD strategies with a fixed odds column."""
    def _ex(t):
        o = t.get(odds_field)
        if not o:
            return None
        entry = {k: (round(t[k], 2) if isinstance(t.get(k), float) else t.get(k)) for k in entry_keys}
        entry["odds"] = round(o, 2)
        return (o, f"{rec} @ {o:.2f}", entry)
    return _ex


def _sd_score(rec_prefix: str, entry_keys: list) -> callable:
    """Factory for CS-score-based SD strategies."""
    def _ex(t):
        score = t.get("trigger_score")
        if not score:
            return None
        col = f"back_rc_{score.replace('-', '_')}"
        o = t.get(col)
        if not o:
            return None
        entry = {k: (round(t[k], 2) if isinstance(t.get(k), float) else t.get(k)) for k in entry_keys}
        entry["odds"] = round(o, 2)
        return (o, f"{rec_prefix} {score} @ {o:.2f}", entry)
    return _ex


def _sd_team(home_field: str, away_field: str, team_field: str,
             rec_prefix: str, entry_keys: list) -> callable:
    """Factory for team-based SD strategies (home OR away)."""
    def _ex(t):
        o = t.get(home_field) or t.get(away_field)
        if not o:
            return None
        team = t.get(team_field)
        label = "HOME" if team == "local" else "AWAY"
        entry = {k: (round(t[k], 2) if isinstance(t.get(k), float) else t.get(k)) for k in entry_keys}
        entry["odds"] = round(o, 2)
        return (o, f"{rec_prefix} {label} @ {o:.2f}", entry)
    return _ex


def _match_score(trigger_score: str, ft_gl: int, ft_gv: int) -> bool:
    """Check if FT score matches trigger_score string (e.g. '2-1')."""
    try:
        tgl, tgv = (int(x) for x in trigger_score.split("-"))
        return ft_gl == tgl and ft_gv == tgv
    except Exception:
        return False


# ── Version-specific trigger wrappers for original 7 strategies ─────────────

def _make_back_draw_trigger(version: str):
    """Wrap _detect_back_draw_00_trigger with version-specific flag check."""
    _FLAG = {"v15": "passes_v15", "v2": "passes_v2r", "v2r": "passes_v2r",
             "v3": "passes_v3", "v4": "passes_v4"}
    _flag_key = _FLAG.get(version)
    def _t(rows, curr_idx, cfg):
        t = _detect_back_draw_00_trigger(rows, curr_idx, cfg)
        if t is None:
            return None
        if _flag_key and not t.get(_flag_key):
            return None
        return t
    return _t


def _make_drift_trigger(version: str):
    """Wrap _detect_odds_drift_trigger with version-specific additional checks."""
    def _t(rows, curr_idx, cfg):
        t = _detect_odds_drift_trigger(rows, curr_idx, cfg)
        if t is None:
            return None
        if version == "v2":
            return t if t["goal_diff"] >= 2 else None
        elif version == "v3":
            return t if t["drift_pct"] >= 100 else None
        elif version == "v4":
            return t if (t["minuto"] > 45 and t["odds_now"] <= 5.0) else None
        elif version in ("v5", "v6"):
            if t["odds_now"] > 5.0:
                return None
            if version == "v6":
                mom_gap_min = float(cfg.get("drift_mom_gap_min", 0))
                if mom_gap_min > 0:
                    synth = _compute_synthetic_at_trigger(rows, curr_idx)
                    mom_gap = synth.get("momentum_gap")
                    if mom_gap is None or mom_gap < mom_gap_min:
                        return None
        return t
    return _t


def _make_momentum_trigger(version: str):
    """Wrap _detect_momentum_xg_trigger with version-specific default cfg."""
    _DEFAULTS = {
        "v1": {"sot_min": 1, "sot_ratio_min": 1.1,  "xg_underperf_min": 0.15,
               "min_m": 10, "max_m": 80, "min_odds": 1.4, "max_odds": 6.0},
        "v2": {"sot_min": 1, "sot_ratio_min": 1.05, "xg_underperf_min": 0.1,
               "min_m": 5,  "max_m": 85, "min_odds": 1.3, "max_odds": 8.0},
    }
    _defaults = _DEFAULTS.get(version, _DEFAULTS["v1"])
    def _t(rows, curr_idx, cfg):
        return _detect_momentum_xg_trigger(rows, curr_idx, {**_defaults, **cfg})
    return _t


def _make_xg_trigger(version: str):
    """Wrap _detect_xg_underperformance_trigger with version-specific default cfg."""
    _DEFAULTS = {
        "base": {"xg_excess_min": 0.5, "sot_min": 0, "minute_max": 90,  "minute_min": 15},
        "v2":   {"xg_excess_min": 0.5, "sot_min": 2, "minute_max": 90,  "minute_min": 15},
        "v3":   {"xg_excess_min": 0.5, "sot_min": 2, "minute_max": 70,  "minute_min": 15},
    }
    _defaults = _DEFAULTS.get(version, _DEFAULTS["base"])
    def _t(rows, curr_idx, cfg):
        return _detect_xg_underperformance_trigger(rows, curr_idx, {**_defaults, **cfg})
    return _t


# ── Extractor functions for original 7 strategies ───────────────────────────

def _extract_drift(t):
    odds = t.get("odds_now")
    if not odds:
        return None
    team = t.get("team", "")
    label = "HOME" if team == "home" else "AWAY"
    return (odds, f"BACK {label} @ {odds:.2f}",
            {"team": label, "drift_pct": round(t.get("drift_pct", 0), 1),
             "odds_before": round(t.get("odds_before", 0), 2)})


def _extract_xg_underperf(t):
    odds = t.get("back_over")
    if not odds:
        return None
    total = t.get("total_goals", 0)
    over_line = total + 0.5
    return (odds, f"BACK Over {over_line} @ {odds:.2f}",
            {"team": t.get("team", ""), "xg_excess": round(t.get("xg_excess", 0), 2),
             "sot_team": t.get("sot_team", 0)})


def _extract_momentum(t):
    odds = t.get("back_odds")
    if not odds:
        return None
    dt = t.get("dominant_team", "")
    label = "HOME" if dt == "Home" else "AWAY"
    return (odds, f"BACK {label} @ {odds:.2f}",
            {"dominant_team": dt, "odds": round(odds, 2)})


def _extract_over_odds(t):
    """Extractor for goal_clustering and pressure_cooker (over_odds in trigger dict)."""
    odds = t.get("over_odds")
    if not odds:
        return None
    total = t.get("total_goals", 0)
    over_line = total + 0.5
    return (odds, f"BACK Over {over_line} @ {odds:.2f}",
            {"total_goals": total, "odds": round(odds, 2)})


# Registry of strategies using the simple trigger+extract pattern.
# Each entry: key, display name, trigger fn, description, extractor fn, win fn.
# win_fn(trig_dict, ft_gl, ft_gv) -> bool used for BT; ignored in LIVE.
_STRATEGY_REGISTRY = [
    ("over25_2goal",    "BACK O2.5 2-Goal Lead",
     _detect_over25_2goal_trigger,
     "Back Over 2.5 when a team leads by 2+ goals with SoT activity",
     _sd_fixed("back_over25", "BACK OVER 2.5", ["goal_diff", "sot_total"]),
     lambda t, gl, gv: (gl + gv) >= 3),

    ("under35_late",    "BACK U3.5 Late",
     _detect_under35_late_trigger,
     "Back Under 3.5 when exactly 3 goals scored and xG is low",
     _sd_fixed("back_under35", "BACK UNDER 3.5", ["total_goals_trigger", "xg_total"]),
     lambda t, gl, gv: (gl + gv) <= 3),

    ("longshot",        "BACK Longshot Leading",
     _detect_longshot_trigger,
     "Back the pre-match longshot when they are leading late",
     _sd_team("back_home", "back_away", "longshot_team", "BACK", ["longshot_team", "xg_longshot"]),
     lambda t, gl, gv: (gl > gv) if t.get("longshot_team") == "local" else (gv > gl)),

    ("cs_close",        "BACK CS Close",
     _detect_cs_close_trigger,
     "Back current Correct Score at close game (2-1 / 1-2)",
     _sd_score("BACK CS", ["score"]),
     lambda t, gl, gv: _match_score(t.get("trigger_score", ""), gl, gv)),

    ("cs_one_goal",     "BACK CS One-Goal",
     _detect_cs_one_goal_trigger,
     "Back current Correct Score at 1-0 / 0-1",
     _sd_score("BACK CS", ["score"]),
     lambda t, gl, gv: _match_score(t.get("trigger_score", ""), gl, gv)),

    ("ud_leading",      "BACK Underdog Leading",
     _detect_ud_leading_trigger,
     "Back the underdog when they are leading late",
     _sd_team("back_home", "back_away", "ud_team", "BACK", ["ud_team", "ud_pre_odds"]),
     lambda t, gl, gv: (gl > gv) if t.get("ud_team") == "local" else (gv > gl)),

    ("home_fav_leading","BACK Home Fav Leading",
     _detect_home_fav_leading_trigger,
     "Back home favourite when leading late",
     _sd_fixed("back_home", "BACK HOME", ["home_pre_odds", "lead"]),
     lambda t, gl, gv: gl > gv),

    ("cs_20",           "BACK CS 2-0/0-2",
     _detect_cs_20_trigger,
     "Back current Correct Score at 2-0 / 0-2",
     _sd_score("BACK CS", ["score"]),
     lambda t, gl, gv: _match_score(t.get("trigger_score", ""), gl, gv)),

    ("cs_big_lead",     "BACK CS Big Lead",
     _detect_cs_big_lead_trigger,
     "Back current Correct Score at big lead (3-0/0-3/3-1/1-3)",
     _sd_score("BACK CS", ["score"]),
     lambda t, gl, gv: _match_score(t.get("trigger_score", ""), gl, gv)),

    ("lay_over45_v3",   "LAY Over 4.5 V3",
     _detect_lay_over45_v3_trigger,
     "Lay Over 4.5 tight: goals<=1, tight minute window",
     _sd_fixed("lay_over45", "LAY OVER 4.5", ["total_goals_trigger"]),
     lambda t, gl, gv: (gl + gv) <= 4),

    ("draw_xg_conv",    "BACK Draw xG Convergence",
     _detect_draw_xg_conv_trigger,
     "Back Draw when xG converges in tied match",
     _sd_fixed("back_draw", "BACK DRAW", ["xg_diff", "score_at_trigger"]),
     lambda t, gl, gv: gl == gv),

    ("poss_extreme",    "BACK Over 0.5 Poss Extreme",
     _detect_poss_extreme_trigger,
     "Back Over 0.5 when possession is extremely one-sided at 0-0",
     _sd_fixed("back_over05", "BACK OVER 0.5", ["poss_max"]),
     lambda t, gl, gv: (gl + gv) >= 1),

    ("cs_00",           "BACK CS 0-0 Early",
     _detect_cs_00_trigger,
     "Back CS 0-0 in early window with low xG and SoT",
     _sd_fixed("back_rc_0_0", "BACK CS 0-0", ["xg_total", "sot_total"]),
     lambda t, gl, gv: gl == 0 and gv == 0),

    ("over25_2goals",   "BACK O2.5 Two Goals",
     _detect_over25_2goals_trigger,
     "Back Over 2.5 when exactly 2 goals scored in stable row",
     _sd_fixed("back_over25", "BACK OVER 2.5", ["total_goals_trigger"]),
     lambda t, gl, gv: (gl + gv) >= 3),

    ("draw_11",         "BACK Draw 1-1",
     _detect_draw_11_trigger,
     "Back Draw when score is exactly 1-1 late",
     _sd_fixed("back_draw", "BACK DRAW", []),
     lambda t, gl, gv: gl == gv),

    ("under35_3goals",  "BACK U3.5 3-Goal Lid",
     _detect_under35_3goals_trigger,
     "Back Under 3.5 when exactly 3 goals and low xG",
     _sd_fixed("back_under35", "BACK UNDER 3.5", ["xg_total"]),
     lambda t, gl, gv: (gl + gv) <= 3),

    ("away_fav_leading","BACK Away Fav Leading",
     _detect_away_fav_leading_trigger,
     "Back away favourite when leading late",
     _sd_fixed("back_away", "BACK AWAY", ["away_pre_odds", "lead"]),
     lambda t, gl, gv: gv > gl),

    ("under45_3goals",  "BACK U4.5 3-Goals Low xG",
     _detect_under45_3goals_trigger,
     "Back Under 4.5 when exactly 3 goals and xG < threshold",
     _sd_fixed("back_under45", "BACK UNDER 4.5", ["xg_total"]),
     lambda t, gl, gv: (gl + gv) <= 4),

    ("cs_11",           "BACK CS 1-1 Late",
     _detect_cs_11_trigger,
     "Back CS 1-1 late in the game",
     _sd_fixed("back_rc_1_1", "BACK CS 1-1", []),
     lambda t, gl, gv: gl == 1 and gv == 1),

    ("draw_equalizer",  "BACK Draw Equalizer Late",
     _detect_draw_equalizer_trigger,
     "Back Draw after underdog equalizes against pre-match favourite",
     _sd_fixed("back_draw", "BACK DRAW", []),
     lambda t, gl, gv: gl == gv),

    ("draw_22",         "BACK Draw 2-2 Late",
     _detect_draw_22_trigger,
     "Back Draw when score is exactly 2-2 late in the game",
     _sd_fixed("back_draw", "BACK DRAW", []),
     lambda t, gl, gv: gl == gv),

    ("lay_over45_blowout", "LAY Over 4.5 Blowout",
     _detect_lay_over45_blowout_trigger,
     "Lay Over 4.5 in 3-0/0-3 blowouts: winning team drops intensity post 3rd goal",
     _sd_fixed("lay_over45", "LAY OVER 4.5", ["goal_minute", "sot_post"]),
     lambda t, gl, gv: (gl + gv) <= 4),

    ("over35_early_goals", "BACK Over 3.5 Early Goals",
     _detect_over35_early_goals_trigger,
     "Back Over 3.5 when exactly 3 goals scored before min 65: market underprices 4th goal",
     _sd_fixed("back_over35", "BACK OVER 3.5", ["goals_total", "score"]),
     lambda t, gl, gv: (gl + gv) >= 4),

    ("lay_draw_away_leading", "LAY Draw Away Leading",
     _detect_lay_draw_away_leading_trigger,
     "LAY Draw when away leads by 1 + low xG: home has no attacking quality to equalize",
     _sd_fixed("lay_draw", "LAY DRAW", ["score", "xg_total"]),
     lambda t, gl, gv: gl != gv),

    ("lay_cs11", "LAY CS 1-1 at 0-1",
     _detect_lay_cs11_trigger,
     "LAY CS 1-1 when score is 0-1 late: market overprices 1-1 via familiarity bias, only 4% actual rate",
     _sd_fixed("lay_rc_1_1", "LAY CS 1-1", ["score"]),
     lambda t, gl, gv: not (gl == 1 and gv == 1)),

    # ─── Original 7 strategies — unified BT/LIVE via registry ──────────────

    # Back Empate 0-0 (6 versions)
    ("back_draw_00_v1",  "BACK Draw 0-0 (V1)",  _make_back_draw_trigger("v1"),
     "Back Draw 0-0: minute window, no extra filters",
     _sd_fixed("back_draw", "BACK DRAW", ["xg_total", "shots_total"]),
     lambda t, gl, gv: gl == gv),

    ("back_draw_00_v15", "BACK Draw 0-0 (V15)", _make_back_draw_trigger("v15"),
     "Back Draw 0-0: xG filter (V15)",
     _sd_fixed("back_draw", "BACK DRAW", ["xg_total"]),
     lambda t, gl, gv: gl == gv),

    ("back_draw_00_v2",  "BACK Draw 0-0 (V2)",  _make_back_draw_trigger("v2"),
     "Back Draw 0-0: xG + possession filter (V2)",
     _sd_fixed("back_draw", "BACK DRAW", ["xg_total", "poss_diff"]),
     lambda t, gl, gv: gl == gv),

    ("back_draw_00_v2r", "BACK Draw 0-0 (V2R)", _make_back_draw_trigger("v2r"),
     "Back Draw 0-0: xG + possession filter (V2R)",
     _sd_fixed("back_draw", "BACK DRAW", ["xg_total", "poss_diff"]),
     lambda t, gl, gv: gl == gv),

    ("back_draw_00_v3",  "BACK Draw 0-0 (V3)",  _make_back_draw_trigger("v3"),
     "Back Draw 0-0: xG dominance filter (V3)",
     _sd_fixed("back_draw", "BACK DRAW", ["xg_total"]),
     lambda t, gl, gv: gl == gv),

    ("back_draw_00_v4",  "BACK Draw 0-0 (V4)",  _make_back_draw_trigger("v4"),
     "Back Draw 0-0: opta gap filter (V4)",
     _sd_fixed("back_draw", "BACK DRAW", ["xg_total"]),
     lambda t, gl, gv: gl == gv),

    # Odds Drift Contrarian (6 versions)
    ("odds_drift_v1",  "Odds Drift Contrarian (V1)", _make_drift_trigger("v1"),
     "Back drifting team: base drift check",
     _extract_drift,
     lambda t, gl, gv: (gl > gv) if t.get("team") == "home" else (gv > gl)),

    ("odds_drift_v2",  "Odds Drift Contrarian (V2)", _make_drift_trigger("v2"),
     "Back drifting team: goal diff >= 2",
     _extract_drift,
     lambda t, gl, gv: (gl > gv) if t.get("team") == "home" else (gv > gl)),

    ("odds_drift_v3",  "Odds Drift Contrarian (V3)", _make_drift_trigger("v3"),
     "Back drifting team: drift >= 100%",
     _extract_drift,
     lambda t, gl, gv: (gl > gv) if t.get("team") == "home" else (gv > gl)),

    ("odds_drift_v4",  "Odds Drift Contrarian (V4)", _make_drift_trigger("v4"),
     "Back drifting team: minute > 45, odds <= 5",
     _extract_drift,
     lambda t, gl, gv: (gl > gv) if t.get("team") == "home" else (gv > gl)),

    ("odds_drift_v5",  "Odds Drift Contrarian (V5)", _make_drift_trigger("v5"),
     "Back drifting team: odds <= 5",
     _extract_drift,
     lambda t, gl, gv: (gl > gv) if t.get("team") == "home" else (gv > gl)),

    ("odds_drift_v6",  "Odds Drift Contrarian (V6)", _make_drift_trigger("v6"),
     "Back drifting team: odds <= 5 + momentum gap",
     _extract_drift,
     lambda t, gl, gv: (gl > gv) if t.get("team") == "home" else (gv > gl)),

    # Momentum Dominante x xG (2 versions)
    ("momentum_xg_v1", "Momentum Dominante x xG (V1)", _make_momentum_trigger("v1"),
     "Back dominant team with unscored xG (V1: sot_ratio>1.1, min 10-80)",
     _extract_momentum,
     lambda t, gl, gv: (gl > gv) if t.get("dominant_team") == "Home" else (gv > gl)),

    ("momentum_xg_v2", "Momentum Dominante x xG (V2)", _make_momentum_trigger("v2"),
     "Back dominant team with unscored xG (V2: sot_ratio>1.05, min 5-85)",
     _extract_momentum,
     lambda t, gl, gv: (gl > gv) if t.get("dominant_team") == "Home" else (gv > gl)),

    # Pressure Cooker
    ("pressure_cooker", "Pressure Cooker", _detect_pressure_cooker_trigger,
     "Back Over when tied with goals (1-1+) between min 65-75",
     _extract_over_odds,
     lambda t, gl, gv: (gl + gv) > t.get("total_goals", 0)),

    # Goal Clustering
    ("goal_clustering", "Goal Clustering", _detect_goal_clustering_trigger,
     "Back Over after recent goal with active SoT",
     _extract_over_odds,
     lambda t, gl, gv: (gl + gv) > t.get("total_goals", 0)),

    # xG Underperformance (3 versions)
    ("xg_underperformance_base", "xG Underperformance (Base)", _make_xg_trigger("base"),
     "Back Over when losing team generates high xG (base: no sot filter)",
     _extract_xg_underperf,
     lambda t, gl, gv: (gl + gv) > t.get("total_goals", 0)),

    ("xg_underperformance_v2",   "xG Underperformance (V2)",   _make_xg_trigger("v2"),
     "Back Over when losing team generates high xG (V2: sot_min>=2)",
     _extract_xg_underperf,
     lambda t, gl, gv: (gl + gv) > t.get("total_goals", 0)),

    ("xg_underperformance_v3",   "xG Underperformance (V3)",   _make_xg_trigger("v3"),
     "Back Over when losing team generates high xG (V3: sot_min>=2, max_min=70)",
     _extract_xg_underperf,
     lambda t, gl, gv: (gl + gv) > t.get("total_goals", 0)),

    # Tarde Asia
    ("tarde_asia", "Tarde Asia", _detect_tarde_asia_trigger,
     "Back Over 2.5 in Asian/high-scoring leagues before min 15",
     _sd_fixed("back_over25", "BACK Over 2.5", ["liga"]),
     lambda t, gl, gv: (gl + gv) >= 3),
]

_STRATEGY_REGISTRY_KEYS = {e[0] for e in _STRATEGY_REGISTRY}

# Market group for same-market deduplication in analyze_cartera().
# Strategies that share a market group → only the earliest bet (by minuto) per
# (match_id, market_group) pair is kept.  Strategies not listed here are treated
# as having a unique market (i.e. no deduplication applied).
_STRATEGY_MARKET: dict[str, str] = {
    "under35_late":   "under_3.5",
    "under35_3goals": "under_3.5",
    "draw_11":        "draw",
    "draw_xg_conv":   "draw",
    "draw_equalizer": "draw",
    "draw_22":        "draw",
    "lay_over45_blowout": "lay_over_4.5",
    "over25_2goal":   "over_2.5",
    "goal_clustering":"over_2.5",
    "pressure_cooker":"over_2.5",
    "lay_draw_away_leading": "lay_draw",
    "lay_cs11":       "lay_cs",
}

# Mapping from registry keys that use legacy config keys to their legacy key.
# Used for both min_duration lookup and config synthesis.
_LEGACY_MIN_DUR_KEY: dict[str, str] = {
    "goal_clustering":         "clustering",
    "pressure_cooker":         "pressure",
    "back_draw_00_v1":         "draw",
    "back_draw_00_v15":        "draw",
    "back_draw_00_v2":         "draw",
    "back_draw_00_v2r":        "draw",
    "back_draw_00_v3":         "draw",
    "back_draw_00_v4":         "draw",
    "odds_drift_v1":           "drift",
    "odds_drift_v2":           "drift",
    "odds_drift_v3":           "drift",
    "odds_drift_v4":           "drift",
    "odds_drift_v5":           "drift",
    "odds_drift_v6":           "drift",
    "xg_underperformance_base":"xg",
    "xg_underperformance_v2":  "xg",
    "xg_underperformance_v3":  "xg",
    "momentum_xg_v1":          "momentum_xg",
    "momentum_xg_v2":          "momentum_xg",
}

_ORIG_REGISTRY_MAP = [
    ("draw", [
        ("back_draw_00_v1", "v1"), ("back_draw_00_v15", "v15"),
        ("back_draw_00_v2", "v2"), ("back_draw_00_v2r", "v2r"),
        ("back_draw_00_v3", "v3"), ("back_draw_00_v4",  "v4"),
    ]),
    ("drift", [
        ("odds_drift_v1", "v1"), ("odds_drift_v2", "v2"), ("odds_drift_v3", "v3"),
        ("odds_drift_v4", "v4"), ("odds_drift_v5", "v5"), ("odds_drift_v6", "v6"),
    ]),
    ("clustering",  [("goal_clustering", None)]),
    ("pressure",    [("pressure_cooker", None)]),
    ("xg", [
        ("xg_underperformance_base", "base"),
        ("xg_underperformance_v2",   "v2"),
        ("xg_underperformance_v3",   "v3"),
    ]),
    ("momentum_xg", [("momentum_xg_v1", "v1"), ("momentum_xg_v2", "v2")]),
    ("tarde_asia",  [("tarde_asia", None)]),
]

_ORIG_DEFAULT_VERS = {"draw": "v2r", "drift": "v1", "xg": "base", "momentum_xg": "off"}

# camelCase config keys → snake_case keys expected by trigger functions.
# Each value is a list because some camelCase keys map to multiple snake_case aliases
# used by different trigger functions (e.g. minuteMin → min_minute AND minute_min).
_CAMEL_TO_SNAKE_ALIASES: dict[str, list[str]] = {
    "minuteMin":   ["min_minute", "minute_min", "m_min", "min_m"],
    "minuteMax":   ["max_minute", "minute_max", "m_max", "max_m"],
    "sotMin":      ["sot_min"],
    "sotRatioMin": ["sot_ratio_min"],
    "xgRemMin":    ["xg_rem_min"],
    "xgExcessMin": ["xg_excess_min"],
    "xgUnderperfMin": ["xg_underperf_min"],
    "xgMax":       ["xg_max"],
    "possMax":     ["poss_max"],
    "shotsMax":    ["shots_max"],
    "driftMin":    ["drift_min_pct"],
    "oddsMax":     ["max_odds"],
    "oddsMin":     ["min_odds", "odds_min"],
    "goalDiffMin": ["goal_diff_min"],
    "momGapMin":   ["drift_mom_gap_min"],
}


def _cfg_add_snake_keys(cfg: dict) -> dict:
    """Return cfg enriched with snake_case aliases for camelCase keys.

    Trigger functions in strategy_triggers.py read snake_case keys (e.g.
    ``sot_min``, ``max_minute``) while cartera_config.json stores camelCase
    (``sotMin``, ``minuteMax``). This function adds the snake_case equivalents
    so both coexist without modifying the config schema.
    Only adds keys that are not already present.
    """
    out = dict(cfg)
    for camel, snakes in _CAMEL_TO_SNAKE_ALIASES.items():
        if camel in cfg:
            for snake in snakes:
                if snake not in out:
                    out[snake] = cfg[camel]
    return out


def _build_registry_config_map(s: dict) -> dict:
    """Map registry strategy keys → effective config with enabled state.

    Synthesizes legacy config keys (clustering, pressure, draw, etc.) to registry
    keys (goal_clustering, pressure_cooker, back_draw_00_v2r, etc.).
    Existing entries in s are NOT overwritten — only missing keys are synthesized.
    """
    result = dict(s)
    for (legacy_key, entries) in _ORIG_REGISTRY_MAP:
        _old_cfg = s.get(legacy_key, {})
        base_enabled = _old_cfg.get("enabled", False)
        default_ver = _ORIG_DEFAULT_VERS.get(legacy_key)
        if default_ver is not None:
            active_ver = "off" if not base_enabled else (_old_cfg.get("version") or default_ver)
        else:
            active_ver = "on" if base_enabled else "off"
        for (_reg_key, _ver) in entries:
            if _reg_key in result:
                continue  # Don't overwrite (analytics.py may have already synthesized)
            if _ver is None:
                _is_active = active_ver == "on"
            else:
                _is_active = active_ver != "off" and active_ver == _ver
            result[_reg_key] = _cfg_add_snake_keys({**_old_cfg, "enabled": _is_active})
    return result


def _analyze_strategy_simple(key: str, trigger_fn, extractor_fn, win_fn,
                              cfg: dict, min_dur: int) -> list:
    """Generic BT runner for registry-based strategies.

    Iterates all finished matches, applies trigger_fn with min_dur persistence,
    extracts odds via extractor_fn, and evaluates win_fn against FT score.
    """
    finished = _get_all_finished_matches()
    bets = []
    for match_data in finished:
        rows = match_data.get("rows") or _read_csv_rows(match_data["csv_path"])
        if not rows:
            continue
        match_id = match_data["match_id"]
        last = rows[-1]
        try:
            ft_gl = int(float(last.get("goles_local") or ""))
            ft_gv = int(float(last.get("goles_visitante") or ""))
        except (ValueError, TypeError):
            continue

        # Merge match metadata so triggers that need it (e.g. tarde_asia) can access it.
        effective_cfg = {**cfg,
                         "match_id":   match_id,
                         "match_name": match_data.get("name", ""),
                         "match_url":  match_data.get("url", "")}

        first_seen = None
        trig_data = None
        for curr_idx in range(len(rows)):
            trig = trigger_fn(rows, curr_idx, effective_cfg)
            if trig:
                if first_seen is None:
                    first_seen = curr_idx
                    trig_data = trig
                if curr_idx >= first_seen + min_dur - 1:
                    extracted = extractor_fn(trig_data)
                    if extracted is None:
                        break
                    odds, rec, entry_cond = extracted
                    won = win_fn(trig_data, ft_gl, ft_gv)
                    is_lay = rec.upper().startswith("LAY")
                    if is_lay:
                        pl = round(0.95 if won else -(odds - 1), 2)
                    else:
                        pl = round((odds - 1) * 0.95 if won else -1.0, 2)
                    try:
                        minuto = int(float(rows[first_seen].get("minuto") or 0))
                    except (ValueError, TypeError):
                        minuto = 0
                    bets.append({
                        "match_id": match_id,
                        "strategy": key,
                        "minuto": minuto,
                        "back_odds": round(odds, 2),
                        "won": won,
                        "pl": pl,
                        "País": rows[first_seen].get("País", "Desconocido"),
                        "Liga": rows[first_seen].get("Liga", "Desconocida"),
                        "timestamp_utc": rows[first_seen].get("timestamp_utc", ""),
                    })
                    break
            else:
                first_seen = None
                trig_data = None
    return bets


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


def analyze_cartera() -> dict:
    """Combined portfolio view of all strategies with flat and managed bankroll simulations."""
    import json as _json
    from api.config import load_config as _load_config
    cfg = _load_config()
    md = cfg.get("min_duration", {})

    # Manual cache key including min_duration values and registry strategy enabled states
    _reg_enabled = {e[0]: cfg.get("strategies", {}).get(e[0], {}).get("enabled", False) for e in _STRATEGY_REGISTRY}
    cache_key = f"cartera_{_json.dumps(md, sort_keys=True)}_{_json.dumps(_reg_enabled, sort_keys=True)}"
    if cache_key in _result_cache:
        return _result_cache[cache_key]

    all_bets = []

    # All strategies use registry loop — single unified BT runner for all 39 strategies.
    _reg_cfg_map = _build_registry_config_map(cfg.get("strategies", {}))
    for (_key, _name, _trigger_fn, _desc, _extract_fn, _win_fn) in _STRATEGY_REGISTRY:
        _s_cfg = _reg_cfg_map.get(_key, {})
        if not _s_cfg.get("enabled"):
            continue  # Skip disabled strategies
        _min_dur_key = _LEGACY_MIN_DUR_KEY.get(_key, _key)
        _min_dur = md.get(_min_dur_key, md.get(_key, 1))
        _s_bets = _analyze_strategy_simple(_key, _trigger_fn, _extract_fn, _win_fn, _cfg_add_snake_keys(_s_cfg), _min_dur)
        for b in _s_bets:
            all_bets.append({**b, "strategy_label": _name})

    all_bets.sort(key=lambda x: x.get("timestamp_utc", ""))

    # Deduplicate: one bet per market per match (take earliest by minuto).
    # Strategies sharing a market group (e.g. under35_late + under35_3goals → under_3.5)
    # compete for the same slot; only the first trigger wins.
    _seen_market: dict = {}
    _deduped: list = []
    for _b in sorted(all_bets, key=lambda x: x.get("minuto", 0) or 0):
        _mid = _b.get("match_id", "")
        _mkt = _STRATEGY_MARKET.get(_b.get("strategy", ""), None)
        if _mkt is None:
            _deduped.append(_b)  # not in a shared-market group → always keep
        else:
            _mkey = (_mid, _mkt)
            if _mkey not in _seen_market:
                _seen_market[_mkey] = True
                _deduped.append(_b)
            # else: drop — duplicate market bet on the same match
    all_bets = _deduped
    all_bets.sort(key=lambda x: x.get("timestamp_utc", ""))  # re-sort after dedup

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
            _key: _strat_summary([b for b in all_bets if b["strategy"] == _key])
            for _key, *_ in _STRATEGY_REGISTRY
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
    if strategy.startswith("back_draw_00"):
        return "back_draw", "lay_draw", bet.get("back_draw") or 0.0

    if strategy.startswith("xg_underperformance") or strategy in ("goal_clustering", "pressure_cooker", "tarde_asia"):
        over_line = bet.get("over_line", "")
        m = re.search(r"(\d+\.?\d+)", over_line or "")
        key = m.group(1) if m else ""
        bc, lc = _OVER_CO_COLS.get(key, ("", ""))
        return bc, lc, bet.get("back_over_odds") or 0.0

    if strategy.startswith("odds_drift"):
        team = bet.get("team", "")
        bc = "back_home" if team == "home" else "back_away"
        lc = "lay_home" if team == "home" else "lay_away"
        return bc, lc, bet.get("back_odds") or 0.0

    if strategy.startswith("momentum_xg"):
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
    if strategy.startswith("back_draw_00"):
        return (gl + gv) > (gl_trigger + gv_trigger)  # cualquier gol perjudica el empate
    if strategy.startswith("momentum_xg"):
        if team == "Local": return gv > gv_trigger    # rival (visitante) marcó
        if team == "Away":  return gl > gl_trigger    # rival (local) marcó
    if strategy.startswith("odds_drift"):
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

# ── Trigger first-data cache ──
# Stores the trigger dict from the FIRST time a strategy fired for a given match,
# so detect_betting_signals can use the same saved data that BT uses (trig_data from
# first_seen row).  Keyed by (match_id, strategy_key).  Cleared when trigger stops firing.
_trigger_first_data: dict[tuple, dict] = {}


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

    # --- Minimum duration config ---
    # Each strategy uses its own key from the min_duration config (analytics.py passes _min_duration).
    _full_min_dur = versions.get("_min_duration", {})
    min_dur_map = {
        _key: int(_full_min_dur.get(_LEGACY_MIN_DUR_KEY.get(_key, _key), 1))
        for _key in _STRATEGY_REGISTRY_KEYS
    }

    # --- Load first-seen timestamps from in-memory cache (loaded once from signals_log.csv) ---
    first_seen_map = _load_first_seen_cache()

    def _get_strategy_family(strategy_key: str) -> str:
        # Each strategy is its own family — uses its own key for min_duration lookup.
        return strategy_key

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
        elif rec.startswith("LAY"):
            # LAY signals are not subject to BACK-side conflict detection:
            # LAY Over = economically equivalent to BACK Under (same direction).
            # Treating them as conflicting would incorrectly block valid stacking.
            return None
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

        # === REGISTRY STRATEGIES (trigger-based, one-shot detection) ===
        # Each strategy is a one-shot trigger: check current state, emit signal if conditions met.
        # Config lives in cartera_config.json under strategies.<key>
        # Synthesize legacy key mappings (clustering→goal_clustering, etc.) if not already done.
        strategy_configs = _build_registry_config_map(versions.get("_strategy_configs", {}))
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

        # --- Registry strategies: loop — all 39 strategies, uniform path ---
        for (_key, _name, _fn, _desc, _extract, _win_fn) in _STRATEGY_REGISTRY:
            _cfg_entry = _cfg_add_snake_keys(strategy_configs.get(_key, {}))
            if not (_cfg_entry.get("enabled") and goals_data_ok):
                _trigger_first_data.pop((match_id, _key), None)
                continue
            # Merge match metadata so triggers that need it (e.g. tarde_asia) can access it.
            _cfg_with_meta = {**_cfg_entry,
                              "match_id":   match_id,
                              "match_name": match.get("name", ""),
                              "match_url":  match.get("url", "")}
            _trig = _fn(rows, len(rows) - 1, _cfg_with_meta)
            if not _trig:
                # Trigger no longer active — reset first-data so next activation is fresh.
                _trigger_first_data.pop((match_id, _key), None)
                continue
            # Use trigger data from FIRST activation (mirrors BT's trig_data from first_seen row).
            _cache_key = (match_id, _key)
            if _cache_key not in _trigger_first_data:
                _trigger_first_data[_cache_key] = _trig
            _extracted = _extract(_trigger_first_data[_cache_key])
            if _extracted is None:
                continue
            _odds_val, _rec_str, _entry_cond = _extracted
            _sd_signal(_key, _name, _rec_str, _odds_val, _desc, _entry_cond)

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


