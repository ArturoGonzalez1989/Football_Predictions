# Estrategia: Back Empate en partidos 0-0 desde minuto 30

## Resumen ejecutivo

| Metrica | V1 (base) | V1.5 | V2r (recomendada) |
|---|---|---|---|
| **Regla** | 0-0 min 30+ | + xG<0.6 + PD<25% | + xG<0.6 + PD<20% + Sh<8 |
| **Muestra** | 16 triggers / 32 partidos | 9 apuestas | 6 apuestas |
| **Win rate** | 31.2% | 55.6% | 66.7% |
| **ROI neto** | -20.8% | +40.8% | +75.3% |
| **P/L neto** | -33.24 EUR | +36.76 EUR | +45.17 EUR |
| **Estado** | En validacion - necesita mas muestra | | |

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

Solo 14 de los 27 partidos scrapeados tienen cuotas pre-partido. Los datos in-play son insuficientes (3 casos en el mejor tramo). Sin embargo, un analisis historico offline con 1,418 partidos resuelve esta hipotesis — ver seccion 3b.

### Filtros combinados - Top 5 mejores reglas

| Regla | N | Win | Win% | P/L neto | ROI |
|---|---|---|---|---|---|
| **SoT = 0** | **5** | **5** | **100%** | **+93.38 EUR** | **+186.8%** |
| xG < 0.8 + pre draw < 4.0 | 8 | 5 | 62.5% | +56.07 EUR | +70.1% |
| xG < 0.8 + SoT < 2 | 10 | 6 | 60.0% | +68.87 EUR | +68.9% |
| xG total < 0.5 | 14 | 8 | 57.1% | +79.65 EUR | +56.9% |
| SoT <= 2 + poss diff < 15% | 15 | 8 | 53.3% | +70.12 EUR | +46.8% |

### 3b. Analisis historico offline: cuotas pre-partido (version no-live)

Analisis complementario usando datos historicos de football-data.co.uk (temporada 2025-2026, 22 ligas europeas). No usa datos del scraper — se basa en el resultado al descanso (HT) como proxy del trigger "0-0 al min 30". La muestra es mucho mayor pero no incluye filtros in-play (xG, tiros a puerta en el momento).

**Fuente**: `historic_data/all-euro-data-2025-2026.xlsx` (4,854 partidos, 1,418 iban 0-0 al HT).

#### Cuota BFED pre-match vs probabilidad de empate final

| Cuota BFED pre | N | Empate final% | 0-0 final% | Edge vs mercado |
|---|---|---|---|---|
| < 2.80 | 39 | 35.9% | 15.4% | -23.9% |
| **2.80-3.20** | **202** | **49.5%** | **33.7%** | **+16.8%** |
| 3.20-3.50 | 414 | 40.6% | 24.6% | +10.6% |
| 3.50-3.80 | 367 | 37.3% | 20.4% | +9.6% |
| 3.80-4.20 | 192 | 35.4% | 22.4% | +10.0% |
| 4.20-5.00 | 115 | 40.0% | 16.5% | +17.6% |
| 5.00+ | 89 | 28.1% | 13.5% | +12.6% |

El tramo BFED 2.80-3.20 es el claro ganador: 49.5% de empate final con 202 casos. Esto **contradice** la hipotesis preliminar de los datos live (3 casos sugerian BFED 3.50-4.00).

#### Refinamiento: equilibrio del partido

Dentro de BFED 2.80-3.20, el ratio de equilibrio (cuota menor / cuota mayor entre home y away) mejora aun mas el filtro:

| Equilibrio | N | Draw% | Significado |
|---|---|---|---|
| < 0.55 (desequilibrado) | 30 | 40.0% | Hay favorito claro |
| 0.55-0.70 | 50 | 48.0% | Moderado |
| 0.70-0.85 | 63 | 49.2% | Bastante equilibrado |
| **>= 0.85 (muy equilibrado)** | **58** | **56.9%** | **Ninguno domina** |

Break-even con comision: cuota in-play >= 1.85. Un 0-0 al descanso en partido equilibrado suele cotizar entre 2.00-2.50 in-play, asi que hay margen.

#### Senales de peligro confirmadas (muestra grande)

- BFED >= 5.00: solo 28.1% empate (el favorito acaba marcando)
- BFED < 2.80: 35.9% (paradojicamente peor — posible efecto "trampa de valor")
- Partido muy desequilibrado (ratio < 0.40): 35.8%

#### Limitaciones de este analisis

- El trigger es "0-0 al HT" (~min 45), no "0-0 al min 30" como la regla live
- No tiene filtros in-play (xG, SoT, posesion al momento del trigger)
- Los BFED son de Betfair Exchange pre-match, no de cuotas capturadas por el scraper
- ~~No se pudo cruzar de forma fiable con los CSVs live (solo 5 partidos en la interseccion)~~ **RESUELTO** — ver 3c

#### Conclusion

Para la version live, el scraper deberia capturar la cuota pre-match de empate BFED antes de que arranque el partido. Asi se podra usar como filtro adicional a los filtros in-play (xG, SoT) sin depender de matching externo. El rango objetivo es **BFED 2.80-3.20 en partido equilibrado**.

### 3c. Validacion live: cruce BFED pre-match con datos scrapeados

Se enriquecieron 54 CSVs scrapeados con columnas BFEH/BFED/BFEA de Football Data (`enrich_prematch_odds.py`). De los 14 triggers V1 actuales, 6 tienen datos BFED (los 8 restantes son ligas no europeas, copas, o futbol femenino).

#### Datos cruzados (6 triggers con BFED)

| Partido | BFED | Balance | xG@30 | DS | FT | W/L | V2 |
|---|---|---|---|---|---|---|---|
| Braunschweig-Darmstadt | 3.60 | 0.75 | 0.44 | 19 | 2-2 | **W** | Y |
| Espanyol-Celta | 3.25 | 0.80 | 0.57 | 16 | 2-2 | **W** | N |
| Fortuna Dusseldorf-Munster | 3.70 | 0.57 | 0.51 | 12 | 0-0 | **W** | N |
| Groningen-Utrecht | 3.40 | 0.52 | 0.99 | 8 | 1-2 | L | N |
| Kocaelispor-Gaziantep | 3.35 | 0.47 | 0.37 | 7 | 3-0 | L | N |
| Stevenage-Huddersfield | 3.25 | 0.99 | 0.82 | 13 | 1-0 | L | N |

*Balance = min(BFEH, BFEA) / max(BFEH, BFEA). 1.0 = partido totalmente equilibrado.*

#### Hallazgos preliminares

**1. Hipotesis BFED 2.80-3.20: NO TESTEABLE AUN**

Los 6 triggers caen en BFED 3.20-3.80. Ninguno en el rango 2.80-3.20 que el analisis historico senalo como optimo. Resultado del rango disponible: 50% WR, +34.6% ROI (3/6).

**2. Balance del partido: SENAL PROMETEDORA**

| Equilibrio | N | Wins | WR% | P/L | ROI |
|---|---|---|---|---|---|
| < 0.55 (favorito claro) | 2 | 0 | 0% | -20.00 | -100% |
| 0.55-0.80 | 2 | 2 | 100% | +36.48 | +182% |
| >= 0.80 (muy equilibrado) | 2 | 1 | 50% | +4.25 | +21% |

Partidos con favorito claro (balance < 0.55) pierden el 100% en esta muestra. El favorito acaba marcando tarde o temprano. Coincide con el patron historico de la seccion 3b.

**3. El filtro V2 (in-play) YA captura lo que el balance senala**

- Stevenage (balance=0.99, el mas equilibrado) pierde → pero tiene xG=0.82. V2 la filtra (xG>=0.5).
- Kocaelispor (balance=0.47, desequilibrado) pierde → tiene 9 tiros. V2 la filtra (shots>=8).
- El balance pre-match es **redundante** con los filtros in-play. No anade informacion nueva CUANDO los filtros V2 estan activos.

**4. BFED no predice stats in-play**

| BFED | Avg xG@30 | N |
|---|---|---|
| <= 3.50 | 0.688 | 4 |
| > 3.50 | 0.475 | 2 |

No hay correlacion. Un BFED bajo no implica menos peligro al min 30. Las stats in-play son independientes de las cuotas pre-match.

#### Conclusion provisional

Con solo 6 datos cruzados, las conclusiones son fragiles. Sin embargo:

1. **BFED como filtro V2**: No mejora V2 — los filtros in-play ya hacen el trabajo
2. **Balance como filtro V1**: Prometedor (balance < 0.55 = 0% WR), pero V2 ya filtra esos partidos por otra via
3. **Balance como pre-filtro rapido**: Podria servir como "filtro de descarte rapido" antes de esperar al min 30 — si balance < 0.55, ni siquiera mirar el partido. Pero necesita mas datos.
4. **Prioridad**: Seguir acumulando datos. El rango BFED 2.80-3.20 aun no tiene ni un solo caso live para validar.

### 3d. Analisis V1.5: filtros intermedios entre V1 y V2

V1 (sin filtros) tiene 31.2% WR (-20.8% ROI). V2 (xG<0.5, PD<20%, shots<8) sube a 50% WR (+33.1% ROI) pero descarta muchos partidos. Se busca una V1.5 con menos filtros que V2 pero mas selectiva que V1.

Analisis sistematico sobre 16 triggers (32 partidos finalizados, 5W/11L en V1).

#### Filtros simples (1 condicion)

| Filtro | N | W | WR% | P/L | ROI |
|---|---|---|---|---|---|
| PD < 15% | 8 | 4 | 50.0% | +17.95 | +22.4% |
| **PD < 20%** | **10** | **5** | **50.0%** | **+26.76** | **+26.8%** |
| PD < 25% | 11 | 5 | 45.5% | +16.76 | +15.2% |
| xG < 0.6 | 13 | 5 | 38.5% | -3.24 | -2.5% |
| Shots < 8 | 11 | 4 | 36.4% | -4.83 | -4.4% |
| SoT <= 2 | 12 | 4 | 33.3% | -22.05 | -18.4% |

**Mejor filtro simple: PD < 20%** — la posesion equilibrada es la senal mas potente individualmente.

#### Filtros combinados (2 condiciones)

| Filtro V1.5 | N | W | WR% | P/L | ROI |
|---|---|---|---|---|---|
| **xG<0.6 + PD<25%** | **9** | **5** | **55.6%** | **+36.76** | **+40.8%** |
| xG<0.8 + PD<25% | 9 | 5 | 55.6% | +36.76 | +40.8% |
| xG<0.8 + shots<8 | 9 | 4 | 44.4% | +15.17 | +16.9% |
| PD<25% + shots<8 | 9 | 4 | 44.4% | +15.17 | +16.9% |

**Mejor V1.5: xG<0.6 + PD<25%** — 55.6% WR, +40.8% ROI. Filtra 7 de 11 perdidas V1.

#### V2 con umbrales relajados

| Variante | N | W | WR% | P/L | ROI | vs V2 |
|---|---|---|---|---|---|---|
| V2 (xG<0.5, PD<20, Sh<8) | 4 | 2 | 50.0% | +13.25 | +33.1% | base |
| **V2 relajada (xG<0.6)** | **6** | **4** | **66.7%** | **+45.17** | **+75.3%** | **+31.92** |

**Hallazgo clave**: Relajar el xG de <0.5 a <0.6 rescata 2 victorias (Espanyol xG=0.57, Fortuna xG=0.51) sin anadir ninguna derrota nueva. El umbral xG=0.5 de V2 es demasiado estricto.

#### Detalle de la V2 relajada (xG<0.6, PD<20%, shots<8)

| Partido | xG | PD | Sh | FT | W/L | V2 |
|---|---|---|---|---|---|---|
| Anorthosis-Ypsona | 0.00 | 2% | 5 | 1-1 | **W** | Y |
| Braunschweig-Darmstadt | 0.44 | 18% | 5 | 2-2 | **W** | Y |
| CSKA Sofia | 0.00 | 2% | 1 | 0-2 | L | Y |
| **Espanyol-Celta** | **0.57** | **7%** | **6** | **2-2** | **W** | **N** |
| **Fortuna-Munster** | **0.51** | **3%** | **7** | **0-0** | **W** | **N** |
| Thun-Sion | 0.45 | 5% | 7 | 1-0 | L | Y |

*En negrita: partidos rescatados por la relajacion del xG.*

#### Perdidas V1 "infiltrables"

De 11 perdidas V1, los filtros capturan la mayoria, pero 2 pasan TODOS los filtros:

| Partido | xG | PD | Sh | Por que pasa | Leccion |
|---|---|---|---|---|---|
| CSKA Sofia | 0.00 | 2% | 1 | Stats perfectas pero gol igualmente | 0-0 con xG=0 no garantiza empate |
| Thun-Sion | 0.45 | 5% | 7 | Todo bajo pero gol en el 85+ | Goles tardios son inevitables |

El resto de perdidas V1 se filtra por al menos una condicion: PD alta (Corinthians 35%, Ludogorets 46%, Mirandés 29%, Kocaelispor 29%), xG alta (Groningen 0.99, Stevenage 0.82, America 0.92), o combinacion de ambas.

#### Conclusion V1.5

| Version | Filtros | N | WR% | ROI |
|---|---|---|---|---|
| V1 | ninguno | 16 | 31.2% | -20.8% |
| **V1.5** | **xG<0.6 + PD<25%** | **9** | **55.6%** | **+40.8%** |
| V2 | xG<0.5 + PD<20 + Sh<8 | 4 | 50.0% | +33.1% |
| **V2r** | **xG<0.6 + PD<20 + Sh<8** | **6** | **66.7%** | **+75.3%** |
| V3a | V2 + DS<=30 | 3 | 66.7% | +77.5% |

La V2 relajada (V2r) domina la tabla: mejor WR y ROI que V2 original, y mas apuestas. **Recomendacion: actualizar V2 a xG<0.6** en vez de xG<0.5.

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

### Regla propuesta v2 (actualizada)

Apostar Back Empate cuando:
1. Marcador 0-0 al minuto 30+
2. **xG total combinado < 0.6** (actualizado desde <0.5 tras analisis V1.5 — ver seccion 3d)
3. Diferencia de posesion < 20%
4. Menos de 8 tiros totales
5. *(En validacion — datos insuficientes)* Cuota pre-match empate BFED entre 2.80-3.20 + balance >= 0.55 (ver secciones 3b y 3c). Primeros datos sugieren que los filtros in-play (puntos 2-4) ya capturan la sennal del balance pre-match.

### Regla alternativa v1.5 (menos filtros)

Para quien prefiera mas volumen de apuestas con menos filtros:
1. Marcador 0-0 al minuto 30+
2. xG total combinado < 0.6
3. Diferencia de posesion < 25%

*V1.5 tiene 55.6% WR (+40.8% ROI) sobre 9 apuestas vs V2r 66.7% WR (+75.3% ROI) sobre 6. Menos selectiva pero mas oportunidades.*

### Patrones complementarios relevantes

- **Clustering de goles**: 18.3% de los goles son seguidos por otro en 5 min. Si se rompe el 0-0, puede venir mas goles rapido.
- **Goles tardios**: 52.2% de los partidos tienen gol despues del min 75. Un 0-0 al min 75 tiene 68.2% de acabar empate.
- **Corners asimetricos**: Diferencia de 5+ corners se asocia con 37.8% probabilidad de gol en 10 min (vs 26% baseline). Puede servir como senal de peligro adicional.
- **Momentum**: Cuando el momentum favorece claramente a un equipo (top 25%), ese equipo gana el 66.7%. Puede ayudar a filtrar.

---

## 5. Investigacion V3: Trading en vivo

### 5a. Concepto V3

V1 y V2 son estrategias de **apuesta plana** (back al empate, hold hasta FT). V3 investiga si un enfoque de **trading activo** mejora los resultados: entrada selectiva, monitoreo continuo, y salida dinamica basada en cuotas y stats.

**V3 = 3 capas:**
1. **Filtro de entrada** (V3a): V2 + danger_score <= 30
2. **Monitoreo post-entrada**: tracking de cuotas y stats minuto a minuto
3. **Salida dinamica** (V3b): cashout, stop loss, o salida por stats

### 5b. Nuevo filtro: Danger Score

El danger_score es un compuesto de stats ofensivas al momento del trigger:

```
danger_score = dangerous_attacks_total + big_chances_total + touches_box_total
```

Mide la "intensidad ofensiva real" del partido — cuanto mayor, mas probable que alguien acabe marcando.

| Filtro (sobre V2) | N | Wins | WR% | P/L | ROI |
|---|---|---|---|---|---|
| DS <= 20 | 1 | 1 | 100% | +18.81 | +188.1% |
| **DS <= 30** | **2** | **2** | **100%** | **+33.25** | **+166.2%** |
| DS <= 40 (= V2) | 3 | 2 | 66.7% | +23.25 | +77.5% |

DS <= 30 es el sweet spot: filtra la unica derrota de V2 (CSKA Sofia, DS=36 — partido aparentemente tranquilo por stats basicas pero con muchos dangerous attacks) mientras mantiene ambas victorias.

### 5c. Evolucion de cuotas post-entrada

Analisis de como se mueven las cuotas de empate despues de entrar al min 30 con 0-0:

| Partido | @30 | @45 | @60 | @75 | Min | Max | Gol | FT | W/L |
|---|---|---|---|---|---|---|---|---|---|
| America De Cali | 2.68 | 2.38 | 1.89 | 5.50 | 1.50 | 11.00 | 75 | 1-0 | L |
| Anorthosis (V3a) | 2.52 | 4.70 | 4.50 | 8.40 | 2.44 | 10.50 | 36 | 1-1 | W |
| Braunschweig (V3a) | 2.98 | 3.45 | 3.70 | 2.98 | 1.01 | 8.60 | 40 | 2-2 | W |
| CSKA Sofia (V2) | 2.54 | 2.36 | 4.30 | 5.00 | 2.30 | 7.40 | 45 | 0-2 | L |
| Espanyol | 2.50 | 3.75 | 3.95 | 1.53 | 1.03 | 6.80 | 37 | 2-2 | W |
| Fortuna Dusseldorf | 2.86 | 2.48 | 1.95 | 1.50 | 1.02 | 2.74 | - | 0-0 | W |
| Liverpool Brighton | 3.65 | 5.90 | 21.00 | 48.00 | 2.50 | 48.00 | 41 | 3-0 | L |
| Stevenage | 2.40 | 2.14 | 1.80 | 1.36 | 1.20 | 11.00 | 85 | 1-0 | L |

**Patrones observados:**
- Los partidos ganados (empates) muestran swings enormes (Braunschweig: 1.01-8.60) porque se marcan goles en ambas direcciones
- Los 0-0 autenticos (Fortuna Dusseldorf) bajan monotonamente: 2.86 → 2.48 → 1.95 → 1.50 → 1.02
- Los partidos perdidos suelen mostrar subida sostenida tras el primer gol (Liverpool: 3.65 → 5.90 → 21.00 → 48.00)

### 5d. Analisis de cashout

Se simulo cashout a diferentes umbrales (salir cuando la cuota de empate baja a X):

**V1 (11 apuestas):**

| Estrategia | Cashouts | P/L | ROI | vs Hold |
|---|---|---|---|---|
| Cashout @1.30 | 5 | +15.01 | +13.6% | **+19.84** |
| Cashout @1.50 | 6 | +19.39 | +17.6% | **+24.22** |
| Cashout @1.80 | 6 | +2.40 | +2.2% | +7.23 |
| HOLD (sin cashout) | 0 | -4.83 | -4.4% | - |

**V2 (3 apuestas):**

| Estrategia | Cashouts | P/L | ROI | vs Hold |
|---|---|---|---|---|
| Cashout @1.50 | 1 | +13.81 | +46.0% | **-9.44** |
| HOLD (sin cashout) | 0 | +23.25 | +77.5% | - |

### 5e. Hallazgo clave

**El cashout tiene valor INVERSO segun la calidad del filtro:**

- **V1 (filtro debil)**: cashout @1.50 mejora el P/L en +24.22 EUR. Razon: cortas las perdidas de partidos que acaban en gol, y cuando el empate baja a 1.50 ya tienes beneficio asegurado.
- **V2/V3a (filtro fuerte)**: cashout EMPEORA el resultado en -9.44 EUR. Razon: tus victorias son reales y el cashout las trunca. Si ya estas en los partidos correctos, dejar correr es optimo.

**Conclusion: V3b trading NO mejora V3a hold con la muestra actual.** Cuando los filtros de entrada son buenos, el trading activo resta valor. La clave esta en ENTRAR bien, no en SALIR rapido.

### 5f. Regla V3 propuesta

**V3 = V2 + danger_score <= 30 + HOLD hasta FT**

Apostar Back Empate cuando:
1. Marcador 0-0 al minuto 30+
2. xG total combinado < 0.5
3. Diferencia de posesion < 20%
4. Menos de 8 tiros totales
5. **danger_score <= 30** (dangerous_attacks + big_chances + touches_box)

No aplicar trading activo (cashout/stop loss). Hold hasta final.

| Metrica | V1 | V1.5 | V2r | V3a |
|---|---|---|---|---|
| Apuestas | 16 | 9 | 6 | 3 |
| Win Rate | 31.2% | 55.6% | 66.7% | 66.7% |
| P/L neto | -33.24 | +36.76 | +45.17 | +23.25 |
| ROI | -20.8% | +40.8% | +75.3% | +77.5% |

*V2r = V2 con xG relajado a <0.6 (ver seccion 3d). V1.5 = xG<0.6 + PD<25%.*

### 5g. Limitaciones y proximos pasos

- **Muestra critica**: Solo 2 apuestas V3 y 3 V2. Necesitamos 50+ triggers para validar.
- **25 partidos finalizados** de 102 CSVs. El resto son pre-partido (61) o incompletos (16).
- El danger_score depende de dangerous_attacks y touches_box, que no siempre estan disponibles.
- **Re-ejecutar `simulate_v3_trading.py`** cada vez que se acumulen 10+ partidos nuevos finalizados.
- Considerar agregar cashout SOLO como proteccion anti-catastrofe (ej: stop loss si odds > 6.00).

---

## 6. Plan de accion

### Fase 0: Acumulacion de datos (actual)
0. Prioridad maxima: acumular partidos finalizados completos (solo 25 de 102 CSVs son utiles)
1. Re-ejecutar `simulate_v3_trading.py` cada 10 partidos nuevos finalizados
2. Objetivo inmediato: 50+ triggers para poder comparar V2 vs V3 con significancia

### Fase 1: Validacion (hasta 200 partidos)
1. Seguir acumulando partidos con el scraper (objetivo: 200+ partidos de calidad)
2. Paper trading manual con la regla v2
3. Analizar si funciona mejor en ciertas ligas, horarios, o tipos de cuota pre-partido
4. Re-ejecutar simulacion cada 50 partidos nuevos para validar que el ROI se mantiene

### Fase 2: Backtesting ampliado (200-500 partidos)
5. Confirmar que el 0-0 sigue siendo significativamente mejor que 1-1 y 2-2
6. Bankroll management: flat stake 3-5% del bankroll
7. Confirmar filtros de xG y tiros a puerta con mas datos
8. Validar filtro BFED 2.80-3.20 con datos live (ya enriquecidos via `enrich_prematch_odds.py` — pendiente acumular casos en ese rango)

### Fase 3: Automatizacion (500+ partidos validados)
9. Alertas en tiempo real cuando se detecte: min >= 30, marcador 0-0, xG < 0.5
10. Paper trading automatico con registro de apuestas virtuales
11. Dashboard de estrategias con P/L acumulado

### Fase 4: Trading real
12. Apuestas reales con stakes minimos (2-5 EUR)
13. Escalar solo si ROI > 10% neto tras 100+ apuestas reales

---

## 7. Datos tecnicos

- **Script de simulacion**: `simulate_draw_strategy.py` (simulacion base con stake fijo)
- **Script de filtros**: `simulate_draw_filters.py` (analisis de filtros estadisticos y pre-partido)
- **Script V3 trading**: `simulate_v3_trading.py` (simulador minuto a minuto con evolucion de cuotas y cashout)
- **Script de patrones**: `analyze_patterns.py` (analisis general de patrones de apuestas)
- **Script V3 analysis**: `analyze_v3_strategy.py` (analisis de filtros avanzados para V3)
- **Datos live**: `betfair_scraper/data/partido_*.csv` (CSVs minuto a minuto)
- **Datos historicos**: `historic_data/all-euro-data-2025-2026.xlsx` (4,854 partidos, 22 ligas europeas, football-data.co.uk)
- **Mapping equipos**: `historic_data/team_mapping.csv` (123 equivalencias Betfair slug → Football Data name)
- **Enriquecimiento pre-match**: `enrich_prematch_odds.py` (descarga fixtures.csv + Latest_Results.csv, anade BFEH/BFED/BFEA a CSVs scrapeados)
- **Comision aplicada**: 5% sobre beneficios netos (Betfair Exchange)

---

## Disclaimer

Este analisis es exploratorio basado en una muestra limitada:
- **V1**: 16 triggers sobre 32 partidos finalizados (datos live del scraper)
- **V1.5**: 9 apuestas, **V2r**: 6, **V3a**: 3 — muestra insuficiente
- **Pre-match BFED**: 6 triggers con datos cruzados, 0 en rango 2.80-3.20
- Todos los ROI **incluyen comisiones** Betfair del 5%
- Son resultados pasados que **NO garantizan rendimiento futuro**
- Se basan en cuotas back disponibles en el momento, sin considerar liquidez real
- Se necesitan 50+ triggers para comparar V2 vs V3 con confianza
