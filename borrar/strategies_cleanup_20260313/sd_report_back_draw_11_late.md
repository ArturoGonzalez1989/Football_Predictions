# Nueva Estrategia: BACK Draw at 1-1 Late (H58)

## Concepto
When the score is 1-1 at minute 70-85 and draw odds are above 1.5, BACK Draw in the Match Odds market. The draw rate at 1-1 late is 55.5%, significantly higher than what the market implies (~43% at avg odds 2.31). Both teams having scored creates a tactical dynamic where neither wants to concede again, leading to more draws than the market expects.

## Edge Thesis
The market underprices draws at 1-1 for several reasons: (1) Both teams having scored creates a "false momentum" impression -- bettors expect more action but teams actually become more cautious. (2) The 1-1 scoreline combines two contradictory signals: "both teams can score" (suggesting more goals) and "game is tight" (suggesting caution). The market leans toward the first interpretation, but the data shows 55.5% of 1-1 games at min 70+ end as draws. (3) This is fundamentally different from the 0-0 draw strategy -- at 0-0, both defenses have been dominant; at 1-1, both attacks have succeeded but the mutual vulnerability creates a stalemate equilibrium.

## Trigger Conditions
- **Minuto**: [70, 85]
- **Marcador**: 1-1
- **Cuota**: back_draw > 1.5
- **No upper odds cap**: all draw odds accepted

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Match Odds - Draw
- **Win condition**: Final score is a draw (any draw, not just 1-1)

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=128)
| Metrica | Valor |
|---------|-------|
| N | 128 |
| Win Rate | 55.5% |
| IC95% | [46.8%, 63.8%] |
| ROI | +31.0% |
| P/L total | +396.80 (stake=10) |
| Avg Odds | 2.31 |
| Max Drawdown | 63.54 |
| Sharpe Ratio | 2.26 |
| Ligas | 31 |

### Train Set (70%, N=89)
| Metrica | Valor |
|---------|-------|
| WR | 55.1% |
| ROI | +34.2% |

### Test Set (30%, N=39)
| Metrica | Valor |
|---------|-------|
| WR | 56.4% |
| ROI | +23.5% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (128) |
| N_test >= 18 | PASS (39) |
| ROI train+test > 0% | PASS (34.2/23.5) |
| IC95% lo > 40% | PASS (46.8%) |
| Max DD < 400 | PASS (63.54) |
| Overlap < 30% | PASS (0% market overlap with Draw 0-0) |
| >= 3 ligas | PASS (31) |
| Concentracion < 50% | PASS (33.6%) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Market overlap |
|---------------------|--------------|----------------|
| Draw 0-0 (Strategy 1) | 39.1% | 0% (mutually exclusive by score: 0-0 vs 1-1) |
| H48 (LAY U2.5 at 1-1) | 65.6% | 0% (different market: Draw vs Under 2.5) |
| H49 (CS 2-1/1-2) | 21.9% | 0% (different market: Draw vs CS) |
| xG Underperformance | 26.6% | 0% (different market) |

H58 trades the Match Odds Draw market at 1-1. No existing strategy trades this exact market in this exact condition. The high match-level overlap with H48 is expected because both trigger on 1-1 games, but they trade completely different markets (H48 lays Under 2.5 = expects more goals; H58 backs Draw = expects no winner).

## Edge Decay Analysis
- Train ROI: 34.2%, Test ROI: 23.5% -- ratio 0.69, healthy
- Date concentration: 33.6% max in any 3-day window (PASS)
- Cross-league: profitable across 31 leagues
- Market efficiency: avg winning odds 2.43, avg losing odds 2.15 -- winners have HIGHER odds than losers, indicating the market is NOT pricing this pattern (genuine edge)

## Config Recomendado (cartera_config.json)
```json
{
  "back_draw_11": {
    "enabled": true,
    "minuteMin": 70,
    "minuteMax": 85,
    "oddsMin": 1.5
  }
}
```

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_back_draw_11(min_dur, ...)`
- **Frontend filter**: `filterBackDraw11Bets(bets, params, version)`
- **Live detection**: STRATEGY N in `detect_betting_signals()`
- **Columnas CSV requeridas**: `back_draw`, `goles_local`, `goles_visitante`, `minuto`
- **Manejo de nulls**: back_draw has >95% availability -- virtually no null issues
- **Differentiation from Draw 0-0**: This strategy is fundamentally different from Strategy 1 (Back Draw 0-0). It triggers on 1-1 (both teams scored), while Strategy 1 triggers on 0-0 (no goals). The tactical dynamics are completely different. No dedup needed between them.
- **Complementarity with H48**: H48 (LAY Under 2.5 at 1-1) and H58 (BACK Draw at 1-1) trigger on the same matches but trade different markets. They are complementary, not conflicting. H48 profits when more goals are scored, H58 profits when the score stays tied. In cases where the match ends 2-2 or higher tied score, both H48 and H58 win. When it ends 1-1, H58 wins but H48 loses. When a team wins 2-1, H48 wins but H58 loses. Correlation is moderate -- they share some wins but also have opposite outcomes.
- **Dedup**: One bet per match. First trigger at 1-1 in minute range counts.
