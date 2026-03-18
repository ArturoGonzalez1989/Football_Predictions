"""
Tier Analysis — Rendimiento por TIER de liga para todas las estrategias activas.
Agrupa las ligas en 4 tiers y detecta divergencias de rendimiento por segmento.

Uso: python auxiliar/tier_analysis.py
Salida: auxiliar/tier_analysis_results.json + reporte en stdout
"""
import sys
import os
import json
import math
from collections import defaultdict
import io

# Forzar UTF-8 en stdout (Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Añadir path del backend para importar csv_reader
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "betfair_scraper", "dashboard", "backend"))

print("Importando analyze_cartera()...", flush=True)
from utils.csv_reader import analyze_cartera

# -- Definición de tiers -------------------------------------------------------

TIER_MAP = {
    # TIER 1 — Ligas top europeas + Champions
    'tier1_europe': [
        'Premier League', 'La Liga', 'Bundesliga', 'Serie A', 'Ligue 1',
        'Champions League', 'Europa League', 'Conference League',
        'Eredivisie', 'Primeira Liga',
    ],
    # TIER 2 — Ligas europeas secundarias
    'tier2_europe': [
        'Championship', 'League One', 'League Two', 'National League',
        'Segunda División', 'Serie B', 'Ligue 2', 'Süper Lig',
        'Jupiler Pro League', 'Liga A', 'Superligaen', 'Super League',
        'Premiership', 'Eerste Divisie', 'Primera Liga Eslovena',
        'Copa del Rey', 'FA Cup', 'Coppa Italia', 'Copa Turca',
        '1st Division', 'League Two Escocesa', 'Challenge Cup',
        'Copa Escocesa', 'League One Escocesa', 'Championship Escocesa',
    ],
    # TIER 3 — Ligas sudamericanas
    'tier3_latam': [
        'Liga Argentina', 'Serie A Brasileña', 'Baiano', 'Carioca',
        'Copa do Brasil', 'Gaúcho', 'Goiano', 'Mineiro', 'Paulista Serie A1',
        'Pernambucano', 'Primera División', 'Liga Colombiana',
        'Serie A Ecuatoriana', 'Liga Uruguaya', 'Copa Argentina',
        'Copa Libertadores', 'Copa Sudamericana', 'CONCACAF Champions',
        'Liga de Expansión', 'Liga MX',
    ],
    # TIER 4 — Ligas asiáticas, africanas, medio oriente, otros
    'tier4_other': [
        'J-League', 'K1 League', 'Saudi Pro League', 'UAE Pro League',
        'China Super League', 'Indonesia Super League', 'Virsliga',
        'Qatar Stars League', 'Iran Pro League', 'Tanzania Premier League',
        'Zambia Superliga', 'Thailand Liga 2', 'MLS',
        'AFC Champions League', 'AFC Champions League 2',
        'FIFA Women WC Qualifiers', 'FIFA Women World Cup',
    ],
}

TIER_LABELS = {
    'tier1_europe': 'TIER 1 — Europa Top',
    'tier2_europe': 'TIER 2 — Europa Secundaria',
    'tier3_latam':  'TIER 3 — Latinoamérica',
    'tier4_other':  'TIER 4 — Asia/Africa/Otros',
    'unknown':      'UNKNOWN',
}

TIER_ORDER = ['tier1_europe', 'tier2_europe', 'tier3_latam', 'tier4_other', 'unknown']

# -- Helpers estadísticos ------------------------------------------------------

STAKE = 10.0


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


def assign_tier(liga_name):
    """
    Asigna un tier a un nombre de liga usando substring matching.
    Devuelve la clave del tier o 'unknown'.
    """
    if not liga_name or liga_name in ('Desconocida', ''):
        return 'unknown'
    for tier_key, liga_list in TIER_MAP.items():
        for pattern in liga_list:
            if pattern.lower() in liga_name.lower():
                return tier_key
    return 'unknown'


# -- Ejecutar backtest ---------------------------------------------------------

print("Ejecutando analyze_cartera() — esto puede tardar 30-60s...", flush=True)
result = analyze_cartera()
all_bets = result.get("bets", [])
print(f"Total bets obtenidos: {len(all_bets)}", flush=True)

# -- Mapear cada bet a su tier -------------------------------------------------

# Cada bet tiene: País, Liga, strategy, won, pl, match_id, minuto, odds, ...
for b in all_bets:
    liga = b.get("Liga", "") or ""
    b["_tier"] = assign_tier(liga)

# -- Distribución global por tier ---------------------------------------------

tier_global_bets = defaultdict(list)
for b in all_bets:
    tier_global_bets[b["_tier"]].append(b)

tier_global_stats = {}
for tier_key in TIER_ORDER:
    bets_in_tier = tier_global_bets.get(tier_key, [])
    stats = compute_group_stats(bets_in_tier)
    stats["pct_of_total"] = round(len(bets_in_tier) / len(all_bets) * 100, 1) if all_bets else 0
    tier_global_stats[tier_key] = stats

# -- Agrupar bets por (estrategia, tier) --------------------------------------

# bets_by_strat_tier[strategy][tier] = [bet, ...]
bets_by_strat_tier = defaultdict(lambda: defaultdict(list))
bets_global_by_strat = defaultdict(list)

for b in all_bets:
    strat = b.get("strategy", "unknown")
    tier = b["_tier"]
    bets_by_strat_tier[strat][tier].append(b)
    bets_global_by_strat[strat].append(b)

# -- Análisis por estrategia ---------------------------------------------------

DIVERGENCE_THRESHOLD = 15.0   # puntos porcentuales de ROI entre mejor y peor tier
MIN_N_FOR_TIER = 5             # N mínimo para considerar un tier en el análisis

strategy_tier_analysis = {}

for strat, strat_bets in bets_global_by_strat.items():
    global_stats = compute_group_stats(strat_bets)

    # Stats por tier
    tier_stats = {}
    for tier_key in TIER_ORDER:
        bets_in_tier = bets_by_strat_tier[strat].get(tier_key, [])
        stats = compute_group_stats(bets_in_tier)
        stats["pct_of_strategy"] = round(stats["n"] / global_stats["n"] * 100, 1) if global_stats["n"] > 0 else 0.0
        tier_stats[tier_key] = stats

    # Calcular mejor y peor tier (solo tiers con N >= MIN_N_FOR_TIER)
    valid_tiers = [(tk, ts) for tk, ts in tier_stats.items() if ts["n"] >= MIN_N_FOR_TIER]
    if valid_tiers:
        best_tier_key = max(valid_tiers, key=lambda x: x[1]["roi_pct"])[0]
        worst_tier_key = min(valid_tiers, key=lambda x: x[1]["roi_pct"])[0]
        best_roi = tier_stats[best_tier_key]["roi_pct"]
        worst_roi = tier_stats[worst_tier_key]["roi_pct"]
        roi_divergence = round(best_roi - worst_roi, 1)
    else:
        best_tier_key = None
        worst_tier_key = None
        roi_divergence = 0.0

    # Divergencia tier1 vs tier4 especificamente
    t1_stats = tier_stats.get("tier1_europe", {})
    t4_stats = tier_stats.get("tier4_other", {})
    t1_valid = t1_stats.get("n", 0) >= MIN_N_FOR_TIER
    t4_valid = t4_stats.get("n", 0) >= MIN_N_FOR_TIER
    if t1_valid and t4_valid:
        tier1_vs_tier4_diff = round(t1_stats["roi_pct"] - t4_stats["roi_pct"], 1)
    else:
        tier1_vs_tier4_diff = None

    has_divergence = roi_divergence >= DIVERGENCE_THRESHOLD

    strategy_tier_analysis[strat] = {
        "global": global_stats,
        "tier_stats": tier_stats,
        "best_tier": best_tier_key,
        "worst_tier": worst_tier_key,
        "roi_divergence_pp": roi_divergence,
        "has_significant_divergence": has_divergence,
        "tier1_vs_tier4_diff_pp": tier1_vs_tier4_diff,
        "n_tiers_with_min_n": len(valid_tiers),
    }

# -- Ranking por divergencia tier1 vs tier4 -----------------------------------

strategies_with_t1_t4 = [
    (strat, data["tier1_vs_tier4_diff_pp"])
    for strat, data in strategy_tier_analysis.items()
    if data["tier1_vs_tier4_diff_pp"] is not None
]
strategies_with_t1_t4.sort(key=lambda x: -abs(x[1]))

# -- Construir output final ----------------------------------------------------

output = {
    "total_bets": len(all_bets),
    "total_strategies": len(strategy_tier_analysis),
    "divergence_threshold_pp": DIVERGENCE_THRESHOLD,
    "min_n_for_tier": MIN_N_FOR_TIER,
    "global_tier_distribution": tier_global_stats,
    "strategy_tier_analysis": strategy_tier_analysis,
    "summary": {
        "strategies_with_divergence": [
            s for s, d in strategy_tier_analysis.items() if d["has_significant_divergence"]
        ],
        "strategies_without_divergence": [
            s for s, d in strategy_tier_analysis.items() if not d["has_significant_divergence"]
        ],
        "tier1_vs_tier4_ranking": [
            {"strategy": s, "tier1_vs_tier4_diff_pp": diff}
            for s, diff in strategies_with_t1_t4
        ],
    },
}

# -- Guardar JSON --------------------------------------------------------------

output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tier_analysis_results.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\nResultados guardados en: {output_path}", flush=True)

# -- Reporte en stdout ---------------------------------------------------------

print("\n" + "=" * 80)
print("DISTRIBUCIÓN GLOBAL DEL DATASET POR TIER")
print("=" * 80)
for tier_key in TIER_ORDER:
    label = TIER_LABELS[tier_key]
    gs = tier_global_stats[tier_key]
    print(f"  {label:<35}  N={gs['n']:>5}  {gs['pct_of_total']:>5.1f}%  WR={gs['wr_pct']:>5.1f}%  ROI={gs['roi_pct']:>6.1f}%  P/L={gs['pl']:>8.2f}")

print(f"\n  Total bets: {len(all_bets)}")

print("\n" + "=" * 80)
print("ANÁLISIS POR ESTRATEGIA — RENDIMIENTO POR TIER")
print("=" * 80)

# Ordenar estrategias por N global desc
sorted_strats = sorted(strategy_tier_analysis.items(), key=lambda x: -x[1]["global"]["n"])

for strat, analysis in sorted_strats:
    g = analysis["global"]
    div_marker = " [*** DIVERGENCIA]" if analysis["has_significant_divergence"] else ""
    print(f"\n{'-' * 72}")
    print(f"ESTRATEGIA: {strat}{div_marker}")
    print(f"  Global: N={g['n']:>4}  WR={g['wr_pct']:>5.1f}%  ROI={g['roi_pct']:>6.1f}%  P/L={g['pl']:>8.2f}  CI95_low={g['ci95_low']:.1f}%")
    print(f"  {'Tier':<35}  {'N':>5}  {'%Bets':>6}  {'WR%':>6}  {'ROI%':>7}  {'P/L':>8}")
    print(f"  {'-'*35}  {'-'*5}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*8}")
    for tier_key in TIER_ORDER:
        ts = analysis["tier_stats"][tier_key]
        if ts["n"] == 0:
            continue
        label = TIER_LABELS[tier_key]
        best_mark = " <-- MEJOR" if tier_key == analysis["best_tier"] else ""
        worst_mark = " <-- PEOR" if tier_key == analysis["worst_tier"] else ""
        marker = best_mark or worst_mark
        print(f"  {label:<35}  {ts['n']:>5}  {ts['pct_of_strategy']:>5.1f}%  {ts['wr_pct']:>5.1f}%  {ts['roi_pct']:>6.1f}%  {ts['pl']:>8.2f}{marker}")

    if analysis["tier1_vs_tier4_diff_pp"] is not None:
        diff = analysis["tier1_vs_tier4_diff_pp"]
        direction = "Tier1 > Tier4" if diff > 0 else "Tier4 > Tier1"
        print(f"  Divergencia Tier1 vs Tier4: {diff:+.1f}pp  ({direction})")

    if analysis["has_significant_divergence"] and analysis["best_tier"] and analysis["worst_tier"]:
        best_roi = analysis["tier_stats"][analysis["best_tier"]]["roi_pct"]
        worst_roi = analysis["tier_stats"][analysis["worst_tier"]]["roi_pct"]
        print(f"  *** Divergencia significativa: {TIER_LABELS[analysis['best_tier']]} ({best_roi:+.1f}%) "
              f"vs {TIER_LABELS[analysis['worst_tier']]} ({worst_roi:+.1f}%) = {analysis['roi_divergence_pp']:.1f}pp")

print("\n" + "=" * 80)
print(f"RANKING — DIVERGENCIA TIER1 vs TIER4 (ROI tier1 - ROI tier4)")
print("=" * 80)
if strategies_with_t1_t4:
    print(f"  {'Estrategia':<35}  {'T1-T4 (pp)':>10}  {'Dirección'}")
    print(f"  {'-'*35}  {'-'*10}  {'-'*20}")
    for strat, diff in strategies_with_t1_t4:
        direction = "Tier1 rinde MEJOR" if diff > 0 else "Tier4 rinde MEJOR"
        print(f"  {strat:<35}  {diff:>+10.1f}  {direction}")
else:
    print("  No hay estrategias con datos suficientes en tier1 y tier4 simultáneamente.")

print("\n" + "=" * 80)
print("ESTRATEGIAS CON DIVERGENCIA SIGNIFICATIVA (>= 15pp ROI entre tiers)")
print("=" * 80)
diverged = [(s, d) for s, d in sorted_strats if d["has_significant_divergence"]]
if diverged:
    for strat, analysis in diverged:
        best_key = analysis["best_tier"]
        worst_key = analysis["worst_tier"]
        best_ts = analysis["tier_stats"].get(best_key, {})
        worst_ts = analysis["tier_stats"].get(worst_key, {})
        print(f"\n  {strat}")
        print(f"    Mejor:  {TIER_LABELS.get(best_key,'?'):<35} N={best_ts.get('n',0):>4}  ROI={best_ts.get('roi_pct',0):>+7.1f}%")
        print(f"    Peor:   {TIER_LABELS.get(worst_key,'?'):<35} N={worst_ts.get('n',0):>4}  ROI={worst_ts.get('roi_pct',0):>+7.1f}%")
        print(f"    Spread: {analysis['roi_divergence_pp']:.1f}pp")
else:
    print("  Ninguna estrategia presenta divergencia significativa entre tiers.")

print("\n" + "=" * 80)
print("CONCLUSION — ¿MERECE SEGMENTAR EL PORTFOLIO POR TIER?")
print("=" * 80)

n_diverged = len(diverged)
n_total = len(strategy_tier_analysis)
pct_diverged = round(n_diverged / n_total * 100, 1) if n_total > 0 else 0

# Calcular ROI promedio por tier (ponderado por bets)
print(f"\n  Estrategias con divergencia significativa: {n_diverged}/{n_total} ({pct_diverged:.1f}%)")
print(f"\n  Rendimiento global por tier:")
for tier_key in TIER_ORDER:
    gs = tier_global_stats[tier_key]
    if gs["n"] > 0:
        label = TIER_LABELS[tier_key]
        print(f"    {label:<35}  N={gs['n']:>5}  ROI={gs['roi_pct']:>+7.1f}%  WR={gs['wr_pct']:>5.1f}%")

# Identificar el tier mas rentable globalmente
valid_tiers_global = [(tk, tier_global_stats[tk]) for tk in TIER_ORDER if tier_global_stats[tk]["n"] >= 20]
if valid_tiers_global:
    best_global = max(valid_tiers_global, key=lambda x: x[1]["roi_pct"])
    worst_global = min(valid_tiers_global, key=lambda x: x[1]["roi_pct"])
    spread_global = round(best_global[1]["roi_pct"] - worst_global[1]["roi_pct"], 1)
    print(f"\n  Mejor tier global:  {TIER_LABELS[best_global[0]]} (ROI={best_global[1]['roi_pct']:+.1f}%)")
    print(f"  Peor tier global:   {TIER_LABELS[worst_global[0]]} (ROI={worst_global[1]['roi_pct']:+.1f}%)")
    print(f"  Spread global:      {spread_global:.1f}pp")
    print()
    if spread_global >= 10.0:
        print("  VEREDICTO: SI merece segmentar por tier.")
        print("  El spread de ROI global entre tiers supera 10pp.")
        if pct_diverged >= 50:
            print(f"  Ademas, {pct_diverged:.0f}% de las estrategias muestran divergencia >= 15pp entre tiers.")
            print("  Recomendacion: considerar filtrar por tier en las estrategias mas divergentes.")
        else:
            print(f"  Solo {pct_diverged:.0f}% de estrategias muestran divergencia individual >= 15pp.")
            print("  Recomendacion: revisar el tier global y aplicar filtros selectivos.")
    else:
        print("  VEREDICTO: NO es urgente segmentar por tier.")
        print(f"  Spread global de ROI entre tiers = {spread_global:.1f}pp (umbral: 10pp).")
        if n_diverged > 0:
            print(f"  Aunque {n_diverged} estrategia(s) muestran divergencia individual, el efecto global es modesto.")

print("\nDone.", flush=True)
