# Strategy Designer -- Round 11 Summary
Date: 2026-03-06
Dataset: 871 matches (2026-02-10 to 2026-03-06)

## Overview
- Hypotheses tested: 4 (H66-H69)
- Approved: 2 (H66, H67)
- Monitoring: 2 (H68, H69)
- Descartadas: 0

## Approved Strategies (ranked by Sharpe)

### 1. H67 -- BACK Away Favourite Leading Late
| Metrica | Valor |
|---------|-------|
| Market | Match Winner (Away) |
| Config | min=60-88, lead<=3, odds<=10, away_fav=true |
| N | 121 |
| WR | 85.1% |
| ROI | +23.9% |
| Sharpe | 2.71 |
| Train/Test ROI | +16.4% / +41.1% |
| MaxDD | 46.26 |
| Ligas | 29 |
| Edge source | Home advantage comeback bias |
| Report | strategies/sd_report_back_away_fav_leading.md |

**Why it works**: The market anchors on "home teams come back" narrative. When the away favourite (objectively stronger team) is already winning at minute 60+, the actual hold rate is 85% vs market-implied 67%. This 18pp gap generates consistent profits across 29 leagues.

**Relationship with H59**: Mutually exclusive complement. H59 covers underdogs leading, H67 covers away favourites leading. Together they form a comprehensive "leader portfolio" with N~310+ and zero overlap.

### 2. H66 -- BACK Under 3.5 Three-Goal Lid
| Metrica | Valor |
|---------|-------|
| Market | Under 3.5 Goals |
| Config | min=65-80, xG_total<2.5, 3 goals scored |
| N | 84 |
| WR | 67.9% |
| ROI | +26.2% |
| Sharpe | 2.33 |
| Train/Test ROI | +11.9% / +58.3% |
| MaxDD | 54.50 |
| Ligas | 29 |
| Edge source | Goal count vs xG divergence |
| Report | strategies/sd_report_back_under35_three_goals.md |

**Why it works**: When 3 goals are scored but xG < 2.5, the goals represent "overperformance" (finishing luck, set pieces, errors). The market sees 3 goals and raises Over probability, but statistical regression makes a 4th goal unlikely. The xG filter is the key insight -- it separates lucky-3-goal games from genuinely high-activity ones.

## Monitoring

### H68 -- BACK Draw at 2-2 Late
- N=44, WR=54.5%, ROI=+28.4%, edge=+10.5pp
- Extends H58 (Draw 1-1) to 2-2 draws. Different tactical dynamic but similar market bias
- Needs N>=60 (est. at ~1200 matches in dataset)

### H69 -- BACK Under 0.5 Late Scoreless
- N=78, WR=61.5%, ROI=+13.1%, Sharpe=0.78
- Edge exists (+12pp at min 80) but low risk-adjusted return
- Conceptual overlap with H44 (LAY O1.5 Scoreless)
- Low priority for approval

## Key Data Insights (PASO 1)

1. **Dataset growth**: 871 matches (up from ~850). Date range 2026-02-10 to 2026-03-06.
2. **Avg goals**: 2.49 per match. Goal distribution: 0 (9.5%), 1 (20.4%), 2 (22.2%), 3 (24.1%), 4+ (23.7%).
3. **Comeback reality**: Leader at 70' holds 85.6%. Trailing team draws 12.2%, wins 2.1%.
4. **Draw frequency**: 27.3% of matches end in draws. 1-1 is most common (43.7% of draws).
5. **Second half**: 77.3% of matches have 1+ 2H goals. Average 1.6 goals in 2H.
6. **Pre-match favourite WR**: Strong fav (<1.5): 72.1%. Mild fav (1.5-2.0): 58.5%.

## Market Coverage After R11

Total unique approved strategies by market (including monitoring):

| Market | Strategies | Status |
|--------|-----------|--------|
| BACK Over 2.5 | 7 | SATURATED |
| BACK Under 2.5 | 2 | Active |
| **BACK Under 3.5** | **H66** | **NEW R11** |
| BACK Under 1.5 | 0 (H47 redundant with H44) | N/A |
| LAY Over 2.5 | 1 | Active |
| LAY Over 1.5 | 1 | Active |
| LAY Under 2.5 | 1 | Active |
| BACK CS 2-1/1-2 | 1 | Active |
| BACK CS 1-0/0-1 | 1 | Active |
| BACK CS 3-0/0-3 | 1 | Monitoring |
| BACK Draw 1-1 | 1 | Active |
| BACK Draw 2-2 | 1 (H68) | Monitoring |
| BACK MO (underdog) | 1 (H59) | Active |
| **BACK MO (away fav)** | **H67** | **NEW R11** |
| BACK MO (leader) | 2 | Active |
| BACK Under 0.5 | 1 (H69) | Monitoring |

## Next Steps

1. **Integrate H66 and H67 into notebook** (strategies_designer.ipynb) following the integration process in PASO 9.
2. **H67+H59 portfolio analysis**: Since they're mutually exclusive, consider whether to implement them as separate strategies or as a single "BACK Leader Late" super-strategy with an is_underdog flag.
3. **Monitor H68 closely**: If dataset reaches 1200 matches and N>=60, H68 (Draw 2-2) should be re-evaluated -- the edge is real but sample size is insufficient.
4. **Future angles for R12**:
   - HOME favourite leading late (complement to H67 for home context) -- but likely low odds/low ROI since home favs are already priced efficiently
   - Under 4.5 with 4 goals (extension of H66 concept to higher goal counts)
   - Specific score dynamics (e.g., 3-1/1-3 at late minutes -- currently only covered by H49 for 2-1/1-2)
   - LAY Under 3.5 when 3 goals + high xG (inverse of H66)
