"""
Preset optimizer — Python backend.
Implements Phase 1 + Phase 2 of findBestCombo (cartera.ts) in Python,
avoiding Chrome's RESULT_CODE_HUNG and Out of Memory issues.

Phase 1 (~6.6M combos): finds best VersionCombo + BankrollMode + RiskFilter.
Phase 2 (~7776 combos): finds best RealisticAdjustments given Phase 1 result.
Phase 3 (5 combos): momentum minute range — stays in browser (trivial).

Mirrors exactly: evaluateCombo, simulateCartera, filterXXXBets,
applyRealisticAdjustments from cartera.ts.
"""
import asyncio
import json
import logging
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Make sure backend utils are importable from worker processes
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

router = APIRouter()

# Pre-computed preset CSVs live here (written by optimizer_cli.py after each run).
_PRESETS_DIR = _backend_dir.parent.parent / "data" / "presets"

# ── Version → params mappings (mirrors cartera.ts exactly) ──────────────────

DRAW_PARAMS: Dict[str, Dict] = {
    "v1":  dict(xg_max=1.0, poss_max=100, shots_max=20, xg_dom_asym=False, min_min=30, min_max=90),
    "v15": dict(xg_max=0.6, poss_max=25,  shots_max=20, xg_dom_asym=False, min_min=30, min_max=90),
    "v2r": dict(xg_max=0.6, poss_max=20,  shots_max=8,  xg_dom_asym=False, min_min=30, min_max=90),
    "v2":  dict(xg_max=0.5, poss_max=20,  shots_max=8,  xg_dom_asym=False, min_min=30, min_max=90),
    "v3":  dict(xg_max=0.6, poss_max=25,  shots_max=20, xg_dom_asym=True,  min_min=30, min_max=90),
}

XG_PARAMS: Dict[str, Dict] = {
    "base": dict(sot_min=0, xg_excess_min=0.5, min_min=0, min_max=70),
    "v2":   dict(sot_min=2, xg_excess_min=0.5, min_min=0, min_max=70),
    "v3":   dict(sot_min=2, xg_excess_min=0.5, min_min=0, min_max=70),
}

DRIFT_PARAMS: Dict[str, Dict] = {
    "v1": dict(goal_diff_min=0, drift_min=30,  odds_max=1e9, min_min=0,  min_max=90, mom_gap_min=0),
    "v2": dict(goal_diff_min=2, drift_min=30,  odds_max=1e9, min_min=0,  min_max=90, mom_gap_min=0),
    "v3": dict(goal_diff_min=0, drift_min=100, odds_max=1e9, min_min=0,  min_max=90, mom_gap_min=0),
    "v4": dict(goal_diff_min=0, drift_min=30,  odds_max=5,   min_min=45, min_max=90, mom_gap_min=0),
    "v5": dict(goal_diff_min=0, drift_min=30,  odds_max=5,   min_min=0,  min_max=90, mom_gap_min=0),
    "v6": dict(goal_diff_min=0, drift_min=30,  odds_max=5,   min_min=0,  min_max=90, mom_gap_min=200),
}

CLUSTERING_PARAMS: Dict[str, Dict] = {
    "v2": dict(sot_min=3, min_min=0, min_max=90, xg_rem_min=0.0),
    "v3": dict(sot_min=3, min_min=0, min_max=60, xg_rem_min=0.0),
    "v4": dict(sot_min=3, min_min=0, min_max=80, xg_rem_min=0.8),
}

# Min odds per strategy — mirrors MIN_ODDS_BY_STRATEGY in cartera.ts
MIN_ODDS: Dict[str, float] = {
    "back_draw_00":        1.93,
    "xg_underperformance": 1.51,
    "odds_drift":          1.65,
    "goal_clustering":     1.73,
    "pressure_cooker":     1.83,
    "tarde_asia":          1.83,
    "momentum_xg_v1":      1.65,
    "momentum_xg_v2":      1.83,
}

# Opts arrays — mirrors cartera.ts findBestCombo exactly
DRAW_OPTS         = ["v1", "v15", "v2r", "v2", "v3", "off"]
XG_OPTS           = ["base", "v2", "v3", "off"]
DRIFT_OPTS        = ["v1", "v2", "v3", "v4", "v5", "v6", "off"]
CLUSTERING_OPTS   = ["v2", "v3", "v4", "off"]
PRESSURE_OPTS     = ["v1", "off"]
TARDESIA_OPTS     = ["v1", "off"]
MOMENTUM_OPTS     = ["v1", "v2", "off"]
LAY15_OPTS        = ["off", "v1", "v2"]
LAY_DA_OPTS       = ["off", "on"]
LAY25_OPTS        = ["off", "on"]
BSD_OPTS          = ["off", "on"]
BO15E_OPTS        = ["off", "on"]
LFF_OPTS          = ["off", "on"]
BR_OPTS           = ["fixed", "half_kelly", "dd_protection", "anti_racha"]
RISK_OPTS         = ["all", "no_risk", "with_risk", "medium"]

# ── SD (Strategy Designer) PARAMS + OPTS ─────────────────────────────────────
# 19 new strategies from sd_strategy_tracker.  Generators in auxiliar/sd_generators.py,
# filters in auxiliar/sd_filters.py.  Here we add the versioned PARAMS + OPTS for
# Phase 1, plus on/off toggles for the simpler strategies.

SD_LAY_O45_PARAMS: Dict[str, Dict] = {
    "v1":   dict(min_min=65, min_max=75, goals_max=2, odds_max=15),
    "v3":   dict(min_min=55, min_max=75, goals_max=1, odds_max=15),
    "v2v4": dict(min_min=55, min_max=75, goals_max=2, odds_max=15, xg_max=2.0),
    "late": dict(min_min=68, min_max=78, goals_max=2, odds_max=15),
}
SD_LEADER_DOM_PARAMS: Dict[str, Dict] = {
    "v1": dict(min_min=55, min_max=70, sot_min=4, sot_max_rival=1),
    "v2": dict(min_min=55, min_max=80, sot_min=3, sot_max_rival=2),
    "v3": dict(min_min=50, min_max=75, sot_min=3, sot_max_rival=1),
}
SD_OVER25_2G_PARAMS: Dict[str, Dict] = {
    "v1": dict(min_min=55, min_max=78, goal_diff_min=2, sot_total_min=3, odds_min=1.5, odds_max=8.0),
    "v3": dict(min_min=55, min_max=75, goal_diff_min=2, sot_total_min=4, odds_min=1.5, odds_max=8.0),
    "v4": dict(min_min=55, min_max=78, goal_diff_min=2, sot_total_min=3, odds_min=1.5, odds_max=8.0, xg_min=0.5),
}

SD_LAY_O45_OPTS    = ["off", "v1", "v3", "v2v4", "late"]
SD_LEADER_DOM_OPTS = ["off", "v1", "v2", "v3"]
SD_OVER25_2G_OPTS  = ["off", "v1", "v3", "v4"]
SD_CONFLUENCE_OPTS = ["off", "on"]
SD_DRAW_EQ_OPTS    = ["off", "on"]
SD_UNDER25_OPTS    = ["off", "on"]
SD_UNDER35_OPTS    = ["off", "on"]
SD_DRAW_STL_OPTS   = ["off", "on"]
SD_DRAW_CONV_OPTS  = ["off", "on"]
SD_CORNER_SOT_OPTS = ["off", "on"]
SD_O25_V4_OPTS     = ["off", "on"]
SD_O35_FH_OPTS     = ["off", "on"]
SD_O25_11_OPTS     = ["off", "on"]
SD_POSS_OPTS       = ["off", "on"]
SD_LONGSHOT_OPTS   = ["off", "on"]
SD_CS00_OPTS       = ["off", "on"]

# All (draw, xg) pairs — 6×4 = 24 combinations (includes draw="off", xg="off").
# Used to split work across up to 24 workers instead of just 6 (draw-only).
ALL_DRAW_XG_PAIRS = [(d, x) for d in DRAW_OPTS for x in XG_OPTS]

_PHASE1_TOTAL = (
    len(["v1", "v15", "v2r", "v2", "v3", "off"]) *       # DRAW
    len(["base", "v2", "v3", "off"]) *                    # XG
    len(["v1", "v2", "v3", "v4", "v5", "v6", "off"]) *   # DRIFT
    len(["v2", "v3", "v4", "off"]) *                      # CLUSTERING
    len(["v1", "off"]) *                                   # PRESSURE
    len(["v1", "off"]) *                                   # TARDESIA
    len(["v1", "v2", "off"]) *                            # MOMENTUM
    len(["off", "v1", "v2"]) *                            # LAY15
    len(["off", "on"]) *                                   # LAY_DA
    len(["off", "on"]) *                                   # LAY25
    len(["off", "on"]) *                                   # BSD
    len(["off", "on"]) *                                   # BO15E
    len(["off", "on"]) *                                   # LFF
    len(["fixed", "half_kelly", "dd_protection", "anti_racha"]) *  # BR
    len(["all", "no_risk", "with_risk", "medium"])        # RISK
)  # = 12,386,304
# NOTE: SD strategies are NOT included in _PHASE1_TOTAL or _phase1_worker.
# Adding 16 extra toggles (5*4*4*2^13 = ~5.2B multiplier) would make the
# brute-force search computationally infeasible.  SD strategies are optimized
# independently in the notebook (strategies_designer.ipynb) via per-strategy
# grid searches, then combined additively with the existing cartera.
_PHASE2_TOTAL = 2 * 3 * 3 * 3 * 2 * 2 * 3 * 3 * 3  # = 7776

# Module-level state — updated from the worker thread, read by GET endpoints.
# CPython's GIL makes dict mutation thread-safe for simple key reads/writes.
_opt_result: Optional[Dict] = None   # last completed result (None if not ready yet)
_opt_progress: Dict[str, Any] = {
    "running": False,
    "phase": "",
    "pct": 0,
    "message": "",
}

MAX_BETS_COMBO = {
    "draw": "v1", "xg": "base", "drift": "v1", "clustering": "v2",
    "pressure": "v1", "tardeAsia": "v1", "momentumXG": "v1",
    "layOver15": "v1", "layDrawAsym": "on", "layOver25Def": "on",
    "backSotDom": "on", "backOver15Early": "on", "layFalseFav": "on",
    # SD strategies — included in max_bets combo for completeness
    "sdLayO45": "v1", "sdLeaderDom": "v1", "sdOver25_2g": "v1",
    "sdConfluence": "on", "sdDrawEq": "on", "sdUnder25": "on",
    "sdUnder35": "on", "sdDrawStl": "on", "sdDrawConv": "on",
    "sdCornerSot": "on", "sdO25V4": "on", "sdO35Fh": "on",
    "sdO25_11": "on", "sdPoss": "on", "sdLongshot": "on", "sdCs00": "on",
    "br": "fixed",
}

# ── Wilson CI helper ─────────────────────────────────────────────────────────

def _wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple:
    """Returns (ci_low, ci_high) Wilson 95% CI for a proportion wins/n."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(max(0.0, center - margin) * 100, 1), round(min(1.0, center + margin) * 100, 1))


# ── Helper: get odds from a bet dict (mirrors getBetOdds in cartera.ts) ──────

_ODDS_KEYS = [
    "back_sot_odds", "back_over15_odds", "lay_false_fav_odds", "lay_draw_odds",
    "lay_over25_odds", "lay_over15_odds", "back_draw", "back_over_odds",
    "over_odds", "back_odds",
    # SD strategy odds keys
    "lay_over45_odds", "back_leader_odds", "back_over25_odds", "back_draw_eq_odds",
    "back_under25_odds", "back_under35_odds", "back_draw_stl_odds",
    "back_draw_conv_odds", "back_over35_odds", "back_over05_odds",
    "back_longshot_odds", "back_cs_00_odds",
]

def _get_bet_odds(b: Dict) -> float:
    for k in _ODDS_KEYS:
        v = b.get(k)
        if v is not None:
            try:
                fv = float(v)
                if fv > 0:
                    return fv
            except (ValueError, TypeError):
                pass
    return 2.0


def _meets_min_odds(b: Dict) -> bool:
    odds = _get_bet_odds(b)
    return odds >= MIN_ODDS.get(b.get("strategy", ""), 1.0)


def _fv(b: Dict, key: str) -> Optional[float]:
    """Safe float extraction from a bet field (None if missing/invalid)."""
    v = b.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ── Filter functions (mirrors cartera.ts filter*Bets exactly) ───────────────

def _filter_draw(bets: List[Dict], v: str) -> List[Dict]:
    if v not in DRAW_PARAMS:
        return []
    p = DRAW_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") != "back_draw_00":
            continue
        xg = _fv(b, "xg_total")
        if p["xg_max"] < 1.0 and xg is not None and xg >= p["xg_max"]:
            continue
        pd = _fv(b, "poss_diff")
        if p["poss_max"] < 100 and pd is not None and pd >= p["poss_max"]:
            continue
        st = _fv(b, "shots_total")
        if p["shots_max"] < 20 and st is not None and st >= p["shots_max"]:
            continue
        if p["xg_dom_asym"]:
            dom = _fv(b, "synth_xg_dominance")
            if dom is not None and 0.45 <= dom <= 0.55:
                continue
        mn = _fv(b, "minuto")
        if p["min_min"] > 0 and mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        result.append(b)
    return result


def _filter_xg(bets: List[Dict], v: str) -> List[Dict]:
    if v not in XG_PARAMS:
        return []
    p = XG_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") not in ("xg_underperformance", "xg_underperformance_base"):
            continue
        xe = _fv(b, "xg_excess")
        if p["xg_excess_min"] > 0 and xe is not None and xe < p["xg_excess_min"]:
            continue
        st = _fv(b, "sot_team")
        if p["sot_min"] > 0 and st is not None and st < p["sot_min"]:
            continue
        mn = _fv(b, "minuto")
        if p["min_min"] > 0 and mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        result.append(b)
    return result


def _filter_drift(bets: List[Dict], v: str) -> List[Dict]:
    if v not in DRIFT_PARAMS:
        return []
    p = DRIFT_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") not in ("odds_drift", "odds_drift_v1"):
            continue
        gd = _fv(b, "goal_diff")
        if p["goal_diff_min"] > 0 and gd is not None and gd < p["goal_diff_min"]:
            continue
        dp = _fv(b, "drift_pct")
        if p["drift_min"] > 30 and dp is not None and dp < p["drift_min"]:
            continue
        bo = _fv(b, "back_odds")
        if p["odds_max"] < 1e8 and bo is not None and bo > p["odds_max"]:
            continue
        mn = _fv(b, "minuto")
        if p["min_min"] > 0 and mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        mg = _fv(b, "synth_momentum_gap")
        if p["mom_gap_min"] > 0 and mg is not None and mg <= p["mom_gap_min"]:
            continue
        result.append(b)
    return result


def _filter_clustering(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    if v not in CLUSTERING_PARAMS:
        return []
    p = CLUSTERING_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") != "goal_clustering":
            continue
        sm = _fv(b, "sot_max")
        if p["sot_min"] > 0 and sm is not None and sm < p["sot_min"]:
            continue
        mn = _fv(b, "minuto")
        if p["min_min"] > 0 and mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        xr = _fv(b, "synth_xg_remaining")
        if p["xg_rem_min"] > 0 and xr is not None and xr < p["xg_rem_min"]:
            continue
        result.append(b)
    return result


def _filter_pressure(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "pressure_cooker"]


def _filter_tardesia(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "tarde_asia"]


def _filter_momentum(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    target = f"momentum_xg_{v}"  # "v1" → "momentum_xg_v1"
    return [b for b in bets if b.get("strategy") == target]


def _filter_lay_over15(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    result = []
    for b in bets:
        if b.get("strategy") != "lay_over15":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < 75:
            continue
        if mn is not None and mn >= 85:
            continue
        if v == "v1" and not b.get("passes_lay_v1"):
            continue
        if v == "v2" and not b.get("passes_lay_v2"):
            continue
        result.append(b)
    return result


def _filter_lay_draw_asym(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    result = []
    for b in bets:
        if b.get("strategy") != "lay_draw_asym":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < 65:
            continue
        if mn is not None and mn >= 75:
            continue
        xr = _fv(b, "xg_ratio")
        if xr is not None and xr < 2.5:
            continue
        result.append(b)
    return result


def _filter_lay_over25_def(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    result = []
    for b in bets:
        if b.get("strategy") != "lay_over25_def":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < 70:
            continue
        if mn is not None and mn >= 80:
            continue
        xt = _fv(b, "xg_total")
        if xt is not None and xt >= 1.2:
            continue
        tg = _fv(b, "total_goals_trigger")
        if tg is not None and tg > 1:
            continue
        result.append(b)
    return result


def _filter_back_sot_dom(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    result = []
    for b in bets:
        if b.get("strategy") != "back_sot_dom":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < 60:
            continue
        if mn is not None and mn > 80:
            continue
        sd = _fv(b, "sot_dominant")
        if sd is not None and sd < 4:
            continue
        sr = _fv(b, "sot_rival")
        if sr is not None and sr > 1:
            continue
        result.append(b)
    return result


def _filter_back_over15_early(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    result = []
    for b in bets:
        if b.get("strategy") != "back_over15_early":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < 25:
            continue
        if mn is not None and mn > 45:
            continue
        xt = _fv(b, "xg_total")
        if xt is not None and xt < 1.0:
            continue
        st = _fv(b, "sot_total")
        if st is not None and st < 4:
            continue
        tg = _fv(b, "total_goals_trigger")
        if tg is not None and tg > 1:
            continue
        result.append(b)
    return result


def _filter_lay_false_fav(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    result = []
    for b in bets:
        if b.get("strategy") != "lay_false_fav":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < 65:
            continue
        if mn is not None and mn > 85:
            continue
        xr = _fv(b, "xg_ratio")
        if xr is not None and xr < 2.0:
            continue
        fo = _fv(b, "fav_back_odds")
        if fo is not None and fo > 1.70:
            continue
        result.append(b)
    return result


# ── SD filter functions (mirrors auxiliar/sd_filters.py) ───────────────────────────
# These are available for future integration into the optimizer or for ad-hoc use.
# Currently NOT called from _phase1_worker (see note above _PHASE1_TOTAL).

def _filter_sd_lay_over45(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off" or v not in SD_LAY_O45_PARAMS:
        return []
    p = SD_LAY_O45_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") != "lay_over45":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        tg = _fv(b, "total_goals_trigger")
        if tg is not None and tg > p["goals_max"]:
            continue
        od = _fv(b, "lay_over45_odds")
        if od is not None and od > p["odds_max"]:
            continue
        if "xg_max" in p:
            xt = _fv(b, "xg_total")
            if xt is not None and xt >= p["xg_max"]:
                continue
        result.append(b)
    return result


def _filter_sd_leader_dom(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off" or v not in SD_LEADER_DOM_PARAMS:
        return []
    p = SD_LEADER_DOM_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") != "back_leader_dom":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        ls = _fv(b, "leader_sot")
        if ls is not None and ls < p["sot_min"]:
            continue
        rs = _fv(b, "rival_sot")
        if rs is not None and rs > p["sot_max_rival"]:
            continue
        result.append(b)
    return result


def _filter_sd_over25_2goal(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off" or v not in SD_OVER25_2G_PARAMS:
        return []
    p = SD_OVER25_2G_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") != "over25_2goal":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        gd = _fv(b, "goal_diff")
        if gd is not None and gd < p["goal_diff_min"]:
            continue
        st = _fv(b, "sot_total")
        if st is not None and st < p["sot_total_min"]:
            continue
        od = _fv(b, "back_over25_odds")
        if od is not None:
            if od < p.get("odds_min", 0):
                continue
            if od > p.get("odds_max", 999):
                continue
        if "xg_min" in p:
            xt = _fv(b, "xg_total")
            if xt is not None and xt < p["xg_min"]:
                continue
        result.append(b)
    return result


def _filter_sd_confluence(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "confluence_over25"]


def _filter_sd_draw_eq(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "draw_equalizer"]


def _filter_sd_under25_scl(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "under25_scoreless"]


def _filter_sd_under35_late(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "under35_late"]


def _filter_sd_draw_stl(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "draw_stalemate"]


def _filter_sd_draw_xg_conv(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "draw_xg_conv"]


def _filter_sd_corner_sot(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "corner_sot_over25"]


def _filter_sd_over25_2g_v4(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "over25_2goal_v4"]


def _filter_sd_over35_fh(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "over35_fh_goals"]


def _filter_sd_over25_11(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "over25_from_11"]


def _filter_sd_poss_extreme(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "poss_extreme"]


def _filter_sd_back_longshot(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "back_longshot"]


def _filter_sd_cs_00(bets: List[Dict], v: str) -> List[Dict]:
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "cs_00"]


def _filter_by_risk(bets: List[Dict], risk: str) -> List[Dict]:
    if risk == "all":
        return bets
    result = []
    for b in bets:
        r = b.get("risk_level") or "none"
        if risk == "no_risk" and r == "none":
            result.append(b)
        elif risk == "with_risk" and r in ("medium", "high"):
            result.append(b)
        elif risk == "medium" and r == "medium":
            result.append(b)
        elif risk == "high" and r == "high":
            result.append(b)
    return result


# ── Realistic adjustment helpers (mirrors applyRealisticAdjustments in cartera.ts) ──

def _bet_market_key(b: Dict) -> str:
    strategy = b.get("strategy", "")
    match_id = b.get("match_id", "")
    if strategy == "back_draw_00":
        return f"{match_id}:draw"
    if strategy in ("odds_drift", "odds_drift_v1", "momentum_xg_v1", "momentum_xg_v2"):
        return f"{match_id}:back:{b.get('team') or 'unknown'}"
    # Goal Clustering: deduplicate at strategy level — only the first trigger per match fires.
    # Each goal changes over_line but we only want the first clustering signal per match.
    if strategy == "goal_clustering":
        return f"{match_id}:goal_clustering"
    return f"{match_id}:over:{b.get('over_line') or 'unknown'}"


def _apply_realistic_adj(bets: List[Dict], adj: Dict) -> List[Dict]:
    """Mirrors applyRealisticAdjustments from cartera.ts exactly."""
    result = list(bets)

    # 0. Global minute range filter
    g_min = adj.get("globalMinuteMin")
    g_max = adj.get("globalMinuteMax")
    if g_min is not None or g_max is not None:
        new: List[Dict] = []
        for b in result:
            mn = _fv(b, "minuto")
            if mn is None:
                new.append(b)
                continue
            if g_min is not None and mn < g_min:
                continue
            if g_max is not None and mn >= g_max:
                continue
            new.append(b)
        result = new

    # 1. Drift min minute
    drift_min = adj.get("driftMinMinute")
    if drift_min is not None:
        result = [
            b for b in result
            if b.get("strategy") not in ("odds_drift", "odds_drift_v1") or (_fv(b, "minuto") or 0) >= drift_min
        ]

    # 2. Max odds filter
    max_odds = adj.get("maxOdds")
    if max_odds is not None:
        result = [b for b in result if _get_bet_odds(b) <= max_odds]

    # 3. Min odds filter
    min_odds = adj.get("minOdds")
    if min_odds is not None:
        result = [b for b in result if _get_bet_odds(b) >= min_odds]

    # 4. Dedup (keep first chronologically per market key; bets already sorted)
    if adj.get("dedup"):
        seen_keys: set = set()
        deduped: List[Dict] = []
        for b in result:
            key = _bet_market_key(b)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(b)
        result = deduped

    # 5. Conflict filter: remove MomXG bets from matches that also have xG Underperf
    if adj.get("conflictFilter"):
        xg_matches = {b.get("match_id") for b in result if b.get("strategy") in ("xg_underperformance", "xg_underperformance_base")}
        result = [
            b for b in result
            if b.get("strategy") not in ("momentum_xg_v1", "momentum_xg_v2")
            or b.get("match_id") not in xg_matches
        ]

    # 5b. Anti-contrarias: remove later contradictory match-odds bets on same match
    if not adj.get("allowContrarias", True):
        seen_match: Dict[str, str] = {}
        new2: List[Dict] = []
        for b in result:
            strategy = b.get("strategy", "")
            is_match_odds = strategy in ("back_draw_00", "odds_drift", "odds_drift_v1", "momentum_xg_v1", "momentum_xg_v2")
            if not is_match_odds:
                new2.append(b)
                continue
            bet_type = "draw" if strategy == "back_draw_00" else (b.get("team") or "home")
            match_id = b.get("match_id")
            first = seen_match.get(match_id)
            if first is None:
                seen_match[match_id] = bet_type
                new2.append(b)
            elif first == bet_type:
                new2.append(b)
            # else: contraria → skip
        result = new2

    # 6. Stability filter
    min_stability = adj.get("minStability", 1)
    if min_stability and min_stability > 1:
        result = [b for b in result if (b.get("stability_count") or 1) >= min_stability]

    # 7. Slippage (BACK bets only, affects wins only — mirrors cartera.ts)
    slippage_pct = adj.get("slippagePct", 0)
    if slippage_pct and slippage_pct > 0:
        factor = 1.0 - slippage_pct / 100.0
        new3: List[Dict] = []
        for b in result:
            if b.get("bet_type_dir") == "lay" or not b.get("won"):
                new3.append(b)
                continue
            adjusted_odds = _round2(_get_bet_odds(b) * factor)
            new_pl = _round2((adjusted_odds - 1.0) * 10.0 * 0.95)
            nb = dict(b)
            nb["pl"] = new_pl
            new3.append(nb)
        result = new3

    return result


# ── Bankroll simulation (mirrors simulateCartera in cartera.ts) ──────────────

def _calc_max_drawdown(cum: List[float]) -> float:
    """Return max peak-to-trough drawdown from cumulative P/L array."""
    if not cum:
        return 0.0
    max_dd = 0.0
    peak = cum[0]
    for v in cum:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _round2(x: float) -> float:
    return round(x * 100) / 100


def _simulate_cartera_py(bets: List[Dict], bankroll_init: float, mode: str, flat_stake: float = 10.0) -> Dict:
    FLAT_STAKE = flat_stake
    pl_scale = flat_stake / 10.0
    KELLY_MIN_BETS = 5

    flat_cum = 0.0
    bankroll = bankroll_init
    peak_bankroll = bankroll_init
    flat_cum_arr: List[float] = []
    managed_cum_arr: List[float] = []
    flat_wins = 0
    managed_pl = 0.0
    rolling_wins = 0
    consecutive_losses = 0

    for i, b in enumerate(bets):
        pl_raw = b.get("pl")
        try:
            pl_raw = float(pl_raw) if pl_raw is not None else 0.0
        except (ValueError, TypeError):
            pl_raw = 0.0

        won = bool(b.get("won"))
        flat_cum = _round2(flat_cum + pl_raw * pl_scale)
        flat_cum_arr.append(flat_cum)
        if won:
            flat_wins += 1

        rolling_wr = rolling_wins / i if i > 0 else 0.5
        odds = _get_bet_odds(b)
        b_net = max(odds - 1.0, 0.01)

        if mode == "fixed":
            stake_pct = 0.02
        elif mode == "kelly":
            if i < KELLY_MIN_BETS:
                stake_pct = 0.02
            else:
                f = (rolling_wr * b_net - (1.0 - rolling_wr)) / b_net
                stake_pct = max(0.0, min(f, 0.08))
        elif mode == "half_kelly":
            if i < KELLY_MIN_BETS:
                stake_pct = 0.01
            else:
                f = (rolling_wr * b_net - (1.0 - rolling_wr)) / b_net
                stake_pct = max(0.0, min(f / 2.0, 0.04))
        elif mode == "dd_protection":
            dd_from_peak = (peak_bankroll - bankroll) / peak_bankroll if peak_bankroll > 0 else 0.0
            if dd_from_peak > 0.10:
                stake_pct = 0.005
            elif dd_from_peak > 0.05:
                stake_pct = 0.01
            else:
                stake_pct = 0.02
        elif mode == "variable":
            strategy = b.get("strategy", "")
            if strategy in ("odds_drift", "odds_drift_v1"):
                stake_pct = 0.025
            elif strategy in ("xg_underperformance", "xg_underperformance_base"):
                stake_pct = 0.03
            elif strategy == "pressure_cooker":
                stake_pct = 0.02
            else:
                stake_pct = 0.015
        elif mode == "anti_racha":
            if consecutive_losses >= 2:
                stake_pct = 0.005
            elif consecutive_losses >= 1:
                stake_pct = 0.01
            else:
                stake_pct = 0.02
        else:
            stake_pct = 0.02

        stake = _round2(bankroll * stake_pct)
        ratio = stake / FLAT_STAKE
        managed_bet_pl = _round2(pl_raw * pl_scale * ratio)
        bankroll = _round2(bankroll + managed_bet_pl)
        if bankroll > peak_bankroll:
            peak_bankroll = bankroll
        managed_pl = _round2(managed_pl + managed_bet_pl)
        managed_cum_arr.append(_round2(bankroll - bankroll_init))

        if won:
            rolling_wins += 1
            consecutive_losses = 0
        else:
            consecutive_losses += 1

    total = len(bets)
    total_staked = total * FLAT_STAKE
    managed_max_dd = _calc_max_drawdown(managed_cum_arr)

    return {
        "total": total,
        "wins": flat_wins,
        "win_pct": _round2(flat_wins / total * 100) if total > 0 else 0.0,
        "flat_pl": flat_cum,
        "flat_roi": _round2(flat_cum / total_staked * 100) if total_staked > 0 else 0.0,
        "managed_pl": managed_pl,
        "managed_max_dd": managed_max_dd,
    }


def _score_of(sim: Dict, criterion: str) -> float:
    # Bayesian confidence weight: penalizes combos with few bets.
    # N=15 → 0.25×, N=30 → 0.50×, N=60 → 1.00×, N>60 → 1.00×
    # Raised from 30 to 60: con dataset de ~743 partidos, N=32 obtenía conf=1.0
    # (mismo que N=300), lo que permitía combos hiper-selectivos de 1 sola
    # estrategia ganar por ROI nominal sin penalización estadística suficiente.
    n = sim["total"]
    conf = min(1.0, n / 60.0)
    if criterion == "max_roi":
        return sim["flat_roi"] * conf
    if criterion == "max_pl":
        return sim["flat_pl"] * conf
    if criterion == "max_wr":
        ci_low, _ = _wilson_ci(sim["wins"], n)
        return ci_low  # Wilson CI lower bound: statistically principled, no magic numbers
    if criterion == "min_dd":
        return (sim["managed_pl"] - sim["managed_max_dd"] * 2.0 + sim["win_pct"] * 0.5) * conf
    return sim["flat_pl"] * conf


# ── Phase 1 worker — must be top-level for Windows ProcessPoolExecutor/spawn ─

def _phase1_worker(args: tuple) -> tuple:
    """
    Runs Phase 1 search for a subset of (draw, xg) pairs.
    Accepts draw_xg_pairs — a list of (draw, xg) tuples — instead of separate
    draw_subset + xg_opts, enabling up to 15-worker splits (5 draws × 3 xg versions).
    Returns (best_combo_dict, best_risk, best_score).
    """
    # Windows: set BELOW_NORMAL priority inside the worker itself.
    # ProcessPoolExecutor uses 'spawn' on Windows, so workers do NOT inherit the
    # parent's priority class — they always start at NORMAL priority regardless of
    # the parent's creationflags. Setting it here guarantees Chrome's renderer is
    # never starved of CPU time.
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(
            ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL

    (bets, draw_xg_pairs, drift_opts, clustering_opts, pressure_opts,
     tardesia_opts, momentum_opts, lay15_opts, lay_da_opts, lay25_opts,
     bsd_opts, bo15e_opts, lff_opts, br_opts, risk_opts,
     criterion, bankroll_init) = args

    best_combo = None
    best_risk = "all"
    best_score = -math.inf
    _itr_p1 = 0

    for draw, xg in draw_xg_pairs:
        draw_bets = _filter_draw(bets, draw)
        xg_bets   = _filter_xg(bets, xg)
        for drift in drift_opts:
            drift_bets = _filter_drift(bets, drift)
            for clustering in clustering_opts:
                clustering_bets = _filter_clustering(bets, clustering)
                for pressure in pressure_opts:
                    pressure_bets = _filter_pressure(bets, pressure)
                    for tardesia in tardesia_opts:
                        tardesia_bets = _filter_tardesia(bets, tardesia)
                        for momentum in momentum_opts:
                            momentum_bets = _filter_momentum(bets, momentum)
                            for lay15 in lay15_opts:
                                lay15_bets = _filter_lay_over15(bets, lay15)
                                for lay_da in lay_da_opts:
                                    lay_da_bets = _filter_lay_draw_asym(bets, lay_da)
                                    for lay25 in lay25_opts:
                                        lay25_bets = _filter_lay_over25_def(bets, lay25)
                                        for bsd in bsd_opts:
                                            bsd_bets = _filter_back_sot_dom(bets, bsd)
                                            for bo15e in bo15e_opts:
                                                bo15e_bets = _filter_back_over15_early(bets, bo15e)
                                                for lff in lff_opts:
                                                    lff_bets = _filter_lay_false_fav(bets, lff)
                                                    combined = [
                                                        b for b in (
                                                            draw_bets + xg_bets + drift_bets +
                                                            clustering_bets + pressure_bets +
                                                            tardesia_bets + momentum_bets +
                                                            lay15_bets + lay_da_bets + lay25_bets +
                                                            bsd_bets + bo15e_bets + lff_bets
                                                        )
                                                        if _meets_min_odds(b)
                                                    ]
                                                    combined.sort(key=lambda b: b.get("timestamp_utc") or "")
                                                    for br in br_opts:
                                                        for risk in risk_opts:
                                                            filtered = _filter_by_risk(combined, risk)
                                                            if len(filtered) < 15:
                                                                continue
                                                            sim = _simulate_cartera_py(filtered, bankroll_init, br)
                                                            score = _score_of(sim, criterion)
                                                            if score > best_score:
                                                                best_score = score
                                                                best_risk = risk
                                                                best_combo = {
                                                                    "draw": draw, "xg": xg,
                                                                    "drift": drift,
                                                                    "clustering": clustering,
                                                                    "pressure": pressure,
                                                                    "tardeAsia": tardesia,
                                                                    "momentumXG": momentum,
                                                                    "layOver15": lay15,
                                                                    "layDrawAsym": lay_da,
                                                                    "layOver25Def": lay25,
                                                                    "backSotDom": bsd,
                                                                    "backOver15Early": bo15e,
                                                                    "layFalseFav": lff,
                                                                    "br": br,
                                                                }
                                                            _itr_p1 += 1
                                                            if _itr_p1 % 100_000 == 0:
                                                                _pct = min(99, round(_itr_p1 / _PHASE1_TOTAL * 100))
                                                                _opt_progress["pct"] = _pct
                                                                _opt_progress["message"] = (
                                                                    f"Phase 1 — {_pct}% "
                                                                    f"({_itr_p1:,} / {_PHASE1_TOTAL:,} combos)"
                                                                )
                                                                logger.info("Optimizer Phase 1: %d%% (%d/%d)",
                                                                            _pct, _itr_p1, _PHASE1_TOTAL)

    return best_combo, best_risk, best_score


def _phase2_worker(args: tuple) -> tuple:
    """
    Runs Phase 2 search: 7776 realistic adjustment candidates given the fixed Phase 1 combo.
    bets_for_combo must already be: combo-filtered + min_odds + sorted chronologically (no risk filter).
    Risk filter is applied AFTER realistic adjustments — mirrors evaluateCombo order in cartera.ts.
    Returns (best_adj_dict | None, best_score).
    """
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(
            ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL

    bets_for_combo, bankroll_init, br_mode, risk_filter, criterion = args
    best_adj: Optional[Dict] = None
    best_score = -math.inf
    _itr_p2 = 0

    for dedup in (False, True):
      for min_odds_val in (None, 1.15, 1.21):
        for max_odds_val in (6.0, 7.0, 10.0):
          for slippage_pct in (0, 2, 3.5):
            for conflict_filter in (False, True):
              for allow_contrarias in (True, False):
                for min_stability in (1, 2, 3):
                  for drift_min in (None, 15, 30):
                    for g_min, g_max in ((None, None), (15, 85), (20, 80)):
                        adj: Dict = {
                            "dedup": dedup,
                            "minOdds": min_odds_val,
                            "maxOdds": max_odds_val,
                            "slippagePct": slippage_pct,
                            "conflictFilter": conflict_filter,
                            "allowContrarias": allow_contrarias,
                            "minStability": min_stability,
                            "driftMinMinute": drift_min,
                            "globalMinuteMin": g_min,
                            "globalMinuteMax": g_max,
                        }
                        after_adj = _apply_realistic_adj(bets_for_combo, adj)
                        after_risk = _filter_by_risk(after_adj, risk_filter)
                        if len(after_risk) < 15:
                            continue
                        sim = _simulate_cartera_py(after_risk, bankroll_init, br_mode)
                        score = _score_of(sim, criterion)
                        if score > best_score:
                            best_score = score
                            best_adj = adj
                        _itr_p2 += 1
                        if _itr_p2 % 500 == 0:
                            _pct2 = min(99, round(_itr_p2 / _PHASE2_TOTAL * 100))
                            _opt_progress["pct"] = _pct2
                            _opt_progress["message"] = f"Phase 2 — {_pct2}% ({_itr_p2} / {_PHASE2_TOTAL} adj combos)"
                            logger.info("Optimizer Phase 2: %d%%", _pct2)

    return best_adj, best_score


# ── Subprocess runner ────────────────────────────────────────────────────────

_CLI_SCRIPT = Path(__file__).parent / "optimizer_cli.py"
_N_WORKERS   = int(os.environ.get("PRESET_WORKERS", "3"))   # default 3 (~12 min Phase 1). Safe for Chrome. Set PRESET_WORKERS=10 for faster runs without browser open.


def _parse_progress_line(line: str) -> None:
    """Update _opt_progress by parsing a stdout line from optimizer_cli.py."""
    if "Phase 1 —" in line and "workers" in line:
        _opt_progress.update({"phase": "Phase 1", "pct": 0, "message": line})
    elif "Worker" in line and "terminado" in line:
        m = re.search(r"\((\d+)/(\d+) listos\)", line)
        if m:
            done, total = int(m.group(1)), int(m.group(2))
            pct = min(98, round(done / total * 99))
            _opt_progress.update({"pct": pct,
                                   "message": f"Phase 1 — {pct}% ({done}/{total} workers)"})
    elif "Phase 1 completada" in line:
        _opt_progress.update({"phase": "Phase 1", "pct": 99, "message": line})
    elif "Phase 2 —" in line or "Phase 2b —" in line:
        _opt_progress.update({"phase": "Phase 2", "pct": 0, "message": line})
    elif "Phase 2 completada" in line or "Phase 2b completada" in line:
        _opt_progress.update({"phase": "Phase 2", "pct": 99, "message": line})
    elif "Phase 2.5 —" in line:
        _opt_progress.update({"phase": "Phase 2.5", "pct": 0, "message": line})
    elif "Phase 2.5 (pase" in line and "desactivar" in line:
        _opt_progress.update({"message": line})
    elif "Phase 2.5 completada" in line:
        _opt_progress.update({"phase": "Phase 2.5", "pct": 99, "message": line})


def _run_subprocess_sync(cmd: list, out_file: Path) -> int:
    """
    Run optimizer_cli.py synchronously, reading stdout line-by-line to update _opt_progress.
    Called via asyncio.to_thread — avoids asyncio.create_subprocess_exec issues on Windows
    where uvicorn may use SelectorEventLoop (which doesn't support async subprocesses).
    Returns the process returncode.
    """
    import subprocess as _sp
    import os as _os
    # Windows: BELOW_NORMAL_PRIORITY_CLASS (0x4000) so Chrome's renderer doesn't starve.
    # Worker processes spawned by ProcessPoolExecutor inherit this priority from the parent.
    _creation_flags = 0x00004000 if sys.platform == "win32" else 0
    # PYTHONUTF8=1 ensures the subprocess uses UTF-8 for stdout/stderr (avoids cp1252 UnicodeEncodeError).
    _env = {**_os.environ, "PYTHONUTF8": "1"}
    proc = _sp.Popen(
        cmd,
        stdout=_sp.PIPE,
        stderr=_sp.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags,
        env=_env,
    )
    for line in iter(proc.stdout.readline, ""):
        line = line.strip()
        if line:
            logger.info("Optimizer: %s", line)
            _parse_progress_line(line)
    proc.stdout.close()
    proc.wait()
    return proc.returncode


async def _run_optimizer_subprocess(criterion: str, bankroll_init: float) -> Dict:
    """
    Launch optimizer_cli.py as an independent subprocess with _N_WORKERS parallel workers.
    Uses asyncio.to_thread + subprocess.Popen — compatible with all Windows event loop types.
    Reads stdout in real-time to update _opt_progress.
    Returns the result dict read from the output JSON file.
    """
    out_file = Path(tempfile.mktemp(suffix=".json"))
    cmd = [
        sys.executable, str(_CLI_SCRIPT),
        criterion,
        "--bankroll", str(bankroll_init),
        "--workers", str(_N_WORKERS),
        "--out", str(out_file),
    ]

    _opt_progress.update({
        "running": True, "phase": "Phase 1", "pct": 0,
        "message": f"Iniciando optimizador ({_N_WORKERS} workers)…",
    })
    logger.info("Optimizer subprocess: %s", " ".join(str(c) for c in cmd))

    try:
        returncode = await asyncio.to_thread(_run_subprocess_sync, cmd, out_file)

        if returncode != 0:
            _opt_progress.update({"running": False, "phase": "error", "pct": 0,
                                   "message": f"Error en el optimizador (código {returncode})"})
            return

        if not out_file.exists():
            _opt_progress.update({"running": False, "phase": "error", "pct": 0,
                                   "message": "Error: fichero de resultado no encontrado"})
            return

        global _opt_result
        _opt_result = json.loads(out_file.read_text(encoding="utf-8"))
        _opt_progress.update({"running": False, "phase": "done", "pct": 100, "message": "Completado"})
        logger.info("Optimizer done — best_score=%.2f", _opt_result.get("best_score", 0))

    except Exception as exc:
        logger.exception("Optimizer subprocess crashed: %s", exc)
        _opt_progress.update({"running": False, "phase": "error", "pct": 0,
                               "message": f"Error inesperado: {exc}"})
    finally:
        out_file.unlink(missing_ok=True)


# ── FastAPI endpoints ─────────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    criterion: str
    bankroll_init: float = 1000.0


@router.get("/strategies/cartera/optimize/progress")
async def get_optimize_progress() -> Dict[str, Any]:
    """Returns current optimizer progress (running/pct/message)."""
    return dict(_opt_progress)


@router.get("/strategies/cartera/optimize/result")
async def get_optimize_result() -> Dict[str, Any]:
    """Returns the last completed optimizer result, or status=running/idle."""
    if _opt_progress.get("running"):
        return {"status": "running"}
    if _opt_result is not None:
        return {"status": "done", **_opt_result}
    return {"status": "idle"}


@router.post("/strategies/cartera/optimize")
async def optimize_preset(body: OptimizeRequest) -> Dict[str, Any]:
    """
    Starts optimization in background and returns IMMEDIATELY (status=started).
    Chrome never waits 4 minutes — no open HTTP connection, no memory accumulation.
    Poll GET /optimize/progress for live updates, GET /optimize/result for the final result.
    """
    global _opt_result

    if body.criterion == "max_bets":
        _opt_result = {"combo": MAX_BETS_COMBO, "risk_filter": "all", "best_score": 0.0}
        return {"status": "done", **_opt_result}

    if _opt_progress.get("running"):
        return {"status": "already_running"}

    _opt_result = None  # clear previous result
    # Reset progress to "running" synchronously BEFORE spawning the task.
    # This prevents the progress poller from reading a stale phase:"done" from the
    # previous optimization and signalling the while-loop to exit prematurely.
    _opt_progress.update({
        "running": True, "phase": "starting", "pct": 0,
        "message": f"Iniciando optimizador {body.criterion}…",
    })
    asyncio.create_task(_run_optimizer_subprocess(body.criterion, body.bankroll_init))
    return {"status": "started"}


@router.get("/strategies/cartera/optimize/config/{criterion}")
async def get_preset_config(criterion: str) -> Dict[str, Any]:
    """
    Returns the pre-computed cartera_config.json-compatible config for the given preset.
    Generated automatically after each optimizer run.
    404 if the optimizer hasn't run yet for this criterion.
    """
    allowed = {"max_roi", "max_pl", "max_wr", "min_dd"}
    if criterion not in allowed:
        raise HTTPException(status_code=400, detail=f"criterion must be one of {sorted(allowed)}")
    cfg_path = _PRESETS_DIR / f"preset_{criterion}_config.json"
    if not cfg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No hay config para '{criterion}'. Lanza el optimizador primero."
        )
    return json.loads(cfg_path.read_text(encoding="utf-8"))


@router.get("/strategies/cartera/optimize/presets")
async def list_preset_csvs() -> Dict[str, Any]:
    """Lists all pre-computed preset CSVs available for download."""
    files = []
    if _PRESETS_DIR.exists():
        for p in sorted(_PRESETS_DIR.glob("preset_*.csv")):
            criterion = p.stem.replace("preset_", "")
            cfg_path = _PRESETS_DIR / f"preset_{criterion}_config.json"
            files.append({
                "criterion": criterion,
                "filename": p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "modified": p.stat().st_mtime,
                "has_config": cfg_path.exists(),
            })
    return {"presets": files}


@router.get("/strategies/cartera/optimize/download/{criterion}")
async def download_preset_csv(criterion: str) -> FileResponse:
    """Download pre-computed preset CSV for the given criterion (max_roi | max_pl | max_wr | min_dd)."""
    allowed = {"max_roi", "max_pl", "max_wr", "min_dd"}
    if criterion not in allowed:
        raise HTTPException(status_code=400, detail=f"criterion must be one of {sorted(allowed)}")
    csv_path = _PRESETS_DIR / f"preset_{criterion}.csv"
    if not csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No hay CSV para '{criterion}'. Lanza el optimizador primero."
        )
    return FileResponse(
        path=str(csv_path),
        filename=f"preset_{criterion}.csv",
        media_type="text/csv",
    )
