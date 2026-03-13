"""
R18 Feasibility Exploration — Gemini Hypotheses H96-H101
Checks scenario frequencies and column availability before running backtests.
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

# Track finished matches
finished = 0
score_at_min = defaultdict(lambda: defaultdict(int))  # {min_bucket: {score: count}}

# Scenario counters
h96_score32 = 0  # Matches reaching 3-2/2-3 at min 65-80
h97_local_leading_away_dom = 0  # Home leading but away dominates
h98_5plus_goals = 0  # 5+ total goals at min 60-72
h99_score30_or_31 = 0  # 3-0/3-1 (or symmetric) at min 55-70
h100_2goal_deficit = 0  # 2-goal deficit at min 65-78
h101_score02_or_20 = 0  # 0-2/2-0 at min 55-75

# Column availability for key CS columns
col_avail = Counter()
col_checks = [
    'back_rc_3_2', 'back_rc_2_3', 'back_over55',
    'back_rc_4_1', 'back_rc_1_4', 'back_rc_0_2', 'back_rc_2_0',
    'lay_rc_3_2', 'lay_rc_2_3', 'lay_rc_0_2', 'lay_rc_2_0',
    'xg_local', 'xg_visitante',
    'tiros_puerta_local', 'tiros_puerta_visitante',
]
col_nonnull = Counter()
matches_with_cols = 0

# FT score distribution for rare outcomes
ft_scores = Counter()

# Detailed tracking for each hypothesis
h96_details = []
h97_details = []
h98_details = []
h99_details = []
h100_details = []
h101_details = []

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
    finished += 1

    match_id = os.path.basename(fpath).replace("partido_", "").replace(".csv", "")
    ft_scores[f"{gl_ft}-{gv_ft}"] += 1

    # Check column availability in first non-empty row
    for row in rows:
        for col in col_checks:
            if col in row:
                col_avail[col] += 1
                if _f(row.get(col, "")) is not None:
                    col_nonnull[col] += 1
        matches_with_cols += 1
        break

    # Scan rows for scenarios
    found_h96 = found_h97 = found_h98 = found_h99 = found_h100 = found_h101 = False

    for idx, row in enumerate(rows):
        m = _f(row.get("minuto", ""))
        if m is None:
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue

        total = gl + gv
        xg_l = _f(row.get("xg_local", ""))
        xg_v = _f(row.get("xg_visitante", ""))
        sot_l = _f(row.get("tiros_puerta_local", ""))
        sot_v = _f(row.get("tiros_puerta_visitante", ""))

        # H96: Score 3-2 or 2-3 at min 65-80
        if not found_h96 and 65 <= m <= 80:
            if (gl == 3 and gv == 2) or (gl == 2 and gv == 3):
                h96_score32 += 1
                found_h96 = True
                odds_32 = _f(row.get("back_rc_3_2", ""))
                odds_23 = _f(row.get("back_rc_2_3", ""))
                xg_t = (xg_l or 0) + (xg_v or 0) if xg_l is not None and xg_v is not None else None
                sot_t = (sot_l or 0) + (sot_v or 0) if sot_l is not None and sot_v is not None else None
                h96_details.append({
                    'match': match_id, 'min': m, 'score': f"{gl}-{gv}",
                    'xg_total': xg_t, 'sot_total': sot_t,
                    'odds_32': odds_32, 'odds_23': odds_23,
                    'ft': f"{gl_ft}-{gv_ft}"
                })

        # H97: Home leading 1-0 or 2-1 but away dominates stats, min 65-80
        if not found_h97 and 65 <= m <= 80:
            if (gl == 1 and gv == 0) or (gl == 2 and gv == 1):
                if xg_v is not None and xg_l is not None and sot_v is not None and sot_l is not None:
                    if xg_v - xg_l >= 0.7 and sot_v >= sot_l + 2:
                        back_away = _f(row.get("back_away", ""))
                        h97_local_leading_away_dom += 1
                        found_h97 = True
                        h97_details.append({
                            'match': match_id, 'min': m, 'score': f"{gl}-{gv}",
                            'xg_diff': round(xg_v - xg_l, 2),
                            'sot_diff': int(sot_v - sot_l),
                            'back_away': back_away,
                            'ft': f"{gl_ft}-{gv_ft}"
                        })

        # H98: 5+ goals at min 60-72
        if not found_h98 and 60 <= m <= 72:
            if total >= 5:
                h98_5plus_goals += 1
                found_h98 = True
                odds_o55 = _f(row.get("back_over55", ""))
                h98_details.append({
                    'match': match_id, 'min': m, 'score': f"{gl}-{gv}",
                    'back_over55': odds_o55,
                    'ft': f"{gl_ft}-{gv_ft}", 'ft_total': gl_ft + gv_ft
                })

        # H99: Score 3-0/0-3/3-1/1-3 at min 55-70
        if not found_h99 and 55 <= m <= 70:
            big_lead = ((gl == 3 and gv == 0) or (gl == 0 and gv == 3) or
                        (gl == 3 and gv == 1) or (gl == 1 and gv == 3))
            if big_lead:
                h99_score30_or_31 += 1
                found_h99 = True
                # Check 4-1/1-4 CS odds
                odds_41 = _f(row.get("back_rc_4_1", ""))
                odds_14 = _f(row.get("back_rc_1_4", ""))
                h99_details.append({
                    'match': match_id, 'min': m, 'score': f"{gl}-{gv}",
                    'odds_41': odds_41, 'odds_14': odds_14,
                    'ft': f"{gl_ft}-{gv_ft}"
                })

        # H100: 2-goal deficit at min 65-78
        if not found_h100 and 65 <= m <= 78:
            diff = abs(gl - gv)
            if diff == 2:
                if xg_l is not None and xg_v is not None and sot_l is not None and sot_v is not None:
                    # trailing team dominates
                    if gl > gv:  # home leads, away trails
                        trail_xg = xg_v
                        lead_xg = xg_l
                        trail_sot = sot_v
                        lead_sot = sot_l
                    else:  # away leads, home trails
                        trail_xg = xg_l
                        lead_xg = xg_v
                        trail_sot = sot_l
                        lead_sot = sot_v
                    # For now just count the scenario (relaxed -- no xG window filter)
                    h100_2goal_deficit += 1
                    found_h100 = True
                    back_draw = _f(row.get("back_draw", ""))
                    h100_details.append({
                        'match': match_id, 'min': m, 'score': f"{gl}-{gv}",
                        'trail_xg': round(trail_xg, 2), 'lead_xg': round(lead_xg, 2),
                        'trail_sot': trail_sot, 'lead_sot': lead_sot,
                        'back_draw': back_draw,
                        'ft': f"{gl_ft}-{gv_ft}",
                        'ft_draw': 1 if gl_ft == gv_ft else 0
                    })

        # H101: Score 0-2/2-0 at min 55-75
        if not found_h101 and 55 <= m <= 75:
            if (gl == 0 and gv == 2) or (gl == 2 and gv == 0):
                h101_score02_or_20 += 1
                found_h101 = True
                back_home = _f(row.get("back_home", ""))
                back_away = _f(row.get("back_away", ""))
                odds_02 = _f(row.get("back_rc_0_2", ""))
                odds_20 = _f(row.get("back_rc_2_0", ""))
                h101_details.append({
                    'match': match_id, 'min': m, 'score': f"{gl}-{gv}",
                    'back_home': back_home, 'back_away': back_away,
                    'odds_02': odds_02, 'odds_20': odds_20,
                    'ft': f"{gl_ft}-{gv_ft}",
                    'ft_changed': 1 if f"{gl_ft}-{gv_ft}" != f"{gl}-{gv}" else 0
                })

print(f"\nFinished matches: {finished}")
print(f"Quality gate N >= {max(15, finished // 25)}")

print(f"\n{'='*60}")
print("SCENARIO FREQUENCIES (matches where scenario occurs at least once)")
print(f"{'='*60}")
print(f"H96 - Score 3-2/2-3 at min 65-80:     {h96_score32}")
print(f"H97 - Home leading, away dominates:     {h97_local_leading_away_dom}")
print(f"H98 - 5+ goals at min 60-72:            {h98_5plus_goals}")
print(f"H99 - Score 3-0/0-3/3-1/1-3 at 55-70:  {h99_score30_or_31}")
print(f"H100 - 2-goal deficit at min 65-78:      {h100_2goal_deficit}")
print(f"H101 - Score 0-2/2-0 at min 55-75:      {h101_score02_or_20}")

print(f"\n{'='*60}")
print("COLUMN AVAILABILITY (presence in headers / non-null values)")
print(f"{'='*60}")
for col in col_checks:
    present = col_avail.get(col, 0)
    nonnull = col_nonnull.get(col, 0)
    pct_present = present / matches_with_cols * 100 if matches_with_cols > 0 else 0
    pct_nonnull = nonnull / matches_with_cols * 100 if matches_with_cols > 0 else 0
    print(f"  {col:30s} present={pct_present:5.1f}%  nonnull={pct_nonnull:5.1f}%")

print(f"\n{'='*60}")
print("FT SCORE DISTRIBUTION (top 20)")
print(f"{'='*60}")
for score, count in ft_scores.most_common(20):
    pct = count / finished * 100
    print(f"  {score:6s}  {count:4d}  ({pct:.1f}%)")

# H96 analysis: What happens after 3-2/2-3?
print(f"\n{'='*60}")
print(f"H96 DETAILS: Score 3-2/2-3 at min 65-80 ({len(h96_details)} matches)")
print(f"{'='*60}")
if h96_details:
    stays = sum(1 for d in h96_details if d['ft'] == d['score'])
    changes = len(h96_details) - stays
    print(f"  Score stays (3-2 or 2-3 final): {stays} ({stays/len(h96_details)*100:.1f}%)")
    print(f"  Score changes (more goals):      {changes} ({changes/len(h96_details)*100:.1f}%)")
    with_xg = [d for d in h96_details if d['xg_total'] is not None]
    print(f"  With xG data: {len(with_xg)}")
    if with_xg:
        high_xg = [d for d in with_xg if d['xg_total'] >= 4.0]
        print(f"  xG_total >= 4.0: {len(high_xg)}")
    with_sot = [d for d in h96_details if d['sot_total'] is not None]
    if with_sot:
        high_sot = [d for d in with_sot if d['sot_total'] >= 12]
        print(f"  SoT_total >= 12: {len(high_sot)}")
    with_odds = [d for d in h96_details if d['odds_32'] is not None or d['odds_23'] is not None]
    print(f"  With CS odds: {len(with_odds)}")

# H97 analysis
print(f"\n{'='*60}")
print(f"H97 DETAILS: Home leading, away dominates ({len(h97_details)} matches)")
print(f"{'='*60}")
if h97_details:
    away_wins = sum(1 for d in h97_details if int(d['ft'].split('-')[1]) > int(d['ft'].split('-')[0]))
    draws = sum(1 for d in h97_details if int(d['ft'].split('-')[0]) == int(d['ft'].split('-')[1]))
    home_wins = len(h97_details) - away_wins - draws
    print(f"  Away wins: {away_wins} ({away_wins/len(h97_details)*100:.1f}%)")
    print(f"  Draws:     {draws} ({draws/len(h97_details)*100:.1f}%)")
    print(f"  Home wins: {home_wins} ({home_wins/len(h97_details)*100:.1f}%)")
    with_odds = [d for d in h97_details if d['back_away'] is not None]
    if with_odds:
        avg_odds = sum(d['back_away'] for d in with_odds) / len(with_odds)
        in_range = [d for d in with_odds if 4 <= d['back_away'] <= 10]
        print(f"  Avg back_away odds: {avg_odds:.2f}")
        print(f"  Odds in [4, 10]: {len(in_range)}")

# H98 analysis
print(f"\n{'='*60}")
print(f"H98 DETAILS: 5+ goals at min 60-72 ({len(h98_details)} matches)")
print(f"{'='*60}")
if h98_details:
    stays_5 = sum(1 for d in h98_details if d['ft_total'] <= 5)
    more = sum(1 for d in h98_details if d['ft_total'] > 5)
    print(f"  FT total <= 5 (LAY O5.5 wins): {stays_5} ({stays_5/len(h98_details)*100:.1f}%)")
    print(f"  FT total > 5  (LAY O5.5 loses): {more} ({more/len(h98_details)*100:.1f}%)")
    with_odds = [d for d in h98_details if d['back_over55'] is not None]
    print(f"  With back_over55 odds: {len(with_odds)}")
    if with_odds:
        avg_o55 = sum(d['back_over55'] for d in with_odds) / len(with_odds)
        in_range = [d for d in with_odds if 1.8 <= d['back_over55'] <= 3.0]
        print(f"  Avg back_over55: {avg_o55:.2f}")
        print(f"  Odds in [1.8, 3.0]: {len(in_range)}")

# H99 analysis
print(f"\n{'='*60}")
print(f"H99 DETAILS: 3-0/0-3/3-1/1-3 at min 55-70 ({len(h99_details)} matches)")
print(f"{'='*60}")
if h99_details:
    ft_41 = sum(1 for d in h99_details if d['ft'] in ('4-1', '1-4'))
    print(f"  FT = 4-1 or 1-4: {ft_41} ({ft_41/len(h99_details)*100:.1f}%)")
    with_odds = sum(1 for d in h99_details if d['odds_41'] is not None or d['odds_14'] is not None)
    print(f"  With CS 4-1/1-4 odds: {with_odds}")

# H100 analysis
print(f"\n{'='*60}")
print(f"H100 DETAILS: 2-goal deficit at min 65-78 ({len(h100_details)} matches)")
print(f"{'='*60}")
if h100_details:
    ft_draw = sum(d['ft_draw'] for d in h100_details)
    print(f"  FT = Draw: {ft_draw} ({ft_draw/len(h100_details)*100:.1f}%)")
    with_odds = [d for d in h100_details if d['back_draw'] is not None]
    print(f"  With back_draw odds: {len(with_odds)}")
    if with_odds:
        avg_draw = sum(d['back_draw'] for d in with_odds) / len(with_odds)
        in_range = [d for d in with_odds if 9 <= d['back_draw'] <= 26]
        print(f"  Avg back_draw: {avg_draw:.2f}")
        print(f"  Odds in [9, 26]: {len(in_range)}")

# H101 analysis
print(f"\n{'='*60}")
print(f"H101 DETAILS: Score 0-2/2-0 at min 55-75 ({len(h101_details)} matches)")
print(f"{'='*60}")
if h101_details:
    changed = sum(d['ft_changed'] for d in h101_details)
    stayed = len(h101_details) - changed
    print(f"  Score stays (0-2/2-0 final): {stayed} ({stayed/len(h101_details)*100:.1f}%)")
    print(f"  Score changes:                {changed} ({changed/len(h101_details)*100:.1f}%)")
    # Check which were fav-losing situations
    fav_losing = 0
    for d in h101_details:
        bh = d['back_home']
        ba = d['back_away']
        if bh is not None and ba is not None:
            score = d['score']
            if score == '0-2':  # home losing -- is home the fav?
                if bh < ba and bh <= 2.0:  # home was fav pre
                    fav_losing += 1
            elif score == '2-0':  # away losing -- is away the fav?
                if ba < bh and ba <= 2.0:
                    fav_losing += 1
    print(f"  Favourite losing (cuota <= 2.0 at trigger): {fav_losing}")
    with_cs_odds = sum(1 for d in h101_details if d['odds_02'] is not None or d['odds_20'] is not None)
    print(f"  With CS 0-2/2-0 odds: {with_cs_odds}")

print(f"\n{'='*60}")
print("FEASIBILITY SUMMARY")
print(f"{'='*60}")
gate = max(15, finished // 25)
for name, n, note in [
    ("H96 LAY CS 3-2/2-3", h96_score32, "Raw scenario count, before stat filters"),
    ("H97 BACK Away Winner", h97_local_leading_away_dom, "After xG+SoT filters"),
    ("H98 LAY Over 5.5", h98_5plus_goals, "Raw 5+ goals, before deceleration filters"),
    ("H99 BACK CS 4-1/1-4", h99_score30_or_31, "3-0/3-1 universe, before xG/SoT/odds"),
    ("H100 BACK Draw 2-deficit", h100_2goal_deficit, "2-goal deficit with stats, before xG window"),
    ("H101 LAY CS 0-2/2-0", h101_score02_or_20, "Raw 0-2/2-0, before fav filter"),
]:
    status = "VIABLE" if n >= gate else ("BORDERLINE" if n >= gate * 0.6 else "LIKELY DEAD")
    print(f"  {name:35s}  N={n:4d}  gate={gate}  -> {status}  ({note})")
