# Guía: Añadir una Nueva Estrategia
**Actualizado:** 2026-03-13
**Estado del sistema:** BT↔LIVE alineados al 97.3%. Arquitectura unificada.

---

## Arquitectura actual (cómo funciona)

Desde la unificación completa de 2026-03-11/13, **todas las estrategias comparten el mismo código** para BT y LIVE. No existe diferenciación entre estrategias "antiguas" y "nuevas".

```
cartera_config.json
       ↓ (parámetros)
csv_reader.py → _detect_<name>_trigger(rows, curr_idx, cfg)
       ↓
  BT: _analyze_strategy_simple()  ←── misma función trigger
  LIVE: detect_betting_signals()  ←── misma función trigger
       ↓
  _STRATEGY_REGISTRY              ←── punto de registro único
```

El `_STRATEGY_REGISTRY` en `csv_reader.py` es la **única lista autoritativa** de estrategias. Todo lo demás (analyze_cartera, detect_betting_signals, reconcile, bt_optimizer) itera sobre él automáticamente.

---

## Checklist: pasos obligatorios

### Paso 1 — Trigger function en `csv_reader.py`

```python
def _detect_<name>_trigger(rows: list, curr_idx: int, cfg: dict):
    """
    Detecta si la estrategia dispara en rows[curr_idx].
    Solo puede mirar rows[:curr_idx+1] — nunca filas futuras.

    Returns: dict con datos del trigger (incluye odds) si dispara, None si no.
    """
    # Leer params del config
    minute_min = cfg.get('minuteMin', 55)
    minute_max = cfg.get('minuteMax', 80)
    ...
    # Retornar None o dict con al menos: {'back_odds': X, 'recommendation': '...'}
```

**Reglas críticas del trigger:**
- Solo leer `rows[:curr_idx+1]` — nunca `rows[curr_idx+1:]` ni `rows[-1]`
- Retornar `None` si no dispara, `dict` si dispara
- El dict debe incluir suficiente info para que `extractor_fn` extraiga las odds

### Paso 2 — Entrada en `_STRATEGY_REGISTRY`

En `csv_reader.py`, añadir al final de `_STRATEGY_REGISTRY`:

```python
(
    'nombre_key',                          # clave en cartera_config.json
    'Nombre Display',                      # nombre legible en UI
    _detect_nombre_trigger,                # función trigger (Paso 1)
    'Descripción breve del edge',          # descripción
    _extract_<mercado>_odds,               # extractor de odds (ver abajo)
    lambda t, gl, gv: <condición_win>,    # win_fn (ver abajo)
),
```

#### Extractores disponibles (reutilizar siempre que sea posible)
| Mercado | Extractor |
|---------|-----------|
| Over/Under goals | `_extract_over_odds` / `_extract_under_odds` |
| Resultado equipo | `_extract_team_odds` |
| Correct Score | `_extract_cs_odds` |
| LAY | `_extract_lay_odds` |

Si el mercado es nuevo, escribir un extractor siguiendo el patrón de los existentes.

#### `win_fn` — función de victoria

La `win_fn` recibe `(trigger_dict, ft_goals_local, ft_goals_visitante)` y retorna `bool`.

```python
# Ejemplos de win_fn
lambda t, gl, gv: (gl + gv) >= 3         # BACK Over 2.5
lambda t, gl, gv: (gl + gv) <= 3         # BACK Under 3.5
lambda t, gl, gv: (gl + gv) <= 4         # BACK Under 4.5 / LAY Over 4.5
lambda t, gl, gv: gl > gv                # BACK Home Win
lambda t, gl, gv: gv > gl                # BACK Away Win
lambda t, gl, gv: gl == gv               # BACK Draw
lambda t, gl, gv: gl == 1 and gv == 0    # BACK CS 1-0
# Para LAY: el win_fn es el mismo (¿no pasó el evento?) — el cálculo de P/L
# en _analyze_strategy_simple ya distingue LAY vs BACK por el rec string
```

**Atención:** un `win_fn` incorrecto genera P/L histórico incorrecto **sin error visible**. Verificar con el notebook o cases manuales antes de commitear.

### Paso 3 — Config inicial en `cartera_config.json`

Añadir una entrada mínima para que bt_optimizer pueda hacer grid search:

```json
"nombre_key": {
    "enabled": false,
    "minuteMin": 55,
    "minuteMax": 85
}
```

Empezar con `enabled: false`. El bt_optimizer decidirá si la activa tras el grid search.

### Paso 4 — ¿Comparte mercado con otra estrategia?

Si la nueva estrategia apuesta en el **mismo mercado** que alguna ya existente, añadirla a `_STRATEGY_MARKET` en `csv_reader.py`:

```python
_STRATEGY_MARKET = {
    'under35_late':   'under_3.5',
    'under35_3goals': 'under_3.5',   # ← mismo grupo = dedup activo
    'draw_11':        'draw',
    'draw_xg_conv':   'draw',
    'over25_2goal':   'over_2.5',
    'goal_clustering':'over_2.5',
    'pressure_cooker':'over_2.5',
    # nueva_estrategia: 'over_2.5',  ← añadir aquí si comparte Over 2.5
}
```

Si se omite este paso y la estrategia comparte mercado, el sistema colocará **dos apuestas sobre el mismo resultado** en el mismo partido — redundante y penaliza el ROI.

Grupos de mercado actuales:
- `under_3.5`: `under35_late`, `under35_3goals`
- `draw`: `draw_11`, `draw_xg_conv`
- `over_2.5`: `over25_2goal`, `goal_clustering`, `pressure_cooker`

### Paso 5 — Correr bt_optimizer

```bash
python scripts/bt_optimizer.py --phase all
```

El optimizer:
1. Hace grid search de parámetros (phase 1)
2. Actualiza `cartera_config.json` con los params óptimos y `enabled: true/false` según quality gates (phase 2)
3. Genera presets de portfolio (phase 3-4)

**No modificar manualmente `enabled` en cartera_config.json.** El BT decide.

### Paso 6 — Verificar alineamiento BT↔LIVE

```bash
python tests/reconcile.py
```

Target mínimo: **≥97% MATCH rate**. Si baja significativamente, hay una discrepancia en el trigger (BT y LIVE están viendo condiciones distintas).

Causas comunes de desalineamiento:
- Trigger lee `rows[-1]` en vez de `rows[curr_idx]`
- Condición asimétrica: `< max` en un lado y `<= max` en el otro
- `win_fn` que usa datos del trigger dict con clave incorrecta

---

## Quality Gates (criterios de aprobación automática en BT)

Para que el optimizer active la estrategia, debe pasar los 3 gates:

| Gate | Umbral | Descripción |
|------|--------|-------------|
| **N mínimo** | `max(15, n_partidos // 25)` | ~46 bets con 1168 partidos |
| **ROI** | ≥ 10% | `sum(pl) / N * 100` |
| **IC95 lower** | ≥ 40% | Límite inferior del intervalo Wilson al 95% |

Estrategias que no pasan: `enabled: false` en config, sin señales LIVE.

`draw_xg_conv` es el ejemplo de estrategia que pasa **por los pelos** (ROI=12.6%, CI_low=40.5%) — válido pero con mayor incertidumbre.

---

## Lo que NO hay que hacer manualmente

| Acción | Por qué no |
|--------|------------|
| Editar `enabled` en cartera_config.json a mano | El BT optimizer lo gestiona. Editarlo a mano desalinea la config del output real de BT |
| Añadir a `analytics.py` bloques `if strategy == 'nueva':` | El registry propaga automáticamente al LIVE via `_strategy_configs` |
| Crear una sección separada en reconcile.py | El reconcile itera `_STRATEGY_REGISTRY` automáticamente |
| Usar prefijos en el key (`sd_`, `new_`, etc.) | Todas las estrategias son entidades independientes sin categorías |

---

## Verificación rápida post-implementación

```python
import sys
sys.path.insert(0, 'betfair_scraper/dashboard/backend')
from utils.csv_reader import _STRATEGY_REGISTRY, _STRATEGY_MARKET

# 1. Estrategia en registry
keys = [k for k, *_ in _STRATEGY_REGISTRY]
assert 'nombre_key' in keys, "Falta en _STRATEGY_REGISTRY"

# 2. Win_fn funciona
win_fn = next(wf for k,_,__,___,____,wf in _STRATEGY_REGISTRY if k == 'nombre_key')
assert win_fn({}, 2, 1) in (True, False), "win_fn devuelve tipo incorrecto"

# 3. Market dedup configurado (si aplica)
# Si comparte mercado, verificar que está en _STRATEGY_MARKET
```

Luego:
```bash
python tests/reconcile.py   # ≥97% MATCH
```
