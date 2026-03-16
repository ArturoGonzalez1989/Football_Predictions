"""
analyze_synergies.py — Strategy Co-occurrence and Outcome Correlation Analysis
Analyzes BT results CSV to find strategy pairs that fire on the same match,
their combined P/L, and how correlated their outcomes are.
"""

import pandas as pd
import numpy as np
from itertools import combinations
from collections import defaultdict

CSV_PATH = "C:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/analisis/bt_results_20260316_095934.csv"

# ── Load data ──────────────────────────────────────────────────────────────────
df = pd.read_csv(CSV_PATH)
print(f"Loaded {len(df)} bets across {df['match_id'].nunique()} unique matches")
print(f"Strategies present: {sorted(df['strategy'].unique())}\n")

# Basic stats per strategy
strat_stats = df.groupby('strategy').agg(
    n_bets=('pl', 'count'),
    wins=('won', 'sum'),
    total_pl=('pl', 'sum'),
).assign(
    win_rate=lambda x: x['wins'] / x['n_bets'] * 100,
    roi=lambda x: x['total_pl'] / x['n_bets'] * 100
).sort_values('n_bets', ascending=False)

print("=== OVERALL STRATEGY STATS ===")
print(strat_stats.to_string())
print()

# ── Group bets by match — find co-occurring pairs ────────────────────────────
match_strategies = df.groupby('match_id')['strategy'].apply(list)
matches_multi = match_strategies[match_strategies.apply(len) > 1]
print(f"Matches with 2+ strategies firing: {len(matches_multi)} / {len(match_strategies)}")

# Count all pairs
pair_counts = defaultdict(int)
for strategies in matches_multi:
    unique_strats = sorted(set(strategies))  # deduplicate within same match
    for pair in combinations(unique_strats, 2):
        pair_counts[pair] += 1

# Top 15 pairs by co-occurrence count
top_pairs = sorted(pair_counts.items(), key=lambda x: -x[1])[:15]
print(f"\n=== TOP 15 MOST CO-OCCURRING STRATEGY PAIRS ===")
print(f"{'Pair':<55} {'Co-occur':>8}")
print("-" * 65)
for (a, b), count in top_pairs:
    print(f"  {a} + {b:<35} {count:>8}")

# ── Detailed analysis per pair ───────────────────────────────────────────────
print("\n\n=== DETAILED PAIR ANALYSIS (Top 15) ===\n")

results = []

for (strat_a, strat_b), n_matches in top_pairs:
    # Find matches where both fired
    matches_with_both = []
    for match_id, strategies in match_strategies.items():
        strat_set = set(strategies)
        if strat_a in strat_set and strat_b in strat_set:
            matches_with_both.append(match_id)

    if not matches_with_both:
        continue

    # Get bets for these matches
    mask = df['match_id'].isin(matches_with_both)
    sub = df[mask & df['strategy'].isin([strat_a, strat_b])].copy()

    # For each match, get the (possibly multiple) bets per strategy — take first if duplicates
    # (a strategy shouldn't fire twice on same match, but just in case)
    sub_dedup = sub.drop_duplicates(subset=['match_id', 'strategy'], keep='first')

    # Pivot to wide format
    pivot = sub_dedup.pivot(index='match_id', columns='strategy', values=['pl', 'won'])
    pivot.columns = ['_'.join(col).strip() for col in pivot.columns]

    pl_a_col = f'pl_{strat_a}'
    pl_b_col = f'pl_{strat_b}'
    won_a_col = f'won_{strat_a}'
    won_b_col = f'won_{strat_b}'

    # Only rows where both bets exist
    both = pivot.dropna(subset=[pl_a_col, pl_b_col])
    n_complete = len(both)

    if n_complete == 0:
        continue

    # Combined P/L per match
    both = both.copy()
    both['combined_pl'] = both[pl_a_col] + both[pl_b_col]
    both['won_a'] = both[won_a_col].astype(bool)
    both['won_b'] = both[won_b_col].astype(bool)

    # Outcome distribution
    both_win = (both['won_a'] & both['won_b']).sum()
    both_lose = (~both['won_a'] & ~both['won_b']).sum()
    split = n_complete - both_win - both_lose

    win_rate_a = both['won_a'].mean() * 100
    win_rate_b = both['won_b'].mean() * 100

    combined_pl_total = both['combined_pl'].sum()
    combined_pl_per_match = both['combined_pl'].mean()

    # Correlation: phi coefficient (binary correlation)
    # phi = (n11*n00 - n10*n01) / sqrt(n1.*n0.*n.1*n.0)
    n11 = both_win
    n00 = both_lose
    n10 = (both['won_a'] & ~both['won_b']).sum()
    n01 = (~both['won_a'] & both['won_b']).sum()

    n1_ = n11 + n10  # A wins
    n0_ = n00 + n01  # A loses
    n_1 = n11 + n01  # B wins
    n_0 = n10 + n00  # B loses

    denom = np.sqrt(n1_ * n0_ * n_1 * n_0) if (n1_ * n0_ * n_1 * n_0) > 0 else 1
    phi = (n11 * n00 - n10 * n01) / denom

    result = {
        'pair': f"{strat_a} + {strat_b}",
        'strat_a': strat_a,
        'strat_b': strat_b,
        'n_matches': n_complete,
        'win_rate_a': win_rate_a,
        'win_rate_b': win_rate_b,
        'both_win': both_win,
        'both_lose': both_lose,
        'split': split,
        'combined_pl_total': combined_pl_total,
        'combined_pl_per_match': combined_pl_per_match,
        'phi_correlation': phi,
        'pl_a_total': both[pl_a_col].sum(),
        'pl_b_total': both[pl_b_col].sum(),
    }
    results.append(result)

    pct_both_win = both_win / n_complete * 100
    pct_both_lose = both_lose / n_complete * 100
    pct_split = split / n_complete * 100
    synergy = "HIGH CORR (risky doubling)" if phi > 0.4 else ("INDEPENDENT (good synergy)" if phi < 0.1 else "MODERATE CORR")

    print(f"{'='*70}")
    print(f"  {strat_a.upper()} + {strat_b.upper()}")
    print(f"  Co-occurring matches: {n_complete}")
    print(f"  Win rate A ({strat_a}): {win_rate_a:.1f}%  |  Win rate B ({strat_b}): {win_rate_b:.1f}%")
    print(f"  Outcome distribution:")
    print(f"    Both win:  {both_win:3d} ({pct_both_win:5.1f}%)")
    print(f"    Both lose: {both_lose:3d} ({pct_both_lose:5.1f}%)")
    print(f"    Split:     {split:3d} ({pct_split:5.1f}%)")
    print(f"  Combined P/L  total: {combined_pl_total:+.2f}  |  per match: {combined_pl_per_match:+.2f}")
    print(f"  Individual P/L  A: {result['pl_a_total']:+.2f}  |  B: {result['pl_b_total']:+.2f}")
    print(f"  Phi correlation: {phi:+.3f}  ({synergy})")
    print()

# -- Summary table -------------------------------------------------------------
if results:
    res_df = pd.DataFrame(results).sort_values('phi_correlation', ascending=False)
    print("\n=== CORRELATION RANKING (highest = most risky doubling) ===")
    print(f"{'Pair':<55} {'N':>4} {'Phi':>6} {'CombPL/match':>13} {'BothWin%':>9} {'BothLose%':>10}")
    print("-" * 100)
    for _, row in res_df.iterrows():
        n = int(row['n_matches'])
        phi = row['phi_correlation']
        cpl = row['combined_pl_per_match']
        bw = row['both_win'] / n * 100
        bl = row['both_lose'] / n * 100
        tag = " *** HIGH CORR" if phi > 0.4 else (" ** MODERATE" if phi > 0.2 else "")
        print(f"  {row['pair']:<53} {n:>4} {phi:>+6.3f} {cpl:>+13.3f} {bw:>8.1f}% {bl:>9.1f}% {tag}")

# ── Special focus: draw_11 related pairs ──────────────────────────────────────
print("\n\n=== SPECIAL FOCUS: draw_11 RELATED PAIRS ===")
draw_pairs = [res for res in results
    if 'draw_11' in res['pair'] or 'draw_xg_conv' in res['pair'] or 'cs_11' in res['pair']]

if draw_pairs:
    for row in draw_pairs:
        n = int(row['n_matches'])
        phi = row['phi_correlation']
        print(f"\n  Pair: {row['pair']}")
        print(f"    N={n}, phi={phi:+.3f}, combined P/L per match={row['combined_pl_per_match']:+.3f}")
        print(f"    Win rates: {row['strat_a']}={row['win_rate_a']:.1f}%, {row['strat_b']}={row['win_rate_b']:.1f}%")
        pct_bw = row['both_win'] / n * 100
        pct_bl = row['both_lose'] / n * 100
        pct_sp = row['split'] / n * 100
        print(f"    Both win={row['both_win']} ({pct_bw:.1f}%), both lose={row['both_lose']} ({pct_bl:.1f}%), split={row['split']} ({pct_sp:.1f}%)")
        if phi > 0.4:
            print(f"    --> RISKY: Outcomes highly correlated. Both bets win or lose together.")
        elif phi < 0.1:
            print(f"    --> GOOD SYNERGY: Outcomes are largely independent.")
        else:
            print(f"    --> MODERATE correlation. Some co-movement but not extreme.")
else:
    print("  No draw_11/draw_xg_conv/cs_11 pairs found in top 15. Checking all pairs...")
    for match_id, strategies in match_strategies.items():
        strat_set = set(strategies)
        for s in ['draw_11', 'draw_xg_conv', 'cs_11']:
            if s in strat_set:
                others = strat_set - {s}
                for o in others:
                    print(f"    {s} co-occurs with: {o}")
        break  # Just sample one

# ── cs_11 specific ────────────────────────────────────────────────────────────
print("\n\n=== cs_11 CO-OCCURRENCES (ALL) ===")
cs11_matches = match_strategies[match_strategies.apply(lambda x: 'cs_11' in x)]
print(f"  cs_11 fires in {len(cs11_matches)} matches")
if len(cs11_matches) > 0:
    cs11_co = defaultdict(int)
    for strategies in cs11_matches:
        for s in strategies:
            if s != 'cs_11':
                cs11_co[s] += 1
    print("  Co-occurring strategies with cs_11:")
    for s, c in sorted(cs11_co.items(), key=lambda x: -x[1]):
        print(f"    {s}: {c} times")

print("\n=== draw_11 CO-OCCURRENCES (ALL) ===")
d11_matches = match_strategies[match_strategies.apply(lambda x: 'draw_11' in x)]
print(f"  draw_11 fires in {len(d11_matches)} matches")
d11_co = defaultdict(int)
for strategies in d11_matches:
    for s in strategies:
        if s != 'draw_11':
            d11_co[s] += 1
print("  Co-occurring strategies with draw_11:")
for s, c in sorted(d11_co.items(), key=lambda x: -x[1])[:15]:
    print(f"    {s}: {c} times")

print("\n=== draw_xg_conv CO-OCCURRENCES (ALL) ===")
dxg_matches = match_strategies[match_strategies.apply(lambda x: 'draw_xg_conv' in x)]
print(f"  draw_xg_conv fires in {len(dxg_matches)} matches")
dxg_co = defaultdict(int)
for strategies in dxg_matches:
    for s in strategies:
        if s != 'draw_xg_conv':
            dxg_co[s] += 1
print("  Co-occurring strategies with draw_xg_conv:")
for s, c in sorted(dxg_co.items(), key=lambda x: -x[1])[:15]:
    print(f"    {s}: {c} times")

# ── draw_11 + draw_xg_conv deep dive ─────────────────────────────────────────
pair_key = ('draw_11', 'draw_xg_conv')
pair_key_rev = ('draw_xg_conv', 'draw_11')

print("\n\n=== DEEP DIVE: draw_11 + draw_xg_conv ===")
matches_both_draw = []
for match_id, strategies in match_strategies.items():
    strat_set = set(strategies)
    if 'draw_11' in strat_set and 'draw_xg_conv' in strat_set:
        matches_both_draw.append(match_id)

print(f"  Matches where BOTH draw_11 AND draw_xg_conv fired: {len(matches_both_draw)}")

if matches_both_draw:
    sub = df[df['match_id'].isin(matches_both_draw) & df['strategy'].isin(['draw_11', 'draw_xg_conv'])].copy()
    sub_dedup = sub.drop_duplicates(subset=['match_id', 'strategy'], keep='first')
    pivot = sub_dedup.pivot(index='match_id', columns='strategy', values=['pl', 'won'])
    pivot.columns = ['_'.join(col).strip() for col in pivot.columns]
    pivot = pivot.dropna()

    if len(pivot) > 0:
        n11 = (pivot['won_draw_11'].astype(bool) & pivot['won_draw_xg_conv'].astype(bool)).sum()
        n00 = (~pivot['won_draw_11'].astype(bool) & ~pivot['won_draw_xg_conv'].astype(bool)).sum()
        n10 = (pivot['won_draw_11'].astype(bool) & ~pivot['won_draw_xg_conv'].astype(bool)).sum()
        n01 = (~pivot['won_draw_11'].astype(bool) & pivot['won_draw_xg_conv'].astype(bool)).sum()
        total = len(pivot)
        print(f"  Outcome matrix (draw_11 rows, draw_xg_conv cols):")
        print(f"              draw_xg WIN  draw_xg LOSE")
        print(f"  draw_11 WIN    {n11:3d} ({n11/total*100:.1f}%)   {n10:3d} ({n10/total*100:.1f}%)")
        print(f"  draw_11 LOSE   {n01:3d} ({n01/total*100:.1f}%)   {n00:3d} ({n00/total*100:.1f}%)")
        denom = np.sqrt((n11+n10)*(n00+n01)*(n11+n01)*(n10+n00))
        phi = (n11*n00 - n10*n01) / denom if denom > 0 else 0
        print(f"\n  Phi correlation: {phi:+.3f}")
        pivot['combined_pl'] = pivot['pl_draw_11'] + pivot['pl_draw_xg_conv']
        print(f"  Combined P/L: total={pivot['combined_pl'].sum():+.2f}, per match={pivot['combined_pl'].mean():+.2f}")
        print(f"  Market dedup NOTE: In LIVE, draw_11 and draw_xg_conv compete for the SAME 'draw' market slot.")
        print(f"  Only the first-firing strategy places a bet. These {len(matches_both_draw)} are BT bets BEFORE dedup.")

print("\nDone.")
