"""
BT vs Paper Trading Discrepancy Analysis
"""
import json
import csv
import sys

sys.path.insert(0, 'betfair_scraper/dashboard/backend')

with open('betfair_scraper/dashboard/backend/../../aux/bt_bets_audit.json') as f:
    bt_bets = json.load(f)

paper_bets = []
with open('betfair_scraper/placed_bets.csv', newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        paper_bets.append(row)

CUTOFF = '2026-03-06'
BT_TO_PAPER = {'pressure_cooker': 'pressure_cooker_v1', 'odds_drift': 'odds_drift_contrarian_v1'}
PAPER_TO_BT = {v: k for k, v in BT_TO_PAPER.items()}

bt_core = [b for b in bt_bets
           if b.get('timestamp_utc', '') >= CUTOFF
           and b.get('strategy', '') in BT_TO_PAPER]

paper_core = [p for p in paper_bets
              if p.get('strategy', '') in BT_TO_PAPER.values()]

paper_sd = [p for p in paper_bets if p.get('strategy', '').startswith('sd_')]

print('='*80)
print('BT vs PAPER TRADING DISCREPANCY REPORT')
print('Paper trading active since: 2026-03-06 20:31:08')
print('='*80)
print()
print(f'Total BT bets (all history): {len(bt_bets)}')
print(f'BT core strategy bets >= {CUTOFF}: {len(bt_core)}')
print(f'Paper bets total: {len(paper_bets)}')
print(f'  - Core strategies (pressure_cooker, odds_drift): {len(paper_core)}')
print(f'  - SD strategies (backtest-only, no BT equivalent): {len(paper_sd)}')
print()

# === SD STRATEGIES IN PAPER (expected, not a discrepancy) ===
sd_strats = {}
for p in paper_sd:
    s = p.get('strategy', '')
    sd_strats[s] = sd_strats.get(s, 0) + 1

print('SD Strategy bets in paper (NO BT equivalent - backtest-only strategies):')
print(f'  {"Strategy":<30} Count')
print(f'  {"-"*35}')
for k, v in sorted(sd_strats.items()):
    print(f'  {k:<30} {v}')
print()

# === CORE STRATEGY ANALYSIS ===
# Categorize each paper core bet
no_match_history = []   # match never in BT (new match)
encoding_mismatch = []  # same match, BT has encoding issues
missing_strategy_bt = []  # match in BT but no pressure_cooker signal
match_correct = []      # found in BT with correct strategy

all_bt_match_ids = set(b.get('match_id', '') for b in bt_bets)

for p in paper_core:
    p_mid = p.get('match_id', '')
    p_strat = p.get('strategy', '')
    bt_strat = PAPER_TO_BT.get(p_strat, p_strat)

    # Check exact match with correct strategy after cutoff
    exact_ok = any(
        b.get('match_id', '') == p_mid
        and b.get('strategy', '') == bt_strat
        and b.get('timestamp_utc', '') >= CUTOFF
        for b in bt_bets
    )
    if exact_ok:
        match_correct.append(p)
        continue

    # Check if exact match_id exists in BT at all
    bt_exact_any = [b for b in bt_bets if b.get('match_id', '') == p_mid]

    # Check for partial/encoding match (first 20 chars)
    prefix = p_mid[:20]
    bt_partial = [
        b for b in bt_bets
        if b.get('match_id', '') != p_mid
        and (prefix in b.get('match_id', '') or b.get('match_id', '')[:20] == prefix)
    ]

    if not bt_exact_any and bt_partial:
        # Same match but different match_id (encoding issue)
        encoding_mismatch.append((p, bt_partial))
    elif not bt_exact_any and not bt_partial:
        # Match not in BT at all
        no_match_history.append(p)
    else:
        # Match exists in BT but pressure_cooker not triggered
        missing_strategy_bt.append((p, bt_exact_any))

# === FALSE NEGATIVES: BT has signal but paper does NOT ===
fn_before_start = []  # BT before paper trading started
fn_missing = []       # BT after start, not in paper
fn_different_mid = [] # BT match_id encoding mismatch

PAPER_START = '2026-03-06 20:31:08'
for b in bt_core:
    b_mid = b.get('match_id', '')
    b_strat_bt = b.get('strategy', '')
    b_strat_paper = BT_TO_PAPER.get(b_strat_bt, b_strat_bt)
    b_ts = b.get('timestamp_utc', '')

    # Check if in paper (exact match_id + strategy)
    in_paper_exact = any(
        p.get('match_id', '') == b_mid and p.get('strategy', '') == b_strat_paper
        for p in paper_bets
    )
    if in_paper_exact:
        continue

    # Check if in paper with partial match_id
    prefix = b_mid[:20]
    in_paper_partial = any(
        prefix in p.get('match_id', '') and p.get('strategy', '') == b_strat_paper
        for p in paper_bets
    )
    if in_paper_partial:
        fn_different_mid.append(b)
        continue

    if b_ts < PAPER_START:
        fn_before_start.append(b)
    else:
        fn_missing.append(b)

# ============================================================
# PRINT RESULTS
# ============================================================

print('='*80)
print('SECTION 1: FALSE POSITIVES (paper has, BT does NOT have for core strategies)')
print('='*80)
print()

print(f'A) NEW MATCHES NOT IN BT HISTORY (match_id not in any historical CSV): {len(no_match_history)}')
print(f'   These matches were live but had no historical data scraped => BT could not backtest them')
print(f'   {"match_id":<58} {"strategy":<25} {"min":>4} {"odds":>6} {"score":<8} timestamp')
print(f'   {"-"*120}')
for p in no_match_history:
    print(f'   {p["match_id"][:57]:<58} {p["strategy"]:<25} {p["minute"]:>4} {p["back_odds"]:>6} {p.get("score","?"):<8} {p["timestamp_utc"]}')
print()

print(f'B) ENCODING MISMATCH (match in BT but match_id differs, UTF-8 vs %-encoded): {len(encoding_mismatch)}')
print(f'   {"match_id_paper":<58} {"strategy":<25} {"min":>4} {"BT_strategy":<25} BT_timestamp')
print(f'   {"-"*140}')
for p, bt_list in encoding_mismatch:
    bt_same_strat = [b for b in bt_list if b.get('strategy', '') == PAPER_TO_BT.get(p['strategy'], '')]
    bt_same_cutoff = [b for b in bt_same_strat if b.get('timestamp_utc', '') >= CUTOFF]
    status = 'OK (BT triggered same strat after cutoff)' if bt_same_cutoff else 'DISCREPANCY (BT has match, pressure_cooker NOT triggered)'
    print(f'   Paper: {p["match_id"][:57]:<58} {p["strategy"]:<25} min={p["minute"]}')
    for b in bt_list[:2]:
        b_odds = b.get('back_odds') or b.get('back_over_odds', '?')
        print(f'   BT:    {b["match_id"][:57]:<58} {b["strategy"]:<25} min={b.get("minuto","?")} ts={b["timestamp_utc"]} -> {status}')
print()

print(f'C) MATCH IN BT (different strategy, no pressure_cooker triggered): {len(missing_strategy_bt)}')
print(f'   {"match_id":<58} {"paper_strategy":<25} {"min":>4} note')
print(f'   {"-"*120}')
for p, bt_list in missing_strategy_bt:
    bt_strats = list(set(b.get('strategy', '') for b in bt_list))
    print(f'   {p["match_id"][:57]:<58} {p["strategy"]:<25} {p["minute"]:>4} BT_strats={bt_strats}')
print()

print('='*80)
print('SECTION 2: FALSE NEGATIVES (BT has signal >= 2026-03-06, paper does NOT)')
print('='*80)
print()

print(f'A) BT SIGNALS BEFORE PAPER TRADING STARTED (before 2026-03-06 20:31:08): {len(fn_before_start)}')
print(f'   These are expected misses - paper trading was not yet active')
print(f'   {"match_id":<58} {"strategy":<25} {"min":>4} {"odds":>6} BT_timestamp')
print(f'   {"-"*120}')
for b in fn_before_start:
    odds = b.get('back_odds') or b.get('back_over_odds', '?')
    print(f'   {b["match_id"][:57]:<58} {BT_TO_PAPER.get(b["strategy"],b["strategy"]):<25} {str(b.get("minuto","?")):>4} {str(odds):>6} {b["timestamp_utc"]}')
print()

print(f'B) ENCODING MISMATCH (BT has, paper has same match but different match_id encoding): {len(fn_different_mid)}')
for b in fn_different_mid:
    odds = b.get('back_odds') or b.get('back_over_odds', '?')
    b_strat_paper = BT_TO_PAPER.get(b['strategy'], b['strategy'])
    prefix = b['match_id'][:20]
    paper_match = [p for p in paper_bets if prefix in p.get('match_id', '') and p.get('strategy', '') == b_strat_paper]
    print(f'   BT: {b["match_id"][:55]} | {b_strat_paper} | min={b.get("minuto","?")} | ts={b["timestamp_utc"]}')
    for p in paper_match:
        print(f'   Paper: {p["match_id"][:55]} | {p["strategy"]} | min={p["minute"]} | ts={p["timestamp_utc"]}')
print()

print(f'C) TRUE MISSING SIGNALS (BT triggered after paper start, paper missed them): {len(fn_missing)}')
print(f'   {"match_id":<58} {"strategy":<25} {"min":>4} {"odds":>6} {"score":<8} BT_timestamp')
print(f'   {"-"*130}')
for b in fn_missing:
    odds = b.get('back_odds') or b.get('back_over_odds', '?')
    score = b.get('score_at_trigger') or b.get('score', '?')
    print(f'   {b["match_id"][:57]:<58} {BT_TO_PAPER.get(b["strategy"],b["strategy"]):<25} {str(b.get("minuto","?")):>4} {str(odds):>6} {str(score):<8} {b["timestamp_utc"]}')
print()

print('='*80)
print('SUMMARY')
print('='*80)
print()
print(f'Core strategy paper bets:          {len(paper_core):>4}')
print(f'  Confirmed in BT (exact match):   {len(match_correct):>4}  (no discrepancy)')
print(f'  FP-A: New matches, no BT data:   {len(no_match_history):>4}  (match never scraped historically)')
print(f'  FP-B: Encoding mismatch:         {len(encoding_mismatch):>4}  (same match, different match_id format)')
print(f'  FP-C: Match in BT, no signal:    {len(missing_strategy_bt):>4}  (BT had match, strategy not triggered)')
print()
print(f'BT core signals >= {CUTOFF}:    {len(bt_core):>4}')
print(f'  Confirmed in paper:              {len(bt_core)-len(fn_before_start)-len(fn_missing)-len(fn_different_mid):>4}  (no discrepancy)')
print(f'  FN-A: Before paper trading:      {len(fn_before_start):>4}  (expected, paper not active yet)')
print(f'  FN-B: Encoding mismatch (found): {len(fn_different_mid):>4}  (same match, different match_id format)')
print(f'  FN-C: TRUE MISSING in paper:     {len(fn_missing):>4}  (BT triggered, paper did NOT place bet)')
print()
print(f'SD paper bets (no BT equivalent): {len(paper_sd):>4}  (expected - SD strategies are backtest-only)')
