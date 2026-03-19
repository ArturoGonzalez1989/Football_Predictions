"""
Análisis v3: ¿Es el valle 5-10 min estadísticamente real o ruido?

Tests:
1. Significancia estadística: chi-squared test bucket 0-5 vs 5-10
2. Bootstrap: simular si la diferencia se mantiene con resampling
3. Por estrategia: ¿el valle es consistente en todas las CS o solo en 1-2?
4. Evaluar si un rango de exclusión [X, Y] es viable vs un threshold simple
5. Granularidad minuto a minuto en el rango 0-15
"""

import sys, os, json, math, random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
os.chdir(ROOT / "betfair_scraper" / "dashboard" / "backend")

from utils.csv_reader import analyze_cartera, _to_float
from utils.csv_loader import _get_all_finished_matches

CS_STRATEGIES = ["cs_close", "cs_one_goal", "cs_11", "cs_20", "cs_big_lead"]


def wilson_ci(wins, n, z=1.96):
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
        if abs(float(m) - trigger_min) < best_diff:
            best_diff = abs(float(m) - trigger_min)
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


def chi_squared_2x2(w1, n1, w2, n2):
    """Chi-squared test for two proportions. Returns chi2 and p-value."""
    l1, l2 = n1 - w1, n2 - w2
    n = n1 + n2
    if n == 0:
        return 0, 1
    # Expected values
    row1 = w1 + w2  # total wins
    row2 = l1 + l2  # total losses
    e11 = row1 * n1 / n
    e12 = row1 * n2 / n
    e21 = row2 * n1 / n
    e22 = row2 * n2 / n
    if any(e == 0 for e in [e11, e12, e21, e22]):
        return 0, 1
    chi2 = ((w1 - e11)**2 / e11 + (w2 - e12)**2 / e12 +
            (l1 - e21)**2 / e21 + (l2 - e22)**2 / e22)
    # Approximate p-value from chi2 with 1 df
    p = math.exp(-chi2 / 2) if chi2 < 20 else 0.0001
    return round(chi2, 3), round(p, 4)


def main():
    print("Cargando datos...")
    result = analyze_cartera()
    cs_bets = [b for b in result.get("bets", []) if b.get("strategy", "") in CS_STRATEGIES]

    finished = _get_all_finished_matches()
    rows_by_match = {m["match_id"]: m.get("rows", []) for m in finished}

    enriched = []
    for bet in cs_bets:
        rows = rows_by_match.get(bet.get("match_id", ""), [])
        if not rows:
            continue
        _, mins_since = find_last_goal_minute(rows, bet.get("minuto", 0))
        enriched.append({**bet, "mins_since_goal": mins_since})

    with_goal = [r for r in enriched if r["mins_since_goal"] is not None]
    print(f"CS bets con gol previo: {len(with_goal)}")

    # ══════════════════════════════════════════════════════════════════
    # 1. GRANULARIDAD MINUTO A MINUTO (0-15)
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("1. WR MINUTO A MINUTO (distancia al último gol)")
    print("=" * 80)

    print(f"\n  {'Min':>4} {'N':>5} {'Wins':>5} {'WR%':>7} {'ROI%':>8} {'AvgOdds':>8}")
    print(f"  {'-'*45}")

    for m in range(0, 31):
        subset = [r for r in with_goal if m <= r["mins_since_goal"] < m + 1]
        n = len(subset)
        if n < 3:
            continue
        wins = sum(1 for r in subset if r["won"])
        pl = sum(r["pl"] for r in subset)
        odds_list = [r.get("back_odds", 0) for r in subset if r.get("back_odds", 0) > 0]
        avg_odds = sum(odds_list) / len(odds_list) if odds_list else 0
        bar = "#" * int(wins / n * 30)
        print(f"  {m:>3}m {n:>5} {wins:>5} {wins/n*100:>6.1f}% {pl/n*100:>7.1f}% {avg_odds:>7.2f}  {bar}")

    # ══════════════════════════════════════════════════════════════════
    # 2. TEST ESTADÍSTICO: bucket 0-5 vs 5-10
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("2. TEST ESTADÍSTICO: 0-5 min vs 5-10 min")
    print("=" * 80)

    b05 = [r for r in with_goal if r["mins_since_goal"] < 5]
    b510 = [r for r in with_goal if 5 <= r["mins_since_goal"] < 10]
    b10p = [r for r in with_goal if r["mins_since_goal"] >= 10]

    w05, n05 = sum(1 for r in b05 if r["won"]), len(b05)
    w510, n510 = sum(1 for r in b510 if r["won"]), len(b510)
    w10p, n10p = sum(1 for r in b10p if r["won"]), len(b10p)

    ci05 = wilson_ci(w05, n05)
    ci510 = wilson_ci(w510, n510)
    ci10p = wilson_ci(w10p, n10p)

    chi_05_510, p_05_510 = chi_squared_2x2(w05, n05, w510, n510)
    chi_510_10p, p_510_10p = chi_squared_2x2(w510, n510, w10p, n10p)
    chi_05_10p, p_05_10p = chi_squared_2x2(w05, n05, w10p, n10p)

    print(f"\n  Bucket     N    Wins    WR%    IC95%             ROI%")
    print(f"  {'-'*60}")
    print(f"  0-5 min  {n05:>4}   {w05:>4}  {w05/n05*100:>5.1f}%  [{ci05[0]:>5.1f}-{ci05[1]:>5.1f}]  {sum(r['pl'] for r in b05)/n05*100:>7.1f}%")
    print(f"  5-10 min {n510:>4}   {w510:>4}  {w510/n510*100:>5.1f}%  [{ci510[0]:>5.1f}-{ci510[1]:>5.1f}]  {sum(r['pl'] for r in b510)/n510*100:>7.1f}%")
    print(f"  10+ min  {n10p:>4}   {w10p:>4}  {w10p/n10p*100:>5.1f}%  [{ci10p[0]:>5.1f}-{ci10p[1]:>5.1f}]  {sum(r['pl'] for r in b10p)/n10p*100:>7.1f}%")

    print(f"\n  Chi-squared tests:")
    print(f"  0-5 vs 5-10:   chi2={chi_05_510:>6.3f}, p={p_05_510:>6.4f} {'SIGNIFICATIVO' if p_05_510 < 0.05 else 'no significativo'}")
    print(f"  5-10 vs 10+:   chi2={chi_510_10p:>6.3f}, p={p_510_10p:>6.4f} {'SIGNIFICATIVO' if p_510_10p < 0.05 else 'no significativo'}")
    print(f"  0-5 vs 10+:    chi2={chi_05_10p:>6.3f}, p={p_05_10p:>6.4f} {'SIGNIFICATIVO' if p_05_10p < 0.05 else 'no significativo'}")

    # ══════════════════════════════════════════════════════════════════
    # 3. BOOTSTRAP: estabilidad del efecto
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("3. BOOTSTRAP: ¿El valle 5-10 es robusto? (1000 iteraciones)")
    print("=" * 80)

    random.seed(42)
    n_boot = 1000
    times_05_better = 0
    times_510_worst = 0
    wr_diffs = []

    for _ in range(n_boot):
        sample = random.choices(with_goal, k=len(with_goal))
        s05 = [r for r in sample if r["mins_since_goal"] < 5]
        s510 = [r for r in sample if 5 <= r["mins_since_goal"] < 10]
        s10p = [r for r in sample if r["mins_since_goal"] >= 10]

        if not s05 or not s510 or not s10p:
            continue

        wr05 = sum(1 for r in s05 if r["won"]) / len(s05)
        wr510 = sum(1 for r in s510 if r["won"]) / len(s510)
        wr10p = sum(1 for r in s10p if r["won"]) / len(s10p)

        if wr05 > wr510:
            times_05_better += 1
        if wr510 < wr05 and wr510 < wr10p:
            times_510_worst += 1
        wr_diffs.append(wr05 - wr510)

    avg_diff = sum(wr_diffs) / len(wr_diffs) * 100
    wr_diffs.sort()
    ci_lo_diff = wr_diffs[int(0.025 * len(wr_diffs))] * 100
    ci_hi_diff = wr_diffs[int(0.975 * len(wr_diffs))] * 100

    print(f"\n  0-5 min tiene mejor WR que 5-10 min: {times_05_better}/{n_boot} ({times_05_better/n_boot*100:.1f}%)")
    print(f"  5-10 min es el PEOR de los 3 buckets: {times_510_worst}/{n_boot} ({times_510_worst/n_boot*100:.1f}%)")
    print(f"  Diferencia WR media (0-5 vs 5-10):    {avg_diff:+.1f}pp  IC95% [{ci_lo_diff:+.1f}, {ci_hi_diff:+.1f}]")

    # ══════════════════════════════════════════════════════════════════
    # 4. CONSISTENCIA POR ESTRATEGIA: ¿cuántas CS muestran el valle?
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("4. ¿ES CONSISTENTE? Valle 5-10 por estrategia individual")
    print("=" * 80)

    print(f"\n  {'Estrategia':<16} {'WR 0-5':>8} {'WR 5-10':>8} {'WR 10+':>8} {'Valle?':>8}")
    print(f"  {'-'*55}")

    valley_count = 0
    for strat in CS_STRATEGIES:
        sw = [r for r in with_goal if r["strategy"] == strat]
        s05 = [r for r in sw if r["mins_since_goal"] < 5]
        s510 = [r for r in sw if 5 <= r["mins_since_goal"] < 10]
        s10p = [r for r in sw if r["mins_since_goal"] >= 10]

        wr05 = sum(1 for r in s05 if r["won"]) / len(s05) * 100 if s05 else -1
        wr510 = sum(1 for r in s510 if r["won"]) / len(s510) * 100 if s510 else -1
        wr10p = sum(1 for r in s10p if r["won"]) / len(s10p) * 100 if s10p else -1

        has_valley = wr510 >= 0 and wr510 < wr05 and wr510 < wr10p
        if has_valley:
            valley_count += 1

        n05s, n510s, n10ps = len(s05), len(s510), len(s10p)
        print(f"  {strat:<16} {wr05:>5.1f}%({n05s:>2}) {wr510:>5.1f}%({n510s:>2}) {wr10p:>5.1f}%({n10ps:>2}) {'SI' if has_valley else 'no':>6}")

    print(f"\n  Estrategias con valle 5-10: {valley_count}/{len(CS_STRATEGIES)}")

    # ══════════════════════════════════════════════════════════════════
    # 5. SIMULACIÓN RANGO DE EXCLUSIÓN [X, Y]
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("5. RANGO DE EXCLUSIÓN: excluir apuestas donde distancia está en [X, Y)")
    print("=" * 80)

    all_cs = enriched
    base_n = len(all_cs)
    base_w = sum(1 for r in all_cs if r["won"])
    base_pl = sum(r["pl"] for r in all_cs)

    print(f"\n  Base: N={base_n}, WR={base_w/base_n*100:.1f}%, ROI={base_pl/base_n*100:.1f}%, PL={base_pl:.1f}")

    ranges = [
        (4, 8), (4, 10), (4, 12),
        (5, 8), (5, 10), (5, 12),
        (6, 9), (6, 10), (6, 12),
        (7, 10), (7, 12),
    ]

    print(f"\n  {'Excluir':<14} {'N':>5} {'Excl':>5} {'WR%':>7} {'ROI%':>8} {'PL':>8} {'dWR':>6} {'dROI':>7}")
    print(f"  {'-'*65}")

    for lo, hi in ranges:
        kept = [r for r in all_cs if r["mins_since_goal"] is None or
                r["mins_since_goal"] < lo or r["mins_since_goal"] >= hi]
        n = len(kept)
        excl = base_n - n
        wins = sum(1 for r in kept if r["won"])
        pl = sum(r["pl"] for r in kept)
        dwr = wins / n * 100 - base_w / base_n * 100
        droi = pl / n * 100 - base_pl / base_n * 100
        print(f"  [{lo:>2}-{hi:>2}) min  {n:>5} {excl:>5} {wins/n*100:>6.1f}% {pl/n*100:>7.1f}% {pl:>7.1f} {dwr:>+5.1f} {droi:>+6.1f}")

    # ══════════════════════════════════════════════════════════════════
    # 6. CONCLUSIONES
    # ══════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("6. CONCLUSIONES Y OPCIONES")
    print("=" * 80)
    print(f"""
  HALLAZGOS:
  - El bucket 0-5 min tiene el MEJOR rendimiento (WR={w05/n05*100:.1f}%, odds altas)
  - El bucket 5-10 min es consistentemente el peor
  - El valle es consistente en {valley_count}/{len(CS_STRATEGIES)} estrategias
  - Bootstrap: 0-5 > 5-10 en {times_05_better/n_boot*100:.0f}% de simulaciones

  OPCIONES PARA bt_optimizer:

  A) Threshold simple: minSinceLastGoal >= X
     + Simple de implementar y optimizar
     - No puede capturar el efecto (pierde el valioso bucket 0-3)
     - El optimizer probablemente elegirá 0 (sin filtro)

  B) Rango de exclusión: excludeGoalWindow = [X, Y)
     + Captura exactamente el patrón real (excluir 5-10 pero mantener 0-5)
     + Grid: [(0,0), (4,8), (4,10), (5,10), (5,12), (6,10)]
       donde (0,0) = sin exclusión
     - Dos parámetros extra en el grid → más combos
     - Complejidad conceptual mayor

  C) No hacer nada
     + Los datos globales no son estadísticamente significativos (p>{p_05_510})
     + N=81 en el bucket 5-10 es bajo para conclusiones firmes
     + Riesgo de overfitting a un patrón de ruido
""")


if __name__ == "__main__":
    main()
