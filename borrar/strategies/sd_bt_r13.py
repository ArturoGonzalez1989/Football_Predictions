"""
Round 13 Backtests - Focus areas:
H77: BACK CS 1-1 Late (CS market, NOT Draw market -- different from H58)
H78: BACK Over 3.5 First-Half Activity (2+ goals by min 35-45)
H79: BACK CS 2-0/0-2 Late (revisit H55 with wider grid and new data)
H80: BACK Home Leading FH (min 25-45, extension of leader portfolio to first half)
H81: LAY Home Undeserved Lead FH (home leads 1-0 but away dominates stats)

Discarded pre-backtest:
- CS 3-1: N=22 superset, below N<50 threshold
- CS 2-2: N=25 superset, below N<50 threshold
- BACK Over 1.5 at 0-0 FH: H28 already descartada (O1.5 market too efficient)
- Underdog leads FH: ROI=6.2% max, below 10% threshold
- Home fav trailing 0-1 FH: N=51 but WR=27.5%, dead angle confirmed
- Odds drift FH: N=34 and no signal (29.4% home win rate = market correct)
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

def pl_lay(lay_odds, won):
    return round(STAKE * 0.95, 2) if won else round(-(STAKE * (lay_odds - 1)), 2)

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
            "country": last.get("País", "?"),
            "league": last.get("Liga", "?"),
            "ft_local": gl, "ft_visitante": gv, "ft_total": gl + gv,
            "rows": rows,
            "timestamp_first": rows[0].get("timestamp_utc", ""),
        })
    return matches

def stats_report(bets, label=""):
    if not bets:
        print(f"  {label}: N=0")
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

    # Train/test
    sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
    split = int(n * 0.7)
    train, test = sorted_b[:split], sorted_b[split:]
    train_pl = sum(b["pl"] for b in train)
    test_pl = sum(b["pl"] for b in test)
    train_roi = round(train_pl / (len(train) * STAKE) * 100, 1) if train else 0
    test_roi = round(test_pl / (len(test) * STAKE) * 100, 1) if test else 0

    md = max_drawdown(pls)
    sh = sharpe_ratio(pls)

    print(f"  {label}: N={n}, WR={wr:.1f}%, ROI={roi:.1f}%, P/L={total_pl:.2f}, "
          f"avg_odds={avg_odds:.2f}, IC95=[{ci_lo},{ci_hi}], MaxDD={md}, Sharpe={sh}, "
          f"Leagues={len(leagues)}, Train={train_roi}%, Test={test_roi}%")

    return {
        "n": n, "wins": wins, "wr": round(wr, 1), "roi": round(roi, 1),
        "pl": round(total_pl, 2), "avg_odds": round(avg_odds, 2),
        "ci95_lo": ci_lo, "ci95_hi": ci_hi, "max_dd": md, "sharpe": sh,
        "leagues": len(leagues), "league_list": sorted(leagues),
        "train_roi": train_roi, "test_roi": test_roi,
        "n_train": len(train), "n_test": len(test),
    }


print("Loading matches...")
matches = load_matches()
print(f"Loaded {len(matches)} matches\n")


# ====================================================================
# H77: BACK CS 1-1 Late
# ====================================================================
print("=" * 70)
print("H77: BACK CS 1-1 Late")
print("Different from H58 (Draw 1-1): this uses CS market (back_rc_1_1)")
print("CS market has higher odds -> higher ROI potential")
print("=" * 70)

best_h77 = None
best_h77_bets = None

for min_lo in [55, 60, 65, 70, 75]:
    for min_hi in [min_lo + 10, min_lo + 15]:
        if min_hi > 90:
            continue
        for odds_max in [5.0, 8.0, 10.0, 15.0]:
            bets = []
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
                    if cs_odds is None or cs_odds < 1.05 or cs_odds > odds_max:
                        continue
                    if not triggered:
                        triggered = True
                        won = m["ft_local"] == 1 and m["ft_visitante"] == 1
                        bets.append({
                            "match_id": m["match_id"],
                            "won": won,
                            "pl": pl_back(cs_odds, won),
                            "odds": cs_odds,
                            "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                            "minuto": mi,
                            "league": m["league"],
                            "bet_type": "back",
                        })
                        break

            if len(bets) < 50:
                continue

            n = len(bets)
            wins = sum(1 for b in bets if b["won"])
            total_pl = sum(b["pl"] for b in bets)
            roi = total_pl / (n * STAKE) * 100
            wr = wins / n * 100
            ci_lo, _ = wilson_ci95(n, wins)

            # Quick train/test
            sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
            split = int(n * 0.7)
            train_pl = sum(b["pl"] for b in sorted_b[:split])
            test_pl = sum(b["pl"] for b in sorted_b[split:])
            train_roi = train_pl / (split * STAKE) * 100 if split > 0 else 0
            test_roi = test_pl / ((n - split) * STAKE) * 100 if (n - split) > 0 else 0

            if roi > 10 and train_roi > 0 and test_roi > 0 and ci_lo >= 30:
                sh = sharpe_ratio([b["pl"] for b in bets])
                print(f"  min={min_lo}-{min_hi}, odds_max={odds_max}: N={n}, WR={wr:.1f}%, "
                      f"ROI={roi:.1f}%, IC95_lo={ci_lo}%, Sharpe={sh}, "
                      f"Train={train_roi:.1f}%, Test={test_roi:.1f}%")
                if best_h77 is None or sh > best_h77["sharpe"]:
                    best_h77 = {"min_lo": min_lo, "min_hi": min_hi, "odds_max": odds_max,
                                "n": n, "wr": round(wr, 1), "roi": round(roi, 1),
                                "sharpe": sh, "train_roi": round(train_roi, 1),
                                "test_roi": round(test_roi, 1), "ci_lo": ci_lo}
                    best_h77_bets = bets

if best_h77:
    print(f"\n  BEST H77: {best_h77}")
    stats_report(best_h77_bets, "H77 BEST")
else:
    print("  No configs pass thresholds")


# ====================================================================
# H78: BACK Over 3.5 First-Half Activity
# ====================================================================
print("\n" + "=" * 70)
print("H78: BACK Over 3.5 - Already 2+ goals by first half")
print("Market: back_over35")
print("Edge thesis: When 2+ goals scored early, market still underprices O3.5")
print("=" * 70)

best_h78 = None
best_h78_bets = None

for min_lo in [25, 30, 35]:
    for min_hi in [40, 45, 50, 55]:
        for min_goals in [2, 3]:
            for odds_max in [3.0, 4.0, 5.0, 8.0]:
                bets = []
                for m in matches:
                    triggered = False
                    for row in m["rows"]:
                        mi = _f(row.get("minuto", ""))
                        if mi is None or mi < min_lo or mi > min_hi:
                            continue
                        gl = _i(row.get("goles_local", ""))
                        gv = _i(row.get("goles_visitante", ""))
                        if gl is None or gv is None:
                            continue
                        total = gl + gv
                        if total < min_goals:
                            continue
                        bo35 = _f(row.get("back_over35", ""))
                        if bo35 is None or bo35 < 1.05 or bo35 > odds_max:
                            continue
                        if not triggered:
                            triggered = True
                            won = m["ft_total"] >= 4
                            bets.append({
                                "match_id": m["match_id"],
                                "won": won,
                                "pl": pl_back(bo35, won),
                                "odds": bo35,
                                "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                                "minuto": mi,
                                "league": m["league"],
                                "bet_type": "back",
                                "goals_at_trigger": total,
                            })
                            break

                if len(bets) < 50:
                    continue

                n = len(bets)
                wins = sum(1 for b in bets if b["won"])
                total_pl = sum(b["pl"] for b in bets)
                roi = total_pl / (n * STAKE) * 100
                wr = wins / n * 100
                ci_lo, _ = wilson_ci95(n, wins)

                sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
                split = int(n * 0.7)
                train_pl = sum(b["pl"] for b in sorted_b[:split])
                test_pl = sum(b["pl"] for b in sorted_b[split:])
                train_roi = train_pl / (split * STAKE) * 100 if split > 0 else 0
                test_roi = test_pl / ((n - split) * STAKE) * 100 if (n - split) > 0 else 0

                if roi > 5 and train_roi > 0 and test_roi > 0:
                    sh = sharpe_ratio([b["pl"] for b in bets])
                    print(f"  min={min_lo}-{min_hi}, goals>={min_goals}, odds_max={odds_max}: "
                          f"N={n}, WR={wr:.1f}%, ROI={roi:.1f}%, IC95_lo={ci_lo}%, "
                          f"Sharpe={sh}, Train={train_roi:.1f}%, Test={test_roi:.1f}%")
                    if best_h78 is None or sh > best_h78["sharpe"]:
                        best_h78 = {"min_lo": min_lo, "min_hi": min_hi,
                                    "min_goals": min_goals, "odds_max": odds_max,
                                    "n": n, "wr": round(wr, 1), "roi": round(roi, 1),
                                    "sharpe": sh}
                        best_h78_bets = bets

if best_h78:
    print(f"\n  BEST H78: {best_h78}")
    stats_report(best_h78_bets, "H78 BEST")
else:
    print("  No configs pass thresholds")


# ====================================================================
# H79: BACK CS 2-0 Late (revisit H55 with wider grid)
# ====================================================================
print("\n" + "=" * 70)
print("H79: BACK CS 2-0/0-2 Late (revisit H55 with new data)")
print("H55 was monitoring with N=105, IC95_lo=32%. Check if 927 matches helps.")
print("=" * 70)

best_h79 = None
best_h79_bets = None

for min_lo in [55, 60, 65, 70, 75]:
    for min_hi in [min_lo + 10, min_lo + 15]:
        if min_hi > 90:
            continue
        for odds_max in [5.0, 8.0, 10.0, 15.0]:
            for both_dirs in [True]:  # 2-0 AND 0-2
                bets = []
                for m in matches:
                    triggered = False
                    for row in m["rows"]:
                        mi = _f(row.get("minuto", ""))
                        if mi is None or mi < min_lo or mi > min_hi:
                            continue
                        gl = _i(row.get("goles_local", ""))
                        gv = _i(row.get("goles_visitante", ""))
                        if gl is None or gv is None:
                            continue

                        cs_col = None
                        ft_match = False
                        if gl == 2 and gv == 0:
                            cs_col = "back_rc_2_0"
                            ft_match = m["ft_local"] == 2 and m["ft_visitante"] == 0
                        elif gl == 0 and gv == 2 and both_dirs:
                            cs_col = "back_rc_0_2"
                            ft_match = m["ft_local"] == 0 and m["ft_visitante"] == 2
                        else:
                            continue

                        cs_odds = _f(row.get(cs_col, ""))
                        if cs_odds is None or cs_odds < 1.05 or cs_odds > odds_max:
                            continue

                        if not triggered:
                            triggered = True
                            bets.append({
                                "match_id": m["match_id"],
                                "won": ft_match,
                                "pl": pl_back(cs_odds, ft_match),
                                "odds": cs_odds,
                                "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                                "minuto": mi,
                                "league": m["league"],
                                "bet_type": "back",
                                "score": f"{gl}-{gv}",
                            })
                            break

                if len(bets) < 50:
                    continue

                n = len(bets)
                wins = sum(1 for b in bets if b["won"])
                total_pl = sum(b["pl"] for b in bets)
                roi = total_pl / (n * STAKE) * 100
                wr = wins / n * 100
                ci_lo, _ = wilson_ci95(n, wins)

                sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
                split = int(n * 0.7)
                train_pl = sum(b["pl"] for b in sorted_b[:split])
                test_pl = sum(b["pl"] for b in sorted_b[split:])
                train_roi = train_pl / (split * STAKE) * 100 if split > 0 else 0
                test_roi = test_pl / ((n - split) * STAKE) * 100 if (n - split) > 0 else 0

                if roi > 10 and train_roi > 0 and test_roi > 0:
                    sh = sharpe_ratio([b["pl"] for b in bets])
                    print(f"  min={min_lo}-{min_hi}, odds_max={odds_max}: N={n}, WR={wr:.1f}%, "
                          f"ROI={roi:.1f}%, IC95_lo={ci_lo}%, Sharpe={sh}, "
                          f"Train={train_roi:.1f}%, Test={test_roi:.1f}%")
                    if best_h79 is None or sh > best_h79["sharpe"]:
                        best_h79 = {"min_lo": min_lo, "min_hi": min_hi, "odds_max": odds_max,
                                    "n": n, "wr": round(wr, 1), "roi": round(roi, 1),
                                    "sharpe": sh}
                        best_h79_bets = bets

if best_h79:
    print(f"\n  BEST H79: {best_h79}")
    stats_report(best_h79_bets, "H79 BEST")
else:
    print("  No configs pass thresholds")


# ====================================================================
# H80: BACK Home Leading First Half
# ====================================================================
print("\n" + "=" * 70)
print("H80: BACK Home Leading FH (min 25-45)")
print("Extension of leader portfolio to first half")
print("=" * 70)

best_h80 = None
best_h80_bets = None

for min_lo in [25, 30, 35]:
    for min_hi in [40, 42, 45]:
        for margin_min in [1, 2]:
            for odds_max in [2.0, 3.0, 4.0, 5.0]:
                for fav_only in [True, False]:
                    bets = []
                    for m in matches:
                        # Get pre-match odds for fav filter
                        pre_home = None
                        for r in m["rows"][:5]:
                            ph = _f(r.get("back_home", ""))
                            if ph and ph > 1.0:
                                pre_home = ph
                                break

                        if fav_only and (pre_home is None or pre_home >= 2.5):
                            continue

                        triggered = False
                        for row in m["rows"]:
                            mi = _f(row.get("minuto", ""))
                            if mi is None or mi < min_lo or mi > min_hi:
                                continue
                            gl = _i(row.get("goles_local", ""))
                            gv = _i(row.get("goles_visitante", ""))
                            if gl is None or gv is None:
                                continue
                            if gl - gv < margin_min:
                                continue
                            bh = _f(row.get("back_home", ""))
                            if bh is None or bh < 1.05 or bh > odds_max:
                                continue

                            if not triggered:
                                triggered = True
                                won = m["ft_local"] > m["ft_visitante"]
                                bets.append({
                                    "match_id": m["match_id"],
                                    "won": won,
                                    "pl": pl_back(bh, won),
                                    "odds": bh,
                                    "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                                    "minuto": mi,
                                    "league": m["league"],
                                    "bet_type": "back",
                                })
                                break

                    if len(bets) < 50:
                        continue

                    n = len(bets)
                    wins = sum(1 for b in bets if b["won"])
                    total_pl = sum(b["pl"] for b in bets)
                    roi = total_pl / (n * STAKE) * 100
                    wr = wins / n * 100
                    ci_lo, _ = wilson_ci95(n, wins)

                    sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
                    split = int(n * 0.7)
                    train_pl = sum(b["pl"] for b in sorted_b[:split])
                    test_pl = sum(b["pl"] for b in sorted_b[split:])
                    train_roi = train_pl / (split * STAKE) * 100 if split > 0 else 0
                    test_roi = test_pl / ((n - split) * STAKE) * 100 if (n - split) > 0 else 0

                    if roi > 5 and train_roi > 0 and test_roi > 0:
                        sh = sharpe_ratio([b["pl"] for b in bets])
                        fav_str = "fav_only" if fav_only else "all"
                        print(f"  min={min_lo}-{min_hi}, margin>={margin_min}, odds_max={odds_max}, "
                              f"{fav_str}: N={n}, WR={wr:.1f}%, ROI={roi:.1f}%, "
                              f"IC95_lo={ci_lo}%, Sharpe={sh}, "
                              f"Train={train_roi:.1f}%, Test={test_roi:.1f}%")
                        if best_h80 is None or sh > best_h80["sharpe"]:
                            best_h80 = {"min_lo": min_lo, "min_hi": min_hi,
                                        "margin_min": margin_min, "odds_max": odds_max,
                                        "fav_only": fav_only,
                                        "n": n, "wr": round(wr, 1), "roi": round(roi, 1),
                                        "sharpe": sh}
                            best_h80_bets = bets

if best_h80:
    print(f"\n  BEST H80: {best_h80}")
    stats_report(best_h80_bets, "H80 BEST")
else:
    print("  No configs pass thresholds")


# ====================================================================
# H81: LAY Home Undeserved Lead FH -- already saw N=5, too few. SKIP.
# Instead: BACK CS 3-1/1-3 + 2-0/0-2 combined (broader CS portfolio)
# ====================================================================
print("\n" + "=" * 70)
print("H81: BACK CS Big-Lead Hold (3-1/1-3 combined with other leads)")
print("Extend CS portfolio to asymmetric scorelines")
print("=" * 70)

# Check all 2-goal lead CS at min 65-85
for scorelines in [
    [(3, 1), (1, 3)],
    [(2, 0), (0, 2), (3, 1), (1, 3)],
    [(3, 0), (0, 3), (3, 1), (1, 3)],
]:
    label = "+".join(f"{a}-{b}" for a, b in scorelines)

    for min_lo in [60, 65, 70, 75]:
        for min_hi in [min_lo + 10, min_lo + 15]:
            if min_hi > 90:
                continue
            for odds_max in [5.0, 8.0, 10.0, 15.0]:
                bets = []
                for m in matches:
                    triggered = False
                    for row in m["rows"]:
                        mi = _f(row.get("minuto", ""))
                        if mi is None or mi < min_lo or mi > min_hi:
                            continue
                        gl = _i(row.get("goles_local", ""))
                        gv = _i(row.get("goles_visitante", ""))
                        if gl is None or gv is None:
                            continue

                        matched_score = None
                        for sl, sv in scorelines:
                            if gl == sl and gv == sv:
                                matched_score = (sl, sv)
                                break
                        if matched_score is None:
                            continue

                        cs_col = f"back_rc_{matched_score[0]}_{matched_score[1]}"
                        cs_odds = _f(row.get(cs_col, ""))
                        if cs_odds is None or cs_odds < 1.05 or cs_odds > odds_max:
                            continue

                        if not triggered:
                            triggered = True
                            ft_match = m["ft_local"] == matched_score[0] and m["ft_visitante"] == matched_score[1]
                            bets.append({
                                "match_id": m["match_id"],
                                "won": ft_match,
                                "pl": pl_back(cs_odds, ft_match),
                                "odds": cs_odds,
                                "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                                "minuto": mi,
                                "league": m["league"],
                                "bet_type": "back",
                                "score": f"{matched_score[0]}-{matched_score[1]}",
                            })
                            break

                if len(bets) < 30:
                    continue

                n = len(bets)
                wins = sum(1 for b in bets if b["won"])
                total_pl = sum(b["pl"] for b in bets)
                roi = total_pl / (n * STAKE) * 100
                wr = wins / n * 100

                sorted_b = sorted(bets, key=lambda b: b.get("timestamp", ""))
                split = int(n * 0.7)
                train_pl = sum(b["pl"] for b in sorted_b[:split])
                test_pl = sum(b["pl"] for b in sorted_b[split:])
                train_roi = train_pl / (split * STAKE) * 100 if split > 0 else 0
                test_roi = test_pl / ((n - split) * STAKE) * 100 if (n - split) > 0 else 0

                if roi > 10 and train_roi > 0 and test_roi > 0:
                    sh = sharpe_ratio([b["pl"] for b in bets])
                    ci_lo, _ = wilson_ci95(n, wins)
                    print(f"  {label} min={min_lo}-{min_hi}, odds_max={odds_max}: N={n}, "
                          f"WR={wr:.1f}%, ROI={roi:.1f}%, IC95_lo={ci_lo}%, Sharpe={sh}, "
                          f"Train={train_roi:.1f}%, Test={test_roi:.1f}%")

# ====================================================================
# Export best bets for realistic validation
# ====================================================================
print("\n" + "=" * 70)
print("EXPORTING BEST BETS FOR REALISTIC VALIDATION")
print("=" * 70)

for name, bets_list in [("h77", best_h77_bets), ("h78", best_h78_bets),
                         ("h79", best_h79_bets), ("h80", best_h80_bets)]:
    if bets_list:
        outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "aux", f"sd_bt_{name}_bets.json")
        os.makedirs(os.path.dirname(outpath), exist_ok=True)
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump({"bets": bets_list}, f, ensure_ascii=False, indent=2)
        print(f"  Exported {name}: {len(bets_list)} bets -> {outpath}")
    else:
        print(f"  {name}: No bets to export (no passing config)")

print("\nBacktest complete.")
