"""
Análisis de estrategias pre-match usando datos históricos de football-data.co.uk

Estrategias a investigar:
1. Under 2.5 en ligas defensivas
2. Over 2.5 en ligas ofensivas
3. Back empate cuando odds home/away similares
4. Lay favorito fuerte (odds < 1.30)
5. Value bets basadas en forma reciente
"""

import pandas as pd
from pathlib import Path
import numpy as np
from typing import Dict, List, Tuple

# Directorios
HISTORIC_DIR = Path(r"C:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\historic_data")

def load_all_seasons() -> pd.DataFrame:
    """Carga todos los archivos Excel (todas las hojas) y combina en un solo DataFrame"""
    all_data = []

    for xlsx_file in sorted(HISTORIC_DIR.glob("*.xlsx")):
        print(f"Cargando {xlsx_file.name}...")
        try:
            # Leer todas las hojas del Excel
            excel_file = pd.ExcelFile(xlsx_file)
            season = xlsx_file.stem.replace("all-euro-", "")

            for sheet_name in excel_file.sheet_names:
                df = pd.read_excel(xlsx_file, sheet_name=sheet_name)
                df['Season'] = season
                df['League'] = sheet_name
                all_data.append(df)
                print(f"  {sheet_name}: {len(df)} partidos")
        except Exception as e:
            print(f"  Error: {e}")

    combined = pd.concat(all_data, ignore_index=True)
    print(f"\nTotal partidos cargados: {len(combined):,}")
    return combined

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y prepara los datos"""
    # Filtrar solo partidos completos (con resultado)
    df = df[df['FTHG'].notna() & df['FTAG'].notna()].copy()

    # Calcular goles totales
    df['TotalGoals'] = df['FTHG'] + df['FTAG']

    # Resultado
    df['FTR'] = df.apply(lambda x: 'H' if x['FTHG'] > x['FTAG'] else ('A' if x['FTAG'] > x['FTHG'] else 'D'), axis=1)

    # Limpiar divisiones (algunos tienen espacios o inconsistencias)
    df['Div'] = df['Div'].str.strip()

    print(f"Partidos después de limpieza: {len(df):,}")
    print(f"Temporadas: {sorted(df['Season'].unique())}")
    print(f"Ligas: {df['Div'].nunique()}")

    return df

def analyze_league_characteristics(df: pd.DataFrame) -> pd.DataFrame:
    """Analiza características de cada liga"""
    league_stats = df.groupby('Div').agg({
        'TotalGoals': ['mean', 'std'],
        'FTHG': 'mean',
        'FTAG': 'mean',
        'FTR': lambda x: (x == 'D').sum() / len(x) * 100,  # % empates
    }).round(2)

    league_stats.columns = ['AvgGoals', 'StdGoals', 'AvgHomeGoals', 'AvgAwayGoals', 'DrawPct']
    league_stats = league_stats.sort_values('AvgGoals', ascending=False)

    # Añadir conteo de partidos
    league_stats['Matches'] = df.groupby('Div').size()

    return league_stats

def strategy_under_25(df: pd.DataFrame, min_odds: float = 1.8) -> Dict:
    """
    Estrategia: Back Under 2.5 en ligas con promedio < 2.3 goles
    """
    # Calcular promedio de goles por liga
    league_avg = df.groupby('Div')['TotalGoals'].mean()
    defensive_leagues = league_avg[league_avg < 2.3].index.tolist()

    # Filtrar partidos en ligas defensivas con odds >= min_odds
    candidates = df[
        (df['Div'].isin(defensive_leagues)) &
        (df['B365<2.5'].notna()) &
        (df['B365<2.5'] >= min_odds)
    ].copy()

    if len(candidates) == 0:
        return {'bets': 0, 'won': 0, 'wr': 0, 'pl': 0, 'roi': 0}

    # Resultado: ganamos si total goles < 2.5
    candidates['Won'] = candidates['TotalGoals'] < 2.5
    candidates['PL'] = candidates.apply(
        lambda x: (x['B365<2.5'] - 1) * 10 * 0.95 if x['Won'] else -10,
        axis=1
    )

    return {
        'bets': len(candidates),
        'won': candidates['Won'].sum(),
        'wr': round(candidates['Won'].mean() * 100, 1),
        'pl': round(candidates['PL'].sum(), 2),
        'roi': round(candidates['PL'].sum() / (len(candidates) * 10) * 100, 1),
        'leagues': defensive_leagues,
    }

def strategy_over_25(df: pd.DataFrame, min_odds: float = 1.8) -> Dict:
    """
    Estrategia: Back Over 2.5 en ligas con promedio >= 2.7 goles
    """
    league_avg = df.groupby('Div')['TotalGoals'].mean()
    offensive_leagues = league_avg[league_avg >= 2.7].index.tolist()

    candidates = df[
        (df['Div'].isin(offensive_leagues)) &
        (df['B365>2.5'].notna()) &
        (df['B365>2.5'] >= min_odds)
    ].copy()

    if len(candidates) == 0:
        return {'bets': 0, 'won': 0, 'wr': 0, 'pl': 0, 'roi': 0}

    candidates['Won'] = candidates['TotalGoals'] > 2.5
    candidates['PL'] = candidates.apply(
        lambda x: (x['B365>2.5'] - 1) * 10 * 0.95 if x['Won'] else -10,
        axis=1
    )

    return {
        'bets': len(candidates),
        'won': candidates['Won'].sum(),
        'wr': round(candidates['Won'].mean() * 100, 1),
        'pl': round(candidates['PL'].sum(), 2),
        'roi': round(candidates['PL'].sum() / (len(candidates) * 10) * 100, 1),
        'leagues': offensive_leagues,
    }

def strategy_draw_balanced(df: pd.DataFrame, min_odds: float = 3.0, max_diff: float = 0.4) -> Dict:
    """
    Estrategia: Back Draw cuando home y away tienen odds similares (partidos equilibrados)
    """
    candidates = df[
        (df['B365H'].notna()) &
        (df['B365A'].notna()) &
        (df['B365D'].notna()) &
        (df['B365D'] >= min_odds) &
        (abs(df['B365H'] - df['B365A']) <= max_diff)
    ].copy()

    if len(candidates) == 0:
        return {'bets': 0, 'won': 0, 'wr': 0, 'pl': 0, 'roi': 0}

    candidates['Won'] = candidates['FTR'] == 'D'
    candidates['PL'] = candidates.apply(
        lambda x: (x['B365D'] - 1) * 10 * 0.95 if x['Won'] else -10,
        axis=1
    )

    return {
        'bets': len(candidates),
        'won': candidates['Won'].sum(),
        'wr': round(candidates['Won'].mean() * 100, 1),
        'pl': round(candidates['PL'].sum(), 2),
        'roi': round(candidates['PL'].sum() / (len(candidates) * 10) * 100, 1),
    }

def strategy_lay_strong_favorite(df: pd.DataFrame, max_odds: float = 1.30) -> Dict:
    """
    Estrategia: Lay favorito fuerte (odds < 1.30)
    Simulamos como Back Away OR Draw
    """
    candidates = df[
        (df['B365H'].notna()) &
        (df['B365H'] <= max_odds)
    ].copy()

    if len(candidates) == 0:
        return {'bets': 0, 'won': 0, 'wr': 0, 'pl': 0, 'roi': 0}

    # Ganamos si NO gana home
    candidates['Won'] = candidates['FTR'] != 'H'

    # Lay simulation: ganamos stake si pierde favorito, perdemos (odds-1)*stake si gana
    # Simplificado: usamos la inversa como si fuera back odds del resultado contrario
    # Aproximación: odds "not home" ≈ 1 / (1 - (1/odds_home))
    candidates['EffectiveOdds'] = 1 / (1 - 1/candidates['B365H'])
    candidates['PL'] = candidates.apply(
        lambda x: (x['EffectiveOdds'] - 1) * 10 * 0.95 if x['Won'] else -10,
        axis=1
    )

    return {
        'bets': len(candidates),
        'won': candidates['Won'].sum(),
        'wr': round(candidates['Won'].mean() * 100, 1),
        'pl': round(candidates['PL'].sum(), 2),
        'roi': round(candidates['PL'].sum() / (len(candidates) * 10) * 100, 1),
    }

def main():
    print("=" * 80)
    print("ANÁLISIS DE ESTRATEGIAS PRE-MATCH")
    print("=" * 80)
    print()

    # Cargar datos
    df = load_all_seasons()
    df = clean_data(df)

    print("\n" + "=" * 80)
    print("CARACTERÍSTICAS POR LIGA")
    print("=" * 80)
    league_stats = analyze_league_characteristics(df)
    print(league_stats.head(20).to_string())

    print("\n" + "=" * 80)
    print("RESULTADOS DE ESTRATEGIAS")
    print("=" * 80)

    strategies = [
        ("Under 2.5 (Ligas Defensivas)", strategy_under_25(df, min_odds=1.8)),
        ("Over 2.5 (Ligas Ofensivas)", strategy_over_25(df, min_odds=1.8)),
        ("Draw (Partidos Equilibrados)", strategy_draw_balanced(df, min_odds=3.0)),
        ("Lay Favorito Fuerte", strategy_lay_strong_favorite(df, max_odds=1.30)),
    ]

    for name, result in strategies:
        print(f"\n{name}")
        print("-" * 80)
        if result['bets'] == 0:
            print("  Sin datos suficientes")
            continue

        print(f"  Apuestas: {result['bets']:,}")
        print(f"  Ganadas: {result['won']:,} ({result['wr']}% WR)")
        print(f"  P/L: {result['pl']:+,.2f} EUR")
        print(f"  ROI: {result['roi']:+.1f}%")
        if 'leagues' in result:
            print(f"  Ligas: {', '.join(result['leagues'][:5])}{'...' if len(result['leagues']) > 5 else ''}")

    print("\n" + "=" * 80)
    print("ANÁLISIS COMPLETADO")
    print("=" * 80)

if __name__ == "__main__":
    main()
