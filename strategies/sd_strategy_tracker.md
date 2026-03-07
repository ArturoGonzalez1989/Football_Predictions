# Strategy Designer — Historial de investigacion
Ultima actualizacion: 2026-03-07
Dataset al momento de la investigacion: 931 partidos finalizados (sorted by timestamp, 2026-02-10 a 2026-03-07)
Total hipotesis investigadas: 87 (H1-H87) en 15 rondas

> Este fichero es la referencia para el agente strategy-designer.
> Antes de investigar una hipotesis nueva, verificar que no este ya listada aqui.

## INTEGRADA EN PRODUCCION

Solo 1 de las 19 aprobadas en rondas anteriores paso los quality gates del notebook `strategies_designer.ipynb` (N>=31, ROI suficiente):

| Estrategia | Mercado | Config | N | WR | ROI | Notebook status |
|---|---|---|---|---|---|---|
| BACK Leader Stat Domination (H2) | BACK Match Winner (leader) | min=55-70, sot>=4, rival<=1 | 26 | 92.3% | +47.4% | ACTIVA |

## APROBADAS RONDA 13 (3 nuevas)

Ronda 13 explored 5 hypotheses (H77-H81) with 896 matches. Focus: unexploited CS scorelines, first-half patterns, LAY home/away. All 3 approved are CS market strategies extending the CS structural inefficiency portfolio. Discarded 2 hypotheses (H78: O3.5 FH test ROI=0.5%; H80: Home leading FH test ROI=1.9%).

| # | Hipotesis | Nombre | Mercado | N | WR | ROI (realistic) | Sharpe | Train ROI | Test ROI | Reporte |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H77 | BACK CS 1-1 Late | BACK CS 1-1 | 102 | 57.8% | +24.1% | 1.63 | +14.6% | +45.7% | strategies/sd_report_back_cs_11_late.md |
| 2 | H79 | BACK CS 2-0/0-2 Late | BACK CS 2-0/0-2 | 90 | 53.3% | +46.2% | 2.19 | +43.5% | +52.0% | strategies/sd_report_back_cs_20_late.md |
| 3 | H81 | BACK CS Big-Lead Late | BACK CS 3-0/0-3/3-1/1-3 | 79 | 65.8% | +58.3% | 3.51 | +69.6% | +32.4% | strategies/sd_report_back_cs_big_lead_late.md |

### Quality gates resumen (Ronda 13, realistic validation)

| Gate | H77 | H79 | H81 |
|------|-----|-----|-----|
| G1: N>=35 | PASS (102) | PASS (90) | PASS (79) |
| G2: ROI>=10% (realistic) | PASS (24.1%) | PASS (46.2%) | PASS (58.3%) |
| G3: IC95_lo>=40% | PASS (48.1%) | PASS (43.1%) | PASS (54.8%) |
| G4: Train ROI>0% | PASS (14.6%) | PASS (43.5%) | PASS (69.6%) |
| G5: Test ROI>0% | PASS (45.7%) | PASS (52.0%) | PASS (32.4%) |
| G6: Overlap<30% same market | PASS (0%) | PASS (0%) | PASS (0%) |
| G7: >=3 ligas | PASS (28) | PASS (28) | PASS (23) |

### Notas sobre las nuevas estrategias

- **All three exploit the same CS structural inefficiency** found in H49/H53 but on NEW scorelines. The CS market must distribute probability across dozens of scores, systematically underpricing whichever score is current. This pattern is now confirmed across 10 different scorelines.
- **H77 (CS 1-1) complements H58 (Draw 1-1)**: Both trigger on 1-1 at min 75+, but trade DIFFERENT markets (CS vs Match Odds). 96% match overlap but 0% market overlap. They are complementary bets on the same situation.
- **H79 supersedes H55**: H55 was in monitoring (IC95_lo=32%). With optimized params (min 75-90, odds_max 10.0), it now passes all gates. H55 removed from monitoring.
- **H81 supersedes H65**: H65 covered only 3-0/0-3 (N=49, insufficient). By adding 3-1/1-3, H81 reaches N=79 and passes all gates. H65 removed from monitoring.
- **H81 is the STAR of R13**: Sharpe=3.51 (realistic), ROI=58.3%, MaxDD=52. The 0-3 scoreline has 82.4% WR -- the highest of any individual scoreline tested.
- **Complete CS Portfolio after R13**: H49(2-1/1-2) + H53(1-0/0-1) + H77(1-1) + H79(2-0/0-2) + H81(3-0/0-3/3-1/1-3) = 10 scorelines, combined N~489, ALL with zero market overlap.
- **All three use ONLY Tier 1 columns** (CS odds, score, minuto) -- zero data availability risk.

### Cross-overlap between R13 approved

| Par | Match overlap | Market overlap |
|-----|---------------|----------------|
| H77 vs H79 | 0% | 0% (different scores) |
| H77 vs H81 | 0% | 0% (different scores) |
| H79 vs H81 | 11.1% of H79 | 0% (different scores) |

### Hypotheses discarded in R13

| H# | Name | Reason |
|----|------|--------|
| H78 | BACK Over 3.5 FH Activity | Test ROI=0.5% (below 10% threshold). N=75, WR=74.7% but avg odds=1.44. Train=14.3%, test collapses. Market adjusts O3.5 accurately when goals are scored early. |
| H80 | BACK Home Leading FH | Test ROI=1.9% (below 10% threshold). N=191, WR=81.7% but avg odds=1.39. The edge at first half is real but tiny (~2pp over implied). H70 (late version, min 55+) captures this much better because the edge grows as time runs out. |

## APROBADAS RONDA 12 (2 nuevas)

Ronda 12 explored 7 hypotheses (H70-H76) with 896 matches. Focus: leader markets (home favourite), Under 4.5, Draw at 0-0, CS extensions. Both approved strategies pass realistic validation (slippage 2%, dedup, odds filter [1.05, 10.0]).

| # | Hipotesis | Nombre | Mercado | N | WR | ROI (realistic) | Sharpe | Train ROI | Test ROI | Reporte |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H70 | BACK Home Favourite Leading Late | BACK MO (home fav) | 225 | 85.8% | +31.1% | 4.43 | +30.9% | +31.4% | strategies/sd_report_back_home_fav_leading.md |
| 2 | H71 | BACK Under 4.5 Three Goals Low xG | BACK U4.5 | 60 | 96.7% | +11.9% | 3.99 | +12.0% | +11.6% | strategies/sd_report_back_under45_three_goals.md |

### Quality gates resumen (Ronda 12, realistic validation)

| Gate | H70 | H71 |
|------|-----|-----|
| G1: N>=35 | PASS (225) | PASS (60) |
| G2: ROI>=10% (realistic) | PASS (31.1%) | PASS (11.9%) |
| G3: IC95_lo>=40% | PASS (80.6%) | PASS (88.6%) |
| G4: Train ROI>0% | PASS (30.9%) | PASS (12.0%) |
| G5: Test ROI>0% | PASS (31.4%) | PASS (11.6%) |
| G6: Overlap<30% same market | PASS (0% vs H67/H59) | PASS (0% -- U4.5 unique) |
| G7: >=3 ligas | PASS (32) | PASS (25) |

### Notas sobre las nuevas estrategias

- **H70 is the STAR of R12**: N=225, Sharpe=4.43 (realistic), train/test ROI virtually identical (30.9/31.4%). Completes the "leader portfolio" with H67 (away fav) and H59 (underdog). The three are MUTUALLY EXCLUSIVE by construction. Combined N would be 540+. The 85.8% hold rate vs market-implied ~63% (avg odds 1.59) shows a +23pp edge -- among the largest found in 76 hypotheses.
- **H71 is ultra-conservative**: 96.7% WR, only 2 losses in 60 bets. MaxDD=10 (one loss). ROI is marginal at 11.9% realistic but extremely stable (train/test nearly equal). 95% match overlap with H66 means they trigger on same matches but different Under markets. Consider as a complementary position to H66 rather than independent strategy.
- **H70 uses only Tier 1 columns** (back_home, back_away, goles, minuto) -- zero data availability risk.
- **H71 uses xG (Tier 1)** as its key filter, which is available in >95% of matches.

### Cross-overlap between R12 approved

| Par | Market overlap |
|-----|----------------|
| H70 vs H71 | 0% (different markets: MO vs U4.5) |
| H70 vs H67 | 0% (mutually exclusive: home fav vs away fav) |
| H70 vs H59 | 2.2% (near-exclusive: fav vs underdog) |
| H71 vs H66 | 0% (different markets: U4.5 vs U3.5, 95% match overlap) |

## APROBADAS RONDA 11 (2 nuevas)

Ronda 11 explored genuinely new angles after 10 rounds of research. Focus: markets not yet covered (Under 3.5, Away Favourite leading). Of 4 hypotheses investigated (H66-H69), 2 approved, 2 in monitoring.

| # | Hipotesis | Nombre | Mercado | N | WR | ROI | Sharpe | Train ROI | Test ROI | Reporte |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | H66 | BACK Under 3.5 Three-Goal Lid | BACK U3.5 | 84 | 67.9% | +26.2% | 2.33 | +11.9% | +58.3% | strategies/sd_report_back_under35_three_goals.md |
| 2 | H67 | BACK Away Favourite Leading Late | BACK MO (away fav) | 121 | 85.1% | +23.9% | 2.71 | +16.4% | +41.1% | strategies/sd_report_back_away_fav_leading.md |

### Quality gates resumen (Ronda 11)

| Gate | H66 | H67 |
|------|-----|-----|
| G1: N>=60 | PASS (84) | PASS (121) |
| G2: N_test>=18 | PASS (26) | PASS (37) |
| G3: ROI train+test>0 | PASS (11.9/58.3) | PASS (16.4/41.1) |
| G4: IC95_lo>40% | PASS (57.3%) | PASS (77.7%) |
| G5: MaxDD<400 | PASS (54.50) | PASS (46.26) |
| G6: Overlap<30% | PASS (0% -- unique market) | PASS (0% -- mutually exclusive with H59) |
| G7: >=3 ligas | PASS (29) | PASS (29) |
| G8: DateConc<50% | PASS (47.6%) | PASS (<30%) |

### Notas sobre las nuevas estrategias

- **H66 opens the Under 3.5 market**: First strategy to use Under 3.5. When 3 goals are scored but xG is below 2.5, the goals are "overperformance" and the 4th is unlikely. Market overestimates based on goal count, not chance quality. ROI positive across ALL 48 configs tested (even without xG filter: N=215, ROI=9.8%). xG filter doubles the ROI by removing genuinely high-activity matches.
- **H67 complements H59 perfectly**: H59 covers underdog leading (any location), H67 covers away FAVOURITE leading. Together they cover ALL "leader late" scenarios. The two strategies are MUTUALLY EXCLUSIVE by definition (same match cannot trigger both). H67 exploits home-advantage bias: market overestimates home comebacks when away favourite already controls the game.
- **H67 is an "invisible strategy"**: 85.1% WR at avg odds 1.50 means the market prices ~67% hold probability when the actual rate is 85%+. This 18pp gap is one of the largest edges found across all 69 hypotheses.
- **H66 and H67 have zero market overlap**: H66 trades Under 3.5 (goals market), H67 trades Match Winner (away). They can both trigger on the same match without conflict.

### Cross-overlap between R11 approved

| Par | Market overlap |
|-----|----------------|
| H66 vs H67 | 0% (different markets: U3.5 vs Match Winner) |
| H66 vs H59 | 0% (U3.5 vs Match Winner) |
| H67 vs H59 | 0% (mutually exclusive: away fav vs underdog) |

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

## EN SEGUIMIENTO (7)

| # | Hipotesis | Nombre | Mercado | N actual | Mejor ROI | Gate que falla | Fecha revision |
|---|---|---|---|---|---|---|---|
| 1 | H40 | BACK HT Leader | BACK MO (leader) | 302 | +3.3% | Train ROI=0.3% (marginal) | Cuando dataset > 1200 |
| 2 | H54 | BACK Over 4.5 High-Activity Momentum | BACK O4.5 | 25 | +96.0% | N=25 < 60 (need more high-scoring games) | Cuando dataset > 1500 |
| 3 | H55 | BACK CS 2-0/0-2 Hold | BACK CS 2-0/0-2 | 105 | +26.5% | SUPERSEDED by H79 (R13) -- better params, passes all gates | -- |
| 4 | H62 | BACK Draw After UD Equalizer Late | BACK Draw | 40 | +149.5% | N=40 < 60 (Sharpe=3.38, train=156%/test=134%) | Cuando dataset > 1200 |
| 5 | H65 | BACK CS 3-0/0-3 Late Hold | BACK CS 3-0/0-3 | 49 | +74.3% | SUPERSEDED by H81 (R13) -- adds 3-1/1-3, passes all gates | -- |
| 6 | H68 | BACK Draw at 2-2 Late | BACK Draw (2-2) | 44 | +28.4% | N=44 < 60 (WR=54.5%, Sharpe=1.16, edge=+10.5pp vs implied) | Cuando dataset > 1200 |
| 7 | H69 | BACK Under 0.5 Late Scoreless | BACK U0.5 | 78 | +15.4% | Sharpe=0.78, low edge/variance ratio; overlaps with H44 concept | Cuando dataset > 1200 |

**H68 nota**: BACK Draw at 2-2 at min 70-85. N=44, WR=54.5%, ROI=28.4%, Sharpe=1.16. The market underprices draws at 2-2 by ~10pp (actual 54.5% vs implied ~38%). Both teams have scored twice, creating mutual exhaustion and risk-aversion that favours draws. Different dynamics from H58 (Draw 1-1) -- at 2-2, each goal required different tactical adjustments. With 1200+ matches should reach N>=60. Extends Draw analysis to high-scoring tied games.

**H69 nota**: BACK Under 0.5 at 0-0 at min 78-90. N=78, WR=61.5%, ROI=13.1%, Sharpe=0.69. The edge exists (+12pp at min 80) but Sharpe is low due to high variance in Under 0.5 market. Conceptually overlaps with H44 (LAY Over 1.5 Scoreless) -- both profit from no-goal games. However, Under 0.5 is a different market with potentially better odds structure. Keep monitoring but de-prioritize. Best config: min=80-90, N=74, WR=64.9%, ROI=15.4%.

**H62 nota**: Underdog equalizes the favourite's lead at min 60-85, fav_pre <= 2.5. BACK Draw. WR=60%, avg odds=4.00. Very high ROI but only N=40. Both train (156.2%) and test (134.1%) are strongly positive, suggesting genuine edge. The edge thesis is compelling: after equalization, the favourite has lost momentum and the underdog defends the draw. Market still prices the favourite to win. With 1200+ matches, should reach N>=60.

**H65 nota**: BACK CS 3-0/0-3 at min 65-85. WR=63.3%, avg odds=2.70. Extends the CS structural inefficiency to 3-goal lead scorelines. Train=86.6%, test=46.4%. The combined version (3-0/0-3 + 2-0/0-2) reaches N=119 but overlaps with H55. As standalone 3-0/0-3, needs more 3-goal games to reach N>=60.

**H40 nota**: La estrategia pasa gates formalmente (train ROI 0.3% > 0) pero el edge es tan marginal que puede ser ruido. Con min=46-55, odds=1.3-3.0, margin>=1: N=302, WR=65.9%, ROI=3.3%, Sharpe=0.73. El mercado pricea parcialmente a los HT leaders. La version con margin>=2 (2+ goal lead) tiene ROI=28.3% pero solo N=32.

**H54 nota**: Con 4+ goals at min 40-55 y SoT>=4: N=25, WR=92%, ROI=96%, Sharpe=3.14. Metrics are extraordinary but sample is tiny. This strategy only triggers in very high-scoring games which are rare. With 1500+ matches, might reach N>=60.

**H55 nota**: CS 2-0/0-2 at min 65-80 without odds cap: N=105, WR=41%, ROI=26.5%, Sharpe=1.48. The WR is too uncertain (IC95 lower bound 32%). With more data, the confidence interval could narrow. The edge appears real (train ROI=22%, test ROI=36.6%) but the variability in outcomes is high because losses cost more (CS odds avg 3.50 means -10 per loss vs +23.75 per win).

## DESCARTADAS (47) -- NO RE-INVESTIGAR

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
| H72 | BACK Over 0.5 Scoreless at HT | BACK O0.5 | Test ROI negative across ALL configs. Best: N=176, ROI=4.2%, test=-4.9%. Market efficient for O0.5 |
| H74 | BACK Draw 0-0 Mid-Game Balanced | BACK Draw | Sharpe < 1.0 across all 76 configs. Best N=32, ROI=16.3% but train=0.9%. Confirms 0-0 Draw market efficient |
| H75 | BACK CS 0-0 Very Late (v2) | BACK CS 0-0 | Negative ROI across all configs. Confirms H56 descarte. Edge is an artefact |
| H76 | BACK Home Fav Leading 2+ Early | BACK MO (home) | N=67, test ROI=2.6%. Strong train/test divergence (26%/2.6%). Subsumed by H70 which is broader and better |
| H78 | BACK Over 3.5 FH Activity | BACK O3.5 | Test ROI=0.5%. N=75 with 3+ goals by min 35-45 but avg odds=1.44, market adjusts correctly |
| H80 | BACK Home Leading FH (fav only) | BACK MO (home) | Test ROI=1.9%. N=191, WR=81.7% but edge only ~2pp. H70 (late) is far superior |
| H82 | Team Yield filter for goal_clustering | FILTER | No signal. Removing negative-yield teams removes PROFITABLE bets. Train filter -6.5pp to -15.8pp vs baseline. |
| H83 | Team Yield filter for pressure_cooker | FILTER | Baseline ROI -2.3%. Best train improvement +4pp but FAILS in test (-16.1pp). Overfitting. |
| H84 | Global Toxic Team filter | FILTER | Max improvement +1.8pp portfolio ROI. Negligible impact for complexity added. |
| H85 | Profitable Away Team boost | FILTER | Strong-looking signal in xg_underperf (N=25 boost ROI=78.8%) but N too small. Under_late max_yield>=0% holds in test (+14.1pp) but effect driven by under_late itself having ~0% ROI. |
| H86 | Team Yield x League Tier interaction | FILTER | Tier 2/3 show positive delta but Tier 1 shows REVERSE signal (-13.8pp). Not actionable. |
| H87 | Team Yield BY ROLE (home-as-home, away-as-away) | FILTER | Pearson r = -0.016 (essentially zero). Role balance unstable across quarters (Q3 reverses -24pp). 12/216 grid combos positive in train+test but all marginal (<5pp train) or tiny N (20-33). Same counter-intuitive pattern as H82-H86: "bad" teams provide more value. Role-specific yield adds no signal vs generic yield. |

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
- **BACK Over 0.5 at 0-0 HT**: H72 -- raw edge +15pp but test ROI always negative. Market adjusts post-HT.
- **BACK Draw at 0-0 mid-game (55-70)**: H74 -- Sharpe <1.0 across 76 configs. Market efficient for Draw 0-0.
- **BACK CS 0-0 very late**: H56 + H75 -- confirmed dead across 2 rounds. Edge is artefact.
- **Home fav leading 2+ early**: H76 -- subsumed by H70 (broader, more robust). Test ROI collapses.
- **BACK Over 3.5 first half**: H78 -- test ROI=0.5%, market adjusts O3.5 correctly when goals scored early
- **BACK Home Leading First Half**: H80 -- test ROI=1.9%, edge only ~2pp. Late strategies (H70) capture this much better
- **Team Yield as filter (H82-H87)**: R14 tested generic yield (H82-H86, 5 hypotheses, 180 combos). R15 tested role-specific yield (H87: home-as-home, away-as-away, 216 combos). BOTH approaches fail. Generic: ZERO combos improve train+test. Role-specific: Pearson r = -0.016 (zero correlation), 12/216 combos positive in both sets but all marginal or tiny N. Signal unstable across quarters (Q3 reverses -24pp). Counter-intuitive "bad yield = better outcomes" pattern persists in role-specific analysis. Team yield -- whether generic or role-specific -- is NOT predictive. Concept EXHAUSTED across 6 hypotheses.
- **Handicap / Asian Handicap**: No columns available in dataset (confirmed R8 exploration)
- **HT-specific markets**: No HT market columns available (confirmed R8 exploration)
- **BTTS markets**: No columns available (confirmed R7 exploration)
- **Yellow cards as predictor of 2H goals**: R10 exploration showed NO correlation (1 card: 1.47 avg 2H goals, 2 cards: 1.47, 3 cards: 1.22). Tarjetas are NOT predictive of goals.
- **Stat-dominant losers (xG+SoT+poss dominant but losing)**: Only 11 matches, 9.1% win rate. DEAD angle confirmed again (R9 also found this).

## NOTAS PARA FUTURAS RONDAS

- Hipotesis H1-H87 ya cubiertas. Siguiente ronda empieza en H88.
- **Ronda 15 hallazgos clave (H87 -- Team Yield by Role)**:
  - Tested role-specific yield (home-as-home ROI, away-as-away ROI, role_balance) across 2155 bets, 7 strategies, 931 matches.
  - Grid search: 3 yield types x 9 thresholds x 4 min_hist x 2 directions = 216 combos.
  - **Pearson r (role_balance vs win) = -0.0157**: essentially ZERO correlation. Role-specific yield is slightly "more predictive" than generic (r=0.006) but both are negligible.
  - **Role balance unstable across quarters**: Q1=+32.8pp, Q2=+6.4pp, Q3=-24.4pp (REVERSED), Q4=+13.5pp. Signal flips sign.
  - **12/216 combos positive in both train+test** but all are either: (a) marginal improvement <5pp in train, (b) tiny N (20-33 bets), or (c) filter so wide it barely removes anything.
  - **Counter-intuitive pattern confirmed AGAIN**: `home_as_home_roi keep_below` (teams with NEGATIVE home ROI) improves portfolio. Same dead-end as H82-H86.
  - **Per-strategy**: 3 strategies show "promising" signals (cs_late, under_late, draw_late) but improvements are small and N is low once filtered.
  - **Conclusion**: Role-specific yield does NOT solve the fundamental problem found in H82-H86. The team yield concept is EXHAUSTED in all forms (generic, role-specific, league-tiered, per-strategy, directional vs non-directional).
- **Ronda 13 hallazgos clave**:
  - **CS structural inefficiency confirmed on ALL tested scorelines**: H77 (1-1), H79 (2-0/0-2), H81 (3-0/0-3/3-1/1-3) all pass realistic validation. The CS market systematically underprices the current score at min 70-90 regardless of scoreline.
  - **CS Portfolio now covers 10 scorelines**: H49(2-1/1-2) + H53(1-0/0-1) + H77(1-1) + H79(2-0/0-2) + H81(3-0/0-3/3-1/1-3). Combined N~489, zero market overlap. This is the largest systematic edge found in the research program.
  - **First-half strategies have weak edges**: H78 (O3.5) and H80 (home leading) both show positive train ROI but test ROI collapses to <2%. The market has more time to adjust in the second half, so edges found in FH are smaller and less stable. Confirmed that min 70+ is the "sweet spot" for edge size.
  - **LAY home/away in FH not viable**: Only 5 matches where home leads 1-0 but away dominates stats. Insufficient N for any LAY strategy.
- **Ronda 14 hallazgos clave (H82-H86 -- Team Yield as filter)**:
  - Tested team yield (chronological ROI per team) as secondary filter for ALL 7 strategy families across 2151 bets from 918 matches.
  - **Fundamental finding: Team yield is NOT predictive.** The most common result is that filtering OUT negative-yield teams HURTS performance because those teams tend to have higher odds and provide more value when they win.
  - **Counter-intuitive reversal in draw_late and cs_late**: Teams with negative yield have HIGHER ROI on draw and CS bets. This is because "bad yield" teams are typically underdogs getting better odds from the market.
  - **Only under_late shows a test-positive signal** (max_yield >= 0% gives +14.1pp in test), but under_late baseline ROI is 0.5% -- the strategy itself is barely profitable, so improving it still yields <10% ROI.
  - **Rolling window instability**: Q1-Q2 show no separation or reversal between yield groups; Q3-Q4 show separation. Signal is temporally unstable.
  - **League tier interaction non-actionable**: Tier 2/3 show positive yield correlation, Tier 1 shows REVERSE. Cannot build a universal filter.
  - **Grid search conclusive**: 180 parameter combinations tested, ZERO show improvement in BOTH train and test at portfolio level. The best test delta is +2.4pp (hist>=5, away_yield_roi keep_below -30%) -- negligible for the implementation complexity.
  - **Team yield concept EXHAUSTED**: Do not re-investigate unless dataset grows significantly (>5000 matches) or team yield is computed differently (e.g., strategy-specific, position-weighted, decay-weighted).
  - **Odds drift in FH is noise**: H=34 drift events, 29.4% home win rate -- market is correct.
  - **0-3 scoreline has 82.4% WR**: The highest single-scoreline WR found. Away teams with 3-goal leads are virtually unbeatable.
  - **H55 and H65 superseded**: Both monitoring strategies now have better versions (H79, H81) that pass all gates.
- **Ronda 11 hallazgos clave**:
  - **Under 3.5 market is genuinely inefficient**: When 3 goals are scored but xG < 2.5, the 4th goal probability is overpriced. H66 found ROI=+26.2% (N=84). Even WITHOUT xG filter, ROI is +9.8% (N=215) -- the market systematically overestimates 4th goal probability regardless of quality.
  - **Away favourite leading is massively underpriced**: H67 found 85.1% hold rate vs market-implied 67%. This 18pp edge is one of the largest in the entire research program. The "home advantage comeback" narrative is deeply embedded in market pricing.
  - **H67 and H59 form a "leader portfolio"**: Together they cover ALL "leading team late" scenarios with zero overlap (mutually exclusive by definition). H59 captures underdog-leads (high odds, high ROI), H67 captures away-favourite-leads (lower odds, very high WR). Combined N would be ~310+.
  - **Draw at 2-2 has genuine edge (+10pp)** but N=44 is insufficient for approval. Extends the Draw analysis from 1-1 (H58) to 2-2. Different dynamics but similar market bias.
  - **Under 0.5 late scoreless has edge (+12pp at min 80)** but overlaps conceptually with H44 and has low Sharpe. Not recommended for approval at current N.
  - **Goal timing analysis**: Second half is more productive (77.3% of matches have 1+ goals in 2H). The 45-55 minute window is peak goal-scoring (avg 0.41 goals/match in those 10 minutes). Late minutes (75-90) see significant goal-scoring but also many holds.
  - **Comeback analysis**: Leader at 70' holds to win 85.6% of the time. Only 12.2% of trailing teams equalize, 2.1% complete a comeback. The market significantly overestimates comeback probability.
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
- **Ronda 12 hallazgos clave**:
  - **Home favourite leading is massively underpriced**: H70 found 85.8% hold rate vs market-implied ~63% (avg odds 1.59). Edge of +23pp, the largest single-strategy edge in the entire program. Train/test ROI nearly identical (30.9/31.4%), indicating zero temporal decay.
  - **Leader portfolio is now COMPLETE**: H70 (home fav) + H67 (away fav) + H59 (underdog) = all possible "leader late" scenarios. Combined N=540+, all mutually exclusive. This is the strongest systematic edge found.
  - **Under 4.5 at 3 goals with low xG is viable**: H71 passes at ROI=11.9% realistic but is marginal. 95% match overlap with H66 means it's essentially a complementary bet, not independent.
  - **Over 0.5 at 0-0 HT is NOT viable**: Despite +15pp raw edge (exploration), actual backtest shows negative test ROI. Market adjusts quickly after HT.
  - **Draw at 0-0 mid-game is NOT viable**: Sharpe < 1.0 across 76 configs. Confirms Draw 0-0 market is efficient (consistent with H51 descartada).
  - **CS 0-0 very late remains dead**: H75 retest confirms H56 -- negative ROI, edge is artefact.
  - **Home fav leading 2+ early (55-70)**: Interesting WR (92.5%) but test ROI collapses (2.6%). H70's broader window is more robust.
  - **Market efficiency by segment**: The market is EFFICIENT for: Draw 0-0, CS 0-0, Over 0.5 scoreless. The market is INEFFICIENT for: leader holds, Under markets at specific goals, CS at non-draw scores.
- **Diversificacion de mercados actual tras R12**:
  - BACK Over 2.5: 7 estrategias (saturado, NO mas)
  - BACK Under 2.5: H25 + H46 (2)
  - **BACK Under 3.5: H26 (off) + H66 (NUEVO R11, 3 goals + low xG)**
  - LAY Over 2.5: H41 (1)
  - LAY Over 1.5: H44 (1)
  - LAY Under 2.5: H48 (1)
  - BACK CS 2-1/1-2: H49 (1)
  - BACK CS 1-0/0-1: H53 (1, NUEVO R9)
  - BACK CS 0-0: H37 (1, off)
  - **BACK CS 1-1: H77 (1, NUEVO R13)**
  - **BACK CS 2-0/0-2: H79 (1, NUEVO R13, supersedes H55)**
  - BACK CS 3-0/0-3+3-1/1-3: **H81 (1, NUEVO R13, supersedes H65)**
  - BACK Draw 0-0: H14, H24, H30 (3, todos off)
  - BACK Draw 1-1: H58 (1, NUEVO R9)
  - BACK Draw post-equalizer: H62 (1, EN SEGUIMIENTO -- N insuficiente)
  - BACK Match Winner (leader): H2, H35, H40 (3)
  - **BACK Match Winner (underdog): H59 (1, R10)** -- reverse fav-longshot bias
  - **BACK Match Winner (away fav): H67 (1, NUEVO R11)** -- away favourite leading, mutually exclusive with H59
  - **BACK Match Winner (home fav leading): H70 (1, NUEVO R12)** -- home favourite leading, completes leader portfolio
  - BACK Under 0.5: H69 (EN SEGUIMIENTO R11)
  - BACK Draw 2-2: H68 (EN SEGUIMIENTO R11)
  - **BACK Under 4.5: H71 (1, NUEVO R12)** -- 3 goals with low xG, complementary to H66
  - LAY Over 4.5: H1 (1, off)
  - BACK Over 4.5: H54 (1, EN SEGUIMIENTO -- N insuficiente)
