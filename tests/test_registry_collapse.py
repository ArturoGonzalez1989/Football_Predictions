"""
Regression test for registry collapse (version system eradication).

Verifies:
  1. Registry size is 32 (no versioned entries)
  2. No versioned strategy keys remain (except lay_over45_v3 which is a name, not a version)
  3. Config keys match registry keys directly (no legacy mapping needed)
  4. No versions block in cartera_config.json
  5. analyze_cartera() runs without errors
  6. All strategy bets use registry keys (no versioned names)

Usage:
    python tests/test_registry_collapse.py
"""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
sys.path.insert(0, str(ROOT / "betfair_scraper"))

from utils.csv_reader import (
    _STRATEGY_REGISTRY,
    _STRATEGY_REGISTRY_KEYS,
    _cfg_add_snake_keys,
)

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  OK {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}: {detail}")


print("=== Test 1: Registry size ===")
check("Registry has 32 entries", len(_STRATEGY_REGISTRY) == 32,
      f"got {len(_STRATEGY_REGISTRY)}")
check("Registry keys set has 32 unique keys", len(_STRATEGY_REGISTRY_KEYS) == 32,
      f"got {len(_STRATEGY_REGISTRY_KEYS)}")

print("\n=== Test 2: No versioned keys ===")
VERSIONED_SUFFIXES = ["_v1", "_v15", "_v2", "_v2r", "_v3", "_v4", "_v5", "_v6", "_base"]
EXCEPTIONS = {"lay_over45_v3"}  # this IS the strategy name, not a version
for key, *_ in _STRATEGY_REGISTRY:
    if key in EXCEPTIONS:
        continue
    has_version = any(key.endswith(sfx) for sfx in VERSIONED_SUFFIXES)
    check(f"No version suffix in '{key}'", not has_version)

print("\n=== Test 3: Config keys match registry keys ===")
with open(ROOT / "betfair_scraper" / "cartera_config.json", encoding="utf-8") as f:
    cfg = json.load(f)
s = cfg["strategies"]

# Verify the 7 original strategies use registry keys (not legacy keys)
REGISTRY_KEYS_EXPECTED = [
    "back_draw_00", "xg_underperformance", "odds_drift",
    "goal_clustering", "pressure_cooker", "momentum_xg", "tarde_asia",
]
for reg_key in REGISTRY_KEYS_EXPECTED:
    check(f"'{reg_key}' exists in strategies", reg_key in s,
          f"missing from strategies dict")

# Verify legacy keys are NOT in config
LEGACY_KEYS = ["draw", "xg", "drift", "clustering", "pressure"]
for legacy_key in LEGACY_KEYS:
    check(f"Legacy key '{legacy_key}' not in strategies", legacy_key not in s,
          "still present")

# Verify no 'version' field in any strategy
for key, strat_cfg in s.items():
    if isinstance(strat_cfg, dict):
        check(f"No 'version' field in '{key}'", "version" not in strat_cfg,
              f"has version={strat_cfg.get('version')}")

print("\n=== Test 4: No versions block in config ===")
check("No 'versions' top-level key", "versions" not in cfg,
      "still present")

# Verify min_duration uses registry keys
md = cfg.get("min_duration", {})
for reg_key in ["back_draw_00", "xg_underperformance", "odds_drift",
                "goal_clustering", "pressure_cooker"]:
    check(f"min_duration has '{reg_key}'", reg_key in md,
          f"missing from min_duration")
for legacy_key in LEGACY_KEYS:
    check(f"min_duration no legacy '{legacy_key}'", legacy_key not in md,
          "still present")

print("\n=== Test 5: Mapping infrastructure deleted ===")
# Verify deleted functions/dicts are not importable
import utils.csv_reader as _cr
check("No _build_registry_config_map", not hasattr(_cr, "_build_registry_config_map"))
check("No _LEGACY_MIN_DUR_KEY", not hasattr(_cr, "_LEGACY_MIN_DUR_KEY"))
check("No _ORIG_REGISTRY_MAP", not hasattr(_cr, "_ORIG_REGISTRY_MAP"))
check("No _ORIG_DEFAULT_VERS", not hasattr(_cr, "_ORIG_DEFAULT_VERS"))
# These should still exist
check("_cfg_add_snake_keys exists", hasattr(_cr, "_cfg_add_snake_keys"))
check("_STRATEGY_REGISTRY exists", hasattr(_cr, "_STRATEGY_REGISTRY"))

print("\n=== Test 6: analyze_cartera() runs ===")
try:
    from utils.csv_reader import analyze_cartera, _result_cache
    _result_cache.clear()
    result = analyze_cartera()
    n_bets = len(result.get("bets", []))
    strategies_found = set(b.get("strategy") for b in result.get("bets", []))
    check(f"analyze_cartera() returned {n_bets} bets", n_bets > 0)
    # Verify no versioned strategy names in bets
    for strat in strategies_found:
        if strat in EXCEPTIONS:
            continue
        has_ver = any(strat.endswith(sfx) for sfx in VERSIONED_SUFFIXES)
        check(f"No versioned strategy '{strat}' in bets", not has_ver)
except Exception as e:
    check("analyze_cartera() runs without error", False, str(e))

print(f"\n{'='*50}")
print(f"Results: {PASS} passed, {FAIL} failed")
if FAIL > 0:
    sys.exit(1)
print("All tests passed!")
