"""
Backtest: H6 - CS 2-2 after momentum shift (Gemini analisis2.md)
Score was 2-0 for N+ minutes, then became 2-1. Back CS 2-2.
Also test: any 2-1 (without requiring prior 2-0 duration) as broadened version.
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
        matches.append({
            "file": os.path.basename(fpath),
            "match_id": os.path.basename(fpath).replace("partido_", "").replace(".csv", ""),
            "ft_local": gl,
            "ft_visitante": gv,
            "ft_total": gl + gv,
            "rows": rows,
            "league": last.get("Liga", "?"),
            "timestamp_first": rows[0].get("timestamp_utc", ""),
        })
    return matches

def run_backtest_strict(matches, m_min, m_max, min_lead_duration, odds_min, odds_max):
    """Strict H6: 2-0 for N+ minutes then 2-1."""
    bets = []
    for match in matches:
        rows = match["rows"]
        triggered = False

        # Track 2-0 duration
        score_20_start = None
        leading_team = None  # "local" or "visitante"

        for idx, row in enumerate(rows):
            if triggered:
                break
            m = _f(row.get("minuto", ""))
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if m is None or gl is None or gv is None:
                continue

            # Track 2-0 state (either direction)
            if (gl == 2 and gv == 0):
                if score_20_start is None:
                    score_20_start = m
                    leading_team = "local"
            elif (gl == 0 and gv == 2):
                if score_20_start is None:
                    score_20_start = m
                    leading_team = "visitante"
            elif score_20_start is not None:
                # Score changed
                duration = m - score_20_start if m > score_20_start else 0

                # Check if it went to 2-1
                is_21 = False
                if leading_team == "local" and gl == 2 and gv == 1:
                    is_21 = True
                elif leading_team == "visitante" and gl == 1 and gv == 2:
                    is_21 = True

                if is_21 and duration >= min_lead_duration and m_min <= m <= m_max:
                    # Get CS 2-2 odds
                    odds = _f(row.get("back_rc_2_2", ""))
                    if odds and odds >= odds_min and odds <= odds_max:
                        won = (match["ft_local"] == 2 and match["ft_visitante"] == 2)
                        pl = round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

                        bets.append({
                            "match_id": match["match_id"],
                            "minuto": m,
                            "odds": odds,
                            "won": won,
                            "pl": pl,
                            "score_at_trigger": f"{gl}-{gv}",
                            "lead_duration": duration,
                            "ft": f"{match['ft_local']}-{match['ft_visitante']}",
                            "league": match.get("league", "?"),
                            "timestamp": match.get("timestamp_first", ""),
                        })
                        triggered = True
                else:
                    score_20_start = None
                    leading_team = None

    return bets

def run_backtest_broad(matches, m_min, m_max, odds_min, odds_max):
    """Broad version: any time score is 2-1, back CS 2-2."""
    bets = []
    for match in matches:
        rows = match["rows"]
        triggered = False

        for idx, row in enumerate(rows):
            if triggered:
                break
            m = _f(row.get("minuto", ""))
            gl = _i(row.get("goles_local", ""))
            gv = _i(row.get("goles_visitante", ""))
            if m is None or gl is None or gv is None:
                continue

            if not (m_min <= m <= m_max):
                continue

            if (gl == 2 and gv == 1) or (gl == 1 and gv == 2):
                odds = _f(row.get("back_rc_2_2", ""))
                if odds and odds >= odds_min and odds <= odds_max:
                    won = (match["ft_local"] == 2 and match["ft_visitante"] == 2)
                    pl = round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

                    bets.append({
                        "match_id": match["match_id"],
                        "minuto": m,
                        "odds": odds,
                        "won": won,
                        "pl": pl,
                        "score_at_trigger": f"{gl}-{gv}",
                        "ft": f"{match['ft_local']}-{match['ft_visitante']}",
                        "league": match.get("league", "?"),
                        "timestamp": match.get("timestamp_first", ""),
                    })
                    triggered = True

    return bets

def main():
    print("Loading matches...")
    matches = load_matches()
    print(f"Loaded {len(matches)} finished matches")
    n_matches = len(matches)
    g_min = max(15, n_matches // 25)
    print(f"Quality gate N minimum: {g_min}")

    # Count FT 2-2 matches
    ft_22 = sum(1 for m in matches if m["ft_local"] == 2 and m["ft_visitante"] == 2)
    print(f"FT 2-2 matches: {ft_22} ({ft_22/n_matches*100:.1f}%)")

    print("\n=== H6 STRICT: 2-0 held for N min, then 2-1 -> Back CS 2-2 ===")
    for m_min in [55, 60, 65]:
        for m_max in [75, 80, 85]:
            for min_dur in [10, 15, 20]:
                for odds_max in [15.0, 25.0, 50.0]:
                    bets = run_backtest_strict(matches, m_min, m_max, min_dur, 2.0, odds_max)
                    if len(bets) >= 3:
                        n = len(bets)
                        wins = sum(1 for b in bets if b["won"])
                        wr = wins / n * 100 if n > 0 else 0
                        total_pl = sum(b["pl"] for b in bets)
                        roi = total_pl / (n * STAKE) * 100 if n > 0 else 0
                        avg_odds = sum(b["odds"] for b in bets) / n if n > 0 else 0
                        print(f"  m=[{m_min},{m_max}] dur>={min_dur} odds<{odds_max}: "
                              f"N={n}, W={wins}, WR={wr:.0f}%, ROI={roi:.1f}%, AvgOdds={avg_odds:.1f}")

    print("\n=== BROAD: Any 2-1 in minute range -> Back CS 2-2 ===")
    for m_min in [50, 55, 60, 65, 70]:
        for m_max in [75, 80, 85, 90]:
            for odds_max in [10.0, 15.0, 25.0]:
                bets = run_backtest_broad(matches, m_min, m_max, 2.0, odds_max)
                if len(bets) >= 15:
                    n = len(bets)
                    wins = sum(1 for b in bets if b["won"])
                    wr = wins / n * 100
                    total_pl = sum(b["pl"] for b in bets)
                    roi = total_pl / (n * STAKE) * 100
                    avg_odds = sum(b["odds"] for b in bets) / n
                    ci_lo, ci_hi = wilson_ci95(n, wins)
                    print(f"  m=[{m_min},{m_max}] odds<{odds_max}: "
                          f"N={n}, W={wins}, WR={wr:.1f}%, ROI={roi:.1f}%, "
                          f"AvgOdds={avg_odds:.1f}, IC95lo={ci_lo}%")

if __name__ == "__main__":
    main()
