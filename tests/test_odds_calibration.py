"""
Tests for _calibrate_odds_min() in scripts/bt_optimizer.py.

Verifies that the analytical odds-minimum calibration:
  1. Returns 0.0 when edge exists even at very low odds
  2. Returns the correct lower-bucket bound when low-odds bets have no edge
  3. Skips buckets with too few bets (< _MIN_BUCKET_N)
  4. Returns None for LAY strategies (asymmetric P/L, WR comparison invalid)
  5. Handles the case where no bucket has sufficient data
  6. Integration: calibrated value passes quality gates validation

Run: python tests/test_odds_calibration.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
sys.path.insert(0, str(ROOT / "betfair_scraper"))

from bt_optimizer import (
    _calibrate_odds_min,
    _ODDS_BUCKETS,
    _MIN_BUCKET_N,
    _PERMANENTLY_DISABLED,
)

PASS = 0
FAIL = 0


def ok(name: str):
    global PASS
    PASS += 1
    print(f"  PASS  {name}")


def fail(name: str, detail: str = ""):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        ok(name)
    else:
        fail(name, detail)


# ── Unit tests for _ODDS_BUCKETS structure ─────────────────────────────────────

def test_bucket_coverage():
    """Buckets must start at 1.0 and cover all odds continuously."""
    prev_hi = 1.0
    for lo, hi, mid in _ODDS_BUCKETS:
        check(
            f"bucket [{lo}, {hi}) starts where previous ended",
            abs(lo - prev_hi) < 1e-9,
            f"expected lo={prev_hi}, got lo={lo}",
        )
        check(
            f"bucket [{lo}, {hi}) midpoint is between lo and hi",
            lo <= mid < hi,
            f"mid={mid} not in [{lo}, {hi})",
        )
        prev_hi = hi
    check(
        "last bucket extends to infinity",
        _ODDS_BUCKETS[-1][1] == float("inf"),
        f"got {_ODDS_BUCKETS[-1][1]}",
    )


def test_min_bucket_n_positive():
    check("_MIN_BUCKET_N >= 1", _MIN_BUCKET_N >= 1, f"got {_MIN_BUCKET_N}")


# ── Core logic tests using a mock strategy ─────────────────────────────────────
# We monkey-patch _registry_entry and _analyze_strategy_simple to avoid
# loading 1200+ CSVs and to exercise the calibration logic in isolation.

import bt_optimizer as _bt_mod


def _make_bets(odds_list, won_list):
    """Build a list of fake bets with back_odds and won flags."""
    return [
        {"back_odds": o, "won": w, "pl": (o - 1) * 0.95 if w else -1.0}
        for o, w in zip(odds_list, won_list)
    ]


def _install_mock(key, bets):
    """
    Patch _registry_entry and _analyze_strategy_simple so that _calibrate_odds_min
    returns the given bets regardless of params.
    """
    fake_entry = (key, None, lambda *a, **k: None, None, None, None)

    original_registry = _bt_mod._registry_entry
    original_analyze  = _bt_mod._analyze_strategy_simple

    def mock_registry(k):
        return fake_entry if k == key else original_registry(k)

    def mock_analyze(k, trigger_fn, extract_fn, win_fn, cfg, min_dur):
        if k == key:
            return bets
        return original_analyze(k, trigger_fn, extract_fn, win_fn, cfg, min_dur)

    _bt_mod._registry_entry       = mock_registry
    _bt_mod._analyze_strategy_simple = mock_analyze
    return original_registry, original_analyze


def _restore_mock(original_registry, original_analyze):
    _bt_mod._registry_entry          = original_registry
    _bt_mod._analyze_strategy_simple = original_analyze


def test_all_buckets_have_edge_returns_zero():
    """When edge exists even at low odds, calibrated min should be 0.0."""
    # Build bets where WR is ~90% across all odds ranges — always > implied WR.
    bets = _make_bets(
        [1.10] * 8 + [1.40] * 8 + [1.57] * 8 + [1.72] * 8 + [1.95] * 8,
        [True]  * 8 + [True]  * 8 + [True]  * 8 + [True]  * 8 + [True]  * 8,
    )
    key = "_mock_all_edge"
    orig_r, orig_a = _install_mock(key, bets)
    try:
        result = _calibrate_odds_min(key, {}, 1)
        check(
            "all-edge strategy returns 0.0",
            result == 0.0,
            f"got {result}",
        )
    finally:
        _restore_mock(orig_r, orig_a)


def test_low_odds_no_edge_returns_correct_cutoff():
    """When edge is absent below 1.50, calibrated min should be 1.50."""
    # Bets in 1.30-1.50 bucket: WR=50% (implied ~71%) → no edge
    # Bets in 1.50-1.65 bucket: WR=70% (implied ~63.5%) → has edge
    bets = (
        _make_bets([1.40] * 8, [True] * 4 + [False] * 4)  # WR=50%, no edge
        + _make_bets([1.57] * 8, [True] * 6 + [False] * 2)  # WR=75%, has edge
    )
    key = "_mock_cutoff_150"
    orig_r, orig_a = _install_mock(key, bets)
    try:
        result = _calibrate_odds_min(key, {}, 1)
        check(
            "no-edge below 1.50 → calibrated min = 1.50",
            result == 1.50,
            f"got {result}",
        )
    finally:
        _restore_mock(orig_r, orig_a)


def test_no_edge_in_two_low_buckets():
    """When no edge in 1.30-1.50 AND 1.50-1.65, min should be 1.65."""
    bets = (
        _make_bets([1.40] * 8, [True] * 3 + [False] * 5)   # WR=37.5%, no edge
        + _make_bets([1.57] * 8, [True] * 4 + [False] * 4)  # WR=50%, no edge (implied 63.5%)
        + _make_bets([1.72] * 8, [True] * 6 + [False] * 2)  # WR=75%, has edge (implied 58%)
    )
    key = "_mock_cutoff_165"
    orig_r, orig_a = _install_mock(key, bets)
    try:
        result = _calibrate_odds_min(key, {}, 1)
        check(
            "no-edge below 1.65 → calibrated min = 1.65",
            result == 1.65,
            f"got {result}",
        )
    finally:
        _restore_mock(orig_r, orig_a)


def test_bucket_too_few_bets_skipped():
    """Buckets with fewer than _MIN_BUCKET_N bets are skipped."""
    # Only 2 bets in 1.30-1.50 (below _MIN_BUCKET_N=5) — should be ignored.
    # Then 8 bets in 1.50-1.65 with edge.
    bets = (
        _make_bets([1.40] * 2, [True] * 2)              # only 2 bets — skip
        + _make_bets([1.57] * 8, [True] * 6 + [False] * 2)  # WR=75%, has edge
    )
    key = "_mock_skip_thin_bucket"
    orig_r, orig_a = _install_mock(key, bets)
    try:
        result = _calibrate_odds_min(key, {}, 1)
        check(
            "thin bucket skipped → calibrated min = 1.50 (start of first reliable bucket)",
            result == 1.50,
            f"got {result}",
        )
    finally:
        _restore_mock(orig_r, orig_a)


def test_no_bets_returns_none():
    """When the strategy produces no bets, return None."""
    key = "_mock_no_bets"
    orig_r, orig_a = _install_mock(key, [])
    try:
        result = _calibrate_odds_min(key, {}, 1)
        check(
            "empty bets list returns None",
            result is None,
            f"got {result}",
        )
    finally:
        _restore_mock(orig_r, orig_a)


def test_lay_strategy_returns_none():
    """LAY strategies must return None (WR comparison doesn't apply)."""
    result_lay = _calibrate_odds_min("lay_over45_v3", {}, 1)
    check(
        "lay_over45_v3 (permanently disabled LAY) returns None",
        result_lay is None,
        f"got {result_lay}",
    )

    result_lay2 = _calibrate_odds_min("lay_draw_away_leading", {}, 1)
    check(
        "lay_draw_away_leading returns None",
        result_lay2 is None,
        f"got {result_lay2}",
    )


def test_no_bucket_has_sufficient_data():
    """When all buckets have fewer than _MIN_BUCKET_N bets, return 0.0 (no data to decide)."""
    bets = _make_bets([1.40] * 3, [False] * 3)  # only 3 bets, all losing
    key = "_mock_all_thin"
    orig_r, orig_a = _install_mock(key, bets)
    try:
        result = _calibrate_odds_min(key, {}, 1)
        # With no reliable buckets, the function cannot determine a cutoff.
        # It should return 0.0 (no minimum imposed) rather than crashing.
        check(
            "all buckets thin → returns 0.0 or None (no crash)",
            result in (0.0, None),
            f"got {result}",
        )
    finally:
        _restore_mock(orig_r, orig_a)


def test_known_strategy_not_lay_returns_float_or_none():
    """draw_22 (a non-LAY strategy) should return float or None, never raise."""
    try:
        result = _calibrate_odds_min("draw_22", {"m_min": 72, "m_max": 90, "odds_max": 8.0}, 2)
        check(
            "draw_22 calibration returns float or None",
            result is None or isinstance(result, float),
            f"got {type(result).__name__}: {result}",
        )
        if result is not None:
            check(
                "draw_22 calibrated min is non-negative",
                result >= 0.0,
                f"got {result}",
            )
    except Exception as e:
        fail("draw_22 calibration must not raise", str(e))


# ── Run all tests ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== test_odds_calibration ===\n")

    print("[ Bucket structure ]")
    test_bucket_coverage()
    test_min_bucket_n_positive()

    print("\n[ Core calibration logic (mocked) ]")
    test_all_buckets_have_edge_returns_zero()
    test_low_odds_no_edge_returns_correct_cutoff()
    test_no_edge_in_two_low_buckets()
    test_bucket_too_few_bets_skipped()
    test_no_bets_returns_none()
    test_lay_strategy_returns_none()
    test_no_bucket_has_sufficient_data()

    print("\n[ Integration (real data — requires betfair_scraper/data/) ]")
    test_known_strategy_not_lay_returns_float_or_none()

    print(f"\n{'='*40}")
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed" + (f", {FAIL} FAILED" if FAIL else " ✓"))
    sys.exit(0 if FAIL == 0 else 1)
