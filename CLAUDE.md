# Instrucciones para Claude Code

## OBLIGATORIO: Leer antes de actuar

**LEER `ARCHITECTURE.md`** en la raiz del proyecto antes de hacer cualquier cambio de codigo. Contiene la arquitectura real y verificada del sistema completo.

## Archivos temporales y auxiliares

**REGLA**: Todo archivo temporal, prescindible o de análisis ad hoc debe guardarse en `/aux` (raiz del proyecto), nunca en la raiz ni en otros directorios.

Ejemplos de lo que va en `/aux`:
- Scripts temporales de análisis (`analyze_*.py`, `test_*.py`, `check_*.py`)
- Capturas de pantalla (`.png`, `.jpg`)
- CSVs de resultados intermedios
- JSONs de exploración
- Logs de análisis puntuales
- Cualquier fichero que no forme parte de la arquitectura permanente

La carpeta `/aux` puede borrarse en cualquier momento sin afectar al sistema. Si no existe, crearla antes de guardar el archivo.

## Reglas criticas

1. **NO ASUMIR** como funciona algo. Verificar siempre en el codigo fuente antes de hacer afirmaciones.

2. **DOBLE CAPA DE FILTRADO (BACKTEST)**:
   - Backend (`csv_reader.py:analyze_cartera()`) genera un SUPERCONJUNTO de bets con condiciones basicas + version flags.
   - Frontend (`cartera.ts:filter*Bets()`) aplica los filtros de `cartera_config.json`.
   - Los params de config (xgMax, possMax, etc.) se aplican en FRONTEND, no en backend.
   - `analyze_cartera()` solo recibe `min_dur` de config. Cache key solo incluye min_duration.

3. **CAPA UNICA (LIVE)**:
   - `analytics.py` construye un dict `versions` con TODOS los params de config.
   - `csv_reader.py:detect_betting_signals(versions)` aplica filtros inline.
   - No hay segunda capa. Ademas, `analytics.py` aplica post-filtros (odds, risk, maturity).

4. **FICHERO CRITICO**: `betfair_scraper/dashboard/backend/utils/csv_reader.py` (~5100 lineas).
   - Contiene TODA la logica de estrategias (backtest y live), carga de datos, cashout simulation, watchlist.
   - Cambios aqui deben ser quirurgicos y verificados.

5. **CONFIG**: `betfair_scraper/cartera_config.json` es la unica fuente de verdad de parametros.

6. **NULL DATA GAP (descartado)**: Ambos sistemas (backtest y live) parten del mismo CSV. Si un stat es null en una fila del CSV historico, eso refleja que el scraper tampoco lo tenia disponible en ese momento en vivo. No hay inflacion sistematica del backtest por nulls.

7. **NO CONTRADECIRSE**: Antes de hacer una afirmacion sobre la arquitectura, verificar en el codigo. No decir "funciona asi" y luego "en realidad funciona de otra forma".

8. **DOCUMENTAR PROACTIVAMENTE**: Cualquier cambio que afecte a logica, interfaz o arquitectura documentada DEBE reflejarse en este CLAUDE.md sin que el usuario lo pida. Si se modifica un fichero clave (cartera.ts, csv_reader.py, StrategiesView.tsx, analytics.py, etc.) y el cambio altera el comportamiento documentado, actualizar la seccion correspondiente antes de terminar la tarea.

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
      api/analytics.py   → Paper trading, senales, cartera (654 lineas)
      api/bets.py        → CRUD apuestas + cashout/settlement (604 lineas)
      api/config.py      → GET/PUT cartera_config.json (102 lineas)
      api/matches.py     → Datos de partidos (133 lineas)
      api/explorer.py    → Explorador estrategias (95 lineas)
      api/system.py      → Start/stop scraper (381 lineas)
      api/debug.py       → Debug endpoints (HTML snapshots, memory)
      api/optimize.py    → Optimizacion presets (Phase 1+2)
      api/optimizer_cli.py → CLI para optimizacion paralela
      api/simulate.py    → Simulador de senales (replay timeline)
      utils/csv_reader.py → Estrategias, backtest, live, helpers compartidos (~5300 lineas)
      utils/scraper_status.py → Estado scraper via psutil + log parsing
      utils/signals_audit_logger.py → Audit log rotativo
    frontend/src/
      lib/api.ts         → Cliente API tipado (938 lineas)
      lib/cartera.ts     → Filtros, simulacion bankroll, optimizacion, presets 3 fases (~1100 lineas)
      lib/trading.ts     → PressureIndex, divergencia, momentum swings (311 lineas)
      lib/sounds.ts      → Alerta sonora Web Audio (61 lineas)
      lib/utils.ts       → cn(), formatTimeAgo(), formatTimeTo() (27 lineas)
      components/        → 21 componentes React (Dashboard, StrategiesView, etc.)

aux/                     → Archivos temporales/prescindibles (gitignored)
strategies/              → Reportes y tracker del strategy-designer agent
.claude/agents/          → Definiciones de agentes (backtest-auditor, strategy-designer, etc.)
analisis/                → Notebooks, audits, portfolio analysis
```

## 7 Estrategias

| Estrategia | Clave config | Estado |
|------------|-------------|--------|
| Back Empate 0-0 | draw | Activa (6 versiones: v1/v15/v2/v2r/v3/v4) |
| xG Underperformance | xg | Activa (3 versiones: base/v2/v3) |
| Odds Drift Contrarian | drift | Activa (6 versiones: v1-v6) |
| Goal Clustering | clustering | Activa (3 versiones: v2/v3/v4) |
| Pressure Cooker | pressure | Activa (2 versiones: v1/v2) |
| Momentum xG | momentum_xg | Activa (2 versiones: v1/v2) |
| Tarde Asia | tarde_asia | Inactiva (solo tracking backtest) |

## Sistema de Presets (cartera.ts + StrategiesView.tsx)

**Regla**: Cualquier parametro que sea guardable con el boton Guardar DEBE poder ser optimizado y asignado por los presets.

### Lo que optimiza cada preset

Los presets ejecutan una busqueda en 3 fases y asignan TODOS los parametros configurables (excepto bankroll inicial y stake, que son del usuario):

| Parametro | Fuente |
|-----------|--------|
| Versiones de estrategia (draw/xg/drift/clustering/pressure/tardeAsia/momentumXG) | Phase 1 |
| Modo bankroll (fixed/kelly/half_kelly/dd_protection/anti_racha) | Phase 1 |
| Filtro de riesgo (all/sin_riesgo/con_riesgo/riesgo_medio) | Phase 1 |
| Ajustes realistas (dedup, minOdds, maxOdds, slippage, conflictFilter, allowContrarias, stability, conservativeOdds, driftMinMinute) | Phase 2 |
| Rango global de minutos (globalMinuteMin/Max) | Phase 2 (candidatos: null, 15-85, 20-80) |
| Rango de minutos Momentum xG (momentumMinuteMin/Max) | Phase 3 (5 opciones: 0-90, 5-85, 10-80, 15-75, 20-70) |
| Rangos de minutos Pressure/TardeAsia | Fijos a 0-90 (su logica ya esta acotada en backend) |
| CO percentage (coLayPct) | Heuristico por criterio |

### Heuristico CO por criterio
- `max_roi` → 15% (solo cashouts con ganancia grande)
- `max_pl` → 20% (equilibrado)
- `max_wr` → 30% (cashout agresivo, mas % ganadas)
- `min_dd` → 10% (cashout muy temprano, reduce perdidas)
- `max_bets` → 20% (default)

### Interfaz `FullPresetResult` (cartera.ts)
```typescript
{
  combo: VersionCombo           // versiones + bankroll mode
  riskFilter: RiskFilter        // filtro de riesgo
  adj: RealisticAdjustments     // ajustes realistas + rango global
  coLayPct: number              // % cashout
  pressureMinuteRange: { min, max }
  tardeAsiaMinuteRange: { min, max }
  momentumMinuteRange: { min, max }
}
```

### Candidatos Phase 2 (_presetAdjCandidates)
7776 combinaciones (2592 base × 3 rangos globales). Incluye:
- `globalMinuteMin/Max`: null×null, 15×85, 20×80

### Nota importante: CO no se puede optimizar inline
El cashout simulation requiere llamadas al backend (GET /analytics/strategies/cartera con cashout_lay_pct). Por eso se usa heuristico fijo. Si se quiere el CO optimo real, usar el boton "Optimizar CO" (runCOOptimizer) que si hace llamadas al backend.

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

- **83% MATCH**, 89.8% MATCH+MIN_DIFF (medido con `aux/run_reconcile.py`)
- **LIVE P/L >= BT P/L** confirmado (BT es conservador)
- Discrepancias restantes son por timing (BT muestrea en filas discretas vs LIVE en instante actual)

### Post-filtros (Filtros Realistas) — ALINEADOS

`analytics.py:_apply_realistic_adjustments()` aplica los mismos filtros que `cartera.ts:applyRealisticAdjustments()`.

### Herramientas de verificacion

- `aux/run_reconcile.py` — simula LIVE fila a fila y compara con BT
- `aux/compare_bt_live.py` — compara rendimiento BT vs LIVE estimado
- `.claude/agents/backtest-auditor.md` — agente de mantenimiento de alineamiento

## Problemas conocidos

1. **Momentum xG hardcodeado**: Params internos (sotMin, sotRatioMin, xgUnderperfMin, oddsMin, oddsMax) no estan en config ni en versions dict. Hardcodeados identicos en backtest y live.
2. **Cache key incompleto**: analyze_cartera() cache solo por min_duration. Correcto para patron actual pero fragil si se mueven filtros al backend.
3. **conservative_odds solo en BT**: Requiere ventana historial, no disponible en live.
