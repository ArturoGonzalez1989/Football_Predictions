# Nueva Estrategia: BACK Under 3.5 Three-Goal Lid (H66)

## Concepto
When a match has exactly 3 goals at minute 65-80 and the combined xG is below 2.5, the 3rd goal was likely an "overperformance" relative to expected quality. The market overestimates the probability of a 4th goal because it anchors on the current goal count (3), not on the underlying quality of chances (xG < 2.5). BACK Under 3.5 exploits this systematic overestimation.

## Edge Thesis
The market has a known recency bias -- after 3 goals, it assumes the match is "high-scoring" and adjusts Over/Under odds accordingly. But when xG is significantly below the actual goal count, the 3 goals were largely due to finishing efficiency or luck (e.g., deflections, penalties, mistakes). Statistical regression to the mean makes a 4th goal less likely than the market prices in. The xG filter removes genuinely high-activity matches where 4+ goals are expected.

## Trigger Conditions
- **Minuto**: [65, 80]
- **Marcador**: Total goals = 3 (any combination: 3-0, 2-1, 1-2, 0-3)
- **Stats**: xG_local + xG_visitante < 2.5 (xG data must be non-null)
- **Cuota**: back_under35, must be > 1.01 and <= 10.0

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Under 3.5 Goals
- **Win condition**: FT total goals <= 3 (no more goals scored)

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Recommended Config: min=65-80, xG_max=2.5

### Dataset Completo (N=84)
| Metrica | Valor |
|---------|-------|
| N | 84 |
| Win Rate | 67.9% |
| IC95% | [57.3%, 76.9%] |
| ROI | +26.2% |
| P/L total | +220.28 (stake=10) |
| Avg Odds | 1.93 |
| Max Drawdown | 54.50 |
| Sharpe Ratio | 2.33 |
| Ligas | 29 |

### Train Set (70%, N=58)
| Metrica | Valor |
|---------|-------|
| WR | ~67% |
| ROI | +11.9% |

### Test Set (30%, N=26)
| Metrica | Valor |
|---------|-------|
| WR | ~69% |
| ROI | +58.3% |

### Alternative Configs (all pass gates)
| Config | N | WR | ROI | Sharpe |
|--------|---|----|----|--------|
| min=65-80, xG<3.0 | 95 | 64.2% | +20.9% | 1.93 |
| min=65-80, xG<3.5 | 101 | 62.4% | +19.5% | 1.82 |
| min=65-80, no xG filter | 215 | 56.7% | +9.8% | 1.27 |
| min=70-80, xG<2.5 | 77 | 71.4% | +23.3% | 2.33 |
| min=70-82, xG<2.5 | 80 | 72.5% | +22.5% | 2.34 |
| min=68-85, xG<2.5 | 91 | 70.3% | +19.9% | 2.08 |

Robustness: ROI is positive across ALL 48 tested configs. Even without xG filter (N=215), ROI is +9.8%. The xG filter improves edge significantly (from ~10% to ~26% ROI) without over-restricting sample size.

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (84) |
| N_test >= 18 | PASS (26) |
| ROI train+test > 0% | PASS (+11.9%/+58.3%) |
| IC95% lo > 40% | PASS (57.3%) |
| Max DD < 400 | PASS (54.50) |
| Overlap < 30% | PASS (0% -- unique market Under 3.5) |
| >= 3 ligas | PASS (29) |
| Concentracion < 50% | PASS (47.6%) |

## Market Efficiency Check
- Won bets avg odds: 1.91
- Lost bets avg odds: 2.00
- Won odds are LOWER than lost odds -- consistent with a genuine edge where market slightly underprices the "hold" probability.

## Overlap con Estrategias Existentes
| Estrategia existente | Market overlap |
|---------------------|--------------|
| H46 (BACK U2.5 One-Goal) | 0% (different score condition: 1 goal vs 3 goals) |
| H48 (LAY U2.5 Tied 1-1) | 0% (different score, different market direction) |
| H39 (BACK O2.5 Two Goals) | 0% (opposite market direction: Over vs Under) |
| LAY O2.5 Scoreless (H41) | 0% (different score condition) |
| All other strategies | 0% (Under 3.5 market not used by any existing strategy) |

## Config Recomendado (cartera_config.json)
```json
{
  "back_under35_lid": {
    "enabled": true,
    "minuteMin": 65,
    "minuteMax": 80,
    "xgTotalMax": 2.5,
    "totalGoals": 3,
    "oddsMax": 10.0
  }
}
```

## Notas de Implementacion
- **Columnas CSV requeridas**: minuto, goles_local, goles_visitante, xg_local, xg_visitante, back_under35
- **Manejo de nulls**: xG columns are Tier 1 (< 5% null rate). Rows with null xG are skipped.
- **Superset gate**: Backend generates bets for all matches with 3 goals at min 60-90. Frontend filters by exact minute range and xG threshold.
- **Risk level**: sin_riesgo (low avg odds ~1.93, high WR ~68%)
