#!/usr/bin/env python3
"""
Clean Placed Bets
Remove non-compliant and duplicate bets from placed_bets.csv
"""

import csv
from pathlib import Path
from typing import Dict, List, Tuple
import shutil
from datetime import datetime

# Current recommended configuration
RECOMMENDED_CONFIG = {
    "back_draw_00": "v15",
    "xg_underperformance": "v3",
    "odds_drift_contrarian": "v1",
    "goal_clustering": "v2",
    "pressure_cooker": "v1",
}


def parse_strategy_version(strategy: str) -> Tuple[str, str]:
    """Parse strategy to extract base and version."""
    parts = strategy.lower().split("_")
    if parts[-1].startswith("v") or parts[-1] == "base":
        version = parts[-1]
        base = "_".join(parts[:-1])
    else:
        version = "v1"
        base = strategy.lower()
    return base, version


def parse_bet_type(recommendation: str) -> str:
    """
    Parse bet type from recommendation.
    Examples:
    - "BACK DRAW @ 2.28" -> "DRAW"
    - "BACK Over 2.5" -> "OVER_2.5"
    - "BACK HOME @ 2.06" -> "HOME"
    """
    if not recommendation:
        return "UNKNOWN"

    rec = recommendation.upper()

    if "DRAW" in rec or "EMPATE" in rec:
        return "DRAW"

    if "OVER" in rec:
        import re
        match = re.search(r"OVER\s+(\d+\.?\d*)", rec)
        return f"OVER_{match.group(1)}" if match else "OVER"

    if "UNDER" in rec:
        import re
        match = re.search(r"UNDER\s+(\d+\.?\d*)", rec)
        return f"UNDER_{match.group(1)}" if match else "UNDER"

    if "HOME" in rec or "LOCAL" in rec:
        return "HOME"

    if "AWAY" in rec or "VISITANTE" in rec:
        return "AWAY"

    return "UNKNOWN"


def should_keep_bet(bet: Dict) -> Tuple[bool, str]:
    """
    Determine if a bet should be kept based on compliance rules.

    Returns:
        (keep: bool, reason: str)
    """
    strategy = bet["strategy"]
    minute = int(bet["minute"]) if bet["minute"] else 0

    base_strategy, version_used = parse_strategy_version(strategy)

    # Get recommended version
    recommended_version = RECOMMENDED_CONFIG.get(base_strategy)

    if not recommended_version:
        return True, "Not in portfolio config"

    # Rule 1: Version must match
    if version_used != recommended_version:
        # Special case: xG V3 blocks min >= 70
        if base_strategy == "xg_underperformance" and recommended_version == "v3":
            if version_used in ["base", "v1", "v2"] and minute >= 70:
                return False, f"xG {version_used.upper()} at min {minute} - V3 would block (>= 70)"
            else:
                return False, f"Used {version_used.upper()} but recommended is {recommended_version.upper()}"

        return False, f"Used {version_used.upper()} but recommended is {recommended_version.upper()}"

    # Rule 2: xG V3 must be < 70 min
    if base_strategy == "xg_underperformance" and version_used == "v3" and minute >= 70:
        return False, f"xG V3 at min {minute} exceeds limit (>= 70)"

    # Rule 3: Goal Clustering V3 must be < 75 min
    if base_strategy == "goal_clustering" and version_used == "v3" and minute >= 75:
        return False, f"Goal Clustering V3 at min {minute} exceeds limit (>= 75)"

    return True, "Complies"


def find_duplicates(bets: List[Dict]) -> List[int]:
    """
    Find duplicate bets (same match + same bet type).

    Returns:
        List of bet IDs to remove (keeps earliest bet)
    """
    seen = {}  # (match_id, bet_type) -> bet_id
    duplicates = []

    for bet in bets:
        match_id = bet["match_id"]
        bet_type = parse_bet_type(bet["recommendation"])
        key = (match_id, bet_type)

        if key in seen:
            # Duplicate found - mark later one for removal
            duplicates.append(int(bet["id"]))
            print(f"  [DUPLICATE] Bet #{bet['id']} ({bet['match_name']} - {bet_type})")
            print(f"              First bet: #{seen[key]}")
        else:
            seen[key] = int(bet["id"])

    return duplicates


def clean_placed_bets(csv_path: Path, dry_run: bool = False):
    """
    Clean placed_bets.csv by removing non-compliant and duplicate bets.
    """
    print("=" * 80)
    print("CLEANING PLACED BETS")
    print("=" * 80)
    print()

    # Skip backup as requested by user
    backup_path = None

    # Read all bets
    bets = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            bets.append(row)

    print(f"[*] Total bets before cleaning: {len(bets)}")
    print()

    # Step 1: Find duplicates
    print("=" * 80)
    print("STEP 1: FINDING DUPLICATES")
    print("=" * 80)
    duplicates_to_remove = find_duplicates(bets)
    print(f"\n[*] Found {len(duplicates_to_remove)} duplicate bets to remove")
    print()

    # Step 2: Check compliance
    print("=" * 80)
    print("STEP 2: CHECKING COMPLIANCE")
    print("=" * 80)
    non_compliant = []
    for bet in bets:
        keep, reason = should_keep_bet(bet)
        if not keep:
            non_compliant.append((int(bet["id"]), bet, reason))
            print(f"  [NON-COMPLIANT] Bet #{bet['id']}: {bet['match_name']}")
            print(f"                  Strategy: {bet['strategy_name']} (Min {bet['minute']}')")
            print(f"                  Reason: {reason}")
            print(f"                  Result: {bet['result'].upper() if bet['result'] else 'PENDING'} ({bet['pl']} EUR)")
            print()

    print(f"[*] Found {len(non_compliant)} non-compliant bets to remove")
    print()

    # Combine IDs to remove
    ids_to_remove = set(duplicates_to_remove)
    ids_to_remove.update([bet_id for bet_id, _, _ in non_compliant])

    # Filter bets
    bets_to_keep = [bet for bet in bets if int(bet["id"]) not in ids_to_remove]

    # Calculate impact
    print("=" * 80)
    print("IMPACT ANALYSIS")
    print("=" * 80)

    removed_pl = sum(float(bet["pl"]) for bet in bets if int(bet["id"]) in ids_to_remove and bet["pl"])
    kept_pl = sum(float(bet["pl"]) for bet in bets_to_keep if bet["pl"])

    print(f"  Bets before: {len(bets)}")
    print(f"  Bets after: {len(bets_to_keep)}")
    print(f"  Bets removed: {len(ids_to_remove)}")
    print()
    print(f"  P/L before: {sum(float(b['pl']) for b in bets if b['pl']):+.2f} EUR")
    print(f"  P/L after: {kept_pl:+.2f} EUR")
    print(f"  P/L from removed bets: {removed_pl:+.2f} EUR")
    print()

    # Win rate analysis
    kept_wins = sum(1 for bet in bets_to_keep if bet["result"] == "won")
    kept_losses = sum(1 for bet in bets_to_keep if bet["result"] == "lost")
    kept_total = kept_wins + kept_losses

    if kept_total > 0:
        print(f"  Win Rate after cleaning: {kept_wins}/{kept_total} = {kept_wins/kept_total*100:.1f}%")
    print()

    # Write cleaned CSV
    if dry_run:
        print("[DRY RUN] No changes written to file")
        print()
        print("Bets that would be removed:")
        for bet_id in sorted(ids_to_remove):
            bet = next(b for b in bets if int(b["id"]) == bet_id)
            print(f"  #{bet_id}: {bet['match_name']} - {bet['strategy_name']} ({bet['result']}: {bet['pl']} EUR)")
    else:
        with open(csv_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(bets_to_keep)

        print(f"[SAVED] Cleaned CSV written to: {csv_path}")

    print()
    print("=" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean placed_bets.csv")
    parser.add_argument(
        "--placed-bets",
        type=Path,
        default=Path(__file__).parent.parent / "placed_bets.csv",
        help="Path to placed_bets.csv"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying file"
    )

    args = parser.parse_args()

    if not args.placed_bets.exists():
        print(f"[ERROR] {args.placed_bets} not found")
        exit(1)

    clean_placed_bets(args.placed_bets, args.dry_run)
