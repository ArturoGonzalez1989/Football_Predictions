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

4. **FICHERO CRITICO**: `betfair_scraper/dashboard/backend/utils/csv_reader.py` (~5761 lineas).
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
      utils/csv_reader.py → Estrategias, backtest, live, helpers compartidos (~5761 lineas)
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
  sd_generators.py       → 19 generadores SD (1816 lineas)
  sd_filters.py          → Filtros realistas SD (825 lineas)
  run_reconcile.py       → Verificacion BT↔LIVE
  compare_bt_live.py     → Comparacion rendimiento BT vs LIVE
  data_quality_analysis.py → Analisis calidad datos
  data_quality_deep.py   → Analisis profundo calidad datos
strategies/              → Reportes .md de estrategias aprobadas + tracker
.claude/agents/          → Definiciones de agentes (system-auditor, strategy-designer, etc.)
analisis/                → 2 notebooks (strategies_designer + reconcile_bt_live)
borrar/                  → Archivos movidos durante limpieza (red de seguridad)
```

## 7 Estrategias Core (cartera_config.json)

Estrategias de produccion con deteccion live + backtest. Configuradas en `cartera_config.json`. Solo las que pasan quality gates (N minimo, ROI >= 10%, IC95_lower >= 40%) se activan.

| Estrategia | Clave config | Estado |
|------------|-------------|--------|
| Back Empate 0-0 | draw | Desactivada por IC95 gate (6 versiones: v1/v15/v2/v2r/v3/v4) |
| xG Underperformance | xg | Activa (3 versiones: base/v2/v3) |
| Odds Drift Contrarian | drift | Depende de datos (6 versiones: v1-v6) |
| Goal Clustering | clustering | Activa (3 versiones: v2/v3/v4) |
| Pressure Cooker | pressure | Activa (2 versiones: v1/v2) |
| Momentum xG | momentum_xg | Depende de datos (2 versiones: v1/v2) |
| Tarde Asia | tarde_asia | Inactiva (solo tracking backtest) |

## 19 Estrategias SD (backtest + config)

Descubiertas por el agente strategy-designer. Evaluadas en `analisis/strategies_designer.ipynb`. Se integran en presets via `_STRATEGY_PARAMS` (notebook) y `_build_preset_config()` (`optimizer_cli.py`). Muchas SD strategies ahora tienen entradas en `cartera_config.json` para sus parametros. **NO tienen deteccion live** — solo backtest. No hay codigo en `detect_betting_signals()` para SD.

Configs en `betfair_scraper/dashboard/backend/utils/sd_strategies.py`, generadores en `auxiliar/sd_generators.py`, filtros en `auxiliar/sd_filters.py`.

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

## Alineamiento BT↔LIVE (completado 2026-03-06)

Las 7 estrategias usan **helpers compartidos** (GR8 compliant). BT y LIVE ejecutan el mismo codigo.

### Arquitectura de helpers compartidos

Cada estrategia tiene un helper `_detect_<name>_trigger(rows, curr_idx, cfg)` en csv_reader.py que:
- **BT** llama iterando todas las filas con `curr_idx=idx` + persistencia (min_dur)
- **LIVE** llama con `curr_idx=len(rows)-1` (ultima fila)
- Solo mira `rows[:curr_idx+1]` — nunca filas futuras

| Helper | Estrategia |
|--------|-----------|
| `_detect_draw_trigger` + `_detect_draw_filters` | Back Empate 0-0 |
| `_detect_xg_trigger` | xG Underperformance |
| `_detect_drift_trigger` | Odds Drift Contrarian |
| `_detect_clustering_trigger` | Goal Clustering |
| `_detect_pressure_trigger` | Pressure Cooker |
| `_detect_momentum_trigger` | Momentum xG |
| `_detect_tardesia_trigger` | Tarde Asia |

### Match rate

- **83% MATCH**, 89.8% MATCH+MIN_DIFF (medido con `auxiliar/run_reconcile.py`)
- **LIVE P/L >= BT P/L** confirmado (BT es conservador)
- Discrepancias restantes son por timing (BT muestrea en filas discretas vs LIVE en instante actual)

### Post-filtros (Filtros Realistas) — ALINEADOS

`analytics.py:_apply_realistic_adjustments()` aplica los filtros realistas en el backend.

### Herramientas de verificacion

- `auxiliar/run_reconcile.py` — simula LIVE fila a fila y compara con BT
- `auxiliar/compare_bt_live.py` — compara rendimiento BT vs LIVE estimado
- `.claude/agents/system-auditor.md` — agente de mantenimiento de alineamiento

## Problemas conocidos

1. **SD sin deteccion live**: Las 19 estrategias SD solo funcionan en backtest (notebook). No hay codigo en `detect_betting_signals()` para SD.
2. **Momentum xG hardcodeado**: Params internos (sotMin, sotRatioMin, xgUnderperfMin, oddsMin, oddsMax) no estan en config ni en versions dict. Hardcodeados identicos en backtest y live.
3. **Cache key incompleto**: analyze_cartera() cache solo por min_duration. Correcto para patron actual pero fragil si se mueven filtros al backend.
4. **conservative_odds solo en BT**: Requiere ventana historial, no disponible en live.

## Limpieza 2026-03-08

Limpieza mayor del proyecto para eliminar codigo muerto y simplificar la arquitectura:

- **Frontend**: eliminado `cartera.ts` (1104 lineas), `cartera.worker.ts`; limpiado `api.ts` (-435 lineas)
- **Backend**: eliminados `debug.py`, `simulate.py`; limpiados 15 endpoints de `analytics.py`
- **Archivos**: organizados `_ux/` a `auxiliar/`, limpiados `strategies/`, `analisis/`, logs antiguos
- Todo lo eliminado movido a `/borrar` como red de seguridad
