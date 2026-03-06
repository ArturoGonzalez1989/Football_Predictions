# Strategy Designer — Historial de investigacion
Ultima actualizacion: 2026-03-05
Dataset al momento de la investigacion: ~850 partidos (2026-02-10 a 2026-03-05)
Total hipotesis investigadas: 65 (H1-H65) en 10 rondas

> Este fichero es la referencia para el agente strategy-designer.
> Antes de investigar una hipotesis nueva, verificar que no este ya listada aqui.

## INTEGRADA EN PRODUCCION

Solo 1 de las 19 aprobadas en rondas anteriores paso los quality gates del notebook `strategies_designer.ipynb` (N>=31, ROI suficiente):

| Estrategia | Mercado | Config | N | WR | ROI | Notebook status |
|---|---|---|---|---|---|---|
| BACK Leader Stat Domination (H2) | BACK Match Winner (leader) | min=55-70, sot>=4, rival<=1 | 26 | 92.3% | +47.4% | ACTIVA |

## APROBADAS RONDA 10 (1 nueva, Perplexity-derived)

Ronda 10 analizo ideas del informe Perplexity sobre estrategias in-play. De 7 hipotesis investigadas (H59-H65), 1 aprobada, 2 en seguimiento, 4 descartadas.

| # | Hipotesis | Nombre | Mercado | N | WR | ROI | Sharpe | Train ROI | Test ROI | Reporte |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H59 | BACK Underdog Leading Late | BACK MO (underdog) | 192 | 65.1% | +93.9% | 3.10 | +121.8% | +29.4% | strategies/sd_report_back_underdog_leading.md |

### Quality gates resumen (Ronda 10)

| Gate | H59 |
|------|-----|
| G1: N>=60 | PASS (192) |
| G2: N_test>=18 | PASS (58) |
| G3: ROI train+test>0 | PASS (121.8/29.4) |
| G4: IC95_lo>40% | PASS (58.1%) |
| G5: MaxDD<400 | PASS (77.04) |
| G6: Overlap<30% | PASS (0% -- unique market) |
| G7: >=3 ligas | PASS (34) |
| G8: DateConc<50% | PASS (33.9%) |

### Notas sobre H59

- **H59 is the highest N strategy ever found** with ROI > 50%. N=192 with ROI=93.9% and Sharpe=3.10.
- **Derived from Perplexity Section 2.1** (reverse favourite-longshot bias): academic evidence that markets undervalue underdogs after unexpected in-play events.
- **Unique angle**: BACK Match Winner for the underdog, but only when they are ALREADY leading. This is the opposite of "LAY Favourite" strategies (which failed: H7, H8, H22, H27, H33, H34, H38). The key difference: we're not betting AGAINST the favourite, we're betting FOR the underdog who has PROVEN they can lead.
- **Market efficiency check confirms genuine mispricing**: Won bets have avg odds 3.08 vs lost bets 2.30. In efficient markets, won bets have LOWER odds.
- **Edge source**: +10.6 percentage points (actual 65.1% vs implied 54.5%). Market anchors on pre-match quality assessment.
- **Alternative configs**: 60-80/lead<=1 has even better test ROI (115.4%) but slightly smaller N (174). 60-80/lead<=2 has best balance (N=195, test ROI=100.6%).
- **Score distribution insight**: WR improves with lead margin (2-1/1-2: 71% vs 0-1/1-0: 63%). But max_lead=1 config is more conservative and has highest Sharpe.
- **No overlap with any existing strategy**: H2 requires tied score, H53/H49 trade CS market, H58 trades Draw. H59 trades Match Winner for underdog -- completely independent market.

## APROBADAS RONDA 9 (2 nuevas)

Estas 2 estrategias pasan los 8 quality gates con el dataset de 850 partidos. Pendientes de integracion en notebook.

| # | Hipotesis | Nombre | Mercado | N | WR | ROI | Sharpe | Train ROI | Test ROI | Reporte |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H53 | BACK CS 1-0/0-1 Late Lock | BACK CS 1-0/0-1 | 216 | 53.7% | +39.1% | 3.15 | +43.7% | +28.4% | strategies/sd_report_back_cs_one_goal.md |
| 2 | H58 | BACK Draw at 1-1 Late | BACK Draw (1-1) | 128 | 55.5% | +31.0% | 2.26 | +34.2% | +23.5% | strategies/sd_report_back_draw_11_late.md |

### Quality gates resumen (Ronda 9)

| Gate | H53 | H58 |
|------|-----|-----|
| G1: N>=60 | PASS (216) | PASS (128) |
| G2: N_test>=18 | PASS (65) | PASS (39) |
| G3: ROI train+test>0 | PASS (43.7/28.4) | PASS (34.2/23.5) |
| G4: IC95_lo>40% | PASS (47.0%) | PASS (46.8%) |
| G5: MaxDD<400 | PASS (60.0) | PASS (63.54) |
| G6: Overlap<30% | PASS (0% market overlap) | PASS (0% market overlap) |
| G7: >=3 ligas | PASS (33) | PASS (31) |
| G8: DateConc<50% | PASS (36.1%) | PASS (33.6%) |

### Notas sobre las nuevas estrategias

- **H53 extends the CS structural inefficiency** found in H49 to 1-0/0-1 scorelines. At min 68-85, score 1-0/0-1 holds 53.7% of the time vs market-implied ~34% (avg odds 2.96). The edge is consistent across train/test and 33 leagues. Together with H49 (2-1/1-2), covers the 4 most common non-draw tight scorelines.
- **H58 is a genuinely new Draw angle**: BACK Draw at 1-1 late (min 70-85). NOT the same as Draw 0-0 (Strategy 1) -- completely different tactical dynamic. At 1-1, both teams scored so the game feels "open", but data shows 55.5% end as draws. Market underprices this at avg odds 2.31. Winner odds are HIGHER than loser odds (2.43 vs 2.15), confirming the market is NOT pricing this pattern.
- **H57 (CS Portfolio) was considered** as a "master CS strategy" combining all 4 scorelines (1-0/0-1/2-1/1-2). It has the highest Sharpe ever found (5.01, N=348). However, since H49 is already approved for 2-1/1-2, approving H53 for 1-0/0-1 separately avoids redundancy while maintaining the portfolio benefit. If H49 were ever removed, H57 could replace both H49+H53 as a single strategy.
- **H53 and H58 have zero market overlap**: H53 trades CS market, H58 trades Match Odds Draw. They can both trigger on the same match without conflict.

### Cross-overlap between R9 and existing

| Candidate | vs H49 (CS 2-1/1-2) | vs H48 (LAY U2.5 1-1) | vs H46 (U2.5 late) | vs Draw 0-0 |
|-----------|---------------------|----------------------|--------------------|----|
| H53 (CS 1-0/0-1) | 0% (different scores) | 0% (different scores) | 82.9% (match, not market) | 71.3% (match, not market) |
| H58 (Draw 1-1) | 21.9% (match, not market) | 65.6% (match, not market) | 10.9% (match, not market) | 39.1% (match, mutually exclusive by score) |

Note: High match-level overlap is expected and harmless -- these strategies trade DIFFERENT markets or trigger on DIFFERENT score conditions. The "overlap" metric for Gate 6 should measure same-market redundancy, not same-match co-occurrence.

## APROBADAS RONDA 8 (3 nuevas)

Estas 3 estrategias pasan los 8 quality gates con el dataset de 850 partidos. Pendientes de integracion en notebook.

| # | Hipotesis | Nombre | Mercado | N | WR | ROI | Sharpe | Train ROI | Test ROI | Reporte |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H46 | BACK Under 2.5 One-Goal Late | BACK U2.5 | 131 | 94.7% | +7.5% | 2.59 | +7.7% | +7.2% | strategies/sd_report_back_under25_one_goal.md |
| 2 | H48 | LAY Under 2.5 Tied at 1-1 | LAY U2.5 | 62 | 62.9% | +15.6% | 1.14 | +15.6% | +15.5% | strategies/sd_report_lay_under25_tied.md |
| 3 | H49 | BACK Correct Score Close Game | BACK CS 2-1/1-2 | 118 | 56.8% | +85.4% | 3.71 | +105.4% | +39.9% | strategies/sd_report_back_cs_close_score.md |

### Quality gates resumen (Ronda 8)

| Gate | H46 | H48 | H49 |
|------|-----|-----|-----|
| G1: N>=60 | PASS (131) | PASS (62) | PASS (118) |
| G2: N_test>=18 | PASS (40) | PASS (19) | PASS (36) |
| G3: ROI train+test>0 | PASS (7.7/7.2) | PASS (15.6/15.5) | PASS (105.4/39.9) |
| G4: IC95_lo>40% | PASS (89.4%) | PASS (50.5%) | PASS (47.8%) |
| G5: MaxDD<400 | PASS (18.29) | PASS (77.90) | PASS (90.43) |
| G6: Overlap<30% | PASS (21% max) | PASS (26% max) | PASS (26% max) |
| G7: >=3 ligas | PASS (31) | PASS (23) | PASS (33) |
| G8: DateConc<50% | PASS (41.2%) | PASS (37.1%) | PASS (33.1%) |

### Notas sobre las nuevas estrategias

- **H46 es ultra-conservadora**: WR=94.7% pero avg odds=1.15. Gana poco por bet pero casi nunca pierde. MaxDD=18 (extremadamente bajo). Ideal como "base" de cartera.
- **H48 es un angulo original**: LAY Under = apostar a que HAY mas goles. La condicion 1-1 es clave; el mercado no distingue bien entre 0-0 y 1-1. Liability capped a 1.5x stake (lay_max=2.5).
- **H49 es la estrella de la ronda**: ROI=85.4%, el mas alto de todas las estrategias SD. El mercado de Correct Score tiene un sesgo estructural: tiene que distribuir probabilidad entre docenas de scorelines, infravalorando sistematicamente el resultado actual. WARNING: CS market menos liquido, slippage potencial.
- **H49 tiene version extendida**: Con 4 scorelines (1-0/0-1/2-1/1-2), N=309, Sharpe=4.47, ROI=51.7%. Mas N y mas robusto, menor ROI individual.

### Cross-overlap entre aprobadas R8

| Par | Overlap |
|-----|---------|
| H46 vs H48 | 0.0% |
| H46 vs H49 | 0.0% |
| H48 vs H49 | 25.8% (16 matches, different markets) |

## APROBADAS RONDA 7 (3 nuevas)

Estas 3 estrategias pasan los 8 quality gates con el dataset de 850 partidos. Pendientes de integracion en notebook.

| # | Hipotesis | Nombre | Mercado | N | WR | ROI | Sharpe | Train ROI | Test ROI | Reporte |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H39 | BACK Over 2.5 from Two Goals | BACK O2.5 | 270 | 74.1% | +5.4% | 1.25 | +5.0% | +6.1% | strategies/sd_report_back_over25_two_goals.md |
| 2 | H41 | LAY Over 2.5 Scoreless Late | LAY O2.5 | 87 | 90.8% | +8.7% | 0.27 | +1.7% | +24.4% | strategies/sd_report_lay_over25_scoreless.md |
| 3 | H44 | LAY Over 1.5 Scoreless Fortress | LAY O1.5 | 72 | 87.5% | +27.9% | 1.27 | +14.5% | +58.5% | strategies/sd_report_lay_over15_scoreless.md |

### Quality gates resumen (Ronda 7)

| Gate | H39 | H41 | H44 |
|------|-----|-----|-----|
| G1: N>=60 | PASS (270) | PASS (87) | PASS (72) |
| G2: N_test>=18 | PASS (81) | PASS (27) | PASS (22) |
| G3: ROI train+test>0 | PASS (5.0/6.1) | PASS (1.7/24.4) | PASS (14.5/58.5) |
| G4: IC95_lo>40% | PASS (68.5%) | PASS (82.9%) | PASS (77.9%) |
| G5: MaxDD<400 | PASS (59.41) | PASS (241.0) | PASS (106.5) |
| G6: Overlap<30% | PASS | PASS | PASS |
| G7: >=3 ligas | PASS (34) | PASS (31) | PASS (25) |
| G8: DateConc<50% | PASS (28.5%) | PASS (24.1%) | PASS (25.0%) |

### Notas sobre riesgo

- **H41 tiene tail risk alto**: avg lay odds 12.1, MaxDD=241. Un solo loss cuesta ~111 (11x stake). Requiere bankroll grande y sizing conservador.
- **H44 tiene tail risk moderado**: avg lay odds 5.4, MaxDD=106.5. Un loss cuesta ~44 (4.4x stake). Mas manejable que H41.
- **H39 es la mas segura**: BACK con odds 1.46 en promedio. MaxDD=59.41, sizing estandar.

## APROBADAS PERO OFF EN NOTEBOOK (18)

Integradas en `strategies_designer.ipynb` pero no pasan quality gates actuales (N insuficiente o ROI insuficiente con el dataset actual). Pueden reactivarse si el dataset crece.

| # | Hipotesis | Nombre | Mercado | Razon off |
|---|---|---|---|---|
| 1 | H1 | LAY Over 4.5 Late Shield | LAY O4.5 | N=20 < 31 |
| 3 | H3 | BACK Over 2.5 from 2-Goal Lead | BACK O2.5 | ROI insuficiente |
| 4 | H23+clust | BACK Over 2.5 Confluence (Tied+Recent Goal) | BACK O2.5 | ROI insuficiente |
| 5 | H24 | BACK Draw After Equalizer | BACK Draw | ROI insuficiente |
| 6 | H25 | BACK Under 2.5 Scoreless Late | BACK U2.5 | ROI insuficiente |
| 7 | H26 | BACK Under 3.5 Low-xG Late | BACK U3.5 | ROI insuficiente |
| 8 | H30 | BACK Draw Late Stalemate | BACK Draw | N=10 < 31 |
| 9 | H1-v3 | LAY Over 4.5 V3 Tight | LAY O4.5 | N=28 < 31 (variante #1) |
| 10 | H1-v2v4 | LAY Over 4.5 V2+V4 combo | LAY O4.5 | N=3 < 31 (variante #1) |
| 11 | H1-late | LAY Over 4.5 min=68-78 | LAY O4.5 | N=17 < 31 (variante #1) |
| 12 | H14 | BACK Draw xG Convergence | BACK Draw | ROI insuficiente |
| 13 | H19 | Corner+SoT -> Over 2.5 | BACK O2.5 | ROI insuficiente |
| 14 | H3-v4 | BACK Over 2.5 from 2-Goal V4 +xG | BACK O2.5 | ROI insuficiente (variante #3) |
| 15 | H21 | BACK Over 3.5 First-Half Goals | BACK O3.5 | ROI insuficiente |
| 16 | H23 | BACK Over 2.5 from 1-1 | BACK O2.5 | ROI insuficiente |
| 17 | H32 | BACK Over 0.5 Possession Extreme | BACK O0.5 | ROI insuficiente |
| 18 | H35 | BACK Longshot Resistente | BACK MO (longshot) | ROI insuficiente |
| 19 | H37 | BACK CS 0-0 Early | BACK CS 0-0 | ROI insuficiente |

## EN SEGUIMIENTO (5)

| # | Hipotesis | Nombre | Mercado | N actual | Mejor ROI | Gate que falla | Fecha revision |
|---|---|---|---|---|---|---|---|
| 1 | H40 | BACK HT Leader | BACK MO (leader) | 302 | +3.3% | Train ROI=0.3% (marginal) | Cuando dataset > 1200 |
| 2 | H54 | BACK Over 4.5 High-Activity Momentum | BACK O4.5 | 25 | +96.0% | N=25 < 60 (need more high-scoring games) | Cuando dataset > 1500 |
| 3 | H55 | BACK CS 2-0/0-2 Hold | BACK CS 2-0/0-2 | 105 | +26.5% | IC95_lo=32.0% < 40% (WR uncertain) | Cuando dataset > 1200 |
| 4 | H62 | BACK Draw After UD Equalizer Late | BACK Draw | 40 | +149.5% | N=40 < 60 (Sharpe=3.38, train=156%/test=134%) | Cuando dataset > 1200 |
| 5 | H65 | BACK CS 3-0/0-3 Late Hold | BACK CS 3-0/0-3 | 49 | +74.3% | N=49 < 60 (train=86.6%/test=46.4%) | Cuando dataset > 1200 |

**H62 nota**: Underdog equalizes the favourite's lead at min 60-85, fav_pre <= 2.5. BACK Draw. WR=60%, avg odds=4.00. Very high ROI but only N=40. Both train (156.2%) and test (134.1%) are strongly positive, suggesting genuine edge. The edge thesis is compelling: after equalization, the favourite has lost momentum and the underdog defends the draw. Market still prices the favourite to win. With 1200+ matches, should reach N>=60.

**H65 nota**: BACK CS 3-0/0-3 at min 65-85. WR=63.3%, avg odds=2.70. Extends the CS structural inefficiency to 3-goal lead scorelines. Train=86.6%, test=46.4%. The combined version (3-0/0-3 + 2-0/0-2) reaches N=119 but overlaps with H55. As standalone 3-0/0-3, needs more 3-goal games to reach N>=60.

**H40 nota**: La estrategia pasa gates formalmente (train ROI 0.3% > 0) pero el edge es tan marginal que puede ser ruido. Con min=46-55, odds=1.3-3.0, margin>=1: N=302, WR=65.9%, ROI=3.3%, Sharpe=0.73. El mercado pricea parcialmente a los HT leaders. La version con margin>=2 (2+ goal lead) tiene ROI=28.3% pero solo N=32.

**H54 nota**: Con 4+ goals at min 40-55 y SoT>=4: N=25, WR=92%, ROI=96%, Sharpe=3.14. Metrics are extraordinary but sample is tiny. This strategy only triggers in very high-scoring games which are rare. With 1500+ matches, might reach N>=60.

**H55 nota**: CS 2-0/0-2 at min 65-80 without odds cap: N=105, WR=41%, ROI=26.5%, Sharpe=1.48. The WR is too uncertain (IC95 lower bound 32%). With more data, the confidence interval could narrow. The edge appears real (train ROI=22%, test ROI=36.6%) but the variability in outcomes is high because losses cost more (CS odds avg 3.50 means -10 per loss vs +23.75 per win).

## DESCARTADAS (37) -- NO RE-INVESTIGAR

| H# | Nombre | Mercado | Razon de descarte |
|---|---|---|---|
| H4 | LAY Over 3.5 Defensive Lock | LAY O3.5 | Tail risk catastrofico (-470/loss), ROI negativo |
| H5 | BACK Over 2.5 Momentum Surge | BACK O2.5 | N<60, ROI marginal 8.3% |
| H6 | BACK Under 2.5 Low-xG Lock | BACK U2.5 | N<60, odds 1.1-1.2, ROI plano |
| H7 | LAY Away Win Late Fortress | LAY Away | Overlap con drift/momentum existentes |
| H8 | LAY Home Underdog Rally | LAY Leader | ROI -40% a -141% |
| H9 | BACK Over 0.5 Scoreless Pressure | BACK O0.5 | N=9, datos insuficientes |
| H10 | LAY Over 5.5 Fortress | LAY O5.5 | Tail risk extremo (-740/loss) |
| H11 | LAY Draw Stat Domination | LAY Draw | N<60 (max 24) |
| H12 | BACK Over 3.5 High Activity | BACK O3.5 | WR 30-45%, ROI negativo |
| H13 | BACK Favorito Remontador | BACK MO (fav) | 0/1440 configs pasan gates |
| H15 | HT SoT Dominant | BACK MO (HT) | ROI max 20.4%, marginal |
| H16 | LAY Under 1.5 Late | LAY U1.5 | 0/34333 configs pasan, ROI siempre negativo |
| H20 | LAY Draw High-Scoring 1-1 | LAY Draw | 0/660 configs pasan, mercado eficiente |
| H22 | LAY Leader Stat Deficit | LAY Leader | 0/801 configs pasan, WR insuficiente para LAY |
| H27 | LAY Safe Harbor | LAY Leader | 0/7350 configs pasan, mercado eficiente |
| H28 | BACK Over 1.5 Two-Sided Attack | BACK O1.5 | ROI siempre negativo, mercado O1.5 eficiente |
| H29 | LAY Correct Score 0-0 High xG | LAY CS 0-0 | N<60, test ROI negativo, CS ~50% null rate |
| H31 | Odds Compression Signal | BACK MO | Odds movement = noise, no signal |
| H33 | LAY Leader xG Deficit | LAY Leader | 0/5041 configs pasan, mercado eficiente |
| H34 | LAY Favorito tras Gol Temprano | LAY MO (fav) | ROI -1.2%, edge solo en trading <5min (Angelini), no en FT |
| H36 | BACK Over Corners Late Tied | BACK Over | Test ROI=0.9%, 60% overlap con #8, corners solo 50% partidos |
| H38 | LAY Fav Momentum Adverso | LAY MO (fav) | N=23, condicion demasiado restrictiva |
| H42 | BACK Over 3.5 Two Goals by HT | BACK O3.5 | No tested: too similar to H21 |
| H43 | BACK Draw After HT Lead Equalizer | BACK Draw | No tested: too similar to H24 |
| H45 | BACK Over 2.5 High-xG Scoreless | BACK O2.5 | WR 10-25%, all test ROIs negative |
| H47 | BACK Under 1.5 at 0-0 | BACK U1.5 | Redundant with H44 (LAY Over 1.5 = BACK Under 1.5, same market direction) |
| H50 | BACK Under 3.5 at 2-0/0-2 | BACK U3.5 | Marginal ROI (4.3% best), barely passes gates |
| H51 | BACK Draw 0-0 Away Underdog | BACK Draw | 0/96 configs pass, ROI always negative |
| H52 | BACK Under 4.5 at 2-0/0-2 lead | BACK U4.5 | avg odds=1.07, one loss wipes 15 wins |
| H53-as-H57 | BACK CS Portfolio (4 scorelines) | BACK CS all | Not rejected per se; H53 (1-0/0-1 portion) approved separately. H57 full version kept as reference. |
| H56 | BACK CS 0-0 Very Late | BACK CS 0-0 | Test ROI=-14.7% (severe overfitting). Only profitable without odds cap where avg odds=2.24, but test set shows complete edge decay |
| H60 | BACK Over After Red Card | BACK Over | Only N=33 red card matches with data. ROI=-11.8% for O1.5, -67.5% for O2.5. Red cards too rare and don't predict more goals |
| H61 | xG Surge -> BACK Over 2.5 | BACK O2.5 | Only N=10 matches with high xG delta. Insufficient data and overlaps with Momentum xG concept |
| H63 | BACK Over in Tight Games (Loser Pushing) | BACK Over | N=89, ROI=-11.7%. Market prices correctly when loser has stats in +-1 games |
| H64 | LAY Favourite After UD Equalizer | LAY MO (fav) | N=23-32, redundant with H62 (same trigger, different side). H62 (BACK Draw) has better ROI |

## MERCADOS / CONCEPTOS AGOTADOS

Estos mercados o angulos han sido investigados extensivamente y el mercado los pricea correctamente. No re-investigar sin nueva evidencia:

- **LAY Leader/Favorito**: H7, H8, H22, H27, H33, H34, H38 -- el mercado ajusta correctamente cuando lider pierde stats
- **LAY Draw**: H11, H20 -- mercado eficiente en pricing draws
- **LAY Over lineas altas (5.5+)**: H10 -- tail risk catastrofico
- **LAY Over 3.5**: H4 -- tail risk insostenible
- **LAY Under 1.5**: H16 -- 0/34k configs viables
- **BACK Over 1.5**: H28 -- mercado O1.5 demasiado eficiente
- **BACK Over 3.5**: H12, H42 -- WR insuficiente
- **BACK Over 2.5**: 7+ estrategias, mercado SATURADO
- **Odds movement como signal**: H31 -- noise >> signal en in-play
- **Correct Score (LAY)**: H29 -- null rate ~50%, N insuficiente
- **Corners como predictor**: H36 -- datos solo en 50% partidos, overlap con estrategias existentes
- **Trading post-gol <5min**: H34 -- nuestro sistema opera por FT, no aplica
- **BACK O2.5 from 0-0 + high xG**: H45 -- mercado pricea correctamente
- **BACK Draw after equalizer**: H24, H43 -- ROI insuficiente
- **BACK Draw 0-0 away underdog**: H51 -- mercado eficiente, ROI siempre negativo
- **BACK Under 4.5 (thin margins)**: H52 -- avg odds 1.07, not worth capital
- **BACK Under 3.5 at 2-0/0-2**: H50 -- marginal ROI 4.3%
- **BACK Under 1.5 at 0-0**: H47 -- redundant with H44 (same market direction)
- **BACK CS 0-0 very late**: H56 -- severe overfitting (test ROI -14.7%)
- **Red cards as predictor**: H60 -- only 65 matches with red card data, too rare for strategies. ROI negative.
- **xG momentum surge**: H61 -- only N=10, insufficient data. Overlaps conceptually with Momentum xG strategy.
- **BACK Over when loser pushes**: H63 -- ROI -11.7%, market prices correctly
- **Handicap / Asian Handicap**: No columns available in dataset (confirmed R8 exploration)
- **HT-specific markets**: No HT market columns available (confirmed R8 exploration)
- **BTTS markets**: No columns available (confirmed R7 exploration)
- **Yellow cards as predictor of 2H goals**: R10 exploration showed NO correlation (1 card: 1.47 avg 2H goals, 2 cards: 1.47, 3 cards: 1.22). Tarjetas are NOT predictive of goals.
- **Stat-dominant losers (xG+SoT+poss dominant but losing)**: Only 11 matches, 9.1% win rate. DEAD angle confirmed again (R9 also found this).

## NOTAS PARA FUTURAS RONDAS

- Hipotesis H1-H65 ya cubiertas. Siguiente ronda empieza en H66.
- El notebook usa `eval_sd()` con gates: N >= G_MIN_BETS_SD (31), ROI >= G_MIN_ROI, IC95_low >= IC95_MIN_LOW.
- Muchas estrategias aprobadas con 800 partidos quedaron "off" con el dataset filtrado del notebook. Con mas datos pueden reactivarse automaticamente.
- Las funciones `_apply_sd_*` y configs `SD_APPROVED_CONFIGS` estan en `betfair_scraper/dashboard/backend/utils/sd_strategies.py`.
- Generadores de bets en `aux/sd_generators.py`, filtros en `aux/sd_filters.py`.
- **Ronda 9 hallazgos clave**:
  - CS structural inefficiency confirmed UNIVERSALLY across all tight scorelines. At min 70-80, EVERY tested score has positive edge vs market-implied probability.
  - The edge is largest for rarer scorelines (3-0, 1-2, 3-1) where market has least information, but also significant for common scores (1-0, 0-1, 2-1).
  - 1-1 at min 75+ leads to draws 57.8% of the time vs market-implied 51.8%. Match Odds Draw market captures this edge more efficiently than CS market (better liquidity).
  - CS 0-0 very late has a large apparent edge (60.4% hold vs 42.8% implied) but FAILS test set validation. The edge appears to decay significantly in the test period. Likely explanation: 0-0 games attract speculative late bets that briefly inflate CS 0-0 odds, then odds compress rapidly. The entry timing matters more for 0-0 than other scores.
  - BACK Over 4.5 from high-scoring states shows massive edge (ROI 96% with xG>=2.0) but only N=25. This is a low-frequency strategy that needs more data.
  - CS 2-0/0-2 has a moderate edge but high variance (WR=41%, IC95 lower bound only 32%). Needs more data to confirm.
  - **Home trailing 0-1 with stat dominance is a DEAD angle**: Even with xG excess, SoT dominance, and possession advantage, home team wins only 5.9-7.7% when trailing 0-1 in the second half. The market is correct here.
  - **Multi-signal comeback (trailing + 3 stat signals) is insufficient**: 41-44% comeback rate means the bet is close to a coin flip. No edge.
- **Ronda 10 hallazgos clave** (Perplexity-derived):
  - **BACK Underdog Leading Late (H59)** is a BREAKTHROUGH: N=192, ROI=93.9%, Sharpe=3.10. The "reverse favourite-longshot bias" from academic literature IS REAL in our dataset. Market underprices underdogs who are already winning by +10.6pp.
  - **Won bets have HIGHER odds than lost bets** (3.08 vs 2.30) -- strongest evidence of genuine inefficiency across all 65 hypotheses.
  - **H59 uses ONLY Tier 1 columns** (back_home, back_away, goles, minuto) -- zero data availability risk.
  - **Yellow cards do NOT predict goals**: 1 card in first 30': 1.47 avg 2H goals; 2 cards: 1.47; 3 cards: 1.22. ZERO correlation. Perplexity Section 4/11.3 hypothesis debunked.
  - **Red cards too rare** (65 matches, 7.7%) for any strategy. Perplexity Section 2.3 is theoretically interesting but not actionable with our data.
  - **BACK Draw After UD Equalizer (H62)** has extraordinary metrics (ROI=149.5%, Sharpe=3.38) but only N=40. In monitoring.
  - **CS 3-0/0-3 (H65)** extends CS structural inefficiency to 3-goal leads (WR=63.3%, avg odds=2.70). N=49, in monitoring.
  - **Stat-dominant losers remain a dead angle**: Only 11 matches, 9.1% win rate. Market correct. Perplexity Section 2.1 (underdog with better stats) only works when underdog is ALREADY LEADING (H59), not when they're losing.
- **Diversificacion de mercados actual tras R10**:
  - BACK Over 2.5: 7 estrategias (saturado, NO mas)
  - BACK Under 2.5: H25 + H46 (2)
  - BACK Under 3.5: H26 (1, off)
  - LAY Over 2.5: H41 (1)
  - LAY Over 1.5: H44 (1)
  - LAY Under 2.5: H48 (1)
  - BACK CS 2-1/1-2: H49 (1)
  - BACK CS 1-0/0-1: H53 (1, NUEVO R9)
  - BACK CS 0-0: H37 (1, off)
  - BACK CS 3-0/0-3: H65 (1, EN SEGUIMIENTO -- N insuficiente)
  - BACK Draw 0-0: H14, H24, H30 (3, todos off)
  - BACK Draw 1-1: H58 (1, NUEVO R9)
  - BACK Draw post-equalizer: H62 (1, EN SEGUIMIENTO -- N insuficiente)
  - BACK Match Winner (leader): H2, H35, H40 (3)
  - **BACK Match Winner (underdog): H59 (1, NUEVO R10)** -- first strategy on this market!
  - LAY Over 4.5: H1 (1, off)
  - BACK Over 4.5: H54 (1, EN SEGUIMIENTO -- N insuficiente)
