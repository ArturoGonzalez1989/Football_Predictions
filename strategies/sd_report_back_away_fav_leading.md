# Nueva Estrategia: BACK Away Favourite Leading Late (H67)

## Concepto
When the away team is the pre-match favourite (lower odds) and is currently leading at minute 60-88, BACK them to win. The market systematically overestimates the home team's comeback probability due to "home advantage bias" -- the persistent belief that home teams rally. In reality, when the away favourite is already leading, they hold the lead 85%+ of the time. The market gives average odds of 1.50, implying only ~67% win probability -- an 18+ percentage point edge.

## Edge Thesis
Three biases compound to create this edge:
1. **Home advantage anchor**: Market participants overweight the home team's ability to come back, even when the away team is objectively stronger AND already winning.
2. **Favourite-longshot bias inversion**: The favourite is already leading, so bookmakers should price them very low (1.10-1.30). Instead, in-play odds stay at 1.40-1.60 because market participants irrationally believe comebacks are more common than they are.
3. **Confirmation bias**: Memorable comebacks (e.g., Liverpool-Barcelona 4-0) are salient in bettors' minds, inflating perceived comeback probability.

This strategy complements H59 (BACK Underdog Leading Late) by covering the OTHER half of "leader wins" situations -- where the favourite is leading away from home. Together, H59 and H67 cover all "leading team wins" scenarios with different edge sources.

## Trigger Conditions
- **Minuto**: [60, 88]
- **Marcador**: Away team leading (goles_visitante > goles_local)
- **Lead margin**: 1-3 goals (lead = gv - gl, 1 <= lead <= 3)
- **Pre-match**: Away team is favourite (back_away at min 1-5 <= back_home at min 1-5)
- **Cuota**: back_away at trigger minute, must be > 1.01 and <= 10.0

## Mercado y Direccion
- **Tipo**: BACK
- **Mercado**: Match Winner (Away)
- **Win condition**: Away team wins (FT goles_visitante > FT goles_local)

## P/L Formula
- **Win**: stake * (odds - 1) * 0.95
- **Loss**: -stake
- **Comision Betfair**: 5%

## Resultados del Backtest

### Recommended Config: min=60-88, lead<=3, odds<=10

### Dataset Completo (N=121)
| Metrica | Valor |
|---------|-------|
| N | 121 |
| Win Rate | 85.1% |
| IC95% | [77.7%, 90.3%] |
| ROI | +23.9% |
| P/L total | +289.39 (stake=10) |
| Avg Odds | 1.50 |
| Max Drawdown | 46.26 |
| Sharpe Ratio | 2.71 |
| Ligas | 29 |

### Train Set (70%, N=84)
| Metrica | Valor |
|---------|-------|
| WR | ~84% |
| ROI | +16.4% |

### Test Set (30%, N=37)
| Metrica | Valor |
|---------|-------|
| WR | ~86% |
| ROI | +41.1% |

### Alternative Configs (all pass gates)
| Config | N | WR | ROI | Sharpe |
|--------|---|----|----|--------|
| min=60-85, lead<=3, odds<=10 | 120 | 85.0% | +24.0% | 2.70 |
| min=65-88, lead<=3, odds<=10 | 110 | 84.5% | +26.2% | 2.68 |
| min=65-85, lead<=3, odds<=10 | 109 | 84.4% | +26.4% | 2.66 |
| min=60-88, lead<=2, odds<=10 | 119 | 84.9% | +21.3% | 2.43 |
| min=60-88, lead<=1, odds<=10 | 99 | 81.8% | +23.6% | 2.25 |
| min=70-85, lead<=3, odds<=10 | 106 | 85.8% | +19.5% | 2.42 |

Robustness: ALL 60 tested configs pass gates. WR stays 81-86% across all minute ranges. ROI is positive across every config tested.

## Quality Gates
| Gate | Resultado |
|------|-----------|
| N >= 60 | PASS (121) |
| N_test >= 18 | PASS (37) |
| ROI train+test > 0% | PASS (+16.4%/+41.1%) |
| IC95% lo > 40% | PASS (77.7%) |
| Max DD < 400 | PASS (46.26) |
| Overlap < 30% | PASS (0% -- different market condition from H59) |
| >= 3 ligas | PASS (29) |
| Concentracion < 50% | PASS (<30%) |

## Market Efficiency Check
- Won bets avg odds: 1.48
- Lost bets avg odds: 1.62
- Won odds lower than lost odds, but the gap is smaller than efficient pricing would require. The key insight: actual hold rate is 85% but market implies only ~67% (1/1.50). This 18pp gap is the edge.

## Overlap Analysis
### vs H59 (BACK Underdog Leading Late)
- H59 triggers when UNDERDOG is leading (higher pre-match odds team)
- H67 triggers when AWAY FAVOURITE is leading (lower pre-match odds team)
- These are MUTUALLY EXCLUSIVE by definition: H59 requires the leader to be the underdog, H67 requires the leader to be the away favourite
- Match overlap: 0% (no match can trigger both)
- Combined with H59, these two strategies cover ALL "leader late" scenarios

### vs Other Strategies
| Estrategia existente | Overlap |
|---------------------|---------|
| H59 (BACK Underdog Leading) | 0% (mutually exclusive: away fav vs underdog) |
| H2 (BACK Leader Stat Dom) | ~15% match overlap but different conditions (H2 requires SoT>=4/<=1) |
| All Over/Under strategies | 0% (different market) |
| All CS strategies | 0% (different market) |
| All Draw strategies | 0% (different market) |

## Config Recomendado (cartera_config.json)
```json
{
  "back_away_fav_leading": {
    "enabled": true,
    "minuteMin": 60,
    "minuteMax": 88,
    "maxLead": 3,
    "oddsMax": 10.0,
    "requireAwayFav": true
  }
}
```

## Notas de Implementacion
- **Columnas CSV requeridas**: minuto, goles_local, goles_visitante, back_home, back_away
- **Pre-match odds detection**: Use first 5 rows to capture early back_home and back_away. If early odds unavailable, skip the match.
- **All Tier 1 columns**: Zero data availability risk
- **Manejo de nulls**: Only skip if early odds are unavailable (rare, <2% of matches)
- **Superset gate**: Backend generates bets for all matches where away team leads at min 55-90. Frontend filters by pre-match favourite status, exact minute range, lead margin, odds cap.
- **Risk level**: sin_riesgo (WR 85%, avg odds 1.50, low max DD)
- **Note on H59 integration**: If H59 (BACK Underdog Leading) is also active, ensure no overlap. H59 covers underdogs (higher pre-match odds), H67 covers away favourites (lower pre-match odds). Together they form a comprehensive "leader wins" portfolio.
