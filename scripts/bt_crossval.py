"""
bt_crossval.py — Cross-validation de estrategias de apuestas.

No modifica ningún fichero del sistema. Solo lee datos y reporta.

Modos:
  Random 5-fold CV  : mezcla los 1202 partidos aleatoriamente, evalúa en 5 folds
  Temporal 70/30    : ordena por fecha, entrena en 70%, evalúa en 30%

Uso:
  python scripts/bt_crossval.py
  python scripts/bt_crossval.py --folds 5 --seed 42
  python scripts/bt_crossval.py --only xg_underperformance pressure_cooker
  python scripts/bt_crossval.py --output auxiliar/crossval_results.json
"""

import sys
import io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import math
import random
import argparse
from pathlib import Path
from datetime import datetime

ROOT    = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "betfair_scraper" / "dashboard" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "betfair_scraper"))

from utils.csv_reader import _STRATEGY_REGISTRY, _cfg_add_snake_keys
from utils.csv_loader  import _get_all_finished_matches, _read_csv_rows

CARTERA_CFG = ROOT / "betfair_scraper" / "cartera_config.json"

# ── Quality gate mínimo para reportar como PASS ───────────────────────────────
G_MIN_ROI    = 10.0
IC95_MIN_LOW = 40.0


# ─────────────────────────────────────────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def _wilson_ci(wins: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    center = (p + z*z / (2*n)) / (1 + z*z / n)
    margin  = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return (round(max(0.0, center - margin) * 100, 1),
            round(min(1.0, center + margin) * 100, 1))


def _match_date(match_data: dict) -> str:
    """Extract earliest timestamp from match rows for sorting."""
    rows = match_data.get("rows")
    if not rows:
        try:
            rows = _read_csv_rows(match_data["csv_path"])
        except Exception:
            return ""
    for row in rows:
        ts = row.get("timestamp_utc", "")
        if ts:
            return ts
    return ""


def _eval_on_matches(key: str, entry: tuple, cfg: dict, min_dur: int,
                     matches: list) -> list:
    """
    Run strategy on given match subset. Same logic as _analyze_strategy_simple
    but accepts an explicit matches list instead of loading all.
    """
    _, _, trigger_fn, _, extract_fn, win_fn = entry
    bets = []

    for match_data in matches:
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

        effective_cfg = {
            **cfg,
            "match_id":   match_id,
            "match_name": match_data.get("name", ""),
            "match_url":  match_data.get("url", ""),
        }

        first_seen = None
        trig_data  = None
        for curr_idx in range(len(rows)):
            trig = trigger_fn(rows, curr_idx, effective_cfg)
            if trig:
                if first_seen is None:
                    first_seen = curr_idx
                    trig_data  = trig
                if curr_idx >= first_seen + min_dur - 1:
                    extracted = extract_fn(trig_data)
                    if extracted is None:
                        break
                    odds, rec, _ = extracted
                    won   = win_fn(trig_data, ft_gl, ft_gv)
                    is_lay = rec.upper().startswith("LAY")
                    if is_lay:
                        pl = round(0.95 if won else -(odds - 1), 2)
                    else:
                        pl = round((odds - 1) * 0.95 if won else -1.0, 2)
                    bets.append({"won": won, "pl": pl})
                    break  # one bet per match per strategy

    return bets


def _metrics(bets: list) -> dict:
    """Compute metrics WITHOUT quality gates (report raw numbers per fold)."""
    n = len(bets)
    if n == 0:
        return {"n": 0, "wr": 0.0, "roi": 0.0, "pl": 0.0, "ci_low": 0.0}
    wins = sum(1 for b in bets if b["won"])
    pl   = sum(b["pl"] for b in bets)
    roi  = pl / n * 100
    ci_l, _ = _wilson_ci(wins, n)
    return {
        "n":     n,
        "wr":    round(wins / n * 100, 1),
        "roi":   round(roi, 1),
        "pl":    round(pl, 2),
        "ci_low": ci_l,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cross-validation
# ─────────────────────────────────────────────────────────────────────────────

def run_crossval(k: int = 5, seed: int = 42, only: list | None = None,
                 output_path: Path | None = None):

    # ── Load data ─────────────────────────────────────────────────────────────
    _log("Cargando datos históricos…")
    all_matches = _get_all_finished_matches()
    n_total = len(all_matches)
    _log(f"  {n_total} partidos cargados")

    # ── Sort by date for temporal split ───────────────────────────────────────
    _log("Ordenando por fecha para split temporal…")
    dated = [(m, _match_date(m)) for m in all_matches]
    dated.sort(key=lambda x: x[1])
    sorted_matches = [m for m, _ in dated]

    split_idx  = int(n_total * 0.70)
    train_temp = sorted_matches[:split_idx]
    test_temp  = sorted_matches[split_idx:]
    _log(f"  Temporal 70/30: train={len(train_temp)}, test={len(test_temp)}")

    # ── Random k-fold ─────────────────────────────────────────────────────────
    rng = random.Random(seed)
    shuffled = sorted_matches[:]
    rng.shuffle(shuffled)
    fold_size = n_total // k
    folds = [shuffled[i * fold_size:(i + 1) * fold_size] for i in range(k)]
    # Last fold absorbs remainder
    if n_total % k:
        folds[-1].extend(shuffled[k * fold_size:])
    _log(f"  Random {k}-fold: ~{fold_size} partidos/fold")

    # ── Load config ───────────────────────────────────────────────────────────
    with open(CARTERA_CFG, encoding="utf-8") as f:
        cfg_global = json.load(f)
    min_dur_map = cfg_global.get("min_duration", {})

    # ── Build registry lookup ─────────────────────────────────────────────────
    registry = {e[0]: e for e in _STRATEGY_REGISTRY}

    # ── Run per strategy ──────────────────────────────────────────────────────
    results = {}

    strategy_keys = [k_s for k_s in cfg_global.get("strategies", {}).keys()
                     if cfg_global["strategies"][k_s].get("enabled", False)]
    if only:
        strategy_keys = [k_s for k_s in strategy_keys if k_s in only]

    _log(f"\nEvaluando {len(strategy_keys)} estrategias activas…\n")

    for strat_key in strategy_keys:
        entry = registry.get(strat_key)
        if entry is None:
            continue

        raw_cfg = cfg_global["strategies"][strat_key]
        cfg     = _cfg_add_snake_keys({**raw_cfg, "enabled": True})
        min_dur = min_dur_map.get(strat_key, 1)

        # ── Random k-fold ──────────────────────────────────────────────────
        fold_metrics = []
        for fold_i, test_fold in enumerate(folds):
            bets = _eval_on_matches(strat_key, entry, cfg, min_dur, test_fold)
            fold_metrics.append(_metrics(bets))

        rois   = [fm["roi"] for fm in fold_metrics]
        mean_roi = round(sum(rois) / len(rois), 1)
        std_roi  = round(math.sqrt(sum((r - mean_roi)**2 for r in rois) / len(rois)), 1)
        n_pos    = sum(1 for r in rois if r > 0)

        # ── Temporal test ──────────────────────────────────────────────────
        bets_temporal_test = _eval_on_matches(strat_key, entry, cfg, min_dur, test_temp)
        temporal_metrics   = _metrics(bets_temporal_test)

        # ── Full sample (baseline) ─────────────────────────────────────────
        bets_full = _eval_on_matches(strat_key, entry, cfg, min_dur, sorted_matches)
        full_metrics = _metrics(bets_full)

        # ── Verdict ────────────────────────────────────────────────────────
        robust = (
            mean_roi >= G_MIN_ROI
            and n_pos >= math.ceil(k * 0.6)   # ≥60% de folds positivos
            and temporal_metrics["roi"] >= 0   # test temporal no negativo
        )

        results[strat_key] = {
            "full":     full_metrics,
            "folds":    fold_metrics,
            "mean_roi": mean_roi,
            "std_roi":  std_roi,
            "n_positive_folds": n_pos,
            "temporal_test":    temporal_metrics,
            "robust":   robust,
        }

        # ── Print row ──────────────────────────────────────────────────────
        fold_str = "  ".join(
            f"F{i+1}:{fm['roi']:+.0f}%(N={fm['n']})" for i, fm in enumerate(fold_metrics)
        )
        verdict = "✓ ROBUSTO" if robust else "✗ FRAGIL"
        print(
            f"  {strat_key:<28} "
            f"Full:{full_metrics['roi']:+.1f}%(N={full_metrics['n']:3d})  "
            f"{fold_str}  "
            f"Mean:{mean_roi:+.1f}±{std_roi:.1f}  "
            f"Temporal_test:{temporal_metrics['roi']:+.1f}%(N={temporal_metrics['n']:3d})  "
            f"{verdict}"
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    n_robust   = sum(1 for v in results.values() if v["robust"])
    n_fragil   = len(results) - n_robust
    print(f"\n{'─'*100}")
    print(f"  ROBUSTAS: {n_robust}/{len(results)}   FRÁGILES: {n_fragil}/{len(results)}")
    print(f"  (Criterio: mean_roi≥{G_MIN_ROI}% Y ≥60% folds positivos Y temporal_test≥0%)")
    print(f"{'─'*100}\n")

    # ── Save JSON ─────────────────────────────────────────────────────────────
    if output_path is None:
        output_path = ROOT / "auxiliar" / "crossval_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"generated": datetime.now().isoformat(),
                   "n_matches": n_total,
                   "k_folds":   k,
                   "seed":      seed,
                   "results":   results}, f, indent=2, ensure_ascii=False)
    _log(f"Resultados guardados en {output_path}")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-validation de estrategias Furbo")
    parser.add_argument("--folds",  type=int, default=5,  help="Número de folds (default: 5)")
    parser.add_argument("--seed",   type=int, default=42, help="Semilla aleatoria (default: 42)")
    parser.add_argument("--only",   nargs="+", default=None, help="Evaluar solo estas estrategias")
    parser.add_argument("--output", type=str, default=None, help="Ruta JSON de salida")
    args = parser.parse_args()

    out = Path(args.output) if args.output else None
    run_crossval(k=args.folds, seed=args.seed, only=args.only, output_path=out)
