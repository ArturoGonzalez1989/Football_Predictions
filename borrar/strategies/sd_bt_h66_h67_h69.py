"""
Backtest H66, H67, H69 with parameter grid search.
H66: BACK Under 3.5 Three-Goal Lid
H67: BACK Away Winner Late Lead
H69: BACK Under 0.5 Late Scoreless
"""
import os, glob, csv, math, json
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
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0, centre - margin) * 100, 1), round(min(1, centre + margin) * 100, 1))

def max_drawdown(pls):
    cumulative = peak = 0
    max_dd = 0
    for pl in pls:
        cumulative += pl
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return round(max_dd, 2)

def sharpe_ratio(pls):
    if len(pls) < 2:
        return 0.0
    mean_pl = sum(pls) / len(pls)
    variance = sum((p - mean_pl) ** 2 for p in pls) / (len(pls) - 1)
    std_pl = math.sqrt(variance) if variance > 0 else 0.001
    return round(mean_pl / std_pl * math.sqrt(len(pls)), 2)

def pl_back(odds, won):
    return round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

def load_matches():
    pattern = os.path.join(DATA_DIR, "partido_*.csv")
    files = glob.glob(pattern)
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
            "ft_local": gl,
            "ft_visitante": gv,
            "ft_total": gl + gv,
            "rows": rows,
            "timestamp_first": rows[0].get("timestamp_utc", ""),
        })
    return matches

def evaluate(bets, label=""):
    if not bets:
        return None
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins / n * 100
    total_pl = sum(b["pl"] for b in bets)
    avg_odds = sum(b["odds"] for b in bets) / n
    roi = total_pl / (n * STAKE) * 100
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    leagues = set(b.get("league", "?") for b in bets)

    # Train/test split
    sorted_bets = sorted(bets, key=lambda b: b.get("timestamp", ""))
    split = int(len(sorted_bets) * 0.7)
    train = sorted_bets[:split]
    test = sorted_bets[split:]
    train_wins = sum(1 for b in train if b["won"])
    test_wins = sum(1 for b in test if b["won"])
    train_pl = sum(b["pl"] for b in train)
    test_pl = sum(b["pl"] for b in test)
    train_roi = train_pl / (len(train) * STAKE) * 100 if train else 0
    test_roi = test_pl / (len(test) * STAKE) * 100 if test else 0

    # Date concentration
    dates = sorted(b.get("timestamp", "")[:10] for b in bets)
    max_conc = 0
    for i in range(len(dates)):
        count = sum(1 for d in dates[i:] if d and dates[i] and d <= dates[i][:8] + str(min(int(dates[i][8:10] or 1) + 3, 31)).zfill(2))
        max_conc = max(max_conc, count / n * 100)

    # Won vs lost odds comparison
    won_odds = [b["odds"] for b in bets if b["won"]]
    lost_odds = [b["odds"] for b in bets if not b["won"]]
    avg_won_odds = sum(won_odds) / len(won_odds) if won_odds else 0
    avg_lost_odds = sum(lost_odds) / len(lost_odds) if lost_odds else 0

    return {
        "label": label,
        "n": n, "wins": wins, "wr": round(wr, 1),
        "avg_odds": round(avg_odds, 2),
        "roi": round(roi, 1),
        "total_pl": round(total_pl, 2),
        "ci_lo": ci_lo, "ci_hi": ci_hi,
        "max_dd": max_drawdown(pls),
        "sharpe": sharpe_ratio(pls),
        "leagues": len(leagues),
        "league_list": sorted(leagues),
        "n_train": len(train), "n_test": len(test),
        "train_roi": round(train_roi, 1),
        "test_roi": round(test_roi, 1),
        "date_conc": round(max_conc, 1),
        "avg_won_odds": round(avg_won_odds, 2),
        "avg_lost_odds": round(avg_lost_odds, 2),
    }

def check_gates(r):
    gates = {}
    gates["G1_N>=60"] = r["n"] >= 60
    gates["G2_Ntest>=18"] = r["n_test"] >= 18
    gates["G3_ROI_both>0"] = r["train_roi"] > 0 and r["test_roi"] > 0
    gates["G4_IC95lo>40"] = r["ci_lo"] > 40
    gates["G5_MaxDD<400"] = r["max_dd"] < 400
    gates["G7_Leagues>=3"] = r["leagues"] >= 3
    gates["G8_DateConc<50"] = r["date_conc"] < 50
    return gates

def print_result(r, gates):
    passed = all(gates.values())
    status = "PASS" if passed else "FAIL"
    failed = [k for k, v in gates.items() if not v]
    print(f"\n  [{status}] {r['label']}")
    print(f"    N={r['n']}, WR={r['wr']}%, ROI={r['roi']}%, Sharpe={r['sharpe']}")
    print(f"    Avg odds={r['avg_odds']}, PL={r['total_pl']}, MaxDD={r['max_dd']}")
    print(f"    CI95=[{r['ci_lo']}, {r['ci_hi']}]")
    print(f"    Train: N={r['n_train']}, ROI={r['train_roi']}%")
    print(f"    Test: N={r['n_test']}, ROI={r['test_roi']}%")
    print(f"    Leagues={r['leagues']}, DateConc={r['date_conc']}%")
    print(f"    Won odds avg={r['avg_won_odds']}, Lost odds avg={r['avg_lost_odds']}")
    if failed:
        print(f"    FAILED gates: {', '.join(failed)}")

# ============ LOAD DATA ============
print("Loading matches...")
matches = load_matches()
print(f"Loaded {len(matches)} matches")

# ============ H66: BACK Under 3.5 Three-Goal Lid ============
print("\n" + "="*60)
print("H66: BACK Under 3.5 Three-Goal Lid")
print("="*60)

best_h66 = None
for min_min, min_max, xg_max in product(
    [65, 68, 70, 72],
    [78, 80, 82, 85],
    [2.5, 3.0, 3.5, 99.0],  # 99=no filter
):
    if min_max <= min_min + 5:
        continue

    bets = []
    for match in matches:
        triggered = False
        for row in match["rows"]:
            if triggered:
                break
            m = _f(row.get("minuto", ""))
            cur_gl = _i(row.get("goles_local", ""))
            cur_gv = _i(row.get("goles_visitante", ""))
            if m is None or cur_gl is None or cur_gv is None:
                continue
            if not (min_min <= m <= min_max):
                continue
            if cur_gl + cur_gv != 3:
                continue

            # xG filter
            xg_l = _f(row.get("xg_local", ""))
            xg_v = _f(row.get("xg_visitante", ""))
            if xg_max < 90:
                if xg_l is None or xg_v is None:
                    continue
                if xg_l + xg_v >= xg_max:
                    continue

            odds = _f(row.get("back_under35", ""))
            if not odds or odds <= 1.01 or odds > 10:
                continue

            won = match["ft_total"] <= 3
            bets.append({
                "won": won,
                "pl": pl_back(odds, won),
                "odds": odds,
                "match_id": match["match_id"],
                "league": match["league"],
                "timestamp": match["timestamp_first"],
            })
            triggered = True

    if len(bets) < 30:
        continue

    r = evaluate(bets, f"min={min_min}-{min_max},xg_max={xg_max}")
    gates = check_gates(r)
    if all(gates.values()):
        print_result(r, gates)
        if best_h66 is None or r["sharpe"] > best_h66["sharpe"]:
            best_h66 = r

if best_h66:
    print(f"\n  >>> BEST H66: {best_h66['label']}")
else:
    print("\n  No H66 config passes all gates.")

# ============ H67: BACK Away Winner Late Lead ============
print("\n" + "="*60)
print("H67: BACK Away Winner Late Lead")
print("="*60)

# Need to check overlap with H59 (underdog leading).
# H67 = away leading. H59 = underdog (higher pre-match odds) leading.
# Overlap: away underdog leading = both trigger. But away favourite leading = only H67.

best_h67 = None
h67_bets_best = []

for min_min, min_max, max_lead, odds_max in product(
    [60, 65, 68, 70],
    [80, 82, 85, 88],
    [1, 2, 3],
    [3.0, 5.0, 10.0, 50.0],
):
    if min_max <= min_min + 8:
        continue

    bets = []
    for match in matches:
        triggered = False
        for row in match["rows"]:
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

            won = match["ft_visitante"] > match["ft_local"]
            bets.append({
                "won": won,
                "pl": pl_back(odds, won),
                "odds": odds,
                "match_id": match["match_id"],
                "league": match["league"],
                "timestamp": match["timestamp_first"],
            })
            triggered = True

    if len(bets) < 30:
        continue

    r = evaluate(bets, f"min={min_min}-{min_max},lead<={max_lead},odds<={odds_max}")
    gates = check_gates(r)
    if all(gates.values()):
        print_result(r, gates)
        if best_h67 is None or r["sharpe"] > best_h67["sharpe"]:
            best_h67 = r
            h67_bets_best = bets

if best_h67:
    print(f"\n  >>> BEST H67: {best_h67['label']}")
    # Check overlap with H59
    h67_ids = set(b["match_id"] for b in h67_bets_best)
    print(f"  H67 match count: {len(h67_ids)}")
else:
    print("\n  No H67 config passes all gates.")

# ============ H69: BACK Under 0.5 Late Scoreless ============
print("\n" + "="*60)
print("H69: BACK Under 0.5 Late Scoreless")
print("="*60)

best_h69 = None
for min_min, min_max, odds_max in product(
    [70, 73, 75, 78, 80],
    [85, 88, 90],
    [3.0, 4.0, 5.0, 50.0],
):
    if min_max <= min_min + 5:
        continue

    bets = []
    for match in matches:
        triggered = False
        for row in match["rows"]:
            if triggered:
                break
            m = _f(row.get("minuto", ""))
            cur_gl = _i(row.get("goles_local", ""))
            cur_gv = _i(row.get("goles_visitante", ""))
            if m is None or cur_gl is None or cur_gv is None:
                continue
            if not (min_min <= m <= min_max):
                continue
            if cur_gl != 0 or cur_gv != 0:
                continue

            odds = _f(row.get("back_under05", ""))
            if not odds or odds <= 1.01 or odds > odds_max:
                continue

            won = match["ft_total"] == 0
            bets.append({
                "won": won,
                "pl": pl_back(odds, won),
                "odds": odds,
                "match_id": match["match_id"],
                "league": match["league"],
                "timestamp": match["timestamp_first"],
            })
            triggered = True

    if len(bets) < 30:
        continue

    r = evaluate(bets, f"min={min_min}-{min_max},odds<={odds_max}")
    gates = check_gates(r)
    if all(gates.values()):
        print_result(r, gates)
        if best_h69 is None or r["sharpe"] > best_h69["sharpe"]:
            best_h69 = r

if best_h69:
    print(f"\n  >>> BEST H69: {best_h69['label']}")
else:
    print("\n  No H69 config passes all gates.")
    # Show best failing
    print("\n  Top failing configs:")
    all_h69 = []
    for min_min, min_max, odds_max in product(
        [70, 73, 75, 78, 80],
        [85, 88, 90],
        [3.0, 4.0, 5.0, 50.0],
    ):
        if min_max <= min_min + 5:
            continue
        bets = []
        for match in matches:
            triggered = False
            for row in match["rows"]:
                if triggered:
                    break
                m = _f(row.get("minuto", ""))
                cur_gl = _i(row.get("goles_local", ""))
                cur_gv = _i(row.get("goles_visitante", ""))
                if m is None or cur_gl is None or cur_gv is None:
                    continue
                if not (min_min <= m <= min_max):
                    continue
                if cur_gl != 0 or cur_gv != 0:
                    continue
                odds = _f(row.get("back_under05", ""))
                if not odds or odds <= 1.01 or odds > odds_max:
                    continue
                won = match["ft_total"] == 0
                bets.append({
                    "won": won,
                    "pl": pl_back(odds, won),
                    "odds": odds,
                    "match_id": match["match_id"],
                    "league": match["league"],
                    "timestamp": match["timestamp_first"],
                })
                triggered = True
        if len(bets) >= 30:
            r = evaluate(bets, f"min={min_min}-{min_max},odds<={odds_max}")
            gates = check_gates(r)
            all_h69.append((r, gates))

    all_h69.sort(key=lambda x: x[0]["sharpe"], reverse=True)
    for r, gates in all_h69[:3]:
        print_result(r, gates)

# ============ H68: BACK Draw at 2-2 Late ============
print("\n" + "="*60)
print("H68: BACK Draw at 2-2 Late (quick check)")
print("="*60)

for min_min, min_max in [(65, 80), (68, 83), (70, 85), (72, 85), (75, 88)]:
    bets = []
    for match in matches:
        triggered = False
        for row in match["rows"]:
            if triggered:
                break
            m = _f(row.get("minuto", ""))
            cur_gl = _i(row.get("goles_local", ""))
            cur_gv = _i(row.get("goles_visitante", ""))
            if m is None or cur_gl is None or cur_gv is None:
                continue
            if not (min_min <= m <= min_max):
                continue
            if cur_gl != 2 or cur_gv != 2:
                continue
            odds = _f(row.get("back_draw", ""))
            if not odds or odds <= 1.01 or odds > 10:
                continue
            won = match["ft_local"] == match["ft_visitante"]
            bets.append({
                "won": won,
                "pl": pl_back(odds, won),
                "odds": odds,
                "match_id": match["match_id"],
                "league": match["league"],
                "timestamp": match["timestamp_first"],
            })
            triggered = True

    if bets:
        r = evaluate(bets, f"draw22 min={min_min}-{min_max}")
        print(f"  {r['label']}: N={r['n']}, WR={r['wr']}%, ROI={r['roi']}%, Sharpe={r['sharpe']}, CI95=[{r['ci_lo']},{r['ci_hi']}]")

# ============ OVERLAP CHECK H67 vs H59 ============
print("\n" + "="*60)
print("OVERLAP CHECK: H67 (away leading) vs H59 (underdog leading)")
print("="*60)

# Simulate H59: underdog leading at min 60-85
h59_ids = set()
h67_ids_all = set()

for match in matches:
    # Get pre-match odds
    early_home, early_away = None, None
    for row in match["rows"][:5]:
        bh = _f(row.get("back_home", ""))
        ba = _f(row.get("back_away", ""))
        if bh and ba and bh > 1 and ba > 1:
            early_home = bh
            early_away = ba
            break

    for row in match["rows"]:
        m = _f(row.get("minuto", ""))
        cur_gl = _i(row.get("goles_local", ""))
        cur_gv = _i(row.get("goles_visitante", ""))
        if m is None or cur_gl is None or cur_gv is None:
            continue
        if not (60 <= m <= 85):
            continue

        # H59: underdog leading
        if early_home and early_away and cur_gl != cur_gv:
            if (cur_gl > cur_gv and early_home > early_away) or \
               (cur_gv > cur_gl and early_away > early_home):
                h59_ids.add(match["match_id"])

        # H67: away leading (best config)
        if cur_gv > cur_gl:
            h67_ids_all.add(match["match_id"])

overlap = h67_ids_all & h59_ids
print(f"  H59 matches: {len(h59_ids)}")
print(f"  H67 matches: {len(h67_ids_all)}")
print(f"  Overlap: {len(overlap)} ({len(overlap)/max(len(h67_ids_all),1)*100:.1f}% of H67)")
only_h67 = h67_ids_all - h59_ids
print(f"  H67 unique (not in H59): {len(only_h67)}")

# What are the H67-only matches? Home team is fav, away leading
print(f"\n  H67-only matches = away FAVOURITE leading (home is underdog)")
print(f"  These are NOT covered by H59.")

print("\n" + "="*60)
print("ALL BACKTESTS COMPLETE")
print("="*60)
