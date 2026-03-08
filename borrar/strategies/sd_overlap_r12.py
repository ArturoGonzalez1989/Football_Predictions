"""
R12 Overlap analysis: H70 and H71 vs existing strategies
"""
import os, glob, csv, math, json
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "betfair_scraper", "data")

def _f(val):
    try:
        v = float(val)
        return v if not math.isnan(v) else None
    except (TypeError, ValueError):
        return None

def _i(val):
    v = _f(val)
    return int(v) if v is not None else None

# Load H70 and H71 match_ids
with open(os.path.join(os.path.dirname(__file__), "sd_bt_h70_bets.json"), encoding="utf-8") as f:
    h70_ids = set(b["match_id"] for b in json.load(f)["bets"])

with open(os.path.join(os.path.dirname(__file__), "sd_bt_h71_bets.json"), encoding="utf-8") as f:
    h71_ids = set(b["match_id"] for b in json.load(f)["bets"])

print(f"H70 match_ids: {len(h70_ids)}")
print(f"H71 match_ids: {len(h71_ids)}")

# Check overlap between H70 and H71
overlap_70_71 = h70_ids & h71_ids
print(f"\nH70 vs H71 overlap: {len(overlap_70_71)} matches ({len(overlap_70_71)/len(h70_ids)*100:.1f}% of H70, {len(overlap_70_71)/len(h71_ids)*100:.1f}% of H71)")
print(f"  Note: Different markets (MO home vs Under 4.5), so overlap is harmless")

# Simulate existing strategies to check overlap
# H59: BACK Underdog Leading Late (min 60-80, underdog leading, back_away or back_home)
# H67: BACK Away Fav Leading Late (min 65-85, away fav leading, back_away)
# H66: BACK Under 3.5 Three-Goal Lid (3 goals, xG<2.5, min 65-80)
# H46: BACK Under 2.5 One-Goal Late (1 goal, min 70-85)
# H53: BACK CS 1-0/0-1 Late Lock (min 68-85, score 1-0/0-1)
# H49: BACK CS 2-1/1-2 (min 68-85, score 2-1/1-2)
# H58: BACK Draw 1-1 Late (min 70-85, score 1-1)

# For simplicity, simulate which matches would trigger each existing strategy
pattern = os.path.join(DATA_DIR, "partido_*.csv")
files = glob.glob(pattern)

existing_ids = defaultdict(set)

for fpath in files:
    rows = []
    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except Exception:
        continue
    if len(rows) < 5:
        continue
    last = rows[-1]
    gl_ft = _i(last.get("goles_local", ""))
    gv_ft = _i(last.get("goles_visitante", ""))
    if gl_ft is None or gv_ft is None:
        continue
    mid = os.path.basename(fpath).replace("partido_", "").replace(".csv", "")

    r0 = rows[0]
    bh0 = _f(r0.get("back_home", ""))
    ba0 = _f(r0.get("back_away", ""))

    for r in rows:
        mn = _f(r.get("minuto", ""))
        if mn is None:
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue

        # H59: Underdog leading 60-80
        if 60 <= mn <= 80 and bh0 is not None and ba0 is not None:
            if bh0 < ba0 and gv > gl:  # home fav, away (underdog) leading
                existing_ids["H59"].add(mid)
            elif ba0 < bh0 and gl > gv:  # away fav, home (underdog) leading
                existing_ids["H59"].add(mid)

        # H67: Away fav leading 65-85
        if 65 <= mn <= 85 and ba0 is not None and bh0 is not None:
            if ba0 < bh0 and gv > gl:  # away is fav AND away is leading
                existing_ids["H67"].add(mid)

        # H66: Under 3.5 three goals 65-80
        if 65 <= mn <= 80 and gl + gv == 3:
            xgl = _f(r.get("xg_local", ""))
            xgv = _f(r.get("xg_visitante", ""))
            if xgl is not None and xgv is not None and xgl + xgv < 2.5:
                existing_ids["H66"].add(mid)

        # H46: Under 2.5 one goal 70-85
        if 70 <= mn <= 85 and gl + gv == 1:
            existing_ids["H46"].add(mid)

        # H53: CS 1-0/0-1 68-85
        if 68 <= mn <= 85 and ((gl == 1 and gv == 0) or (gl == 0 and gv == 1)):
            existing_ids["H53"].add(mid)

        # H49: CS 2-1/1-2 68-85
        if 68 <= mn <= 85 and ((gl == 2 and gv == 1) or (gl == 1 and gv == 2)):
            existing_ids["H49"].add(mid)

        # H58: Draw 1-1 70-85
        if 70 <= mn <= 85 and gl == 1 and gv == 1:
            existing_ids["H58"].add(mid)

print("\n" + "="*60)
print("H70 overlap with existing strategies:")
print("="*60)
for strat, ids in sorted(existing_ids.items()):
    overlap = h70_ids & ids
    pct = len(overlap) / len(h70_ids) * 100 if h70_ids else 0
    market_note = ""
    if strat == "H67":
        market_note = " (SAME market MO, but H70=home fav, H67=away fav -> MUTUALLY EXCLUSIVE)"
    elif strat == "H59":
        market_note = " (SAME market MO, but H70=fav leading, H59=underdog leading -> MUTUALLY EXCLUSIVE)"
    print(f"  vs {strat}: {len(overlap)}/{len(h70_ids)} = {pct:.1f}%{market_note}")

print("\n" + "="*60)
print("H71 overlap with existing strategies:")
print("="*60)
for strat, ids in sorted(existing_ids.items()):
    overlap = h71_ids & ids
    pct = len(overlap) / len(h71_ids) * 100 if h71_ids else 0
    market_note = ""
    if strat == "H66":
        market_note = " (RELATED: H66=U3.5 at 3 goals, H71=U4.5 at 3 goals -> different market but same trigger)"
    print(f"  vs {strat}: {len(overlap)}/{len(h71_ids)} = {pct:.1f}%{market_note}")

# Critical check: H70 vs H67 mutual exclusivity
print("\n" + "="*60)
print("H70 vs H67 MUTUAL EXCLUSIVITY CHECK")
print("="*60)
both = h70_ids & existing_ids.get("H67", set())
print(f"Matches where both H70 and H67 trigger: {len(both)}")
if both:
    print(f"  IDs: {sorted(both)[:10]}")
    print("  NOTE: These should be 0 since H70=home fav leading, H67=away fav leading")
    print("  If non-zero, there may be matches where home switches from fav to non-fav during the match")

# H70 vs H59
both_59 = h70_ids & existing_ids.get("H59", set())
print(f"\nMatches where both H70 and H59 trigger: {len(both_59)}")
if both_59:
    print(f"  NOTE: H70=home fav leading, H59=underdog leading. Should be 0.")

print("\nDone.")
