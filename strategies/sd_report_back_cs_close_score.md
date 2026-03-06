# Nueva Estrategia: BACK Correct Score Close Game (H49)

## Concepto
In matches at 2-1 or 1-2 between minutes 70-80, the current scoreline has a ~57% probability of being the final result. The Correct Score market offers average odds of 3.57 for these outcomes, implying only ~28% probability. This massive gap between actual probability and market-implied probability creates exceptional value. The strategy backs the current correct score, betting that no further goals will be scored.

## Edge Thesis
The Correct Score market prices in ALL possible future scores (2-2, 3-1, 3-2, 2-3, etc.), significantly underestimating the probability of the current score holding. At 2-1/1-2 around minute 70-80:
- The leading team has a 1-goal cushion and shifts to defensive mode
- The trailing team pushes forward but rarely scores (especially in the last 20 min)
- The market distributes probability across many CS outcomes, each unlikely individually
- The current score being the most probable single outcome is systematically underpriced

This is a **structural inefficiency** in the CS market: it must price dozens of possible scorelines, and the most likely one (current score) is always underweighted by construction. The further into the match, the more extreme this mispricing becomes.

## Trigger Conditions
- **Minuto**: [70, 80]
- **Marcador**: Score is 2-1 or 1-2
- **Stats**: None required
- **Cuota**: `back_rc_{gl}_{gv}` for current score > 1.0

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Correct Score (dynamic: backs the current scoreline)
- **Win condition**: FT score matches the score at time of bet

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=118)
| Metrica | Valor |
|---------|-------|
| N | 118 |
| Win Rate | 56.8% |
| IC95% | [47.8%, 65.4%] |
| ROI | 85.4% |
| P/L total | +1008.00 (stake=10) |
| Avg Odds | 3.57 |
| Max Drawdown | 90.43 |
| Sharpe Ratio | 3.71 |
| Ligas | 33 |

### Train Set (70%, N=82)
| Metrica | Valor |
|---------|-------|
| WR | 57.3% |
| ROI | 105.4% |

### Test Set (30%, N=36)
| Metrica | Valor |
|---------|-------|
| WR | 55.6% |
| ROI | 39.9% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (118) |
| N_test >= 18 | PASS (36) |
| ROI train+test > 0% | PASS (105.4%/39.9%) |
| IC95% lo > 40% | PASS (47.8%) |
| Max DD < 400 | PASS (90.43) |
| Overlap < 30% | PASS (25.8% max with H48) |
| >= 3 ligas | PASS (33) |
| Concentracion < 50% | PASS (33.1%) |

## Extended Versions (tested but primary recommendation is 2-1/1-2)

| Scorelines | Min range | N | WR | ROI | Sharpe | Test ROI |
|------------|-----------|---|----|----|--------|----------|
| 2-1/1-2 | 70-80 | 118 | 56.8% | +85.4% | 3.71 | +39.9% |
| 1-0/0-1/2-1/1-2 | 70-80 | 309 | 56.6% | +51.7% | 4.47 | +24.1% |
| 1-0/0-1 | 70-80 | 193 | 56.5% | +33.9% | 2.73 | +7.2% |
| all non-draw | 70-80 | 384 | 52.6% | +38.6% | 3.87 | +13.8% |

The 4-scoreline version (1-0/0-1/2-1/1-2) has the highest Sharpe (4.47) and largest N (309) but lower ROI. It may be a more robust version to implement.

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap |
|---------------------|--------------|
| H46 BACK Under 2.5 One-Goal | 0% |
| H48 LAY Under 2.5 Tied | 25.8% (16 matches) |
| H25/H41/H44 Scoreless | 0% |

## Market Efficiency Check
- Avg odds of winning bets: 3.38
- Avg odds of losing bets: 3.81
- Losing bets have slightly higher odds (market partially efficient for extreme odds)
- But the edge persists even with odds cap at 6.0 (ROI=40.2%)

## Odds Cap Analysis
| Odds cap | N | WR | ROI | Test ROI |
|----------|---|----|----|----------|
| No cap | 118 | 56.8% | +85.4% | +39.9% |
| <= 6.0 | 104 | 57.7% | +40.2% | +19.7% |
| <= 5.0 | 101 | 58.4% | +27.9% | +11.8% |
| <= 4.0 | 99 | 57.6% | +19.6% | +10.4% |
| <= 3.0 | 95 | 57.9% | +17.2% | +14.2% |

Without a cap, ROI is highest but volatile. A cap at 6.0 reduces ROI but improves consistency.

## Config Recomendado (cartera_config.json)
```json
{
  "back_cs_close": {
    "enabled": true,
    "minuteMin": 70,
    "minuteMax": 80,
    "scores": ["2-1", "1-2"],
    "oddsMax": null
  }
}
```

### Alternative broad version
```json
{
  "back_cs_close": {
    "enabled": true,
    "minuteMin": 70,
    "minuteMax": 80,
    "scores": ["1-0", "0-1", "2-1", "1-2"],
    "oddsMax": null
  }
}
```

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_back_cs_close(min_dur, ...)`
- **Frontend filter**: `filterBackCsCloseBets(bets, params, version)`
- **Live detection**: STRATEGY N in `detect_betting_signals()`
- **Columnas CSV requeridas**: `minuto`, `goles_local`, `goles_visitante`, `back_rc_{gl}_{gv}` (dynamic)
- **Manejo de nulls**: CS columns have ~55-74% coverage. If the CS odds column is null, bet is skipped.
- **Dynamic column selection**: The odds column depends on the current score. Implementation must construct `back_rc_{gl}_{gv}` dynamically.
- **Superset gate**: Backend generates bets for all scores in the configured list with `minuto >= minuteMin - 5`.
- **Dedup**: One bet per match -- first qualifying row triggers the bet.
- **WARNING**: CS market is less liquid than Over/Under. Slippage may be higher. Consider conservative odds adjustment.
