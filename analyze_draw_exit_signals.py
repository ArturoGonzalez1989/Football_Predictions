"""
analyze_draw_exit_signals.py
============================
Analiza datos históricos POST-trigger de Back Draw 0-0 para encontrar
variables que predicen pérdida. El objetivo es descubrir señales de salida
(cashout) basadas en patrones empíricos, no en heurísticas inventadas.

Metodología:
  Para cada bet perdido/ganado, rastrea la evolución de variables clave
  desde el trigger (min 30, 0-0) hasta el final. Para cada variable y
  umbral, compara win% de bets que cruzaron ese umbral vs los que no.
  Un umbral con win% muy bajo cuando se cruza = buena señal de salida.

Uso:
  python analyze_draw_exit_signals.py [--version v2r]
"""

import csv
import sys
import re
from pathlib import Path
from collections import defaultdict

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# ─── Paths ───────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent
DATA_DIR = ROOT / "betfair_scraper" / "data"
BACKEND  = ROOT / "betfair_scraper" / "dashboard" / "backend"
sys.path.insert(0, str(BACKEND))

from utils.csv_reader import (
    analyze_strategy_back_draw_00,
    _read_csv_rows,
    _to_float,
    _resolve_csv_path,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _find_trigger_idx(rows, trigger_min: float) -> int | None:
    """Encuentra el índice de la fila trigger (0-0, minuto más cercano a trigger_min)."""
    best_idx = None
    best_dist = float("inf")
    for i, row in enumerate(rows):
        m  = _to_float(row.get("minuto", ""))
        gl = _to_float(row.get("goles_local", ""))
        gv = _to_float(row.get("goles_visitante", ""))
        if m is None or gl is None or gv is None:
            continue
        if int(gl) == 0 and int(gv) == 0:
            dist = abs(m - trigger_min)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
    return best_idx if (best_idx is not None and best_dist <= 5) else None


def _extract_post_trigger(rows, trigger_idx: int, trigger_xg: float, trigger_shots: float,
                           trigger_lay: float | None) -> list[dict]:
    """Extrae métricas fila a fila desde el trigger hasta el final del partido."""
    post = []
    first_goal_min = None

    for row in rows[trigger_idx + 1:]:
        m  = _to_float(row.get("minuto", ""))
        if m is None:
            continue

        gl = _to_float(row.get("goles_local", ""))
        gv = _to_float(row.get("goles_visitante", ""))

        # Primer gol
        goals = int(gl or 0) + int(gv or 0)
        if first_goal_min is None and goals > 0:
            first_goal_min = m

        # xG
        xg_l = _to_float(row.get("xg_local",    "")) or 0
        xg_v = _to_float(row.get("xg_visitante", "")) or 0
        xg_total = xg_l + xg_v

        # Tiros
        shots_l = _to_float(row.get("tiros_local",     "")) or 0
        shots_v = _to_float(row.get("tiros_visitante",  "")) or 0
        shots_total = shots_l + shots_v

        # Tiros a puerta
        sot_l = _to_float(row.get("tiros_puerta_local",     "")) or 0
        sot_v = _to_float(row.get("tiros_puerta_visitante",  "")) or 0
        sot_total = sot_l + sot_v

        # Posesión
        poss_l = _to_float(row.get("posesion_local",     "")) or 50
        poss_v = _to_float(row.get("posesion_visitante",  "")) or 50
        poss_diff = abs(poss_l - poss_v)

        # Cuotas
        lay_draw  = _to_float(row.get("lay_draw",  ""))
        back_draw = _to_float(row.get("back_draw", ""))

        # Deltas vs trigger
        delta_xg    = xg_total - trigger_xg    if trigger_xg    is not None else None
        delta_shots = shots_total - trigger_shots if trigger_shots is not None else None
        lay_pct     = ((lay_draw - trigger_lay) / trigger_lay * 100
                       if (lay_draw and trigger_lay and trigger_lay > 0) else None)

        post.append({
            "minute":         m,
            "goals":          goals,
            "first_goal":     first_goal_min is not None,
            "first_goal_min": first_goal_min,
            "xg_total":       xg_total,
            "delta_xg":       delta_xg,
            "shots_total":    shots_total,
            "delta_shots":    delta_shots,
            "sot_total":      sot_total,
            "poss_diff":      poss_diff,
            "lay_draw":       lay_draw,
            "back_draw":      back_draw,
            "lay_pct":        lay_pct,
        })

    return post


# ─── Threshold tester ────────────────────────────────────────────────────────

def _test_threshold(bet_post_data, variable: str, threshold: float) -> dict:
    """
    Para cada bet, detecta si la variable cruzó el umbral (> threshold) en
    algún momento post-trigger. Compara win% de cruzados vs no cruzados.
    """
    cross_won = cross_tot = 0
    no_won    = no_tot    = 0
    lays_at_cross = []
    mins_at_cross = []

    for post_rows, won in bet_post_data:
        crossed  = False
        for row in post_rows:
            val = row.get(variable)
            if val is None:
                continue
            if val > threshold:
                crossed = True
                if row.get("lay_draw"):
                    lays_at_cross.append(row["lay_draw"])
                mins_at_cross.append(row["minute"])
                break   # primera vez que se cruza

        if crossed:
            cross_tot += 1
            if won: cross_won += 1
        else:
            no_tot += 1
            if won: no_won += 1

    return {
        "cross_n":   cross_tot,
        "cross_wr":  cross_won / cross_tot if cross_tot > 0 else None,
        "no_n":      no_tot,
        "no_wr":     no_won / no_tot if no_tot > 0 else None,
        "avg_lay":   sum(lays_at_cross) / len(lays_at_cross) if lays_at_cross else None,
        "avg_min":   sum(mins_at_cross) / len(mins_at_cross) if mins_at_cross else None,
    }


def _test_boolean(bet_post_data, variable: str) -> dict:
    """Para variables booleanas (ej: first_goal). Detecta si alguna vez fue True."""
    cross_won = cross_tot = 0
    no_won    = no_tot    = 0
    lays_at_cross = []
    mins_at_cross = []

    for post_rows, won in bet_post_data:
        crossed = False
        for row in post_rows:
            if row.get(variable):
                crossed = True
                if row.get("lay_draw"):
                    lays_at_cross.append(row["lay_draw"])
                mins_at_cross.append(row["minute"])
                break

        if crossed:
            cross_tot += 1
            if won: cross_won += 1
        else:
            no_tot += 1
            if won: no_won += 1

    return {
        "cross_n":  cross_tot,
        "cross_wr": cross_won / cross_tot if cross_tot > 0 else None,
        "no_n":     no_tot,
        "no_wr":    no_won / no_tot if no_tot > 0 else None,
        "avg_lay":  sum(lays_at_cross) / len(lays_at_cross) if lays_at_cross else None,
        "avg_min":  sum(mins_at_cross) / len(mins_at_cross) if mins_at_cross else None,
    }


# ─── Cashout EV ──────────────────────────────────────────────────────────────

def _cashout_pl(back_odds: float, lay_odds: float, stake: float = 10.0) -> float:
    """P/L garantizado al hacer cashout (lay en contra). Positivo = recuperas."""
    if not back_odds or not lay_odds or lay_odds <= 0:
        return 0.0
    return stake * (back_odds / lay_odds - 1)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    version = "v2r"
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--version" and i + 1 < len(sys.argv) - 1:
            version = sys.argv[i + 2]

    print("=" * 72)
    print("  SEÑALES DE SALIDA — Back Draw 0-0  (versión de filtro de entrada:", version, ")")
    print("=" * 72)

    # ── 1. Obtener apuestas históricas ────────────────────────────────────────
    result = analyze_strategy_back_draw_00(min_dur=1)
    all_bets = result.get("bets", [])

    # Filtrar por versión
    ver_key = f"passes_{version}"
    bets = [b for b in all_bets if b.get(ver_key, False)]
    if not bets:
        print(f"AVISO: ningún bet pasa el filtro '{version}'. Usando todos ({len(all_bets)}).")
        bets = all_bets

    n_won  = sum(1 for b in bets if b["won"])
    n_lost = sum(1 for b in bets if not b["won"])
    overall_wr = n_won / len(bets) if bets else 0

    print(f"\nBets analizados : {len(bets)}  (filtro {version})")
    print(f"Ganados / Perdidos : {n_won} / {n_lost}  — Win% global: {overall_wr*100:.1f}%\n")

    # ── 2. Construir datos post-trigger ───────────────────────────────────────
    bet_post_data   = []   # [(post_rows, won), ...]
    bet_details     = []   # para tabla de detalle

    for bet in bets:
        match_id    = bet["match_id"]
        trigger_min = bet.get("minuto") or 30.0
        won         = bet["won"]
        back_odds   = bet.get("back_draw")

        csv_path = _resolve_csv_path(match_id)
        if not csv_path or not csv_path.exists():
            continue

        rows = _read_csv_rows(csv_path)
        tidx = _find_trigger_idx(rows, trigger_min)
        if tidx is None:
            continue

        trigger_row   = rows[tidx]
        trigger_xg    = bet.get("xg_total")    or 0.0
        trigger_shots = bet.get("shots_total")  or 0.0
        trigger_lay   = _to_float(trigger_row.get("lay_draw", ""))

        post = _extract_post_trigger(rows, tidx, trigger_xg, trigger_shots, trigger_lay)
        if not post:
            continue

        bet_post_data.append((post, won))
        bet_details.append({
            "match":       bet.get("match", match_id),
            "trigger_min": trigger_min,
            "back_odds":   back_odds,
            "trigger_lay": trigger_lay,
            "won":         won,
            "post":        post,
        })

    print(f"Bets con datos CSV disponibles: {len(bet_post_data)}\n")
    if not bet_post_data:
        print("No hay datos suficientes para el análisis.")
        return

    # ── 3. Definir umbrales a testear ─────────────────────────────────────────
    THRESHOLDS = [
        # (variable, threshold_or_None, tipo, etiqueta)
        ("first_goal",  None,  "bool",    "Primer gol marcado"),
        ("delta_xg",    0.15,  "numeric", "D_xG > +0.15"),
        ("delta_xg",    0.20,  "numeric", "D_xG > +0.20"),
        ("delta_xg",    0.30,  "numeric", "D_xG > +0.30"),
        ("delta_xg",    0.40,  "numeric", "D_xG > +0.40"),
        ("delta_xg",    0.50,  "numeric", "D_xG > +0.50"),
        ("xg_total",    0.65,  "numeric", "xG total > 0.65"),
        ("xg_total",    0.80,  "numeric", "xG total > 0.80"),
        ("xg_total",    1.00,  "numeric", "xG total > 1.00"),
        ("xg_total",    1.20,  "numeric", "xG total > 1.20"),
        ("delta_shots", 3,     "numeric", "D_tiros > +3"),
        ("delta_shots", 5,     "numeric", "D_tiros > +5"),
        ("delta_shots", 8,     "numeric", "D_tiros > +8"),
        ("sot_total",   4,     "numeric", "SoT total > 4"),
        ("sot_total",   6,     "numeric", "SoT total > 6"),
        ("poss_diff",   20,    "numeric", "Dif. posesión > 20%"),
        ("poss_diff",   25,    "numeric", "Dif. posesión > 25%"),
        ("poss_diff",   30,    "numeric", "Dif. posesión > 30%"),
        ("lay_pct",     20,    "numeric", "Lay empate +20% vs trigger"),
        ("lay_pct",     30,    "numeric", "Lay empate +30% vs trigger"),
        ("lay_pct",     40,    "numeric", "Lay empate +40% vs trigger"),
        ("lay_pct",     60,    "numeric", "Lay empate +60% vs trigger"),
    ]

    # ── 4. Ejecutar tests ─────────────────────────────────────────────────────
    rows_out = []
    for variable, threshold, tipo, label in THRESHOLDS:
        if tipo == "bool":
            res = _test_boolean(bet_post_data, variable)
        else:
            res = _test_threshold(bet_post_data, variable, threshold)

        if res["cross_n"] < 4:   # mínimo muestral
            continue

        lift = (res["cross_wr"] or 0) - overall_wr
        rows_out.append({
            "label":      label,
            "cross_n":    res["cross_n"],
            "cross_wr":   res["cross_wr"],
            "no_n":       res["no_n"],
            "no_wr":      res["no_wr"],
            "lift":       lift,
            "avg_lay":    res["avg_lay"],
            "avg_min":    res["avg_min"],
        })

    # Ordenar por lift ascendente (más negativo = mejor señal de salida)
    rows_out.sort(key=lambda x: x["lift"] or 0)

    # ── 5. Tabla de señales ───────────────────────────────────────────────────
    W1, W2, W3, W4, W5, W6, W7 = 32, 7, 14, 17, 9, 9, 9
    header = (
        f"{'Condición de salida':<{W1}} {'N':>{W2}} {'Win% cruzado':>{W3}} "
        f"{'Win% no cruzado':>{W4}} {'Lift':>{W5}} {'Lay avg':>{W6}} {'Min avg':>{W7}}"
    )
    print(header)
    print("-" * (W1 + W2 + W3 + W4 + W5 + W6 + W7 + 6))

    for r in rows_out:
        cr = f"{r['cross_wr']*100:.0f}%"  if r["cross_wr"] is not None else "N/A"
        nc = f"{r['no_wr']*100:.0f}%"     if r["no_wr"]    is not None else "N/A"
        li = f"{r['lift']*100:+.0f}%"
        la = f"{r['avg_lay']:.2f}"         if r["avg_lay"]  is not None else "N/A"
        mi = f"{r['avg_min']:.0f}'"        if r["avg_min"]  is not None else "N/A"
        print(f"{r['label']:<{W1}} {r['cross_n']:>{W2}} {cr:>{W3}} {nc:>{W4}} {li:>{W5}} {la:>{W6}} {mi:>{W7}}")

    print()
    print("Lift = Win% cruzado - Win% global. Negativo = peor outcome cuando se cruza.")
    print("Lay avg = cuota lay del empate en el momento del cruce (coste cashout).")

    # ── 6. Detalle bets perdidos ───────────────────────────────────────────────
    print("\n\n--- DETALLE APUESTAS PERDIDAS ---")
    hdr2 = f"{'Partido':<38} {'Trig':>5} {'1er gol':>8} {'D_xG max':>9} {'Lay% max':>9} {'Lay@1g':>8}"
    print(hdr2)
    print("-" * (38 + 5 + 8 + 9 + 9 + 8 + 5))

    for d in bet_details:
        if d["won"]:
            continue
        post = d["post"]
        fg   = next((r["first_goal_min"] for r in post if r.get("first_goal_min")), None)
        max_dxg = max((r["delta_xg"]  or 0 for r in post), default=0)
        max_lpct = max((r["lay_pct"]  or 0 for r in post), default=0)

        # Lay cuando se marcó el primer gol
        lay_at_goal = None
        if fg is not None:
            for r in post:
                if r["first_goal_min"] == fg and r.get("lay_draw"):
                    lay_at_goal = r["lay_draw"]
                    break

        fg_str  = f"{fg:.0f}'"      if fg       is not None else "sin gol"
        lag_str = f"{lay_at_goal:.2f}" if lay_at_goal else "N/A"
        print(
            f"{d['match'][:38]:<38} {d['trigger_min']:>5.0f} "
            f"{fg_str:>8} {max_dxg:>9.2f} {max_lpct:>8.0f}% {lag_str:>8}"
        )

    # ── 7. Resumen ejecutivo ───────────────────────────────────────────────────
    best = rows_out[0] if rows_out else None
    if best:
        print("\n\n── RESUMEN EJECUTIVO ──────────────────────────────────────────────────")
        print(f"Mejor señal de salida encontrada: '{best['label']}'")
        print(f"  → Cuando se cruza: Win% = {(best['cross_wr'] or 0)*100:.0f}%  (vs {overall_wr*100:.0f}% global)")
        print(f"  → Cuota lay promedio al cruce: {best['avg_lay']:.2f if best['avg_lay'] else 'N/A'}")
        print(f"  → Minuto promedio al cruce: {best['avg_min']:.0f if best['avg_min'] else 'N/A'}'")
        if best["avg_lay"] and bet_details:
            avg_back = sum(d["back_odds"] for d in bet_details if d["back_odds"]) / len([d for d in bet_details if d["back_odds"]])
            co_pl = _cashout_pl(avg_back, best["avg_lay"])
            print(f"  → P/L estimado del cashout: {co_pl:+.2f}€ por 10€ de stake")
            print(f"    (vs pérdida total de -10€ si no haces cashout)")

    print("\nFin del análisis.")


if __name__ == "__main__":
    main()