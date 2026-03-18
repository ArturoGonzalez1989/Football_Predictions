import csv
from io import StringIO
from collections import defaultdict
import re

data = (
    "id,timestamp_utc,match_id,match_name,strategy,minute,score,recommendation,back_odds,min_odds,status,result,pl\n"
    "50,2026-03-17 00:33:27,racing-club-estudiantes-rio-cuarto,Racing Club - Estudiantes Rio Cuarto,cs_one_goal,70,1-0,BACK CS 1-0 @ 1.98,1.98,,lost,lost,-1.0\n"
    "51,2026-03-17 00:37:59,chapecoense-grêmio,Chapecoense - Grêmio,draw_11,70,1-1,BACK DRAW @ 1.77,1.77,1.2,won,won,0.73\n"
    "52,2026-03-17 00:38:00,chapecoense-grêmio,Chapecoense - Grêmio,cs_11,70,1-1,BACK CS 1-1 @ 2.08,2.08,,won,won,1.03\n"
    "53,2026-03-17 01:09:31,colo-colo-huachipato,Colo Colo - Huachipato,cs_one_goal,70,1-0,BACK CS 1-0 @ 1.96,1.96,,lost,lost,-1.0\n"
    "54,2026-03-17 01:28:15,colo-colo-huachipato,Colo Colo - Huachipato,cs_20,88,2-0,BACK CS 2-0 @ 1.22,1.22,,won,won,0.21\n"
    "55,2026-03-17 02:19:30,umecit-union-cocle,UMECIT - Union Cocle,goal_clustering,47,0-1,BACK Over 1.5 @ 1.31,1.31,,won,won,0.29\n"
    "56,2026-03-17 02:43:01,instituto-ca-independiente,Instituto - CA Independiente,under35_3goals,63,2-1,BACK UNDER 3.5 @ 2.46,2.46,1.4,lost,lost,-1.0\n"
    "57,2026-03-17 03:05:10,umecit-union-cocle,UMECIT - Union Cocle,cs_one_goal,71,0-1,BACK CS 0-1 @ 2.08,2.08,,lost,lost,-1.0\n"
    "58,2026-03-17 03:07:14,umecit-union-cocle,UMECIT - Union Cocle,draw_11,74,1-1,BACK DRAW @ 3.80,3.8,1.2,won,won,2.66\n"
    "59,2026-03-17 12:06:55,gimcheon-sangmu-gwangju-fc,Gimcheon Sangmu - Gwangju FC,cs_one_goal,71,0-1,BACK CS 0-1 @ 1.78,1.78,,lost,lost,-1.0\n"
    "60,2026-03-17 17:24:07,lokomotiv-sofia-septemvri,Lokomotiv Sofia - Septemvri,under35_3goals,63,3-0,BACK UNDER 3.5 @ 3.10,3.1,1.4,lost,lost,-1.0\n"
    "61,2026-03-17 17:31:01,lokomotiv-sofia-septemvri,Lokomotiv Sofia - Septemvri,cs_big_lead,70,3-0,BACK CS 3-0 @ 2.24,2.24,,won,won,1.18\n"
    "62,2026-03-17 18:24:45,fenerbahce-gaziantep-fk,Fenerbahce - Gaziantep FK,home_fav_leading,61,2-1,BACK HOME @ 1.56,1.56,1.4,won,won,0.53\n"
    "63,2026-03-17 18:36:57,fenerbahce-gaziantep-fk,Fenerbahce - Gaziantep FK,cs_big_lead,73,3-1,BACK CS 3-1 @ 2.24,2.24,,lost,lost,-1.0\n"
    "64,2026-03-17 19:21:26,sporting-de-lisboa-bodo-glimt,Sporting de Lisboa - Bodo Glimt,cs_20,75,2-0,BACK CS 2-0 @ 1.02,1.02,,pending,,\n"
    "65,2026-03-17 19:27:25,sporting-de-lisboa-bodo-glimt,Sporting de Lisboa - Bodo Glimt,cs_big_lead,81,3-0,BACK CS 3-0 @ 1.80,1.8,,pending,,\n"
    "66,2026-03-17 19:28:50,st-gallen-lugano,St Gallen - Lugano,draw_xg_conv,68,1-1,BACK DRAW @ 7.60,7.6,2.1,won,won,6.27\n"
    "67,2026-03-17 19:31:43,st-gallen-lugano,St Gallen - Lugano,cs_one_goal,71,1-0,BACK CS 1-0 @ 2.26,2.26,,lost,lost,-1.0\n"
    "68,2026-03-17 19:35:54,palermo-juve-stabia,Palermo - Juve Stabia,under35_3goals,70,2-1,BACK UNDER 3.5 @ 1.80,1.8,1.4,pending,,\n"
    "69,2026-03-17 19:40:05,palermo-juve-stabia,Palermo - Juve Stabia,draw_22,76,2-2,BACK DRAW @ 1.57,1.57,1.5,pending,,\n"
    "70,2026-03-17 20:23:07,fc-dordrecht-fc-oss,FC Dordrecht - FC Oss,under35_3goals,63,2-1,BACK UNDER 3.5 @ 3.45,3.45,1.4,lost,lost,-1.0\n"
    "71,2026-03-17 20:28:00,almere-city-rkc,Almere City - RKC,under35_3goals,63,1-2,BACK UNDER 3.5 @ 3.40,3.4,1.4,lost,lost,-1.0\n"
    "72,2026-03-17 20:29:51,fc-dordrecht-fc-oss,FC Dordrecht - FC Oss,draw_equalizer,70,2-2,BACK DRAW @ 6.80,6.8,2.5,won,won,5.51\n"
    "73,2026-03-17 20:31:22,spezia-empoli,Spezia - Empoli,cs_one_goal,72,1-0,BACK CS 1-0 @ 1.70,1.7,,lost,lost,-1.0\n"
    "74,2026-03-17 20:35:20,fc-dordrecht-fc-oss,FC Dordrecht - FC Oss,under35_late,67,2-1,BACK UNDER 3.5 @ 2.52,2.52,1.4,,lost,lost,-1.0\n"
    "75,2026-03-17 20:35:25,mantova-cesena,Mantova - Cesena,cs_20,75,2-0,BACK CS 2-0 @ 1.77,1.77,,lost,lost,-1.0\n"
    "76,2026-03-17 20:35:25,ado-den-haag-jong-fc-utrecht,Ado Den Haag - Jong FC Utrecht,cs_one_goal,71,1-0,BACK CS 1-0 @ 2.08,2.08,,pending,,\n"
    "77,2026-03-17 20:35:26,vvv-jong-ajax-amsterdam,VVV - Jong Ajax Amsterdam,longshot,70,0-1,BACK AWAY @ 1.74,1.74,1.5,won,won,0.7\n"
    "78,2026-03-17 20:35:31,vvv-jong-ajax-amsterdam,VVV - Jong Ajax Amsterdam,cs_one_goal,70,0-1,BACK CS 0-1 @ 2.84,2.84,,won,won,1.75\n"
    "79,2026-03-17 20:38:09,venezia-padova,Venezia - Padova,cs_big_lead,75,3-0,BACK CS 3-0 @ 1.78,1.78,,lost,lost,-1.0\n"
    "80,2026-03-17 20:43:06,venezia-padova,Venezia - Padova,under35_3goals,78,3-0,BACK UNDER 3.5 @ 1.65,1.65,1.4,lost,lost,-1.0\n"
    "81,2026-03-17 21:12:42,watford-wrexham,Watford - Wrexham,under35_3goals,64,2-1,BACK UNDER 3.5 @ 2.54,2.54,1.4,lost,lost,-1.0\n"
    "82,2026-03-17 21:27:55,chelsea-psg,Chelsea - PSG,under35_late,68,0-3,BACK UNDER 3.5 @ 2.76,2.76,1.4,lost,lost,-1.0\n"
    "83,2026-03-17 21:29:52,chelsea-psg,Chelsea - PSG,cs_big_lead,70,0-3,BACK CS 0-3 @ 2.26,2.26,,won,won,1.2\n"
    "84,2026-03-17 21:29:53,manchester-city-real-madrid,Manchester City - Real Madrid,draw_xg_conv,66,1-1,BACK DRAW @ 2.48,2.48,2.1,lost,lost,-1.0\n"
    "85,2026-03-17 21:31:37,barnsley-wigan,Barnsley - Wigan,cs_one_goal,71,0-1,BACK CS 0-1 @ 2.40,2.4,,lost,lost,-1.0\n"
    "86,2026-03-17 21:31:40,barnsley-wigan,Barnsley - Wigan,away_fav_leading,71,0-1,BACK AWAY @ 1.51,1.51,1.2,lost,lost,-1.0\n"
    "87,2026-03-17 21:33:33,manchester-city-real-madrid,Manchester City - Real Madrid,cs_11,70,1-1,BACK CS 1-1 @ 3.20,3.2,,lost,lost,-1.0\n"
    "88,2026-03-17 21:42:18,arsenal-leverkusen,Arsenal - Leverkusen,cs_20,82,2-0,BACK CS 2-0 @ 1.56,1.56,,won,won,0.53\n"
    "89,2026-03-17 21:59:01,watford-wrexham,Watford - Wrexham,under35_late,75,2-1,BACK UNDER 3.5 @ 2.38,2.38,1.4,,lost,lost,-1.0\n"
    "90,2026-03-17 22:41:20,llaneros-cucuta-deportivo,Llaneros - Cucuta Deportivo,under35_3goals,61,2-1,BACK UNDER 3.5 @ 2.56,2.56,1.4,pending,,\n"
)

reader = csv.DictReader(StringIO(data))
bets = list(reader)

print(f"TOTAL BETS: {len(bets)}")

won = [b for b in bets if b['result'] == 'won']
lost = [b for b in bets if b['result'] == 'lost']
pending = [b for b in bets if b['result'] not in ('won','lost')]

resolved = won + lost
won_pl = sum(float(b['pl']) for b in won)
lost_pl = sum(-1.0 for b in lost)
total_pl = won_pl + lost_pl

print(f"Won: {len(won)}, Lost: {len(lost)}, Pending: {len(pending)}")
print(f"Win rate (resolved {len(resolved)}): {len(won)/len(resolved)*100:.1f}%")
print(f"Won P&L: {won_pl:+.2f}")
print(f"Lost P&L: {lost_pl:+.2f}")
print(f"Total P&L resolved: {total_pl:+.2f}")

print("\n--- PER STRATEGY ---")
strat_stats = defaultdict(lambda: {'n':0,'won':0,'lost':0,'pending':0,'pl':0.0})
for b in bets:
    s = b['strategy']
    strat_stats[s]['n'] += 1
    if b['result'] == 'won':
        strat_stats[s]['won'] += 1
        strat_stats[s]['pl'] += float(b['pl'])
    elif b['result'] == 'lost':
        strat_stats[s]['lost'] += 1
        strat_stats[s]['pl'] -= 1.0
    else:
        strat_stats[s]['pending'] += 1

for s, st in sorted(strat_stats.items(), key=lambda x: x[1]['n'], reverse=True):
    r = st['won'] + st['lost']
    wr = st['won']/r*100 if r > 0 else 0
    print(f"  {s}: N={st['n']} W={st['won']} L={st['lost']} P={st['pending']}  WR={wr:.0f}%  PL={st['pl']:+.2f}")

print("\n--- MARKET DEDUP ANALYSIS (live logic: text-based) ---")
match_bets = defaultdict(list)
for b in bets:
    match_bets[b['match_id']].append(b)

def live_market_key(b):
    rec = b['recommendation'].upper()
    match_id = b['match_id']
    if ' CS ' in rec:
        cs_match = re.search(r'CS\s+(\d+)[_-](\d+)', rec)
        if cs_match:
            return f"{match_id}::cs_{cs_match.group(1)}_{cs_match.group(2)}"
    if 'OVER' in rec:
        parts = rec.split()
        over_idx = next((i for i,p in enumerate(parts) if p=='OVER'), -1)
        if over_idx >= 0 and over_idx+1 < len(parts):
            return f"{match_id}::over_{parts[over_idx+1]}"
    if 'UNDER' in rec:
        parts = rec.split()
        under_idx = next((i for i,p in enumerate(parts) if p=='UNDER'), -1)
        if under_idx >= 0 and under_idx+1 < len(parts):
            return f"{match_id}::under_{parts[under_idx+1]}"
    if 'HOME' in rec:
        return f"{match_id}::home"
    if 'AWAY' in rec:
        return f"{match_id}::away"
    if 'DRAW' in rec:
        return f"{match_id}::draw"
    return f"{match_id}::unknown"

print("Checking for market dedup violations (same market key in same match):")
seen_keys = defaultdict(list)
for b in bets:
    k = live_market_key(b)
    seen_keys[k].append(b)

violations = {k: v for k, v in seen_keys.items() if len(v) > 1}
if violations:
    for k, bs in violations.items():
        ids = [b['id'] for b in bs]
        strats = [b['strategy'] for b in bs]
        recs = [b['recommendation'] for b in bs]
        mins = [b['minute'] for b in bs]
        print(f"  VIOLATION key={k}")
        for i, bx in enumerate(bs):
            print(f"    ID={bx['id']} min={bx['minute']} strat={bx['strategy']} rec={bx['recommendation']}")
else:
    print("  No violations found")

print("\n--- UNDER_3.5 MARKET GROUP VIOLATIONS (strategy-level, same match) ---")
under35_strategies = {'under35_late', 'under35_3goals'}
for mid, mbets in match_bets.items():
    under_bets = [b for b in mbets if b['strategy'] in under35_strategies]
    if len(under_bets) > 1:
        print(f"  VIOLATION in {mbets[0]['match_name']}:")
        for b in under_bets:
            print(f"    ID={b['id']} min={b['minute']} strat={b['strategy']} score={b['score']} odds={b['back_odds']}")

print("\n--- DRAW MARKET GROUP VIOLATIONS ---")
draw_strategies = {'draw_11', 'draw_xg_conv', 'draw_equalizer', 'draw_22', 'cs_11'}
for mid, mbets in match_bets.items():
    draw_bets = [b for b in mbets if b['strategy'] in draw_strategies]
    if len(draw_bets) > 1:
        print(f"  In {mbets[0]['match_name']}:")
        for b in draw_bets:
            print(f"    ID={b['id']} min={b['minute']} strat={b['strategy']} score={b['score']} key={live_market_key(b)}")
        # Check if any share same live market key
        keys = [live_market_key(b) for b in draw_bets]
        if len(set(keys)) < len(keys):
            print(f"    ** LIVE DEDUP VIOLATION: same market key used twice **")
        else:
            print(f"    (different market keys, no live dedup violation - cs_11 is cs_1_1 not draw)")

print("\n--- SCORE COHERENCE ANALYSIS ---")
issues = []
for b in bets:
    mid = b['match_id']
    strat = b['strategy']
    score = b['score']
    minute = int(b['minute'])
    try:
        parts = score.split('-')
        gl = int(parts[0])
        gv = int(parts[1])
        total_goals = gl + gv
    except:
        issues.append(f"ID {b['id']}: unparseable score '{score}'")
        continue

    if strat == 'under35_3goals' and total_goals != 3:
        issues.append(f"ID {b['id']} ({b['match_name']}): under35_3goals fired with {total_goals} goals ({score}) -- EXPECTS EXACTLY 3")

    if strat == 'under35_late':
        cfg_goals_min = 2
        cfg_goals_max = 3
        if not (cfg_goals_min <= total_goals <= cfg_goals_max):
            issues.append(f"ID {b['id']} ({b['match_name']}): under35_late fired with {total_goals} goals ({score}) -- expects 2-3 goals")

    if strat == 'cs_20':
        if not ((gl==2 and gv==0) or (gl==0 and gv==2)):
            issues.append(f"ID {b['id']} ({b['match_name']}): cs_20 fired with score {score} -- expects 2-0 or 0-2")

    if strat == 'cs_big_lead':
        valid = {(3,0),(0,3),(3,1),(1,3)}
        if (gl,gv) not in valid:
            issues.append(f"ID {b['id']} ({b['match_name']}): cs_big_lead fired with score {score} -- expects 3-0/0-3/3-1/1-3")

    if strat == 'draw_11' and (gl!=1 or gv!=1):
        issues.append(f"ID {b['id']} ({b['match_name']}): draw_11 fired with score {score} -- expects 1-1")

    if strat == 'draw_22' and (gl!=2 or gv!=2):
        issues.append(f"ID {b['id']} ({b['match_name']}): draw_22 fired with score {score} -- expects 2-2")

    if strat == 'cs_11' and (gl!=1 or gv!=1):
        issues.append(f"ID {b['id']} ({b['match_name']}): cs_11 fired with score {score} -- expects 1-1")

    if strat == 'cs_one_goal':
        diff = abs(gl - gv)
        if diff != 1:
            issues.append(f"ID {b['id']} ({b['match_name']}): cs_one_goal score {score} diff={diff} -- expects 1")

    if strat == 'away_fav_leading' and gv <= gl:
        issues.append(f"ID {b['id']} ({b['match_name']}): away_fav_leading with score {score} -- away team not leading")

    if strat == 'home_fav_leading' and gl <= gv:
        issues.append(f"ID {b['id']} ({b['match_name']}): home_fav_leading with score {score} -- home team not leading")

if issues:
    for i in issues:
        print(f"  ISSUE: {i}")
else:
    print("  No score coherence issues")

print("\n--- ST GALLEN LUGANO: SCORE TIMELINE ANOMALY ---")
sg_bets = [b for b in bets if b['match_id'] == 'st-gallen-lugano']
for b in sg_bets:
    print(f"  ID={b['id']} min={b['minute']} score={b['score']} strat={b['strategy']} rec={b['recommendation']}")
print("  NOTE: draw_xg_conv at min=68 score=1-1, then cs_one_goal at min=71 score=1-0")
print("  This implies score regressed from 1-1 to 1-0 -- possible goal cancellation or score oscillation in CSV")

print("\n--- FC DORDRECHT UNDER_3.5 DEDUP CHECK ---")
dordrecht_bets = [b for b in bets if b['match_id'] == 'fc-dordrecht-fc-oss']
for b in dordrecht_bets:
    print(f"  ID={b['id']} min={b['minute']} score={b['score']} strat={b['strategy']} key={live_market_key(b)}")

print("\n--- ODDS EXTREMES ---")
for b in bets:
    odds = float(b['back_odds'])
    if odds <= 1.10:
        print(f"  CRITICAL LOW: ID {b['id']} {b['strategy']} {b['match_name']} odds={odds} (near-certainty, terrible value)")
    elif odds < 1.30:
        print(f"  LOW: ID {b['id']} {b['strategy']} {b['match_name']} odds={odds}")

print("\n--- PENDING BETS ANALYSIS ---")
for b in pending:
    print(f"  ID={b['id']} {b['match_name']} strat={b['strategy']} min={b['minute']} score={b['score']} odds={b['back_odds']}")

print("\n--- WATFORD WREXHAM DOUBLE UNDER35 ---")
ww = [b for b in bets if b['match_id'] == 'watford-wrexham']
for b in ww:
    print(f"  ID={b['id']} min={b['minute']} score={b['score']} strat={b['strategy']} key={live_market_key(b)}")

print("\n--- CHELSEA PSG: UNDER35_LATE WITH 3 GOALS ---")
cp = [b for b in bets if b['match_id'] == 'chelsea-psg']
for b in cp:
    print(f"  ID={b['id']} min={b['minute']} score={b['score']} strat={b['strategy']} total_goals={sum(int(x) for x in b['score'].split('-'))}")

print("\n--- CHAPECOENSE: DRAW_11 + CS_11 DEDUP ---")
chap = [b for b in bets if b['match_id'] == 'chapecoense-grêmio']
for b in chap:
    mk = live_market_key(b)
    print(f"  ID={b['id']} strat={b['strategy']} key={mk}")
print("  NOTE: draw_11 -> '::draw', cs_11 -> '::cs_1_1' -- DIFFERENT keys, dedup does NOT apply")
print("  Both fire at same minute (70) same score (1-1). cs_11 is a different market (correct score vs match result).")

print("\n--- PALERMO: UNDER35_3GOALS + DRAW_22 ---")
pal = [b for b in bets if b['match_id'] == 'palermo-juve-stabia']
for b in pal:
    mk = live_market_key(b)
    print(f"  ID={b['id']} min={b['minute']} score={b['score']} strat={b['strategy']} key={mk}")
print("  NOTE: under35_3goals at min=70 score=2-1 (3 total), draw_22 at min=76 score=2-2")
print("  Score went from 2-1 -> 2-2 between mins 70-76. Coherent. Different markets (under_3.5 vs draw).")

print("\n--- UMECIT: GOAL_CLUSTERING + CS_ONE_GOAL + DRAW_11 ---")
um = [b for b in bets if b['match_id'] == 'umecit-union-cocle']
for b in um:
    mk = live_market_key(b)
    print(f"  ID={b['id']} min={b['minute']} score={b['score']} strat={b['strategy']} key={mk}")
