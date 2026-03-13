"""
Backtest H101: LAY CS 0-2/2-0
BROADER version: no favourite filter (since only 2 matches have fav losing at cuota<=2.0)
Instead: LAY the current CS when score is 0-2 or 2-0 at min 55-85.
Win if FT != that exact CS. Loss if FT == that CS.

Grid search:
  min_start: [55, 60, 65, 70]
  min_end: [75, 80, 85]
  odds_min: [2.0, 2.5, 3.0]
  odds_max: [6.0, 8.0, 10.0]
"""
import os, glob, csv, math, json
from collections import defaultdict

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
    z = 1.96
    p = wins / n
    denom = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denom
    margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return (round(max(0, centre-margin)*100, 1), round(min(1, centre+margin)*100, 1))

def max_drawdown(pls):
    cum = peak = dd = 0
    for pl in pls:
        cum += pl
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return round(dd, 2)

def sharpe_ratio(pls):
    if len(pls) < 2: return 0.0
    mean = sum(pls)/len(pls)
    var = sum((p-mean)**2 for p in pls)/(len(pls)-1)
    std = math.sqrt(var) if var > 0 else 0.001
    return round(mean/std * math.sqrt(len(pls)), 2)

def pl_lay(lay_odds, won):
    """LAY bet P/L. Won = event did NOT happen."""
    if won:
        return round(STAKE * 0.95, 2)  # collect stake minus commission
    else:
        return round(-(STAKE * (lay_odds - 1)), 2)  # pay out liability

# Load matches
pattern = os.path.join(DATA_DIR, "partido_*.csv")
files = glob.glob(pattern)
matches = []
for fpath in files:
    rows = []
    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except:
        continue
    if len(rows) < 5: continue
    last = rows[-1]
    gl = _i(last.get("goles_local",""))
    gv = _i(last.get("goles_visitante",""))
    if gl is None or gv is None: continue
    matches.append({
        "file": os.path.basename(fpath),
        "match_id": os.path.basename(fpath).replace("partido_","").replace(".csv",""),
        "ft_local": gl, "ft_visitante": gv,
        "rows": rows,
        "league": last.get("Liga","?"),
        "timestamp_first": rows[0].get("timestamp_utc",""),
    })

print(f"Loaded {len(matches)} finished matches")

# Grid search
grid = []
for ms in [55, 60, 65, 70]:
    for me in [75, 80, 85]:
        if me <= ms: continue
        for omin in [2.0, 2.5, 3.0]:
            for omax in [6.0, 8.0, 10.0]:
                grid.append((ms, me, omin, omax))

print(f"Grid size: {len(grid)} combos")

best = None
best_sharpe = -999
results = []

for ms, me, omin, omax in grid:
    bets = []
    for match in matches:
        triggered = False
        for idx, row in enumerate(match["rows"]):
            if triggered: break
            m = _f(row.get("minuto",""))
            if m is None or not (ms <= m <= me): continue
            gl = _i(row.get("goles_local",""))
            gv = _i(row.get("goles_visitante",""))
            if gl is None or gv is None: continue

            # Score must be 0-2 or 2-0
            if not ((gl == 0 and gv == 2) or (gl == 2 and gv == 0)):
                continue

            # Get CS odds for the current score
            if gl == 0 and gv == 2:
                odds_col = "back_rc_0_2"
                ft_match = (match["ft_local"] == 0 and match["ft_visitante"] == 2)
            else:  # gl == 2, gv == 0
                odds_col = "back_rc_2_0"
                ft_match = (match["ft_local"] == 2 and match["ft_visitante"] == 0)

            odds = _f(row.get(odds_col, ""))
            if odds is None or not (omin <= odds <= omax):
                continue

            # LAY this CS: win if FT != this CS
            won = not ft_match
            pl = pl_lay(odds, won)

            bets.append({
                "match_id": match["match_id"],
                "won": won,
                "pl": pl,
                "odds": odds,
                "bet_type": "lay",
                "minuto": m,
                "score": f"{gl}-{gv}",
                "ft": f"{match['ft_local']}-{match['ft_visitante']}",
                "league": match["league"],
                "timestamp": match["timestamp_first"],
                "strategy": "lay_cs_02_20",
            })
            triggered = True

    n = len(bets)
    if n < 10: continue

    wins = sum(1 for b in bets if b["won"])
    wr = wins/n*100
    total_pl = sum(b["pl"] for b in bets)
    roi = total_pl/(n*STAKE)*100
    avg_odds = sum(b["odds"] for b in bets)/n
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    sh = sharpe_ratio(pls)
    md = max_drawdown(pls)
    leagues = len(set(b["league"] for b in bets))

    # Train/test split
    sorted_bets = sorted(bets, key=lambda b: b["timestamp"])
    sp = int(len(sorted_bets)*0.7)
    train, test = sorted_bets[:sp], sorted_bets[sp:]
    train_pl = sum(b["pl"] for b in train)
    test_pl = sum(b["pl"] for b in test)
    train_roi = train_pl/(len(train)*STAKE)*100 if train else 0
    test_roi = test_pl/(len(test)*STAKE)*100 if test else 0

    r = {
        "params": f"min={ms}-{me}, odds={omin}-{omax}",
        "n": n, "wins": wins, "wr": round(wr,1),
        "roi": round(roi,1), "pl": round(total_pl,2),
        "avg_odds": round(avg_odds,2),
        "ci95": (ci_lo, ci_hi), "sharpe": sh, "max_dd": md,
        "leagues": leagues,
        "train_roi": round(train_roi,1), "test_roi": round(test_roi,1),
        "train_n": len(train), "test_n": len(test),
    }
    results.append(r)

    if sh > best_sharpe and n >= 38:
        best_sharpe = sh
        best = r
        best_bets = bets

# Sort by Sharpe
results.sort(key=lambda x: x["sharpe"], reverse=True)

print(f"\n{'='*70}")
print(f"TOP 10 COMBOS BY SHARPE (N >= 10)")
print(f"{'='*70}")
for r in results[:10]:
    print(f"  {r['params']:35s}  N={r['n']:3d}  WR={r['wr']:5.1f}%  ROI={r['roi']:6.1f}%  "
          f"Sharpe={r['sharpe']:5.2f}  CI95=[{r['ci95'][0]:.1f},{r['ci95'][1]:.1f}]  "
          f"Train={r['train_roi']:5.1f}%  Test={r['test_roi']:5.1f}%  Leagues={r['leagues']}")

# Also show combos that pass all quality gates
gate_n = max(15, len(matches) // 25)
print(f"\n{'='*70}")
print(f"COMBOS PASSING ALL GATES (N>={gate_n}, ROI>=10%, CI95_lo>=40%, Train>0, Test>0)")
print(f"{'='*70}")
passing = [r for r in results
           if r['n'] >= gate_n
           and r['roi'] >= 10
           and r['ci95'][0] >= 40
           and r['train_roi'] > 0
           and r['test_roi'] > 0]
if not passing:
    print("  NONE")
else:
    for r in passing:
        print(f"  {r['params']:35s}  N={r['n']:3d}  WR={r['wr']:5.1f}%  ROI={r['roi']:6.1f}%  "
              f"Sharpe={r['sharpe']:5.2f}  CI95=[{r['ci95'][0]:.1f},{r['ci95'][1]:.1f}]  "
              f"Train={r['train_roi']:5.1f}%  Test={r['test_roi']:5.1f}%")

# Export best bets for validator
if best and best_bets:
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auxiliar", "sd_bt_h101_bets.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(best_bets, f, ensure_ascii=False)
    print(f"\nExported {len(best_bets)} bets to {out_path}")

print(f"\nBest combo: {best}")
