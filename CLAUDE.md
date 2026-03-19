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
   - El backtest se ejecuta via `scripts/bt_optimizer.py` (nuevo, preferido) o el notebook legacy `analisis/strategies_designer.ipynb`.
   - `scripts/bt_optimizer.py` ejecuta grid search completo via `_analyze_strategy_simple()` directamente (no usa analyze_cartera()). Fases: 0=carga datos, 1=grid search individual, 2=build config optima, 3=presets via optimizer_cli, 4=apply, 5=export.
   - Backend (`csv_reader.py:analyze_cartera()`) genera bets con condiciones basicas para cada estrategia activa.
   - Ya no existe capa de filtrado frontend (cartera.ts fue eliminado en limpieza 2026-03-08).
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
  scripts/               → 9 scripts (find_matches, clean_games, bt_optimizer, etc.)
  dashboard/
    backend/
      main.py            → FastAPI app + 5 background tasks (417 lineas)
      api/analytics.py   → Paper trading, senales, cartera (750 lineas)
      api/alerts.py      → Alertas y monitor (~750 lineas)
      api/bets.py        → CRUD apuestas + cashout/settlement (604 lineas)
      api/config.py      → GET/PUT cartera_config.json (102 lineas)
      api/matches.py     → Datos de partidos (133 lineas)
      api/system.py      → Start/stop scraper (381 lineas)
      api/optimize.py    → Optimizacion presets: steepest descent dinamico + adjustments (~700 lineas)
      api/optimizer_cli.py → CLI para optimizacion de portfolio (~500 lineas)
      utils/csv_reader.py → Estrategias, backtest, live, helpers compartidos (~6200 lineas)
      utils/sd_strategies.py → eval_sd() evaluador legacy para notebook (205 lineas)
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

32 estrategias independientes. Cada una tiene su propia clave en `cartera_config.json`, su propio trigger `_detect_<name>_trigger()` en csv_reader.py, deteccion live via `detect_betting_signals()` y backtest via `analyze_cartera()`. No hay categorias ni jerarquias.

**Para consultar qué estrategias están activas y sus parámetros actuales, leer directamente `betfair_scraper/cartera_config.json`** — es la única fuente de verdad. El estado en cualquier documento es siempre potencialmente desactualizado.

Triggers de todas las estrategias en `betfair_scraper/dashboard/backend/utils/csv_reader.py` (32 funciones `_detect_*_trigger`). `sd_strategies.py` contiene solo el evaluador `eval_sd()` para uso del notebook legacy. Generadores auxiliares legacy en `auxiliar/sd_generators.py`.

## Quality Gates (aplicados a TODAS las estrategias)

1. **N >= G_MIN_BETS**: `max(15, n_partidos // 25)` (~46 con 1166 partidos)
2. **ROI >= G_MIN_ROI** (10%): ROI calculado como `sum(pl) / N * 100` donde pl es profit por £1 stake
3. **IC95_lower >= IC95_MIN_LOW** (40%): intervalo Wilson al 95%

Implementados en `_eval_bets()` (`scripts/bt_optimizer.py`), `_eval_combo()` (notebook) y `eval_sd()` (`sd_strategies.py`).

### bt_optimizer.py — resultados con 1202 partidos (2026-03-13)

Resultados del ultimo run completo (1202 partidos): ver `auxiliar/bt_optimizer_results.json`. Las 32 estrategias se evaluan; las que no pasan quality gates quedan con `enabled: false` en `cartera_config.json`.

bt_optimizer.py features: `_eval_preset_real_stats()` para stats honestas de phase4, `MIN_PRESET_N=200`, `DEFAULT_SELECTOR="robust"`.

**cartera_config.json actual**: 32 estrategias, enabled segun ultimo BT run. El portfolio optimizer (phase3) genera 4 presets via optimizer_cli. Todas las estrategias son iguales, no hay jerarquias ni categorias.

### phase4_apply — merge inteligente

`phase4_apply()` en `scripts/bt_optimizer.py` hace merge:
- Estrategias que el preset ACTIVA: aplica todos los params del preset (portfolio-optimizados).
- Estrategias que el preset DESACTIVA: solo cambia `enabled=False`, preserva params optimizados.
- Estrategias no cubiertas por el preset: sin cambios.

### _build_preset_config

`optimizer_cli._build_preset_config(disabled, adj, risk_filter, br_mode, ...)` parte del `cartera_config.json` actual. Recibe un `disabled: set` con las estrategias que el optimizer decidio desactivar (dinamico, no hardcodeado). Los params (xgMax, driftMin, etc.) se preservan del grid search de bt_optimizer. Respeta quality gates: nunca re-habilita una estrategia que bt_optimizer marco como `enabled: false`.

## Sistema de Presets

Los presets se computan offline via `optimizer_cli.py` y se guardan directamente en `cartera_config.json`. La optimizacion ejecuta estas fases:

1. **Phase 1**: steepest descent forward+backward sobre TODAS las estrategias presentes en los bets (dinamico, no hardcodeado). Prueba `risk_filter` (4 opciones) y `bankroll_mode` (solo para min_dd — irrelevante para max_roi/max_pl/max_wr porque usan metricas flat).
2. **Phase 2**: adjustments realistas (7,776 combos): dedup, min/max odds, slippage, conflict filter, stability, minute ranges.
3. **Phase 2.5**: re-check post-adj — steepest descent adicional con adjustments aplicados.
4. **Phase 3**: momentum minute range (5 opciones).
5. **Phase 4**: cashout pct (9 opciones).

Produce la configuracion optima segun el criterio seleccionado (max_roi, max_pl, max_wr, min_dd).

## 5 Background tasks del backend

1. `auto_refresh_matches()` — cada 10 min: clean_games + find_matches
2. `_scheduler_watchdog()` — reinicia auto_refresh si crashea
3. `_scraper_watchdog()` — monitora heartbeat, auto-restart scraper si muerto
4. `auto_paper_trading()` — cada 60s: detecta senales + coloca bets + cashout
5. `_paper_trading_watchdog()` — reinicia paper trading si crashea

## Alineamiento BT↔LIVE (completado 2026-03-11)

Las **32 estrategias** usan **helpers compartidos**. BT y LIVE ejecutan el mismo codigo de deteccion.

### Arquitectura de helpers compartidos

Cada estrategia tiene un helper `_detect_<name>_trigger(rows, curr_idx, cfg)` en csv_reader.py que:
- **BT** llama iterando todas las filas con `curr_idx=idx` + persistencia (min_dur)
- **LIVE** llama con `curr_idx=len(rows)-1` (ultima fila)
- Solo mira `rows[:curr_idx+1]` — nunca filas futuras

**32 triggers** en csv_reader.py, todos con la misma interfaz `_detect_<name>_trigger(rows, curr_idx, cfg)`:

`_detect_back_draw_00_trigger`, `_detect_xg_underperformance_trigger`, `_detect_odds_drift_trigger`,
`_detect_goal_clustering_trigger`, `_detect_pressure_cooker_trigger`, `_detect_momentum_xg_trigger`,
`_detect_tardesia_trigger`, `_detect_over25_2goal_trigger`, `_detect_under35_late_trigger`,
`_detect_lay_over45_v3_trigger`, `_detect_draw_xg_conv_trigger`, `_detect_poss_extreme_trigger`,
`_detect_longshot_trigger`, `_detect_cs_00_trigger`, `_detect_over25_2goals_trigger`,
`_detect_cs_close_trigger`, `_detect_cs_one_goal_trigger`, `_detect_draw_11_trigger`,
`_detect_ud_leading_trigger`, `_detect_under35_3goals_trigger`, `_detect_away_fav_leading_trigger`,
`_detect_home_fav_leading_trigger`, `_detect_under45_3goals_trigger`, `_detect_cs_11_trigger`,
`_detect_cs_20_trigger`, `_detect_cs_big_lead_trigger`, `_detect_draw_equalizer_trigger`,
`_detect_draw_22_trigger`, `_detect_lay_over45_blowout_trigger`, `_detect_over35_early_goals_trigger`,
`_detect_lay_draw_away_leading_trigger`, `_detect_lay_cs11_trigger`

### Match rate

- **97.3% MATCH**, 97.7% MATCH+MIN_DIFF (medido con `tests/reconcile.py` en 1202 partidos, tras deduplicacion de mercado 2026-03-13)
- **LIVE P/L >= BT P/L** confirmado (BT es conservador)
- Discrepancias restantes: BT_ONLY por null goals en filas intermedias (scores oscilantes en CSVs historicos), LIVE_ONLY por FT score null, MINUTE_DIFF por timing

### Post-filtros (Filtros Realistas) — ALINEADOS

`analytics.py:_apply_realistic_adjustments()` aplica los filtros realistas en el backend.

### Herramientas de verificacion

- `tests/reconcile.py` — simula LIVE fila a fila y compara con BT. VERSIONS = {'_strategy_configs': s, '_min_duration': md}. Aplica market-group dedup al LIVE side (via `_STRATEGY_MARKET`) antes de comparar. ~175 lineas.
- `auxiliar/compare_bt_live.py` — compara rendimiento BT vs LIVE estimado
- `.claude/agents/system-auditor.md` — agente de mantenimiento de alineamiento

## Problemas conocidos

1. **Momentum xG hardcodeado**: Params internos (sotMin, sotRatioMin, xgUnderperfMin, oddsMin, oddsMax) no estan en config. Hardcodeados identicos en backtest y live.
2. **Cache key parcial**: analyze_cartera() cache incluye min_duration + enabled states de todas las estrategias del registry. Cambios de parametros config distintos de enabled/min_duration requieren invalidacion manual (limpiar _result_cache).
3. **conservative_odds solo en BT**: Requiere ventana historial, no disponible en live.
4. **Portfolio optimizer dinamico** (implementado 2026-03-19): optimizer_cli usa steepest descent forward+backward sobre TODAS las estrategias (sin hardcoding). `bankroll_mode` solo se prueba para `min_dd` (irrelevante para max_roi/max_pl/max_wr). `min_dd` usa Calmar ratio con penalizacion exponencial por drawdown >30%. `_co_market_cols()` y `_is_adverse_goal()` cubren las 32 estrategias para cashout simulation. `MIN_PORTFOLIO_BETS=200` previene over-selectivity.
6. **Deduplicacion de mercado** (implementado 2026-03-13, actualizado 2026-03-16): Una sola apuesta por mercado por partido. `_STRATEGY_MARKET` en csv_reader.py define los grupos. Primera estrategia en disparar (por minuto) tiene prioridad. LIVE dedup es siempre-activo via Pass 5 en `_apply_realistic_adjustments()`. Para ver los grupos actuales, leer `_STRATEGY_MARKET` en csv_reader.py:372.

## placed_bets.csv — estado 2026-03-13

Curado 2026-03-13: 239 bets, 17 estrategias activas. Bets de estrategias desactivadas eliminados; bets faltantes de partidos tracked añadidos retroactivamente.

## Limpieza 2026-03-08

Limpieza mayor del proyecto para eliminar codigo muerto y simplificar la arquitectura:

- **Frontend**: eliminado `cartera.ts` (1104 lineas), `cartera.worker.ts`; limpiado `api.ts` (-435 lineas)
- **Backend**: eliminados `debug.py`, `simulate.py`; limpiados 15 endpoints de `analytics.py`
- **Archivos**: organizados `_ux/` a `auxiliar/`, limpiados `strategies/`, `analisis/`, logs antiguos
- Todo lo eliminado movido a `/borrar` como red de seguridad
