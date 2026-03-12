# Instrucciones para Claude Code

## OBLIGATORIO: Leer antes de actuar

**LEER `ARCHITECTURE.md`** en la raiz del proyecto antes de hacer cualquier cambio de codigo. Contiene la arquitectura real y verificada del sistema completo.

## Archivos temporales y auxiliares

**REGLA**: Todo archivo temporal, prescindible o de análisis ad hoc debe guardarse en `/auxiliar` (raiz del proyecto), nunca en la raiz ni en otros directorios.

Ejemplos de lo que va en `/auxiliar`:
- Scripts temporales de análisis (`analyze_*.py`, `test_*.py`, `check_*.py`)
- Capturas de pantalla (`.png`, `.jpg`)
- CSVs de resultados intermedios
- JSONs de exploración
- Logs de análisis puntuales
- Cualquier fichero que no forme parte de la arquitectura permanente

La carpeta `/auxiliar` puede borrarse en cualquier momento sin afectar al sistema. Si no existe, crearla antes de guardar el archivo.

## Reglas criticas

1. **NO ASUMIR** como funciona algo. Verificar siempre en el codigo fuente antes de hacer afirmaciones.

2. **CAPA UNICA (BACKTEST)**:
   - El backtest se ejecuta via notebook (`analisis/strategies_designer.ipynb`) o `optimizer_cli.py`.
   - Backend (`csv_reader.py:analyze_cartera()`) genera bets con condiciones basicas + version flags.
   - Ya no existe capa de filtrado frontend (cartera.ts fue eliminado en limpieza 2026-03-08).
   - El notebook aplica su propia logica de filtrado y quality gates.
   - `analyze_cartera()` solo recibe `min_dur` de config. Cache key solo incluye min_duration.

3. **CAPA UNICA (LIVE)**:
   - `analytics.py` construye un dict `versions` con TODOS los params de config.
   - `csv_reader.py:detect_betting_signals(versions)` aplica filtros inline.
   - No hay segunda capa. Ademas, `analytics.py` aplica post-filtros (odds, risk, maturity).

4. **FICHERO CRITICO**: `betfair_scraper/dashboard/backend/utils/csv_reader.py` (~6200 lineas).
   - Contiene TODA la logica de estrategias (backtest y live), carga de datos, cashout simulation, watchlist.
   - Cambios aqui deben ser quirurgicos y verificados.

5. **CONFIG**: `betfair_scraper/cartera_config.json` es la unica fuente de verdad de parametros.

6. **NULL DATA GAP (descartado)**: Ambos sistemas (backtest y live) parten del mismo CSV. Si un stat es null en una fila del CSV historico, eso refleja que el scraper tampoco lo tenia disponible en ese momento en vivo. No hay inflacion sistematica del backtest por nulls.

7. **NO CONTRADECIRSE**: Antes de hacer una afirmacion sobre la arquitectura, verificar en el codigo. No decir "funciona asi" y luego "en realidad funciona de otra forma".

8. **DOCUMENTAR PROACTIVAMENTE**: Cualquier cambio que afecte a logica, interfaz o arquitectura documentada DEBE reflejarse en este CLAUDE.md sin que el usuario lo pida. Si se modifica un fichero clave (csv_reader.py, analytics.py, etc.) y el cambio altera el comportamiento documentado, actualizar la seccion correspondiente antes de terminar la tarea.

## Estructura del proyecto

```
betfair_scraper/
  main.py                → Scraper Selenium multi-driver (~3000 lineas)
  config.py              → Selectores CSS, Chrome options (100 lineas)
  stats_api.py           → Cliente REST Opta/Stats Perform (923 lineas)
  extract_iframe_stats.py → Fallback stats via iframe (233 lineas)
  cartera_config.json    → Config unica de estrategias
  supervisor_workflow.py → Orquestador 7 scripts de mantenimiento
  games.csv              → Partidos activos
  placed_bets.csv        → Apuestas paper
  data/                  → CSVs partido_*.csv + .heartbeat
  logs/                  → Logs scraper (gitignored)
  scripts/               → 8 scripts (find_matches, clean_games, etc.)
  dashboard/
    backend/
      main.py            → FastAPI app + 5 background tasks (417 lineas)
      api/analytics.py   → Paper trading, senales, cartera (750 lineas)
      api/alerts.py      → Alertas y monitor (~750 lineas)
      api/bets.py        → CRUD apuestas + cashout/settlement (604 lineas)
      api/config.py      → GET/PUT cartera_config.json (102 lineas)
      api/matches.py     → Datos de partidos (133 lineas)
      api/system.py      → Start/stop scraper (381 lineas)
      api/optimize.py    → Optimizacion presets Phase 1+2 (1329 lineas)
      api/optimizer_cli.py → CLI para optimizacion paralela (691 lineas)
      utils/csv_reader.py → Estrategias, backtest, live, helpers compartidos (~6200 lineas)
      utils/sd_strategies.py → 19 SD configs + evaluador (205 lineas)
      utils/scraper_status.py → Estado scraper via psutil + log parsing
      utils/signals_audit_logger.py → Audit log rotativo
    frontend/src/
      lib/api.ts         → Cliente API tipado (~500 lineas)
      lib/trading.ts     → PressureIndex, divergencia, momentum swings (311 lineas)
      lib/sounds.ts      → Alerta sonora Web Audio (61 lineas)
      lib/utils.ts       → cn(), formatTimeAgo(), formatTimeTo() (27 lineas)
      components/        → 19 componentes React (Dashboard, BettingSignalsView, etc.)

auxiliar/                     → Archivos auxiliares de analisis (tracked en git)
  sd_generators.py       → Generadores auxiliares para las 19 estrategias adicionales (wrappers sobre triggers de csv_reader, usados en notebooks)
  sd_filters.py          → Filtros auxiliares para las 19 estrategias adicionales
  compare_bt_live.py     → Comparacion rendimiento BT vs LIVE
  data_quality_analysis.py → Analisis calidad datos
  data_quality_deep.py   → Analisis profundo calidad datos
  capture_baseline.py    → Captura baseline de metricas (refactor_baseline_*.json)
  refactor_baseline_sd.json → Baseline SD bets por estrategia (2542 total)
  refactor_baseline_cartera.json → Baseline analyze_cartera() (2102 bets)
tests/                        → Herramientas de verificacion permanentes
  reconcile.py           → Simula LIVE fila a fila y mide match rate vs BT
strategies/              → Reportes .md de estrategias aprobadas + tracker
.claude/agents/          → Definiciones de agentes (system-auditor, strategy-designer, etc.)
analisis/                → 2 notebooks (strategies_designer + reconcile_bt_live)
borrar/                  → Archivos movidos durante limpieza (red de seguridad)
```

## Estrategias (cartera_config.json)

26 estrategias independientes. Cada una tiene su propia clave en `cartera_config.json`, su propio trigger `_detect_<name>_trigger()` en csv_reader.py, deteccion live via `detect_betting_signals()` y backtest via `analyze_cartera()`. No hay categorias ni jerarquias.

| Estrategia | Clave config | Estado |
|------------|-------------|--------|
| Back Empate 0-0 | draw | Desactivada por IC95 gate |
| xG Underperformance | xg | Activa |
| Odds Drift Contrarian | drift | Activa |
| Goal Clustering | clustering | Activa |
| Pressure Cooker | pressure | Activa |
| Momentum xG | momentum_xg | Config-dependiente |
| Tarde Asia | tarde_asia | Inactiva |
| BACK Over 2.5 2-Goal Lead | over25_2goal | Activa |
| BACK Under 3.5 Late | under35_late | Activa |
| BACK Longshot Leading | longshot | Activa |
| BACK Correct Score Close | cs_close | Activa |
| BACK CS 1-0/0-1 | cs_one_goal | Activa |
| BACK Underdog Leading | ud_leading | Activa |
| BACK Home Fav Leading | home_fav_leading | Activa |
| BACK CS 2-0/0-2 | cs_20 | Activa |
| BACK CS Big Lead | cs_big_lead | Activa |
| LAY Over 4.5 v3 | lay_over45_v3 | Activa |
| BACK Draw xG Conv | draw_xg_conv | Activa |
| BACK Poss Extreme | poss_extreme | Activa |
| BACK CS 0-0 | cs_00 | Activa |
| BACK Over 2.5 2 Goals | over25_2goals | Activa |
| BACK Draw 1-1 | draw_11 | Activa |
| BACK Under 3.5 3 Goals | under35_3goals | Activa |
| BACK Away Fav Leading | away_fav_leading | Activa |
| BACK Under 4.5 3 Goals | under45_3goals | Activa |
| BACK CS 1-1 | cs_11 | Activa |

Configs de evaluacion de calidad en `betfair_scraper/dashboard/backend/utils/sd_strategies.py`, generadores auxiliares en `auxiliar/sd_generators.py`, filtros auxiliares en `auxiliar/sd_filters.py`.

## Quality Gates (aplicados a TODAS las estrategias)

1. **N >= G_MIN_BETS**: `max(15, n_partidos // 25)` (~33 con 800+ partidos)
2. **ROI >= G_MIN_ROI** (10%)
3. **IC95_lower >= IC95_MIN_LOW** (40%): intervalo Wilson al 95%

Implementados en `_eval_combo()` (notebook) y `eval_sd()` (`sd_strategies.py`).

## Sistema de Presets

Los presets se computan offline via `optimizer_cli.py` o el notebook `strategies_designer.ipynb` y se guardan directamente en `cartera_config.json`. La optimizacion ejecuta una busqueda en 3 fases (versiones, ajustes realistas, rangos de minutos) y produce la configuracion optima segun el criterio seleccionado (max_roi, max_pl, max_wr, min_dd, max_bets).

### Heuristico CO por criterio
- `max_roi` → 15% (solo cashouts con ganancia grande)
- `max_pl` → 20% (equilibrado)
- `max_wr` → 30% (cashout agresivo, mas % ganadas)
- `min_dd` → 10% (cashout muy temprano, reduce perdidas)
- `max_bets` → 20% (default)

## 5 Background tasks del backend

1. `auto_refresh_matches()` — cada 10 min: clean_games + find_matches
2. `_scheduler_watchdog()` — reinicia auto_refresh si crashea
3. `_scraper_watchdog()` — monitora heartbeat, auto-restart scraper si muerto
4. `auto_paper_trading()` — cada 60s: detecta senales + coloca bets + cashout
5. `_paper_trading_watchdog()` — reinicia paper trading si crashea

## Alineamiento BT↔LIVE (completado 2026-03-11)

Las **26 estrategias** usan **helpers compartidos** (GR8/GR9 compliant). BT y LIVE ejecutan el mismo codigo de deteccion.

### Arquitectura de helpers compartidos

Cada estrategia tiene un helper `_detect_<name>_trigger(rows, curr_idx, cfg)` en csv_reader.py que:
- **BT** llama iterando todas las filas con `curr_idx=idx` + persistencia (min_dur)
- **LIVE** llama con `curr_idx=len(rows)-1` (ultima fila)
- Solo mira `rows[:curr_idx+1]` — nunca filas futuras

**26 triggers** en csv_reader.py, todos con la misma interfaz `_detect_<name>_trigger(rows, curr_idx, cfg)`:

`_detect_back_draw_00_trigger`, `_detect_xg_underperformance_trigger`, `_detect_odds_drift_trigger`,
`_detect_goal_clustering_trigger`, `_detect_pressure_cooker_trigger`, `_detect_momentum_xg_trigger`,
`_detect_tardesia_trigger`, `_detect_over25_2goal_trigger`, `_detect_under35_late_trigger`,
`_detect_lay_over45_v3_trigger`, `_detect_draw_xg_conv_trigger`, `_detect_poss_extreme_trigger`,
`_detect_longshot_trigger`, `_detect_cs_00_trigger`, `_detect_over25_2goals_trigger`,
`_detect_cs_close_trigger`, `_detect_cs_one_goal_trigger`, `_detect_draw_11_trigger`,
`_detect_ud_leading_trigger`, `_detect_under35_3goals_trigger`, `_detect_away_fav_leading_trigger`,
`_detect_home_fav_leading_trigger`, `_detect_under45_3goals_trigger`, `_detect_cs_11_trigger`,
`_detect_cs_20_trigger`, `_detect_cs_big_lead_trigger`

### Match rate

- **78.2% MATCH**, 81.1% MATCH+MIN_DIFF (medido con `tests/reconcile.py` en 1162 partidos, todas las estrategias unificadas)
- **LIVE P/L >= BT P/L** confirmado (BT es conservador)
- Discrepancias restantes son por timing (BT muestrea en filas discretas vs LIVE en instante actual)

### Post-filtros (Filtros Realistas) — ALINEADOS

`analytics.py:_apply_realistic_adjustments()` aplica los filtros realistas en el backend.

### Herramientas de verificacion

- `tests/reconcile.py` — simula LIVE fila a fila y compara con BT
- `auxiliar/compare_bt_live.py` — compara rendimiento BT vs LIVE estimado
- `.claude/agents/system-auditor.md` — agente de mantenimiento de alineamiento

## Problemas conocidos

1. **Momentum xG hardcodeado**: Params internos (sotMin, sotRatioMin, xgUnderperfMin, oddsMin, oddsMax) no estan en config ni en versions dict. Hardcodeados identicos en backtest y live.
2. **Cache key parcial**: analyze_cartera() cache incluye min_duration + enabled states de las 19 estrategias adicionales. Cambios de parametros config distintos de enabled/min_duration requieren invalidacion manual (limpiar _result_cache).
3. **conservative_odds solo en BT**: Requiere ventana historial, no disponible en live.

## Limpieza 2026-03-08

Limpieza mayor del proyecto para eliminar codigo muerto y simplificar la arquitectura:

- **Frontend**: eliminado `cartera.ts` (1104 lineas), `cartera.worker.ts`; limpiado `api.ts` (-435 lineas)
- **Backend**: eliminados `debug.py`, `simulate.py`; limpiados 15 endpoints de `analytics.py`
- **Archivos**: organizados `_ux/` a `auxiliar/`, limpiados `strategies/`, `analisis/`, logs antiguos
- Todo lo eliminado movido a `/borrar` como red de seguridad
