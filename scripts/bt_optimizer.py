"""
bt_optimizer.py — Backtest optimizer for Furbo betting strategies.

Replaces the strategies_designer.ipynb notebook with a fully reproducible CLI script.

Phases:
  0  Pre-load all historical match data into memory (once, ~5 s)
  1  Grid search per strategy → best (params) using _analyze_strategy_simple directly
  2  Quality gate: discard strategies that don't pass N / ROI / IC95 thresholds
  3  Portfolio preset generation: run optimizer_cli.run() for 4 criteria
  4  Select best preset and apply to cartera_config.json
  5  Export CSV + XLSX with all bets from the final portfolio

Usage:
  python scripts/bt_optimizer.py                      # run all phases
  python scripts/bt_optimizer.py --phase individual   # only phase 1+2
  python scripts/bt_optimizer.py --phase presets      # only phase 3
  python scripts/bt_optimizer.py --phase apply --criterion max_pl
  python scripts/bt_optimizer.py --phase export
  python scripts/bt_optimizer.py --dry-run            # never writes cartera_config.json
  python scripts/bt_optimizer.py --workers 8
"""

import sys
import io
# Force UTF-8 output on Windows (avoids UnicodeEncodeError for → ✓ etc.)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import json
import math
import shutil
import argparse
import itertools
import time
from pathlib import Path
from datetime import datetime

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "betfair_scraper" / "dashboard" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "betfair_scraper"))

from utils import csv_reader
from utils.csv_reader import (
    _STRATEGY_REGISTRY,
    _STRATEGY_REGISTRY_KEYS,
    _LEGACY_MIN_DUR_KEY,
    _analyze_strategy_simple,
    _cfg_add_snake_keys,
    _build_registry_config_map,
)
from utils.csv_loader import _get_all_finished_matches
from api import optimizer_cli

# ── Paths ─────────────────────────────────────────────────────────────────────
CARTERA_CFG   = ROOT / "betfair_scraper" / "cartera_config.json"
PRESETS_DIR   = ROOT / "betfair_scraper" / "data" / "presets"
EXPORTS_DIR   = ROOT / "analisis"
RESULTS_FILE  = ROOT / "auxiliar" / "bt_optimizer_results.json"

PRESETS_DIR.mkdir(parents=True, exist_ok=True)

# ── Quality gates ─────────────────────────────────────────────────────────────
G_MIN_ROI    = 10.0   # minimum ROI %
IC95_MIN_LOW = 40.0   # minimum Wilson CI lower bound

# ── Selector ──────────────────────────────────────────────────────────────────
CRITERIA = ["max_roi", "max_pl", "max_wr", "min_dd"]
DEFAULT_SELECTOR = "robust"          # ci_low × wr × sqrt(N) — rewards quality + sample size
MIN_PRESET_N     = 200  # real stats from analyze_cartera-equivalent; N<200 signals something odd

# ── Min-duration defaults (same as cartera_config.json) ──────────────────────
DEFAULT_MIN_DUR = {
    "draw":        2,
    "xg":          3,
    "drift":       2,
    "clustering":  4,
    "pressure":    4,
}

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH SPACES
# Keys must match what _cfg_add_snake_keys() produces (snake_case) or the
# camelCase names that _cfg_add_snake_keys translates.
# ─────────────────────────────────────────────────────────────────────────────
SEARCH_SPACES: dict[str, dict[str, list]] = {

    # ── Original 7 — versioned strategies ─────────────────────────────────────
    # For these, "version" selects which trigger wrapper is used.
    # The grid loops over versions AND params together.

    "back_draw_00": {   # applies to versions v1/v15/v2/v2r/v3/v4
        "xg_max":    [0.4, 0.5, 0.6, 0.7, 1.0],
        "poss_max":  [15, 20, 25, 30, 100],
        "shots_max": [6, 8, 10, 12, 20],
        "minute_min":[25, 30, 35],
        "minute_max":[75, 80, 85, 90],
    },
    "xg_underperformance": {   # applies to versions base/v2/v3
        "xg_excess_min": [0.3, 0.4, 0.5, 0.6, 0.7],
        "sot_min":       [0, 1, 2, 3],
        "minute_min":    [0, 10, 15, 20],
        "minute_max":    [60, 65, 70, 75, 80, 90],
        "odds_min":      [0, 1.20, 1.30, 1.40],
    },
    "odds_drift": {   # applies to versions v1/v2/v3/v4/v5/v6
        "drift_min_pct": [15, 20, 30],
        "max_odds":      [5.0, 999],
        "goal_diff_min": [0, 1],
        "min_minute":    [0, 30],
        "max_minute":    [85, 90],
        "odds_min":      [0, 1.20, 1.40],
    },
    "goal_clustering": {
        "sot_min":    [0, 2, 3, 4],
        "min_minute": [0, 15, 20],
        "max_minute": [55, 60, 65, 70],
        "xg_rem_min": [0.0, 0.3, 0.6],
        "odds_min":   [0, 1.20, 1.30],
    },
    "pressure_cooker": {
        "min_minute":    [55, 60, 65, 68],
        "max_minute":    [70, 73, 75, 78],
        "score_confirm": [1, 2, 3],
        "odds_min":      [0, 1.20, 1.30],
    },
    "momentum_xg": {   # applies to versions v1/v2
        "min_m": [0, 5, 10, 15, 20],
        "max_m": [70, 75, 80, 85, 90],
    },

    # ── 19 additional strategies ───────────────────────────────────────────────
    "over25_2goal": {
        "m_min":         [45, 50, 55, 60],
        "m_max":         [75, 78, 81, 84],
        "goal_diff_min": [1, 2],
        "sot_total_min": [0, 2, 3, 5],
        "odds_min":      [1.2, 1.4, 1.6],
    },
    "under35_late": {
        "m_min":      [60, 65, 70],
        "m_max":      [75, 78, 81, 85],
        "xg_max":     [2.5, 3.0, 3.5],
        "goals_min":  [2, 3],
        "goals_max":  [3, 4],
        "odds_min":   [0, 1.20, 1.30, 1.40],
    },
    "longshot": {
        "m_min":     [60, 65, 70],
        "m_max":     [80, 83, 86, 88],
        "odds_min":  [1.2, 1.3, 1.5],
        "odds_max":  [5.0, 7.0, 10.0],
    },
    "cs_close": {
        "m_min":    [60, 65, 67, 70],
        "m_max":    [78, 80, 83, 85],
        "odds_min": [0, 3.0, 4.0, 5.0],
    },
    "cs_one_goal": {
        "m_min":    [60, 65, 68, 70],
        "m_max":    [82, 85, 88, 90],
        "odds_min": [0, 2.5, 3.0, 3.5],
    },
    "ud_leading": {
        "m_min":            [45, 50, 53, 58],
        "m_max":            [78, 80, 83, 85],
        "ud_min_pre_odds":  [1.3, 1.5, 1.8, 2.0, 2.5],
        "max_lead":         [1, 2, 3],
        "odds_min":         [0, 1.20, 1.40, 1.60],
    },
    "home_fav_leading": {
        "m_min":     [50, 55, 60],
        "m_max":     [75, 78, 80, 83],
        "max_lead":  [1, 2, 3],
        "fav_max":   [2.0, 2.5, 3.0],
        "odds_min":  [0, 1.20, 1.30, 1.40],
    },
    "cs_20": {
        "m_min":    [65, 70, 72, 75],
        "m_max":    [83, 85, 88, 90],
        "odds_max": [8.0, 10.0, 15.0],
        "odds_min": [0, 2.0, 3.0, 4.0],
    },
    "cs_big_lead": {
        "m_min":    [65, 68, 70, 72],
        "m_max":    [80, 82, 85],
        "odds_max": [6.0, 8.0, 10.0],
        "odds_min": [0, 2.0, 3.0, 4.0],
    },
    "lay_over45_v3": {
        "m_min":      [45, 50, 55, 60],
        "m_max":      [70, 73, 75, 78],
        "goals_max":  [1, 2, 3],
        "odds_max":   [10.0, 15.0, 20.0],
    },
    "draw_xg_conv": {
        "m_min":       [55, 60, 63, 65],
        "m_max":       [78, 80, 83, 85],
        "xg_diff_max": [0.5, 0.8, 1.0, 1.3],
        "odds_min":    [0, 1.50, 1.80, 2.10],
    },
    "poss_extreme": {
        "m_min":    [25, 30, 35],
        "m_max":    [45, 50, 53, 55],
        "poss_min": [50, 55, 58, 60],
    },
    "cs_00": {
        "m_min":    [25, 28, 30],
        "m_max":    [30, 33, 35],
        "xg_max":   [1.0, 1.5, 2.0],
        "odds_min": [4.0, 5.0, 6.0],
        "odds_max": [10.0, 12.0, 15.0],
    },
    "over25_2goals": {
        "m_min":    [40, 45, 48, 52],
        "m_max":    [58, 60, 63, 65],
        "odds_max": [3.0, 4.0, 5.0, 6.0],
        "odds_min": [0, 1.20, 1.30, 1.40],
    },
    "draw_11": {
        "m_min":    [62, 65, 68, 70],
        "m_max":    [82, 85, 88, 90],
        "odds_min": [1.0, 1.2, 1.4],
    },
    "under35_3goals": {
        "m_min":    [60, 65, 70],
        "m_max":    [80, 83, 85, 90],
        "xg_max":   [2.0, 2.5, 3.0],
        "odds_min": [0, 1.20, 1.30, 1.40],
    },
    "away_fav_leading": {
        "m_min":    [60, 65, 68, 70],
        "m_max":    [80, 83, 85, 88],
        "max_lead": [1, 2, 3],
        "fav_max":  [2.0, 2.5, 3.0],
        "odds_min": [0, 1.20, 1.40, 1.60],
    },
    "under45_3goals": {
        "m_min":    [50, 55, 58, 60],
        "m_max":    [75, 78, 80, 83],
        "xg_max":   [2.0, 2.5, 3.0],
        "odds_min": [0, 1.20, 1.30, 1.40],
    },
    "cs_11": {
        "m_min":    [62, 65, 68, 70],
        "m_max":    [82, 85, 88, 90],
        "odds_min": [0, 3.0, 4.0, 5.0],
    },
    "draw_equalizer": {
        "m_min":          [60, 63, 65, 68],
        "m_max":          [85, 88, 90],
        "fav_pre_max":    [2.0, 2.5, 3.0],
        "min_goals_each": [1, 2],
        "odds_max":       [6.0, 8.0, 10.0],
        "odds_min":       [0, 1.50, 2.00, 2.50],
    },
    "draw_22": {
        "m_min":    [65, 68, 70, 72],
        "m_max":    [85, 88, 90],
        "odds_max": [6.0, 8.0, 10.0],
        "odds_min": [0, 1.50, 2.00, 2.50],
    },
    "lay_over45_blowout": {
        "m_min":        [55, 58, 60, 63],
        "m_max":        [72, 75, 78],
        "post_window":  [5, 8, 10, 12],
        "sot_max":      [0, 1, 2],
        "odds_max":     [10.0, 15.0, 20.0],
        "include_31":   [0, 1],
    },

    # ── R19 brute-force discoveries ────────────────────────────────────────────
    "over35_early_goals": {
        "m_min":     [40, 45, 50],
        "m_max":     [60, 65, 70],
        "odds_min":  [1.5, 1.8, 2.0],
        "odds_max":  [6.0, 8.0, 10.0],
    },
    "lay_draw_away_leading": {  # LAY — win=+stake*0.95, loss=-stake*(odds-1)
        "m_min":    [50, 55, 60],
        "m_max":    [75, 78, 80],
        "xg_max":   [1.2, 1.5, 1.8, 2.0],
        "odds_min": [2.0, 2.5],
        "odds_max": [8.0, 10.0],
    },
    "lay_cs11": {               # LAY — win=+stake*0.95, loss=-stake*(odds-1)
        "m_min":     [55, 58, 60, 63],
        "m_max":     [80, 83, 85, 88],
        "odds_min":  [1.5, 2.0],
        "odds_max":  [20.0, 50.0],
    },

    # tarde_asia: no grid search (detection is liga-based, no tunable params)
}

# Which versioned registry keys belong to each "family" for the grid search
VERSIONED_FAMILIES = {
    "back_draw_00":       ["back_draw_00_v1", "back_draw_00_v15", "back_draw_00_v2",
                           "back_draw_00_v2r", "back_draw_00_v3", "back_draw_00_v4"],
    "xg_underperformance":["xg_underperformance_base", "xg_underperformance_v2",
                           "xg_underperformance_v3"],
    "odds_drift":         ["odds_drift_v1", "odds_drift_v2", "odds_drift_v3",
                           "odds_drift_v4", "odds_drift_v5", "odds_drift_v6"],
    "momentum_xg":        ["momentum_xg_v1", "momentum_xg_v2"],
}

# Flat strategy keys (one registry entry = one strategy, no versioning)
SINGLE_STRATEGIES = [
    "goal_clustering", "pressure_cooker",
    "over25_2goal", "under35_late", "longshot",
    "cs_close", "cs_one_goal", "ud_leading", "home_fav_leading",
    "cs_20", "cs_big_lead", "lay_over45_v3", "draw_xg_conv",
    "poss_extreme", "cs_00", "over25_2goals", "draw_11",
    "under35_3goals", "away_fav_leading", "under45_3goals", "cs_11",
    "draw_equalizer", "draw_22",
    "lay_over45_blowout",
    # R19 brute-force discoveries
    "over35_early_goals", "lay_draw_away_leading", "lay_cs11",
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _wilson_ci(wins: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin  = z * math.sqrt(p * (1-p) / n + z*z / (4*n*n)) / (1 + z*z/n)
    return (round(max(0.0, center - margin) * 100, 1),
            round(min(1.0, center + margin) * 100, 1))


def _n_matches() -> int:
    return len(_get_all_finished_matches())


def _min_n(n_fin: int) -> int:
    return max(15, n_fin // 25)


def _eval_bets(bets: list, n_fin: int) -> dict | None:
    """Apply quality gates; return metrics dict or None if gates fail."""
    n = len(bets)
    if n < _min_n(n_fin):
        return None
    wins = sum(1 for b in bets if b["won"])
    pl   = sum(b["pl"] for b in bets)
    roi  = pl / n * 100
    if roi < G_MIN_ROI:
        return None
    ci_l, ci_h = _wilson_ci(wins, n)
    if ci_l < IC95_MIN_LOW:
        return None
    max_dd = _max_drawdown([b["pl"] for b in bets])
    return {
        "n":      n,
        "wins":   wins,
        "wr":     round(wins / n * 100, 1),
        "pl":     round(pl, 2),
        "roi":    round(roi, 1),
        "ci_low": ci_l,
        "ci_high":ci_h,
        "max_dd": max_dd,
        "score":  round(ci_l * roi / 100, 4),
    }


def _max_drawdown(pl_list: list) -> float:
    peak = cur = 0.0
    max_dd = 0.0
    for pl in pl_list:
        cur += pl
        if cur > peak:
            peak = cur
        dd = peak - cur
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def _registry_entry(key: str):
    for e in _STRATEGY_REGISTRY:
        if e[0] == key:
            return e
    return None


def _get_min_dur(key: str, cfg_md: dict) -> int:
    legacy_key = _LEGACY_MIN_DUR_KEY.get(key, key)
    return cfg_md.get(legacy_key, cfg_md.get(key, 1))


def _load_config() -> dict:
    with open(CARTERA_CFG, encoding="utf-8") as f:
        return json.load(f)


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 0 — Pre-load match data
# ─────────────────────────────────────────────────────────────────────────────

def phase0_load() -> tuple[list, int]:
    """Load all finished matches into memory cache. Returns (matches, n_matches)."""
    _log("Phase 0 — cargando datos históricos…")
    t0 = time.time()
    matches = _get_all_finished_matches()
    n = len(matches)
    _log(f"  {n} partidos cargados en {time.time()-t0:.1f}s")
    return matches, n


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Individual grid search
# ─────────────────────────────────────────────────────────────────────────────

def _run_single_strategy(key: str, space: dict, min_dur: int, n_fin: int) -> dict | None:
    """Grid search for a single (non-versioned) strategy. Returns best result or None."""
    entry = _registry_entry(key)
    if entry is None:
        return None
    _, _, trigger_fn, _, extract_fn, win_fn = entry

    param_names  = list(space.keys())
    param_values = list(space.values())
    best = None

    for combo_vals in itertools.product(*param_values):
        raw_cfg = dict(zip(param_names, combo_vals))
        cfg     = _cfg_add_snake_keys({**raw_cfg, "enabled": True})
        bets    = _analyze_strategy_simple(key, trigger_fn, extract_fn, win_fn, cfg, min_dur)
        metrics = _eval_bets(bets, n_fin)
        if metrics and (best is None or metrics["score"] > best["score"]):
            best = {**metrics, "params": raw_cfg, "key": key}

    return best


def _run_versioned_family(family: str, version_keys: list, space: dict,
                           min_dur: int, n_fin: int) -> dict | None:
    """Grid search over all versions + all params for a versioned family."""
    param_names  = list(space.keys())
    param_values = list(space.values())
    best = None

    for ver_key in version_keys:
        entry = _registry_entry(ver_key)
        if entry is None:
            continue
        _, _, trigger_fn, _, extract_fn, win_fn = entry

        for combo_vals in itertools.product(*param_values):
            raw_cfg = dict(zip(param_names, combo_vals))
            cfg     = _cfg_add_snake_keys({**raw_cfg, "enabled": True})
            bets    = _analyze_strategy_simple(ver_key, trigger_fn, extract_fn, win_fn, cfg, min_dur)
            metrics = _eval_bets(bets, n_fin)
            if metrics and (best is None or metrics["score"] > best["score"]):
                best = {**metrics, "params": raw_cfg, "version_key": ver_key,
                        "family": family}

    return best


def phase1_individual(n_fin: int, workers: int = 4,
                       only: list | None = None) -> dict:
    """
    Run grid search for all strategies. Returns dict keyed by strategy family:
      { "goal_clustering": { n, wins, wr, pl, roi, ci_low, ci_high, max_dd, score,
                              params: {...}, key/version_key: ... },
        "back_draw_00":    { ..., family: "back_draw_00", version_key: "back_draw_00_v2r" },
        ... }
    Strategies that don't pass quality gates are absent from the result.
    """
    cfg   = _load_config()
    md    = cfg.get("min_duration", {})
    results: dict[str, dict] = {}

    _log(f"Phase 1 — grid search ({n_fin} partidos)…")
    tasks = []

    for key in SINGLE_STRATEGIES:
        if only and key not in only:
            continue
        space = SEARCH_SPACES.get(key)
        if space is None:
            _log(f"  WARN: {key} — sin search space definido, skip")
            continue
        tasks.append(("single", key, space, _get_min_dur(key, md)))

    for family, ver_keys in VERSIONED_FAMILIES.items():
        if only and family not in only:
            continue
        space = SEARCH_SPACES.get(family)
        if space is None:
            _log(f"  WARN: {family} — sin search space definido, skip")
            continue
        tasks.append(("versioned", family, ver_keys, space, _get_min_dur(ver_keys[0], md)))

    n_total = len(tasks)
    t0      = time.time()

    # Sequential execution — trigger lambdas in the registry are not picklable.
    # Match data is in module cache so each call is fast (~0.3-0.5 s).
    for t in tasks:
        kind = t[0]
        if kind == "single":
            _, key, space, min_dur = t
            best = _run_single_strategy(key, space, min_dur, n_fin)
            if best:
                results[key] = best
                _log(f"  ✓ {key}: N={best['n']} ROI={best['roi']}% "
                     f"IC=[{best['ci_low']}-{best['ci_high']}] "
                     f"params={best['params']}")
            else:
                _log(f"  ✗ {key}: no pasó quality gates")
        else:
            _, family, ver_keys, space, min_dur = t
            best = _run_versioned_family(family, ver_keys, space, min_dur, n_fin)
            if best:
                results[family] = best
                _log(f"  ✓ {family} ({best['version_key']}): N={best['n']} "
                     f"ROI={best['roi']}% IC=[{best['ci_low']}-{best['ci_high']}] "
                     f"params={best['params']}")
            else:
                _log(f"  ✗ {family}: no pasó quality gates (todas las versiones)")

    elapsed = time.time() - t0
    _log(f"Phase 1 completada en {elapsed:.1f}s — "
         f"{len(results)}/{n_total} estrategias aprobadas")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Build optimal config from individual results
# ─────────────────────────────────────────────────────────────────────────────

def phase2_build_config(individual_results: dict) -> dict:
    """
    Merge best individual params into cartera_config.json format.
    Returns the new strategies dict (does NOT write to disk yet).
    """
    _log("Phase 2 — construyendo config óptimo por estrategia…")
    base_cfg = _load_config()
    new_strategies = dict(base_cfg.get("strategies", {}))

    approved   = []
    discarded  = []

    for family, result in individual_results.items():
        params = result["params"]
        if family in VERSIONED_FAMILIES:
            # Map back to the legacy config key (draw, xg, drift, momentum_xg)
            legacy_map = {
                "back_draw_00":        "draw",
                "xg_underperformance": "xg",
                "odds_drift":          "drift",
                "momentum_xg":         "momentum_xg",
            }
            cfg_key  = legacy_map.get(family, family)
            ver_key  = result.get("version_key", "")
            # Extract version suffix: "back_draw_00_v2r" → "v2r"
            ver_sfx  = ver_key.replace(family + "_", "").replace("back_draw_00_", "")

            # Convert snake_case params back to camelCase for cartera_config.json
            camel_params = _snake_to_camel(params)
            new_strategies[cfg_key] = {
                "enabled": True,
                "version": ver_sfx,
                **camel_params,
            }
            approved.append(f"{family} ({ver_key})")
        else:
            # Direct registry strategy — keep its own key
            camel_params = _snake_to_camel(params)
            new_strategies[family] = {
                "enabled": True,
                **camel_params,
            }
            approved.append(family)

    # Disable strategies that didn't pass quality gates
    all_families = (list(VERSIONED_FAMILIES.keys()) +
                    SINGLE_STRATEGIES +
                    ["tarde_asia"])
    legacy_map_inv = {
        "back_draw_00": "draw", "xg_underperformance": "xg",
        "odds_drift": "drift",  "momentum_xg": "momentum_xg",
    }
    for fam in all_families:
        if fam not in individual_results:
            cfg_key = legacy_map_inv.get(fam, fam)
            if cfg_key in new_strategies:
                new_strategies[cfg_key] = {**new_strategies[cfg_key], "enabled": False}
                discarded.append(fam)

    _log(f"  Aprobadas ({len(approved)}): {', '.join(approved)}")
    if discarded:
        _log(f"  Descartadas ({len(discarded)}): {', '.join(discarded)}")
    return new_strategies


def _snake_to_camel(params: dict) -> dict:
    """Convert snake_case param keys to camelCase for cartera_config.json."""
    SNAKE_TO_CAMEL = {
        "minute_min":    "minuteMin",
        "min_minute":    "minuteMin",
        "minute_max":    "minuteMax",
        "max_minute":    "minuteMax",
        "xg_max":        "xgMax",
        "poss_max":      "possMax",
        "shots_max":     "shotsMax",
        "xg_excess_min": "xgExcessMin",
        "sot_min":       "sotMin",
        "xg_rem_min":    "xgRemMin",
        "drift_min_pct": "driftMin",
        "max_odds":      "oddsMax",
        "odds_min":      "oddsMin",
        "goal_diff_min": "goalDiffMin",
        "drift_mom_gap_min": "momGapMin",
        # Direct keys (already camelCase or pass-through)
        "m_min":          "minuteMin",
        "m_max":          "minuteMax",
        "min_m":          "minuteMin",
        "max_m":          "minuteMax",
    }
    result = {}
    for k, v in params.items():
        camel = SNAKE_TO_CAMEL.get(k, k)
        result[camel] = v
    return result


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Portfolio preset generation
# ─────────────────────────────────────────────────────────────────────────────

def phase3_presets(new_strategies: dict, workers: int = 4,
                   dry_run: bool = False) -> dict[str, Path]:
    """
    Write the optimized individual params to a staging config, then run
    optimizer_cli.run() for each of 4 criteria to produce preset files.
    Returns dict { criterion: preset_path }.
    """
    _log("Phase 3 — generando presets de portfolio…")

    # Write staging config (backup first)
    base_cfg = _load_config()
    staging  = {**base_cfg, "strategies": new_strategies}

    bak = CARTERA_CFG.with_suffix(f".json.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    if not dry_run:
        shutil.copy2(CARTERA_CFG, bak)
        CARTERA_CFG.write_text(json.dumps(staging, indent=2, ensure_ascii=False),
                                encoding="utf-8")
        _log(f"  Staging config escrito (backup: {bak.name})")
    else:
        _log("  DRY_RUN: staging config NO escrito")

    preset_paths: dict[str, Path] = {}

    for criterion in CRITERIA:
        _log(f"  Ejecutando optimizer_cli — criterio={criterion}…")
        t0 = time.time()
        try:
            result = optimizer_cli.run(
                criterion=criterion,
                bankroll_init=1000.0,
                n_workers=workers,
                out=str(PRESETS_DIR / f"preset_{criterion}_result.json"),
            )
            preset_path = PRESETS_DIR / f"preset_{criterion}_config.json"
            if preset_path.exists():
                preset_paths[criterion] = preset_path
                _log(f"  ✓ {criterion}: {preset_path.name} "
                     f"({time.time()-t0:.0f}s)")
            else:
                _log(f"  ✗ {criterion}: preset no generado")
        except Exception as e:
            _log(f"  ✗ {criterion}: error — {e}")

    if dry_run:
        _log("  DRY_RUN: restaurando config original…")
    return preset_paths


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — Select best preset and apply
# ─────────────────────────────────────────────────────────────────────────────

def _merge_preset_strategies(preset_cfg: dict, base_cfg: dict) -> dict:
    """
    Return merged strategies dict applying preset on top of base config.
    - Preset enables  a strategy → apply all preset params.
    - Preset disables a strategy → only set enabled=False, keep base params.
    - Strategies not in base config → skipped (prevents re-adding obsolete keys).
    """
    merged = dict(base_cfg.get("strategies", {}))
    for k, v in preset_cfg.get("strategies", {}).items():
        if k not in merged:
            continue
        if v.get("enabled"):
            merged[k] = {**merged.get(k, {}),
                         **{pk: pv for pk, pv in v.items() if pv is not None}}
        else:
            merged[k] = {**merged.get(k, {}), "enabled": False}
    return merged


def _eval_preset_real_stats(preset_cfg: dict, base_cfg: dict) -> dict:
    """
    Evaluate a preset using analyze_cartera-equivalent logic.
    Returns real stats (n, wr, roi, pl, ci_low) reflecting what the live system
    would actually produce — not the portfolio optimizer's internal cherry-pick.
    """
    strategy_configs = _build_registry_config_map(
        _merge_preset_strategies(preset_cfg, base_cfg)
    )
    md = base_cfg.get("min_duration", {})

    all_bets = []
    for (_key, _name, _trigger_fn, _desc, _extract_fn, _win_fn) in _STRATEGY_REGISTRY:
        s_cfg = strategy_configs.get(_key, {})
        if not s_cfg.get("enabled"):
            continue
        min_dur_key = _LEGACY_MIN_DUR_KEY.get(_key, _key)
        min_dur = md.get(min_dur_key, md.get(_key, 1))
        bets = _analyze_strategy_simple(
            _key, _trigger_fn, _extract_fn, _win_fn,
            _cfg_add_snake_keys(s_cfg), min_dur,
        )
        all_bets.extend(bets)

    n = len(all_bets)
    if n == 0:
        return {"n": 0, "wr": 0.0, "roi": 0.0, "pl": 0.0, "ci_low": 0.0}
    wins = sum(1 for b in all_bets if b["won"])
    pl   = sum(b["pl"] for b in all_bets)
    ci_l, _ = _wilson_ci(wins, n)
    return {
        "n":      n,
        "wr":     round(wins / n * 100, 1),
        "roi":    round(pl / n * 100, 1),
        "pl":     round(pl, 2),
        "ci_low": ci_l,
    }


def phase4_apply(preset_paths: dict[str, Path],
                 selector: str = DEFAULT_SELECTOR,
                 dry_run: bool = False) -> str | None:
    """
    Compare preset stats, select best, apply to cartera_config.json.
    Returns winning criterion name or None if no valid preset found.
    """
    _log(f"Phase 4 — seleccionando mejor preset (criterio={selector})…")

    base_cfg = json.loads(CARTERA_CFG.read_text(encoding="utf-8"))

    candidates = []
    for crit, path in preset_paths.items():
        try:
            preset_cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        _log(f"  Evaluando {crit} con stats reales…")
        rs = _eval_preset_real_stats(preset_cfg, base_cfg)
        n, wr, roi, ci_l, pl = rs["n"], rs["wr"], rs["roi"], rs["ci_low"], rs["pl"]
        _log(f"    {crit}: N={n} WR={wr}% ROI={roi}% IC={ci_l} P/L={pl}")

        if n < MIN_PRESET_N or ci_l < IC95_MIN_LOW:
            _log(f"  SKIP {crit}: N={n} ci_low={ci_l} — no pasa quality gate")
            continue

        score_map = {
            "confident_roi": ci_l * roi / 100,
            "max_wr":        wr,
            "max_roi":       roi,
            "max_pl":        pl,
            "min_dd":        pl,   # no max_dd available in real stats; use pl as proxy
            # Balances statistical quality (ci_low, wr) with sample size (sqrt(N)).
            # Penalizes low-N presets even if they have high ROI.
            # Formula: ci_low × wr × sqrt(N)
            "robust":        ci_l * wr * math.sqrt(max(n, 1)),
        }
        score = score_map.get(selector, ci_l * roi / 100)
        candidates.append({
            "criterion": crit, "score": score,
            "n": n, "wr": wr, "roi": roi, "ci_low": ci_l, "pl": pl,
        })

    if not candidates:
        _log("  No hay presets válidos — cartera_config.json sin cambios")
        return None

    best = max(candidates, key=lambda x: x["score"])
    _log(f"  GANADOR: {best['criterion']} — "
         f"N={best['n']} WR={best['wr']}% ROI={best['roi']}% "
         f"IC=[{best['ci_low']}] P/L={best['pl']}")
    _log(f"  Otros presets: {[c['criterion'] for c in candidates if c != best]}")

    src = preset_paths[best["criterion"]]
    if not dry_run:
        bak = CARTERA_CFG.with_suffix(
            f".json.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}_final")
        shutil.copy2(CARTERA_CFG, bak)

        preset_cfg = json.loads(src.read_text(encoding="utf-8"))
        merged = dict(base_cfg)
        for key in ("flat_stake", "initial_bankroll", "bankroll_mode",
                    "active_preset", "risk_filter", "adjustments"):
            if key in preset_cfg:
                merged[key] = preset_cfg[key]
        merged["strategies"] = _merge_preset_strategies(preset_cfg, base_cfg)

        CARTERA_CFG.write_text(json.dumps(merged, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        _log(f"  ✓ cartera_config.json actualizado desde {src.name}")
        _log(f"    (backup: {bak.name})")
    else:
        _log(f"  DRY_RUN: se aplicaría {src.name}")

    return best["criterion"]


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 5 — Export
# ─────────────────────────────────────────────────────────────────────────────

def phase5_export():
    """
    Generate CSV + XLSX from the current cartera_config.json (final portfolio).
    """
    _log("Phase 5 — exportando resultados…")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Re-run analyze_cartera with final config
    if hasattr(csv_reader, "_cartera_cache"):
        csv_reader._cartera_cache.clear()
    if hasattr(csv_reader, "_result_cache"):
        csv_reader._result_cache.clear()

    data  = csv_reader.analyze_cartera()
    bets  = data.get("bets", [])
    by_st = data.get("by_strategy", {})

    # ── CSV ──────────────────────────────────────────────────────────────────
    import csv as _csv
    csv_path = EXPORTS_DIR / f"bt_results_{ts}.csv"
    fieldnames = ["match_id", "strategy", "strategy_label", "minuto",
                  "back_odds", "won", "pl", "País", "Liga", "timestamp_utc"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(bets)
    _log(f"  CSV: {csv_path.name}  ({len(bets)} bets)")

    # ── XLSX ─────────────────────────────────────────────────────────────────
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()

        # Sheet 1: all bets
        ws_bets = wb.active
        ws_bets.title = "Bets"
        _xlsx_write_rows(ws_bets, fieldnames,
                         [{f: b.get(f, "") for f in fieldnames} for b in bets])

        # Sheet 2: strategy summary
        ws_sum = wb.create_sheet("Por Estrategia")
        sum_fields = ["strategy", "bets", "wins", "win_pct", "pl", "roi"]
        sum_rows = []
        for st_key, st_data in sorted(by_st.items()):
            if st_data.get("bets", 0) == 0:
                continue
            ci_l, ci_h = _wilson_ci(st_data.get("wins", 0), st_data.get("bets", 0))
            sum_rows.append({
                "strategy": st_key,
                "bets":     st_data.get("bets", 0),
                "wins":     st_data.get("wins", 0),
                "win_pct":  st_data.get("win_pct", 0),
                "pl":       st_data.get("pl", 0),
                "roi":      st_data.get("roi", 0),
                "ci_low":   ci_l,
                "ci_high":  ci_h,
            })
        _xlsx_write_rows(ws_sum,
                         ["strategy","bets","wins","win_pct","pl","roi","ci_low","ci_high"],
                         sum_rows)

        # Sheet 3: cumulative P/L
        ws_cum = wb.create_sheet("Acumulado")
        ws_cum.append(["#", "strategy", "won", "pl", "cumul_pl"])
        cumul = 0.0
        for i, b in enumerate(bets, 1):
            cumul += b["pl"]
            ws_cum.append([i, b.get("strategy",""), b.get("won",""),
                           b.get("pl",""), round(cumul, 2)])

        xlsx_path = EXPORTS_DIR / f"bt_results_{ts}.xlsx"
        wb.save(str(xlsx_path))
        _log(f"  XLSX: {xlsx_path.name}")
    except ImportError:
        _log("  WARN: openpyxl no disponible — XLSX no generado. "
             "Instala con: pip install openpyxl")

    return csv_path


def _xlsx_write_rows(ws, headers: list, rows: list):
    """Write headers + rows to a worksheet with basic formatting."""
    from openpyxl.styles import Font, PatternFill, Alignment
    header_fill = PatternFill("solid", fgColor="2F5496")
    ws.append(headers)
    for cell in ws[1]:
        cell.font      = Font(bold=True, color="FFFFFF")
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        ws.append([row.get(h, "") for h in headers])


# ─────────────────────────────────────────────────────────────────────────────
# SAVE / LOAD intermediate results
# ─────────────────────────────────────────────────────────────────────────────

def save_results(individual: dict, approved_strategies: dict):
    data = {
        "timestamp":  datetime.now().isoformat(),
        "individual": individual,
        "approved":   approved_strategies,
    }
    RESULTS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    _log(f"Resultados guardados en {RESULTS_FILE.name}")


def load_results() -> tuple[dict, dict] | None:
    if not RESULTS_FILE.exists():
        return None
    data = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    return data.get("individual", {}), data.get("approved", {})


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Furbo BT optimizer")
    parser.add_argument("--phase",
        choices=["all", "individual", "presets", "apply", "export"],
        default="all")
    parser.add_argument("--strategies", default=None,
        help="Comma-separated list of strategy families to optimize (individual phase only)")
    parser.add_argument("--criterion", default=DEFAULT_SELECTOR,
        help=f"Selector criterion for best preset: {DEFAULT_SELECTOR}")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true",
        help="Never write to cartera_config.json")
    args = parser.parse_args()

    only = [s.strip() for s in args.strategies.split(",")] if args.strategies else None
    dry  = args.dry_run

    _log("=" * 60)
    _log(f"bt_optimizer.py  phase={args.phase}  workers={args.workers}"
         f"  dry_run={dry}")
    _log("=" * 60)

    # ── Phase 0: always load data first ─────────────────────────────────────
    _, n_fin = phase0_load()

    if args.phase in ("all", "individual"):
        individual = phase1_individual(n_fin, workers=args.workers, only=only)
        new_strats = phase2_build_config(individual)
        save_results(individual, new_strats)

        # Print summary table
        _log("\n── RESUMEN PHASE 1+2 ──────────────────────────────────────")
        _log(f"{'Estrategia':<28} {'N':>5} {'WR%':>6} {'ROI%':>7} "
             f"{'P/L':>8} {'IC95':>12}")
        _log("-" * 70)
        for fam, r in sorted(individual.items(), key=lambda x: -x[1]["score"]):
            ver = r.get("version_key", "")
            label = f"{fam} ({ver})" if ver else fam
            ci    = f"[{r['ci_low']}-{r['ci_high']}]"
            _log(f"{label:<28} {r['n']:>5} {r['wr']:>6} {r['roi']:>7} "
                 f"{r['pl']:>8.1f} {ci:>12}")

        if args.phase == "individual":
            return

    elif args.phase in ("presets", "apply"):
        saved = load_results()
        if saved is None:
            _log("ERROR: no hay resultados de phase individual guardados. "
                 "Ejecuta --phase individual primero.")
            sys.exit(1)
        individual, new_strats = saved

    if args.phase in ("all", "presets"):
        preset_paths = phase3_presets(new_strats, workers=args.workers, dry_run=dry)
        if not preset_paths:
            _log("No se generaron presets — abortando")
            return

        if args.phase == "presets":
            return

    if args.phase in ("all", "apply"):
        if args.phase == "apply":
            preset_paths = {
                c: PRESETS_DIR / f"preset_{c}_config.json"
                for c in CRITERIA
                if (PRESETS_DIR / f"preset_{c}_config.json").exists()
            }
        best = phase4_apply(preset_paths, selector=args.criterion, dry_run=dry)
        if best:
            _log(f"\n✓ Preset aplicado: {best}")

    if args.phase in ("all", "export"):
        phase5_export()

    _log("\n✓ bt_optimizer.py completado")


if __name__ == "__main__":
    main()
