"""
League Analysis — Rendimiento por liga para todas las estrategias activas.
Detecta sesgos de liga: estrategias impulsadas por ligas específicas.

Uso: python auxiliar/league_analysis.py
Salida: auxiliar/league_analysis_results.json + reporte en stdout
"""
import sys
import os
import json
import math

# Añadir path del backend para importar csv_reader
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "betfair_scraper", "dashboard", "backend"))

print("Importando analyze_cartera()...", flush=True)
from utils.csv_reader import analyze_cartera

# ── Helpers estadísticos ─────────────────────────────────────────────────────

STAKE = 10.0  # flat stake usado por analyze_cartera

def wilson_ci95(n, wins):
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0, centre - margin) * 100, 1),
            round(min(1, centre + margin) * 100, 1))

def compute_group_stats(bets):
    """Calcula estadísticas para un grupo de bets."""
    n = len(bets)
    if n == 0:
        return {"n": 0, "wins": 0, "wr_pct": 0.0, "pl": 0.0, "roi_pct": 0.0, "ci95_low": 0.0}
    wins = sum(1 for b in bets if b["won"])
    total_pl = sum(b["pl"] for b in bets)
    wr = wins / n * 100
    roi = total_pl / (n * STAKE) * 100
    ci_lo, _ = wilson_ci95(n, wins)
    return {
        "n": n,
        "wins": wins,
        "wr_pct": round(wr, 1),
        "pl": round(total_pl, 2),
        "roi_pct": round(roi, 1),
        "ci95_low": ci_lo,
    }

# ── Ejecutar backtest ────────────────────────────────────────────────────────

print("Ejecutando analyze_cartera() — esto puede tardar 30-60s...", flush=True)
result = analyze_cartera()
all_bets = result.get("bets", [])
print(f"Total bets: {len(all_bets)}", flush=True)

# ── Distribución del dataset por liga ────────────────────────────────────────

from collections import defaultdict

league_counts = defaultdict(int)
for b in all_bets:
    pais = b.get("País", "Desconocido") or "Desconocido"
    liga = b.get("Liga", "Desconocida") or "Desconocida"
    key = f"{pais} — {liga}"
    league_counts[key] += 1

top_leagues_global = sorted(league_counts.items(), key=lambda x: -x[1])[:20]

# ── Agrupar bets por (estrategia, liga) ──────────────────────────────────────

# Estructura: bets_by_strategy[strategy][league_key] = [bet, ...]
bets_by_strategy = defaultdict(lambda: defaultdict(list))
bets_global_by_strategy = defaultdict(list)

for b in all_bets:
    strat = b.get("strategy", "unknown")
    pais = b.get("País", "Desconocido") or "Desconocido"
    liga = b.get("Liga", "Desconocida") or "Desconocida"
    league_key = f"{pais} — {liga}"
    bets_by_strategy[strat][league_key].append(b)
    bets_global_by_strategy[strat].append(b)

# ── Análisis por estrategia ──────────────────────────────────────────────────

BIAS_THRESHOLD_PCT = 40.0  # Si una liga aporta >40% del P/L ganado de la estrategia → sesgada

strategy_analysis = {}

for strat, strat_bets_all in bets_global_by_strategy.items():
    global_stats = compute_group_stats(strat_bets_all)
    global_pl = global_stats["pl"]

    # Ordenar ligas por N de bets
    leagues_in_strat = bets_by_strategy[strat]
    league_stats_list = []
    for league_key, league_bets in leagues_in_strat.items():
        stats = compute_group_stats(league_bets)
        stats["league"] = league_key
        stats["n_matches_pct"] = round(stats["n"] / global_stats["n"] * 100, 1) if global_stats["n"] > 0 else 0
        # % del P/L total que aporta esta liga
        stats["pl_contribution_pct"] = round(stats["pl"] / global_pl * 100, 1) if global_pl != 0 else 0
        league_stats_list.append(stats)

    league_stats_list.sort(key=lambda x: -x["n"])

    # Top 5 ligas por N
    top5 = league_stats_list[:5]

    # Detección de sesgo: ¿alguna liga aporta >BIAS_THRESHOLD_PCT del P/L total?
    bias_flags = []
    total_winning_pl = sum(b["pl"] for b in strat_bets_all if b["pl"] > 0)
    for ls in league_stats_list:
        league_winning_pl = sum(b["pl"] for b in leagues_in_strat[ls["league"]] if b["pl"] > 0)
        if total_winning_pl > 0:
            league_win_pct = league_winning_pl / total_winning_pl * 100
        else:
            league_win_pct = 0.0
        ls["winning_pl_contribution_pct"] = round(league_win_pct, 1)
        if league_win_pct > BIAS_THRESHOLD_PCT and ls["n"] >= 5:
            bias_flags.append({
                "league": ls["league"],
                "n": ls["n"],
                "winning_pl_pct": round(league_win_pct, 1),
                "roi_pct": ls["roi_pct"],
                "wr_pct": ls["wr_pct"],
            })

    # Calcular stats SIN la liga más sesgada (si existe)
    if bias_flags:
        top_biased_league = bias_flags[0]["league"]
        bets_without_bias = [b for b in strat_bets_all if f"{b.get('País','?')} — {b.get('Liga','?')}" != top_biased_league]
        stats_without_bias = compute_group_stats(bets_without_bias)
    else:
        top_biased_league = None
        stats_without_bias = None

    strategy_analysis[strat] = {
        "global": global_stats,
        "n_leagues": len(leagues_in_strat),
        "top5_leagues": top5,
        "all_leagues": league_stats_list,
        "bias_flags": bias_flags,
        "is_biased": len(bias_flags) > 0,
        "top_biased_league": top_biased_league,
        "stats_without_top_bias": stats_without_bias,
    }

# ── Construir output final ────────────────────────────────────────────────────

output = {
    "total_bets": len(all_bets),
    "total_strategies_with_bets": len(strategy_analysis),
    "dataset_distribution": {
        "top20_leagues_by_bets": [{"league": k, "n_bets": v} for k, v in top_leagues_global],
        "total_leagues": len(league_counts),
    },
    "strategy_analysis": strategy_analysis,
    "summary": {
        "biased_strategies": [s for s, a in strategy_analysis.items() if a["is_biased"]],
        "clean_strategies": [s for s, a in strategy_analysis.items() if not a["is_biased"]],
    },
}

# ── Guardar JSON ──────────────────────────────────────────────────────────────

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "league_analysis_results.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\nResultados guardados en: {output_path}", flush=True)

# ── Reporte en stdout ─────────────────────────────────────────────────────────

print("\n" + "="*80)
print("DISTRIBUCIÓN DEL DATASET — TOP 20 LIGAS POR BETS")
print("="*80)
for item in top_leagues_global:
    print(f"  {item[0]:<45} {item[1]:>5} bets")

print(f"\nTotal ligas en dataset: {len(league_counts)}")

print("\n" + "="*80)
print("ANÁLISIS POR ESTRATEGIA")
print("="*80)

# Ordenar estrategias por N global desc
sorted_strats = sorted(strategy_analysis.items(), key=lambda x: -x[1]["global"]["n"])

for strat, analysis in sorted_strats:
    g = analysis["global"]
    print(f"\n{'─'*70}")
    print(f"ESTRATEGIA: {strat}")
    print(f"  Global: N={g['n']:>4}  WR={g['wr_pct']:>5.1f}%  ROI={g['roi_pct']:>6.1f}%  P/L={g['pl']:>8.2f}  CI95_low={g['ci95_low']:.1f}%")
    print(f"  Ligas distintas: {analysis['n_leagues']}")
    print(f"  Top 5 ligas por N:")
    for lg in analysis["top5_leagues"]:
        bias_marker = " *** SESGADA" if lg["winning_pl_contribution_pct"] > BIAS_THRESHOLD_PCT else ""
        print(f"    {lg['league']:<45} N={lg['n']:>4}  WR={lg['wr_pct']:>5.1f}%  ROI={lg['roi_pct']:>6.1f}%  PL%={lg['pl_contribution_pct']:>6.1f}%  WinPL%={lg['winning_pl_contribution_pct']:>5.1f}%{bias_marker}")
    if analysis["is_biased"]:
        print(f"  *** SESGADA: {analysis['top_biased_league']}")
        if analysis["stats_without_top_bias"]:
            sw = analysis["stats_without_top_bias"]
            print(f"      Sin esa liga: N={sw['n']}  WR={sw['wr_pct']}%  ROI={sw['roi_pct']}%  P/L={sw['pl']}")

print("\n" + "="*80)
print("RESUMEN SESGO")
print("="*80)
print(f"\nEstrategias SESGADAS ({len(output['summary']['biased_strategies'])}):")
for s in output["summary"]["biased_strategies"]:
    a = strategy_analysis[s]
    print(f"  {s:<30} → liga dominante: {a['top_biased_league']} ({a['bias_flags'][0]['winning_pl_pct']:.1f}% del P/L ganado)")

print(f"\nEstrategias LIMPIAS ({len(output['summary']['clean_strategies'])}):")
for s in output["summary"]["clean_strategies"]:
    g = strategy_analysis[s]["global"]
    print(f"  {s:<30}  N={g['n']:>4}  ROI={g['roi_pct']:>6.1f}%")

print("\nDone.", flush=True)