# Guía de bt_optimizer.py

`scripts/bt_optimizer.py` es el pipeline de backtest y optimización de parámetros para las
estrategias de Furbo. Reemplaza el notebook `strategies_designer.ipynb` con un CLI reproducible.

---

## Uso rápido

```bash
# Desde la raíz del proyecto:
python scripts/bt_optimizer.py                            # pipeline completo (phases 0-5, ~20 min)
python scripts/bt_optimizer.py --phase individual         # solo grid search + build config (~15 min)
python scripts/bt_optimizer.py --phase presets            # solo generar 4 presets de portfolio
python scripts/bt_optimizer.py --phase apply              # aplicar mejor preset al config
python scripts/bt_optimizer.py --phase apply --criterion max_wr   # aplicar preset específico
python scripts/bt_optimizer.py --phase export             # solo exportar CSV + XLSX
python scripts/bt_optimizer.py --dry-run                  # simular sin escribir cartera_config.json
python scripts/bt_optimizer.py --phase individual --strategies pressure_cooker,ud_leading  # estrategias concretas
```

---

## Fases del pipeline

### Phase 0 — Carga de datos
Carga todos los `partido_*.csv` históricos en memoria caché una sola vez (~3-5 s).
Las fases siguientes reutilizan este caché sin releer disco.

### Phase 1 — Grid search individual
Evalúa todas las combinaciones de parámetros definidas en `SEARCH_SPACES` para cada estrategia.
Para cada combo:
1. Llama a `_analyze_strategy_simple(trigger_fn, cfg, min_dur)` con los params del combo.
2. Evalúa los quality gates (`_eval_bets`): N mínimo, ROI ≥ 10%, IC95_lower ≥ 40%.
3. Guarda el mejor combo (máximo `score = ci_low × roi / 100`).

Al final imprime una tabla ordenada por score:
```
Estrategia                   N    WR%   ROI%      P/L        IC95
ud_leading               213   65.0   77.5    165.0 [58.0-71.2]
...
```

Estrategias que no pasan ningún combo quedan como "discarded" y se desactivan en phase 2.

### Phase 2 — Build config óptimo
Toma los resultados de phase 1 y construye el nuevo bloque `strategies` para
`cartera_config.json`:
- Estrategias aprobadas: `enabled: true` + parámetros óptimos del grid (convertidos a camelCase).
- Estrategias rechazadas: `enabled: false`, preserva los mejores params encontrados.
- Estrategias sin search space (tarde_asia): sin cambios.

Los params se convierten de snake_case a camelCase via `_snake_to_camel()`:
`m_min → minuteMin`, `xg_max → xgMax`, `drift_min_pct → driftMin`, etc.

Resultado guardado en `auxiliar/bt_optimizer_results.json`.

### Phase 3 — Portfolio presets
Ejecuta `optimizer_cli.run()` para 4 criterios de optimización de portfolio:
- `max_roi`: maximiza ROI del portfolio
- `max_pl`: maximiza P/L absoluto
- `max_wr`: maximiza win rate
- `min_dd`: minimiza drawdown máximo

Genera 4 archivos en `betfair_scraper/data/presets/`:
- `preset_max_roi_config.json` — config del portfolio óptimo según ROI
- `preset_max_pl_config.json` — config según P/L
- `preset_max_wr_config.json` — config según WR
- `preset_min_dd_config.json` — config según drawdown

Cada preset contiene el subconjunto de estrategias que maximiza el criterio elegido.
El portfolio optimizer puede decidir excluir estrategias que sí pasan gates individuales
si el portfolio es mejor sin ellas (comportamiento correcto, no un bug).

### Phase 4 — Aplicar mejor preset
Compara los 4 presets por el selector (por defecto `confident_roi = ci_low × roi`).
Aplica el ganador a `cartera_config.json` con **merge inteligente**:
- Estrategias que el preset activa: aplica todos los params del preset.
- Estrategias que el preset desactiva: solo pone `enabled: false`, preserva params.
- Estrategias fuera del preset (nuevas, no conocidas): sin cambios.
- No reintroduce claves obsoletas de presets antiguos.

### Phase 5 — Export
Ejecuta `analyze_cartera()` con el config final y exporta:
- `analisis/bt_results_<timestamp>.csv` — todas las apuestas BT, una fila por apuesta
- `analisis/bt_results_<timestamp>.xlsx` — 3 hojas:
  - `Bets`: todas las apuestas
  - `Por Estrategia`: resumen por estrategia (N, WR%, P/L, ROI%, IC95)
  - `Acumulado`: P/L acumulado cronológico

---

## Quality gates

Aplicados en `_eval_bets()`:

| Gate | Valor |
|------|-------|
| N mínimo | `max(15, n_partidos // 25)` ≈ 48 con ~1200 partidos |
| ROI mínimo | ≥ 10% |
| IC95 lower (Wilson) | ≥ 40% |

Si un combo no supera los tres gates, se descarta. Si ningún combo de una estrategia los supera,
la estrategia queda desactivada.

---

## Añadir una nueva estrategia al pipeline

Para que bt_optimizer.py incluya una nueva estrategia en el grid search hay que tocar **4 sitios**:

### 1. Trigger en `strategy_triggers.py`
Crear la función `_detect_<name>_trigger(rows, curr_idx, cfg) → dict | None`.
- Recibe las filas del partido hasta `curr_idx` inclusive.
- Lee parámetros del `cfg` dict usando `cfg.get("m_min", DEFAULT)` (snake_case).
- Devuelve un dict con datos del trigger (odds, minuto, etc.) o `None` si no se cumple.

### 2. Entrada en `_STRATEGY_REGISTRY` (`csv_reader.py`)
Añadir una tupla al final de la lista (línea ~428):
```python
("nombre_estrategia", "Nombre Legible",
 _detect_nombre_trigger,          # función trigger
 "Descripción breve",             # descripción
 _extract_nombre_odds,            # función extractor de odds
 lambda t, gl, gv: <condición_victoria>),  # win function
```
La win function evalúa si la apuesta ganó dado el resultado final (`gl` = goles local, `gv` = visitante).

Todas las estrategias son directas (sin versiones). Añadirla a `SINGLE_STRATEGIES` en bt_optimizer.py.

### 3. Search space en `SEARCH_SPACES` (`bt_optimizer.py`)
Añadir un entry en el dict `SEARCH_SPACES` (línea ~89):
```python
"nombre_estrategia": {
    "m_min":    [50, 55, 60, 65],    # ventana de minutos inferior
    "m_max":    [75, 80, 85, 90],    # ventana de minutos superior
    "param_1":  [val1, val2, val3],  # otros parámetros
    "param_2":  [val_a, val_b],
},
```
Reglas para el search space:
- Usar nombres snake_case que coincidan exactamente con los que lee el trigger.
- `m_min`/`m_max` se convierten a `minuteMin`/`minuteMax` en cartera_config.json (via `_snake_to_camel`).
- Mantener el número de combos razonable: con 1200 partidos cada combo tarda ~0.3-0.5 s,
  por lo que 200 combos = ~1 min.

Añadir también el key a `SINGLE_STRATEGIES` (línea ~250):
```python
SINGLE_STRATEGIES = [
    "goal_clustering", "pressure_cooker",
    ...,
    "nombre_estrategia",   # <-- añadir aquí
]
```

### 4. Config en `cartera_config.json`
Añadir la entrada con `enabled: false` inicialmente (se activará si pasa quality gates):
```json
"nombre_estrategia": {
    "enabled": false,
    "minuteMin": 0,
    "minuteMax": 90
}
```

---

## Parámetros de ejecución

| Flag | Default | Descripción |
|------|---------|-------------|
| `--phase` | `all` | Qué fases ejecutar: `all`, `individual`, `presets`, `apply`, `export` |
| `--strategies` | (todas) | Comma-separated: solo optimizar estas familias (ej. `pressure_cooker,ud_leading`) |
| `--criterion` | `confident_roi` | Selector del mejor preset en phase 4: `max_roi`, `max_pl`, `max_wr`, `min_dd`, `confident_roi` |
| `--workers` | 4 | Número de workers (no usado actualmente — lambdas no son picklables) |
| `--dry-run` | false | No escribe `cartera_config.json` ni presets. Solo muestra qué haría |

---

## Archivos de entrada/salida

| Archivo | Rol |
|---------|-----|
| `betfair_scraper/data/partido_*.csv` | Datos históricos de partidos (entrada, solo lectura) |
| `betfair_scraper/cartera_config.json` | Config de estrategias (entrada + salida en phases 2/4) |
| `auxiliar/bt_optimizer_results.json` | Resultados del último phase 1+2 (intermedio) |
| `betfair_scraper/data/presets/preset_*_config.json` | Presets generados (salida phase 3) |
| `betfair_scraper/data/presets/preset_*_result.json` | Stats del optimizer por preset (salida phase 3) |
| `analisis/bt_results_<ts>.csv` | Apuestas BT del portfolio final (salida phase 5) |
| `analisis/bt_results_<ts>.xlsx` | Mismo contenido + resumen en Excel (salida phase 5) |

---

## Flujo típico

```
Añades nueva estrategia → Editas SEARCH_SPACES + SINGLE_STRATEGIES
    ↓
python bt_optimizer.py --phase individual --strategies nombre_nueva
    → Ver si pasa quality gates y con qué params
    ↓
Si pasa: python bt_optimizer.py --phase presets
    → Regenerar presets con la nueva estrategia incluida
    ↓
python bt_optimizer.py --phase apply
    → Aplicar el mejor preset al cartera_config.json
    ↓
python bt_optimizer.py --phase export
    → CSV/XLSX actualizados
    ↓
python tests/reconcile.py
    → Verificar que BT-LIVE match rate sigue ≥ 97%
```

---

## Estrategias LAY — P/L distinto al BACK

Las estrategias LAY tienen una fórmula de P/L diferente a las BACK:
- **Win**: `+STAKE * 0.95` (fijo, independiente de odds)
- **Loss**: `-STAKE * (lay_odds - 1)` (liability — crece con las odds)

Esto significa que odds altas en LAY implican pérdidas potenciales grandes. El ROI del BT
refleja esto correctamente porque `_analyze_strategy_simple` lee la win function del registry
(que evalúa si el resultado final cumple la condición) y el P/L calculado en `analyze_cartera()`
usa la fórmula LAY cuando el tipo de mercado es LAY.

Estrategias LAY actuales en el pipeline: `lay_over45_v3`, `lay_over45_blowout`,
`lay_draw_away_leading` (H104), `lay_cs11` (H106).

**Importante al definir el search space de una estrategia LAY**: incluir un rango de `odds_max`
que controle la liability máxima. Con odds muy altas (>20), una sola pérdida puede borrar
muchas ganancias.

---

## Estrategias registradas en el pipeline

| Estrategia | Tipo | Round | Estado bt_optimizer |
|-----------|------|-------|---------------------|
| goal_clustering | BACK | Original | ✅ En SINGLE_STRATEGIES |
| pressure_cooker | BACK | Original | ✅ |
| over25_2goal | BACK | R1 | ✅ |
| under35_late | BACK | R1 | ✅ |
| longshot | BACK | R1 | ✅ |
| cs_close | BACK | R1 | ✅ |
| cs_one_goal | BACK | R1 | ✅ |
| ud_leading | BACK | R1 | ✅ |
| home_fav_leading | BACK | R1 | ✅ |
| cs_20 | BACK | R1 | ✅ |
| cs_big_lead | BACK | R1 | ✅ |
| lay_over45_v3 | LAY | R1 | ✅ |
| draw_xg_conv | BACK | R1 | ✅ |
| poss_extreme | BACK | R1 | ✅ |
| cs_00 | BACK | R1 | ✅ |
| over25_2goals | BACK | R1 | ✅ |
| draw_11 | BACK | R1 | ✅ |
| under35_3goals | BACK | R1 | ✅ |
| away_fav_leading | BACK | R1 | ✅ |
| under45_3goals | BACK | R1 | ✅ |
| cs_11 | BACK | R1 | ✅ |
| draw_equalizer | BACK | R17 | ✅ |
| draw_22 | BACK | R17 | ✅ |
| lay_over45_blowout | LAY | R18 | ✅ |
| over35_early_goals | BACK | R19 | ✅ (añadida 2026-03-14) |
| lay_draw_away_leading | LAY | R19 | ✅ (añadida 2026-03-14) |
| lay_cs11 | LAY | R19 | ✅ (añadida 2026-03-14) |
| back_draw_00 | BACK | Original | ✅ (versioned family) |
| xg_underperformance | BACK | Original | ✅ (versioned family) |
| odds_drift | BACK | Original | ✅ (versioned family) |
| momentum_xg | BACK | Original | ✅ (versioned family) |
| tarde_asia | BACK | Original | Sin search space (liga-based) |

---

## Notas importantes

- **`--phase individual` guarda resultados** en `bt_optimizer_results.json`. Los phases posteriores
  (`presets`, `apply`) cargan ese fichero — no necesitan relanzar el grid search.
- **Backup automático**: phases 3 y 4 hacen backup de `cartera_config.json` antes de escribirlo
  (`.json.bak_<timestamp>`). Si algo sale mal se puede restaurar.
- **Orden camelCase↔snake_case**: los triggers leen snake_case (`m_min`, `xg_max`).
  La config almacena camelCase (`minuteMin`, `xgMax`). La traducción ocurre en
  `_cfg_add_snake_keys()` al ejecutar BT y LIVE. El mapping completo está en
  `_CAMEL_TO_SNAKE_ALIASES` en `csv_reader.py`.
- **tarde_asia** no tiene entry en `SEARCH_SPACES` (su detección es por liga, sin parámetros
  tuneables). Se incluye en `all_families` para que phase 2 la marque como descartada
  (no pasa gates) y la deje en `enabled: false`.
