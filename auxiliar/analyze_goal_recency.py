"""
Análisis: ¿Afecta la distancia al último gol al win rate de estrategias CS?

Hipótesis: Si el último gol fue muy reciente (< X minutos), el partido está
"caliente" (momentum del goleador o reacción del rival), haciendo que el
marcador sea más probable que cambie → peor WR para apuestas CS.

NO MODIFICA ningún fichero del sistema. Solo lee datos y calcula estadísticas.
"""

import sys, os, json
from pathlib import Path

# Setup paths para importar módulos del backend
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
os.chdir(ROOT / "betfair_scraper" / "dashboard" / "backend")

from utils.csv_reader import analyze_cartera, _to_float
from utils.csv_loader import _get_all_finished_matches, _read_csv_rows


# ── Estrategias CS ──────────────────────────────────────────────────
CS_STRATEGIES = ["cs_close", "cs_one_goal", "cs_11", "cs_20", "cs_big_lead", "cs_00"]


def find_last_goal_minute(rows, trigger_min):
    """
    Busca el minuto del último gol ANTES del trigger_min.
    Retorna (last_goal_minute, minutes_since_goal) o (None, None) si no hubo goles.
    """
    # Encontrar el índice más cercano al trigger_min
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

    # Recorrer hacia atrás buscando cambio de marcador
    for i in range(trigger_idx, 0, -1):
        curr_gl = _to_float(rows[i].get("goles_local", ""))
        curr_gv = _to_float(rows[i].get("goles_visitante", ""))
        prev_gl = _to_float(rows[i - 1].get("goles_local", ""))
        prev_gv = _to_float(rows[i - 1].get("goles_visitante", ""))

        if any(v is None for v in [curr_gl, curr_gv, prev_gl, prev_gv]):
            continue

        total_now = int(curr_gl) + int(curr_gv)
        total_prev = int(prev_gl) + int(prev_gv)

        if total_now > total_prev:
            goal_min = _to_float(rows[i].get("minuto", ""))
            if goal_min is not None:
                return float(goal_min), trigger_min - float(goal_min)

    return None, None


def main():
    print("Cargando partidos y ejecutando backtest...")

    # 1) Obtener todas las apuestas del BT actual (usa config real)
    result = analyze_cartera()
    all_bets = result.get("bets", [])

    # 2) Filtrar solo CS
    cs_bets = [b for b in all_bets if b.get("strategy", "") in CS_STRATEGIES]
    print(f"Total apuestas BT: {len(all_bets)}")
    print(f"Apuestas CS: {len(cs_bets)}")

    if not cs_bets:
        print("No hay apuestas CS. ¿Están habilitadas en cartera_config.json?")
        return

    # 3) Cargar filas de cada partido para calcular distancia al gol
    finished = _get_all_finished_matches()
    rows_by_match = {m["match_id"]: m.get("rows", []) for m in finished}

    # 4) Enriquecer cada apuesta con min_since_last_goal
    enriched = []
    for bet in cs_bets:
        match_id = bet.get("match_id", "")
        trigger_min = bet.get("minuto", 0)
        rows = rows_by_match.get(match_id, [])

        if not rows:
            continue

        last_goal_min, mins_since = find_last_goal_minute(rows, trigger_min)
        enriched.append({
            **bet,
            "last_goal_min": last_goal_min,
            "mins_since_goal": mins_since,
        })

    print(f"Apuestas CS enriquecidas: {len(enriched)}")

    # Separar con/sin gol previo
    with_goal = [r for r in enriched if r["mins_since_goal"] is not None]
    without_goal = [r for r in enriched if r["mins_since_goal"] is None]

    # ── ANÁLISIS GLOBAL ─────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("ANÁLISIS GLOBAL: WR por distancia al último gol (todas las CS)")
    print("=" * 80)
    print(f"\n  Con gol previo: {len(with_goal)}  |  Sin gol (0-0): {len(without_goal)}")

    if without_goal:
        n0 = len(without_goal)
        w0 = sum(1 for r in without_goal if r["won"])
        print(f"  Score 0-0: N={n0}, WR={w0/n0*100:.1f}%, ROI={sum(r['pl'] for r in without_goal)/n0*100:.1f}%")

    buckets = [
        ("0-5 min",   0,  5),
        ("5-10 min",  5, 10),
        ("10-15 min", 10, 15),
        ("15-20 min", 15, 20),
        ("20-30 min", 20, 30),
        ("30+ min",   30, 999),
    ]

    print(f"\n  {'Bucket':<12} {'N':>5} {'Wins':>5} {'WR%':>7} {'ROI%':>8} {'AvgPL':>8}")
    print(f"  {'-'*50}")

    for label, lo, hi in buckets:
        subset = [r for r in with_goal if lo <= r["mins_since_goal"] < hi]
        n = len(subset)
        if n == 0:
            print(f"  {label:<12} {0:>5}   ---")
            continue
        wins = sum(1 for r in subset if r["won"])
        total_pl = sum(r["pl"] for r in subset)
        print(f"  {label:<12} {n:>5} {wins:>5} {wins/n*100:>6.1f}% {total_pl/n*100:>7.1f}% {total_pl/n:>7.3f}")

    # ── ANÁLISIS POR ESTRATEGIA ──────────────────────────────────────
    print("\n" + "=" * 80)
    print("ANÁLISIS POR ESTRATEGIA")
    print("=" * 80)

    for strat in CS_STRATEGIES:
        strat_data = [r for r in enriched if r["strategy"] == strat]
        if not strat_data:
            continue

        sw = [r for r in strat_data if r["mins_since_goal"] is not None]
        s0 = [r for r in strat_data if r["mins_since_goal"] is None]
        n_total = len(strat_data)
        wr_total = sum(1 for r in strat_data if r["won"]) / n_total * 100

        print(f"\n  --- {strat} (N={n_total}, WR={wr_total:.1f}%) ---")

        if s0:
            n0 = len(s0)
            w0 = sum(1 for r in s0 if r["won"])
            print(f"  Sin gol previo: N={n0}, WR={w0/n0*100:.1f}%, ROI={sum(r['pl'] for r in s0)/n0*100:.1f}%")

        simple_buckets = [
            ("< 5 min",  0,  5),
            ("5-10 min", 5, 10),
            ("10-20",    10, 20),
            ("20+ min",  20, 999),
        ]

        print(f"  {'Bucket':<12} {'N':>5} {'Wins':>5} {'WR%':>7} {'ROI%':>8}")
        print(f"  {'-'*40}")

        for label, lo, hi in simple_buckets:
            subset = [r for r in sw if lo <= r["mins_since_goal"] < hi]
            n = len(subset)
            if n == 0:
                print(f"  {label:<12} {0:>5}   ---")
                continue
            wins = sum(1 for r in subset if r["won"])
            total_pl = sum(r["pl"] for r in subset)
            print(f"  {label:<12} {n:>5} {wins:>5} {wins/n*100:>6.1f}% {total_pl/n*100:>7.1f}%")

    # ── BÚSQUEDA DE UMBRAL ÓPTIMO ────────────────────────────────────
    print("\n" + "=" * 80)
    print("UMBRAL ÓPTIMO: minSinceLastGoal >= X (solo apuestas con gol previo)")
    print("=" * 80)

    thresholds = [3, 5, 7, 10, 12, 15, 20]

    print(f"\n  {'Umbral':<12} {'N kept':>6} {'WR%':>7} {'ROI%':>8}  |  {'N excl':>6} {'WR%':>7} {'ROI%':>8}")
    print(f"  {'-'*70}")

    for t in thresholds:
        kept = [r for r in with_goal if r["mins_since_goal"] >= t]
        excl = [r for r in with_goal if r["mins_since_goal"] < t]
        nk, ne = len(kept), len(excl)
        if nk == 0 or ne == 0:
            continue
        wk = sum(1 for r in kept if r["won"])
        we = sum(1 for r in excl if r["won"])
        rk = sum(r["pl"] for r in kept) / nk * 100
        re = sum(r["pl"] for r in excl) / ne * 100
        print(f"  >= {t:>2} min   {nk:>6} {wk/nk*100:>6.1f}% {rk:>7.1f}%  |  {ne:>6} {we/ne*100:>6.1f}% {re:>7.1f}%")

    # ── RESUMEN ───────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)

    if with_goal:
        recent = [r for r in with_goal if r["mins_since_goal"] < 10]
        stable = [r for r in with_goal if r["mins_since_goal"] >= 10]

        if recent and stable:
            wr_r = sum(1 for r in recent if r["won"]) / len(recent) * 100
            wr_s = sum(1 for r in stable if r["won"]) / len(stable) * 100
            roi_r = sum(r["pl"] for r in recent) / len(recent) * 100
            roi_s = sum(r["pl"] for r in stable) / len(stable) * 100

            print(f"\n  Gol reciente (<10 min):    N={len(recent)}, WR={wr_r:.1f}%, ROI={roi_r:.1f}%")
            print(f"  Partido estable (>=10 min): N={len(stable)}, WR={wr_s:.1f}%, ROI={roi_s:.1f}%")
            diff_wr = wr_s - wr_r
            diff_roi = roi_s - roi_r
            print(f"\n  Delta WR:  {diff_wr:+.1f}pp")
            print(f"  Delta ROI: {diff_roi:+.1f}pp")

            if diff_wr > 3:
                print(f"\n  >> HIPÓTESIS VALIDADA: Filtrar goles recientes mejora WR en {diff_wr:.1f}pp")
            elif diff_wr < -3:
                print(f"\n  >> HIPÓTESIS RECHAZADA: Goles recientes tienen MEJOR WR")
            else:
                print(f"\n  >> INCONCLUSO: Diferencia menor a 3pp")


if __name__ == "__main__":
    main()
