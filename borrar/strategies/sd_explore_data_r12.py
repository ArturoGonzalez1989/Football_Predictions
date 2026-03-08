"""
R12 Data Exploration — Focus on unexploited angles.
Looking for patterns NOT covered by H1-H69.
"""
import os, glob, csv, math, json
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
        "country": last.get("Pa\u00eds", last.get("Pais", "?")),
        "league": last.get("Liga", "?"),
        "ft_local": gl, "ft_visitante": gv, "ft_total": gl + gv,
        "rows": rows,
        "ts": rows[0].get("timestamp_utc", ""),
    })

print(f"Loaded matches: {len(matches)}")

# ============================================================
# 1. HALF-TIME SCORES & SECOND-HALF DYNAMICS
# ============================================================
print("\n" + "="*70)
print("1. HALF-TIME TO FULL-TIME TRANSITIONS")
print("="*70)

ht_ft_transitions = Counter()
ht_scores = Counter()
second_half_goals = []

for m in matches:
    # Find HT row (closest to min 45)
    ht_row = None
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is not None and 44 <= mn <= 48:
            ht_row = r
            break
    if ht_row is None:
        continue
    ht_gl = _i(ht_row.get("goles_local", ""))
    ht_gv = _i(ht_row.get("goles_visitante", ""))
    if ht_gl is None or ht_gv is None:
        continue

    ft_gl, ft_gv = m["ft_local"], m["ft_visitante"]
    goals_2h = (ft_gl - ht_gl) + (ft_gv - ht_gv)
    second_half_goals.append(goals_2h)

    # Classify HT state
    if ht_gl > ht_gv:
        ht_state = "home_lead"
    elif ht_gl < ht_gv:
        ht_state = "away_lead"
    else:
        ht_state = "tied"

    # Classify FT outcome
    if ft_gl > ft_gv:
        ft_result = "home_win"
    elif ft_gl < ft_gv:
        ft_result = "away_win"
    else:
        ft_result = "draw"

    ht_ft_transitions[(ht_state, ft_result)] += 1
    ht_scores[(ht_gl, ht_gv)] += 1

print("\nHT state -> FT outcome:")
for ht_state in ["home_lead", "away_lead", "tied"]:
    total = sum(v for (h, _), v in ht_ft_transitions.items() if h == ht_state)
    if total == 0:
        continue
    print(f"\n  {ht_state} (N={total}):")
    for ft_result in ["home_win", "away_win", "draw"]:
        count = ht_ft_transitions.get((ht_state, ft_result), 0)
        print(f"    -> {ft_result}: {count} ({count/total*100:.1f}%)")

print(f"\nSecond half avg goals: {sum(second_half_goals)/len(second_half_goals):.2f}")

# ============================================================
# 2. SCORE AT MINUTE 60 -> FINAL OUTCOME ANALYSIS
# ============================================================
print("\n" + "="*70)
print("2. SCORE AT MINUTE 60 -> WHAT HAPPENS NEXT")
print("="*70)

# For each score state at min 60, what's the probability of various outcomes?
min60_analysis = defaultdict(lambda: Counter())

for m in matches:
    row60 = None
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is not None and 58 <= mn <= 62:
            row60 = r
            break
    if row60 is None:
        continue
    gl60 = _i(row60.get("goles_local", ""))
    gv60 = _i(row60.get("goles_visitante", ""))
    if gl60 is None or gv60 is None:
        continue

    ft_gl, ft_gv = m["ft_local"], m["ft_visitante"]
    more_goals = (ft_gl + ft_gv) - (gl60 + gv60)

    score_key = f"{gl60}-{gv60}"
    min60_analysis[score_key]["total"] += 1
    min60_analysis[score_key][f"more_goals_{more_goals}"] += 1
    min60_analysis[score_key]["ft_same_score"] += (1 if ft_gl == gl60 and ft_gv == gv60 else 0)
    min60_analysis[score_key]["ft_total_goals"] += (ft_gl + ft_gv)

print("\nScore at min 60 -> goals in remaining 30 minutes:")
for score, data in sorted(min60_analysis.items(), key=lambda x: -x[1]["total"]):
    n = data["total"]
    if n < 15:
        continue
    same = data["ft_same_score"]
    avg_remaining = (data["ft_total_goals"] / n) - sum(int(x) for x in score.split("-"))
    print(f"  {score} (N={n}): Score holds {same/n*100:.1f}%, avg remaining goals: {avg_remaining:.2f}")

# ============================================================
# 3. FIRST-HALF GOAL PATTERNS -> SECOND HALF PREDICTION
# ============================================================
print("\n" + "="*70)
print("3. FIRST-HALF GOALS -> SECOND HALF GOALS")
print("="*70)

fh_to_sh = defaultdict(list)
for m in matches:
    ht_row = None
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is not None and 44 <= mn <= 48:
            ht_row = r
            break
    if ht_row is None:
        continue
    ht_gl = _i(ht_row.get("goles_local", ""))
    ht_gv = _i(ht_row.get("goles_visitante", ""))
    if ht_gl is None or ht_gv is None:
        continue
    fh_goals = ht_gl + ht_gv
    sh_goals = (m["ft_local"] - ht_gl) + (m["ft_visitante"] - ht_gv)
    fh_to_sh[fh_goals].append(sh_goals)

print("\nFirst-half goals -> Second-half goals:")
for fh in sorted(fh_to_sh.keys()):
    vals = fh_to_sh[fh]
    n = len(vals)
    if n < 10:
        continue
    avg = sum(vals) / n
    zero_sh = sum(1 for v in vals if v == 0)
    three_plus = sum(1 for v in vals if v >= 3)
    print(f"  FH={fh} goals (N={n}): 2H avg={avg:.2f}, 0 goals 2H: {zero_sh/n*100:.1f}%, 3+ goals 2H: {three_plus/n*100:.1f}%")

# ============================================================
# 4. FAVOURITE PRE-MATCH ODDS AT KICKOFF -> PATTERNS
# ============================================================
print("\n" + "="*70)
print("4. PRE-MATCH FAVOURITE ANALYSIS (by min 1 odds)")
print("="*70)

fav_analysis = defaultdict(lambda: {"n": 0, "wins": 0, "draws": 0, "goals": [],
                                     "fav_scores_first": 0, "ud_scores_first": 0})
for m in matches:
    r0 = m["rows"][0]
    bh = _f(r0.get("back_home", ""))
    ba = _f(r0.get("back_away", ""))
    if bh is None or ba is None:
        continue

    fav_odds = min(bh, ba)
    fav_is_home = bh <= ba

    if fav_odds < 1.3:
        bucket = "<1.30"
    elif fav_odds < 1.6:
        bucket = "1.30-1.59"
    elif fav_odds < 2.0:
        bucket = "1.60-1.99"
    elif fav_odds < 2.5:
        bucket = "2.00-2.49"
    else:
        bucket = "2.50+"

    d = fav_analysis[bucket]
    d["n"] += 1
    ft_gl, ft_gv = m["ft_local"], m["ft_visitante"]
    d["goals"].append(ft_gl + ft_gv)

    fav_won = (fav_is_home and ft_gl > ft_gv) or (not fav_is_home and ft_gv > ft_gl)
    if fav_won:
        d["wins"] += 1
    if ft_gl == ft_gv:
        d["draws"] += 1

    # Who scores first?
    for r in m["rows"][1:]:
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        if gl + gv > 0:
            if (gl > 0 and fav_is_home) or (gv > 0 and not fav_is_home):
                d["fav_scores_first"] += 1
            else:
                d["ud_scores_first"] += 1
            break

print("\nFavourite (by pre-match odds) performance:")
for bucket in ["<1.30", "1.30-1.59", "1.60-1.99", "2.00-2.49", "2.50+"]:
    d = fav_analysis[bucket]
    if d["n"] < 10:
        continue
    avg_goals = sum(d["goals"]) / d["n"]
    wr = d["wins"] / d["n"] * 100
    dr = d["draws"] / d["n"] * 100
    fav_first = d["fav_scores_first"] / d["n"] * 100 if d["n"] > 0 else 0
    print(f"  {bucket} (N={d['n']}): WR={wr:.1f}%, Draw={dr:.1f}%, AvgGoals={avg_goals:.2f}, "
          f"FavScoresFirst={fav_first:.1f}%")

# ============================================================
# 5. UNDER 4.5 AT DIFFERENT TOTAL GOALS (min 65+)
# ============================================================
print("\n" + "="*70)
print("5. UNDER 4.5 MARKET: HOLD RATES BY TOTAL GOALS AT MIN 65")
print("="*70)

u45_data = defaultdict(lambda: {"holds": 0, "fails": 0, "odds_sum": 0, "odds_n": 0})
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (63 <= mn <= 67):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        total = gl + gv
        if total > 4:
            continue  # Already over 4.5

        u45_odds = _f(r.get("back_under45", ""))
        if u45_odds is not None and u45_odds > 1.0:
            d = u45_data[total]
            d["odds_sum"] += u45_odds
            d["odds_n"] += 1

        ft_total = m["ft_total"]
        if ft_total <= 4:
            u45_data[total]["holds"] += 1
        else:
            u45_data[total]["fails"] += 1
        break

print("\nTotal goals at min 65 -> Under 4.5 hold rate:")
for total in sorted(u45_data.keys()):
    d = u45_data[total]
    n = d["holds"] + d["fails"]
    if n < 10:
        continue
    hold_pct = d["holds"] / n * 100
    avg_odds = d["odds_sum"] / d["odds_n"] if d["odds_n"] > 0 else 0
    implied = 100 / avg_odds if avg_odds > 1 else 0
    edge = hold_pct - implied
    print(f"  {total} goals at 65' (N={n}): Holds={hold_pct:.1f}%, AvgOdds={avg_odds:.2f}, "
          f"Implied={implied:.1f}%, Edge={edge:+.1f}pp")

# ============================================================
# 6. BACK HOME WIN: HOME LEADING BY 1 AT 65-75', FAV AT KO
# ============================================================
print("\n" + "="*70)
print("6. BACK HOME WIN: Home leading by 1 at 65-75' (home was fav at KO)")
print("="*70)

home_lead1_data = {"n": 0, "holds": 0, "odds_sum": 0, "odds_n": 0}
for m in matches:
    # Check if home was favourite
    r0 = m["rows"][0]
    bh0 = _f(r0.get("back_home", ""))
    ba0 = _f(r0.get("back_away", ""))
    if bh0 is None or ba0 is None or bh0 >= ba0:
        continue  # Home not favourite

    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (65 <= mn <= 75):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        if gl - gv != 1:
            continue

        bh = _f(r.get("back_home", ""))
        if bh is not None and bh > 1.0:
            home_lead1_data["odds_sum"] += bh
            home_lead1_data["odds_n"] += 1

        home_lead1_data["n"] += 1
        if m["ft_local"] > m["ft_visitante"]:
            home_lead1_data["holds"] += 1
        break

d = home_lead1_data
if d["n"] > 0:
    hold_pct = d["holds"] / d["n"] * 100
    avg_odds = d["odds_sum"] / d["odds_n"] if d["odds_n"] > 0 else 0
    implied = 100 / avg_odds if avg_odds > 1 else 0
    print(f"  Home fav leading by 1 at 65-75' (N={d['n']}): "
          f"Holds={hold_pct:.1f}%, AvgOdds={avg_odds:.2f}, Implied={implied:.1f}%, Edge={hold_pct-implied:+.1f}pp")

# ============================================================
# 7. GOALS IN LAST 15 MINUTES (75-90) BY SCORE STATE
# ============================================================
print("\n" + "="*70)
print("7. GOALS IN LAST 15 MINUTES BY SCORE STATE AT 75'")
print("="*70)

late_goals = defaultdict(lambda: {"n": 0, "goals_0": 0, "goals_1": 0, "goals_2plus": 0})
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (73 <= mn <= 77):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue

        total75 = gl + gv
        ft_total = m["ft_total"]
        remaining = ft_total - total75

        if gl > gv:
            state = "home_leading"
        elif gl < gv:
            state = "away_leading"
        else:
            state = "tied"

        key = f"{state}_{total75}goals"
        d = late_goals[key]
        d["n"] += 1
        if remaining == 0:
            d["goals_0"] += 1
        elif remaining == 1:
            d["goals_1"] += 1
        else:
            d["goals_2plus"] += 1
        break

print("\nScore state at 75' -> Goals in last 15 minutes:")
for key in sorted(late_goals.keys(), key=lambda x: -late_goals[x]["n"]):
    d = late_goals[key]
    if d["n"] < 15:
        continue
    print(f"  {key} (N={d['n']}): 0 more={d['goals_0']/d['n']*100:.1f}%, "
          f"1 more={d['goals_1']/d['n']*100:.1f}%, 2+ more={d['goals_2plus']/d['n']*100:.1f}%")

# ============================================================
# 8. xG OVERPERFORMANCE ANALYSIS (goals > xG by team)
# ============================================================
print("\n" + "="*70)
print("8. xG OVERPERFORMANCE: Teams scoring MORE than xG suggests")
print("="*70)

overperf_data = defaultdict(lambda: {"n": 0, "more_goals": 0, "same_goals": 0, "fewer_goals": 0})
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (63 <= mn <= 67):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        xgl = _f(r.get("xg_local", ""))
        xgv = _f(r.get("xg_visitante", ""))
        if None in (gl, gv, xgl, xgv):
            continue

        total = gl + gv
        total_xg = xgl + xgv

        if total_xg < 0.1:
            continue

        overperf = total - total_xg
        if overperf >= 1.5:
            bucket = "overperf_1.5+"
        elif overperf >= 0.5:
            bucket = "overperf_0.5-1.5"
        elif overperf >= -0.5:
            bucket = "neutral"
        elif overperf >= -1.5:
            bucket = "underperf_0.5-1.5"
        else:
            bucket = "underperf_1.5+"

        ft_remaining = m["ft_total"] - total
        d = overperf_data[bucket]
        d["n"] += 1
        if ft_remaining > 0:
            d["more_goals"] += 1
        elif ft_remaining == 0:
            d["same_goals"] += 1
        else:
            d["fewer_goals"] += 1  # shouldn't happen
        break

print("\nxG overperf at min 65 -> more goals in remaining time:")
for bucket in ["overperf_1.5+", "overperf_0.5-1.5", "neutral", "underperf_0.5-1.5", "underperf_1.5+"]:
    d = overperf_data[bucket]
    if d["n"] < 10:
        continue
    more_pct = d["more_goals"] / d["n"] * 100
    print(f"  {bucket} (N={d['n']}): More goals after 65': {more_pct:.1f}%, "
          f"No more: {d['same_goals']/d['n']*100:.1f}%")

# ============================================================
# 9. BACK UNDER 1.5 at specific scores (min 70+)
# ============================================================
print("\n" + "="*70)
print("9. UNDER 1.5 HOLD RATES AT MIN 70 (0-0 and 1-0/0-1)")
print("="*70)

u15_data = defaultdict(lambda: {"holds": 0, "fails": 0, "odds_sum": 0, "odds_n": 0})
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (68 <= mn <= 72):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        total = gl + gv
        if total > 1:
            continue

        score = f"{gl}-{gv}"
        u15_odds = _f(r.get("back_under15", ""))
        if u15_odds is not None and u15_odds > 1.0:
            u15_data[score]["odds_sum"] += u15_odds
            u15_data[score]["odds_n"] += 1

        if m["ft_total"] <= 1:
            u15_data[score]["holds"] += 1
        else:
            u15_data[score]["fails"] += 1
        break

for score in sorted(u15_data.keys()):
    d = u15_data[score]
    n = d["holds"] + d["fails"]
    if n < 10:
        continue
    hold_pct = d["holds"] / n * 100
    avg_odds = d["odds_sum"] / d["odds_n"] if d["odds_n"] > 0 else 0
    implied = 100 / avg_odds if avg_odds > 1 else 0
    print(f"  {score} at 70' (N={n}): Holds={hold_pct:.1f}%, AvgOdds={avg_odds:.2f}, "
          f"Implied={implied:.1f}%, Edge={hold_pct-implied:+.1f}pp")

# ============================================================
# 10. OVER 0.5 SECOND HALF (at HT with 0-0)
# ============================================================
print("\n" + "="*70)
print("10. OVER 0.5 SECOND-HALF: Scoreless at HT -> do they score?")
print("="*70)

scoreless_ht = {"n": 0, "score_2h": 0, "odds_o05_sum": 0, "odds_o05_n": 0}
for m in matches:
    ht_row = None
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is not None and 44 <= mn <= 48:
            ht_row = r
            break
    if ht_row is None:
        continue
    ht_gl = _i(ht_row.get("goles_local", ""))
    ht_gv = _i(ht_row.get("goles_visitante", ""))
    if ht_gl is None or ht_gv is None:
        continue
    if ht_gl + ht_gv > 0:
        continue

    scoreless_ht["n"] += 1
    if m["ft_total"] > 0:
        scoreless_ht["score_2h"] += 1

    o05 = _f(ht_row.get("back_over05", ""))
    if o05 is not None and o05 > 1.0:
        scoreless_ht["odds_o05_sum"] += o05
        scoreless_ht["odds_o05_n"] += 1

d = scoreless_ht
if d["n"] > 0:
    score_pct = d["score_2h"] / d["n"] * 100
    avg_o05 = d["odds_o05_sum"] / d["odds_o05_n"] if d["odds_o05_n"] > 0 else 0
    implied = 100 / avg_o05 if avg_o05 > 1 else 0
    print(f"  0-0 at HT (N={d['n']}): Score in 2H: {score_pct:.1f}%, AvgOdds O0.5={avg_o05:.2f}, "
          f"Implied={implied:.1f}%, Edge={score_pct-implied:+.1f}pp")

# ============================================================
# 11. HOME WIN RATES BY xG DOMINANCE + SCORE
# ============================================================
print("\n" + "="*70)
print("11. EXPLORING: Dominant team at 0-0 late -> who wins?")
print("="*70)

dom_00 = defaultdict(lambda: {"n": 0, "home_win": 0, "away_win": 0, "draw": 0,
                                "home_odds_sum": 0, "home_odds_n": 0})
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (58 <= mn <= 65):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None or gl + gv != 0:
            continue

        xgl = _f(r.get("xg_local", ""))
        xgv = _f(r.get("xg_visitante", ""))
        sot_l = _f(r.get("tiros_puerta_local", ""))
        sot_v = _f(r.get("tiros_puerta_visitante", ""))

        if None in (xgl, xgv, sot_l, sot_v):
            continue

        total_xg = xgl + xgv
        if total_xg < 0.3:
            cat = "both_dormant"
        elif xgl > xgv * 2 and sot_l > sot_v:
            cat = "home_dominant"
        elif xgv > xgl * 2 and sot_v > sot_l:
            cat = "away_dominant"
        else:
            cat = "balanced"

        d = dom_00[cat]
        d["n"] += 1
        ft_gl, ft_gv = m["ft_local"], m["ft_visitante"]
        if ft_gl > ft_gv:
            d["home_win"] += 1
        elif ft_gv > ft_gl:
            d["away_win"] += 1
        else:
            d["draw"] += 1

        bh = _f(r.get("back_home", ""))
        if bh and bh > 1.0:
            d["home_odds_sum"] += bh
            d["home_odds_n"] += 1
        break

for cat in ["home_dominant", "away_dominant", "balanced", "both_dormant"]:
    d = dom_00[cat]
    if d["n"] < 5:
        continue
    hw = d["home_win"] / d["n"] * 100
    aw = d["away_win"] / d["n"] * 100
    dr = d["draw"] / d["n"] * 100
    avg_ho = d["home_odds_sum"] / d["home_odds_n"] if d["home_odds_n"] > 0 else 0
    print(f"  {cat} at 0-0 min60 (N={d['n']}): HomeWin={hw:.1f}%, AwayWin={aw:.1f}%, Draw={dr:.1f}%, AvgHomeOdds={avg_ho:.2f}")

# ============================================================
# 12. UNDER 2.5 AT 1-1: Already have H48 (LAY U2.5) - check BACK U2.5
# ============================================================
print("\n" + "="*70)
print("12. BACK UNDER 2.5 at 2-0/0-2 (60-75')")
print("="*70)

u25_twozero = {"n": 0, "holds": 0, "odds_sum": 0, "odds_n": 0}
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (60 <= mn <= 75):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        if not ((gl == 2 and gv == 0) or (gl == 0 and gv == 2)):
            continue

        u25 = _f(r.get("back_under25", ""))
        if u25 is not None and u25 > 1.0:
            u25_twozero["odds_sum"] += u25
            u25_twozero["odds_n"] += 1

        u25_twozero["n"] += 1
        if m["ft_total"] <= 2:
            u25_twozero["holds"] += 1
        break

d = u25_twozero
if d["n"] > 0:
    hold_pct = d["holds"] / d["n"] * 100
    avg_odds = d["odds_sum"] / d["odds_n"] if d["odds_n"] > 0 else 0
    implied = 100 / avg_odds if avg_odds > 1 else 0
    print(f"  2-0/0-2 at 60-75' (N={d['n']}): Holds={hold_pct:.1f}%, AvgOdds={avg_odds:.2f}, "
          f"Implied={implied:.1f}%, Edge={hold_pct-implied:+.1f}pp")

# ============================================================
# 13. BACK UNDER 4.5 at 3 goals (65-80')
# ============================================================
print("\n" + "="*70)
print("13. BACK UNDER 4.5 at 3 goals (65-80')")
print("="*70)

u45_3goals = defaultdict(lambda: {"n": 0, "holds": 0, "odds_sum": 0, "odds_n": 0})
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (63 <= mn <= 82):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        if gl + gv != 3:
            continue

        xgl = _f(r.get("xg_local", ""))
        xgv = _f(r.get("xg_visitante", ""))
        total_xg = (xgl or 0) + (xgv or 0) if xgl is not None and xgv is not None else None

        u45 = _f(r.get("back_under45", ""))

        if total_xg is not None:
            if total_xg < 2.0:
                xg_cat = "low_xg"
            elif total_xg < 3.0:
                xg_cat = "mid_xg"
            else:
                xg_cat = "high_xg"
        else:
            xg_cat = "no_xg"

        d = u45_3goals[xg_cat]
        d["n"] += 1
        if u45 is not None and u45 > 1.0:
            d["odds_sum"] += u45
            d["odds_n"] += 1
        if m["ft_total"] <= 4:
            d["holds"] += 1
        break

for cat in ["low_xg", "mid_xg", "high_xg", "no_xg"]:
    d = u45_3goals[cat]
    if d["n"] < 5:
        continue
    hold_pct = d["holds"] / d["n"] * 100
    avg_odds = d["odds_sum"] / d["odds_n"] if d["odds_n"] > 0 else 0
    implied = 100 / avg_odds if avg_odds > 1 else 0
    print(f"  3 goals, {cat} (N={d['n']}): Holds={hold_pct:.1f}%, AvgOdds={avg_odds:.2f}, "
          f"Implied={implied:.1f}%, Edge={hold_pct-implied:+.1f}pp")

# ============================================================
# 14. CORRECT SCORE MARKET: Any score at min 80+ hold rates
# ============================================================
print("\n" + "="*70)
print("14. CORRECT SCORE HOLD RATES AT MIN 80+ (all scores)")
print("="*70)

cs_hold = defaultdict(lambda: {"n": 0, "holds": 0, "odds_sum": 0, "odds_n": 0})
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (78 <= mn <= 82):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        score = f"{gl}-{gv}"

        cs_col = f"back_rc_{gl}_{gv}"
        cs_odds = _f(r.get(cs_col, ""))

        d = cs_hold[score]
        d["n"] += 1
        if cs_odds is not None and cs_odds > 1.0:
            d["odds_sum"] += cs_odds
            d["odds_n"] += 1
        if m["ft_local"] == gl and m["ft_visitante"] == gv:
            d["holds"] += 1
        break

print("\nCS hold rates at min 80:")
for score in sorted(cs_hold.keys(), key=lambda x: -cs_hold[x]["n"]):
    d = cs_hold[score]
    if d["n"] < 10:
        continue
    hold_pct = d["holds"] / d["n"] * 100
    avg_odds = d["odds_sum"] / d["odds_n"] if d["odds_n"] > 0 else 0
    implied = 100 / avg_odds if avg_odds > 1 else 0
    edge = hold_pct - implied
    print(f"  CS {score} at 80' (N={d['n']}): Holds={hold_pct:.1f}%, "
          f"AvgOdds={avg_odds:.2f}, Implied={implied:.1f}%, Edge={edge:+.1f}pp")

# ============================================================
# 15. DRAW MARKET AT NON-STANDARD SCORES (2-2, 3-3, 0-0 min 55-65)
# ============================================================
print("\n" + "="*70)
print("15. DRAW RATES AT MIN 55-65 BY TIED SCORE")
print("="*70)

draw_tied = defaultdict(lambda: {"n": 0, "stays_draw": 0, "draw_odds_sum": 0, "draw_odds_n": 0})
for m in matches:
    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (53 <= mn <= 67):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None or gl != gv:
            continue

        score = f"{gl}-{gv}"
        d = draw_tied[score]
        d["n"] += 1

        bd = _f(r.get("back_draw", ""))
        if bd is not None and bd > 1.0:
            d["draw_odds_sum"] += bd
            d["draw_odds_n"] += 1

        if m["ft_local"] == m["ft_visitante"]:
            d["stays_draw"] += 1
        break

for score in sorted(draw_tied.keys(), key=lambda x: -draw_tied[x]["n"]):
    d = draw_tied[score]
    if d["n"] < 10:
        continue
    draw_pct = d["stays_draw"] / d["n"] * 100
    avg_odds = d["draw_odds_sum"] / d["draw_odds_n"] if d["draw_odds_n"] > 0 else 0
    implied = 100 / avg_odds if avg_odds > 1 else 0
    print(f"  Tied {score} at 55-65' (N={d['n']}): EndsDraw={draw_pct:.1f}%, "
          f"AvgOdds={avg_odds:.2f}, Implied={implied:.1f}%, Edge={draw_pct-implied:+.1f}pp")

# ============================================================
# 16. BACK HOME FAV LEADING LATE (complement to H67 away fav)
# ============================================================
print("\n" + "="*70)
print("16. BACK HOME FAV LEADING LATE (65-80')")
print("="*70)

home_fav_lead = defaultdict(lambda: {"n": 0, "holds": 0, "odds_sum": 0, "odds_n": 0})
for m in matches:
    r0 = m["rows"][0]
    bh0 = _f(r0.get("back_home", ""))
    ba0 = _f(r0.get("back_away", ""))
    if bh0 is None or ba0 is None or bh0 >= ba0:
        continue

    for r in m["rows"]:
        mn = _f(r.get("minuto", ""))
        if mn is None or not (65 <= mn <= 80):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        if gl <= gv:
            continue

        lead = gl - gv
        bh = _f(r.get("back_home", ""))

        d = home_fav_lead[lead]
        d["n"] += 1
        if bh is not None and bh > 1.0:
            d["odds_sum"] += bh
            d["odds_n"] += 1
        if m["ft_local"] > m["ft_visitante"]:
            d["holds"] += 1
        break

for lead in sorted(home_fav_lead.keys()):
    d = home_fav_lead[lead]
    if d["n"] < 10:
        continue
    hold_pct = d["holds"] / d["n"] * 100
    avg_odds = d["odds_sum"] / d["odds_n"] if d["odds_n"] > 0 else 0
    implied = 100 / avg_odds if avg_odds > 1 else 0
    print(f"  Home fav leading by {lead} at 65-80' (N={d['n']}): "
          f"Holds={hold_pct:.1f}%, AvgOdds={avg_odds:.2f}, Implied={implied:.1f}%, Edge={hold_pct-implied:+.1f}pp")

print("\n\nDone.")
