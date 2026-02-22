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
  logs/                  → Logs scraper
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
      utils/csv_reader.py → TODO: estrategias, backtest, live (~5100 lineas)
      utils/scraper_status.py → Estado scraper via psutil + log parsing
      utils/signals_audit_logger.py → Audit log rotativo
    frontend/src/
      lib/api.ts         → Cliente API tipado (938 lineas)
      lib/cartera.ts     → Filtros, simulacion bankroll, optimizacion, presets 3 fases (~1100 lineas)
      lib/trading.ts     → PressureIndex, divergencia, momentum swings (311 lineas)
      lib/sounds.ts      → Alerta sonora Web Audio (61 lineas)
      lib/utils.ts       → cn(), formatTimeAgo(), formatTimeTo() (27 lineas)
      components/        → 23 componentes React (Dashboard, StrategiesView, etc.)
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

## Divergencias Live vs Backtest (auditado 2026-02-22)

Resultado del audit completo de `detect_betting_signals()` vs `filter*Bets()`. Ordenadas por impacto.

### Divergencias por estrategia

#### Back Empate 0-0 (draw)
- **ALINEADO**: Todos los filtros (xgMax, possMax, shotsMax, xgDomAsym, minuteMin, minuteMax) se pasan al dict versions y se aplican en live igual que en backtest.

#### xG Underperformance (xg)
- **ALINEADO**: xgExcessMin, sotMin, minuteMin, minuteMax se pasan y aplican igual.
- **Fallback hardcodeado en v3**: Si `_xg_minute_max >= 90` en live, usa cutoff=70 igualmente (v3 define minuteMax=70 en el UI, por lo que en la practica no es divergencia si el config se guarda desde el UI).

#### Odds Drift Contrarian (drift)
- **ALINEADO** (corregido 2026-02-22): minute gate usa `_drift_minute_min` del config, minuteMax comprobado, V6 implementado via `_compute_synthetic_at_trigger`.
- **[MINOR] Nota**: filterDriftBets en frontend usa `b.minuto < p.minuteMin` (corregido de `<=`).

#### Goal Clustering (clustering)
- **ALINEADO** (corregido 2026-02-22): xgRemMin comprobado via `_compute_synthetic_at_trigger`. Clustering V4 se comporta igual en live y backtest.
- **Nota**: max minuto de goal detection en backtest (`analyze_cartera`) y live ambos limitan a 80 de facto. No hay divergencia real.

#### Pressure Cooker (pressure)
- **ALINEADO** (corregido 2026-02-22): Eliminados los clamps `max(65,...)` y `min(75,...)`. Live usa el rango configurado directamente con defaults 65/75.

#### Momentum xG (momentum)
- **ALINEADO** (corregido 2026-02-22): minute range usa defaults suaves como Pressure. Config momentum.minuteMin/Max se aplica directamente sin clamps.
- **Params hardcodeados en live y backtest por igual**: sotMin, sotRatio, xgUnderperf, oddsMin, oddsMax estan hardcodeados identicos en ambos sistemas. No estan en config.

#### Tarde Asia
- Solo existe en backtest (tracking historico). No hay logica en `detect_betting_signals`.

### Post-filtros (Filtros Realistas) — ALINEADOS (corregido 2026-02-22)

`analytics.py:_apply_realistic_adjustments()` aplica TODOS los filtros en el mismo orden que `cartera.ts:applyRealisticAdjustments()`. Se usa en `get_betting_signals` y `run_paper_auto_place`.

| Filtro Realista | Backtest | Live |
|-----------------|----------|------|
| global_minute_min/max | SI | SI (pass 1) |
| adjDriftMinMin | SI | SI (pass 1, usa drift.minuteMin del config) |
| min_odds / max_odds con slippage | SI | SI (pass 1, aplica slippage_pct antes) |
| risk_filter | SI | SI (pass 1) |
| stability | SI | SI (pass 2, 1 captura ≈ 0.5 min) |
| conflict_filter (MomXG+xGUnderperf) | SI | SI (pass 3) |
| allow_contrarias | SI | SI (pass 4) |
| dedup (mismo match+mercado) | SI | SI (pass 5) |
| conservative_odds | SI | NO — requiere ventana historial, no disponible en live |
| maturity (min_duration_caps) | SI | SI (is_mature en detect + post-filtro) |

## Problemas conocidos

1. **Momentum xG hardcodeado**: Params internos (sotMin, sotRatioMin, xgUnderperfMin, oddsMin, oddsMax) no estan en config ni en versions dict. Hardcodeados identicos en backtest y live.
3. **Odds Drift alineado**: analyze_cartera() ahora usa el mismo algoritmo que live: lookback fijo 10 min + mismo marcador en fila historica + score_confirm_count >= 3.
4. **Cache key incompleto**: analyze_cartera() cache solo por min_duration. Correcto para patron actual pero fragil si se mueven filtros al backend.
5. **adjDriftMinMin (realistic adj) no en live**: El ajuste drift_min_minute de los Filtros Realistas solo aplica en backtest. En live, el minuteMin del config de drift ya lo controla directamente.
