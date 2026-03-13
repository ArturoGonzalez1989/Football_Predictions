# H105: BACK Home Leading +1 Low xG — REJECTED (Redundant)

## Concept
Back the home team on Match Odds when they lead by exactly 1 goal in the late game (65-90 min), optionally filtering for low total xG. The thesis is that a 1-goal home lead in a low-xG game is more likely to hold than the market implies.

## Edge Thesis
Home teams leading by 1 late benefit from crowd support and game management. When combined with low xG (few dangerous chances created), the game is "quiet" and the lead is likely to hold. The market may underestimate the probability of the result holding in low-activity games.

## Verdict: REJECTED

**Reason: 60.7% overlap with `home_fav_leading` (same market, BACK Home Match Odds)**

H105 is not an independent strategy. It is the mathematical union of two existing strategies:
1. **home_fav_leading** (H70): covers home favourites leading (215 of 354 H105 bets)
2. **ud_leading** (H59): covers home non-favourites leading (the remaining 139 bets)

Both already exist in production and are active.

## Grid Search Results (30 combos, 963 matches)

Gate N threshold: >= 38

### Top 10 combos by Sharpe

| Combo | N | WR% | ROI% | P/L | AvgOdds | MaxDD | Sharpe | CI95lo | Leagues | TrROI | TeROI | Pass |
|-------|---|-----|------|-----|---------|-------|--------|--------|---------|-------|-------|------|
| min[65-90] xg<none | 354 | 77.7 | 33.8 | 1195.4 | 1.83 | 70.2 | 4.68 | 73.1 | 54 | 34.0 | 33.2 | PASS |
| min[70-90] xg<none | 324 | 78.7 | 31.2 | 1012.1 | 1.76 | 67.7 | 4.11 | 73.9 | 53 | 31.2 | 31.3 | PASS |
| min[65-85] xg<none | 327 | 76.5 | 25.5 | 833.8 | 1.75 | 70.5 | 3.78 | 71.6 | 51 | 30.1 | 15.0 | PASS |
| min[60-85] xg<none | 356 | 75.0 | 22.7 | 806.6 | 1.76 | 94.9 | 3.57 | 70.3 | 51 | 29.2 | 7.5 | PASS |
| min[65-80] xg<none | 304 | 77.0 | 19.4 | 589.4 | 1.63 | 63.2 | 3.04 | 71.9 | 49 | 23.6 | 9.8 | PASS |
| min[65-90] xg<2.0 | 89 | 79.8 | 32.5 | 289.2 | 1.76 | 45.7 | 2.20 | 70.3 | 28 | 51.5 | -11.2 | FAIL(TE) |
| min[65-90] xg<2.5 | 105 | 78.1 | 28.6 | 300.4 | 1.72 | 45.7 | 2.19 | 69.3 | 30 | 40.3 | 1.9 | PASS |
| min[65-90] xg<1.8 | 78 | 79.5 | 34.3 | 267.9 | 1.78 | 35.7 | 2.08 | 69.2 | 27 | 54.0 | -9.9 | FAIL(TE) |
| min[70-90] xg<2.0 | 81 | 84.0 | 31.3 | 253.5 | 1.70 | 28.6 | 2.05 | 74.5 | 28 | 44.0 | 2.8 | PASS |
| min[65-90] xg<1.5 | 70 | 81.4 | 35.3 | 247.1 | 1.73 | 28.4 | 2.04 | 70.8 | 27 | 50.7 | -0.7 | FAIL(TE) |

12/30 combos pass all quality gates (N, ROI, CI95, Train>0, Test>0).

### Key observation: xG filter HURTS stability

Combos without xG filter (xg<none) are the most stable — they all have positive test ROI. Combos with xG filters tend to fail the test ROI gate because:
- Low xG games are a smaller sample, more volatile
- xG adds a data-availability constraint (null xG values reduce N)
- The edge comes from the score state (leading by 1 late), not from xG

## Overlap Analysis

### vs home_fav_leading (SAME market: BACK Home)

| Metric | Value |
|--------|-------|
| H105 triggers | 354 |
| home_fav_leading triggers | 239 |
| Overlap (both trigger) | 215 (60.7% of H105) |
| H105 unique | 139 |
| home_fav_leading unique | 24 |

**Overlap = 60.7% >> 30% threshold. REJECTED.**

### Breakdown of H105 bets

| Segment | N | WR% | ROI% | Sharpe | Description |
|---------|---|-----|------|--------|-------------|
| Overlap (in home_fav_leading) | 215 | 84.2 | 25.9 | 3.73 | Pre-match favourite homes leading by 1 late |
| Unique (NOT in home_fav_leading) | 139 | 67.6 | 45.9 | 3.08 | Home non-favourites leading by 1 late |

The "unique" 139 bets are home teams that are NOT pre-match favourites (i.e., home underdogs or evenly-matched). These are already covered by `ud_leading` (H59), which backs any underdog leading late (both home and away).

## Why H105 Cannot Be Salvaged

1. **Same market**: Both H105 and home_fav_leading bet on BACK Home Match Odds. Market-group dedup would eliminate duplicates anyway.
2. **Superset, not complement**: H105 = home_fav_leading UNION (ud_leading restricted to home). No new information.
3. **The unique subset is ud_leading**: The 139 non-favourite homes leading are exactly ud_leading's home-team subset. Adding H105 would create triple-counting on some matches.

## Backtest Script
`strategies/sd_bt_h105_back_home_leading_xglow.py`

## Bets Export
`auxiliar/sd_bt_h105_bets.json` (354 bets, best combo min[65-90] xg<none)
