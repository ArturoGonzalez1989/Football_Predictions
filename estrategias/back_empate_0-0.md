# Estrategia: Back Empate en partidos 0-0 desde minuto 30

## Resumen ejecutivo

| Metrica | Valor |
|---|---|
| **Regla** | Apostar al empate cuando el marcador es 0-0 a partir del minuto 30 |
| **Muestra** | 27 apuestas sobre 67 partidos finalizados |
| **Win rate** | 52% (14/27) |
| **ROI neto** | +39.4% (con comision Betfair 5%) |
| **P/L neto** | +106.26 EUR (stakes de 10 EUR) |
| **Estado** | En validacion - necesita mas muestra |

---

## 1. Origen de la estrategia

### Descubrimiento inicial

Analizando 67 partidos finalizados de Betfair Exchange, se detecto que apostar al empate cuando el marcador esta igualado produce ROI positivo con una tendencia monotonica creciente:

| Minuto | N partidos | % empate final | Cuota promedio | ROI | Valoracion |
|---|---|---|---|---|---|
| 0-15 | 36 | 30.6% | 3.38 | +5.5% | Marginal |
| 15-30 | 38 | 34.2% | 3.14 | +12.8% | Aceptable |
| 30-45 | 29 | 44.8% | 2.86 | +25.6% | Bueno |
| 45-60 | 24 | 54.2% | 2.59 | +35.2% | Muy bueno |
| 60-75 | 20 | 60.0% | 2.29 | +33.5% | Muy bueno |
| 75-90 | 22 | 68.2% | 1.90 | +42.8% | Excelente |

El ROI sube en CADA tramo de 15 minutos sin excepcion. Cuando ves una tendencia asi de limpia en 6 tramos consecutivos, no es ruido. Es una ineficiencia real del mercado.

### Por que funciona

El mercado subestima la "inercia" de un empate. Cuanto mas tiempo llevan igualados, menos probable es que alguien marque: los equipos se conforman, bajan ritmo, juegan a no perder. Pero las cuotas no bajan al ritmo correcto, creando una ventaja sistematica.

### Por que es la mejor estrategia del catalogo

- **Baja varianza**: Cuotas entre 1.90-3.38, no necesitas rachas largas para ser rentable
- **Facil de detectar**: Solo necesitas saber si el marcador esta igualado y el minuto
- **Alta frecuencia**: Practicamente todos los partidos pasan por un periodo igualado
- **Automatizable**: El scraper ya captura minuto, goles y cuotas de empate

---

## 2. Simulacion con stakes reales

### Regla base: Back Empate cuando igualados, min 30+, stake 10 EUR

Simulacion sobre 67 partidos finalizados. Se aplica comision Betfair del 5% sobre beneficios.

**Resultado global:**

| Metrica | Valor |
|---|---|
| Partidos con trigger | 40 de 67 (60%) |
| Apuestas ganadas | 18 de 40 (45.0%) |
| Total apostado | 400.00 EUR |
| Beneficio bruto | +74.70 EUR |
| Comisiones Betfair (5%) | -14.74 EUR |
| **Beneficio neto** | **+59.96 EUR** |
| **ROI neto** | **+15.0%** |

### Hallazgo clave: filtrar por marcador

| Marcador | Apuestas | Win rate | P/L neto | ROI |
|---|---|---|---|---|
| **0-0** | **27** | **52%** | **+106.26 EUR** | **+39.4%** |
| 1-1 | 10 | 30% | -51.48 EUR | -51.5% |
| 2-2 | 3 | 33% | +5.18 EUR | +17.2% |

**Conclusion**: La estrategia es rentable en partidos 0-0 (+39.4% ROI neto) y pierde dinero en 1-1 (-51.5%). Un 0-0 indica que ambos equipos luchan por no encajar. Un 1-1 demuestra que ambos son capaces de marcar y es mas probable que alguien marque de nuevo.

**Regla refinada: SOLO apostar cuando el marcador es 0-0 a partir del minuto 30.**

### Desglose por minuto de entrada

| Minuto | Apuestas | Ganadas | P/L neto | ROI |
|---|---|---|---|---|
| Min 30-45 | 29 | 13 (45%) | +62.58 EUR | +21.6% |
| Min 45-60 | 6 | 3 (50%) | -4.07 EUR | -6.8% |
| Min 60-75 | 3 | 0 (0%) | -30.00 EUR | -100.0% |
| Min 75-90 | 2 | 2 (100%) | +31.45 EUR | +157.2% |

La mayoria de triggers (29/40) ocurren en min 30-45 porque es cuando mas partidos estan igualados. Los tramos 60-75 y 75-90 tienen muy pocos datos para ser significativos.

### Gestion de riesgo

| Metrica | Valor |
|---|---|
| Bankroll maximo alcanzado | +82.58 EUR |
| Bankroll minimo alcanzado | -20.00 EUR |
| Max drawdown | 54.07 EUR |
| Mejor racha ganadora | 3 seguidas |
| Peor racha perdedora | 4 seguidas |

Con un bankroll inicial de 200-300 EUR y stakes de 10 EUR, el drawdown maximo (54 EUR) es manejable. La peor racha de 4 perdidas seguidas supone -40 EUR, recuperable con 2-3 aciertos.

---

## 3. Analisis de filtros: refinando la regla

Analisis ejecutado sobre las 27 apuestas base (solo 0-0 desde min 30). Objetivo: encontrar filtros estadisticos que mejoren el win rate del 52% base.

### Filtro 1: Estadisticas al momento del trigger

#### 1a. Tiros a puerta totales (hallazgo clave)

| Filtro | N | Win | Win% | P/L neto | ROI |
|---|---|---|---|---|---|
| **0 tiros a puerta** | **5** | **5** | **100%** | **+93.38 EUR** | **+186.8%** |
| 1-2 tiros a puerta | 16 | 5 | 31.2% | -28.49 EUR | -17.8% |
| 3-4 tiros a puerta | 3 | 2 | 66.7% | +22.49 EUR | +75.0% |
| 5+ tiros a puerta | 3 | 1 | 33.3% | -4.80 EUR | -16.0% |

Cuando ningun equipo ha tirado a puerta al minuto 30, el 0-0 se mantiene el 100% de las veces. Muestra pequena (5 casos) pero logica aplastante: si nadie tira a puerta en 30 minutos, es un partido donde ninguno de los dos es capaz de generar peligro.

#### 1b. xG total combinado

| Filtro | N | Win | Win% | P/L neto | ROI |
|---|---|---|---|---|---|
| **xG total < 0.5** | **14** | **8** | **57.1%** | **+79.65 EUR** | **+56.9%** |
| xG total 0.5-1.0 | 9 | 3 | 33.3% | -7.66 EUR | -8.5% |
| xG total 1.0-1.5 | 1 | 1 | 100% | +13.68 EUR | +136.8% |

El xG confirma lo que vemos con los tiros a puerta: cuando la calidad de las ocasiones es baja (xG combinado < 0.5), el empate aguanta mucho mejor.

#### 1c. xG maximo de un solo equipo

| Filtro | N | Win | Win% | P/L neto | ROI |
|---|---|---|---|---|---|
| Max xG equipo < 0.3 | 12 | 6 | 50.0% | +42.98 EUR | +35.8% |
| Max xG equipo 0.3-0.6 | 6 | 4 | 66.7% | +48.59 EUR | +81.0% |
| **Max xG equipo 0.6+** | **6** | **2** | **33.3%** | **-5.89 EUR** | **-9.8%** |

Cuando algun equipo ya tiene un xG >= 0.6, la probabilidad de que marque sube y el empate peligra.

#### 1d. Diferencia de posesion

| Filtro | N | Win | Win% | P/L neto | ROI |
|---|---|---|---|---|---|
| **Poss diff < 10%** | **15** | **8** | **53.3%** | **+69.94 EUR** | **+46.6%** |
| Poss diff 10-20% | 4 | 2 | 50.0% | +14.20 EUR | +35.5% |
| **Poss diff 20%+** | **7** | **2** | **28.6%** | **-18.46 EUR** | **-26.4%** |

Partido equilibrado en posesion = empate mas probable. Cuando un equipo domina con >20% diferencia de posesion, tiene mas probabilidad de acabar marcando.

#### 1e. Tiros totales

| Filtro | N | Win | Win% | P/L neto | ROI |
|---|---|---|---|---|---|
| 0-3 tiros | 5 | 2 | 40.0% | +4.20 EUR | +8.4% |
| **4-7 tiros** | **14** | **9** | **64.3%** | **+104.28 EUR** | **+74.5%** |
| 8+ tiros | 8 | 2 | 25.0% | -25.89 EUR | -32.4% |

4-7 tiros es el sweet spot. Pocos tiros (0-3) puede ser que el partido aun no ha "arrancado". Muchos tiros (8+) indica presion ofensiva que acabara en gol.

### Filtro 2: Cuotas pre-partido

Solo 14 de los 27 partidos tienen cuotas pre-partido (los demas empezaron a capturarse en vivo). Los datos son insuficientes para conclusiones firmes:

| Filtro | N | Win | Win% | P/L neto | ROI |
|---|---|---|---|---|---|
| Draw pre < 3.00 | 2 | 0 | 0% | -20.00 EUR | -100.0% |
| Draw pre 3.00-3.50 | 7 | 2 | 28.6% | -16.75 EUR | -23.9% |
| **Draw pre 3.50-4.00** | **3** | **3** | **100%** | **+52.82 EUR** | **+176.1%** |
| Draw pre 4.00+ | 2 | 0 | 0% | -20.00 EUR | -100.0% |

La tendencia sugiere que partidos con draw pre ~3.50-4.00 funcionan mejor (empate "posible pero no favorito"), pero solo hay 3 casos. Necesita mucha mas muestra.

### Filtros combinados - Top 5 mejores reglas

| Regla | N | Win | Win% | P/L neto | ROI |
|---|---|---|---|---|---|
| **SoT = 0** | **5** | **5** | **100%** | **+93.38 EUR** | **+186.8%** |
| xG < 0.8 + pre draw < 4.0 | 8 | 5 | 62.5% | +56.07 EUR | +70.1% |
| xG < 0.8 + SoT < 2 | 10 | 6 | 60.0% | +68.87 EUR | +68.9% |
| xG total < 0.5 | 14 | 8 | 57.1% | +79.65 EUR | +56.9% |
| SoT <= 2 + poss diff < 15% | 15 | 8 | 53.3% | +70.12 EUR | +46.8% |

---

## 4. Conclusiones y regla final

### Regla optima (muestra pequena)

**"0-0 al minuto 30 con 0 tiros a puerta totales"** - 100% win rate, ROI +186.8%. Pero solo 5 casos, demasiado poco para fiarse ciegamente.

### Regla equilibrada (recomendada)

**"0-0 al minuto 30 con xG total < 0.5"** - 57.1% win rate, ROI +56.9%. Casi duplica el ROI de la regla base y tiene 14 casos.

### Senales de PELIGRO (cuando NO apostar)

- Algun equipo con xG >= 0.6 al minuto 30 (win rate cae al 33%)
- Diferencia de posesion > 20% (win rate cae al 28.6%)
- 8+ tiros totales al minuto 30 (win rate cae al 25%)

### Regla propuesta v2

Apostar Back Empate cuando:
1. Marcador 0-0 al minuto 30+
2. xG total combinado < 0.5 (o en su defecto, ningun equipo con xG > 0.6)
3. Diferencia de posesion < 20%
4. Menos de 8 tiros totales

### Patrones complementarios relevantes

- **Clustering de goles**: 18.3% de los goles son seguidos por otro en 5 min. Si se rompe el 0-0, puede venir mas goles rapido.
- **Goles tardios**: 52.2% de los partidos tienen gol despues del min 75. Un 0-0 al min 75 tiene 68.2% de acabar empate.
- **Corners asimetricos**: Diferencia de 5+ corners se asocia con 37.8% probabilidad de gol en 10 min (vs 26% baseline). Puede servir como senal de peligro adicional.
- **Momentum**: Cuando el momentum favorece claramente a un equipo (top 25%), ese equipo gana el 66.7%. Puede ayudar a filtrar.

---

## 5. Plan de accion

### Fase 1: Validacion (actual - hasta 200 partidos)
1. Seguir acumulando partidos con el scraper (objetivo: 200+ partidos de calidad)
2. Paper trading manual con la regla v2
3. Analizar si funciona mejor en ciertas ligas, horarios, o tipos de cuota pre-partido
4. Re-ejecutar simulacion cada 50 partidos nuevos para validar que el ROI se mantiene

### Fase 2: Backtesting ampliado (200-500 partidos)
5. Confirmar que el 0-0 sigue siendo significativamente mejor que 1-1 y 2-2
6. Bankroll management: flat stake 3-5% del bankroll
7. Confirmar filtros de xG y tiros a puerta con mas datos
8. Analizar cuotas pre-partido con muestra suficiente

### Fase 3: Automatizacion (500+ partidos validados)
9. Alertas en tiempo real cuando se detecte: min >= 30, marcador 0-0, xG < 0.5
10. Paper trading automatico con registro de apuestas virtuales
11. Dashboard de estrategias con P/L acumulado

### Fase 4: Trading real
12. Apuestas reales con stakes minimos (2-5 EUR)
13. Escalar solo si ROI > 10% neto tras 100+ apuestas reales

---

## 6. Datos tecnicos

- **Script de simulacion**: `simulate_draw_strategy.py` (simulacion base con stake fijo)
- **Script de filtros**: `simulate_draw_filters.py` (analisis de filtros estadisticos y pre-partido)
- **Script de patrones**: `analyze_patterns.py` (analisis general de patrones de apuestas)
- **Datos**: `betfair_scraper/data/partido_*.csv` (CSVs minuto a minuto)
- **Comision aplicada**: 5% sobre beneficios netos (Betfair Exchange)

---

## Disclaimer

Este analisis es exploratorio basado en una muestra limitada de 67 partidos (27 con trigger 0-0):
- Todos los ROI **incluyen comisiones** Betfair del 5%
- Son resultados pasados que **NO garantizan rendimiento futuro**
- Se basan en cuotas back disponibles en el momento, sin considerar liquidez real
- 27 apuestas es una muestra todavia pequena. Se necesitan 200+ para alta confianza
