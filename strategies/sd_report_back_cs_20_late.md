# Nueva Estrategia: BACK CS 2-0/0-2 Late (H79)

## Concepto
Back Correct Score 2-0 or 0-2 when the match shows that exact score at minute 75-90. A 2-goal lead this late holds ~53% of the time, but the CS market implies only ~36% (avg odds 2.74). This is a revision of H55 (previously in monitoring with IC95_lo=32%) -- with updated data and optimized params, it now passes all quality gates.

## Edge Thesis
Same structural CS inefficiency as H49/H53/H77: the market must distribute probability across all possible final scores, systematically underpricing the current score. For 2-0/0-2 specifically, the market overestimates both (a) the trailing team scoring AND (b) the leading team scoring again. A 2-goal lead late is a "defensive equilibrium" where both teams settle into roles that maintain the status quo. The 0-2 scoreline shows even higher WR (59.3%) because away teams with 2-goal leads tend to be more defensive-minded.

## Trigger Conditions
- **Minuto**: [75, 90]
- **Marcador**: Score is exactly 2-0 or 0-2
- **Stats**: None required (Tier 1 only)
- **Cuota**: back_rc_2_0 or back_rc_0_2, must be in range [1.05, 10.0]

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Correct Score 2-0 or 0-2
- **Win condition**: Final score matches the current score (2-0 or 0-2)

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=90)
| Metrica | Valor |
|---------|-------|
| N | 90 |
| Win Rate | 53.3% |
| IC95% | [43.1%, 63.3%] |
| ROI (raw) | 49.1% |
| ROI (realistic) | 46.2% |
| P/L total (realistic) | 415.38 (stake=10) |
| Avg Odds | 2.74 |
| Max Drawdown | 102.46 |
| Sharpe Ratio (realistic) | 2.19 |
| Ligas | 28 |

### Score Breakdown
| Scoreline | N | WR | Avg Odds |
|-----------|---|----|----------|
| 2-0 | 63 | 50.8% | 2.58 |
| 0-2 | 27 | 59.3% | 3.13 |

### Train Set (70%, N=63)
| Metrica | Valor |
|---------|-------|
| ROI (realistic) | 43.5% |

### Test Set (30%, N=27)
| Metrica | Valor |
|---------|-------|
| ROI (realistic) | 52.0% |

## Realistic Validation Output (sd_validate_realistic.py)
```
============================================================
  SD REALISTIC VALIDATION
============================================================
  Raw:       N=90, WR=53.3%, ROI=49.1%, P/L=441.59, MaxDD=70.65
  Realistic: N=90, WR=53.3%, ROI=46.2%, P/L=415.38, MaxDD=102.46
  Delta:     N=0, WR=0.0pp, ROI=-2.9pp, P/L=-26.21
  Slippage:  2% | Odds: [1.05, 10.0] | Dedup: True

  Quality Gates (PASS):
    [PASS] min_n: 90 (required: 35)
    [PASS] min_roi: 46.2 (required: 10.0)
    [PASS] ic95_low: 43.1 (required: 40.0)
    [PASS] train_roi_positive: 43.5 (required: > 0)
    [PASS] test_roi_positive: 52.0 (required: > 0)
============================================================
```

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 35 | PASS (90) |
| ROI realistic >= 10% | PASS (46.2%) |
| IC95% lo > 40% | PASS (43.1%) |
| Train ROI > 0% | PASS (43.5%) |
| Test ROI > 0% | PASS (52.0%) |
| Overlap < 30% same market | PASS (0% -- unique CS scoreline) |
| >= 3 ligas | PASS (28) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Market overlap |
|---------------------|--------------|----------------|
| H49 (CS 2-1/1-2) | 6.7% | 0% (different scorelines) |
| H53 (CS 1-0/0-1) | 33.3% | 0% (different scorelines) |
| H55 (monitoring) | 100% -- H79 IS H55 revisited | same |
| H77 (CS 1-1) | 0% | 0% |
| H81 (CS 3-0/0-3+3-1/1-3) | 11.1% | 0% |

Note: H79 supersedes H55 (which was in monitoring). H55 should be removed from monitoring.

## Config Recomendado (cartera_config.json)
```json
{
  "cs_20": {
    "enabled": true,
    "minuteMin": 75,
    "minuteMax": 90,
    "oddsMax": 10.0
  }
}
```

## Notas de Implementacion
- **Columnas CSV requeridas**: minuto, goles_local, goles_visitante, back_rc_2_0, back_rc_0_2
- **Manejo de nulls**: Skip row if relevant back_rc column is null
- **Tier dependencia**: 1 only
- **Relationship to H55**: This IS H55 with better params (min 75-90 instead of 65-80, odds_max 10.0). H55 should be moved to SUPERSEDED.
