"""
Análisis profundo: distancia al último gol en estrategias CS.

Investiga:
1. Si el efecto 0-5min se debe a odds más altas (no a mejor WR real)
2. Granularidad fina en el rango 0-15 min
3. IC95% por bucket para ver significancia estadística
4. Análisis por estrategia individual
5. Propuesta de parametrización para bt_optimizer
"""

import sys, os, json, math
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
os.chdir(ROOT / "betfair_scraper" / "dashboard" / "backend")

from utils.csv_reader import analyze_cartera, _to_float
from utils.csv_loader import _get_all_finished_matches

CS_STRATEGIES = ["cs_close", "cs_one_goal", "cs_11", "cs_20", "cs_big_lead"]


def wilson_ci(wins, n, z=1.96):
    """Intervalo de confianza Wilson al 95%."""
    if n == 0:
        return 0, 0
    p = wins / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return round((centre - margin) * 100, 1), round((centre + margin) * 100, 1)


def find_last_goal_minute(rows, trigger_min):
    trigger_idx = 0
    best_diff = float('inf')
    for i, r in enumerate(rows):
        m = _to_float(r.get("minuto", ""))
        if m is None:
            continue
        diff = abs(float(m) - trigger_min)
        if diff < best_diff:
            best_diff = diff
            trigger_idx = i

    for i in range(trigger_idx, 0, -1):
        curr_gl = _to_float(rows[i].get("goles_local", ""))
        curr_gv = _to_float(rows[i].get("goles_visitante", ""))
        prev_gl = _to_float(rows[i - 1].get("goles_local", ""))
        prev_gv = _to_float(rows[i - 1].get("goles_visitante", ""))

        if any(v is None for v in [curr_gl, curr_gv, prev_gl, prev_gv]):
            continue

        if int(curr_gl) + int(curr_gv) > int(prev_gl) + int(prev_gv):
            goal_min = _to_float(rows[i].get("minuto", ""))
            if goal_min is not None:
                return float(goal_min), trigger_min - float(goal_min)

    return None, None


def main():
    print("Cargando datos...")
    result = analyze_cartera()
    all_bets = result.get("bets", [])
    cs_bets = [b for b in all_bets if b.get("strategy", "") in CS_STRATEGIES]

    finished = _get_all_finished_matches()
    rows_by_match = {m["match_id"]: m.get("rows", []) for m in finished}

    enriched = []
    for bet in cs_bets:
        rows = rows_by_match.get(bet.get("match_id", ""), [])
        if not rows:
            continue
        last_gm, mins_since = find_last_goal_minute(rows, bet.get("minuto", 0))
        enriched.append({**bet, "last_goal_min": last_gm, "mins_since_goal": mins_since})

    with_goal = [r for r in enriched if r["mins_since_goal"] is not None]
    without_goal = [r for r in enriched if r["mins_since_goal"] is None]

    print(f"CS bets: {len(enriched)} (con gol previo: {len(with_goal)}, sin gol: {len(without_goal)})")

    # ══════════════════════════════════════════════════════════════════
    # 1. DESGLOSE ODDS: ¿El ROI alto en 0-5 min es por odds más altas?
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("1. ODDS PROMEDIO POR BUCKET — ¿el ROI es por mejores odds o mejor WR?")
    print("=" * 90)

    fine_buckets = [
        ("0-3 min",   0,  3),
        ("3-5 min",   3,  5),
        ("5-7 min",   5,  7),
        ("7-10 min",  7, 10),
        ("10-15 min", 10, 15),
        ("15-25 min", 15, 25),
        ("25+ min",   25, 999),
    ]

    print(f"\n  {'Bucket':<12} {'N':>5} {'WR%':>7} {'ROI%':>8} {'AvgOdds':>8} {'MedOdds':>8} {'AvgPL':>8}  {'IC95%':>14}")
    print(f"  {'-'*80}")

    for label, lo, hi in fine_buckets:
        subset = [r for r in with_goal if lo <= r["mins_since_goal"] < hi]
        n = len(subset)
        if n == 0:
            print(f"  {label:<12} {0:>5}   ---")
            continue
        wins = sum(1 for r in subset if r["won"])
        total_pl = sum(r["pl"] for r in subset)
        odds_list = [r.get("back_odds", 0) for r in subset if r.get("back_odds", 0) > 0]
        avg_odds = sum(odds_list) / len(odds_list) if odds_list else 0
        sorted_odds = sorted(odds_list)
        med_odds = sorted_odds[len(sorted_odds) // 2] if sorted_odds else 0
        ci_lo, ci_hi = wilson_ci(wins, n)
        print(f"  {label:<12} {n:>5} {wins/n*100:>6.1f}% {total_pl/n*100:>7.1f}% {avg_odds:>7.2f} {med_odds:>7.2f} {total_pl/n:>7.3f}  [{ci_lo:>5.1f}-{ci_hi:>5.1f}]")

    # ══════════════════════════════════════════════════════════════════
    # 2. POR ESTRATEGIA con granularidad fina
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("2. POR ESTRATEGIA — buckets finos + odds + IC95%")
    print("=" * 90)

    for strat in CS_STRATEGIES:
        sw = [r for r in with_goal if r["strategy"] == strat]
        if not sw:
            continue

        n_total = len(sw)
        wr_total = sum(1 for r in sw if r["won"]) / n_total * 100
        roi_total = sum(r["pl"] for r in sw) / n_total * 100

        print(f"\n  {'='*70}")
        print(f"  {strat.upper()} (N={n_total}, WR={wr_total:.1f}%, ROI={roi_total:.1f}%)")
        print(f"  {'='*70}")

        strat_buckets = [
            ("0-5 min",   0,  5),
            ("5-10 min",  5, 10),
            ("10-20 min", 10, 20),
            ("20+ min",   20, 999),
        ]

        print(f"  {'Bucket':<12} {'N':>5} {'WR%':>7} {'ROI%':>8} {'AvgOdds':>8}  {'IC95%':>14}")
        print(f"  {'-'*60}")

        for label, lo, hi in strat_buckets:
            subset = [r for r in sw if lo <= r["mins_since_goal"] < hi]
            n = len(subset)
            if n == 0:
                print(f"  {label:<12} {0:>5}   ---")
                continue
            wins = sum(1 for r in subset if r["won"])
            total_pl = sum(r["pl"] for r in subset)
            odds_list = [r.get("back_odds", 0) for r in subset if r.get("back_odds", 0) > 0]
            avg_odds = sum(odds_list) / len(odds_list) if odds_list else 0
            ci_lo, ci_hi = wilson_ci(wins, n)
            print(f"  {label:<12} {n:>5} {wins/n*100:>6.1f}% {total_pl/n*100:>7.1f}% {avg_odds:>7.2f}  [{ci_lo:>5.1f}-{ci_hi:>5.1f}]")

    # ══════════════════════════════════════════════════════════════════
    # 3. ANÁLISIS DE FILTRO: ¿qué pasa si EXCLUIMOS el bucket 5-10?
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("3. SIMULACIÓN: ¿Qué pasa si excluimos el rango 5-10 min?")
    print("=" * 90)

    all_cs = enriched  # incluye sin gol previo
    base_n = len(all_cs)
    base_wins = sum(1 for r in all_cs if r["won"])
    base_pl = sum(r["pl"] for r in all_cs)

    # Excluir 5-10
    filtered = [r for r in all_cs if r["mins_since_goal"] is None or
                r["mins_since_goal"] < 5 or r["mins_since_goal"] >= 10]
    filt_n = len(filtered)
    filt_wins = sum(1 for r in filtered if r["won"])
    filt_pl = sum(r["pl"] for r in filtered)

    print(f"\n  {'':20} {'N':>6} {'Wins':>6} {'WR%':>7} {'ROI%':>8} {'Total PL':>10}")
    print(f"  {'-'*60}")
    print(f"  {'Sin filtro':<20} {base_n:>6} {base_wins:>6} {base_wins/base_n*100:>6.1f}% {base_pl/base_n*100:>7.1f}% {base_pl:>9.2f}")
    print(f"  {'Excl. 5-10 min':<20} {filt_n:>6} {filt_wins:>6} {filt_wins/filt_n*100:>6.1f}% {filt_pl/filt_n*100:>7.1f}% {filt_pl:>9.2f}")

    excl_5_10 = [r for r in with_goal if 5 <= r["mins_since_goal"] < 10]
    if excl_5_10:
        en = len(excl_5_10)
        ew = sum(1 for r in excl_5_10 if r["won"])
        epl = sum(r["pl"] for r in excl_5_10)
        print(f"  {'Solo 5-10 min':<20} {en:>6} {ew:>6} {ew/en*100:>6.1f}% {epl/en*100:>7.1f}% {epl:>9.2f}")

    # ══════════════════════════════════════════════════════════════════
    # 4. UMBRAL como parámetro continuo — sweep completo
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("4. SWEEP: minSinceLastGoal >= X para todas las CS con gol previo")
    print("=" * 90)
    print("   (Nota: se mantienen apuestas sin gol previo siempre)")

    print(f"\n  {'Umbral':<10} {'N':>6} {'WR%':>7} {'ROI%':>8} {'PL':>8} {'IC95_lo':>8}")
    print(f"  {'-'*50}")

    # Sin filtro
    all_n = len(enriched)
    all_w = sum(1 for r in enriched if r["won"])
    all_pl = sum(r["pl"] for r in enriched)
    ci_lo, _ = wilson_ci(all_w, all_n)
    print(f"  {'ninguno':<10} {all_n:>6} {all_w/all_n*100:>6.1f}% {all_pl/all_n*100:>7.1f}% {all_pl:>7.1f} {ci_lo:>7.1f}")

    for t in range(1, 21):
        kept = [r for r in enriched if r["mins_since_goal"] is None or r["mins_since_goal"] >= t]
        n = len(kept)
        if n < 20:
            continue
        wins = sum(1 for r in kept if r["won"])
        pl = sum(r["pl"] for r in kept)
        ci_lo, _ = wilson_ci(wins, n)
        marker = " <--" if t in [5, 7, 10] else ""
        print(f"  >= {t:>2} min  {n:>6} {wins/n*100:>6.1f}% {pl/n*100:>7.1f}% {pl:>7.1f} {ci_lo:>7.1f}{marker}")

    # ══════════════════════════════════════════════════════════════════
    # 5. ¿El efecto es por el TIPO de gol? (equipo que marcó vs el que no)
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("5. ¿QUIÉN MARCÓ EL ÚLTIMO GOL importa?")
    print("=" * 90)
    print("   (¿Es peor si el equipo con más goles acaba de anotar vs empate reciente?)")

    # Para esto necesitamos saber el score en el trigger y cuál equipo anotó
    for strat in CS_STRATEGIES:
        sw = [r for r in with_goal if r["strategy"] == strat]
        if len(sw) < 20:
            continue

        # Determinar si el último gol fue "igualador" (empate) o "ventajista" (amplió diferencia)
        eq_bets = []  # gol igualó el marcador
        lead_bets = []  # gol amplió/creó ventaja

        for bet in sw:
            score = bet.get("score_bet", "")
            if not score or "-" not in score:
                continue
            try:
                gl, gv = int(score.split("-")[0]), int(score.split("-")[1])
            except (ValueError, IndexError):
                continue

            rows = rows_by_match.get(bet.get("match_id", ""), [])
            if not rows:
                continue

            # Buscar el score ANTES del último gol
            trigger_idx = 0
            best_diff = float('inf')
            for i, r in enumerate(rows):
                m = _to_float(r.get("minuto", ""))
                if m is None:
                    continue
                diff = abs(float(m) - bet.get("minuto", 0))
                if diff < best_diff:
                    best_diff = diff
                    trigger_idx = i

            for i in range(trigger_idx, 0, -1):
                curr_gl = _to_float(rows[i].get("goles_local", ""))
                curr_gv = _to_float(rows[i].get("goles_visitante", ""))
                prev_gl = _to_float(rows[i - 1].get("goles_local", ""))
                prev_gv = _to_float(rows[i - 1].get("goles_visitante", ""))

                if any(v is None for v in [curr_gl, curr_gv, prev_gl, prev_gv]):
                    continue

                if int(curr_gl) + int(curr_gv) > int(prev_gl) + int(prev_gv):
                    # Score después del gol
                    after_gl, after_gv = int(curr_gl), int(curr_gv)
                    if after_gl == after_gv:
                        eq_bets.append(bet)
                    else:
                        lead_bets.append(bet)
                    break

        if eq_bets and lead_bets:
            eq_n = len(eq_bets)
            eq_w = sum(1 for b in eq_bets if b["won"])
            eq_pl = sum(b["pl"] for b in eq_bets)
            ld_n = len(lead_bets)
            ld_w = sum(1 for b in lead_bets if b["won"])
            ld_pl = sum(b["pl"] for b in lead_bets)

            print(f"\n  {strat}:")
            print(f"    Gol igualador (empató):  N={eq_n:>4}, WR={eq_w/eq_n*100:>5.1f}%, ROI={eq_pl/eq_n*100:>6.1f}%")
            print(f"    Gol ventajista (lideró): N={ld_n:>4}, WR={ld_w/ld_n*100:>5.1f}%, ROI={ld_pl/ld_n*100:>6.1f}%")

    # ══════════════════════════════════════════════════════════════════
    # 6. PROPUESTA FINAL
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 90)
    print("6. PROPUESTA PARA bt_optimizer")
    print("=" * 90)
    print("""
  Los datos NO soportan un filtro simple "excluir goles recientes".
  El bucket 0-5 min tiene el MEJOR rendimiento (odds infladas por volatilidad).
  El bucket 5-10 min es el peor (odds ya ajustadas, momentum aún activo).

  PROPUESTA: Añadir parámetro `minSinceLastGoal` al grid search del optimizer,
  con valores de búsqueda: [0, 3, 5, 7, 10, 15]
  - 0 = sin filtro (actual)
  - El optimizer decide por estrategia cuál umbral maximiza ROI/WR

  Esto permite que cada estrategia CS tenga su propio umbral óptimo,
  y si el optimizer elige 0, significa que el filtro no ayuda.

  Implementación:
  1. Añadir 'minSinceLastGoal' a cartera_config.json (default: 0)
  2. Cada _detect_cs_*_trigger() calcula distancia al último gol
  3. Si mins_since < cfg['minSinceLastGoal'], no dispara
  4. bt_optimizer incluye el parámetro en su grid search
""")


if __name__ == "__main__":
    main()
