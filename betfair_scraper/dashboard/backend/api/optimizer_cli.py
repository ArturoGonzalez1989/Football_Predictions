"""
Optimizador de presets — CLI independiente.

Uso:
    python betfair_scraper/dashboard/backend/api/optimizer_cli.py max_roi
    python betfair_scraper/dashboard/backend/api/optimizer_cli.py max_roi --bankroll 2000
    python betfair_scraper/dashboard/backend/api/optimizer_cli.py max_roi --workers 5
    python betfair_scraper/dashboard/backend/api/optimizer_cli.py max_roi --workers 5 --out resultado.json

Criterios disponibles: max_roi | max_pl | max_wr | min_dd

Dynamic portfolio optimizer: uses steepest descent over ALL strategies
present in the bets pool (no hardcoded strategy lists). Bankroll mode
is only tested for min_dd criterion (irrelevant for the other three).
"""
import argparse
import csv as _csv
import json
import math
import sys
import time
from pathlib import Path


# ── Asegurar que el backend es importable ─────────────────────────────────────
_backend_dir = Path(__file__).resolve().parent.parent  # .../dashboard/backend
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# ── Imports del proyecto ──────────────────────────────────────────────────────
from utils import csv_reader  # noqa: E402
from api.optimize import (    # noqa: E402
    _phase2_worker,
    _collect_bets_dynamic, _eval_dynamic, _steepest_descent,
    _apply_realistic_adj, _filter_by_risk,
    _simulate_cartera_py, _score_of, _get_bet_odds, _fv, _wilson_ci,
    BR_OPTS, RISK_OPTS,
    _PHASE2_TOTAL,
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


def _collect_bets_with_momentum_range(bets: list, disabled: set, m_min: int, m_max: int) -> list:
    """Collect bets excluding disabled, and filter momentum bets by minute range."""
    cb = _collect_bets_dynamic(bets, disabled)
    if "momentum_xg" in disabled:
        return cb
    result = []
    for b in cb:
        if b.get("strategy", "").startswith("momentum_xg"):
            mn = _fv(b, "minuto")
            if mn is not None and (mn < m_min or mn >= m_max):
                continue
        result.append(b)
    return result


def _find_best_momentum_range(bets: list, disabled: set, adj: dict, risk_filter: str,
                               bankroll_init: float, br: str, criterion: str) -> tuple:
    """Phase 3: test 5 momentum minute ranges, return best (min, max) tuple."""
    if "momentum_xg" in disabled:
        return (0, 90)
    # Check if there are any momentum_xg bets
    has_momentum = any(b.get("strategy") == "momentum_xg" for b in bets if b.get("strategy") not in disabled)
    if not has_momentum:
        return (0, 90)
    best_range = (0, 90)
    best_score = -math.inf
    for m_min, m_max in _MOMENTUM_RANGES:
        cb = _collect_bets_with_momentum_range(bets, disabled, m_min, m_max)
        after_adj = _apply_realistic_adj(cb, adj)
        after_risk = _filter_by_risk(after_adj, risk_filter)
        if len(after_risk) < 15:
            continue
        sim = _simulate_cartera_py(after_risk, bankroll_init, br)
        score = _score_of(sim, criterion)
        if score > best_score:
            best_score = score
            best_range = (m_min, m_max)
    return best_range


def _find_best_co_pct(
    cartera_data: dict, disabled: set, adj: dict, risk_filter: str,
    m_min: int, m_max: int, bankroll_init: float, br: str, criterion: str,
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

        cb = _collect_bets_with_momentum_range(co_bets, disabled, m_min, m_max)
        after_adj = _apply_realistic_adj(cb, adj)
        after_risk = _filter_by_risk(after_adj, risk_filter)
        if len(after_risk) < 15:
            continue

        sim = _simulate_cartera_py(after_risk, bankroll_init, br)
        score = _score_of(sim, criterion)
        _log(f"  CO pct={pct:2d}%: score={score:.4f}  flat_pl={sim['flat_pl']:.2f}")

        if score > best_score:
            best_score = score
            best_pct = pct

    _log(f"Phase 4 completada en {time.time()-t0:.1f}s — best_co_pct={best_pct}%")
    return best_pct


def _build_preset_config(disabled: set, adj: dict, risk_filter: str,
                          br_mode: str, criterion: str, m_min: int, m_max: int,
                          co_pct: int, bankroll_init: float,
                          stats: dict = None,
                          strategy_params: dict = None) -> dict:
    """
    Build a full cartera_config.json-compatible dict from optimizer result.

    Uses a set of disabled strategy keys (dynamic, from steepest descent).
    Strategy params (xgMax, possMax, etc.) come from the current cartera_config.json
    (already set by bt_optimizer grid search).
    """
    adj = adj or DEFAULT_ADJ

    # Read current cartera_config.json to preserve all strategy params
    base_cfg = {}
    if _CARTERA_CFG.exists():
        try:
            base_cfg = json.loads(_CARTERA_CFG.read_text(encoding="utf-8"))
        except Exception:
            pass

    flat_stake       = base_cfg.get("flat_stake", 1)
    initial_bankroll = base_cfg.get("initial_bankroll", 100)
    min_duration     = base_cfg.get("min_duration", {})
    cashout_minute   = base_cfg.get("adjustments", {}).get("cashout_minute", None)

    # Start from current strategies in cartera_config.json (preserves all params)
    _base_strategies = base_cfg.get("strategies", {}) or {}
    strategies = {k: dict(v) if isinstance(v, dict) else v
                  for k, v in _base_strategies.items()}

    # Apply on/off from disabled set (dynamic — works with ALL strategies).
    # Respect quality gates: if staging disabled a strategy (failed phase1/2), never re-enable it.
    for reg_key in list(strategies.keys()):
        if not isinstance(strategies[reg_key], dict):
            continue
        base_entry = _base_strategies.get(reg_key, {})
        base_enabled = base_entry.get("enabled", True) if isinstance(base_entry, dict) else True
        if not base_enabled:
            # Failed quality gates in bt_optimizer — keep disabled regardless
            strategies[reg_key]["enabled"] = False
        elif reg_key in disabled:
            # Portfolio optimizer decided to disable this strategy
            strategies[reg_key]["enabled"] = False
        else:
            strategies[reg_key]["enabled"] = True

    # Apply momentum minute range from Phase 3
    if "momentum_xg" in strategies and isinstance(strategies["momentum_xg"], dict):
        strategies["momentum_xg"]["minute_min"] = m_min
        strategies["momentum_xg"]["minute_max"] = m_max

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _run_phase1(bets, criterion, bankroll_init, n_workers):
    """Dynamic Phase 1: find best risk_filter (+ br for min_dd) then steepest descent.

    For max_roi/max_pl/max_wr: bankroll_mode is irrelevant (scoring uses flat metrics).
    Only min_dd needs to test multiple bankroll modes.
    Steepest descent replaces the old 2^7 brute-force search.
    """
    strategy_keys = sorted({b.get("strategy") for b in bets if b.get("strategy")})
    n_strategies = len(strategy_keys)
    _log(f"Phase 1 — {n_strategies} estrategias dinámicas, steepest descent…")
    t0 = time.time()

    # Determine which BR modes to test
    br_candidates = BR_OPTS if criterion == "min_dd" else ["fixed"]

    best_disabled = set()
    best_risk = "all"
    best_br = "fixed"
    best_score = -math.inf

    # Step 1: find best (risk_filter, br) with all strategies on
    for risk in RISK_OPTS:
        for br in br_candidates:
            score = _eval_dynamic(bets, set(), None, risk, bankroll_init, br, criterion)
            if score > best_score:
                best_score = score
                best_risk = risk
                best_br = br

    n_base = len(RISK_OPTS) * len(br_candidates)
    _log(f"  Base: {n_base} combos (risk×br) — best_risk={best_risk} best_br={best_br} score={best_score:.4f}")

    # Step 2: steepest descent with the best risk+br, no adj yet
    disabled = _steepest_descent(
        bets, strategy_keys, None, best_risk, bankroll_init, best_br, criterion)

    final_score = _eval_dynamic(bets, disabled, None, best_risk, bankroll_init, best_br, criterion)
    if disabled:
        _log(f"  Steepest descent desactivó: {', '.join(sorted(disabled))}")
    _log(f"Phase 1 completada en {time.time()-t0:.1f}s — score={final_score:.4f}")

    return disabled, best_risk, best_br, final_score


def _run_phase2(bets, disabled, best_risk, best_br, criterion, bankroll_init,
                label="Phase 2", adj_override=None):
    """Phase 2: search 7776 realistic adjustment combos."""
    combo_bets = _collect_bets_dynamic(bets, disabled)

    if adj_override is not None:
        _log(f"{label} — adj_override activo, omitiendo búsqueda ({len(combo_bets)} bets)")
        return adj_override

    _log(f"{label} — {_PHASE2_TOTAL} adj combos ({len(combo_bets)} bets base)…")
    t0 = time.time()
    found_adj, _ = _phase2_worker((combo_bets, bankroll_init, best_br, best_risk, criterion))
    _log(f"{label} completada en {time.time()-t0:.1f}s")
    return found_adj if found_adj is not None else DEFAULT_ADJ


def _run_phase25(bets, disabled, best_adj, best_risk, best_br, criterion, bankroll_init):
    """Post-adj steepest descent: re-check if any strategy should be disabled
    now that realistic adjustments are applied."""
    strategy_keys = sorted({b.get("strategy") for b in bets if b.get("strategy")})
    current_score = _eval_dynamic(bets, disabled, best_adj, best_risk, bankroll_init, best_br, criterion)
    _log(f"Phase 2.5 — score inicial con adj: {current_score:.4f}")

    # Steepest descent starts from the Phase 1 disabled state so the baseline
    # score reflects prior decisions. Only active strategies are candidates.
    combined = _steepest_descent(
        bets, [k for k in strategy_keys if k not in disabled],
        best_adj, best_risk, bankroll_init, best_br, criterion,
        initial_disabled=disabled)

    newly_disabled = combined - disabled
    final_score = _eval_dynamic(bets, combined, best_adj, best_risk, bankroll_init, best_br, criterion)

    if newly_disabled:
        _log(f"  Phase 2.5 desactivó adicionalmente: {', '.join(sorted(newly_disabled))}")
    _log(f"Phase 2.5 completada — score final: {final_score:.4f}")
    return combined, final_score


# ── Entry point ───────────────────────────────────────────────────────────────

def run(criterion: str, bankroll_init: float = 1000.0, n_workers: int = 1, out: str = None,
        adj_override: dict = None, strategy_params: dict = None) -> dict:
    """
    Dynamic portfolio optimizer entry point.

    Uses steepest descent over ALL strategies in the bets pool (no hardcoded lists).
    Bankroll mode only tested for min_dd criterion.

    Returns { disabled, risk_filter, best_score, adj, br, ... }
    """
    _log(f"Iniciando optimizador dinámico — criterio={criterion} bankroll={bankroll_init}")
    if adj_override is not None:
        _log(f"adj_override activo: {adj_override}")

    _log("Cargando datos desde CSV…")
    t0 = time.time()
    data = csv_reader.analyze_cartera()
    bets = data.get("bets", [])
    _log(f"Datos cargados en {time.time()-t0:.1f}s — {len(bets)} bets")

    if not bets:
        raise RuntimeError("No se encontraron bets. Verifica que existan CSVs en betfair_scraper/data/")

    # Phase 1: dynamic steepest descent (replaces 2048-combo brute force)
    disabled, best_risk, best_br, best_score = _run_phase1(bets, criterion, bankroll_init, n_workers)

    # Phase 2: realistic adjustments search
    best_adj = _run_phase2(bets, disabled, best_risk, best_br, criterion, bankroll_init,
                           adj_override=adj_override)

    # Phase 2.5: re-check disabling with adj applied
    disabled_before_25 = set(disabled)
    disabled, final_score = _run_phase25(bets, disabled, best_adj, best_risk, best_br, criterion, bankroll_init)

    # If Phase 2.5 changed the disabled set, re-optimize adj for the new set
    if disabled != disabled_before_25:
        _log("Phase 2.5 cambió las desactivadas — re-optimizando adj (Phase 2b)…")
        best_adj = _run_phase2(bets, disabled, best_risk, best_br, criterion, bankroll_init,
                               label="Phase 2b", adj_override=adj_override)
        disabled, final_score = _run_phase25(bets, disabled, best_adj, best_risk, best_br, criterion, bankroll_init)

    result = {
        "disabled": sorted(disabled),  # list for JSON serialization
        "risk_filter": best_risk,
        "br": best_br,
        "best_score": final_score if final_score > -math.inf else 0.0,
        "adj": best_adj,
    }

    # ── Post-optimization exports ──────────────────────────────────────────────
    _final_adj = best_adj or DEFAULT_ADJ
    try:
        # Phase 3: best momentum minute range
        m_min, m_max = _find_best_momentum_range(
            bets, disabled, _final_adj, best_risk, bankroll_init, best_br, criterion)
        _log(f"Phase 3 completada — best_momentum_range=({m_min}, {m_max})")

        # Phase 4: best CO percentage
        best_co_pct = _find_best_co_pct(
            data, disabled, _final_adj, best_risk, m_min, m_max, bankroll_init, best_br, criterion)

        # CSV uses momentum-filtered bets for accurate representation
        combo_bets  = _collect_bets_with_momentum_range(bets, disabled, m_min, m_max)
        bets_after  = _apply_realistic_adj(combo_bets, _final_adj)
        bets_final  = _filter_by_risk(bets_after, best_risk)
        # Stats with confidence interval
        n_bets = len(bets_final)
        wins = sum(1 for b in bets_final if b.get("won") in (True, 1, "1", "True", "true"))
        sim_final = _simulate_cartera_py(bets_final, bankroll_init, best_br)
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
        preset_cfg  = _build_preset_config(disabled, _final_adj, best_risk,
                                            best_br, criterion, m_min, m_max, best_co_pct,
                                            bankroll_init, _stats,
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
        # Convert set to list for JSON
        json_result = dict(result)
        if isinstance(json_result.get("disabled"), set):
            json_result["disabled"] = sorted(json_result["disabled"])
        out_path.write_text(json.dumps(json_result, indent=2, ensure_ascii=False), encoding="utf-8")
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
