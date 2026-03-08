"""
Round 13 Exploration - Focus on unexploited niches:
1. First-half patterns (min 20-45) -- almost all existing strategies are min 55+
2. LAY home/away (not Over/Under) -- unexplored direction
3. BACK Over 1.5/3.5 -- mixed evidence, check with new angles
4. Correct scores different from 0-0, 1-0, 2-1
5. Stat combinations: SoT ratio, xG delta, corners+possession
6. Odds drift + stats combinations
7. Score at half-time -> second half patterns
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
files = glob.glob(pattern)
print(f"Total CSVs: {len(files)}")

# Load all matches
matches = []
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
    matches.append({
        "file": os.path.basename(fpath),
        "match_id": os.path.basename(fpath).replace("partido_", "").replace(".csv", ""),
        "ft_local": gl,
        "ft_visitante": gv,
        "ft_total": gl + gv,
        "rows": rows,
        "ts": rows[0].get("timestamp_utc", ""),
    })

print(f"Finished matches loaded: {len(matches)}")
print()

# ====================================================================
# 1. FIRST HALF ANALYSIS: What happens at HT and after?
# ====================================================================
print("=" * 70)
print("1. HALF-TIME SCORE DISTRIBUTION & SECOND HALF PATTERNS")
print("=" * 70)

ht_scores = Counter()
ht_to_ft = defaultdict(list)

for m in matches:
    # Find HT row (closest to min 45)
    ht_row = None
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is not None and 43 <= mi <= 48:
            ht_row = row
            break
    if ht_row is None:
        # Try wider range
        for row in m["rows"]:
            mi = _f(row.get("minuto", ""))
            if mi is not None and 40 <= mi <= 50:
                ht_row = row
                break
    if ht_row is None:
        continue
    gl_ht = _i(ht_row.get("goles_local", ""))
    gv_ht = _i(ht_row.get("goles_visitante", ""))
    if gl_ht is None or gv_ht is None:
        continue

    ht_key = f"{gl_ht}-{gv_ht}"
    ht_scores[ht_key] += 1

    # Second half goals
    sh_local = m["ft_local"] - gl_ht
    sh_visit = m["ft_visitante"] - gv_ht
    ht_to_ft[ht_key].append({
        "ft_local": m["ft_local"], "ft_visitante": m["ft_visitante"],
        "sh_local": sh_local, "sh_visit": sh_visit,
        "sh_total": sh_local + sh_visit,
        "ft_key": f"{m['ft_local']}-{m['ft_visitante']}",
        "match_id": m["match_id"],
    })

print(f"Matches with HT data: {sum(ht_scores.values())}")
print("\nHT score distribution:")
for ht, cnt in sorted(ht_scores.items(), key=lambda x: -x[1])[:15]:
    pct = cnt / sum(ht_scores.values()) * 100
    # Second half analysis
    entries = ht_to_ft[ht]
    avg_sh_goals = sum(e["sh_total"] for e in entries) / len(entries)
    draws_ft = sum(1 for e in entries if e["ft_local"] == e["ft_visitante"])
    draw_pct = draws_ft / len(entries) * 100
    # Hold rate (HT leader still wins)
    parts = ht.split("-")
    ht_gl, ht_gv = int(parts[0]), int(parts[1])
    if ht_gl > ht_gv:
        holds = sum(1 for e in entries if e["ft_local"] > e["ft_visitante"])
        hold_pct = holds / len(entries) * 100
        print(f"  {ht}: {cnt} ({pct:.1f}%) | avg 2H goals: {avg_sh_goals:.2f} | "
              f"FT Draw: {draw_pct:.1f}% | Home holds: {hold_pct:.1f}%")
    elif ht_gv > ht_gl:
        holds = sum(1 for e in entries if e["ft_visitante"] > e["ft_local"])
        hold_pct = holds / len(entries) * 100
        print(f"  {ht}: {cnt} ({pct:.1f}%) | avg 2H goals: {avg_sh_goals:.2f} | "
              f"FT Draw: {draw_pct:.1f}% | Away holds: {hold_pct:.1f}%")
    else:
        print(f"  {ht}: {cnt} ({pct:.1f}%) | avg 2H goals: {avg_sh_goals:.2f} | "
              f"FT Draw: {draw_pct:.1f}%")

# ====================================================================
# 2. FIRST-HALF STAT DOMINANCE -> SECOND HALF OUTCOMES
# ====================================================================
print("\n" + "=" * 70)
print("2. FIRST-HALF STAT DOMINANCE (min 30-45) -> OUTCOMES")
print("=" * 70)

# Check who dominates at min 35-45 via SoT ratio, xG delta, possession
fh_dom_results = []
for m in matches:
    # Find row around min 35-40
    fh_row = None
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is not None and 33 <= mi <= 42:
            fh_row = row
            break
    if fh_row is None:
        continue

    sot_l = _f(fh_row.get("tiros_puerta_local", ""))
    sot_v = _f(fh_row.get("tiros_puerta_visitante", ""))
    xg_l = _f(fh_row.get("xg_local", ""))
    xg_v = _f(fh_row.get("xg_visitante", ""))
    poss_l = _f(fh_row.get("posesion_local", ""))
    gl = _i(fh_row.get("goles_local", ""))
    gv = _i(fh_row.get("goles_visitante", ""))
    back_home = _f(fh_row.get("back_home", ""))
    back_away = _f(fh_row.get("back_away", ""))
    back_o15 = _f(fh_row.get("back_over15", ""))
    back_o25 = _f(fh_row.get("back_over25", ""))

    if sot_l is None or sot_v is None or gl is None or gv is None:
        continue

    fh_dom_results.append({
        "match_id": m["match_id"],
        "sot_l": sot_l, "sot_v": sot_v,
        "xg_l": xg_l, "xg_v": xg_v,
        "poss_l": poss_l,
        "gl_ht": gl, "gv_ht": gv,
        "ft_local": m["ft_local"], "ft_visitante": m["ft_visitante"],
        "ft_total": m["ft_total"],
        "back_home": back_home, "back_away": back_away,
        "back_o15": back_o15, "back_o25": back_o25,
    })

print(f"Matches with FH stat data at min 35: {len(fh_dom_results)}")

# SoT dominance at FH: one team has 3+ SoT, other has 0-1
sot_dom_0_0 = [r for r in fh_dom_results
               if r["gl_ht"] == 0 and r["gv_ht"] == 0
               and ((r["sot_l"] >= 3 and r["sot_v"] <= 1) or (r["sot_v"] >= 3 and r["sot_l"] <= 1))]
print(f"\n  SoT dominant (>=3 vs <=1) at 0-0 in FH: {len(sot_dom_0_0)}")
if sot_dom_0_0:
    # Does the dominant team score in 2H?
    dom_scores = 0
    for r in sot_dom_0_0:
        if r["sot_l"] >= 3:
            dom_scores += 1 if r["ft_local"] > 0 else 0
        else:
            dom_scores += 1 if r["ft_visitante"] > 0 else 0
    print(f"    Dominant team scores in 2H: {dom_scores}/{len(sot_dom_0_0)} ({dom_scores/len(sot_dom_0_0)*100:.1f}%)")

    total_goals_2h = sum(r["ft_total"] for r in sot_dom_0_0)
    avg_goals = total_goals_2h / len(sot_dom_0_0)
    o15_rate = sum(1 for r in sot_dom_0_0 if r["ft_total"] >= 2) / len(sot_dom_0_0) * 100
    o25_rate = sum(1 for r in sot_dom_0_0 if r["ft_total"] >= 3) / len(sot_dom_0_0) * 100
    print(f"    Avg FT goals: {avg_goals:.2f} | Over 1.5 rate: {o15_rate:.1f}% | Over 2.5 rate: {o25_rate:.1f}%")

# xG dominance at FH: one team xG >= 0.8, other <= 0.2, still 0-0
xg_dom_0_0 = [r for r in fh_dom_results
              if r["gl_ht"] == 0 and r["gv_ht"] == 0
              and r["xg_l"] is not None and r["xg_v"] is not None
              and ((r["xg_l"] >= 0.8 and r["xg_v"] <= 0.3) or (r["xg_v"] >= 0.8 and r["xg_l"] <= 0.3))]
print(f"\n  xG dominant (>=0.8 vs <=0.3) at 0-0 in FH: {len(xg_dom_0_0)}")
if xg_dom_0_0:
    dom_scores = 0
    for r in xg_dom_0_0:
        if r["xg_l"] >= 0.8:
            dom_scores += 1 if r["ft_local"] > 0 else 0
        else:
            dom_scores += 1 if r["ft_visitante"] > 0 else 0
    print(f"    Dominant team scores: {dom_scores}/{len(xg_dom_0_0)} ({dom_scores/len(xg_dom_0_0)*100:.1f}%)")
    o15_rate = sum(1 for r in xg_dom_0_0 if r["ft_total"] >= 2) / len(xg_dom_0_0) * 100
    print(f"    Over 1.5 rate: {o15_rate:.1f}%")

# ====================================================================
# 3. LAY HOME/AWAY PATTERNS (not Over/Under)
# ====================================================================
print("\n" + "=" * 70)
print("3. LAY HOME/AWAY - POTENTIAL EDGES")
print("=" * 70)

# LAY Home at first half when away dominates stats
# LAY Away when home dominates
# Key: find situations where odds are LOW but team loses

for m in matches:
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is None:
            continue

# Explore LAY home when home is losing at various minutes
lay_home_scenarios = []
for m in matches:
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is None or mi < 25 or mi > 45:
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        bh = _f(row.get("back_home", ""))
        lh = _f(row.get("lay_home", ""))
        ba = _f(row.get("back_away", ""))
        xg_l = _f(row.get("xg_local", ""))
        xg_v = _f(row.get("xg_visitante", ""))
        sot_l = _f(row.get("tiros_puerta_local", ""))
        sot_v = _f(row.get("tiros_puerta_visitante", ""))

        if gl is None or gv is None or lh is None:
            continue

        lay_home_scenarios.append({
            "match_id": m["match_id"],
            "minuto": mi,
            "gl": gl, "gv": gv,
            "lay_home": lh, "back_home": bh,
            "back_away": ba,
            "xg_l": xg_l, "xg_v": xg_v,
            "sot_l": sot_l, "sot_v": sot_v,
            "ft_local": m["ft_local"], "ft_visitante": m["ft_visitante"],
        })
        break  # first row in range per match

print(f"Matches with FH LAY home data (min 25-45): {len(lay_home_scenarios)}")

# LAY Home when home leads 1-0 but away dominates stats (SoT, xG)
# The idea: home scored but doesn't deserve the lead
lay_home_undeserved = [s for s in lay_home_scenarios
                       if s["gl"] == 1 and s["gv"] == 0
                       and s["xg_l"] is not None and s["xg_v"] is not None
                       and s["sot_l"] is not None and s["sot_v"] is not None
                       and s["xg_v"] >= s["xg_l"]  # away has better xG
                       and s["sot_v"] >= s["sot_l"]]  # away has more SoT
print(f"\n  Home leads 1-0 but away dominates xG+SoT at FH: {len(lay_home_undeserved)}")
if lay_home_undeserved:
    home_loses = sum(1 for s in lay_home_undeserved if s["ft_local"] <= s["ft_visitante"])
    print(f"    Home fails to win FT: {home_loses}/{len(lay_home_undeserved)} ({home_loses/len(lay_home_undeserved)*100:.1f}%)")
    avg_lh = sum(s["lay_home"] for s in lay_home_undeserved) / len(lay_home_undeserved)
    print(f"    Avg LAY home odds: {avg_lh:.2f}")

# LAY Away when away team has low odds but home dominates
lay_away_scenarios = []
for m in matches:
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is None or mi < 25 or mi > 45:
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        la = _f(row.get("lay_away", ""))
        ba = _f(row.get("back_away", ""))

        if gl is None or gv is None or la is None:
            continue

        lay_away_scenarios.append({
            "match_id": m["match_id"],
            "minuto": mi,
            "gl": gl, "gv": gv,
            "lay_away": la, "back_away": ba,
            "ft_local": m["ft_local"], "ft_visitante": m["ft_visitante"],
        })
        break

# ====================================================================
# 4. CORRECT SCORE ANALYSIS - UNEXPLOITED SCORELINES
# ====================================================================
print("\n" + "=" * 70)
print("4. CORRECT SCORE - UNEXPLOITED SCORELINES")
print("=" * 70)

# Existing CS strategies: 0-0 (dead), 1-0/0-1 (H53), 2-1/1-2 (H49), 2-0/0-2 (H55 monitoring), 3-0/0-3 (H65 monitoring)
# Unexploited: 1-1, 2-2, 3-1/1-3, 2-0/0-2 with better params

# CS hold rates at different minutes
for score in ["1-1", "2-2", "3-1", "1-3", "2-0", "0-2"]:
    parts = score.split("-")
    s_gl, s_gv = int(parts[0]), int(parts[1])

    for min_range in [(55, 65), (65, 75), (70, 80), (75, 85)]:
        triggers = 0
        holds = 0
        odds_sum = 0

        for m in matches:
            triggered = False
            for row in m["rows"]:
                mi = _f(row.get("minuto", ""))
                if mi is None or mi < min_range[0] or mi > min_range[1]:
                    continue
                gl = _i(row.get("goles_local", ""))
                gv = _i(row.get("goles_visitante", ""))
                if gl != s_gl or gv != s_gv:
                    continue

                cs_col = f"back_rc_{s_gl}_{s_gv}"
                cs_odds = _f(row.get(cs_col, ""))
                if cs_odds is None or cs_odds < 1.01:
                    continue

                if not triggered:
                    triggered = True
                    triggers += 1
                    odds_sum += cs_odds
                    if m["ft_local"] == s_gl and m["ft_visitante"] == s_gv:
                        holds += 1
                    break

        if triggers >= 20:
            wr = holds / triggers * 100
            avg_o = odds_sum / triggers
            implied = 100 / avg_o
            edge = wr - implied
            roi = (holds * (avg_o - 1) * 0.95 - (triggers - holds)) / triggers * 100
            print(f"  CS {score} at min {min_range[0]}-{min_range[1]}: "
                  f"N={triggers}, WR={wr:.1f}%, avg_odds={avg_o:.2f}, "
                  f"implied={implied:.1f}%, edge={edge:+.1f}pp, ROI={roi:.1f}%")

# ====================================================================
# 5. ODDS DRIFT IN FIRST HALF + STATS
# ====================================================================
print("\n" + "=" * 70)
print("5. ODDS DRIFT IN FIRST HALF (min 20-45)")
print("=" * 70)

# Track odds movement over 10-minute windows in first half
drift_events = []
for m in matches:
    rows = m["rows"]
    for i, row in enumerate(rows):
        mi = _f(row.get("minuto", ""))
        if mi is None or mi < 30 or mi > 45:
            continue
        bh_now = _f(row.get("back_home", ""))
        ba_now = _f(row.get("back_away", ""))
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))

        if bh_now is None or ba_now is None or gl is None:
            continue

        # Find odds 10 min earlier
        bh_prev = ba_prev = None
        for j in range(max(0, i-15), i):
            mj = _f(rows[j].get("minuto", ""))
            if mj is not None and abs(mj - (mi - 10)) < 3:
                bh_prev = _f(rows[j].get("back_home", ""))
                ba_prev = _f(rows[j].get("back_away", ""))
                break

        if bh_prev is None or ba_prev is None or bh_prev < 1.01:
            continue

        drift_home = (bh_now - bh_prev) / bh_prev * 100
        drift_away = (ba_now - ba_prev) / ba_prev * 100

        drift_events.append({
            "match_id": m["match_id"],
            "minuto": mi,
            "gl": gl, "gv": gv,
            "bh_now": bh_now, "bh_prev": bh_prev,
            "ba_now": ba_now, "ba_prev": ba_prev,
            "drift_home": drift_home, "drift_away": drift_away,
            "ft_local": m["ft_local"], "ft_visitante": m["ft_visitante"],
        })
        break

print(f"Matches with FH drift data: {len(drift_events)}")

# Home odds drifting UP (getting worse) at 0-0 -- market losing confidence
# But if stats show home is dominant, this might be value
home_drift_up_0_0 = [d for d in drift_events if d["gl"] == 0 and d["gv"] == 0 and d["drift_home"] >= 15]
print(f"\n  Home odds drift UP >=15% at 0-0 (min 30-45): {len(home_drift_up_0_0)}")
if home_drift_up_0_0:
    home_wins = sum(1 for d in home_drift_up_0_0 if d["ft_local"] > d["ft_visitante"])
    print(f"    Home wins FT: {home_wins}/{len(home_drift_up_0_0)} ({home_wins/len(home_drift_up_0_0)*100:.1f}%)")

# Away odds drifting DOWN (getting better = market favoring away more)
# If away was already favourite and odds keep dropping at 0-0
away_getting_fav = [d for d in drift_events if d["gl"] == 0 and d["gv"] == 0
                     and d["drift_away"] <= -15 and d["ba_now"] < d["bh_now"]]
print(f"\n  Away odds drop >=15% at 0-0 (away becoming more fav): {len(away_getting_fav)}")
if away_getting_fav:
    away_wins = sum(1 for d in away_getting_fav if d["ft_visitante"] > d["ft_local"])
    print(f"    Away wins FT: {away_wins}/{len(away_getting_fav)} ({away_wins/len(away_getting_fav)*100:.1f}%)")

# ====================================================================
# 6. FIRST-HALF LEADER PATTERNS (min 25-45)
# ====================================================================
print("\n" + "=" * 70)
print("6. FIRST-HALF LEADER -> FULL-TIME OUTCOMES")
print("=" * 70)

fh_leader = []
for m in matches:
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is None or mi < 25 or mi > 42:
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        bh = _f(row.get("back_home", ""))
        ba = _f(row.get("back_away", ""))

        if gl is None or gv is None or bh is None:
            continue
        if gl == gv:
            continue  # tied

        leader = "home" if gl > gv else "away"
        margin = abs(gl - gv)
        leader_odds = bh if leader == "home" else ba

        # Check if leader was favourite pre-match (odds at min 1-5)
        pre_home = pre_away = None
        for r2 in m["rows"][:5]:
            pre_home = _f(r2.get("back_home", ""))
            pre_away = _f(r2.get("back_away", ""))
            if pre_home and pre_away:
                break

        pre_fav = None
        if pre_home and pre_away:
            pre_fav = "home" if pre_home < pre_away else "away"

        is_underdog = (pre_fav is not None and leader != pre_fav)

        fh_leader.append({
            "match_id": m["match_id"],
            "minuto": mi,
            "leader": leader,
            "margin": margin,
            "leader_odds": leader_odds,
            "is_underdog": is_underdog,
            "pre_fav": pre_fav,
            "ft_local": m["ft_local"], "ft_visitante": m["ft_visitante"],
        })
        break

print(f"Matches with FH leader (min 25-42): {len(fh_leader)}")

# Home leads at FH
home_leads = [f for f in fh_leader if f["leader"] == "home"]
if home_leads:
    holds = sum(1 for f in home_leads if f["ft_local"] > f["ft_visitante"])
    print(f"\n  Home leads at FH: {len(home_leads)}, holds to win: {holds} ({holds/len(home_leads)*100:.1f}%)")
    avg_odds = sum(f["leader_odds"] for f in home_leads if f["leader_odds"]) / len(home_leads)
    print(f"    Avg leader odds: {avg_odds:.2f}")

# Away leads at FH
away_leads = [f for f in fh_leader if f["leader"] == "away"]
if away_leads:
    holds = sum(1 for f in away_leads if f["ft_visitante"] > f["ft_local"])
    print(f"\n  Away leads at FH: {len(away_leads)}, holds to win: {holds} ({holds/len(away_leads)*100:.1f}%)")
    avg_odds = sum(f["leader_odds"] for f in away_leads if f["leader_odds"]) / len(away_leads)
    print(f"    Avg leader odds: {avg_odds:.2f}")

# Underdog leads at FH -- potentially high value
ud_leads = [f for f in fh_leader if f["is_underdog"]]
if ud_leads:
    holds = sum(1 for f in ud_leads
                if (f["leader"] == "home" and f["ft_local"] > f["ft_visitante"]) or
                   (f["leader"] == "away" and f["ft_visitante"] > f["ft_local"]))
    print(f"\n  Underdog leads at FH: {len(ud_leads)}, holds to win: {holds} ({holds/len(ud_leads)*100:.1f}%)")
    avg_odds = sum(f["leader_odds"] for f in ud_leads if f["leader_odds"]) / len(ud_leads)
    print(f"    Avg leader odds: {avg_odds:.2f}")

# ====================================================================
# 7. BACK OVER 3.5 - EARLY HIGH ACTIVITY
# ====================================================================
print("\n" + "=" * 70)
print("7. BACK OVER 3.5 - WHEN ALREADY 2+ GOALS BY MIN 35")
print("=" * 70)

o35_fh = []
for m in matches:
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is None or mi < 25 or mi > 45:
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        total = (gl or 0) + (gv or 0)
        bo35 = _f(row.get("back_over35", ""))
        xg_l = _f(row.get("xg_local", ""))
        xg_v = _f(row.get("xg_visitante", ""))
        sot_l = _f(row.get("tiros_puerta_local", ""))
        sot_v = _f(row.get("tiros_puerta_visitante", ""))

        if gl is None or gv is None or bo35 is None:
            continue
        if total < 2:
            continue

        xg_total = (xg_l or 0) + (xg_v or 0) if xg_l is not None and xg_v is not None else None
        sot_total = (sot_l or 0) + (sot_v or 0) if sot_l is not None and sot_v is not None else None

        o35_fh.append({
            "match_id": m["match_id"],
            "minuto": mi,
            "total_goals": total,
            "back_o35": bo35,
            "xg_total": xg_total,
            "sot_total": sot_total,
            "ft_total": m["ft_total"],
        })
        break

print(f"Matches with 2+ goals by min 25-45 and O3.5 odds: {len(o35_fh)}")
if o35_fh:
    wins = sum(1 for o in o35_fh if o["ft_total"] >= 4)
    avg_odds = sum(o["back_o35"] for o in o35_fh) / len(o35_fh)
    wr = wins / len(o35_fh) * 100
    implied = 100 / avg_odds
    roi = (wins * (avg_odds - 1) * 0.95 - (len(o35_fh) - wins)) / len(o35_fh) * 100
    print(f"  All: N={len(o35_fh)}, WR={wr:.1f}%, avg_odds={avg_odds:.2f}, implied={implied:.1f}%, ROI={roi:.1f}%")

    # With xG filter
    xg_high = [o for o in o35_fh if o["xg_total"] is not None and o["xg_total"] >= 1.5]
    if xg_high:
        wins_xg = sum(1 for o in xg_high if o["ft_total"] >= 4)
        avg_o_xg = sum(o["back_o35"] for o in xg_high) / len(xg_high)
        wr_xg = wins_xg / len(xg_high) * 100
        roi_xg = (wins_xg * (avg_o_xg - 1) * 0.95 - (len(xg_high) - wins_xg)) / len(xg_high) * 100
        print(f"  xG>=1.5: N={len(xg_high)}, WR={wr_xg:.1f}%, avg_odds={avg_o_xg:.2f}, ROI={roi_xg:.1f}%")

# ====================================================================
# 8. CS 1-1 AT VARIOUS MINUTES
# ====================================================================
print("\n" + "=" * 70)
print("8. CS 1-1 HOLD RATES (different from Draw 1-1 -- CS market)")
print("=" * 70)

for min_lo, min_hi in [(55, 65), (60, 70), (65, 75), (70, 80), (75, 85)]:
    triggers = 0
    holds = 0
    odds_sum = 0
    for m in matches:
        triggered = False
        for row in m["rows"]:
            mi = _f(row.get("minuto", ""))
            if mi is None or mi < min_lo or mi > min_hi:
                continue
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if gl != 1 or gv != 1:
                continue
            cs_odds = _f(row.get("back_rc_1_1", ""))
            if cs_odds is None or cs_odds < 1.01:
                continue
            if not triggered:
                triggered = True
                triggers += 1
                odds_sum += cs_odds
                if m["ft_local"] == 1 and m["ft_visitante"] == 1:
                    holds += 1
                break
    if triggers >= 10:
        wr = holds / triggers * 100
        avg_o = odds_sum / triggers
        implied = 100 / avg_o
        edge = wr - implied
        roi = (holds * (avg_o - 1) * 0.95 - (triggers - holds)) / triggers * 100
        print(f"  CS 1-1 at min {min_lo}-{min_hi}: N={triggers}, WR={wr:.1f}%, "
              f"avg_odds={avg_o:.2f}, implied={implied:.1f}%, edge={edge:+.1f}pp, ROI={roi:.1f}%")

# ====================================================================
# 9. LAY HOME AT FIRST HALF: HOME LEADS BUT STATS SAY OTHERWISE
# ====================================================================
print("\n" + "=" * 70)
print("9. LAY HOME FH: Home leads 1-0 at min 30-45 but stats dominated by away")
print("=" * 70)

lay_home_fh = []
for m in matches:
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is None or mi < 30 or mi > 45:
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        if gl != 1 or gv != 0:
            continue

        lh = _f(row.get("lay_home", ""))
        xg_l = _f(row.get("xg_local", ""))
        xg_v = _f(row.get("xg_visitante", ""))
        sot_l = _f(row.get("tiros_puerta_local", ""))
        sot_v = _f(row.get("tiros_puerta_visitante", ""))
        poss_l = _f(row.get("posesion_local", ""))

        if lh is None or xg_l is None or xg_v is None:
            continue

        lay_home_fh.append({
            "match_id": m["match_id"],
            "minuto": mi,
            "lay_home": lh,
            "xg_l": xg_l, "xg_v": xg_v,
            "sot_l": sot_l, "sot_v": sot_v,
            "poss_l": poss_l,
            "ft_local": m["ft_local"], "ft_visitante": m["ft_visitante"],
        })
        break

print(f"Home leads 1-0 at min 30-45 with xG data: {len(lay_home_fh)}")

# Away dominates xG at home 1-0
away_dom_xg = [l for l in lay_home_fh if l["xg_v"] > l["xg_l"]]
print(f"  Of which away has higher xG: {len(away_dom_xg)}")
if away_dom_xg:
    home_fails = sum(1 for l in away_dom_xg if l["ft_local"] <= l["ft_visitante"])
    print(f"    Home fails to win FT: {home_fails}/{len(away_dom_xg)} ({home_fails/len(away_dom_xg)*100:.1f}%)")
    avg_lay = sum(l["lay_home"] for l in away_dom_xg) / len(away_dom_xg)
    print(f"    Avg LAY home odds: {avg_lay:.2f}")
    # LAY P/L: win = stake*0.95, loss = -(lay-1)*stake
    wins = home_fails  # LAY wins when home doesn't win
    n = len(away_dom_xg)
    avg_lh = avg_lay
    pl = wins * 10 * 0.95 + (n - wins) * (-(avg_lh - 1) * 10)
    roi = pl / (n * 10) * 100
    print(f"    LAY Home ROI (rough): {roi:.1f}%")

# ====================================================================
# 10. BACK OVER 1.5 at 0-0 FIRST HALF with HIGH ACTIVITY
# ====================================================================
print("\n" + "=" * 70)
print("10. BACK OVER 1.5 at 0-0 min 30-45 with high SoT+xG")
print("=" * 70)

bo15_fh = []
for m in matches:
    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is None or mi < 30 or mi > 45:
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        if gl != 0 or gv != 0:
            continue

        bo15 = _f(row.get("back_over15", ""))
        xg_l = _f(row.get("xg_local", ""))
        xg_v = _f(row.get("xg_visitante", ""))
        sot_l = _f(row.get("tiros_puerta_local", ""))
        sot_v = _f(row.get("tiros_puerta_visitante", ""))

        if bo15 is None or xg_l is None or xg_v is None:
            continue

        xg_tot = xg_l + xg_v
        sot_tot = ((sot_l or 0) + (sot_v or 0)) if sot_l is not None and sot_v is not None else None

        bo15_fh.append({
            "match_id": m["match_id"],
            "minuto": mi,
            "back_o15": bo15,
            "xg_total": xg_tot,
            "sot_total": sot_tot,
            "ft_total": m["ft_total"],
        })
        break

print(f"0-0 at min 30-45 with O1.5 odds: {len(bo15_fh)}")

# Various thresholds
for xg_min in [0.5, 0.8, 1.0, 1.2]:
    for sot_min in [3, 4, 5]:
        subset = [b for b in bo15_fh if b["xg_total"] >= xg_min
                  and b["sot_total"] is not None and b["sot_total"] >= sot_min]
        if len(subset) < 30:
            continue
        wins = sum(1 for b in subset if b["ft_total"] >= 2)
        avg_o = sum(b["back_o15"] for b in subset) / len(subset)
        wr = wins / len(subset) * 100
        implied = 100 / avg_o
        roi = (wins * (avg_o - 1) * 0.95 - (len(subset) - wins)) / len(subset) * 100
        print(f"  xG>={xg_min}, SoT>={sot_min}: N={len(subset)}, WR={wr:.1f}%, "
              f"avg_odds={avg_o:.2f}, implied={implied:.1f}%, edge={wr-implied:+.1f}pp, ROI={roi:.1f}%")

# ====================================================================
# 11. CS 2-2 HOLD RATES (monitoring H68, check deeper)
# ====================================================================
print("\n" + "=" * 70)
print("11. CS 2-2 HOLD RATES")
print("=" * 70)

for min_lo, min_hi in [(60, 70), (65, 75), (70, 80), (75, 85)]:
    triggers = 0
    holds = 0
    odds_sum = 0
    for m in matches:
        triggered = False
        for row in m["rows"]:
            mi = _f(row.get("minuto", ""))
            if mi is None or mi < min_lo or mi > min_hi:
                continue
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if gl != 2 or gv != 2:
                continue
            cs_odds = _f(row.get("back_rc_2_2", ""))
            if cs_odds is None or cs_odds < 1.01:
                continue
            if not triggered:
                triggered = True
                triggers += 1
                odds_sum += cs_odds
                if m["ft_local"] == 2 and m["ft_visitante"] == 2:
                    holds += 1
                break
    if triggers >= 10:
        wr = holds / triggers * 100
        avg_o = odds_sum / triggers
        implied = 100 / avg_o
        edge = wr - implied
        roi = (holds * (avg_o - 1) * 0.95 - (triggers - holds)) / triggers * 100
        print(f"  CS 2-2 at min {min_lo}-{min_hi}: N={triggers}, WR={wr:.1f}%, "
              f"avg_odds={avg_o:.2f}, implied={implied:.1f}%, edge={edge:+.1f}pp, ROI={roi:.1f}%")

# ====================================================================
# 12. BACK UNDERDOG LEADING IN FIRST HALF (extension of H59 to earlier)
# ====================================================================
print("\n" + "=" * 70)
print("12. BACK UNDERDOG LEADING AT FIRST HALF (min 25-45)")
print("=" * 70)

ud_fh = [f for f in fh_leader if f["is_underdog"]]
if ud_fh:
    for max_odds in [3.0, 4.0, 5.0, 8.0]:
        subset = [f for f in ud_fh if f["leader_odds"] is not None and f["leader_odds"] <= max_odds]
        if len(subset) < 20:
            continue
        wins = sum(1 for f in subset
                   if (f["leader"] == "home" and f["ft_local"] > f["ft_visitante"]) or
                      (f["leader"] == "away" and f["ft_visitante"] > f["ft_local"]))
        avg_o = sum(f["leader_odds"] for f in subset) / len(subset)
        wr = wins / len(subset) * 100
        implied = 100 / avg_o
        roi = (wins * (avg_o - 1) * 0.95 - (len(subset) - wins)) / len(subset) * 100
        print(f"  UD leads FH, odds<={max_odds}: N={len(subset)}, WR={wr:.1f}%, "
              f"avg_odds={avg_o:.2f}, implied={implied:.1f}%, ROI={roi:.1f}%")

# ====================================================================
# 13. FIRST HALF: BACK HOME when trailing 0-1 but is HEAVY favourite
# ====================================================================
print("\n" + "=" * 70)
print("13. HOME FAVOURITE TRAILING 0-1 AT FIRST HALF")
print("=" * 70)

home_fav_trailing = []
for m in matches:
    # Get pre-match odds
    pre_home = None
    for r in m["rows"][:5]:
        ph = _f(r.get("back_home", ""))
        if ph and ph > 1.0:
            pre_home = ph
            break
    if pre_home is None or pre_home >= 2.0:  # not a strong favourite
        continue

    for row in m["rows"]:
        mi = _f(row.get("minuto", ""))
        if mi is None or mi < 25 or mi > 45:
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        if gl != 0 or gv != 1:
            continue
        bh = _f(row.get("back_home", ""))
        xg_l = _f(row.get("xg_local", ""))
        xg_v = _f(row.get("xg_visitante", ""))
        sot_l = _f(row.get("tiros_puerta_local", ""))
        sot_v = _f(row.get("tiros_puerta_visitante", ""))

        if bh is None:
            continue

        home_fav_trailing.append({
            "match_id": m["match_id"],
            "pre_home": pre_home,
            "bh_now": bh,
            "xg_l": xg_l, "xg_v": xg_v,
            "sot_l": sot_l, "sot_v": sot_v,
            "ft_local": m["ft_local"], "ft_visitante": m["ft_visitante"],
        })
        break

print(f"Home fav (pre<2.0) trailing 0-1 at FH: {len(home_fav_trailing)}")
if home_fav_trailing:
    wins = sum(1 for h in home_fav_trailing if h["ft_local"] > h["ft_visitante"])
    draws = sum(1 for h in home_fav_trailing if h["ft_local"] == h["ft_visitante"])
    avg_bh = sum(h["bh_now"] for h in home_fav_trailing) / len(home_fav_trailing)
    print(f"  Home wins FT: {wins}/{len(home_fav_trailing)} ({wins/len(home_fav_trailing)*100:.1f}%)")
    print(f"  Home draws FT: {draws}/{len(home_fav_trailing)} ({draws/len(home_fav_trailing)*100:.1f}%)")
    print(f"  Avg BACK home odds: {avg_bh:.2f}")
    # With stat dominance
    dom = [h for h in home_fav_trailing if h["xg_l"] is not None and h["xg_v"] is not None
           and h["xg_l"] > h["xg_v"]]
    if dom:
        dom_wins = sum(1 for h in dom if h["ft_local"] > h["ft_visitante"])
        print(f"  With xG dominance: {len(dom)}, wins: {dom_wins} ({dom_wins/len(dom)*100:.1f}%)")

# ====================================================================
# 14. SCORE AT BREAK -> OVER 1.5 IN SECOND HALF
# ====================================================================
print("\n" + "=" * 70)
print("14. BACK OVER 1.5 GOALS IN 2H (from various HT scores)")
print("=" * 70)

for ht_score in ["0-0", "1-0", "0-1", "1-1"]:
    parts = ht_score.split("-")
    ht_gl, ht_gv = int(parts[0]), int(parts[1])
    entries = ht_to_ft.get(ht_score, [])
    if len(entries) < 20:
        continue

    o15_2h = sum(1 for e in entries if e["sh_total"] >= 2)
    wr = o15_2h / len(entries) * 100
    avg_sh_goals = sum(e["sh_total"] for e in entries) / len(entries)
    print(f"  HT {ht_score}: N={len(entries)}, 2H Over 1.5: {o15_2h} ({wr:.1f}%), avg 2H goals: {avg_sh_goals:.2f}")

print("\n\nExploration complete.")
