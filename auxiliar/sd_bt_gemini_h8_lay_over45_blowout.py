"""
Backtest: H8 - LAY Over 4.5 in Blowouts (Gemini analisis2.md)
Score is 3-0 or 0-3 at min 60-75. After the 3rd goal, SoT drops.
LAY Over 4.5 (bet that total goals <= 4).

Overlap check: lay_over45_v3 triggers on goals<=2, so 3-0/0-3 is EXCLUDED from that strategy.
This is a complementary strategy for a different score regime.
"""
import os, glob, csv, math, json, itertools
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
            "ft_local": gl,
            "ft_visitante": gv,
            "ft_total": gl + gv,
            "rows": rows,
            "timestamp_first": rows[0].get("timestamp_utc", ""),
        })
    return matches

def run_backtest(matches, m_trigger_min, m_trigger_max, post_goal_window, max_sot_post,
                 odds_max, include_31=False, require_sot_filter=True):
    """
    Strategy: When score reaches 3-0/0-3 (optionally 3-1/1-3) at m_trigger_min-m_trigger_max,
    wait post_goal_window minutes. If total SoT increase <= max_sot_post in that window,
    LAY Over 4.5.

    Win condition: FT total goals <= 4.
    """
    bets = []
    for match in matches:
        triggered = False
        rows = match["rows"]

        # Find when score first reaches 3-0/0-3 (or 3-1/1-3)
        third_goal_minute = None
        third_goal_idx = None
        score_at_3rd = None
        sot_at_3rd_l = None
        sot_at_3rd_v = None

        prev_total = 0
        for idx, row in enumerate(rows):
            m = _f(row.get("minuto", ""))
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if gl is None or gv is None or m is None:
                continue

            total = gl + gv

            # Check if we just reached a qualifying score
            valid_score = False
            if (gl == 3 and gv == 0) or (gl == 0 and gv == 3):
                valid_score = True
            if include_31 and ((gl == 3 and gv == 1) or (gl == 1 and gv == 3)):
                valid_score = True

            if valid_score and total > prev_total and third_goal_minute is None:
                if m_trigger_min <= m <= m_trigger_max:
                    third_goal_minute = m
                    third_goal_idx = idx
                    score_at_3rd = f"{gl}-{gv}"
                    sot_at_3rd_l = _i(row.get("tiros_puerta_local", ""))
                    sot_at_3rd_v = _i(row.get("tiros_puerta_visitante", ""))

            prev_total = total

        if third_goal_minute is None:
            continue

        # Now find the row at third_goal_minute + post_goal_window
        entry_row = None
        entry_idx = None
        for idx in range(third_goal_idx, len(rows)):
            row = rows[idx]
            m = _f(row.get("minuto", ""))
            if m is None:
                continue
            if m >= third_goal_minute + post_goal_window:
                entry_row = row
                entry_idx = idx
                break

        if entry_row is None:
            continue

        # Check SoT increase in the post-goal window
        if require_sot_filter:
            sot_now_l = _i(entry_row.get("tiros_puerta_local", ""))
            sot_now_v = _i(entry_row.get("tiros_puerta_visitante", ""))

            if sot_at_3rd_l is not None and sot_at_3rd_v is not None and \
               sot_now_l is not None and sot_now_v is not None:
                sot_delta = (sot_now_l + sot_now_v) - (sot_at_3rd_l + sot_at_3rd_v)
                if sot_delta > max_sot_post:
                    continue
            elif require_sot_filter:
                # SoT data not available, skip if we require it
                # Try without filter instead
                pass

        # Get LAY Over 4.5 odds
        lay_odds = _f(entry_row.get("lay_over45", ""))
        if lay_odds is None or lay_odds <= 1.0 or lay_odds > odds_max:
            continue

        # Check score hasn't changed further
        gl_now = _i(entry_row.get("goles_local", ""))
        gv_now = _i(entry_row.get("goles_visitante", ""))
        if gl_now is None or gv_now is None:
            continue
        total_now = gl_now + gv_now

        entry_m = _f(entry_row.get("minuto", ""))

        # Win condition: FT total goals <= 4
        won = match["ft_total"] <= 4

        # LAY P/L: win = STAKE * 0.95, loss = -(STAKE * (lay_odds - 1))
        if won:
            pl = round(STAKE * 0.95, 2)
        else:
            pl = round(-(STAKE * (lay_odds - 1)), 2)

        bets.append({
            "match_id": match["match_id"],
            "minuto": entry_m,
            "odds": lay_odds,
            "won": won,
            "pl": pl,
            "score_at_3rd_goal": score_at_3rd,
            "score_at_entry": f"{gl_now}-{gv_now}",
            "third_goal_min": third_goal_minute,
            "ft": f"{match['ft_local']}-{match['ft_visitante']}",
            "ft_total": match["ft_total"],
            "league": match.get("league", "?"),
            "timestamp": match.get("timestamp_first", ""),
            "bet_type_dir": "lay",
        })

    return bets

def eval_bets(bets, label=""):
    if not bets:
        print(f"  {label}: N=0")
        return None
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins / n * 100
    total_pl = sum(b["pl"] for b in bets)
    roi = total_pl / (n * STAKE) * 100
    avg_odds = sum(b["odds"] for b in bets) / n
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    leagues = set(b.get("league", "?") for b in bets)
    md = max_drawdown(pls)
    sr = sharpe_ratio(pls)

    print(f"  {label}: N={n}, Wins={wins}, WR={wr:.1f}%, ROI={roi:.1f}%, "
          f"P/L={total_pl:.2f}, AvgOdds={avg_odds:.2f}, "
          f"IC95=[{ci_lo}, {ci_hi}], MaxDD={md}, Sharpe={sr}, Leagues={len(leagues)}")
    return {
        "n": n, "wins": wins, "wr": wr, "roi": roi, "pl": total_pl,
        "avg_odds": avg_odds, "ci_lo": ci_lo, "ci_hi": ci_hi,
        "max_dd": md, "sharpe": sr, "leagues": len(leagues),
        "league_list": sorted(leagues),
    }

def main():
    print("Loading matches...")
    matches = load_matches()
    print(f"Loaded {len(matches)} finished matches")
    n_matches = len(matches)
    g_min = max(15, n_matches // 25)
    print(f"Quality gate N minimum: {g_min}")

    print("\n=== H8: LAY Over 4.5 in Blowouts (3-0 / 0-3) ===")
    print("Grid search across multiple parameters\n")

    # PHASE 1: Broad search WITHOUT SoT filter (more data)
    print("--- PHASE 1: Without SoT filter (broadest universe) ---")
    results = []
    for m_min, m_max in [(45, 70), (50, 68), (55, 70), (55, 75), (60, 75), (45, 75)]:
        for post_window in [0, 5, 8, 10]:
            for odds_max in [3.0, 5.0, 8.0, 15.0]:
                for include_31 in [False, True]:
                    bets = run_backtest(matches, m_min, m_max, post_window, 99,
                                       odds_max, include_31=include_31, require_sot_filter=False)
                    if len(bets) >= 10:
                        n = len(bets)
                        wins = sum(1 for b in bets if b["won"])
                        wr = wins / n * 100
                        total_pl = sum(b["pl"] for b in bets)
                        roi = total_pl / (n * STAKE) * 100
                        avg_odds = sum(b["odds"] for b in bets) / n
                        ci_lo, ci_hi = wilson_ci95(n, wins)
                        pls = [b["pl"] for b in bets]
                        leagues = len(set(b.get("league", "?") for b in bets))

                        results.append({
                            "m_min": m_min, "m_max": m_max,
                            "post_window": post_window, "max_sot": 99,
                            "odds_max": odds_max, "include_31": include_31,
                            "sot_filter": False,
                            "N": n, "wins": wins, "wr": wr, "roi": roi,
                            "pl": total_pl, "avg_odds": avg_odds,
                            "ci_lo": ci_lo, "ci_hi": ci_hi, "leagues": leagues,
                            "sharpe": sharpe_ratio(pls), "max_dd": max_drawdown(pls),
                        })

    # Sort by ROI, filter N >= g_min
    viable = [r for r in results if r["N"] >= g_min]
    viable.sort(key=lambda x: -x["roi"])

    print(f"Total combos with N>=10: {len(results)}")
    print(f"Combos with N>={g_min}: {len(viable)}")

    if viable:
        print(f"\nTop 15 viable combos (N>={g_min}) by ROI:")
        print(f"{'m_rng':>8} {'pw':>3} {'odds<':>6} {'31?':>4} | {'N':>4} {'W':>4} {'WR%':>6} {'ROI%':>7} {'AvgOdd':>7} {'IC95lo':>7} {'Shrp':>5} {'Lgs':>4}")
        print("-" * 85)
        for r in viable[:15]:
            rng = f"{r['m_min']}-{r['m_max']}"
            print(f"{rng:>8} {r['post_window']:>3} {r['odds_max']:>5.1f} {'Y' if r['include_31'] else 'N':>4} | "
                  f"{r['N']:>4} {r['wins']:>4} {r['wr']:>5.1f}% {r['roi']:>6.1f}% {r['avg_odds']:>7.2f} {r['ci_lo']:>6.1f}% {r['sharpe']:>5.2f} {r['leagues']:>4}")

    # PHASE 2: WITH SoT filter on best minute ranges
    print("\n--- PHASE 2: With SoT filter ---")
    results2 = []
    for m_min, m_max in [(45, 70), (50, 68), (55, 75), (45, 75)]:
        for post_window in [5, 8, 10]:
            for max_sot in [0, 1, 2]:
                for odds_max in [3.0, 5.0, 8.0, 15.0]:
                    for include_31 in [False, True]:
                        bets = run_backtest(matches, m_min, m_max, post_window, max_sot,
                                           odds_max, include_31=include_31, require_sot_filter=True)
                        if len(bets) >= 10:
                            n = len(bets)
                            wins = sum(1 for b in bets if b["won"])
                            wr = wins / n * 100
                            total_pl = sum(b["pl"] for b in bets)
                            roi = total_pl / (n * STAKE) * 100
                            avg_odds = sum(b["odds"] for b in bets) / n
                            ci_lo, ci_hi = wilson_ci95(n, wins)
                            pls = [b["pl"] for b in bets]
                            leagues = len(set(b.get("league", "?") for b in bets))

                            results2.append({
                                "m_min": m_min, "m_max": m_max,
                                "post_window": post_window, "max_sot": max_sot,
                                "odds_max": odds_max, "include_31": include_31,
                                "sot_filter": True,
                                "N": n, "wins": wins, "wr": wr, "roi": roi,
                                "pl": total_pl, "avg_odds": avg_odds,
                                "ci_lo": ci_lo, "ci_hi": ci_hi, "leagues": leagues,
                                "sharpe": sharpe_ratio(pls), "max_dd": max_drawdown(pls),
                            })

    viable2 = [r for r in results2 if r["N"] >= g_min]
    viable2.sort(key=lambda x: -x["roi"])

    print(f"Total combos with N>=10: {len(results2)}")
    print(f"Combos with N>={g_min}: {len(viable2)}")

    if viable2:
        print(f"\nTop 10 viable combos with SoT filter:")
        print(f"{'m_rng':>8} {'pw':>3} {'sot<':>5} {'odds<':>6} {'31?':>4} | {'N':>4} {'W':>4} {'WR%':>6} {'ROI%':>7} {'AvgOdd':>7} {'IC95lo':>7} {'Shrp':>5} {'Lgs':>4}")
        print("-" * 90)
        for r in viable2[:10]:
            rng = f"{r['m_min']}-{r['m_max']}"
            print(f"{rng:>8} {r['post_window']:>3} {r['max_sot']:>5} {r['odds_max']:>5.1f} {'Y' if r['include_31'] else 'N':>4} | "
                  f"{r['N']:>4} {r['wins']:>4} {r['wr']:>5.1f}% {r['roi']:>6.1f}% {r['avg_odds']:>7.2f} {r['ci_lo']:>6.1f}% {r['sharpe']:>5.2f} {r['leagues']:>4}")

    # PHASE 3: Detailed analysis of best combo
    all_results = results + results2
    all_viable = [r for r in all_results if r["N"] >= g_min and r["roi"] > 0]
    if all_viable:
        all_viable.sort(key=lambda x: -x["sharpe"])
        best = all_viable[0]
        print(f"\n=== BEST COMBO (by Sharpe) ===")
        print(f"  Params: m=[{best['m_min']},{best['m_max']}], post_window={best['post_window']}, "
              f"max_sot={'no filter' if best['max_sot'] == 99 else best['max_sot']}, "
              f"odds_max={best['odds_max']}, include_31={best['include_31']}")
        print(f"  N={best['N']}, WR={best['wr']:.1f}%, ROI={best['roi']:.1f}%, "
              f"Sharpe={best['sharpe']:.2f}, MaxDD={best['max_dd']:.2f}, Leagues={best['leagues']}")

        # Rerun to get detailed bets
        bets = run_backtest(matches, best['m_min'], best['m_max'],
                           best['post_window'], best.get('max_sot', 99),
                           best['odds_max'], include_31=best['include_31'],
                           require_sot_filter=best.get('sot_filter', False))

        print(f"\n  Score at 3rd goal distribution:")
        scores = Counter(b["score_at_3rd_goal"] for b in bets)
        for s, c in scores.most_common():
            w = sum(1 for b in bets if b["score_at_3rd_goal"] == s and b["won"])
            print(f"    {s}: {c} bets, {w} wins ({w/c*100:.0f}%)")

        print(f"\n  FT distribution:")
        fts = Counter(b["ft"] for b in bets)
        for ft, c in fts.most_common(10):
            print(f"    {ft}: {c} matches")

        print(f"\n  League distribution:")
        lgs = Counter(b["league"] for b in bets)
        for lg, c in lgs.most_common(10):
            print(f"    {lg}: {c}")

        # Train/test split
        sorted_bets = sorted(bets, key=lambda b: b.get("timestamp", ""))
        split = int(len(sorted_bets) * 0.7)
        train = sorted_bets[:split]
        test = sorted_bets[split:]

        print(f"\n  Train/Test split (70/30 chronological):")
        eval_bets(train, "TRAIN")
        eval_bets(test, "TEST")

        # Quality gates
        print(f"\n  Quality Gates:")
        print(f"    G1: N >= {g_min}: {'PASS' if best['N'] >= g_min else 'FAIL'} ({best['N']})")
        print(f"    G2: ROI >= 10%: {'PASS' if best['roi'] >= 10 else 'FAIL'} ({best['roi']:.1f}%)")
        print(f"    G3: IC95_lo >= 40%: {'PASS' if best['ci_lo'] >= 40 else 'FAIL'} ({best['ci_lo']}%)")

        train_wins = sum(1 for b in train if b["won"]) if train else 0
        train_roi = sum(b["pl"] for b in train) / (len(train) * STAKE) * 100 if train else 0
        test_wins = sum(1 for b in test if b["won"]) if test else 0
        test_roi = sum(b["pl"] for b in test) / (len(test) * STAKE) * 100 if test else 0

        print(f"    G4: Train ROI > 0%: {'PASS' if train_roi > 0 else 'FAIL'} ({train_roi:.1f}%)")
        print(f"    G5: Test ROI > 0%: {'PASS' if test_roi > 0 else 'FAIL'} ({test_roi:.1f}%)")
        print(f"    G6: Leagues >= 3: {'PASS' if best['leagues'] >= 3 else 'FAIL'} ({best['leagues']})")

        # Export bets for realistic validator
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "sd_bt_gemini_h8_bets.json")
        with open(out_path, "w") as f:
            json.dump(bets, f, ensure_ascii=False, indent=2)
        print(f"\n  Bets exported to: {out_path}")

    # Also check the simple "back under 4.5 at 3-0" approach (no waiting)
    print("\n\n=== ALTERNATIVE: Simple BACK Under 4.5 at 3-0/0-3 (immediate entry) ===")
    for m_min, m_max in [(50, 75), (55, 72), (45, 75)]:
        for odds_max in [2.0, 3.0, 5.0]:
            bets_simple = []
            for match in matches:
                triggered = False
                for idx, row in enumerate(match["rows"]):
                    if triggered:
                        break
                    m = _f(row.get("minuto", ""))
                    gl = _i(row.get("goles_local", ""))
                    gv = _i(row.get("goles_visitante", ""))
                    if m is None or gl is None or gv is None:
                        continue
                    if not (m_min <= m <= m_max):
                        continue
                    if (gl == 3 and gv == 0) or (gl == 0 and gv == 3):
                        odds = _f(row.get("back_under45", ""))
                        if odds and odds > 1.0 and odds <= odds_max:
                            won = match["ft_total"] <= 4
                            pl = round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE
                            bets_simple.append({
                                "match_id": match["match_id"],
                                "minuto": m,
                                "odds": odds,
                                "won": won,
                                "pl": pl,
                                "league": match.get("league", "?"),
                            })
                            triggered = True

            if len(bets_simple) >= 10:
                n = len(bets_simple)
                wins = sum(1 for b in bets_simple if b["won"])
                wr = wins / n * 100
                total_pl = sum(b["pl"] for b in bets_simple)
                roi = total_pl / (n * STAKE) * 100
                avg_odds = sum(b["odds"] for b in bets_simple) / n
                ci_lo, _ = wilson_ci95(n, wins)
                print(f"  m=[{m_min},{m_max}] odds<{odds_max}: N={n}, WR={wr:.1f}%, ROI={roi:.1f}%, AvgOdds={avg_odds:.2f}, IC95lo={ci_lo}%")

if __name__ == "__main__":
    main()
