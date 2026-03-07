# Round 13 Summary

## Overview
- **Dataset**: 896 matches (927 CSVs, 896 finished)
- **Hypotheses explored**: 5 (H77-H81)
- **Approved**: 3 (H77, H79, H81) -- all PASS realistic validation
- **Discarded**: 2 (H78, H80) -- test ROI below 10% threshold

## Focus Areas Investigated

### 1. First-half patterns (min 20-45) -- RESULT: WEAK EDGES
The user requested exploration of first-half triggers since existing strategies are concentrated at min 55+. Findings:
- **H78 (O3.5 from 3+ goals by FH)**: Train ROI=14.3% but test ROI=0.5%. The market adjusts Over 3.5 pricing accurately once goals are scored early. **Discarded.**
- **H80 (Home leading FH, favourite)**: Train ROI=15.2% but test ROI=1.9%. The edge at first half is ~2pp -- far too small for reliable profitability. H70 (min 55+) captures the same concept with 10x the ROI. **Discarded.**
- **Conclusion**: First-half edges exist but are too small to survive realistic adjustments. The market has the entire second half to adjust, reducing edge magnitude. Min 70+ remains the sweet spot.

### 2. LAY home/away -- RESULT: INSUFFICIENT DATA
- Only 5 matches where home leads 1-0 but away dominates both xG and SoT at first half. Impossible to build a strategy on N=5.
- LAY home ROI was -6.2% even in this tiny sample. No signal.
- **Conclusion**: LAY home/away requires extremely specific conditions that rarely occur. Not viable with 900 matches.

### 3. Correct Scores (unexploited scorelines) -- RESULT: 3 NEW STRATEGIES
This was the most productive area. The CS structural inefficiency discovered in R8-R9 (H49, H53) extends to ALL tested scorelines:

| Scoreline | Strategy | N | WR | ROI (realistic) | Sharpe |
|-----------|----------|---|----|-----------------|--------|
| 1-1 | H77 | 102 | 57.8% | 24.1% | 1.63 |
| 2-0/0-2 | H79 | 90 | 53.3% | 46.2% | 2.19 |
| 3-0/0-3/3-1/1-3 | H81 | 79 | 65.8% | 58.3% | 3.51 |

### 4. Stat combinations (SoT ratio, xG delta, corners+possession)
- SoT dominance at 0-0 FH: N=31, dominant team scores 67.7% but Over 1.5 rate only 41.9% -- not enough for BACK Over strategy
- xG dominance at 0-0 FH: N=12, too few for analysis
- **Conclusion**: Stat combinations in first half produce insufficient N for reliable strategies

### 5. Odds drift + stats
- N=34 drift events (>=15% drift in 10min) at 0-0 in first half
- Home win rate with negative drift: 29.4% -- market is correct
- **Conclusion**: Odds drift in first half is noise, confirmed (see also H31 from R5)

## Approved Strategies (Top 3, ordered by Sharpe)

### 1. H81: BACK CS Big-Lead Late (Sharpe=3.51, ROI=58.3%)
- **What**: Back correct score for 3-0/0-3/3-1/1-3 at min 70-85
- **Why it works**: 2-3 goal leads at min 70+ hold 65.8% of the time, CS market implies only ~40%
- **Edge**: +26pp over market implied probability
- **Risk**: N=79 is adequate but not large. 0-3 scoreline (N=17, WR=82.4%) is the strongest sub-component
- **Report**: `strategies/sd_report_back_cs_big_lead_late.md`

### 2. H79: BACK CS 2-0/0-2 Late (Sharpe=2.19, ROI=46.2%)
- **What**: Back correct score for 2-0/0-2 at min 75-90
- **Why it works**: 2-goal clean sheet holds 53.3%, CS market implies ~36%
- **Edge**: +17pp over market implied probability
- **Risk**: Moderate -- 0-2 scoreline has better WR (59.3%) than 2-0 (50.8%)
- **Supersedes**: H55 (was in monitoring)
- **Report**: `strategies/sd_report_back_cs_20_late.md`

### 3. H77: BACK CS 1-1 Late (Sharpe=1.63, ROI=24.1%)
- **What**: Back correct score 1-1 at min 75-90
- **Why it works**: 1-1 holds 57.8%, CS market implies ~46%
- **Edge**: +12pp over market implied probability
- **Complements**: H58 (BACK Draw 1-1) -- same match, different market
- **Report**: `strategies/sd_report_back_cs_11_late.md`

## Complete CS Portfolio (after R13)

| Strategy | Scorelines | N | ROI | Sharpe |
|----------|-----------|---|-----|--------|
| H49 (R8) | 2-1, 1-2 | 118 | 85.4% | 3.71 |
| H53 (R9) | 1-0, 0-1 | 216 | 39.1% | 3.15 |
| H77 (R13) | 1-1 | 102 | 24.1% | 1.63 |
| H79 (R13) | 2-0, 0-2 | 90 | 46.2% | 2.19 |
| H81 (R13) | 3-0, 0-3, 3-1, 1-3 | 79 | 58.3% | 3.51 |
| **TOTAL** | **10 scorelines** | **~605** | **avg ~50%** | -- |

All 10 scorelines have ZERO market overlap (each bet is on a unique correct score). The CS structural inefficiency is the most robust and universal edge found in 81 hypotheses of research.

## Discarded Hypotheses

| H# | Name | N | Train ROI | Test ROI | Reason |
|----|------|---|-----------|----------|--------|
| H78 | BACK O3.5 FH Activity | 75 | 14.3% | 0.5% | Test ROI below 10% threshold |
| H80 | BACK Home Leading FH | 191 | 15.2% | 1.9% | Test ROI below 10% threshold |

## Key Learnings

1. **CS structural inefficiency is UNIVERSAL**: Every scoreline tested at min 70-90 shows positive edge. The market's constraint of pricing dozens of outcomes simultaneously creates a persistent, exploitable inefficiency.

2. **First-half strategies are structurally weak**: The market has 45+ minutes to adjust, reducing edge magnitude to <2pp. This is likely a fundamental limitation, not a data issue. Future research should focus on min 65+ windows.

3. **LAY strategies in FH need more data**: The conditions required for LAY home/away produce too few matches (<10) to be viable with 900-match datasets. Would need 5000+ matches.

4. **Train/test divergence reveals market efficiency timing**: H78 and H80 both show decent train ROI but test collapse. This pattern consistently indicates the market prices the pattern correctly on average -- any train-period edge is statistical noise.

## Next Steps

1. **Integrate H77, H79, H81 into notebook** (`strategies_designer.ipynb`)
2. **Focus future research on**:
   - CS market for remaining scorelines with sufficient N (2-2 when dataset grows)
   - Completely new market types not yet explored (if any become available in data)
   - Cross-strategy portfolio optimization (combining CS bets with leader portfolio)
3. **Stop investigating**: First-half patterns, LAY home/away, odds drift -- all confirmed as dead angles in R13
