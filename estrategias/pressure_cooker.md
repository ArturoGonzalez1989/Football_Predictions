# Estrategia: Pressure Cooker - Back Over en empates con goles (min 65-75)

## Resumen Ejecutivo

| Metrica | Valor |
|---|---|
| **Triggers** | 16 (empates 1-1+ con cuotas disponibles) |
| **Win Rate** | 81.2% |
| **ROI neto** | +81.9% |
| **P/L (stake 10 EUR)** | +131.01 EUR |
| **Max Drawdown** | 20 EUR (2 perdidas) |
| **Avg odds** | 2.41 |

**Estado**: Backtest sobre 151 partidos finalizados (~3 dias de datos). Muestra prometedora pero necesita mas datos para confirmar.

---

## 1. Concepto

Cuando un partido esta empatado **con goles** (1-1, 2-2, etc.) entre el minuto 65 y 75, apostar a **Back Over** en la linea actual (total_goles + 0.5).

**Logica**: Si ambos equipos ya han marcado, esta demostrado que ambos pueden generar gol. La inercia ofensiva continua en la recta final del partido, donde los entrenadores hacen cambios ofensivos y los equipos se abren buscando la victoria.

**CLAVE**: Excluir empates 0-0. Un 0-0 al minuto 65 indica equipos que NO saben o NO pueden marcar. Apostar Over ahi destruye dinero (WR 50%, ROI -32.5%).

---

## 2. Origen

Propuesta inicial: Gemini sugiere "Lay The Draw Pressure Cooker" con filtros de momentum (SoT, corners, dangerous attacks).

**Descubrimiento tras backtest**: Los filtros de momentum NO mejoran los resultados. Lo que realmente predice si habra mas goles es el **marcador**: empates con goles vs empates sin goles.

El concepto se reconvirtio de Lay The Draw (requiere trading/cash-out) a **Back Over** (compatible con apuesta simple, esperar al final).

---

## 3. Reglas de Entrada

| Condicion | Valor |
|---|---|
| **Minuto** | 65 a 75 |
| **Marcador** | Empate con goles: 1-1, 2-2, 3-3... (**nunca 0-0**) |
| **Apuesta** | Back Over [total_goles_actual + 0.5] |
| **Cuota minima** | > 1.0 (cualquier cuota disponible) |
| **Frecuencia** | 1 trigger maximo por partido |

### Filtros descartados (no aportan edge)

| Filtro probado | N | WR | ROI | Conclusion |
|---|---|---|---|---|
| SoT delta >= 2 + Corners >= 2 | 4 | 50% | -27.5% | Demasiado restrictivo, filtra buenos partidos |
| DA desequilibrado >70% | 0 | - | - | Sin datos suficientes |
| xG delta >= 0.5 | 1 | 100% | +108% | Muestra insuficiente |
| **Score != 0-0 (elegido)** | **16** | **81.2%** | **+81.9%** | **Simple y efectivo** |

---

## 4. Resultados del Backtest

### Dataset
- 151 partidos finalizados (de 189 CSVs scrapeados)
- Periodo: 13-16 Febrero 2026
- 56 partidos con empate entre min 65-75
- 28 con cuotas Over disponibles (50% cobertura)

### Por marcador al trigger

| Marcador | N | WR | P/L | ROI | Avg Odds |
|---|---|---|---|---|---|
| 0-0 | 12 | 50% | -39.01 | **-32.5%** | 1.42 |
| **1-1** | **10** | **90%** | **+73.97** | **+74.0%** | **1.95** |
| **2-2+** | **6** | **67%** | **+57.04** | **+95.1%** | **3.19** |

### Combinaciones de filtros sobre empates 1-1+

| Filtro | N | WR | P/L | ROI |
|---|---|---|---|---|
| Solo 1-1+ (base) | 16 | 81.2% | +131.01 | +81.9% |
| 1-1+ y Shots>=2 | 10 | 90.0% | +109.59 | +109.6% |
| 1-1+ y SoT>=1 | 11 | 81.8% | +99.59 | +90.5% |
| 1-1+ y Corners>=1 | 12 | 83.3% | +109.75 | +91.5% |
| 1-1+ y Odds>=1.5 | 14 | 78.6% | +123.98 | +88.6% |

### Detalle de perdidas en empates 1-1+

Solo 3 perdidas (1 es dato corrupto):

1. **Kifisia-OFI** (2-2 → 2-2): Partido griego menor, se cerro sin goles
2. **Sevilla-Alaves** (1-1 → 1-1): Alaves muro defensivo clasico
3. **Udinese-Sassuolo** (2-2 → 1-2): **DATO CORRUPTO** - score 2-2 fue glitch del scraper de 1 ciclo, score real era 1-2

Sin el dato corrupto: **15 bets, 13W/2L, 86.7% WR, +141 EUR, +94% ROI**

---

## 5. Complementariedad con Cartera Actual

| Estrategia existente | Trigger | Mercado | Hora partido | Solapamiento |
|---|---|---|---|---|
| Back Empate | min 30 | Match Odds (Draw) | 1a mitad | NINGUNO |
| xG Underperf | min 15+ | Over (score+0.5) | Cualquiera | BAJO (trigger diferente) |
| Odds Drift | min ganando | Match Odds (Winner) | Cualquiera | NINGUNO |
| Goal Clustering | post-gol | Over (score+0.5) | min 15-80 | BAJO (mismo mercado Over pero trigger diferente) |
| **Pressure Cooker** | **min 65-75** | **Over (score+0.5)** | **Solo 2a mitad** | - |

La Pressure Cooker es complementaria porque:
- Se activa SOLO en empates (las demas estrategias se activan mayormente cuando hay diferencia en marcador)
- Ventana temporal unica (65-75) que no solapa con Goal Clustering (que triggerea al primer gol, tipicamente antes del 65)
- Apuesta al mismo mercado Over pero por razon diferente (inercia de goles vs clustering post-gol)

---

## 6. Limitaciones

1. **Muestra pequena**: Solo 16 triggers con cuotas en 3 dias. Necesitamos 50-100 para validar estadisticamente.
2. **Cobertura de cuotas**: Solo 28/56 candidatos tenian cuotas Over disponibles (50%). Puede haber sesgo de seleccion.
3. **Cuota media alta**: 2.41 parece alta para Over en empate al 65. Verificar que no hay sesgo en el momento de captura.
4. **Sin datos de momentum**: Los dangerous attacks muestran deltas ~0 en la mayoria de partidos (posible problema de datos).
5. **Dato corrupto detectado**: Udinese-Sassuolo tuvo score falso. Necesitamos sanitizacion de datos mas robusta.

---

## 7. Proximos pasos

1. **Acumular mas datos**: Dejar correr el scraper 1-2 semanas mas para obtener 50+ triggers
2. **Validar en produccion**: Incluir en la cartera como "en prueba" (paper trading)
3. **Monitorizar cobertura de cuotas**: Si >50% de candidatos no tienen cuotas, revisar scraper
4. **Criterio de salida**: Si tras 50 triggers WR < 65% o ROI < 0%, descartar

---

## 8. Implementacion Tecnica

### Backend (csv_reader.py)
- Nueva funcion `analyze_strategy_pressure_cooker()`
- Lee CSVs finalizados, busca empates 1-1+ entre min 65-75
- Calcula delta de metricas en ventana 10 min (informativo, no filtra)
- Apuesta Back Over y calcula P/L

### Frontend (InsightsView.tsx)
- Nueva pestana "Pressure Cooker" en Insights → Estrategias
- Version unica V1 (filtro simple: score != 0-0)
- Integrado en Cartera con toggle ON/OFF
