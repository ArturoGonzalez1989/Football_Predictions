"""
H67 vs H59 overlap analysis and H67-unique backtest.
H67 = away team leading late -> BACK Away
H59 = underdog leading late -> BACK underdog
Overlap = away underdog leading (both trigger)
H67-unique = away FAVOURITE leading (only H67 triggers)
"""
import os, glob, csv, math
from collections import defaultdict, Counter
from itertools import product

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "betfair_scraper", "data")
STAKE = 10.0

def _f(val):
    try:
        v = float(val)
        return v if not math.isnan(v) else None
    except (TypeError, ValueError):
        return None

def _i(val):
    v = _f(val)
    return int(v) if v is not None else None

def wilson_ci95(n, wins):
    if n == 0: return (0.0, 0.0)
    z = 1.96; p = wins / n; denom = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denom
    margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return (round(max(0,centre-margin)*100,1), round(min(1,centre+margin)*100,1))

def max_drawdown(pls):
    c = peak = md = 0
    for p in pls:
        c += p; peak = max(peak, c); md = max(md, peak-c)
    return round(md, 2)

def sharpe_ratio(pls):
    if len(pls)<2: return 0.0
    m = sum(pls)/len(pls); v = sum((p-m)**2 for p in pls)/(len(pls)-1)
    s = math.sqrt(v) if v>0 else 0.001
    return round(m/s*math.sqrt(len(pls)), 2)

def pl_back(odds, won):
    return round(STAKE*(odds-1)*0.95, 2) if won else -STAKE

# Load all matches
pattern = os.path.join(DATA_DIR, "partido_*.csv")
files = glob.glob(pattern)

all_bets = []  # Full H67
h59_overlap_bets = []  # Overlap (away underdog leading)
h67_only_bets = []  # H67-unique (away favourite leading)

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

    match_id = os.path.basename(fpath).replace("partido_", "").replace(".csv", "")
    league = last.get("Liga", "?")
    timestamp = rows[0].get("timestamp_utc", "")

    # Get pre-match odds (first 5 rows)
    early_home, early_away = None, None
    for row in rows[:5]:
        bh = _f(row.get("back_home", ""))
        ba = _f(row.get("back_away", ""))
        if bh and ba and bh > 1 and ba > 1:
            early_home = bh
            early_away = ba
            break

    triggered = False
    for row in rows:
        if triggered:
            break
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue
        if not (60 <= m <= 88):
            continue
        if cur_gv <= cur_gl:
            continue
        if cur_gv - cur_gl > 3:
            continue

        odds = _f(row.get("back_away", ""))
        if not odds or odds <= 1.01 or odds > 10:
            continue

        won = gv > gl
        bet = {
            "won": won,
            "pl": pl_back(odds, won),
            "odds": odds,
            "match_id": match_id,
            "league": league,
            "timestamp": timestamp,
            "early_home": early_home,
            "early_away": early_away,
            "lead": cur_gv - cur_gl,
            "minute": m,
        }
        all_bets.append(bet)

        # Classify: is away team the underdog (higher pre-match odds)?
        is_underdog = False
        if early_home and early_away:
            is_underdog = early_away > early_home  # Away has higher odds = underdog

        if is_underdog:
            h59_overlap_bets.append(bet)
        else:
            h67_only_bets.append(bet)

        triggered = True

def evaluate(bets, label):
    if not bets:
        print(f"  {label}: No bets")
        return
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins/n*100
    total_pl = sum(b["pl"] for b in bets)
    avg_odds = sum(b["odds"] for b in bets)/n
    roi = total_pl/(n*STAKE)*100
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    leagues = set(b["league"] for b in bets)

    sorted_bets = sorted(bets, key=lambda b: b["timestamp"])
    split = int(len(sorted_bets) * 0.7)
    train = sorted_bets[:split]
    test = sorted_bets[split:]
    train_roi = sum(b["pl"] for b in train)/(len(train)*STAKE)*100 if train else 0
    test_roi = sum(b["pl"] for b in test)/(len(test)*STAKE)*100 if test else 0

    won_odds = [b["odds"] for b in bets if b["won"]]
    lost_odds = [b["odds"] for b in bets if not b["won"]]

    print(f"\n  {label}:")
    print(f"    N={n}, WR={wr:.1f}%, ROI={roi:.1f}%, Sharpe={sharpe_ratio(pls)}")
    print(f"    Avg odds={avg_odds:.2f}, PL={total_pl:.2f}, MaxDD={max_drawdown(pls)}")
    print(f"    CI95=[{ci_lo}, {ci_hi}]")
    print(f"    Train: N={len(train)}, ROI={train_roi:.1f}%")
    print(f"    Test: N={len(test)}, ROI={test_roi:.1f}%")
    print(f"    Leagues={len(leagues)}")
    print(f"    Won odds avg={sum(won_odds)/len(won_odds):.2f}" if won_odds else "")
    print(f"    Lost odds avg={sum(lost_odds)/len(lost_odds):.2f}" if lost_odds else "")

print("="*60)
print("H67 DECOMPOSITION: Full vs Overlap vs Unique")
print("="*60)

evaluate(all_bets, "FULL H67 (min=60-88, lead<=3, odds<=10)")
evaluate(h59_overlap_bets, "OVERLAP (away UNDERDOG leading) = would also trigger H59")
evaluate(h67_only_bets, "UNIQUE (away FAVOURITE leading) = H67-only")

# Now test H67-unique with various configs
print("\n" + "="*60)
print("H67-UNIQUE GRID SEARCH (away favourite leading)")
print("="*60)

# Rebuild with various minute ranges for unique portion only
for min_min, min_max, max_lead, odds_max in product(
    [60, 65, 70],
    [82, 85, 88],
    [1, 2, 3],
    [5.0, 10.0],
):
    if min_max <= min_min + 8:
        continue

    bets = []
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

        match_id = os.path.basename(fpath).replace("partido_", "").replace(".csv", "")
        league = last.get("Liga", "?")
        timestamp = rows[0].get("timestamp_utc", "")

        early_home, early_away = None, None
        for row in rows[:5]:
            bh = _f(row.get("back_home", ""))
            ba = _f(row.get("back_away", ""))
            if bh and ba and bh > 1 and ba > 1:
                early_home = bh
                early_away = ba
                break

        if not early_home or not early_away:
            continue
        # Only away FAVOURITE (away odds <= home odds)
        if early_away > early_home:
            continue

        triggered = False
        for row in rows:
            if triggered:
                break
            m = _f(row.get("minuto", ""))
            cur_gl = _i(row.get("goles_local", ""))
            cur_gv = _i(row.get("goles_visitante", ""))
            if m is None or cur_gl is None or cur_gv is None:
                continue
            if not (min_min <= m <= min_max):
                continue
            if cur_gv <= cur_gl:
                continue
            if cur_gv - cur_gl > max_lead:
                continue
            odds = _f(row.get("back_away", ""))
            if not odds or odds <= 1.01 or odds > odds_max:
                continue

            won = gv_ft > gl_ft
            bets.append({
                "won": won,
                "pl": pl_back(odds, won),
                "odds": odds,
                "match_id": match_id,
                "league": league,
                "timestamp": timestamp,
            })
            triggered = True

    if len(bets) < 30:
        continue

    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins/n*100
    total_pl = sum(b["pl"] for b in bets)
    avg_odds = sum(b["odds"] for b in bets)/n
    roi = total_pl/(n*STAKE)*100
    ci_lo, _ = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    sh = sharpe_ratio(pls)
    leagues = len(set(b["league"] for b in bets))

    sorted_b = sorted(bets, key=lambda b: b["timestamp"])
    split = int(len(sorted_b)*0.7)
    train_roi = sum(b["pl"] for b in sorted_b[:split])/(split*STAKE)*100 if split else 0
    test_n = n - split
    test_roi = sum(b["pl"] for b in sorted_b[split:])/(test_n*STAKE)*100 if test_n else 0

    passes = n>=60 and test_n>=18 and train_roi>0 and test_roi>0 and ci_lo>40 and leagues>=3
    tag = "PASS" if passes else "fail"
    print(f"  [{tag}] min={min_min}-{min_max},lead<={max_lead},odds<={odds_max}: "
          f"N={n}, WR={wr:.1f}%, ROI={roi:.1f}%, Sh={sh}, CI95lo={ci_lo}, "
          f"train={train_roi:.1f}%/test={test_roi:.1f}%, L={leagues}")

# Also check: HOME leading (home is not favourite)
print("\n" + "="*60)
print("BONUS: HOME UNDERDOG leading late (complement to H67-unique)")
print("="*60)

for min_min, min_max, max_lead, odds_max in product(
    [60, 65, 70],
    [82, 85, 88],
    [1, 2, 3],
    [5.0, 10.0],
):
    if min_max <= min_min + 8:
        continue

    bets = []
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

        match_id = os.path.basename(fpath).replace("partido_", "").replace(".csv", "")
        league = last.get("Liga", "?")
        timestamp = rows[0].get("timestamp_utc", "")

        early_home, early_away = None, None
        for row in rows[:5]:
            bh = _f(row.get("back_home", ""))
            ba = _f(row.get("back_away", ""))
            if bh and ba and bh > 1 and ba > 1:
                early_home = bh
                early_away = ba
                break

        if not early_home or not early_away:
            continue
        # HOME UNDERDOG (home odds > away odds, i.e. away is fav)
        if early_home <= early_away:
            continue

        triggered = False
        for row in rows:
            if triggered:
                break
            m = _f(row.get("minuto", ""))
            cur_gl = _i(row.get("goles_local", ""))
            cur_gv = _i(row.get("goles_visitante", ""))
            if m is None or cur_gl is None or cur_gv is None:
                continue
            if not (min_min <= m <= min_max):
                continue
            if cur_gl <= cur_gv:  # Home must be leading
                continue
            if cur_gl - cur_gv > max_lead:
                continue
            odds = _f(row.get("back_home", ""))
            if not odds or odds <= 1.01 or odds > odds_max:
                continue

            won = gl_ft > gv_ft
            bets.append({
                "won": won,
                "pl": pl_back(odds, won),
                "odds": odds,
                "match_id": match_id,
                "league": league,
                "timestamp": timestamp,
            })
            triggered = True

    if len(bets) < 20:
        continue

    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins/n*100
    total_pl = sum(b["pl"] for b in bets)
    avg_odds = sum(b["odds"] for b in bets)/n
    roi = total_pl/(n*STAKE)*100
    ci_lo, _ = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    sh = sharpe_ratio(pls)
    leagues = len(set(b["league"] for b in bets))

    sorted_b = sorted(bets, key=lambda b: b["timestamp"])
    split = int(len(sorted_b)*0.7)
    train_roi = sum(b["pl"] for b in sorted_b[:split])/(split*STAKE)*100 if split else 0
    test_n = n - split
    test_roi = sum(b["pl"] for b in sorted_b[split:])/(test_n*STAKE)*100 if test_n else 0

    passes = n>=60 and test_n>=18 and train_roi>0 and test_roi>0 and ci_lo>40 and leagues>=3
    tag = "PASS" if passes else "fail"
    print(f"  [{tag}] min={min_min}-{min_max},lead<={max_lead},odds<={odds_max}: "
          f"N={n}, WR={wr:.1f}%, ROI={roi:.1f}%, Sh={sh}, CI95lo={ci_lo}, "
          f"train={train_roi:.1f}%/test={test_roi:.1f}%, L={leagues}")

print("\n" + "="*60)
print("DONE")
print("="*60)
