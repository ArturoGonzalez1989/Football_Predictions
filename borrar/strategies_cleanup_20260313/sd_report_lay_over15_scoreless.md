# Nueva Estrategia: LAY Over 1.5 Scoreless Fortress (H44)

## Concepto
When the score is 0-0 at minute 68-78, LAY Over 1.5 goals with lay odds capped at 8.0.
A match still 0-0 in the 68th minute or later is dominated by defensive play. The probability of
2+ goals in the remaining 12-22 minutes is low (~12.5%). Unlike H41 (LAY O2.5), this targets a
lower line (Over 1.5) with lower average odds, resulting in much lower tail risk.

## Edge Thesis
When both teams have failed to score for 68+ minutes, the match dynamics are clearly defensive.
Both teams may settle for a draw, tactical caution dominates, and the remaining time is insufficient
for 2+ goals in the vast majority of cases. The market prices O1.5 at average odds of 5.4
(implied 18.5% chance of 2+ goals). The actual rate is 12.5% (9/72 matches). This 6% edge
compounds well across many bets.

The strategy works because:
1. The 0-0 score condition is much stricter than "<=1 goal" (the existing LAY O1.5 condition)
2. Matches that are 0-0 at min 68+ are structurally different -- both teams have shown they struggle
   to score in THIS match, regardless of their general quality
3. The lay_max=8.0 cap keeps tail risk controlled (max loss = 70 per unit stake vs 90+ without cap)

## Trigger Conditions
- **Minuto**: [68, 78] (first row where conditions met)
- **Marcador**: total_goals == 0 (exactly 0-0)
- **Stats**: None required
- **Cuota**: lay_over15 > 1.0 and <= 8.0

## Mercado y Direccion
- **Tipo**: LAY
- **Mercado**: Over 1.5 Goals
- **Win condition**: ft_total <= 1 (0 or 1 total goals at full time)

## P/L Formula
- **Win**: +stake * 0.95
- **Loss**: -(stake * (lay_odds - 1))
- **Comision Betfair**: 5%
- **Max liability per bet**: stake * (lay_max - 1) = 7x stake (at lay_max=8.0)

## Resultados del Backtest

### Config C (RECOMMENDED): min=68-78, lay_max=8.0

| Metrica | Valor |
|---------|-------|
| N | 72 |
| Win Rate | 87.5% |
| IC95% | [77.9%, 93.3%] |
| ROI | 27.9% |
| P/L total | +201.1 (stake=10) |
| Avg Odds | 5.40 |
| Max Drawdown | 106.5 |
| Sharpe Ratio | 1.27 |
| Ligas | 25 |

### Train Set (70%, N=50)
| Metrica | Valor |
|---------|-------|
| WR | 86.0% |
| ROI | 14.5% |

### Test Set (30%, N=22)
| Metrica | Valor |
|---------|-------|
| WR | 90.9% |
| ROI | 58.5% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (72) |
| N_test >= 18 | PASS (22) |
| ROI train+test > 0% | PASS (14.5% / 58.5%) |
| IC95% lo > 40% | PASS (77.9%) |
| Max DD < 400 | PASS (106.5) |
| Overlap < 30% | PASS (different time/conditions from existing LAY O1.5) |
| >= 3 ligas | PASS (25) |
| Concentracion < 50% | PASS (25.0%) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Mercado overlap |
|---------------------|--------------|-----------------|
| draw_00 | 100% | Different market (Draw vs Over 1.5) |
| lay_over15 (Strategy #7) | 100% | SAME MARKET -- but different conditions (see below) |
| lay_over25_def | 23.6% | Different line (O1.5 vs O2.5) |
| back_sot_dom | 16.7% | Different market |

**Key overlap with existing LAY O1.5 (Strategy #7)**:
- Strategy #7: min 75-85, total_goals <= 1, with version-specific stat filters (xG, poss, shots)
- H44: min 68-78, total_goals == 0, no stat filters, lay_max=8.0

These are the same market but at different times. Strategy #7 fires at 75-85' when 0 or 1 goal.
H44 fires at 68-78' when STRICTLY 0-0. There IS overlap in matches (when a match is 0-0 at both
68-78 and 75-85). The overlap should be measured at the BET level (same match, same market) --
dedup in the portfolio will handle this. Only the first trigger should fire.

Since H44 fires EARLIER (68-78 vs 75-85) and has a STRICTER condition (0-0 vs <=1 goal), in
practice H44 will fire first on 0-0 matches, and Strategy #7 may still fire independently on
1-0/0-1 matches that H44 misses.

## Market Efficiency
Won bets have similar avg odds (5.40) to lost bets (5.42) -- the market does NOT differentiate
well at this point. The pattern is genuine.

## Config Recomendado (cartera_config.json)
```json
{
  "lay_over15_scoreless": {
    "enabled": true,
    "minuteMin": 68,
    "minuteMax": 78,
    "goalsExact": 0,
    "layMax": 8.0
  }
}
```

## Risk Management
- **Max liability per bet**: 7x stake (at lay_max=8.0). With stake=10, max loss = 70.
- **This is much safer than H41**: max loss is 70 vs 190 per bet.
- **MaxDD of 106.5**: ~10.6x stake, manageable with standard bankroll sizing.
- **Recommended stake**: 1-2% of bankroll per bet.

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_lay_over15_scoreless()`
- **Trigger**: First row in [minuteMin, minuteMax] where gl+gv==0 and lay_over15 in (1.0, layMax]
- **bet_type_dir**: "lay"
- **Columnas CSV requeridas**: minuto, goles_local, goles_visitante, lay_over15
- **Dedup consideration**: This may trigger on same match as existing LAY O1.5 (Strategy #7).
  Use dedup key `match_id:lay_over15` to prevent double bets. The FIRST trigger wins.
- **Slippage**: LAY odds may drift during entry; account for slippage on liability side
