# Cartera Final de Estrategias - Conclusiones

**Fecha**: 16 Febrero 2026
**Muestra**: 63 apuestas simuladas (153 partidos históricos)
**Periodo**: 12-15 Febrero 2026

---

## Resumen Ejecutivo

Tras analizar y simular 3 estrategias principales durante 153 partidos históricos, se ha identificado la **cartera óptima** para operar en Betfair Exchange:

- **Estrategia sin gestión** (validación inicial): Back Empate V2r + xG V2 + Odds Drift V1 → **+446.62 EUR** (ROI +54.5%)
- **Estrategia con gestión** (largo plazo): Mismas estrategias + **Half-Kelly** → **+1638.15 EUR** (ROI +327.6%)

---

## 1. Mejor Estrategia SIN Gestión de Cartera

### Configuración Recomendada para Validación Inicial

**Objetivo**: Validar las estrategias con stake fijo durante las primeras 50-100 apuestas reales antes de implementar gestión de bankroll.

| Componente | Versión | Condiciones de Entrada |
|------------|---------|------------------------|
| **Back Empate 0-0** | **V2r** | Trigger: 0-0 al min 30+ <br> Filtros: xG combinado <0.6 + Posesión Dominante <20% + Tiros <8 <br> Apuesta: Back Draw |
| **xG Underperformance** | **V2** | Trigger: Equipo PERDIENDO + (xG_equipo - goles_equipo) >= 0.5 (min 15+) <br> Filtro: Tiros a puerta >= 2 <br> Apuesta: Back Over (total+0.5) |
| **Odds Drift Contrarian** | **V1** | Trigger: Equipo GANANDO 1-0 + drift cuota >= 25% en 10min <br> Apuesta: Back equipo (mantiene ventaja) |

### Stake: 10 EUR fijo por apuesta

### Resultados Esperados (basado en simulación histórica)

- **Total apuestas**: 45 (7 Draw + 11 xG + 27 Drift)
- **Win Rate**: 66.67% (30/45)
- **P/L neto**: +446.62 EUR
- **ROI**: +54.5% (10 EUR/apuesta × 45 = 650 EUR invertido)
- **Max Drawdown**: -101.73 EUR (de +408 cayó a +306, 25% devuelto)
- **Peor racha**: 6 fallos seguidos (#51 a #56)

### Desglose por Estrategia

| Estrategia | Apuestas | Win Rate | P/L | ROI |
|------------|----------|----------|-----|-----|
| Back Empate V2r | 7 | 57.1% | +35.17 EUR | **+50.2%** |
| xG Underperf V2 | 11 | 72.7% | +27.13 EUR | **+24.7%** |
| Odds Drift V1 | 27 | 66.7% | +384.32 EUR | **+142.3%** |

### Por Qué Esta Configuración

1. **V2r de Back Empate**: Mejor balance entre sample (7 apuestas) y ROI (50.2%). V2 solo tiene 5 apuestas.
2. **V2 de xG**: El filtro SoT>=2 duplica el ROI (6.6% → 24.7%) validando que el equipo está atacando de verdad.
3. **V1 de Odds Drift**: Muestra más grande (27 apuestas), ROI excelente (142%), menos riesgo que versiones filtradas.

### Reglas de Operación (Stake Fijo)

- Apostar **10 EUR** en cada trigger que cumpla las condiciones
- **No perseguir** pérdidas (no aumentar stake tras rachas negativas)
- **Registrar** cada apuesta: partido, minuto, condiciones, odds, resultado
- **Revisar** tras 50 apuestas: si WR real < 55%, pausar y analizar
- **Objetivo**: Validar que el WR real se mantiene cerca del 67% simulado

---

## 2. Mejor Estrategia CON Gestión de Cartera (Largo Plazo)

### Configuración Óptima para Maximizar Crecimiento

**Objetivo**: Maximizar el beneficio absoluto usando gestión de bankroll una vez validadas las estrategias (después de 50-100 apuestas exitosas con stake fijo).

### Mismas Estrategias + Half-Kelly Bankroll Management

| Componente | Configuración |
|------------|---------------|
| **Estrategias** | Back Empate V2r + xG Underperf V2 + Odds Drift V1 (iguales que sin gestión) |
| **Bankroll Inicial** | 500 EUR |
| **Modo de Gestión** | **Half-Kelly** |
| **Cálculo de Stake** | stake% = Kelly_fraction / 2, donde Kelly = (WR × odds_netas - (1 - WR)) / odds_netas <br> Mínimo: 1% bankroll <br> Máximo: 4% bankroll |

### Resultados Esperados (basado en simulación histórica)

- **Total apuestas**: 45 (mismas que sin gestión)
- **Win Rate**: 66.67% (30/45)
- **P/L neto**: **+1638.15 EUR**
- **ROI**: **+327.6%** (sobre bankroll inicial de 500 EUR)
- **Bankroll final**: 2138 EUR (de 500 inicial)
- **Max Drawdown**: -681.96 EUR (de bankroll 1973 cayó a 1291, nunca bajó de 500 inicial)
- **% DD sobre bankroll inicial**: 136% (cayó 681 desde pico, pero pico era +1473 sobre inicial)

### Comparativa: Half-Kelly vs Otras Gestiones

| Modo | P/L | ROI | Bankroll Final | Max DD |
|------|-----|-----|----------------|--------|
| **Half-Kelly** (recomendado) | **+1638 EUR** | **+327.6%** | 2138 EUR | -682 EUR |
| Kelly completo | +2572 EUR | +514.3% | 3072 EUR | **-3357 EUR** ⚠️ |
| Fijo 2% | +422 EUR | +84.4% | 922 EUR | -198 EUR |
| Protección DD | +385 EUR | +77% | 885 EUR | -115 EUR |

### Por Qué Half-Kelly

**✅ Ventajas**:
- **3.9x más beneficio** que stake fijo (1638 vs 422 EUR)
- **Drawdown manejable** (-682 EUR vs -3357 del Kelly completo)
- **Matemáticamente óptimo** para maximizar crecimiento logarítmico con riesgo controlado
- **Se adapta** a rachas: apuesta más cuando va ganando, menos cuando va perdiendo

**❌ Por qué NO Kelly completo**:
- DD de -3357 EUR es psicológicamente devastador
- Caída de bankroll de 5759 a 2402 (-58% desde pico) puede hacer abandonar la estrategia
- Un solo error en estimación de WR puede causar overbetting catastrófico

**❌ Por qué NO Fijo 2% o Protección DD**:
- Muy conservadores para un WR de 67%
- Dejan dinero en la mesa (Half-Kelly da 3.9x más que Fijo 2%)

### Reglas de Operación (Half-Kelly)

1. **Calcular WR rolling** antes de cada apuesta (solo de apuestas PREVIAS, no futuras):
   - Primeras 5 apuestas: usar WR estimado 50% (conservador)
   - Después de 5 apuestas: WR = aciertos previos / apuestas previas

2. **Calcular Kelly fraction**:
   ```
   odds_netas = odds_back - 1
   kelly = (WR × odds_netas - (1 - WR)) / odds_netas
   ```

3. **Aplicar Half-Kelly**:
   ```
   stake% = kelly / 2
   stake% = max(1%, min(stake%, 4%))  // entre 1% y 4% del bankroll
   stake_EUR = bankroll_actual × stake%
   ```

4. **Actualizar bankroll** después de cada apuesta:
   ```
   bankroll_nuevo = bankroll_anterior + P/L_apuesta
   ```

5. **Monitoreo continuo**:
   - Si bankroll cae >30% desde pico: reducir a Fijo 2% temporalmente
   - Si WR rolling cae <50% durante 20 apuestas: pausar y re-analizar

---

## 3. Plan de Implementación

### Fase 1: Validación (Primeras 50-100 apuestas)

**Duración estimada**: 2-4 semanas
**Modo**: Stake fijo 10 EUR
**Objetivo**: Confirmar que WR real >= 60%

**Criterios de éxito**:
- ✅ WR >= 60% después de 50 apuestas
- ✅ P/L positivo después de 50 apuestas
- ✅ Ninguna estrategia individual con WR < 40%

**Criterios de fracaso (detener y re-analizar)**:
- ❌ WR < 55% después de 50 apuestas
- ❌ P/L negativo después de 75 apuestas
- ❌ Alguna estrategia con WR < 30% y >10 apuestas

### Fase 2: Transición a Half-Kelly (Apuestas 101-200)

**Modo**: Half-Kelly con bankroll inicial = capital disponible
**Objetivo**: Validar gestión de bankroll

**Criterios de éxito**:
- ✅ Bankroll crece >20% en 100 apuestas
- ✅ Max DD < 40% del bankroll inicial
- ✅ WR se mantiene >= 60%

### Fase 3: Operación Normal (Apuestas 200+)

**Modo**: Half-Kelly optimizado
**Objetivo**: Crecimiento sostenido del capital

**Revisión mensual**:
- Analizar WR por estrategia
- Ajustar versiones si alguna estrategia falla consistentemente
- Considerar añadir nuevas estrategias si WR validado >70%

---

## 4. Gestión de Riesgo

### Límites Estrictos

1. **Bankroll dedicado**: Nunca operar con más del 50% del capital total disponible
2. **Stop-loss global**: Si bankroll cae 50% desde inicial, pausar 1 semana y re-evaluar
3. **Stop-loss por estrategia**: Si alguna estrategia tiene WR <40% con >20 apuestas, desactivarla
4. **Max apuestas/día**: 5 apuestas máximo (evitar tilt y perseguir pérdidas)
5. **Max stake por apuesta**: Nunca >5% del bankroll (aunque Half-Kelly recomiende más)

### Señales de Alerta

⚠️ **Pausar operaciones si**:
- 3 días consecutivos con pérdidas
- Racha de 10+ pérdidas seguidas
- Bankroll cae >40% desde pico en 1 semana
- WR rolling cae <50% durante 30 apuestas

---

## 5. Tracking y Mejora Continua

### Métricas a Registrar por Apuesta

- Fecha/hora del partido
- Estrategia + versión utilizada
- Minuto del trigger
- Condiciones cumplidas (xG, drift%, score, etc.)
- Odds back apostada
- Stake en EUR
- Resultado (won/lost)
- P/L neto
- Bankroll después de apuesta
- Observaciones (si algo no cuadró)

### Revisión Semanal

- WR acumulado global y por estrategia
- ROI acumulado
- Max DD alcanzado
- Comparar métricas reales vs simuladas
- Identificar partidos/ligas problemáticos

### Revisión Mensual

- Decisión: continuar, ajustar o pausar cada estrategia
- Evaluar si incorporar nuevas versiones filtradas
- Ajustar bankroll mode si es necesario
- Actualizar simulaciones con datos nuevos

---

## 6. Limitaciones y Disclaimers

### Limitaciones de la Simulación

1. **Muestra pequeña**: 45 apuestas simuladas (63 totales antes de filtros)
   - Odds Drift: solo 27 apuestas, necesita >100 para validar
   - Back Empate V2r: solo 7 apuestas, alta varianza
   - xG Underperf V2: solo 11 apuestas, intervalo confianza amplio

2. **Datos históricos**: Basado en partidos 12-15 Feb 2026
   - Resultados pasados **NO garantizan** rendimiento futuro
   - Cuotas pueden cambiar (menor liquidez, mercado más eficiente)
   - Calidad de datos depende del scraper (pueden haber errores)

3. **No considera**:
   - Slippage (cuotas disponibles vs cuotas ejecutadas)
   - Liquidez insuficiente en algunos mercados
   - Suspensión de mercados durante el partido
   - Errores humanos al colocar apuestas
   - Costes de oportunidad (tiempo dedicado)

### Riesgos

⚠️ **Riesgo de ruina**: Aunque Half-Kelly minimiza riesgo, una racha de 15-20 pérdidas seguidas puede reducir bankroll >50%

⚠️ **Sobreajuste**: Las versiones filtradas (V2r, V2) pueden estar sobreajustadas a estos 153 partidos históricos

⚠️ **Cambios de mercado**: Si Betfair detecta patron ganador, pueden reducir límites o ajustar cuotas

⚠️ **Factor psicológico**: Ver el bankroll caer -682 EUR desde pico de +1473 requiere disciplina férrea

---

## 7. Estrategias Analizadas y Descartadas

Durante el análisis de 153 partidos históricos se exploraron múltiples estrategias. A continuación el resumen de las **descartadas**:

### ❌ Sharp Odds Drop - Backing al Favorito (ROI: -43.0%)

**Concepto**: Apostar al equipo cuyas cuotas bajan >20% en 10 minutos (favorito emergente)

**Resultados**:
- 125 triggers totales
- Win Rate: 36%
- ROI: **-43.0%** (destruye dinero)

**Conclusión**: Llegar tarde a movimientos de cuotas es regalar dinero al mercado. El momento óptimo ya pasó.

**Desglose por momento**:
| Periodo | Triggers | WR | ROI |
|---------|----------|-----|-----|
| Min 0-30 | 61 | 41.0% | -27.4% |
| Min 31-60 | 40 | 30.0% | -56.1% |
| Min 61-90+ | 24 | 33.3% | -60.8% |

Cuanto más tarde en el partido, peor el ROI (mercado ya ajustó correctamente).

---

### ❌ Equipo Domina pero Pierde (ROI: +56.8%)

**Concepto**: Apostar a equipo que domina estadísticas (posesión, tiros) pero va perdiendo

**Resultados**:
- 12 casos detectados
- Win Rate: 16.7%
- ROI: +56.8% (cuotas medias 10.85)

**Conclusión**: Solo 12 casos = **ruido estadístico**, no una estrategia validable. Muestra insuficiente y cuotas de lotería.

---

### ❌ Fade al Overperformer (ROI: +63.1%)

**Concepto**: Apostar contra el equipo que tiene más goles que xG (está "de suerte")

**Resultados**:
- 60 instancias
- Oponente gana: 20% (12/60)
- Cuotas medias del oponente: **19.59**

**Conclusión**: Cuotas de ~20.0 = lotería disfrazada. No es replicable, no es estrategia.

---

### ❌ Tarjetas Amarillas como Predictor de Goles (ROI: N/A)

**Concepto**: Las tarjetas amarillas predicen tensión → más goles

**Resultados**:
- Tasa de gol en 10 min post-tarjeta: **24.6%**
- Baseline normal sin tarjeta: **27.5%**

**Conclusión**: Las tarjetas **NO predicen goles**. De hecho, después de una tarjeta hay **menos** probabilidad de gol (partido se enfría).

---

### ❌ Odds Drift - Back al Perdedor Abandonado (ROI: -18.9%)

**Concepto original (FALLIDO)**: Cuando equipo que va PERDIENDO tiene drift odds >30%, el mercado lo abandona erróneamente → back a ese equipo

**Resultados**:
- 210 triggers (equipo perdiendo con drift)
- Win Rate: ~35%
- ROI: **-18.9%**

**Conclusión**: La hipótesis original era incorrecta. El mercado tenía razón al abandonar al perdedor.

**Descubrimiento clave**: Lo que **SÍ funciona** es lo contrario:
- Apostar al equipo que va **GANANDO** pero sufre drift → ROI +202.6%
- Versión final implementada: **Odds Drift Contrarian V1** (incluida en cartera final)

---

### 📊 Patrones Complementarios Identificados (No convertidos en estrategias)

Estos patrones tienen valor estadístico pero no se convirtieron en estrategias operables:

**Goles Tardíos (75+)**:
- 52.2% de partidos tienen gol después del min 75
- Con 2 goles al min 75: 71.4% tienen gol tardío
- Con posesión local >55% al min 75: 68.8% tienen gol tardío

**Clustering de Goles**:
- 18.3% de goles seguidos por otro en 5 min
- 38.5% de goles seguidos por otro en 10 min
- Media entre goles consecutivos: 17.2 min

**Corners como Predictor**:
- Diferencia de 5+ corners: 37.8% probabilidad de gol en 10 min (vs 26% baseline)
- Útil como filtro secundario, no como estrategia principal

**Momentum del Scraper**:
- Cuando momentum favorece claramente al local (top 25%): home win 66.7%
- El momentum capturado **SÍ tiene valor predictivo**
- Potencial para estrategia futura si se refina

---

### Resumen: Por Qué Se Descartaron

| Estrategia | Razón de Descarte |
|------------|-------------------|
| Sharp Odds Drop | ROI negativo brutal (-43%), llegar tarde al mercado |
| Equipo Domina Perdiendo | Muestra insuficiente (12 casos), ruido estadístico |
| Fade Overperformer | Cuotas de lotería (~20.0), no replicable |
| Tarjetas Amarillas | Correlación negativa con goles (opuesto a hipótesis) |
| Drift Back Perdedor | Hipótesis incorrecta, ROI negativo (-18.9%) |

**Lección clave**: De 8 hipótesis iniciales, solo 3 resultaron rentables tras filtrado riguroso. El 62.5% de ideas iniciales se descartaron por datos.

---

## 8. Conclusión

La cartera óptima identificada combina:
- **Back Empate V2r**: Sólida (50% ROI) en partidos de bajo xG
- **xG Underperf V2**: Excelente (24.7% ROI) cuando equipo pierde pero ataca
- **Odds Drift V1**: Excepcional (142% ROI) cuando mercado abandona al ganador

**Para validación inicial** → Stake fijo 10 EUR, esperado **+446 EUR** en 45 apuestas

**Para largo plazo** → Half-Kelly, esperado **+1638 EUR** en 45 apuestas (3.9x más)

El éxito depende de:
1. ✅ Disciplina estricta en criterios de entrada
2. ✅ Gestión emocional durante drawdowns
3. ✅ Registro meticuloso de cada apuesta
4. ✅ Revisión y ajuste continuo basado en datos reales

---

**Próximos pasos**:
1. Iniciar Fase 1 con stake fijo 10 EUR
2. Trackear primeras 50 apuestas reales
3. Comparar WR real vs simulado (esperado 67%)
4. Si validado → transitar a Half-Kelly en Fase 2
