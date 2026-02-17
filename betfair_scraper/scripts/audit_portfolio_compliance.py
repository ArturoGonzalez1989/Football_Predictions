#!/usr/bin/env python3
"""
Portfolio Compliance Audit
Checks if historical bets comply with current recommended portfolio configuration.
"""

import csv
from pathlib import Path
from typing import Dict, List, Tuple

# Current recommended configuration (from STRATEGY_VERSIONS_GUIDE.md)
RECOMMENDED_CONFIG = {
    "back_draw_00": "v15",  # V1.5
    "xg_underperformance": "v3",  # V3 (changed today)
    "odds_drift_contrarian": "v1",  # V1
    "goal_clustering": "v2",  # V2
    "pressure_cooker": "v1",  # V1
}

# Version-specific rules
V3_RULES = {
    "xg_underperformance_v3": {
        "max_minute": 70,
        "description": "xG V3 blocks entries at min >= 70",
    },
    "goal_clustering_v3": {
        "max_minute": 75,
        "description": "Goal Clustering V3 blocks entries at min >= 75",
    },
}


def parse_strategy_version(strategy: str) -> Tuple[str, str]:
    """
    Parse strategy name to extract base strategy and version.

    Examples:
    - "xg_underperformance_v2" -> ("xg_underperformance", "v2")
    - "xg_underperformance_base" -> ("xg_underperformance", "base")
    - "back_draw_00_v15" -> ("back_draw_00", "v15")
    """
    parts = strategy.lower().split("_")

    # Check for version suffix
    if parts[-1].startswith("v") or parts[-1] == "base":
        version = parts[-1]
        base = "_".join(parts[:-1])
    else:
        # No version specified, assume v1 or base
        version = "v1"
        base = strategy.lower()

    return base, version


def check_bet_compliance(bet: Dict) -> Tuple[bool, str]:
    """
    Check if a bet complies with current recommended configuration.

    Returns:
        (compliant: bool, reason: str)
    """
    strategy = bet["strategy"]
    minute = int(bet["minute"]) if bet["minute"] else 0

    base_strategy, version_used = parse_strategy_version(strategy)

    # Get recommended version for this strategy
    recommended_version = RECOMMENDED_CONFIG.get(base_strategy)

    if not recommended_version:
        return True, "Strategy not in recommended config"

    # Check if version matches
    if version_used != recommended_version:
        return False, f"Used {version_used.upper()} but recommended is {recommended_version.upper()}"

    # Check version-specific rules
    if strategy == "xg_underperformance_v3" or (base_strategy == "xg_underperformance" and version_used == "v3"):
        max_min = V3_RULES["xg_underperformance_v3"]["max_minute"]
        if minute >= max_min:
            return False, f"V3 blocks min >= {max_min} (bet was at min {minute})"

    if strategy == "goal_clustering_v3" or (base_strategy == "goal_clustering" and version_used == "v3"):
        max_min = V3_RULES["goal_clustering_v3"]["max_minute"]
        if minute >= max_min:
            return False, f"V3 blocks min >= {max_min} (bet was at min {minute})"

    # Special check: xG BASE or V2 when V3 is recommended
    if base_strategy == "xg_underperformance" and recommended_version == "v3":
        if version_used in ["base", "v1", "v2"]:
            # Check if bet would have been blocked by V3
            if minute >= 70:
                return False, f"Used {version_used.upper()} at min {minute} - V3 would have BLOCKED (min >= 70)"

    return True, "Complies with recommended config"


def audit_placed_bets(csv_path: Path):
    """
    Audit all placed bets for compliance with recommended configuration.
    """
    print("=" * 80)
    print("PORTFOLIO COMPLIANCE AUDIT")
    print("=" * 80)
    print()
    print("Current Recommended Configuration:")
    for strategy, version in RECOMMENDED_CONFIG.items():
        print(f"  • {strategy.replace('_', ' ').title()}: {version.upper()}")
    print()
    print("=" * 80)
    print()

    # Read bets
    bets = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bets.append(row)

    # Audit each bet
    non_compliant_bets = []
    compliant_bets = []

    for bet in bets:
        compliant, reason = check_bet_compliance(bet)

        if not compliant:
            non_compliant_bets.append({
                "bet": bet,
                "reason": reason,
            })
        else:
            compliant_bets.append(bet)

    # Report
    print(f"SUMMARY:")
    print(f"  Total bets: {len(bets)}")
    print(f"  Compliant: {len(compliant_bets)} ({len(compliant_bets)/len(bets)*100:.1f}%)")
    print(f"  Non-compliant: {len(non_compliant_bets)} ({len(non_compliant_bets)/len(bets)*100:.1f}%)")
    print()

    if non_compliant_bets:
        print("=" * 80)
        print("NON-COMPLIANT BETS (would be blocked/different under current config):")
        print("=" * 80)
        print()

        total_nc_pl = 0.0

        for i, item in enumerate(non_compliant_bets, 1):
            bet = item["bet"]
            reason = item["reason"]

            pl = float(bet["pl"]) if bet["pl"] else 0.0
            total_nc_pl += pl

            print(f"[{i}] {bet['match_name']}")
            print(f"    Strategy: {bet['strategy_name']}")
            print(f"    Time: {bet['timestamp_utc']} (Min {bet['minute']}')")
            print(f"    Recommendation: {bet['recommendation']}")
            print(f"    Result: {bet['result'].upper() if bet['result'] else 'PENDING'} ({pl:+.2f} EUR)")
            print(f"    [!] ISSUE: {reason}")
            print()

        print("=" * 80)
        print(f"IMPACT OF NON-COMPLIANT BETS:")
        print(f"  Total P/L from non-compliant bets: {total_nc_pl:+.2f} EUR")
        print()

        # Check how many would have been blocked
        blocked_count = sum(1 for item in non_compliant_bets if "would have BLOCKED" in item["reason"])
        if blocked_count > 0:
            blocked_pl = sum(
                float(item["bet"]["pl"]) if item["bet"]["pl"] else 0.0
                for item in non_compliant_bets
                if "would have BLOCKED" in item["reason"]
            )
            print(f"  Bets that would have been BLOCKED by V3: {blocked_count}")
            print(f"  P/L that would have been PREVENTED: {blocked_pl:+.2f} EUR")
            print()

        # Calculate what P/L would have been with compliant config
        total_pl = sum(float(bet["pl"]) for bet in bets if bet["pl"])
        hypothetical_pl = total_pl - total_nc_pl

        print(f"  Actual P/L (all bets): {total_pl:+.2f} EUR")
        print(f"  Hypothetical P/L (only compliant bets): {hypothetical_pl:+.2f} EUR")
        print(f"  Difference: {hypothetical_pl - total_pl:+.2f} EUR")
        print()
    else:
        print("[OK] All bets comply with current recommended configuration!")
        print()

    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Audit portfolio compliance")
    parser.add_argument(
        "--placed-bets",
        type=Path,
        default=Path(__file__).parent.parent / "placed_bets.csv",
        help="Path to placed_bets.csv"
    )

    args = parser.parse_args()

    if not args.placed_bets.exists():
        print(f"[ERROR] {args.placed_bets} not found")
        exit(1)

    audit_placed_bets(args.placed_bets)
