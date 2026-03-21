"""
test_monte_carlo.py — Tests for Monte Carlo risk analysis module.

Categories:
  MC1  Determinism: same seed -> same results
  MC2  Strategy fragility: known distributions produce expected fragility
  MC3  Portfolio drawdown: distribution properties and bounds
  MC4  Portfolio profit: distribution properties, P(loss), P(ruin)
  MC5  Edge cases: empty bets, single bet, all wins, all losses
  MC6  Statistical sanity: bootstrap mean ≈ actual metric (unbiasedness)

Usage:
    python tests/test_monte_carlo.py
    python tests/test_monte_carlo.py --verbose
    python tests/test_monte_carlo.py -k MC3
"""

import sys
import os
import io
import math
import argparse
from pathlib import Path

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import monte_carlo

# ── Test runner ───────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0
VERBOSE = False
CATEGORY_FILTER = None
_results = []


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if condition:
        PASS += 1
    else:
        FAIL += 1
    _results.append((status, name, detail))
    if VERBOSE or not condition:
        marker = "  PASS" if condition else "  FAIL"
        msg = f"{marker}  {name}"
        if detail:
            msg += f"  — {detail}"
        print(msg)


def should_run(category: str) -> bool:
    if CATEGORY_FILTER is None:
        return True
    return CATEGORY_FILTER.upper() in category.upper()


# ── Test data generators ─────────────────────────────────────────────────────

def _make_bets(pls: list, wons: list | None = None) -> list:
    """Create minimal bet dicts from P/L and won lists."""
    if wons is None:
        wons = [pl > 0 for pl in pls]
    return [{"pl": pl, "won": w, "strategy": "test"} for pl, w in zip(pls, wons)]


def _make_portfolio_bets(strategies: dict) -> list:
    """Create bets for multiple strategies. strategies = {"name": [(pl, won), ...]}"""
    bets = []
    for name, entries in strategies.items():
        for pl, won in entries:
            bets.append({"pl": pl, "won": won, "strategy": name})
    return bets


# ── Fixtures ─────────────────────────────────────────────────────────────────

# Strong strategy: 100 bets, ~70% WR, high ROI (~40%)
STRONG_BETS = _make_bets(
    [1.0] * 70 + [-1.0] * 30,  # 70 wins, 30 losses, WR=70%, PL=40, ROI=40%
)

# Borderline strategy: 50 bets, WR ~52%, ROI ~10.4%
BORDERLINE_BETS = _make_bets(
    [0.9] * 26 + [-1.0] * 24,  # 26 wins, 24 losses, WR=52%, PL=0.52*26-24=-0.6
)
# Fix: need ROI >= 10% -> adjust odds. 26 wins * 1.5 - 24 = 15, ROI = 15/50*100 = 30%
# Let's make it truly borderline
BORDERLINE_BETS = _make_bets(
    [1.1] * 28 + [-1.0] * 22,  # 28 wins * 1.1 = 30.8, - 22 = 8.8, ROI = 17.6%
    [True] * 28 + [False] * 22,  # WR = 56%, barely above IC95 threshold with N=50
)

# Perfect strategy: all wins
PERFECT_BETS = _make_bets([0.9] * 60, [True] * 60)

# Terrible strategy: all losses
ALL_LOSS_BETS = _make_bets([-1.0] * 60, [False] * 60)

# Concentrated edge: a few big wins carry the whole strategy
CONCENTRATED_BETS = _make_bets(
    [5.0] * 5 + [-1.0] * 45,   # 5 big wins carry the strategy
    [True] * 5 + [False] * 45,  # WR=10%, PL=25-45=-20, ROI=-40% -> will fail gates
)

N_FIN = 1200  # typical number of finished matches


# ─────────────────────────────────────────────────────────────────────────────
# MC1: Determinism
# ─────────────────────────────────────────────────────────────────────────────

def test_mc1_determinism():
    if not should_run("MC1"):
        return

    # Same seed -> identical results
    r1 = monte_carlo.strategy_fragility(STRONG_BETS, N_FIN, n_sims=1000, seed=42)
    r2 = monte_carlo.strategy_fragility(STRONG_BETS, N_FIN, n_sims=1000, seed=42)
    check("MC1.1 strategy_fragility deterministic (same seed)",
          r1 == r2,
          f"r1={r1['fragility_pct']} r2={r2['fragility_pct']}")

    d1 = monte_carlo.portfolio_drawdown_distribution(STRONG_BETS, n_sims=1000, seed=42)
    d2 = monte_carlo.portfolio_drawdown_distribution(STRONG_BETS, n_sims=1000, seed=42)
    check("MC1.2 portfolio_drawdown deterministic (same seed)",
          d1 == d2)

    p1 = monte_carlo.portfolio_profit_distribution(STRONG_BETS, n_sims=1000, seed=42)
    p2 = monte_carlo.portfolio_profit_distribution(STRONG_BETS, n_sims=1000, seed=42)
    check("MC1.3 portfolio_profit deterministic (same seed)",
          p1 == p2)

    # Different seed -> different results
    r3 = monte_carlo.strategy_fragility(STRONG_BETS, N_FIN, n_sims=1000, seed=99)
    check("MC1.4 different seed -> different results",
          r1["fragility_pct"] != r3["fragility_pct"] or r1["roi_p5"] != r3["roi_p5"],
          f"seed42={r1['fragility_pct']} seed99={r3['fragility_pct']}")


# ─────────────────────────────────────────────────────────────────────────────
# MC2: Strategy fragility
# ─────────────────────────────────────────────────────────────────────────────

def test_mc2_strategy_fragility():
    if not should_run("MC2"):
        return

    # Strong strategy should have low fragility
    strong = monte_carlo.strategy_fragility(STRONG_BETS, N_FIN, n_sims=5000, seed=42)
    check("MC2.1 strong strategy fragility < 20%",
          strong["fragility_pct"] < 20,
          f"fragility={strong['fragility_pct']}%")

    # Perfect strategy should have ~0% fragility
    perfect = monte_carlo.strategy_fragility(PERFECT_BETS, N_FIN, n_sims=5000, seed=42)
    check("MC2.2 perfect strategy fragility ≈ 0%",
          perfect["fragility_pct"] < 1.0,
          f"fragility={perfect['fragility_pct']}%")

    # All-loss strategy should have 100% fragility
    terrible = monte_carlo.strategy_fragility(ALL_LOSS_BETS, N_FIN, n_sims=1000, seed=42)
    check("MC2.3 all-loss strategy fragility = 100%",
          terrible["fragility_pct"] == 100.0,
          f"fragility={terrible['fragility_pct']}%")

    # Perfect strategy DD should be 0
    check("MC2.4 perfect strategy DD p95 = 0",
          perfect["dd_p95"] == 0.0,
          f"dd_p95={perfect['dd_p95']}")

    # All-loss strategy ROI should be deeply negative
    check("MC2.5 all-loss strategy ROI mean < 0",
          terrible["roi_mean"] < -50,
          f"roi_mean={terrible['roi_mean']}")

    # Strong strategy ROI mean ≈ actual ROI
    actual_roi = sum(b["pl"] for b in STRONG_BETS) / len(STRONG_BETS) * 100
    check("MC2.6 strong strategy ROI mean ≈ actual ROI (within 5pp)",
          abs(strong["roi_mean"] - actual_roi) < 5.0,
          f"mc_mean={strong['roi_mean']} actual={actual_roi:.1f}")

    # Borderline strategy should have higher fragility than strong
    borderline = monte_carlo.strategy_fragility(BORDERLINE_BETS, N_FIN, n_sims=5000, seed=42)
    check("MC2.7 borderline fragility > strong fragility",
          borderline["fragility_pct"] > strong["fragility_pct"],
          f"borderline={borderline['fragility_pct']}% strong={strong['fragility_pct']}%")


# ─────────────────────────────────────────────────────────────────────────────
# MC3: Portfolio drawdown distribution
# ─────────────────────────────────────────────────────────────────────────────

def test_mc3_drawdown_distribution():
    if not should_run("MC3"):
        return

    dd = monte_carlo.portfolio_drawdown_distribution(STRONG_BETS, n_sims=5000, seed=42)

    # Basic structure
    check("MC3.1 dd result has all expected keys",
          all(k in dd for k in ["n_bets", "actual_dd", "dd_p5", "dd_p50", "dd_p95",
                                 "dd_mean", "actual_percentile"]))

    # Percentiles are ordered (p5 <= p25 <= p50 <= p75 <= p95)
    check("MC3.2 DD percentiles are ordered",
          dd["dd_p5"] <= dd["dd_p25"] <= dd["dd_p50"] <= dd["dd_p75"] <= dd["dd_p95"],
          f"p5={dd['dd_p5']} p25={dd['dd_p25']} p50={dd['dd_p50']} "
          f"p75={dd['dd_p75']} p95={dd['dd_p95']}")

    # All drawdowns are non-negative
    check("MC3.3 all DD percentiles >= 0",
          all(dd[k] >= 0 for k in ["dd_p5", "dd_p25", "dd_p50", "dd_p75", "dd_p95"]))

    # Actual DD is within reasonable range (between p1 and p99 implicitly)
    check("MC3.4 actual DD >= 0",
          dd["actual_dd"] >= 0)

    # Actual percentile is between 0 and 100
    check("MC3.5 actual percentile in [0, 100]",
          0 <= dd["actual_percentile"] <= 100,
          f"percentile={dd['actual_percentile']}")

    # Perfect bets: all wins -> DD should be 0 everywhere
    dd_perfect = monte_carlo.portfolio_drawdown_distribution(PERFECT_BETS, n_sims=1000, seed=42)
    check("MC3.6 perfect bets -> DD p95 = 0",
          dd_perfect["dd_p95"] == 0.0,
          f"dd_p95={dd_perfect['dd_p95']}")

    # All losses: DD should be very high (N-1 because peak starts at first element)
    dd_loss = monte_carlo.portfolio_drawdown_distribution(ALL_LOSS_BETS, n_sims=1000, seed=42)
    n_loss = len(ALL_LOSS_BETS)
    # Peak = first cumsum value (-1), trough = last cumsum value (-N), DD = N-1
    expected_dd = n_loss - 1
    check("MC3.7 all-loss DD p50 = N-1 (peak at first element, trough at last)",
          abs(dd_loss["dd_p50"] - expected_dd) < 0.01,
          f"dd_p50={dd_loss['dd_p50']} expected={expected_dd}")


# ─────────────────────────────────────────────────────────────────────────────
# MC4: Portfolio profit distribution
# ─────────────────────────────────────────────────────────────────────────────

def test_mc4_profit_distribution():
    if not should_run("MC4"):
        return

    profit = monte_carlo.portfolio_profit_distribution(
        STRONG_BETS, bankroll_init=500.0, n_sims=5000, seed=42)

    # Basic structure
    check("MC4.1 profit result has all expected keys",
          all(k in profit for k in ["n_bets", "actual_profit", "profit_p5", "profit_p50",
                                     "profit_p95", "profit_mean", "p_loss", "p_ruin_50pct"]))

    # Percentiles are ordered
    check("MC4.2 profit percentiles are ordered",
          profit["profit_p5"] <= profit["profit_p25"] <= profit["profit_p50"]
          <= profit["profit_p75"] <= profit["profit_p95"],
          f"p5={profit['profit_p5']} p50={profit['profit_p50']} p95={profit['profit_p95']}")

    # P(loss) is between 0 and 100
    check("MC4.3 P(loss) in [0, 100]",
          0 <= profit["p_loss"] <= 100,
          f"p_loss={profit['p_loss']}")

    # P(ruin) is between 0 and 100
    check("MC4.4 P(ruin) in [0, 100]",
          0 <= profit["p_ruin_50pct"] <= 100,
          f"p_ruin={profit['p_ruin_50pct']}")

    # Strong strategy: P(loss) should be low
    check("MC4.5 strong strategy P(loss) < 10%",
          profit["p_loss"] < 10,
          f"p_loss={profit['p_loss']}%")

    # Perfect strategy: P(loss) = 0, P(ruin) = 0
    p_perfect = monte_carlo.portfolio_profit_distribution(
        PERFECT_BETS, bankroll_init=500.0, n_sims=1000, seed=42)
    check("MC4.6 perfect strategy P(loss) = 0%",
          p_perfect["p_loss"] == 0.0,
          f"p_loss={p_perfect['p_loss']}")
    check("MC4.7 perfect strategy P(ruin) = 0%",
          p_perfect["p_ruin_50pct"] == 0.0,
          f"p_ruin={p_perfect['p_ruin_50pct']}")

    # All-loss strategy: P(loss) = 100%
    p_loss = monte_carlo.portfolio_profit_distribution(
        ALL_LOSS_BETS, bankroll_init=500.0, n_sims=1000, seed=42)
    check("MC4.8 all-loss strategy P(loss) = 100%",
          p_loss["p_loss"] == 100.0,
          f"p_loss={p_loss['p_loss']}")


# ─────────────────────────────────────────────────────────────────────────────
# MC5: Edge cases
# ─────────────────────────────────────────────────────────────────────────────

def test_mc5_edge_cases():
    if not should_run("MC5"):
        return

    # Empty bets
    r = monte_carlo.strategy_fragility([], N_FIN, n_sims=100, seed=42)
    check("MC5.1 empty bets -> fragility 100%",
          r["fragility_pct"] == 100.0 and r["n"] == 0)

    dd = monte_carlo.portfolio_drawdown_distribution([], n_sims=100, seed=42)
    check("MC5.2 empty bets -> DD all zeros",
          dd["n_bets"] == 0 and dd["actual_dd"] == 0.0)

    p = monte_carlo.portfolio_profit_distribution([], n_sims=100, seed=42)
    check("MC5.3 empty bets -> P(loss) 100%, P(ruin) 100%",
          p["p_loss"] == 100.0 and p["p_ruin_50pct"] == 100.0)

    # Single bet (win)
    single_win = _make_bets([0.9], [True])
    r1 = monte_carlo.strategy_fragility(single_win, N_FIN, n_sims=100, seed=42)
    check("MC5.4 single winning bet -> fragility 100% (N < min_n)",
          r1["fragility_pct"] == 100.0,
          f"fragility={r1['fragility_pct']}% (N=1 < min_n={monte_carlo._min_n(N_FIN)})")

    dd1 = monte_carlo.portfolio_drawdown_distribution(single_win, n_sims=100, seed=42)
    check("MC5.5 single winning bet -> DD = 0",
          dd1["actual_dd"] == 0.0)

    # Single bet (loss): peak = first element = -1, trough = -1, DD = 0
    # (no drawdown because there's no prior high to draw down from)
    single_loss = _make_bets([-1.0], [False])
    dd2 = monte_carlo.portfolio_drawdown_distribution(single_loss, n_sims=100, seed=42)
    check("MC5.6 single losing bet -> DD = 0 (no prior peak to draw down from)",
          dd2["actual_dd"] == 0.0,
          f"actual_dd={dd2['actual_dd']}")


# ─────────────────────────────────────────────────────────────────────────────
# MC6: Statistical sanity (bootstrap unbiasedness)
# ─────────────────────────────────────────────────────────────────────────────

def test_mc6_statistical_sanity():
    if not should_run("MC6"):
        return

    # Bootstrap mean profit ≈ actual profit (unbiased estimator)
    actual_pl = sum(b["pl"] for b in STRONG_BETS)
    p = monte_carlo.portfolio_profit_distribution(
        STRONG_BETS, n_sims=10000, seed=42)
    check("MC6.1 bootstrap mean profit ≈ actual profit (within 10%)",
          abs(p["profit_mean"] - actual_pl) < abs(actual_pl) * 0.10,
          f"bootstrap_mean={p['profit_mean']} actual={actual_pl}")

    # Bootstrap mean ROI ≈ actual ROI
    actual_roi = actual_pl / len(STRONG_BETS) * 100
    r = monte_carlo.strategy_fragility(STRONG_BETS, N_FIN, n_sims=10000, seed=42)
    check("MC6.2 bootstrap mean ROI ≈ actual ROI (within 3pp)",
          abs(r["roi_mean"] - actual_roi) < 3.0,
          f"bootstrap_mean={r['roi_mean']} actual={actual_roi:.1f}")

    # Bootstrap mean WR ≈ actual WR
    actual_wr = sum(1 for b in STRONG_BETS if b["won"]) / len(STRONG_BETS) * 100
    check("MC6.3 bootstrap mean WR ≈ actual WR (within 3pp)",
          abs(r["wr_mean"] - actual_wr) < 3.0,
          f"bootstrap_mean={r['wr_mean']} actual={actual_wr:.1f}")

    # DD p50 ≈ actual DD for permutations (within reasonable margin)
    dd = monte_carlo.portfolio_drawdown_distribution(
        STRONG_BETS, n_sims=10000, seed=42)
    check("MC6.4 DD mean is positive for mixed-result portfolio",
          dd["dd_mean"] > 0,
          f"dd_mean={dd['dd_mean']}")

    # run_full_analysis produces consistent structure
    report = monte_carlo.run_full_analysis(
        STRONG_BETS, N_FIN, n_sims=1000, seed=42)
    check("MC6.5 run_full_analysis has by_strategy key",
          "by_strategy" in report and "test" in report["by_strategy"])
    check("MC6.6 run_full_analysis has portfolio_drawdown key",
          "portfolio_drawdown" in report)
    check("MC6.7 run_full_analysis has portfolio_profit key",
          "portfolio_profit" in report)
    check("MC6.7b run_full_analysis has goal_sensitivity key",
          "goal_sensitivity" in report)

    # Multi-strategy portfolio groups correctly
    multi_bets = _make_portfolio_bets({
        "strat_a": [(0.9, True)] * 30 + [(-1.0, False)] * 10,
        "strat_b": [(0.5, True)] * 25 + [(-1.0, False)] * 15,
    })
    report2 = monte_carlo.run_full_analysis(multi_bets, N_FIN, n_sims=1000, seed=42)
    check("MC6.8 multi-strategy: both strategies in by_strategy",
          "strat_a" in report2["by_strategy"] and "strat_b" in report2["by_strategy"])
    check("MC6.9 multi-strategy: correct N per strategy",
          report2["by_strategy"]["strat_a"]["n"] == 40
          and report2["by_strategy"]["strat_b"]["n"] == 40,
          f"a={report2['by_strategy']['strat_a']['n']} b={report2['by_strategy']['strat_b']['n']}")
    check("MC6.10 multi-strategy: portfolio DD uses all 80 bets",
          report2["portfolio_drawdown"]["n_bets"] == 80)


# ─────────────────────────────────────────────────────────────────────────────
# MC7: Goal sensitivity
# ─────────────────────────────────────────────────────────────────────────────

def _make_gs_bet(strategy, score_bet, score_final, odds, won, pl, mercado="BACK DRAW"):
    """Helper to build bet dicts for goal sensitivity tests."""
    return {
        "strategy": strategy, "match_id": "test-match",
        "score_bet": score_bet, "score_final": score_final,
        "back_odds": odds, "won": won, "pl": pl,
        "mercado": mercado, "minuto": 70,
    }


def test_mc7_goal_sensitivity():
    if not should_run("MC7"):
        return

    # 1. Draw bet that WON (1-1 -> 1-1): any +1 goal flips -> GOOD_LUCK
    b1 = _make_gs_bet("draw_11", "1-1", "1-1", 3.0, True, 1.90)
    gs = monte_carlo.goal_sensitivity([b1])
    d = gs["by_strategy"]["draw_11"]
    check("MC7.1 draw_11 won at 1-1: edge=0%, good_luck=100%",
          d["edge_pct"] == 0.0 and d["good_luck_pct"] == 100.0,
          f"edge={d['edge_pct']} luck={d['good_luck_pct']}")

    # 2. Draw bet that LOST (1-1 -> 2-1): -1 home restores draw -> BAD_LUCK
    b2 = _make_gs_bet("draw_11", "1-1", "2-1", 3.0, False, -1.0)
    gs2 = monte_carlo.goal_sensitivity([b2])
    d2 = gs2["by_strategy"]["draw_11"]
    check("MC7.2 draw_11 lost at 2-1: bad_luck > 0%",
          d2["bad_luck_pct"] > 0,
          f"bad_luck={d2['bad_luck_pct']}")

    # 3. home_fav_leading WON by 2+ goals (3-0 -> 3-0): -1 home still wins -> EDGE
    b3 = _make_gs_bet("home_fav_leading", "3-0", "3-0", 1.5, True, 0.48,
                       mercado="BACK HOME")
    gs3 = monte_carlo.goal_sensitivity([b3])
    d3 = gs3["by_strategy"]["home_fav_leading"]
    check("MC7.3 home_fav 3-0->3-0: EDGE (survives -1 home)",
          d3["edge_pct"] == 100.0,
          f"edge={d3['edge_pct']}")

    # 4. home_fav_leading WON by 1 goal (1-0 -> 1-0): +1 away flips -> GOOD_LUCK
    b4 = _make_gs_bet("home_fav_leading", "1-0", "1-0", 1.8, True, 0.76,
                       mercado="BACK HOME")
    gs4 = monte_carlo.goal_sensitivity([b4])
    d4 = gs4["by_strategy"]["home_fav_leading"]
    check("MC7.4 home_fav 1-0->1-0: GOOD_LUCK (away+1 flips)",
          d4["good_luck_pct"] == 100.0,
          f"good_luck={d4['good_luck_pct']}")

    # 5. CS bet that WON: always GOOD_LUCK (any goal change breaks CS)
    b5 = _make_gs_bet("cs_close", "2-1", "2-1", 8.0, True, 6.65,
                       mercado="BACK CS")
    gs5 = monte_carlo.goal_sensitivity([b5])
    d5 = gs5["by_strategy"]["cs_close"]
    check("MC7.5 cs_close won at 2-1: always GOOD_LUCK",
          d5["good_luck_pct"] == 100.0,
          f"good_luck={d5['good_luck_pct']}")

    # 6. under35_late WON (3 goals -> 3 goals): +1 goal flips -> GOOD_LUCK
    b6 = _make_gs_bet("under35_late", "3-0", "3-0", 1.5, True, 0.43,
                       mercado="BACK UNDER 3.5")
    gs6 = monte_carlo.goal_sensitivity([b6])
    d6 = gs6["by_strategy"]["under35_late"]
    check("MC7.6 under35 won at 3 goals: GOOD_LUCK (+1 breaks)",
          d6["good_luck_pct"] == 100.0,
          f"good_luck={d6['good_luck_pct']}")

    # 7. Empty bets
    gs_empty = monte_carlo.goal_sensitivity([])
    check("MC7.7 empty bets -> 0 analyzed",
          gs_empty["n_bets_analyzed"] == 0)

    # 8. Unknown strategy is skipped
    b_unk = _make_gs_bet("nonexistent_strategy", "0-0", "1-0", 2.0, False, -1.0)
    gs_unk = monte_carlo.goal_sensitivity([b_unk])
    check("MC7.8 unknown strategy skipped",
          gs_unk["n_bets_analyzed"] == 0)

    # 9. Luck score: for CS bet, actual_pl > expected_pl → luck > 0
    check("MC7.9 CS won has positive luck_score",
          d5["luck_score"] > 0,
          f"luck={d5['luck_score']}")

    # 10. Robustness classification for team bets
    check("MC7.10 home_fav 3-0 -> ROBUST verdict",
          d3["robustness"] == "ROBUST",
          f"robustness={d3['robustness']}")

    # 11. Lay draw won: not_draw — any goal helps maintain non-draw
    b_lay = _make_gs_bet("lay_draw_away_leading", "0-1", "0-1", 2.5, True, 0.95,
                          mercado="LAY DRAW")
    gs_lay = monte_carlo.goal_sensitivity([b_lay])
    d_lay = gs_lay["by_strategy"]["lay_draw_away_leading"]
    check("MC7.11 lay_draw won at 0-1: high edge (most variations stay non-draw)",
          d_lay["edge_pct"] >= 50.0,
          f"edge={d_lay['edge_pct']}")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global VERBOSE, CATEGORY_FILTER

    parser = argparse.ArgumentParser(description="Monte Carlo test suite")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("-k", default=None, help="Category filter (e.g., MC3)")
    args = parser.parse_args()
    VERBOSE = args.verbose
    CATEGORY_FILTER = args.k

    print("=" * 60)
    print("test_monte_carlo.py — Monte Carlo risk analysis tests")
    print("=" * 60)

    test_mc1_determinism()
    test_mc2_strategy_fragility()
    test_mc3_drawdown_distribution()
    test_mc4_profit_distribution()
    test_mc5_edge_cases()
    test_mc6_statistical_sanity()
    test_mc7_goal_sensitivity()

    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    if FAIL > 0:
        print("\nFailed tests:")
        for status, name, detail in _results:
            if status == "FAIL":
                msg = f"  FAIL  {name}"
                if detail:
                    msg += f"  — {detail}"
                print(msg)
    print("=" * 60)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
