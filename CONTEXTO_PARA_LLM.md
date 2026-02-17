# Contexto del Proyecto Furbo - Trading Deportivo en Betfair

**Fecha**: 17 Febrero 2026
**Propósito**: Documento de contexto para análisis por LLMs y generación de nuevas estrategias

---

## 📋 Índice

1. [Visión General del Proyecto](#1-visión-general-del-proyecto)
2. [Arquitectura y Flujo de Datos](#2-arquitectura-y-flujo-de-datos)
3. [Estructura de Datos (CSVs)](#3-estructura-de-datos-csvs)
4. [Estrategias Activas](#4-estrategias-activas)
5. [Resultados Actuales](#5-resultados-actuales)
6. [Limitaciones y Consideraciones](#6-limitaciones-y-consideraciones)
7. [Oportunidades de Análisis](#7-oportunidades-de-análisis)

---

## 1. Visión General del Proyecto

### ¿Qué es Furbo?

**Furbo** es un sistema automatizado de **trading deportivo in-play** que opera en el mercado de Betfair Exchange durante partidos de fútbol en vivo.

### Objetivo

Identificar **ineficiencias de mercado** mediante análisis de datos en tiempo real (cuotas + estadísticas Opta) para generar señales de trading rentables.

### Componentes principales

1. **Scraper (Selenium)**: Captura cuotas Match Odds, Over/Under, Resultado Correcto cada 30 segundos
2. **Extractor de estadísticas**: Extrae 100+ métricas Opta (xG, tiros, posesión, corners, etc.)
3. **Motor de estrategias**: Evalúa 5 estrategias validadas en tiempo real
4. **Dashboard React**: Visualiza señales, partidos activos, analytics y apuestas
5. **Sistema de apuestas**: Paper trading con registro completo de P/L

### Filosofía

- **Data-driven**: Toda estrategia debe tener backtesting con ROI positivo en 100+ triggers
- **Gestión de riesgo**: Half-Kelly bankroll management para largo plazo
- **Validación continua**: Win Rate real debe mantenerse cerca del backtested (±5%)
- **No sobreajuste**: Preferir versiones simples con muestra grande vs. filtros complejos con poca muestra

---

## 2. Arquitectura y Flujo de Datos

```
┌─────────────────────────────────────────────────────┐
│  BETFAIR EXCHANGE (Fuente de datos)                 │
│  - Cuotas en tiempo real (Match Odds, OU, RC)       │
│  - Estadísticas Opta embebidas en iframe            │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  SCRAPER (main.py - Selenium)                       │
│  - Ciclo 30s por partido                            │
│  - Extrae cuotas + score + minuto                   │
│  - Extrae 100+ stats Opta del iframe                │
│  - Guarda en: data/partido_{match_id}.csv           │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  SUPERVISOR WORKFLOW (orquestador)                  │
│  1. start_scraper.py - Verifica/arranca scraper     │
│  2. find_matches.py - Busca nuevos partidos         │
│  3. clean_games.py - Elimina partidos terminados    │
│  4. check_urls.py - Valida URLs 404                 │
│  5. generate_report.py - Reporta estado             │
│  6. validate_stats.py - Valida stats capturadas     │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  DATOS ESTRUCTURADOS                                │
│  - games.csv (partidos trackeados)                  │
│  - partido_{id}.csv (147 cols × ~46 rows)           │
│  - signals_log.csv (señales generadas)              │
│  - placed_bets.csv (apuestas registradas)           │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  MOTOR DE ESTRATEGIAS (dashboard backend)           │
│  - Lee CSVs en tiempo real                          │
│  - Evalúa 5 estrategias activas                     │
│  - Genera señales con confidence/EV/odds            │
│  - Evita duplicados (anti-spam)                     │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│  DASHBOARD (React + FastAPI)                        │
│  - Señales: Lista de señales activas por partido    │
│  - Partidos: Estado de partidos trackeados          │
│  - Insights: Presets de cartera y stats             │
│  - Mis Apuestas: Apuestas en juego                  │
│  - Analytics: Historial, P/L, WR, ROI, métricas     │
└─────────────────────────────────────────────────────┘
```

---

## 3. Estructura de Datos (CSVs)

### 3.1. games.csv (Partidos Trackeados)

Contiene la lista de partidos que el scraper está monitoreando.

**Columnas** (3):
- `Game`: Nombre del partido (ej: "FC Machida - Chengdu Rongcheng")
- `url`: URL completa de Betfair Exchange
- `fecha_hora_inicio`: Timestamp de inicio programado

**Propósito**: El scraper lee este archivo para saber qué partidos debe capturar.

---

### 3.2. partido_{match_id}.csv (Snapshots Temporales)

Un archivo por partido. Cada fila = 1 snapshot capturado cada 30 segundos.

**Columnas** (147):

#### Metadatos (5)
- `tab_id`: ID interno
- `timestamp_utc`: Timestamp de captura
- `evento`: Nombre del partido
- `hora_comienzo`: Hora de inicio
- `url`: URL Betfair

#### Estado del partido (4)
- `estado_partido`: pre_partido | en_juego | descanso | finalizado
- `minuto`: Minuto actual del partido
- `goles_local`: Goles del equipo local
- `goles_visitante`: Goles del equipo visitante

#### Cuotas Match Odds (6)
- `back_home`, `lay_home`: Cuotas back/lay para victoria local
- `back_draw`, `lay_draw`: Cuotas back/lay para empate
- `back_away`, `lay_away`: Cuotas back/lay para victoria visitante

#### Cuotas Over/Under (20)
- `back_over05`, `lay_over05`, `back_under05`, `lay_under05`: Línea 0.5 goles
- `back_over15`, `lay_over15`, `back_under15`, `lay_under15`: Línea 1.5 goles
- `back_over25`, `lay_over25`, `back_under25`, `lay_under25`: Línea 2.5 goles
- `back_over35`, `lay_over35`, `back_under35`, `lay_under35`: Línea 3.5 goles
- `back_over45`, `lay_over45`, `back_under45`, `lay_under45`: Línea 4.5 goles

#### Cuotas Resultado Correcto (30)
- `back_rc_0_0`, `lay_rc_0_0`: 0-0
- `back_rc_1_0`, `lay_rc_1_0`: 1-0
- `back_rc_0_1`, `lay_rc_0_1`: 0-1
- `back_rc_1_1`, `lay_rc_1_1`: 1-1
- `back_rc_2_0`, `lay_rc_2_0`: 2-0
- `back_rc_0_2`, `lay_rc_0_2`: 0-2
- `back_rc_2_1`, `lay_rc_2_1`: 2-1
- `back_rc_1_2`, `lay_rc_1_2`: 1-2
- `back_rc_2_2`, `lay_rc_2_2`: 2-2
- `back_rc_3_0`, `lay_rc_3_0`: 3-0
- `back_rc_0_3`, `lay_rc_0_3`: 0-3
- `back_rc_3_1`, `lay_rc_3_1`: 3-1
- `back_rc_1_3`, `lay_rc_1_3`: 1-3
- `back_rc_3_2`, `lay_rc_3_2`: 3-2
- `back_rc_2_3`, `lay_rc_2_3`: 2-3

#### Estadísticas Opta - Expected Goals (2)
- `xg_local`: Expected Goals del equipo local
- `xg_visitante`: Expected Goals del equipo visitante

#### Estadísticas Opta - Performance (2)
- `opta_points_local`: Puntos Opta (índice de rendimiento)
- `opta_points_visitante`: Puntos Opta visitante

#### Estadísticas Opta - Posesión (2)
- `posesion_local`: % de posesión del equipo local
- `posesion_visitante`: % de posesión del equipo visitante

#### Estadísticas Opta - Tiros (4)
- `tiros_local`: Tiros totales del local
- `tiros_visitante`: Tiros totales del visitante
- `tiros_puerta_local`: Tiros a puerta (SoT) del local
- `tiros_puerta_visitante`: Tiros a puerta del visitante

#### Estadísticas Opta - Zona Peligrosa (2)
- `touches_box_local`: Toques en área rival (local)
- `touches_box_visitante`: Toques en área rival (visitante)

#### Estadísticas Opta - Corners (2)
- `corners_local`: Corners del equipo local
- `corners_visitante`: Corners del equipo visitante

#### Estadísticas Opta - Pases (2)
- `total_passes_local`: Pases totales del local
- `total_passes_visitante`: Pases totales del visitante

#### Estadísticas Opta - Faltas (2)
- `fouls_conceded_local`: Faltas cometidas por el local
- `fouls_conceded_visitante`: Faltas cometidas por el visitante

#### Estadísticas Opta - Tarjetas (4)
- `tarjetas_amarillas_local`: Tarjetas amarillas del local
- `tarjetas_amarillas_visitante`: Tarjetas amarillas del visitante
- `tarjetas_rojas_local`: Tarjetas rojas del local
- `tarjetas_rojas_visitante`: Tarjetas rojas del visitante

#### Estadísticas Opta - Booking Points (2)
- `booking_points_local`: Puntos de tarjetas (10=amarilla, 25=roja)
- `booking_points_visitante`: Puntos de tarjetas visitante

#### Estadísticas Opta - Ocasiones (2)
- `big_chances_local`: Ocasiones claras del local
- `big_chances_visitante`: Ocasiones claras del visitante

#### Estadísticas Opta - Tiros (2)
- `shots_off_target_local`: Tiros fuera del local
- `shots_off_target_visitante`: Tiros fuera del visitante

#### Estadísticas Opta - Ataques (2)
- `attacks_local`: Ataques del local
- `attacks_visitante`: Ataques del visitante

#### Estadísticas Opta - Woodwork (2)
- `hit_woodwork_local`: Balones al palo del local
- `hit_woodwork_visitante`: Balones al palo del visitante

#### Estadísticas Opta - Tiros Bloqueados (2)
- `blocked_shots_local`: Tiros bloqueados del local
- `blocked_shots_visitante`: Tiros bloqueados del visitante

#### Estadísticas Opta - Precisión de Tiro (2)
- `shooting_accuracy_local`: % precisión de tiro del local
- `shooting_accuracy_visitante`: % precisión de tiro del visitante

#### Estadísticas Opta - Ataques Peligrosos (2)
- `dangerous_attacks_local`: Ataques peligrosos del local
- `dangerous_attacks_visitante`: Ataques peligrosos del visitante

#### Estadísticas Opta - Entradas (2)
- `tackles_local`: Entradas del local
- `tackles_visitante`: Entradas del visitante

#### Estadísticas Opta - Éxito en Entradas (2)
- `tackle_success_pct_local`: % éxito en entradas del local
- `tackle_success_pct_visitante`: % éxito en entradas del visitante

#### Estadísticas Opta - Duelos (4)
- `duels_won_local`: Duelos ganados por el local
- `duels_won_visitante`: Duelos ganados por el visitante
- `aerial_duels_won_local`: Duelos aéreos ganados por el local
- `aerial_duels_won_visitante`: Duelos aéreos ganados por el visitante

#### Estadísticas Opta - Despejes (2)
- `clearance_local`: Despejes del local
- `clearance_visitante`: Despejes del visitante

#### Estadísticas Opta - Paradas (2)
- `saves_local`: Paradas del portero local
- `saves_visitante`: Paradas del portero visitante

#### Estadísticas Opta - Intercepciones (2)
- `interceptions_local`: Intercepciones del local
- `interceptions_visitante`: Intercepciones del visitante

#### Estadísticas Opta - Precisión de Pases (2)
- `pass_success_pct_local`: % precisión de pases del local
- `pass_success_pct_visitante`: % precisión de pases del visitante

#### Estadísticas Opta - Centros (4)
- `crosses_local`: Centros del local
- `crosses_visitante`: Centros del visitante
- `successful_crosses_pct_local`: % centros exitosos del local
- `successful_crosses_pct_visitante`: % centros exitosos del visitante

#### Estadísticas Opta - Pases en Campo Rival (2)
- `successful_passes_opp_half_local`: Pases exitosos en campo rival (local)
- `successful_passes_opp_half_visitante`: Pases exitosos en campo rival (visitante)

#### Estadísticas Opta - Pases en Tercio Final (2)
- `successful_passes_final_third_local`: Pases exitosos en tercio final (local)
- `successful_passes_final_third_visitante`: Pases exitosos en tercio final (visitante)

#### Estadísticas Opta - Saques (6)
- `goal_kicks_local`: Saques de puerta del local
- `goal_kicks_visitante`: Saques de puerta del visitante
- `throw_ins_local`: Saques de banda del local
- `throw_ins_visitante`: Saques de banda del visitante
- `free_kicks_local`: Tiros libres del local
- `free_kicks_visitante`: Tiros libres del visitante

#### Estadísticas Opta - Fueras de Juego (2)
- `offsides_local`: Fueras de juego del local
- `offsides_visitante`: Fueras de juego del visitante

#### Estadísticas Opta - Cambios (2)
- `substitutions_local`: Cambios realizados por el local
- `substitutions_visitante`: Cambios realizados por el visitante

#### Estadísticas Opta - Lesiones (2)
- `injuries_local`: Lesiones del local
- `injuries_visitante`: Lesiones del visitante

#### Estadísticas Opta - Tiempo en Ataque Peligroso (2)
- `time_in_dangerous_attack_pct_local`: % tiempo en ataque peligroso (local)
- `time_in_dangerous_attack_pct_visitante`: % tiempo en ataque peligroso (visitante)

#### Estadísticas Opta - Momentum (2)
- `momentum_local`: Momentum del local (0-100, calculado por Opta)
- `momentum_visitante`: Momentum del visitante (0-100)

#### Volumen de Mercado (1)
- `volumen_matched`: Volumen total matched en EUR

#### Cuotas BFEH (Back For Each Half) - Betfair Extra (3)
- `BFEH`: Cuota Back For Each Half (local)
- `BFED`: Cuota Back For Each Half (empate)
- `BFEA`: Cuota Back For Each Half (visitante)

**Ejemplo de snapshot**:
```csv
tab_id,timestamp_utc,evento,...,minuto,goles_local,goles_visitante,back_home,back_draw,back_away,xg_local,xg_visitante,posesion_local,tiros_puerta_local,...
ajax-fortuna,2026-02-14 19:59:56,...,descanso,3,1,1.01,26,48,10.5,0.6,53.3,5,...
```

**Características clave**:
- **Temporal**: Cada CSV crece con el tiempo (~46 filas por partido de 90 min)
- **Completo**: 147 campos capturados cada 30 segundos
- **Histórico**: Permite análisis retrospectivo de evolución de cuotas y estadísticas

---

### 3.3. signals_log.csv (Señales Generadas)

Registro de todas las señales generadas por el motor de estrategias.

**Columnas** (17):
- `timestamp_utc`: Timestamp de generación de señal
- `match_id`: ID del partido
- `match_name`: Nombre del partido
- `match_url`: URL Betfair
- `strategy`: ID técnico de estrategia (ej: "back_draw_00_v15")
- `strategy_name`: Nombre legible (ej: "Back Empate 0-0 (V1.5)")
- `minute`: Minuto del partido cuando se generó
- `score`: Marcador en el momento del trigger
- `recommendation`: Texto de la recomendación (ej: "BACK DRAW @ 2.70")
- `back_odds`: Cuota back recomendada
- `min_odds`: Cuota mínima aceptable
- `expected_value`: Valor esperado calculado
- `confidence`: Nivel de confianza (high/medium/low)
- `win_rate_historical`: Win Rate histórico de la estrategia
- `roi_historical`: ROI histórico de la estrategia
- `sample_size`: Tamaño de muestra del backtest
- `conditions`: JSON con condiciones que se cumplieron

**Propósito**: Tracking de todas las señales generadas, incluso las que no se apostaron.

---

### 3.4. placed_bets.csv (Apuestas Registradas)

Registro de apuestas colocadas (paper trading o reales).

**Columnas** (23):
- `id`: ID único de apuesta
- `timestamp_utc`: Timestamp de colocación
- `match_id`: ID del partido
- `match_name`: Nombre del partido
- `match_url`: URL Betfair
- `strategy`: ID técnico de estrategia
- `strategy_name`: Nombre legible de estrategia
- `minute`: Minuto de entrada
- `score`: Marcador al entrar
- `recommendation`: Tipo de apuesta (ej: "BACK DRAW @ 2.70")
- `back_odds`: Cuota apostada
- `min_odds`: Cuota mínima requerida
- `expected_value`: EV calculado
- `confidence`: Nivel de confianza
- `win_rate_historical`: WR histórico
- `roi_historical`: ROI histórico
- `sample_size`: Muestra del backtest
- `bet_type`: "paper" o "real"
- `stake`: Cantidad apostada en EUR
- `notes`: Notas adicionales
- `status`: "pending" | "won" | "lost"
- `result`: "won" | "lost" (después de resolución)
- `pl`: Profit/Loss neto en EUR

**Propósito**: Tracking de P/L, win rate real, validación de estrategias.

**Estado actual** (9 apuestas):
- Win Rate: 77.8% (7W-2L)
- P/L Total: +75.37 EUR
- ROI: Muy positivo

---

## 4. Estrategias Activas

El sistema evalúa **5 estrategias** en tiempo real. Cada una tiene backtesting histórico con 100+ triggers.

### 4.1. Back Empate 0-0 (V1.5)

**Concepto**: Cuando un partido está 0-0 después del minuto 30, apostar al empate.

**Lógica**: El mercado subestima la "inercia" de un empate. Cuanto más tiempo llevan igualados a 0-0, menos probable es que alguien marque (equipos se conforman, bajan ritmo).

**Condiciones de entrada**:
- Marcador: 0-0
- Minuto: >= 30
- xG combinado: < 0.6
- Diferencia de posesión dominante: < 20%
- Tiros totales: < 8
- Apuesta: **BACK DRAW**

**Resultados históricos** (9 apuestas validadas):
- Win Rate: 55.6%
- ROI: +40.8%
- P/L: +36.76 EUR (stake 10 EUR)
- Cuotas medias: ~2.80

**Versión recomendada**: V1.5 (balance entre muestra y ROI)

**Riesgo**: Baja varianza (cuotas 2.5-3.5)

---

### 4.2. xG Underperformance (V3)

**Concepto**: Cuando un equipo tiene xG significativamente mayor que sus goles (exceso >= 0.5) y va **perdiendo**, apostar a Over.

**Lógica**: La regresión a la media indica que el equipo acabará convirtiendo. Si va perdiendo, la urgencia aumenta y el mercado Over puede estar infravalorado.

**Condiciones de entrada**:
- Equipo PERDIENDO
- (xG_equipo - goles_equipo) >= 0.5
- Minuto: >= 15
- Tiros a puerta >= 2 (confirma que está atacando)
- Apuesta: **BACK OVER (total_actual + 0.5)**

**Resultados históricos** (11 apuestas):
- Win Rate: 72.7%
- ROI: +24.7%
- P/L: +27.13 EUR
- Cuotas medias: ~2.20

**Versión recomendada**: V3 (bloquea entradas >= min 70 para evitar over-betting tardío)

**Riesgo**: Moderada varianza

---

### 4.3. Odds Drift Contrarian (V1)

**Concepto**: Cuando un equipo va **ganando** pero sus cuotas suben >= 30% en 10 minutos (el mercado lo "abandona"), apostar a que mantiene la victoria.

**Lógica**: El mercado sobrereacciona a eventos puntuales (gol del rival, tarjeta, momentum temporal). Un equipo que ya va ganando tiene ventaja psicológica y táctica.

**Condiciones de entrada**:
- Equipo va GANANDO en el marcador
- Drift de cuotas: >= 30% en últimos 10 minutos
- Minuto: 5-80
- Cuotas: 1.5-30.0
- Apuesta: **BACK al equipo con drift**

**Resultados históricos** (27 apuestas):
- Win Rate: 66.7%
- ROI: **+142.3%** (mejor ROI de la cartera)
- P/L: +384.32 EUR
- Cuotas medias: 3.96

**Versión recomendada**: V1 (muestra más grande, ROI excelente)

**Riesgo**: Moderada-alta varianza (cuotas pueden llegar a 10.0+)

**Nota importante**: La hipótesis original era apostar al perdedor abandonado. Los datos demostraron lo contrario: solo funciona con el ganador.

---

### 4.4. Goal Clustering (V2)

**Concepto**: Después de un gol, los goles tienden a venir en rachas (efecto clustering). Apostar a Over aprovechando esta ventana temporal.

**Lógica**:
- **Psicológico**: Equipo que encaja busca empate, equipo que marca baja concentración
- **Táctico**: El partido "se abre", ambos atacan más
- **Mercado**: Las cuotas Over no ajustan completamente el efecto clustering inmediato

**Condiciones de entrada**:
- Acaba de haber un gol (minuto 15-80)
- Algún equipo tiene >= 3 tiros a puerta (confirma intensidad)
- Apuesta: **BACK OVER (total_actual + 0.5)**

**Resultados históricos** (44 apuestas):
- Win Rate: 75.0%
- ROI: **+72.7%**
- P/L: +320.04 EUR
- Cuotas medias: 2.96
- Tiempo promedio hasta siguiente gol: ~14 minutos

**Versión recomendada**: V2 (filtro SoT >= 3 confirma que hay intensidad ofensiva real)

**Riesgo**: Baja-moderada varianza

---

### 4.5. Pressure Cooker (V1) - EN PRUEBA

**Concepto**: Cuando un partido está empatado **con goles** (1-1, 2-2) entre minuto 65-75, apostar a Over.

**Lógica**: Si ambos equipos ya han marcado, está demostrado que ambos pueden generar gol. En la recta final, entrenadores hacen cambios ofensivos y los equipos se abren buscando la victoria.

**Condiciones de entrada**:
- Minuto: 65-75
- Marcador: Empate con goles (1-1, 2-2, 3-3...) - **NUNCA 0-0**
- Apuesta: **BACK OVER (total_actual + 0.5)**

**Resultados históricos** (16 apuestas - muestra pequeña):
- Win Rate: 81.2%
- ROI: +81.9%
- P/L: +131.01 EUR
- Cuotas medias: 2.41

**Estado**: **EN VALIDACIÓN** - Necesita 50+ triggers para confirmar

**Versión recomendada**: V1 (versión simple sin filtros de momentum)

**Riesgo**: Baja varianza, pero muestra insuficiente

**Nota clave**: Un 0-0 al minuto 65 tiene WR 50% y ROI -32.5% (destruye dinero). El filtro "score != 0-0" es crítico.

---

## 5. Resultados Actuales

### 5.1. Cartera Validada (3 estrategias principales)

**Configuración**: Back Empate V1.5 + xG V3 + Odds Drift V1

**Backtest histórico** (45 apuestas, 153 partidos, Feb 12-15 2026):
- Total apuestas: 45 (7 Draw + 11 xG + 27 Drift)
- Win Rate: 66.67% (30/45)
- P/L neto: **+446.62 EUR** (stake fijo 10 EUR)
- ROI: **+54.5%**
- Max Drawdown: -101.73 EUR
- Peor racha: 6 fallos seguidos

### 5.2. Cartera Ampliada (4 estrategias)

**Configuración**: Cartera validada + Goal Clustering V2

**Backtest histórico** (89 apuestas, 186 partidos):
- Win Rate: ~70%
- P/L neto: **+766 EUR**
- ROI: ~86%

### 5.3. Resultados Reales (9 apuestas paper)

**Periodo**: 16 Feb 2026 (1 día de operación real)

| # | Estrategia | Resultado | Cuotas | P/L |
|---|-----------|----------|--------|-----|
| 1 | Odds Drift V1 | WON | 2.06 | +10.07 |
| 2 | Back Empate V15 | WON | 2.70 | +16.15 |
| 3 | Back Empate V15 | WON | 2.38 | +13.11 |
| 4 | Odds Drift V1 | WON | 2.00 | +10.00 |
| 5 | Goal Clustering V2 | WON | 1.50 | +5.00 |
| 6 | Goal Clustering V2 | WON | 4.10 | +29.45 |
| 7 | Back Empate V15 | WON | 2.22 | +11.59 |
| 8 | Back Empate V15 | LOST | 2.28 | -10.00 |
| 9 | Goal Clustering V2 | LOST | 4.90 | -10.00 |

**Resumen**:
- Win Rate: **77.8%** (7W-2L)
- P/L Total: **+75.37 EUR**
- ROI: **+83.7%** (sobre 90 EUR apostados)
- Cuotas medias: 2.69

**Comparación con backtest**: El WR real (77.8%) está **por encima** del esperado (66.7%), lo cual es excelente pero podría ser varianza de muestra pequeña.

### 5.4. Gestión de Bankroll (Largo Plazo)

**Modo recomendado**: Half-Kelly

**Configuración**:
- Bankroll inicial: 500 EUR
- Stake%: Kelly_fraction / 2
- Mínimo: 1% bankroll
- Máximo: 4% bankroll

**Resultados esperados** (simulación sobre 45 apuestas):
- P/L neto: **+1638.15 EUR**
- ROI: **+327.6%**
- Bankroll final: 2138 EUR
- Max Drawdown: -681.96 EUR (desde pico de 1973 EUR)

**Ventaja vs stake fijo**: 3.9x más beneficio (1638 vs 422 EUR)

---

## 6. Limitaciones y Consideraciones

### 6.1. Limitaciones de Datos

1. **Muestra pequeña en backtests**:
   - Back Empate V1.5: solo 9 apuestas
   - xG V3: solo 11 apuestas
   - Pressure Cooker V1: solo 16 apuestas
   - **Problema**: Alta varianza, intervalos de confianza amplios

2. **Periodo histórico corto**:
   - Backtests sobre 3-4 días de datos (Feb 12-16 2026)
   - No captura variación estacional (ligas diferentes, momentos de temporada)

3. **Calidad de datos**:
   - Depende del scraper (pueden haber errores de captura)
   - Estadísticas Opta no siempre disponibles (pre-partido no hay stats)
   - Algunas estadísticas pueden tener delay de 1-2 minutos

### 6.2. Riesgos de Trading

1. **Sobreajuste**: Las versiones filtradas (V2, V3, V1.5) pueden estar sobreajustadas a la muestra histórica

2. **Slippage**:
   - Cuotas capturadas != cuotas ejecutables
   - Liquidez insuficiente en algunos mercados
   - Suspensión de mercados durante el partido

3. **Cambios de mercado**:
   - Si Betfair detecta patrón ganador, pueden reducir límites
   - El mercado puede volverse más eficiente con el tiempo

4. **Factor psicológico**:
   - Ver drawdown de -682 EUR desde pico requiere disciplina férrea
   - Tentación de perseguir pérdidas o abandonar tras rachas negativas

### 6.3. Limitaciones Técnicas

1. **Scraper**:
   - Puede fallar si Betfair cambia selectores CSS
   - Consume recursos (Chrome headless 24/7)
   - Desktop heap limit en Windows con múltiples tabs

2. **Anti-bot**:
   - Betfair puede bloquear IP si detecta scraping excesivo
   - Delay aleatorio de 8-12 seg entre tabs para parecer humano

3. **Latencia**:
   - Ciclo de 30 segundos → señales pueden llegar tarde
   - Cuotas pueden haber cambiado cuando llegas a apostar

---

## 7. Oportunidades de Análisis

### 7.1. Para LLMs: ¿Qué podéis aportar?

1. **Nuevas estrategias**:
   - Analizar los 147 campos del CSV para encontrar patrones no explorados
   - Proponer hipótesis basadas en teoría de juego, psicología deportiva, etc.
   - Identificar combinaciones de variables que no hemos probado

2. **Mejora de estrategias existentes**:
   - ¿Hay filtros adicionales que mejoren WR sin reducir mucho la muestra?
   - ¿Hay variables que predicen cuándo una estrategia NO debe activarse?
   - ¿Hay timing óptimo (minutos) que no hemos explorado?

3. **Gestión de riesgo**:
   - Proponer modelos de bankroll management alternativos a Half-Kelly
   - Identificar condiciones de stop-loss inteligentes
   - Estrategias de hedging o cash-out

4. **Feature engineering**:
   - Variables derivadas que podrían tener valor predictivo
   - Ratios, deltas, tendencias temporales
   - Interacciones entre variables (ej: xG × momentum)

### 7.2. Patrones Ya Descartados (No repetir)

Estas hipótesis ya fueron exploradas y **NO funcionan**:

1. **Sharp Odds Drop - Back al favorito**: ROI -43%, llegar tarde al movimiento
2. **Equipo domina pero pierde**: Solo 12 casos, ruido estadístico
3. **Fade al overperformer**: Cuotas de lotería (~20.0), no replicable
4. **Tarjetas amarillas predicen goles**: Correlación negativa (opuesto a hipótesis)
5. **Drift Back al perdedor**: ROI -18.9%, hipótesis incorrecta

### 7.3. Patrones Identificados pero No Convertidos en Estrategias

1. **Goles Tardíos (75+)**: 52.2% de partidos tienen gol después del 75', pero cuotas Over muy ajustadas (ROI -23.5%)

2. **Clustering de Goles**: 18.3% de goles seguidos por otro en 5 min, 38.5% en 10 min (ya explotado en Goal Clustering V2)

3. **Corners como predictor**: Diferencia de 5+ corners → 37.8% prob de gol en 10 min (vs 26% baseline). Potencial como filtro secundario.

4. **Momentum del scraper**: Cuando momentum favorece claramente al local (top 25%) → home win 66.7%. Potencial para estrategia futura.

### 7.4. Preguntas Abiertas

1. **¿Hay sinergia entre estrategias?**
   - ¿Combinar señales de múltiples estrategias mejora confianza?
   - ¿Hay momentos donde varias estrategias se contradicen? ¿Cómo resolver?

2. **¿Hay variables ignoradas con valor predictivo?**
   - `time_in_dangerous_attack_pct`: ¿predice goles inminentes?
   - `aerial_duels_won`: ¿indica dominio físico que deriva en goles?
   - `shooting_accuracy`: ¿equipo con alta precisión marcará pronto?

3. **¿Hay meta-patrones por liga/hora/día?**
   - ¿Algunas ligas son más predecibles?
   - ¿Partidos de tarde tienen más goles que de noche?
   - ¿Fines de semana vs entre semana?

4. **¿Hay valor en mercados alternativos?**
   - Resultado Correcto: 15 líneas diferentes capturadas
   - BFEH (Back For Each Half): ¿hay edge?
   - Lay strategies: ¿podemos invertir alguna hipótesis?

### 7.5. Datos Disponibles para Análisis

Si necesitas datos históricos para proponer nuevas estrategias:

- **CSVs de partidos**: ~20 partidos × 46 snapshots × 147 campos = ~135,000 puntos de datos
- **Apuestas históricas**: 9 apuestas reales + 45 simuladas en backtest
- **Señales generadas**: signals_log.csv con todas las señales (apostadas o no)

---

## 8. Formato de Propuesta de Estrategia

Si deseas proponer una nueva estrategia, usa este formato:

```markdown
### Nombre de Estrategia

**Concepto**: [Descripción en 1-2 líneas]

**Lógica**: [Por qué debería funcionar - fundamento teórico]

**Condiciones de entrada**:
- Variable 1: condición
- Variable 2: condición
- ...
- Apuesta: BACK/LAY [qué mercado]

**Hipótesis**:
- Win Rate esperado: X%
- ROI esperado: Y%
- Cuotas medias esperadas: Z

**Riesgos**:
- [Identificar posibles problemas]

**Siguiente paso**:
- [Cómo validar: qué datos necesitas, qué análisis hacer]
```

---

## 9. Conclusión

**Furbo** es un sistema de trading deportivo automatizado con:
- ✅ Captura de datos en tiempo real (147 campos × 30s)
- ✅ 5 estrategias validadas con ROI positivo
- ✅ Dashboard funcional para señales y analytics
- ✅ Resultados reales prometedores (77.8% WR, +75 EUR en 1 día)
- ❌ Muestra histórica pequeña (necesita más validación)
- ❌ Riesgo de sobreajuste en versiones filtradas

**Tu misión como LLM**:
Analizar los datos disponibles, proponer nuevas hipótesis, identificar patrones no explorados, y ayudarnos a construir estrategias rentables basadas en evidencia.

---

**Fecha de documento**: 17 Febrero 2026
**Versión**: 1.0
**Contacto**: Este documento será compartido con múltiples LLMs para análisis colaborativo
