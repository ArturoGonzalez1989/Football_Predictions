"""
Re-export H104 bets for the N=57 combo (better sample size).
Combo: min=55-80, xg_max=1.8, score=away_plus1_any, odds=[2.0,10.0]
"""
import os, glob, csv, math, json
from collections import Counter

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
            "country": last.get("Pais", last.get("País", "?")),
            "league": last.get("Liga", "?"),
            "ft_local": gl,
            "ft_visitante": gv,
            "ft_total": gl + gv,
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
    mean_pl = sum(pls) / len(pls)
    var = sum((p - mean_pl) ** 2 for p in pls) / (len(pls) - 1)
    std = math.sqrt(var) if var > 0 else 0.001
    return round(mean_pl / std * math.sqrt(len(pls)), 2)

def pl_lay(odds, won):
    if won:
        return round(STAKE * 0.95, 2)
    else:
        return round(-STAKE * (odds - 1), 2)

def main():
    matches = load_matches()
    n_matches = len(matches)
    print(f"Loaded {n_matches} finished matches")
    min_n = max(15, n_matches // 25)
    print(f"Quality gate N >= {min_n}")

    # Two combos to export: the best by Sharpe and the best by N
    combos_to_test = [
        {"name": "best_sharpe_0-1_only", "minute_min": 55, "minute_max": 75,
         "xg_max": 1.8, "odds_lo": 2.0, "odds_hi": 10.0, "score_filter": "0-1_only"},
        {"name": "robust_away_plus1", "minute_min": 55, "minute_max": 80,
         "xg_max": 1.8, "odds_lo": 2.0, "odds_hi": 10.0, "score_filter": "away_plus1_any"},
        {"name": "wider_window", "minute_min": 45, "minute_max": 80,
         "xg_max": 2.0, "odds_lo": 2.0, "odds_hi": 10.0, "score_filter": "away_plus1_any"},
        {"name": "robust_01_12", "minute_min": 50, "minute_max": 80,
         "xg_max": 2.0, "odds_lo": 2.0, "odds_hi": 10.0, "score_filter": "01_12"},
    ]

    for cfg in combos_to_test:
        bets = []
        for match in matches:
            triggered = False
            for idx, row in enumerate(match["rows"]):
                if triggered:
                    break
                m = _f(row.get("minuto", ""))
                if m is None or not (cfg["minute_min"] <= m <= cfg["minute_max"]):
                    continue
                gl = _i(row.get("goles_local", ""))
                gv = _i(row.get("goles_visitante", ""))
                if gl is None or gv is None:
                    continue
                if gv - gl != 1:
                    continue
                sf = cfg["score_filter"]
                if sf == "0-1_only" and not (gl == 0 and gv == 1):
                    continue
                if sf == "01_12" and not ((gl == 0 and gv == 1) or (gl == 1 and gv == 2)):
                    continue
                xg_l = _f(row.get("xg_local", ""))
                xg_v = _f(row.get("xg_visitante", ""))
                if xg_l is None or xg_v is None:
                    continue
                xg_total = xg_l + xg_v
                if xg_total > cfg["xg_max"]:
                    continue
                odds = _f(row.get("lay_draw", ""))
                if odds is None or odds <= 1.0:
                    continue
                if not (cfg["odds_lo"] <= odds <= cfg["odds_hi"]):
                    continue
                won = match["ft_local"] != match["ft_visitante"]
                bet_pl = pl_lay(odds, won)
                bets.append({
                    "match_id": match["match_id"],
                    "file": match["file"],
                    "league": match["league"],
                    "country": match["country"],
                    "minuto": m,
                    "score_trigger": f"{gl}-{gv}",
                    "xg_total": round(xg_total, 2),
                    "odds": odds,
                    "ft": f"{match['ft_local']}-{match['ft_visitante']}",
                    "ft_total": match["ft_total"],
                    "won": won,
                    "pl": bet_pl,
                    "timestamp": match["timestamp_first"],
                    "bet_type": "lay",
                })
                triggered = True

        if not bets:
            print(f"\n{cfg['name']}: 0 bets")
            continue

        n = len(bets)
        wins = sum(1 for b in bets if b["won"])
        total_pl = sum(b["pl"] for b in bets)
        avg_odds = sum(b["odds"] for b in bets) / n
        roi = total_pl / (n * STAKE) * 100
        ci_lo, ci_hi = wilson_ci95(n, wins)
        pls = [b["pl"] for b in bets]
        leagues = set(b["league"] for b in bets)
        sorted_b = sorted(bets, key=lambda b: b["timestamp"])
        split = int(len(sorted_b) * 0.7)
        train, test = sorted_b[:split], sorted_b[split:]
        train_pl = sum(b["pl"] for b in train)
        test_pl = sum(b["pl"] for b in test)
        train_roi = round(train_pl / (len(train) * STAKE) * 100, 1) if train else 0
        test_roi = round(test_pl / (len(test) * STAKE) * 100, 1) if test else 0

        print(f"\n{'='*60}")
        print(f"{cfg['name']}:")
        print(f"  N={n}, WR={wins/n*100:.1f}%, ROI={roi:.1f}%, Sharpe={sharpe_ratio(pls)}")
        print(f"  CI95=[{ci_lo},{ci_hi}], AvgOdds={avg_odds:.2f}, MaxDD={max_drawdown(pls)}")
        print(f"  Train: N={len(train)}, ROI={train_roi}% | Test: N={len(test)}, ROI={test_roi}%")
        print(f"  Leagues: {len(leagues)}")

        # Gate check
        gates_pass = True
        if n < min_n:
            print(f"  GATE FAIL: N={n} < {min_n}")
            gates_pass = False
        if roi < 10:
            print(f"  GATE FAIL: ROI={roi:.1f}% < 10%")
            gates_pass = False
        if ci_lo < 40:
            print(f"  GATE FAIL: CI95_lo={ci_lo} < 40")
            gates_pass = False
        if train_roi <= 0:
            print(f"  GATE FAIL: Train ROI={train_roi}% <= 0")
            gates_pass = False
        if test_roi <= 0:
            print(f"  GATE FAIL: Test ROI={test_roi}% <= 0")
            gates_pass = False
        if len(leagues) < 3:
            print(f"  GATE FAIL: Leagues={len(leagues)} < 3")
            gates_pass = False

        if gates_pass:
            print(f"  ALL GATES PASS")

        # Score dist
        score_dist = Counter(b["score_trigger"] for b in bets)
        print(f"  Scores: {dict(score_dist.most_common())}")

        # FT dist
        ft_dist = Counter(b["ft"] for b in bets)
        print(f"  FT: {dict(ft_dist.most_common(5))}")

    # Export the robust combo (away_plus1_any, 55-80, xg 1.8)
    print(f"\n{'='*60}")
    print("Exporting robust combo bets...")
    cfg = combos_to_test[1]  # robust_away_plus1
    bets = []
    for match in matches:
        triggered = False
        for idx, row in enumerate(match["rows"]):
            if triggered:
                break
            m = _f(row.get("minuto", ""))
            if m is None or not (cfg["minute_min"] <= m <= cfg["minute_max"]):
                continue
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            if gv - gl != 1:
                continue
            xg_l = _f(row.get("xg_local", ""))
            xg_v = _f(row.get("xg_visitante", ""))
            if xg_l is None or xg_v is None:
                continue
            xg_total = xg_l + xg_v
            if xg_total > cfg["xg_max"]:
                continue
            odds = _f(row.get("lay_draw", ""))
            if odds is None or odds <= 1.0:
                continue
            if not (cfg["odds_lo"] <= odds <= cfg["odds_hi"]):
                continue
            won = match["ft_local"] != match["ft_visitante"]
            bet_pl = pl_lay(odds, won)
            bets.append({
                "match_id": match["match_id"],
                "file": match["file"],
                "league": match["league"],
                "country": match["country"],
                "minuto": m,
                "score_trigger": f"{gl}-{gv}",
                "xg_total": round(xg_total, 2),
                "odds": odds,
                "ft": f"{match['ft_local']}-{match['ft_visitante']}",
                "ft_total": match["ft_total"],
                "won": won,
                "pl": bet_pl,
                "timestamp": match["timestamp_first"],
                "bet_type": "lay",
            })
            triggered = True

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "auxiliar", "sd_bt_h104_bets.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bets, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(bets)} bets to {out_path}")


if __name__ == "__main__":
    main()
