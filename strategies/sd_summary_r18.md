# R18 Summary -- Gemini Batch 2 Hypotheses (H96-H101)

**Date:** 2026-03-13
**Dataset:** 954 finished matches (1228 CSVs)
**Quality gate N >= 38** (954 // 25 = 38)

## Executive Summary

All 6 hypotheses proposed by external Gemini analysis fail. None reach the backtest stage with viable parameters. The primary failure modes are:

1. **Insufficient scenario frequency** (H96, H97, H100): The proposed conditions are too restrictive, yielding N << 38.
2. **Missing data columns** (H98, H99): Key columns (back_over55, back_rc_4_1/1_4) are either near-empty or nonexistent.
3. **Market correctly priced** (H101): Full grid search confirms no edge.

## Results Per Hypothesis

| H# | Name | Market | Disposition | Key Metric |
|----|------|--------|-------------|------------|
| H96 | LAY CS 3-2/2-3 | LAY CS | DESCARTADA | N=0 after xG filter |
| H97 | BACK Away (stat reversal) | BACK Away | DESCARTADA | N=5 total |
| H98 | LAY Over 5.5 | LAY O5.5 | DESCARTADA | back_over55 7.3% non-null |
| H99 | BACK CS 4-1/1-4 | BACK CS | DESCARTADA | Columns don't exist |
| H100 | BACK Draw 2-deficit | BACK Draw | DESCARTADA | 3.0% WR |
| H101 | LAY CS 0-2/2-0 | LAY CS | DESCARTADA | 108 combos, all ROI < 0 |

## Detailed Analysis

### H96 -- "Fiesta Inacabada 3-2" LAY CS 3-2/2-3

**Proposed trigger:** Score 3-2/2-3 at min 65-80, xG_total >= 4.0, SoT_total >= 12.

**Findings:**
- 24 matches reach 3-2/2-3 at min 65-80 (2.5% of dataset)
- Of those 24, ZERO have xG_total >= 4.0 (the xG filter is too aggressive for 5-goal games)
- Only 1 of 24 has SoT_total >= 12
- Only 3 of 24 have CS odds data available
- Even without filters: 58.3% of 3-2/2-3 scores hold to FT (LAY would lose 58% of the time)

**Verdict:** DEAD. The scenario is too rare and the proposed filters eliminate every single match. Even the unfiltered base shows the wrong direction for LAY.

### H97 -- "Colapso Local Estadistico" BACK Away Winner

**Proposed trigger:** Home leads 1-0/2-1 at min 65-80, xG_away - xG_home >= 0.7, SoT_away >= SoT_home + 2.

**Findings:**
- Only 5 matches in the entire dataset meet all conditions
- Away team wins in only 1 of those 5 (20% WR)
- Home team wins in 4 of 5 despite stat disadvantage
- Avg back_away odds: 20.75 (all above the proposed 4-10 range)

**Verdict:** DEAD. The "stat-dominant away team losing" scenario essentially doesn't happen in our data because teams that lead typically also dominate the stats. When it does happen, the home team usually holds on.

### H98 -- "Anti-Goleada 5+" LAY Over 5.5

**Proposed trigger:** 5+ goals at min 60-72, deceleration indicators, back_over55 in 1.8-3.0.

**Findings:**
- `back_over55` has only 7.3% non-null rate -- column is effectively empty
- 35 matches reach 5+ goals at min 60-72
- Of 13 with odds, avg = 1.39 (all below proposed 1.8-3.0 range)
- 57.1% of these matches DO score more (FT > 5), so the LAY would lose majority
- H10 (LAY O5.5) was already descartada in R3 for "tail risk extremo"

**Verdict:** DEAD. Column unavailable, odds too low, and the market is correct -- high-scoring matches continue scoring.

### H99 -- "Cierre 4-1 del Gigante" BACK CS 4-1/1-4

**Proposed trigger:** Score 3-0/3-1 at min 55-70, BACK CS 4-1/1-4.

**Findings:**
- `back_rc_4_1` and `back_rc_1_4` columns **DO NOT EXIST** in CSVs (0% presence in headers)
- 97 matches reach 3-0/0-3/3-1/1-3 at min 55-70
- Of those, only 11 (11.3%) end 4-1/1-4
- Even if columns existed: 11.3% WR would need avg odds > 9.4 to break even, unlikely for CS markets

**Verdict:** NOT TESTABLE. The Betfair scraper does not capture CS 4-1/1-4 odds.

### H100 -- "Remontada Incompleta" BACK Draw from 2-Goal Deficit

**Proposed trigger:** 2-goal deficit at min 65-78, trailing team dominates recent xG/SoT.

**Findings:**
- 67 matches have 2-goal deficit at min 65-78 with stats available
- Only 2 end in a draw (3.0% WR)
- Avg back_draw = 20.18 in these scenarios
- Expected ROI: 3.0% * 20.18 * 0.95 - 97% = -39.5%. Clearly unprofitable.
- This confirms the established finding that comebacks from 2+ goals are nearly impossible (leader at 70' holds 85.6%)

**Verdict:** DEAD. The base rate for draw from 2 goals down is 3%, far too low for profitability at any odds level.

### H101 -- "Anti-Scoreline 0-2/2-0" LAY CS 0-2/2-0

**Proposed trigger:** Score 0-2/2-0 at min 55-75, favourite losing.

**Findings:**
- 191 matches reach 0-2/2-0 at min 55-75 (good N)
- Only 2 have favourite losing with cuota <= 2.0 (fav filter kills N)
- Without fav filter: full 108-combo grid search executed
- ALL 108 combos have **negative ROI** (best: -18.2%)
- The math: 69.8% WR at avg odds 4.06 gives +9.50 per win, but losses cost -30.60 each. 30.2% loss rate * 30.60 > 69.8% * 9.50.
- Score changes 68.1% of the time from 0-2/2-0 (high "LAY win" rate), but the CS LAY liability when wrong is too large

**Verdict:** DEAD. Market correctly prices CS 0-2/2-0. The LAY liability math makes this unprofitable even with a 70% win rate.

## Lessons Learned

1. **Rare scoreline strategies need massive datasets**: 3-2/2-3 appears in only 2.5% of matches. With 954 matches, that's 24 occurrences. After any stat filter, N drops to near zero. Need 5000+ matches for viable rare-scoreline strategies.

2. **Column availability is a hard constraint**: back_over55 (7.3%), back_rc_4_1 (0%), back_rc_1_4 (0%). These are structural data gaps, not quality issues. Strategies should be designed around available columns.

3. **LAY CS math is challenging**: Even with a 70% win rate, the asymmetric payout (win +9.50 vs lose -30.60 at odds 4.06) makes profitability very difficult. LAY CS only works at very low odds or very high WR.

4. **2-goal deficit comebacks are statistically negligible**: 3.0% draw rate confirms the established pattern. This angle has now been tested from multiple directions (H100 here, plus existing leader strategies showing 85.6% hold rate).

5. **Stat-reversal from away team is too rare**: The condition "home leads but away dominates all stats" occurs in only 0.5% of matches. Market-moving stat reversals are uncommon because favourites that score also dominate stats.

## Recommendations

- **Next hypothesis number: H102**
- Focus new hypotheses on markets with available columns and sufficient scenario frequency (>5% of matches)
- LAY CS strategies should target low-odds scenarios (< 3.0) where liability is manageable
- The most productive remaining areas are likely refinements of existing proven concepts rather than entirely new angles

## Scripts

- Feasibility exploration: `strategies/sd_explore_data_r18.py`
- H101 backtest: `strategies/sd_bt_h101_lay_cs_02_20.py`
- Tracker updated: `strategies/sd_strategy_tracker.md`
