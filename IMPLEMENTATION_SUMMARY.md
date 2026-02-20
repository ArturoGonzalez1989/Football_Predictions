# Implementación: Filtro de Cuotas Over/Under Congeladas

## ✅ Completado

### 1. Identificación de Partidos Corruptos

**Script**: `find_frozen_odds.py`
- Escanea todos los CSVs históricos
- Detecta columnas Over/Under con varianza = 0 (congeladas)
- **Resultado**: 31 partidos corruptos (13.4% del total)

**Archivo generado**: `corrupted_matches.txt`
- Lista completa de los 31 partidos con cuotas congeladas

### 2. Extracción de Match IDs

**Script**: `extract_match_ids.py`
- Extrae los match_ids de los 31 partidos corruptos
- **Archivo generado**: `betfair_scraper/corrupted_over_matches.txt`
- Formato: un match_id por línea, con comentarios al inicio

### 3. Modificaciones en csv_reader.py

**Ubicación**: `betfair_scraper/dashboard/backend/utils/csv_reader.py`

#### 3.1. Carga de Lista (Líneas 12-22)
```python
# Load corrupted Over/Under matches list
CORRUPTED_OVER_MATCHES = set()
_corrupted_file = BASE_DIR / "corrupted_over_matches.txt"
if _corrupted_file.exists():
    with open(_corrupted_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                CORRUPTED_OVER_MATCHES.add(line)
```

#### 3.2. Backtest Goal Clustering (Línea ~3077)
```python
for match_data in finished:
    results["total_matches"] += 1
    match_id = match_data["match_id"]
    match_name = match_data["name"]
    csv_path = _resolve_csv_path(match_id)

    # Skip matches with corrupted Over/Under odds
    if match_id in CORRUPTED_OVER_MATCHES:
        continue
```

#### 3.3. Backtest xG Underperformance (Línea ~1653)
```python
for match in finished_matches:
    # Skip matches with corrupted Over/Under odds
    if match["match_id"] in CORRUPTED_OVER_MATCHES:
        continue
```

#### 3.4. Señales Live - Goal Clustering (Línea ~2564)
```python
# === STRATEGY 4: Goal Clustering (version-specific) ===
# Skip if match has corrupted Over/Under odds
if match_id not in CORRUPTED_OVER_MATCHES and clustering_ver != "off" and len(rows) >= 2 and 15 <= minuto <= 80:
```

#### 3.5. Señales Live - xG Underperformance (Línea ~2391)
```python
# === STRATEGY 2: xG Underperformance (version-specific) ===
# Skip if match has corrupted Over/Under odds
if match_id not in CORRUPTED_OVER_MATCHES and xg_ver != "off" and minuto >= 15 and xg_local is not None and xg_visitante is not None:
```

#### 3.6. Señales Live - Pressure Cooker (Línea ~2656)
```python
# === STRATEGY 5: Pressure Cooker (version-specific) ===
# Skip if match has corrupted Over/Under odds
if match_id not in CORRUPTED_OVER_MATCHES and pressure_ver != "off" and (65 <= minuto <= 75 and is_draw and has_goals):
```

---

## Estrategias Protegidas

### ✅ Con Filtro (Usan Over/Under)
1. **Goal Clustering (V2/V3)** - Backtest + Live
2. **xG Underperformance (Base/V2/V3)** - Backtest + Live
3. **Pressure Cooker** - Live

### ⚪ Sin Filtro (NO usan Over/Under)
1. **Back Empate 0-0** - Match Odds (DRAW)
2. **Odds Drift Contrarian** - Match Odds (HOME/AWAY)
3. **Momentum xG (V1/V2)** - Match Odds (HOME/AWAY)

---

## Impacto Esperado

### Antes
- **Goal Clustering backtest**: ~300-400 EUR P/L (con fantasía)
- **Señales Over**: 4 de 8 con cuotas sospechosas (varianza < 0.05)

### Después
- **Goal Clustering backtest**: ~100-200 EUR P/L (real estimado)
- **Señales Over**: Solo partidos con cuotas dinámicas válidas
- **31 partidos excluidos** de estrategias Over/Under
- **Datos Match Odds intactos** para otras estrategias

---

## Verificación

### ✅ Sintaxis Python
```bash
python -m py_compile betfair_scraper/dashboard/backend/utils/csv_reader.py
# ✓ Sintaxis válida
```

### ✅ Archivos Creados
- `betfair_scraper/corrupted_over_matches.txt` (31 match IDs)
- `FROZEN_ODDS_REPORT.md` (análisis detallado)
- `IMPLEMENTATION_SUMMARY.md` (este archivo)

---

## Próximos Pasos

1. **Reiniciar dashboard** para cargar los cambios
2. **Verificar backtest Goal Clustering** en Insights → Strategies → Cartera
   - Comparar métricas antes/después
   - Esperado: Reducción en P/L total pero métricas más realistas
3. **Monitorear señales en vivo**
   - Verificar que NO se generen señales Over para partidos en `corrupted_over_matches.txt`
4. **Actualizar lista si es necesario**
   - Si nuevos partidos muestran cuotas congeladas, añadir a `corrupted_over_matches.txt`

---

## Mantenimiento

### Añadir un partido a la lista de corruptos
1. Editar `betfair_scraper/corrupted_over_matches.txt`
2. Añadir una línea con el match_id
3. Reiniciar el dashboard

### Quitar un partido (si se obtienen datos correctos)
1. Editar `betfair_scraper/corrupted_over_matches.txt`
2. Borrar o comentar la línea con `#`
3. Reiniciar el dashboard

### Verificar si un partido tiene cuotas congeladas
```bash
python find_frozen_odds.py
# Genera corrupted_matches.txt con la lista actualizada
```

---

## Archivos Modificados

1. ✅ `betfair_scraper/corrupted_over_matches.txt` (nuevo)
2. ✅ `betfair_scraper/dashboard/backend/utils/csv_reader.py` (modificado)
3. ✅ `FROZEN_ODDS_REPORT.md` (nuevo - documentación)
4. ✅ `IMPLEMENTATION_SUMMARY.md` (nuevo - este archivo)

---

## Código de Verificación Rápida

Para verificar que el filtro está activo:

```python
# En Python console del dashboard
from betfair_scraper.dashboard.backend.utils.csv_reader import CORRUPTED_OVER_MATCHES
print(f"Partidos corruptos cargados: {len(CORRUPTED_OVER_MATCHES)}")
print(f"Ejemplo: {list(CORRUPTED_OVER_MATCHES)[:5]}")
# Esperado: 31 partidos, ej: ['35172745', '35172770', '35172773', '35215933', '35215939']
```
