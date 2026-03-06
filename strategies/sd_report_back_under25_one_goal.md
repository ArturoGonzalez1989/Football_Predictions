# Nueva Estrategia: BACK Under 2.5 One-Goal Late (H46)

## Concepto
When a match is at 1-0 or 0-1 with 15 minutes or less remaining (min 75-85), the likelihood of 2+ additional goals is very low. The leading team defends and slows the game, while the trailing team pushes but rarely scores. BACK Under 2.5 captures this low-scoring endgame pattern.

## Edge Thesis
The Under 2.5 market at 1-goal scores (75-85') still prices in some probability of 2+ additional goals (equalizer + go-ahead or two late goals). In reality, only ~5% of these games reach 3+ total goals. The market overestimates late-game goal probability in games where one team has been defending a lead for most of the second half.

## Trigger Conditions
- **Minuto**: [75, 85]
- **Marcador**: Total goals = 1 (score 1-0 or 0-1)
- **Stats**:
  - xG total <= 2.0 (filters out high-xG games where more goals are likely)
  - SoT total <= 6 (filters out games with heavy shot activity)
- **Cuota**: `back_under25` > 1.0

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Under 2.5 Goals
- **Win condition**: FT total goals <= 2

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=131)
| Metrica | Valor |
|---------|-------|
| N | 131 |
| Win Rate | 94.7% |
| IC95% | [89.4%, 97.4%] |
| ROI | 7.5% |
| P/L total | +98.71 (stake=10) |
| Avg Odds | 1.15 |
| Max Drawdown | 18.29 |
| Sharpe Ratio | 2.59 |
| Ligas | 31 |

### Train Set (70%, N=91)
| Metrica | Valor |
|---------|-------|
| WR | 93.4% |
| ROI | 7.7% |

### Test Set (30%, N=40)
| Metrica | Valor |
|---------|-------|
| WR | 97.5% |
| ROI | 7.2% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (131) |
| N_test >= 18 | PASS (40) |
| ROI train+test > 0% | PASS (7.7%/7.2%) |
| IC95% lo > 40% | PASS (89.4%) |
| Max DD < 400 | PASS (18.29) |
| Overlap < 30% | PASS (16-21% with scoreless strategies) |
| >= 3 ligas | PASS (31) |
| Concentracion < 50% | PASS (41.2%) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap |
|---------------------|--------------|
| H25 BACK Under 2.5 Scoreless | 16.0% |
| H44 LAY Over 1.5 Scoreless | 13.0% |
| H41 LAY Over 2.5 Scoreless | 20.6% |
| H48 LAY Under 2.5 at 1-1 | 0.0% |
| H49 BACK CS 2-1/1-2 | 0.0% |

## Market Efficiency Check
- Avg odds of winning bets: 1.16
- Avg odds of losing bets: 1.15
- Winners and losers have similar odds, suggesting the edge is genuine and not driven by odds-level selection bias.

## Robustness
- Strategy works across 31 leagues
- No single league accounts for more than 28.2% of bets
- Train and test ROI are remarkably consistent (7.7% vs 7.2%)
- Date concentration 41.2% -- within limits but on the higher side
- Removing xG and SoT filters (broader version): N=182, WR=92.3%, ROI=6.9% -- still works without stat filters

## Config Recomendado (cartera_config.json)
```json
{
  "back_under25_one_goal": {
    "enabled": true,
    "minuteMin": 75,
    "minuteMax": 85,
    "xgMax": 2.0,
    "sotMax": 6
  }
}
```

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_back_under25_one_goal(min_dur, ...)`
- **Frontend filter**: `filterBackUnder25OneGoalBets(bets, params, version)`
- **Live detection**: STRATEGY N in `detect_betting_signals()`
- **Columnas CSV requeridas**: `minuto`, `goles_local`, `goles_visitante`, `back_under25`, `xg_local`, `xg_visitante`, `tiros_puerta_local`, `tiros_puerta_visitante`
- **Manejo de nulls**: xG and SoT are Tier 1 (>95% coverage). If null, the filter is skipped (bet still triggers).
- **Superset gate**: Backend uses `total_goals <= 2` and `minuto >= 70` for broader superset. Frontend applies exact params.
- **Risk profile**: Very safe -- avg odds 1.15, max loss = 1 stake, typical win = 0.14 * stake. Slow grinder.
