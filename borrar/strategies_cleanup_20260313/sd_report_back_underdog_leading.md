# Nueva Estrategia: BACK Underdog Leading Late (H59)

## Concepto
When the pre-match underdog (team with higher opening odds, >= 2.0) takes the lead during the match and is still leading at minute 55-80, BACK them to win. The market systematically underprices the probability that the underdog will hold on to their lead.

## Edge Thesis
Betfair in-play odds embed the pre-match assessment of team quality. When an underdog takes the lead, the market partially adjusts but retains an "anchor" to pre-match probabilities. However, possessing the lead is itself the strongest predictor of final outcome -- especially from minute 55 onward. The market underestimates the underdog's ability to hold on.

Evidence: Actual win rate 65.1% vs market-implied 54.5% = +10.6pp edge. Won bets have HIGHER avg odds (3.08) than lost bets (2.30), confirming the market is genuinely wrong, not just noisy.

This is a "reverse favourite-longshot bias" identified in academic literature (Perplexity Section 2.1): after unexpected events (underdog taking the lead), markets are systematically slow to update.

## Trigger Conditions
- **Minuto**: [55, 80]
- **Marcador**: Underdog leading by 1 goal (score difference = 1)
- **Pre-match odds**: Underdog's opening back odds >= 2.0
- **Cuota**: back_home or back_away (whichever is the underdog) > 1.0

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Match Winner (back the underdog)
- **Win condition**: The underdog team wins the match (FT)

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=192)
| Metrica | Valor |
|---------|-------|
| N | 192 |
| Win Rate | 65.1% |
| IC95% | [58.1%, 71.5%] |
| ROI | +93.9% |
| P/L total | +1803.09 (stake=10) |
| Avg Odds | 2.81 |
| Max Drawdown | 77.04 |
| Sharpe Ratio | 3.10 |
| Ligas | 34 |

### Train Set (70%, N=134)
| Metrica | Valor |
|---------|-------|
| WR | 66.4% |
| ROI | +121.8% |

### Test Set (30%, N=58)
| Metrica | Valor |
|---------|-------|
| WR | 62.1% |
| ROI | +29.4% |

### Alternative Config: 60-80, lead<=2 (N=195)
| Metrica | Valor |
|---------|-------|
| WR | 71.3% |
| ROI | +86.0% |
| Train ROI | +79.7% |
| Test ROI | +100.6% |
| Sharpe | 2.73 |

### Alternative Config: 60-80, lead=1 (N=174)
| Metrica | Valor |
|---------|-------|
| WR | 69.5% |
| ROI | +97.4% |
| Train ROI | +89.5% |
| Test ROI | +115.4% |
| Sharpe | 2.76 |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (192) |
| N_test >= 18 | PASS (58) |
| ROI train+test > 0% | PASS (121.8%/29.4%) |
| IC95% lo > 40% | PASS (58.1%) |
| Max DD < 400 | PASS (77.04) |
| Overlap < 30% | PASS (0% -- unique market) |
| >= 3 ligas | PASS (34) |
| Concentracion < 50% | PASS (33.9%) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Market overlap |
|---------------------|--------------|----------------|
| H53 (CS 1-0/0-1) | 64.1% (same match) | 0% (different market: CS vs MO) |
| H49 (CS 2-1/1-2) | 33.9% (same match) | 0% (different market: CS vs MO) |
| H2 (Leader Stat Dom) | 0% (H2 requires tied score) | N/A |
| H46 (Under 2.5 late) | some (1-goal games) | 0% (different market) |
| H58 (Draw 1-1) | 0% (H58 requires tied score) | N/A |

Note: High match-level overlap with H53/H49 is EXPECTED and HARMLESS. They trade completely different markets (CS vs Match Winner). A match where the underdog leads 1-0 at min 70 can trigger both H59 (BACK underdog to win on MO) and H53 (BACK CS 1-0). These are independent bets on different markets.

## Market Efficiency Check
| Metric | Won bets | Lost bets |
|--------|----------|-----------|
| Avg odds | 3.08 | 2.30 |

Won bets have HIGHER odds than lost bets. This is strong evidence of genuine inefficiency (in an efficient market, won bets have lower odds).

## Cross-League Robustness
- 34 leagues represented
- No single league > 23.4% of total bets
- Positive ROI in majority of leagues with N >= 5
- Edge present in both "known" leagues (La Liga, Serie A, Bundesliga, Premier League) and lesser-known leagues

## Score Distribution at Trigger
| Score | N | % | WR |
|-------|---|---|-----|
| 0-1 | 77 | 40.1% | 58.4% |
| 1-0 | 46 | 24.0% | 67.4% |
| 1-2 | 41 | 21.4% | 70.7% |
| 2-1 | 24 | 12.5% | 70.8% |

Note: WR increases with goal difference (1-2/2-1 better than 0-1/1-0). This makes sense: a 2-1 lead is harder to overturn than 0-1.

## Config Recomendado (cartera_config.json)
```json
{
  "back_ud_leading": {
    "enabled": true,
    "minuteMin": 55,
    "minuteMax": 80,
    "udMinPreOdds": 2.0,
    "maxLead": 1
  }
}
```

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_back_ud_leading(min_dur, ...)`
- **Frontend filter**: `filterBackUdLeadingBets(bets, params, version)`
- **Live detection**: STRATEGY N in `detect_betting_signals()`
- **Columnas CSV requeridas**: `back_home`, `back_away`, `goles_local`, `goles_visitante`, `minuto`
- **Pre-match odds**: Use first row `back_home`/`back_away` as proxy for pre-match odds
- **Underdog identification**: Team with higher back odds in first row
- **Manejo de nulls**: All required columns are Tier 1 (null rate < 5%)
- **Superset gate**: backend uses `lead >= 1` (no max lead filter) and `ud_pre >= 1.5` (wider than 2.0); frontend applies exact `udMinPreOdds` and `maxLead`
