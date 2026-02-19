#!/usr/bin/env python3
"""
Automatic Bet Resolver
Resolves pending bets by checking final match scores from CSV files.
"""

import csv
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_recommendation(rec: str) -> Tuple[str, Optional[float]]:
    """
    Parse recommendation string to extract bet type and threshold.

    Examples:
    - "BACK DRAW @ 2.28" -> ("DRAW", None)
    - "BACK Over 2.5" -> ("OVER", 2.5)
    - "BACK HOME @ 2.06" -> ("HOME", None)
    - "BACK AWAY @ 2.00" -> ("AWAY", None)
    """
    rec_upper = rec.upper().strip()

    if "DRAW" in rec_upper:
        return ("DRAW", None)
    elif "OVER" in rec_upper:
        match = re.search(r"OVER\s+(\d+\.?\d*)", rec_upper)
        if match:
            return ("OVER", float(match.group(1)))
    elif "UNDER" in rec_upper:
        match = re.search(r"UNDER\s+(\d+\.?\d*)", rec_upper)
        if match:
            return ("UNDER", float(match.group(1)))
    elif "HOME" in rec_upper or "LOCAL" in rec_upper:
        return ("HOME", None)
    elif "AWAY" in rec_upper or "VISITANTE" in rec_upper:
        return ("AWAY", None)

    return ("UNKNOWN", None)


def parse_score(score_str: str) -> Tuple[int, int]:
    """Parse score string like '1-0' or '2-1' to (home, away)."""
    if not score_str or score_str == "-" or ":" not in score_str and "-" not in score_str:
        raise ValueError(f"Invalid score format: {score_str}")

    separator = "-" if "-" in score_str else ":"
    parts = score_str.split(separator)
    return int(parts[0].strip()), int(parts[1].strip())


def get_active_match_ids(games_csv_path: Path) -> set:
    """
    Read games.csv and return a set of active match IDs.
    Match IDs are extracted from the URL column.

    Returns:
        Set of match_id strings (e.g., 'partido-x-y-apuestas-12345')
    """
    active_matches = set()

    if not games_csv_path.exists():
        print(f"   [WARN] games.csv not found at {games_csv_path}")
        return active_matches

    try:
        with open(games_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('url', '')
                if url:
                    # Extract match_id from URL
                    # Example: https://.../partido-x-y-apuestas-12345 -> partido-x-y-apuestas-12345
                    match = re.search(r'([^/]+apuestas-\d+)', url)
                    if match:
                        active_matches.add(match.group(1))
    except Exception as e:
        print(f"   [ERROR] Error reading games.csv: {e}")

    return active_matches


def find_match_csv(match_id: str, data_dir: Path) -> Optional[Path]:
    """
    Find the CSV file for a given match_id.
    Match CSVs are in betfair_scraper/data/ with format: partido_{match_id}.csv
    """
    # Try with partido_ prefix
    csv_path = data_dir / f"partido_{match_id}.csv"
    if csv_path.exists():
        return csv_path

    # Try without prefix (fallback)
    csv_path = data_dir / f"{match_id}.csv"
    if csv_path.exists():
        return csv_path

    return None


def get_final_score(csv_path: Path) -> Optional[str]:
    """
    Read match CSV and get the final score from the last row.
    Returns score string like "1-0" or None if not found.
    """
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            last_row = None
            for row in reader:
                # Only consider rows with actual match state (not pre_partido)
                if row.get('estado_partido') not in ['pre_partido', '', None]:
                    last_row = row

            if last_row:
                # Try to construct score from goles_local and goles_visitante
                if 'goles_local' in last_row and 'goles_visitante' in last_row:
                    home = last_row['goles_local']
                    away = last_row['goles_visitante']
                    if home and away:
                        return f"{home}-{away}"

                # Fallback: try 'score' column
                if 'score' in last_row and last_row['score']:
                    return last_row['score']
    except Exception as e:
        print(f"   [ERROR] Error reading {csv_path}: {e}")

    return None


def determine_bet_result(bet_type: str, threshold: Optional[float],
                        final_score: str) -> bool:
    """
    Determine if bet won based on bet type and final score.

    Returns True if bet won, False if lost.
    """
    home_goals, away_goals = parse_score(final_score)
    total_goals = home_goals + away_goals

    if bet_type == "DRAW":
        return home_goals == away_goals

    elif bet_type == "OVER":
        if threshold is None:
            raise ValueError("OVER bet requires threshold")
        return total_goals > threshold

    elif bet_type == "UNDER":
        if threshold is None:
            raise ValueError("UNDER bet requires threshold")
        return total_goals < threshold

    elif bet_type == "HOME":
        return home_goals > away_goals

    elif bet_type == "AWAY":
        return away_goals > home_goals

    else:
        raise ValueError(f"Unknown bet type: {bet_type}")


def calculate_pl(won: bool, stake: float, back_odds: float) -> float:
    """Calculate profit/loss for a bet."""
    if won:
        return stake * (back_odds - 1)
    else:
        return -stake


def resolve_pending_bets(placed_bets_path: Path, data_dir: Path, games_csv_path: Path, dry_run: bool = False):
    """
    Main function to resolve pending bets.

    Args:
        placed_bets_path: Path to placed_bets.csv
        data_dir: Path to directory containing match CSV files
        games_csv_path: Path to games.csv (to check which matches are still active)
        dry_run: If True, only print what would be changed without modifying file
    """
    print(f"[*] Reading placed bets from: {placed_bets_path}")
    print(f"[*] Looking for match CSVs in: {data_dir}")
    print(f"[*] Checking active matches in: {games_csv_path}")
    print()

    # Get active matches from games.csv
    active_matches = get_active_match_ids(games_csv_path)
    print(f"[*] Active matches in games.csv: {len(active_matches)}")
    print()

    # Read all bets
    rows = []
    pending_bets = []

    with open(placed_bets_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            rows.append(row)
            # Check for both empty status and 'pending' status
            if row['status'] in ('', 'pending'):
                pending_bets.append(row)

    print(f"[*] Total bets: {len(rows)}")
    print(f"[*] Pending bets: {len(pending_bets)}")
    print()

    if not pending_bets:
        print("[OK] No pending bets to resolve!")
        return

    # Process each pending bet
    resolved_count = 0
    failed_count = 0
    skipped_count = 0

    for bet in pending_bets:
        bet_id = bet['id']
        match_id = bet['match_id']
        match_name = bet['match_name']
        recommendation = bet['recommendation']
        stake = float(bet['stake'])

        # Parse back_odds (may be empty for some bets)
        try:
            back_odds = float(bet['back_odds']) if bet['back_odds'] else None
        except ValueError:
            back_odds = None

        print(f"[BET] #{bet_id}: {match_name}")
        print(f"   Strategy: {bet['strategy_name']}")
        print(f"   Recommendation: {recommendation}")

        # Check if match is still active in games.csv
        if match_id in active_matches:
            print(f"   [SKIP] Match is still active in games.csv - keeping bet as pending")
            skipped_count += 1
            print()
            continue

        # Find match CSV
        match_csv = find_match_csv(match_id, data_dir)

        if not match_csv:
            print(f"   [ERROR] Match CSV not found: {match_id}.csv")
            failed_count += 1
            print()
            continue

        # Get final score
        final_score = get_final_score(match_csv)

        if not final_score:
            print(f"   [ERROR] Could not read final score from {match_csv}")
            failed_count += 1
            print()
            continue

        print(f"   [SCORE] Final score: {final_score}")

        # Parse bet type
        bet_type, threshold = parse_recommendation(recommendation)

        if bet_type == "UNKNOWN":
            print(f"   [ERROR] Could not parse bet type from: {recommendation}")
            failed_count += 1
            print()
            continue

        # Determine result
        try:
            bet_won = determine_bet_result(bet_type, threshold, final_score)
        except Exception as e:
            print(f"   [ERROR] Error determining result: {e}")
            failed_count += 1
            print()
            continue

        # Calculate P/L
        if back_odds is None:
            print(f"   [WARN] No back_odds found, cannot calculate P/L")
            failed_count += 1
            print()
            continue

        pl = calculate_pl(bet_won, stake, back_odds)
        result = "won" if bet_won else "lost"

        print(f"   [{'WIN' if bet_won else 'LOSS'}] Result: {result.upper()}")
        print(f"   [P/L] {pl:+.2f} EUR")

        # Update bet in rows
        for row in rows:
            if row['id'] == bet_id:
                row['status'] = result
                row['result'] = result
                row['pl'] = f"{pl:.2f}"
                break

        resolved_count += 1
        print()

    # Summary
    print("=" * 60)
    print(f"[RESOLVED] {resolved_count}")
    print(f"[SKIPPED] {skipped_count} (matches still active in games.csv)")
    print(f"[FAILED] {failed_count}")
    print()

    if resolved_count > 0:
        if dry_run:
            print("[DRY RUN] No changes written to file")
        else:
            # Write updated CSV
            with open(placed_bets_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            print(f"[SAVED] Updated {placed_bets_path}")
            print()

            # Calculate new totals
            total_pl = sum(float(row['pl']) for row in rows if row['pl'])
            total_bets = len(rows)
            wins = sum(1 for row in rows if row['result'] == 'won')
            losses = sum(1 for row in rows if row['result'] == 'lost')
            pending = sum(1 for row in rows if row['status'] == 'pending')

            print("[TOTALS]")
            print(f"   Total bets: {total_bets}")
            print(f"   Wins: {wins}")
            print(f"   Losses: {losses}")
            print(f"   Pending: {pending}")
            print(f"   Total P/L: {total_pl:+.2f} EUR")

            if wins + losses > 0:
                win_rate = (wins / (wins + losses)) * 100
                print(f"   Win Rate: {win_rate:.1f}%")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Resolve pending bets automatically")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files"
    )
    parser.add_argument(
        "--placed-bets",
        type=Path,
        default=Path(__file__).parent.parent / "placed_bets.csv",
        help="Path to placed_bets.csv"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).parent.parent / "data",
        help="Directory containing match CSV files"
    )
    parser.add_argument(
        "--games-csv",
        type=Path,
        default=Path(__file__).parent.parent / "games.csv",
        help="Path to games.csv (active matches)"
    )

    args = parser.parse_args()

    if not args.placed_bets.exists():
        print(f"[ERROR] {args.placed_bets} not found")
        exit(1)

    if not args.data_dir.exists():
        print(f"[ERROR] {args.data_dir} not found")
        exit(1)

    if not args.games_csv.exists():
        print(f"[WARN] {args.games_csv} not found - will settle all pending bets")

    resolve_pending_bets(args.placed_bets, args.data_dir, args.games_csv, args.dry_run)
