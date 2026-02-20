# Filtro de Riesgo Tiempo + Marcador en Señales Live

## ✅ Cambio Implementado

**Objetivo**: Bloquear completamente señales de **Momentum xG** y **Odds Drift** que tengan riesgo tiempo/marcador (`risk_level != "none"`), pero mantener el selector de riesgo en el backtest de cartera.

---

## 📋 Modificaciones en csv_reader.py

### 1. Señales Live - Odds Drift Contrarian (Línea ~2569)

**Antes:**
```python
if (match_id, signal["strategy"]) not in placed_bets_keys:
    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
    if conflict:
        signal["blocked"] = conflict
    else:
        signals.append(signal)
        _log_signal_to_csv(signal)
        _register_outcome(match_id, signal["recommendation"], match_outcomes)
```

**Después:**
```python
if (match_id, signal["strategy"]) not in placed_bets_keys:
    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
    if conflict:
        signal["blocked"] = conflict
    # Block signals with time/score risk
    elif risk_info["risk_level"] != "none":
        signal["blocked"] = f"Riesgo {risk_info['risk_level']}: {risk_info['risk_reason']}"
    else:
        signals.append(signal)
        _log_signal_to_csv(signal)
        _register_outcome(match_id, signal["recommendation"], match_outcomes)
```

---

### 2. Señales Live - Momentum Dominante x xG (Línea ~2829)

**Antes:**
```python
if (match_id, signal["strategy"]) not in placed_bets_keys:
    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
    if conflict:
        signal["blocked"] = conflict
    else:
        signals.append(signal)
        _log_signal_to_csv(signal)
        _register_outcome(match_id, signal["recommendation"], match_outcomes)
```

**Después:**
```python
if (match_id, signal["strategy"]) not in placed_bets_keys:
    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
    if conflict:
        signal["blocked"] = conflict
    # Block signals with time/score risk
    elif risk_info["risk_level"] != "none":
        signal["blocked"] = f"Riesgo {risk_info['risk_level']}: {risk_info['risk_reason']}"
    else:
        signals.append(signal)
        _log_signal_to_csv(signal)
        _register_outcome(match_id, signal["recommendation"], match_outcomes)
```

---

## 🎯 Criterios de Bloqueo

Las señales se bloquean si el equipo apostado **va perdiendo** en el momento del trigger:

### 🔴 Alto Riesgo (BLOQUEADO):
- Quedan **<20 min** y el equipo va perdiendo por **2+ goles**
- Quedan **<15 min** y el equipo va perdiendo por **1 gol**

### 🟠 Riesgo Medio (BLOQUEADO):
- Quedan **<25 min** y el equipo va perdiendo por **2+ goles**
- Quedan **<20 min** y el equipo va perdiendo por **1 gol**

### 🟢 Sin Riesgo (PERMITIDO):
- El equipo va **ganando o empatando**
- O quedan suficientes minutos para remontar

---

## 📊 Impacto Esperado

### Datos Históricos (de tu backtest):

**Antes del filtro:**
- Total apuestas: 162
- Con riesgo: 2 (1.2%)
  - Riesgo medio: 1 apuesta → 0% WR, -10 EUR
  - Alto riesgo: 1 apuesta → 0% WR, -10 EUR
- Sin riesgo: 160 (98.8%)
  - 69.4% WR, +1245 EUR, +77.8% ROI

**Después del filtro:**
- Total señales: 160 (las 2 con riesgo serán bloqueadas)
- Con riesgo: 0 (bloqueadas automáticamente)
- Sin riesgo: 160
  - 69.4% WR, +1245 EUR, +77.8% ROI

**Beneficio:**
- Evitar -20 EUR en pérdidas futuras
- Mantener 69.4% WR limpio
- Reducir estrés mental (no apostar a remontadas improbables)

---

## ⚙️ Comportamiento

### ✅ Señales Live (detect_signals)
- **BLOQUEADAS** si `risk_level != "none"`
- Aparecerán en el dashboard con estado `blocked` y razón del bloqueo
- No se registrarán en `signals_log.csv`
- No se añadirán a `placed_bets.csv`

### ✅ Backtest Cartera (InsightsView)
- **SIN CAMBIOS** - Mantiene selector de riesgo
- El análisis "Riesgo Tiempo + Marcador" sigue mostrando distribución
- Puedes filtrar por riesgo usando el selector existente
- Permite analizar históricamente el impacto del riesgo

---

## 🔍 Verificación

### Sintaxis Python
```bash
python -m py_compile betfair_scraper/dashboard/backend/utils/csv_reader.py
# ✓ Sintaxis válida
```

### Testing Manual
1. Reiniciar dashboard
2. Esperar señal de Momentum xG u Odds Drift donde:
   - El equipo dominante va perdiendo
   - Quedan <25 minutos
3. Verificar que la señal aparece como `blocked` con mensaje de riesgo

---

## 📁 Archivo Modificado

- ✅ `betfair_scraper/dashboard/backend/utils/csv_reader.py`
  - Línea ~2572: Filtro en Odds Drift
  - Línea ~2832: Filtro en Momentum xG

---

## 💡 Notas

- **NO afecta a otras estrategias**: Back Empate, Goal Clustering, xG Underperformance, Pressure Cooker no tienen filtro de riesgo (no aplica)
- **Solo señales live**: El backtest sigue mostrando todas las apuestas para análisis histórico
- **Mensaje descriptivo**: Las señales bloqueadas muestran exactamente por qué fueron rechazadas (ej: "Riesgo medium: RIESGO MEDIO: Quedan 18 min para remontar 1 gol. Tiempo limitado.")
