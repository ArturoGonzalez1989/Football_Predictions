#!/usr/bin/env python3
"""Analiza datos pre-partido disponibles en los CSVs del scraper."""

import pandas as pd
import glob
import os
from datetime import datetime

DATA_DIR = r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data'

def main():
    files = glob.glob(os.path.join(DATA_DIR, 'partido_*.csv'))

    prematch_matches = []
    no_prematch = []

    for f in files:
        try:
            df = pd.read_csv(f)
            if 'estado_partido' not in df.columns:
                continue

            match_name = os.path.basename(f).replace('partido_', '').replace('.csv', '')

            # Filas pre-partido
            pre = df[df['estado_partido'] == 'pre_partido']

            if len(pre) == 0:
                no_prematch.append(match_name)
                continue

            # Convertir columnas
            for col in ['back_home', 'back_draw', 'back_away', 'lay_home', 'lay_draw', 'lay_away']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            pre = df[df['estado_partido'] == 'pre_partido'].copy()

            # Timestamps
            timestamps = []
            ts_col = 'timestamp_utc' if 'timestamp_utc' in pre.columns else 'timestamp'
            if ts_col in pre.columns:
                for ts in pre[ts_col]:
                    try:
                        t = pd.to_datetime(ts)
                        timestamps.append(t)
                    except:
                        pass

            # Primera fila en_juego (kickoff approx)
            ingame = df[df['estado_partido'] == 'en_juego']
            kickoff_ts = None
            ts_col_ig = 'timestamp_utc' if 'timestamp_utc' in ingame.columns else 'timestamp'
            if len(ingame) > 0 and ts_col_ig in ingame.columns:
                try:
                    kickoff_ts = pd.to_datetime(ingame[ts_col_ig].iloc[0])
                except:
                    pass

            # Cuotas pre-partido
            back_home_vals = pre['back_home'].dropna().tolist() if 'back_home' in pre.columns else []
            back_draw_vals = pre['back_draw'].dropna().tolist() if 'back_draw' in pre.columns else []
            back_away_vals = pre['back_away'].dropna().tolist() if 'back_away' in pre.columns else []

            # Minutos antes del kickoff
            mins_before = []
            if kickoff_ts and timestamps:
                for ts in timestamps:
                    diff = (kickoff_ts - ts).total_seconds() / 60
                    if diff > 0:
                        mins_before.append(round(diff, 1))

            prematch_matches.append({
                'match': match_name,
                'pre_rows': len(pre),
                'first_ts': str(timestamps[0]) if timestamps else '?',
                'last_ts': str(timestamps[-1]) if timestamps else '?',
                'kickoff_ts': str(kickoff_ts) if kickoff_ts else '?',
                'mins_before_first': max(mins_before) if mins_before else '?',
                'mins_before_last': min(mins_before) if mins_before else '?',
                'back_home_first': back_home_vals[0] if back_home_vals else None,
                'back_draw_first': back_draw_vals[0] if back_draw_vals else None,
                'back_away_first': back_away_vals[0] if back_away_vals else None,
                'back_home_last': back_home_vals[-1] if back_home_vals else None,
                'back_draw_last': back_draw_vals[-1] if back_draw_vals else None,
                'back_away_last': back_away_vals[-1] if back_away_vals else None,
            })

        except Exception as e:
            pass

    print("=" * 120)
    print("  DATOS PRE-PARTIDO DISPONIBLES EN EL SCRAPER")
    print("=" * 120)
    print()
    print(f"  Partidos CON datos pre-match: {len(prematch_matches)}")
    print(f"  Partidos SIN datos pre-match: {len(no_prematch)}")
    print()

    print("-" * 120)
    header_note = "(ultima captura pre)"
    print(f"  {'#':<4} {'Partido':<55} {'Filas':<6} {'Min antes':<20} {'Back H':<9} {'Back D':<9} {'Back A':<9} {header_note}")
    print("-" * 120)

    for i, m in enumerate(sorted(prematch_matches, key=lambda x: str(x['mins_before_first']), reverse=True), 1):
        mins_str = f"{m['mins_before_first']}-{m['mins_before_last']} min" if m['mins_before_first'] != '?' else "?"
        bh = f"{m['back_home_last']:.2f}" if m['back_home_last'] else "?"
        bd = f"{m['back_draw_last']:.2f}" if m['back_draw_last'] else "?"
        ba = f"{m['back_away_last']:.2f}" if m['back_away_last'] else "?"
        print(f"  {i:<4} {m['match'][:53]:<55} {m['pre_rows']:<6} {mins_str:<20} {bh:<9} {bd:<9} {ba:<9}")

    # Detalle con timestamps
    print()
    print("=" * 120)
    print("  DETALLE DE TIMESTAMPS")
    print("=" * 120)
    print()
    print(f"  {'Partido':<55} {'Primera captura pre':<25} {'Ultima captura pre':<25} {'Kickoff (1er en_juego)':<25}")
    print(f"  {'-'*120}")

    for m in sorted(prematch_matches, key=lambda x: str(x['first_ts'])):
        first = m['first_ts'][:19] if m['first_ts'] != '?' else '?'
        last = m['last_ts'][:19] if m['last_ts'] != '?' else '?'
        kick = m['kickoff_ts'][:19] if m['kickoff_ts'] != '?' else '?'
        print(f"  {m['match'][:53]:<55} {first:<25} {last:<25} {kick:<25}")

    # Cuotas detalladas para comparacion
    print()
    print("=" * 120)
    print("  CUOTAS PRE-PARTIDO PARA COMPARACION CON FUENTE EXTERNA")
    print("=" * 120)
    print()
    print(f"  {'Partido':<55} {'Back Home':<12} {'Back Draw':<12} {'Back Away':<12} {'Fecha captura':<20}")
    print(f"  {'-'*110}")

    for m in sorted(prematch_matches, key=lambda x: x['match']):
        bh = f"{m['back_home_last']:.2f}" if m['back_home_last'] else "N/A"
        bd = f"{m['back_draw_last']:.2f}" if m['back_draw_last'] else "N/A"
        ba = f"{m['back_away_last']:.2f}" if m['back_away_last'] else "N/A"
        ts = m['last_ts'][:16] if m['last_ts'] != '?' else '?'
        print(f"  {m['match'][:53]:<55} {bh:<12} {bd:<12} {ba:<12} {ts:<20}")

    print()
    print(f"  NOTA: Estas son cuotas de la ULTIMA captura pre-partido (la mas cercana al kickoff).")
    print(f"  Son cuotas BACK de Betfair Exchange, no de casas de apuestas tradicionales.")


if __name__ == '__main__':
    main()
