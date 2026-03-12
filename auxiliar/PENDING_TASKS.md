# Pendientes técnicos — Furbo Betfair System

Documento generado el 2026-03-12. Contiene todo el contexto descubierto durante el desarrollo para
que otro LLM pueda implementar los cambios sin ambigüedad. Al terminar, los cambios serán revisados
por Claude Code.

---

## Contexto del sistema (leer antes de cualquier cambio)

### Arquitectura general

```
scripts/bt_optimizer.py         → CLI pipeline BT (phases 0-5)
betfair_scraper/
  cartera_config.json           → ÚNICA fuente de verdad de parámetros
  dashboard/backend/
    utils/csv_reader.py         → ~6200 líneas. TODA la lógica BT + LIVE
    api/optimizer_cli.py        → Portfolio optimizer CLI (~691 líneas)
    api/optimize.py             → Helpers compartidos + filtros (~1329 líneas)
    api/analytics.py            → Paper trading, señales live (~750 líneas)
```

### 26 estrategias independientes

Cada estrategia tiene:
- Un trigger `_detect_<name>_trigger(rows, curr_idx, cfg)` en `csv_reader.py`
- Un entry en `_STRATEGY_REGISTRY` (lista de tuplas en `csv_reader.py`)
- Config en `cartera_config.json` bajo `strategies.<key>`
- BT via `analyze_cartera()` → `_analyze_strategy_simple()`
- LIVE via `detect_betting_signals()`

Las 26 estrategias en `_STRATEGY_REGISTRY` (38 entradas totales contando versiones):

**Estrategias "planas" (1 entrada = 1 estrategia):**
`over25_2goal`, `under35_late`, `longshot`, `cs_close`, `cs_one_goal`,
`ud_leading`, `home_fav_leading`, `cs_20`, `cs_big_lead`, `lay_over45_v3`,
`draw_xg_conv`, `poss_extreme`, `cs_00`, `over25_2goals`, `draw_11`,
`under35_3goals`, `away_fav_leading`, `under45_3goals`, `cs_11`,
`pressure_cooker`, `goal_clustering`, `tarde_asia`

**Estrategias "versionadas" (familia → versiones en registry):**
- `back_draw_00` → `back_draw_00_v1`, `v15`, `v2`, `v2r`, `v3`, `v4`
- `xg_underperformance` → `xg_underperformance_base`, `v2`, `v3`
- `odds_drift` → `odds_drift_v1`, `v2`, `v3`, `v4`, `v5`, `v6`
- `momentum_xg` → `momentum_xg_v1`, `v2`

### Config actual de cartera_config.json (2026-03-12)

24 estrategias, 18 enabled con params del grid search individual:

```
draw:              enabled=False (no pasa quality gates)
xg:                enabled=True,  version=base, xgExcessMin=0.6, sotMin=0, minuteMin=10, minuteMax=90
drift:             enabled=True,  version=v1,   driftMin=15, oddsMax=999, goalDiffMin=0, minuteMin=0, minuteMax=90
clustering:        enabled=True,  sotMin=3, minuteMin=0, minuteMax=60, xgRemMin=0.0
pressure:          enabled=True,  minuteMin=0, minuteMax=90, xg_sum_min=0.5
tarde_asia:        enabled=False
momentum_xg:       enabled=False, version=off
over25_2goal:      enabled=True,  minuteMin=45, minuteMax=75, goalDiffMin=2, sot_total_min=3, odds_min=1.6
under35_late:      enabled=True,  minuteMin=65, minuteMax=75, xgMax=2.5, goals_min=3, goals_max=3
longshot:          enabled=True,  minuteMin=70, minuteMax=86, odds_min=1.5, odds_max=10.0
cs_close:          enabled=False
cs_one_goal:       enabled=True,  minuteMin=68, minuteMax=88
ud_leading:        enabled=True,  minuteMin=58, minuteMax=85, ud_min_pre_odds=1.3, max_lead=1
home_fav_leading:  enabled=True,  minuteMin=60, minuteMax=83, max_lead=1, fav_max=2.5
cs_20:             enabled=False
cs_big_lead:       enabled=False
goal_clustering:   enabled=True,  sotMin=0, minuteMin=20, minuteMax=70, xgRemMin=0.0
pressure_cooker:   enabled=True,  minuteMin=55, minuteMax=75, score_confirm=1
lay_over45_v3:     enabled=True,  minuteMin=50, minuteMax=70, goals_max=1, odds_max=20.0
poss_extreme:      enabled=True,  minuteMin=35, minuteMax=50, poss_min=60
draw_11:           enabled=True,  minuteMin=70, minuteMax=90, odds_min=1.0
under35_3goals:    enabled=True,  minuteMin=65, minuteMax=80, xgMax=2.5
away_fav_leading:  enabled=True,  minuteMin=68, minuteMax=85, max_lead=1, fav_max=2.0
under45_3goals:    enabled=True,  minuteMin=60, minuteMax=78, xgMax=2.5
```

**NOTA:** `draw_xg_conv`, `cs_00`, `over25_2goals`, `cs_11` — tienen trigger y BT pero NO
están en `cartera_config.json` aún. El portfolio optimizer los evalúa igualmente porque
los lee de `analyze_cartera()`.

### Presets generados (data/presets/)

```
preset_max_roi_config.json   → N=32, WR=78.1%, IC=[61.2-89%], ROI=142%
preset_max_pl_config.json    → N=32, WR=78.1%, IC=[61.2-89%], ROI=142%
preset_max_wr_config.json    → N=32, WR=78.1%, IC=[61.2-89%], ROI=12.7% (optimiza WR)
preset_min_dd_config.json    → N=32, WR=78.1%, IC=[61.2-89%], ROI=142%
```

Todos tienen solo 13 estrategias (los 7 originales + 6 SD obsoletas).

---

## TAREA 1 — `_build_preset_config()` no incluye las estrategias nuevas

### Prioridad: ALTA

### Problema

`_build_preset_config()` en `optimizer_cli.py:201-370` construye el `preset_{criterion}_config.json`.
Solo escribe 13 estrategias hardcodeadas:
- Las 7 originales: `draw, xg, drift, clustering, pressure, tarde_asia, momentum_xg`
- Las 6 SD obsoletas: `lay_over15, lay_draw_asym, lay_over25_def, back_sot_dom, back_over15_early, lay_false_fav`

**No incluye las 11+ estrategias nuevas** (`goal_clustering`, `pressure_cooker`, `over25_2goal`,
`under35_late`, `longshot`, etc.) que son las que actualmente generan la mayoría de los bets.

Esto afecta a:
1. El **endpoint FastAPI** `POST /api/analytics/strategies/cartera/optimize` — que llama a
   `optimizer_cli.run()` → `_build_preset_config()` y devuelve el preset al frontend
2. El archivo `preset_{criterion}_config.json` que queda incompleto

**NOTA:** `scripts/bt_optimizer.py:phase4_apply()` YA ESTÁ ARREGLADO (2026-03-12) con merge
inteligente. Solo el preset config file generado por `_build_preset_config()` está incompleto.

### Causa raíz

`_build_preset_config()` construye el `strategies` dict explícitamente hardcodeando cada estrategia.
Nunca leyó el `cartera_config.json` completo para preservar las estrategias no-conocidas.

### Solución propuesta

**Opción A (recomendada) — Merge con base config:**

En `_build_preset_config()`, después de construir el `strategies` dict actual (línea 265-347),
hacer un merge con las estrategias del `cartera_config.json` que no estén cubiertas:

```python
# Al final del return, antes de cerrar el dict:
# Merge: preservar todas las estrategias del config actual
# que _build_preset_config no gestiona explícitamente
_known_keys = {
    "draw", "xg", "drift", "clustering", "pressure", "tarde_asia", "momentum_xg",
    "lay_over15", "lay_draw_asym", "lay_over25_def", "back_sot_dom",
    "back_over15_early", "lay_false_fav",
}
_base_strategies = base_cfg.get("strategies", {})
_extra = {k: v for k, v in _base_strategies.items() if k not in _known_keys}
# El dict de strategies retornado + _extra
```

Y en el `return`, cambiar:
```python
return {
    "strategies": {
        **{las 13 hardcodeadas actuales},
        **_extra,   # <-- añadir esto
    },
    ...
}
```

**Opción B — Simplificar `_build_preset_config` para que use merge completo:**

Igual que la fix que ya se hizo en `phase4_apply`:
1. Leer todo el `base_cfg` (ya lo hace en líneas 241-246)
2. Para las 13 estrategias conocidas, aplicar los params del combo
3. Para el resto, preservarlas tal cual del `base_cfg`

### Archivos a modificar

- `betfair_scraper/dashboard/backend/api/optimizer_cli.py`
  - Función `_build_preset_config()` líneas 201-370
  - Específicamente el `return` dict en línea 265

### Verificación

```python
import json, sys
sys.path.insert(0, 'betfair_scraper/dashboard/backend')
from api import optimizer_cli

result = optimizer_cli.run("max_roi", bankroll_init=1000.0, n_workers=4)
cfg_path = result.get("config_path")
with open(cfg_path) as f:
    cfg = json.load(f)
strats = cfg.get("strategies", {})
print("Strategy count:", len(strats))
# Debe ser >= 24 (no 13)
assert "goal_clustering" in strats, "goal_clustering debe estar en el preset"
assert "under35_3goals" in strats, "under35_3goals debe estar en el preset"
assert "poss_extreme" in strats, "poss_extreme debe estar en el preset"
print("OK — todas las estrategias presentes")
```

### Checklist

- [ ] Modificar `_build_preset_config()` para incluir estrategias del `base_cfg` no-gestionadas
- [ ] Verificar que el preset resultante tiene ≥24 estrategias
- [ ] Verificar que las estrategias nuevas preservan sus params optimizados
- [ ] Verificar que las estrategias desactivadas por el optimizer tienen `enabled=False`
- [ ] Confirmar que el endpoint FastAPI devuelve el config completo (si se puede testear)

---

## TAREA 2 — Portfolio optimizer excluye xg_underperformance y odds_drift

### Prioridad: MEDIA

### Contexto

El portfolio optimizer (`optimizer_cli.run()`) evalúa todas las combinaciones posibles de
estrategias para encontrar el mejor portfolio. Actualmente concluye que el mejor portfolio
NO incluye `xg_underperformance` ni `odds_drift`, y las auto-desactiva.

Esto se puede observar en los logs de fase 3:
```
Auto-disable (0 bets): draw, xg, drift, tardeAsia, momentumXG
```

**El auto-disable es comportamiento correcto del optimizador** — el portfolio con esas
estrategias excluidas obtiene mejor score. El mensaje "(0 bets)" es técnicamente un log
engañoso (hay 52 xg-bets y 51 drift-bets), pero el resultado es válido.

Sin embargo, `xg_underperformance` y `odds_drift` SÍ pasan quality gates individuales:
- `xg_underperformance_base`: N=70, WR=72.9%, ROI=19.4%, IC95=[61.5-81.9%]
- `odds_drift_v1`: N=51, WR=68.6%, ROI=56.9%, IC95=[55.0-79.7%]

### El problema real

El portfolio optimizer evalúa las estrategias "versionadas" (xg, drift) con sus filtros en
`optimize.py` (`_filter_xg`, `_filter_drift`), pero las estrategias "planas" nuevas
(goal_clustering, ud_leading, etc.) se evalúan directamente por `strategy`. La función
`_assign_bets_from_combo()` en `optimizer_cli.py` gestiona cómo se combinan.

El optimizer podría estar excluyendo xg/drift porque sus bets solapan con otras estrategias
(por ejemplo, conflict_filter) o porque el criterio de portfolio (WR, ROI, min_dd) mejora
sin ellas.

### Investigación necesaria (antes de decidir si es un bug)

1. **Verificar el auto-disable log**: El log dice "0 bets" pero los bets existen. Investigar
   en qué punto del código se emite ese mensaje cuando los filtros SÍ retornan bets.

   En `optimizer_cli.py:487-513` (`_auto_disable_empty_strategies`):
   ```python
   n = len(fn(bets, ver))
   if n == 0:
       combo[key] = "off"
       disabled.append(key)
   ```

   Si el log dice "0 bets" para xg pero `_filter_xg(bets, 'base')` retorna 52... posible
   explicación: el `best_combo` de phase 1 tiene `xg="off"` como mejor versión, y la
   función SALTA las estrategias con `ver=="off"`. Pero entonces NO aparecerían en
   `disabled`. Contradicción. Requiere debug.

2. **Si el auto-disable es por versión no-reconocida**: Verificar que `best_combo["xg"]`
   sea uno de los valores en `XG_OPTS = ["base", "v2", "v3", "off"]`.

3. **Si es comportamiento correcto del optimizer**: No hace falta arreglar nada. Las
   estrategias siguen activas en `cartera_config.json` (habilitadas individualmente),
   solo el preset-portfolio las excluye.

### Diagnóstico rápido

```python
import sys
sys.path.insert(0, 'betfair_scraper/dashboard/backend')
from utils import csv_reader
from api.optimize import _filter_xg, _filter_drift

data = csv_reader.analyze_cartera()
bets = data.get('bets', [])

for v in ['base', 'v2', 'v3']:
    n = len(_filter_xg(bets, v))
    print(f'_filter_xg(bets, {v!r}) = {n}')
for v in ['v1', 'v2', 'v3']:
    n = len(_filter_drift(bets, v))
    print(f'_filter_drift(bets, {v!r}) = {n}')

# Si todos retornan 0 → hay un problema con el naming
# Si retornan > 0 → el optimizer simplemente prefiere excluirlas (OK)
```

### Si se confirma que es un bug de naming

El naming mismatch histórico ya fue arreglado en `optimize.py:283` y `optimize.py:306`:
```python
# optimize.py línea 283 — ya correcto:
if b.get("strategy") not in ("xg_underperformance", "xg_underperformance_base"):
# optimize.py línea 306 — ya correcto:
if b.get("strategy") not in ("odds_drift", "odds_drift_v1"):
```

Si los filtros retornan 0 bets, buscar si hay OTRA versión del filtro en otro archivo.

### Checklist

- [ ] Ejecutar el diagnóstico rápido y verificar si los filtros retornan bets
- [ ] Si retornan 0: investigar por qué y aplicar fix de naming
- [ ] Si retornan > 0: documentar que el auto-disable es comportamiento del optimizer (no bug)
- [ ] Verificar el log "(0 bets)" — si el mensaje es engañoso, corregirlo para mayor claridad

---

## TAREA 3 — Momentum xG params hardcodeados (no están en config)

### Prioridad: BAJA

### Problema

`_detect_momentum_xg_trigger()` en `csv_reader.py` tiene parámetros críticos hardcodeados
que no pueden configurarse desde `cartera_config.json`:

```python
# Valores hardcodeados en el trigger (no exponibles via config):
sotMin = 2          # shots on target mínimo
sotRatioMin = 1.5   # ratio SOT local/visitante
xgUnderperfMin = 0.3 # diferencia xG mínima
oddsMin = 1.5       # cuotas mínimas
oddsMax = 4.0       # cuotas máximas
```

Estos mismos valores están duplicados en LIVE (`analytics.py` o `csv_reader.py`).
Como son idénticos en BT y LIVE no hay desalineamiento, pero no son tuneables.

### Búsqueda del código

```bash
# Localizar el trigger:
grep -n "_detect_momentum_xg_trigger\|sotRatioMin\|xgUnderperfMin" \
  betfair_scraper/dashboard/backend/utils/csv_reader.py | head -30
```

### Solución propuesta

1. Añadir al config de `momentum_xg` en `cartera_config.json`:
   ```json
   "momentum_xg": {
     "enabled": false,
     "version": "off",
     "minuteMin": 0,
     "minuteMax": 90,
     "sotMin": 2,
     "sotRatioMin": 1.5,
     "xgUnderperfMin": 0.3,
     "oddsMin": 1.5,
     "oddsMax": 4.0
   }
   ```

2. En `_detect_momentum_xg_trigger()`, leer esos parámetros del `cfg` dict:
   ```python
   sot_min = cfg.get("sotMin", cfg.get("sot_min", 2))
   sot_ratio_min = cfg.get("sotRatioMin", cfg.get("sot_ratio_min", 1.5))
   # etc.
   ```

3. En `_CAMEL_TO_SNAKE_ALIASES` (csv_reader.py ~línea 514), añadir los aliases:
   ```python
   "sotRatioMin": ["sot_ratio_min"],
   "xgUnderperfMin": ["xg_underperf_min"],
   ```

### Checklist

- [ ] Localizar todos los usos hardcodeados en `_detect_momentum_xg_trigger()`
- [ ] Añadir params al config de `momentum_xg` en `cartera_config.json`
- [ ] Modificar el trigger para leerlos del cfg
- [ ] Añadir aliases camelCase→snake_case en `_CAMEL_TO_SNAKE_ALIASES`
- [ ] Verificar con reconcile.py que BT-LIVE match rate no baja

---

## TAREA 4 — bt_optimizer.py lento para odds_drift

### Prioridad: BAJA (nice-to-have)

### Problema

El grid search para `odds_drift` evalúa:
- 6 versiones (v1-v6) × múltiples combos de params → ~5760 combos
- Tiempo: ~37 minutos para esta sola estrategia

Observación clave: el mejor combo siempre es el más permisivo
(`drift_min_pct=15, max_odds=999`) independientemente de la versión.
Esto sugiere que el search space se puede reducir drásticamente.

### Grid search actual (en bt_optimizer.py)

```python
# bt_optimizer.py — GRIDS dict, entrada para odds_drift:
"odds_drift": {
    "drift_min_pct": [15, 20, 25, 30, 40],
    "max_odds":      [3, 5, 999],
    "goal_diff_min": [0, 1, 2],
    "min_minute":    [0, 15, 30, 45],
    "max_minute":    [75, 85, 90],
},
```
Combos: 5×3×3×4×3 = 540 × 6 versiones = 3240 (algunos con workers ~37 min)

### Solución propuesta

**Opción A — Reducir el search space:**

Dado que la experiencia muestra que los params más permisivos siempre ganan,
se puede reducir a:

```python
"odds_drift": {
    "drift_min_pct": [15, 20, 30],     # 3 en vez de 5
    "max_odds":      [5, 999],          # 2 en vez de 3
    "goal_diff_min": [0, 1],            # 2 en vez de 3
    "min_minute":    [0, 30],           # 2 en vez de 4
    "max_minute":    [85, 90],          # 2 en vez de 3
},
```
Combos: 3×2×2×2×2 = 48 × 6 versiones = 288 → ~3 min

**Opción B — Paralelizar a nivel de versión + combo:**

El `phase1_grid_search` en bt_optimizer.py usa `ProcessPoolExecutor` pero con
splits por "familia". Para `odds_drift`, iterar las 6 versiones en paralelo:

```python
# En phase1_grid_search(), para VERSIONED_FAMILIES:
# Lanzar un worker por versión (6 workers para odds_drift)
```

### Archivos a modificar

- `scripts/bt_optimizer.py`
  - `GRIDS` dict — entrada `"odds_drift"` (alrededor de línea 200-230)
  - Opcionalmente, lógica de paralelización en `phase1_grid_search()`

### Checklist

- [ ] Identificar la entrada `odds_drift` en el `GRIDS` dict de bt_optimizer.py
- [ ] Reducir el search space (Opción A) — más simple y suficiente
- [ ] Verificar que el resultado sigue siendo ≥10% ROI y ≥40% IC95
- [ ] Medir el tiempo de ejecución tras el cambio

---

## TAREA 5 — cs_11, draw_xg_conv, cs_00, over25_2goals sin entrada en cartera_config.json

### Prioridad: BAJA

### Problema

Estas 4 estrategias tienen triggers en `csv_reader.py` y BT via `analyze_cartera()`,
pero **no tienen entrada en `cartera_config.json`**. Esto significa:

1. `analyze_cartera()` las omite en BT (no están habilitadas en config)
2. `detect_betting_signals()` no las detecta en LIVE
3. No aparecen en el dashboard

De las 24 estrategias actuales en config, estas 4 faltan.

**NOTA:** En el bt_optimizer.py grid search SÍ se evalúan porque el grid
usa `_analyze_strategy_simple()` directamente con los params del grid,
sin necesidad de que estén en config. Pero sus resultados NO se aplican al
live trading porque no están en config.

### Verificación del estado actual

```python
import json
with open('betfair_scraper/cartera_config.json') as f:
    cfg = json.load(f)
strats = cfg.get('strategies', {})
for k in ('draw_xg_conv', 'cs_11', 'cs_00', 'over25_2goals'):
    print(f'{k}: {"PRESENTE" if k in strats else "AUSENTE"}')
```

### Resultados de quality gates (del grid search)

- `draw_xg_conv`: NO pasa quality gates (en la lista de "discarded")
- `cs_11`: NO pasa quality gates
- `cs_00`: NO pasa quality gates
- `over25_2goals`: NO pasa quality gates

**Conclusión:** Como no pasan los gates, no merece la pena añadirlas con `enabled=True`.
Se pueden añadir con `enabled=False` para consistencia, o simplemente dejarlas fuera.

### Solución propuesta

Añadir las 4 a `cartera_config.json` con `enabled=False` y sus params del grid
(para que queden documentadas y puedan habilitarse si en el futuro pasan los gates):

```json
"draw_xg_conv": { "enabled": false, "minuteMin": 0, "minuteMax": 90 },
"cs_11":        { "enabled": false, "m_min": 62,   "m_max": 82   },
"cs_00":        { "enabled": false, "minuteMin": 0, "minuteMax": 90 },
"over25_2goals":{ "enabled": false, "minuteMin": 0, "minuteMax": 90 }
```

### Checklist

- [ ] Confirmar params del grid search para cada una (revisar `auxiliar/bt_optimizer_results.json`)
- [ ] Añadir las 4 entradas a `cartera_config.json` con `enabled=false`
- [ ] Verificar que `analyze_cartera()` no las activa
- [ ] Opcional: actualizar CLAUDE.md para reflejar que son 28 estrategias en config

---

## Contexto adicional importante

### Cómo funciona `_build_registry_config_map()` (para TAREA 1 y 2)

En `csv_reader.py:548-572`. Toma el dict `strategies` de config y mapea las claves
legacy (`"xg"`, `"drift"`, etc.) a claves de registry (`"xg_underperformance_base"`, etc.):

```python
_ORIG_REGISTRY_MAP = [
    ("draw",       [("back_draw_00_v1","v1"), ("back_draw_00_v15","v15"), ...]),
    ("drift",      [("odds_drift_v1","v1"), ("odds_drift_v2","v2"), ...]),
    ("clustering", [("goal_clustering", None)]),
    ("pressure",   [("pressure_cooker", None)]),
    ("xg",         [("xg_underperformance_base","base"), ("xg_underperformance_v2","v2"), ...]),
    ("momentum_xg",[("momentum_xg_v1","v1"), ("momentum_xg_v2","v2")]),
    ("tarde_asia", [("tarde_asia", None)]),
]
_ORIG_DEFAULT_VERS = {"draw": "v2r", "drift": "v1", "xg": "base", "momentum_xg": "off"}
```

Si `cartera_config.json` tiene `"xg": {"enabled": true, "version": "base"}`, entonces
`xg_underperformance_base` queda `enabled=true` y las demás versiones `enabled=false`.

Las estrategias "planas" nuevas (goal_clustering, pressure_cooker, etc.) NO pasan por
`_ORIG_REGISTRY_MAP`. Se leen directamente de `config["strategies"]["goal_clustering"]`.

### Estado del `bt_optimizer.py:phase4_apply()` — YA ARREGLADO

En `scripts/bt_optimizer.py:711-737`, la función `phase4_apply()` ya usa merge inteligente
(arreglado 2026-03-12). No necesita más cambios.

### Cómo ejecutar el pipeline completo

```bash
# Desde la raiz del proyecto:
python scripts/bt_optimizer.py                           # todo
python scripts/bt_optimizer.py --phase individual        # solo grid search (phases 1+2)
python scripts/bt_optimizer.py --phase presets           # solo generar presets (phase 3)
python scripts/bt_optimizer.py --phase apply             # solo aplicar mejor preset
python scripts/bt_optimizer.py --phase apply --criterion max_wr
python scripts/bt_optimizer.py --export                  # solo exportar CSV/XLSX
python scripts/bt_optimizer.py --dry-run                 # simular sin escribir config
```

### Cómo verificar BT-LIVE match rate

```bash
python tests/reconcile.py
# Debe mostrar ≥96% MATCH y ≥97% MATCH+MIN_DIFF sobre 1166+ partidos
```

### Archivos de referencia clave

```
auxiliar/bt_optimizer_results.json   → resultados del último grid search
betfair_scraper/data/presets/        → 4 presets + 4 result files
analisis/bt_results_*.csv            → último export de bets
betfair_scraper/cartera_config.json  → config activo
```

---

## Resumen de prioridades

| Tarea | Descripción | Prioridad | Esfuerzo |
|-------|-------------|-----------|----------|
| 1 | `_build_preset_config()` incluir estrategias nuevas | ALTA | ~30 min |
| 2 | Investigar auto-disable xg/drift en portfolio optimizer | MEDIA | ~1h |
| 3 | Momentum xG params en config | BAJA | ~45 min |
| 4 | Reducir search space odds_drift | BAJA | ~15 min |
| 5 | Añadir 4 estrategias faltantes a config | BAJA | ~10 min |

**Empezar por TAREA 1** — es la más clara y de mayor impacto para el sistema live.
