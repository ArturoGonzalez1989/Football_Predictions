"""
Realistic validation layer for SD strategy backtests.

Applies the same realistic adjustments as the BT notebook pipeline
(optimize.py:_apply_realistic_adj) and checks quality gates so the
strategy-designer agent sees results closer to production reality.

Usage:
  python aux/sd_validate_realistic.py --file aux/sd_bt_results.json
  python aux/sd_validate_realistic.py < raw_bets.json
  python aux/sd_validate_realistic.py --file bets.json --n-matches 850

Input:  JSON with a "bets" array (or top-level array) of bet dicts.
        Each bet needs: won, pl, odds, match_id, timestamp, minuto.
        Optional: bet_type (back|lay), strategy.

Output: JSON to stdout with raw vs realistic comparison + gate verdicts.
"""

import argparse
import json
import math
import sys


# ── Realistic adjustment defaults (mirror notebook G_ADJ) ──────────────

DEFAULT_ADJ = {
    "minOdds": 1.05,
    "maxOdds": 10.0,
    "slippagePct": 2,
    "dedup": True,
    "minStability": 1,       # SD strategies are one-shot triggers
}

# ── Quality gates (mirror notebook) ────────────────────────────────────

DEFAULT_MIN_ROI = 10.0       # G_MIN_ROI
DEFAULT_IC95_LOW = 40.0      # IC95_MIN_LOW
STAKE = 10.0


# ── Stats helpers ──────────────────────────────────────────────────────

def wilson_ci95(n, wins):
    if n == 0:
        return 0.0, 0.0
    z = 1.96
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0, centre - margin) * 100, 1),
            round(min(1, centre + margin) * 100, 1))


def max_drawdown(pls):
    cum = peak = dd = 0
    for pl in pls:
        cum += pl
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return round(dd, 2)


def sharpe_ratio(pls):
    if len(pls) < 2:
        return 0.0
    mean = sum(pls) / len(pls)
    var = sum((p - mean) ** 2 for p in pls) / (len(pls) - 1)
    std = math.sqrt(var) if var > 0 else 0.001
    return round(mean / std * math.sqrt(len(pls)), 2)


def compute_stats(bets):
    if not bets:
        return {"n": 0, "wins": 0, "wr": 0, "roi": 0, "pl": 0,
                "ci95_low": 0, "ci95_high": 0, "max_dd": 0, "sharpe": 0,
                "avg_odds": 0, "train_roi": 0, "test_roi": 0}
    n = len(bets)
    wins = sum(1 for b in bets if b.get("won"))
    wr = round(wins / n * 100, 1)
    total_pl = round(sum(b.get("pl", 0) for b in bets), 2)
    roi = round(total_pl / (n * STAKE) * 100, 1)
    avg_odds = round(sum(b.get("odds", 1) for b in bets) / n, 2)
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b.get("pl", 0) for b in bets]

    # Train/test split 70/30 chronological
    sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
    split = int(len(sorted_b) * 0.7)
    train, test = sorted_b[:split], sorted_b[split:]
    train_pl = sum(b.get("pl", 0) for b in train)
    test_pl = sum(b.get("pl", 0) for b in test)
    train_roi = round(train_pl / (len(train) * STAKE) * 100, 1) if train else 0
    test_roi = round(test_pl / (len(test) * STAKE) * 100, 1) if test else 0

    return {
        "n": n, "wins": wins, "wr": wr, "roi": roi, "pl": total_pl,
        "ci95_low": ci_lo, "ci95_high": ci_hi,
        "max_dd": max_drawdown(pls), "sharpe": sharpe_ratio(pls),
        "avg_odds": avg_odds,
        "train_roi": train_roi, "test_roi": test_roi,
    }


# ── Realistic adjustments (mirrors optimize.py) ───────────────────────

def _apply_realistic_adj(bets, adj):
    """Apply realistic filters. Same order as optimize.py."""
    result = list(bets)

    # 1. Max odds filter
    max_odds = adj.get("maxOdds")
    if max_odds is not None:
        result = [b for b in result if b.get("odds", 1) <= max_odds]

    # 2. Min odds filter
    min_odds = adj.get("minOdds")
    if min_odds is not None:
        result = [b for b in result if b.get("odds", 1) >= min_odds]

    # 3. Dedup (keep first chronologically per match)
    if adj.get("dedup"):
        seen = set()
        deduped = []
        for b in sorted(result, key=lambda x: x.get("timestamp", "")):
            key = b.get("match_id", "")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(b)
        result = deduped

    # 4. Slippage (BACK wins only — 2% odds reduction)
    slippage_pct = adj.get("slippagePct", 0)
    if slippage_pct and slippage_pct > 0:
        factor = 1.0 - slippage_pct / 100.0
        adjusted = []
        for b in result:
            bet_type = b.get("bet_type", "back")
            if bet_type == "lay" or not b.get("won"):
                adjusted.append(b)
                continue
            adj_odds = round(b.get("odds", 1) * factor, 2)
            new_pl = round((adj_odds - 1.0) * STAKE * 0.95, 2)
            nb = dict(b)
            nb["pl"] = new_pl
            nb["odds_adjusted"] = adj_odds
            adjusted.append(nb)
        result = adjusted

    return result


# ── Main ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SD realistic validator")
    parser.add_argument("--file", "-f", help="JSON file with bets")
    parser.add_argument("--n-matches", type=int, default=850,
                        help="Total matches in dataset (for dynamic min_bets)")
    parser.add_argument("--min-roi", type=float, default=DEFAULT_MIN_ROI)
    parser.add_argument("--ic95-low", type=float, default=DEFAULT_IC95_LOW)
    parser.add_argument("--adj", help="JSON string with custom adjustments")
    args = parser.parse_args()

    # Load bets
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    # Accept top-level array or {"bets": [...]}
    if isinstance(data, list):
        bets = data
    elif isinstance(data, dict):
        # Try multiple keys the sub-backtest-runner might use
        bets = data.get("bets") or data.get("param_results", [{}])[0].get("bets", [])
        if not bets and "match_ids" in data:
            print(json.dumps({"error": "Input has match_ids but no bets array. "
                              "Re-run backtest with --export-bets flag."}))
            sys.exit(1)
    else:
        print(json.dumps({"error": "Invalid input format"}))
        sys.exit(1)

    if not bets:
        print(json.dumps({"error": "No bets found in input"}))
        sys.exit(1)

    # Adjustments
    adj = dict(DEFAULT_ADJ)
    if args.adj:
        adj.update(json.loads(args.adj))

    # Dynamic min_bets: max(15, n_matches // 25)
    min_bets = max(15, args.n_matches // 25)

    # Raw stats
    raw = compute_stats(bets)

    # Apply realistic adjustments
    realistic_bets = _apply_realistic_adj(bets, adj)
    real = compute_stats(realistic_bets)

    # Quality gates (on realistic stats)
    gates = {
        "min_n": {
            "required": min_bets,
            "actual": real["n"],
            "pass": real["n"] >= min_bets,
        },
        "min_roi": {
            "required": args.min_roi,
            "actual": real["roi"],
            "pass": real["roi"] >= args.min_roi,
        },
        "ic95_low": {
            "required": args.ic95_low,
            "actual": real["ci95_low"],
            "pass": real["ci95_low"] >= args.ic95_low,
        },
        "train_roi_positive": {
            "required": "> 0",
            "actual": real["train_roi"],
            "pass": real["train_roi"] > 0,
        },
        "test_roi_positive": {
            "required": "> 0",
            "actual": real["test_roi"],
            "pass": real["test_roi"] > 0,
        },
    }

    verdict = "PASS" if all(g["pass"] for g in gates.values()) else "FAIL"
    failed = [k for k, g in gates.items() if not g["pass"]]

    # Delta
    delta = {
        "n": real["n"] - raw["n"],
        "wr": round(real["wr"] - raw["wr"], 1),
        "roi": round(real["roi"] - raw["roi"], 1),
        "pl": round(real["pl"] - raw["pl"], 2),
    }

    output = {
        "raw": raw,
        "realistic": real,
        "delta": delta,
        "adjustments_applied": adj,
        "gates": gates,
        "verdict": verdict,
        "failed_gates": failed,
        "n_matches_dataset": args.n_matches,
        "min_bets_dynamic": min_bets,
    }

    # Human-readable summary to stderr
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  SD REALISTIC VALIDATION", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"  Raw:       N={raw['n']}, WR={raw['wr']}%, ROI={raw['roi']}%, "
          f"P/L={raw['pl']}, MaxDD={raw['max_dd']}", file=sys.stderr)
    print(f"  Realistic: N={real['n']}, WR={real['wr']}%, ROI={real['roi']}%, "
          f"P/L={real['pl']}, MaxDD={real['max_dd']}", file=sys.stderr)
    print(f"  Delta:     N={delta['n']}, WR={delta['wr']}pp, "
          f"ROI={delta['roi']}pp, P/L={delta['pl']}", file=sys.stderr)
    print(f"  Slippage:  {adj.get('slippagePct', 0)}% | "
          f"Odds: [{adj.get('minOdds', '-')}, {adj.get('maxOdds', '-')}] | "
          f"Dedup: {adj.get('dedup', False)}", file=sys.stderr)
    print(f"\n  Quality Gates ({verdict}):", file=sys.stderr)
    for name, g in gates.items():
        status = "PASS" if g["pass"] else "FAIL"
        print(f"    [{status}] {name}: {g['actual']} "
              f"(required: {g['required']})", file=sys.stderr)
    if failed:
        print(f"\n  FAILED: {', '.join(failed)}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    # JSON to stdout
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
