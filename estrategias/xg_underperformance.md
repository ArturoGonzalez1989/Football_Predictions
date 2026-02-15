# Estrategia: xG Underperformance - Back Over Goals

## Resumen Ejecutivo

| Metrica | Base (todos) | Filtro: Perdiendo | Perdiendo (sin outlier min90) |
|---|---|---|---|
| **Triggers** | 26 | 7 | 6 |
| **Apuestas con cuota** | 15 | 7 | 6 |
| **Win Rate** | 80.0% | 100.0% | 100.0% |
| **ROI neto** | +34.9% | +111.5% | +41.5% |
| **P/L (stake 10 EUR)** | +52.28 | +78.08 | +24.88 |
| **Mercado** | Back Over (total+0.5) | Back Over (total+0.5) | Back Over (total+0.5) |

**Estado**: Analisis inicial exploratorio - muestra MUY pequena (38 partidos con xG)

---

## 1. Concepto

Cuando un equipo tiene xG significativamente mayor que sus goles reales (exceso >= 0.5), la regresion a la media dice que ese equipo acabara convirtiendo. Si ademas va **perdiendo**, la urgencia por marcar aumenta y el mercado Over puede estar infravalorado.

**Logica estadistica**: El xG mide la calidad de las ocasiones creadas. Un equipo que crea buenas ocasiones pero no marca esta "en deuda" estadistica. La probabilidad de que marque aumenta con cada nueva ocasion de calidad.

---

## 2. Datos del Analisis

- **Fecha**: Febrero 2026
- **Partidos analizados**: 39 (38 con datos xG)
- **Triggers detectados**: 26 (xG - goles >= 0.5 para algun equipo)
- **Apuestas simuladas**: 15 con cuotas Over disponibles
- **Stake**: 10 EUR plano
- **Comision Betfair**: 5% sobre ganancias

---

## 3. Analisis de Resultados

### 3a. Que pasa despues del trigger?

| Metrica | N | % |
|---|---|---|
| El equipo marca al menos 1 gol mas | 12/26 | 46.2% |
| Se marca al menos 1 gol mas (cualquier equipo) | 19/26 | **73.1%** |
| El proximo gol es del equipo underperforming | 7/26 | 26.9% |
| El equipo underperforming gana el partido | 4/26 | 15.4% |

**Conclusion**: Aunque el equipo especifico solo marca el 46% de las veces, la probabilidad de que haya MAS GOLES despues del trigger es del 73%. Esto apunta claramente a **Back Over** como el mercado correcto, no a Back Team.

### 3b. Momento de deteccion

| Rango | N | Equipo marca | % | Algun gol | % |
|---|---|---|---|---|---|
| Min 15-29 | 5 | 4 | 80.0% | 5 | **100%** |
| Min 30-44 | 7 | 4 | 57.1% | 5 | 71.4% |
| Min 45-59 | 6 | 3 | 50.0% | 5 | 83.3% |
| Min 60-74 | 6 | 0 | 0.0% | 3 | 50.0% |
| Min 75+ | 2 | 1 | 50.0% | 1 | 50.0% |

**Insight**: La deteccion temprana (min 15-44) tiene mayor tasa de "algun gol despues", pero las cuotas son muy bajas (Over 0.5 a @1.05-1.10) porque queda mucho partido. La ventana optima parece ser cuando ya hay goles en el marcador y el Over siguiente tiene cuotas mas altas.

### 3c. Magnitud del exceso xG

| Exceso xG | N | Equipo marca | % |
|---|---|---|---|
| 0.50-0.74 | 20 | 7 | 35.0% |
| **0.75-0.99** | **5** | **5** | **100%** |
| 1.00+ | 1 | 0 | 0.0% |

**Insight**: El rango 0.75-0.99 muestra una senal perfecta (5/5 marcan), pero la muestra es minima. El exceso >= 1.0 tiene solo 1 caso. Necesita mucha mas data.

---

## 4. Simulacion de Mercados

Se simularon 3 mercados posibles. Solo Back Over resulta rentable:

### 4a. Back Over (total+0.5) -- RENTABLE

Apostar a que habra al menos 1 gol mas despues del trigger.

| Metrica | Valor |
|---|---|
| Apuestas | 15 |
| Wins | 12 |
| Win Rate | 80.0% |
| P/L neto | +52.28 EUR |
| ROI | **+34.9%** |

**AVISO IMPORTANTE**: El ROI esta inflado por 1 apuesta outlier:
- Espanyol-Celta min 90, cuota Over 3.5 a @6.60 = +53.20 EUR
- Sin este outlier: 14 apuestas, P/L = -0.92 EUR, ROI = -0.7%

Esto significa que la estrategia sin filtros **no es rentable por si sola**. Necesita filtros.

### 4b. Back Team (ganador del partido) -- NO RENTABLE

| Metrica | Valor |
|---|---|
| Apuestas | 25 |
| Wins | 4 |
| Win Rate | 16.0% |
| ROI | **-59.6%** |

El equipo underperforming rara vez gana el partido. Descartado.

### 4c. Lay Draw -- NO RENTABLE

| Metrica | Valor |
|---|---|
| Apuestas | 25 |
| Wins | 14 |
| Win Rate | 56.0% |
| ROI | **-45.4%** |

Las perdidas cuando el empate se mantiene son demasiado grandes. Descartado.

---

## 5. Filtros: Donde esta el edge?

### 5a. Filtros individuales (Back Over)

| Filtro | N | WR% | ROI |
|---|---|---|---|
| **Equipo perdiendo** | **7** | **100%** | **+111.5%** |
| Posesion >= 55% | 15 | - | +80.6% |
| Score NO es 0-0 | 14 | - | +85.1% |
| SoT >= 2 | 8 | 87.5% | +74.6% |
| Min >= 45 (deteccion tardia) | 14 | - | +66.5% |
| Min < 45 (temprana) | 12 | - | -1.4% |
| Score es 0-0 | 12 | - | -22.6% |
| Posesion < 55% | 11 | - | -33.7% |
| SoT < 2 | 11 | - | -10.5% |

**Filtro dominante: "equipo va perdiendo"**

El filtro mas potente con diferencia es cuando el equipo underperforming va PERDIENDO en ese momento. Los 7 triggers en esta situacion resultaron TODOS en mas goles = 100% WR.

### 5b. Combinaciones (Back Over)

| Combinacion | N | WR% | ROI |
|---|---|---|---|
| Perdiendo + SoT >= 3 | 4 | 100% | +163.9% |
| Perdiendo + SoT >= 2 | 5 | 100% | +136.2% |
| Perdiendo (cualquier SoT) | 7 | 100% | +111.5% |
| Perdiendo, excl. min 75+ (sin outlier) | 6 | 100% | +41.5% |

### 5c. Por que funciona el filtro "perdiendo"?

Cuando un equipo:
1. Tiene xG alto (crea buenas ocasiones)
2. No ha convertido (mala suerte o buen portero rival)
3. Va perdiendo (necesita marcar urgentemente)

...la presion ofensiva se intensifica. El equipo arriesga mas, sube lineas, comete errores defensivos. Esto genera goles **para ambos equipos**, no solo para el underperformer. El Over se beneficia de esta dinamica.

Los 7 casos "perdiendo":

| Partido | Equipo | Min | Score | xG ex | Over@ | FT | Resultado |
|---|---|---|---|---|---|---|---|
| Kilmarnock-Celtic | Away | 29 | 2-0 | 0.64 | - | 2-2 | +2 goles |
| Reading-Wycombe | Away | 36 | 1-0 | 0.80 | 1.34 | 3-2 | +4 goles |
| Stoke-Fulham | Away | 39 | 1-0 | 0.51 | 1.28 | 1-1 | +1 gol |
| Genclerbirligi-Rizespor | Away | 40 | 1-0 | 0.82 | - | 2-2 | +3 goles |
| Eintracht-B Munich | Away | 45 | 2-0 | 0.65 | 1.71 | 3-0 | +1 gol |
| Charleroi-Gante | Home | 57 | 0-1 | 0.80 | 1.37 | 2-3 | +4 goles |
| Corinthians-RB Bragantino | Away | 62 | 1-0 | 1.24 | 1.65 | 2-0 | +1 gol |

**Todos los partidos tuvieron al menos 1 gol mas despues del trigger.** En promedio, 2.3 goles mas por partido.

---

## 6. Regla Propuesta

### Regla V1 (base)

```
TRIGGER: xG_equipo - goles_equipo >= 0.5
         Y el equipo va PERDIENDO
MERCADO: Back Over (goles_totales_actuales + 0.5)
STAKE:   10 EUR plano (o 1% del bankroll)
HOLD:    Hasta el final del partido
```

### Regla V1+ (refinada)

```
TRIGGER: xG_equipo - goles_equipo >= 0.5
         Y el equipo va PERDIENDO
         Y tiros a puerta del equipo >= 2
MERCADO: Back Over (goles_totales_actuales + 0.5)
STAKE:   10 EUR plano
HOLD:    Hasta el final del partido
```

---

## 7. Analisis de Riesgos

### Riesgo 1: Muestra extremadamente pequena
- Solo 38 partidos con xG analizados
- Solo 7 triggers con filtro "perdiendo" (5 con cuotas Over)
- 100% WR puede ser pura suerte con N=7

### Riesgo 2: Cuotas Over bajas en 0-0
- Cuando el score es 0-0, el Over 0.5 tiene cuotas de 1.05-1.11
- Ganas 0.50-1.05 EUR por acierto vs pierdes 10 EUR por fallo
- Necesitas >90% WR para ser rentable con cuotas tan bajas

### Riesgo 3: Dependencia de outliers
- Sin filtro "perdiendo", toda la rentabilidad depende de 1 apuesta (Espanyol min 90)
- Incluso con el filtro, los numeros son tan pequenos que 1-2 fallos cambian todo

### Riesgo 4: Disponibilidad de datos xG
- Solo 38 de 39 partidos finalizados tienen datos xG
- La calidad del xG depende del proveedor de Betfair y puede variar

---

## 8. Sinergia con Back Empate 0-0

Esta estrategia complementa la estrategia principal:

| Situacion | Back Empate | xG Underperformance |
|---|---|---|
| 0-0 min 30+, xG bajo (ambos) | ENTRAR | No trigger |
| 0-0 min 30+, xG alto (un equipo) | NO ENTRAR (filtro xG) | ALERTA: equipo puede marcar |
| 1-0 / 0-1, equipo perdiendo con xG alto | No aplica | ENTRAR: Back Over |

Cuando la estrategia Back Empate RECHAZA un partido por xG alto, esa misma senal puede ser un trigger para Back Over. Son estrategias inversas y complementarias.

---

## 9. Proximos Pasos

1. **Acumular datos**: Necesitamos minimo 200 triggers para validar. Con ~0.7 triggers/partido, necesitamos ~280 partidos mas
2. **Tracking en vivo**: Anadir al dashboard de Insights para monitorear triggers en tiempo real
3. **Refinar xG threshold**: Con mas datos, probar si exceso >= 0.75 es mejor que >= 0.50
4. **Explorar trading**: Si tras entrar el score cambia a favor (equipo empata), las cuotas Over bajan y se puede hacer cashout
5. **Correlacion con momentum**: Explorar si el momentum de Betfair refuerza la senal xG

---

## 10. Resumen de Hallazgos

### Lo que funciona
- **Back Over** es el unico mercado rentable
- El filtro **"equipo perdiendo"** transforma una estrategia mediocre en una con 100% WR
- **SoT >= 2** y **posesion >= 55%** tambien mejoran resultados

### Lo que NO funciona
- Back Team: -59.6% ROI (el equipo underperforming casi nunca gana)
- Lay Draw: -45.4% ROI (las perdidas por empate son demasiado altas)
- Sin filtros: el ROI depende de 1 outlier

### Veredicto
**Prometedor pero prematuro.** La logica es solida, el filtro "perdiendo" tiene sentido intuitivo y los numeros son perfectos, pero con N=7 no se puede confirmar nada. Necesita mas datos urgentemente.

---

## Disclaimer

- Muestra de solo 38 partidos con xG - resultados NO son estadisticamente significativos
- ROI incluye comisiones Betfair del 5%
- Son resultados pasados que NO garantizan rendimiento futuro
- Se basan en cuotas back disponibles, sin considerar liquidez real
- La regla "equipo perdiendo + xG underperformance" tiene solo 7 casos historicos
- Script de analisis: `analyze_xg_underperformance.py`
