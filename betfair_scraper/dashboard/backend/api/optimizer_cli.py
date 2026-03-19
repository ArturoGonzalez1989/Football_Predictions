"""
Optimizador de presets — CLI independiente.

Uso:
    python betfair_scraper/dashboard/backend/api/optimizer_cli.py max_roi
    python betfair_scraper/dashboard/backend/api/optimizer_cli.py max_roi --bankroll 2000
    python betfair_scraper/dashboard/backend/api/optimizer_cli.py max_roi --workers 5
    python betfair_scraper/dashboard/backend/api/optimizer_cli.py max_roi --workers 5 --out resultado.json

Criterios disponibles: max_roi | max_pl | max_wr | min_dd

Corre el mismo algoritmo que el endpoint POST /api/analytics/strategies/cartera/optimize
pero de forma totalmente independiente: sin FastAPI, sin Chrome.

Con --workers > 1 usa ProcessPoolExecutor real (multicore). Esto es seguro aquí porque
Chrome no está involucrado y no hay riesgo de OOM en el browser.
El split se hace por pares (draw × xg) = 4 combinaciones, lo que permite hasta 4 workers.
"""
import argparse
import csv as _csv
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path


def _worker_set_below_normal_priority():
    """
    Initializer for ProcessPoolExecutor workers.
    On Windows, spawned processes do NOT inherit the parent's priority class.
    This function explicitly sets BELOW_NORMAL_PRIORITY_CLASS in each worker
    so Chrome's renderer thread is never starved of CPU time.
    """
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(
            ctypes.windll.kernel32.GetCurrentProcess(),
            0x00004000,  # BELOW_NORMAL_PRIORITY_CLASS
        )

# ── Asegurar que el backend es importable ─────────────────────────────────────
_backend_dir = Path(__file__).resolve().parent.parent  # .../dashboard/backend
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# ── Imports del proyecto ──────────────────────────────────────────────────────
from utils import csv_reader  # noqa: E402
from api.optimize import (    # noqa: E402
    _phase1_worker, _phase2_worker,
    _filter_draw, _filter_xg, _filter_drift, _filter_clustering,
    _filter_pressure, _filter_tardesia, _filter_momentum,
    _meets_min_odds, _apply_realistic_adj, _filter_by_risk,
    _simulate_cartera_py, _score_of, _get_bet_odds, _fv, _wilson_ci,
    ALL_DRAW_XG_PAIRS, DRIFT_OPTS, CLUSTERING_OPTS,
    PRESSURE_OPTS, TARDESIA_OPTS, MOMENTUM_OPTS,
    BR_OPTS, RISK_OPTS,
    _PHASE1_TOTAL, _PHASE2_TOTAL,
)

# ── Paths ─────────────────────────────────────────────────────────────────────

_SCRAPER_DIR  = _backend_dir.parent.parent               # betfair_scraper/
_PRESETS_DIR  = _SCRAPER_DIR / "data" / "presets"
_CARTERA_CFG  = _SCRAPER_DIR / "cartera_config.json"

# Columns exported per bet for external analysis.
_EXPORT_COLS = [
    # Identifiers
    "timestamp_utc", "match_id",
    # Strategy & trigger
    "strategy", "minuto", "bet_type_dir",
    # Result
    "won", "pl", "effective_odds",
    # Risk classification
    "risk_level",
    # xG / possession metrics
    "xg_total", "xg_excess", "xg_ratio", "poss_diff", "shots_total",
    # SoT metrics
    "sot_team", "sot_total", "sot_max", "sot_dominant", "sot_rival",
    # Drift metrics
    "drift_pct", "goal_diff",
    # Market odds
    "back_draw", "back_odds", "over_odds",
    "backed_team", "team",
    # Triggers / flags
    "total_goals_trigger",
]


def _export_preset_csv(bets_final: list, criterion: str) -> Path:
    """Write the final filtered bets for a preset to data/presets/preset_{criterion}.csv."""
    _PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _PRESETS_DIR / f"preset_{criterion}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=_EXPORT_COLS, extrasaction="ignore")
        writer.writeheader()
        for b in bets_final:
            row = {col: b.get(col, "") for col in _EXPORT_COLS}
            row["effective_odds"] = _get_bet_odds(b)
            writer.writerow(row)
    _log(f"CSV preset exportado: {out_path} ({len(bets_final)} bets)")
    return out_path


# ── Preset config generation ──────────────────────────────────────────────────

# Phase 3 momentum minute range options (mirrors cartera.ts findBestCombo Phase 3)
_MOMENTUM_RANGES = [(0, 90), (5, 85), (10, 80), (15, 75), (20, 70)]

# Phase 4 CO percentage candidates (same as runCOOptimizer in cartera.ts)
_CO_PCT_CANDIDATES = [0, 5, 10, 15, 20, 25, 30, 40, 50]


def _collect_bets_with_momentum_range(bets: list, combo: dict, m_min: int, m_max: int) -> list:
    """Collect combo bets and filter momentum bets by the given minute range."""
    cb = _collect_bets(bets, combo)
    if combo.get("momentumXG") == "off":
        return cb
    result = []
    for b in cb:
        if b.get("strategy", "").startswith("momentum_xg"):
            mn = _fv(b, "minuto")
            if mn is not None and (mn < m_min or mn >= m_max):
                continue
        result.append(b)
    return result


def _find_best_momentum_range(bets: list, combo: dict, adj: dict, risk_filter: str,
                               bankroll_init: float, criterion: str) -> tuple:
    """Phase 3: test 5 momentum minute ranges, return best (min, max) tuple."""
    if combo.get("momentumXG") == "off":
        return (0, 90)
    best_range = (0, 90)
    best_score = -math.inf
    for m_min, m_max in _MOMENTUM_RANGES:
        cb = _collect_bets_with_momentum_range(bets, combo, m_min, m_max)
        after_adj = _apply_realistic_adj(cb, adj)
        after_risk = _filter_by_risk(after_adj, risk_filter)
        if len(after_risk) < 15:
            continue
        sim = _simulate_cartera_py(after_risk, bankroll_init, combo.get("br", "fixed"))
        score = _score_of(sim, criterion)
        if score > best_score:
            best_score = score
            best_range = (m_min, m_max)
    return best_range


def _find_best_co_pct(
    cartera_data: dict, combo: dict, adj: dict, risk_filter: str,
    m_min: int, m_max: int, bankroll_init: float, criterion: str,
) -> int:
    """Phase 4: find the CO percentage that maximises the criterion score.

    Tests cashout_lay_pct in _CO_PCT_CANDIDATES using simulate_cashout_cartera +
    the same filter pipeline the frontend uses with 'Optimizar CO'.
    Returns 0 if no CO pct improves over not using CO at all.
    """
    best_pct = 0
    best_score = -math.inf
    _log(f"Phase 4 — probando CO pct {_CO_PCT_CANDIDATES}…")
    t0 = time.time()

    for pct in _CO_PCT_CANDIDATES:
        if pct == 0:
            co_bets = cartera_data.get("bets", [])
        else:
            co_data = csv_reader.simulate_cashout_cartera(cartera_data, cashout_lay_pct=float(pct))
            co_bets = co_data.get("bets", [])

        cb = _collect_bets_with_momentum_range(co_bets, combo, m_min, m_max)
        after_adj = _apply_realistic_adj(cb, adj)
        after_risk = _filter_by_risk(after_adj, risk_filter)
        if len(after_risk) < 15:
            continue

        sim = _simulate_cartera_py(after_risk, bankroll_init, combo.get("br", "fixed"))
        score = _score_of(sim, criterion)
        _log(f"  CO pct={pct:2d}%: score={score:.4f}  flat_pl={sim['flat_pl']:.2f}")

        if score > best_score:
            best_score = score
            best_pct = pct

    _log(f"Phase 4 completada en {time.time()-t0:.1f}s — best_co_pct={best_pct}%")
    return best_pct


def _build_preset_config(combo: dict, adj: dict, risk_filter: str,
                          criterion: str, m_min: int, m_max: int,
                          co_pct: int, bankroll_init: float,
                          stats: dict = None,
                          strategy_params: dict = None) -> dict:
    """
    Build a full cartera_config.json-compatible dict from optimizer result.

    The preset only decides on/off per strategy. Strategy params (xgMax, possMax, etc.)
    come from the current cartera_config.json (already set by bt_optimizer grid search).
    m_min/m_max come from Phase 3, co_pct from Phase 4.
    """
    adj = adj or DEFAULT_ADJ
    br_mode = combo.get("br", "fixed")

    # Read current cartera_config.json to preserve all strategy params
    base_cfg = {}
    if _CARTERA_CFG.exists():
        try:
            base_cfg = json.loads(_CARTERA_CFG.read_text(encoding="utf-8"))
        except Exception:
            pass

    flat_stake       = base_cfg.get("flat_stake", 1)
    initial_bankroll = base_cfg.get("initial_bankroll", 100)
    min_duration     = base_cfg.get("min_duration", {
        "back_draw_00": 2, "xg_underperformance": 3, "odds_drift": 2,
        "goal_clustering": 4, "pressure_cooker": 4,
    })
    cashout_minute = base_cfg.get("adjustments", {}).get("cashout_minute", None)

    # Map combo keys → registry strategy keys
    _COMBO_TO_REGISTRY = {
        "draw": "back_draw_00",
        "xg": "xg_underperformance",
        "drift": "odds_drift",
        "clustering": "goal_clustering",
        "pressure": "pressure_cooker",
        "tardeAsia": "tarde_asia",
        "momentumXG": "momentum_xg",
    }

    # Start from current strategies in cartera_config.json (preserves all params)
    _base_strategies = base_cfg.get("strategies", {}) or {}
    strategies = {k: dict(v) if isinstance(v, dict) else v
                  for k, v in _base_strategies.items()}

    # Apply on/off from combo.
    # Respect quality gates: if staging disabled a strategy (failed phase1/2), never re-enable it.
    for combo_key, reg_key in _COMBO_TO_REGISTRY.items():
        enabled = combo.get(combo_key, "off") != "off"
        base_entry = _base_strategies.get(reg_key, {})
        if isinstance(base_entry, dict) and not base_entry.get("enabled", True):
            enabled = False  # failed quality gates — keep disabled regardless of combo
        if reg_key in strategies and isinstance(strategies[reg_key], dict):
            strategies[reg_key]["enabled"] = enabled
        else:
            strategies[reg_key] = {"enabled": enabled}

    # Apply momentum minute range from Phase 3
    if "momentum_xg" in strategies and isinstance(strategies["momentum_xg"], dict):
        strategies["momentum_xg"]["minuteMin"] = m_min
        strategies["momentum_xg"]["minuteMax"] = m_max

    # Apply strategy_params overrides if provided
    _sp = strategy_params or {}
    for k, v in _sp.items():
        if k in csv_reader._STRATEGY_REGISTRY_KEYS:
            strategies.setdefault(k, {})
            strategies[k] = {**strategies[k], "enabled": True, **v}

    return {
        "strategies": strategies,
        "bankroll_mode":    br_mode,
        "flat_stake":       flat_stake,
        "initial_bankroll": initial_bankroll,
        "active_preset":    criterion,
        "risk_filter":      risk_filter,
        "min_duration":     min_duration,
        "adjustments": {
            "enabled":            True,
            "dedup":              adj.get("dedup", False),
            "max_odds":           adj.get("maxOdds", 10),
            "min_odds":           adj.get("minOdds"),
            "drift_min_minute":   adj.get("driftMinMinute") or 0,
            "slippage_pct":       adj.get("slippagePct", 0),
            "conflict_filter":    adj.get("conflictFilter", False),
            "allow_contrarias":   adj.get("allowContrarias", True),
            "stability":          adj.get("minStability", 1),
            "global_minute_min":  adj.get("globalMinuteMin"),
            "global_minute_max":  adj.get("globalMinuteMax"),
            "cashout_minute":     cashout_minute,
            "cashout_pct":        co_pct,
        },
        "_optimizer_stats": stats or {},
    }


# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_ADJ = {
    "dedup": False, "minOdds": None, "maxOdds": None, "slippagePct": 0,
    "conflictFilter": False, "allowContrarias": True, "minStability": 1,
    "driftMinMinute": None, "globalMinuteMin": None, "globalMinuteMax": None,
}
DEFAULT_COMBO = {
    "draw": "on", "xg": "on", "drift": "on", "clustering": "on",
    "pressure": "on", "tardeAsia": "off", "momentumXG": "off",
    "br": "fixed",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _run_phase1(bets, criterion, bankroll_init, n_workers):
    # Split by (draw, xg) pairs: 5×3 = 15 combinations → up to 15 workers.
    # Distributes the heaviest draw version (v1) across 3 workers instead of 1.
    n_workers = min(n_workers, len(ALL_DRAW_XG_PAIRS))  # cap at 4
    common_args = (
        DRIFT_OPTS, CLUSTERING_OPTS, PRESSURE_OPTS,
        TARDESIA_OPTS, MOMENTUM_OPTS, BR_OPTS, RISK_OPTS,
        criterion, bankroll_init,
    )
    best_combo = None
    best_risk = "all"
    best_score = -math.inf
    t0 = time.time()

    if n_workers > 1:
        pair_chunks = [ALL_DRAW_XG_PAIRS[i::n_workers] for i in range(n_workers)]
        # Remove empty chunks (when n_workers > len(ALL_DRAW_XG_PAIRS))
        pair_chunks = [c for c in pair_chunks if c]
        actual_workers = len(pair_chunks)
        _log(f"Phase 1 — {_PHASE1_TOTAL:,} combos en {actual_workers} workers "
             f"(split por {len(ALL_DRAW_XG_PAIRS)} pares draw×xg)…")
        with ProcessPoolExecutor(max_workers=actual_workers) as ex:
            futures = {
                ex.submit(_phase1_worker, (bets, chunk) + common_args): i
                for i, chunk in enumerate(pair_chunks)
            }
            done = 0
            for fut in as_completed(futures):
                combo, risk, score = fut.result(timeout=600)
                done += 1
                _log(f"  Worker {futures[fut]+1}/{actual_workers} terminado — "
                     f"score={score:.4f}  ({done}/{actual_workers} listos)")
                if score > best_score:
                    best_score = score
                    best_combo = combo
                    best_risk = risk
    else:
        _log(f"Phase 1 — {_PHASE1_TOTAL:,} combos (secuencial)…")
        best_combo, best_risk, best_score = _phase1_worker((bets, ALL_DRAW_XG_PAIRS) + common_args)

    _log(f"Phase 1 completada en {time.time()-t0:.1f}s — best_score={best_score:.4f}")
    return best_combo, best_risk, best_score


def _run_phase2(bets, best_combo, best_risk, criterion, bankroll_init, label="Phase 2", adj_override=None):
    if best_combo is None:
        return adj_override if adj_override is not None else DEFAULT_ADJ

    combo_bets = _collect_bets(bets, best_combo)

    # When caller provides explicit adj constraints, skip the Phase 2 search entirely
    if adj_override is not None:
        _log(f"{label} — adj_override activo, omitiendo búsqueda ({len(combo_bets)} bets)")
        return adj_override

    _log(f"{label} — {_PHASE2_TOTAL} adj combos ({len(combo_bets)} bets base)…")
    t0 = time.time()
    found_adj, _ = _phase2_worker((combo_bets, bankroll_init, best_combo["br"], best_risk, criterion))
    _log(f"{label} completada en {time.time()-t0:.1f}s")
    return found_adj if found_adj is not None else DEFAULT_ADJ


def _collect_bets(bets, combo):
    """Collect and sort all bets for a given combo (shared by Phase 2 and 2.5)."""
    cb = (
        _filter_draw(bets, combo["draw"]) +
        _filter_xg(bets, combo["xg"]) +
        _filter_drift(bets, combo["drift"]) +
        _filter_clustering(bets, combo["clustering"]) +
        _filter_pressure(bets, combo["pressure"]) +
        _filter_tardesia(bets, combo["tardeAsia"]) +
        _filter_momentum(bets, combo["momentumXG"])
    )
    cb = [b for b in cb if _meets_min_odds(b)]
    cb.sort(key=lambda b: b.get("timestamp_utc") or "")
    return cb


def _eval_with_adj(bets, combo, adj, risk, bankroll_init, criterion):
    """Evaluate a combo with a fixed adj — used by Phase 2.5."""
    after = _filter_by_risk(_apply_realistic_adj(_collect_bets(bets, combo), adj), risk)
    if len(after) < 15:
        return -math.inf
    sim = _simulate_cartera_py(after, bankroll_init, combo["br"])
    return _score_of(sim, criterion)


def _auto_disable_empty_strategies(bets, combo):
    """
    Auto-disable strategies that produce 0 bets in the dataset.
    Called between Phase 1 and Phase 2.5 so the optimizer doesn't keep
    strategies that have no data (e.g. drift/pressure with 0 triggers).
    """
    _KEY_FILTER = {
        "draw": _filter_draw, "xg": _filter_xg, "drift": _filter_drift,
        "clustering": _filter_clustering, "pressure": _filter_pressure,
        "tardeAsia": _filter_tardesia, "momentumXG": _filter_momentum,
    }
    disabled = []
    combo = dict(combo)
    for key, fn in _KEY_FILTER.items():
        ver = combo.get(key, "off")
        if ver == "off":
            continue
        n = len(fn(bets, ver))
        if n == 0:
            combo[key] = "off"
            disabled.append(key)
    if disabled:
        _log(f"Auto-disable (0 bets): {', '.join(disabled)}")
    return combo


def _run_phase25(bets, best_combo, best_adj, best_risk, criterion, bankroll_init):
    """
    Steepest-descent strategy disabling: given Phase 2's adj, each pass tries
    disabling every active strategy and applies the single best disabling found.
    Repeats until no improvement (max 5 passes).

    Fixes the Phase-1-vs-adj interaction gap where Phase 1 (no adj) includes
    strategies whose bets are later blocked by allowContrarias=False in Phase 2.

    Returns (refined_combo, final_adj_score).
    """
    STRATEGY_KEYS = [
        "draw", "xg", "drift", "clustering", "pressure", "tardeAsia",
        "momentumXG",
    ]

    current_score = _eval_with_adj(bets, best_combo, best_adj, best_risk, bankroll_init, criterion)
    _log(f"Phase 2.5 — score inicial con adj: {current_score:.4f}")

    improved = True
    passes = 0
    while improved and passes < 5:
        improved = False
        passes += 1
        best_key, best_trial_score = None, current_score
        for key in STRATEGY_KEYS:
            if best_combo.get(key) == "off":
                continue
            trial = dict(best_combo)
            trial[key] = "off"
            score = _eval_with_adj(bets, trial, best_adj, best_risk, bankroll_init, criterion)
            if score > best_trial_score:
                best_trial_score = score
                best_key = key
        if best_key is not None:
            current_score = best_trial_score
            best_combo = dict(best_combo)
            best_combo[best_key] = "off"
            improved = True
            _log(f"  Phase 2.5 (pase {passes}): desactivar '{best_key}' mejora score -> {best_trial_score:.4f}")

    _log(f"Phase 2.5 completada — score final: {current_score:.4f}")
    return best_combo, current_score


# ── Entry point ───────────────────────────────────────────────────────────────

def run(criterion: str, bankroll_init: float = 1000.0, n_workers: int = 1, out: str = None,
        adj_override: dict = None, strategy_params: dict = None) -> dict:
    """
    Punto de entrada programático (para lanzar desde la app o desde otro script).
    adj_override: si se especifica, se usa directamente como adj (omite búsqueda Phase 2).
    strategy_params: dict of optimized params from notebook cells for on/off strategies.
        Passed through to _build_preset_config() to override hardcoded defaults.
    Devuelve el dict resultado: { combo, risk_filter, best_score, adj }
    """
    _log(f"Iniciando optimizador — criterio={criterion} bankroll={bankroll_init} workers={n_workers}")
    if adj_override is not None:
        _log(f"adj_override activo: {adj_override}")

    _log("Cargando datos desde CSV…")
    t0 = time.time()
    data = csv_reader.analyze_cartera()
    bets = data.get("bets", [])
    _log(f"Datos cargados en {time.time()-t0:.1f}s — {len(bets)} bets")

    if not bets:
        raise RuntimeError("No se encontraron bets. Verifica que existan CSVs en betfair_scraper/data/")

    best_combo, best_risk, best_score = _run_phase1(bets, criterion, bankroll_init, n_workers)
    if best_combo:
        best_combo = _auto_disable_empty_strategies(bets, best_combo)
    best_adj = _run_phase2(bets, best_combo, best_risk, criterion, bankroll_init, adj_override=adj_override)
    combo_before_25 = best_combo or DEFAULT_COMBO
    best_combo, final_score = _run_phase25(bets, combo_before_25, best_adj, best_risk, criterion, bankroll_init)

    # If Phase 2.5 changed the combo, the adj was optimised for the old combo —
    # re-run Phase 2 with the refined combo so adj reflects the actual strategy set.
    if best_combo != combo_before_25:
        _log("Phase 2.5 cambió el combo — re-optimizando adj (Phase 2b)…")
        best_adj = _run_phase2(bets, best_combo, best_risk, criterion, bankroll_init, label="Phase 2b", adj_override=adj_override)
        best_combo, final_score = _run_phase25(bets, best_combo, best_adj, best_risk, criterion, bankroll_init)

    result = {
        "combo": best_combo,
        "risk_filter": best_risk,
        "best_score": final_score if final_score > -math.inf else 0.0,
        "adj": best_adj,
    }

    # ── Post-optimization exports ──────────────────────────────────────────────
    _final_combo = best_combo or DEFAULT_COMBO
    _final_adj   = best_adj   or DEFAULT_ADJ
    try:
        # Phase 3: best momentum minute range
        m_min, m_max = _find_best_momentum_range(
            bets, _final_combo, _final_adj, best_risk, bankroll_init, criterion)
        _log(f"Phase 3 completada — best_momentum_range=({m_min}, {m_max})")

        # Phase 4: best CO percentage (replaces heuristic)
        best_co_pct = _find_best_co_pct(
            data, _final_combo, _final_adj, best_risk, m_min, m_max, bankroll_init, criterion)

        # CSV uses momentum-filtered bets for accurate representation
        combo_bets  = _collect_bets_with_momentum_range(bets, _final_combo, m_min, m_max)
        bets_after  = _apply_realistic_adj(combo_bets, _final_adj)
        bets_final  = _filter_by_risk(bets_after, best_risk)
        # Stats with confidence interval
        n_bets = len(bets_final)
        wins = sum(1 for b in bets_final if b.get("won") in (True, 1, "1", "True", "true"))
        sim_final = _simulate_cartera_py(bets_final, bankroll_init, _final_combo.get("br", "fixed"))
        ci_low, ci_high = _wilson_ci(wins, n_bets)
        result["n_bets"]     = n_bets
        result["wins"]       = wins
        result["win_pct"]    = round(wins / n_bets * 100, 1) if n_bets > 0 else 0.0
        result["flat_roi"]   = sim_final["flat_roi"]
        result["flat_pl"]    = sim_final["flat_pl"]
        result["ci_low"]     = ci_low
        result["ci_high"]    = ci_high
        _log(f"Stats finales: N={n_bets}  WR={result['win_pct']}%  IC95=[{ci_low}%–{ci_high}%]  ROI={result['flat_roi']}%  PL={result['flat_pl']:.2f}")
        # 1) Detailed CSV for external analysis
        csv_path = _export_preset_csv(bets_final, criterion)
        result["csv_path"] = str(csv_path)
        # 2) Full cartera_config.json-compatible config
        _stats = {"n": n_bets, "wr": result["win_pct"], "ci_low": ci_low, "ci_high": ci_high, "roi": result["flat_roi"]}
        preset_cfg  = _build_preset_config(_final_combo, _final_adj, best_risk,
                                            criterion, m_min, m_max, best_co_pct, bankroll_init, _stats,
                                            strategy_params=strategy_params)
        cfg_path = _PRESETS_DIR / f"preset_{criterion}_config.json"
        cfg_path.write_text(json.dumps(preset_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        result["config_path"] = str(cfg_path)
        _log(f"Preset config guardado: {cfg_path}")
    except Exception as exc:
        _log(f"WARN: No se pudieron exportar artefactos del preset: {exc}")

    if out:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        _log(f"Resultado guardado en: {out_path}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Optimizador de presets Betfair (CLI, sin Chrome)"
    )
    parser.add_argument("criterion",
                        choices=["max_roi", "max_pl", "max_wr", "min_dd"],
                        help="Criterio de optimización")
    parser.add_argument("--bankroll", type=float, default=1000.0,
                        help="Bankroll inicial (default: 1000)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Workers paralelos para Phase 1. En i9/64GB usar 5 o más. (default: 1)")
    parser.add_argument("--out", type=str, default=None,
                        help="Guardar resultado JSON en este fichero (opcional)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  criterio={args.criterion}  bankroll={args.bankroll}  workers={args.workers}")
    print("=" * 60)

    result = run(args.criterion, args.bankroll, args.workers, args.out)

    print()
    print("RESULTADO:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("=" * 60)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()  # necesario en Windows con spawn
    main()
