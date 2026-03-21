"""
monte_carlo.py — Monte Carlo risk analysis for the Furbo betting portfolio.

Pure analysis module: receives lists of bets, returns distributions and metrics.
Does NOT modify any config or data files.

Three analyses:
  1. Strategy fragility (bootstrap): resample each strategy's bets with replacement,
     check how often quality gates still pass.
  2. Portfolio drawdown distribution (permutation): shuffle bet order, compute
     max drawdown for each permutation → percentile distribution.
  3. Portfolio profit distribution (bootstrap): resample portfolio bets with
     replacement → profit percentiles + P(loss) + P(ruin).

Usage standalone:
    python scripts/monte_carlo.py                    # run on current cartera_config
    python scripts/monte_carlo.py --sims 5000        # custom simulation count
    python scripts/monte_carlo.py --seed 123         # reproducible results
"""

import sys
import math
import json
import time
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "betfair_scraper" / "dashboard" / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(ROOT / "betfair_scraper"))

# ── Quality gate constants (same as bt_optimizer.py) ──────────────────────────
G_MIN_ROI = 10.0
IC95_MIN_LOW = 40.0


def _wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (
        round(max(0.0, center - margin) * 100, 1),
        round(min(1.0, center + margin) * 100, 1),
    )


def _min_n(n_fin: int) -> int:
    return max(15, n_fin // 25)


def _min_pl_per_bet(n_fin: int) -> float:
    return min(0.30, 0.10 + n_fin / 10000)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Strategy fragility (bootstrap)
# ─────────────────────────────────────────────────────────────────────────────

def strategy_fragility(
    bets: list[dict],
    n_fin: int,
    n_sims: int = 10_000,
    seed: int = 42,
) -> dict:
    """Bootstrap resample a single strategy's bets and check quality gate pass rate.

    Args:
        bets: list of bet dicts with at least {"won": bool, "pl": float}
        n_fin: total number of finished matches (for dynamic quality gates)
        n_sims: number of bootstrap resamples
        seed: random seed for reproducibility

    Returns:
        {
            "n": int,                   # original bet count
            "fragility_pct": float,     # % of resamples that FAIL quality gates (0-100)
            "roi_mean": float,          # mean ROI across resamples
            "roi_p5": float,            # 5th percentile ROI
            "roi_p50": float,           # median ROI
            "roi_p95": float,           # 95th percentile ROI
            "wr_mean": float,           # mean win rate across resamples
            "dd_p50": float,            # median max drawdown
            "dd_p95": float,            # 95th percentile max drawdown (worst realistic)
        }
    """
    n = len(bets)
    if n == 0:
        return {
            "n": 0, "fragility_pct": 100.0,
            "roi_mean": 0.0, "roi_p5": 0.0, "roi_p50": 0.0, "roi_p95": 0.0,
            "wr_mean": 0.0, "dd_p50": 0.0, "dd_p95": 0.0,
        }

    rng = np.random.default_rng(seed)

    # Pre-extract arrays for vectorized resampling
    pls = np.array([b["pl"] for b in bets], dtype=np.float64)
    wons = np.array([1 if b["won"] else 0 for b in bets], dtype=np.int32)

    min_n = _min_n(n_fin)
    min_pl = _min_pl_per_bet(n_fin)

    # Generate all resample indices at once: (n_sims, n)
    indices = rng.integers(0, n, size=(n_sims, n))

    # Vectorized resampling
    sim_pls = pls[indices]       # (n_sims, n)
    sim_wons = wons[indices]     # (n_sims, n)

    # Metrics per simulation
    total_pl = sim_pls.sum(axis=1)          # (n_sims,)
    total_wins = sim_wons.sum(axis=1)       # (n_sims,)
    rois = total_pl / n * 100               # (n_sims,)
    wrs = total_wins / n * 100              # (n_sims,)

    # Wilson CI lower bound (vectorized)
    p = total_wins / n
    z = 1.96
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    ci_lows = np.clip(center - margin, 0.0, 1.0) * 100

    # Quality gate check per simulation
    passes = (
        (n >= min_n)
        & (rois >= G_MIN_ROI)
        & (total_pl / n >= min_pl)
        & (ci_lows >= IC95_MIN_LOW)
    )
    fail_pct = round((1.0 - passes.mean()) * 100, 1)

    # Max drawdown per simulation
    cum_pl = np.cumsum(sim_pls, axis=1)     # (n_sims, n)
    running_peak = np.maximum.accumulate(cum_pl, axis=1)
    drawdowns = running_peak - cum_pl       # always >= 0
    max_dds = drawdowns.max(axis=1)         # (n_sims,)

    return {
        "n": n,
        "fragility_pct": fail_pct,
        "roi_mean": round(float(rois.mean()), 1),
        "roi_p5": round(float(np.percentile(rois, 5)), 1),
        "roi_p50": round(float(np.percentile(rois, 50)), 1),
        "roi_p95": round(float(np.percentile(rois, 95)), 1),
        "wr_mean": round(float(wrs.mean()), 1),
        "dd_p50": round(float(np.percentile(max_dds, 50)), 2),
        "dd_p95": round(float(np.percentile(max_dds, 95)), 2),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Portfolio drawdown distribution (permutation)
# ─────────────────────────────────────────────────────────────────────────────

def portfolio_drawdown_distribution(
    bets: list[dict],
    n_sims: int = 10_000,
    seed: int = 42,
) -> dict:
    """Permute bet order and compute max drawdown distribution.

    Args:
        bets: list of bet dicts with at least {"pl": float}
        n_sims: number of permutations
        seed: random seed

    Returns:
        {
            "n_bets": int,
            "actual_dd": float,         # max DD of the actual (chronological) sequence
            "dd_p5": float,             # 5th percentile (worst realistic)
            "dd_p25": float,
            "dd_p50": float,            # median
            "dd_p75": float,
            "dd_p95": float,            # 95th percentile (best realistic)
            "dd_mean": float,
            "actual_percentile": float, # where the actual DD falls in the distribution
        }
    """
    n = len(bets)
    if n == 0:
        return {
            "n_bets": 0, "actual_dd": 0.0,
            "dd_p5": 0.0, "dd_p25": 0.0, "dd_p50": 0.0, "dd_p75": 0.0,
            "dd_p95": 0.0, "dd_mean": 0.0, "actual_percentile": 0.0,
        }

    rng = np.random.default_rng(seed)
    pls = np.array([b["pl"] for b in bets], dtype=np.float64)

    # Actual (chronological) max drawdown
    cum = np.cumsum(pls)
    peak = np.maximum.accumulate(cum)
    actual_dd = float((peak - cum).max())

    # Permutation simulations
    max_dds = np.empty(n_sims, dtype=np.float64)
    for i in range(n_sims):
        shuffled = rng.permutation(pls)
        cum_s = np.cumsum(shuffled)
        peak_s = np.maximum.accumulate(cum_s)
        max_dds[i] = (peak_s - cum_s).max()

    # Where does actual DD fall in the distribution?
    # Higher percentile = actual DD is worse than most permutations
    actual_pct = float(np.searchsorted(np.sort(max_dds), actual_dd) / n_sims * 100)

    return {
        "n_bets": n,
        "actual_dd": round(actual_dd, 2),
        "dd_p5": round(float(np.percentile(max_dds, 5)), 2),
        "dd_p25": round(float(np.percentile(max_dds, 25)), 2),
        "dd_p50": round(float(np.percentile(max_dds, 50)), 2),
        "dd_p75": round(float(np.percentile(max_dds, 75)), 2),
        "dd_p95": round(float(np.percentile(max_dds, 95)), 2),
        "dd_mean": round(float(max_dds.mean()), 2),
        "actual_percentile": round(actual_pct, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Portfolio profit distribution (bootstrap)
# ─────────────────────────────────────────────────────────────────────────────

def portfolio_profit_distribution(
    bets: list[dict],
    bankroll_init: float = 500.0,
    n_sims: int = 10_000,
    seed: int = 42,
) -> dict:
    """Bootstrap resample portfolio bets → profit distribution + ruin probability.

    Args:
        bets: list of bet dicts with at least {"pl": float}
        bankroll_init: initial bankroll in £ (for ruin calculation)
        n_sims: number of bootstrap resamples
        seed: random seed

    Returns:
        {
            "n_bets": int,
            "actual_profit": float,
            "profit_p5": float,
            "profit_p25": float,
            "profit_p50": float,
            "profit_p75": float,
            "profit_p95": float,
            "profit_mean": float,
            "p_loss": float,            # P(total profit < 0) as percentage
            "p_ruin_50pct": float,      # P(bankroll drops below 50% at any point)
        }
    """
    n = len(bets)
    if n == 0:
        return {
            "n_bets": 0, "actual_profit": 0.0,
            "profit_p5": 0.0, "profit_p25": 0.0, "profit_p50": 0.0,
            "profit_p75": 0.0, "profit_p95": 0.0, "profit_mean": 0.0,
            "p_loss": 100.0, "p_ruin_50pct": 100.0,
        }

    rng = np.random.default_rng(seed)
    pls = np.array([b["pl"] for b in bets], dtype=np.float64)

    actual_profit = float(pls.sum())

    # Generate all resample indices at once
    indices = rng.integers(0, n, size=(n_sims, n))
    sim_pls = pls[indices]  # (n_sims, n)

    # Final profits
    final_profits = sim_pls.sum(axis=1)  # (n_sims,)

    # P(loss)
    p_loss = float((final_profits < 0).mean() * 100)

    # P(ruin): bankroll drops below 50% of initial at any point
    # Using flat £10 stake (same as analyze_cartera flat staking)
    sim_pls_scaled = sim_pls * 10.0  # scale from per-£1 to per-£10 stake
    cum_pl = np.cumsum(sim_pls_scaled, axis=1)
    bankroll_curve = bankroll_init + cum_pl  # (n_sims, n)
    ruin_threshold = bankroll_init * 0.5
    hit_ruin = (bankroll_curve.min(axis=1) < ruin_threshold)
    p_ruin = float(hit_ruin.mean() * 100)

    return {
        "n_bets": n,
        "actual_profit": round(actual_profit, 2),
        "profit_p5": round(float(np.percentile(final_profits, 5)), 2),
        "profit_p25": round(float(np.percentile(final_profits, 25)), 2),
        "profit_p50": round(float(np.percentile(final_profits, 50)), 2),
        "profit_p75": round(float(np.percentile(final_profits, 75)), 2),
        "profit_p95": round(float(np.percentile(final_profits, 95)), 2),
        "profit_mean": round(float(final_profits.mean()), 2),
        "p_loss": round(p_loss, 1),
        "p_ruin_50pct": round(p_ruin, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Full report: combines all three analyses
# ─────────────────────────────────────────────────────────────────────────────

def run_full_analysis(
    bets: list[dict],
    n_fin: int,
    bankroll_init: float = 500.0,
    n_sims: int = 10_000,
    seed: int = 42,
) -> dict:
    """Run complete Monte Carlo analysis on a portfolio of bets.

    Args:
        bets: list of bet dicts (from analyze_cartera or bt_optimizer)
        n_fin: total finished matches (for quality gate thresholds)
        bankroll_init: initial bankroll in £
        n_sims: simulations per analysis
        seed: random seed

    Returns:
        {
            "timestamp": str,
            "n_sims": int,
            "seed": int,
            "n_fin": int,
            "by_strategy": { "strategy_key": { fragility metrics }, ... },
            "portfolio_drawdown": { DD distribution },
            "portfolio_profit": { profit distribution },
        }
    """
    # Group bets by strategy
    by_strat: dict[str, list] = {}
    for b in bets:
        key = b.get("strategy", "unknown")
        by_strat.setdefault(key, []).append(b)

    # 1. Strategy fragility
    strat_results = {}
    for key, strat_bets in sorted(by_strat.items()):
        strat_results[key] = strategy_fragility(
            strat_bets, n_fin, n_sims=n_sims, seed=seed,
        )

    # 2. Portfolio drawdown distribution
    dd_dist = portfolio_drawdown_distribution(bets, n_sims=n_sims, seed=seed)

    # 3. Portfolio profit distribution
    profit_dist = portfolio_profit_distribution(
        bets, bankroll_init=bankroll_init, n_sims=n_sims, seed=seed,
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "n_sims": n_sims,
        "seed": seed,
        "n_fin": n_fin,
        "by_strategy": strat_results,
        "portfolio_drawdown": dd_dist,
        "portfolio_profit": profit_dist,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Console output formatting
# ─────────────────────────────────────────────────────────────────────────────

def print_report(report: dict):
    """Print Monte Carlo report to console in a readable table format."""
    strats = report.get("by_strategy", {})
    dd = report.get("portfolio_drawdown", {})
    profit = report.get("portfolio_profit", {})

    n_sims = report.get("n_sims", 0)
    print(f"\n  Strategy Robustness ({n_sims:,} bootstrap resamples):")
    print(f"  {'Strategy':<28} {'N':>5} {'ROI%':>6} {'Fragil%':>8} "
          f"{'ROI p5':>7} {'ROI p95':>8} {'DD p95':>7}")
    print(f"  {'-'*72}")

    for key, m in sorted(strats.items(), key=lambda x: x[1]["fragility_pct"]):
        frag_marker = " !" if m["fragility_pct"] >= 30 else ""
        print(f"  {key:<28} {m['n']:>5} {m['roi_mean']:>+5.1f}% "
              f"{m['fragility_pct']:>7.1f}%{frag_marker}"
              f"{m['roi_p5']:>+7.1f} {m['roi_p95']:>+7.1f}  "
              f"{m['dd_p95']:>6.2f}")

    print(f"\n  Portfolio Drawdown ({n_sims:,} permutations):")
    print(f"    p5 (worst realistic):  {dd.get('dd_p95', 0):.2f}")
    print(f"    p25:                   {dd.get('dd_p75', 0):.2f}")
    print(f"    p50 (median):          {dd.get('dd_p50', 0):.2f}")
    print(f"    p75:                   {dd.get('dd_p25', 0):.2f}")
    print(f"    p95 (best realistic):  {dd.get('dd_p5', 0):.2f}")
    print(f"    Actual (historical):   {dd.get('actual_dd', 0):.2f}  "
          f"(percentile {dd.get('actual_percentile', 0):.0f})")

    print(f"\n  Portfolio Profit ({n_sims:,} bootstrap resamples):")
    print(f"    p5:          {profit.get('profit_p5', 0):+.2f}")
    print(f"    p50 (median):{profit.get('profit_p50', 0):+.2f}")
    print(f"    p95:         {profit.get('profit_p95', 0):+.2f}")
    print(f"    P(loss):     {profit.get('p_loss', 0):.1f}%")
    print(f"    P(ruin<50%): {profit.get('p_ruin_50pct', 0):.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point (standalone)
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Monte Carlo risk analysis")
    parser.add_argument("--sims", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bankroll", type=float, default=500.0)
    args = parser.parse_args()

    from utils import csv_reader
    from utils.csv_loader import _get_all_finished_matches

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Monte Carlo — "
          f"loading portfolio…")
    t0 = time.time()

    csv_reader.clear_analytics_cache()
    data = csv_reader.analyze_cartera()
    bets = data.get("bets", [])
    matches = _get_all_finished_matches()
    n_fin = len(matches)

    print(f"  {len(bets)} bets, {n_fin} matches loaded in {time.time()-t0:.1f}s")
    print(f"  Running {args.sims:,} simulations (seed={args.seed})…")

    t0 = time.time()
    report = run_full_analysis(
        bets, n_fin,
        bankroll_init=args.bankroll,
        n_sims=args.sims,
        seed=args.seed,
    )
    elapsed = time.time() - t0

    print_report(report)
    print(f"\n  Monte Carlo completed in {elapsed:.1f}s")

    # Save to auxiliar
    out_path = ROOT / "auxiliar" / "mc_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"  Report saved → {out_path.name}")


if __name__ == "__main__":
    main()