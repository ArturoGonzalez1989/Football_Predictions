"""
R12 Backtest: H74 - BACK Draw at 0-0 Mid-Game (min 55-70)
Edge thesis: At 0-0 around min 60, the market still favours one team to win.
But data shows 39-48% of 0-0 games at min 60 end as draws. If stats show
balanced play (similar xG), the draw is underpriced.

Different from existing Draw strategies:
- H58 = Draw at 1-1 late (70-85)
- H14 = Draw xG convergence (off, ROI insuficiente)
- H24/H30 = Draw after equalizer / stalemate (off)
- H51 = Draw 0-0 away underdog (DESCARTADA)

H74 targets the MID-GAME window (55-70) at 0-0 with balanced stats.
The key insight: at min 55-65, 0-0 games have draw rate ~39-48% but
draw odds are typically 2.4-2.6 (implying ~38-42%). If stats are balanced,
draw probability goes UP (51.3% from exploration data for "balanced" 0-0).
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

def pl_back(odds, won):
    return round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

def wilson_ci95(n, wins):
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0, centre - margin) * 100, 1),
            round(min(1, centre + margin) * 100, 1))

def max_drawdown(pls):
    cum = peak = dd = 0
    for pl in pls:
        cum += pl
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return round(dd, 2)

def sharpe_ratio(pls):
    if len(pls) < 2:
        return 0.0
    mean = sum(pls) / len(pls)
    var = sum((p - mean) ** 2 for p in pls) / (len(pls) - 1)
    std = math.sqrt(var) if var > 0 else 0.001
    return round(mean / std * math.sqrt(len(pls)), 2)

def stats(bets):
    if not bets:
        return {"n": 0}
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    total_pl = sum(b["pl"] for b in bets)
    avg_odds = sum(b["odds"] for b in bets) / n
    roi = total_pl / (n * STAKE) * 100
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    leagues = set(b.get("league", "?") for b in bets)
    sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
    split = int(len(sorted_b) * 0.7)
    train, test = sorted_b[:split], sorted_b[split:]
    train_pl = sum(b["pl"] for b in train)
    test_pl = sum(b["pl"] for b in test)
    train_roi = round(train_pl / (len(train) * STAKE) * 100, 1) if train else 0
    test_roi = round(test_pl / (len(test) * STAKE) * 100, 1) if test else 0
    return {
        "n": n, "wins": wins, "wr_pct": round(wins / n * 100, 1),
        "avg_odds": round(avg_odds, 2), "roi_pct": round(roi, 1),
        "total_pl": round(total_pl, 2), "ci95_lo": ci_lo, "ci95_hi": ci_hi,
        "max_dd": max_drawdown(pls), "sharpe": sharpe_ratio(pls),
        "leagues": len(leagues), "train_roi": train_roi, "test_roi": test_roi,
    }

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
        "match_id": os.path.basename(fpath).replace("partido_", "").replace(".csv", ""),
        "league": last.get("Liga", "?"),
        "ft_local": gl, "ft_visitante": gv, "ft_total": gl + gv,
        "rows": rows,
        "timestamp_first": rows[0].get("timestamp_utc", ""),
    })

print(f"Loaded {len(matches)} matches")

# ============================================================
# H74: BACK Draw at 0-0 Mid-Game (55-70) with balanced stats
# ============================================================
print("\n" + "="*70)
print("H74: BACK Draw at 0-0 Mid-Game")
print("="*70)

grid = []
for min_min, min_max in [(55, 65), (55, 68), (55, 70), (58, 68), (58, 70), (60, 70)]:
    for max_xg_ratio in [2.0, 2.5, 3.0, 99.0]:  # Max ratio between teams' xG
        for max_sot_diff in [2, 3, 4, 99]:  # Max SoT difference between teams
            bets = []
            for m in matches:
                triggered = False
                for r in m["rows"]:
                    if triggered:
                        break
                    mn = _f(r.get("minuto", ""))
                    if mn is None or not (min_min <= mn <= min_max):
                        continue
                    gl = _i(r.get("goles_local", ""))
                    gv = _i(r.get("goles_visitante", ""))
                    if gl is None or gv is None or gl + gv != 0:
                        continue

                    # Balance filters
                    if max_xg_ratio < 90:
                        xgl = _f(r.get("xg_local", ""))
                        xgv = _f(r.get("xg_visitante", ""))
                        if xgl is None or xgv is None:
                            continue
                        min_xg = min(xgl, xgv)
                        max_xg = max(xgl, xgv)
                        if min_xg < 0.05:
                            ratio = 99
                        else:
                            ratio = max_xg / min_xg
                        if ratio > max_xg_ratio:
                            continue

                    if max_sot_diff < 90:
                        sot_l = _f(r.get("tiros_puerta_local", ""))
                        sot_v = _f(r.get("tiros_puerta_visitante", ""))
                        if sot_l is None or sot_v is None:
                            continue
                        if abs(sot_l - sot_v) > max_sot_diff:
                            continue

                    bd = _f(r.get("back_draw", ""))
                    if bd is None or bd < 1.05 or bd > 10.0:
                        continue

                    won = m["ft_local"] == m["ft_visitante"]
                    bets.append({
                        "match_id": m["match_id"],
                        "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
                        "minuto": mn,
                        "odds": bd,
                        "won": won,
                        "pl": pl_back(bd, won),
                        "league": m["league"],
                        "bet_type": "back",
                    })
                    triggered = True

            s = stats(bets)
            if s["n"] >= 30:
                grid.append({
                    "params": f"min={min_min}-{min_max}, xgRatio<={max_xg_ratio}, sotDiff<={max_sot_diff}",
                    **s,
                })

grid.sort(key=lambda x: -x.get("sharpe", 0))
print(f"\nGrid results ({len(grid)} configs with N>=30):")
for r in grid[:15]:
    print(f"  {r['params']}: N={r['n']}, WR={r['wr_pct']}%, ROI={r['roi_pct']}%, "
          f"Sharpe={r['sharpe']}, TrainROI={r['train_roi']}%, TestROI={r['test_roi']}%, "
          f"AvgOdds={r['avg_odds']}, CI95=[{r['ci95_lo']},{r['ci95_hi']}]")

# ============================================================
# H75: BACK Under 1.5 at 0-0 Late (min 70-80)
# Exploration showed: 87% hold rate vs 71.9% implied = +15.1pp edge
# Different from H44 (LAY Over 1.5) which is the SAME market direction
# but H47 was descartada for being redundant with H44.
# SKIP - already descartada as H47
# ============================================================

# ============================================================
# H75 (alternative): BACK CS Portfolio Extended (all tight scores at 80+)
# From exploration: CS hold rates at min 80 show universal edge
# H49 covers 2-1/1-2, H53 covers 1-0/0-1
# What about 0-0, 1-1, 2-0, 0-2 as a CS bet?
# ============================================================
print("\n" + "="*70)
print("H75: BACK CS 0-0 at min 78-88 (Very Late)")
print("="*70)
# NOTE: H56 was descartada (test ROI=-14.7%)
# But let's check with narrower window and more data (896 vs 850)

grid75 = []
for min_min, min_max in [(76, 85), (78, 85), (78, 88), (80, 88), (80, 90)]:
    for max_odds in [3.0, 4.0, 5.0, 8.0]:
        bets = []
        for m in matches:
            triggered = False
            for r in m["rows"]:
                if triggered:
                    break
                mn = _f(r.get("minuto", ""))
                if mn is None or not (min_min <= mn <= min_max):
                    continue
                gl = _i(r.get("goles_local", ""))
                gv = _i(r.get("goles_visitante", ""))
                if gl is None or gv is None or gl != 0 or gv != 0:
                    continue

                cs_odds = _f(r.get("back_rc_0_0", ""))
                if cs_odds is None or cs_odds < 1.05 or cs_odds > max_odds:
                    continue

                won = m["ft_local"] == 0 and m["ft_visitante"] == 0
                bets.append({
                    "match_id": m["match_id"],
                    "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
                    "minuto": mn,
                    "odds": cs_odds,
                    "won": won,
                    "pl": pl_back(cs_odds, won),
                    "league": m["league"],
                    "bet_type": "back",
                })
                triggered = True

        s = stats(bets)
        if s["n"] >= 20:
            grid75.append({
                "params": f"min={min_min}-{min_max}, maxOdds={max_odds}",
                **s,
            })

grid75.sort(key=lambda x: -x.get("sharpe", 0))
print(f"\nGrid results ({len(grid75)} configs with N>=20):")
for r in grid75[:10]:
    print(f"  {r['params']}: N={r['n']}, WR={r['wr_pct']}%, ROI={r['roi_pct']}%, "
          f"Sharpe={r['sharpe']}, TrainROI={r['train_roi']}%, TestROI={r['test_roi']}%, "
          f"AvgOdds={r['avg_odds']}, CI95=[{r['ci95_lo']},{r['ci95_hi']}]")

# ============================================================
# H76: BACK Home Favourite Leading by 2+ at 55-70 (Early Confirmation)
# Different from H70 which is 65-85 with any lead
# This targets the "early secure lead" - fav already 2+ up before 70'
# ============================================================
print("\n" + "="*70)
print("H76: BACK Home Fav Leading by 2+ Early (55-70)")
print("="*70)

grid76 = []
for min_min, min_max in [(50, 65), (50, 70), (55, 65), (55, 70)]:
    for fav_max in [1.80, 2.00, 2.50]:
        bets = []
        for m in matches:
            r0 = m["rows"][0]
            bh0 = _f(r0.get("back_home", ""))
            ba0 = _f(r0.get("back_away", ""))
            if bh0 is None or ba0 is None or bh0 >= ba0 or bh0 > fav_max:
                continue
            triggered = False
            for r in m["rows"]:
                if triggered:
                    break
                mn = _f(r.get("minuto", ""))
                if mn is None or not (min_min <= mn <= min_max):
                    continue
                gl = _i(r.get("goles_local", ""))
                gv = _i(r.get("goles_visitante", ""))
                if gl is None or gv is None:
                    continue
                if gl - gv < 2:
                    continue

                bh = _f(r.get("back_home", ""))
                if bh is None or bh < 1.05 or bh > 10.0:
                    continue
                won = m["ft_local"] > m["ft_visitante"]
                bets.append({
                    "match_id": m["match_id"],
                    "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
                    "minuto": mn,
                    "odds": bh,
                    "won": won,
                    "pl": pl_back(bh, won),
                    "league": m["league"],
                    "bet_type": "back",
                })
                triggered = True

        s = stats(bets)
        if s["n"] >= 15:
            grid76.append({
                "params": f"min={min_min}-{min_max}, favMax={fav_max}",
                **s,
            })

grid76.sort(key=lambda x: -x.get("sharpe", 0))
print(f"\nGrid results ({len(grid76)} configs with N>=15):")
for r in grid76[:10]:
    print(f"  {r['params']}: N={r['n']}, WR={r['wr_pct']}%, ROI={r['roi_pct']}%, "
          f"Sharpe={r['sharpe']}, TrainROI={r['train_roi']}%, TestROI={r['test_roi']}%, "
          f"AvgOdds={r['avg_odds']}, CI95=[{r['ci95_lo']},{r['ci95_hi']}]")

print("\nDone.")
