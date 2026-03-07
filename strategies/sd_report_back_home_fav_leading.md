# Nueva Estrategia: BACK Home Favourite Leading Late (H70)

## Concepto
When the home team was the pre-match favourite (odds < 2.50 at kickoff) and is leading at minute 65-85, back them to win. The market systematically overestimates the probability of the trailing team mounting a comeback, particularly when the leading team has home advantage AND was the pre-match quality assessment favourite.

## Edge Thesis
The market overreacts to the "remaining time" factor and underweights two compounding advantages: (1) home advantage in defending a lead, and (2) pre-match quality superiority confirmed by the lead itself. When a home favourite leads, they have both tactical (defending at home with crowd) and quality (better team) advantages. The market still prices ~14pp too much comeback probability, likely anchored on generic "anything can happen" sentiment.

This is mutually exclusive with H67 (away favourite leading) and H59 (underdog leading). Together, these three strategies cover nearly ALL "leader late" scenarios from different angles.

## Trigger Conditions
- **Minuto**: [65, 85]
- **Marcador**: Home team leading (gl > gv), lead 1-3 goals
- **Stats**: Home team was favourite at kickoff (back_home at row[0] < back_away at row[0], and back_home at row[0] <= 2.50)
- **Cuota**: back_home in-play, must be >= 1.05 and <= 10.0

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Match Odds (Home Win)
- **Win condition**: Home team wins (ft_local > ft_visitante)

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Dataset Completo (N=225)
| Metrica | Valor |
|---------|-------|
| N | 225 |
| Win Rate | 85.8% |
| IC95% | [80.6%, 89.7%] |
| ROI (raw) | 33.6% |
| ROI (realistic) | 31.1% |
| P/L total (realistic) | 699.13 (stake=10) |
| Avg Odds | 1.59 |
| Max Drawdown | 33.41 |
| Sharpe Ratio | 4.43 (realistic) |
| Ligas | 32 |

### Train Set (70%, N=158)
| Metrica | Valor |
|---------|-------|
| WR | ~86% |
| ROI | 30.9% |

### Test Set (30%, N=67)
| Metrica | Valor |
|---------|-------|
| WR | ~86% |
| ROI | 31.4% |

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 35 | PASS (225) |
| ROI >= 10% (realistic) | PASS (31.1%) |
| IC95% lo >= 40% | PASS (80.6%) |
| Train ROI > 0% | PASS (30.9%) |
| Test ROI > 0% | PASS (31.4%) |
| Overlap < 30% (same market) | PASS (0% vs H67, 2.2% vs H59) |
| >= 3 ligas | PASS (32) |

## Overlap con Estrategias Existentes
| Estrategia existente | Match overlap | Market overlap |
|---------------------|--------------|----------------|
| H67 (Away Fav Leading) | 0.0% | MUTUALLY EXCLUSIVE |
| H59 (Underdog Leading) | 2.2% | Near-exclusive (5 edge cases) |
| H53 (CS 1-0/0-1) | 49.8% | Different market (MO vs CS) |
| H46 (Under 2.5) | 45.8% | Different market (MO vs U2.5) |
| H49 (CS 2-1/1-2) | 36.4% | Different market (MO vs CS) |
| H66 (Under 3.5) | 15.6% | Different market (MO vs U3.5) |
| H58 (Draw 1-1) | 12.9% | Different market (MO vs Draw) |

## Realistic Validation
- Slippage 2%: ROI drops from 33.6% to 31.1% (-2.5pp)
- Dedup: No change (already 1 bet per match)
- Odds filter [1.05, 10.0]: No change
- **Verdict: PASS** -- all quality gates met with realistic adjustments

## Config Recomendado (cartera_config.json)
```json
{
  "home_fav_leading": {
    "enabled": true,
    "minuteMin": 65,
    "minuteMax": 85,
    "maxLead": 3,
    "favMaxOdds": 2.5
  }
}
```

## Notas de Implementacion
- **Backtest function**: `analyze_strategy_home_fav_leading(min_dur, ...)`
- **Frontend filter**: `filterHomeFavLeadingBets(bets, params, version)`
- **Columnas CSV requeridas**: `back_home` (row 0 + in-play), `back_away` (row 0), `goles_local`, `goles_visitante`, `minuto`
- **Manejo de nulls**: All Tier 1 columns. back_home/back_away at row 0 should always be available.
- **Leader portfolio**: H70 + H67 + H59 = complete "leader late" coverage. Home fav (H70), away fav (H67), underdog (H59) -- mutually exclusive by construction.
- **Robustness**: Train ROI (30.9%) and test ROI (31.4%) are nearly identical, indicating extremely stable edge with no temporal decay.
