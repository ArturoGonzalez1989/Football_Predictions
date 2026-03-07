# R12 Strategy Research Summary
Date: 2026-03-07
Dataset: 896 matches (up from 871 in R11)

## Overview
- **Hypotheses tested**: 7 (H70-H76)
- **Approved**: 2 (H70, H71)
- **Discarded**: 5 (H72, H73, H74, H75, H76)
- **Realistic validation applied**: Yes (slippage 2%, dedup, odds [1.05-10.0])

## Approved Strategies

### 1. H70 -- BACK Home Favourite Leading Late (STAR)
- **Market**: Match Odds (Home Win)
- **Trigger**: Home team was pre-match favourite (odds < 2.50), leading at min 65-85
- **N**: 225 | **WR**: 85.8% | **ROI (realistic)**: 31.1% | **Sharpe**: 4.43
- **Train/Test ROI**: 30.9% / 31.4% (virtually identical -- very robust)
- **Edge**: +23pp (85.8% actual vs ~63% market-implied)
- **Leagues**: 32
- **Overlap**: 0% with H67 and H59 (mutually exclusive by design)
- **Report**: `strategies/sd_report_back_home_fav_leading.md`
- **Significance**: Completes the "leader portfolio" (H70+H67+H59), covering ALL leader-late scenarios with combined N=540+

### 2. H71 -- BACK Under 4.5 Three Goals Low xG
- **Market**: Under 4.5 Goals
- **Trigger**: 3 goals scored, combined xG < 2.0, min 65-85
- **N**: 60 | **WR**: 96.7% | **ROI (realistic)**: 11.9% | **Sharpe**: 3.99
- **Train/Test ROI**: 12.0% / 11.6% (stable)
- **Edge**: +12pp (96.7% actual vs ~84% market-implied)
- **Leagues**: 25
- **Overlap**: 95% match overlap with H66 (same trigger, different market U4.5 vs U3.5)
- **Report**: `strategies/sd_report_back_under45_three_goals.md`
- **Caveat**: Marginal ROI (11.9%), close to 10% threshold. Ultra-conservative (2 losses in 60 bets).

## Discarded Strategies

| H# | Name | Reason |
|----|------|--------|
| H72 | BACK Over 0.5 at 0-0 HT | Test ROI negative across all 20 configs. Market adjusts post-HT. |
| H73 | BACK CS 3-1/1-3 Late | N=37, insufficient sample. In monitoring if needed. |
| H74 | BACK Draw 0-0 Mid-Game | Sharpe < 1.0 across 76 configs. Market prices 0-0 draws correctly. |
| H75 | BACK CS 0-0 Very Late v2 | Negative ROI all configs. Reconfirms H56. |
| H76 | BACK Home Fav 2+ Early | Test ROI collapses (2.6%). Subsumed by H70. |

## Key Insights

1. **Leader portfolio is now complete**: H70 (home fav) + H67 (away fav) + H59 (underdog) covers all leader-late scenarios. Combined N=540+, all mutually exclusive. This is the strongest systematic edge discovered across 76 hypotheses and 12 rounds.

2. **Home favourite leading has the highest edge of any strategy**: +23pp (85.8% vs 63% implied). The market dramatically overestimates comeback probability when facing a home favourite defending a lead.

3. **Under markets continue to show inefficiency**: H71 confirms that Under markets at specific goal counts with xG filters have persistent edge. The xG filter is crucial -- it separates "lucky" high-scoring games from genuinely high-activity ones.

4. **0-0 markets are efficient**: H72, H74, H75 all confirm that the market prices 0-0 games correctly. No more investment in this area.

## Next Steps
- Integrate H70 into production pipeline (highest priority -- N=225, Sharpe=4.43)
- Integrate H71 as complementary to H66 (same trigger, different Under market)
- Monitor H73 (CS 3-1/1-3) for when N reaches 60+
- Continue monitoring H68 (Draw 2-2), H62 (Draw after UD equalizer), H65 (CS 3-0/0-3)
- Next round: H77+. Focus on remaining unexplored angles (few left):
  - Score-specific Under markets (Under 2.5 at 2-0 with xG filter?)
  - Time-decay patterns (odds movement speed as signal?)
  - Combined trigger strategies (multiple conditions from different approved strategies)
