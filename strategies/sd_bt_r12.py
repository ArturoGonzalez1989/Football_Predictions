"""
R12 Backtest: 4 hypotheses
H70: BACK Home Favourite Leading Late (MO home, 65-80')
H71: BACK Under 4.5 Three Goals Low xG (65-80')
H72: BACK Over 0.5 Scoreless at HT (min 46-55)
H73: BACK CS 3-1/1-3 Late Lock (min 70-85)
"""
import os, glob, csv, math, json
from collections import defaultdict, Counter

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
            "ft_local": gl, "ft_visitante": gv, "ft_total": gl + gv,
            "rows": rows,
            "timestamp_first": rows[0].get("timestamp_utc", ""),
        })
    return matches

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

def pl_back(odds, won):
    return round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

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

    # train/test
    sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
    split = int(len(sorted_b) * 0.7)
    train, test = sorted_b[:split], sorted_b[split:]
    train_pl = sum(b["pl"] for b in train)
    test_pl = sum(b["pl"] for b in test)
    train_roi = round(train_pl / (len(train) * STAKE) * 100, 1) if train else 0
    test_roi = round(test_pl / (len(test) * STAKE) * 100, 1) if test else 0

    return {
        "n": n, "wins": wins,
        "wr_pct": round(wins / n * 100, 1),
        "avg_odds": round(avg_odds, 2),
        "roi_pct": round(roi, 1),
        "total_pl": round(total_pl, 2),
        "ci95_lo": ci_lo, "ci95_hi": ci_hi,
        "max_dd": max_drawdown(pls),
        "sharpe": sharpe_ratio(pls),
        "leagues": len(leagues),
        "league_list": sorted(leagues),
        "train_roi": train_roi,
        "test_roi": test_roi,
        "n_train": len(train),
        "n_test": len(test),
    }

matches = load_matches()
print(f"Loaded {len(matches)} matches")

# ============================================================
# H70: BACK Home Favourite Leading Late
# ============================================================
print("\n" + "="*70)
print("H70: BACK Home Favourite Leading Late")
print("="*70)

h70_grid = []
for min_min, min_max in [(60, 80), (65, 80), (65, 85), (70, 85)]:
    for max_lead in [1, 2, 3]:
        for fav_max in [1.80, 2.00, 2.50]:
            bets = []
            for m in matches:
                # Check home was favourite at KO
                r0 = m["rows"][0]
                bh0 = _f(r0.get("back_home", ""))
                ba0 = _f(r0.get("back_away", ""))
                if bh0 is None or ba0 is None or bh0 >= ba0:
                    continue
                if bh0 > fav_max:
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
                    lead = gl - gv
                    if lead < 1 or lead > max_lead:
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
            if s["n"] >= 30:
                h70_grid.append({
                    "params": f"min={min_min}-{min_max}, maxLead={max_lead}, favMax={fav_max}",
                    **s,
                })

h70_grid.sort(key=lambda x: -x.get("sharpe", 0))
print(f"\nGrid results ({len(h70_grid)} configs with N>=30):")
for r in h70_grid[:10]:
    print(f"  {r['params']}: N={r['n']}, WR={r['wr_pct']}%, ROI={r['roi_pct']}%, "
          f"Sharpe={r['sharpe']}, TrainROI={r['train_roi']}%, TestROI={r['test_roi']}%, "
          f"AvgOdds={r['avg_odds']}, CI95=[{r['ci95_lo']},{r['ci95_hi']}], Leagues={r['leagues']}")

# Export best H70 bets for validator
if h70_grid:
    best = h70_grid[0]
    # Re-run best config to get bets
    best_params = best["params"]
    print(f"\n  BEST: {best_params}")

# ============================================================
# H71: BACK Under 4.5 Three Goals Low xG
# ============================================================
print("\n" + "="*70)
print("H71: BACK Under 4.5 Three Goals Low xG")
print("="*70)

h71_grid = []
for min_min, min_max in [(60, 80), (65, 80), (65, 85), (70, 85)]:
    for max_xg in [2.0, 2.5, 3.0, 99.0]:
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
                if gl is None or gv is None:
                    continue
                if gl + gv != 3:
                    continue

                # xG filter
                if max_xg < 90:
                    xgl = _f(r.get("xg_local", ""))
                    xgv = _f(r.get("xg_visitante", ""))
                    if xgl is None or xgv is None:
                        continue
                    if xgl + xgv > max_xg:
                        continue

                u45 = _f(r.get("back_under45", ""))
                if u45 is None or u45 < 1.05 or u45 > 10.0:
                    continue

                won = m["ft_total"] <= 4
                bets.append({
                    "match_id": m["match_id"],
                    "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
                    "minuto": mn,
                    "odds": u45,
                    "won": won,
                    "pl": pl_back(u45, won),
                    "league": m["league"],
                    "bet_type": "back",
                })
                triggered = True

        s = stats(bets)
        if s["n"] >= 20:
            h71_grid.append({
                "params": f"min={min_min}-{min_max}, maxXG={max_xg}",
                **s,
            })

h71_grid.sort(key=lambda x: -x.get("sharpe", 0))
print(f"\nGrid results ({len(h71_grid)} configs with N>=20):")
for r in h71_grid[:10]:
    print(f"  {r['params']}: N={r['n']}, WR={r['wr_pct']}%, ROI={r['roi_pct']}%, "
          f"Sharpe={r['sharpe']}, TrainROI={r['train_roi']}%, TestROI={r['test_roi']}%, "
          f"AvgOdds={r['avg_odds']}, CI95=[{r['ci95_lo']},{r['ci95_hi']}], Leagues={r['leagues']}")

# ============================================================
# H72: BACK Over 0.5 Scoreless at HT
# ============================================================
print("\n" + "="*70)
print("H72: BACK Over 0.5 Scoreless at HT (min 46-58)")
print("="*70)

h72_grid = []
for min_min, min_max in [(46, 55), (46, 58), (48, 55), (48, 58), (50, 58)]:
    for min_sot in [0, 2, 3, 4]:
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

                # SoT filter
                if min_sot > 0:
                    sot_l = _f(r.get("tiros_puerta_local", ""))
                    sot_v = _f(r.get("tiros_puerta_visitante", ""))
                    if sot_l is None or sot_v is None:
                        continue
                    if sot_l + sot_v < min_sot:
                        continue

                o05 = _f(r.get("back_over05", ""))
                if o05 is None or o05 < 1.05 or o05 > 10.0:
                    continue

                won = m["ft_total"] >= 1
                bets.append({
                    "match_id": m["match_id"],
                    "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
                    "minuto": mn,
                    "odds": o05,
                    "won": won,
                    "pl": pl_back(o05, won),
                    "league": m["league"],
                    "bet_type": "back",
                })
                triggered = True

        s = stats(bets)
        if s["n"] >= 30:
            h72_grid.append({
                "params": f"min={min_min}-{min_max}, minSoT={min_sot}",
                **s,
            })

h72_grid.sort(key=lambda x: -x.get("sharpe", 0))
print(f"\nGrid results ({len(h72_grid)} configs with N>=30):")
for r in h72_grid[:10]:
    print(f"  {r['params']}: N={r['n']}, WR={r['wr_pct']}%, ROI={r['roi_pct']}%, "
          f"Sharpe={r['sharpe']}, TrainROI={r['train_roi']}%, TestROI={r['test_roi']}%, "
          f"AvgOdds={r['avg_odds']}, CI95=[{r['ci95_lo']},{r['ci95_hi']}], Leagues={r['leagues']}")

# ============================================================
# H73: BACK CS 3-1/1-3 Late Lock
# ============================================================
print("\n" + "="*70)
print("H73: BACK CS 3-1/1-3 Late Lock (min 70-85)")
print("="*70)

h73_grid = []
for min_min, min_max in [(65, 80), (68, 82), (70, 85), (72, 85), (75, 85)]:
    for max_odds in [5.0, 8.0, 15.0]:
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
                if gl is None or gv is None:
                    continue
                if not ((gl == 3 and gv == 1) or (gl == 1 and gv == 3)):
                    continue

                cs_col = f"back_rc_{gl}_{gv}"
                cs_odds = _f(r.get(cs_col, ""))
                if cs_odds is None or cs_odds < 1.05 or cs_odds > max_odds:
                    continue

                won = m["ft_local"] == gl and m["ft_visitante"] == gv
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
        if s["n"] >= 10:
            h73_grid.append({
                "params": f"min={min_min}-{min_max}, maxOdds={max_odds}",
                **s,
            })

h73_grid.sort(key=lambda x: -x.get("sharpe", 0))
print(f"\nGrid results ({len(h73_grid)} configs with N>=10):")
for r in h73_grid[:10]:
    print(f"  {r['params']}: N={r['n']}, WR={r['wr_pct']}%, ROI={r['roi_pct']}%, "
          f"Sharpe={r['sharpe']}, TrainROI={r['train_roi']}%, TestROI={r['test_roi']}%, "
          f"AvgOdds={r['avg_odds']}, CI95=[{r['ci95_lo']},{r['ci95_hi']}], Leagues={r['leagues']}")

# ============================================================
# EXPORT BEST BETS FOR VALIDATOR
# ============================================================
print("\n" + "="*70)
print("EXPORTING BEST CONFIGS FOR REALISTIC VALIDATION")
print("="*70)

def export_bets(hypothesis, bets_fn, params_desc):
    """Re-run and export bets as JSON for validator."""
    bets = bets_fn()
    if not bets:
        print(f"  {hypothesis}: No bets generated")
        return
    outpath = os.path.join(os.path.dirname(__file__), f"sd_bt_{hypothesis.lower()}_bets.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({"hypothesis": hypothesis, "params": params_desc, "bets": bets}, f, ensure_ascii=False, indent=2)
    print(f"  {hypothesis}: {len(bets)} bets -> {outpath}")

# H70 best: re-run with best params
def gen_h70():
    bets = []
    for m in matches:
        r0 = m["rows"][0]
        bh0 = _f(r0.get("back_home", ""))
        ba0 = _f(r0.get("back_away", ""))
        if bh0 is None or ba0 is None or bh0 >= ba0:
            continue
        if bh0 > 2.00:
            continue
        triggered = False
        for r in m["rows"]:
            if triggered:
                break
            mn = _f(r.get("minuto", ""))
            if mn is None or not (65 <= mn <= 80):
                continue
            gl = _i(r.get("goles_local", ""))
            gv = _i(r.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            if gl - gv < 1 or gl - gv > 2:
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
    return bets

def gen_h71():
    bets = []
    for m in matches:
        triggered = False
        for r in m["rows"]:
            if triggered:
                break
            mn = _f(r.get("minuto", ""))
            if mn is None or not (65 <= mn <= 80):
                continue
            gl = _i(r.get("goles_local", ""))
            gv = _i(r.get("goles_visitante", ""))
            if gl is None or gv is None or gl + gv != 3:
                continue
            xgl = _f(r.get("xg_local", ""))
            xgv = _f(r.get("xg_visitante", ""))
            if xgl is None or xgv is None or xgl + xgv > 2.5:
                continue
            u45 = _f(r.get("back_under45", ""))
            if u45 is None or u45 < 1.05 or u45 > 10.0:
                continue
            won = m["ft_total"] <= 4
            bets.append({
                "match_id": m["match_id"],
                "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
                "minuto": mn,
                "odds": u45,
                "won": won,
                "pl": pl_back(u45, won),
                "league": m["league"],
                "bet_type": "back",
            })
            triggered = True
    return bets

def gen_h72():
    bets = []
    for m in matches:
        triggered = False
        for r in m["rows"]:
            if triggered:
                break
            mn = _f(r.get("minuto", ""))
            if mn is None or not (46 <= mn <= 55):
                continue
            gl = _i(r.get("goles_local", ""))
            gv = _i(r.get("goles_visitante", ""))
            if gl is None or gv is None or gl + gv != 0:
                continue
            sot_l = _f(r.get("tiros_puerta_local", ""))
            sot_v = _f(r.get("tiros_puerta_visitante", ""))
            if sot_l is None or sot_v is None or sot_l + sot_v < 2:
                continue
            o05 = _f(r.get("back_over05", ""))
            if o05 is None or o05 < 1.05 or o05 > 10.0:
                continue
            won = m["ft_total"] >= 1
            bets.append({
                "match_id": m["match_id"],
                "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
                "minuto": mn,
                "odds": o05,
                "won": won,
                "pl": pl_back(o05, won),
                "league": m["league"],
                "bet_type": "back",
            })
            triggered = True
    return bets

def gen_h73():
    bets = []
    for m in matches:
        triggered = False
        for r in m["rows"]:
            if triggered:
                break
            mn = _f(r.get("minuto", ""))
            if mn is None or not (70 <= mn <= 85):
                continue
            gl = _i(r.get("goles_local", ""))
            gv = _i(r.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            if not ((gl == 3 and gv == 1) or (gl == 1 and gv == 3)):
                continue
            cs_col = f"back_rc_{gl}_{gv}"
            cs_odds = _f(r.get(cs_col, ""))
            if cs_odds is None or cs_odds < 1.05 or cs_odds > 8.0:
                continue
            won = m["ft_local"] == gl and m["ft_visitante"] == gv
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
    return bets

export_bets("H70", gen_h70, "min=65-80, maxLead=2, favMax=2.00")
export_bets("H71", gen_h71, "min=65-80, maxXG=2.5")
export_bets("H72", gen_h72, "min=46-55, minSoT=2")
export_bets("H73", gen_h73, "min=70-85, maxOdds=8.0")

print("\nDone. Run sd_validate_realistic.py on each *_bets.json file.")
