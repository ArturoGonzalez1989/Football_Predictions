# Posibles Estrategias de Apuestas en Vivo

## Datos del Analisis
- **Fecha**: Febrero 2026
- **Muestra**: 67 partidos finalizados con calidad >= 70%
- **Fuente**: Datos minuto a minuto de Betfair Exchange (cuotas back/lay + estadisticas)
- **Goles totales**: 190 (2.84 por partido)
- **Resultados**: 28 victorias local, 20 victorias visitante, 19 empates

---

## Ranking de Estrategias (de mas a menos viable)

### TIER 1 - Estrategia Principal

### 1. Back Empate en partidos 0-0 desde minuto 30

**ROI neto: +39.4%** (con comisiones Betfair) | **Win rate: 52%** | 27 apuestas

Apostar al empate cuando el marcador es 0-0 a partir del minuto 30. La regla refinada con filtros estadisticos (xG < 0.5) sube el ROI al +56.9%.

Analisis completo, simulacion, filtros y regla final: **[back_empate_0-0.md](back_empate_0-0.md)**

---

### TIER 2 - Estrategias Secundarias (necesitan mas datos)

### 2. xG Underperformance - Back Over Goals (ROI: +34.9% base, +111.5% filtrado)

**Concepto**: Cuando un equipo tiene xG significativamente mayor que sus goles reales (exceso >= 0.5), apostar a que habra MAS GOLES (Back Over).

**Resultados actualizados** (38 partidos con xG):
- 26 triggers detectados (xG - goles >= 0.5)
- El equipo marca despues: 46.2% (12/26)
- Algun gol mas se marca: **73.1%** (19/26)

**Mercado correcto: Back Over (total+0.5)**
- 15 apuestas con cuota disponible, 80% WR, ROI +34.9%
- Back Team: -59.6% ROI (descartado)
- Lay Draw: -45.4% ROI (descartado)

**Filtro clave: equipo va PERDIENDO**
- 7 triggers donde el equipo underperformer pierde: **100% WR, +111.5% ROI**
- Sin outlier (min 90): 6 triggers, 100% WR, +41.5% ROI
- Logica: equipo perdiendo + creando ocasiones = presion ofensiva = mas goles

**Regla propuesta**: xG_equipo - goles >= 0.5 + equipo perdiendo -> Back Over (total+0.5)

**Limitaciones**: Muestra MUY pequena (7 triggers con filtro). Necesita +200 triggers para validar.

Analisis completo: **[xg_underperformance.md](xg_underperformance.md)**

---

### 3. Odds Drift - Backing al equipo castigado (ROI: +77.4%)

**Concepto**: Cuando las cuotas de un equipo suben mas de un 30% en 10 minutos (el mercado lo "abandona"), apostar a que ese equipo se recupera.

**Resultados**:
- 119 triggers detectados
- Win rate: 30.3% (36/119)
- Cuotas promedio al trigger: 9.59
- Break-even win rate: 10.4%
- **ROI estimado: +77.4%**

**Por que el ROI es alto pero peligroso**:
- **Cuotas de 9.59 = solo ganas 1 de cada 3**. Vas a tener rachas de 10-15 fallos seguidos.
- Necesitas un bankroll enorme y nervios de acero para aguantar la varianza.
- La ejecucion es dificil: detectar el drift Y colocar la apuesta a tiempo en Betfair.
- Un par de aciertos en cuotas altas inflan el ROI de toda la muestra.

**Veredicto**: Potencialmente muy rentable pero necesita +500 partidos para confirmar que no es varianza, y un bankroll management muy estricto (stakes del 1-2% max).

---

### TIER 3 - Descartadas o Insuficientes

### 4. Equipo Domina pero Pierde (ROI: +56.8%) - DESCARTADA

**Resultados**: 12 casos, 16.7% win rate, cuotas 10.85.

**Veredicto**: Solo 12 casos. Ruido estadistico, no una estrategia.

---

### 5. Fade al Overperformer (ROI: +63.1%) - DESCARTADA

**Resultados**: 60 instancias, oponente gana 20% (12/60), cuotas del oponente 19.59.

**Veredicto**: Cuotas de 19.59 = una loteria disfrazada de estrategia. No es replicable ni fiable.

---

## Estrategias Confirmadas NO Rentables

### Sharp Odds Drop - Backing al Favorito (ROI: -43.0%)
Cuando las cuotas bajan bruscamente (>20% en 10 min), apostar al equipo favorecido **destruye dinero**. Win rate 36% con cuotas de 2.25.

**Leccion clave**: Llegar tarde a un movimiento de cuotas es regalar dinero.

**Desglose por momento**:
- Min 0-30: 61 triggers, win rate 41.0%, ROI -27.4%
- Min 31-60: 40 triggers, win rate 30.0%, ROI -56.1%
- Min 61-90+: 24 triggers, win rate 33.3%, ROI -60.8%

### Tarjetas Amarillas como Predictor de Goles
Las tarjetas **NO predicen goles**. Tasa de gol en 10 min post-tarjeta: 24.6%. Baseline normal: 27.5%. Despues de una tarjeta hay menos probabilidad de gol, no mas.

---

## Patrones Complementarios

### Goles por Intervalo de 10 Minutos
Intervalos con mas goles: min 40-49 (14.9%), min 50-59 (14.3%), min 70-79 (14.9%).
Intervalos con menos goles: min 0-9 (5.4%), min 10-19 (4.8%).

### Clustering de Goles
- 18.3% de los goles son seguidos por otro en los siguientes 5 minutos
- 38.5% de los goles son seguidos por otro en los siguientes 10 minutos
- Media entre goles consecutivos: 17.2 minutos, mediana: 12.0 minutos

### Goles Tardios (75+)
- 52.2% de los partidos tienen al menos un gol despues del minuto 75
- Con 2 goles al minuto 75: 71.4% tienen gol tardio
- Con posesion local >55% al minuto 75: 68.8% tienen gol tardio
- 19.4% de los partidos tienen un gol decisivo (go-ahead) despues del 75

### Corners como Predictor
- El equipo con mas corners gana en el 53.3% (local) / 36.7% (visitante)
- Diferencia de 5+ corners: 37.8% probabilidad de gol en 10 min (vs 26% baseline)

### Momentum (dato del scraper)
- Cuando el momentum favorece claramente al local (top 25%): home win 66.7% (20/30 partidos)
- El momentum capturado por el scraper SI tiene valor predictivo

---

## Documentos detallados

| Estrategia | Documento | Estado |
|---|---|---|
| Back Empate 0-0 | [back_empate_0-0.md](back_empate_0-0.md) | Analisis completo |
| xG Underperformance | [xg_underperformance.md](xg_underperformance.md) | Analisis inicial |
| Odds Drift | Pendiente | Necesita mas datos |

---

## Disclaimer

Este analisis es exploratorio basado en una muestra limitada de 67 partidos:
- La simulacion de la estrategia principal (Back Empate 0-0) **SI incluye comisiones** Betfair del 5%
- Los ROI de las demas estrategias (TIER 2, TIER 3) **NO incluyen comisiones**
- Son resultados pasados que **NO garantizan rendimiento futuro**
- Se basan en cuotas back disponibles en el momento, sin considerar liquidez real
- Las estrategias de TIER 3 estan descartadas por muestra insuficiente o varianza excesiva
