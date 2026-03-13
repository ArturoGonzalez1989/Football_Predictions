# Nueva Estrategia: BACK Draw After UD Equalizer Late (H62)

## Concepto
When the pre-match favourite takes the lead but the underdog equalizes at min 65-90, BACK Draw. The underdog has proven they can score against the favourite, and the favourite has lost momentum. The market still prices the favourite to regain the lead, but equalization creates a psychological shift that favours the draw.

## Edge Thesis
After equalization by the underdog, the market anchors on the pre-match favourite's quality and overestimates the probability of them scoring again. But the dynamics have changed: the underdog is defending with confidence after equalizing, and the favourite's tactical plan has failed. The draw probability is systematically underpriced by ~18pp (actual 55.9% vs implied ~38%).

## Trigger Conditions
- **Minuto**: [65, 90]
- **Marcador**: Tied (gl == gv), at least 1 goal each side
- **Pre-match favourite**: min(back_home, back_away) at first row <= 2.5
- **Equalization**: At some point before trigger, the favourite was leading (checked via score history)
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

### Dataset Completo (N=111)
| Metrica | Valor |
|---------|-------|
| N | 111 |
| Win Rate | 55.9% |
| IC95% | [46.6%, 64.7%] |
| ROI | 62.5% |
| P/L total | 693.91 (stake=10) |
| Avg Odds | 2.62 |
| Max Drawdown | 51.53 |
| Sharpe Ratio | 3.31 |
| Ligas | 38 |

### Train Set (70%, N=77)
| Metrica | Valor |
|---------|-------|
| WR | ~57% |
| ROI | 69.2% |

### Test Set (30%, N=34)
| Metrica | Valor |
|---------|-------|
| WR | ~53% |
| ROI | 47.5% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 37 | PASS (111) |
| ROI >= 10% | PASS (62.5%) |
| IC95% lo >= 40% | PASS (46.6%) |
| Train ROI > 0% | PASS (69.2%) |
| Test ROI > 0% | PASS (47.5%) |
| >= 3 ligas | PASS (38) |
| Date conc < 50% | PASS (22.5%) |

## Validacion Realista (sd_validate_realistic.py)
**Verdict: PASS**

| Metrica | Raw | Realistic | Delta |
|---------|-----|-----------|-------|
| N | 111 | 111 | 0 |
| WR% | 55.9 | 55.9 | 0pp |
| ROI% | 62.5 | 59.3 | -3.2pp |
| P/L | 693.91 | 658.05 | -35.86 |
| Train ROI | 69.2% | 65.8% | -3.4pp |
| Test ROI | 47.5% | 44.6% | -2.9pp |
| Sharpe | 3.31 | 3.20 | -0.11 |

> Output completo del validador:
> ```
> ============================================================
>   SD REALISTIC VALIDATION
> ============================================================
>   Raw:       N=111, WR=55.9%, ROI=62.5%, P/L=693.91, MaxDD=51.53
>   Realistic: N=111, WR=55.9%, ROI=59.3%, P/L=658.05, MaxDD=52.94
>   Delta:     N=0, WR=0.0pp, ROI=-3.2pp, P/L=-35.86
>   Slippage:  2% | Odds: [1.05, 10.0] | Dedup: True
>   Quality Gates (PASS):
>     [PASS] min_n: 111 (required: 37)
>     [PASS] min_roi: 59.3 (required: 10.0)
>     [PASS] ic95_low: 46.6 (required: 40.0)
>     [PASS] train_roi_positive: 65.8 (required: > 0)
>     [PASS] test_roi_positive: 44.6 (required: > 0)
> ============================================================
> ```

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Market overlap |
|---------------------|--------------|----------------|
| H58 (Draw 1-1 Late) | 89.2% of H62's 1-1 bets | SAME (BACK Draw) |
| H68 (Draw 2-2 Late) | 39.3% of H62's 2-2 bets | SAME (BACK Draw) |

**IMPORTANT**: H62 overlaps significantly with H58 at the match level (74/83 bets at 1-1 also trigger H58). However:
1. H62 is a higher-quality SELECTION (ROI 63% vs H58's 31%) due to the equalizer filter
2. The dedup system ensures only 1 bet per match per market
3. 37 bets (33%) are genuinely unique (2-2 and 3-3 equalizations + 9 bets at 1-1 outside H58 minute range)
4. The unique portion has ROI=57.6% -- still very strong

## Score Distribution at Trigger
| Score | N | % |
|-------|---|---|
| 1-1 | 83 | 74.8% |
| 2-2 | 26 | 23.4% |
| 3-3 | 2 | 1.8% |

## Config Recomendado (cartera_config.json)
```json
{
  "draw_equalizer": {
    "enabled": true,
    "minuteMin": 65,
    "minuteMax": 90,
    "favPreMax": 2.5,
    "minGoalsEach": 1,
    "oddsMax": 8.0
  }
}
```

## Notas de Implementacion
- **Backtest function**: `_detect_draw_equalizer_trigger(rows, curr_idx, cfg)`
- **Key logic**: Must scan score history to detect if favourite was ever leading, then underdog equalized
- **Columnas CSV requeridas**: back_home, back_away, back_draw, goles_local, goles_visitante, minuto (all Tier 1)
- **Manejo de nulls**: Skip row if any of the 4 goal/odds columns are null
- **Dedup priority**: When both H62 and H58 trigger on same match, H62 should take priority (higher ROI filter)
