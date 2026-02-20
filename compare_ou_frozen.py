"""
Compare a match with healthy Over/Under odds updates vs one with frozen O/U odds.
Goal: understand WHY some matches have O/U odds that never change during in-play.
"""
import os
import sys
import csv
from collections import defaultdict

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data"

OU_COLS = ["back_over25", "lay_over25", "back_over35", "lay_over35"]
ALL_OU_COLS = [
    "back_over05", "lay_over05", "back_under05", "lay_under05",
    "back_over15", "lay_over15", "back_under15", "lay_under15",
    "back_over25", "lay_over25", "back_under25", "lay_under25",
    "back_over35", "lay_over35", "back_under35", "lay_under35",
    "back_over45", "lay_over45", "back_under45", "lay_under45",
]
DISPLAY_COLS = ["timestamp_utc", "minuto", "goles_local", "goles_visitante",
                "back_over25", "lay_over25", "back_over35", "lay_over35"]

def read_csv(filepath):
    rows = []
    with open(filepath, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def is_inplay(row):
    estado = (row.get("estado_partido") or "").strip().lower()
    minuto = (row.get("minuto") or "").strip()
    if minuto and minuto not in ["", "None"]:
        return True
    if estado in ["descanso", "1st", "2nd", "en_juego"]:
        return True
    return False

def is_prematch(row):
    estado = (row.get("estado_partido") or "").strip().lower()
    minuto = (row.get("minuto") or "").strip()
    if not minuto or minuto in ["", "None"]:
        if estado in ["", "prematch", "none"] or not estado:
            return True
    return False

def get_ou_tuple(row):
    vals = []
    for c in OU_COLS:
        v = (row.get(c) or "").strip()
        vals.append(v)
    return tuple(vals)

def has_any_ou(row):
    for c in OU_COLS:
        v = (row.get(c) or "").strip()
        if v and v not in ["", "None", "0"]:
            return True
    return False

def has_any_all_ou(row):
    """Check if ANY of the over/under columns has data."""
    for c in ALL_OU_COLS:
        v = (row.get(c) or "").strip()
        if v and v not in ["", "None", "0"]:
            return True
    return False

# ============================================================
# PHASE 1: Scan all matches - categorize precisely
# ============================================================
print("=" * 80)
print("PHASE 1: Scanning all match files with precise categorization...")
print("=" * 80)

match_stats = []
files = [f for f in os.listdir(DATA_DIR) if f.startswith("partido_") and f.endswith(".csv")]
print(f"Found {len(files)} match files\n")

for fname in files:
    filepath = os.path.join(DATA_DIR, fname)
    try:
        rows = read_csv(filepath)
    except Exception as e:
        continue

    inplay_rows = [r for r in rows if is_inplay(r)]
    prematch_rows = [r for r in rows if is_prematch(r)]

    if len(inplay_rows) < 5:
        continue

    # Count distinct O/U value combinations during in-play
    inplay_ou_values = set()
    inplay_back_over25_values = set()
    inplay_rows_with_ou = 0
    inplay_rows_with_any_ou = 0
    for r in inplay_rows:
        if has_any_ou(r):
            inplay_rows_with_ou += 1
            inplay_ou_values.add(get_ou_tuple(r))
            v = (r.get("back_over25") or "").strip()
            if v and v not in ["", "None"]:
                inplay_back_over25_values.add(v)
        if has_any_all_ou(r):
            inplay_rows_with_any_ou += 1

    # Prematch O/U
    prematch_ou_values = set()
    prematch_rows_with_ou = 0
    for r in prematch_rows:
        if has_any_ou(r):
            prematch_rows_with_ou += 1
            prematch_ou_values.add(get_ou_tuple(r))

    url = ""
    for r in rows:
        u = (r.get("url") or "").strip()
        if u:
            url = u
            break

    # Categorize
    if inplay_rows_with_ou == 0:
        category = "NO_OU_DATA"
    elif len(inplay_back_over25_values) <= 2:
        category = "FROZEN_WITH_VALUES"  # Has O/U data but stuck at 1-2 values
    elif len(inplay_back_over25_values) <= 5:
        category = "LOW_VARIETY"
    elif len(inplay_back_over25_values) <= 10:
        category = "MODERATE"
    else:
        category = "HEALTHY"

    # Check 1X2 variety for comparison
    back_home_vals = set()
    for r in inplay_rows:
        bh = (r.get("back_home") or "").strip()
        if bh and bh not in ["", "None"]:
            back_home_vals.add(bh)

    match_stats.append({
        "file": fname,
        "total_rows": len(rows),
        "prematch_rows": len(prematch_rows),
        "inplay_rows": len(inplay_rows),
        "inplay_rows_with_ou": inplay_rows_with_ou,
        "inplay_rows_with_any_ou": inplay_rows_with_any_ou,
        "distinct_inplay_ou": len(inplay_ou_values),
        "distinct_inplay_back25": len(inplay_back_over25_values),
        "distinct_prematch_ou": len(prematch_ou_values),
        "prematch_rows_with_ou": prematch_rows_with_ou,
        "distinct_1x2_home": len(back_home_vals),
        "category": category,
        "url": url,
        "filepath": filepath,
    })

# Print distribution
cat_counts = defaultdict(int)
for m in match_stats:
    cat_counts[m["category"]] += 1

print("Category distribution:")
for cat in ["HEALTHY", "MODERATE", "LOW_VARIETY", "FROZEN_WITH_VALUES", "NO_OU_DATA"]:
    print(f"  {cat:<25} {cat_counts[cat]:>4} matches")

# ============================================================
# Find best examples
# ============================================================
frozen_with_vals = [m for m in match_stats if m["category"] == "FROZEN_WITH_VALUES"]
no_ou = [m for m in match_stats if m["category"] == "NO_OU_DATA"]
healthy_list = [m for m in match_stats if m["category"] == "HEALTHY"]

print(f"\n--- FROZEN_WITH_VALUES candidates (have O/U but stuck): {len(frozen_with_vals)} ---")
frozen_with_vals.sort(key=lambda x: x["inplay_rows_with_ou"], reverse=True)
for m in frozen_with_vals[:10]:
    print(f"  {m['file'][:60]:<60} ip_rows={m['inplay_rows']:>3} rows_w_ou={m['inplay_rows_with_ou']:>3} distinct_o25={m['distinct_inplay_back25']:>2} 1x2_vals={m['distinct_1x2_home']:>3}")

print(f"\n--- NO_OU_DATA top examples (O/U columns completely blank): {len(no_ou)} ---")
no_ou.sort(key=lambda x: x["inplay_rows"], reverse=True)
for m in no_ou[:10]:
    print(f"  {m['file'][:60]:<60} ip_rows={m['inplay_rows']:>3} 1x2_vals={m['distinct_1x2_home']:>3} any_ou_rows={m['inplay_rows_with_any_ou']:>3}")

print(f"\n--- HEALTHY top examples: {len(healthy_list)} ---")
healthy_list.sort(key=lambda x: x["distinct_inplay_back25"], reverse=True)
for m in healthy_list[:5]:
    print(f"  {m['file'][:60]:<60} ip_rows={m['inplay_rows']:>3} distinct_o25={m['distinct_inplay_back25']:>2} 1x2_vals={m['distinct_1x2_home']:>3}")


# ============================================================
# PHASE 2: Select best exemplars and do deep comparison
# ============================================================
print("\n" + "=" * 80)
print("PHASE 2: Deep comparison")
print("=" * 80)

# Pick a FROZEN_WITH_VALUES match (if available) else pick NO_OU_DATA with most inplay rows
if frozen_with_vals:
    frozen = frozen_with_vals[0]
    frozen_type = "FROZEN_WITH_VALUES"
else:
    frozen = no_ou[0] if no_ou else None
    frozen_type = "NO_OU_DATA"

healthy = healthy_list[0] if healthy_list else None

def analyze_match(label, info, show_all_ou=False):
    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"{'=' * 70}")
    print(f"  File: {info['file']}")
    print(f"  URL:  {info['url']}")
    print(f"  Total rows: {info['total_rows']}, Prematch: {info['prematch_rows']}, In-play: {info['inplay_rows']}")
    print(f"  In-play rows WITH O/U (back_o25 cols): {info['inplay_rows_with_ou']}")
    print(f"  In-play rows with ANY O/U col: {info['inplay_rows_with_any_ou']}")
    print(f"  Distinct in-play back_over25 values: {info['distinct_inplay_back25']}")
    print(f"  Distinct in-play O/U combos: {info['distinct_inplay_ou']}")
    print(f"  Prematch rows with O/U: {info['prematch_rows_with_ou']}")
    print(f"  Distinct 1X2 home values (in-play): {info['distinct_1x2_home']}")

    rows = read_csv(info["filepath"])
    inplay_rows = [r for r in rows if is_inplay(r)]
    prematch_rows = [r for r in rows if is_prematch(r)]

    # Show first 5 in-play rows
    print(f"\n  First 5 in-play rows:")
    print(f"  {'timestamp_utc':<22} {'min':>5} {'GL':>3} {'GV':>3} {'bk_o25':>8} {'ly_o25':>8} {'bk_o35':>8} {'ly_o35':>8} {'bk_home':>8} {'ly_home':>8}")
    print(f"  {'-'*22} {'-'*5} {'-'*3} {'-'*3} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for r in inplay_rows[:5]:
        ts = (r.get("timestamp_utc") or "")[:22]
        mi = (r.get("minuto") or "")[:5]
        gl = (r.get("goles_local") or "")[:3]
        gv = (r.get("goles_visitante") or "")[:3]
        bo25 = (r.get("back_over25") or "-")[:8]
        lo25 = (r.get("lay_over25") or "-")[:8]
        bo35 = (r.get("back_over35") or "-")[:8]
        lo35 = (r.get("lay_over35") or "-")[:8]
        bh = (r.get("back_home") or "-")[:8]
        lh = (r.get("lay_home") or "-")[:8]
        print(f"  {ts:<22} {mi:>5} {gl:>3} {gv:>3} {bo25:>8} {lo25:>8} {bo35:>8} {lo35:>8} {bh:>8} {lh:>8}")

    # Show rows around minute 20-25 (mid first half)
    mid_rows = [r for r in inplay_rows if 20 <= float(r.get("minuto") or 0) <= 25]
    if mid_rows:
        print(f"\n  Rows around min 20-25 (mid first half):")
        print(f"  {'timestamp_utc':<22} {'min':>5} {'GL':>3} {'GV':>3} {'bk_o25':>8} {'ly_o25':>8} {'bk_o35':>8} {'ly_o35':>8} {'bk_home':>8} {'ly_home':>8}")
        print(f"  {'-'*22} {'-'*5} {'-'*3} {'-'*3} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for r in mid_rows[:5]:
            ts = (r.get("timestamp_utc") or "")[:22]
            mi = (r.get("minuto") or "")[:5]
            gl = (r.get("goles_local") or "")[:3]
            gv = (r.get("goles_visitante") or "")[:3]
            bo25 = (r.get("back_over25") or "-")[:8]
            lo25 = (r.get("lay_over25") or "-")[:8]
            bo35 = (r.get("back_over35") or "-")[:8]
            lo35 = (r.get("lay_over35") or "-")[:8]
            bh = (r.get("back_home") or "-")[:8]
            lh = (r.get("lay_home") or "-")[:8]
            print(f"  {ts:<22} {mi:>5} {gl:>3} {gv:>3} {bo25:>8} {lo25:>8} {bo35:>8} {lo35:>8} {bh:>8} {lh:>8}")

    # Show last 5 in-play rows
    print(f"\n  Last 5 in-play rows:")
    print(f"  {'timestamp_utc':<22} {'min':>5} {'GL':>3} {'GV':>3} {'bk_o25':>8} {'ly_o25':>8} {'bk_o35':>8} {'ly_o35':>8} {'bk_home':>8} {'ly_home':>8}")
    print(f"  {'-'*22} {'-'*5} {'-'*3} {'-'*3} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for r in inplay_rows[-5:]:
        ts = (r.get("timestamp_utc") or "")[:22]
        mi = (r.get("minuto") or "")[:5]
        gl = (r.get("goles_local") or "")[:3]
        gv = (r.get("goles_visitante") or "")[:3]
        bo25 = (r.get("back_over25") or "-")[:8]
        lo25 = (r.get("lay_over25") or "-")[:8]
        bo35 = (r.get("back_over35") or "-")[:8]
        lo35 = (r.get("lay_over35") or "-")[:8]
        bh = (r.get("back_home") or "-")[:8]
        lh = (r.get("lay_home") or "-")[:8]
        print(f"  {ts:<22} {mi:>5} {gl:>3} {gv:>3} {bo25:>8} {lo25:>8} {bo35:>8} {lo35:>8} {bh:>8} {lh:>8}")

    # If show_all_ou, show a sample of ALL O/U columns for one in-play row
    if show_all_ou and inplay_rows:
        mid_idx = len(inplay_rows) // 4  # ~minute 20
        sample_row = inplay_rows[mid_idx]
        print(f"\n  ALL Over/Under columns for row at index {mid_idx} (min={sample_row.get('minuto','?')}):")
        for c in ALL_OU_COLS:
            v = (sample_row.get(c) or "").strip()
            marker = "" if v else " <-- EMPTY"
            print(f"    {c:<20} = {v or '(blank)'}{marker}")

    # Collect all distinct back_over25 values during in-play
    distinct_vals = set()
    for r in inplay_rows:
        v = (r.get("back_over25") or "").strip()
        if v and v not in ["", "None"]:
            distinct_vals.add(v)

    if distinct_vals:
        try:
            sorted_vals = sorted(distinct_vals, key=lambda x: float(x))
        except:
            sorted_vals = sorted(distinct_vals)
        print(f"\n  All distinct back_over25 in-play values ({len(distinct_vals)}): {sorted_vals[:25]}")
    else:
        print(f"\n  All distinct back_over25 in-play values: NONE (all blank)")

    return rows, prematch_rows, inplay_rows


if healthy:
    h_rows, h_pre, h_ip = analyze_match("HEALTHY MATCH (O/U updates normally)", healthy, show_all_ou=True)
else:
    print("\n  [No healthy match found]")
    h_rows, h_pre, h_ip = [], [], []

if frozen:
    f_rows, f_pre, f_ip = analyze_match(f"FROZEN MATCH ({frozen_type})", frozen, show_all_ou=True)
else:
    print("\n  [No frozen match found]")
    f_rows, f_pre, f_ip = [], [], []


# ============================================================
# PHASE 3: Check if frozen O/U equals last pre-match values
# ============================================================
print("\n" + "=" * 80)
print("PHASE 3: Are frozen in-play O/U values identical to last pre-match values?")
print("=" * 80)

if frozen and frozen_type == "FROZEN_WITH_VALUES":
    f_pre_with_ou = [r for r in f_pre if has_any_ou(r)]
    f_ip_with_ou = [r for r in f_ip if has_any_ou(r)]

    if f_pre_with_ou and f_ip_with_ou:
        last_pre = f_pre_with_ou[-1]
        first_ip = f_ip_with_ou[0]

        print(f"\n  Last pre-match O/U values:")
        for c in OU_COLS:
            print(f"    {c}: {last_pre.get(c, 'N/A')}")

        print(f"\n  First in-play O/U values:")
        for c in OU_COLS:
            print(f"    {c}: {first_ip.get(c, 'N/A')}")

        all_same = True
        for c in OU_COLS:
            pre_v = (last_pre.get(c) or "").strip()
            ip_v = (first_ip.get(c) or "").strip()
            if pre_v != ip_v:
                all_same = False

        if all_same:
            print(f"\n  >>> CONFIRMED: First in-play O/U = last pre-match O/U")
        else:
            print(f"\n  >>> Values differ between last pre-match and first in-play")

        # Check what percentage of in-play rows have the same O/U as pre-match
        pre_tuple = get_ou_tuple(last_pre)
        frozen_count = sum(1 for r in f_ip_with_ou if get_ou_tuple(r) == pre_tuple)
        print(f"\n  In-play rows with O/U: {len(f_ip_with_ou)}")
        print(f"  Rows stuck at prematch value: {frozen_count} ({frozen_count/len(f_ip_with_ou)*100:.1f}%)")

        # Does it EVER change?
        first_tuple = get_ou_tuple(f_ip_with_ou[0])
        changed = any(get_ou_tuple(r) != first_tuple for r in f_ip_with_ou[1:])
        if not changed:
            print(f"\n  >>> O/U NEVER changes during the entire match ({len(f_ip_with_ou)} rows)")
            print(f"  >>> The scraper reads the same cached/stale O/U value every time")
        else:
            print(f"\n  >>> O/U does change at some point during the match")
    elif f_ip_with_ou and not f_pre_with_ou:
        print(f"\n  No pre-match O/U data, but frozen in-play values exist")
        first_tuple = get_ou_tuple(f_ip_with_ou[0])
        changed = any(get_ou_tuple(r) != first_tuple for r in f_ip_with_ou[1:])
        unique_combos = set(get_ou_tuple(r) for r in f_ip_with_ou)
        print(f"  Unique O/U combos during in-play: {len(unique_combos)}")
        for combo in unique_combos:
            print(f"    {combo}")
        if not changed:
            print(f"  >>> O/U NEVER changes: stuck at {first_tuple}")
    else:
        print("  [Not enough data to compare]")
elif frozen and frozen_type == "NO_OU_DATA":
    print(f"\n  This frozen match has NO O/U data at all (all columns blank)")
    print(f"  Checking if it has correct score data or other markets...")

    # Check what data IS present
    sample = f_ip[len(f_ip) // 4] if f_ip else None
    if sample:
        print(f"\n  Sample in-play row (min ~{sample.get('minuto','?')}):")
        has_1x2 = bool((sample.get("back_home") or "").strip())
        has_rc = bool((sample.get("back_rc_0_0") or "").strip())
        has_ou = bool((sample.get("back_over25") or "").strip())
        has_xg = bool((sample.get("xg_local") or "").strip())
        print(f"    Has 1X2 odds: {has_1x2}")
        print(f"    Has Correct Score: {has_rc}")
        print(f"    Has Over/Under: {has_ou}")
        print(f"    Has xG data: {has_xg}")

        # Check: maybe O/U uses different column names?
        print(f"\n  All columns that have data in this row:")
        for key, val in sample.items():
            v = (val or "").strip()
            if v and "over" in key.lower() or "under" in key.lower():
                print(f"    {key} = {v}")


# ============================================================
# PHASE 4: Compare URL patterns
# ============================================================
print("\n" + "=" * 80)
print("PHASE 4: URL pattern comparison")
print("=" * 80)

def extract_url_parts(url):
    parts = url.split("/")
    league = ""
    match_slug = ""
    for i, p in enumerate(parts):
        if p in ["fútbol", "f%C3%BAtbol"]:
            if i + 1 < len(parts):
                league = parts[i + 1]
            if i + 2 < len(parts):
                match_slug = parts[i + 2]
    return {"league": league, "match_slug": match_slug, "full_url": url}

if healthy:
    h_url = extract_url_parts(healthy["url"])
    print(f"\n  Healthy match URL:")
    print(f"    League: {h_url['league']}")
    print(f"    Slug:   {h_url['match_slug']}")
    print(f"    Full:   {h_url['full_url']}")

if frozen:
    f_url = extract_url_parts(frozen["url"])
    print(f"\n  Frozen match URL:")
    print(f"    League: {f_url['league']}")
    print(f"    Slug:   {f_url['match_slug']}")
    print(f"    Full:   {f_url['full_url']}")

if healthy and frozen:
    if h_url["league"] == f_url["league"]:
        print(f"\n  >>> Same league: {h_url['league']}")
    else:
        print(f"\n  >>> DIFFERENT leagues: healthy='{h_url['league']}' vs frozen='{f_url['league']}'")


# ============================================================
# PHASE 5: Transition analysis - prematch to in-play
# ============================================================
print("\n" + "=" * 80)
print("PHASE 5: Pre-match to in-play transition analysis")
print("=" * 80)

def analyze_transition(label, rows, prematch_rows, inplay_rows):
    print(f"\n  --- {label} ---")

    pre_with_ou = [r for r in prematch_rows if has_any_ou(r)]
    ip_with_ou = [r for r in inplay_rows if has_any_ou(r)]

    if pre_with_ou:
        print(f"\n  Last 3 pre-match rows with O/U:")
        print(f"  {'timestamp_utc':<22} {'estado':<12} {'min':>5} {'bk_o25':>8} {'ly_o25':>8} {'bk_o35':>8} {'ly_o35':>8}")
        for r in pre_with_ou[-3:]:
            ts = (r.get("timestamp_utc") or "")[:22]
            est = (r.get("estado_partido") or "")[:12]
            mi = (r.get("minuto") or "")[:5]
            bo25 = (r.get("back_over25") or "-")[:8]
            lo25 = (r.get("lay_over25") or "-")[:8]
            bo35 = (r.get("back_over35") or "-")[:8]
            lo35 = (r.get("lay_over35") or "-")[:8]
            print(f"  {ts:<22} {est:<12} {mi:>5} {bo25:>8} {lo25:>8} {bo35:>8} {lo35:>8}")
    else:
        print("  [No pre-match rows with O/U]")

    if ip_with_ou:
        print(f"\n  First 3 in-play rows with O/U:")
        print(f"  {'timestamp_utc':<22} {'estado':<12} {'min':>5} {'bk_o25':>8} {'ly_o25':>8} {'bk_o35':>8} {'ly_o35':>8}")
        for r in ip_with_ou[:3]:
            ts = (r.get("timestamp_utc") or "")[:22]
            est = (r.get("estado_partido") or "")[:12]
            mi = (r.get("minuto") or "")[:5]
            bo25 = (r.get("back_over25") or "-")[:8]
            lo25 = (r.get("lay_over25") or "-")[:8]
            bo35 = (r.get("back_over35") or "-")[:8]
            lo35 = (r.get("lay_over35") or "-")[:8]
            print(f"  {ts:<22} {est:<12} {mi:>5} {bo25:>8} {lo25:>8} {bo35:>8} {lo35:>8}")

        if pre_with_ou:
            last_pre = get_ou_tuple(pre_with_ou[-1])
            first_ip = get_ou_tuple(ip_with_ou[0])
            if last_pre == first_ip:
                print(f"\n  >>> First in-play O/U is IDENTICAL to last prematch O/U")
                changed = any(get_ou_tuple(r) != first_ip for r in ip_with_ou[1:])
                if changed:
                    print(f"  >>> But it DOES change later during in-play (normal)")
                else:
                    print(f"  >>> And it NEVER changes! Stuck for {len(ip_with_ou)} rows")
                    print(f"  >>> THIS IS THE BUG: DOM serving stale pre-match data")
            else:
                print(f"\n  >>> First in-play O/U DIFFERS from last prematch (values updated at kickoff)")
    else:
        print("  [No in-play rows with O/U]")
        print(f"  Total in-play rows: {len(inplay_rows)}")
        print(f"  The O/U section is completely absent from all in-play scrapes")

if healthy:
    analyze_transition("HEALTHY MATCH", h_rows, h_pre, h_ip)

if frozen:
    analyze_transition("FROZEN MATCH", f_rows, f_pre, f_ip)


# ============================================================
# PHASE 6: League-level frozen analysis
# ============================================================
print("\n" + "=" * 80)
print("PHASE 6: Frozen O/U by league")
print("=" * 80)

league_stats = defaultdict(lambda: {"total": 0, "frozen_val": 0, "no_ou": 0, "healthy": 0})
for m in match_stats:
    url_parts = extract_url_parts(m["url"])
    league = url_parts["league"] or "unknown"
    league_stats[league]["total"] += 1
    if m["category"] == "FROZEN_WITH_VALUES":
        league_stats[league]["frozen_val"] += 1
    elif m["category"] == "NO_OU_DATA":
        league_stats[league]["no_ou"] += 1
    elif m["category"] == "HEALTHY":
        league_stats[league]["healthy"] += 1

print(f"\n  {'League':<45} {'Tot':>4} {'NoOU':>5} {'Frzn':>5} {'OK':>4} {'%NoOU':>6}")
print(f"  {'-'*45} {'-'*4} {'-'*5} {'-'*5} {'-'*4} {'-'*6}")
for league in sorted(league_stats.keys(), key=lambda l: league_stats[l]["no_ou"] + league_stats[l]["frozen_val"], reverse=True):
    s = league_stats[league]
    pct = (s["no_ou"] + s["frozen_val"]) / s["total"] * 100 if s["total"] > 0 else 0
    print(f"  {league[:45]:<45} {s['total']:>4} {s['no_ou']:>5} {s['frozen_val']:>5} {s['healthy']:>4} {pct:>5.0f}%")


# ============================================================
# PHASE 7: In frozen matches, do OTHER odds update?
# ============================================================
print("\n" + "=" * 80)
print("PHASE 7: In frozen/no-OU matches, do 1X2 and correct score update?")
print("=" * 80)

# Check across ALL frozen and no-OU matches
for cat_label, cat_key in [("FROZEN_WITH_VALUES", "FROZEN_WITH_VALUES"), ("NO_OU_DATA", "NO_OU_DATA")]:
    cat_matches = [m for m in match_stats if m["category"] == cat_key]
    if not cat_matches:
        continue

    print(f"\n  --- {cat_label} ({len(cat_matches)} matches) ---")

    # Stats: how many have 1X2 updating
    updating_1x2 = sum(1 for m in cat_matches if m["distinct_1x2_home"] >= 5)
    print(f"  Matches with updating 1X2 (>=5 distinct back_home): {updating_1x2}/{len(cat_matches)}")

    # Pick one example
    example = max(cat_matches, key=lambda x: x["inplay_rows"])
    rows = read_csv(example["filepath"])
    inplay = [r for r in rows if is_inplay(r)]

    rc_vals = set()
    for r in inplay:
        v = (r.get("back_rc_0_0") or "").strip()
        if v and v not in ["", "None"]:
            rc_vals.add(v)

    print(f"\n  Example: {example['file']}")
    print(f"    1X2 back_home distinct values: {example['distinct_1x2_home']}")
    print(f"    Correct score back_rc_0_0 distinct values: {len(rc_vals)}")
    print(f"    O/U back_over25 distinct values: {example['distinct_inplay_back25']}")

    if example['distinct_1x2_home'] >= 5 and example['distinct_inplay_back25'] <= 2:
        print(f"    >>> 1X2 updates but O/U is stuck/blank = selective freeze")


# ============================================================
# PHASE 8: Check if there's a pattern in WHEN O/U disappears
# ============================================================
print("\n" + "=" * 80)
print("PHASE 8: When does O/U data appear/disappear in frozen matches?")
print("=" * 80)

if frozen:
    rows = read_csv(frozen["filepath"])

    print(f"\n  Match: {frozen['file']}")
    print(f"\n  Row-by-row O/U presence (first 30 rows):")
    print(f"  {'#':>4} {'timestamp':<22} {'estado':<12} {'min':>5} {'has_ou':>7} {'bk_o25':>8} {'bk_home':>8}")
    for i, r in enumerate(rows[:30]):
        ts = (r.get("timestamp_utc") or "")[:22]
        est = (r.get("estado_partido") or "")[:12]
        mi = (r.get("minuto") or "")[:5]
        has = "YES" if has_any_ou(r) else "no"
        bo25 = (r.get("back_over25") or "-")[:8]
        bh = (r.get("back_home") or "-")[:8]
        print(f"  {i:>4} {ts:<22} {est:<12} {mi:>5} {has:>7} {bo25:>8} {bh:>8}")

    # Find the transition point where O/U disappears
    had_ou = False
    lost_ou_at = None
    for i, r in enumerate(rows):
        if has_any_ou(r):
            had_ou = True
        elif had_ou and not has_any_ou(r) and is_inplay(r):
            lost_ou_at = i
            break

    if lost_ou_at:
        print(f"\n  O/U data disappears at row {lost_ou_at}")
        print(f"  Row before (with O/U): {rows[lost_ou_at-1].get('timestamp_utc','')} min={rows[lost_ou_at-1].get('minuto','')} estado={rows[lost_ou_at-1].get('estado_partido','')}")
        print(f"  Row after (no O/U):    {rows[lost_ou_at].get('timestamp_utc','')} min={rows[lost_ou_at].get('minuto','')} estado={rows[lost_ou_at].get('estado_partido','')}")
    elif not had_ou:
        print(f"\n  O/U data was NEVER present in this match (not even pre-match)")
    else:
        print(f"\n  O/U data present throughout (or at end)")

    # Also check: did the healthy match ever lose O/U?
    if healthy:
        print(f"\n  Healthy match O/U timeline:")
        h_rows2 = read_csv(healthy["filepath"])
        total_rows = len(h_rows2)
        rows_with = sum(1 for r in h_rows2 if has_any_ou(r))
        rows_without = total_rows - rows_with
        print(f"    Total rows: {total_rows}")
        print(f"    Rows WITH O/U: {rows_with}")
        print(f"    Rows WITHOUT O/U: {rows_without}")

        # Find when O/U stops
        last_ou_idx = 0
        for i, r in enumerate(h_rows2):
            if has_any_ou(r):
                last_ou_idx = i
        if last_ou_idx < total_rows - 1:
            print(f"    Last row with O/U: index {last_ou_idx}, min={h_rows2[last_ou_idx].get('minuto','')}")
            print(f"    (O/U naturally disappears in late minutes as markets suspend)")


# ============================================================
# PHASE 9: Check a FROZEN_WITH_VALUES match in detail (if we have one)
# ============================================================
print("\n" + "=" * 80)
print("PHASE 9: Deep dive into a FROZEN_WITH_VALUES match (if available)")
print("=" * 80)

if frozen_with_vals:
    fwv = frozen_with_vals[0]
    rows = read_csv(fwv["filepath"])
    inplay = [r for r in rows if is_inplay(r)]
    prematch = [r for r in rows if is_prematch(r)]
    ip_with_ou = [r for r in inplay if has_any_ou(r)]

    print(f"\n  Match: {fwv['file']}")
    print(f"  URL:   {fwv['url']}")
    print(f"  In-play rows: {fwv['inplay_rows']}, with O/U: {fwv['inplay_rows_with_ou']}")
    print(f"  Distinct O/U combos: {fwv['distinct_inplay_ou']}")

    if ip_with_ou:
        # Show the actual stuck values
        unique_combos = set()
        for r in ip_with_ou:
            unique_combos.add(get_ou_tuple(r))
        print(f"\n  Unique O/U combinations during in-play:")
        for combo in sorted(unique_combos):
            count = sum(1 for r in ip_with_ou if get_ou_tuple(r) == combo)
            print(f"    back_o25={combo[0]}, lay_o25={combo[1]}, back_o35={combo[2]}, lay_o35={combo[3]}  ({count} rows)")

        # Compare with prematch
        pre_with_ou = [r for r in prematch if has_any_ou(r)]
        if pre_with_ou:
            last_pre_tuple = get_ou_tuple(pre_with_ou[-1])
            print(f"\n  Last prematch O/U: back_o25={last_pre_tuple[0]}, lay_o25={last_pre_tuple[1]}, back_o35={last_pre_tuple[2]}, lay_o35={last_pre_tuple[3]}")
            if last_pre_tuple in unique_combos:
                print(f"  >>> The prematch values appear in the in-play frozen values!")
            else:
                print(f"  >>> The prematch values are DIFFERENT from the frozen in-play values")

        # Show a timeline of O/U values
        print(f"\n  O/U timeline (every 5th row with O/U):")
        print(f"  {'timestamp':<22} {'min':>5} {'GL-GV':>6} {'bk_o25':>8} {'ly_o25':>8} {'bk_o35':>8} {'ly_o35':>8}")
        for i, r in enumerate(ip_with_ou):
            if i % 5 == 0:
                ts = (r.get("timestamp_utc") or "")[:22]
                mi = (r.get("minuto") or "")[:5]
                gl = r.get("goles_local", "?")
                gv = r.get("goles_visitante", "?")
                combo = get_ou_tuple(r)
                print(f"  {ts:<22} {mi:>5} {gl}-{gv:>3} {combo[0]:>8} {combo[1]:>8} {combo[2]:>8} {combo[3]:>8}")
else:
    print("\n  No FROZEN_WITH_VALUES matches found.")
    print("  All 'frozen' matches actually have BLANK O/U columns (NO_OU_DATA).")
    print("  This means Betfair simply doesn't provide O/U markets for these matches.")


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 80)
print("FINAL SUMMARY")
print("=" * 80)
total = len(match_stats)
print(f"\n  Total matches analyzed: {total}")
print(f"  HEALTHY (>=11 distinct O/U values):        {cat_counts.get('HEALTHY',0):>4} ({cat_counts.get('HEALTHY',0)/total*100:.1f}%)")
print(f"  MODERATE (6-10 distinct):                   {cat_counts.get('MODERATE',0):>4} ({cat_counts.get('MODERATE',0)/total*100:.1f}%)")
print(f"  LOW_VARIETY (3-5 distinct):                  {cat_counts.get('LOW_VARIETY',0):>4} ({cat_counts.get('LOW_VARIETY',0)/total*100:.1f}%)")
print(f"  FROZEN_WITH_VALUES (1-2 distinct, not blank):{cat_counts.get('FROZEN_WITH_VALUES',0):>4} ({cat_counts.get('FROZEN_WITH_VALUES',0)/total*100:.1f}%)")
print(f"  NO_OU_DATA (all O/U columns blank):          {cat_counts.get('NO_OU_DATA',0):>4} ({cat_counts.get('NO_OU_DATA',0)/total*100:.1f}%)")

print(f"\n  KEY FINDINGS:")
if cat_counts.get('FROZEN_WITH_VALUES', 0) > 0:
    print(f"  - {cat_counts['FROZEN_WITH_VALUES']} matches have O/U data that is stuck at fixed values")
    print(f"    These need investigation: the scraper reads O/U values but they never update")
else:
    print(f"  - NO matches have 'stuck' O/U values (all frozen matches have BLANK O/U)")
    print(f"    This means Betfair simply doesn't offer O/U markets for those matches")
    print(f"    The issue is NOT stale/cached data; the O/U market simply doesn't exist")
    print(f"    for {cat_counts.get('NO_OU_DATA',0)} out of {total} matches")

if cat_counts.get('NO_OU_DATA', 0) > 0:
    # Check if no-OU matches still have 1X2
    no_ou_with_1x2 = sum(1 for m in match_stats
                         if m["category"] == "NO_OU_DATA" and m["distinct_1x2_home"] >= 5)
    print(f"\n  - Of the {cat_counts['NO_OU_DATA']} no-O/U matches:")
    print(f"    {no_ou_with_1x2} have updating 1X2 odds (match is tracked, just no O/U market)")
    no_ou_no_1x2 = cat_counts['NO_OU_DATA'] - no_ou_with_1x2
    print(f"    {no_ou_no_1x2} have no updating 1X2 either (potentially dead/abandoned scrapes)")
