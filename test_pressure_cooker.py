#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Backtest: Pressure Cooker Strategy
===================================
Hipotesis: Si hay empate entre min 65-75 y uno de los equipos acumula momentum
reciente (SoT, corners, dangerous attacks en ultimos 10 min), apuesta Back Over
en la linea actual (goles actuales + 0.5).

Usa los datos reales capturados por el scraper.
"""

import csv
import os
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("betfair_scraper/data")
STAKE = 10
COMMISSION = 0.05

def to_float(val):
    if not val or val in ('', 'N/A', 'None', '-'):
        return None
    try:
        return float(str(val).replace(',', '.').replace('%', ''))
    except:
        return None

def to_int(val):
    f = to_float(val)
    return int(f) if f is not None else None

def get_over_field(total_goals):
    """Devuelve el campo back_over correcto para la linea actual."""
    line = total_goals + 0.5
    if line == 0.5:
        return "back_over05"
    elif line == 1.5:
        return "back_over15"
    elif line == 2.5:
        return "back_over25"
    elif line == 3.5:
        return "back_over35"
    elif line == 4.5:
        return "back_over45"
    return None

def load_match(csv_path):
    """Carga un CSV de partido y devuelve filas filtradas a en_juego con minuto numerico."""
    with open(csv_path, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    # Solo filas en juego con minuto numerico
    match_rows = []
    for row in rows:
        estado = row.get('estado_partido', '')
        minuto = to_int(row.get('minuto', ''))
        if estado == 'en_juego' and minuto is not None and minuto > 0:
            row['_minuto'] = minuto
            match_rows.append(row)

    return match_rows

def find_row_at_minute(rows, target_min):
    """Busca la fila mas cercana a un minuto dado."""
    best = None
    for row in rows:
        m = row['_minuto']
        if m <= target_min:
            if best is None or m > best['_minuto']:
                best = row
    return best

def calc_delta(rows, field, current_min, window=10):
    """Calcula el delta de un campo estadistico en los ultimos `window` minutos."""
    current_row = find_row_at_minute(rows, current_min)
    past_row = find_row_at_minute(rows, current_min - window)

    if not current_row or not past_row:
        return None

    val_now = to_float(current_row.get(field, ''))
    val_past = to_float(past_row.get(field, ''))

    if val_now is None or val_past is None:
        return None

    return val_now - val_past

def get_ft_score(rows):
    """Obtiene el marcador final del partido."""
    # Buscar la fila con minuto mas alto o estado finalizado
    best_min = 0
    best_gl, best_gv = None, None

    for row in rows:
        m = row['_minuto']
        gl = to_int(row.get('goles_local', ''))
        gv = to_int(row.get('goles_visitante', ''))
        if gl is not None and gv is not None and m >= best_min:
            best_min = m
            best_gl, best_gv = gl, gv

    # Tambien revisar filas de finalizado
    return best_gl, best_gv, best_min

def backtest():
    csv_files = sorted(DATA_DIR.glob("partido_*.csv"))
    print(f"Archivos de partidos encontrados: {len(csv_files)}")
    print("=" * 120)

    all_bets = []
    matches_scanned = 0
    matches_with_draw_65_75 = 0
    matches_skipped_no_data = 0

    # Para explorar umbrales, guardar todos los candidatos con sus metricas
    all_candidates = []

    for csv_path in csv_files:
        match_name = csv_path.stem.replace('partido_', '')
        rows = load_match(csv_path)

        if len(rows) < 20:  # Partido con pocos datos
            matches_skipped_no_data += 1
            continue

        matches_scanned += 1
        ft_gl, ft_gv, ft_min = get_ft_score(rows)

        if ft_gl is None or ft_gv is None:
            continue

        if ft_min < 85:  # Partido probablemente no finalizado
            continue

        ft_total = ft_gl + ft_gv

        # Buscar ventanas de trigger entre min 65-75
        trigger_checked = False
        for target_min in range(65, 76):
            trigger_row = find_row_at_minute(rows, target_min)
            if not trigger_row or trigger_row['_minuto'] < target_min - 2:
                continue  # No hay datos suficientemente cercanos a este minuto

            actual_min = trigger_row['_minuto']
            gl = to_int(trigger_row.get('goles_local', ''))
            gv = to_int(trigger_row.get('goles_visitante', ''))

            if gl is None or gv is None:
                continue

            # CONDICION 1: Empate
            if gl != gv:
                continue

            total_goals = gl + gv

            if trigger_checked:
                continue  # Solo un trigger por partido
            trigger_checked = True

            matches_with_draw_65_75 += 1

            # Calcular metricas de momentum (delta ultimos 10 min)
            sot_home_delta = calc_delta(rows, 'tiros_puerta_local', actual_min, 10) or 0
            sot_away_delta = calc_delta(rows, 'tiros_puerta_visitante', actual_min, 10) or 0
            sot_total_delta = sot_home_delta + sot_away_delta

            corners_home_delta = calc_delta(rows, 'corners_local', actual_min, 10) or 0
            corners_away_delta = calc_delta(rows, 'corners_visitante', actual_min, 10) or 0
            corners_total_delta = corners_home_delta + corners_away_delta

            da_home_delta = calc_delta(rows, 'dangerous_attacks_local', actual_min, 10) or 0
            da_away_delta = calc_delta(rows, 'dangerous_attacks_visitante', actual_min, 10) or 0
            da_total_delta = da_home_delta + da_away_delta

            shots_home_delta = calc_delta(rows, 'tiros_local', actual_min, 10) or 0
            shots_away_delta = calc_delta(rows, 'tiros_visitante', actual_min, 10) or 0
            shots_total_delta = shots_home_delta + shots_away_delta

            # Obtener cuotas Over
            over_field = get_over_field(total_goals)
            over_odds = to_float(trigger_row.get(over_field, '')) if over_field else None

            # xG delta (momentum ofensivo)
            xg_home_delta = calc_delta(rows, 'xg_local', actual_min, 10) or 0
            xg_away_delta = calc_delta(rows, 'xg_visitante', actual_min, 10) or 0
            xg_total_delta = xg_home_delta + xg_away_delta

            # Posesion diferencial actual
            poss_home = to_float(trigger_row.get('posesion_local', ''))
            poss_away = to_float(trigger_row.get('posesion_visitante', ''))

            # Resultado: hubo mas goles?
            won = ft_total > total_goals

            candidate = {
                "match": match_name[:50],
                "min": actual_min,
                "score": f"{gl}-{gv}",
                "ft_score": f"{ft_gl}-{ft_gv}",
                "sot_delta": sot_total_delta,
                "corners_delta": corners_total_delta,
                "da_delta": da_total_delta,
                "shots_delta": shots_total_delta,
                "xg_delta": round(xg_total_delta, 2),
                "over_odds": over_odds,
                "over_field": over_field,
                "won": won,
                "poss_home": poss_home,
                "poss_away": poss_away,
                # Desglose por equipo
                "sot_h": sot_home_delta,
                "sot_a": sot_away_delta,
                "da_h": da_home_delta,
                "da_a": da_away_delta,
            }
            all_candidates.append(candidate)

    # ================================================================
    # ANALISIS DE RESULTADOS
    # ================================================================
    print(f"\nPartidos escaneados: {matches_scanned}")
    print(f"Partidos con empate entre min 65-75: {matches_with_draw_65_75}")
    print(f"Partidos descartados (pocos datos / no finalizados): {matches_skipped_no_data}")

    if not all_candidates:
        print("\nSin candidatos. No hay partidos con empate entre min 65-75.")
        return

    # ================================================================
    # BASELINE: Todos los empates al 65-75 (sin filtro de momentum)
    # ================================================================
    print("\n" + "=" * 120)
    print("BASELINE: Back Over en TODOS los empates al min 65-75 (sin filtro)")
    print("=" * 120)

    baseline_with_odds = [c for c in all_candidates if c['over_odds'] and c['over_odds'] > 1]
    if baseline_with_odds:
        wins = sum(1 for c in baseline_with_odds if c['won'])
        losses = len(baseline_with_odds) - wins
        total_pl = 0
        for c in baseline_with_odds:
            if c['won']:
                total_pl += round((c['over_odds'] - 1) * STAKE * (1 - COMMISSION), 2)
            else:
                total_pl -= STAKE
        wr = wins / len(baseline_with_odds) * 100
        roi = total_pl / (len(baseline_with_odds) * STAKE) * 100
        avg_odds = sum(c['over_odds'] for c in baseline_with_odds) / len(baseline_with_odds)

        print(f"  Apuestas: {len(baseline_with_odds)} | Wins: {wins} | WR: {wr:.1f}% | P/L: {total_pl:+.2f} | ROI: {roi:+.1f}% | Avg odds: {avg_odds:.2f}")

    # ================================================================
    # DISTRIBUCION DE METRICAS (para elegir umbrales)
    # ================================================================
    print("\n" + "=" * 120)
    print("DISTRIBUCION DE METRICAS EN CANDIDATOS")
    print("=" * 120)

    for metric in ['sot_delta', 'corners_delta', 'da_delta', 'shots_delta', 'xg_delta']:
        vals = [c[metric] for c in all_candidates]
        vals_won = [c[metric] for c in all_candidates if c['won']]
        vals_lost = [c[metric] for c in all_candidates if not c['won']]

        avg_all = sum(vals) / len(vals) if vals else 0
        avg_won = sum(vals_won) / len(vals_won) if vals_won else 0
        avg_lost = sum(vals_lost) / len(vals_lost) if vals_lost else 0

        print(f"  {metric:>15}: avg_all={avg_all:>6.2f} | avg_WON={avg_won:>6.2f} | avg_LOST={avg_lost:>6.2f} | max={max(vals):>5.1f} | min={min(vals):>5.1f}")

    # ================================================================
    # TEST FILTROS PROGRESIVOS
    # ================================================================
    print("\n" + "=" * 120)
    print("TEST DE FILTROS PROGRESIVOS (sobre candidatos con cuotas)")
    print("=" * 120)

    filters = [
        ("Sin filtro", lambda c: True),
        ("SoT delta >= 1", lambda c: c['sot_delta'] >= 1),
        ("SoT delta >= 2", lambda c: c['sot_delta'] >= 2),
        ("SoT delta >= 3", lambda c: c['sot_delta'] >= 3),
        ("Corners delta >= 2", lambda c: c['corners_delta'] >= 2),
        ("Corners delta >= 3", lambda c: c['corners_delta'] >= 3),
        ("DA delta >= 5", lambda c: c['da_delta'] >= 5),
        ("DA delta >= 10", lambda c: c['da_delta'] >= 10),
        ("DA delta >= 15", lambda c: c['da_delta'] >= 15),
        ("Shots delta >= 2", lambda c: c['shots_delta'] >= 2),
        ("Shots delta >= 3", lambda c: c['shots_delta'] >= 3),
        ("Shots delta >= 4", lambda c: c['shots_delta'] >= 4),
        ("xG delta >= 0.3", lambda c: c['xg_delta'] >= 0.3),
        ("xG delta >= 0.5", lambda c: c['xg_delta'] >= 0.5),
        ("xG delta >= 0.8", lambda c: c['xg_delta'] >= 0.8),
        # Combinaciones (propuesta Gemini)
        ("Gemini: SoT>=2 + Corners>=2", lambda c: c['sot_delta'] >= 2 and c['corners_delta'] >= 2),
        ("Gemini: SoT>=2 + Corners>=2 + DA>=10", lambda c: c['sot_delta'] >= 2 and c['corners_delta'] >= 2 and c['da_delta'] >= 10),
        # Variantes propias
        ("Shots>=3 + Corners>=2", lambda c: c['shots_delta'] >= 3 and c['corners_delta'] >= 2),
        ("Shots>=3 + DA>=10", lambda c: c['shots_delta'] >= 3 and c['da_delta'] >= 10),
        ("SoT>=2 + DA>=10", lambda c: c['sot_delta'] >= 2 and c['da_delta'] >= 10),
        ("xG>=0.3 + Shots>=3", lambda c: c['xg_delta'] >= 0.3 and c['shots_delta'] >= 3),
        ("xG>=0.5 + SoT>=2", lambda c: c['xg_delta'] >= 0.5 and c['sot_delta'] >= 2),
        # Un equipo domina (asimetria)
        ("Un equipo DA desequilibrado (>70%)", lambda c: c['da_h'] > 0 and c['da_a'] > 0 and (c['da_h'] / (c['da_h'] + c['da_a']) > 0.7 or c['da_a'] / (c['da_h'] + c['da_a']) > 0.7)),
        ("SoT>=2 + DA desbalance >70%", lambda c: c['sot_delta'] >= 2 and c['da_h'] > 0 and c['da_a'] > 0 and (c['da_h'] / (c['da_h'] + c['da_a']) > 0.7 or c['da_a'] / (c['da_h'] + c['da_a']) > 0.7)),
        # Cuota filtro
        ("Odds >= 1.5 (sin filtro momentum)", lambda c: c['over_odds'] and c['over_odds'] >= 1.5),
        ("Odds >= 2.0 (sin filtro momentum)", lambda c: c['over_odds'] and c['over_odds'] >= 2.0),
        ("SoT>=2 + Odds>=1.5", lambda c: c['sot_delta'] >= 2 and c['over_odds'] and c['over_odds'] >= 1.5),
        ("SoT>=2 + Odds>=2.0", lambda c: c['sot_delta'] >= 2 and c['over_odds'] and c['over_odds'] >= 2.0),
    ]

    print(f"\n  {'Filtro':<45} {'N':>4} {'W':>4} {'L':>4} {'WR':>7} {'P/L':>10} {'ROI':>8} {'AvgOdds':>8}")
    print(f"  {'-'*95}")

    for name, fn in filters:
        subset = [c for c in all_candidates if c['over_odds'] and c['over_odds'] > 1 and fn(c)]
        if not subset:
            print(f"  {name:<45} {'--':>4} {'--':>4} {'--':>4} {'--':>7} {'--':>10} {'--':>8} {'--':>8}")
            continue

        wins = sum(1 for c in subset if c['won'])
        losses = len(subset) - wins
        total_pl = 0
        for c in subset:
            if c['won']:
                total_pl += round((c['over_odds'] - 1) * STAKE * (1 - COMMISSION), 2)
            else:
                total_pl -= STAKE

        wr = wins / len(subset) * 100 if subset else 0
        roi = total_pl / (len(subset) * STAKE) * 100 if subset else 0
        avg_odds = sum(c['over_odds'] for c in subset) / len(subset) if subset else 0

        marker = " ***" if roi > 10 and len(subset) >= 5 else ""
        print(f"  {name:<45} {len(subset):>4} {wins:>4} {losses:>4} {wr:>6.1f}% {total_pl:>+10.2f} {roi:>+7.1f}% {avg_odds:>8.2f}{marker}")

    # ================================================================
    # DETALLE DE APUESTAS (mejor filtro)
    # ================================================================
    print("\n" + "=" * 120)
    print("DETALLE: Todos los candidatos con empate 65-75 (sin filtro)")
    print("=" * 120)
    print(f"  {'Partido':<45} {'Min':>4} {'Score':>6} {'FT':>6} {'SoT':>5} {'Crn':>5} {'DA':>5} {'Shots':>5} {'xG':>5} {'Odds':>6} {'Won':>4} {'P/L':>8}")
    print(f"  {'-'*115}")

    cum_pl = 0
    for c in sorted(all_candidates, key=lambda x: x['match']):
        odds = c['over_odds']
        if not odds or odds <= 1:
            odds_str = "N/A"
            pl = 0
        else:
            if c['won']:
                pl = round((odds - 1) * STAKE * (1 - COMMISSION), 2)
            else:
                pl = -STAKE
            odds_str = f"{odds:.2f}"
            cum_pl += pl

        won_str = "W" if c['won'] else "L"
        print(f"  {c['match']:<45} {c['min']:>4} {c['score']:>6} {c['ft_score']:>6} {c['sot_delta']:>5.0f} {c['corners_delta']:>5.0f} {c['da_delta']:>5.0f} {c['shots_delta']:>5.0f} {c['xg_delta']:>5.2f} {odds_str:>6} {won_str:>4} {pl:>+8.2f}")

    print(f"\n  Acumulado P/L: {cum_pl:+.2f}")

    # ================================================================
    # KEY INSIGHT: Filtro por marcador (no 0-0)
    # ================================================================
    print("\n" + "=" * 120)
    print("FILTRO CLAVE: Excluir 0-0 (solo empates con goles: 1-1, 2-2, 3-3...)")
    print("=" * 120)

    score_filters = [
        ("Solo 0-0", lambda c: c['score'] == '0-0'),
        ("Solo 1-1+", lambda c: c['score'] != '0-0'),
        ("Solo 1-1", lambda c: c['score'] == '1-1'),
        ("Solo 2-2+", lambda c: c['score'] not in ('0-0', '1-1')),
        ("1-1+ y Shots>=2", lambda c: c['score'] != '0-0' and c['shots_delta'] >= 2),
        ("1-1+ y SoT>=1", lambda c: c['score'] != '0-0' and c['sot_delta'] >= 1),
        ("1-1+ y Corners>=1", lambda c: c['score'] != '0-0' and c['corners_delta'] >= 1),
        ("1-1+ y xG>=0.1", lambda c: c['score'] != '0-0' and c['xg_delta'] >= 0.1),
        ("1-1+ y Odds>=1.5", lambda c: c['score'] != '0-0' and c['over_odds'] and c['over_odds'] >= 1.5),
        ("1-1+ y Odds>=1.3", lambda c: c['score'] != '0-0' and c['over_odds'] and c['over_odds'] >= 1.3),
    ]

    print(f"\n  {'Filtro':<40} {'N':>4} {'W':>4} {'L':>4} {'WR':>7} {'P/L':>10} {'ROI':>8} {'AvgOdds':>8}")
    print(f"  {'-'*90}")

    for name, fn in score_filters:
        subset = [c for c in all_candidates if c['over_odds'] and c['over_odds'] > 1 and fn(c)]
        if not subset:
            print(f"  {name:<40} {'--':>4}")
            continue

        wins = sum(1 for c in subset if c['won'])
        losses = len(subset) - wins
        total_pl = 0
        for c in subset:
            if c['won']:
                total_pl += round((c['over_odds'] - 1) * STAKE * (1 - COMMISSION), 2)
            else:
                total_pl -= STAKE

        wr = wins / len(subset) * 100
        roi = total_pl / (len(subset) * STAKE) * 100
        avg_odds = sum(c['over_odds'] for c in subset) / len(subset)

        marker = " ***" if roi > 10 and len(subset) >= 5 else ""
        print(f"  {name:<40} {len(subset):>4} {wins:>4} {losses:>4} {wr:>6.1f}% {total_pl:>+10.2f} {roi:>+7.1f}% {avg_odds:>8.2f}{marker}")

    # Detalle de las PERDIDAS en 1-1+
    print("\n  --- Detalle de PERDIDAS en empates 1-1+ ---")
    losses_non00 = [c for c in all_candidates if c['over_odds'] and c['over_odds'] > 1 and c['score'] != '0-0' and not c['won']]
    for c in losses_non00:
        print(f"  {c['match']:<45} min={c['min']} score={c['score']} ft={c['ft_score']} odds={c['over_odds']:.2f} shots={c['shots_delta']:.0f} sot={c['sot_delta']:.0f} corners={c['corners_delta']:.0f}")

    # Detalle de las GANANCIAS en 1-1+
    print("\n  --- Detalle de GANANCIAS en empates 1-1+ ---")
    wins_non00 = [c for c in all_candidates if c['over_odds'] and c['over_odds'] > 1 and c['score'] != '0-0' and c['won']]
    for c in wins_non00:
        pl = round((c['over_odds'] - 1) * STAKE * (1 - COMMISSION), 2)
        print(f"  {c['match']:<45} min={c['min']} score={c['score']} ft={c['ft_score']} odds={c['over_odds']:.2f} shots={c['shots_delta']:.0f} sot={c['sot_delta']:.0f} corners={c['corners_delta']:.0f} pl=+{pl:.2f}")

    # ================================================================
    # SCORE-BASED ANALYSIS
    # ================================================================
    print("\n" + "=" * 120)
    print("ANALISIS POR MARCADOR AL TRIGGER")
    print("=" * 120)

    by_score = defaultdict(list)
    for c in all_candidates:
        by_score[c['score']].append(c)

    for score, group in sorted(by_score.items()):
        with_odds = [c for c in group if c['over_odds'] and c['over_odds'] > 1]
        if not with_odds:
            continue
        wins = sum(1 for c in with_odds if c['won'])
        total_pl = sum(
            round((c['over_odds'] - 1) * STAKE * (1 - COMMISSION), 2) if c['won'] else -STAKE
            for c in with_odds
        )
        wr = wins / len(with_odds) * 100
        avg_odds = sum(c['over_odds'] for c in with_odds) / len(with_odds)
        roi = total_pl / (len(with_odds) * STAKE) * 100
        print(f"  {score}: {len(with_odds)} bets | WR: {wr:.0f}% | P/L: {total_pl:+.2f} | ROI: {roi:+.1f}% | Avg odds: {avg_odds:.2f}")

if __name__ == "__main__":
    backtest()
