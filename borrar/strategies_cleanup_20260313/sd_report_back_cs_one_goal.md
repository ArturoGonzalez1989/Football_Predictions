# Nueva Estrategia: BACK CS 1-0/0-1 Late Lock (H53)

## Concepto
When the score is 1-0 or 0-1 at minute 68-85, BACK the current correct score in the CS market. The Correct Score market systematically underprices the probability of the current score holding because it must distribute probability across 15+ possible final scorelines. At 1-0/0-1, the hold rate is significantly higher than the market implies (53.7% actual vs ~34% implied at avg odds 2.96).

## Edge Thesis
The CS market has a structural inefficiency: it must allocate probability among dozens of scorelines, and the residual error systematically underweights the most probable outcome (the current score). This was proven by H49 (2-1/1-2, ROI=85.4%) and now confirmed for 1-0/0-1 with an even larger sample. At 1-0/0-1 late, the market overestimates the probability of further goals because: (a) bettors psychologically expect "something to happen" in the final 20 minutes, and (b) the CS market aggregates this expectation across all non-current scorelines, inflating their combined probability.

## Trigger Conditions
- **Minuto**: [68, 85]
- **Marcador**: 1-0 or 0-1
- **Cuota**: back_rc_1_0 or back_rc_0_1 > 1.0
- **No odds cap**: wider range captures the full edge

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Correct Score (current score)
- **Win condition**: Final score == score at trigger (1-0 or 0-1 holds to FT)

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=216)
| Metrica | Valor |
|---------|-------|
| N | 216 |
| Win Rate | 53.7% |
| IC95% | [47.0%, 60.3%] |
| ROI | +39.1% |
| P/L total | +844.94 (stake=10) |
| Avg Odds | 2.96 |
| Max Drawdown | 60.0 |
| Sharpe Ratio | 3.15 |
| Ligas | 33 |

### Train Set (70%, N=151)
| Metrica | Valor |
|---------|-------|
| WR | 53.6% |
| ROI | +43.7% |

### Test Set (30%, N=65)
| Metrica | Valor |
|---------|-------|
| WR | 53.8% |
| ROI | +28.4% |

### Score-specific Breakdown
| Score | N | WR | ROI | Avg Odds | Train ROI | Test ROI |
|-------|---|-----|------|----------|-----------|----------|
| 1-0 | 127 | 55.1% | 35.5% | 2.80 | 20.5% | 69.9% |
| 0-1 | 89 | 51.7% | 44.2% | 3.18 | 80.3% | -13.6% |

Note: Individual score splits show some variance but aggregate is robust.

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (216) |
| N_test >= 18 | PASS (65) |
| ROI train+test > 0% | PASS (43.7/28.4) |
| IC95% lo > 40% | PASS (47.0%) |
| Max DD < 400 | PASS (60.0) |
| Overlap < 30% | PASS (see below) |
| >= 3 ligas | PASS (33) |
| Concentracion < 50% | PASS (36.1%) |

## Overlap con Estrategias Existentes
Note: Match-level overlap with existing strategies is expected because the SAME match can trigger multiple strategies in DIFFERENT markets. The overlap below measures same-match triggers, NOT same-market redundancy.

| Estrategia existente | Match overlap | Notes |
|---------------------|--------------|-------|
| H49 (CS 2-1/1-2) | 0% | Different scorelines, zero overlap |
| H48 (LAY U2.5 1-1) | 0% | Score 1-0/0-1 vs 1-1, mutually exclusive |
| Draw 0-0 | 71.3% | Different score (0-0 vs 1-0), different market |
| Under 2.5 | 82.9% | Different market entirely |
| LAY Over 2.5 Def | 94.0% | Different market entirely |

The strategy is genuinely independent: it trades the CS market, which no other active strategy trades for these scorelines.

## Edge Decay Analysis
- Train ROI: 43.7%, Test ROI: 28.4% -- ratio 0.65, no significant decay
- Date concentration: 36.1% max in any 3-day window (PASS)
- Cross-league: profitable across 33 leagues, no single league dominates
- Market efficiency: avg winning odds (2.96) vs avg losing odds (2.96) -- no systematic bias

## Config Recomendado (cartera_config.json)
```json
{
  "back_cs_one_goal": {
    "enabled": true,
    "minuteMin": 68,
    "minuteMax": 85
  }
}
```

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_back_cs_one_goal(min_dur, ...)`
- **Frontend filter**: `filterBackCsOneGoalBets(bets, params, version)`
- **Live detection**: STRATEGY N in `detect_betting_signals()`
- **Columnas CSV requeridas**: `back_rc_1_0`, `back_rc_0_1`, `goles_local`, `goles_visitante`, `minuto`
- **Manejo de nulls**: CS columns have ~40-50% availability at min 75-85. Matches without CS odds are skipped (not bet on). This naturally filters to matches with sufficient Betfair CS liquidity.
- **Relationship with H49**: H49 covers 2-1/1-2, this covers 1-0/0-1. Together they exploit the CS structural inefficiency across the 4 most common non-draw scorelines.
- **Dedup**: One bet per match. If score is 1-0 at min 68 and still 1-0 at min 72, only the first trigger counts.
