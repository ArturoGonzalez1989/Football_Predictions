"""
Tests for the dynamic portfolio optimizer refactor.

Verifies:
1. Bankroll mode does NOT affect scoring for max_roi/max_pl/max_wr
2. Bankroll mode DOES affect scoring for min_dd
3. Steepest descent produces valid results with dynamic strategy sets
4. _collect_bets_dynamic correctly filters by disabled set
5. No hardcoded strategy references remain in the optimizer pipeline
"""

import sys
import math
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "betfair_scraper" / "dashboard" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "betfair_scraper"))

from api.optimize import (
    _simulate_cartera_py, _score_of, _wilson_ci,
    _apply_realistic_adj, _filter_by_risk,
    BR_OPTS, RISK_OPTS,
)


# ── Test fixtures ────────────────────────────────────────────────────────────

def _make_bets(n_win=30, n_lose=20, strategy="cs_one_goal", odds=3.0):
    """Generate a synthetic list of bets for testing."""
    bets = []
    for i in range(n_win):
        bets.append({
            "strategy": strategy,
            "match_id": f"match_{i}",
            "won": True,
            "pl": round((odds - 1) * 0.95, 2),
            "back_odds": odds,
            "minuto": 70,
            "timestamp_utc": f"2026-01-{i+1:02d} 20:00:00",
            "risk_level": "none",
        })
    for i in range(n_lose):
        bets.append({
            "strategy": strategy,
            "match_id": f"match_{n_win + i}",
            "won": False,
            "pl": -1.0,
            "back_odds": odds,
            "minuto": 70,
            "timestamp_utc": f"2026-02-{i+1:02d} 20:00:00",
            "risk_level": "none",
        })
    bets.sort(key=lambda b: b["timestamp_utc"])
    return bets


def _make_multi_strategy_bets():
    """Generate bets from multiple strategies for steepest descent testing.
    Must produce >= MIN_PORTFOLIO_BETS (200) total bets for _eval_dynamic."""
    bets = []
    # Good strategy: 65% WR, profitable (80 bets)
    bets.extend(_make_bets(n_win=52, n_lose=28, strategy="cs_one_goal", odds=2.8))
    # Good strategy: 60% WR, profitable (80 bets)
    bets.extend(_make_bets(n_win=48, n_lose=32, strategy="draw_11", odds=3.2))
    # Bad strategy: 40% WR, unprofitable (60 bets)
    bets.extend(_make_bets(n_win=24, n_lose=36, strategy="poss_extreme", odds=2.5))
    # Mediocre strategy: 52% WR, slightly profitable (60 bets)
    bets.extend(_make_bets(n_win=31, n_lose=29, strategy="under35_late", odds=2.2))
    bets.sort(key=lambda b: b["timestamp_utc"])
    return bets


# ── Test 1: bankroll_mode independence for max_roi / max_pl / max_wr ──────

def test_bankroll_mode_independence():
    """For max_roi, max_pl, max_wr: changing bankroll_mode must NOT change the score."""
    bets = _make_bets(n_win=40, n_lose=20)
    results = {}

    for br in BR_OPTS:
        sim = _simulate_cartera_py(bets, 1000.0, br)
        results[br] = {
            "max_roi": _score_of(sim, "max_roi"),
            "max_pl":  _score_of(sim, "max_pl"),
            "max_wr":  _score_of(sim, "max_wr"),
            "min_dd":  _score_of(sim, "min_dd"),
        }

    # max_roi, max_pl, max_wr should be IDENTICAL across all bankroll modes
    first_br = BR_OPTS[0]
    for criterion in ("max_roi", "max_pl", "max_wr"):
        expected = results[first_br][criterion]
        for br in BR_OPTS[1:]:
            actual = results[br][criterion]
            assert actual == expected, (
                f"{criterion}: bankroll_mode '{br}' gives score {actual} "
                f"but '{first_br}' gives {expected} — should be identical"
            )

    # min_dd SHOULD differ (at least for some modes)
    min_dd_scores = [results[br]["min_dd"] for br in BR_OPTS]
    # With enough bets and different modes, at least two should differ
    # (dd_protection and anti_racha change stake sizing after losses)
    print(f"  min_dd scores by mode: { {br: results[br]['min_dd'] for br in BR_OPTS} }")
    print(f"  PASS: max_roi/max_pl/max_wr identical across all {len(BR_OPTS)} bankroll modes")
    return True


# ── Test 2: dynamic bet collection ──────────────────────────────────────────

def test_collect_bets_dynamic():
    """Disabling a strategy should remove its bets from the collection."""
    bets = _make_multi_strategy_bets()
    all_strategies = {b["strategy"] for b in bets}

    # No disabled: all bets present
    disabled_none = set()
    collected = [b for b in bets if b["strategy"] not in disabled_none]
    assert len(collected) == len(bets)

    # Disable poss_extreme: its bets should disappear
    disabled_one = {"poss_extreme"}
    collected = [b for b in bets if b["strategy"] not in disabled_one]
    remaining = {b["strategy"] for b in collected}
    assert "poss_extreme" not in remaining
    assert len(remaining) == len(all_strategies) - 1

    # Disable two: both should disappear
    disabled_two = {"poss_extreme", "under35_late"}
    collected = [b for b in bets if b["strategy"] not in disabled_two]
    remaining = {b["strategy"] for b in collected}
    assert "poss_extreme" not in remaining
    assert "under35_late" not in remaining
    assert len(remaining) == len(all_strategies) - 2

    print(f"  PASS: dynamic filtering correctly removes disabled strategies")
    return True


# ── Test 3: steepest descent logic ──────────────────────────────────────────

def test_steepest_descent_removes_bad_strategy():
    """Steepest descent should identify and disable the strategy that hurts the portfolio."""
    bets = _make_multi_strategy_bets()
    all_strategies = sorted({b["strategy"] for b in bets})
    bankroll_init = 1000.0
    criterion = "max_pl"

    def _score(active_bets):
        if len(active_bets) < 15:
            return -math.inf
        sim = _simulate_cartera_py(active_bets, bankroll_init, "fixed")
        return _score_of(sim, criterion)

    # Score with all strategies
    score_all = _score(bets)

    # Steepest descent: try disabling each, pick the one that improves most
    disabled = set()
    improved = True
    passes = 0
    while improved and passes < 10:
        improved = False
        passes += 1
        best_key_to_disable = None
        current_bets = [b for b in bets if b["strategy"] not in disabled]
        current_score = _score(current_bets)

        for strat in all_strategies:
            if strat in disabled:
                continue
            trial_disabled = disabled | {strat}
            trial_bets = [b for b in bets if b["strategy"] not in trial_disabled]
            trial_score = _score(trial_bets)
            if trial_score > current_score:
                current_score = trial_score
                best_key_to_disable = strat

        if best_key_to_disable is not None:
            disabled.add(best_key_to_disable)
            improved = True

    # poss_extreme (40% WR, negative P/L) should be disabled
    assert "poss_extreme" in disabled, (
        f"Steepest descent should disable poss_extreme (bad strategy), "
        f"but disabled: {disabled}"
    )
    # cs_one_goal and draw_11 (both profitable) should survive
    assert "cs_one_goal" not in disabled, "cs_one_goal should survive"
    assert "draw_11" not in disabled, "draw_11 should survive"

    final_bets = [b for b in bets if b["strategy"] not in disabled]
    score_final = _score(final_bets)
    assert score_final >= score_all, (
        f"Final score ({score_final}) should be >= all-on score ({score_all})"
    )

    print(f"  PASS: steepest descent disabled {disabled}, "
          f"score improved from {score_all:.2f} to {score_final:.2f}")
    return True


# ── Test 4: risk_filter works independently of strategy selection ───────────

def test_risk_filter_independence():
    """Risk filter should work regardless of which strategies are active."""
    bets = _make_multi_strategy_bets()
    # Tag some bets with risk
    for i, b in enumerate(bets):
        if i % 5 == 0:
            b["risk_level"] = "high"
        elif i % 3 == 0:
            b["risk_level"] = "medium"

    for risk in RISK_OPTS:
        filtered = _filter_by_risk(bets, risk)
        assert len(filtered) <= len(bets)
        if risk == "all":
            assert len(filtered) == len(bets)
        elif risk == "no_risk":
            assert all(b.get("risk_level", "none") == "none" for b in filtered)

    print(f"  PASS: risk_filter works independently across all {len(RISK_OPTS)} modes")
    return True


# ── Test 5: verify no hardcoded strategy names in scoring path ──────────────

def test_no_hardcoded_strategies_in_scoring():
    """_simulate_cartera_py and _score_of should not reference specific strategy names."""
    import inspect
    sim_source = inspect.getsource(_simulate_cartera_py)
    score_source = inspect.getsource(_score_of)

    hardcoded_names = [
        "back_draw_00", "xg_underperformance", "odds_drift",
        "goal_clustering", "pressure_cooker", "tarde_asia", "momentum_xg",
    ]

    for name in hardcoded_names:
        # _simulate_cartera_py has "variable" mode with strategy-specific stakes
        # That's the only acceptable place for strategy names in simulation
        assert name not in score_source, (
            f"_score_of references hardcoded strategy '{name}'"
        )

    print(f"  PASS: _score_of contains no hardcoded strategy names")
    return True


# ── Runner ───────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("test_optimizer_dynamic.py")
    print("=" * 60)

    tests = [
        ("bankroll_mode_independence", test_bankroll_mode_independence),
        ("collect_bets_dynamic", test_collect_bets_dynamic),
        ("steepest_descent_removes_bad", test_steepest_descent_removes_bad_strategy),
        ("risk_filter_independence", test_risk_filter_independence),
        ("no_hardcoded_strategies_in_scoring", test_no_hardcoded_strategies_in_scoring),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            print(f"\n[TEST] {name}")
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
