"""
Compara 3 opciones de G_MIN_PL_PER_BET usando los datos actuales (1446 partidos):
  A) Fijo 0.15 (actual)
  B) Fijo 0.25
  C) Dinamico: 0.10 + n_partidos/10000

Luego simula que pasaria con la opcion dinamica cuando tengamos mas partidos,
verificando si el "doble apriete" (N_min + PL/bet subiendo juntos) mata
demasiadas estrategias.

Uso: python auxiliar/simulate_dynamic_vs_fixed.py
"""

import sys, os, json, math, itertools, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
os.chdir(ROOT / "betfair_scraper" / "dashboard" / "backend")

from utils.csv_reader import _analyze_strategy_simple, _STRATEGY_REGISTRY, _cfg_add_snake_keys
from bt_optimizer import SEARCH_SPACES, _wilson_ci, _max_drawdown, _get_min_dur
from utils.csv_loader import _get_all_finished_matches

G_MIN_ROI = 10.0
IC95_MIN_LOW = 40.0


def eval_bets(bets, n_fin, min_pl_per_bet):
    min_n = max(15, n_fin // 25)
    n = len(bets)
    if n < min_n:
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
    return {
        "n": n, "wins": wins, "wr": round(wins / n * 100, 1),
        "pl": round(pl, 2), "roi": round(roi, 1),
        "ci_low": ci_l, "score": round(ci_l * roi / 100, 4),
        "pl_per_bet": round(pl / n, 3),
    }


def main():
    t0 = time.time()
    n_fin = len(_get_all_finished_matches())

    with open(ROOT / "betfair_scraper" / "cartera_config.json") as f:
        cfg = json.load(f)
    md = cfg.get("min_duration", {})

    print(f"Partidos: {n_fin}, N_min: {max(15, n_fin // 25)}")
    print(f"Ejecutando grid search completo...\n")

    # Grid search una sola vez, guardar todos los (combo, bets)
    strategy_combos = {}
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
        strategy_combos[key] = combos
        print(f"  {key}: {len(combos)} combos")

    elapsed_grid = time.time() - t0
    print(f"\nGrid completo en {elapsed_grid:.0f}s\n")

    # ================================================================
    # 1. Comparacion de las 3 opciones con datos actuales
    # ================================================================
    print("=" * 90)
    print("1. COMPARACION: Fijo 0.15 vs Fijo 0.25 vs Dinamico")
    print("=" * 90)

    dynamic_threshold = 0.10 + n_fin / 10000
    options = [
        ("A) Fijo 0.15 (actual)", 0.15),
        ("B) Fijo 0.25", 0.25),
        (f"C) Dinamico ({dynamic_threshold:.3f})", dynamic_threshold),
    ]

    results_by_option = {}
    print(f"\n  {'Opcion':<28} {'Umbral':>7} {'Strats':>6} {'N':>6} {'PL':>9} {'ROI%':>7} {'PL/bet':>7}")
    print(f"  {'-'*75}")

    for label, threshold in options:
        enabled = {}
        for key, combos in strategy_combos.items():
            best = None
            for raw_cfg, bets in combos:
                metrics = eval_bets(bets, n_fin, threshold)
                if metrics and (best is None or metrics["score"] > best["score"]):
                    best = {**metrics, "params": raw_cfg, "key": key}
            if best:
                enabled[key] = best

        results_by_option[label] = enabled
        n_strats = len(enabled)
        total_n = sum(v["n"] for v in enabled.values())
        total_pl = sum(v["pl"] for v in enabled.values())
        roi = total_pl / total_n * 100 if total_n else 0
        plb = total_pl / total_n if total_n else 0

        print(f"  {label:<28} {threshold:>7.3f} {n_strats:>6} {total_n:>6} {total_pl:>8.1f} {roi:>6.1f}% {plb:>6.3f}")

    # Que pierde cada opcion vs baseline
    base_strats = set(results_by_option[options[0][0]].keys())
    for label, threshold in options[1:]:
        lost = base_strats - set(results_by_option[label].keys())
        print(f"\n  {label} pierde: {', '.join(sorted(lost)) if lost else 'ninguna'}")

    # ================================================================
    # 2. Detalle por estrategia
    # ================================================================
    print(f"\n{'=' * 90}")
    print("2. PL/BET DE CADA ESTRATEGIA (con umbral actual 0.15)")
    print("=" * 90)

    base = results_by_option[options[0][0]]
    sorted_strats = sorted(base.items(), key=lambda x: x[1]["pl_per_bet"])

    print(f"\n  {'Estrategia':<24} {'N':>6} {'WR%':>7} {'ROI%':>8} {'PL':>9} {'PL/bet':>8} {'Pasa 0.25?':>10}")
    print(f"  {'-'*75}")

    for key, data in sorted_strats:
        passes_025 = "SI" if data["pl_per_bet"] >= 0.25 else "NO"
        print(f"  {key:<24} {data['n']:>6} {data['wr']:>6.1f}% {data['roi']:>7.1f}% {data['pl']:>8.2f} {data['pl_per_bet']:>7.3f} {passes_025:>10}")

    # ================================================================
    # 3. Proyeccion futura del doble apriete
    # ================================================================
    print(f"\n{'=' * 90}")
    print("3. PROYECCION FUTURA: doble apriete (N_min + PL/bet subiendo)")
    print("=" * 90)

    # Asumiendo que las estrategias mantienen ratio bets/partidos similar,
    # proyectar cuantas bets tendria cada estrategia con mas partidos
    print(f"\n  Ratio bets/partido actual por estrategia:")
    ratios = {}
    for key, data in base.items():
        ratio = data["n"] / n_fin
        ratios[key] = ratio

    print(f"\n  {'N partidos':>12} {'N_min':>6} {'PL/bet din':>11} {'Strats OK (est.)':>17}")
    print(f"  {'-'*50}")

    for np in [1446, 1800, 2000, 2500, 3000, 4000, 5000]:
        nmin = max(15, np // 25)
        plb_threshold = 0.10 + np / 10000
        # Estimar cuantas estrategias pasarian:
        # Una estrategia pasa si: N_estimado >= nmin AND pl_per_bet >= plb_threshold
        surviving = 0
        for key, data in base.items():
            estimated_n = int(ratios[key] * np)
            # PL/bet se mantiene aprox constante si los params no cambian
            if estimated_n >= nmin and data["pl_per_bet"] >= plb_threshold:
                surviving += 1
        print(f"  {np:>12} {nmin:>6} {plb_threshold:>11.3f} {surviving:>17}/{len(base)}")

    # ================================================================
    # 4. Alternativa: formula con techo
    # ================================================================
    print(f"\n{'=' * 90}")
    print("4. ALTERNATIVA: dinamico con techo (cap)")
    print("=" * 90)
    print("""
  Si el problema es el doble apriete a largo plazo, una opcion es
  poner un techo al umbral dinamico:

    G_MIN_PL_PER_BET = min(0.30, 0.10 + n_partidos / 10000)

  Asi sube con los datos pero nunca pasa de 0.30.
""")

    for np in [1446, 2000, 3000, 5000, 10000]:
        uncapped = 0.10 + np / 10000
        capped = min(0.30, uncapped)
        print(f"  {np:>6} partidos: sin cap={uncapped:.3f}, con cap={capped:.3f}")

    # Evaluar cap=0.30 con datos actuales
    th_capped = min(0.30, 0.10 + n_fin / 10000)
    enabled_cap = {}
    for key, combos in strategy_combos.items():
        best = None
        for raw_cfg, bets in combos:
            metrics = eval_bets(bets, n_fin, th_capped)
            if metrics and (best is None or metrics["score"] > best["score"]):
                best = {**metrics, "params": raw_cfg, "key": key}
        if best:
            enabled_cap[key] = best

    total_n = sum(v["n"] for v in enabled_cap.values())
    total_pl = sum(v["pl"] for v in enabled_cap.values())
    print(f"\n  Con datos actuales (cap={th_capped:.3f}):")
    print(f"  Strats={len(enabled_cap)}, N={total_n}, PL={total_pl:.1f}, "
          f"ROI={total_pl/total_n*100:.1f}%, PL/bet={total_pl/total_n:.3f}")
    lost = base_strats - set(enabled_cap.keys())
    print(f"  Pierde vs 0.15: {', '.join(sorted(lost)) if lost else 'ninguna'}")

    print(f"\nCompletado en {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
