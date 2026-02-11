"""
EDA - Analisis Exploratorio de Datos del Scraper de Betfair
"""
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Cargar datos
print("=" * 80)
print("ANALISIS EXPLORATORIO DE DATOS - BETFAIR SCRAPER")
print("=" * 80)
print()

df = pd.read_csv('data/unificado.csv')

# Información básica
print(f"[*]� Dataset: {df.shape[0]} filas × {df.shape[1]} columnas")
print(f"[*]� Partidos únicos: {df['tab_id'].nunique()}")
print()

# Ver partidos
print("[*] PARTIDOS EN EL DATASET:")
print("-" * 80)
for partido in df['tab_id'].unique():
    partido_df = df[df['tab_id'] == partido]
    print(f"\n{partido}")
    print(f"  • Capturas: {len(partido_df)}")
    print(f"  • Estado: {partido_df['estado_partido'].iloc[-1]}")
    print(f"  • Resultado final: {partido_df['goles_local'].iloc[-1]}-{partido_df['goles_visitante'].iloc[-1]}")
    if 'minuto' in partido_df.columns:
        min_inicio = partido_df['minuto'].iloc[0] if pd.notna(partido_df['minuto'].iloc[0]) else 'N/A'
        min_final = partido_df['minuto'].iloc[-1] if pd.notna(partido_df['minuto'].iloc[-1]) else 'N/A'
        print(f"  • Cobertura temporal: min {min_inicio} → min {min_final}")

print("\n" + "=" * 80)
print()

# Análisis de completitud de datos
print("[*]� COMPLETITUD DE DATOS:")
print("-" * 80)

# Calcular porcentaje de datos no vacíos por partido
for partido in df['tab_id'].unique():
    partido_df = df[df['tab_id'] == partido]

    # Contar columnas con datos
    non_empty = partido_df.notna().sum(axis=1).mean()
    total_cols = len(partido_df.columns)
    pct = (non_empty / total_cols) * 100

    print(f"\n{partido.split('-')[0][:30]}...")
    print(f"  • Promedio columnas con datos: {non_empty:.1f}/{total_cols} ({pct:.1f}%)")

    # Ver qué tipos de datos tiene
    tiene_stats = partido_df['xg_local'].notna().any()
    tiene_attacking = partido_df['big_chances_local'].notna().any()
    tiene_defence = partido_df['tackles_local'].notna().any()
    tiene_distribution = partido_df['crosses_local'].notna().any()
    tiene_momentum = partido_df['momentum_local'].notna().any()

    print(f"  • Stats Summary: {'[*]' if tiene_stats else '[*]'}")
    print(f"  • Stats Attacking: {'[*]' if tiene_attacking else '[*]'}")
    print(f"  • Stats Defence: {'[*]' if tiene_defence else '[*]'}")
    print(f"  • Stats Distribution: {'[*]' if tiene_distribution else '[*]'}")
    print(f"  • Momentum: {'[*]' if tiene_momentum else '[*]'}")

print("\n" + "=" * 80)
print()

# Análisis temporal del partido con más datos
partido_completo = df.groupby('tab_id').size().idxmax()
partido_df = df[df['tab_id'] == partido_completo].copy()

if len(partido_df) > 1 and partido_df['xg_local'].notna().any():
    print(f"[*]� ANÁLISIS TEMPORAL: {partido_completo.split('-')[0][:40]}")
    print("-" * 80)
    print()

    # Convertir timestamp
    partido_df['timestamp'] = pd.to_datetime(partido_df['timestamp'])
    partido_df = partido_df.sort_values('timestamp')

    # Análisis de xG
    if partido_df['xg_local'].notna().any():
        print("[*]� EVOLUCIÓN xG (Expected Goals):")
        xg_data = partido_df[['minuto', 'xg_local', 'xg_visitante']].dropna()
        if len(xg_data) > 0:
            print(xg_data.to_string(index=False))
            print()

            # Calcular tendencia
            xg_local_final = float(xg_data['xg_local'].iloc[-1])
            xg_visit_final = float(xg_data['xg_visitante'].iloc[-1])
            print(f"  • xG Final: Local {xg_local_final:.2f} - {xg_visit_final:.2f} Visitante")

            if xg_local_final > xg_visit_final:
                print(f"  • El equipo LOCAL dominó las ocasiones ({xg_local_final - xg_visit_final:.2f} xG de diferencia)")
            elif xg_visit_final > xg_local_final:
                print(f"  • El equipo VISITANTE dominó las ocasiones ({xg_visit_final - xg_local_final:.2f} xG de diferencia)")
            else:
                print(f"  • Partido EQUILIBRADO en ocasiones")

    print()

    # Análisis de Momentum
    if partido_df['momentum_local'].notna().any():
        print("[*] EVOLUCIÓN MOMENTUM:")
        momentum_data = partido_df[['minuto', 'momentum_local', 'momentum_visitante']].dropna()
        if len(momentum_data) > 0:
            print(momentum_data.to_string(index=False))
            print()

            # Calcular tendencia
            mom_local_final = float(momentum_data['momentum_local'].iloc[-1])
            mom_visit_final = float(momentum_data['momentum_visitante'].iloc[-1])
            total_momentum = mom_local_final + mom_visit_final
            pct_local = (mom_local_final / total_momentum) * 100 if total_momentum > 0 else 0

            print(f"  • Momentum Final: Local {mom_local_final:.2f} ({pct_local:.1f}%) - Visitante {mom_visit_final:.2f} ({100-pct_local:.1f}%)")

            if pct_local > 65:
                print(f"  • Dominio CLARO del equipo local en momentum")
            elif pct_local < 35:
                print(f"  • Dominio CLARO del equipo visitante en momentum")
            else:
                print(f"  • Partido EQUILIBRADO en momentum")

    print()

    # Análisis de Odds (cuotas)
    if partido_df['back_home'].notna().any():
        print("[*]� EVOLUCIÓN DE CUOTAS (Match Odds):")
        odds_data = partido_df[['minuto', 'back_home', 'back_draw', 'back_away']].dropna()
        if len(odds_data) > 0:
            # Mostrar primera y última
            print(f"\n  Minuto {odds_data['minuto'].iloc[0]}: Local {odds_data['back_home'].iloc[0]:.2f} | Empate {odds_data['back_draw'].iloc[0]:.2f} | Visitante {odds_data['back_away'].iloc[0]:.2f}")
            print(f"  Minuto {odds_data['minuto'].iloc[-1]}: Local {odds_data['back_home'].iloc[-1]:.2f} | Empate {odds_data['back_draw'].iloc[-1]:.2f} | Visitante {odds_data['back_away'].iloc[-1]:.2f}")

            # Análisis de cambio
            home_inicio = float(odds_data['back_home'].iloc[0])
            home_final = float(odds_data['back_home'].iloc[-1])
            away_inicio = float(odds_data['back_away'].iloc[0])
            away_final = float(odds_data['back_away'].iloc[-1])

            print()
            if home_final < home_inicio:
                cambio = ((home_inicio - home_final) / home_inicio) * 100
                print(f"  • Cuota LOCAL BAJÓ {cambio:.1f}% → El mercado cree más en victoria local")
            elif home_final > home_inicio:
                cambio = ((home_final - home_inicio) / home_inicio) * 100
                print(f"  • Cuota LOCAL SUBIÓ {cambio:.1f}% → El mercado cree menos en victoria local")

            if away_final < away_inicio:
                cambio = ((away_inicio - away_final) / away_inicio) * 100
                print(f"  • Cuota VISITANTE BAJÓ {cambio:.1f}% → El mercado cree más en victoria visitante")
            elif away_final > away_inicio:
                cambio = ((away_final - away_inicio) / away_inicio) * 100
                print(f"  • Cuota VISITANTE SUBIÓ {cambio:.1f}% → El mercado cree menos en victoria visitante")

print()
print("=" * 80)
print()

# Insights finales
print("[*]� INSIGHTS Y CONCLUSIONES:")
print("-" * 80)
print()

# Buscar el partido con más datos
if df['xg_local'].notna().any():
    partido_completo_df = df[df['xg_local'].notna()].iloc[0:1]

    xg_local = float(partido_completo_df['xg_local'].iloc[0])
    xg_visitante = float(partido_completo_df['xg_visitante'].iloc[0])
    goles_local = int(partido_completo_df['goles_local'].iloc[0])
    goles_visitante = int(partido_completo_df['goles_visitante'].iloc[0])

    print("1. EFICIENCIA EN FINALIZACIÓN:")
    print(f"   • Local: {goles_local} goles con {xg_local:.2f} xG → Eficiencia: {(goles_local/xg_local*100) if xg_local > 0 else 0:.1f}%")
    print(f"   • Visitante: {goles_visitante} goles con {xg_visitante:.2f} xG → Eficiencia: {(goles_visitante/xg_visitante*100) if xg_visitante > 0 else 0:.1f}%")

    if goles_local > xg_local * 1.5:
        print(f"   [*][*] Local marcó MÁS de lo esperado → Sobreperformance o suerte")
    elif goles_local < xg_local * 0.5:
        print(f"   [*][*] Local marcó MENOS de lo esperado → Baja eficiencia o mala suerte")

    print()

print("2. CALIDAD DEL DATASET:")
print(f"   • Total de capturas: {len(df)}")
print(f"   • Partidos con estadísticas completas: {df['xg_local'].notna().sum()} capturas")
print(f"   • Partidos con datos limitados: {len(df) - df['xg_local'].notna().sum()} capturas")
print()

print("3. POTENCIAL DE ANÁLISIS:")
if df['xg_local'].notna().any():
    print("   [*] Análisis de xG vs Resultado real")
    print("   [*] Análisis de momentum y su correlación con resultado")
    print("   [*] Evolución temporal de cuotas")
    print("   [*] Análisis de mercado (valor en apuestas)")
else:
    print("   [*][*] Con más partidos con stats completas podríamos:")
    print("     - Predecir resultados usando xG")
    print("     - Detectar valor en cuotas")
    print("     - Identificar patrones de momentum")

print()
print("=" * 80)
print("[*] Análisis completado")
