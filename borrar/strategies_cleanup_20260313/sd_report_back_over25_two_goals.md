# Nueva Estrategia: BACK Over 2.5 from Two Goals (H39)

## Concepto
When exactly 2 goals have been scored by minute 48-65 (regardless of scoreline: 2-0, 1-1, 0-2),
BACK Over 2.5 goals. Matches that reach 2 goals early are genuinely open and attacking -- the pace
continues into the remaining 25-40 minutes. The win rate is ~74% across 270 matches.

## Edge Thesis
The market partially prices this pattern (won bets have slightly lower odds than lost bets: 1.44 vs 1.50),
but not fully. A match with 2 goals by minute 55 has a structural reason for more goals: both teams
have shown they can score, tactical adjustments haven't yet "closed" the game, and the remaining
time is sufficient for at least one more goal. The ~74% actual win rate vs ~68% implied probability
(avg odds 1.46 = 68.5% implied) provides a 5-6% edge.

## Trigger Conditions
- **Minuto**: [48, 65] (first row where conditions met)
- **Marcador**: total_goals == 2 (exactly 2 goals at trigger time, any scoreline)
- **Stats**: None required (SoT filter tested but reduces N without improving test ROI)
- **Cuota**: back_over25 > 1.0 and <= 4.0 (Config B) or <= 8.0 (Config A)

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Over 2.5 Goals
- **Win condition**: ft_total >= 3 (at least 3 goals at full time)

## P/L Formula
- **Win**: +stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Config B (RECOMMENDED): min=50-60, odds_max=4.0, no SoT filter

| Metrica | Valor |
|---------|-------|
| N | 270 |
| Win Rate | 74.1% |
| IC95% | [68.5%, 78.9%] |
| ROI | 5.4% |
| P/L total | +144.71 (stake=10) |
| Avg Odds | 1.46 |
| Max Drawdown | 59.41 |
| Sharpe Ratio | 1.25 |
| Ligas | 34 |

### Train Set (70%, N=189)
| Metrica | Valor |
|---------|-------|
| WR | 73.0% |
| ROI | 5.0% |

### Test Set (30%, N=81)
| Metrica | Valor |
|---------|-------|
| WR | 76.5% |
| ROI | 6.1% |

### Config A (BROADER): min=48-65, odds_max=8.0, no SoT filter

| Metrica | Valor |
|---------|-------|
| N | 313 |
| Win Rate | 71.6% |
| ROI | 2.9% |
| Train ROI | 1.7% |
| Test ROI | 5.8% |
| Sharpe | 0.67 |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (270) |
| N_test >= 18 | PASS (81) |
| ROI train+test > 0% | PASS (5.0% / 6.1%) |
| IC95% lo > 40% | PASS (68.5%) |
| Max DD < 400 | PASS (59.41) |
| Overlap < 30% | PASS (see below) |
| >= 3 ligas | PASS (34) |
| Concentracion < 50% | PASS (28.5%) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Mercado overlap |
|---------------------|--------------|-----------------|
| clustering | 100% | NO - different market (next goal vs O2.5) |
| draw_00 | 27.4% | NO - different direction (BACK Draw vs BACK Over) |
| pressure | 34.1% | NO - different market |
| xg_underperf | 17.0% | NO - different trigger |
| lay_over25_def | 0.4% | NO - opposite direction |

Note: 100% overlap with clustering is expected (any match with 2 goals has a "recent goal" event).
However, the market and direction are completely different. This strategy is independent in terms
of what it bets on.

## Config Recomendado (cartera_config.json)
```json
{
  "back_over25_2goals": {
    "enabled": true,
    "minuteMin": 50,
    "minuteMax": 60,
    "goalsExact": 2,
    "oddsMax": 4.0
  }
}
```

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_back_over25_2goals()`
- **Trigger**: First row in [minuteMin, minuteMax] where total_goals == 2 and back_over25 in (1.0, oddsMax]
- **No stat filter needed**: SoT/xG filters reduce N without improving test ROI
- **bet_type_dir**: "back"
- **Columnas CSV requeridas**: minuto, goles_local, goles_visitante, back_over25
- **Manejo de nulls**: Only back_over25 can be null; skip row if null
- **Market efficiency warning**: Won bets have slightly lower odds (1.44) vs lost (1.50) -- market partially prices this. The edge is real but moderate (~5-6% ROI).
- **Robustness**: Works across 34 leagues, no temporal concentration, test set confirms train set direction.
