#!/usr/bin/env python3
"""
Simulacion: Back Empate cuando marcador igualado a partir del minuto 30.
Stake fijo de 10 EUR por apuesta.
"""

import pandas as pd
import glob
import os

DATA_DIR = r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data'
STAKE = 10.0
MIN_ENTRY = 30
COMISION_BETFAIR = 0.05  # 5% sobre beneficios netos

def main():
    files = glob.glob(os.path.join(DATA_DIR, 'partido_*.csv'))

    bets = []
    skipped = []

    for f in files:
        try:
            df = pd.read_csv(f)
            if 'estado_partido' not in df.columns:
                continue

            match_name = os.path.basename(f).replace('partido_', '').replace('.csv', '')

            # Convertir columnas
            for col in ['minuto', 'goles_local', 'goles_visitante', 'back_draw']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Solo filas en juego o descanso
            ingame = df[df['estado_partido'].isin(['en_juego', 'descanso'])].copy()
            ingame = ingame.sort_values('minuto')

            if len(ingame) < 5:
                continue

            # Determinar resultado final
            final_rows = df[df['estado_partido'] == 'finalizado']
            if len(final_rows) == 0:
                final_rows = df.tail(1)

            final_h = final_rows['goles_local'].iloc[-1]
            final_a = final_rows['goles_visitante'].iloc[-1]

            if pd.isna(final_h) or pd.isna(final_a):
                continue

            ended_draw = (int(final_h) == int(final_a))
            final_score = f"{int(final_h)}-{int(final_a)}"

            # Buscar primer momento: minuto >= 30 AND marcador igualado AND cuota disponible
            entry_row = None
            for _, row in ingame.iterrows():
                minute = row.get('minuto')
                goals_h = row.get('goles_local')
                goals_a = row.get('goles_visitante')
                back_draw = row.get('back_draw')

                if pd.isna(minute) or pd.isna(goals_h) or pd.isna(goals_a) or pd.isna(back_draw):
                    continue

                if minute >= MIN_ENTRY and goals_h == goals_a and back_draw > 1.01:
                    entry_row = row
                    break

            if entry_row is None:
                skipped.append((match_name, final_score, "No hay momento igualado desde min 30 con cuota"))
                continue

            odds = entry_row['back_draw']
            entry_minute = int(entry_row['minuto'])
            entry_score = f"{int(entry_row['goles_local'])}-{int(entry_row['goles_visitante'])}"

            if ended_draw:
                profit_bruto = (odds - 1) * STAKE
                comision = profit_bruto * COMISION_BETFAIR
                profit_neto = profit_bruto - comision
            else:
                profit_bruto = -STAKE
                comision = 0
                profit_neto = -STAKE

            bets.append({
                'match': match_name[:50],
                'entry_min': entry_minute,
                'entry_score': entry_score,
                'odds': odds,
                'final_score': final_score,
                'draw': ended_draw,
                'profit_bruto': profit_bruto,
                'comision': comision,
                'profit_neto': profit_neto
            })

        except Exception as e:
            pass

    # Ordenar por minuto de entrada
    bets.sort(key=lambda x: x['entry_min'])

    print("=" * 110)
    print("  SIMULACION: BACK EMPATE CUANDO IGUALADOS (MIN 30+) - STAKE 10 EUR")
    print("=" * 110)
    print()

    # Detalle de cada apuesta
    print(f"{'#':<4} {'Partido':<45} {'Min':<5} {'Marcador':<9} {'Cuota':<7} {'Final':<7} {'Resultado':<12} {'P/L Bruto':<11} {'Comision':<9} {'P/L Neto':<10}")
    print("-" * 110)

    running_total = 0
    running_total_neto = 0

    for i, b in enumerate(bets, 1):
        running_total += b['profit_bruto']
        running_total_neto += b['profit_neto']
        result_str = "GANADA" if b['draw'] else "PERDIDA"
        print(f"{i:<4} {b['match']:<45} {b['entry_min']:<5} {b['entry_score']:<9} {b['odds']:<7.2f} {b['final_score']:<7} {result_str:<12} {b['profit_bruto']:>+8.2f} EUR {b['comision']:>6.2f} EUR {b['profit_neto']:>+8.2f} EUR")

    print("-" * 110)

    # Resumen
    total_bets = len(bets)
    wins = sum(1 for b in bets if b['draw'])
    losses = total_bets - wins
    total_staked = total_bets * STAKE
    total_profit_bruto = sum(b['profit_bruto'] for b in bets)
    total_comision = sum(b['comision'] for b in bets)
    total_profit_neto = sum(b['profit_neto'] for b in bets)
    avg_odds = sum(b['odds'] for b in bets) / total_bets if total_bets > 0 else 0
    win_rate = wins / total_bets * 100 if total_bets > 0 else 0
    roi_bruto = total_profit_bruto / total_staked * 100 if total_staked > 0 else 0
    roi_neto = total_profit_neto / total_staked * 100 if total_staked > 0 else 0

    print()
    print("=" * 110)
    print("  RESUMEN")
    print("=" * 110)
    print()
    print(f"  Apuestas realizadas:    {total_bets}")
    print(f"  Ganadas:                {wins} ({win_rate:.1f}%)")
    print(f"  Perdidas:               {losses}")
    print(f"  Cuota promedio:         {avg_odds:.2f}")
    print(f"  Break-even win rate:    {100/avg_odds:.1f}%")
    print()
    print(f"  Total apostado:         {total_staked:.2f} EUR ({total_bets} x {STAKE:.0f} EUR)")
    print(f"  Beneficio bruto:        {total_profit_bruto:+.2f} EUR")
    print(f"  Comisiones Betfair (5%): -{total_comision:.2f} EUR")
    print(f"  BENEFICIO NETO:         {total_profit_neto:+.2f} EUR")
    print()
    print(f"  ROI bruto:              {roi_bruto:+.1f}%")
    print(f"  ROI neto (con comision): {roi_neto:+.1f}%")
    print()

    # Evolucion del bankroll
    print("-" * 60)
    print("  EVOLUCION DEL BANKROLL (neto)")
    print("-" * 60)

    bankroll = 0
    max_bankroll = 0
    min_bankroll = 0
    max_drawdown = 0
    peak = 0
    best_streak = 0
    worst_streak = 0
    current_streak = 0

    for b in bets:
        bankroll += b['profit_neto']

        if bankroll > max_bankroll:
            max_bankroll = bankroll
        if bankroll < min_bankroll:
            min_bankroll = bankroll

        if bankroll > peak:
            peak = bankroll
        dd = peak - bankroll
        if dd > max_drawdown:
            max_drawdown = dd

        if b['draw']:
            if current_streak >= 0:
                current_streak += 1
            else:
                current_streak = 1
        else:
            if current_streak <= 0:
                current_streak -= 1
            else:
                current_streak = -1

        if current_streak > best_streak:
            best_streak = current_streak
        if current_streak < worst_streak:
            worst_streak = current_streak

    print(f"  Bankroll maximo:         {max_bankroll:+.2f} EUR")
    print(f"  Bankroll minimo:         {min_bankroll:+.2f} EUR")
    print(f"  Max drawdown:            {max_drawdown:.2f} EUR")
    print(f"  Mejor racha ganadora:    {best_streak} seguidas")
    print(f"  Peor racha perdedora:    {abs(worst_streak)} seguidas")
    print()

    # Desglose por minuto de entrada
    print("-" * 60)
    print("  DESGLOSE POR MINUTO DE ENTRADA")
    print("-" * 60)

    for lo, hi in [(30, 45), (45, 60), (60, 75), (75, 95)]:
        subset = [b for b in bets if lo <= b['entry_min'] < hi]
        if not subset:
            continue
        n = len(subset)
        w = sum(1 for b in subset if b['draw'])
        staked = n * STAKE
        profit = sum(b['profit_neto'] for b in subset)
        avg_o = sum(b['odds'] for b in subset) / n
        roi = profit / staked * 100
        print(f"  Min {lo}-{hi}: {n} apuestas, {w} ganadas ({w/n*100:.0f}%), cuota avg {avg_o:.2f}, P/L neto {profit:+.2f} EUR, ROI {roi:+.1f}%")

    # Desglose por marcador de entrada
    print()
    print("-" * 60)
    print("  DESGLOSE POR MARCADOR AL ENTRAR")
    print("-" * 60)

    scores = set(b['entry_score'] for b in bets)
    for sc in sorted(scores):
        subset = [b for b in bets if b['entry_score'] == sc]
        n = len(subset)
        w = sum(1 for b in subset if b['draw'])
        profit = sum(b['profit_neto'] for b in subset)
        avg_o = sum(b['odds'] for b in subset) / n
        roi = profit / (n * STAKE) * 100
        print(f"  Marcador {sc}: {n} apuestas, {w} ganadas ({w/n*100:.0f}%), cuota avg {avg_o:.2f}, P/L neto {profit:+.2f} EUR, ROI {roi:+.1f}%")

    print()

    # Partidos sin apuesta
    if skipped:
        print("-" * 60)
        print(f"  PARTIDOS SIN APUESTA ({len(skipped)})")
        print("-" * 60)
        for name, score, reason in skipped[:10]:
            print(f"  - {name[:50]:<50} ({score}) - {reason}")
        if len(skipped) > 10:
            print(f"  ... y {len(skipped) - 10} mas")


if __name__ == '__main__':
    main()
