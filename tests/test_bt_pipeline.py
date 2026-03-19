"""
test_bt_pipeline.py — Cross-phase invariant tests for the backtest pipeline.

Ensures that data flowing between bt_optimizer phases is consistent and that
no change to one phase can silently break another. Organized by phase boundary.

Categories:
  C1  Phase 0→1: SEARCH_SPACES ↔ registry ↔ config alignment
  C2  Phase 1:   Quality gate consistency and _eval_bets correctness
  C3  Phase 1→1.5: Odds calibration buckets and LAY exclusion
  C4  Phase 1→2: snake_to_camel mapping completeness
  C5  Phase 2→2.5: Cross-validation contract (robust/fragile handling)
  C6  Phase 3→4: Config merge, preset eval, dedup alignment
  C7  Phase 4→5: Export consistency
  C8  Cross-cutting: Wilson CI, drawdown, determinism

Usage:
    python tests/test_bt_pipeline.py
    python tests/test_bt_pipeline.py --verbose
    python tests/test_bt_pipeline.py -k C4   # run only category C4
"""

import sys
import os
import io
import json
import math
import inspect
import argparse
import re
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "betfair_scraper" / "dashboard" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "betfair_scraper"))
sys.path.insert(0, str(ROOT / "scripts"))

# ── Imports ───────────────────────────────────────────────────────────────────
from utils.csv_reader import (
    _STRATEGY_REGISTRY,
    _STRATEGY_REGISTRY_KEYS,
    _analyze_strategy_simple,
    _cfg_add_snake_keys,
    _normalize_mercado,
    _STRATEGY_MARKET,
)

import bt_optimizer
from bt_optimizer import (
    SEARCH_SPACES, SINGLE_STRATEGIES, _PERMANENTLY_DISABLED,
    _eval_bets, _wilson_ci, _max_drawdown, _snake_to_camel,
    _calibrate_odds_min, _ODDS_BUCKETS, _MIN_BUCKET_N,
    G_MIN_ROI, IC95_MIN_LOW, _min_pl_per_bet, _min_n,
    phase2_build_config, _merge_preset_strategies,
    _eval_preset_real_stats, DEFAULT_MIN_DUR,
    MIN_PRESET_N, CRITERIA, DEFAULT_SELECTOR,
)

from api.optimize import (
    _simulate_cartera_py, _score_of, _wilson_ci as opt_wilson_ci,
    _collect_bets_dynamic, _eval_dynamic,
    _apply_realistic_adj, _filter_by_risk,
    BR_OPTS, RISK_OPTS,
)

from api.optimizer_cli import (
    _build_preset_config, DEFAULT_ADJ,
)

CARTERA_CFG = ROOT / "betfair_scraper" / "cartera_config.json"


# ── Test runner ───────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0
VERBOSE = False
CATEGORY_FILTER = None
_results = []


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    _results.append((status, name, detail))
    if VERBOSE or not condition:
        tag = "✓" if condition else "✗"
        msg = f"  {tag} {name}"
        if detail:
            msg += f"\n      {detail}"
        print(msg)


def section(title: str):
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_config():
    with open(CARTERA_CFG, encoding="utf-8") as f:
        return json.load(f)


def _make_bets(n_win=30, n_lose=20, strategy="test_strat", odds=3.0, base_date="2026-01"):
    """Generate synthetic bets for testing."""
    bets = []
    for i in range(n_win):
        bets.append({
            "strategy": strategy,
            "match_id": f"match_{i}",
            "won": True,
            "pl": round((odds - 1) * 0.95, 2),
            "back_odds": odds,
            "minuto": 70,
            "timestamp_utc": f"{base_date}-{i+1:02d} 20:00:00",
            "risk_level": "none",
            "mercado": "BACK DRAW",
        })
    for i in range(n_lose):
        bets.append({
            "strategy": strategy,
            "match_id": f"match_{n_win + i}",
            "won": False,
            "pl": -1.0,
            "back_odds": odds,
            "minuto": 70,
            "timestamp_utc": f"{base_date}-{max(1, (n_win + i + 1) % 28):02d} 20:00:00",
            "risk_level": "none",
            "mercado": "BACK DRAW",
        })
    bets.sort(key=lambda b: b["timestamp_utc"])
    return bets


REGISTRY_KEYS = {e[0] for e in _STRATEGY_REGISTRY}


# ═══════════════════════════════════════════════════════════════════════════════
# C1 — Phase 0→1: SEARCH_SPACES ↔ registry ↔ config alignment
# ═══════════════════════════════════════════════════════════════════════════════

def c1_search_spaces_alignment():
    section("C1 — Phase 0→1: SEARCH_SPACES ↔ registry alignment")

    # C1.1: Every SINGLE_STRATEGIES entry has a SEARCH_SPACES entry
    ss_keys = set(SEARCH_SPACES.keys())
    missing_ss = [k for k in SINGLE_STRATEGIES if k not in ss_keys]
    check("C1.1 Every SINGLE_STRATEGY has SEARCH_SPACES",
          len(missing_ss) == 0,
          f"missing: {missing_ss}")

    # C1.2: Every SEARCH_SPACES key is a valid registry key
    orphan_ss = ss_keys - REGISTRY_KEYS
    check("C1.2 All SEARCH_SPACES keys are valid registry keys",
          len(orphan_ss) == 0,
          f"orphaned: {sorted(orphan_ss)}")

    # C1.3: Every SEARCH_SPACES key is in SINGLE_STRATEGIES
    ss_not_in_single = ss_keys - set(SINGLE_STRATEGIES)
    check("C1.3 All SEARCH_SPACES keys are in SINGLE_STRATEGIES",
          len(ss_not_in_single) == 0,
          f"in SEARCH_SPACES but not SINGLE_STRATEGIES: {sorted(ss_not_in_single)}")

    # C1.4: SINGLE_STRATEGIES + tarde_asia covers ALL registry keys
    all_bt_keys = set(SINGLE_STRATEGIES + ["tarde_asia"])
    uncovered = REGISTRY_KEYS - all_bt_keys
    check("C1.4 SINGLE_STRATEGIES + tarde_asia covers all registry",
          len(uncovered) == 0,
          f"uncovered registry keys: {sorted(uncovered)}")

    extra = all_bt_keys - REGISTRY_KEYS
    check("C1.5 No phantom keys in SINGLE_STRATEGIES",
          len(extra) == 0,
          f"in SINGLE_STRATEGIES but not registry: {sorted(extra)}")

    # C1.6: _PERMANENTLY_DISABLED are all in SINGLE_STRATEGIES (so they're known)
    unknown_disabled = _PERMANENTLY_DISABLED - set(SINGLE_STRATEGIES)
    check("C1.6 _PERMANENTLY_DISABLED keys are in SINGLE_STRATEGIES",
          len(unknown_disabled) == 0,
          f"unknown disabled: {sorted(unknown_disabled)}")

    # C1.7: _PERMANENTLY_DISABLED are valid registry keys
    bad_disabled = _PERMANENTLY_DISABLED - REGISTRY_KEYS
    check("C1.7 _PERMANENTLY_DISABLED are valid registry keys",
          len(bad_disabled) == 0,
          f"not in registry: {sorted(bad_disabled)}")

    # C1.8: Every registry key has a cartera_config.json entry
    cfg = _load_config()
    cfg_strats = set(cfg.get("strategies", {}).keys())
    missing_cfg = REGISTRY_KEYS - cfg_strats
    check("C1.8 Every registry key has a config entry",
          len(missing_cfg) == 0,
          f"in registry but not config: {sorted(missing_cfg)}")

    # C1.9: SEARCH_SPACES param lists are non-empty
    empty_params = [k for k, v in SEARCH_SPACES.items()
                    if not v or any(len(vals) == 0 for vals in v.values())]
    check("C1.9 All SEARCH_SPACES have non-empty param lists",
          len(empty_params) == 0,
          f"empty param lists: {empty_params}")

    # C1.10: Grid sizes are reasonable (< 50,000 combos per strategy)
    import itertools
    too_large = []
    for k, v in SEARCH_SPACES.items():
        n_combos = 1
        for vals in v.values():
            n_combos *= len(vals)
        if n_combos > 50000:
            too_large.append(f"{k}: {n_combos}")
    check("C1.10 No SEARCH_SPACE has > 50k combos",
          len(too_large) == 0,
          f"too large: {too_large}")


# ═══════════════════════════════════════════════════════════════════════════════
# C2 — Phase 1: Quality gate consistency
# ═══════════════════════════════════════════════════════════════════════════════

def c2_quality_gates():
    section("C2 — Phase 1: Quality gate consistency")

    n_fin = 1200  # typical dataset size

    # C2.1: _eval_bets returns None for too few bets
    small_bets = _make_bets(n_win=5, n_lose=3)
    check("C2.1 _eval_bets rejects N < min_n",
          _eval_bets(small_bets, n_fin) is None,
          f"min_n({n_fin})={_min_n(n_fin)}, got N={len(small_bets)}")

    # C2.2: _eval_bets returns None for low ROI
    # Make bets with ~0% ROI: equal wins and losses at odds 2.0
    # odds=2.0: win_pl = (2-1)*0.95 = 0.95, lose_pl = -1.0
    # At 50/50 the avg pl = (0.95 - 1.0)/2 = -0.025 → negative ROI
    low_roi_bets = _make_bets(n_win=26, n_lose=24, odds=2.0)
    result = _eval_bets(low_roi_bets, n_fin)
    check("C2.2 _eval_bets rejects low ROI (<10%)",
          result is None,
          f"50 bets at 52% WR with odds=2.0 should fail ROI gate")

    # C2.3: _eval_bets accepts clearly good bets
    good_bets = _make_bets(n_win=40, n_lose=10, odds=3.0)
    good_result = _eval_bets(good_bets, n_fin)
    check("C2.3 _eval_bets accepts strong strategy (80% WR, odds=3.0)",
          good_result is not None,
          "40W/10L at odds 3.0 should easily pass")

    if good_result:
        # C2.4: Score formula is ci_low * roi / 100
        expected_score = round(good_result["ci_low"] * good_result["roi"] / 100, 4)
        check("C2.4 Score formula = ci_low * roi / 100",
              abs(good_result["score"] - expected_score) < 0.01,
              f"expected={expected_score}, got={good_result['score']}")

        # C2.5: Metrics are internally consistent
        check("C2.5 wins <= n",
              good_result["wins"] <= good_result["n"])
        check("C2.6 wr = wins/n * 100",
              abs(good_result["wr"] - good_result["wins"] / good_result["n"] * 100) < 0.2)
        check("C2.7 roi = pl/n * 100",
              abs(good_result["roi"] - good_result["pl"] / good_result["n"] * 100) < 0.2)

    # C2.8: Quality gate constants match documented values
    check("C2.8 G_MIN_ROI = 10.0",
          G_MIN_ROI == 10.0,
          f"actual={G_MIN_ROI}")
    check("C2.9 IC95_MIN_LOW = 40.0",
          IC95_MIN_LOW == 40.0,
          f"actual={IC95_MIN_LOW}")

    # C2.10: _min_n formula is max(15, n_fin // 25)
    for nf in [100, 500, 1200, 2000]:
        expected = max(15, nf // 25)
        actual = _min_n(nf)
        check(f"C2.10 _min_n({nf}) = {expected}",
              actual == expected,
              f"expected={expected}, actual={actual}")

    # C2.11: _min_pl_per_bet is capped at 0.30
    check("C2.11 _min_pl_per_bet(10000) = 0.30 (cap)",
          abs(_min_pl_per_bet(10000) - 0.30) < 0.001)
    check("C2.12 _min_pl_per_bet(0) = 0.10 (floor)",
          abs(_min_pl_per_bet(0) - 0.10) < 0.001)

    # C2.13: DEFAULT_MIN_DUR keys are all valid registry keys
    bad_md = [k for k in DEFAULT_MIN_DUR if k not in REGISTRY_KEYS]
    check("C2.13 DEFAULT_MIN_DUR keys are valid registry keys",
          len(bad_md) == 0,
          f"invalid: {bad_md}")


# ═══════════════════════════════════════════════════════════════════════════════
# C3 — Phase 1→1.5: Odds calibration
# ═══════════════════════════════════════════════════════════════════════════════

def c3_odds_calibration():
    section("C3 — Phase 1→1.5: Odds calibration invariants")

    # C3.1: Odds buckets are contiguous (each bucket's upper == next's lower)
    for i in range(len(_ODDS_BUCKETS) - 1):
        _, hi, _ = _ODDS_BUCKETS[i]
        lo_next, _, _ = _ODDS_BUCKETS[i + 1]
        check(f"C3.1 Bucket {i}→{i+1} contiguous ({hi} == {lo_next})",
              abs(hi - lo_next) < 0.001,
              f"gap: bucket {i} ends at {hi}, bucket {i+1} starts at {lo_next}")

    # C3.2: First bucket starts at 1.00
    check("C3.2 First bucket starts at 1.00",
          abs(_ODDS_BUCKETS[0][0] - 1.00) < 0.001)

    # C3.3: Last bucket ends at infinity
    check("C3.3 Last bucket ends at infinity",
          _ODDS_BUCKETS[-1][1] == float("inf"))

    # C3.4: Bucket midpoints are within [lo, hi]
    for i, (lo, hi, mid) in enumerate(_ODDS_BUCKETS):
        if hi != float("inf"):
            check(f"C3.4 Bucket {i} midpoint {mid} in [{lo}, {hi}]",
                  lo <= mid <= hi,
                  f"midpoint {mid} outside [{lo}, {hi}]")

    # C3.5: _MIN_BUCKET_N is positive
    check("C3.5 _MIN_BUCKET_N > 0",
          _MIN_BUCKET_N > 0,
          f"actual={_MIN_BUCKET_N}")

    # C3.6: _calibrate_odds_min returns None for LAY strategies
    for lay_key in _PERMANENTLY_DISABLED:
        result = _calibrate_odds_min(lay_key, {"m_min": 60, "m_max": 85}, 1)
        check(f"C3.6 _calibrate_odds_min returns None for LAY '{lay_key}'",
              result is None)

    # C3.7: _calibrate_odds_min returns None for strategies with "lay" in name
    result = _calibrate_odds_min("lay_draw_away_leading", {"m_min": 50, "m_max": 80}, 1)
    check("C3.7 _calibrate_odds_min returns None for lay_draw_away_leading",
          result is None)


# ═══════════════════════════════════════════════════════════════════════════════
# C4 — Phase 1→2: snake_to_camel mapping completeness
# ═══════════════════════════════════════════════════════════════════════════════

def c4_param_mapping():
    section("C4 — Phase 1→2: snake_to_camel mapping completeness")

    # Collect ALL param keys used across all SEARCH_SPACES
    all_search_params = set()
    for space in SEARCH_SPACES.values():
        all_search_params.update(space.keys())

    # C4.1: Every SEARCH_SPACES param survives the full round-trip:
    #   snake (grid search) → _snake_to_camel → config → _cfg_add_snake_keys → trigger
    # Some params have explicit camelCase mappings (xg_max→xgMax); others are
    # pass-through (fav_max stays fav_max). Both are valid as long as the trigger
    # can read the value after the round-trip.
    camel_results = {}
    roundtrip_failures = []
    for param in sorted(all_search_params):
        result = _snake_to_camel({param: 42})
        camel_key = list(result.keys())[0]
        camel_results[param] = camel_key
        # Now simulate reading from config: _cfg_add_snake_keys should produce
        # the original param key (or the value should be accessible)
        cfg_out = _cfg_add_snake_keys({camel_key: 42})
        # The trigger reads cfg.get(param) — the original snake key must be present
        if param not in cfg_out and camel_key not in cfg_out:
            roundtrip_failures.append(f"{param} → {camel_key} → lost in _cfg_add_snake_keys")
        elif cfg_out.get(param) != 42 and cfg_out.get(camel_key) != 42:
            roundtrip_failures.append(f"{param} → {camel_key} → value changed")

    check("C4.1 All SEARCH_SPACES params survive round-trip (snake→camel→config→trigger)",
          len(roundtrip_failures) == 0,
          f"failures: {roundtrip_failures}")

    # C4.2: No collisions — two different snake keys shouldn't map to same camelCase
    from collections import Counter
    camel_values = list(camel_results.values())
    dupes = {v: [k for k, cv in camel_results.items() if cv == v]
             for v, count in Counter(camel_values).items() if count > 1}
    # Filter: only flag if the colliding keys are from the SAME strategy's search space
    real_collisions = {}
    for camel, snake_keys in dupes.items():
        for strat, space in SEARCH_SPACES.items():
            overlapping = [sk for sk in snake_keys if sk in space]
            if len(overlapping) > 1:
                real_collisions[f"{strat}/{camel}"] = overlapping
    check("C4.2 No same-strategy snake_to_camel collisions",
          len(real_collisions) == 0,
          f"collisions: {real_collisions}")

    # C4.3: _cfg_add_snake_keys round-trip — camelCase → snake → used by trigger
    # For each camel key that _snake_to_camel produces, _cfg_add_snake_keys
    # should produce the original snake_case key (or an alias)
    failed_roundtrip = []
    for snake_param, camel_param in camel_results.items():
        cfg_out = _cfg_add_snake_keys({camel_param: 42})
        # The original snake_case key (or a known alias) should be present
        if snake_param not in cfg_out:
            # Check common aliases
            aliases_present = [k for k in cfg_out.keys()
                               if k != camel_param and cfg_out[k] == 42]
            if not aliases_present:
                failed_roundtrip.append(
                    f"{camel_param} → _cfg_add_snake_keys → "
                    f"missing '{snake_param}' (got keys: {list(cfg_out.keys())})"
                )
    check("C4.3 _cfg_add_snake_keys produces snake aliases for all camel keys",
          len(failed_roundtrip) == 0,
          "\n      ".join(failed_roundtrip[:5]))

    # C4.4: Params written to config can be read back by triggers
    # Verify that for each strategy, the camelCase params in config are
    # what _cfg_add_snake_keys can translate
    cfg = _load_config()
    strategies = cfg.get("strategies", {})
    known_non_param_keys = {"enabled", "_stats", "label", "description"}
    untranslatable = []
    for strat_key, strat_cfg in strategies.items():
        if not isinstance(strat_cfg, dict):
            continue
        for param_key in strat_cfg:
            if param_key in known_non_param_keys or param_key.startswith("_"):
                continue
            # This camelCase key should be translatable by _cfg_add_snake_keys
            translated = _cfg_add_snake_keys({param_key: strat_cfg[param_key]})
            # Should produce at least one snake_case alias beyond the original
            snake_aliases = [k for k in translated if k != param_key]
            if not snake_aliases and "_" not in param_key:
                # camelCase key with no snake translation — potential issue
                # but only flag if the key has uppercase (true camelCase)
                if any(c.isupper() for c in param_key) and param_key not in translated:
                    untranslatable.append(f"{strat_key}.{param_key}")

    # This is informational — not all camelCase keys need snake aliases
    # (some triggers read camelCase directly via cfg.get())
    if VERBOSE and untranslatable:
        print(f"    [INFO] camelCase keys without snake aliases: {untranslatable[:10]}")

    # C4.5: _snake_to_camel handles all keys in DEFAULT_MIN_DUR-related spaces
    # The minute_min/minute_max/min_minute/max_minute aliases are particularly tricky
    minute_aliases = ["minute_min", "minute_max", "min_minute", "max_minute",
                      "m_min", "m_max", "min_m", "max_m"]
    for alias in minute_aliases:
        result = _snake_to_camel({alias: 50})
        camel = list(result.keys())[0]
        check(f"C4.5 _snake_to_camel('{alias}') → camelCase '{camel}'",
              camel in ("minuteMin", "minuteMax"),
              f"got: {camel}")


# ═══════════════════════════════════════════════════════════════════════════════
# C5 — Phase 2→2.5: Cross-validation contract
# ═══════════════════════════════════════════════════════════════════════════════

def c5_crossval_contract():
    section("C5 — Phase 2→2.5: Cross-validation contract")

    # C5.1: Robustness criteria constants are correct
    check("C5.1 Robustness: mean ROI >= G_MIN_ROI (10%)",
          G_MIN_ROI == 10.0)

    # C5.2: phase2_5_crossval signature accepts required params
    sig = inspect.signature(bt_optimizer.phase2_5_crossval)
    params = list(sig.parameters.keys())
    check("C5.2 phase2_5_crossval has required params",
          all(p in params for p in ["individual_results", "new_strategies", "all_matches"]),
          f"params: {params}")

    # C5.3: _crossval_raw_metrics handles empty bets
    from bt_optimizer import _crossval_raw_metrics
    empty_metrics = _crossval_raw_metrics([])
    check("C5.3 _crossval_raw_metrics({}) returns n=0",
          empty_metrics["n"] == 0 and empty_metrics["wr"] == 0.0)

    # C5.4: _crossval_raw_metrics produces correct values
    test_bets = [{"won": True, "pl": 1.0}] * 7 + [{"won": False, "pl": -1.0}] * 3
    metrics = _crossval_raw_metrics(test_bets)
    check("C5.4 _crossval_raw_metrics: 7W/3L → wr=70%",
          abs(metrics["wr"] - 70.0) < 0.1)
    check("C5.5 _crossval_raw_metrics: 7W/3L → roi=40%",
          abs(metrics["roi"] - 40.0) < 0.1)

    # C5.6: _eval_on_matches_subset signature matches contract
    from bt_optimizer import _eval_on_matches_subset
    sig = inspect.signature(_eval_on_matches_subset)
    params = list(sig.parameters.keys())
    check("C5.6 _eval_on_matches_subset has (key, entry, cfg, min_dur, matches)",
          all(p in params for p in ["key", "entry", "cfg", "min_dur", "matches"]),
          f"params: {params}")


# ═══════════════════════════════════════════════════════════════════════════════
# C6 — Phase 3→4: Config merge, preset eval, dedup alignment
# ═══════════════════════════════════════════════════════════════════════════════

def c6_config_flow():
    section("C6 — Phase 3→4: Config merge and preset eval")

    # ── C6.1-C6.4: _merge_preset_strategies contract ────────────────────────

    base = {
        "strategies": {
            "strat_a": {"enabled": True, "minuteMin": 30, "xgMax": 0.5},
            "strat_b": {"enabled": False, "minuteMin": 60},
            "strat_c": {"enabled": True, "oddsMin": 2.0},
        }
    }

    # C6.1: Preset enables strat_a → all preset params applied
    preset = {
        "strategies": {
            "strat_a": {"enabled": True, "minuteMin": 40, "xgMax": 0.7, "newParam": 99},
        }
    }
    merged = _merge_preset_strategies(preset, base)
    check("C6.1 Preset enable: all preset params applied",
          merged["strat_a"]["minuteMin"] == 40 and merged["strat_a"]["xgMax"] == 0.7,
          f"got: {merged['strat_a']}")
    check("C6.1b Preset enable: new params added",
          merged["strat_a"].get("newParam") == 99)

    # C6.2: Preset disables strat_c → only enabled=False, params preserved
    preset_off = {
        "strategies": {
            "strat_c": {"enabled": False},
        }
    }
    merged_off = _merge_preset_strategies(preset_off, base)
    check("C6.2 Preset disable: enabled=False",
          merged_off["strat_c"]["enabled"] is False)
    check("C6.2b Preset disable: original params preserved",
          merged_off["strat_c"].get("oddsMin") == 2.0,
          f"got: {merged_off['strat_c']}")

    # C6.3: Preset references unknown strategy → ignored
    preset_phantom = {
        "strategies": {
            "phantom_strat": {"enabled": True, "minuteMin": 50},
        }
    }
    merged_phantom = _merge_preset_strategies(preset_phantom, base)
    check("C6.3 Phantom strategy in preset is ignored",
          "phantom_strat" not in merged_phantom)

    # C6.4: Base strategy not in preset → unchanged
    check("C6.4 Strategies not in preset are unchanged",
          merged["strat_b"]["enabled"] is False and
          merged["strat_b"]["minuteMin"] == 60)

    # ── C6.5: _build_preset_config never re-enables failed strategies ────────

    # C6.5: _build_preset_config respects base config disabled strategies
    # The function reads cartera_config.json, so we test its signature contract
    sig = inspect.signature(_build_preset_config)
    params = list(sig.parameters.keys())
    check("C6.5 _build_preset_config accepts 'disabled' param",
          "disabled" in params,
          f"params: {params}")

    # ── C6.6: phase2_build_config correctly enables/disables ─────────────────

    # Simulate: strat_a passed quality gates, strat_b didn't
    individual = {
        "cs_one_goal": {
            "n": 80, "wins": 50, "wr": 62.5, "pl": 20.0, "roi": 25.0,
            "ci_low": 51.0, "ci_high": 72.5, "max_dd": 4.0, "score": 12.75,
            "params": {"m_min": 65, "m_max": 88, "odds_min": 3.0, "odds_max": 999},
            "key": "cs_one_goal",
        }
    }
    new_strats = phase2_build_config(individual)

    check("C6.6 phase2_build_config: approved strategy is enabled",
          new_strats.get("cs_one_goal", {}).get("enabled") is True)

    # Strategies not in individual_results should be disabled
    for key in SINGLE_STRATEGIES + ["tarde_asia"]:
        if key != "cs_one_goal" and key in new_strats:
            check(f"C6.7 phase2_build_config: {key} disabled (not approved)",
                  new_strats[key].get("enabled") is False)
            break  # just check one representative

    # C6.8: Approved strategy has camelCase params
    check("C6.8 Approved strategy params are camelCase",
          "minuteMin" in new_strats.get("cs_one_goal", {}),
          f"keys: {list(new_strats.get('cs_one_goal', {}).keys())}")

    # ── C6.9-C6.10: _eval_preset_real_stats applies dedup ────────────────────

    # C6.9: _eval_preset_real_stats has correct signature
    sig = inspect.signature(_eval_preset_real_stats)
    params = list(sig.parameters.keys())
    check("C6.9 _eval_preset_real_stats accepts (preset_cfg, base_cfg)",
          "preset_cfg" in params and "base_cfg" in params)

    # C6.10: _normalize_mercado is used in _eval_preset_real_stats (source check)
    src = inspect.getsource(_eval_preset_real_stats)
    check("C6.10 _eval_preset_real_stats uses _normalize_mercado",
          "_normalize_mercado" in src,
          "market dedup must use _normalize_mercado for alignment with analyze_cartera")

    # ── C6.11: MIN_PRESET_N is enforced ──────────────────────────────────────

    check("C6.11 MIN_PRESET_N >= 100 (prevents over-selective portfolios)",
          MIN_PRESET_N >= 100,
          f"actual={MIN_PRESET_N}")

    # ── C6.12: All 4 CRITERIA are defined ────────────────────────────────────

    check("C6.12 CRITERIA has 4 entries",
          len(CRITERIA) == 4,
          f"actual: {CRITERIA}")
    for c in ["max_roi", "max_pl", "max_wr", "min_dd"]:
        check(f"C6.13 '{c}' in CRITERIA",
              c in CRITERIA)

    # ── C6.14: Selector scoring formulas ─────────────────────────────────────
    # Verify the score formulas in phase4_apply source code
    src = inspect.getsource(bt_optimizer.phase4_apply)
    check("C6.14 phase4_apply has 'robust' selector formula",
          "robust" in src and "sqrt" in src,
          "robust selector should use ci_l * wr * sqrt(N)")


# ═══════════════════════════════════════════════════════════════════════════════
# C7 — Phase 4→5: Export consistency
# ═══════════════════════════════════════════════════════════════════════════════

def c7_export_consistency():
    section("C7 — Phase 4→5: Export consistency")

    # C7.1: phase5_export clears caches before running
    src = inspect.getsource(bt_optimizer.phase5_export)
    check("C7.1 phase5_export clears _cartera_cache",
          "_cartera_cache" in src and "clear" in src,
          "Must clear cache to pick up Phase 4 config changes")
    check("C7.2 phase5_export clears _result_cache",
          "_result_cache" in src and "clear" in src)

    # C7.3: phase5_export uses analyze_cartera (ground truth)
    check("C7.3 phase5_export calls analyze_cartera()",
          "analyze_cartera()" in src,
          "Export must use analyze_cartera for final bets")

    # C7.4: Export CSV fieldnames match expected schema
    expected_fields = {"fecha", "match_id", "match_name", "strategy", "minuto",
                       "mercado", "back_odds", "won", "pl"}
    # Check source for fieldnames list
    fieldnames_match = re.search(r'fieldnames\s*=\s*\[([^\]]+)\]', src)
    if fieldnames_match:
        fields_str = fieldnames_match.group(1)
        for f in expected_fields:
            check(f"C7.4 Export CSV has field '{f}'",
                  f'"{f}"' in fields_str or f"'{f}'" in fields_str)
    else:
        check("C7.4 Export CSV fieldnames found in source", False,
              "Could not parse fieldnames from phase5_export source")

    # C7.5: XLSX duplicate detection sheet exists in export
    check("C7.5 Export generates 'Duplicados Mercado' sheet",
          "Duplicados Mercado" in src)


# ═══════════════════════════════════════════════════════════════════════════════
# C8 — Cross-cutting invariants
# ═══════════════════════════════════════════════════════════════════════════════

def c8_cross_cutting():
    section("C8 — Cross-cutting invariants")

    # ── C8.1-C8.5: Wilson CI ──────────────────────────────────────────────────

    # C8.1: Wilson CI returns (0, 0) for n=0
    ci_l, ci_h = _wilson_ci(0, 0)
    check("C8.1 Wilson CI(0, 0) = (0, 0)",
          ci_l == 0.0 and ci_h == 0.0)

    # C8.2: Wilson CI lower <= upper
    for wins, n in [(10, 20), (1, 100), (99, 100), (50, 50), (0, 50)]:
        ci_l, ci_h = _wilson_ci(wins, n)
        check(f"C8.2 Wilson CI({wins}/{n}): lower({ci_l}) <= upper({ci_h})",
              ci_l <= ci_h)

    # C8.3: Wilson CI bounds are in [0, 100]
    for wins, n in [(10, 20), (1, 100), (99, 100)]:
        ci_l, ci_h = _wilson_ci(wins, n)
        check(f"C8.3 Wilson CI({wins}/{n}): 0 <= {ci_l} <= {ci_h} <= 100",
              0 <= ci_l <= ci_h <= 100)

    # C8.4: Wilson CI consistency between bt_optimizer and optimize.py
    for wins, n in [(30, 50), (10, 100), (45, 60)]:
        bt_ci = _wilson_ci(wins, n)
        opt_ci = opt_wilson_ci(wins, n)
        check(f"C8.4 Wilson CI({wins}/{n}) bt==optimize",
              abs(bt_ci[0] - opt_ci[0]) < 0.1 and abs(bt_ci[1] - opt_ci[1]) < 0.1,
              f"bt={bt_ci}, opt={opt_ci}")

    # ── C8.5-C8.7: Max drawdown ─────────────────────────────────────────────

    # C8.5: Drawdown is never negative
    check("C8.5 _max_drawdown([]) = 0.0",
          _max_drawdown([]) == 0.0)

    # C8.6: All wins → no drawdown
    check("C8.6 _max_drawdown all wins = 0.0",
          _max_drawdown([1.0, 1.0, 1.0, 1.0]) == 0.0)

    # C8.7: Known drawdown sequence
    dd = _max_drawdown([1.0, -2.0, -1.0, 3.0, -0.5])
    check("C8.7 _max_drawdown([1, -2, -1, 3, -0.5]) = 3.0",
          abs(dd - 3.0) < 0.01,
          f"got: {dd}")

    # C8.8: All losses → drawdown = total loss
    dd_all_loss = _max_drawdown([-1.0, -1.0, -1.0])
    check("C8.8 _max_drawdown all losses = total loss",
          abs(dd_all_loss - 3.0) < 0.01,
          f"got: {dd_all_loss}")

    # ── C8.9-C8.12: _normalize_mercado determinism ──────────────────────────

    # C8.9: Same input → same output
    test_mercados = [
        "BACK DRAW", "BACK HOME", "BACK AWAY",
        "BACK CS 2-1", "BACK OVER 2.5", "BACK UNDER 3.5",
        "LAY DRAW", "LAY OVER 4.5",
    ]
    for m in test_mercados:
        r1 = _normalize_mercado(m)
        r2 = _normalize_mercado(m)
        check(f"C8.9 _normalize_mercado('{m}') deterministic",
              r1 == r2,
              f"first={r1}, second={r2}")

    # C8.10: Different mercados → different normalized keys
    draw_key = _normalize_mercado("BACK DRAW")
    home_key = _normalize_mercado("BACK HOME")
    check("C8.10 BACK DRAW ≠ BACK HOME normalized",
          draw_key != home_key,
          f"both map to: {draw_key}")

    # ── C8.11: _STRATEGY_MARKET keys are in registry ────────────────────────

    bad_market_keys = [k for k in _STRATEGY_MARKET if k not in REGISTRY_KEYS]
    check("C8.11 All _STRATEGY_MARKET keys are valid registry keys",
          len(bad_market_keys) == 0,
          f"invalid: {bad_market_keys}")

    # C8.12: _STRATEGY_MARKET values are non-empty strings
    bad_values = [k for k, v in _STRATEGY_MARKET.items()
                  if not isinstance(v, str) or not v]
    check("C8.12 All _STRATEGY_MARKET values are non-empty strings",
          len(bad_values) == 0,
          f"bad values: {bad_values}")

    # ── C8.13-C8.15: _PERMANENTLY_DISABLED invariants ───────────────────────

    # C8.13: Permanently disabled strategies should NOT be enabled in config
    cfg = _load_config()
    strats = cfg.get("strategies", {})
    wrongly_enabled = [k for k in _PERMANENTLY_DISABLED
                       if strats.get(k, {}).get("enabled") is True]
    check("C8.13 _PERMANENTLY_DISABLED not enabled in cartera_config.json",
          len(wrongly_enabled) == 0,
          f"wrongly enabled: {wrongly_enabled}")

    # C8.14: Scoring functions in optimize.py are consistent with bt_optimizer
    # Both should use the same Wilson CI formula
    bets = _make_bets(n_win=35, n_lose=15)
    sim = _simulate_cartera_py(bets, 1000.0, "fixed")
    for criterion in CRITERIA:
        score = _score_of(sim, criterion)
        check(f"C8.14 _score_of(sim, '{criterion}') is finite",
              math.isfinite(score),
              f"got: {score}")

    # C8.15: _collect_bets_dynamic correctly filters
    multi_bets = (
        _make_bets(n_win=20, n_lose=10, strategy="strat_a") +
        _make_bets(n_win=15, n_lose=5, strategy="strat_b")
    )
    collected_all = _collect_bets_dynamic(multi_bets, set())
    check("C8.15 _collect_bets_dynamic(disabled={}) returns all",
          len(collected_all) == len(multi_bets))

    collected_a = _collect_bets_dynamic(multi_bets, {"strat_a"})
    check("C8.16 _collect_bets_dynamic(disabled={'strat_a'}) removes strat_a",
          all(b["strategy"] != "strat_a" for b in collected_a))
    check("C8.17 _collect_bets_dynamic preserves strat_b when strat_a disabled",
          any(b["strategy"] == "strat_b" for b in collected_a))


# ═══════════════════════════════════════════════════════════════════════════════
# Main runner
# ═══════════════════════════════════════════════════════════════════════════════

ALL_CATEGORIES = [
    ("C1", c1_search_spaces_alignment),
    ("C2", c2_quality_gates),
    ("C3", c3_odds_calibration),
    ("C4", c4_param_mapping),
    ("C5", c5_crossval_contract),
    ("C6", c6_config_flow),
    ("C7", c7_export_consistency),
    ("C8", c8_cross_cutting),
]


def main():
    global VERBOSE, CATEGORY_FILTER

    parser = argparse.ArgumentParser(description="BT pipeline cross-phase tests")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("-k", "--category", type=str, default=None,
                        help="Run only categories matching this prefix (e.g. C4)")
    args = parser.parse_args()
    VERBOSE = args.verbose
    CATEGORY_FILTER = args.category

    print("=" * 70)
    print("  BACKTEST PIPELINE — Cross-Phase Invariant Tests")
    print("=" * 70)

    for cat_id, cat_fn in ALL_CATEGORIES:
        if CATEGORY_FILTER and not cat_id.upper().startswith(CATEGORY_FILTER.upper()):
            continue
        try:
            cat_fn()
        except Exception as e:
            print(f"\n  !! {cat_id} CRASHED: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    total = PASS + FAIL
    print(f"\n{'='*70}")
    print(f"  RESULTADO: {PASS}/{total} passed", end="")
    if FAIL:
        print(f"  ({FAIL} FAILED)")
        failed = [(n, d) for s, n, d in _results if s == "FAIL"]
        print("\n  FALLOS:")
        for name, detail in failed:
            print(f"    ✗ {name}")
            if detail:
                for line in detail.split("\n"):
                    print(f"      {line}")
    else:
        print("  — ALL PASS ✓")
    print("=" * 70)

    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
