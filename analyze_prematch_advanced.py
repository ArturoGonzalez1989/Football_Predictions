"""
Análisis avanzado de estrategias pre-match

Investigación exhaustiva de múltiples estrategias y optimización de parámetros
"""

import pandas as pd
from pathlib import Path
import numpy as np
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Directorios
HISTORIC_DIR = Path(r"C:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\historic_data")

def load_all_seasons() -> pd.DataFrame:
    """Carga todos los archivos Excel (todas las hojas)"""
    all_data = []
    for xlsx_file in sorted(HISTORIC_DIR.glob("*.xlsx")):
        excel_file = pd.ExcelFile(xlsx_file)
        season = xlsx_file.stem.replace("all-euro-", "")
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(xlsx_file, sheet_name=sheet_name)
            df['Season'] = season
            df['League'] = sheet_name
            all_data.append(df)
    return pd.concat(all_data, ignore_index=True)

def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y prepara los datos"""
    df = df[df['FTHG'].notna() & df['FTAG'].notna()].copy()
    df['TotalGoals'] = df['FTHG'] + df['FTAG']
    df['FTR'] = df.apply(lambda x: 'H' if x['FTHG'] > x['FTAG'] else ('A' if x['FTAG'] > x['FTHG'] else 'D'), axis=1)
    df['Div'] = df['Div'].str.strip()
    df['BTTS'] = (df['FTHG'] > 0) & (df['FTAG'] > 0)
    return df

def calc_strategy_metrics(candidates: pd.DataFrame, odds_col: str, win_condition) -> Dict:
    """Calcula métricas de una estrategia"""
    if len(candidates) == 0 or odds_col not in candidates.columns:
        return {'bets': 0, 'won': 0, 'wr': 0, 'pl': 0, 'roi': 0}

    candidates = candidates[candidates[odds_col].notna()].copy()
    if len(candidates) == 0:
        return {'bets': 0, 'won': 0, 'wr': 0, 'pl': 0, 'roi': 0}

    candidates['Won'] = win_condition(candidates)
    candidates['PL'] = candidates.apply(
        lambda x: (x[odds_col] - 1) * 10 * 0.95 if x['Won'] else -10,
        axis=1
    )

    total_staked = len(candidates) * 10
    return {
        'bets': len(candidates),
        'won': candidates['Won'].sum(),
        'wr': round(candidates['Won'].mean() * 100, 1) if len(candidates) > 0 else 0,
        'pl': round(candidates['PL'].sum(), 2),
        'roi': round(candidates['PL'].sum() / total_staked * 100, 1) if total_staked > 0 else 0,
    }

# ═══════════════════════════════════════════════════════════════════════
# ESTRATEGIAS
# ═══════════════════════════════════════════════════════════════════════

def strategy_btts(df: pd.DataFrame, min_odds: float = 1.6, max_odds: float = 2.0) -> Dict:
    """Both Teams To Score - usando Over 2.5 como proxy"""
    # Ligas con alto BTTS%
    league_stats = df.groupby('Div')['BTTS'].mean()
    btts_leagues = league_stats[league_stats > 0.55].index.tolist()

    candidates = df[
        (df['Div'].isin(btts_leagues)) &
        (df['B365>2.5'].notna()) &
        (df['B365>2.5'] >= min_odds) &
        (df['B365>2.5'] <= max_odds)
    ].copy()

    result = calc_strategy_metrics(
        candidates,
        'B365>2.5',
        lambda x: x['BTTS']  # Verificamos BTTS real aunque apostamos Over 2.5
    )
    result['leagues'] = btts_leagues[:5]
    return result

def strategy_away_underdog(df: pd.DataFrame, min_odds: float = 2.5, max_odds: float = 5.0) -> Dict:
    """Back Away cuando visitante es underdog moderado"""
    candidates = df[
        (df['B365A'].notna()) &
        (df['B365A'] >= min_odds) &
        (df['B365A'] <= max_odds) &
        (df['B365H'].notna()) &
        (df['B365H'] < 2.0)  # Home es favorito
    ].copy()

    return calc_strategy_metrics(
        candidates,
        'B365A',
        lambda x: x['FTR'] == 'A'
    )

def strategy_draw_low_scoring(df: pd.DataFrame, min_draw_odds: float = 3.0) -> Dict:
    """Draw en ligas defensivas con odds altas"""
    league_avg = df.groupby('Div')['TotalGoals'].mean()
    defensive = league_avg[league_avg < 2.5].index.tolist()

    candidates = df[
        (df['Div'].isin(defensive)) &
        (df['B365D'].notna()) &
        (df['B365D'] >= min_draw_odds) &
        (df['B365H'].notna()) &
        (df['B365A'].notna()) &
        # Partidos equilibrados
        (abs(df['B365H'] - df['B365A']) < 0.5)
    ].copy()

    result = calc_strategy_metrics(
        candidates,
        'B365D',
        lambda x: x['FTR'] == 'D'
    )
    result['leagues'] = defensive[:5]
    return result

def strategy_home_favorite_value(df: pd.DataFrame, max_odds: float = 1.6) -> Dict:
    """Back Home favorito con odds 1.3-1.6 (value zone)"""
    candidates = df[
        (df['B365H'].notna()) &
        (df['B365H'] >= 1.30) &
        (df['B365H'] <= max_odds)
    ].copy()

    return calc_strategy_metrics(
        candidates,
        'B365H',
        lambda x: x['FTR'] == 'H'
    )

def strategy_over_btts_combo(df: pd.DataFrame, min_over_odds: float = 1.6) -> Dict:
    """Over 2.5 en ligas con alto BTTS%"""
    league_btts = df.groupby('Div')['BTTS'].mean()
    high_btts = league_btts[league_btts > 0.55].index.tolist()

    candidates = df[
        (df['Div'].isin(high_btts)) &
        (df['B365>2.5'].notna()) &
        (df['B365>2.5'] >= min_over_odds)
    ].copy()

    result = calc_strategy_metrics(
        candidates,
        'B365>2.5',
        lambda x: x['TotalGoals'] > 2.5
    )
    result['leagues'] = high_btts[:5]
    return result

def strategy_under_tight_defense(df: pd.DataFrame, min_odds: float = 1.7) -> Dict:
    """Under 2.5 cuando ambos equipos son defensivos (proxy: away goals bajo)"""
    league_away = df.groupby('Div')['FTAG'].mean()
    defensive = league_away[league_away < 1.15].index.tolist()

    candidates = df[
        (df['Div'].isin(defensive)) &
        (df['B365<2.5'].notna()) &
        (df['B365<2.5'] >= min_odds) &
        (df['B365H'].notna()) &
        (df['B365H'] < 2.2)  # No mucho dominio home
    ].copy()

    result = calc_strategy_metrics(
        candidates,
        'B365<2.5',
        lambda x: x['TotalGoals'] < 2.5
    )
    result['leagues'] = defensive[:5]
    return result

def grid_search_lay_favorite(df: pd.DataFrame) -> pd.DataFrame:
    """Grid search para encontrar threshold óptimo de lay favorito"""
    results = []

    for max_odds in [1.20, 1.25, 1.30, 1.35, 1.40, 1.45, 1.50]:
        candidates = df[
            (df['B365H'].notna()) &
            (df['B365H'] <= max_odds)
        ].copy()

        if len(candidates) == 0:
            continue

        candidates['Won'] = candidates['FTR'] != 'H'
        candidates['EffectiveOdds'] = 1 / (1 - 1/candidates['B365H'])
        candidates['PL'] = candidates.apply(
            lambda x: (x['EffectiveOdds'] - 1) * 10 * 0.95 if x['Won'] else -10,
            axis=1
        )

        total_staked = len(candidates) * 10
        results.append({
            'Max Odds': max_odds,
            'Bets': len(candidates),
            'Won': candidates['Won'].sum(),
            'WR%': round(candidates['Won'].mean() * 100, 1),
            'P/L': round(candidates['PL'].sum(), 2),
            'ROI%': round(candidates['PL'].sum() / total_staked * 100, 1),
        })

    return pd.DataFrame(results)

def analyze_by_season(df: pd.DataFrame) -> pd.DataFrame:
    """Analiza ROI de lay favorito por temporada (detectar cambios)"""
    results = []

    for season in sorted(df['Season'].unique()):
        season_df = df[df['Season'] == season]
        candidates = season_df[
            (season_df['B365H'].notna()) &
            (season_df['B365H'] <= 1.30)
        ].copy()

        if len(candidates) == 0:
            continue

        candidates['Won'] = candidates['FTR'] != 'H'
        candidates['EffectiveOdds'] = 1 / (1 - 1/candidates['B365H'])
        candidates['PL'] = candidates.apply(
            lambda x: (x['EffectiveOdds'] - 1) * 10 * 0.95 if x['Won'] else -10,
            axis=1
        )

        total_staked = len(candidates) * 10
        results.append({
            'Season': season,
            'Bets': len(candidates),
            'WR%': round(candidates['Won'].mean() * 100, 1),
            'P/L': round(candidates['PL'].sum(), 2),
            'ROI%': round(candidates['PL'].sum() / total_staked * 100, 1),
        })

    return pd.DataFrame(results)

def main():
    print("=" * 100)
    print("ANÁLISIS AVANZADO DE ESTRATEGIAS PRE-MATCH")
    print("=" * 100)
    print("\nCargando datos históricos...")

    df = load_all_seasons()
    df = clean_data(df)

    print(f"[OK] {len(df):,} partidos cargados")
    print(f"[OK] {df['Season'].nunique()} temporadas")
    print(f"[OK] {df['Div'].nunique()} ligas")

    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("NUEVAS ESTRATEGIAS")
    print("=" * 100)

    strategies = [
        ("BTTS (Both Teams Score)", strategy_btts(df, min_odds=1.8, max_odds=2.3)),
        ("Away Underdog (2.5-5.0 odds)", strategy_away_underdog(df, min_odds=2.5, max_odds=5.0)),
        ("Draw Low-Scoring Leagues", strategy_draw_low_scoring(df, min_draw_odds=3.0)),
        ("Home Favorite Value (1.3-1.6)", strategy_home_favorite_value(df, max_odds=1.6)),
        ("Over 2.5 + High BTTS%", strategy_over_btts_combo(df, min_over_odds=1.6)),
        ("Under 2.5 Tight Defense", strategy_under_tight_defense(df, min_odds=1.7)),
    ]

    for name, result in strategies:
        print(f"\n{name}")
        print("-" * 100)
        if result['bets'] == 0:
            print("  [!] Sin datos suficientes")
            continue

        color = "[+]" if result['roi'] > 0 else "[-]"
        print(f"  {color} Apuestas: {result['bets']:,}")
        print(f"  {color} Win Rate: {result['wr']}%")
        print(f"  {color} P/L: {result['pl']:+,.2f} EUR")
        print(f"  {color} ROI: {result['roi']:+.1f}%")
        if 'leagues' in result and result['leagues']:
            print(f"  Ligas: {', '.join(str(x) for x in result['leagues'][:5])}")

    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("OPTIMIZACIÓN: LAY FAVORITO (Grid Search)")
    print("=" * 100)
    grid_results = grid_search_lay_favorite(df)
    print(grid_results.to_string(index=False))

    best_row = grid_results.loc[grid_results['ROI%'].idxmax()]
    print(f"\n[***] MEJOR THRESHOLD: Max Odds {best_row['Max Odds']} -> ROI {best_row['ROI%']:+.1f}%")

    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("ANÁLISIS POR TEMPORADA (Lay Favorito @ 1.30)")
    print("=" * 100)
    season_results = analyze_by_season(df)
    print(season_results.to_string(index=False))

    avg_roi = season_results['ROI%'].mean()
    print(f"\nROI Promedio: {avg_roi:+.1f}%")
    print(f"Consistencia: {'[OK] Positivo en todas' if season_results['ROI%'].min() > 0 else '[!] Inconsistente entre temporadas'}")

    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 100)
    print("RESUMEN EJECUTIVO")
    print("=" * 100)

    all_strategies = [
        ("Lay Favorito @ 1.30", grid_results[grid_results['Max Odds'] == 1.30].iloc[0]['ROI%'] if len(grid_results[grid_results['Max Odds'] == 1.30]) > 0 else 0),
        ("Home Favorite Value", strategies[3][1]['roi']),
        ("Away Underdog", strategies[1][1]['roi']),
        ("BTTS", strategies[0][1]['roi']),
        ("Over 2.5 High BTTS", strategies[4][1]['roi']),
    ]

    profitable = [(name, roi) for name, roi in all_strategies if roi > 3]

    if profitable:
        print("\n[OK] ESTRATEGIAS RENTABLES (ROI > 3%):")
        for name, roi in sorted(profitable, key=lambda x: x[1], reverse=True):
            print(f"  - {name}: {roi:+.1f}%")
    else:
        print("\n[!] NINGUNA ESTRATEGIA SUPERA +3% ROI")
        print("\nMejor estrategia:")
        best = max(all_strategies, key=lambda x: x[1])
        print(f"  - {best[0]}: {best[1]:+.1f}%")

    print("\n" + "=" * 100)

if __name__ == "__main__":
    main()
