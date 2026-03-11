import os, csv, glob, statistics
from collections import Counter

DATA_DIR = r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data"
files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")), key=os.path.getmtime, reverse=True)
sample = files[:200]

# Deeper analysis 1: Are empty stats columns correlated with leagues?
print("=" * 80)
print("DEEP DIVE: Empty xG by League/Country")
print("=" * 80)

league_xg_empty = Counter()
league_xg_present = Counter()
league_stats_empty = Counter()
league_stats_present = Counter()

for fpath in sample:
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except:
        continue
    if not rows:
        continue

    # Get league/country from last row
    liga = rows[-1].get("Liga", "").strip() or "UNKNOWN"
    pais = rows[-1].get("Pais", rows[-1].get("País", "")).strip() or "UNKNOWN"
    key = f"{pais} / {liga}"

    xg_empty = all(not r.get("xg_local", "").strip() for r in rows)
    stats_empty = all(not r.get("posesion_local", "").strip() for r in rows)

    if xg_empty:
        league_xg_empty[key] += 1
    else:
        league_xg_present[key] += 1

    if stats_empty:
        league_stats_empty[key] += 1
    else:
        league_stats_present[key] += 1

print("\nLeagues with xG ALWAYS empty:")
for league, count in league_xg_empty.most_common(20):
    total = count + league_xg_present.get(league, 0)
    print(f"  {league}: {count}/{total} files empty")

print("\nLeagues with xG PRESENT:")
for league, count in league_xg_present.most_common(20):
    total = count + league_xg_empty.get(league, 0)
    print(f"  {league}: {count}/{total} files have xG")

print("\n\nLeagues with possession ALWAYS empty:")
for league, count in league_stats_empty.most_common(20):
    total = count + league_stats_present.get(league, 0)
    print(f"  {league}: {count}/{total} files empty")

# Deeper analysis 2: Stale score - check if these are genuinely goals from start
print(f"\n{'='*80}")
print("DEEP DIVE: Stale Score Files")
print("=" * 80)

for fpath in sample:
    fname = os.path.basename(fpath)
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except:
        continue
    if len(rows) < 10:
        continue

    goals_h_vals = []
    goals_a_vals = []
    for r in rows:
        gh = r.get("goles_local", "").strip()
        ga = r.get("goles_visitante", "").strip()
        if gh.isdigit():
            goals_h_vals.append(int(gh))
        if ga.isdigit():
            goals_a_vals.append(int(ga))

    if not goals_h_vals or not goals_a_vals:
        continue

    final_h = goals_h_vals[-1]
    final_a = goals_a_vals[-1]
    total = final_h + final_a
    if total > 0 and len(set(goals_h_vals)) == 1 and len(set(goals_a_vals)) == 1:
        minutes = []
        for r in rows:
            m = r.get("minuto", "").strip()
            if m:
                try:
                    minutes.append(float(m))
                except:
                    pass
        min_range = f"min {minutes[0]:.0f}-{minutes[-1]:.0f}" if minutes else "no minutes"
        print(f"  {fname}: score={final_h}-{final_a}, rows={len(rows)}, {min_range}")
        print(f"    First goal val row0: H={goals_h_vals[0]} A={goals_a_vals[0]}")

# Deeper analysis 3: Time gap distribution for files that ended early
print(f"\n{'='*80}")
print("DEEP DIVE: Early-end files with large gaps (scraper died mid-match)")
print("=" * 80)

from datetime import datetime

count_died = 0
for fpath in sample:
    fname = os.path.basename(fpath)
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except:
        continue
    if len(rows) < 5:
        continue

    minutes = []
    for r in rows:
        m = r.get("minuto", "").strip()
        if m:
            try:
                minutes.append(float(m))
            except:
                pass

    if not minutes:
        continue

    last_min = minutes[-1]
    estados = [r.get("estado_partido", "").strip().lower() for r in rows]
    has_finalizado = any("final" in e for e in estados if e)

    if last_min < 80 and not has_finalizado:
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

        if len(timestamps) >= 2:
            max_gap = max((timestamps[i] - timestamps[i-1]).total_seconds() / 60
                         for i in range(1, len(timestamps)))
            if max_gap > 10:
                count_died += 1
                if count_died <= 8:
                    print(f"  {fname}: ended at min {last_min:.0f}, max_gap={max_gap:.1f}min, rows={len(rows)}")

print(f"\n  Total early-end + large-gap files: {count_died}")

# Deeper analysis 4: How many files have stats that APPEAR partway through?
print(f"\n{'='*80}")
print("DEEP DIVE: Stats appearing late (xG starts empty, then appears)")
print("=" * 80)

late_stats = 0
for fpath in sample:
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except:
        continue
    if len(rows) < 20:
        continue

    # Check if xg starts empty but appears later
    first_10_empty = all(not r.get("xg_local", "").strip() for r in rows[:10])
    last_10_present = any(r.get("xg_local", "").strip() for r in rows[-10:])

    if first_10_empty and last_10_present:
        late_stats += 1

print(f"  Files where xG starts empty but appears later: {late_stats}/{len(sample)}")

# Deeper analysis 5: Scraping frequency
print(f"\n{'='*80}")
print("DEEP DIVE: Scraping interval (median gap between rows)")
print("=" * 80)

median_gaps = []
for fpath in sample:
    try:
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except:
        continue
    if len(rows) < 5:
        continue

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

    if len(timestamps) >= 5:
        gaps = [(timestamps[i] - timestamps[i-1]).total_seconds() / 60
                for i in range(1, len(timestamps))]
        median_gaps.append(statistics.median(gaps))

if median_gaps:
    print(f"  Mean median gap:   {statistics.mean(median_gaps):.1f} min")
    print(f"  Median median gap: {statistics.median(median_gaps):.1f} min")
    print(f"  Min:               {min(median_gaps):.1f} min")
    print(f"  Max:               {max(median_gaps):.1f} min")
