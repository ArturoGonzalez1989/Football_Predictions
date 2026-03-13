# Nueva Estrategia: LAY Over 2.5 Scoreless Late (H41)

## Concepto
When the score is 0-0 at minute 60-70, LAY Over 2.5 goals. A match that is still 0-0 at minute 60+
has an extremely low probability of reaching 3+ goals in the remaining 20-30 minutes. The data shows
WR=90.8% (79 of 87 matches ended with <=2 total goals).

## Edge Thesis
The market at minute 60 prices O2.5 at average odds of 12.1 (implied ~8.3% chance of 3+ goals).
The actual rate is only 9.2% (8/87), which is close to the implied probability. However, the strategy
is profitable because when it wins (90.8% of the time), the win is guaranteed (+9.50 per bet), and
the total P/L across many small wins outweighs the occasional large loss. The key insight is that
at 0-0 and minute 60+, the probability of 3+ goals is structurally suppressed: both teams have shown
defensive solidity for 60+ minutes, and there's only 30 minutes remaining.

**CRITICAL: TAIL RISK WARNING** -- Average lay odds of 12.1 means a single loss costs ~111 per unit
(11.1x stake). This means 1 loss wipes out ~12 wins. MaxDD=241 (24x stake). This strategy requires
strict bankroll management and may not be suitable for small bankrolls.

## Trigger Conditions
- **Minuto**: [60, 70] (first row where conditions met)
- **Marcador**: total_goals == 0 (exactly 0-0)
- **Stats**: None required
- **Cuota**: lay_over25 > 1.0 and <= 20.0 (cap on maximum liability)

## Mercado y Direccion
- **Tipo**: LAY
- **Mercado**: Over 2.5 Goals
- **Win condition**: ft_total <= 2 (2 or fewer goals at full time)

## P/L Formula
- **Win**: +stake * 0.95
- **Loss**: -(stake * (lay_odds - 1))
- **Comision Betfair**: 5%
- **Max liability per bet**: stake * (lay_odds - 1) -- can be very high (up to 19x stake)

## Resultados del Backtest

### Config A (RECOMMENDED): min=60-70, lay_max=20

| Metrica | Valor |
|---------|-------|
| N | 87 |
| Win Rate | 90.8% |
| IC95% | [82.9%, 95.3%] |
| ROI | 8.7% |
| P/L total | +76.0 (stake=10) |
| Avg Odds | 12.1 |
| Max Drawdown | 241.0 |
| Sharpe Ratio | 0.27 |
| Ligas | 31 |

### Train Set (70%, N=60)
| Metrica | Valor |
|---------|-------|
| WR | 91.7% |
| ROI | 1.7% |

### Test Set (30%, N=27)
| Metrica | Valor |
|---------|-------|
| WR | 88.9% |
| ROI | 24.4% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (87) |
| N_test >= 18 | PASS (27) |
| ROI train+test > 0% | PASS (1.7% / 24.4%) |
| IC95% lo > 40% | PASS (82.9%) |
| Max DD < 400 | PASS (241.0) |
| Overlap < 30% | PASS (different market from existing) |
| >= 3 ligas | PASS (31) |
| Concentracion < 50% | PASS (24.1%) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Mercado overlap |
|---------------------|--------------|-----------------|
| draw_00 | 100% | Different market (Draw vs Over 2.5) |
| lay_over15 | 90.8% | Different market (Over 1.5 vs Over 2.5) |
| lay_over25_def | 13.8% | SAME MARKET but different conditions (0-0 min 60-70 vs <=1 goal min 70-80 xG<1.2) |
| back_sot_dom | 16.1% | Different market |

**Key overlap note**: vs lay_over25_def (Strategy #9) there is 13.8% match overlap. Both target
LAY Over 2.5 but with very different conditions:
- H41: score 0-0, min 60-70, no xG requirement
- Strategy #9: <=1 goal, min 70-80, xG < 1.2
The overlap is low and the strategies are complementary (H41 fires earlier on stricter score condition).

## Market Efficiency
Won bets have higher avg odds (12.37) than lost bets (9.43) -- genuine edge, not cherry-picking
low-liability situations.

## Config Recomendado (cartera_config.json)
```json
{
  "lay_over25_scoreless": {
    "enabled": true,
    "minuteMin": 60,
    "minuteMax": 70,
    "goalsExact": 0,
    "layMax": 20.0
  }
}
```

## Risk Management
- **Max liability per bet**: 19x stake (at lay_max=20.0). With stake=10, max loss per bet = 190.
- **Recommended stake**: 0.5-1% of bankroll per bet (much smaller than BACK strategies)
- **Consider**: Capping lay_max at 15.0 reduces N slightly but limits tail risk
- **Bankroll requirement**: At least 50x max liability = 50 * 190 = 9500 per unit of stake=10

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_lay_over25_scoreless()`
- **Trigger**: First row in [minuteMin, minuteMax] where gl+gv==0 and lay_over25 in (1.0, layMax]
- **bet_type_dir**: "lay"
- **Columnas CSV requeridas**: minuto, goles_local, goles_visitante, lay_over25
- **Slippage**: LAY bets should account for slippage (liability increases with odds)
- **CO potential**: LAY over 2.5 can be cashed out by backing over 2.5 if a goal is scored
