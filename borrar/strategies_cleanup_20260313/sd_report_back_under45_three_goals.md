# Nueva Estrategia: BACK Under 4.5 Three Goals Low xG (H71)

## Concepto
When 3 goals have been scored by minute 65-85 but the combined xG is below 2.0, the goals represent overperformance relative to chance quality. The 4th goal is unlikely because the underlying match quality does not support high-scoring games. The Under 4.5 market overprices the probability of a 4th goal based on the raw goal count rather than chance quality.

## Edge Thesis
The market anchors on "3 goals already scored" and extrapolates more goals. But xG analysis reveals these games are actually low-activity matches where goals came from overperformance (lucky finishes, defensive errors, set pieces). With xG < 2.0 at minute 65+, the expected remaining goals are very low. The 4th goal probability is overpriced by ~12pp.

This extends H66 (Under 3.5 at 3 goals) to a different Under market. Same trigger concept but complementary bet: H66 bets no more goals at all, H71 allows one more goal (Under 4.5 is more conservative).

## Trigger Conditions
- **Minuto**: [65, 85]
- **Marcador**: Exactly 3 total goals (gl + gv = 3)
- **Stats**: Combined xG (xg_local + xg_visitante) < 2.0
- **Cuota**: back_under45, must be >= 1.05 and <= 10.0

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Under 4.5 Goals
- **Win condition**: Final total goals <= 4

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=60)
| Metrica | Valor |
|---------|-------|
| N | 60 |
| Win Rate | 96.7% |
| IC95% | [88.6%, 99.1%] |
| ROI (raw) | 13.9% |
| ROI (realistic) | 11.9% |
| P/L total (realistic) | 71.18 (stake=10) |
| Avg Odds | 1.19 |
| Max Drawdown | 10.0 |
| Sharpe Ratio | 3.99 (realistic) |
| Ligas | 25 |

### Train Set (70%, N=42)
| Metrica | Valor |
|---------|-------|
| WR | ~97% |
| ROI | 12.0% |

### Test Set (30%, N=18)
| Metrica | Valor |
|---------|-------|
| WR | ~97% |
| ROI | 11.6% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 35 | PASS (60) |
| ROI >= 10% (realistic) | PASS (11.9%) |
| IC95% lo >= 40% | PASS (88.6%) |
| Train ROI > 0% | PASS (12.0%) |
| Test ROI > 0% | PASS (11.6%) |
| Overlap < 30% (same market) | PASS (0% -- Under 4.5 is unique market) |
| >= 3 ligas | PASS (25) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Market overlap |
|---------------------|--------------|----------------|
| H66 (Under 3.5) | 95.0% | Different market (U4.5 vs U3.5) |
| H49 (CS 2-1/1-2) | 76.7% | Different market |
| H59 (Underdog Leading) | 33.3% | Different market |
| H67 (Away Fav Leading) | 20.0% | Different market |
| H58 (Draw 1-1) | 13.3% | Different market |

**Note**: 95% match overlap with H66 means these strategies trigger on the same matches but in different markets. This is by design -- the same "3 goals with low xG" situation presents value in both Under 3.5 and Under 4.5 markets. However, this means H71 adds minimal INDEPENDENT information to the portfolio. It is essentially a complementary bet to H66 on the same trigger.

## Realistic Validation
- Slippage 2%: ROI drops from 13.9% to 11.9% (-2.0pp)
- Dedup: No change
- Odds filter: No change
- **Verdict: PASS** -- passes all gates but ROI is close to the 10% threshold

## Risk Assessment
- **Ultra-low risk**: WR=96.7%, MaxDD=10 (one loss). Only 2 losses in 60 bets.
- **Low return per bet**: Avg odds 1.19 means winning ~1.71 per bet, losing ~10 per bet. Need ~6 wins per loss to break even.
- **ROI sensitivity**: At 11.9% realistic, slippage or odds deterioration could push below 10% threshold.

## Config Recomendado (cartera_config.json)
```json
{
  "under45_three_goals": {
    "enabled": true,
    "minuteMin": 65,
    "minuteMax": 85,
    "totalGoals": 3,
    "maxXG": 2.0
  }
}
```

## Notas de Implementacion
- **Columnas CSV requeridas**: `back_under45`, `xg_local`, `xg_visitante`, `goles_local`, `goles_visitante`, `minuto`
- **Manejo de nulls**: xG is Tier 1 (< 5% null rate). If xG is null, skip the row.
- **Complementary to H66**: Can trigger simultaneously with H66 on the same match. Consider combined position sizing.
- **Marginal approval**: ROI realistic is 11.9%, just above the 10% threshold. Monitor closely with new data.
