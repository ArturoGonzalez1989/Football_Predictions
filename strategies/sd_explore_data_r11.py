"""
PASO 1 - Data Exploration for Round 11 (H66+)
Focus: Finding NEW angles not covered by 65 previous hypotheses.
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
print(f"Total CSVs: {len(files)}")

# ---- 1. Dataset overview ----
countries = Counter()
leagues = Counter()
dates = []
total_rows = 0
finished = 0

# ---- 2. Score distribution ----
final_scores = Counter()

# ---- 3. Goal timing (by 5-min buckets) ----
goal_timing = Counter()  # bucket -> count

# ---- 4. First half vs second half patterns ----
ht_scores = Counter()  # score at HT (min 45)
ft_scores_given_ht = defaultdict(Counter)  # ht_score -> ft_score -> count

# ---- 5. NEW: Comeback frequency analysis ----
comeback_stats = {
    "trailing_at_60": 0,
    "comeback_draw_60": 0,
    "comeback_win_60": 0,
    "trailing_at_70": 0,
    "comeback_draw_70": 0,
    "comeback_win_70": 0,
    "leading_at_60": 0,
    "holds_60": 0,
    "leading_at_70": 0,
    "holds_70": 0,
}

# ---- 6. NEW: Score change patterns ----
# How often does score change in last 20 min?
late_goal_stats = {
    "total_matches": 0,
    "goal_70_90": 0,
    "goal_75_90": 0,
    "goal_80_90": 0,
    "no_goal_60_90": 0,
}

# ---- 7. NEW: Odds movement patterns ----
odds_at_start = []  # (back_home, back_draw, back_away) at min 1-5
odds_movements = []  # how much odds change between min 30 and min 60

# ---- 8. NEW: Under/Over market analysis at different minutes ----
ou_market_data = defaultdict(list)  # (line, minute_bucket) -> [odds]

# ---- 9. NEW: Pre-match favourite analysis ----
fav_analysis = {
    "strong_fav_wins": 0,  # pre odds < 1.5
    "strong_fav_total": 0,
    "mild_fav_wins": 0,    # pre odds 1.5-2.0
    "mild_fav_total": 0,
    "even_match_total": 0, # both odds 2.0-3.5
    "even_home_wins": 0,
    "even_draws": 0,
    "even_away_wins": 0,
}

# ---- 10. NEW: Score volatility (total goals at different minutes) ----
goals_by_minute = defaultdict(list)  # minute -> list of total_goals at that minute

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

    finished += 1
    total_rows += len(rows)

    country = last.get("Pa\u00eds", last.get("Pais", "?"))
    league = last.get("Liga", "?")
    countries[country] += 1
    leagues[league] += 1

    ts = rows[0].get("timestamp_utc", "")
    if ts and len(ts) >= 10:
        dates.append(ts[:10])

    # Final score
    score_key = f"{gl}-{gv}"
    final_scores[score_key] += 1

    # Goal timing - detect when goals happen
    prev_gl, prev_gv = 0, 0
    ht_gl, ht_gv = None, None

    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue

        # Record goals at each minute for volatility
        total_now = cur_gl + cur_gv
        goals_by_minute[int(m)].append(total_now)

        # Detect goal scored
        if cur_gl > prev_gl:
            for _ in range(cur_gl - prev_gl):
                bucket = int(m // 5) * 5
                goal_timing[bucket] += 1
        if cur_gv > prev_gv:
            for _ in range(cur_gv - prev_gv):
                bucket = int(m // 5) * 5
                goal_timing[bucket] += 1

        # HT score (around min 45)
        if m >= 42 and m <= 48 and ht_gl is None:
            ht_gl, ht_gv = cur_gl, cur_gv

        # Comeback analysis
        if 59 <= m <= 61:
            if cur_gl != cur_gv:
                comeback_stats["trailing_at_60"] += 1
                leader = "home" if cur_gl > cur_gv else "away"
                comeback_stats["leading_at_60"] += 1
                if (leader == "home" and gl > gv) or (leader == "away" and gv > gl):
                    comeback_stats["holds_60"] += 1
                if gl == gv:
                    comeback_stats["comeback_draw_60"] += 1
                elif (leader == "home" and gv > gl) or (leader == "away" and gl > gv):
                    comeback_stats["comeback_win_60"] += 1

        if 69 <= m <= 71:
            if cur_gl != cur_gv:
                comeback_stats["trailing_at_70"] += 1
                leader = "home" if cur_gl > cur_gv else "away"
                comeback_stats["leading_at_70"] += 1
                if (leader == "home" and gl > gv) or (leader == "away" and gv > gl):
                    comeback_stats["holds_70"] += 1
                if gl == gv:
                    comeback_stats["comeback_draw_70"] += 1
                elif (leader == "home" and gv > gl) or (leader == "away" and gl > gv):
                    comeback_stats["comeback_win_70"] += 1

        # Under/Over odds at different minutes
        for line in ["15", "25", "35", "45"]:
            back_over = _f(row.get(f"back_over{line}", ""))
            back_under = _f(row.get(f"back_under{line}", ""))
            if back_over and 1.0 < back_over < 100 and 25 <= m <= 85:
                bucket = int(m // 10) * 10
                ou_market_data[(f"over{line}", bucket)].append(back_over)
            if back_under and 1.0 < back_under < 100 and 25 <= m <= 85:
                bucket = int(m // 10) * 10
                ou_market_data[(f"under{line}", bucket)].append(back_under)

        prev_gl, prev_gv = cur_gl, cur_gv

    # HT analysis
    if ht_gl is not None:
        ht_key = f"{ht_gl}-{ht_gv}"
        ht_scores[ht_key] += 1
        ft_scores_given_ht[ht_key][score_key] += 1

    # Late goals
    late_goal_stats["total_matches"] += 1
    if gl + gv > (prev_gl + prev_gv if prev_gl is not None else 0):
        pass  # handled above

    # Count matches with goals in late periods
    found_70 = found_75 = found_80 = False
    found_no_goal_60 = True
    prev_tot = 0
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl2 = _i(row.get("goles_local", ""))
        cur_gv2 = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl2 is None or cur_gv2 is None:
            continue
        cur_tot = cur_gl2 + cur_gv2
        if m >= 60 and cur_tot > prev_tot:
            found_no_goal_60 = False
        if m >= 70 and cur_tot > prev_tot and not found_70:
            found_70 = True
        if m >= 75 and cur_tot > prev_tot and not found_75:
            found_75 = True
        if m >= 80 and cur_tot > prev_tot and not found_80:
            found_80 = True
        prev_tot = cur_tot

    if found_70: late_goal_stats["goal_70_90"] += 1
    if found_75: late_goal_stats["goal_75_90"] += 1
    if found_80: late_goal_stats["goal_80_90"] += 1
    if found_no_goal_60: late_goal_stats["no_goal_60_90"] += 1

    # Pre-match favourite (use first few rows)
    early_home = None
    early_away = None
    for row in rows[:5]:
        bh = _f(row.get("back_home", ""))
        ba = _f(row.get("back_away", ""))
        if bh and ba and bh > 1 and ba > 1:
            early_home = bh
            early_away = ba
            break

    if early_home and early_away:
        home_won = gl > gv
        away_won = gv > gl
        draw = gl == gv

        if early_home < 1.5:
            fav_analysis["strong_fav_total"] += 1
            if home_won: fav_analysis["strong_fav_wins"] += 1
        elif early_home < 2.0:
            fav_analysis["mild_fav_total"] += 1
            if home_won: fav_analysis["mild_fav_wins"] += 1
        elif early_away < 1.5:
            fav_analysis["strong_fav_total"] += 1
            if away_won: fav_analysis["strong_fav_wins"] += 1
        elif early_away < 2.0:
            fav_analysis["mild_fav_total"] += 1
            if away_won: fav_analysis["mild_fav_wins"] += 1
        elif 2.0 <= early_home <= 3.5 and 2.0 <= early_away <= 3.5:
            fav_analysis["even_match_total"] += 1
            if home_won: fav_analysis["even_home_wins"] += 1
            if draw: fav_analysis["even_draws"] += 1
            if away_won: fav_analysis["even_away_wins"] += 1


# ============ PRINT RESULTS ============

print(f"\n{'='*60}")
print(f"DATASET OVERVIEW")
print(f"{'='*60}")
print(f"Finished matches: {finished}")
print(f"Total rows: {total_rows}")
print(f"Avg rows/match: {total_rows/finished:.1f}")
if dates:
    print(f"Date range: {min(dates)} to {max(dates)}")
print(f"Countries: {len(countries)}")
print(f"Leagues: {len(leagues)}")
print(f"\nTop 10 leagues:")
for lg, cnt in leagues.most_common(10):
    print(f"  {lg}: {cnt}")

print(f"\n{'='*60}")
print(f"FINAL SCORE DISTRIBUTION (top 15)")
print(f"{'='*60}")
for score, cnt in final_scores.most_common(15):
    print(f"  {score}: {cnt} ({cnt/finished*100:.1f}%)")

total_goals = sum(int(s.split('-')[0]) + int(s.split('-')[1]) for s in final_scores for _ in range(final_scores[s]))
avg_goals = total_goals / finished
print(f"\nAvg total goals: {avg_goals:.2f}")

# Goal count distribution
goal_counts = Counter()
for score, cnt in final_scores.items():
    g = int(score.split('-')[0]) + int(score.split('-')[1])
    goal_counts[g] += cnt
print(f"\nGoal count distribution:")
for g in sorted(goal_counts):
    print(f"  {g} goals: {goal_counts[g]} ({goal_counts[g]/finished*100:.1f}%)")

print(f"\n{'='*60}")
print(f"GOAL TIMING (5-min buckets)")
print(f"{'='*60}")
for bucket in sorted(goal_timing):
    bar = '#' * int(goal_timing[bucket] / 3)
    print(f"  {bucket:2d}-{bucket+5:2d}: {goal_timing[bucket]:4d} {bar}")

print(f"\n{'='*60}")
print(f"HALF-TIME ANALYSIS")
print(f"{'='*60}")
print(f"HT score distribution (top 10):")
for ht, cnt in ht_scores.most_common(10):
    print(f"  HT {ht}: {cnt} ({cnt/finished*100:.1f}%)")

# What happens after specific HT scores
print(f"\nFT outcomes given HT score (top 5 HT scores):")
for ht, _ in ht_scores.most_common(5):
    total = sum(ft_scores_given_ht[ht].values())
    print(f"\n  HT {ht} (N={total}):")
    for ft, cnt in ft_scores_given_ht[ht].most_common(5):
        print(f"    -> FT {ft}: {cnt} ({cnt/total*100:.1f}%)")

print(f"\n{'='*60}")
print(f"COMEBACK & HOLD ANALYSIS")
print(f"{'='*60}")
for key, val in comeback_stats.items():
    print(f"  {key}: {val}")

if comeback_stats["leading_at_60"] > 0:
    hold_60 = comeback_stats["holds_60"] / comeback_stats["leading_at_60"] * 100
    print(f"\n  Leader at 60' holds to win: {hold_60:.1f}%")
if comeback_stats["leading_at_70"] > 0:
    hold_70 = comeback_stats["holds_70"] / comeback_stats["leading_at_70"] * 100
    print(f"  Leader at 70' holds to win: {hold_70:.1f}%")
if comeback_stats["trailing_at_60"] > 0:
    draw_60 = comeback_stats["comeback_draw_60"] / comeback_stats["trailing_at_60"] * 100
    win_60 = comeback_stats["comeback_win_60"] / comeback_stats["trailing_at_60"] * 100
    print(f"  Trailing at 60' -> draws: {draw_60:.1f}%, wins: {win_60:.1f}%")
if comeback_stats["trailing_at_70"] > 0:
    draw_70 = comeback_stats["comeback_draw_70"] / comeback_stats["trailing_at_70"] * 100
    win_70 = comeback_stats["comeback_win_70"] / comeback_stats["trailing_at_70"] * 100
    print(f"  Trailing at 70' -> draws: {draw_70:.1f}%, wins: {win_70:.1f}%")

print(f"\n{'='*60}")
print(f"LATE GOALS")
print(f"{'='*60}")
for key, val in late_goal_stats.items():
    pct = val / late_goal_stats["total_matches"] * 100 if late_goal_stats["total_matches"] > 0 else 0
    print(f"  {key}: {val} ({pct:.1f}%)")

print(f"\n{'='*60}")
print(f"PRE-MATCH FAVOURITE ANALYSIS")
print(f"{'='*60}")
for key, val in fav_analysis.items():
    print(f"  {key}: {val}")

if fav_analysis["strong_fav_total"] > 0:
    print(f"\n  Strong fav win rate: {fav_analysis['strong_fav_wins']/fav_analysis['strong_fav_total']*100:.1f}%")
if fav_analysis["mild_fav_total"] > 0:
    print(f"  Mild fav win rate: {fav_analysis['mild_fav_wins']/fav_analysis['mild_fav_total']*100:.1f}%")
if fav_analysis["even_match_total"] > 0:
    e = fav_analysis
    print(f"  Even match: H={e['even_home_wins']/e['even_match_total']*100:.1f}%, "
          f"D={e['even_draws']/e['even_match_total']*100:.1f}%, "
          f"A={e['even_away_wins']/e['even_match_total']*100:.1f}%")

# ---- 11. NEW EXPLORATION: Second-half-only patterns ----
print(f"\n{'='*60}")
print(f"SECOND HALF GOALS DISTRIBUTION")
print(f"{'='*60}")
sh_goals = Counter()
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

    ht_gl, ht_gv = None, None
    for row in rows:
        m = _f(row.get("minuto", ""))
        if m and 42 <= m <= 48:
            ht_gl = _i(row.get("goles_local", ""))
            ht_gv = _i(row.get("goles_visitante", ""))
            break

    if ht_gl is not None and ht_gv is not None:
        sh = (gl - ht_gl) + (gv - ht_gv)
        sh_goals[sh] += 1

print(f"2H goals distribution:")
for g in sorted(sh_goals):
    print(f"  {g} goals in 2H: {sh_goals[g]} ({sh_goals[g]/sum(sh_goals.values())*100:.1f}%)")

# ---- 12. NEW: Match Winner market -- implied vs actual at different minutes ----
print(f"\n{'='*60}")
print(f"MATCH WINNER: IMPLIED vs ACTUAL PROBABILITIES")
print(f"{'='*60}")
# For tied games at different minutes, what % does home/draw/away win?
tied_outcomes = defaultdict(lambda: {"home": 0, "draw": 0, "away": 0, "total": 0})

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

    seen_minutes = set()
    for row in rows:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue

        bucket = int(m // 10) * 10
        if bucket in seen_minutes:
            continue
        seen_minutes.add(bucket)

        if cur_gl == cur_gv and bucket in [30, 40, 50, 60, 70, 80]:
            tied_outcomes[bucket]["total"] += 1
            if gl > gv:
                tied_outcomes[bucket]["home"] += 1
            elif gl == gv:
                tied_outcomes[bucket]["draw"] += 1
            else:
                tied_outcomes[bucket]["away"] += 1

print(f"When tied at minute X, final outcome:")
for bucket in [30, 40, 50, 60, 70, 80]:
    d = tied_outcomes[bucket]
    if d["total"] > 0:
        n = d["total"]
        print(f"  Min {bucket}: H={d['home']/n*100:.1f}%, D={d['draw']/n*100:.1f}%, A={d['away']/n*100:.1f}% (N={n})")

# ---- 13. Under market inefficiency scan ----
print(f"\n{'='*60}")
print(f"UNDER MARKET ANALYSIS: How often does total stay under X?")
print(f"{'='*60}")
# At each score state at different minutes, how often does total stay under various lines?
under_analysis = defaultdict(lambda: {"holds": 0, "total": 0, "odds_sum": 0, "odds_count": 0})

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

        cur_total = cur_gl + cur_gv
        bucket = int(m // 10) * 10

        # Under 0.5 (0-0 at min X -> stays 0-0?)
        key05 = (f"U0.5_at_{bucket}", cur_total)
        if key05 not in seen and bucket in [50, 60, 70, 80] and cur_total == 0:
            seen.add(key05)
            under_analysis[f"U0.5_min{bucket}"]["total"] += 1
            if ft_total == 0:
                under_analysis[f"U0.5_min{bucket}"]["holds"] += 1
            bo05 = _f(row.get("back_under05", ""))
            if bo05 and 1.0 < bo05 < 50:
                under_analysis[f"U0.5_min{bucket}"]["odds_sum"] += bo05
                under_analysis[f"U0.5_min{bucket}"]["odds_count"] += 1

        # Under 1.5 at various states
        key15 = (f"U1.5_at_{bucket}", cur_total)
        if key15 not in seen and bucket in [50, 60, 70, 80] and cur_total <= 1:
            seen.add(key15)
            k = f"U1.5_min{bucket}_goals{cur_total}"
            under_analysis[k]["total"] += 1
            if ft_total <= 1:
                under_analysis[k]["holds"] += 1
            bo15 = _f(row.get("back_under15", ""))
            if bo15 and 1.0 < bo15 < 50:
                under_analysis[k]["odds_sum"] += bo15
                under_analysis[k]["odds_count"] += 1

        # Under 3.5 at various states
        key35 = (f"U3.5_at_{bucket}", cur_total)
        if key35 not in seen and bucket in [60, 70, 80] and cur_total <= 3:
            seen.add(key35)
            k = f"U3.5_min{bucket}_goals{cur_total}"
            under_analysis[k]["total"] += 1
            if ft_total <= 3:
                under_analysis[k]["holds"] += 1
            bo35 = _f(row.get("back_under35", ""))
            if bo35 and 1.0 < bo35 < 50:
                under_analysis[k]["odds_sum"] += bo35
                under_analysis[k]["odds_count"] += 1

for k in sorted(under_analysis):
    d = under_analysis[k]
    if d["total"] >= 20:
        hold_pct = d["holds"] / d["total"] * 100
        avg_odds = d["odds_sum"] / d["odds_count"] if d["odds_count"] > 0 else 0
        implied = 100 / avg_odds if avg_odds > 1 else 0
        edge = hold_pct - implied
        print(f"  {k}: holds={hold_pct:.1f}%, N={d['total']}, "
              f"avg_odds={avg_odds:.2f}, implied={implied:.1f}%, "
              f"edge={edge:+.1f}pp")

# ---- 14. NEW: Correct Score market at 2-0, 0-2, 3-1, 1-3 at late minutes ----
print(f"\n{'='*60}")
print(f"CORRECT SCORE HOLD RATES (less common scorelines)")
print(f"{'='*60}")
cs_analysis = defaultdict(lambda: {"holds": 0, "total": 0})

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

        for target_min in [65, 70, 75, 80]:
            if abs(m - target_min) <= 2:
                score_now = f"{cur_gl}-{cur_gv}"
                key = (score_now, target_min)
                if key not in seen:
                    seen.add(key)
                    cs_analysis[key]["total"] += 1
                    if gl == cur_gl and gv == cur_gv:
                        cs_analysis[key]["holds"] += 1

print(f"Score at min X -> holds to FT:")
for (score, minute), d in sorted(cs_analysis.items(), key=lambda x: (-x[1]["total"],)):
    if d["total"] >= 15:
        hold = d["holds"] / d["total"] * 100
        print(f"  {score} at min {minute}: holds={hold:.1f}%, N={d['total']}")

# ---- 15. NEW: Draw-specific deep dive for non-zero draws ----
print(f"\n{'='*60}")
print(f"DRAW ANALYSIS BY SCORE")
print(f"{'='*60}")
draw_scores = {s: c for s, c in final_scores.items() if s.split('-')[0] == s.split('-')[1]}
total_draws = sum(draw_scores.values())
print(f"Total draws: {total_draws} ({total_draws/finished*100:.1f}%)")
for s, c in sorted(draw_scores.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c} ({c/total_draws*100:.1f}% of draws)")

# When does 2-2 happen? How does it differ from 1-1?
print(f"\n  2-2 draws: {final_scores.get('2-2', 0)}")
print(f"  3-3 draws: {final_scores.get('3-3', 0)}")

print(f"\n{'='*60}")
print(f"DONE")
print(f"{'='*60}")
