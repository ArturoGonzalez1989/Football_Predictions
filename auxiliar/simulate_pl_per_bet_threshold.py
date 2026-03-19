"""
Simula el impacto de subir G_MIN_PL_PER_BET en bt_optimizer.

Ejecuta el grid search completo de todas las estrategias y evalua
con diferentes umbrales de PL/bet para ver cuantas estrategias
sobreviven y como cambia el portfolio.

Uso: python auxiliar/simulate_pl_per_bet_threshold.py
"""

import sys, os, json, math, itertools, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
os.chdir(ROOT / "betfair_scraper" / "dashboard" / "backend")

from utils.csv_reader import _analyze_strategy_simple, _STRATEGY_REGISTRY, _cfg_add_snake_keys
from bt_optimizer import SEARCH_SPACES, _wilson_ci, _max_drawdown, _min_n, _get_min_dur
from utils.csv_loader import _get_all_finished_matches

G_MIN_ROI = 10.0
IC95_MIN_LOW = 40.0
THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]


def eval_bets(bets, n_fin, min_pl_per_bet):
    n = len(bets)
    if n < _min_n(n_fin):
        return None
    wins = sum(1 for b in bets if b["won"])
    pl = sum(b["pl"] for b in bets)
    roi = pl / n * 100
    if roi < G_MIN_ROI:
        return None
    if pl / n < min_pl_per_bet:
        return None
    ci_l, ci_h = _wilson_ci(wins, n)
    if ci_l < IC95_MIN_LOW:
        return None
    max_dd = _max_drawdown([b["pl"] for b in bets])
    return {
        "n": n, "wins": wins, "wr": round(wins / n * 100, 1),
        "pl": round(pl, 2), "roi": round(roi, 1),
        "ci_low": ci_l, "ci_high": ci_h, "max_dd": max_dd,
        "score": round(ci_l * roi / 100, 4),
        "pl_per_bet": round(pl / n, 3),
    }


def main():
    t0 = time.time()
    n_fin = len(_get_all_finished_matches())
    g_min_n = _min_n(n_fin)

    with open(ROOT / "betfair_scraper" / "cartera_config.json") as f:
        cfg = json.load(f)
    md = cfg.get("min_duration", {})

    print(f"Partidos: {n_fin}, N minimo: {g_min_n}")
    print(f"Ejecutando grid search completo...")

    # Phase 1: run grid search for all strategies (store all combos)
    strategy_grids = {}
    for key in list(SEARCH_SPACES.keys()):
        entry = None
        for e in _STRATEGY_REGISTRY:
            if e[0] == key:
                entry = e
                break
        if not entry:
            continue
        _, _, trigger_fn, _, extract_fn, win_fn = entry
        space = SEARCH_SPACES[key]
        min_dur = _get_min_dur(key, md)

        param_names = list(space.keys())
        param_values = list(space.values())

        combos = []
        for combo_vals in itertools.product(*param_values):
            raw_cfg = dict(zip(param_names, combo_vals))
            cfg_run = _cfg_add_snake_keys({**raw_cfg, "enabled": True})
            bets = _analyze_strategy_simple(key, trigger_fn, extract_fn, win_fn, cfg_run, min_dur)
            if bets:
                combos.append((raw_cfg, bets))
        strategy_grids[key] = combos
        print(f"  {key}: {len(combos)} combos evaluadas")

    elapsed = time.time() - t0
    print(f"\nGrid search completo en {elapsed:.0f}s para {len(strategy_grids)} estrategias.\n")

    # Phase 2: evaluate with each threshold
    print("=" * 95)
    print("IMPACTO POR UMBRAL G_MIN_PL_PER_BET")
    print("=" * 95)
    header = f"  {'Umbral':<10} {'Strats':>6} {'N total':>8} {'PL total':>10} {'ROI%':>7} {'PL/bet':>8}"
    print(header)
    print(f"  {'-'*55}")

    all_results = {}
    baseline_strats = set()

    for threshold in THRESHOLDS:
        enabled = {}
        for key, combos in strategy_grids.items():
            best = None
            for raw_cfg, bets in combos:
                metrics = eval_bets(bets, n_fin, threshold)
                if metrics and (best is None or metrics["score"] > best["score"]):
                    best = {**metrics, "params": raw_cfg, "key": key}
            if best:
                enabled[key] = best

        if threshold == 0.15:
            baseline_strats = set(enabled.keys())

        all_results[threshold] = enabled
        lost = baseline_strats - set(enabled.keys())

        n_strats = len(enabled)
        total_n = sum(v["n"] for v in enabled.values())
        total_pl = sum(v["pl"] for v in enabled.values())
        avg_roi = total_pl / total_n * 100 if total_n else 0
        avg_plb = total_pl / total_n if total_n else 0

        print(f"  {threshold:<10.2f} {n_strats:>6} {total_n:>8} {total_pl:>9.2f} {avg_roi:>6.1f}% {avg_plb:>7.3f}")
        if lost:
            print(f"             Pierden: {', '.join(sorted(lost))}")

    # Phase 3: detailed comparison 0.15 vs 0.25
    print(f"\n{'=' * 100}")
    print("DETALLE: umbral 0.15 (actual) vs 0.25")
    print("=" * 100)

    r1_all = all_results.get(0.15, {})
    r2_all = all_results.get(0.25, {})

    print(f"\n  {'Estrategia':<24} {'N(.15)':>7} {'N(.25)':>7} {'ROI(.15)':>9} {'ROI(.25)':>9} {'PL/b(.15)':>10} {'PL/b(.25)':>10} {'Cambio':>8}")
    print(f"  {'-'*90}")

    all_keys = sorted(set(list(r1_all.keys()) + list(r2_all.keys())))
    for key in all_keys:
        a = r1_all.get(key)
        b = r2_all.get(key)

        n1 = str(a["n"]) if a else "-"
        n2 = str(b["n"]) if b else "-"
        roi1 = f"{a['roi']}%" if a else "-"
        roi2 = f"{b['roi']}%" if b else "-"
        plb1 = f"{a['pl_per_bet']:.3f}" if a else "-"
        plb2 = f"{b['pl_per_bet']:.3f}" if b else "-"

        if a and not b:
            change = "DROPPED"
        elif a and b and a["params"] != b["params"]:
            change = "RETUNED"
        elif a and b:
            change = "same"
        else:
            change = "NEW"

        print(f"  {key:<24} {n1:>7} {n2:>7} {roi1:>9} {roi2:>9} {plb1:>10} {plb2:>10} {change:>8}")

    # Phase 4: what dynamic threshold would look like
    print(f"\n{'=' * 100}")
    print("PROPUESTA: G_MIN_PL_PER_BET dinamico basado en N partidos")
    print("=" * 100)
    print("""
  Idea: a mas partidos, mas exigente el umbral.

  Formula propuesta: G_MIN_PL_PER_BET = 0.10 + (n_partidos / 10000)

  Ejemplos:
""")
    for np in [500, 750, 1000, 1200, 1443, 1800, 2000, 3000, 5000]:
        dynamic = 0.10 + np / 10000
        print(f"    {np:>5} partidos -> G_MIN_PL_PER_BET = {dynamic:.3f}")


if __name__ == "__main__":
    main()
