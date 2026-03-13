# Market Scanner R19 — Hallazgos (2026-03-13)

## Metodología

Script `strategies/market_scanner.py` — escaneo exhaustivo de 54,600 combinaciones:
- **52 mercados** (match odds, over/under, correct score — BACK y LAY)
- **7 ventanas temporales** (40-60, 45-65, 50-70, 55-75, 60-80, 65-85, 70-90)
- **15 estados de marcador** (0-0, home+1, away+1, home+2, away+2, tied 1-1, 2-2, goals_ge2/3/4, etc.)
- **10 filtros de stats** (ninguno, xG home/away dom, xG bajo/alto, SoT home/away dom, posesión home/away)

**Quality gates (6):**
1. N >= 38 (max(15, 963//25))
2. ROI raw >= 15%
3. IC95 lower >= 40% (Wilson)
4. >= 3 ligas distintas
5. No más del 70% de bets en una liga
6. Train ROI > 0 Y Test ROI > 0 (split cronológico 70/30)

**Anti-tautología:** se excluyen combinaciones matemáticamente garantizadas (e.g., BACK Over 2.5 cuando ya hay 3 goles).

**Resultados:** 224 supervivientes, 155 genuinamente nuevos (sin overlap conocido con 26 estrategias activas).

Resultados completos: `analisis/scan_results_20260313_230107.csv`

---

## Patrones dominantes detectados

### PATRÓN A: Estrategias con away team liderando (alto volumen)
Múltiples combinaciones de LAY Home / BACK Away / LAY Draw cuando away lidera (away+1) en ventanas 45-85 con xG bajo aparecen con N alto y ROI 30-55%. Muchas solapan con `away_fav_leading`, pero algunas variaciones con LAY Home y LAY Draw son genuinamente nuevas.

### PATRÓN B: Correct Score 1-1 como mercado LAY en contextos específicos
`LAY CS 1-1` aparece en múltiples ventanas (60-90) con distintos score states (away+1, lead1, any+xg_low). ROI 41-75%, N 39-89. Intuición: el mercado 1-1 es relativamente más "popular" (gusta a punters), por lo que se sobrevalora como resultado final en situaciones donde estadísticamente es poco probable.

### PATRÓN C: BACK Over 3.5 con 3+ goles antes de min 65
Con 3 goles ya marcados en la primera hora de juego, el mercado no ajusta lo suficiente las probabilidades de que haya un 4º gol. N=90-110, ROI=37%, Sharpe~3. No es tautológico (necesita un gol más que el marcador actual).

### PATRÓN D: BACK Home liderando + xG bajo (min 65-85)
Home team leading by 1 (home+1) en las fases finales con bajo xG. N=132-198 (muy robusto), ROI=20-23%, Sharpe~3. Concepto: en partidos de bajo xG donde local lleva ventaja, el "cierre de partido" es eficiente. Posible solapamiento con `home_fav_leading` (verificar).

### PATRÓN E: LAY Draw cuando un equipo lidera + xG bajo (50-80)
Varios combos de LAY Draw con lead1 o away+1 + xg_low, N=120-293, ROI=21-33%. Con ventaja y bajo xG, el empate es el resultado menos probable.

### PATRÓN F: BACK Under 3.5 con SoT home dominante (60-80)
Sin filtro de marcador, cualquier score, pero local tiene más SoT. N=57-67, ROI=38-40%, Sharpe~2.5-2.9. Interesante porque no requiere un score específico — la dominancia en tiros es el trigger.

---

## Top 15 candidatos genuinamente nuevos (sin overlap con 26 estrategias activas)

| # | Mercado | Ventana | Score | Filtro | N | WR% | ROI% | Sharpe | CI_lo | Tr_ROI | Te_ROI | Nota |
|---|---------|---------|-------|--------|---|-----|------|--------|-------|--------|--------|------|
| 1 | LAY CS 1-1 | 60-80 | away+1 | none | 39 | 94.9 | 75.5 | 5.55 | 83.1 | 80.7 | 63.7 | N borderline |
| 2 | LAY Home | 45-65 | away+1 | xg_low | 61 | 85.2 | 51.4 | 3.59 | 74.3 | 57.4 | 38.3 | Test cae |
| 3 | BACK Over 2.5 | 40-60 | goals_ge2 | xg_low | 239 | 77.0 | 17.8 | 3.41 | 71.2 | 20.3 | 12.2 | ROI marginal |
| 4 | LAY Home | 45-65 | away+1 | none | 65 | 84.6 | 48.3 | 3.35 | 73.9 | 51.5 | 41.1 | Mismo concepto que #2 |
| 5 | BACK Over 2.5 | 40-60 | goals_ge2 | none | 266 | 76.7 | 15.8 | 3.24 | 71.3 | 16.3 | 14.7 | ROI raw demasiado bajo |
| 6 | LAY CS 1-1 | 65-85 | lead1 | xg_low | 63 | 90.5 | 53.3 | 3.18 | 80.7 | 71.1 | 11.8 | Test colapsa |
| 7 | BACK Home | 65-85 | home+1 | xg_low | 169 | 75.1 | 23.0 | 3.10 | 68.1 | 22.5 | 24.4 | Posible overlap home_fav |
| 8 | LAY Home | 55-75 | away+1 | none | 39 | 87.2 | 54.2 | 3.09 | 73.3 | 46.8 | 70.9 | N borderline |
| 9 | **BACK Over 3.5** | **45-65** | **goals_ge3** | **none** | **110** | **64.5** | **37.0** | **3.07** | **55.3** | **35.6** | **40.5** | **Top candidato** |
| 10 | BACK Home | 65-85 | home+1 | none | 198 | 72.7 | 20.2 | 2.89 | 66.1 | 20.2 | 20.2 | Posible overlap home_fav |
| 11 | **BACK Under 3.5** | **60-80** | **any** | **sot_home** | **67** | **74.6** | **37.8** | **2.88** | **63.1** | **35.3** | **43.2** | **Top candidato** |
| 12 | BACK Home | 70-90 | home+1 | none | 161 | 75.2 | 21.9 | 2.83 | 67.9 | 24.5 | 16.0 | Test cae |
| 13 | BACK Over 2.5 | 40-60 | tied_1-1 | xg_low | 130 | 78.5 | 20.2 | 2.81 | 70.6 | 22.3 | 15.2 | ROI marginal |
| 14 | **BACK Over 3.5** | **40-60** | **goals_ge3** | **none** | **90** | **64.4** | **37.3** | **2.81** | **54.1** | **33.9** | **44.8** | **Top candidato** |
| 15 | BACK Home | 70-90 | home+1 | xg_low | 132 | 76.5 | 23.5 | 2.76 | 68.6 | 28.0 | 13.3 | Test cae |

---

## Candidatos priorizados para validación profunda (R19)

Criterios de priorización: ROI > 20%, N > 60, Train/Test ambos positivos y estables, concepto genuinamente nuevo.

### CANDIDATO A: BACK Over 3.5 con 3+ goles antes de min 65
**Concepto:** con 3 goles marcados antes del minuto 65, el mercado infravalora la probabilidad de un 4º gol. El juego ya demostró ser abierto y ofensivo, pero las odds de Over 3.5 siguen siendo "largas" porque el mercado da peso a que ambos equipos gestionen.

- Ventana óptima: 40-65 (combinar #9 y #14)
- N=90-110, ROI=37%, Sharpe=2.81-3.07, Train/Test estables
- **No cubre ninguna estrategia existente** (lay_over45_blowout es diferente: LAY O4.5 con pocos goles)
- Siguiente paso: backtest detallado con grid de parámetros, luego validador realista

### CANDIDATO B: LAY CS 1-1 en situaciones de desequilibrio
**Concepto:** en partidos donde hay un líder claro (away+1, o lead1) la probabilidad de que el marcador termine exactamente en 1-1 es muy baja, pero el mercado sigue "preciando" ese CS con odds relativamente bajas porque 1-1 es el resultado de empate más común.

- Mejor combo: 60-80, away+1, N=39 ROI=75.5% — pero N muy borderline
- Variante más robusta: 65-85, lead1, N=89, ROI=41.1% — pero test ROI = 1.3% (cae mucho)
- **Riesgo:** N bajo y test instable. Necesita validación cuidadosa.
- Siguiente paso: investigar si el score state "away+1" incluye solo 0-1 o también 1-2, 2-3...

### CANDIDATO C: BACK Under 3.5 con SoT home dominante (sin score filter)
**Concepto:** cuando el equipo local domina en tiros a puerta sin que eso se traduzca en goles (SoT_home >= SoT_away + 2), el partido es "controlado" por el local y es improbable que alcance 4+ goles.

- N=67, ROI=37.8%, Sharpe=2.88, Train=35.3%, Test=43.2% (test MEJOR que train — robusto)
- **Concepto genuinamente nuevo** — under35_late requiere score 1-0/0-1 y bajo xG; esta no exige score ni xG
- Siguiente paso: grid search con variantes de SoT threshold y ventana temporal

### CANDIDATO D: LAY Home / LAY Draw con away liderando + xG bajo
**Concepto:** cuando away lidera a mitad partido con bajo xG, el mercado sobrevalora al home team (por sesgo de favoritismo local). LAY Home o LAY Draw son apuestas equivalentes en este contexto.

- Multiple combos consistentes, N=39-123, ROI=33-54%, pero varios tienen Test ROI que cae
- **Posible overlap** con away_fav_leading (verificar % de matches compartidos)
- Candidato secundario — depende del análisis de overlap

---

## Red flags y descartados del scanner

### Descartados automáticamente (en el scanner):
- Over X.5 + goals_ge(X+1) → tautologías (win ya garantizado)
- LAY Under X.5 + goals_ge(X+1) → tautologías

### A descartar manualmente (candidatos con problemas claros):
- BACK Over 2.5 con goals_ge2 (#3, #5): ROI raw 15-18% — no sobrevivirá el realistic validator (necesita >15% para el -2% de slippage + filtro de odds)
- LAY CS 1-1 con lead1 (#6): Test ROI = 1.3% — claramente overfitted al train
- Cualquier candidato con Test ROI < 10% se descarta sin investigar más

---

## Limitaciones del scanner

1. **Múltiples comparaciones:** con 54,600 combos, ~2,700 pasarían ROI gate por azar (p<0.05). Los 6 gates reducen esto drasticamente pero no eliminan el ruido completamente.

2. **Score states simplificados:** "away+1" incluye todos los scores donde away lidera por 1 (0-1, 1-2, 2-3...). Las estrategias reales suelen ser más específicas.

3. **Stats sin ventana temporal:** los filtros de stats (xG, SoT, posesión) usan valores acumulados del partido, no de los últimos N minutos. Puede estar capturando señales que en live serían más débiles.

4. **Odds range genérico:** los rangos de odds por mercado son amplios. Un grid search más fino podría mejorar o deteriorar los resultados.

5. **Sin deduplicación:** el scanner no aplica deduplicación de mercado (una bet por mercado por partido). Los candidatos en mercados ya cubiertos podrían solapar más de lo detectado.

---

## Siguientes pasos (R19 — próxima sesión)

1. **Validar CANDIDATO A** (BACK Over 3.5, goals_ge3, 40-65) con backtest detallado + validador realista
2. **Validar CANDIDATO C** (BACK Under 3.5, sot_home, 60-80) con grid de SoT threshold
3. **Análisis de overlap** del CANDIDATO D (LAY Home/Draw con away leading) vs away_fav_leading
4. **Investigar LAY CS 1-1** solo si score state "away+1" = específicamente 0-1 (más restrictivo)
5. **Actualizar tracker** con candidatos A-D (H102+)
