#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simula Half-Kelly para verificar si el cálculo de €7,588 es correcto
Analiza las primeras 20 apuestas del CSV Max P/L
"""

import csv
from io import StringIO

# Primeras filas del CSV Max P/L (ordenadas cronológicamente)
csv_data = """match,match_id,csv_file,timestamp_utc,strategy,minuto,score,ft_score,won,pl,back_draw,back_over_odds,over_line,back_odds,drift_pct,xg_total,xg_excess,poss_diff,shots_total,sot_total,sot_max,passes_v15,passes_v2r,passes_v2,passes_v3,passes_v4,team,goal_diff
"Corinthians Red Bull Bragantino",corinthians-red-bull-bragantino-apuestas-35207556,corinthians-red-bull-bragantino-apuestas-35207556.csv,2026-02-13 00:30:55,xG Underperf,62,1-0,2-0,1,6.17,,1.65,Over 1.5,,,,1.24,,,,,0,0,1,0,0,away,
"Corinthians Red Bull Bragantino",corinthians-red-bull-bragantino-apuestas-35207556,corinthians-red-bull-bragantino-apuestas-35207556.csv,2026-02-13 00:30:55,Goal Clustering,62,,2-0,1,6.17,,,,,,,,,,,4,0,0,0,0,0,,
"Corinthians Red Bull Bragantino",corinthians-red-bull-bragantino-apuestas-35207556,corinthians-red-bull-bragantino-apuestas-35207556.csv,2026-02-13 00:42:49,Odds Drift,75,2-0,2-0,1,7.5,,,,1.79,53,,,,,,,0,0,1,0,1,home,2
"Corinthians Red Bull Bragantino",corinthians-red-bull-bragantino-apuestas-35207556,corinthians-red-bull-bragantino-apuestas-35207556.csv,2026-02-13 00:42:49,Goal Clustering,75,,2-0,0,-10,,,,,,,,,,,4,0,0,0,0,0,,
"Internacional Se Palmeiras",internacional-se-palmeiras-apuestas-35224753,internacional-se-palmeiras-apuestas-35224753.csv,2026-02-13 00:53:56,Odds Drift,22,0-1,0-1,1,14.82,,,,2.56,36.2,,,,,,,0,0,0,0,0,away,1
"Spartak Varna Lokomotiv Sofia",spartak-varna-lokomotiv-sofia-apuestas-35239864,spartak-varna-lokomotiv-sofia-apuestas-35239864.csv,2026-02-13 16:02:04,Odds Drift,14,1-0,2-2,0,-10,,,,1.81,69.2,,,,,,,0,0,0,0,0,home,1
"Spartak Varna Lokomotiv Sofia",spartak-varna-lokomotiv-sofia-apuestas-35239864,spartak-varna-lokomotiv-sofia-apuestas-35239864.csv,2026-02-13 17:23:18,Goal Clustering,77,,2-2,1,25.17,,,,,,,,,,,5,0,0,0,0,0,,
"Galatasaray Eyupspor",galatasaray-eyupspor-apuestas-35243984,galatasaray-eyupspor-apuestas-35243984.csv,2026-02-13 17:35:20,Odds Drift,33,2-0,5-1,1,8.83,,,,1.93,82.1,,,,,,,0,0,1,0,0,home,2
"Galatasaray Eyupspor",galatasaray-eyupspor-apuestas-35243984,galatasaray-eyupspor-apuestas-35243984.csv,2026-02-13 17:35:20,Goal Clustering,33,,5-1,1,2.76,,,,,,,,,,,5,0,0,0,0,0,,
"Anorthosis Digenis Ypsona",anorthosis-digenis-ypsona-apuestas-35247517,anorthosis-digenis-ypsona-apuestas-35247517.csv,2026-02-13 17:41:23,Goal Clustering,36,,1-1,1,3.52,,,,,,,,,,,3,0,0,0,0,0,,
"NÃºremberg Karlsruhe",nÃºremberg-karlsruhe-apuestas-35243488,nÃºremberg-karlsruhe-apuestas-35243488.csv,2026-02-13 17:59:05,Goal Clustering,28,,5-1,1,5.42,,,,,,,,,,,3,0,0,0,0,0,,
"Galatasaray Eyupspor",galatasaray-eyupspor-apuestas-35243984,galatasaray-eyupspor-apuestas-35243984.csv,2026-02-13 18:08:03,Goal Clustering,47,,5-1,1,7.6,,,,,,,,,,,5,0,0,0,0,0,,
"NÃºremberg Karlsruhe",nÃºremberg-karlsruhe-apuestas-35243488,nÃºremberg-karlsruhe-apuestas-35243488.csv,2026-02-13 18:11:03,Goal Clustering,40,,5-1,1,14.44,,,,,,,,,,,5,0,0,0,0,0,,
"NÃºremberg Karlsruhe",nÃºremberg-karlsruhe-apuestas-35243488,nÃºremberg-karlsruhe-apuestas-35243488.csv,2026-02-13 18:14:03,Odds Drift,43,3-0,5-1,1,40.85,,,,5.3,390.7,,,,,,,0,0,1,1,0,home,3
"NÃºremberg Karlsruhe",nÃºremberg-karlsruhe-apuestas-35243488,nÃºremberg-karlsruhe-apuestas-35243488.csv,2026-02-13 18:41:16,Goal Clustering,50,,5-1,1,32.3,,,,,,,,,,,7,0,0,0,0,0,,
"Liverpool Montevideo Defensor Sp",liverpool-montevideo-defensor-sp-apuestas-35238332,liverpool-montevideo-defensor-sp-apuestas-35238332.csv,2026-02-14 01:03:33,Odds Drift,32,0-1,1-2,1,13.87,,,,2.46,123.6,,,,,,,0,0,0,1,0,away,1
"Liverpool Montevideo Defensor Sp",liverpool-montevideo-defensor-sp-apuestas-35238332,liverpool-montevideo-defensor-sp-apuestas-35238332.csv,2026-02-14 01:14:48,Goal Clustering,43,,1-2,1,11.97,,,,,,,,,,,3,0,0,0,0,0,,
"America De Cali Sa Santa Fe",america-de-cali-sa-santa-fe-apuestas-35238051,america-de-cali-sa-santa-fe-apuestas-35238051.csv,2026-02-14 02:42:05,Odds Drift,75,1-0,1-0,1,55.1,,,,6.8,78.9,,,,,,,0,0,0,0,0,home,1
"America De Cali Sa Santa Fe",america-de-cali-sa-santa-fe-apuestas-35238051,america-de-cali-sa-santa-fe-apuestas-35238051.csv,2026-02-14 02:42:05,Goal Clustering,75,,1-0,0,-10,,,,,,,,,,,5,0,0,0,0,0,,
"Hertha BerlÃ­n Hannover",hertha-berlÃ­n-hannover-apuestas-35243477,hertha-berlÃ­n-hannover-apuestas-35243477.csv,2026-02-14 12:08:12,Odds Drift,7,0-1,2-3,1,156.75,,,,17.5,635.3,,,,,,,0,0,0,1,0,away,1"""

def get_bet_odds(row):
    """Obtener cuota de la apuesta"""
    odds = row.get('back_odds') or row.get('back_over_odds') or row.get('back_draw')
    return float(odds) if odds and odds != '' else 2.0

def simulate_half_kelly(csv_text, initial_bankroll=500):
    """Simula Half-Kelly con las apuestas del CSV"""
    FLAT_STAKE = 10
    KELLY_MIN_BETS = 5

    bankroll = initial_bankroll
    rolling_wins = 0
    total_pl_flat = 0

    print("="*100)
    print(f"SIMULACION HALF-KELLY | Bankroll Inicial: EUR {initial_bankroll}")
    print("="*100)
    print(f"{'#':<4} {'Match':<30} {'Won':<5} {'Odds':<6} {'WR':<7} {'Stake%':<8} {'Stake':<8} {'P/L':<10} {'BR':<10}")
    print("-"*100)

    reader = csv.DictReader(StringIO(csv_text))
    for i, row in enumerate(reader):
        match = row['match'][:28]
        won = int(row['won'])
        pl_flat = float(row['pl'])
        odds = get_bet_odds(row)

        total_pl_flat += pl_flat

        # Win rate rolling (solo apuestas previas)
        rolling_wr = rolling_wins / i if i > 0 else 0.5

        # Calcula stake % (Half-Kelly)
        b_net = max(odds - 1, 0.01)
        if i < KELLY_MIN_BETS:
            stake_pct = 0.01  # 1% primeras 5 apuestas
        else:
            f = (rolling_wr * b_net - (1 - rolling_wr)) / b_net
            stake_pct = max(0, min(f / 2, 0.04))  # cap 4%

        # Stake y P/L gestionado
        stake = round(bankroll * stake_pct, 2)
        ratio = stake / FLAT_STAKE
        pl_managed = round(pl_flat * ratio, 2)
        bankroll = round(bankroll + pl_managed, 2)

        # Update rolling wins DESPUÉS
        if won:
            rolling_wins += 1

        # Print cada apuesta
        print(f"{i+1:<4} {match:<30} {won:<5} {odds:<6.2f} {rolling_wr:<7.1%} {stake_pct:<8.2%} {stake:<8.2f} {pl_managed:>+10.2f} {bankroll:>10.2f}")

        if i >= 19:  # Solo primeras 20
            break

    print("-"*100)
    print(f"{'TOTAL (20 apuestas)':<50} {'':20} {total_pl_flat:>+10.2f} {bankroll:>10.2f}")
    print(f"P/L Flat Total: EUR {total_pl_flat:.2f}")
    print(f"P/L Gestion: EUR {bankroll - initial_bankroll:.2f} (ROI: {(bankroll - initial_bankroll) / initial_bankroll * 100:.1f}%)")
    print("="*100)

if __name__ == "__main__":
    simulate_half_kelly(csv_data, 500)
