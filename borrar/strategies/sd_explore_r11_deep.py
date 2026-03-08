"""
Deep exploration for R11 - targeting specific angles not yet explored.
Focus:
1. BACK Under 0.5 (0-0 stays 0-0) at late minutes - big edge found (11.6pp at min80)
2. BACK Draw at 2-2 late - 2-2 is 18% of draws, different dynamics than 1-1
3. BACK Match Winner for home team in "even" matches with stat dominance
4. Under 3.5 with 3 goals at late minutes - edge=7.4pp at min80
5. Score 2-0/0-2 dynamics -- 2-0 holds only 38-53%, is there a contrarian play?
"""
import os, glob, csv, math
from collections import defaultdict, Counter

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

pattern = os.path.join(DATA_DIR, "partido_*.csv")
files = sorted(glob.glob(pattern))

# ---- A. BACK Under 0.5 at late minutes (0-0 match stays 0-0) ----
print("="*60)
print("A. BACK Under 0.5 LATE (0-0 stays 0-0)")
print("="*60)
# Already know: At min 80, holds 64.7% vs implied 53.1% (edge +11.6pp)
# But we need to check the ODDS distribution to see if value is there
u05_data = defaultdict(list)  # minute_range -> [(odds, won)]

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
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue
    ft_total = gl + gv

    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue
        if cur_gl == 0 and cur_gv == 0:
            odds = _f(row.get("back_under05", ""))
            if odds and 1.01 < odds < 50:
                for rng in [(60, 70), (65, 75), (70, 80), (75, 85), (78, 88)]:
                    if rng[0] <= m <= rng[1]:
                        u05_data[rng].append((odds, ft_total == 0, m))

for rng in sorted(u05_data):
    entries = u05_data[rng]
    # Deduplicate by taking first entry per match approximation (use unique odds values)
    # Actually need match dedup - use all for now
    n = len(entries)
    wins = sum(1 for _, w, _ in entries if w)
    avg_odds = sum(o for o, _, _ in entries) / n
    wr = wins/n*100
    implied = 100/avg_odds
    edge = wr - implied
    print(f"  Min {rng[0]}-{rng[1]}: N={n}, WR={wr:.1f}%, avg_odds={avg_odds:.2f}, implied={implied:.1f}%, edge={edge:+.1f}pp")

# ---- B. BACK Draw 2-2 late ----
print("\n" + "="*60)
print("B. BACK Draw at 2-2 LATE")
print("="*60)
draw22_data = defaultdict(list)

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
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue

    seen = set()
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue
        if cur_gl == 2 and cur_gv == 2:
            odds_draw = _f(row.get("back_draw", ""))
            if odds_draw and 1.01 < odds_draw < 50:
                for rng in [(60, 70), (65, 75), (70, 80), (75, 85)]:
                    if rng[0] <= m <= rng[1] and rng not in seen:
                        seen.add(rng)
                        draw22_data[rng].append((odds_draw, gl == gv, m, os.path.basename(fpath)))

for rng in sorted(draw22_data):
    entries = draw22_data[rng]
    n = len(entries)
    wins = sum(1 for _, w, _, _ in entries if w)
    avg_odds = sum(o for o, _, _, _ in entries) / n
    wr = wins/n*100
    implied = 100/avg_odds
    edge = wr - implied
    print(f"  Min {rng[0]}-{rng[1]}: N={n}, WR={wr:.1f}%, avg_odds={avg_odds:.2f}, implied={implied:.1f}%, edge={edge:+.1f}pp")

# ---- C. Score 2-0/0-2: When does it NOT hold? ----
print("\n" + "="*60)
print("C. Score 2-0/0-2 NON-HOLD analysis (potential BACK Over)")
print("="*60)
score20_data = defaultdict(list)

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
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue
    ft_total = gl + gv

    seen = set()
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue
        # 2-0 or 0-2 at minute
        if (cur_gl == 2 and cur_gv == 0) or (cur_gl == 0 and cur_gv == 2):
            xg_l = _f(row.get("xg_local", ""))
            xg_v = _f(row.get("xg_visitante", ""))
            sot_l = _i(row.get("tiros_puerta_local", ""))
            sot_v = _i(row.get("tiros_puerta_visitante", ""))

            for rng in [(45, 55), (50, 60), (55, 65), (60, 70)]:
                if rng[0] <= m <= rng[1] and rng not in seen:
                    seen.add(rng)
                    # trailing team = the one with 0 goals
                    if cur_gl == 0:
                        trailing_xg = xg_l
                        trailing_sot = sot_l
                    else:
                        trailing_xg = xg_v
                        trailing_sot = sot_v

                    more_goals = ft_total > 2
                    score20_data[rng].append({
                        "more_goals": more_goals,
                        "ft_score": f"{gl}-{gv}",
                        "trailing_xg": trailing_xg,
                        "trailing_sot": trailing_sot,
                        "file": os.path.basename(fpath),
                    })

for rng in sorted(score20_data):
    entries = score20_data[rng]
    n = len(entries)
    more = sum(1 for e in entries if e["more_goals"])
    print(f"\n  2-0/0-2 at min {rng[0]}-{rng[1]}: N={n}, more goals={more} ({more/n*100:.1f}%)")
    # When trailing team has high xG, does that predict more goals?
    with_xg = [e for e in entries if e["trailing_xg"] is not None]
    if with_xg:
        hi_xg = [e for e in with_xg if e["trailing_xg"] >= 0.5]
        lo_xg = [e for e in with_xg if e["trailing_xg"] < 0.5]
        if hi_xg:
            pct = sum(1 for e in hi_xg if e["more_goals"])/len(hi_xg)*100
            print(f"    trailing xG>=0.5: {len(hi_xg)} matches, more_goals={pct:.1f}%")
        if lo_xg:
            pct = sum(1 for e in lo_xg if e["more_goals"])/len(lo_xg)*100
            print(f"    trailing xG<0.5: {len(lo_xg)} matches, more_goals={pct:.1f}%")

# ---- D. BACK Home in Even Matches with SoT dominance ----
print("\n" + "="*60)
print("D. BACK HOME in Even Match (both pre-odds 2.0-3.5) with stat dominance")
print("="*60)
home_dom_data = defaultdict(list)

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
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue

    # Get pre-match odds
    early_home, early_away = None, None
    for row in rows[:5]:
        bh = _f(row.get("back_home", ""))
        ba = _f(row.get("back_away", ""))
        if bh and ba and bh > 1.5 and ba > 1.5:
            early_home = bh
            early_away = ba
            break

    if not early_home or not early_away:
        continue

    seen = set()
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue

        if cur_gl == cur_gv:  # Tied
            sot_l = _i(row.get("tiros_puerta_local", ""))
            sot_v = _i(row.get("tiros_puerta_visitante", ""))
            xg_l = _f(row.get("xg_local", ""))
            xg_v = _f(row.get("xg_visitante", ""))
            poss_l = _f(row.get("posesion_local", ""))
            back_home = _f(row.get("back_home", ""))

            if sot_l is not None and sot_v is not None:
                for rng in [(50, 65), (55, 70), (60, 75)]:
                    if rng[0] <= m <= rng[1] and rng not in seen:
                        # Home dominates SoT
                        if sot_l >= 4 and sot_v <= 2 and sot_l >= sot_v + 2:
                            seen.add(rng)
                            home_dom_data[rng].append({
                                "won": gl > gv,
                                "ft": f"{gl}-{gv}",
                                "odds": back_home,
                                "pre_home": early_home,
                                "pre_away": early_away,
                                "sot_l": sot_l,
                                "sot_v": sot_v,
                                "xg_l": xg_l,
                                "xg_v": xg_v,
                                "poss_l": poss_l,
                            })

for rng in sorted(home_dom_data):
    entries = home_dom_data[rng]
    n = len(entries)
    wins = sum(1 for e in entries if e["won"])
    with_odds = [e for e in entries if e["odds"] and e["odds"] > 1]
    avg_odds = sum(e["odds"] for e in with_odds) / len(with_odds) if with_odds else 0
    wr = wins/n*100
    implied = 100/avg_odds if avg_odds > 1 else 0
    edge = wr - implied
    print(f"  Min {rng[0]}-{rng[1]}: N={n}, WR={wr:.1f}%, avg_odds={avg_odds:.2f}, implied={implied:.1f}%, edge={edge:+.1f}pp")

# ---- E. Under 3.5 with exactly 3 goals at late minutes ----
print("\n" + "="*60)
print("E. BACK Under 3.5 with 3 goals at late minutes")
print("="*60)
u35_3g = defaultdict(list)

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
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue
    ft_total = gl + gv

    seen = set()
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue

        if cur_gl + cur_gv == 3:
            odds = _f(row.get("back_under35", ""))
            xg_total = None
            xg_l = _f(row.get("xg_local", ""))
            xg_v = _f(row.get("xg_visitante", ""))
            if xg_l is not None and xg_v is not None:
                xg_total = xg_l + xg_v

            for rng in [(65, 75), (68, 78), (70, 80), (72, 82), (75, 85)]:
                if rng[0] <= m <= rng[1] and rng not in seen:
                    seen.add(rng)
                    u35_3g[rng].append({
                        "won": ft_total <= 3,
                        "odds": odds,
                        "xg_total": xg_total,
                        "ft_total": ft_total,
                    })

for rng in sorted(u35_3g):
    entries = u35_3g[rng]
    n = len(entries)
    wins = sum(1 for e in entries if e["won"])
    with_odds = [e for e in entries if e["odds"] and e["odds"] > 1]
    avg_odds = sum(e["odds"] for e in with_odds) / len(with_odds) if with_odds else 0
    wr = wins/n*100
    implied = 100/avg_odds if avg_odds > 1 else 0
    edge = wr - implied
    print(f"  Min {rng[0]}-{rng[1]}: N={n}, WR={wr:.1f}%, avg_odds={avg_odds:.2f}, implied={implied:.1f}%, edge={edge:+.1f}pp")

    # xG filter
    lo_xg = [e for e in entries if e["xg_total"] is not None and e["xg_total"] < 3.0]
    hi_xg = [e for e in entries if e["xg_total"] is not None and e["xg_total"] >= 3.0]
    if lo_xg:
        wr_lo = sum(1 for e in lo_xg if e["won"])/len(lo_xg)*100
        print(f"    xG_total<3.0: N={len(lo_xg)}, WR={wr_lo:.1f}%")
    if hi_xg:
        wr_hi = sum(1 for e in hi_xg if e["won"])/len(hi_xg)*100
        print(f"    xG_total>=3.0: N={len(hi_xg)}, WR={wr_hi:.1f}%")

# ---- F. NEW: Match Winner for AWAY team when leading at late minutes ----
print("\n" + "="*60)
print("F. BACK AWAY Winner when leading late (complement to H59)")
print("="*60)
# H59 is underdog leading. What about AWAY team leading (regardless of fav/UD)?
away_leading = defaultdict(list)

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
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue

    seen = set()
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue

        if cur_gv > cur_gl:  # Away leading
            odds_away = _f(row.get("back_away", ""))
            if odds_away and 1.01 < odds_away < 50:
                for rng in [(60, 75), (65, 80), (70, 85), (75, 90)]:
                    if rng[0] <= m <= rng[1] and rng not in seen:
                        seen.add(rng)
                        away_leading[rng].append({
                            "won": gv > gl,
                            "odds": odds_away,
                            "lead": cur_gv - cur_gl,
                        })

for rng in sorted(away_leading):
    entries = away_leading[rng]
    n = len(entries)
    wins = sum(1 for e in entries if e["won"])
    avg_odds = sum(e["odds"] for e in entries) / n
    wr = wins/n*100
    implied = 100/avg_odds
    edge = wr - implied
    print(f"  Min {rng[0]}-{rng[1]}: N={n}, WR={wr:.1f}%, avg_odds={avg_odds:.2f}, implied={implied:.1f}%, edge={edge:+.1f}pp")

    # By lead margin
    for lead in [1, 2]:
        subset = [e for e in entries if e["lead"] == lead]
        if len(subset) >= 10:
            w = sum(1 for e in subset if e["won"])
            ao = sum(e["odds"] for e in subset) / len(subset)
            print(f"    lead={lead}: N={len(subset)}, WR={w/len(subset)*100:.1f}%, avg_odds={ao:.2f}")

# ---- G. NEW: Goal-less second half patterns ----
print("\n" + "="*60)
print("G. BACK Under 0.5 2nd Half (no more goals from HT score)")
print("="*60)
# 22.7% of matches have 0 goals in 2H. Can we identify these early in 2H?
no_2h_goals = defaultdict(list)

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
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue
    ft_total = gl + gv

    ht_total = None
    seen = set()
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue

        if 42 <= m <= 48 and ht_total is None:
            ht_total = cur_gl + cur_gv

        # At minute 55-65, if no goals since HT
        if ht_total is not None and cur_gl + cur_gv == ht_total:
            xg_l = _f(row.get("xg_local", ""))
            xg_v = _f(row.get("xg_visitante", ""))
            sot_l = _i(row.get("tiros_puerta_local", ""))
            sot_v = _i(row.get("tiros_puerta_visitante", ""))

            for rng in [(55, 65), (58, 68), (60, 70), (63, 73), (65, 75)]:
                if rng[0] <= m <= rng[1] and rng not in seen:
                    seen.add(rng)
                    no_2h_goals[rng].append({
                        "no_more_goals": ft_total == ht_total,
                        "ht_total": ht_total,
                        "xg_total": (xg_l + xg_v) if xg_l is not None and xg_v is not None else None,
                        "sot_total": (sot_l + sot_v) if sot_l is not None and sot_v is not None else None,
                    })

for rng in sorted(no_2h_goals):
    entries = no_2h_goals[rng]
    n = len(entries)
    holds = sum(1 for e in entries if e["no_more_goals"])
    print(f"\n  No goals since HT at min {rng[0]}-{rng[1]}: N={n}, no_more_goals={holds/n*100:.1f}%")

    # By HT total goals
    for ht_g in [0, 1, 2, 3]:
        subset = [e for e in entries if e["ht_total"] == ht_g]
        if len(subset) >= 10:
            h = sum(1 for e in subset if e["no_more_goals"])
            print(f"    HT total={ht_g}: N={len(subset)}, no_more={h/len(subset)*100:.1f}%")

# ---- H. NEW: Draw at high-scoring tied games (2-2, 3-3) ----
print("\n" + "="*60)
print("H. BACK Draw at high-scoring tied games")
print("="*60)
hi_draw = defaultdict(list)

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
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue

    seen = set()
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue

        # 2-2 or 3-3
        if cur_gl == cur_gv and cur_gl >= 2:
            odds_draw = _f(row.get("back_draw", ""))
            if odds_draw and 1.01 < odds_draw < 50:
                for rng in [(60, 70), (65, 75), (70, 80), (75, 85)]:
                    if rng[0] <= m <= rng[1] and rng not in seen:
                        seen.add(rng)
                        hi_draw[rng].append({
                            "draw": gl == gv,
                            "odds": odds_draw,
                            "score": f"{cur_gl}-{cur_gv}",
                            "ft": f"{gl}-{gv}",
                        })

for rng in sorted(hi_draw):
    entries = hi_draw[rng]
    n = len(entries)
    wins = sum(1 for e in entries if e["draw"])
    avg_odds = sum(e["odds"] for e in entries) / n
    wr = wins/n*100
    implied = 100/avg_odds
    edge = wr - implied
    print(f"  Min {rng[0]}-{rng[1]}: N={n}, WR={wr:.1f}%, avg_odds={avg_odds:.2f}, implied={implied:.1f}%, edge={edge:+.1f}pp")

    # Breakdown by score
    for sc in ["2-2", "3-3"]:
        subset = [e for e in entries if e["score"] == sc]
        if len(subset) >= 5:
            w = sum(1 for e in subset if e["draw"])
            ao = sum(e["odds"] for e in subset) / len(subset)
            print(f"    {sc}: N={len(subset)}, WR={w/len(subset)*100:.1f}%, avg_odds={ao:.2f}")

print("\n" + "="*60)
print("EXPLORATION COMPLETE")
print("="*60)
