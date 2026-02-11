"""
Trading Pattern Analysis - Betfair Exchange Football Data
Busca patrones rentables para trading de apuestas en vivo.
"""
import pandas as pd
import numpy as np
import os
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

def load_all_matches():
    """Carga todos los CSVs individuales de partidos."""
    matches = {}
    for f in os.listdir(DATA_DIR):
        if f.startswith('partido_') and f.endswith('.csv'):
            path = os.path.join(DATA_DIR, f)
            try:
                df = pd.read_csv(path)
                if len(df) > 1:
                    df['timestamp_utc'] = pd.to_datetime(df['timestamp_utc'])
                    df = df.sort_values('timestamp_utc').reset_index(drop=True)
                    match_id = df['tab_id'].iloc[0]
                    matches[match_id] = df
            except Exception:
                pass
    return matches

def spread(back, lay):
    """Calcula el spread porcentual."""
    if pd.isna(back) or pd.isna(lay) or back == 0:
        return np.nan
    return ((lay - back) / back) * 100

def implied_prob(odds):
    """Convierte cuota decimal a probabilidad implicita."""
    if pd.isna(odds) or odds <= 0:
        return np.nan
    return 1.0 / odds

print("=" * 80)
print("  TRADING PATTERN ANALYSIS - BETFAIR EXCHANGE")
print("=" * 80)
print()

matches = load_all_matches()
print(f"Partidos cargados: {len(matches)}")
print()

# ============================================================================
# 1. RESUMEN POR PARTIDO
# ============================================================================
print("=" * 80)
print("1. RESUMEN DE PARTIDOS")
print("=" * 80)

match_summaries = []
for match_id, df in sorted(matches.items(), key=lambda x: len(x[1]), reverse=True):
    n = len(df)
    goles_l = df['goles_local'].dropna()
    goles_v = df['goles_visitante'].dropna()

    # Detectar goles
    goal_events = []
    if len(goles_l) > 1:
        for i in range(1, len(df)):
            gl = df['goles_local'].iloc[i]
            gv = df['goles_visitante'].iloc[i]
            gl_prev = df['goles_local'].iloc[i-1]
            gv_prev = df['goles_visitante'].iloc[i-1]
            if pd.notna(gl) and pd.notna(gl_prev) and gl > gl_prev:
                goal_events.append(('LOCAL', df['minuto'].iloc[i], i))
            if pd.notna(gv) and pd.notna(gv_prev) and gv > gv_prev:
                goal_events.append(('VISIT', df['minuto'].iloc[i], i))

    resultado = f"{int(goles_l.iloc[-1]) if len(goles_l) > 0 else '?'}-{int(goles_v.iloc[-1]) if len(goles_v) > 0 else '?'}"
    minutos = df['minuto'].dropna()
    cobertura = f"min {int(minutos.iloc[0])}-{int(minutos.iloc[-1])}" if len(minutos) > 1 else "N/A"

    has_stats = df['opta_points_local'].notna().any()
    has_momentum = df['momentum_local'].notna().any()

    print(f"\n  {match_id[:55]}")
    print(f"    Capturas: {n} | Resultado: {resultado} | Cobertura: {cobertura}")
    print(f"    Goles detectados: {len(goal_events)} | Stats: {'SI' if has_stats else 'NO'} | Momentum: {'SI' if has_momentum else 'NO'}")

    for team, minute, idx in goal_events:
        print(f"    GOL {team} min {minute}")

    match_summaries.append({
        'match_id': match_id, 'n_capturas': n, 'resultado': resultado,
        'n_goles': len(goal_events), 'has_stats': has_stats, 'has_momentum': has_momentum,
        'goal_events': goal_events
    })

# ============================================================================
# 2. ANALISIS DE MOVIMIENTO DE CUOTAS TRAS GOL
# ============================================================================
print("\n\n" + "=" * 80)
print("2. MOVIMIENTO DE CUOTAS DESPUES DE UN GOL")
print("=" * 80)
print("   (Clave para trading: Back antes del gol, Lay despues)")

all_goal_analysis = []
for match_id, df in matches.items():
    if len(df) < 3:
        continue

    for i in range(1, len(df)):
        gl = df['goles_local'].iloc[i]
        gv = df['goles_visitante'].iloc[i]
        gl_prev = df['goles_local'].iloc[i-1]
        gv_prev = df['goles_visitante'].iloc[i-1]

        gol_local = pd.notna(gl) and pd.notna(gl_prev) and gl > gl_prev
        gol_visit = pd.notna(gv) and pd.notna(gv_prev) and gv > gv_prev

        if not gol_local and not gol_visit:
            continue

        team = 'LOCAL' if gol_local else 'VISIT'
        minuto = df['minuto'].iloc[i]

        # Cuotas ANTES del gol (fila anterior)
        back_home_before = df['back_home'].iloc[i-1]
        back_draw_before = df['back_draw'].iloc[i-1]
        back_away_before = df['back_away'].iloc[i-1]

        # Cuotas DESPUES del gol (fila actual)
        back_home_after = df['back_home'].iloc[i]
        back_draw_after = df['back_draw'].iloc[i]
        back_away_after = df['back_away'].iloc[i]

        # Cuotas 2-3 capturas despues (si existen)
        back_home_later = df['back_home'].iloc[min(i+2, len(df)-1)] if i+2 < len(df) else np.nan
        back_away_later = df['back_away'].iloc[min(i+2, len(df)-1)] if i+2 < len(df) else np.nan

        # Momentum antes del gol
        mom_local_before = df['momentum_local'].iloc[i-1] if pd.notna(df['momentum_local'].iloc[i-1]) else np.nan
        mom_visit_before = df['momentum_visitante'].iloc[i-1] if pd.notna(df['momentum_visitante'].iloc[i-1]) else np.nan

        all_goal_analysis.append({
            'match': match_id[:40], 'team': team, 'minuto': minuto,
            'bh_before': back_home_before, 'bh_after': back_home_after, 'bh_later': back_home_later,
            'bd_before': back_draw_before, 'bd_after': back_draw_after,
            'ba_before': back_away_before, 'ba_after': back_away_after, 'ba_later': back_away_later,
            'mom_local': mom_local_before, 'mom_visit': mom_visit_before,
        })

if all_goal_analysis:
    print(f"\n  Total goles detectados con datos de cuotas: {len(all_goal_analysis)}")

    for g in all_goal_analysis:
        print(f"\n  GOL {g['team']} (min {g['minuto']}) - {g['match']}")

        if pd.notna(g['bh_before']) and pd.notna(g['bh_after']):
            if g['team'] == 'LOCAL':
                cambio_scorer = ((g['bh_before'] - g['bh_after']) / g['bh_before']) * 100
                print(f"    Cuota Local:  {g['bh_before']:.2f} -> {g['bh_after']:.2f} (cayo {cambio_scorer:.1f}%)")
            else:
                cambio_scorer = ((g['ba_before'] - g['ba_after']) / g['ba_before']) * 100 if pd.notna(g['ba_before']) and pd.notna(g['ba_after']) else 0
                print(f"    Cuota Visit:  {g['ba_before']:.2f} -> {g['ba_after']:.2f} (cayo {cambio_scorer:.1f}%)")

            if pd.notna(g['bd_before']) and pd.notna(g['bd_after']):
                cambio_draw = ((g['bd_after'] - g['bd_before']) / g['bd_before']) * 100
                print(f"    Cuota Empate: {g['bd_before']:.2f} -> {g['bd_after']:.2f} (subio {cambio_draw:.1f}%)")

        if pd.notna(g['mom_local']) and pd.notna(g['mom_visit']):
            total_mom = g['mom_local'] + g['mom_visit']
            pct = (g['mom_local'] / total_mom * 100) if total_mom > 0 else 50
            print(f"    Momentum pre-gol: Local {pct:.0f}% - Visit {100-pct:.0f}%")
else:
    print("\n  No se detectaron goles con datos suficientes de cuotas.")

# ============================================================================
# 3. ANALISIS DE SPREAD (BACK - LAY) COMO INDICADOR DE LIQUIDEZ
# ============================================================================
print("\n\n" + "=" * 80)
print("3. ANALISIS DE SPREAD (BACK-LAY)")
print("=" * 80)
print("   Spread bajo = alta liquidez = buen momento para trading")

for match_id, df in matches.items():
    if len(df) < 5:
        continue

    df['spread_home'] = df.apply(lambda r: spread(r['back_home'], r['lay_home']), axis=1)
    df['spread_draw'] = df.apply(lambda r: spread(r['back_draw'], r['lay_draw']), axis=1)
    df['spread_away'] = df.apply(lambda r: spread(r['back_away'], r['lay_away']), axis=1)

    spreads = df[['minuto', 'spread_home', 'spread_draw', 'spread_away']].dropna()
    if len(spreads) > 0:
        print(f"\n  {match_id[:55]}")
        print(f"    Spread Home:  avg {spreads['spread_home'].mean():.2f}% | min {spreads['spread_home'].min():.2f}% | max {spreads['spread_home'].max():.2f}%")
        print(f"    Spread Draw:  avg {spreads['spread_draw'].mean():.2f}% | min {spreads['spread_draw'].min():.2f}% | max {spreads['spread_draw'].max():.2f}%")
        print(f"    Spread Away:  avg {spreads['spread_away'].mean():.2f}% | min {spreads['spread_away'].min():.2f}% | max {spreads['spread_away'].max():.2f}%")

# ============================================================================
# 4. CORRELACION MOMENTUM vs MOVIMIENTO DE CUOTAS
# ============================================================================
print("\n\n" + "=" * 80)
print("4. CORRELACION MOMENTUM vs CUOTAS")
print("=" * 80)
print("   Puede el momentum predecir hacia donde se mueven las cuotas?")

for match_id, df in matches.items():
    if len(df) < 5 or not df['momentum_local'].notna().any():
        continue

    # Calcular momentum ratio
    df['mom_ratio'] = df['momentum_local'] / (df['momentum_local'] + df['momentum_visitante'])

    # Calcular cambios en cuotas
    df['home_odds_change'] = df['back_home'].pct_change()
    df['away_odds_change'] = df['back_away'].pct_change()

    # Calcular cambio de momentum
    df['mom_ratio_change'] = df['mom_ratio'].diff()

    # Correlacion
    valid = df[['mom_ratio', 'back_home', 'mom_ratio_change', 'home_odds_change']].dropna()
    if len(valid) > 3:
        corr_level = valid['mom_ratio'].corr(valid['back_home'])
        corr_change = valid['mom_ratio_change'].corr(valid['home_odds_change'])

        print(f"\n  {match_id[:55]}")
        print(f"    Datos: {len(valid)} capturas con momentum + cuotas")
        print(f"    Corr(momentum_ratio, cuota_home): {corr_level:.3f}")
        print(f"      -> {'NEGATIVA (mas momentum = menor cuota = mas probable)' if corr_level < -0.3 else 'POSITIVA' if corr_level > 0.3 else 'DEBIL'}")
        print(f"    Corr(cambio_momentum, cambio_cuota): {corr_change:.3f}")
        print(f"      -> {'momentum PREDICE movimiento de cuotas' if abs(corr_change) > 0.3 else 'momentum NO predice cuotas a corto plazo'}")

# ============================================================================
# 5. ANALISIS ESTADISTICAS OPTA vs CUOTAS
# ============================================================================
print("\n\n" + "=" * 80)
print("5. ESTADISTICAS OPTA vs CUOTAS")
print("=" * 80)
print("   Las stats Opta se reflejan en las cuotas? Si no, hay valor!")

for match_id, df in matches.items():
    if len(df) < 5 or not df['opta_points_local'].notna().any():
        continue

    # Opta points ratio
    valid = df[['opta_points_local', 'opta_points_visitante', 'back_home', 'back_away',
                'posesion_local', 'tiros_local', 'tiros_visitante', 'tiros_puerta_local', 'tiros_puerta_visitante',
                'attacks_local', 'attacks_visitante']].dropna()

    if len(valid) < 3:
        continue

    valid['opta_ratio'] = valid['opta_points_local'] / (valid['opta_points_local'] + valid['opta_points_visitante'])
    valid['implied_home'] = valid['back_home'].apply(implied_prob)
    valid['shot_diff'] = valid['tiros_local'] - valid['tiros_visitante']
    valid['sot_diff'] = valid['tiros_puerta_local'] - valid['tiros_puerta_visitante']
    valid['attack_diff'] = valid['attacks_local'] - valid['attacks_visitante']

    corr_opta = valid['opta_ratio'].corr(valid['implied_home'])
    corr_shots = valid['shot_diff'].corr(valid['implied_home'])
    corr_sot = valid['sot_diff'].corr(valid['implied_home'])

    print(f"\n  {match_id[:55]} ({len(valid)} capturas)")
    print(f"    Corr(Opta_ratio, prob_implicita_home):  {corr_opta:.3f} {'ALINEADO' if abs(corr_opta) > 0.5 else 'DESALINEADO - posible valor!'}")
    print(f"    Corr(diff_tiros, prob_implicita_home):   {corr_shots:.3f}")
    print(f"    Corr(diff_tiros_puerta, prob_home):      {corr_sot:.3f}")

    # Verificar si hay discrepancia: equipo dominando stats pero cuota no refleja
    last = valid.iloc[-1]
    if last['opta_ratio'] > 0.6 and last['implied_home'] < 0.5:
        print(f"    ** POSIBLE VALOR: Local domina Opta ({last['opta_ratio']:.0%}) pero cuota implica solo {last['implied_home']:.0%}")
    elif last['opta_ratio'] < 0.4 and last['implied_home'] > 0.5:
        print(f"    ** POSIBLE VALOR: Local inferior en Opta ({last['opta_ratio']:.0%}) pero cuota implica {last['implied_home']:.0%}")

# ============================================================================
# 6. ANALISIS DE OVER/UNDER
# ============================================================================
print("\n\n" + "=" * 80)
print("6. MERCADO OVER/UNDER - MOVIMIENTO TEMPORAL")
print("=" * 80)
print("   Como se mueven las cuotas Over/Under durante el partido?")

for match_id, df in matches.items():
    if len(df) < 5:
        continue

    ou_cols = ['back_over25', 'back_under25', 'back_over15', 'back_under15']
    valid = df[['minuto'] + [c for c in ou_cols if c in df.columns]].dropna()

    if len(valid) < 3:
        continue

    print(f"\n  {match_id[:55]}")

    if 'back_over25' in valid.columns and len(valid) > 0:
        o25_inicio = valid['back_over25'].iloc[0]
        o25_final = valid['back_over25'].iloc[-1]
        u25_inicio = valid['back_under25'].iloc[0]
        u25_final = valid['back_under25'].iloc[-1]

        print(f"    Over 2.5:  {o25_inicio:.2f} -> {o25_final:.2f} | Under 2.5: {u25_inicio:.2f} -> {u25_final:.2f}")

        # Total de goles del partido
        total_goles = 0
        if df['goles_local'].notna().any() and df['goles_visitante'].notna().any():
            total_goles = int(df['goles_local'].iloc[-1]) + int(df['goles_visitante'].iloc[-1])
            print(f"    Total goles: {total_goles} ({'Over 2.5 GANO' if total_goles > 2 else 'Under 2.5 GANO'})")

            if total_goles <= 2 and o25_inicio < 2.5:
                print(f"    ** Over 2.5 estaba a {o25_inicio:.2f} (prob {1/o25_inicio:.0%}) pero el partido fue Under")
            if total_goles > 2 and u25_inicio < 2.5:
                print(f"    ** Under 2.5 estaba a {u25_inicio:.2f} (prob {1/u25_inicio:.0%}) pero el partido fue Over")

# ============================================================================
# 7. PATRON: DESCANSO (Halftime)
# ============================================================================
print("\n\n" + "=" * 80)
print("7. PATRON DE DESCANSO (HALFTIME)")
print("=" * 80)
print("   Las cuotas se mueven de forma predecible durante el descanso?")

for match_id, df in matches.items():
    ht_rows = df[df['estado_partido'].str.contains('descanso|half', case=False, na=False)]

    if len(ht_rows) < 2:
        continue

    # Encontrar primera y ultima fila de descanso
    first_ht = ht_rows.iloc[0]
    last_ht = ht_rows.iloc[-1]

    # Encontrar la fila despues del descanso (inicio 2T)
    ht_end_idx = ht_rows.index[-1]
    post_ht = df[df.index > ht_end_idx].head(2)

    print(f"\n  {match_id[:55]}")
    print(f"    Capturas en HT: {len(ht_rows)} | Resultado al descanso: {first_ht.get('goles_local', '?')}-{first_ht.get('goles_visitante', '?')}")

    if pd.notna(first_ht.get('back_home')) and pd.notna(last_ht.get('back_home')):
        print(f"    Cuota Home: {first_ht['back_home']:.2f} -> {last_ht['back_home']:.2f} durante HT")

    if len(post_ht) > 0 and pd.notna(last_ht.get('back_home')) and pd.notna(post_ht.iloc[0].get('back_home')):
        print(f"    Cuota Home: {last_ht['back_home']:.2f} -> {post_ht.iloc[0]['back_home']:.2f} al inicio 2T")

# ============================================================================
# 8. PATRON: POSESION vs CUOTA EN VIVO
# ============================================================================
print("\n\n" + "=" * 80)
print("8. POSESION vs PROBABILIDAD IMPLICITA")
print("=" * 80)
print("   La posesion dice algo sobre el resultado que las cuotas no capturen?")

for match_id, df in matches.items():
    valid = df[['posesion_local', 'back_home', 'goles_local', 'goles_visitante']].dropna()
    if len(valid) < 3:
        continue

    valid['implied_home'] = valid['back_home'].apply(implied_prob) * 100
    valid['posesion_local'] = pd.to_numeric(valid['posesion_local'], errors='coerce')

    corr = valid['posesion_local'].corr(valid['implied_home'])

    avg_pos = valid['posesion_local'].mean()
    avg_prob = valid['implied_home'].mean()

    resultado = f"{int(valid['goles_local'].iloc[-1])}-{int(valid['goles_visitante'].iloc[-1])}"

    print(f"\n  {match_id[:55]}")
    print(f"    Posesion media Local: {avg_pos:.0f}% | Prob implicita media: {avg_prob:.0f}% | Resultado: {resultado}")

    if avg_pos > 55 and avg_prob < 45:
        print(f"    ** ANOMALIA: Local domina posesion ({avg_pos:.0f}%) pero mercado lo infravalora ({avg_prob:.0f}%)")
    elif avg_pos < 45 and avg_prob > 55:
        print(f"    ** ANOMALIA: Local inferior en posesion ({avg_pos:.0f}%) pero mercado lo sobrevalora ({avg_prob:.0f}%)")

# ============================================================================
# 9. RESUMEN DE HALLAZGOS
# ============================================================================
print("\n\n" + "=" * 80)
print("  RESUMEN Y CONCLUSIONES PARA TRADING")
print("=" * 80)

total_capturas = sum(len(df) for df in matches.values())
total_goles = sum(s['n_goles'] for s in match_summaries)
partidos_con_stats = sum(1 for s in match_summaries if s['has_stats'])
partidos_con_momentum = sum(1 for s in match_summaries if s['has_momentum'])

print(f"""
  DATOS DISPONIBLES:
    - {len(matches)} partidos con 2+ capturas
    - {total_capturas} capturas totales
    - {total_goles} goles detectados
    - {partidos_con_stats} partidos con estadisticas Opta
    - {partidos_con_momentum} partidos con datos de momentum

  LIMITACIONES ACTUALES:
    - La mayoria de partidos tienen pocas capturas (3-15)
    - Solo CSKA Sofia (97 capturas) tiene datos granulares
    - Las capturas no son cada minuto (hay gaps)
    - Se necesita MAS DATOS para validar patrones estadisticamente

  PATRONES OBSERVADOS (requieren validacion con mas datos):

    1. MOVIMIENTO POST-GOL:
       - Las cuotas reaccionan INMEDIATAMENTE al gol
       - Para trading: hay que estar posicionado ANTES del gol
       - Momentum alto + muchos tiros = probabilidad de gol sube

    2. SPREAD COMO INDICADOR:
       - Spread bajo = alta liquidez = mejor momento para entrar/salir
       - Spread sube en partidos de ligas menores (menos liquidez)

    3. MOMENTUM VS CUOTAS:
       - El momentum se correlaciona con la direccion de las cuotas
       - Pero la correlacion es debil en cambios a corto plazo
       - Util como indicador de TENDENCIA, no de timing exacto

    4. DESCANSO (HALFTIME):
       - Las cuotas se estabilizan durante el descanso
       - Posible oportunidad: comprar antes del 2T si las stats
         muestran dominio claro no reflejado en las cuotas

  PROXIMOS PASOS RECOMENDADOS:
    1. Acumular datos de 50+ partidos con capturas cada minuto
    2. Entrenar modelo: momentum + stats -> probabilidad de gol en proximos 10 min
    3. Comparar prediccion propia vs cuota de mercado para detectar VALOR
    4. Backtesting con stake fijo para validar rentabilidad
""")

print("=" * 80)
print("  Analisis completado")
print("=" * 80)
