"""
Análisis de distribución de apuestas por rango de cuotas por estrategia.
Responde: ¿conviene filtrar a odds >= 2.0?

Usa _analyze_strategy_simple() de csv_reader.py con los params óptimos del
último bt_optimizer_results.json.
"""
import sys
import os
import json
import math

# ── paths — igual que bt_optimizer.py ─────────────────────────────────────────
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(REPO, "betfair_scraper", "dashboard", "backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(REPO, "betfair_scraper"))

# Importar como paquete: "from utils import csv_reader"
from utils import csv_reader as cr
from utils.csv_reader import (
    _STRATEGY_REGISTRY,
    _analyze_strategy_simple,
    _cfg_add_snake_keys,
)

BT_RESULTS_FILE = os.path.join(REPO, "auxiliar", "bt_optimizer_results.json")
CARTERA_CFG_FILE = os.path.join(REPO, "betfair_scraper", "cartera_config.json")

# ── helpers ────────────────────────────────────────────────────────────────────
STAKE = 10.0

BUCKETS = [
    (1.0,  1.5,  "1.0-1.5"),
    (1.5,  2.0,  "1.5-2.0"),
    (2.0,  2.5,  "2.0-2.5"),
    (2.5,  3.0,  "2.5-3.0"),
    (3.0,  4.0,  "3.0-4.0"),
    (4.0,  999,  "4.0+   "),
]


def wilson_ci95_low(n, wins):
    if n == 0:
        return 0.0
    z = 1.96
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0, centre - margin) * 100, 1)


def bucket_stats(bets):
    """Devuelve lista de dicts con stats por bucket de cuotas."""
    results = []
    for lo, hi, label in BUCKETS:
        subset = [b for b in bets if lo <= b["odds"] < hi]
        n = len(subset)
        if n == 0:
            results.append({"label": label, "n": 0})
            continue
        wins = sum(1 for b in subset if b["won"])
        wr = wins / n * 100
        pl = sum(b["pl"] for b in subset)
        roi = pl / (n * STAKE) * 100
        ci_low = wilson_ci95_low(n, wins)
        midpoint = (lo + min(hi, 8.0)) / 2   # cap hi en 8 para EV del bucket 4+
        ev = wr / 100 * (midpoint - 1) - (1 - wr / 100)   # EV por unidad apostada
        results.append({
            "label": label,
            "n": n,
            "wins": wins,
            "wr": round(wr, 1),
            "pl": round(pl, 2),
            "roi": round(roi, 1),
            "ci_low": ci_low,
            "ev_unit": round(ev, 3),
        })
    return results


def global_stats(bets):
    n = len(bets)
    if n == 0:
        return {"n": 0}
    wins = sum(1 for b in bets if b["won"])
    pl = sum(b["pl"] for b in bets)
    return {
        "n": n,
        "wr": round(wins / n * 100, 1),
        "pl": round(pl, 2),
        "roi": round(pl / (n * STAKE) * 100, 1),
        "ci_low": wilson_ci95_low(n, wins),
    }


def print_strategy_report(key, bets):
    g_all  = global_stats(bets)
    g_ge2  = global_stats([b for b in bets if b["odds"] >= 2.0])
    buckets = bucket_stats(bets)

    print(f"\n{'='*70}")
    print(f"  {key}   (N total={g_all['n']})")
    print(f"{'='*70}")
    print(f"  GLOBAL:         N={g_all['n']:>4}  WR={g_all['wr']:>5.1f}%  "
          f"ROI={g_all['roi']:>7.1f}%  P/L={g_all['pl']:>8.2f}  CI95_low={g_all['ci_low']}%")
    if g_ge2['n'] > 0:
        print(f"  odds >= 2.0:    N={g_ge2['n']:>4}  WR={g_ge2['wr']:>5.1f}%  "
              f"ROI={g_ge2['roi']:>7.1f}%  P/L={g_ge2['pl']:>8.2f}  CI95_low={g_ge2['ci_low']}%")
    else:
        print(f"  odds >= 2.0:    N=   0  (sin datos)")

    print(f"\n  {'Bucket':<10} {'N':>5} {'WR%':>6} {'ROI%':>8} {'P/L':>9} {'CI95lo':>8} {'EV/unit':>8}")
    print(f"  {'-'*58}")
    for bk in buckets:
        if bk["n"] == 0:
            print(f"  {bk['label']:<10} {'':>5}")
        else:
            print(f"  {bk['label']:<10} {bk['n']:>5} {bk['wr']:>6.1f} "
                  f"{bk['roi']:>8.1f} {bk['pl']:>9.2f} {bk['ci_low']:>8.1f} {bk['ev_unit']:>8.3f}")

    return g_all, g_ge2, buckets


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    print("Cargando bt_optimizer_results.json ...")
    with open(BT_RESULTS_FILE, encoding="utf-8") as f:
        bt_results = json.load(f)

    print("Cargando cartera_config.json ...")
    with open(CARTERA_CFG_FILE, encoding="utf-8") as f:
        cartera_cfg = json.load(f)

    individual = bt_results.get("individual", {})
    cartera_strategies = cartera_cfg.get("strategies", {})
    min_duration_cfg = cartera_cfg.get("min_duration", {})

    # Construir lookup key -> entry desde el registry
    registry = {entry[0]: entry for entry in _STRATEGY_REGISTRY}

    print(f"\nEstrategias con datos en bt_optimizer_results: {list(individual.keys())}")
    print(f"Estrategias activas en cartera_config: "
          f"{[k for k, v in cartera_strategies.items() if v.get('enabled')]}")

    all_strategy_bets = {}   # key -> list[bet normalizado]

    for key, bt_data in individual.items():
        if key not in registry:
            print(f"  SKIP {key}: no encontrado en _STRATEGY_REGISTRY")
            continue

        entry = registry[key]
        _, _name, trigger_fn, _desc, extract_fn, win_fn = entry

        # Params optimos del grid search
        bt_params = bt_data.get("params", {})

        # Merge: config de cartera (keys que triggers necesitan) + params BT (tienen prioridad)
        cartera_s_cfg = cartera_strategies.get(key, {})
        merged_cfg = {**cartera_s_cfg, **bt_params}
        cfg = _cfg_add_snake_keys(merged_cfg)

        min_dur = min_duration_cfg.get(key, 1)

        print(f"  Ejecutando {key} (min_dur={min_dur}, params={bt_params}) ...", flush=True)
        try:
            bets = _analyze_strategy_simple(key, trigger_fn, extract_fn, win_fn, cfg, min_dur)
        except Exception as exc:
            print(f"    ERROR en {key}: {exc}")
            bets = []

        # Normalizar: extraer odds del campo correcto
        normalized = []
        for b in bets:
            odds_val = b.get("back_odds") or 0.0
            if not odds_val or odds_val <= 1.0:
                continue
            normalized.append({
                "odds": odds_val,
                "won": b.get("won", False),
                "pl": b.get("pl", 0.0),
                "match_id": b.get("match_id", ""),
                "minuto": b.get("minuto", 0),
            })

        all_strategy_bets[key] = normalized
        print(f"    -> {len(normalized)} bets validos (odds > 1.0)")

    # ── Reportes por estrategia ────────────────────────────────────────────────
    print("\n\n" + "#"*70)
    print("  REPORTE POR ESTRATEGIA -- DISTRIBUCION POR BUCKET DE CUOTAS")
    print("#"*70)

    agg_all_bets = []
    summary_rows = []

    for key in sorted(all_strategy_bets.keys()):
        bets = all_strategy_bets[key]
        if not bets:
            print(f"\n  {key}: sin bets")
            continue
        g_all, g_ge2, buckets = print_strategy_report(key, bets)
        agg_all_bets.extend(bets)
        summary_rows.append({
            "key": key,
            "g_all": g_all,
            "g_ge2": g_ge2,
            "buckets": buckets,
        })

    # ── Resumen agregado del portfolio ─────────────────────────────────────────
    print("\n\n" + "#"*70)
    print("  RESUMEN AGREGADO -- PORTFOLIO COMPLETO (todas las estrategias)")
    print("#"*70)

    g_portfolio_all = global_stats(agg_all_bets)
    g_portfolio_ge2 = global_stats([b for b in agg_all_bets if b["odds"] >= 2.0])
    portfolio_buckets = bucket_stats(agg_all_bets)

    print(f"\n  GLOBAL:      N={g_portfolio_all['n']:>5}  WR={g_portfolio_all['wr']:>5.1f}%  "
          f"ROI={g_portfolio_all['roi']:>7.1f}%  P/L={g_portfolio_all['pl']:>9.2f}  "
          f"CI95_low={g_portfolio_all['ci_low']}%")
    print(f"  odds >= 2.0: N={g_portfolio_ge2['n']:>5}  WR={g_portfolio_ge2['wr']:>5.1f}%  "
          f"ROI={g_portfolio_ge2['roi']:>7.1f}%  P/L={g_portfolio_ge2['pl']:>9.2f}  "
          f"CI95_low={g_portfolio_ge2['ci_low']}%")

    print(f"\n  {'Bucket':<10} {'N':>6} {'WR%':>6} {'ROI%':>8} {'P/L':>10} {'CI95lo':>8} {'EV/unit':>8}")
    print(f"  {'-'*60}")
    for bk in portfolio_buckets:
        if bk["n"] == 0:
            print(f"  {bk['label']:<10} {'':>6}")
        else:
            print(f"  {bk['label']:<10} {bk['n']:>6} {bk['wr']:>6.1f} "
                  f"{bk['roi']:>8.1f} {bk['pl']:>10.2f} {bk['ci_low']:>8.1f} {bk['ev_unit']:>8.3f}")

    # ── Tabla comparativa por estrategia: GLOBAL vs >= 2.0 ────────────────────
    print("\n\n" + "#"*70)
    print("  TABLA COMPARATIVA: GLOBAL vs odds >= 2.0")
    print("#"*70)
    hdr = (f"  {'Estrategia':<22} {'N_all':>6} {'ROI_all':>8}  "
           f"{'N_ge2':>6} {'ROI_ge2':>8}  {'Delta_ROI':>10}  {'Delta_N':>7}")
    print(hdr)
    print("  " + "-"*74)
    for row in sorted(summary_rows, key=lambda r: r["g_all"].get("roi", 0), reverse=True):
        k = row["key"]
        ga = row["g_all"]
        gb = row["g_ge2"]
        n_all = ga.get("n", 0)
        n_ge2 = gb.get("n", 0)
        roi_all = ga.get("roi", 0)
        roi_ge2 = gb.get("roi", 0) if n_ge2 > 0 else float("nan")
        delta_roi = roi_ge2 - roi_all if n_ge2 > 0 else float("nan")
        delta_n = n_ge2 - n_all

        flag = ""
        if n_ge2 > 0 and not math.isnan(delta_roi):
            if delta_roi > 5:
                flag = "  <<< mejora"
            elif delta_roi < -5:
                flag = "  --- empeora"

        if math.isnan(roi_ge2):
            print(f"  {k:<22} {n_all:>6} {roi_all:>8.1f}%  "
                  f"{'N/A':>6} {'N/A':>8}  {'N/A':>10}  {delta_n:>7}{flag}")
        else:
            print(f"  {k:<22} {n_all:>6} {roi_all:>8.1f}%  "
                  f"{n_ge2:>6} {roi_ge2:>8.1f}%  {delta_roi:>+10.1f}pp  {delta_n:>7}{flag}")

    # ── Histograma del portfolio ───────────────────────────────────────────────
    print("\n\n" + "#"*70)
    print("  DISTRIBUCION DE CUOTAS -- HISTOGRAMA PORTFOLIO COMPLETO")
    print("#"*70)
    print(f"\n  {'Bucket':<10} {'N':>6} {'% bets':>8} {'P/L acum':>10} {'EV/unit':>9}")
    print("  " + "-"*48)
    total_n = g_portfolio_all.get("n", 1) or 1
    for bk in portfolio_buckets:
        if bk["n"] == 0:
            print(f"  {bk['label']:<10} {'':>6}")
        else:
            pct = bk["n"] / total_n * 100
            print(f"  {bk['label']:<10} {bk['n']:>6} {pct:>8.1f}%  {bk['pl']:>9.2f}  {bk['ev_unit']:>8.3f}")

    # ── Veredicto ──────────────────────────────────────────────────────────────
    print("\n\n" + "#"*70)
    print("  VEREDICTO: CONVIENE FILTRAR odds >= 2.0?")
    print("#"*70)

    if g_portfolio_all["n"] > 0 and g_portfolio_ge2["n"] > 0:
        delta_roi = g_portfolio_ge2["roi"] - g_portfolio_all["roi"]
        delta_n = g_portfolio_ge2["n"] - g_portfolio_all["n"]
        pct_bets_lost = abs(delta_n) / g_portfolio_all["n"] * 100

        bets_below2 = [b for b in agg_all_bets if b["odds"] < 2.0]
        pl_below2 = sum(b["pl"] for b in bets_below2)
        n_below2 = len(bets_below2)
        wins_below2 = sum(1 for b in bets_below2 if b["won"])
        wr_below2 = wins_below2 / n_below2 * 100 if n_below2 > 0 else 0

        print(f"\n  Bets con odds < 2.0 :  N={n_below2},  WR={wr_below2:.1f}%,  P/L={pl_below2:.2f}")
        print(f"  ROI global actual   :  {g_portfolio_all['roi']:.1f}%")
        print(f"  ROI con odds >= 2.0 :  {g_portfolio_ge2['roi']:.1f}%  (Delta {delta_roi:+.1f}pp)")
        print(f"  Bets perdidos       :  {abs(delta_n)} ({pct_bets_lost:.1f}% del total)")
        print(f"  P/L perdido (< 2.0) :  {pl_below2:.2f}")

        if delta_roi > 5 and pl_below2 < 0:
            print("\n  -> RECOMENDACION: Filtrar odds >= 2.0 MEJORA el ROI y elimina P/L negativo.")
            print("     Las cuotas bajas destruyen valor en este portfolio.")
        elif delta_roi > 5 and pl_below2 >= 0:
            print("\n  -> RECOMENDACION: Filtrar sube ROI pero sacrifica P/L positivo en cuotas bajas.")
            print("     Analizar estrategia por estrategia para decidir si vale la pena.")
        elif delta_roi < -5:
            print("\n  -> RECOMENDACION: Las cuotas bajas son RENTABLES -- NO filtrar odds >= 2.0.")
            print("     El valor esta en las cuotas cortas (alta WR).")
        else:
            print(f"\n  -> RECOMENDACION: Efecto neutral (Delta={delta_roi:+.1f}pp < 5pp umbral).")
            print("     Analizar por estrategia individualmente segun perfil de cuotas.")


if __name__ == "__main__":
    main()