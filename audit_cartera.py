#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auditoria exhaustiva de la cartera final antes de produccion.
Verifica: P/L, duplicados, consistencia, comisiones, acumulados.
"""

import csv
from collections import defaultdict

CSV_PATH = "cartera_max_pl_2026-02-16.csv"
STAKE = 10
COMMISSION = 0.05  # 5% Betfair commission on winnings

def load_bets():
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def audit():
    bets = load_bets()
    errors = []
    warnings = []

    print("=" * 100)
    print("AUDITORIA EXHAUSTIVA DE CARTERA FINAL")
    print(f"Total apuestas en CSV: {len(bets)}")
    print("=" * 100)

    # ============================================================
    # 1. CHECK DUPLICADOS (mismo match_id + misma strategy)
    # ============================================================
    print("\n--- 1. CHECK DUPLICADOS (match_id + strategy) ---")
    seen = defaultdict(list)
    for i, bet in enumerate(bets):
        key = (bet['match_id'], bet['strategy'])
        seen[key].append(i + 1)  # 1-indexed row

    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    if duplicates:
        for (mid, strat), rows in duplicates.items():
            match_name = next(b['match'] for b in bets if b['match_id'] == mid)
            msg = f"DUPLICADO: {match_name} | {strat} | Filas: {rows}"
            errors.append(msg)
            print(f"  [ERROR] {msg}")
    else:
        print("  [OK] Sin duplicados")

    # ============================================================
    # 2. CHECK P/L POR ESTRATEGIA
    # ============================================================
    print("\n--- 2. VERIFICACION P/L POR APUESTA ---")
    pl_errors = 0

    for i, bet in enumerate(bets):
        row_num = i + 1
        strategy = bet['strategy']
        won = bet['won'] == '1' or bet['won'] == 'True'
        pl_csv = float(bet['pl'])

        if strategy == 'Back Empate':
            odds = float(bet['back_draw']) if bet['back_draw'] else None
            if won and odds:
                expected_pl = round((odds - 1) * STAKE * (1 - COMMISSION), 2)
            elif not won:
                expected_pl = -STAKE
            else:
                expected_pl = None

        elif strategy == 'xG Underperf':
            odds = float(bet['back_over_odds']) if bet['back_over_odds'] else None
            if won and odds:
                expected_pl = round((odds - 1) * STAKE * (1 - COMMISSION), 2)
            elif not won:
                expected_pl = -STAKE
            else:
                expected_pl = None

        elif strategy == 'Odds Drift':
            odds = float(bet['back_odds']) if bet['back_odds'] else None
            if won and odds:
                expected_pl = round((odds - 1) * STAKE * (1 - COMMISSION), 2)
            elif not won:
                expected_pl = -STAKE
            else:
                expected_pl = None

        elif strategy == 'Goal Clustering':
            odds = float(bet['back_over_odds']) if bet['back_over_odds'] else None
            if odds:
                if won:
                    expected_pl = round((odds - 1) * STAKE * (1 - COMMISSION), 2)
                else:
                    expected_pl = -STAKE
            else:
                # Goal Clustering sin cuotas - que odds se usaron?
                expected_pl = None

        else:
            expected_pl = None
            warnings.append(f"Fila {row_num}: Estrategia desconocida '{strategy}'")

        # Comparar
        if expected_pl is not None:
            diff = abs(pl_csv - expected_pl)
            if diff > 0.02:  # Tolerancia de 2 centimos
                msg = f"Fila {row_num}: {bet['match'][:30]} | {strategy} | won={won} | odds={odds} | PL_csv={pl_csv} | PL_esperado={expected_pl} | diff={diff:.2f}"
                errors.append(msg)
                print(f"  [ERROR] {msg}")
                pl_errors += 1
        else:
            # No tenemos odds para verificar
            if won and pl_csv <= 0:
                msg = f"Fila {row_num}: {bet['match'][:30]} | {strategy} | won=1 pero pl={pl_csv}"
                errors.append(msg)
                print(f"  [ERROR] {msg}")
                pl_errors += 1
            elif not won and pl_csv != -10:
                msg = f"Fila {row_num}: {bet['match'][:30]} | {strategy} | won=0 pero pl={pl_csv} (esperado -10)"
                errors.append(msg)
                print(f"  [ERROR] {msg}")
                pl_errors += 1

    if pl_errors == 0:
        print("  [OK] Todos los P/L verificados correctamente")

    # ============================================================
    # 3. CHECK GOAL CLUSTERING - fuente de cuotas
    # ============================================================
    print("\n--- 3. GOAL CLUSTERING: Verificacion de cuotas ---")
    gc_bets = [b for b in bets if b['strategy'] == 'Goal Clustering']
    gc_with_odds = sum(1 for b in gc_bets if b['back_over_odds'])
    gc_without_odds = sum(1 for b in gc_bets if not b['back_over_odds'])
    print(f"  Total Goal Clustering: {len(gc_bets)}")
    print(f"  Con cuotas Over: {gc_with_odds}")
    print(f"  Sin cuotas Over: {gc_without_odds}")

    for i, bet in enumerate(bets):
        if bet['strategy'] != 'Goal Clustering':
            continue
        row_num = i + 1
        odds = bet.get('back_over_odds', '')
        won = bet['won'] == '1'
        pl = float(bet['pl'])

        if not odds and won and pl > 0:
            warnings.append(f"Fila {row_num}: Goal Clustering sin cuotas pero won=1 y pl={pl}. De donde sale el P/L?")
            print(f"  [WARN] Fila {row_num}: {bet['match'][:30]} | Sin cuotas | won={won} | pl={pl} - DE DONDE SALE ESTE P/L?")

    # ============================================================
    # 4. CHECK won vs ft_score CONSISTENCIA
    # ============================================================
    print("\n--- 4. CONSISTENCIA won vs ft_score ---")
    consistency_errors = 0

    for i, bet in enumerate(bets):
        row_num = i + 1
        strategy = bet['strategy']
        won = bet['won'] == '1'
        ft_score = bet['ft_score']
        score = bet['score']

        if not ft_score:
            continue

        ft_parts = ft_score.split('-')
        if len(ft_parts) != 2:
            continue
        ft_gl, ft_gv = int(ft_parts[0]), int(ft_parts[1])
        ft_total = ft_gl + ft_gv

        if strategy == 'Back Empate':
            expected_won = ft_gl == ft_gv
            if won != expected_won:
                msg = f"Fila {row_num}: {bet['match'][:30]} | Back Empate | ft={ft_score} | won={won} (esperado {expected_won})"
                errors.append(msg)
                print(f"  [ERROR] {msg}")
                consistency_errors += 1

        elif strategy == 'Odds Drift':
            team = bet.get('team', '')
            if team == 'home':
                expected_won = ft_gl > ft_gv
            elif team == 'away':
                expected_won = ft_gv > ft_gl
            else:
                continue
            if won != expected_won:
                msg = f"Fila {row_num}: {bet['match'][:30]} | Odds Drift | team={team} | ft={ft_score} | won={won} (esperado {expected_won})"
                errors.append(msg)
                print(f"  [ERROR] {msg}")
                consistency_errors += 1

        elif strategy in ('xG Underperf', 'Goal Clustering'):
            # Won = mas goles que en el momento del trigger
            if score:
                score_parts = score.split('-')
                if len(score_parts) == 2:
                    trigger_total = int(score_parts[0]) + int(score_parts[1])
                    expected_won = ft_total > trigger_total
                    if won != expected_won:
                        msg = f"Fila {row_num}: {bet['match'][:30]} | {strategy} | score_trigger={score} (total={trigger_total}) | ft={ft_score} (total={ft_total}) | won={won} (esperado {expected_won})"
                        errors.append(msg)
                        print(f"  [ERROR] {msg}")
                        consistency_errors += 1

    if consistency_errors == 0:
        print("  [OK] Todos los resultados son consistentes con ft_score")

    # ============================================================
    # 5. RESUMEN FINANCIERO
    # ============================================================
    print("\n--- 5. RESUMEN FINANCIERO ---")

    total_bets = len(bets)
    total_wins = sum(1 for b in bets if b['won'] == '1')
    total_losses = total_bets - total_wins
    total_pl = sum(float(b['pl']) for b in bets)
    total_staked = total_bets * STAKE
    roi = (total_pl / total_staked * 100) if total_staked > 0 else 0

    print(f"  Apuestas totales: {total_bets}")
    print(f"  Ganadas: {total_wins} ({total_wins/total_bets*100:.1f}%)")
    print(f"  Perdidas: {total_losses} ({total_losses/total_bets*100:.1f}%)")
    print(f"  Total apostado: EUR {total_staked:.2f}")
    print(f"  P/L total: EUR {total_pl:.2f}")
    print(f"  ROI: {roi:.1f}%")

    # Por estrategia
    print("\n  --- Por Estrategia ---")
    strategies = defaultdict(lambda: {"bets": 0, "wins": 0, "pl": 0.0})
    for bet in bets:
        s = bet['strategy']
        strategies[s]["bets"] += 1
        strategies[s]["pl"] += float(bet['pl'])
        if bet['won'] == '1':
            strategies[s]["wins"] += 1

    print(f"  {'Estrategia':<20} {'Bets':>6} {'Wins':>6} {'WR':>8} {'P/L':>10} {'ROI':>8}")
    print(f"  {'-'*60}")
    for strat, data in sorted(strategies.items()):
        wr = data['wins'] / data['bets'] * 100 if data['bets'] > 0 else 0
        roi_s = data['pl'] / (data['bets'] * STAKE) * 100 if data['bets'] > 0 else 0
        print(f"  {strat:<20} {data['bets']:>6} {data['wins']:>6} {wr:>7.1f}% {data['pl']:>+10.2f} {roi_s:>+7.1f}%")

    # ============================================================
    # 6. CHECK xG Underperf - score vs over_line
    # ============================================================
    print("\n--- 6. xG Underperf: Verificacion over_line ---")
    xg_bets = [b for b in bets if b['strategy'] == 'xG Underperf']
    for i, bet in enumerate(bets):
        if bet['strategy'] != 'xG Underperf':
            continue
        row_num = i + 1
        score = bet['score']
        over_line = bet.get('over_line', '')
        if score and over_line:
            parts = score.split('-')
            if len(parts) == 2:
                total_trigger = int(parts[0]) + int(parts[1])
                expected_line = f"Over {total_trigger + 0.5}"
                if over_line != expected_line:
                    msg = f"Fila {row_num}: score={score} (total={total_trigger}) | over_line={over_line} | esperado={expected_line}"
                    errors.append(msg)
                    print(f"  [ERROR] {msg}")
    print("  [OK] Verificacion completada")

    # ============================================================
    # 7. CHECK Goal Clustering - cuotas duplicadas con xG Underperf
    # ============================================================
    print("\n--- 7. Goal Clustering vs xG Underperf: Mismos P/L sospechosos ---")
    by_match_ts = defaultdict(list)
    for bet in bets:
        key = (bet['match_id'], bet['timestamp_utc'])
        by_match_ts[key].append(bet)

    for key, group in by_match_ts.items():
        if len(group) > 1:
            pls = [float(b['pl']) for b in group]
            strats = [b['strategy'] for b in group]
            # Si GC y xG tienen el mismo P/L exacto, puede ser sospechoso
            gc_pls = [float(b['pl']) for b in group if b['strategy'] == 'Goal Clustering']
            xg_pls = [float(b['pl']) for b in group if b['strategy'] == 'xG Underperf']
            if gc_pls and xg_pls:
                for gc_pl in gc_pls:
                    for xg_pl in xg_pls:
                        if gc_pl == xg_pl and gc_pl != -10:
                            match_name = group[0]['match'][:30]
                            warnings.append(f"{match_name}: GC y xG tienen mismo P/L={gc_pl} - posible cuota compartida")
                            print(f"  [WARN] {match_name}: Goal Clustering P/L={gc_pl} == xG Underperf P/L={xg_pl}")

    # ============================================================
    # 8. CHECK Goal Clustering sin campo back_over_odds
    # ============================================================
    print("\n--- 8. Goal Clustering: De donde obtiene cuotas? ---")
    for i, bet in enumerate(bets):
        if bet['strategy'] != 'Goal Clustering':
            continue
        row_num = i + 1
        over_odds = bet.get('back_over_odds', '')
        over_line = bet.get('over_line', '')
        pl = float(bet['pl'])
        won = bet['won'] == '1'

        # Recalcular P/L si hay cuotas
        if over_odds:
            odds_val = float(over_odds)
            if won:
                expected = round((odds_val - 1) * STAKE * 0.95, 2)
            else:
                expected = -STAKE
            diff = abs(pl - expected)
            if diff > 0.02:
                print(f"  [ERROR] Fila {row_num}: odds={odds_val} | won={won} | pl={pl} | esperado={expected}")
        else:
            print(f"  [INFO] Fila {row_num}: {bet['match'][:30]} | SIN CUOTAS | pl={pl} | won={won}")

    # ============================================================
    # 9. CRONOLOGIA - orden temporal correcto?
    # ============================================================
    print("\n--- 9. CRONOLOGIA ---")
    prev_ts = ""
    chrono_errors = 0
    for i, bet in enumerate(bets):
        ts = bet['timestamp_utc']
        if ts < prev_ts:
            print(f"  [ERROR] Fila {i+1}: Orden cronologico roto: {ts} < {prev_ts}")
            chrono_errors += 1
        prev_ts = ts
    if chrono_errors == 0:
        print("  [OK] Orden cronologico correcto")

    # ============================================================
    # RESUMEN FINAL
    # ============================================================
    print("\n" + "=" * 100)
    print("RESUMEN AUDITORIA")
    print("=" * 100)
    print(f"  ERRORES: {len(errors)}")
    for e in errors:
        print(f"    - {e}")
    print(f"\n  WARNINGS: {len(warnings)}")
    for w in warnings:
        print(f"    - {w}")

    if len(errors) == 0:
        print("\n  >>> RESULTADO: CARTERA APTA PARA PRODUCCION <<<")
    else:
        print("\n  >>> RESULTADO: CARTERA CON ERRORES - NO APTA <<<")
    print("=" * 100)

if __name__ == "__main__":
    audit()
