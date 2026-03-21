"""
test_system_integrity.py — Verificacion de integridad del sistema Betfair

Cubre 16 categorias de invariantes que deben mantenerse en cualquier estado del sistema:

  T1  Registry — sin versiones, conteo correcto, triggers existentes
  T2  Config structure — sin keys legacy, sin campos version, sin leakage
  T3  Config ↔ Registry sync — sin huerfanos en ninguna direccion
  T4  BT path — analyze_cartera usa todos los triggers del registry
  T5  LIVE path — analytics.py pasa 100% de params desde config, sin hardcoding legacy
  T6  Portfolio optimizer — Phase1 combos correctos, filters sin nombres legacy
  T7  Frontend — sin nombres de estrategia legacy en componentes TS/TSX
  T8  No legacy code — grep de patrones prohibidos en archivos activos
  T9  Preset files — sin keys legacy (draw/xg/drift), sin estrategias muertas, sin campos version
  T10 _STRATEGY_MARKET — todos los keys existen en el registry
  T11 Trigger naming — cada registry key tiene _detect_{key}_trigger en csv_reader
  T12 SEARCH_SPACES — cubre todos los SINGLE_STRATEGIES de bt_optimizer
  T13 _COMBO_TO_REGISTRY — todos los valores son registry keys validos
  T14 Signal min_odds — usa oddsMin del config, no hardcoded 1.21
  T15 Settlement — placed_bets won/lost coincide con score final del CSV
  T16 Match finalization — CSVs de partidos con apuestas tienen estado finalizado

Uso:
    python tests/test_system_integrity.py
    python tests/test_system_integrity.py --verbose
"""

import sys
import io
import os
import json
import re
import subprocess
import importlib
import inspect
import argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ─────────────────────────────────────────────────────────────────────────────
# Test runner helpers
# ─────────────────────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0
VERBOSE = False
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
    print(f"\n{'─'*65}")
    print(f"  {title}")
    print(f"{'─'*65}")


# ─────────────────────────────────────────────────────────────────────────────
# Load modules once
# ─────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, os.path.join(ROOT, "betfair_scraper", "dashboard", "backend"))

try:
    from utils import csv_reader as _cr
    CSV_READER_OK = True
except Exception as e:
    CSV_READER_OK = False
    CSV_READER_ERR = str(e)

try:
    from api import analytics as _analytics
    ANALYTICS_OK = True
except Exception as e:
    ANALYTICS_OK = False
    ANALYTICS_ERR = str(e)

try:
    from api import optimize as _optimize
    OPTIMIZE_OK = True
except Exception as e:
    OPTIMIZE_OK = False
    OPTIMIZE_ERR = str(e)

try:
    from api import optimizer_cli as _optimizer_cli
    OPTIMIZER_CLI_OK = True
except Exception as e:
    OPTIMIZER_CLI_OK = False
    OPTIMIZER_CLI_ERR = str(e)

_CARTERA_PATH = os.path.join(ROOT, "betfair_scraper", "cartera_config.json")
with open(_CARTERA_PATH, encoding="utf-8") as f:
    _CONFIG = json.load(f)

# ─────────────────────────────────────────────────────────────────────────────
# T1 — Registry integrity
# ─────────────────────────────────────────────────────────────────────────────

VERSIONED_SUFFIXES = ["_v1", "_v15", "_v2", "_v2r", "_v3", "_v4", "_v5", "_v6", "_base"]
# Canonical strategy names that legitimately contain a version-like suffix
# (these are standalone strategies, not versioned duplicates of another key)
CANONICAL_VERSIONED_EXCEPTIONS = {"lay_over45_v3"}
EXPECTED_REGISTRY_COUNT = 32


def t1_registry():
    section("T1 — Registry integrity")

    check("csv_reader importable", CSV_READER_OK,
          CSV_READER_ERR if not CSV_READER_OK else "")

    if not CSV_READER_OK:
        return

    reg = _cr._STRATEGY_REGISTRY
    keys = [e[0] for e in reg]

    check(f"Registry count == {EXPECTED_REGISTRY_COUNT}",
          len(reg) == EXPECTED_REGISTRY_COUNT,
          f"actual={len(reg)}, keys={keys}")

    versioned = [k for k in keys
                 if any(k.endswith(s) for s in VERSIONED_SUFFIXES)
                 and k not in CANONICAL_VERSIONED_EXCEPTIONS]
    check("No versioned keys in registry (except canonical exceptions)",
          len(versioned) == 0,
          f"versioned keys found: {versioned}")

    dupes = [k for k in keys if keys.count(k) > 1]
    check("No duplicate keys in registry",
          len(dupes) == 0,
          f"duplicate keys: {list(set(dupes))}")

    # Every key has a callable trigger as element [2]
    bad_triggers = []
    for entry in reg:
        key, _name, trigger_fn = entry[0], entry[1], entry[2]
        if not callable(trigger_fn):
            bad_triggers.append(key)
    check("All registry triggers are callable",
          len(bad_triggers) == 0,
          f"non-callable triggers: {bad_triggers}")

    # Legacy infrastructure must NOT exist
    check("No _build_registry_config_map",
          not hasattr(_cr, "_build_registry_config_map"))
    check("No _LEGACY_MIN_DUR_KEY",
          not hasattr(_cr, "_LEGACY_MIN_DUR_KEY"))
    check("No _ORIG_REGISTRY_MAP",
          not hasattr(_cr, "_ORIG_REGISTRY_MAP"))
    check("No version factory functions (_make_*_trigger)",
          not any(hasattr(_cr, f"_make_{s}_trigger")
                  for s in ("back_draw", "drift", "momentum", "xg")))


# ─────────────────────────────────────────────────────────────────────────────
# T2 — Config structure
# ─────────────────────────────────────────────────────────────────────────────

# Known valid root-level keys in cartera_config.json
VALID_ROOT_KEYS = {
    "bankroll_mode", "active_preset", "risk_filter", "min_duration",
    "adjustments", "strategies", "flat_stake", "initial_bankroll",
    "stake_pct", "stake_mode", "stake_fixed", "min_duration_live",
    "_optimizer_stats",
}


def t2_config_structure():
    section("T2 — Config structure")

    check("cartera_config.json parseable", True)  # already loaded

    # No top-level "versions" key
    check("No 'versions' key at root",
          "versions" not in _CONFIG)

    # No 'version' field inside any strategy
    strategies = _CONFIG.get("strategies", {})
    strats_with_version = [k for k, v in strategies.items()
                           if isinstance(v, dict) and "version" in v]
    check("No 'version' field in any strategy",
          len(strats_with_version) == 0,
          f"strategies with 'version' field: {strats_with_version}")

    # No strategy keys leaked to root level
    if CSV_READER_OK:
        registry_keys = {e[0] for e in _cr._STRATEGY_REGISTRY}
        leaked = [k for k in _CONFIG.keys() if k in registry_keys]
        check("No strategy keys at config root level",
              len(leaked) == 0,
              f"leaked to root: {leaked}")

    # All root keys are known
    unknown_root = [k for k in _CONFIG.keys() if k not in VALID_ROOT_KEYS]
    check("No unknown root-level keys",
          len(unknown_root) == 0,
          f"unknown keys: {unknown_root}")

    # min_duration keys are valid registry keys (if csv_reader loaded)
    if CSV_READER_OK:
        registry_keys = {e[0] for e in _cr._STRATEGY_REGISTRY}
        bad_md_keys = [k for k in _CONFIG.get("min_duration", {}).keys()
                       if k not in registry_keys]
        check("min_duration keys are all valid registry keys",
              len(bad_md_keys) == 0,
              f"invalid min_duration keys: {bad_md_keys}")

    # Strategies must have at least 'enabled' field
    missing_enabled = [k for k, v in strategies.items()
                       if isinstance(v, dict) and "enabled" not in v]
    check("All strategies have 'enabled' field",
          len(missing_enabled) == 0,
          f"missing 'enabled': {missing_enabled}")

    # No versioned strategy keys in config (except canonical exceptions)
    versioned_cfg = [k for k in strategies.keys()
                     if any(k.endswith(s) for s in VERSIONED_SUFFIXES)
                     and k not in CANONICAL_VERSIONED_EXCEPTIONS]
    check("No versioned strategy keys in config (except canonical exceptions)",
          len(versioned_cfg) == 0,
          f"versioned keys in config: {versioned_cfg}")


# ─────────────────────────────────────────────────────────────────────────────
# T3 — Config ↔ Registry sync
# ─────────────────────────────────────────────────────────────────────────────

def t3_config_registry_sync():
    section("T3 — Config ↔ Registry sync")

    if not CSV_READER_OK:
        check("SKIP (csv_reader not loaded)", False, "")
        return

    registry_keys = {e[0] for e in _cr._STRATEGY_REGISTRY}
    config_keys = set(_CONFIG.get("strategies", {}).keys())

    # Every registry key must have a config entry
    missing_in_config = registry_keys - config_keys
    check("Every registry strategy has a config entry",
          len(missing_in_config) == 0,
          f"in registry but not config: {sorted(missing_in_config)}")

    # Every config strategy key must be in registry (no orphaned config)
    orphaned_config = config_keys - registry_keys
    check("No orphaned strategy keys in config (not in registry)",
          len(orphaned_config) == 0,
          f"in config but not registry: {sorted(orphaned_config)}")

    # SINGLE_STRATEGIES covers all registry keys (including tarde_asia)
    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import bt_optimizer as _bt
        bt_families = set(_bt.SINGLE_STRATEGIES)
        missing_in_bt = registry_keys - bt_families
        check("bt_optimizer SINGLE_STRATEGIES covers all registry keys",
              len(missing_in_bt) == 0,
              f"in registry but not in bt_optimizer: {sorted(missing_in_bt)}")
        extra_in_bt = bt_families - registry_keys
        check("No bt_optimizer SINGLE_STRATEGIES keys missing from registry",
              len(extra_in_bt) == 0,
              f"in bt_optimizer but not in registry: {sorted(extra_in_bt)}")
    except Exception as e:
        check("bt_optimizer importable", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# T4 — BT path integrity
# ─────────────────────────────────────────────────────────────────────────────

def t4_bt_path():
    section("T4 — BT path integrity")

    if not CSV_READER_OK:
        check("SKIP (csv_reader not loaded)", False)
        return

    # _analyze_strategy_simple must exist and be callable
    check("_analyze_strategy_simple exists",
          hasattr(_cr, "_analyze_strategy_simple") and
          callable(_cr._analyze_strategy_simple))

    # analyze_cartera must exist
    check("analyze_cartera exists",
          hasattr(_cr, "analyze_cartera") and callable(_cr.analyze_cartera))

    # _cfg_add_snake_keys must exist (translates camelCase params for triggers)
    check("_cfg_add_snake_keys exists",
          hasattr(_cr, "_cfg_add_snake_keys") and callable(_cr._cfg_add_snake_keys))

    # No versioned strategy names in simulate_cashout_cartera's by_strategy block
    # Verify by inspecting source code
    src = inspect.getsource(_cr)
    bad_cashout_refs = re.findall(
        r'strategy.*in.*\(.*momentum_xg_v[12]|momentum_xg_v[12].*momentum_xg_v[12]',
        src
    )
    check("simulate_cashout_cartera uses 'momentum_xg' (not _v1/_v2)",
          len(bad_cashout_refs) == 0,
          f"legacy refs found: {bad_cashout_refs}")

    # Verify the by_strategy section uses correct key
    by_strat_block = re.search(
        r'result\["by_strategy"\]\["momentum_xg"\]\s*=\s*_s\(\s*\[b for b in bets if b\["strategy"\]\s*==\s*"momentum_xg"\]',
        src
    )
    check("by_strategy[momentum_xg] uses == 'momentum_xg'",
          by_strat_block is not None)


# ─────────────────────────────────────────────────────────────────────────────
# T5 — LIVE path integrity
# ─────────────────────────────────────────────────────────────────────────────

def t5_live_path():
    section("T5 — LIVE path integrity")

    if not ANALYTICS_OK:
        check("analytics importable", False, ANALYTICS_ERR if not ANALYTICS_OK else "")
        return

    check("analytics importable", True)

    src = inspect.getsource(_analytics)

    # No _ver() function
    check("No _ver() function in analytics.py",
          not re.search(r'^def _ver\(', src, re.MULTILINE))

    # No _ORIG_MAP
    check("No _ORIG_MAP in analytics.py",
          "_ORIG_MAP" not in src)

    # versions dict uses _strategy_configs and _min_duration keys
    check("versions dict uses '_strategy_configs' key",
          '"_strategy_configs"' in src or "'_strategy_configs'" in src)
    check("versions dict uses '_min_duration' key",
          '"_min_duration"' in src or "'_min_duration'" in src)

    # No legacy strategy names in analytics.py
    legacy_in_analytics = re.findall(
        r'momentum_xg_v[12]|odds_drift_v[1-6]|back_draw_00_v|xg_underperformance_base',
        src
    )
    check("No legacy versioned strategy names in analytics.py",
          len(legacy_in_analytics) == 0,
          f"legacy refs: {legacy_in_analytics}")

    # detect_betting_signals must be called with versions dict
    check("analytics calls detect_betting_signals(versions=...)",
          "detect_betting_signals(versions=" in src or
          "detect_betting_signals(versions =" in src)


# ─────────────────────────────────────────────────────────────────────────────
# T6 — Portfolio optimizer integrity
# ─────────────────────────────────────────────────────────────────────────────

def t6_optimizer():
    section("T6 — Portfolio optimizer integrity")

    if not OPTIMIZE_OK:
        check("optimize importable", False, OPTIMIZE_ERR if not OPTIMIZE_OK else "")
        return

    check("optimize importable", True)

    # Dynamic optimizer: no hardcoded strategy lists
    check("No _PHASE1_TOTAL (brute force removed)",
          not hasattr(_optimize, '_PHASE1_TOTAL'))
    check("No _phase1_worker (brute force removed)",
          not hasattr(_optimize, '_phase1_worker'))
    check("No MIN_ODDS hardcoded dict",
          not hasattr(_optimize, 'MIN_ODDS'))
    check("No MAX_BETS_COMBO hardcoded dict",
          not hasattr(_optimize, 'MAX_BETS_COMBO'))

    # Dynamic helpers exist
    check("_collect_bets_dynamic exists",
          hasattr(_optimize, '_collect_bets_dynamic'))
    check("_steepest_descent exists",
          hasattr(_optimize, '_steepest_descent'))
    check("_eval_dynamic exists",
          hasattr(_optimize, '_eval_dynamic'))

    # No hardcoded per-strategy filter functions
    for dead_name in ("_filter_draw", "_filter_xg", "_filter_drift",
                      "_filter_clustering", "_filter_pressure",
                      "_filter_tardesia", "_filter_momentum",
                      "DRAW_OPTS", "XG_OPTS", "DRIFT_OPTS",
                      "CLUSTERING_OPTS", "PRESSURE_OPTS", "TARDESIA_OPTS", "MOMENTUM_OPTS",
                      "ALL_DRAW_XG_PAIRS",
                      "DRAW_PARAMS", "XG_PARAMS", "DRIFT_PARAMS", "CLUSTERING_PARAMS"):
        check(f"No {dead_name} in optimize.py",
              not hasattr(_optimize, dead_name))

    # No legacy versioned strategy names
    src = inspect.getsource(_optimize)
    legacy_in_optimize = re.findall(
        r'momentum_xg_v[12]|odds_drift_v[1-6]|back_draw_00_v|xg_underperformance_base',
        src
    )
    check("No legacy versioned strategy names in optimize.py",
          len(legacy_in_optimize) == 0,
          f"legacy refs: {legacy_in_optimize}")

    # _build_preset_config uses dynamic disabled set, not hardcoded combo mapping
    if OPTIMIZER_CLI_OK:
        cli_src = inspect.getsource(_optimizer_cli)
        check("_build_preset_config uses 'disabled' parameter (dynamic)",
              "disabled" in inspect.signature(_optimizer_cli._build_preset_config).parameters)
        check("No _COMBO_TO_REGISTRY (hardcoded mapping removed)",
              "_COMBO_TO_REGISTRY" not in cli_src)
        # Must not reference legacy version dicts
        legacy_in_cli = re.findall(
            r'DRAW_PARAMS\[|XG_PARAMS\[|DRIFT_PARAMS\[|CLUSTERING_PARAMS\[',
            cli_src
        )
        check("No legacy DRAW_PARAMS/XG_PARAMS in optimizer_cli.py",
              len(legacy_in_cli) == 0,
              f"refs found: {legacy_in_cli}")


# ─────────────────────────────────────────────────────────────────────────────
# T7 — Frontend integrity
# ─────────────────────────────────────────────────────────────────────────────

FRONTEND_SRC = os.path.join(ROOT, "betfair_scraper", "dashboard", "frontend", "src")

LEGACY_STRATEGY_PATTERNS = [
    r'momentum_xg_v[12]',
    r'odds_drift_v[1-6]',
    r'back_draw_00_v\w',
    r'xg_underperformance_base',
    r'xg_underperformance_v[23]',
]


def t7_frontend():
    section("T7 — Frontend integrity")

    if not os.path.isdir(FRONTEND_SRC):
        check("frontend/src directory exists", False, f"not found: {FRONTEND_SRC}")
        return

    ts_files = []
    for dirpath, _, filenames in os.walk(FRONTEND_SRC):
        for fn in filenames:
            if fn.endswith(".ts") or fn.endswith(".tsx"):
                ts_files.append(os.path.join(dirpath, fn))

    check(f"Found TypeScript files ({len(ts_files)})", len(ts_files) > 0)

    for pattern in LEGACY_STRATEGY_PATTERNS:
        hits = []
        for fpath in ts_files:
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            matches = re.findall(pattern, content)
            if matches:
                rel = os.path.relpath(fpath, ROOT)
                hits.append(f"{rel}: {matches}")
        check(f"No '{pattern}' in frontend TS files",
              len(hits) == 0,
              "\n      ".join(hits))


# ─────────────────────────────────────────────────────────────────────────────
# T8 — No legacy code grep (active files only, exclude /borrar)
# ─────────────────────────────────────────────────────────────────────────────

# (pattern, description, allowed_files) — allowed_files: files where pattern is OK
# Files that are allowed to reference legacy patterns (test files that CHECK for their absence)
_SELF_EXEMPT = ["test_registry_collapse.py", "test_system_integrity.py"]

LEGACY_CODE_CHECKS = [
    # Version infrastructure
    (r'_LEGACY_MIN_DUR_KEY',     "No _LEGACY_MIN_DUR_KEY",     _SELF_EXEMPT),
    (r'_build_registry_config_map', "No _build_registry_config_map", _SELF_EXEMPT),
    (r'_ORIG_REGISTRY_MAP',      "No _ORIG_REGISTRY_MAP",      _SELF_EXEMPT),
    (r'VERSIONED_FAMILIES',      "No VERSIONED_FAMILIES",       _SELF_EXEMPT),
    (r'_run_versioned_family',   "No _run_versioned_family",    _SELF_EXEMPT),
    # Legacy strategy names in active code (not docstrings)
    (r'momentum_xg_v[12]',       "No momentum_xg_v1/v2",        _SELF_EXEMPT),
    (r'odds_drift_v[1-6]',       "No odds_drift_v1..v6",        _SELF_EXEMPT),
    (r'back_draw_00_v[0-9]',     "No back_draw_00_v*",          _SELF_EXEMPT),
    (r'xg_underperformance_base', "No xg_underperformance_base", _SELF_EXEMPT),
    # Dead portfolio optimizer code
    (r'DRAW_PARAMS\s*=\s*\{',    "No DRAW_PARAMS dict",         _SELF_EXEMPT),
    (r'XG_PARAMS\s*=\s*\{',      "No XG_PARAMS dict",           _SELF_EXEMPT),
    (r'DRIFT_PARAMS\s*=\s*\{',   "No DRIFT_PARAMS dict",        _SELF_EXEMPT),
    (r'CLUSTERING_PARAMS\s*=\s*\{', "No CLUSTERING_PARAMS dict", _SELF_EXEMPT),
    (r'LAY15_OPTS\s*=',          "No LAY15_OPTS",               _SELF_EXEMPT),
    (r'_filter_lay_over15\b',    "No _filter_lay_over15",       _SELF_EXEMPT),
    (r'_filter_lay_draw_asym\b', "No _filter_lay_draw_asym",    _SELF_EXEMPT),
    (r'_filter_back_sot_dom\b',  "No _filter_back_sot_dom",     _SELF_EXEMPT),
]

SCAN_EXTENSIONS = {".py", ".ts", ".tsx", ".json"}
EXCLUDE_DIRS = {"borrar", "node_modules", ".git", "__pycache__", ".venv", "venv", "logs"}


def _scan_file(fpath: str, pattern: str) -> list[str]:
    try:
        with open(fpath, encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return re.findall(pattern, content)
    except Exception:
        return []


def t8_no_legacy_code():
    section("T8 — No legacy code (grep active files)")

    all_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        # Prune excluded dirs in-place
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if any(fn.endswith(ext) for ext in SCAN_EXTENSIONS):
                all_files.append(os.path.join(dirpath, fn))

    for pattern, desc, allowed_basenames in LEGACY_CODE_CHECKS:
        hits = []
        for fpath in all_files:
            basename = os.path.basename(fpath)
            if basename in allowed_basenames:
                continue
            matches = _scan_file(fpath, pattern)
            if matches:
                rel = os.path.relpath(fpath, ROOT)
                hits.append(f"{rel}: {matches}")
        check(desc, len(hits) == 0, "\n      ".join(hits))


# ─────────────────────────────────────────────────────────────────────────────
# T9 — Preset files integrity
# ─────────────────────────────────────────────────────────────────────────────

PRESETS_DIR = os.path.join(ROOT, "betfair_scraper", "data", "presets")

# Legacy keys that must NOT appear in preset strategy sections
LEGACY_PRESET_KEYS = {"draw", "xg", "drift", "clustering", "pressure"}

# Dead strategies that must NOT appear anywhere in preset files
DEAD_PRESET_STRATEGIES = {
    "lay_over15", "lay_draw_asym", "lay_over25_def",
    "back_sot_dom", "back_over15_early", "lay_false_fav",
}


def t9_preset_files():
    section("T9 — Preset files integrity")

    if not os.path.isdir(PRESETS_DIR):
        check("presets/ directory exists", False, f"not found: {PRESETS_DIR}")
        return

    preset_files = [f for f in os.listdir(PRESETS_DIR) if f.endswith(".json")]
    check(f"preset JSON files found ({len(preset_files)})", len(preset_files) > 0,
          f"no preset files in {PRESETS_DIR}")

    if not preset_files:
        return

    for fname in sorted(preset_files):
        fpath = os.path.join(PRESETS_DIR, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                pcfg = json.load(f)
        except Exception as e:
            check(f"{fname}: parseable", False, str(e))
            continue

        check(f"{fname}: parseable", True)

        strategies = pcfg.get("strategies", {})

        # No legacy keys in strategies section
        legacy_found = [k for k in strategies if k in LEGACY_PRESET_KEYS]
        check(f"{fname}: no legacy strategy keys (draw/xg/drift/clustering/pressure)",
              len(legacy_found) == 0,
              f"legacy keys found: {legacy_found}")

        # No dead strategies
        dead_found = [k for k in strategies if k in DEAD_PRESET_STRATEGIES]
        check(f"{fname}: no dead strategies",
              len(dead_found) == 0,
              f"dead strategies found: {dead_found}")

        # No 'version' field in any strategy
        with_version = [k for k, v in strategies.items()
                        if isinstance(v, dict) and "version" in v]
        check(f"{fname}: no 'version' field in strategies",
              len(with_version) == 0,
              f"strategies with 'version' field: {with_version}")

        # If csv_reader loaded, all strategy keys must be in registry
        if CSV_READER_OK:
            registry_keys = {e[0] for e in _cr._STRATEGY_REGISTRY}
            unknown_keys = [k for k in strategies if k not in registry_keys]
            check(f"{fname}: all strategy keys are valid registry keys",
                  len(unknown_keys) == 0,
                  f"unknown keys: {unknown_keys}")


# ─────────────────────────────────────────────────────────────────────────────
# T10 — _STRATEGY_MARKET keys exist in registry
# ─────────────────────────────────────────────────────────────────────────────

def t10_strategy_market():
    section("T10 — _STRATEGY_MARKET integrity")

    if not CSV_READER_OK:
        check("SKIP (csv_reader not loaded)", False)
        return

    check("_STRATEGY_MARKET exists",
          hasattr(_cr, "_STRATEGY_MARKET"),
          "missing _STRATEGY_MARKET in csv_reader")

    if not hasattr(_cr, "_STRATEGY_MARKET"):
        return

    market_map = _cr._STRATEGY_MARKET
    registry_keys = {e[0] for e in _cr._STRATEGY_REGISTRY}

    # All strategy keys in _STRATEGY_MARKET must exist in registry
    missing = [k for k in market_map if k not in registry_keys]
    check("All _STRATEGY_MARKET keys exist in registry",
          len(missing) == 0,
          f"keys not in registry: {missing}")

    # No strategy appears in multiple market groups (values should be consistent per key)
    # Check that there are no duplicate keys (Python dict guarantees this, but verify)
    check("No duplicate keys in _STRATEGY_MARKET",
          len(market_map) == len(set(market_map.keys())))

    # All market group values are non-empty strings
    bad_values = [k for k, v in market_map.items() if not isinstance(v, str) or not v]
    check("All _STRATEGY_MARKET values are non-empty strings",
          len(bad_values) == 0,
          f"bad values for keys: {bad_values}")


# ─────────────────────────────────────────────────────────────────────────────
# T11 — Trigger naming convention: _detect_{key}_trigger
# ─────────────────────────────────────────────────────────────────────────────

def t11_trigger_naming():
    section("T11 — Trigger naming convention")

    if not CSV_READER_OK:
        check("SKIP (csv_reader not loaded)", False)
        return

    reg = _cr._STRATEGY_REGISTRY
    missing_triggers = []
    bad_signature = []

    for entry in reg:
        key = entry[0]
        expected_fn_name = f"_detect_{key}_trigger"
        fn = getattr(_cr, expected_fn_name, None)
        if fn is None:
            missing_triggers.append(f"{key} → expected {expected_fn_name}")
        else:
            # Check signature: (rows, curr_idx, cfg)
            try:
                sig = inspect.signature(fn)
                params = list(sig.parameters.keys())
                if len(params) < 3:
                    bad_signature.append(f"{expected_fn_name}: params={params} (expected >=3)")
            except (ValueError, TypeError):
                pass  # some builtins can't be inspected

    check("Each registry key has _detect_{key}_trigger function",
          len(missing_triggers) == 0,
          "\n      ".join(missing_triggers))

    check("All trigger functions have at least 3 params (rows, curr_idx, cfg)",
          len(bad_signature) == 0,
          "\n      ".join(bad_signature))

    # Registry element[2] (trigger_fn) matches the named function
    wrong_fn = []
    for entry in reg:
        key = entry[0]
        trigger_fn = entry[2]
        expected_fn = getattr(_cr, f"_detect_{key}_trigger", None)
        if expected_fn is not None and trigger_fn is not expected_fn:
            wrong_fn.append(f"{key}: registry fn != _detect_{key}_trigger")
    check("Registry trigger_fn matches _detect_{key}_trigger by identity",
          len(wrong_fn) == 0,
          "\n      ".join(wrong_fn))


# ─────────────────────────────────────────────────────────────────────────────
# T12 — SEARCH_SPACES covers all SINGLE_STRATEGIES
# ─────────────────────────────────────────────────────────────────────────────

def t12_search_spaces():
    section("T12 — bt_optimizer SEARCH_SPACES coverage")

    try:
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import bt_optimizer as _bt
    except Exception as e:
        check("bt_optimizer importable", False, str(e))
        return

    check("bt_optimizer importable", True)

    check("SINGLE_STRATEGIES exists", hasattr(_bt, "SINGLE_STRATEGIES"))
    check("SEARCH_SPACES exists", hasattr(_bt, "SEARCH_SPACES"))

    if not (hasattr(_bt, "SINGLE_STRATEGIES") and hasattr(_bt, "SEARCH_SPACES")):
        return

    ss = set(_bt.SINGLE_STRATEGIES)
    sp = set(_bt.SEARCH_SPACES.keys())

    # Every SINGLE_STRATEGY must have a SEARCH_SPACES entry
    missing_in_sp = ss - sp
    check("Every SINGLE_STRATEGY has a SEARCH_SPACES entry",
          len(missing_in_sp) == 0,
          f"in SINGLE_STRATEGIES but no SEARCH_SPACES: {sorted(missing_in_sp)}")

    # No unknown strategies in SEARCH_SPACES (orphaned entries)
    if CSV_READER_OK:
        registry_keys = {e[0] for e in _cr._STRATEGY_REGISTRY}
        unknown_in_sp = sp - registry_keys
        check("All SEARCH_SPACES keys are valid registry keys",
              len(unknown_in_sp) == 0,
              f"in SEARCH_SPACES but not registry: {sorted(unknown_in_sp)}")

    # tarde_asia included in SINGLE_STRATEGIES with empty search space (evaluated once with defaults)
    check("tarde_asia included in SINGLE_STRATEGIES",
          "tarde_asia" in ss)
    check("tarde_asia has empty search space (no tunable params)",
          _bt.SEARCH_SPACES.get("tarde_asia") == {})


# ─────────────────────────────────────────────────────────────────────────────
# T13 — Dynamic optimizer architecture (replaces _COMBO_TO_REGISTRY check)
# ─────────────────────────────────────────────────────────────────────────────

def t13_combo_to_registry():
    section("T13 — Dynamic optimizer architecture")

    if not OPTIMIZER_CLI_OK:
        check("optimizer_cli importable", False,
              OPTIMIZER_CLI_ERR if not OPTIMIZER_CLI_OK else "")
        return

    check("optimizer_cli importable", True)

    # Verify the old hardcoded mapping is gone
    cli_src = inspect.getsource(_optimizer_cli)
    check("No _COMBO_TO_REGISTRY (hardcoded mapping removed)",
          "_COMBO_TO_REGISTRY" not in cli_src)

    # Verify dynamic architecture is in place
    check("_build_preset_config accepts 'disabled' parameter",
          "disabled" in inspect.signature(_optimizer_cli._build_preset_config).parameters)

    check("_run_phase1 exists and is dynamic",
          hasattr(_optimizer_cli, '_run_phase1'))

    # Verify no hardcoded strategy filter functions imported
    for fn_name in ("_filter_draw", "_filter_xg", "_filter_drift",
                    "_filter_clustering", "_filter_pressure",
                    "_filter_tardesia", "_filter_momentum"):
        check(f"No {fn_name} in optimizer_cli",
              fn_name not in cli_src)


# ─────────────────────────────────────────────────────────────────────────────
# T14 — Signal min_odds uses oddsMin from config, not hardcoded 1.21
# ─────────────────────────────────────────────────────────────────────────────

def t14_signal_min_odds():
    section("T14 — Signal min_odds not hardcoded")

    if not CSV_READER_OK:
        check("SKIP T14 (csv_reader not loaded)", False)
        return

    src_path = os.path.join(ROOT, "betfair_scraper", "dashboard", "backend",
                            "utils", "csv_reader.py")
    src = open(src_path, encoding="utf-8").read()

    # 1. The hardcoded 1.21 must not appear as min_odds value in signal construction
    hardcoded = re.search(r'"min_odds"\s*:\s*1\.21', src)
    check("No hardcoded min_odds: 1.21 in signal construction",
          hardcoded is None,
          f"Found hardcoded 1.21 at: {hardcoded.group(0)}" if hardcoded else "")

    # 2. _sd_signal must accept a cfg_min_odds parameter
    has_param = "cfg_min_odds" in src
    check("_sd_signal accepts cfg_min_odds parameter", has_param)

    # 3. The registry loop must pass cfg_min_odds from _cfg_entry
    has_pass = "_cfg_entry.get(\"odds_min\")" in src or "_cfg_entry.get('odds_min')" in src
    check("Registry loop passes odds_min from _cfg_entry to _sd_signal", has_pass)

    # 4. odds_favorable is computed dynamically (not always True)
    has_dynamic_favorable = re.search(
        r'"odds_favorable"\s*:\s*\(odds\s*>=\s*cfg_min_odds\)', src
    )
    check("odds_favorable computed from cfg_min_odds (not hardcoded True)",
          has_dynamic_favorable is not None)

    # 5. Config sanity: strategies with oddsMin=0 should NOT force favorable=False
    #    (0 means no filter — any odds acceptable)
    cfg_path = os.path.join(ROOT, "betfair_scraper", "cartera_config.json")
    try:
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        strategies = cfg.get("strategies", {})
        # Verify that at least some enabled strategies have a meaningful odds_min (>0)
        meaningful_odds = [
            k for k, v in strategies.items()
            if isinstance(v, dict) and v.get("enabled") and (v.get("odds_min") or 0) > 0
        ]
        check(f"At least some enabled strategies have meaningful odds_min>0 ({len(meaningful_odds)} found)",
              len(meaningful_odds) >= 3,
              f"only found: {meaningful_odds}")
    except Exception as e:
        check("cartera_config.json readable for oddsMin check", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# T15 — Settlement: placed_bets won/lost matches final CSV score
# ─────────────────────────────────────────────────────────────────────────────

def t15_settlement():
    section("T15 — Settlement correctness")

    import glob as _glob
    from urllib.parse import quote

    placed = os.path.join(ROOT, "betfair_scraper", "placed_bets.csv")
    data_dir = os.path.join(ROOT, "betfair_scraper", "data")

    if not os.path.exists(placed):
        check("placed_bets.csv exists", False, "file not found")
        return

    def _resolve(mid):
        p = os.path.join(data_dir, f"partido_{mid}.csv")
        if os.path.exists(p):
            return p
        enc = quote(mid, safe="-")
        p2 = os.path.join(data_dir, f"partido_{enc}.csv")
        if os.path.exists(p2):
            return p2
        prefix = re.sub(r"-?\d+$", "", mid)
        if prefix:
            for f in sorted(_glob.glob(os.path.join(data_dir, f"partido_{prefix}*.csv"))):
                if f.endswith(".csv"):
                    return f
            enc_prefix = re.sub(r"-?\d+$", "", enc)
            if enc_prefix != prefix:
                for f in sorted(_glob.glob(os.path.join(data_dir, f"partido_{enc_prefix}*.csv"))):
                    if f.endswith(".csv"):
                        return f
        return None

    def _final_score(mid):
        path = _resolve(mid)
        if not path or not os.path.exists(path):
            return None, None
        import csv as _csv
        with open(path, "r", encoding="utf-8") as f:
            rows = list(_csv.DictReader(f))
        for row in reversed(rows):
            est = row.get("estado_partido", "").strip().lower()
            if est not in ("pre_partido", "prematch"):
                try:
                    return int(float(row.get("goles_local", ""))), int(float(row.get("goles_visitante", "")))
                except (ValueError, TypeError):
                    return None, None
        return None, None

    def _check_would_win(rec, gl, gv):
        rec = rec.upper()
        is_lay = rec.startswith("LAY")
        if "DRAW" in rec:
            r = gl == gv
            return (not r) if is_lay else r
        m = re.search(r"CS\s+(\d+)-(\d+)", rec)
        if m:
            r = gl == int(m.group(1)) and gv == int(m.group(2))
            return (not r) if is_lay else r
        m = re.search(r"OVER\s+(\d+\.?\d*)", rec)
        if m:
            r = (gl + gv) > float(m.group(1))
            return (not r) if is_lay else r
        m = re.search(r"UNDER\s+(\d+\.?\d*)", rec)
        if m:
            r = (gl + gv) < float(m.group(1))
            return (not r) if is_lay else r
        if "HOME" in rec:
            r = gl > gv
            return (not r) if is_lay else r
        if "AWAY" in rec:
            r = gv > gl
            return (not r) if is_lay else r
        return None

    import csv as _csv
    with open(placed, "r", encoding="utf-8") as f:
        bets = list(_csv.DictReader(f))

    wrong = []
    verified = 0
    for b in bets:
        status = b.get("status", "")
        if status not in ("won", "lost"):
            continue
        gl, gv = _final_score(b["match_id"])
        if gl is None:
            continue
        expected = _check_would_win(b.get("recommendation", ""), gl, gv)
        if expected is None:
            continue
        verified += 1
        expected_status = "won" if expected else "lost"
        if status != expected_status:
            wrong.append(f"ID={b['id']} {b['match_name'][:30]} | {b['recommendation'][:25]} | final={gl}-{gv} | is={status} should={expected_status}")

    check(f"All settled bets match final score ({verified} verified)",
          len(wrong) == 0,
          "\n".join(wrong) if wrong else "")


# ─────────────────────────────────────────────────────────────────────────────
# T16 — Match finalization: CSVs for bet matches have estado=finalizado
# ─────────────────────────────────────────────────────────────────────────────

def t16_match_finalization():
    section("T16 — Match finalization")

    import glob as _glob
    from urllib.parse import quote

    placed = os.path.join(ROOT, "betfair_scraper", "placed_bets.csv")
    data_dir = os.path.join(ROOT, "betfair_scraper", "data")

    if not os.path.exists(placed):
        check("placed_bets.csv exists", False, "file not found")
        return

    def _resolve(mid):
        p = os.path.join(data_dir, f"partido_{mid}.csv")
        if os.path.exists(p):
            return p
        enc = quote(mid, safe="-")
        p2 = os.path.join(data_dir, f"partido_{enc}.csv")
        if os.path.exists(p2):
            return p2
        prefix = re.sub(r"-?\d+$", "", mid)
        if prefix:
            for f in sorted(_glob.glob(os.path.join(data_dir, f"partido_{prefix}*.csv"))):
                if f.endswith(".csv"):
                    return f
            enc_prefix = re.sub(r"-?\d+$", "", enc)
            if enc_prefix != prefix:
                for f in sorted(_glob.glob(os.path.join(data_dir, f"partido_{enc_prefix}*.csv"))):
                    if f.endswith(".csv"):
                        return f
        return None

    import csv as _csv
    with open(placed, "r", encoding="utf-8") as f:
        bets = list(_csv.DictReader(f))

    # Only check settled bets (won/lost) — pending ones may still be in play
    settled_match_ids = set()
    for b in bets:
        if b.get("status") in ("won", "lost", "cashout"):
            settled_match_ids.add(b["match_id"])

    finished_states = {"finalizado", "finished", "ft", "full_time", "ended"}
    missing_final = []

    for mid in sorted(settled_match_ids):
        path = _resolve(mid)
        if not path or not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            rows = list(_csv.DictReader(f))
        # Check last non-pre_partido row
        for row in reversed(rows):
            est = row.get("estado_partido", "").strip().lower()
            if est not in ("pre_partido", "prematch"):
                if est not in finished_states:
                    gl = row.get("goles_local", "?")
                    gv = row.get("goles_visitante", "?")
                    minuto = row.get("minuto", "?")
                    missing_final.append(f"{mid[:45]} | {gl}-{gv} min={minuto} | estado={est}")
                break

    check(f"All settled-bet match CSVs have estado=finalizado ({len(settled_match_ids)} matches)",
          len(missing_final) == 0,
          "\n".join(missing_final) if missing_final else "")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global VERBOSE
    parser = argparse.ArgumentParser(description="System integrity tests")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    VERBOSE = args.verbose

    print("=" * 65)
    print("  SYSTEM INTEGRITY — Betfair Dashboard")
    print("=" * 65)

    t1_registry()
    t2_config_structure()
    t3_config_registry_sync()
    t4_bt_path()
    t5_live_path()
    t6_optimizer()
    t7_frontend()
    t8_no_legacy_code()
    t9_preset_files()
    t10_strategy_market()
    t11_trigger_naming()
    t12_search_spaces()
    t13_combo_to_registry()
    t14_signal_min_odds()
    t15_settlement()
    t16_match_finalization()

    total = PASS + FAIL
    print(f"\n{'='*65}")
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
    print("=" * 65)

    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
