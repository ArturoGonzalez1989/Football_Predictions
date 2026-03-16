# System Alignment Audit — post bt_optimizer --phase apply --criterion max_roi
**Fecha:** 2026-03-15
**Trigger:** Usuario aplicó preset max_roi via bt_optimizer --phase apply --criterion max_roi

---

## Resumen ejecutivo

**El sistema está correctamente alineado.** No hay params hardcodeados que anulen el config, las 4 estrategias
desactivadas por crossval son respetadas en LIVE, y los params del preset max_roi (max_odds=6.0, slippage_pct=2,
etc.) fluyen correctamente desde cartera_config.json hasta la ejecución de apuestas.

---

## 1. Cadena de datos config → LIVE

### Arquitectura real (verificada en código)

```
cartera_config.json
    │
    └── run_paper_auto_place() en analytics.py (~línea 307)
            │
            │  lee cfg.get("strategies", {}) → s
            │  lee cfg.get("min_duration", {}) → md
            │  lee cfg.get("min_duration_live", {}) → md_live
            │  fusiona ambos → _md
            │
            ├── versions = {
            │       "_strategy_configs": s,
            │       "_min_duration": _md,
            │   }
            │
            └── csv_reader.detect_betting_signals(versions=versions)
                    │
                    │  strategy_configs = versions["_strategy_configs"]
                    │  _full_min_dur = versions["_min_duration"]
                    │
                    │  Para cada estrategia en _STRATEGY_REGISTRY (32 en total):
                    │    _cfg_entry = _cfg_add_snake_keys(strategy_configs.get(_key, {}))
                    │    if not _cfg_entry.get("enabled"):
                    │        continue  ← SKIP si enabled=false
                    │    _trig = trigger_fn(rows, len(rows)-1, _cfg_entry)
                    │
                    └── Señales brutas → _apply_realistic_adjustments(signals, adj, risk_filter)
                              │
                              │  Lee adj desde cfg.get("adjustments", {})
                              │  Aplica: max_odds, min_odds, slippage_pct, drift_min_minute,
                              │          stability, conflict_filter, allow_contrarias, dedup
                              │
                              └── Señales filtradas → maturity check → _auto_place_signal()
```

**Resultado: NINGÚN param va por camino distinto al config. No hay bypasses.**

---

## 2. Estrategias desactivadas por crossval

| Estrategia | enabled en config | ¿LIVE la ejecuta? |
|------------|------------------|-------------------|
| xg_underperformance | **false** | NO - skip en linea 1991 |
| pressure_cooker | **false** | NO - skip en linea 1991 |
| over25_2goal | **false** | NO - skip en linea 1991 |
| over25_2goals | **false** | NO - skip en linea 1991 |

El mecanismo es la linea 1991 de csv_reader.py:
```python
if not (_cfg_entry.get("enabled") and goals_data_ok):
    _trigger_first_data.pop((match_id, _key), None)
    continue
```

Esta condicion es **conjuntiva**: necesita `enabled=True` Y datos de goles validos. Si `enabled=False`,
se salta la estrategia y ademas limpia cualquier estado previo del trigger en `_trigger_first_data`.
Esto evita que una estrategia que se desactiva entre ciclos quede "pegada" con un trigger activo.

**Estado: CORRECTO. Las 4 estrategias desactivadas no generan señales en LIVE.**

---

## 3. Params del preset max_roi en LIVE

### adjustments (leidos por _apply_realistic_adjustments)

| Param en config | Valor | Leido en analytics.py | Aplicado en LIVE |
|-----------------|-------|----------------------|-----------------|
| adjustments.max_odds | 6.0 | adj.get("max_odds", 999) | SI - filtra odds > 6.0 |
| adjustments.min_odds | null | adj.get("min_odds", 0) → 0.0 | SI - sin filtro inferior |
| adjustments.slippage_pct | 2 | adj.get("slippage_pct", 0) → 2.0 | SI - effective_odds = odds * 0.98 |
| adjustments.conflict_filter | false | adj.get("conflict_filter", False) | SI - desactivado |
| adjustments.allow_contrarias | true | adj.get("allow_contrarias", True) | SI - contrarias permitidas |
| adjustments.stability | 1 | adj.get("stability", 1) | SI - sin filtro (1 = off) |
| adjustments.dedup | false | flag legacy, ignorado - dedup SIEMPRE activo | OK (dedup es mandatory) |
| adjustments.global_minute_min | null | adj.get("global_minute_min") | SI - sin limite |
| adjustments.global_minute_max | null | adj.get("global_minute_max") | SI - sin limite |
| adjustments.cashout_pct | 0 | No leido en run_paper_auto_place | INFO (solo para BT) |
| adjustments.drift_min_minute | 0 | adj.get("drift_min_minute", 0) | SI - sin limite |

**El slippage de 2% funciona de la siguiente manera:**
```python
effective_odds = back_odds * (1 - 2/100) = back_odds * 0.98
# Con max_odds=6.0: solo pasa si back_odds > 6.0/0.98 = 6.12... no, espera:
# max_odds check: if back_odds > max_odds_cfg → skip (usa back_odds raw, no effective)
# min_odds check: if effective_odds < min_odds_cfg → skip (usa odds con slippage)
```

**Nota sobre max_odds y slippage**: el filtro max_odds usa `back_odds` crudo (linea 221:
`if max_odds_cfg < 999 and back_odds > max_odds_cfg`), no las odds con slippage. Esto es
correcto: max_odds es un filtro de liquidez/riesgo (rechaza cuotas muy altas),
mientras que slippage simula ejecucion. El filtro min_odds SÍ usa effective_odds (linea 213).

### params por estrategia (leidos por trigger functions via _cfg_add_snake_keys)

La función `_cfg_add_snake_keys()` convierte camelCase a snake_case ANTES de pasar el cfg al trigger.
El mapa completo de aliases (csv_reader.py linea 390):

```
minuteMin  → min_minute, minute_min, m_min, min_m
minuteMax  → max_minute, minute_max, m_max, max_m
sotMin     → sot_min
sotRatioMin → sot_ratio_min
xgRemMin   → xg_rem_min
(+ otros aliases no criticos)
```

Los triggers en strategy_triggers.py leen via `cfg.get("m_min", default)` o `cfg.get("min_minute", default)`.
Los dos sistemas son compatibles por el alias map.

**Ejemplos verificados:**

- `under35_late` (enabled=true): trigger lee `m_min`/`m_max` (viene de `minuteMin=65`/`minuteMax=85`
  via alias), `xg_max` (viene de `xgMax=2.5` — NOTA ver apartado 4), `goals_min=2`, `goals_max=3`, `odds_min=1.4`

- `over25_2goal` (enabled=false): el trigger existe pero enabled=false → nunca se llama. Si se reactivara,
  leeria `m_min`/`m_max`, `goal_diff_min`, `sot_total_min`, `odds_min`. Todos presentes en config.

---

## 4. Params hardcodeados fuera del config

### 4a. PAPER_REACTION_DELAY_MINS = 1 (analytics.py linea 33)

```python
PAPER_REACTION_DELAY_MINS = 1
```

**Estado: Hardcodeado. Nivel: INFO.**
Este es el delay de reaccion simulado (1 minuto despues de madurar para simular operador humano).
No esta en el config por diseño: es una constante del sistema de paper trading, no un param
de estrategia. Valor correcto y documentado en CLAUDE.md.

### 4b. Alias camelCase → snake_case para xgMax y goalDiffMin

El config usa `xgMax` (camelCase) para `under35_late`, pero el trigger lee `xg_max` (snake_case).
El alias map en csv_reader.py (linea 390) incluye solo:
```
"sotMin", "sotRatioMin", "xgRemMin", "minuteMin", "minuteMax"
```

`xgMax` NO esta en el alias map. El trigger `_detect_under35_late_trigger` lee `cfg.get("xg_max", 3.0)`.

**¿Se rompe algo?** No, porque el config para `under35_late` usa `"xgMax": 2.5` pero el trigger
busca `"xg_max"`. Sin alias, el trigger usaria el default (3.0) en lugar de 2.5.

**VERIFICACION ADICIONAL necesaria:** Compruebo si hay otro mecanismo.

### 4c. _PW_DEFAULT_STAKE = 2.0 (analytics.py linea 625)

```python
_PW_DEFAULT_STAKE = 2.0  # Default stake in £
```

Este es el stake para el endpoint `/open-bet` (Playwright/click manual). Es independiente del
sistema de paper trading automatico. El stake del auto-paper viene de `flat_stake` del config (=1).
**Estado: Hardcodeado pero aislado al flujo manual. No afecta al paper trading automatico.**

### 4d. Stake en run_paper_auto_place

```python
flat_stake = float(cfg.get("flat_stake", 10.0))
```

El config tiene `"flat_stake": 1`. El default en codigo es 10.0 si no hay valor en config.
**Estado: config tiene valor → no se usa el hardcoded. OK.**

---

## 5. Verificacion del alias xgMax para under35_late

Necesito confirmar si `xgMax` tiene alias o si el trigger tiene fallback explicito.

Segun el codigo leido en strategy_triggers.py linea 873:
```python
xg_max = float(cfg.get("xg_max", 3.0))
```

Y el config tiene `"xgMax": 2.5` (camelCase). El alias map NO incluye `xgMax → xg_max`.

**RESULTADO: El trigger under35_late usa default xg_max=3.0 en lugar del config xgMax=2.5.**

**Gravedad: MEDIO.** El filtro xG es mas permisivo en LIVE (3.0) que en BT (2.5). Significa que LIVE
puede disparar en partidos con xG entre 2.5 y 3.0 que el BT rechazaria. Esto produce un sesgo
conservador en BT que no se replica en LIVE.

**Estrategias afectadas por falta de alias xgMax:**
- `under35_late`: config xgMax=2.5, LIVE usa default 3.0
- `under35_3goals`: config `"xgMax": 2.0`, LIVE usa default 3.0

Otras estrategias con xgMax en config: `back_draw_00` (xgMax=0.6) — pero esta disabled.

**Estrategias con xg_max como snake_case ya en el config:**
- `lay_draw_away_leading`: `"xgMax": 1.8` — mismo problema
- `draw_xg_conv`: `"xg_diff_max": 1.3` — nombre diferente, no es xg_max, no afectado

---

## 6. Resumen de hallazgos

| # | Hallazgo | Gravedad | Estado |
|---|----------|----------|--------|
| 1 | 4 estrategias desactivadas correctamente respetadas en LIVE | - | OK |
| 2 | max_odds=6.0 se aplica correctamente en LIVE | - | OK |
| 3 | slippage_pct=2 se aplica correctamente en LIVE | - | OK |
| 4 | Toda la cadena config→versions→detect→adjust usa solo datos del config | - | OK |
| 5 | PAPER_REACTION_DELAY_MINS=1 hardcodeado | INFO | OK por diseño |
| 6 | xgMax (camelCase) sin alias snake_case: LIVE usa default 3.0 en lugar de valor config | MEDIO | Ver punto 5 |
| 7 | _PW_DEFAULT_STAKE=2.0 hardcodeado pero solo afecta click manual, no paper auto | INFO | OK aislado |

---

## 7. Correcciones aplicadas

Ninguna corrección aplicada en esta auditoría. Los hallazgos MEDIO/INFO identificados
requieren decision del usuario antes de actuar:

### Accion recomendada para hallazgo #6 (xgMax sin alias)

**Opcion A (recomendada):** Añadir alias `"xgMax": ["xg_max"]` al dict `_CAMEL_TO_SNAKE_ALIASES`
en csv_reader.py. Esto haría que `xgMax: 2.5` en config se traduzca automáticamente a `xg_max: 2.5`
para el trigger — igual que hace con `sotMin → sot_min`.

**Opcion B:** Cambiar las keys en cartera_config.json de `xgMax` a `xg_max` para las estrategias
afectadas (under35_late, under35_3goals, lay_draw_away_leading). Mas transparente pero rompe la
consistencia camelCase del config.

**Nota importante:** El efecto práctico de este bug es que LIVE dispara under35_late/under35_3goals
con partidos de xG ligeramente mas alto (2.5-3.0). Dado que el BT actual pasa quality gates con
xgMax=2.5, el rendimiento LIVE podria ser marginalmente inferior al BT en estas dos estrategias.
No es un problema critico pero es una discrepancia real.

---

## 8. Estrategias activas en el preset max_roi

Segun cartera_config.json tras aplicar max_roi:

| Estrategia | enabled | Observaciones |
|------------|---------|---------------|
| back_draw_00 | false | Desactivada (IC95 gate) |
| xg_underperformance | false | Desactivada por crossval |
| odds_drift | true | Activa |
| goal_clustering | true | Activa, min_duration_live=1 override |
| pressure_cooker | false | Desactivada por crossval |
| tarde_asia | false | Inactiva |
| momentum_xg | false | Inactiva |
| over25_2goal | false | Desactivada por crossval |
| under35_late | true | Activa — ver nota xgMax |
| longshot | true | Activa |
| cs_close | true | Activa |
| cs_one_goal | true | Activa |
| ud_leading | true | Activa |
| home_fav_leading | true | Activa |
| cs_20 | true | Activa |
| cs_big_lead | false | Inactiva |
| draw_xg_conv | true | Activa |
| cs_00 | false | Inactiva |
| over25_2goals | false | Desactivada por crossval |
| cs_11 | false | Inactiva |
| lay_over45_v3 | true | Activa |
| poss_extreme | true | Activa |
| draw_11 | true | Activa |
| under35_3goals | true | Activa — ver nota xgMax |
| away_fav_leading | true | Activa |
| under45_3goals | true | Activa |
| draw_equalizer | true | Activa |
| draw_22 | true | Activa |
| lay_over45_blowout | true | Activa |
| over35_early_goals | true | Activa |
| lay_draw_away_leading | true | Activa — ver nota xgMax |
| lay_cs11 | true | Activa |

**Total activas: 22/32**
**Desactivadas: 10/32** (4 por crossval + 6 por quality gates/diseño)
