"""
Re-evaluate H62 and H68 with current dataset (1168+ matches).
H62: BACK Draw After UD Equalizer Late
H68: BACK Draw at 2-2 Late
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
    cumulative = peak = max_dd = 0
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

def stats_block(bets, label=""):
    if not bets:
        return {"n": 0}
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins / n * 100
    total_pl = sum(b["pl"] for b in bets)
    avg_odds = sum(b["odds"] for b in bets) / n
    roi = total_pl / (n * STAKE) * 100
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    leagues = set(b.get("league", "?") for b in bets)
    return {
        "n": n, "wins": wins, "wr": round(wr, 1),
        "avg_odds": round(avg_odds, 2),
        "roi": round(roi, 1), "pl": round(total_pl, 2),
        "ci95_lo": ci_lo, "ci95_hi": ci_hi,
        "max_dd": max_drawdown(pls), "sharpe": sharpe_ratio(pls),
        "leagues": len(leagues), "league_list": sorted(leagues),
    }

def train_test(bets, ratio=0.7):
    s = sorted(bets, key=lambda b: b.get("timestamp", ""))
    idx = int(len(s) * ratio)
    return s[:idx], s[idx:]

# ====================================================================
# H62: BACK Draw After UD Equalizer Late
# Underdog equalizes the favourite's lead. BACK Draw.
# Conditions:
#   - min in [min_lo, min_hi]
#   - Score is tied (gl == gv) and at least 1 goal each
#   - At some earlier point in the match, one team was leading
#   - The team that was leading is the favourite (pre-match odds < fav_pre_max)
#   - The equalizer was scored by the underdog
#   - BACK Draw odds from back_draw column
# ====================================================================
def backtest_h62(matches, min_lo, min_hi, fav_pre_max, min_goals_each=1, odds_max=10.0):
    bets = []
    for m in matches:
        rows = m["rows"]
        triggered = False
        for idx, row in enumerate(rows):
            mi = _f(row.get("minuto", ""))
            if mi is None or not (min_lo <= mi <= min_hi):
                continue
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            # Must be tied with at least min_goals_each each
            if gl != gv or gl < min_goals_each:
                continue
            # Check that this is an equalization (previous row had different score)
            # Look back for a row where one team was leading
            was_leading_home = False
            was_leading_away = False
            for prev_row in rows[:idx]:
                pgl = _i(prev_row.get("goles_local", ""))
                pgv = _i(prev_row.get("goles_visitante", ""))
                if pgl is not None and pgv is not None:
                    if pgl > pgv:
                        was_leading_home = True
                    if pgv > pgl:
                        was_leading_away = True

            if not (was_leading_home or was_leading_away):
                continue  # Never had a lead - was always tied

            # The leading team must be the favourite (lower back odds at start)
            # Get pre-match odds (first row)
            first_row = rows[0]
            back_home_pre = _f(first_row.get("back_home", ""))
            back_away_pre = _f(first_row.get("back_away", ""))
            if back_home_pre is None or back_away_pre is None:
                continue

            # Determine who was the favourite
            fav_is_home = back_home_pre < back_away_pre
            fav_odds_pre = min(back_home_pre, back_away_pre)

            if fav_odds_pre > fav_pre_max:
                continue  # Not a clear favourite

            # The favourite must have been leading at some point, and the underdog equalized
            if fav_is_home and not was_leading_home:
                continue  # Home was fav but never led -> no equalization by underdog
            if not fav_is_home and not was_leading_away:
                continue  # Away was fav but never led -> no equalization by underdog

            # Get draw odds
            draw_odds = _f(row.get("back_draw", ""))
            if draw_odds is None or draw_odds < 1.05 or draw_odds > odds_max:
                continue

            # Bet on draw
            ft_draw = (m["ft_local"] == m["ft_visitante"])
            bet = {
                "match_id": m["match_id"],
                "minuto": mi,
                "odds": draw_odds,
                "won": ft_draw,
                "pl": pl_back(draw_odds, ft_draw),
                "league": m["league"],
                "country": m["country"],
                "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                "ft_local": m["ft_local"],
                "ft_visitante": m["ft_visitante"],
                "score_at_trigger": f"{gl}-{gv}",
                "fav_odds_pre": fav_odds_pre,
                "bet_type": "back",
            }
            bets.append(bet)
            triggered = True
            break  # One bet per match
    return bets

# ====================================================================
# H68: BACK Draw at 2-2 Late
# Score is 2-2, min in range, BACK Draw
# ====================================================================
def backtest_h68(matches, min_lo, min_hi, odds_max=10.0):
    bets = []
    for m in matches:
        rows = m["rows"]
        for idx, row in enumerate(rows):
            mi = _f(row.get("minuto", ""))
            if mi is None or not (min_lo <= mi <= min_hi):
                continue
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            if gl != 2 or gv != 2:
                continue
            draw_odds = _f(row.get("back_draw", ""))
            if draw_odds is None or draw_odds < 1.05 or draw_odds > odds_max:
                continue
            ft_draw = (m["ft_local"] == m["ft_visitante"])
            bet = {
                "match_id": m["match_id"],
                "minuto": mi,
                "odds": draw_odds,
                "won": ft_draw,
                "pl": pl_back(draw_odds, ft_draw),
                "league": m["league"],
                "country": m["country"],
                "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                "ft_local": m["ft_local"],
                "ft_visitante": m["ft_visitante"],
                "bet_type": "back",
            }
            bets.append(bet)
            break
    return bets


def print_results(name, bets):
    s = stats_block(bets)
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    if s["n"] == 0:
        print("  No bets triggered.")
        return s

    train, test = train_test(bets)
    s_train = stats_block(train)
    s_test = stats_block(test)

    print(f"  N={s['n']}, Wins={s['wins']}, WR={s['wr']}%")
    print(f"  Avg Odds={s['avg_odds']}, ROI={s['roi']}%, P/L={s['pl']}")
    print(f"  IC95=[{s['ci95_lo']}%, {s['ci95_hi']}%]")
    print(f"  MaxDD={s['max_dd']}, Sharpe={s['sharpe']}")
    print(f"  Leagues={s['leagues']}")
    print(f"  Train (70%): N={s_train['n']}, WR={s_train['wr']}%, ROI={s_train['roi']}%")
    print(f"  Test  (30%): N={s_test['n']}, WR={s_test['wr']}%, ROI={s_test['roi']}%")

    # Score distribution
    scores = Counter(b["score_at_trigger"] if "score_at_trigger" in b else f"{b['ft_local']}-{b['ft_visitante']}" for b in bets)
    print(f"  Score at trigger: {dict(scores.most_common(10))}")

    # Win rate by won/lost
    won_odds = [b["odds"] for b in bets if b["won"]]
    lost_odds = [b["odds"] for b in bets if not b["won"]]
    if won_odds:
        print(f"  Won bets avg odds: {sum(won_odds)/len(won_odds):.2f}")
    if lost_odds:
        print(f"  Lost bets avg odds: {sum(lost_odds)/len(lost_odds):.2f}")

    return s


def main():
    print("Loading matches...")
    matches = load_matches()
    print(f"Loaded {len(matches)} finished matches")
    n_matches = len(matches)
    min_bets = max(15, n_matches // 25)
    print(f"Quality gate: N >= {min_bets}")

    # ============================================================
    # H62: Grid search
    # ============================================================
    print(f"\n{'#'*60}")
    print(f"  H62: BACK Draw After UD Equalizer Late")
    print(f"{'#'*60}")

    h62_results = []
    for min_lo in [55, 60, 65, 70]:
        for min_hi in [80, 85, 90]:
            for fav_pre_max in [2.0, 2.5, 3.0]:
                for min_goals_each in [1]:
                    for odds_max in [6.0, 8.0, 10.0]:
                        bets = backtest_h62(matches, min_lo, min_hi, fav_pre_max, min_goals_each, odds_max)
                        if len(bets) < 10:
                            continue
                        s = stats_block(bets)
                        train, test = train_test(bets)
                        s_train = stats_block(train)
                        s_test = stats_block(test)
                        h62_results.append({
                            "min_lo": min_lo, "min_hi": min_hi,
                            "fav_pre_max": fav_pre_max,
                            "min_goals_each": min_goals_each,
                            "odds_max": odds_max,
                            **s,
                            "train_roi": s_train["roi"],
                            "test_roi": s_test["roi"],
                            "n_test": s_test["n"],
                            "bets": bets,
                        })

    # Sort by Sharpe
    h62_results.sort(key=lambda x: x["sharpe"], reverse=True)

    print(f"\nTotal configs tested: {len(h62_results)}")
    print(f"\nTop 10 by Sharpe:")
    print(f"{'min':>5} {'max':>5} {'fav':>5} {'omax':>5} | {'N':>4} {'WR':>6} {'ROI':>7} {'Sharpe':>7} | {'TrROI':>7} {'TeROI':>7} {'NTe':>4} | {'IC95lo':>7} {'Lgs':>4}")
    for r in h62_results[:15]:
        print(f"{r['min_lo']:>5} {r['min_hi']:>5} {r['fav_pre_max']:>5.1f} {r['odds_max']:>5.1f} | "
              f"{r['n']:>4} {r['wr']:>5.1f}% {r['roi']:>6.1f}% {r['sharpe']:>7.2f} | "
              f"{r['train_roi']:>6.1f}% {r['test_roi']:>6.1f}% {r['n_test']:>4} | "
              f"{r['ci95_lo']:>6.1f}% {r['leagues']:>4}")

    # Best passing all gates
    print(f"\nConfigs passing quality gates (N>={min_bets}, ROI>=10%, IC95_lo>=40%, train>0, test>0):")
    passing_h62 = [r for r in h62_results
                   if r["n"] >= min_bets
                   and r["roi"] >= 10.0
                   and r["ci95_lo"] >= 40.0
                   and r["train_roi"] > 0
                   and r["test_roi"] > 0]

    for r in passing_h62[:5]:
        print(f"  min=[{r['min_lo']},{r['min_hi']}] fav<={r['fav_pre_max']} omax={r['odds_max']} -> "
              f"N={r['n']}, WR={r['wr']}%, ROI={r['roi']}%, Sharpe={r['sharpe']}, "
              f"Train={r['train_roi']}%, Test={r['test_roi']}%, IC95=[{r['ci95_lo']},{r['ci95_hi']}]")

    if not passing_h62:
        print("  NONE pass all gates")

    # Export best H62 bets for realistic validation
    if passing_h62:
        best_h62 = passing_h62[0]
        export_bets = best_h62["bets"]
        os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auxiliar"), exist_ok=True)
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auxiliar", "sd_bt_h62_bets.json"), "w") as f:
            json.dump(export_bets, f, ensure_ascii=False)
        print(f"\n  Exported {len(export_bets)} bets to auxiliar/sd_bt_h62_bets.json")

    # ============================================================
    # H68: Grid search
    # ============================================================
    print(f"\n{'#'*60}")
    print(f"  H68: BACK Draw at 2-2 Late")
    print(f"{'#'*60}")

    h68_results = []
    for min_lo in [60, 65, 70, 75]:
        for min_hi in [80, 85, 90]:
            for odds_max in [5.0, 6.0, 8.0, 10.0]:
                bets = backtest_h68(matches, min_lo, min_hi, odds_max)
                if len(bets) < 10:
                    continue
                s = stats_block(bets)
                train, test = train_test(bets)
                s_train = stats_block(train)
                s_test = stats_block(test)
                h68_results.append({
                    "min_lo": min_lo, "min_hi": min_hi,
                    "odds_max": odds_max,
                    **s,
                    "train_roi": s_train["roi"],
                    "test_roi": s_test["roi"],
                    "n_test": s_test["n"],
                    "bets": bets,
                })

    h68_results.sort(key=lambda x: x["sharpe"], reverse=True)

    print(f"\nTotal configs tested: {len(h68_results)}")
    print(f"\nTop 10 by Sharpe:")
    print(f"{'min':>5} {'max':>5} {'omax':>5} | {'N':>4} {'WR':>6} {'ROI':>7} {'Sharpe':>7} | {'TrROI':>7} {'TeROI':>7} {'NTe':>4} | {'IC95lo':>7} {'Lgs':>4}")
    for r in h68_results[:15]:
        print(f"{r['min_lo']:>5} {r['min_hi']:>5} {r['odds_max']:>5.1f} | "
              f"{r['n']:>4} {r['wr']:>5.1f}% {r['roi']:>6.1f}% {r['sharpe']:>7.2f} | "
              f"{r['train_roi']:>6.1f}% {r['test_roi']:>6.1f}% {r['n_test']:>4} | "
              f"{r['ci95_lo']:>6.1f}% {r['leagues']:>4}")

    passing_h68 = [r for r in h68_results
                   if r["n"] >= min_bets
                   and r["roi"] >= 10.0
                   and r["ci95_lo"] >= 40.0
                   and r["train_roi"] > 0
                   and r["test_roi"] > 0]

    print(f"\nConfigs passing quality gates (N>={min_bets}, ROI>=10%, IC95_lo>=40%, train>0, test>0):")
    for r in passing_h68[:5]:
        print(f"  min=[{r['min_lo']},{r['min_hi']}] omax={r['odds_max']} -> "
              f"N={r['n']}, WR={r['wr']}%, ROI={r['roi']}%, Sharpe={r['sharpe']}, "
              f"Train={r['train_roi']}%, Test={r['test_roi']}%, IC95=[{r['ci95_lo']},{r['ci95_hi']}]")

    if not passing_h68:
        print("  NONE pass all gates")

    # Export best H68 bets
    if passing_h68:
        best_h68 = passing_h68[0]
        export_bets = best_h68["bets"]
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "auxiliar", "sd_bt_h68_bets.json"), "w") as f:
            json.dump(export_bets, f, ensure_ascii=False)
        print(f"\n  Exported {len(export_bets)} bets to auxiliar/sd_bt_h68_bets.json")

    # ============================================================
    # Summary
    # ============================================================
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Dataset: {n_matches} matches, min_bets threshold: {min_bets}")
    print(f"  H62: {len(passing_h62)} configs pass all gates (of {len(h62_results)} tested)")
    print(f"  H68: {len(passing_h68)} configs pass all gates (of {len(h68_results)} tested)")

    if passing_h62:
        b = passing_h62[0]
        print(f"\n  H62 BEST: min=[{b['min_lo']},{b['min_hi']}], fav<={b['fav_pre_max']}, odds_max={b['odds_max']}")
        print(f"    N={b['n']}, WR={b['wr']}%, ROI={b['roi']}%, Sharpe={b['sharpe']}")
        print(f"    Train={b['train_roi']}%, Test={b['test_roi']}%")

    if passing_h68:
        b = passing_h68[0]
        print(f"\n  H68 BEST: min=[{b['min_lo']},{b['min_hi']}], odds_max={b['odds_max']}")
        print(f"    N={b['n']}, WR={b['wr']}%, ROI={b['roi']}%, Sharpe={b['sharpe']}")
        print(f"    Train={b['train_roi']}%, Test={b['test_roi']}%")


if __name__ == "__main__":
    main()
