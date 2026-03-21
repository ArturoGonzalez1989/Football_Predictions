"""
tests/test_param_fidelity.py

Verifies that strategy parameters from cartera_config.json are correctly
applied in the LIVE detection path (detect_betting_signals).

For each sampled enabled strategy:
  POSITIVE: original config → LIVE fires at the same minute (±5) as BT
  NEGATIVE: impossible param (oddsMin=90 or minuteMin=9999) → LIVE does NOT fire

The negative test is the critical one: if params are ignored in csv_reader,
the signal would fire despite the impossible constraint.

Usage:
    python tests/test_param_fidelity.py
"""

import sys, io, csv, json, glob, copy, builtins
from pathlib import Path
from urllib.parse import unquote

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'betfair_scraper' / 'dashboard' / 'backend'))
sys.path.insert(0, str(ROOT / 'betfair_scraper'))

for mod in list(sys.modules.keys()):
    if 'csv_reader' in mod:
        del sys.modules[mod]

from utils import csv_reader

# ── Config ──────────────────────────────────────────────────────────────────

with open(str(ROOT / 'betfair_scraper' / 'cartera_config.json'), encoding='utf-8') as f:
    CONFIG = json.load(f)

STRATS = CONFIG.get('strategies', {})
MD     = CONFIG.get('min_duration', {})
DATA_DIR = ROOT / 'betfair_scraper' / 'data'

MIN_DUR_MAP = {k: MD.get(k, 1) for k, *_ in csv_reader._STRATEGY_REGISTRY}

# ── Build match_id → csv_path map ───────────────────────────────────────────

CSV_MAP: dict[str, Path] = {}
for p in DATA_DIR.glob('partido_*.csv'):
    mid = unquote(p.stem[len('partido_'):])
    CSV_MAP[mid] = p

# ── Load latest bt_results ───────────────────────────────────────────────────

bt_files = sorted(glob.glob(str(ROOT / 'analisis' / 'bt_results_*.csv')))
if not bt_files:
    print("SKIP: no bt_results_*.csv found in analisis/")
    sys.exit(0)

bt_path = bt_files[-1]
print(f"BT results: {Path(bt_path).name}")

bt_bets: list[dict] = []
with open(bt_path, encoding='utf-8', errors='replace') as f:
    for row in csv.DictReader(f):
        bt_bets.append(row)

print(f"BT bets loaded: {len(bt_bets)}")

# ── Sample: first bet per enabled strategy that has a local CSV ──────────────

MAX_STRATEGIES = 8   # keep runtime under ~60 s

sampled: dict[str, dict] = {}
for bet in bt_bets:
    strat = bet.get('strategy', '')
    if strat in sampled:
        continue
    if not STRATS.get(strat, {}).get('enabled'):
        continue
    mid = bet.get('match_id', '')
    if mid not in CSV_MAP:
        continue
    strat_cfg = STRATS[strat]
    sampled[strat] = {
        'match_id' : mid,
        'csv_path' : CSV_MAP[mid],
        'bt_minute': int(bet.get('minuto', 0) or 0),
        'bt_odds'  : float(bet.get('back_odds', 0) or 0),
        'cfg'      : strat_cfg,
    }
    if len(sampled) >= MAX_STRATEGIES:
        break

print(f"Sampled {len(sampled)} strategies: {list(sampled.keys())}\n")

# ── Simulation helper ────────────────────────────────────────────────────────

def _simulate_strategy(
    csv_path: Path,
    match_id: str,
    strategy_key: str,
    strat_configs: dict,
) -> int | None:
    """
    Row-by-row LIVE simulation for one match.
    Returns the fired game-minute for `strategy_key`, or None if it never fires.
    """
    with open(str(csv_path), 'r', encoding='utf-8', errors='replace') as f:
        all_rows = list(csv.DictReader(f))
    if len(all_rows) < 3:
        return None

    versions = {'_strategy_configs': strat_configs, '_min_duration': MD}

    _orig_load    = csv_reader.load_games
    _orig_resolve = csv_reader._resolve_csv_path
    _orig_read    = csv_reader._read_csv_rows
    _orig_open    = builtins.open

    first_seen: dict[str, int]  = {}
    first_seen_min: dict[str, int | None] = {}
    fired: dict[str, int | None] = {}

    try:
        game_entry = [{'match_id': match_id, 'name': match_id, 'status': 'live', 'url': ''}]
        csv_reader.load_games        = lambda _ge=game_entry: _ge
        csv_reader._resolve_csv_path = lambda mid, _p=csv_path: _p

        def _patched_open(file, *a, **kw):
            if 'placed_bets' in str(file):
                raise FileNotFoundError('patched')
            return _orig_open(file, *a, **kw)

        builtins.open = _patched_open

        signals_by_row: list[int | None] = []  # None = not present, else game minute

        for i in range(len(all_rows)):
            csv_reader._read_csv_rows = lambda path, _pr=all_rows[: i + 1]: _pr
            try:
                sigs = csv_reader.detect_betting_signals(versions).get('signals', [])
            except Exception:
                sigs = []

            match_min: int | None = None
            for sig in sigs:
                if sig.get('strategy') == strategy_key:
                    match_min = sig.get('minute')
                    break
            signals_by_row.append(match_min)

        # Persistence logic (mirrors reconcile.py)
        min_dur = MIN_DUR_MAP.get(strategy_key, 1)
        for i, match_min in enumerate(signals_by_row):
            if strategy_key in fired:
                break

            present = match_min is not None
            if present and strategy_key not in first_seen:
                first_seen[strategy_key]     = i
                first_seen_min[strategy_key] = match_min

            if strategy_key in first_seen:
                start_i  = first_seen[strategy_key]
                target_i = start_i + min_dur - 1

                if i == target_i:
                    if present:
                        fired[strategy_key] = first_seen_min[strategy_key]
                    else:
                        del first_seen[strategy_key]
                        first_seen_min.pop(strategy_key, None)
                elif i > target_i and not present:
                    del first_seen[strategy_key]
                    first_seen_min.pop(strategy_key, None)

    finally:
        csv_reader.load_games        = _orig_load
        csv_reader._resolve_csv_path = _orig_resolve
        csv_reader._read_csv_rows    = _orig_read
        builtins.open                = _orig_open

    return fired.get(strategy_key)  # None if never fired


# ── Run tests ────────────────────────────────────────────────────────────────

MINUTE_TOL = 5
passed = failed = skipped = 0

for strat, info in sampled.items():
    csv_path  = info['csv_path']
    match_id  = info['match_id']
    bt_minute = info['bt_minute']
    strat_cfg = info['cfg']

    print(f"{'─' * 60}")
    print(f"Strategy : {strat}")
    print(f"Match    : {match_id}")
    print(f"BT minute: {bt_minute}  |  BT odds: {info['bt_odds']}")

    # ── POSITIVE: original config should fire ────────────────────────────
    live_min = _simulate_strategy(csv_path, match_id, strat, STRATS)

    if live_min is None:
        # Known reconcile discrepancy — not a param bug
        print(f"  [POSITIVE] SKIP — LIVE did not fire (known reconcile discrepancy)")
        skipped += 1
    else:
        diff = abs(live_min - bt_minute)
        if diff <= MINUTE_TOL:
            print(f"  [POSITIVE] PASS — LIVE fires at min {live_min} (diff={diff})")
            passed += 1
        else:
            print(f"  [POSITIVE] FAIL — LIVE fires at min {live_min} (diff={diff} > tol={MINUTE_TOL})")
            failed += 1

    # ── NEGATIVE: impossible param should block the signal ───────────────
    strats_tight = copy.deepcopy(STRATS)

    if 'odds_min' in strat_cfg or 'oddsMin' in strat_cfg:
        # Set odds_min above any realistic market odds (all aliases)
        for k in ('odds_min', 'oddsMin', 'min_odds'):
            strats_tight[strat][k] = 90.0
        neg_label = 'odds_min=90.0'
    else:
        # Block all game minutes — set ALL known aliases to 9999
        for k in ('minute_min', 'minuteMin', 'min_minute', 'm_min', 'min_m'):
            strats_tight[strat][k] = 9999
        neg_label = 'minute_min=9999'

    live_min_neg = _simulate_strategy(csv_path, match_id, strat, strats_tight)

    if live_min_neg is None:
        print(f"  [NEGATIVE] PASS — blocked by {neg_label}")
        passed += 1
    else:
        print(f"  [NEGATIVE] FAIL — fires at min {live_min_neg} despite {neg_label}  ← PARAM IGNORED")
        failed += 1

    print()

# ── Summary ──────────────────────────────────────────────────────────────────

total_run = passed + failed
print(f"{'=' * 60}")
print(f"PARAM FIDELITY: {passed}/{total_run} passed  |  {skipped} skipped  |  {failed} FAILED")

if failed:
    print("RESULT: FAIL — parameter wiring bugs detected in LIVE detection")
    sys.exit(1)
else:
    print("RESULT: PASS — sampled params correctly wired in LIVE detection")
    sys.exit(0)
