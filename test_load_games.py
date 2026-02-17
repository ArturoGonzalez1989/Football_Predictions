#!/usr/bin/env python3
"""Test what load_games() actually returns."""

import sys
sys.path.insert(0, "betfair_scraper/dashboard/backend")

from utils.csv_reader import load_games

games = load_games()

print(f"Total games loaded: {len(games)}\n")

# Count by status
status_counts = {}
for g in games:
    status = g["status"]
    status_counts[status] = status_counts.get(status, 0) + 1

print("Status breakdown:")
for status, count in status_counts.items():
    print(f"  {status}: {count}")

print(f"\nFinished matches:")
finished = [g for g in games if g["status"] == "finished"]
print(f"  Total: {len(finished)}")

if finished:
    print(f"\n  Sample finished matches:")
    for g in finished[:5]:
        print(f"    - {g['name']} (CSV rows: {g['capture_count']})")
