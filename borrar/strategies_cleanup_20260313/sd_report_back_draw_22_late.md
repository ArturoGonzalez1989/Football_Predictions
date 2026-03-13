# Nueva Estrategia: BACK Draw at 2-2 Late (H68)

## Concepto
When the score is 2-2 at min 70-90, BACK Draw. Both teams have scored twice, creating a state of mutual exhaustion and tactical caution. The psychological dynamic at 2-2 is different from 1-1: having been behind and come back (or having traded goals) makes both teams risk-averse. Market underprices the draw by ~22pp.

## Edge Thesis
At 2-2, both teams have demonstrated ability to score, which makes the market overestimate the probability of a 5th goal. But the data shows that after 4 goals, match tempo often drops -- players are tired, managers make defensive substitutions, and the tactical incentive to push for a win diminishes when a draw is an acceptable result for both sides. The market prices ~38% draw probability (avg odds 2.83) when the actual rate is 60.7%.

## Trigger Conditions
- **Minuto**: [70, 90]
- **Marcador**: 2-2 exactly
- **Cuota**: back_draw, must be in [1.05, 8.0]

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Match Odds Draw
- **Win condition**: Match ends in a draw (ft_local == ft_visitante)

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=61)
| Metrica | Valor |
|---------|-------|
| N | 61 |
| Win Rate | 60.7% |
| IC95% | [48.1%, 71.9%] |
| ROI | 84.0% |
| P/L total | 512.26 (stake=10) |
| Avg Odds | 2.83 |
| Max Drawdown | 77.38 |
| Sharpe Ratio | 3.18 |
| Ligas | 37 |

### Train Set (70%, N=42)
| Metrica | Valor |
|---------|-------|
| WR | ~62% |
| ROI | 91.4% |

### Test Set (30%, N=19)
| Metrica | Valor |
|---------|-------|
| WR | ~58% |
| ROI | 67.6% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 37 | PASS (61) |
| ROI >= 10% | PASS (84.0%) |
| IC95% lo >= 40% | PASS (48.1%) |
| Train ROI > 0% | PASS (91.4%) |
| Test ROI > 0% | PASS (67.6%) |
| >= 3 ligas | PASS (37) |
| Date conc < 50% | PASS (23.0%) |

## Validacion Realista (sd_validate_realistic.py)
**Verdict: PASS**

| Metrica | Raw | Realistic | Delta |
|---------|-----|-----------|-------|
| N | 61 | 61 | 0 |
| WR% | 60.7 | 60.7 | 0pp |
| ROI% | 84.0 | 80.4 | -3.6pp |
| P/L | 512.26 | 490.45 | -21.81 |
| Train ROI | 91.4% | 87.7% | -3.7pp |
| Test ROI | 67.6% | 64.3% | -3.3pp |
| Sharpe | 3.18 | 3.11 | -0.07 |

> Output completo del validador:
> ```
> ============================================================
>   SD REALISTIC VALIDATION
> ============================================================
>   Raw:       N=61, WR=60.7%, ROI=84.0%, P/L=512.26, MaxDD=77.38
>   Realistic: N=61, WR=60.7%, ROI=80.4%, P/L=490.45, MaxDD=31.73
>   Delta:     N=0, WR=0.0pp, ROI=-3.6pp, P/L=-21.81
>   Slippage:  2% | Odds: [1.05, 10.0] | Dedup: True
>   Quality Gates (PASS):
>     [PASS] min_n: 61 (required: 37)
>     [PASS] min_roi: 80.4 (required: 10.0)
>     [PASS] ic95_low: 48.1 (required: 40.0)
>     [PASS] train_roi_positive: 87.7 (required: > 0)
>     [PASS] test_roi_positive: 64.3 (required: > 0)
> ============================================================
> ```

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Market overlap |
|---------------------|--------------|----------------|
| H58 (Draw 1-1 Late) | 0% | 0% (different scores: 2-2 vs 1-1) |
| H62 (Draw Equalizer) | 39.3% of H68 match-level | SAME market but H62 is more selective |
| H77 (CS 1-1) | 0% | 0% (different markets and scores) |

**H68 is fully independent from H58** -- they trigger on mutually exclusive score conditions (2-2 vs 1-1). Together they extend the "Draw late" portfolio to a second scoreline.

## FT Outcomes
| Final Score | N | |
|-------------|---|---|
| 2-2 (Draw - WON) | 34 | 55.7% |
| 3-2 | 10 | 16.4% |
| 2-3 | 7 | 11.5% |
| 3-3 (Draw - WON) | 3 | 4.9% |
| Other | 7 | 11.5% |

## Config Recomendado (cartera_config.json)
```json
{
  "draw_22": {
    "enabled": true,
    "minuteMin": 70,
    "minuteMax": 90,
    "oddsMax": 8.0
  }
}
```

## Notas de Implementacion
- **Backtest function**: `_detect_draw_22_trigger(rows, curr_idx, cfg)`
- **Key logic**: Simply check score is 2-2 and minute is in range. Very simple trigger.
- **Columnas CSV requeridas**: back_draw, goles_local, goles_visitante, minuto (all Tier 1)
- **Manejo de nulls**: Skip row if any required column is null
- **Complementary to H58**: Forms a "Draw portfolio" with H58 (1-1) covering the two most common drawn scorelines
