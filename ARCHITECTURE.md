# Arquitectura del Proyecto — Betfair Scraper + Dashboard

> **LEER ANTES DE CUALQUIER ACCION.** Este documento describe la arquitectura real y verificada del sistema completo. Cualquier cambio de codigo debe partir de la comprension de este documento.

---

## 1. Vision general

El sistema captura cuotas y estadisticas de partidos de futbol en vivo desde Betfair Exchange, las almacena en CSVs, y proporciona un dashboard web para:

1. **Monitorizar partidos en vivo** (cuotas, stats, momentum)
2. **Detectar senales de apuesta** en tiempo real (7 estrategias core + 19 SD backtest-only)
3. **Paper trading automatico** (colocacion automatica de apuestas simuladas)
4. **Analisis historico** (backtest sobre datos pasados con filtrado configurable)
5. **Optimizacion de cartera** (busqueda de la mejor combinacion de versiones y ajustes)
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
├── scripts/                   # 8 scripts de utilidad
│   ├── start_scraper.py       # Monitor de proceso, auto-restart
│   ├── find_matches.py        # Descubrimiento de partidos (Playwright)
│   ├── clean_games.py         # Eliminar partidos terminados de games.csv
│   ├── check_urls.py          # Eliminar URLs 404
│   ├── generate_report.py     # Informes de salud del sistema
│   ├── validate_stats.py      # Comparar stats capturadas vs disponibles
│   ├── unify_data.py          # Combinar CSVs en unificado.csv
│   └── strategy_explorer.py   # Grid search de estrategias (min x condicion x resultado)
│
└── dashboard/
    ├── start.bat              # Lanza backend + frontend
    ├── signals_log.csv        # Log de senales detectadas
    ├── backend/
    │   ├── main.py            # FastAPI app, routers, 5 background tasks (417 lineas)
    │   ├── api/
    │   │   ├── analytics.py   # Paper trading, senales, cartera, cashout (750 lineas)
    │   │   ├── bets.py        # CRUD apuestas colocadas (604 lineas)
    │   │   ├── config.py      # GET/PUT cartera_config.json (102 lineas)
    │   │   ├── matches.py     # Datos de partidos (133 lineas)
    │   │   ├── system.py      # Start/stop scraper, cleanup Chrome (381 lineas)
    │   │   ├── debug.py       # Debug endpoints: HTML snapshots, memory monitoring (127 lineas)
    │   │   ├── optimize.py    # Optimizacion presets Phase 1+2 (1329 lineas)
    │   │   ├── optimizer_cli.py # CLI para optimizacion paralela (691 lineas)
    │   │   └── simulate.py    # Simulador de senales: replay timeline (540 lineas)
    │   └── utils/
    │       ├── csv_reader.py      # ~5761 lineas. EL fichero critico. Helpers compartidos BT↔LIVE.
    │       ├── sd_strategies.py   # 19 SD strategies: configs + evaluator (205 lineas)
    │       ├── scraper_status.py  # Estado del scraper via psutil + log parsing (231 lineas)
    │       └── signals_audit_logger.py  # Audit log rotativo 50MB x 10 (214 lineas)
    │
    └── frontend/
        └── src/
            ├── App.tsx, main.tsx
            ├── index.css          # Tema "Charcoal Pro"
            ├── lib/
            │   ├── api.ts         # Cliente API con interfaces TypeScript (932 lineas)
            │   ├── cartera.ts     # Filtros, simulacion bankroll, optimizacion (1104 lineas)
            │   ├── trading.ts     # PressureIndex, divergencia, momentum swings (311 lineas)
            │   ├── sounds.ts      # Alerta sonora Web Audio (61 lineas)
            │   └── utils.ts       # cn(), formatTimeAgo(), formatTimeTo() (27 lineas)
            └── components/        # 19 componentes React
                ├── Dashboard.tsx          # Shell de navegacion (vistas, polling 10s)
                ├── BettingSignalsView.tsx  # Senales live + watchlist + cartera activa
                ├── PlacedBetsView.tsx      # Tracking de apuestas paper
                ├── LiveView.tsx           # Partidos en vivo (MatchCard por partido)
                ├── MatchCard.tsx          # Tarjeta de partido con stats + cuotas
                ├── DataQualityView.tsx    # Calidad de datos capturados
                ├── AnalyticsView.tsx      # Analisis de mercado
                ├── UpcomingView.tsx       # Proximos partidos
                ├── SystemStatus.tsx       # Estado del sistema + controles
                └── (10 componentes menores: StatusBadge, CaptureIndicator,
                     StatsBar, GapAnalysis, CaptureTable, OddsChart,
                     MomentumChart, MomentumSwings, PriceVsReality, SiegeMeter)

aux/                           # Archivos auxiliares de analisis (tracked en git)
├── sd_generators.py           # 19 generadores de estrategias SD (1816 lineas)
├── sd_filters.py              # Filtros realistas para SD backtests (825 lineas)
├── run_reconcile.py           # Verificacion BT↔LIVE fila a fila
├── compare_bt_live.py         # Comparacion rendimiento BT vs LIVE
└── (scripts temporales de analisis, CSVs intermedios)

strategies/                    # Trabajo del strategy-designer agent
├── sd_strategy_tracker.md     # Estado de investigacion de todas las rondas
└── (reportes de backtests, resultados por ronda)

analisis/                      # Notebooks y analisis
├── strategies_designer.ipynb  # Notebook principal: BT + presets + SD (65 celdas)
└── (portfolio analysis, audit reports)

.claude/agents/                # Definiciones de agentes Claude
├── backtest-auditor.md        # Auditor de alineamiento BT↔LIVE (5 pasos)
├── strategy-designer.md       # Disenador de nuevas estrategias (8 pasos)
├── sub-backtest-runner.md     # Sub-agente: ejecuta backtests individuales
├── sub-match-analyzer.md      # Sub-agente: analisis de partidos individuales
└── sub-strategy-meta-analyst.md # Sub-agente: meta-analisis de portfolio
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
- **5 Routers** (incluidos en este orden):
  1. `matches_router` → datos de partidos
  2. `system_router` → start/stop scraper, cleanup
  3. `analytics_router` → prefijo `/api/analytics` (senales, cartera, cashout)
  4. `bets_router` → CRUD apuestas (`/api/bets/*`)
  5. `config_router` → prefijo `/api` (GET/PUT `/config/cartera`)
- **5 background tasks** (lanzadas en `startup_event`, lineas 343-367):
  1. **`auto_refresh_matches()`** — cada 10 minutos (delay inicial 30s): ejecuta `clean_games.py` + `find_matches.py` via subprocess. Flag `_is_refreshing` previene concurrencia.
  2. **`_scheduler_watchdog()`** — reinicia `auto_refresh_matches()` si crashea.
  3. **`_scraper_watchdog()`** — cada 60s monitoriza heartbeat del scraper. Si stale >120s, ejecuta `start_scraper.py` via subprocess para reiniciar.
  4. **`auto_paper_trading()`** — cada 60s (delay inicial 90s): llama `run_paper_auto_place()` + `run_auto_cashout()`. Limpia cache analytics cada ciclo.
  5. **`_paper_trading_watchdog()`** — reinicia `auto_paper_trading()` si crashea.
- **`/api/health`** endpoint: estado comprensivo del sistema (scraper, paper trading, auto-refresh, config).

### 3.5 csv_reader.py — El fichero critico (~5761 lineas)

Este fichero contiene TODA la logica de:
1. Carga y limpieza de datos CSV
2. Analisis historico de cada estrategia (funciones `analyze_strategy_*()`)
3. Orquestacion de cartera (`analyze_cartera()`)
4. Deteccion de senales live (`detect_betting_signals()`)
5. Watchlist (condiciones parciales: `detect_watchlist()`)
6. Cashout simulation y optimizacion
7. Calidad de datos, correlaciones, gap analysis

**Funciones principales y sus lineas:**

| Funcion | Linea | Proposito |
|---------|-------|-----------|
| `_resolve_csv_path()` | 42 | Resuelve ruta a CSV de partido |
| `_to_float()` | ~50 | Conversion segura str→float |
| `_compute_synthetic_at_trigger()` | ~130 | Calcula campos sinteticos (pressure_index, xg_remaining, match_openness, momentum_gap) en el momento del trigger |
| `load_games()` | 237 | Carga games.csv + escanea data/ para CSV huerfanos |
| `_normalize_halftime_minutes()` | 404 | Corrige minutos de descanso (>45 en 1T → cap a 45) |
| `delete_match()` | 481 | Elimina de games.csv + borra CSV de datos |
| `load_all_captures()` | 526 | Todas las capturas con ~50 campos de stats |
| `load_match_detail()` | 606 | Ultimas 10 capturas + quality score + gap analysis |
| `load_momentum_data()` | 723 | Series temporales para graficos de momentum |
| `load_all_stats()` | 762 | Ultimo row con todos los STAT_COLUMNS |
| `_clean_odds_outliers()` | 816 | Elimina outliers de cuotas (>median*5 o <median/5) |
| `load_match_full()` | 853 | Stats finales + cuotas apertura/cierre + odds timeline |
| `_get_cached_finished_data()` | 950 | Cache 5 min de partidos terminados con rows preprocesados |
| `analyze_strategy_back_draw_00()` | 1747 | Backtest Back Empate |
| `analyze_strategy_xg_underperformance()` | 2026 | Backtest xG Underperf |
| `analyze_strategy_odds_drift()` | 2207 | Backtest Odds Drift |
| **`analyze_cartera()`** | **2423** | **Orquestador de backtest (llama 7 estrategias)** |
| `_co_market_cols()` | 2542 | Mapea estrategia a columnas back/lay para cashout |
| `_simulate_config()` | 2634 | Bucle interno de simulacion cashout |
| `optimize_cashout_cartera()` | 2730 | Grid search sobre modos de cashout |
| `simulate_cashout_cartera()` | 2818 | Simulacion cashout con config especifica |
| **`detect_betting_signals()`** | **3253** | **Deteccion live de senales (6 estrategias)** |
| `detect_watchlist()` | 4116 | Partidos cerca de trigger (condiciones parciales) |
| `analyze_strategy_goal_clustering()` | 4335 | Backtest Goal Clustering |
| `analyze_strategy_pressure_cooker()` | 4528 | Backtest Pressure Cooker |
| `analyze_strategy_tarde_asia()` | 4718 | Backtest Tarde Asia (inactiva) |
| `analyze_strategy_momentum_xg()` | 4924 | Backtest Momentum xG |

### 3.6 Frontend React (`dashboard/frontend/src/`)

- **Stack**: React 18 + TypeScript + Vite + Tailwind CSS
- **Puerto dev**: 5173 (proxy Vite redirige `/api` → `localhost:8000`)
- **Tema**: "Charcoal Pro" (dark theme definido en index.css)
- **Dashboard.tsx**: 6 vistas (signals, bets, live, upcoming, quality, analytics). Polling de matches + system status cada 10 segundos.
- **Librerias clave**:
  - `api.ts`: objeto `api` con metodos tipados para todos los endpoints. Interfaces TypeScript completas (Match, CarteraBet, BettingSignal, PlacedBet, CarteraConfig, ExplorerResult, etc.)
  - `cartera.ts`: filtros por estrategia, simulacion de bankroll (6 modos), optimizacion de presets (57,600 combos fase 1 + 2,592 combos fase 2), ajustes realistas
  - `trading.ts`: PressureIndex (rolling window 10 min), divergencia precio-realidad, momentum swings
  - `sounds.ts`: alerta bell via Web Audio API (4 armonicos, decay exponencial)

---

## 4. PATRON CRITICO: Filtrado de doble capa (Backtest)

> **ESTO ES LO MAS IMPORTANTE DE ENTENDER.**

El analisis historico (cartera/backtest) usa un patron de **doble capa**:

### Capa 1: Backend genera SUPERCONJUNTO

```
analyze_cartera()  →  analyze_strategy_back_draw_00(min_dur=N)
                  →  analyze_strategy_xg_underperformance(min_dur=N)
                  →  analyze_strategy_odds_drift(min_dur=N)
                  →  analyze_strategy_goal_clustering(min_dur=N)
                  →  analyze_strategy_pressure_cooker(min_dur=N)
                  →  analyze_strategy_tarde_asia(min_dur=N)
                  →  analyze_strategy_momentum_xg(version, min_dur=N)
```

Cada `analyze_strategy_*()` genera TODAS las apuestas posibles que cumplen condiciones basicas (marcador, minuto minimo, datos disponibles). Cada bet incluye **version flags** (passes_v2, passes_v3, etc.) que el frontend usa para filtrar.

El unico parametro que `analyze_cartera()` pasa a las estrategias es `min_dur` (duracion minima de la senal), leido de `cartera_config.json > min_duration`.

### Capa 2: Frontend aplica filtros de config

Cuando el frontend recibe las bets del backend, aplica los filtros de `cartera_config.json`:

```typescript
// En StrategiesView.tsx, pipeline de filtrado:
filterDrawBets(bets, drawParams)       // xgMax, possMax, shotsMax, minuteMin, minuteMax
filterXGBets(bets, xgParams)           // sotMin, xgExcessMin, minuteMin, minuteMax
filterDriftBets(bets, driftParams)     // goalDiffMin, driftMin, oddsMax, minuteMin, minuteMax, momGapMin
filterClusteringBets(bets, clusterParams) // sotMin, minuteMin, minuteMax, xgRemMin
filterPressureBets(bets, version)      // version-based toggle
filterMomentumXGBets(bets, version)    // v1/v2 toggle
→ applyRealisticAdjustments()          // dedup, maxOdds, minOdds, slippage, stability, conflictos
→ filterByRisk()                       // risk_filter preset
```

Estas funciones estan en `cartera.ts`.

### Flujo completo (Backtest):

```
cartera_config.json
       ↓ (frontend lee al cargar)
StrategiesView.tsx: configToState()
       ↓
API call: GET /analytics/strategies/cartera
       ↓
Backend: analyze_cartera() → genera superconjunto
       ↓ (response con TODAS las bets + version flags)
Frontend: filter*Bets() → aplica params de config
       ↓
Frontend: applyRealisticAdjustments() → dedup, odds, slippage
       ↓
Frontend: simulateCartera() → simulacion de bankroll
       ↓
Resultado: tabla + grafico + metricas
```

### Guardado de config:

```
Usuario cambia params en UI
       ↓
buildConfig() en StrategiesView.tsx
       ↓
PUT /config/cartera → escribe cartera_config.json
       ↓
Frontend re-aplica filtros → resultado actualizado
```

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

### El dict `versions` (analytics.py lineas 137-172 / 516-553):

Se construye leyendo TODOS los params de `cartera_config.json > strategies`:

```python
versions = {
    "draw":       "v2r",           # version de estrategia
    "xg":         "base",
    "drift":      "v1",
    "clustering": "v2",
    "pressure":   "v1",
    "momentum":   "v1",
    "tarde_asia": "v1" | "off",
    # min_duration por estrategia
    "draw_min_dur":          "2",
    "xg_min_dur":            "3",
    "drift_min_dur":         "2",
    "clustering_min_dur":    "4",
    "pressure_min_dur":      "2",
    # params de filtro por estrategia (todos como strings)
    "drift_threshold":       "30",      # strategies.drift.driftMin
    "drift_odds_max":        "999",     # strategies.drift.oddsMax
    "drift_goal_diff_min":   "0",       # strategies.drift.goalDiffMin
    "drift_minute_min":      "0",       # strategies.drift.minuteMin
    "drift_mom_gap_min":     "0",       # strategies.drift.momGapMin
    "clustering_minute_max": "60",      # strategies.clustering.minuteMax (default: 90)
    "clustering_xg_rem_min": "0",       # strategies.clustering.xgRemMin
    "clustering_sot_min":    "3",       # strategies.clustering.sotMin
    "xg_minute_max":         "70",      # strategies.xg.minuteMax
    "xg_sot_min":            "0",       # strategies.xg.sotMin
    "xg_xg_excess_min":      "0.5",    # strategies.xg.xgExcessMin
    "draw_xg_max":           "0.6",     # strategies.draw.xgMax
    "draw_poss_max":         "25",      # strategies.draw.possMax
    "draw_shots_max":        "20",      # strategies.draw.shotsMax
    "draw_minute_min":       "30",      # strategies.draw.minuteMin
    "draw_minute_max":       "90",      # strategies.draw.minuteMax
    "xg_minute_min":         "0",       # strategies.xg.minuteMin
    "clustering_minute_min": "0",       # strategies.clustering.minuteMin
    "pressure_minute_min":   "0",       # strategies.pressure.minuteMin
    "pressure_minute_max":   "90",      # strategies.pressure.minuteMax
    "momentum_minute_min":   "0",       # strategies.momentum_xg.minuteMin
    "momentum_minute_max":   "90",      # strategies.momentum_xg.minuteMax
}
```

`detect_betting_signals()` extrae TODOS estos params al inicio (lineas 3275-3296 aprox) y los usa inline para filtrar cada senal. **No hay segunda capa de filtrado.**

---

## 6. DIFERENCIA CRITICA: Backtest vs Live

| Aspecto | Backtest (Cartera) | Live (Senales) |
|---------|-------------------|----------------|
| **Donde se filtran los params de config** | Frontend (`cartera.ts`) | Backend (`csv_reader.py:detect_betting_signals()`) |
| **Capas de filtrado** | 2 (backend superconjunto + frontend filtros) | 1 (todo inline en backend) |
| **Quien lee cartera_config.json** | Frontend (via GET /config/cartera) | Backend (`analytics.py` cada 60s) |
| **Datos null** | Frontend DEJA PASAR bets con datos null | Live REQUIERE datos no-null para generar senal |
| **Versiones de estrategia** | Backend genera ALL bets con version flags; frontend filtra con la version activa | Backend filtra con la version activa directamente |
| **Thresholds hardcodeados** | Cada `analyze_strategy_*()` tiene sus propias constantes internas | `detect_betting_signals()` lee params de `versions` dict |

### Nota sobre datos NULL (descartado como problema)

Ambos sistemas (backtest y live) parten del mismo CSV. Si un stat es null en una fila del CSV historico, eso refleja que el scraper tampoco lo tenia disponible en ese momento en vivo. No hay inflacion sistematica del backtest por nulls.

---

## 7. Estrategias

### 7.0 Quality Gates (aplicados a TODAS las estrategias)

Tanto las estrategias core como las SD deben pasar 3 quality gates:

1. **N >= G_MIN_BETS**: minimo de apuestas (dinamico: `max(15, n_partidos // 25)`, tipicamente ~33)
2. **ROI >= G_MIN_ROI** (10%): retorno minimo sobre inversion
3. **IC95_lower >= IC95_MIN_LOW** (40%): limite inferior del intervalo de confianza Wilson al 95%

Si una estrategia no pasa alguno de estos gates, se desactiva automaticamente en la combinacion optima.

### 7.1 Back Empate (`back_draw_00`)

- **Trigger**: marcador 0-0, minuto >= 30
- **Mercado**: Back al empate (Match Odds)
- **Versiones**: v1 (sin filtro extra), v15 (xG+poss), v2 (xG<0.5+poss<20+shots<8), v2r (xG<0.6+poss<20+shots<8, default), v3 (+xG dominance asimetrica), v4 (+Opta gap <= 10)
- **Config params**: `xgMax` (0.6), `possMax` (25), `shotsMax` (20), `xgDomAsym` (false, activa filtro v3), `minuteMin` (30), `minuteMax` (90)
- **Sentinel OFF**: `xgMax >= 1.0` = filtro xG off, `possMax >= 100` = poss off, `shotsMax >= 20` = shots off
- **Backtest** (linea 1747): genera bets con version flags (passes_v15, passes_v2r, passes_v2, passes_v3). Usa thresholds hardcodeados: v15=xg<0.6+poss<25, v2r=xg<0.6+poss<20+shots<8, v2=xg<0.5+poss<20+shots<8.
- **Live** (linea 3521): usa params del `versions` dict con logica sentinel idéntica.

### 7.2 xG Underperformance (`xg_underperformance`)

- **Trigger**: equipo perdiendo con xG excess >= 0.5 (mas xG que goles), min >= 15
- **Mercado**: Back Over (linea de Over mas cercana a goles actuales + 0.5)
- **Versiones**: base (config params), v2 (SoT >= max(2, sotMin)), v3 (v2 + minuteMax filtro)
- **Config params**: `xgExcessMin` (0.5), `sotMin` (2), `minuteMin` (0), `minuteMax` (70)
- **Backtest** (linea 2026): hardcodea xg_excess threshold 0.5, min 15, SoT v2=2, v3=min<70.
- **Live** (linea 3611): usa params del `versions` dict.

### 7.3 Odds Drift Contrarian (`odds_drift`)

- **Trigger**: equipo ganando cuyas cuotas suben >= drift_min% en 10 min (mercado pierde confianza → apostar contrarian)
- **Mercado**: Back al equipo ganando cuyas cuotas driftan
- **Versiones**: v1 (base), v2 (goalDiff>=2), v3 (drift>=100%), v4 (min>45+odds<=5), v5 (odds<=5), v6 (v5+momGap>0)
- **Config params**: `driftMin` (30), `oddsMax` (999), `goalDiffMin` (0), `minuteMin` (0), `minuteMax` (90), `momGapMin` (0)
- **Backtest** (linea 2207): CONSTANTES HARDCODEADAS propias: `DRIFT_MIN=0.30, WINDOW_MIN=10, MIN_MINUTE=5, MAX_MINUTE=80, MIN_ODDS=1.50, MAX_ODDS=30.0`. No usa config.
- **Live** (linea 3694): HARDCODEA `minuto >= 30` como gate inicial (no usa `_drift_minute_min` para este check). Luego aplica params del `versions` dict para version-specific filters.

### 7.4 Goal Clustering (`goal_clustering`)

- **Trigger**: gol reciente (ultimas 3 capturas) + SoT max >= sotMin + minuto 15-80
- **Mercado**: Back Over (total_actual + 0.5)
- **Versiones**: v2 (base), v3 (minuteMax=60), v4 (xg_rem)
- **Config params**: `sotMin` (3), `minuteMin` (0), `minuteMax` (60), `xgRemMin` (0)
- **Restriccion**: una sola bet por partido.
- **Backtest** (linea 4335): hardcodea min 15-80, SoT>=3.
- **Live** (linea 3817): usa `max(15, _clustering_min_min)` como minimo, aplica minuteMax del config.

### 7.5 Pressure Cooker (`pressure_cooker`)

- **Trigger**: empate con goles (1-1+) en minutos 65-75
- **Mercado**: Back Over (total_actual + 0.5)
- **Versiones**: v1 (base), v2 (relaxed)
- **Config params**: `minuteMin` (0), `minuteMax` (90)
- **Logica**: `max(65, minuteMin) <= minuto <= min(75, minuteMax)` (siempre acota a 65-75 como limites duros)
- **Score confirmation**: requiere 3+ capturas consecutivas con mismo score para confirmar que no es un cambio reciente.

### 7.6 Momentum xG (`momentum_xg`)

- **Trigger**: equipo dominante en SoT (ratio >= sotRatioMin) + xG underperformance >= xgUnderperfMin + rango de minutos + rango de cuotas
- **Mercado**: Back al equipo dominante (home o away)
- **Versiones**: v1 (conservador), v2 (agresivo)
- **Config params en cartera_config.json**: solo `version` ("v1"/"v2"), `minuteMin`, `minuteMax`
- **HARDCODEADO en AMBOS sistemas** (ni en config ni en versions dict):
  - v1: `sotMin=1, sotRatioMin=1.1, xgUnderperfMin=0.15, minMinute=10, maxMinute=80, oddsMin=1.4, oddsMax=6.0`
  - v2: `sotMin=1, sotRatioMin=1.05, xgUnderperfMin=0.1, minMinute=5, maxMinute=85, oddsMin=1.3, oddsMax=8.0`
- **Backtest** (linea 4924): `mom_cfg` dict hardcodeado por version.
- **Live** (linea 3973): `mom_cfg` dict hardcodeado identico. Minutos override: usa `max(mom_cfg["min_m"], _momentum_minute_min)` y `min(mom_cfg["max_m"], _momentum_minute_max)`.

### 7.7 Tarde Asia (`tarde_asia`) — INACTIVA

- **Trigger**: partidos de ligas objetivo (Bundesliga, Ligue, Eredivisie, J-League, K-League) en primeros 15 minutos
- **Mercado**: Back Over 2.5
- **Deteccion de liga**: por URL keywords primero, luego fallback por nombres de equipos (listas hardcodeadas de equipos por pais)
- Solo tracking en backtest. Config: `enabled: true` pero `tarde_asia: "off"` en versions dict.
- No genera senales live.

### 7.8 Estrategias SD (Strategy Designer) — 19 estrategias, SOLO BACKTEST

Las estrategias SD fueron descubiertas automaticamente por el agente strategy-designer sobre los datos historicos (~800+ partidos). Estan definidas en:

- **`aux/sd_generators.py`** (1816 lineas): 19 funciones generadoras que iteran filas de CSV y producen bets
- **`aux/sd_filters.py`** (825 lineas): filtros realistas (odds, dedup, slippage, stability)
- **`betfair_scraper/dashboard/backend/utils/sd_strategies.py`** (205 lineas): `SD_APPROVED_CONFIGS` (19 configs) + `eval_sd()` evaluador

**Las 19 estrategias SD aprobadas:**

| # | Clave | Descripcion |
|---|-------|-------------|
| 1 | `sd_over25_2goal` | BACK O2.5 from 2-Goal Lead |
| 2 | `sd_under35_late` | BACK U3.5 Late |
| 3 | `sd_lay_over45_v3` | LAY O4.5 V3 Tight |
| 4 | `sd_draw_xg_conv` | BACK Draw xG Convergence |
| 5 | `sd_poss_extreme` | BACK O0.5 Poss Extreme |
| 6 | `sd_longshot` | BACK Longshot |
| 7 | `sd_cs_00` | BACK CS 0-0 |
| 8 | `sd_over25_2goals` | BACK O2.5 from Two Goals |
| 9 | `sd_cs_close` | BACK CS 2-1/1-2 |
| 10 | `sd_cs_one_goal` | BACK CS 1-0/0-1 |
| 11 | `sd_draw_11` | BACK Draw 1-1 |
| 12 | `sd_ud_leading` | BACK UD Leading |
| 13 | `sd_under35_3goals` | BACK U3.5 Three-Goal Lid |
| 14 | `sd_away_fav_leading` | BACK Away Fav Leading |
| 15 | `sd_home_fav_leading` | BACK Home Fav Leading |
| 16 | `sd_under45_3goals` | BACK U4.5 Three Goals Low xG |
| 17 | `sd_cs_11` | BACK CS 1-1 Late |
| 18 | `sd_cs_20` | BACK CS 2-0/0-2 Late |
| 19 | `sd_cs_big_lead` | BACK CS Big Lead Late |

**Limitaciones actuales:**
- **Sin deteccion live**: no hay codigo en `detect_betting_signals()` para SD. Solo funcionan en backtest via el notebook.
- **Evaluacion**: el notebook (`strategies_designer.ipynb`) ejecuta los generadores sobre datos historicos y aplica los mismos quality gates + ajustes realistas que las core.
- **Presets**: las SD se incluyen en `_STRATEGY_PARAMS` (celda notebook) y en `_build_preset_config()` (`optimizer_cli.py`) para persistir en `cartera_config.json`.

---

## 8. Sistema de versiones y presets

### Version-to-params adapters (cartera.ts)

Cada estrategia tiene una funcion `*VersionToParams()` que convierte un string de version en un objeto de parametros de filtro. Se usan en la optimizacion para probar combinaciones:

```typescript
drawVersionToParams("v2r") → { xgMax: 0.5, possMax: 20, shotsMax: 8, minuteMin: 30, minuteMax: 90 }
drawVersionToParams("v1")  → { xgMax: 1.0, possMax: 100, shotsMax: 20, minuteMin: 30, minuteMax: 90 }
// xgMax=1.0 → sentinel OFF (no filtra por xG)
```

### Presets

5 presets disponibles: `max_roi`, `max_pl`, `max_wr`, `min_dd`, `max_bets`

Cada preset ejecuta `findBestCombo()`:
- Fase 1: hasta 57,600 combinaciones (versiones × bankroll modes × risk filters)
- Fase 2: hasta 2,592 combinaciones de adjustments (dedup × maxOdds × minOdds × slippage × stability × etc.)
- Produce la configuracion optima segun la metrica del preset

### Bankroll modes

6 modos: `fixed` (2% del bankroll), `kelly`, `half_kelly`, `dd_protection`, `variable`, `anti_racha`

Implementados en `simulateCartera()` en `cartera.ts`. Default: `fixed` con `flat_stake=1`.

---

## 9. Sistema de ajustes (adjustments)

Pipeline en `applyRealisticAdjustments()` (cartera.ts):

1. **Global minute filter** — filtra por rango de minutos global
2. **Drift minute filter** — minuto minimo especifico para drift (ej: drift_min_minute=30)
3. **Max odds** — excluye bets con cuota > max_odds
4. **Min odds** — excluye bets con cuota < min_odds
5. **Dedup** — elimina bets duplicadas en el mismo partido/estrategia
6. **Conflict filter** — elimina bets contradictorias (draw + over en mismo partido)
7. **Anti-contrarias** — elimina pares de bets opuestas (home + away)
8. **Stability** — requiere N capturas consecutivas donde la cuota no cambia mas de 3%
9. **Conservative odds + Slippage** — usa cuota conservadora (mas baja en ventana) + reduce P/L en slippage_pct

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
    → Construir versions dict
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
    → Misma logica de versions dict + detect_betting_signals()
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

Cache key de `analyze_cartera()`:
```python
cache_key = f"cartera_{json.dumps(md, sort_keys=True)}"
```
Solo incluye `min_duration` values. **No incluye** params de estrategia (xgMax, etc.) porque esos se filtran en frontend. Esto es correcto para el patron de doble capa actual.

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

### strategy_explorer.py:
Grid search independiente sobre combinaciones minuto × condicion × resultado. Llamado via `/api/explorer/run`. Resultados cacheados en JSON.

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

### 17.1 SD strategies: sin deteccion live

Las 19 estrategias SD solo funcionan en backtest (notebook). No hay codigo en `detect_betting_signals()` para detectar senales SD en tiempo real. Implementar esto requiere anadir generadores SD al flujo live de `csv_reader.py`.

### 17.2 Momentum xG: params hardcodeados

Los parametros internos de Momentum xG (sotMin, sotRatioMin, xgUnderperfMin, oddsMin, oddsMax) estan hardcodeados tanto en el backtest como en el live. No existen en `cartera_config.json` ni en el dict `versions`. Cambiar la version v1/v2 cambia TODOS los params de golpe — no se pueden ajustar individualmente.

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

`analyze_cartera()` usa cache key basado solo en `min_duration`. Correcto para el patron actual (filtros en frontend), pero si se movieran filtros al backend el cache key deberia ampliarse.

### 17.5 Drift minuteMax: muerto en live

`cartera_config.json` tiene `strategies.drift.minuteMax` y el frontend lo usa para filtrar en backtest (`cartera.ts:filterDriftBets`). Pero `analytics.py` **NO pasa** `drift_minute_max` al dict `versions`, y `detect_betting_signals()` **NO lo extrae**. Resultado: cambiar `drift.minuteMax` en config solo afecta al backtest, no al live.

### 17.6 Divergencia backtest/live en Odds Drift minute gate

- **Backtest**: `MIN_MINUTE = 5` (hardcoded), acepta senales desde minuto 5.
- **Live**: `minuto >= 30` (hardcoded en linea ~3694), rechaza senales antes de minuto 30.
- Resultado: el backtest incluye bets entre minutos 5-29 que el live nunca generaria.

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
Usuario abre StrategiesView
  → GET /config/cartera → cartera_config.json
  → GET /analytics/strategies/cartera
    → analyze_cartera() lee min_duration de config
    → Llama 7x analyze_strategy_*() sobre datos historicos
    → Devuelve superconjunto de bets con version flags
  → Frontend aplica filtros de config (cartera.ts:filter*Bets)
  → Frontend aplica ajustes (applyRealisticAdjustments)
  → Frontend simula bankroll (simulateCartera)
  → Muestra tabla + grafico P/L + metricas
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
3. **Recordar la doble capa**: backtest filtra en frontend, live filtra en backend.
4. **Parametros de config** afectan AMBOS sistemas pero por caminos distintos.
5. **No mover logica de frontend a backend** (ni viceversa) sin entender las consecuencias en cache, rendimiento y consistencia.
6. **Verificar NULL handling** al tocar filtros — es la fuente principal de discrepancias.
7. **csv_reader.py** es el fichero mas critico y complejo. Cualquier cambio aqui debe ser quirurgico.
8. **Testar cambios** comparando output de backtest y senales live con los mismos datos.
9. **No tocar la cache key** de analyze_cartera() sin entender que los filtros se aplican en frontend.
10. **Los params hardcodeados** de Momentum xG y Odds Drift backtest son un problema conocido — no asumir que estan en config.
11. **SD strategies** son backtest-only. Sus configs estan en `sd_strategies.py` y se integran en presets via `optimizer_cli.py`.
