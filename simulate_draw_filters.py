#!/usr/bin/env python3
"""
Analisis de filtros para refinar la estrategia Back Empate 0-0 desde min 30.
Filtro 1: Estadisticas al minuto 30 (tiros, xG, posesion, tiros a puerta)
Filtro 2: Cuotas pre-partido del empate
"""

import pandas as pd
import numpy as np
import glob
import os

DATA_DIR = r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data'
STAKE = 10.0
COMISION = 0.05

def hr(c='=', w=90):
    print(c * w)

def main():
    files = glob.glob(os.path.join(DATA_DIR, 'partido_*.csv'))

    matches_data = []

    for f in files:
        try:
            df = pd.read_csv(f)
            if 'estado_partido' not in df.columns:
                continue

            match_name = os.path.basename(f).replace('partido_', '').replace('.csv', '')

            for col in ['minuto', 'goles_local', 'goles_visitante', 'back_draw',
                        'back_home', 'back_away',
                        'tiros_local', 'tiros_visitante',
                        'tiros_puerta_local', 'tiros_puerta_visitante',
                        'xg_local', 'xg_visitante',
                        'posesion_local', 'posesion_visitante',
                        'corners_local', 'corners_visitante']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Resultado final
            final_rows = df[df['estado_partido'] == 'finalizado']
            if len(final_rows) == 0:
                final_rows = df.tail(1)
            final_h = final_rows['goles_local'].iloc[-1]
            final_a = final_rows['goles_visitante'].iloc[-1]
            if pd.isna(final_h) or pd.isna(final_a):
                continue
            ended_draw = (int(final_h) == int(final_a))
            final_score = f"{int(final_h)}-{int(final_a)}"

            # Cuotas pre-partido (primera fila con estado pre_partido o la primera fila)
            pre_rows = df[df['estado_partido'] == 'pre_partido']
            pre_draw_odds = None
            pre_home_odds = None
            pre_away_odds = None
            if len(pre_rows) > 0:
                pre_draw_odds = pre_rows['back_draw'].dropna().iloc[0] if len(pre_rows['back_draw'].dropna()) > 0 else None
                pre_home_odds = pre_rows['back_home'].dropna().iloc[0] if len(pre_rows['back_home'].dropna()) > 0 else None
                pre_away_odds = pre_rows['back_away'].dropna().iloc[0] if len(pre_rows['back_away'].dropna()) > 0 else None

            # Buscar momento 0-0 a partir de min 30
            ingame = df[df['estado_partido'].isin(['en_juego', 'descanso'])].copy()
            ingame = ingame.sort_values('minuto')

            entry_row = None
            for _, row in ingame.iterrows():
                minute = row.get('minuto')
                goals_h = row.get('goles_local')
                goals_a = row.get('goles_visitante')
                back_draw = row.get('back_draw')

                if pd.isna(minute) or pd.isna(goals_h) or pd.isna(goals_a) or pd.isna(back_draw):
                    continue

                if minute >= 30 and goals_h == 0 and goals_a == 0 and back_draw > 1.01:
                    entry_row = row
                    break

            if entry_row is None:
                continue

            # Stats al momento del trigger
            entry_min = int(entry_row['minuto'])
            odds = entry_row['back_draw']
            shots_h = entry_row.get('tiros_local', np.nan)
            shots_a = entry_row.get('tiros_visitante', np.nan)
            sot_h = entry_row.get('tiros_puerta_local', np.nan)
            sot_a = entry_row.get('tiros_puerta_visitante', np.nan)
            xg_h = entry_row.get('xg_local', np.nan)
            xg_a = entry_row.get('xg_visitante', np.nan)
            poss_h = entry_row.get('posesion_local', np.nan)
            poss_a = entry_row.get('posesion_visitante', np.nan)
            corners_h = entry_row.get('corners_local', np.nan)
            corners_a = entry_row.get('corners_visitante', np.nan)

            total_shots = (shots_h or 0) + (shots_a or 0) if not pd.isna(shots_h) and not pd.isna(shots_a) else np.nan
            total_sot = (sot_h or 0) + (sot_a or 0) if not pd.isna(sot_h) and not pd.isna(sot_a) else np.nan
            total_xg = (xg_h or 0) + (xg_a or 0) if not pd.isna(xg_h) and not pd.isna(xg_a) else np.nan
            max_xg = max(xg_h or 0, xg_a or 0) if not pd.isna(xg_h) and not pd.isna(xg_a) else np.nan
            poss_diff = abs((poss_h or 50) - (poss_a or 50)) if not pd.isna(poss_h) else np.nan
            total_corners = (corners_h or 0) + (corners_a or 0) if not pd.isna(corners_h) and not pd.isna(corners_a) else np.nan

            # P/L
            if ended_draw:
                profit_bruto = (odds - 1) * STAKE
                profit_neto = profit_bruto - (profit_bruto * COMISION)
            else:
                profit_bruto = -STAKE
                profit_neto = -STAKE

            matches_data.append({
                'match': match_name[:45],
                'entry_min': entry_min,
                'odds': odds,
                'final_score': final_score,
                'draw': ended_draw,
                'profit_neto': profit_neto,
                'total_shots': total_shots,
                'total_sot': total_sot,
                'total_xg': total_xg,
                'max_xg': max_xg,
                'poss_diff': poss_diff,
                'total_corners': total_corners,
                'shots_h': shots_h, 'shots_a': shots_a,
                'sot_h': sot_h, 'sot_a': sot_a,
                'xg_h': xg_h, 'xg_a': xg_a,
                'pre_draw_odds': pre_draw_odds,
                'pre_home_odds': pre_home_odds,
                'pre_away_odds': pre_away_odds,
            })

        except Exception:
            pass

    if not matches_data:
        print("No hay datos.")
        return

    df_all = pd.DataFrame(matches_data)
    n_total = len(df_all)
    wins_total = df_all['draw'].sum()
    pl_total = df_all['profit_neto'].sum()

    hr('*')
    print("  ANALISIS DE FILTROS - ESTRATEGIA BACK EMPATE 0-0 DESDE MIN 30")
    hr('*')
    print()
    print(f"  Base: {n_total} apuestas en partidos 0-0 al min 30+")
    print(f"  Win rate base: {wins_total}/{n_total} = {wins_total/n_total*100:.1f}%")
    print(f"  P/L base: {pl_total:+.2f} EUR | ROI: {pl_total/(n_total*STAKE)*100:+.1f}%")

    # ==================================================================
    # FILTRO 1: ESTADISTICAS AL MINUTO 30
    # ==================================================================
    hr()
    print("  FILTRO 1: ESTADISTICAS AL MOMENTO DEL TRIGGER")
    hr()

    # 1a. Total tiros
    print()
    print("  1a. TIROS TOTALES al momento del trigger")
    print(f"  {'Filtro':<30} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*68}")

    valid_shots = df_all[df_all['total_shots'].notna()]
    for lo, hi, label in [(0, 4, "0-3 tiros"), (4, 8, "4-7 tiros"), (8, 12, "8-11 tiros"), (12, 50, "12+ tiros")]:
        subset = valid_shots[(valid_shots['total_shots'] >= lo) & (valid_shots['total_shots'] < hi)]
        if len(subset) > 0:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            print(f"  {label:<30} {len(subset):<5} {int(w):<5} {w/len(subset)*100:>5.1f}%  {pl:>+9.2f} EUR {roi:>+6.1f}%")

    # 1b. Tiros a puerta
    print()
    print("  1b. TIROS A PUERTA TOTALES al trigger")
    print(f"  {'Filtro':<30} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*68}")

    valid_sot = df_all[df_all['total_sot'].notna()]
    for lo, hi, label in [(0, 1, "0 tiros a puerta"), (1, 3, "1-2 tiros a puerta"), (3, 5, "3-4 tiros a puerta"), (5, 50, "5+ tiros a puerta")]:
        subset = valid_sot[(valid_sot['total_sot'] >= lo) & (valid_sot['total_sot'] < hi)]
        if len(subset) > 0:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            print(f"  {label:<30} {len(subset):<5} {int(w):<5} {w/len(subset)*100:>5.1f}%  {pl:>+9.2f} EUR {roi:>+6.1f}%")

    # 1c. xG total
    print()
    print("  1c. xG TOTAL COMBINADO al trigger")
    print(f"  {'Filtro':<30} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*68}")

    valid_xg = df_all[df_all['total_xg'].notna()]
    for lo, hi, label in [(0, 0.5, "xG total < 0.5"), (0.5, 1.0, "xG total 0.5-1.0"), (1.0, 1.5, "xG total 1.0-1.5"), (1.5, 10, "xG total 1.5+")]:
        subset = valid_xg[(valid_xg['total_xg'] >= lo) & (valid_xg['total_xg'] < hi)]
        if len(subset) > 0:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            print(f"  {label:<30} {len(subset):<5} {int(w):<5} {w/len(subset)*100:>5.1f}%  {pl:>+9.2f} EUR {roi:>+6.1f}%")

    # 1d. xG maximo de un equipo
    print()
    print("  1d. xG MAXIMO de un solo equipo al trigger")
    print(f"  {'Filtro':<30} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*68}")

    valid_maxg = df_all[df_all['max_xg'].notna()]
    for lo, hi, label in [(0, 0.3, "Max xG equipo < 0.3"), (0.3, 0.6, "Max xG equipo 0.3-0.6"), (0.6, 1.0, "Max xG equipo 0.6-1.0"), (1.0, 10, "Max xG equipo 1.0+")]:
        subset = valid_maxg[(valid_maxg['max_xg'] >= lo) & (valid_maxg['max_xg'] < hi)]
        if len(subset) > 0:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            print(f"  {label:<30} {len(subset):<5} {int(w):<5} {w/len(subset)*100:>5.1f}%  {pl:>+9.2f} EUR {roi:>+6.1f}%")

    # 1e. Diferencia de posesion
    print()
    print("  1e. DIFERENCIA DE POSESION (|home - away|) al trigger")
    print(f"  {'Filtro':<30} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*68}")

    valid_poss = df_all[df_all['poss_diff'].notna()]
    for lo, hi, label in [(0, 10, "Poss diff < 10%"), (10, 20, "Poss diff 10-20%"), (20, 50, "Poss diff 20%+")]:
        subset = valid_poss[(valid_poss['poss_diff'] >= lo) & (valid_poss['poss_diff'] < hi)]
        if len(subset) > 0:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            print(f"  {label:<30} {len(subset):<5} {int(w):<5} {w/len(subset)*100:>5.1f}%  {pl:>+9.2f} EUR {roi:>+6.1f}%")

    # 1f. Corners totales
    print()
    print("  1f. CORNERS TOTALES al trigger")
    print(f"  {'Filtro':<30} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*68}")

    valid_corners = df_all[df_all['total_corners'].notna()]
    for lo, hi, label in [(0, 3, "0-2 corners"), (3, 6, "3-5 corners"), (6, 10, "6-9 corners"), (10, 50, "10+ corners")]:
        subset = valid_corners[(valid_corners['total_corners'] >= lo) & (valid_corners['total_corners'] < hi)]
        if len(subset) > 0:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            print(f"  {label:<30} {len(subset):<5} {int(w):<5} {w/len(subset)*100:>5.1f}%  {pl:>+9.2f} EUR {roi:>+6.1f}%")

    # ==================================================================
    # FILTRO 2: CUOTAS PRE-PARTIDO
    # ==================================================================
    hr()
    print("  FILTRO 2: CUOTAS PRE-PARTIDO")
    hr()

    # 2a. Cuota pre-partido del empate
    print()
    print("  2a. CUOTA PRE-PARTIDO DEL EMPATE")
    print(f"  {'Filtro':<30} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*68}")

    valid_pre = df_all[df_all['pre_draw_odds'].notna() & (df_all['pre_draw_odds'] > 1)]
    for lo, hi, label in [(1, 3.0, "Draw pre < 3.00"), (3.0, 3.5, "Draw pre 3.00-3.50"), (3.5, 4.0, "Draw pre 3.50-4.00"), (4.0, 20, "Draw pre 4.00+")]:
        subset = valid_pre[(valid_pre['pre_draw_odds'] >= lo) & (valid_pre['pre_draw_odds'] < hi)]
        if len(subset) > 0:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            avg_pre = subset['pre_draw_odds'].mean()
            print(f"  {label:<30} {len(subset):<5} {int(w):<5} {w/len(subset)*100:>5.1f}%  {pl:>+9.2f} EUR {roi:>+6.1f}%  (avg pre: {avg_pre:.2f})")

    # 2b. Ratio entre favorito y no favorito (cuanto de asimetrico es el partido)
    print()
    print("  2b. ASIMETRIA DEL PARTIDO (cuota favorito pre-partido)")
    print(f"  {'Filtro':<30} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*68}")

    valid_asym = df_all[df_all['pre_home_odds'].notna() & df_all['pre_away_odds'].notna() & (df_all['pre_home_odds'] > 1) & (df_all['pre_away_odds'] > 1)]
    if len(valid_asym) > 0:
        valid_asym = valid_asym.copy()
        valid_asym['fav_odds'] = valid_asym[['pre_home_odds', 'pre_away_odds']].min(axis=1)
        valid_asym['underdog_odds'] = valid_asym[['pre_home_odds', 'pre_away_odds']].max(axis=1)
        valid_asym['odds_ratio'] = valid_asym['underdog_odds'] / valid_asym['fav_odds']

        for lo, hi, label in [(1.0, 1.5, "Muy equilibrado (<1.5x)"), (1.5, 2.5, "Equilibrado (1.5-2.5x)"), (2.5, 4.0, "Asimetrico (2.5-4x)"), (4.0, 50, "Muy asimetrico (4x+)")]:
            subset = valid_asym[(valid_asym['odds_ratio'] >= lo) & (valid_asym['odds_ratio'] < hi)]
            if len(subset) > 0:
                w = subset['draw'].sum()
                pl = subset['profit_neto'].sum()
                roi = pl / (len(subset) * STAKE) * 100
                avg_fav = subset['fav_odds'].mean()
                print(f"  {label:<30} {len(subset):<5} {int(w):<5} {w/len(subset)*100:>5.1f}%  {pl:>+9.2f} EUR {roi:>+6.1f}%  (avg fav: {avg_fav:.2f})")

    # ==================================================================
    # FILTROS COMBINADOS
    # ==================================================================
    hr()
    print("  FILTROS COMBINADOS - Buscando la regla optima")
    hr()
    print()

    combos = []

    # Combo: xG total bajo + 0-0
    for xg_max in [0.5, 0.8, 1.0, 1.5]:
        subset = df_all[(df_all['total_xg'].notna()) & (df_all['total_xg'] < xg_max)]
        if len(subset) >= 3:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            combos.append((f"xG total < {xg_max}", len(subset), int(w), w/len(subset)*100, pl, roi))

    # Combo: tiros a puerta bajos
    for sot_max in [1, 2, 3]:
        subset = df_all[(df_all['total_sot'].notna()) & (df_all['total_sot'] < sot_max)]
        if len(subset) >= 3:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            combos.append((f"Tiros puerta < {sot_max}", len(subset), int(w), w/len(subset)*100, pl, roi))

    # Combo: cuota pre draw
    for pre_max in [3.2, 3.5, 3.8]:
        subset = df_all[(df_all['pre_draw_odds'].notna()) & (df_all['pre_draw_odds'] < pre_max)]
        if len(subset) >= 3:
            w = subset['draw'].sum()
            pl = subset['profit_neto'].sum()
            roi = pl / (len(subset) * STAKE) * 100
            combos.append((f"Draw pre < {pre_max}", len(subset), int(w), w/len(subset)*100, pl, roi))

    # Combo: xG bajo + cuota pre baja
    for xg_max in [0.8, 1.0, 1.5]:
        for pre_max in [3.5, 4.0]:
            subset = df_all[
                (df_all['total_xg'].notna()) & (df_all['total_xg'] < xg_max) &
                (df_all['pre_draw_odds'].notna()) & (df_all['pre_draw_odds'] < pre_max)
            ]
            if len(subset) >= 3:
                w = subset['draw'].sum()
                pl = subset['profit_neto'].sum()
                roi = pl / (len(subset) * STAKE) * 100
                combos.append((f"xG<{xg_max} + pre draw<{pre_max}", len(subset), int(w), w/len(subset)*100, pl, roi))

    # Combo: tiros a puerta bajo + posesion equilibrada
    subset = df_all[
        (df_all['total_sot'].notna()) & (df_all['total_sot'] <= 2) &
        (df_all['poss_diff'].notna()) & (df_all['poss_diff'] < 15)
    ]
    if len(subset) >= 3:
        w = subset['draw'].sum()
        pl = subset['profit_neto'].sum()
        roi = pl / (len(subset) * STAKE) * 100
        combos.append((f"SoT<=2 + poss diff<15%", len(subset), int(w), w/len(subset)*100, pl, roi))

    # Combo: xG bajo + tiros a puerta bajo
    for xg_max in [0.8, 1.0]:
        for sot_max in [2, 3]:
            subset = df_all[
                (df_all['total_xg'].notna()) & (df_all['total_xg'] < xg_max) &
                (df_all['total_sot'].notna()) & (df_all['total_sot'] < sot_max)
            ]
            if len(subset) >= 3:
                w = subset['draw'].sum()
                pl = subset['profit_neto'].sum()
                roi = pl / (len(subset) * STAKE) * 100
                combos.append((f"xG<{xg_max} + SoT<{sot_max}", len(subset), int(w), w/len(subset)*100, pl, roi))

    # Ordenar por ROI
    combos.sort(key=lambda x: x[5], reverse=True)

    print(f"  {'Filtro combinado':<35} {'N':<5} {'Win':<5} {'Win%':<8} {'P/L neto':<12} {'ROI':<8}")
    print(f"  {'-'*73}")
    for c in combos:
        print(f"  {c[0]:<35} {c[1]:<5} {c[2]:<5} {c[3]:>5.1f}%  {c[4]:>+9.2f} EUR {c[5]:>+6.1f}%")

    # ==================================================================
    # DETALLE: Mejores filtros aplicados a cada partido
    # ==================================================================
    print()
    hr()
    print("  DETALLE: CADA PARTIDO CON STATS AL TRIGGER")
    hr()
    print()
    print(f"  {'Partido':<40} {'Min':<5} {'Tiros':<6} {'SoT':<5} {'xG tot':<7} {'Poss diff':<10} {'Pre draw':<10} {'Final':<7} {'P/L':<10}")
    print(f"  {'-'*100}")

    for _, row in df_all.sort_values('draw', ascending=False).iterrows():
        ts = f"{row['total_shots']:.0f}" if not pd.isna(row['total_shots']) else "?"
        sot = f"{row['total_sot']:.0f}" if not pd.isna(row['total_sot']) else "?"
        xg = f"{row['total_xg']:.2f}" if not pd.isna(row['total_xg']) else "?"
        pd_val = f"{row['poss_diff']:.0f}%" if not pd.isna(row['poss_diff']) else "?"
        pre = f"{row['pre_draw_odds']:.2f}" if not pd.isna(row['pre_draw_odds']) else "?"
        result = "DRAW" if row['draw'] else "NO"
        print(f"  {row['match']:<40} {row['entry_min']:<5} {ts:<6} {sot:<5} {xg:<7} {pd_val:<10} {pre:<10} {row['final_score']:<7} {row['profit_neto']:>+8.2f}")

    print()


if __name__ == '__main__':
    main()
