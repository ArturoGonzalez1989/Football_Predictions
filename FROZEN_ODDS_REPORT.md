# REPORTE: Cuotas Over/Under Congeladas

## Resumen Ejecutivo

**Problema confirmado**: Las cuotas Over/Under permanecen congeladas en valores pre-partido durante el juego en vivo, mientras que las cuotas Match Odds (1X2) se actualizan correctamente.

### Impacto

- **31 partidos corruptos** de 232 totales = **13.4%**
- **1 apuesta Over** de 8 totales fue impactada en `placed_bets.csv` (FC Seoul-Hiroshima)
- **Todas las apuestas Over de Goal Clustering** usan cuotas congeladas en el simulador de cartera

### Caso Crítico: Galatasaray - Juventus

**Minuto 32, Score 1-2 (3 goles totales)**

```
back_home:   2.46 → 1.17 → 7.2  ✓ Se mueve correctamente
back_over35: 3.25 (CONGELADO)   ✗ Debería estar ~1.20-1.30
back_over45: 6.40 (CONGELADO)   ✗ Debería estar ~1.20-1.30
```

**Cuota usada en cartera**: Over 3.5 @ 3.25 (valor pre-partido 0-0)
**Cuota real esperada**: ~1.25 (3 goles ya, solo necesita 1 más)
**P/L simulado**: +21.38 EUR
**P/L real estimado**: +2.50 EUR

**Error de P/L**: ~+19 EUR de fantasía

---

## Análisis Detallado

### Partidos con Cuotas Congeladas

**Total**: 31 partidos (13.4%)

**Patrón**: Las columnas congeladas varían por partido. No todos tienen todas las líneas congeladas:

- **Parcial (1-3 columnas)**: 23 partidos
  - Ejemplo: Arsenal-Wigan → `back_over15`, `back_under15`, `back_over35`, `back_under35`, `back_over45`
  - Ejemplo: FC Seoul-Hiroshima → `back_over05`, `back_under05`, `back_over35`

- **Extenso (6-8 columnas)**: 8 partidos
  - Granada-Valladolid: 8 columnas congeladas
  - Barnet-Cheltenham: 6 columnas congeladas
  - Puebla-Pumas UNAM: 6 columnas congeladas

**Lista completa**: Ver `corrupted_matches.txt`

---

### Apuestas Over/Under Realizadas (placed_bets.csv)

**Total**: 8 apuestas Over de 28 totales (28.6%)

**Por estrategia**:
- Goal Clustering (V2): 7 bets
- xG Underperformance (V3): 1 bet

**Análisis de varianza de cuotas usadas**:

| ID | Partido | Over Line | Varianza | Valores Únicos | Estado |
|----|---------|-----------|----------|----------------|--------|
| 7 | NK Bravo - NK Aluminij | 2.5 | 0.380 | 50 | ✅ OK |
| 8 | Kasimpasa - Fatih | 3.5 | (Goal Clustering manual) | - | ✅ OK |
| 11 | Sociedad B - Málaga | 3.5 | 1.023 | 50 | ✅ OK |
| 12 | FC Machida - Chengdu | 2.5 | 0.008 | 6 | ⚠️ SOSPECHOSO |
| 13 | FC Seoul - Hiroshima | 2.5 | 0.009 | 4 | ⚠️ SOSPECHOSO |
| 15 | Al-Sadd - Al-Ittihad | 2.5 | 0.039 | 6 | ⚠️ SOSPECHOSO |
| 16 | Galatasaray - Juventus | 3.5 | 0.018 | 3 | ⚠️ SOSPECHOSO |
| 33 | Mónaco - PSG | 4.5 | 0.988 | 37 | ✅ OK |

**Apuestas en partidos técnicamente "congelados" (varianza=0)**:
- FC Seoul-Hiroshima: `back_over05`, `back_under05`, `back_over35` congeladas, pero usó `back_over25` (var=0.009)

**Apuestas con varianza extremadamente baja (<0.05)**:
- **4 de 8** apuestas Over tienen datos casi estancados (var < 0.05)

---

## Impacto en Backtests

### Goal Clustering (V2) - Cartera

El backtest de Goal Clustering analiza **todos los partidos históricos** que disparan la señal (2+ goles en ventana de tiempo).

**Problema**: Si el partido tiene cuotas Over congeladas, el P/L calculado es **fantasía**.

**Ejemplo real** (Galatasaray-Juventus):
- Backtest: +21.38 EUR
- Real estimado: +2.50 EUR
- **Diferencia**: ~+19 EUR de error

**Escala del problema**:
- 31 partidos corruptos de ~232 partidos históricos
- Si Goal Clustering disparó en 10-15 de estos partidos corruptos
- Error estimado total: **~150-300 EUR en P/L fantasma**

---

## Soluciones Propuestas

### Opción 1: Borrar Partidos Corruptos ❌

**Acción**: Eliminar los 31 CSVs corruptos

**Ventajas**:
- Limpieza total
- No requiere cambios en código

**Desventajas**:
- **Pérdida de datos**: Muchos de estos partidos tienen datos Match Odds (1X2) válidos
- Solo 13.4% de partidos → se pierde muestra histórica
- Estrategias como Odds Drift, Back Empate, Momentum xG **no se verían afectadas** (usan Match Odds)

### Opción 2: Marcar Partidos como "No Over/Under" ✅ RECOMENDADO

**Acción**: Crear archivo `corrupted_over_matches.txt` con la lista de match_ids corruptos

**Cambios en código**:

1. **csv_reader.py** - Goal Clustering backtest:
   ```python
   # Load corrupted list at module level
   CORRUPTED_OVER_MATCHES = set()
   corrupted_file = Path(__file__).parent.parent.parent / "corrupted_over_matches.txt"
   if corrupted_file.exists():
       with open(corrupted_file, "r") as f:
           CORRUPTED_OVER_MATCHES = {line.strip() for line in f if line.strip()}

   # In analyze_strategy_goal_clustering():
   for csv_file in csv_files:
       match_id = extract_match_id_from_filename(csv_file.name)
       if match_id in CORRUPTED_OVER_MATCHES:
           continue  # Skip this match
   ```

2. **csv_reader.py** - Live signal detection:
   ```python
   # In detect_signals() - Goal Clustering section:
   if match_id in CORRUPTED_OVER_MATCHES:
       continue  # Skip Over signal for this match
   ```

**Ventajas**:
- Mantiene datos históricos para estrategias Match Odds (1X2)
- Solo excluye Over/Under en partidos problemáticos
- Fácil de implementar
- Se puede revertir (quitar del archivo) si se obtienen datos correctos

**Desventajas**:
- Requiere mantener lista de partidos corruptos

### Opción 3: Validación Dinámica de Varianza ⚠️

**Acción**: En tiempo real, calcular varianza de la cuota Over antes de usar

**Lógica**:
```python
def is_over_odds_valid(df, over_col):
    values = df[over_col].dropna()
    if len(values) < 5:
        return False
    # Require minimum variance (odds must move)
    return values.std() > 0.05 and values.nunique() > 3
```

**Ventajas**:
- Detección automática
- No requiere mantener listas

**Desventajas**:
- Más complejo
- Puede rechazar partidos válidos con mercados poco líquidos
- No resuelve backtests históricos (ya están guardados)

---

## Recomendación Final

**Implementar Opción 2**: Marcar partidos como "No Over/Under"

**Pasos**:
1. Extraer match_ids de los 31 partidos corruptos
2. Crear `betfair_scraper/corrupted_over_matches.txt`
3. Modificar `csv_reader.py` para cargar y usar esta lista
4. Volver a generar backtest de Goal Clustering
5. Verificar que P/L de cartera sea más realista

**Beneficio esperado**:
- Reducir ~150-300 EUR de P/L fantasma en backtest Goal Clustering
- Prevenir señales Over basadas en cuotas congeladas
- Mantener integridad de datos para otras estrategias

---

## Próximos Pasos

1. ¿Aprobar Opción 2?
2. Generar `corrupted_over_matches.txt`
3. Implementar filtro en csv_reader.py
4. Re-ejecutar backtest Goal Clustering
5. Comparar métricas antes/después

