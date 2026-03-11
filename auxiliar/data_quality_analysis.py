import os, csv, glob, sys, statistics
from datetime import datetime, timedelta
from collections import defaultdict, Counter

DATA_DIR = r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data"
files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")), key=os.path.getmtime, reverse=True)

sample = files[:200]
print(f"Total CSV files: {len(files)}")
print(f"Sampling: {len(sample)} most recent files\n")

issues = {
    "few_rows": [],
    "time_gaps": [],
    "empty_key_cols": [],
    "late_start": [],
    "early_end": [],
    "dup_timestamps": [],
    "non_monotonic_ts": [],
    "stale_score": [],
    "corrupted": [],
    "no_odds": [],
}

KEY_COLS = ["back_home", "back_draw", "back_away", "xg_local", "xg_visitante",
            "posesion_local", "posesion_visitante", "tiros_local", "tiros_visitante",
            "back_over25", "back_under25"]

ODDS_COLS = ["back_home", "lay_home", "back_draw", "lay_draw", "back_away", "lay_away"]

row_counts = []
gap_maxes = []

for fpath in sample:
    fname = os.path.basename(fpath)
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        issues["corrupted"].append((fname, f"Read error: {e}"))
        continue

    if not rows:
        issues["few_rows"].append((fname, 0))
        continue

    nrows = len(rows)
    row_counts.append(nrows)

    # 1. Few rows
    if nrows < 10:
        issues["few_rows"].append((fname, nrows))

    # Parse minutes
    minutes = []
    for r in rows:
        m = r.get("minuto", "")
        if m and m.strip():
            try:
                minutes.append(float(m))
            except:
                pass

    # Parse timestamps
    timestamps = []
    for r in rows:
        ts_str = r.get("timestamp_utc", "").strip()
        if ts_str:
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]:
                try:
                    timestamps.append(datetime.strptime(ts_str, fmt))
                    break
                except:
                    pass

    # 2. Time gaps
    if len(timestamps) >= 2:
        max_gap_sec = 0
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i-1]).total_seconds()
            if gap > max_gap_sec:
                max_gap_sec = gap
        max_gap_min = max_gap_sec / 60
        gap_maxes.append(max_gap_min)
        if max_gap_min > 10:
            issues["time_gaps"].append((fname, round(max_gap_min, 1), nrows))

    # 3. Empty key columns
    empty_cols = []
    for col in KEY_COLS:
        all_empty = all(not r.get(col, "").strip() for r in rows)
        if all_empty:
            empty_cols.append(col)
    if empty_cols:
        issues["empty_key_cols"].append((fname, empty_cols, nrows))

    # Check core odds
    all_odds_empty = all(
        all(not r.get(col, "").strip() for r in rows)
        for col in ODDS_COLS
    )
    if all_odds_empty:
        issues["no_odds"].append((fname, nrows))

    # 4. Late start
    if minutes:
        first_min = minutes[0]
        if first_min > 30:
            issues["late_start"].append((fname, first_min, nrows))

    # 5. Early end
    if minutes:
        last_min = minutes[-1]
        estados = [r.get("estado_partido", "").strip().lower() for r in rows]
        has_finalizado = any("final" in e for e in estados if e)
        if last_min < 80 and not has_finalizado:
            issues["early_end"].append((fname, last_min, nrows))

    # 6. Duplicate timestamps
    if timestamps:
        ts_strs = [r.get("timestamp_utc", "").strip() for r in rows]
        ts_counts = Counter(ts_strs)
        dups = {k: v for k, v in ts_counts.items() if v > 1 and k}
        if dups:
            total_dups = sum(v - 1 for v in dups.values())
            issues["dup_timestamps"].append((fname, total_dups, nrows))

    # Non-monotonic timestamps
    if len(timestamps) >= 2:
        non_mono = 0
        for i in range(1, len(timestamps)):
            if timestamps[i] < timestamps[i-1]:
                non_mono += 1
        if non_mono > 0:
            issues["non_monotonic_ts"].append((fname, non_mono, nrows))

    # 7. Stale score
    if nrows >= 10:
        try:
            goals_h = [r.get("goles_local", "").strip() for r in rows]
            goals_a = [r.get("goles_visitante", "").strip() for r in rows]
            goals_h_vals = [int(g) for g in goals_h if g.isdigit()]
            goals_a_vals = [int(g) for g in goals_a if g.isdigit()]
            if goals_h_vals and goals_a_vals:
                final_h = goals_h_vals[-1]
                final_a = goals_a_vals[-1]
                total_goals = final_h + final_a
                h_changes = len(set(goals_h_vals))
                a_changes = len(set(goals_a_vals))
                if total_goals > 0 and h_changes == 1 and a_changes == 1:
                    issues["stale_score"].append((fname, f"{final_h}-{final_a}", nrows))
        except:
            pass

    # 8. Corrupted rows
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            header_line = f.readline()
            expected_cols = len(header_line.split(","))
            bad_rows = 0
            for line in f:
                if line.strip() and len(line.split(",")) != expected_cols:
                    bad_rows += 1
            if bad_rows > 0:
                issues["corrupted"].append((fname, f"{bad_rows} rows with wrong column count"))
    except:
        pass

# ===== REPORT =====
print("=" * 80)
print("DATA QUALITY ANALYSIS REPORT")
print(f"Sample: {len(sample)} most recent CSV files")
print("=" * 80)

if row_counts:
    print(f"\n--- ROW COUNT STATS ---")
    print(f"  Mean rows/file: {statistics.mean(row_counts):.1f}")
    print(f"  Median:         {statistics.median(row_counts):.0f}")
    print(f"  Min:            {min(row_counts)}")
    print(f"  Max:            {max(row_counts)}")
    print(f"  Files < 10 rows:  {sum(1 for r in row_counts if r < 10)}")
    print(f"  Files < 50 rows:  {sum(1 for r in row_counts if r < 50)}")
    print(f"  Files > 100 rows: {sum(1 for r in row_counts if r > 100)}")

if gap_maxes:
    print(f"\n--- MAX TIME GAP STATS (minutes between consecutive rows) ---")
    sorted_gaps = sorted(gap_maxes)
    print(f"  Mean max gap:   {statistics.mean(gap_maxes):.1f} min")
    print(f"  Median:         {statistics.median(gap_maxes):.1f} min")
    print(f"  P90:            {sorted_gaps[int(len(sorted_gaps)*0.90)]:.1f} min")
    print(f"  P95:            {sorted_gaps[int(len(sorted_gaps)*0.95)]:.1f} min")
    print(f"  P99:            {sorted_gaps[min(int(len(sorted_gaps)*0.99), len(sorted_gaps)-1)]:.1f} min")
    print(f"  Max:            {max(gap_maxes):.1f} min")
    print(f"  Files > 5 min:  {sum(1 for g in gap_maxes if g > 5)}")
    print(f"  Files > 10 min: {sum(1 for g in gap_maxes if g > 10)}")
    print(f"  Files > 30 min: {sum(1 for g in gap_maxes if g > 30)}")

print(f"\n{'='*80}")
print("ISSUE BREAKDOWN")
print(f"{'='*80}")

def print_issue(name, desc, data, show_top=8):
    pct = len(data) / len(sample) * 100
    print(f"\n--- {name} --- ({len(data)}/{len(sample)} files = {pct:.1f}%)")
    print(f"  {desc}")
    if data:
        for item in data[:show_top]:
            print(f"    {item}")
        if len(data) > show_top:
            print(f"    ... and {len(data) - show_top} more")

print_issue("1. FEW ROWS (< 10)",
            "Scraper barely captured / match not tracked",
            issues["few_rows"], 10)

print_issue("2. LARGE TIME GAPS (> 10 min)",
            "Stalled capture between consecutive rows",
            issues["time_gaps"], 10)

print_issue("3. KEY COLUMNS ALWAYS EMPTY",
            "Extraction failure for important data columns",
            issues["empty_key_cols"], 10)

print_issue("4. NO ODDS DATA AT ALL",
            "All 6 core odds columns empty throughout file",
            issues["no_odds"], 10)

print_issue("5. LATE START (first minute > 30)",
            "Match detected late, missed early data",
            issues["late_start"], 10)

print_issue("6. EARLY END (last minute < 80, no finalizado)",
            "Premature driver death / lost tracking",
            issues["early_end"], 10)

print_issue("7. DUPLICATE TIMESTAMPS",
            "Same timestamp appears multiple times",
            issues["dup_timestamps"], 10)

print_issue("8. NON-MONOTONIC TIMESTAMPS",
            "Timestamps go backwards",
            issues["non_monotonic_ts"], 10)

print_issue("9. STALE SCORE",
            "Final score > 0 but value never changed row-to-row (always same from first row)",
            issues["stale_score"], 10)

print_issue("10. CORRUPTED/MALFORMED",
            "Read errors or rows with wrong column count",
            issues["corrupted"], 10)

# Summary
print(f"\n{'='*80}")
print("SUMMARY")
print(f"{'='*80}")
total_issues = sum(len(v) for v in issues.values())
files_with_any = set()
for v in issues.values():
    for item in v:
        files_with_any.add(item[0])
print(f"  Total issue instances:    {total_issues}")
print(f"  Files with any issue:     {len(files_with_any)}/{len(sample)} ({len(files_with_any)/len(sample)*100:.1f}%)")
print(f"  Clean files (no issues):  {len(sample) - len(files_with_any)}/{len(sample)} ({(len(sample)-len(files_with_any))/len(sample)*100:.1f}%)")

# Most commonly empty columns
if issues["empty_key_cols"]:
    col_freq = Counter()
    for _, cols, _ in issues["empty_key_cols"]:
        for c in cols:
            col_freq[c] += 1
    print(f"\n  Most commonly empty key columns:")
    for col, count in col_freq.most_common():
        print(f"    {col}: {count} files ({count/len(sample)*100:.1f}%)")

# Cross-issue analysis
print(f"\n--- CROSS-ISSUE: Files with BOTH few rows AND late start ---")
few_set = set(x[0] for x in issues["few_rows"])
late_set = set(x[0] for x in issues["late_start"])
both = few_set & late_set
print(f"  {len(both)} files")

print(f"\n--- CROSS-ISSUE: Files with BOTH early end AND time gaps ---")
early_set = set(x[0] for x in issues["early_end"])
gap_set = set(x[0] for x in issues["time_gaps"])
both2 = early_set & gap_set
print(f"  {len(both2)} files")
