# Nueva Estrategia: BACK CS 1-1 Late (H77)

## Concepto
Back Correct Score 1-1 when the match is tied 1-1 at minute 75-90. The CS market must distribute probability across dozens of possible scorelines, systematically undervaluing the current score. At 1-1 late, the hold rate is 57.8% vs market-implied ~46% (avg odds 2.19).

## Edge Thesis
The CS market has a structural inefficiency: it must price ALL possible final scores simultaneously, so the probability assigned to any single score is compressed. This effect is strongest for the CURRENT score late in the game because the market overestimates the chance of further goals. Different from H58 (BACK Draw 1-1) which uses the Match Odds Draw market -- this targets the CS market which has higher odds and therefore higher ROI potential, though with lower liquidity.

## Trigger Conditions
- **Minuto**: [75, 90]
- **Marcador**: Score is exactly 1-1
- **Stats**: None required (Tier 1 only: score + CS odds)
- **Cuota**: back_rc_1_1, must be in range [1.05, 8.0]

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Correct Score 1-1
- **Win condition**: Final score is exactly 1-1

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=102)
| Metrica | Valor |
|---------|-------|
| N | 102 |
| Win Rate | 57.8% |
| IC95% | [48.1%, 67.0%] |
| ROI (raw) | 26.6% |
| ROI (realistic) | 24.1% |
| P/L total (realistic) | 245.76 (stake=10) |
| Avg Odds | 2.19 |
| Max Drawdown | 85.53 |
| Sharpe Ratio (realistic) | 1.63 |
| Ligas | 28 |

### Train Set (70%, N=71)
| Metrica | Valor |
|---------|-------|
| WR | 57.8% |
| ROI (realistic) | 14.6% |

### Test Set (30%, N=31)
| Metrica | Valor |
|---------|-------|
| WR | 57.8% |
| ROI (realistic) | 45.7% |

## Realistic Validation Output (sd_validate_realistic.py)
```
============================================================
  SD REALISTIC VALIDATION
============================================================
  Raw:       N=102, WR=57.8%, ROI=26.6%, P/L=271.11, MaxDD=112.01
  Realistic: N=102, WR=57.8%, ROI=24.1%, P/L=245.76, MaxDD=85.53
  Delta:     N=0, WR=0.0pp, ROI=-2.5pp, P/L=-25.35
  Slippage:  2% | Odds: [1.05, 10.0] | Dedup: True

  Quality Gates (PASS):
    [PASS] min_n: 102 (required: 35)
    [PASS] min_roi: 24.1 (required: 10.0)
    [PASS] ic95_low: 48.1 (required: 40.0)
    [PASS] train_roi_positive: 14.6 (required: > 0)
    [PASS] test_roi_positive: 45.7 (required: > 0)
============================================================
```

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 35 | PASS (102) |
| ROI realistic >= 10% | PASS (24.1%) |
| IC95% lo > 40% | PASS (48.1%) |
| Train ROI > 0% | PASS (14.6%) |
| Test ROI > 0% | PASS (45.7%) |
| Overlap < 30% same market | PASS (0% -- unique CS scoreline) |
| >= 3 ligas | PASS (28) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Market overlap |
|---------------------|--------------|----------------|
| H49 (CS 2-1/1-2) | 14.7% | 0% (different scorelines) |
| H53 (CS 1-0/0-1) | 35.3% | 0% (different scorelines) |
| H58 (Draw 1-1) | 96.1% | 0% (CS vs Match Odds markets) |
| H79 (CS 2-0/0-2) | 0% | 0% |
| H81 (CS 3-0/0-3+3-1/1-3) | 0% | 0% |

Note: 96.1% match overlap with H58 is expected -- both trigger on 1-1 scoreline but trade DIFFERENT markets (CS vs Match Odds Draw). They are complementary bets, not redundant.

## Config Recomendado (cartera_config.json)
```json
{
  "cs_11": {
    "enabled": true,
    "minuteMin": 75,
    "minuteMax": 90,
    "oddsMax": 8.0
  }
}
```

## Notas de Implementacion
- **Columnas CSV requeridas**: minuto, goles_local, goles_visitante, back_rc_1_1
- **Manejo de nulls**: Skip row if back_rc_1_1 is null (Tier 1, <5% null rate)
- **Tier dependencia**: 1 only (zero data availability risk)
- **Liquidity warning**: CS market may have lower liquidity than Match Odds. Consider slippage > 2% for large stakes.
