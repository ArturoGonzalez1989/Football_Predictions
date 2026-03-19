# Arquitectura del Proyecto — Betfair Scraper + Dashboard

> **LEER ANTES DE CUALQUIER ACCION.** Este documento describe la arquitectura real y verificada del sistema completo. Cualquier cambio de codigo debe partir de la comprension de este documento.

---

## 1. Vision general

El sistema captura cuotas y estadisticas de partidos de futbol en vivo desde Betfair Exchange, las almacena en CSVs, y proporciona un dashboard web para:

1. **Monitorizar partidos en vivo** (cuotas, stats, momentum)
2. **Detectar senales de apuesta** en tiempo real (32 estrategias independientes, todas activas en BT y LIVE)
3. **Paper trading automatico** (colocacion automatica de apuestas simuladas)
4. **Analisis historico** (backtest via `scripts/bt_optimizer.py` CLI o notebook legacy)
5. **Optimizacion de cartera** (grid search individual + portfolio optimizer via `bt_optimizer.py`)
6. **Strategy Designer** (descubrimiento automatizado de nuevas estrategias via agentes)

---

## 2. Estructura de directorios

```
betfair_scraper/
├── main.py                    # Motor de scraping (Selenium multi-driver, ~3000 lineas)
├── config.py                  # Selectores CSS, timeouts, opciones Chrome (100 lineas)
├── stats_api.py               # Cliente REST Opta/Stats Perform (923 lineas)
├── extract_iframe_stats.py    # Fallback: stats via scraping de iframe (233 lineas)
├── cartera_config.json        # UNICA FUENTE DE VERDAD de parametros de estrategia
├── games.csv                  # Lista de partidos activos a scrapear
├── placed_bets.csv            # Apuestas paper colocadas
├── signals_audit.log          # Audit log rotativo de senales (50MB x 10)
├── supervisor_workflow.py     # Orquestador de 7 scripts de mantenimiento
├── data/                      # CSVs individuales: partido_*.csv + .heartbeat
├── logs/                      # Logs del scraper (scraper_YYYYMMDD_HHMMSS.log)
├── scripts/                   # 9 scripts de utilidad
│   ├── bt_optimizer.py        # Pipeline BT completo: grid search + presets + apply + export
│   ├── start_scraper.py       # Monitor de proceso, auto-restart
│   ├── find_matches.py        # Descubrimiento de partidos (Playwright)
│   ├── clean_games.py         # Eliminar partidos terminados de games.csv
│   ├── check_urls.py          # Eliminar URLs 404
│   ├── generate_report.py     # Informes de salud del sistema
│   ├── validate_stats.py      # Comparar stats capturadas vs disponibles
│   ├── unify_data.py          # Combinar CSVs en unificado.csv
│   └── strategy_triggers.py   # Triggers legacy (algunos triggers estan aqui)
│
└── dashboard/
    ├── start.bat              # Lanza backend + frontend
    ├── signals_log.csv        # Log de senales detectadas
    ├── backend/
    │   ├── main.py            # FastAPI app, routers, 5 background tasks (417 lineas)
    │   ├── api/
    │   │   ├── analytics.py   # Paper trading, senales, cartera, cashout (750 lineas)
    │   │   ├── alerts.py      # Alertas del sistema (monitoring + notificaciones)
    │   │   ├── bets.py        # CRUD apuestas colocadas (604 lineas)
    │   │   ├── config.py      # GET/PUT cartera_config.json (102 lineas)
    │   │   ├── matches.py     # Datos de partidos (133 lineas)
    │   │   ├── system.py      # Start/stop scraper, cleanup Chrome (381 lineas)
    │   │   ├── optimize.py    # Optimizacion presets Phase 1+2 (1329 lineas)
    │   │   └── optimizer_cli.py # CLI para optimizacion paralela (691 lineas)
    │   └── utils/
    │       ├── csv_reader.py      # ~6200 lineas. EL fichero critico. Registry de 32 estrategias + BT + LIVE.
    │       ├── sd_strategies.py   # eval_sd() evaluador legacy para notebook (205 lineas)
    │       ├── scraper_status.py  # Estado del scraper via psutil + log parsing (231 lineas)
    │       └── signals_audit_logger.py  # Audit log rotativo 50MB x 10 (214 lineas)
    │
    └── frontend/
        └── src/
            ├── App.tsx, main.tsx
            ├── index.css          # Tema "Charcoal Pro"
            ├── lib/
            │   ├── api.ts         # Cliente API con interfaces TypeScript (~500 lineas)
            │   ├── trading.ts     # PressureIndex, divergencia, momentum swings (311 lineas)
            │   ├── sounds.ts      # Alerta sonora Web Audio (61 lineas)
            │   └── utils.ts       # cn(), formatTimeAgo(), formatTimeTo() (27 lineas)
            └── components/        # 19 componentes React
                ├── Dashboard.tsx          # Shell de navegacion (7 vistas, polling 10s)
                ├── BettingSignalsView.tsx  # Senales live + watchlist + cartera activa
                ├── PlacedBetsView.tsx      # Tracking de apuestas paper
                ├── LiveView.tsx           # Partidos en vivo (MatchCard por partido)
                ├── MatchCard.tsx          # Tarjeta de partido con stats + cuotas
                ├── DataQualityView.tsx    # Calidad de datos capturados
                ├── AnalyticsView.tsx      # Analisis de mercado
                ├── UpcomingView.tsx       # Proximos partidos
                ├── AlertsView.tsx         # Vista de alertas del sistema
                ├── SystemStatus.tsx       # Estado del sistema + controles
                └── (9 componentes menores: StatusBadge, CaptureIndicator,
                     StatsBar, GapAnalysis, CaptureTable, OddsChart,
                     MomentumChart, MomentumSwings, PriceVsReality)

auxiliar/                      # Archivos auxiliares de analisis (tracked en git, borrable sin riesgo)
├── sd_generators.py           # Generadores legacy de estrategias SD (wrappers sobre triggers)
├── sd_filters.py              # Filtros legacy para backtests SD
├── compare_bt_live.py         # Comparacion rendimiento BT vs LIVE
├── data_quality_analysis.py   # Analisis de calidad de datos
├── data_quality_deep.py       # Analisis profundo de calidad de datos
├── bt_optimizer_results.json  # Resultados del ultimo grid search (phases 1+2)
└── PENDING_TASKS.md           # Tareas pendientes con contexto tecnico completo

tests/                         # Herramientas de verificacion permanentes
└── reconcile.py               # Simula LIVE fila a fila y mide match rate vs BT

strategies/                    # Reportes y tracker del strategy-designer agent
├── sd_strategy_tracker.md     # Estado de investigacion de todas las rondas
└── (reportes .md de backtests por ronda)

analisis/                      # Notebooks de analisis
├── strategies_designer.ipynb  # Notebook principal: BT + presets + SD (65 celdas)
└── reconcile_bt_live.ipynb    # Notebook de reconciliacion BT vs LIVE

.claude/agents/                # Definiciones de agentes Claude
├── system-auditor.md          # Auditor del sistema (alineamiento, salud, etc.)
├── strategy-designer.md       # Disenador de nuevas estrategias (8 pasos)
├── sub-backtest-runner.md     # Sub-agente: ejecuta backtests individuales
├── sub-match-analyzer.md      # Sub-agente: analisis de partidos individuales
└── sub-strategy-meta-analyst.md # Sub-agente: meta-analisis de portfolio

borrar/                        # Archivos movidos durante limpieza, pendientes de borrado definitivo
```

---

## 3. Componentes principales

### 3.1 Motor de scraping (`main.py`)

- **Clase `MatchDriver`** (linea 1955): un proceso Chrome (Selenium) independiente por partido. Encapsula driver, lock, opta_event_id cache, consecutive_failures counter, y tracking de stage/progreso para heartbeat.
- **`captura_paralela_multidriver()`** (linea 2250): ThreadPoolExecutor, max 16 workers concurrentes.
- **Ciclo de captura**: cada `CICLO_TOTAL_SEG` = 30 segundos captura cuotas de todos los mercados + stats.
- **Flujo por captura** (`MatchDriver.capturar()`, linea 2040):
  1. Click boton "Actualizar" (refresh de pagina parcial)
  2. `extraer_info_partido()` → minuto, goles, estado
  3. `extraer_runners_match_odds()` → back/lay home, draw, away (6 precios)
  4. Mecanismo F5: si <2 de los 3 back criticos estan presentes → `driver.refresh()` + reintento
  5. `extraer_over_under()` → back/lay Over/Under 0.5-6.5. Si <4 campos → `extraer_over_under_via_mercado()` (fallback mercado individual)
  6. `extraer_resultado_correcto()` → ~20+ marcadores back/lay
  7. `extraer_estadisticas()` → intenta Opta API (`stats_api.get_all_stats()`) primero; si falla, `extract_iframe_stats.extract_stats_from_iframe()` como fallback
  8. `extraer_volumen()` → volumen matched del mercado
  9. Momentum: de la API (viene en stats) o fallback visual (`extraer_momentum()`)
  10. `extraer_pais_liga_de_url()` → mapea URL a (Pais, Liga) via `URL_LEAGUE_MAPPING` (150+ entradas)
- **Output por partido**: `data/partido_<match_id>.csv` con 154 columnas (definidas en `CSV_COLUMNS`, linea 278).
- **Heartbeat**: `data/.heartbeat` (JSON) actualizado cada 4s por thread daemon. Contiene drivers_progress con stage/pct por partido.
- **Scheduling**: lee `games.csv`, filtra por ventana temporal (10 min antes → 120 min despues del inicio). Cada 5 ciclos re-lee games.csv para detectar nuevos/eliminados partidos.
- **Auto-recovery**: 3 fallos consecutivos → marca driver como muerto → reinicio automatico.

### 3.2 Stats Perform / Opta API (`stats_api.py`)

- **Base URL**: `https://betfair.cpp.statsperform.com/stats`
- **5 endpoints** llamados en paralelo con ThreadPoolExecutor(max_workers=5):
  - `get_summary_stats()` → xG, posesion, tiros, corners, tarjetas, attacks, opta points, touches
  - `get_momentum_data()` → probabilidades minuto a minuto (home/away sum)
  - `get_attacking_stats()` → bigChances, shotsOffTarget, blockedShots, shootingAccuracy, crosses
  - `get_defence_stats()` → tackles, duelsWon, saves, interceptions, clearances
  - `get_xg_details()` → xG breakdown (open play, set play, penalty)
- **Event ID resolution**: extrae Betfair event ID de HTML/URL → consulta videoplayer endpoint → obtiene Opta UUID (`providerEventId`).
- **Parsing**: datos embebidos en `<script id="__NEXT_DATA__">` como JSON dentro de HTML.
- **Deteccion de campos nuevos**: `_detect_unknown_fields()` compara campos disponibles vs whitelist, logea campos desconocidos.
- **Timeout**: 5 segundos por peticion HTTP.

### 3.3 Iframe fallback (`extract_iframe_stats.py`)

- Navegacion directa al iframe de Sportradar: `https://videoplayer.betfair.es/GetPlayer.do?eID={betfair_event_id}&contentType=viz&contentView=mstats`
- Extrae stats via XPath del DOM renderizado (sibling navigation para pattern "X LABEL Y")
- Campos capturados: SoT, corners, posesion, fouls, saves, dangerous attacks, goal kicks, throw-ins, shots off target, blocked shots, free kicks, offsides, substitutions, injuries
- NO captura: xG, momentum, opta points, big chances, shooting accuracy (solo disponibles via Opta API)
- CRITICO: guarda URL original y vuelve a ella al terminar para no romper el flujo de captura.

### 3.4 Backend FastAPI (`dashboard/backend/main.py`)

- **Puerto**: 8000
- **CORS**: localhost:5173, localhost:3000
- **6 Routers** (incluidos en este orden):
  1. `matches_router` → datos de partidos
  2. `system_router` → start/stop scraper, cleanup
  3. `analytics_router` → prefijo `/api/analytics` (senales, cartera, cashout)
  4. `bets_router` → CRUD apuestas (`/api/bets/*`)
  5. `config_router` → prefijo `/api` (GET/PUT `/config/cartera`)
  6. `alerts_router` → alertas del sistema (monitoring, notificaciones)
- **5 background tasks** (lanzadas en `startup_event`, lineas 343-367):
  1. **`auto_refresh_matches()`** — cada 10 minutos (delay inicial 30s): ejecuta `clean_games.py` + `find_matches.py` via subprocess. Flag `_is_refreshing` previene concurrencia.
  2. **`_scheduler_watchdog()`** — reinicia `auto_refresh_matches()` si crashea.
  3. **`_scraper_watchdog()`** — cada 60s monitoriza heartbeat del scraper. Si stale >120s, ejecuta `start_scraper.py` via subprocess para reiniciar.
  4. **`auto_paper_trading()`** — cada 60s (delay inicial 90s): llama `run_paper_auto_place()` + `run_auto_cashout()`. Limpia cache analytics cada ciclo.
  5. **`_paper_trading_watchdog()`** — reinicia `auto_paper_trading()` si crashea.
- **`/api/health`** endpoint: estado comprensivo del sistema (scraper, paper trading, auto-refresh, config).

### 3.5 csv_reader.py — El fichero critico (~6200 lineas)

Este fichero contiene TODA la logica de:
1. Carga y limpieza de datos CSV
2. **Registry de las 32 estrategias** (`_STRATEGY_REGISTRY`): lista de tuplas `(key, name, trigger_fn, desc, extract_fn, win_fn)`
3. **Runner BT generico** (`_analyze_strategy_simple()`): ejecuta cualquier estrategia del registry
4. **Orquestacion de cartera** (`analyze_cartera()`): itera el registry y llama `_analyze_strategy_simple` para cada una
5. **Deteccion de senales live** (`detect_betting_signals()`): usa los mismos triggers del registry
6. Watchlist (condiciones parciales: `detect_watchlist()`)
7. Cashout simulation y optimizacion
8. Calidad de datos, correlaciones, gap analysis

#### Arquitectura de helpers compartidos BT↔LIVE

**32 triggers** con interfaz identica `_detect_<name>_trigger(rows, curr_idx, cfg)`:
- **BT** (`_analyze_strategy_simple`): itera todas las filas, `curr_idx=idx`
- **LIVE** (`detect_betting_signals`): `curr_idx=len(rows)-1` (ultima fila)
- Solo leen `rows[:curr_idx+1]` — nunca filas futuras

#### Estructuras de datos clave en csv_reader.py

```python
# Registry: 32 entradas, una por estrategia (sin versiones)
_STRATEGY_REGISTRY = [
    ("over25_2goal", "BACK Over 2.5...", _detect_over25_2goal_trigger, ...),
    ("xg_underperformance", "xG Underperf", _detect_xg_underperformance_trigger, ...),
    ("back_draw_00", "Back Empate 0-0", _detect_back_draw_00_trigger, ...),
    ...  # 32 entradas totales
]
_STRATEGY_REGISTRY_KEYS = {e[0] for e in _STRATEGY_REGISTRY}

# Cache de primer trigger (garantiza mismos datos en BT y LIVE)
_trigger_first_data: dict  # keyed by (match_id, strategy_key)
```

#### Funciones principales

| Funcion | Proposito |
|---------|-----------|
| `_analyze_strategy_simple(key, trigger_fn, extract_fn, win_fn, cfg, min_dur)` | Runner BT generico — itera partidos e invoca trigger |
| `_cfg_add_snake_keys(cfg)` | Traduce camelCase config keys → snake_case para los triggers |
| `analyze_cartera()` | Orquestador BT: itera `_STRATEGY_REGISTRY` → `_analyze_strategy_simple` por cada estrategia activa |
| `detect_betting_signals(versions)` | Deteccion live: mismos triggers, `curr_idx=ultimo` |
| `_detect_<name>_trigger(rows, curr_idx, cfg)` | 32 triggers, uno por estrategia |
| `load_games()` | Carga games.csv + escanea data/ para CSV huerfanos |
| `load_all_captures()` | Todas las capturas con ~50 campos de stats |
| `load_match_detail()` | Ultimas 10 capturas + quality score + gap analysis |
| `_get_cached_finished_data()` | Cache 5 min de partidos terminados con rows preprocesados |
| `_co_market_cols()` | Mapea estrategia a columnas back/lay para cashout |
| `_simulate_config()` | Bucle interno de simulacion cashout |
| `optimize_cashout_cartera()` | Grid search sobre modos de cashout |
| `detect_watchlist()` | Partidos cerca de trigger (condiciones parciales) |

**NOTA:** Los numeros de linea cambian frecuentemente. Usar `grep` para localizar funciones especificas.

### 3.6 Frontend React (`dashboard/frontend/src/`)

- **Stack**: React 18 + TypeScript + Vite + Tailwind CSS
- **Puerto dev**: 5173 (proxy Vite redirige `/api` → `localhost:8000`)
- **Tema**: "Charcoal Pro" (dark theme definido en index.css)
- **Dashboard.tsx**: 7 vistas (signals, bets, live, upcoming, quality, analytics, alerts). Polling de matches + system status cada 10 segundos.
- **Librerias clave**:
  - `api.ts`: Cliente API con interfaces TypeScript (~500 lineas). Objeto `api` con metodos tipados para todos los endpoints.
  - `trading.ts`: PressureIndex (rolling window 10 min), divergencia precio-realidad, momentum swings
  - `sounds.ts`: alerta bell via Web Audio API (4 armonicos, decay exponencial)
- **Nota**: La optimizacion de presets y el backtest se realizan ahora via el notebook (`strategies_designer.ipynb`) y `optimizer_cli.py`, no desde el frontend.

---

## 4. Backtest (Cartera)

El backtest principal se ejecuta via `scripts/bt_optimizer.py` (pipeline completo: grid search + presets + apply). El notebook `analisis/strategies_designer.ipynb` es un legacy alternativo.

### bt_optimizer.py — Pipeline completo (5 fases):

```
Phase 0: Carga datos historicos (CSVs partido_*.csv)
       ↓
Phase 1: Grid search individual por estrategia
         _analyze_strategy_simple(key, trigger_fn, extract_fn, win_fn, cfg, min_dur)
         → evaluacion con quality gates (N, ROI, IC95)
       ↓
Phase 2: Construye cartera_config.json optima por estrategia
       ↓
Phase 3: Portfolio presets via optimizer_cli.py
         → 4 criterios: max_roi, max_pl, max_wr, min_dd
         → resultados en data/presets/preset_*.json
       ↓
Phase 4: Apply (merge inteligente en cartera_config.json)
         → preserva las 32 estrategias; disabled solo cambia enabled=False
       ↓
Phase 5: Export CSV/XLSX de resultados
```

### analyze_cartera() — Orquestador backend:

`analyze_cartera()` itera el `_STRATEGY_REGISTRY` y llama `_analyze_strategy_simple()` para cada estrategia:

```
analyze_cartera()
    for (key, name, trigger_fn, extract_fn, win_fn) in _STRATEGY_REGISTRY:
        _analyze_strategy_simple(key, trigger_fn, extract_fn, win_fn, cfg, min_dur)
```

No hay funciones `analyze_strategy_*()` individuales. El unico parametro que `analyze_cartera()` pasa es `min_dur`, leido de `cartera_config.json > min_duration`.

### Endpoint backend:

El endpoint `GET /analytics/strategies/cartera` es usado por `optimizer_cli.py` para obtener el superconjunto de bets para el portfolio optimizer (Phase 3).

---

## 5. PATRON CRITICO: Deteccion live (Senales)

El sistema live funciona de forma **DIFERENTE** al backtest:

### Flujo completo (Live):

```
cartera_config.json
       ↓ (backend lee cada 60s)
analytics.py: run_paper_auto_place()
       ↓
Construye dict "versions" con TODOS los params
       ↓
csv_reader.detect_betting_signals(versions=versions)
       ↓
Aplica filtros INLINE (no hay doble capa)
       ↓
Devuelve solo senales que pasan TODOS los filtros
       ↓
Post-filtros en analytics.py: odds favorable, risk level, maturity
       ↓
Paper trading: auto-coloca bets maduras (age >= min_dur + 1 min)
```

### El dict `versions` (analytics.py):

Se construye directamente desde `cartera_config.json > strategies`. Contiene dos claves:

```python
versions = {
    "_strategy_configs": {        # dict de estrategias con sus params
        "back_draw_00":        {"enabled": True, "xgMax": 0.6, "possMax": 25, ...},
        "xg_underperformance": {"enabled": True, "xgExcessMin": 0.5, ...},
        "odds_drift":          {"enabled": True, "driftMin": 30, ...},
        # ... las 32 estrategias
    },
    "_min_duration": {            # duración mínima de señal (capturas)
        "back_draw_00": 2, "xg_underperformance": 3, ...
    },
}
```

`detect_betting_signals()` pasa `versions["_strategy_configs"]` directamente a cada trigger via `cfg`. **No hay segunda capa de filtrado.**

---

## 6. Backtest vs Live — Arquitectura actual

Tras la limpieza, ambos sistemas son ahora de **capa unica** (backend only):

| Aspecto | Backtest (Cartera) | Live (Senales) |
|---------|-------------------|----------------|
| **Quien ejecuta** | Notebook / optimizer_cli.py | Background task auto_paper_trading() |
| **Capas de filtrado** | 1 (backend genera bets → notebook/CLI filtra y evalua) | 1 (todo inline en backend) |
| **Quien lee cartera_config.json** | Backend (via API) + notebook/CLI | Backend (`analytics.py` cada 60s) |
| **Datos null** | Backend DEJA PASAR bets con datos null | Live REQUIERE datos no-null para generar senal |
| **Triggers** | `_analyze_strategy_simple()` llama triggers con `curr_idx=idx` para cada fila | `detect_betting_signals()` llama triggers con `curr_idx=len(rows)-1` |
| **Parametros de estrategia** | `analyze_cartera()` lee params de `cfg.get("strategies", {})` directamente para cada trigger. | `detect_betting_signals()` lee params de `versions["_strategy_configs"]` pasado por analytics.py — mismo config, mismos params. |

### Nota sobre datos NULL (descartado como problema)

Ambos sistemas (backtest y live) parten del mismo CSV. Si un stat es null en una fila del CSV historico, eso refleja que el scraper tampoco lo tenia disponible en ese momento en vivo. No hay inflacion sistematica del backtest por nulls.

---

## 7. Estrategias

### 7.0 Quality Gates (aplicados a TODAS las estrategias)

Todas las estrategias deben pasar 3 quality gates:

1. **N >= G_MIN_BETS**: minimo de apuestas (dinamico: `max(15, n_partidos // 25)`, ~46 con 1168 partidos)
2. **ROI >= G_MIN_ROI** (10%): retorno minimo sobre inversion
3. **IC95_lower >= IC95_MIN_LOW** (40%): limite inferior del intervalo de confianza Wilson al 95%

Si una estrategia no pasa alguno de estos gates, se desactiva automaticamente en la combinacion optima.

### 7.1 Back Empate (`back_draw_00`)

- **Trigger**: marcador 0-0, minuto >= minuteMin
- **Mercado**: Back al empate (Match Odds)
- **Config params**: `xgMax` (0.6), `possMax` (25), `shotsMax` (20), `xgDomAsym` (false), `minuteMin` (30), `minuteMax` (90)
- **Sentinel OFF**: `xgMax >= 1.0` = filtro xG off, `possMax >= 100` = poss off, `shotsMax >= 20` = shots off
- BT y LIVE usan los mismos params del trigger via `cfg` dict.

### 7.2 xG Underperformance (`xg_underperformance`)

- **Trigger**: equipo perdiendo con xG excess >= xgExcessMin, min >= 15
- **Mercado**: Back Over (linea de Over mas cercana a goles actuales + 0.5)
- **Config params**: `xgExcessMin` (0.5), `sotMin` (2), `minuteMin` (0), `minuteMax` (70)

### 7.3 Odds Drift Contrarian (`odds_drift`)

- **Trigger**: equipo ganando cuyas cuotas suben >= driftMin% en 10 min (mercado pierde confianza → apostar contrarian)
- **Mercado**: Back al equipo ganando cuyas cuotas driftan
- **Config params**: `driftMin` (30), `oddsMax` (999), `goalDiffMin` (0), `minuteMin` (0), `minuteMax` (90), `momGapMin` (0)

### 7.4 Goal Clustering (`goal_clustering`)

- **Trigger**: gol reciente (ultimas 3 capturas) + SoT max >= sotMin + minuto en rango
- **Mercado**: Back Over (total_actual + 0.5)
- **Config params**: `sotMin` (3), `minuteMin` (0), `minuteMax` (60), `xgRemMin` (0)
- **Restriccion**: una sola bet por partido (market dedup).

### 7.5 Pressure Cooker (`pressure_cooker`)

- **Trigger**: empate con goles (1-1+) en minutos 65-75
- **Mercado**: Back Over (total_actual + 0.5)
- **Config params**: `minuteMin` (0), `minuteMax` (90)
- **Logica**: `max(65, minuteMin) <= minuto <= min(75, minuteMax)` (65-75 como limites duros)
- **Score confirmation**: requiere 3+ capturas consecutivas con mismo score.

### 7.6 Momentum xG (`momentum_xg`)

- **Trigger**: equipo dominante en SoT (ratio >= sotRatioMin) + xG underperformance >= xgUnderperfMin + rango de minutos + rango de cuotas
- **Mercado**: Back al equipo dominante (home o away)
- **Config params**: `minuteMin` (0), `minuteMax` (90). Params internos (sotMin, sotRatioMin, xgUnderperfMin, oddsMin, oddsMax) hardcodeados en el trigger — no en config.
- LIVE usa `max(hardcoded_min, minuteMin)` y `min(hardcoded_max, minuteMax)`.

### 7.7 Tarde Asia (`tarde_asia`) — INACTIVA

- **Trigger**: partidos de ligas objetivo (Bundesliga, Ligue, Eredivisie, J-League, K-League) en primeros 15 minutos
- **Mercado**: Back Over 2.5
- **Deteccion de liga**: por URL keywords primero, luego fallback por nombres de equipos (listas hardcodeadas de equipos por pais)
- Config: `enabled: false`. No genera senales live.

### 7.8 Las 25 estrategias adicionales — completamente integradas

Las 31 estrategias adicionales fueron descubiertas por el agente strategy-designer en varias rondas. Todas son entidades completamente independientes e iguales al resto.

**Integracion completa** (identica a las 7 estrategias originales):
- Trigger propio `_detect_<name>_trigger()` en `csv_reader.py`
- BT via `analyze_cartera()` → `_analyze_strategy_simple()`
- LIVE via `detect_betting_signals()` con los mismos triggers
- Config propia en `cartera_config.json`

**Las 25 estrategias:**

| # | Clave | Descripcion |
|---|-------|-------------|
| 1 | `over25_2goal` | BACK O2.5 from 2-Goal Lead |
| 2 | `under35_late` | BACK U3.5 Late |
| 3 | `lay_over45_v3` | LAY O4.5 V3 Tight |
| 4 | `draw_xg_conv` | BACK Draw xG Convergence |
| 5 | `poss_extreme` | BACK O0.5 Poss Extreme |
| 6 | `longshot` | BACK Longshot |
| 7 | `cs_00` | BACK CS 0-0 |
| 8 | `over25_2goals` | BACK O2.5 from Two Goals |
| 9 | `cs_close` | BACK CS 2-1/1-2 |
| 10 | `cs_one_goal` | BACK CS 1-0/0-1 |
| 11 | `draw_11` | BACK Draw 1-1 |
| 12 | `ud_leading` | BACK UD Leading |
| 13 | `under35_3goals` | BACK U3.5 Three-Goal Lid |
| 14 | `away_fav_leading` | BACK Away Fav Leading |
| 15 | `home_fav_leading` | BACK Home Fav Leading |
| 16 | `under45_3goals` | BACK U4.5 Three Goals Low xG |
| 17 | `cs_11` | BACK CS 1-1 Late |
| 18 | `cs_20` | BACK CS 2-0/0-2 Late |
| 19 | `cs_big_lead` | BACK CS Big Lead Late |
| 20 | `draw_equalizer` | BACK Draw Equalizer Late |
| 21 | `draw_22` | BACK Draw 2-2 Late |
| 22 | `lay_over45_blowout` | LAY Over 4.5 Blowout |
| 23 | `over35_early_goals` | BACK Over 3.5 Early Goals |
| 24 | `lay_draw_away_leading` | LAY Draw Away Leading |
| 25 | `lay_cs11` | LAY CS 1-1 at 0-1 |

**Archivos auxiliares** (legacy, usados en notebooks):
- `auxiliar/sd_generators.py` — generadores legacy (wrappers sobre triggers de csv_reader)
- `auxiliar/sd_filters.py` — filtros legacy para backtests en notebook
- `utils/sd_strategies.py` — `eval_sd()` evaluador legacy para notebook

---

## 8. Sistema de presets

### Presets

5 presets disponibles: `max_roi`, `max_pl`, `max_wr`, `min_dd`, `max_bets`

Los presets se computan via `optimizer_cli.py` o el notebook (`strategies_designer.ipynb`). El proceso ejecuta una busqueda en fases:

- **Fase 1**: combinaciones on/off de 7 estrategias × bankroll modes × risk filters (2,048 combos total)
- **Fase 2**: combinaciones de adjustments (dedup × maxOdds × minOdds × slippage × stability × etc.) (7,776 combos)
- **Fase 2.5**: steepest-descent para desactivar estrategias que no aportan con los adjustments de Fase 2
- **Fase 3**: rangos de minutos para momentum_xg (5 candidatos)
- **Fase 4**: porcentaje de cashout optimo (9 candidatos)

El preset solo decide `enabled: true/false` por estrategia. Los params de cada estrategia (xgMax, driftMin, etc.) vienen del `bt_optimizer.py` grid search y están en `cartera_config.json`.

Produce la configuracion optima segun la metrica del preset y la persiste en `cartera_config.json`.

### Bankroll modes

6 modos: `fixed` (2% del bankroll), `kelly`, `half_kelly`, `dd_protection`, `variable`, `anti_racha`

Default: `fixed` con `flat_stake=1`.

### Heuristico CO por criterio

- `max_roi` → 15% (solo cashouts con ganancia grande)
- `max_pl` → 20% (equilibrado)
- `max_wr` → 30% (cashout agresivo, mas % ganadas)
- `min_dd` → 10% (cashout muy temprano, reduce perdidas)
- `max_bets` → 20% (default)

---

## 9. Sistema de ajustes (adjustments)

Pipeline de ajustes realistas:

1. **Global minute filter** — filtra por rango de minutos global
2. **Drift minute filter** — minuto minimo especifico para drift (ej: drift_min_minute=30)
3. **Max odds** — excluye bets con cuota > max_odds
4. **Min odds** — excluye bets con cuota < min_odds
5. **Dedup** — elimina bets duplicadas en el mismo partido/estrategia
6. **Conflict filter** — elimina bets contradictorias (draw + over en mismo partido)
7. **Anti-contrarias** — elimina pares de bets opuestas (home + away)
8. **Stability** — requiere N capturas consecutivas donde la cuota no cambia mas de 3%
9. **Conservative odds + Slippage** — usa cuota conservadora (mas baja en ventana) + reduce P/L en slippage_pct

**Donde se aplican:**
- **Live**: `analytics.py:_apply_realistic_adjustments()` aplica los ajustes en el flujo de paper trading.
- **Backtest**: el notebook (`strategies_designer.ipynb`) aplica los ajustes equivalentes sobre los datos del backend.

Parametros en `cartera_config.json > adjustments`:
```json
{
  "enabled": true,
  "dedup": true,
  "max_odds": 7,
  "min_odds": 1.21,
  "drift_min_minute": 30,
  "slippage_pct": 3.5,
  "conflict_filter": false,
  "allow_contrarias": false,
  "stability": 3,
  "conservative_odds": false,
  "global_minute_min": null,
  "global_minute_max": null,
  "cashout_minute": null,
  "cashout_pct": 50
}
```

---

## 10. Paper Trading

### Flujo automatico (cada 60s):

```
main.py: background task auto_paper_trading()
  → analytics.py: run_paper_auto_place()
    → Leer cartera_config.json
    → Construir versions dict: {"_strategy_configs": strategies, "_min_duration": md}
    → csv_reader.detect_betting_signals(versions=versions)
    → Post-filtros en analytics.py:
      - min_odds check (min_odds >= 1.21)
      - max_odds check (max_odds <= 7)
      - risk filter (risk_level check)
      - maturity check (age >= min_dur + PAPER_REACTION_DELAY_MINS)
    → Para cada senal madura:
      → Verificar dedup: _has_existing_bet() via market key (draw/home/away/over_X.5)
      → Verificar anti-contrarias: _is_contraria()
      → Registrar en placed_bets.csv via _auto_place_signal()
      → Log via signals_audit_logger
```

### Senales endpoint (BettingSignalsView):

```
GET /analytics/signals/betting-opportunities
  → analytics.py: get_betting_signals()
    → Mismo versions dict + detect_betting_signals()
    → Mismos post-filtros (odds, risk)
    → Devuelve senales + watchlist (detect_watchlist())
    → NO coloca bets (read-only)
```

### Madurez de senal:

Una senal debe persistir durante `min_dur` capturas del scraper (cada ~30s) para ser "madura". Ademas, hay un `PAPER_REACTION_DELAY_MINS = 1` minuto adicional simulando tiempo de reaccion humano.

### Cashout y settlement (cada 60s):

```
analytics.py: run_auto_cashout()
  → bets.py: run_auto_cashout()
    → Para cada bet activa (status=active):
      → Leer datos live del partido (_enrich_with_live_data())
      → Cashout: si lay_now >= back_odds * (1 + cashout_pct/100) → ejecutar
      → Settlement: si partido finalizado → calcular won/lost basado en resultado final
```

### Signals Audit Logger:

`signals_audit_logger.py` registra en `signals_audit.log` (rotacion 50MB x 10):
- `CYCLE_START` / `CYCLE_END`: cada ciclo de polling
- `RADAR`: partido en watchlist con condiciones parciales
- `SIGNAL_ACTIVE`: senal detectada
- `SIGNAL_FILTERED`: senal descartada (con motivo)
- `BET_PLACED`: apuesta paper registrada
- `CASHOUT`: cashout automatico ejecutado
- `SETTLEMENT`: liquidacion por fin de partido

---

## 11. Sistema de cache

### Backend (csv_reader.py):

- `_analytics_cache`: dict con partidos terminados + rows preprocesados. TTL de 5 minutos (300s). Se invalida via `clear_analytics_cache()`.
- `_result_cache`: cache de resultados de `analyze_strategy_*()`. Se invalida cuando `_analytics_cache` se reconstruye.
- `_get_cached_finished_data()` (linea 950): construye cache de partidos finished. Incluye preprocessing: normalizacion halftime, limpieza outliers, outlier stats, gap analysis. Se reutiliza por todas las funciones de analisis.
- `clear_analytics_cache()`: llamado cada ciclo de paper trading (60s) y al guardar config.

Cache key de `analyze_cartera()`: incluye `min_duration` + estado `enabled` de todas las estrategias. Cambios de params (xgMax, driftMin, etc.) requieren invalidacion manual via `clear_analytics_cache()`.

### Frontend:

- `localStorage` como fallback para config (si API falla)
- Auto-refresh cada 10s (matches + system status via Dashboard.tsx polling)

---

## 12. Formato de datos CSV de partido

Cada `data/partido_*.csv` tiene **154 columnas** (definidas en `main.py:CSV_COLUMNS`, linea 278):

```
# Metadatos (8)
tab_id, timestamp_utc, evento, hora_comienzo, estado_partido, minuto,
goles_local, goles_visitante,

# Match Odds (6)
back_home, lay_home, back_draw, lay_draw, back_away, lay_away,

# Over/Under 0.5-6.5 (28: 7 lineas x 4 columnas)
back_over05, lay_over05, back_under05, lay_under05,
... (1.5, 2.5, 3.5, 4.5, 5.5) ...
back_over65, lay_over65, back_under65, lay_under65,

# Correct Score (30: 15 marcadores x back/lay)
back_rc_0_0, lay_rc_0_0,   back_rc_1_0, lay_rc_1_0,   back_rc_0_1, lay_rc_0_1,
back_rc_1_1, lay_rc_1_1,   back_rc_2_0, lay_rc_2_0,   back_rc_0_2, lay_rc_0_2,
back_rc_2_1, lay_rc_2_1,   back_rc_1_2, lay_rc_1_2,   back_rc_2_2, lay_rc_2_2,
back_rc_3_0, lay_rc_3_0,   back_rc_0_3, lay_rc_0_3,   back_rc_3_1, lay_rc_3_1,
back_rc_1_3, lay_rc_1_3,   back_rc_3_2, lay_rc_3_2,   back_rc_2_3, lay_rc_2_3,

# Estadisticas - Summary (24: 12 pares local/visitante)
xg_local, xg_visitante,
opta_points_local, opta_points_visitante,
posesion_local, posesion_visitante,
tiros_local, tiros_visitante,
tiros_puerta_local, tiros_puerta_visitante,
touches_box_local, touches_box_visitante,
corners_local, corners_visitante,
total_passes_local, total_passes_visitante,
fouls_conceded_local, fouls_conceded_visitante,
tarjetas_amarillas_local, tarjetas_amarillas_visitante,
tarjetas_rojas_local, tarjetas_rojas_visitante,
booking_points_local, booking_points_visitante,

# Estadisticas - Attacking (14: 7 pares)
big_chances_local, big_chances_visitante,
shots_off_target_local, shots_off_target_visitante,
attacks_local, attacks_visitante,
hit_woodwork_local, hit_woodwork_visitante,
blocked_shots_local, blocked_shots_visitante,
shooting_accuracy_local, shooting_accuracy_visitante,
dangerous_attacks_local, dangerous_attacks_visitante,

# Estadisticas - Defence (14: 7 pares)
tackles_local, tackles_visitante,
tackle_success_pct_local, tackle_success_pct_visitante,
duels_won_local, duels_won_visitante,
aerial_duels_won_local, aerial_duels_won_visitante,
clearance_local, clearance_visitante,
saves_local, saves_visitante,
interceptions_local, interceptions_visitante,

# Estadisticas - Distribution + Misc (26: 13 pares)
pass_success_pct_local, pass_success_pct_visitante,
crosses_local, crosses_visitante,
successful_crosses_pct_local, successful_crosses_pct_visitante,
successful_passes_opp_half_local, successful_passes_opp_half_visitante,
successful_passes_final_third_local, successful_passes_final_third_visitante,
goal_kicks_local, goal_kicks_visitante,
throw_ins_local, throw_ins_visitante,
free_kicks_local, free_kicks_visitante,
offsides_local, offsides_visitante,
substitutions_local, substitutions_visitante,
injuries_local, injuries_visitante,
time_in_dangerous_attack_pct_local, time_in_dangerous_attack_pct_visitante,
momentum_local, momentum_visitante,

# Metadata (4)
volumen_matched, url, País, Liga
```

### Preprocessing en cache:
1. `_normalize_halftime_minutes()` — cap 1T added time a 45
2. `_clean_odds_outliers()` — elimina cuotas > median*5

---

## 13. Cashout simulation

### Modos de cashout disponibles (csv_reader.py):

1. **Fijo**: cashout cuando lay >= back * (1 + cashout_lay_pct/100). Grid: 5-50%.
2. **Adaptativo**: threshold diferente antes/despues de minuto split. Grid: early 15-30% / late 5-20% / split 60-80.
3. **Gol adverso**: cashout inmediato si se produce un gol que perjudica la apuesta. Solo para apuestas de match odds (draw, home, away). Over bets: ningun gol es adverso.
4. **Trailing stop**: mantiene registro del lay minimo y cashoutea si lay sube trailing_stop_pct% desde el minimo. Grid: 5-25%.
5. **Combinaciones** de los anteriores.

### Grid search:
`optimize_cashout_cartera()` (linea 2730) prueba ~200 configuraciones. Retorna top_n rankeadas por P/L neto.

### Deteccion de corrupcion:
`_co_is_corrupted()` filtra rows con spread >50% o lay < back (suspension de mercado).

---

## 14. Supervisor y scripts de mantenimiento

### supervisor_workflow.py (190 lineas):
Orquesta 7 scripts en secuencia:
1. `start_scraper.py` — verifica/arranca scraper
2. `find_matches.py` — busca nuevos partidos en Betfair via Playwright
3. `clean_games.py` — elimina partidos terminados de games.csv
4. `check_urls.py` — elimina URLs 404
5. `generate_report.py` — genera informe de salud del sistema
6. `validate_stats.py` — compara stats capturadas vs disponibles (OBLIGATORIO)
7. `unify_data.py` — combina CSVs en unificado.csv

Timeout: 5 minutos por script. Critical steps: 1 (scraper) y 6 (validacion stats).

---

## 15. Puertos y URLs

| Servicio | Puerto | URL |
|----------|--------|-----|
| Backend FastAPI | 8000 | http://localhost:8000 |
| Frontend Vite | 5173 | http://localhost:5173 |
| Opta Stats API | — | https://betfair.cpp.statsperform.com/stats |
| Betfair videoplayer | — | https://videoplayer.betfair.es/GetPlayer.do |

---

## 16. Dependencias clave

### Backend:
- Python 3.13+
- FastAPI + Uvicorn
- Selenium + ChromeDriver + webdriver-manager
- Playwright (solo para find_matches.py)
- psutil (para scraper_status.py)
- requests (para stats_api.py)

### Frontend:
- React 18 + TypeScript
- Vite
- Tailwind CSS
- Lucide React (iconos)
- clsx + tailwind-merge (utilidades CSS)

---

## 17. Problemas conocidos

### 17.1 Momentum xG: params parcialmente hardcodeados

### 17.2 Momentum xG: params parcialmente hardcodeados

Los parametros internos de Momentum xG (sotMin, sotRatioMin, xgUnderperfMin, oddsMin, oddsMax) estan hardcodeados en el trigger. No existen en `cartera_config.json`. Solo minuteMin/minuteMax son configurables via config.

### 17.3 Odds Drift: constantes hardcodeadas en backtest

El backtest de Odds Drift tiene constantes hardcodeadas que no estan en config:
```python
DRIFT_MIN = 0.30    # = config drift.driftMin / 100 (coincide, pero no usa config)
WINDOW_MIN = 10     # no en config
MIN_MINUTE = 5      # no en config (live usa minuto >= 30 hardcodeado)
MAX_MINUTE = 80     # no en config
MIN_ODDS = 1.50     # no en config
MAX_ODDS = 30.0     # no en config
```

### 17.4 Cache key incompleto

`analyze_cartera()` usa cache key basado solo en `min_duration`. Correcto para el patron actual (filtros en notebook/CLI), pero si se movieran filtros al backend el cache key deberia ampliarse.

---

## 18. Flujos de datos principales

### 18.1 Captura de datos

```
Betfair Exchange (web)
  → Selenium Chrome drivers (main.py, 1 Chrome/partido)
    → Match Odds + Over/Under + Correct Score (CSS selectors)
    → Stats: Opta API (stats_api.py, 5 endpoints paralelos)
             ↓ fallback si falla
             Iframe scraping (extract_iframe_stats.py)
    → data/partido_<match_id>.csv (append por ciclo, 154 cols)
    → data/.heartbeat (JSON, cada 4s)
```

### 18.2 Backtest completo

```
Notebook (strategies_designer.ipynb) / optimizer_cli.py
  → GET /analytics/strategies/cartera
    → analyze_cartera() lee min_duration de config
    → Llama 7x analyze_strategy_*() sobre datos historicos
    → Devuelve superconjunto de bets con version flags
  → Notebook/CLI aplica filtros por version
  → Notebook/CLI aplica ajustes realistas
  → Notebook/CLI simula bankroll
  → Resultado: metricas + combinacion optima → persiste en cartera_config.json
```

### 18.3 Deteccion live + paper trading

```
Background task cada 60s (auto_paper_trading)
  → analytics.py: run_paper_auto_place()
    → Lee cartera_config.json → construye versions dict
    → csv_reader.detect_betting_signals(versions)
      → Lee datos de TODOS los partidos activos
      → Por cada partido, evalua 6 estrategias inline
      → Devuelve senales activas con madurez
    → Post-filtros: odds, risk, maturity
    → Auto-coloca paper bets maduras → placed_bets.csv
  → bets.py: run_auto_cashout()
    → Cashout: lay favorable → ejecutar
    → Settlement: partido terminado → calcular won/lost
```

### 18.4 Visualizacion de senales

```
BettingSignalsView (auto-refresh 10s)
  → GET /analytics/signals/betting-opportunities
    → Misma logica que run_paper_auto_place() pero read-only
    → Devuelve senales + watchlist
  → Frontend muestra cards con info detallada
  → Alerta sonora (sounds.ts) cuando hay nueva senal favorable
```

---

## 19. Reglas para modificar codigo

1. **Leer este documento** antes de cualquier cambio.
2. **No asumir** como funciona algo — verificar en el codigo fuente.
3. **Parametros de config** se leen en el backend para live, y en notebook/CLI para backtest.
4. **Verificar NULL handling** al tocar filtros — es la fuente principal de discrepancias.
5. **csv_reader.py** es el fichero mas critico y complejo. Cualquier cambio aqui debe ser quirurgico.
6. **Testar cambios** comparando output de backtest y senales live con los mismos datos.
7. **Los params hardcodeados** de Momentum xG y Odds Drift backtest son un problema conocido — no asumir que estan en config.
8. `sd_strategies.py` contiene el evaluador `eval_sd()` para uso del notebook legacy solamente.
