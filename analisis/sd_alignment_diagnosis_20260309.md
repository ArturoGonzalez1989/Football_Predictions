# Diagnóstico de Alineamiento BT vs LIVE — Estrategias SD
**Fecha:** 2026-03-09
**Objetivo:** Identificar qué condiciones son distintas entre BT (sd_generators.py) y LIVE (csv_reader.py:detect_betting_signals) para las 8 SD strategies que dispararon en paper.

---

## Arquitectura de las SD strategies (contexto crítico)

Las SD strategies tienen **tres capas** en el BT, pero **solo una** en LIVE:

### BT (Notebook / sd_generators.py)
```
sd_generators.py:gen_<nombre>()    ← genera bets desde superset gate (rango amplio)
       ↓
sd_filters.py:_apply_sd_<nombre>() ← aplica filtro config (rango exacto aprobado)
       ↓
eval_sd()                          ← evalúa estadísticas
```

### LIVE (csv_reader.py:detect_betting_signals)
```
detect_betting_signals()           ← bloque inline con config de cartera_config.json
```

El generador BT usa un **superset gate** (rango ligeramente más amplio que el filtro aprobado) para poder hacer grid search. El filtro `_apply_sd_*` es lo que aplica los params exactos del config aprobado. En LIVE, solo existe el bloque inline.

**Implicación fundamental:** cuando comparamos BT vs LIVE hay que comparar el filtro `_apply_sd_*` (no el generador) contra LIVE.

---

## DISCREPANCIA GLOBAL #1 (CRÍTICO): Semántica de m_max — `<` (BT) vs `<=` (LIVE)

Este es el bug más sistemático. Afecta a **todas** las SD strategies.

### BT (sd_filters.py)
```python
# Línea 358 (sd_over25_2goal): mm <= (b.get('minuto') or 0) < mx
# Línea 410 (sd_under35_late): mm <= (b.get('minuto') or 0) < mx
# Línea 640 (sd_cs_close):     mm <= (b.get('minuto') or 0) < mx
# Línea 656 (sd_cs_one_goal):  mm <= (b.get('minuto') or 0) < mx
# Línea 693 (sd_ud_leading):   mm <= (b.get('minuto') or 0) < mx
# Línea 751 (sd_home_fav_leading): mm <= (b.get('minuto') or 0) < mx
# Línea 806 (sd_cs_20):        mm <= (b.get('minuto') or 0) < mx
# Línea 824 (sd_cs_big_lead):  mm <= (b.get('minuto') or 0) < mx
```
**El filtro BT usa `< mx` (EXCLUSIVO en el extremo superior).**

### LIVE (csv_reader.py)
```python
# Línea 4815: if (_sd_m_min <= _m <= _sd_m_max ...  ← sd_over25_2goal
# Línea 4831: if (_sd_m_min <= _m <= _sd_m_max ...  ← sd_under35_late
# Línea 4874: if _sd_m_min <= _m <= _sd_m_max ...   ← sd_cs_close
# Línea 4890: if _sd_m_min <= _m <= _sd_m_max ...   ← sd_cs_one_goal
# Línea 4907: if _sd_m_min <= _m <= _sd_m_max ...   ← sd_ud_leading
# Línea 4940: if _sd_m_min <= _m <= _sd_m_max ...   ← sd_home_fav_leading
# Línea 4963: if _sd_m_min <= _m <= _sd_m_max ...   ← sd_cs_20
# Línea 4979: if _sd_m_min <= _m <= _sd_m_max ...   ← sd_cs_big_lead
```
**LIVE usa `<= _sd_m_max` (INCLUSIVO en el extremo superior).**

### Impacto concreto
LIVE acepta apuestas **en el minuto exacto del m_max** que BT rechazaría.

Ejemplo: `sd_ud_leading` con `m_max=80`:
- BT solo dispara en minutos 55, 56, ..., 79 (NO 80)
- LIVE dispara en minutos 55, 56, ..., 79, **80** (SÍ dispara en 80)

Impacto: si el minuto del partido cuando el scraper captura el estado es exactamente `m_max`, LIVE dispara y BT no. Probabilidad baja por poll cada 60s pero real.

---

## DISCREPANCIA GLOBAL #2 (ALTO): `triggered=True` en BT — BT solo apuesta UNA vez por partido

### BT (sd_generators.py — todas las funciones)
```python
triggered = False
for row in rows:
    if triggered:
        break           # ← Sale al encontrar la primera señal válida
    ...
    triggered = True
    bets.append(...)
```
**BT apuesta exactamente UNA VEZ por partido por estrategia (first-trigger semantics).**

### LIVE (detect_betting_signals — csv_reader.py, líneas 4796-4802)
```python
if (match_id, sig["strategy"]) not in placed_bets_keys:
    ...
    signals.append(sig)
```
LIVE también tiene dedup por `(match_id, strategy)` via `placed_bets_keys` (cargado de placed_bets.csv). Esto **simula** el `triggered=True` del BT.

**Sin embargo:** si en paper trading se pone una apuesta y luego se resuelve o se elimina de placed_bets.csv, LIVE podría volver a disparar. BT nunca lo haría.

**Conclusión:** Funcionalmente equivalente mientras placed_bets.csv esté intacto, pero hay riesgo de doble disparo si se manipula placed_bets.csv.

---

## DISCREPANCIA GLOBAL #3 (ALTO): El generador BT usa superset gate, no el filtro exacto

Hay que aclarar qué es "BT" para este diagnóstico:

- **gen_<nombre>()** = superset gate, NO es lo que se valida en producción
- **_apply_sd_<nombre>(bets, cfg)** = filtro config, ESTE es el BT real comparable con LIVE

Los rangos del generador son más amplios a propósito. La comparación relevante es siempre `_apply_sd_*` vs bloque LIVE.

---

## Por estrategia: tabla de discrepancias detalladas

### 1. sd_ud_leading

| Condición | BT Generator (gen_ud_leading, línea 1442) | BT Filter (_apply_sd_ud_leading, línea 685) | LIVE (detect, línea 4901) | Config | Alineado |
|-----------|------------------------------------------|---------------------------------------------|---------------------------|--------|----------|
| Ventana minutos | `53 <= m <= 83` | `55 <= m < 80` | `55 <= m <= 80` | m_min=55, m_max=80 | PARCIAL (m_max: `<` vs `<=`) |
| Underdog source | `rows[0]` (primera fila) | — (heredado del generator) | `rows[:5]` (primeras 5 filas) | — | DIFERENTE |
| Gate de odds pre-match | `>= 1.5` (superset) | `ud_pre_odds >= 2.0` | Mismos _bh0 >= _sd_ud_pre | ud_min_pre_odds=2.0 | OK |
| max_lead | `<= 2` (superset) | `lead <= 1` | `_goal_diff <= 1` | max_lead=1 | OK |
| Odds actuales | `odds > 1.0` | — | `_ud_odds > 1.0` | — | OK |
| Condición "ganando" | `ud_team_winning` | — | `_ud_winning` | — | OK |
| Identificación underdog | `if first_home > first_away: ud_team='local'` else `ud_team='visitante'` | — | `if _bh0 > _ba0 and _bh0 >= _sd_ud_pre: ud='local'` elif `_ba0 >= _bh0 and _ba0 >= _sd_ud_pre: ud='visitante'` | — | DIFERENTE |

**Discrepancias críticas en sd_ud_leading:**

**D1 — Identificación del underdog (ALTO):**
- BT (gen, línea 1454): `if first_home > first_away: ud_team = 'local'` — el underdog es SIEMPRE el que tiene odds más altas, sin umbral mínimo en la primera fila.
- LIVE (línea 4915): `if _bh0 > _ba0 and _bh0 >= _sd_ud_pre: ud_team = 'local'` elif `elif _ba0 >= _bh0 and _ba0 >= _sd_ud_pre`

  El BT generator asigna underdog al team con mayor odds independientemente del umbral (el umbral se aplica después en `ud_pre_odds < 1.5`). En LIVE, la asignación del underdog ya incluye el check `>= _sd_ud_pre`. Esto significa:
  - Si `back_home = 2.3` y `back_away = 1.8`: BT → ud_team='local'. LIVE → ud_team='local' (OK, 2.3 >= 2.0).
  - Si `back_home = 1.6` y `back_away = 1.4`: BT → ud_team='local' (y luego falla el gate 1.5). LIVE → ud_team=None (ninguno >= 2.0).
  - Si `back_home = 1.8` y `back_away = 2.1`: BT → ud_team='visitante'. LIVE → `elif _ba0 >= _bh0 and _ba0 >= _sd_ud_pre` → `2.1 >= 1.8` es True y `2.1 >= 2.0` es True → ud_team='visitante' (OK).
  - Pero si `back_home = 2.1` y `back_away = 2.3`: BT → ud_team='visitante'. LIVE: `_bh0 > _ba0`? → `2.1 > 2.3` → False. `elif _ba0 >= _bh0 and _ba0 >= _sd_ud_pre`: `2.3 >= 2.1` True y `2.3 >= 2.0` True → ud_team='visitante' (OK).

  El único caso problemático es cuando ambas odds son >= 2.0 pero la condición elif falla. Esto parece raro en la práctica pero existe la posibilidad de que en el bucle `for _r in rows[:5]` la primera fila con odds válidas asigne incorrecto.

**D2 — Lookup del underdog: rows[0] (BT) vs rows[:5] (LIVE) (MEDIO):**
- BT usa `rows[0]` directamente (primera fila = pre-partido o inicio)
- LIVE busca en las primeras 5 filas hasta encontrar una con odds válidas (`_bh0 and _ba0 and _bh0 > 1 and _ba0 > 1`)

  Si `rows[0]` tiene odds nulas (inicio antes de que Betfair abra mercados), BT devuelve `None` y abandona. LIVE continúa en rows[1..4]. Esto hace que LIVE pueda identificar underdog en casos donde BT no puede → LIVE dispara, BT no.

**D3 — Caso Kayserispor-Trabzonspor (BT dispara min57, paper no captura):**
Probable explicación: LIVE tenía condición de minuto OK, pero placed_bets_keys ya contenía esa apuesta (bet anterior), o el partido estaba en estado no-live cuando se procesó. No es discrepancia de lógica — es de timing/estado.

---

### 2. sd_cs_one_goal

| Condición | BT Generator (gen_cs_one_goal, línea 1370) | BT Filter (_apply_sd_cs_one_goal, línea 651) | LIVE (detect, línea 4886) | Config | Alineado |
|-----------|---------------------------------------------|----------------------------------------------|---------------------------|--------|----------|
| Ventana minutos | `65 <= m <= 88` | `68 <= m < 85` | `68 <= m <= 85` | m_min=68, m_max=85 | PARCIAL (m_max: `<` vs `<=`) |
| Score válido | `(1,0)` o `(0,1)` | heredado del generator | `_total_goals == 1` y `(_gl,_gv) in ((1,0),(0,1))` | — | OK |
| Odds | `odds > 1.0` | — | `_cs_odds > 1.0` | — | OK |
| odds_max | ninguno en generator | ninguno en filter | ninguno en LIVE | — (config no tiene odds_max) | OK |

**Discrepancia en sd_cs_one_goal:**

**D4 — m_max semántica (ALTO) — m=85 excluido en BT, incluido en LIVE.**

**D5 — Caso Panaitolikos-Kifisia (sd_cs_one_goal en paper, no en BT) (ALTO):**

El generador BT usa la ventana `65 <= m <= 88` (superset), y el filtro aplica `68 <= m < 85`. Si el partido disparó en LIVE a m=85, BT lo habría rechazado (el filtro excluye m=85). LIVE lo acepta. Esta discrepancia de un minuto en el extremo superior podría explicar el caso.

Otra causa posible: el BT solo tiene datos históricos del partido hasta cierto punto. Si placed_bets.csv tiene la apuesta de ese partido bajo condiciones que en BT ya existía (minuto anterior donde se cumplían condiciones), y BT disparó en m=68 (primer minuto válido) pero el BT dataset del reconcile usó una versión anterior del CSV antes de que ese partido terminara.

---

### 3. sd_cs_close

| Condición | BT Generator (gen_cs_close, línea 1333) | BT Filter (_apply_sd_cs_close, línea 635) | LIVE (detect, línea 4869) | Config | Alineado |
|-----------|------------------------------------------|-------------------------------------------|---------------------------|--------|----------|
| Ventana minutos | `67 <= m <= 83` | `70 <= m < 80` | `70 <= m <= 80` | m_min=70, m_max=80 | PARCIAL (m_max: `<` vs `<=`) |
| Score válido | `(2,1)` o `(1,2)` | heredado | `(_gl,_gv) in ((2,1),(1,2))` | — | OK |
| Condición total_goals | implícito (2+1=3 o 1+2=3) | implícito | `_total_goals >= 2 and _goal_diff == 1` entonces check explícito | — | DIFERENTE |
| Odds | `odds > 1.0` | — | `_cs_odds > 1.0` | — | OK |

**Discrepancias en sd_cs_close:**

**D6 — Condición de score en LIVE tiene gate intermedia (BAJO):**
LIVE en línea 4874: `if _sd_m_min <= _m <= _sd_m_max and _total_goals >= 2 and _goal_diff == 1:`
y luego línea 4876: `if (_gl, _gv) in ((2, 1), (1, 2)):`

El check `_total_goals >= 2 and _goal_diff == 1` es redundante con el check `in ((2,1),(1,2))` que lo sigue, pero no causa false positives — solo hace la lógica más explícita. Semánticamente equivalente.

**D7 — m_max: m=80 excluido en BT, incluido en LIVE (ALTO).**

**D8 — Caso Panaitolikos-Kifisia (sd_cs_close a min73 en paper, no en BT):**
El minuto 73 está dentro del rango BT `70 <= m < 80` Y dentro del rango LIVE `70 <= m <= 80`. Si el BT no lo capturó, la causa probable es una de:
1. El CSV del partido en el BT no tenía esa fila (datos incompletos)
2. La primera fila válida del BT fue en un minuto posterior al 73 (unlikely si el CSV está completo)
3. Diferencia en cuándo las odds del CS estaban disponibles (datos de `back_rc_2_1` o `back_rc_1_2` nulos en BT pero presentes en LIVE)

---

### 4. sd_cs_big_lead

| Condición | BT Generator (gen_cs_big_lead, línea 1742) | BT Filter (_apply_sd_cs_big_lead, línea 817) | LIVE (detect, línea 4973) | Config | Alineado |
|-----------|---------------------------------------------|-----------------------------------------------|---------------------------|--------|----------|
| Ventana minutos | `67 <= m <= 88` | `70 <= m < 85` | `70 <= m <= 85` | m_min=70, m_max=85 | PARCIAL (m_max: `<` vs `<=`) |
| Scores válidos | `{(3,0),(0,3),(3,1),(1,3)}` | heredado | `((3,0),(0,3),(3,1),(1,3))` | — | OK |
| odds_max | `odds > 1.0` (sin max en generator) | `back_cs_odds <= 8.0` | `_cs_odds <= 8.0` | odds_max=8.0 | OK |

**Discrepancias en sd_cs_big_lead:**
**D9 — m_max: m=85 excluido en BT, incluido en LIVE (ALTO).**

---

### 5. sd_home_fav_leading

| Condición | BT Generator (gen_home_fav_leading, línea 1584) | BT Filter (_apply_sd_home_fav_leading, línea 743) | LIVE (detect, línea 4933) | Config | Alineado |
|-----------|--------------------------------------------------|---------------------------------------------------|---------------------------|--------|----------|
| Ventana minutos | `62 <= m <= 88` | `65 <= m < 85` | `65 <= m <= 85` | m_min=65, m_max=85 | PARCIAL (m_max: `<` vs `<=`) |
| Home es favorito | `first_home < first_away` (primera fila exacta) | `home_pre_odds <= fav_max` (filtro post-generator) | `_home_pre <= _sd_fav_max` (rows[:5]) | fav_max=2.5 | DIFERENTE |
| Home liderando | `gl > gv` | heredado | `_gl > _gv` (condición de entrada) | — | OK |
| max_lead | `lead <= 3` (superset en generator) | `lead <= 3` | `_goal_diff <= 3` | max_lead=3 | OK |
| Odds actuales | `odds > 1.0 and <= 10` | — | `_home_odds > 1.0` | — | DIFERENTE (LIVE no tiene odds_max=10) |
| Identificación pre-odds | `rows[0]` primera fila | `home_pre_odds` del dict del bet | `rows[:5]` primera fila válida | — | DIFERENTE |

**Discrepancias en sd_home_fav_leading:**

**D10 — Lookup de pre-match odds: rows[0] (BT generator) vs rows[:5] (LIVE) (MEDIO):**
Igual que en sd_ud_leading. Si rows[0] tiene odds nulas, BT genera ningún bet, LIVE puede encontrar odds en rows[1..4] y disparar.

**D11 — odds_max en live ausente (BAJO):**
BT generator (línea 1617) tiene `odds > 10` como gate (rechaza odds de 10+). El filtro `_apply_sd_home_fav_leading` NO aplica odds_max explícito. LIVE tampoco. Semánticamente: BT generator rechaza odds > 10 para la primera señal, pero el filtro post-generator no añade restricción adicional. LIVE no tiene restricción de odds_max. Mismatch teórico pero en práctica las odds de home favorito liderando difícilmente superan 10.

**D12 — m_max: m=85 excluido en BT, incluido en LIVE (ALTO).**

---

### 6. sd_under35_late

| Condición | BT Generator (gen_under35_late, línea 446) | BT Filter (_apply_sd_under35_late, línea 400) | LIVE (detect, línea 4823) | Config | Alineado |
|-----------|---------------------------------------------|-----------------------------------------------|---------------------------|--------|----------|
| Ventana minutos | `65 <= m <= 81` | `65 <= m < 78` | `65 <= m <= 78` | m_min=65, m_max=78 | PARCIAL (m_max: `<` vs `<=`) |
| goals_exact | `total_now in [2..4]` (superset) | `total_goals_trigger == 3` | `_total_goals == _sd_goals_exact` (3 de config) | goals_exact=3 | OK |
| xg_max | `xg_total > 3.0` (superset) | `xg_total < 2.0` | `_xg_total <= _sd_xg_max` (2.0 de config) | xg_max=2.0 | DIFERENTE (< vs <=) |
| xg None gate | `if xg_l is None and xg_v is None: continue` (ambos nulos = skip) | `xg_total < xg_max` via `(b.get('xg_total') or 0)` | `_xg_total is not None and _xg_total <= _sd_xg_max` | — | OK (LIVE gate explícita) |
| odds_max | `odds > 8` (superset) | `back_under35_odds <= 5.0` | ninguno | — | DIFERENTE |

**Discrepancias en sd_under35_late:**

**D13 — xg_max semántica: `<` (BT) vs `<=` (LIVE) (BAJO):**
- BT filter (línea 412): `(b.get('xg_total') or 0) < xgmax` → excluye exactamente xg=2.0
- LIVE (línea 4833): `_xg_total <= _sd_xg_max` → incluye xg=2.0
- Impacto real mínimo (probabilidad de xG exactamente en 2.0 es muy baja).

**D14 — odds_max en LIVE ausente (CRÍTICO):**
- BT filter (línea 408): `omax = cfg.get('odds_max', 5.0)` y `omin <= (b.get('back_under35_odds') or 0) <= omax` → filtra odds > 5.0
- LIVE (líneas 4830-4833): solo `_sd_odds and _sd_odds > 1.0` — NO hay odds_max ni odds_min
- El config en `cartera_config.json` para `sd_under35_late` NO tiene `odds_min` ni `odds_max`.
- El BT filter usa los defaults del código (`odds_min=1.1`, `odds_max=5.0`) que NO están en el config.
- LIVE lo dispara con cualquier odds > 1.0. BT rechaza odds > 5.0.

**Esta es la discrepancia más grave de sd_under35_late.** LIVE puede disparar con odds de 6, 7, 8 en under 3.5 (donde xG bajo indica partido contenido pero los odds de under 3.5 deberían ser bajos). Si las odds son altas con 3 goles, algo ha cambiado.

**D15 — m_max: m=78 excluido en BT, incluido en LIVE (ALTO).**

---

### 7. sd_over25_2goal

| Condición | BT Generator (gen_over25_2goal, línea 211) | BT Filter (_apply_sd_over25_2goal, línea 347) | LIVE (detect, línea 4805) | Config | Alineado |
|-----------|---------------------------------------------|------------------------------------------------|---------------------------|--------|----------|
| Ventana minutos | `55 <= m <= 81` | `55 <= m < 78` | `55 <= m <= 78` | m_min=55, m_max=78 | PARCIAL (m_max: `<` vs `<=`) |
| goal_diff_min | `goal_diff >= 2` | `goal_diff >= gd` (2 del config) | `_goal_diff >= _sd_gd_min` (2) | goal_diff_min=2 | OK |
| sot_total_min | `sot_total >= 3` | `sot_total >= smin` (3) | `_sot_total >= _sd_sot_min` (3) | sot_total_min=3 | OK |
| odds_min | ninguno (generator) | `odds_min=1.5` | `_sd_odds_min <= _sd_odds` (1.5) | odds_min=1.5 | OK |
| odds_max | `odds > 10` rechaza | `odds_max=8.0` | `_sd_odds <= _sd_odds_max` (8.0) | odds_max=8.0 | OK |
| just_reached_2goal_lead | skip si gol acababa de entrar (línea 231-236) | NO existe este gate | NO existe este gate | — | DIFERENTE |
| xg_min | ninguno en generator | `xg_min=0` (default, no filtra) | ninguno en LIVE | — | OK |

**Discrepancias en sd_over25_2goal:**

**D16 — Goal transition gate ausente en LIVE (MEDIO):**
BT generator (líneas 230-236): cuando se acaba de establecer la ventaja de 2 goles (prev_goal_diff < 2, ahora >= 2), **salta esa fila** porque las odds de over 2.5 todavía reflejan el estado pre-gol y estarán desactualizadas. Este es un gate de calidad de datos.

LIVE no tiene este gate. Cuando el scraper detecta un cambio en el marcador y la señal se emite en el poll inmediatamente posterior, puede estar usando odds obsoletas (el mercado de Betfair tarda unos segundos en actualizarse tras un gol).

En la práctica, LIVE tiene una ventaja: el poll es cada 60s, así que para el momento en que se procesa la nueva fila, es probable que las odds ya estén actualizadas. Pero no está garantizado.

**D17 — m_max: m=78 excluido en BT, incluido en LIVE (ALTO).**

---

### 8. sd_cs_20

| Condición | BT Generator (gen_cs_20, línea 1707) | BT Filter (_apply_sd_cs_20, línea 799) | LIVE (detect, línea 4957) | Config | Alineado |
|-----------|--------------------------------------|----------------------------------------|---------------------------|--------|----------|
| Ventana minutos | `72 <= m <= 92` | `75 <= m < 90` | `75 <= m <= 90` | m_min=75, m_max=90 | PARCIAL (m_max: `<` vs `<=`) |
| Scores válidos | `(2,0)` o `(0,2)` | heredado | `((2,0),(0,2))` | — | OK |
| odds_max | ninguno en generator (odds > 1.0 implícito) | `back_cs_odds <= 10.0` | `_cs_odds <= 10.0` | odds_max=10.0 | OK |

**Discrepancias en sd_cs_20:**
**D18 — m_max: m=90 incluido en LIVE pero excluido en BT (ALTO).**

Nota especial: el BT generator usa `72 <= m <= 92` (superset) pero el filtro usa `75 <= m < 90`. LIVE usa `75 <= m <= 90`. El minuto 90 exacto (tiempo reglamentario finalizado) puede estar presente en el CSV si el partido va a la prórroga. Si el partido termina en 90' exacto, BT no lo toma (< 90) pero LIVE sí (<=90).

---

## Resumen de discrepancias por severidad

### CRÍTICO — LIVE dispara cuando BT no debería (o viceversa por condición incorrecta)

| ID | Estrategia | Descripción | Efecto |
|----|-----------|-------------|--------|
| D14 | sd_under35_late | LIVE no tiene odds_max (BT filter usa default 5.0). Config tampoco lo define. | LIVE dispara con odds de under 3.5 hasta infinito. BT rechaza > 5.0. |

### ALTO — Parámetro distinto que causa divergencia sistemática

| ID | Estrategia | Descripción | Efecto |
|----|-----------|-------------|--------|
| D1 (global) | TODAS (8) | m_max: BT usa `< mx` (exclusivo), LIVE usa `<= m_max` (inclusivo) | LIVE dispara en el minuto exacto del límite superior, BT no |
| D2 | sd_ud_leading | rows[0] vs rows[:5] para identificar underdog pre-match | LIVE puede disparar en partidos donde rows[0] tiene odds nulas |
| D10 | sd_home_fav_leading | rows[0] vs rows[:5] para identificar favorito pre-match | Igual que D2 |
| D15 | sd_under35_late | m_max semántica | m=78 incluido en LIVE |
| D17 | sd_over25_2goal | m_max semántica | m=78 incluido en LIVE |
| D9 | sd_cs_big_lead | m_max semántica | m=85 incluido en LIVE |
| D12 | sd_home_fav_leading | m_max semántica | m=85 incluido en LIVE |
| D7 | sd_cs_close | m_max semántica | m=80 incluido en LIVE |
| D4 | sd_cs_one_goal | m_max semántica | m=85 incluido en LIVE |
| D18 | sd_cs_20 | m_max semántica | m=90 incluido en LIVE |

### MEDIO — Gap de timing o condición secundaria distinta

| ID | Estrategia | Descripción |
|----|-----------|-------------|
| D16 | sd_over25_2goal | BT salta fila de transición de gol (odds obsoletas); LIVE no |
| D2/D10 | sd_ud_leading, sd_home_fav_leading | Búsqueda de pre-match odds en 5 filas vs 1 |

### BAJO — Discrepancia teórica, impacto práctico mínimo

| ID | Estrategia | Descripción |
|----|-----------|-------------|
| D13 | sd_under35_late | xg_max: `< 2.0` (BT) vs `<= 2.0` (LIVE). Solo afecta si xG exactamente = 2.0 |
| D11 | sd_home_fav_leading | LIVE no tiene odds_max=10 de BT generator (pero el config tampoco lo tiene) |
| D6 | sd_cs_close | Gate intermedia redundante en LIVE (no causa false positives) |

---

## Caso específico: Eyupspor-Kocaelispor (xg_underperformance a min38 en BT, min58 en paper)

Esta es una estrategia CORE (no SD), así que el análisis es diferente — usa el helper compartido `_detect_xg_trigger`.

**Causa probable:** El helper `_detect_xg_trigger` tiene una lógica de persistencia de señal. En BT, itera todas las filas y registra el primer minuto donde se cumplen las condiciones. En LIVE, solo ve la última fila. Si la señal se cumplió primero en min38 en BT (primera fila con condición válida), en LIVE el poll de min38 puede no haberla capturado si el ciclo de paper trading de 60s no estaba activo en ese momento exacto, o si `min_duration` no había madurado aún.

Además, BT registra el minuto de la primera fila de la señal. LIVE registra el minuto cuando el poll captura la señal madura. Si la señal necesita `min_duration=3` minutos para madurar:
- BT: trigger a min38 → primera fila válida = min38 (no tiene concepto de maduración para el timestamp)
- LIVE: trigger se detecta en min38, pero solo se coloca la apuesta cuando la señal ha estado activa `min_duration+1=4 mins` → la apuesta se coloca ~min42 o cuando el siguiente poll la confirma. El minuto registrado en LIVE es el del momento de la colocación.

La diferencia de 20 minutos (38 vs 58) es inusualmente grande para esto. Causas alternativas:
1. El partido tuvo una interrupción de scraping y LIVE perdió los primeros ciclos
2. La señal desapareció (condición dejó de cumplirse) y reapareció en min58
3. La señal requería condiciones adicionales (momentum, odds drift) que se cumplieron más tarde

Sin ver el CSV del partido, no se puede determinar con precisión.

---

## Caso específico: Panaitolikos-Kifisia (sd_ud_leading min59, sd_cs_close min73 en paper, no en BT)

**sd_ud_leading a min59 — LIVE dispara, BT no:**
Hipótesis principal: **D2** (rows[:5] vs rows[0]). Si la primera fila del CSV tiene odds nulas (inicio del scraping después del pitido inicial o antes de que Betfair actualizara las cuotas), BT generator evalúa `first_home = None` y retorna vacío. LIVE busca en las 5 primeras filas y puede encontrar odds válidas en rows[2] o rows[3].

**sd_cs_close a min73 — LIVE dispara, BT no:**
Hipótesis: el CSV histórico del partido Panaitolikos-Kifisia puede no tener datos de `back_rc_2_1` o `back_rc_1_2` en las filas alrededor de min73, o el CSV está incompleto. LIVE tiene datos en tiempo real que el CSV histórico no capturó (posibles gaps en el scraping histórico).

---

## Caso específico: Kayserispor-Trabzonspor (sd_ud_leading BT min57, paper no captura)

**LIVE no disparó, BT sí:**
Hipótesis: el match ya tenía una apuesta en `placed_bets_keys` cuando LIVE evaluó la señal (dedup), o el partido no aparecía como "live" en games.csv en el momento del poll, o la señal no maduró (`min_duration`=1 debería ser inmediato, pero si la señal solo se cumplía en una sola fila de 60s y el siguiente poll ya estaba fuera de la ventana de minutos).

---

## Resumen final: qué corregir (diagnóstico, no fix)

Las correcciones requieren decisión del usuario porque implican un trade-off:

1. **D1 (global, ALTO) — m_max `<` vs `<=`:** Hay que elegir la semántica canónica. Si el diseño del BT filter (exclusivo) es el correcto, LIVE debe cambiarse de `<= m_max` a `< m_max`. Si el config define m_max como "inclusive last minute", el BT filter es el que está mal.

2. **D14 (CRÍTICO) — sd_under35_late sin odds_max en LIVE:** Añadir `odds_max` al config de `sd_under35_late` (o añadir un default en el código LIVE que refleje lo que el BT filter usa: 5.0). También añadir `odds_min` (BT filter default: 1.1).

3. **D2/D10 (ALTO) — rows[0] vs rows[:5]:** Alinear la estrategia de lookup de pre-match odds. La opción rows[:5] de LIVE es más robusta para producción, pero introduce una discrepancia con BT. O bien actualizar el generator BT para usar la misma lógica de rows[:5], o cambiar LIVE a rows[0] con None-check.

4. **D16 (MEDIO) — sd_over25_2goal goal-transition gate:** El BT tiene lógica para evitar odds obsoletas post-gol. LIVE no. Este gate es difícil de implementar en LIVE (requeriría recordar el score anterior). Documentar como discrepancia conocida aceptable.
