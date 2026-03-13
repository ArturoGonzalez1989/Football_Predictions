"""
Backtest: H4 - Reverse Favourite-Longshot Bias (Gemini analisis2.md)
Underdog scores to take lead at min 72-88, pre-match fav < 1.60, underdog > 5.0.
BACK underdog match winner.

Expected small universe -- this is a feasibility check.
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

        # Get pre-match odds
        pre_home = None
        pre_away = None
        for r in rows[:10]:
            if r.get("estado_partido", "") == "pre_partido":
                h = _f(r.get("back_home", ""))
                a = _f(r.get("back_away", ""))
                if h and a and h > 1 and a > 1:
                    pre_home = h
                    pre_away = a
        # Also try first in-play rows if no pre-match
        if pre_home is None:
            for r in rows[:15]:
                h = _f(r.get("back_home", ""))
                a = _f(r.get("back_away", ""))
                if h and a and h > 1 and a > 1:
                    pre_home = h
                    pre_away = a
                    break

        matches.append({
            "file": os.path.basename(fpath),
            "match_id": os.path.basename(fpath).replace("partido_", "").replace(".csv", ""),
            "country": last.get("País", "?"),
            "league": last.get("Liga", "?"),
            "ft_local": gl,
            "ft_visitante": gv,
            "ft_total": gl + gv,
            "rows": rows,
            "pre_home": pre_home,
            "pre_away": pre_away,
            "timestamp_first": rows[0].get("timestamp_utc", ""),
        })
    return matches

def run_backtest(matches, m_min, m_max, fav_pre_max, ud_pre_min):
    bets = []
    for match in matches:
        pre_home = match["pre_home"]
        pre_away = match["pre_away"]
        if pre_home is None or pre_away is None:
            continue

        fav_odds = min(pre_home, pre_away)
        ud_odds = max(pre_home, pre_away)

        if fav_odds > fav_pre_max or ud_odds < ud_pre_min:
            continue

        # Determine which team is the underdog
        if pre_home > pre_away:
            ud_team = "local"
        else:
            ud_team = "visitante"

        triggered = False
        prev_gl = None
        prev_gv = None

        for idx, row in enumerate(match["rows"]):
            m = _f(row.get("minuto", ""))
            if m is None or not (m_min <= m <= m_max):
                gl_now = _i(row.get("goles_local", ""))
                gv_now = _i(row.get("goles_visitante", ""))
                if gl_now is not None:
                    prev_gl = gl_now
                if gv_now is not None:
                    prev_gv = gv_now
                continue

            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue

            # Check if underdog just scored (score changed from previous)
            just_scored = False
            if prev_gl is not None and prev_gv is not None:
                if ud_team == "local":
                    if gl > prev_gl and gl > gv:  # Local (underdog) scored and leads
                        just_scored = True
                else:
                    if gv > prev_gv and gv > gl:  # Visitante (underdog) scored and leads
                        just_scored = True

            # Also check: underdog is leading (even if we missed the exact goal moment)
            ud_leading = False
            if ud_team == "local" and gl > gv:
                ud_leading = True
            elif ud_team == "visitante" and gv > gl:
                ud_leading = True

            if (just_scored or ud_leading) and not triggered:
                # Get current odds for the underdog
                if ud_team == "local":
                    odds_col = "back_home"
                else:
                    odds_col = "back_away"

                odds = _f(row.get(odds_col, ""))
                if odds is None or odds <= 1.0:
                    prev_gl = gl
                    prev_gv = gv
                    continue

                # Market still expects comeback: underdog odds > 1.55
                if odds < 1.55:
                    prev_gl = gl
                    prev_gv = gv
                    continue

                # Check win condition
                if ud_team == "local":
                    won = match["ft_local"] > match["ft_visitante"]
                else:
                    won = match["ft_visitante"] > match["ft_local"]

                pl = round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

                bets.append({
                    "match_id": match["match_id"],
                    "minuto": m,
                    "odds": odds,
                    "won": won,
                    "pl": pl,
                    "ud_team": ud_team,
                    "fav_odds": fav_odds,
                    "ud_odds": ud_odds,
                    "score_at_trigger": f"{gl}-{gv}",
                    "ft": f"{match['ft_local']}-{match['ft_visitante']}",
                    "league": match.get("league", "?"),
                    "timestamp": match.get("timestamp_first", ""),
                })
                triggered = True

            prev_gl = gl
            prev_gv = gv

    return bets

def eval_bets(bets, label=""):
    if not bets:
        print(f"  {label}: N=0")
        return
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins / n * 100
    total_pl = sum(b["pl"] for b in bets)
    roi = total_pl / (n * STAKE) * 100
    avg_odds = sum(b["odds"] for b in bets) / n
    ci_lo, ci_hi = wilson_ci95(n, wins)
    leagues = set(b.get("league", "?") for b in bets)
    print(f"  {label}: N={n}, Wins={wins}, WR={wr:.1f}%, ROI={roi:.1f}%, "
          f"P/L={total_pl:.2f}, AvgOdds={avg_odds:.2f}, "
          f"IC95=[{ci_lo}, {ci_hi}], Leagues={len(leagues)}")

def main():
    print("Loading matches...")
    matches = load_matches()
    print(f"Loaded {len(matches)} finished matches")

    # Count matches with pre-match odds
    with_odds = sum(1 for m in matches if m["pre_home"] is not None)
    print(f"Matches with pre-match odds: {with_odds}")

    print("\n=== H4: Reverse Favourite-Longshot Bias ===")
    print("Grid search: m_min x m_max x fav_pre_max x ud_pre_min\n")

    results = []
    for m_min in [65, 70, 72, 75]:
        for m_max in [82, 85, 88, 90]:
            for fav_pre_max in [1.40, 1.50, 1.60, 1.80, 2.00]:
                for ud_pre_min in [3.0, 4.0, 5.0, 6.0]:
                    bets = run_backtest(matches, m_min, m_max, fav_pre_max, ud_pre_min)
                    if len(bets) >= 5:
                        n = len(bets)
                        wins = sum(1 for b in bets if b["won"])
                        wr = wins / n * 100
                        total_pl = sum(b["pl"] for b in bets)
                        roi = total_pl / (n * STAKE) * 100
                        avg_odds = sum(b["odds"] for b in bets) / n
                        ci_lo, ci_hi = wilson_ci95(n, wins)
                        leagues = len(set(b.get("league", "?") for b in bets))
                        results.append({
                            "m_min": m_min, "m_max": m_max,
                            "fav_pre_max": fav_pre_max, "ud_pre_min": ud_pre_min,
                            "N": n, "wins": wins, "wr": wr, "roi": roi,
                            "pl": total_pl, "avg_odds": avg_odds,
                            "ci_lo": ci_lo, "ci_hi": ci_hi, "leagues": leagues,
                        })

    # Sort by N descending
    results.sort(key=lambda x: -x["N"])

    print(f"Total combos with N>=5: {len(results)}")
    print(f"\nTop 20 by sample size:")
    print(f"{'m_min':>5} {'m_max':>5} {'fav<':>5} {'ud>':>5} | {'N':>4} {'W':>4} {'WR%':>6} {'ROI%':>7} {'AvgOdd':>7} {'IC95lo':>7} {'Lgs':>4}")
    print("-" * 75)
    for r in results[:20]:
        print(f"{r['m_min']:>5} {r['m_max']:>5} {r['fav_pre_max']:>5.2f} {r['ud_pre_min']:>5.1f} | "
              f"{r['N']:>4} {r['wins']:>4} {r['wr']:>5.1f}% {r['roi']:>6.1f}% {r['avg_odds']:>7.2f} {r['ci_lo']:>6.1f}% {r['leagues']:>4}")

    print(f"\nTop 10 by ROI (N>=15):")
    roi_results = [r for r in results if r["N"] >= 15]
    roi_results.sort(key=lambda x: -x["roi"])
    for r in roi_results[:10]:
        print(f"{r['m_min']:>5} {r['m_max']:>5} {r['fav_pre_max']:>5.2f} {r['ud_pre_min']:>5.1f} | "
              f"{r['N']:>4} {r['wins']:>4} {r['wr']:>5.1f}% {r['roi']:>6.1f}% {r['avg_odds']:>7.2f} {r['ci_lo']:>6.1f}% {r['leagues']:>4}")

    # Show the best combo with N>=30
    best_30 = [r for r in results if r["N"] >= 30]
    if best_30:
        best_30.sort(key=lambda x: -x["roi"])
        print(f"\nBest combo with N>=30:")
        r = best_30[0]
        print(f"  m=[{r['m_min']},{r['m_max']}], fav<{r['fav_pre_max']}, ud>{r['ud_pre_min']}")
        print(f"  N={r['N']}, WR={r['wr']:.1f}%, ROI={r['roi']:.1f}%, AvgOdds={r['avg_odds']:.2f}")

    # Max N achieved
    if results:
        max_n = max(r["N"] for r in results)
        print(f"\nMax N achieved across all combos: {max_n}")
        print(f"N>=48 (quality gate): {'YES' if max_n >= 48 else 'NO'}")

    # Detailed analysis of broadest combo
    if results:
        broadest = results[0]
        print(f"\nBroadest combo details:")
        bets = run_backtest(matches, broadest["m_min"], broadest["m_max"],
                           broadest["fav_pre_max"], broadest["ud_pre_min"])
        print(f"  Score distribution at trigger:")
        scores = Counter(b["score_at_trigger"] for b in bets)
        for s, c in scores.most_common():
            w = sum(1 for b in bets if b["score_at_trigger"] == s and b["won"])
            print(f"    {s}: {c} bets, {w} wins ({w/c*100:.0f}%)")

if __name__ == "__main__":
    main()
