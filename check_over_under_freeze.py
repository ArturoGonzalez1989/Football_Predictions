"""
Check if Over/Under odds are frozen (stuck at pre-match values) across match CSVs.
Reports distinct values per match for back_over25, back_over35, back_over45 during in-play.
"""

import glob
import os
import csv
from urllib.parse import unquote

DATA_DIR = r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data"

cols_of_interest = ["back_over25", "back_over35", "back_over45"]

files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")))

print(f"Found {len(files)} partido_*.csv files\n")

results = []

for fpath in files:
    fname = os.path.basename(fpath)
    # Decode URL-encoded filenames for readability
    match_name = unquote(fname.replace("partido_", "").replace(".csv", ""))

    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)

            in_play_rows = 0
            distinct_values = {col: set() for col in cols_of_interest}

            for row in reader:
                estado = row.get("estado_partido", "").strip()
                if estado != "en_juego":
                    continue

                in_play_rows += 1

                for col in cols_of_interest:
                    val = row.get(col, "").strip()
                    if val and val != "":
                        distinct_values[col].add(val)

        results.append({
            "match": match_name,
            "in_play_rows": in_play_rows,
            "distinct_o25": len(distinct_values["back_over25"]),
            "distinct_o35": len(distinct_values["back_over35"]),
            "distinct_o45": len(distinct_values["back_over45"]),
            "values_o25": distinct_values["back_over25"],
            "values_o35": distinct_values["back_over35"],
            "values_o45": distinct_values["back_over45"],
        })
    except Exception as e:
        print(f"  ERROR reading {fname}: {e}")

# --- REPORT ---

# Separate matches with in-play data from those without
with_data = [r for r in results if r["in_play_rows"] > 0]
no_data = [r for r in results if r["in_play_rows"] == 0]

print(f"Total files: {len(results)}")
print(f"  With in-play rows: {len(with_data)}")
print(f"  Without in-play rows: {len(no_data)}")
print()

# Classify
FROZEN_THRESHOLD = 2  # 1-2 distinct values = frozen
MIN_ROWS_TO_JUDGE = 5  # need at least 5 in-play rows to judge

frozen_matches = []
healthy_matches = []
insufficient_data = []

for r in with_data:
    if r["in_play_rows"] < MIN_ROWS_TO_JUDGE:
        insufficient_data.append(r)
        continue

    # A column is frozen if it has 0-2 distinct values OR has no data at all
    o25_frozen = r["distinct_o25"] <= FROZEN_THRESHOLD
    o35_frozen = r["distinct_o35"] <= FROZEN_THRESHOLD
    o45_frozen = r["distinct_o45"] <= FROZEN_THRESHOLD

    # All three frozen = match is frozen
    all_frozen = o25_frozen and o35_frozen and o45_frozen
    any_frozen = o25_frozen or o35_frozen or o45_frozen

    r["all_frozen"] = all_frozen
    r["any_frozen"] = any_frozen

    if all_frozen:
        frozen_matches.append(r)
    else:
        healthy_matches.append(r)

print("=" * 120)
print("MATCHES WITH HEALTHY (MOVING) OVER/UNDER ODDS")
print("=" * 120)
print(f"{'Match':<60} {'Rows':>6} {'O2.5':>6} {'O3.5':>6} {'O4.5':>6}  Status")
print("-" * 120)

for r in sorted(healthy_matches, key=lambda x: x["distinct_o25"], reverse=True):
    status_parts = []
    if r["distinct_o25"] <= FROZEN_THRESHOLD:
        status_parts.append("O2.5 frozen")
    if r["distinct_o35"] <= FROZEN_THRESHOLD:
        status_parts.append("O3.5 frozen")
    if r["distinct_o45"] <= FROZEN_THRESHOLD:
        status_parts.append("O4.5 frozen")
    status = ", ".join(status_parts) if status_parts else "OK"

    print(f"{r['match'][:58]:<60} {r['in_play_rows']:>6} {r['distinct_o25']:>6} {r['distinct_o35']:>6} {r['distinct_o45']:>6}  {status}")

print()
print("=" * 120)
print("MATCHES WITH FROZEN OVER/UNDER ODDS (ALL 3 columns <=2 distinct values)")
print("=" * 120)
print(f"{'Match':<60} {'Rows':>6} {'O2.5':>6} {'O3.5':>6} {'O4.5':>6}  O2.5 values seen")
print("-" * 120)

for r in sorted(frozen_matches, key=lambda x: x["in_play_rows"], reverse=True):
    vals_preview = sorted(r["values_o25"])[:5]
    vals_str = ", ".join(vals_preview) if vals_preview else "(empty)"
    print(f"{r['match'][:58]:<60} {r['in_play_rows']:>6} {r['distinct_o25']:>6} {r['distinct_o35']:>6} {r['distinct_o45']:>6}  {vals_str}")

print()
print(f"Matches with insufficient data (<{MIN_ROWS_TO_JUDGE} in-play rows): {len(insufficient_data)}")

# --- SUMMARY ---
print()
print("=" * 120)
print("SUMMARY")
print("=" * 120)
total_judgeable = len(frozen_matches) + len(healthy_matches)
if total_judgeable > 0:
    pct_frozen = len(frozen_matches) / total_judgeable * 100
    pct_healthy = len(healthy_matches) / total_judgeable * 100
else:
    pct_frozen = pct_healthy = 0

print(f"  Judgeable matches (>={MIN_ROWS_TO_JUDGE} in-play rows): {total_judgeable}")
print(f"  ALL Over/Under frozen:  {len(frozen_matches):>4} ({pct_frozen:.1f}%)")
print(f"  At least some moving:   {len(healthy_matches):>4} ({pct_healthy:.1f}%)")
print()

# Among healthy matches, how many have SOME frozen columns?
partial_frozen = [r for r in healthy_matches if r.get("any_frozen")]
print(f"  Of the {len(healthy_matches)} 'healthy' matches, {len(partial_frozen)} have at least one frozen column")
print()

# Distribution of distinct values
print("DISTRIBUTION OF DISTINCT back_over25 VALUES (judgeable matches):")
from collections import Counter
dist = Counter()
for r in frozen_matches + healthy_matches:
    bucket = r["distinct_o25"]
    if bucket == 0:
        dist["0 (empty)"] += 1
    elif bucket <= 2:
        dist["1-2 (frozen)"] += 1
    elif bucket <= 5:
        dist["3-5"] += 1
    elif bucket <= 10:
        dist["6-10"] += 1
    elif bucket <= 20:
        dist["11-20"] += 1
    else:
        dist[f"21+"] += 1

for bucket in ["0 (empty)", "1-2 (frozen)", "3-5", "6-10", "11-20", "21+"]:
    count = dist.get(bucket, 0)
    bar = "#" * count
    print(f"  {bucket:>15}: {count:>4}  {bar}")

print()

# Show a few examples of matches with MANY distinct values to confirm they're real
print("TOP 10 matches by distinct back_over25 values (most movement):")
top = sorted(with_data, key=lambda x: x["distinct_o25"], reverse=True)[:10]
for r in top:
    sample = sorted(r["values_o25"])[:8]
    sample_str = ", ".join(sample)
    print(f"  {r['match'][:55]:<57} rows={r['in_play_rows']:>4}  distinct_o25={r['distinct_o25']:>3}  sample: {sample_str}")
