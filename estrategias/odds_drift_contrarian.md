# Estrategia: Odds Drift Contrarian - Back al equipo que va ganando

## Resumen Ejecutivo

| Metrica | V1 Base | V2 Ventaja 2+ | V3 Drift >=100% | V4 Odds<=5 + 2a parte |
|---|---|---|---|---|
| **Triggers** | 41 | 13 | 23 | 13 |
| **Win Rate** | 78.0% | 100.0% | 87.0% | 92.3% |
| **ROI neto** | +202.6% | +231.9% | +329.0% | +145.1% |
| **P/L (stake 10 EUR)** | +830.73 | +301.42 | +756.60 | +188.64 |
| **Max Drawdown** | 30 EUR | 0 EUR | 10 EUR | 10 EUR |
| **Peor racha** | 3 fallos | 0 | 1 fallo | 1 fallo |
| **Avg odds** | 3.96 | 3.44 | 5.26 | 2.74 |

**Estado**: Analisis sobre 148 partidos. Muestra prometedora pero necesita mas datos para confirmar.

---

## 1. Concepto

Cuando un equipo **va ganando** pero sus cuotas suben mas de un 30% en 10 minutos (el mercado lo "abandona" a pesar de ir por delante), apostar a que ese equipo mantiene la victoria.

**Logica**: El mercado sobrereacciona a eventos puntuales (gol del rival, tarjeta, momentum temporal). Un equipo que ya va ganando tiene ventaja psicologica y tactica. Si el drift es extremo (>100%), la sobrereaccion es mayor y la reversion mas probable.

**IMPORTANTE**: La hipotesis original era "apostar al equipo abandonado (que va perdiendo)". Los datos demuestran lo contrario:
- Equipo va ganando + drift: **+202.6% ROI**
- Equipo va empatando + drift: **-5.3% ROI**
- Equipo va perdiendo + drift: **-18.9% ROI**

La estrategia solo funciona cuando el equipo ya lleva ventaja en el marcador.

---

## 2. Datos del Analisis

- **Fecha**: Febrero 2026
- **Partidos analizados**: 148 finalizados con datos completos
- **Triggers detectados**: 251 totales (drift >30% en 10 min, odds 1.5-30)
- **Triggers con equipo ganando**: 41
- **Stake**: 10 EUR plano
- **Comision Betfair**: 5% sobre ganancias
- **Mercado**: Match Odds (Back al equipo con drift que va ganando)

---

## 3. Parametros de Deteccion

| Parametro | Valor |
|---|---|
| Drift minimo | 30% de subida en cuotas |
| Ventana temporal | 10 minutos |
| Minuto minimo | 5 |
| Minuto maximo | 80 |
| Odds minimas | 1.50 |
| Odds maximas | 30.00 |
| Condicion clave | Equipo con drift va GANANDO en el marcador |
| Max 1 trigger por equipo por partido | Si |

---

## 4. Analisis de Resultados

### 4a. Resultados por equipo local/visitante

| Team | Triggers | WR | ROI | MaxDD | Racha |
|---|---|---|---|---|---|
| HOME | 25 | 80.0% | +210.4% | 20 EUR | 2 |
| AWAY | 16 | 75.0% | +190.5% | 20 EUR | 2 |

Ambos son rentables. HOME ligeramente mejor pero sin diferencia significativa.

### 4b. Resultados por minuto

| Rango | Triggers | WR | ROI | MaxDD | Racha |
|---|---|---|---|---|---|
| Min 5-30 | 12 | 66.7% | +249.2% | 30 EUR | 3 |
| Min 31-45 | 13 | 84.6% | +217.9% | 11 EUR | 1 |
| Min 46-80 | 16 | 81.2% | +155.3% | 10 EUR | 1 |

Minutos 31+ tienen mejor WR y menor drawdown. Los triggers tempranos (5-30) son los mas arriesgados.

### 4c. Resultados por rango de odds

| Rango | Triggers | WR | ROI | MaxDD | Racha |
|---|---|---|---|---|---|
| Odds <= 3.0 | 22 | 72.7% | +56.2% | 20 EUR | 2 |
| Odds 3.0-5.0 | 11 | 90.9% | +208.5% | 10 EUR | 1 |
| Odds 5.0-10.0 | 7 | 71.4% | +458.6% | 10 EUR | 1 |
| Odds > 10.0 | 1 | 100.0% | +1567.5% | 0 EUR | 0 |

El rango 3.0-5.0 es el sweet spot: 90.9% WR con buen ROI y riesgo controlado. Odds <= 3 tienen peor WR porque el payout es bajo.

### 4d. Resultados por magnitud del drift

| Drift | Triggers | WR | ROI | MaxDD | Racha |
|---|---|---|---|---|---|
| 30-50% | 9 | 66.7% | +29.3% | 22 EUR | 2 |
| 50-100% | 9 | 66.7% | +53.1% | 20 EUR | 2 |
| >= 100% | 23 | **87.0%** | **+329.0%** | 10 EUR | 1 |

El drift extremo (>=100%) es el mejor predictor. Cuando el mercado sobrereacciona MUCHO, la reversion es casi segura.

### 4e. Resultados por diferencia de goles

| Ventaja | Triggers | WR | ROI | MaxDD | Racha |
|---|---|---|---|---|---|
| 1 gol | 28 | 67.9% | +189.0% | 50 EUR | 5 |
| 2+ goles | 13 | **100.0%** | +231.9% | **0 EUR** | **0** |

**Hallazgo clave**: Con ventaja de 2+ goles, NUNCA se pierde (13/13). Los 9 fallos son TODOS con ventaja de solo 1 gol.

---

## 5. Analisis de Fallos

Los 9 triggers perdedores comparten patrones claros:

| Partido | Min | Score | Odds | Drift | FT |
|---|---|---|---|---|---|
| Barnsley - AFC Wimbledon | 27 | 2-1 | 2.06 | 51.5% | 3-3 |
| Brentford - Arsenal | 61 | 0-1 | 2.74 | 33.0% | 1-1 |
| Dynamo Dresden - Elversberg | 51 | 1-0 | 6.20 | 262.6% | 1-3 |
| Espanyol - Celta de Vigo | 38 | 0-1 | 4.10 | 30.2% | 2-2 |
| FC Osaka - Kochi Univ | 11 | 1-0 | 2.08 | 70.5% | 2-2 |
| Fredericia - AGF | 6 | 1-0 | 2.36 | 50.3% | 1-1 |
| Heerenveen - PEC Zwolle | 31 | 1-2 | 1.76 | 33.3% | 4-2 |
| Kagoshima Utd - FC Ryukyu | 6 | 0-1 | 2.14 | 111.9% | 3-1 |
| Standard Lieja - Union St Gilloise | 48 | 1-0 | 9.80 | 329.8% | 1-1 |

### Perfil del fallo vs acierto

| Metrica | Aciertos (32) | Fallos (9) |
|---|---|---|
| Minuto medio | 41.2 | 31.0 |
| Odds media | 4.0 | 3.7 |
| Drift medio | 186.2% | 108.1% |
| Goal diff | 1.7 | **1.0** |
| SoT del equipo | 3.7 | **1.4** |
| Tiros del equipo | 7.2 | **3.4** |
| Posesion | 54.6% | 51.3% |

Los fallos se caracterizan por:
1. **Siempre ventaja de 1 solo gol** (nunca 2+)
2. Menos tiros a puerta (1.4 vs 3.7): el equipo no esta dominando
3. Minuto mas temprano: queda mas tiempo para el rival
4. Drift menor: la sobrereaccion del mercado era menor (quiza justificada)

---

## 6. Versiones de la Estrategia

### V1 - Base
**Regla**: Drift >30% en 10 min + equipo va GANANDO
- 41 triggers | 78.0% WR | +202.6% ROI | MaxDD 30 EUR | Racha 3

### V2 - Ventaja 2+ goles
**Regla**: V1 + diferencia de goles >= 2
- 13 triggers | **100% WR** | +231.9% ROI | MaxDD 0 EUR | Racha 0
- **Ventaja**: Nunca pierde. **Desventaja**: Solo 13 triggers, necesita validar con mas datos.

### V3 - Drift extremo
**Regla**: V1 + drift >= 100% (cuotas se duplican o mas)
- 23 triggers | **87.0% WR** | +329.0% ROI | MaxDD 10 EUR | Racha 1
- **Mejor equilibrio** entre muestra (23) y fiabilidad (87%). El drift extremo indica sobrereaccion del mercado.

### V4 - Segunda parte conservadora
**Regla**: V1 + odds <= 5.0 + minuto > 45
- 13 triggers | **92.3% WR** | +145.1% ROI | MaxDD 10 EUR | Racha 1
- **Mas conservadora**: odds razonables + menos tiempo de partido = menor riesgo de remontada.

---

## 7. Recomendacion

**Estrategia recomendada: V3 (Drift extremo)**

Razon: mejor ratio muestra/WR/ROI. 23 triggers con 87% WR y solo 1 fallo consecutivo maximo. El ROI de +329% es el mas alto y la logica es solida: a mayor sobrereaccion del mercado, mayor probabilidad de reversion.

**Estrategia mas segura: V2 (Ventaja 2+ goles)** - 100% WR pero con solo 13 triggers.

**Para cartera combinada**: V1 base (41 triggers, 78% WR) es la mas adecuada porque genera mas apuestas y ya tiene un ROI excelente.

---

## 8. Limitaciones

1. **Muestra limitada**: 148 partidos, 41 triggers (V1). Necesita +500 partidos para validar estadisticamente.
2. **Ejecucion**: Requiere detectar el drift en tiempo real y colocar la apuesta antes de que las cuotas bajen.
3. **Liquidez**: Las cuotas despues del drift pueden tener poca liquidez en Betfair.
4. **Sesgo temporal**: Todos los datos son de febrero 2026. Falta validar en otros periodos.
5. **100% WR en V2**: Con solo 13 casos, es estadisticamente posible que sea ruido. No asumir que sera siempre 100%.

---

## 9. Implementacion en el Scraper

El scraper ya captura todos los datos necesarios:
- `back_home`, `back_away`: cuotas cada ~60 segundos
- `goles_local`, `goles_visitante`: marcador en vivo
- `minuto`: tiempo de partido
- `timestamp_utc`: para calcular ventanas de 10 minutos

La deteccion automatica requiere comparar cuotas entre captures consecutivas con ventana de 10 minutos y verificar que el equipo con drift va ganando.
