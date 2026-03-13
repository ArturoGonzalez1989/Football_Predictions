# Nueva Estrategia: LAY Under 2.5 Tied at 1-1 (H48)

## Concepto
When two teams are level at 1-1 in the second half (min 55-65), both teams have strong incentive to attack for the winning goal. Unlike 0-0 or 1-goal-lead scenarios, at 1-1 both teams know a draw is suboptimal -- each pushes for the winner, creating an open game. The Under 2.5 market at 1-1 overestimates the chance of no further goals because the score "looks balanced." In reality, 57-63% of 1-1 games at min 55-65 produce 3+ total goals.

## Edge Thesis
Market participants see 1-1 and think "balanced game, likely to stay this way." But the psychology of 1-1 is the opposite of 0-0: both managers have tasted a goal and want more. Both teams open up, creating space. The stat evidence shows xG and SoT don't predict which 1-1 games produce more goals -- it's the tactical dynamic itself. The Under 2.5 market overprices the "stay at 1-1" scenario because it treats all tied games similarly, ignoring the tactical divergence between 0-0 and 1-1.

## Trigger Conditions
- **Minuto**: [55, 65]
- **Marcador**: Score = 1-1 exactly
- **Stats**: None required (xG and SoT do not improve prediction)
- **Cuota**: `lay_under25` > 1.0 AND `lay_under25` <= 2.5

## Mercado y Direccion
- **Tipo**: LAY
- **Mercado**: Under 2.5 Goals
- **Win condition**: FT total goals >= 3 (Under 2.5 loses, our LAY wins)

## P/L Formula
- **Win**: +stake * 0.95
- **Loss**: -(stake * (lay_odds - 1))
- **Comision Betfair**: 5%
- **Max liability per bet**: stake * (2.5 - 1) = 1.5 * stake (with lay_max=2.5)

## Resultados del Backtest

### Dataset Completo (N=62)
| Metrica | Valor |
|---------|-------|
| N | 62 |
| Win Rate | 62.9% |
| IC95% | [50.5%, 73.8%] |
| ROI | 15.6% |
| P/L total | +96.50 (stake=10) |
| Avg Odds | 2.10 |
| Max Drawdown | 77.90 |
| Sharpe Ratio | 1.14 |
| Ligas | 23 |

### Train Set (70%, N=43)
| Metrica | Valor |
|---------|-------|
| WR | 62.8% |
| ROI | 15.6% |

### Test Set (30%, N=19)
| Metrica | Valor |
|---------|-------|
| WR | 63.2% |
| ROI | 15.5% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (62) |
| N_test >= 18 | PASS (19) |
| ROI train+test > 0% | PASS (15.6%/15.5%) |
| IC95% lo > 40% | PASS (50.5%) |
| Max DD < 400 | PASS (77.90) |
| Overlap < 30% | PASS (25.8% max with H49) |
| >= 3 ligas | PASS (23) |
| Concentracion < 50% | PASS (37.1%) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap |
|---------------------|--------------|
| H25 BACK Under 2.5 Scoreless | 0% |
| H41 LAY Over 2.5 Scoreless | 0% |
| H44 LAY Over 1.5 Scoreless | 0% |
| H46 BACK Under 2.5 One-Goal | 0% |
| H49 BACK CS 2-1/1-2 | 25.8% (16 matches) |

The 25.8% overlap with H49 is expected -- some 1-1 games become 2-1 or 1-2, triggering both strategies on the same match but at different minutes and on different markets. This is acceptable as they are truly independent bets.

## Stat Analysis
Interestingly, at 1-1 in min 55-65, the stats of games that go Over 2.5 vs Under 2.5 are nearly identical:
- xG total: Over 2.5 avg=1.22 vs Under 2.5 avg=1.37 (no difference)
- SoT total: Over 2.5 avg=5.39 vs Under 2.5 avg=5.70 (no difference)
- This confirms that stat-based filters don't help -- the edge is purely in the 1-1 tactical dynamic.

## Risk Profile
- **Max loss per bet**: stake * (2.5 - 1) = 1.5x stake (with lay_max=2.5)
- This is a MODERATE risk LAY strategy -- liability is capped at 1.5x stake
- Much safer than LAY Over strategies where lay odds can be 5-12x

## Config Recomendado (cartera_config.json)
```json
{
  "lay_under25_tied": {
    "enabled": true,
    "minuteMin": 55,
    "minuteMax": 65,
    "layMax": 2.5
  }
}
```

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_lay_under25_tied(min_dur, ...)`
- **Frontend filter**: `filterLayUnder25TiedBets(bets, params, version)`
- **Live detection**: STRATEGY N in `detect_betting_signals()`
- **Columnas CSV requeridas**: `minuto`, `goles_local`, `goles_visitante`, `lay_under25`
- **Manejo de nulls**: Only Tier 1 columns used. If `lay_under25` is null, bet is skipped.
- **Superset gate**: Backend uses `goles_local == 1 AND goles_visitante == 1` and `minuto >= 50`.
- **Key insight**: No stat filters improve this strategy. The edge is entirely in the 1-1 game state.
