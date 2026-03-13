"""
Backtest: H105 — BACK Home Match Odds when home leading by 1 + low xG (late game)
Validates whether home+1 late with low xG is a profitable BACK Home signal,
and measures overlap with existing home_fav_leading strategy.
"""
import os, glob, csv, math, json, sys
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
    cumulative = 0
    peak = 0
    max_dd = 0
    for pl in pls:
        cumulative += pl
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)
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

def check_home_fav_leading(rows, cfg=None):
    """Simulate _detect_home_fav_leading_trigger to find if match triggers it."""
    if cfg is None:
        cfg = {"m_min": 60, "m_max": 83, "max_lead": 1, "fav_max": 2.5}
    m_min = float(cfg.get("m_min", 60))
    m_max = float(cfg.get("m_max", 83))
    max_lead = int(cfg.get("max_lead", 1))
    fav_max = float(cfg.get("fav_max", 2.5))

    first_home = None
    first_away = None
    for r in rows[:5]:
        bh = _f(r.get("back_home", ""))
        ba = _f(r.get("back_away", ""))
        if bh and ba and bh > 1 and ba > 1:
            first_home = bh
            first_away = ba
            break
    if first_home is None or first_away is None:
        return False
    if first_home >= first_away:
        return False  # home NOT favourite
    if first_home > fav_max:
        return False

    for row in rows:
        m = _f(row.get("minuto", ""))
        if m is None or not (m_min <= m <= m_max):
            continue
        gl = _i(row.get("goles_local", ""))
        gv = _i(row.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        if gl <= gv:
            continue
        lead = gl - gv
        if lead > max_lead:
            continue
        odds = _f(row.get("back_home", ""))
        if odds is None or odds <= 1.0 or odds > 10:
            continue
        return True
    return False

def run_backtest(matches, min_min, min_max, xg_thresh, min_dur=1):
    """Run H105 backtest with given params."""
    bets = []
    for match in matches:
        rows = match["rows"]
        triggered = False
        for idx, row in enumerate(rows):
            m = _f(row.get("minuto", ""))
            if m is None or not (min_min <= m <= min_max):
                continue
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            if gl - gv != 1:
                continue

            # xG filter (None means no filter)
            if xg_thresh is not None:
                xg_l = _f(row.get("xg_local", ""))
                xg_v = _f(row.get("xg_visitante", ""))
                if xg_l is None or xg_v is None:
                    continue
                if xg_l + xg_v >= xg_thresh:
                    continue

            # Get entry odds (with min_dur)
            entry_idx = min(idx + min_dur - 1, len(rows) - 1)
            entry_row = rows[entry_idx]
            odds = _f(entry_row.get("back_home", ""))
            if odds is None or odds <= 1.0 or odds > 10:
                continue

            won = match["ft_local"] > match["ft_visitante"]
            bets.append({
                "match_id": match["match_id"],
                "file": match["file"],
                "minuto": m,
                "odds": odds,
                "won": won,
                "pl": pl_back(odds, won),
                "league": match["league"],
                "country": match["country"],
                "timestamp": match["timestamp_first"],
                "ft_local": match["ft_local"],
                "ft_visitante": match["ft_visitante"],
                "gl_at_trigger": gl,
                "gv_at_trigger": gv,
            })
            triggered = True
            break  # 1 bet per match
    return bets

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
    }

def train_test_split(bets, train_ratio=0.7):
    sorted_bets = sorted(bets, key=lambda b: b.get("timestamp", ""))
    split_idx = int(len(sorted_bets) * train_ratio)
    return sorted_bets[:split_idx], sorted_bets[split_idx:]

def main():
    print("Loading matches...")
    matches = load_matches()
    n_matches = len(matches)
    print(f"Loaded {n_matches} finished matches")
    gate_n = max(15, n_matches // 25)
    print(f"Gate N >= {gate_n}")

    # Grid search
    minute_ranges = [
        (60, 80), (60, 85), (65, 80), (65, 85), (65, 90), (70, 90)
    ]
    xg_thresholds = [None, 1.5, 1.8, 2.0, 2.5]

    results = []
    for (min_min, min_max) in minute_ranges:
        for xg_thresh in xg_thresholds:
            bets = run_backtest(matches, min_min, min_max, xg_thresh)
            s = stats(bets)
            if s["n"] == 0:
                continue
            train, test = train_test_split(bets)
            s_train = stats(train)
            s_test = stats(test)

            label = f"min[{min_min}-{min_max}] xg<{xg_thresh if xg_thresh else 'none'}"
            results.append({
                "label": label,
                "min_min": min_min,
                "min_max": min_max,
                "xg_thresh": xg_thresh,
                "bets": bets,
                **s,
                "train_n": s_train["n"],
                "train_wr": s_train.get("wr_pct", 0),
                "train_roi": s_train.get("roi_pct", 0),
                "test_n": s_test["n"],
                "test_wr": s_test.get("wr_pct", 0),
                "test_roi": s_test.get("roi_pct", 0),
            })

    # Sort by Sharpe
    results.sort(key=lambda x: x.get("sharpe", 0), reverse=True)

    print("\n" + "=" * 120)
    print("GRID SEARCH RESULTS")
    print("=" * 120)
    print(f"{'Combo':<35} {'N':>4} {'WR%':>6} {'ROI%':>7} {'P/L':>8} {'AvgOdds':>8} {'MaxDD':>7} {'Sharpe':>7} {'CI95lo':>7} {'Lgs':>4} {'TrROI':>7} {'TeROI':>7} {'Pass':>5}")
    print("-" * 120)

    passing = []
    for r in results:
        n_pass = r["n"] >= gate_n
        roi_pass = r["roi_pct"] >= 10
        ci_pass = r["ci95_lo"] >= 40
        train_pass = r["train_roi"] > 0
        test_pass = r["test_roi"] > 0
        all_pass = n_pass and roi_pass and ci_pass and train_pass and test_pass

        flags = []
        if not n_pass: flags.append("N")
        if not roi_pass: flags.append("ROI")
        if not ci_pass: flags.append("CI")
        if not train_pass: flags.append("TR")
        if not test_pass: flags.append("TE")

        status = "PASS" if all_pass else ",".join(flags)

        print(f"{r['label']:<35} {r['n']:>4} {r['wr_pct']:>6.1f} {r['roi_pct']:>7.1f} {r['total_pl']:>8.1f} {r['avg_odds']:>8.2f} {r['max_dd']:>7.1f} {r['sharpe']:>7.2f} {r['ci95_lo']:>7.1f} {r['leagues']:>4} {r['train_roi']:>7.1f} {r['test_roi']:>7.1f} {status:>5}")

        if all_pass:
            passing.append(r)

    # ============================
    # OVERLAP ANALYSIS
    # ============================
    print("\n" + "=" * 80)
    print("OVERLAP ANALYSIS vs home_fav_leading")
    print("=" * 80)

    # Use the best passing combo (or best overall if none pass)
    best = passing[0] if passing else results[0]
    print(f"\nAnalyzing overlap for best combo: {best['label']}")

    h105_match_ids = set(b["match_id"] for b in best["bets"])
    hfl_match_ids = set()

    hfl_cfg = {"m_min": 60, "m_max": 83, "max_lead": 1, "fav_max": 2.5}
    for match in matches:
        if check_home_fav_leading(match["rows"], hfl_cfg):
            hfl_match_ids.add(match["match_id"])

    overlap = h105_match_ids & hfl_match_ids
    h105_only = h105_match_ids - hfl_match_ids
    hfl_only = hfl_match_ids - h105_match_ids

    overlap_pct = len(overlap) / len(h105_match_ids) * 100 if h105_match_ids else 0

    print(f"H105 triggers: {len(h105_match_ids)}")
    print(f"home_fav_leading triggers: {len(hfl_match_ids)}")
    print(f"Overlap (both trigger): {len(overlap)} ({overlap_pct:.1f}% of H105)")
    print(f"H105 only (unique): {len(h105_only)}")
    print(f"home_fav_leading only: {len(hfl_only)}")

    # Analyze unique H105 bets (not in home_fav_leading)
    unique_bets = [b for b in best["bets"] if b["match_id"] not in hfl_match_ids]
    overlap_bets = [b for b in best["bets"] if b["match_id"] in hfl_match_ids]

    if unique_bets:
        s_unique = stats(unique_bets)
        print(f"\nH105 UNIQUE bets (not in home_fav_leading): N={s_unique['n']}, WR={s_unique['wr_pct']}%, ROI={s_unique['roi_pct']}%, Sharpe={s_unique['sharpe']}")
    if overlap_bets:
        s_overlap = stats(overlap_bets)
        print(f"H105 OVERLAP bets (also in home_fav_leading): N={s_overlap['n']}, WR={s_overlap['wr_pct']}%, ROI={s_overlap['roi_pct']}%, Sharpe={s_overlap['sharpe']}")

    # Export bets for realistic validation
    if passing:
        best_passing = passing[0]
        export_bets = []
        for b in best_passing["bets"]:
            export_bets.append({
                "match_id": b["match_id"],
                "file": b["file"],
                "minuto": b["minuto"],
                "odds": b["odds"],
                "won": b["won"],
                "pl": b["pl"],
                "league": b["league"],
                "country": b["country"],
                "timestamp": b["timestamp"],
            })
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auxiliar", "sd_bt_h105_bets.json")
        with open(out_path, "w") as f:
            json.dump(export_bets, f, ensure_ascii=False)
        print(f"\nExported {len(export_bets)} bets to {out_path}")

    # ============================
    # SUMMARY
    # ============================
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total combos tested: {len(results)}")
    print(f"Combos passing all gates: {len(passing)}")
    print(f"Overlap with home_fav_leading: {overlap_pct:.1f}%")

    if overlap_pct >= 30:
        print("\n*** OVERLAP >= 30% — H105 is REDUNDANT with home_fav_leading ***")
        print("VERDICT: REJECT (redundant)")
    elif not passing:
        print("\n*** No combos pass all quality gates ***")
        print("VERDICT: REJECT (quality gates)")
    else:
        print(f"\nBest passing combo: {passing[0]['label']}")
        print(f"  N={passing[0]['n']}, WR={passing[0]['wr_pct']}%, ROI={passing[0]['roi_pct']}%")
        print(f"  Sharpe={passing[0]['sharpe']}, CI95=[{passing[0]['ci95_lo']}, {passing[0]['ci95_hi']}]")
        print(f"  Train ROI={passing[0]['train_roi']}%, Test ROI={passing[0]['test_roi']}%")
        print(f"  Overlap={overlap_pct:.1f}%")
        print("VERDICT: CANDIDATE — run realistic validation next")

if __name__ == "__main__":
    main()
