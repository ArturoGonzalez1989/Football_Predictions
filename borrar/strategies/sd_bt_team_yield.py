"""
Team Yield Filter Analysis — H82-H86
Tests whether historical team performance (yield/ROI) can predict
future bet outcomes across ALL strategies in the portfolio.

Hypotheses:
  H82: Team yield filter for goal_clustering
  H83: Team yield filter for pressure_cooker
  H84: "Toxic team" global filter (any strategy)
  H85: "Profitable away team" boost for clustering/pressure
  H86: Team yield x league tier interaction

Methodology:
  - Replicate strategy triggers from raw CSVs (no dependency on csv_reader.py)
  - Build chronological team yield per team
  - Test if filtering by team yield improves ROI
  - Train/test 70/30 chronological split
  - Quality gates: N>=60 per group, IC95 lo > 40%
"""

import os, glob, csv, math, json, sys
from collections import defaultdict, Counter
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "betfair_scraper", "data")
LOOKUP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analisis", "team_lookup.json")
STAKE = 10.0

# ── Helpers ──────────────────────────────────────────────────────────────

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

def stats_report(bets, label=""):
    if not bets:
        return {"n": 0, "label": label}
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins / n * 100
    total_pl = sum(b["pl"] for b in bets)
    roi = total_pl / (n * STAKE) * 100
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    leagues = set(b.get("league", "?") for b in bets)
    return {
        "label": label, "n": n, "wins": wins,
        "wr": round(wr, 1), "roi": round(roi, 1),
        "total_pl": round(total_pl, 2),
        "ci95_lo": ci_lo, "ci95_hi": ci_hi,
        "avg_odds": round(sum(b["odds"] for b in bets) / n, 2),
        "max_dd": max_drawdown(pls),
        "sharpe": sharpe_ratio(pls),
        "leagues": len(leagues),
    }

def print_stats(s):
    if s["n"] == 0:
        print(f"  {s['label']}: N=0")
        return
    print(f"  {s['label']}: N={s['n']}, WR={s['wr']}%, ROI={s['roi']}%, "
          f"P/L={s['total_pl']}, AvgOdds={s['avg_odds']}, "
          f"IC95=[{s['ci95_lo']}%,{s['ci95_hi']}%], Sharpe={s['sharpe']}, "
          f"MaxDD={s['max_dd']}, Leagues={s['leagues']}")

# ── Load data ────────────────────────────────────────────────────────────

def load_team_lookup():
    with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

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
        # Get first valid timestamp
        ts = ""
        for r in rows:
            t = r.get("timestamp_utc", "")
            if t and len(t) >= 10:
                ts = t
                break
        match_id = os.path.basename(fpath).replace("partido_", "").replace(".csv", "")
        matches.append({
            "file": os.path.basename(fpath),
            "match_id": match_id,
            "country": last.get("País", "?"),
            "league": last.get("Liga", "?"),
            "ft_local": gl,
            "ft_visitante": gv,
            "ft_total": gl + gv,
            "rows": rows,
            "timestamp": ts,
        })
    # Sort by timestamp
    matches.sort(key=lambda m: m["timestamp"])
    return matches

# ── Strategy trigger replication ─────────────────────────────────────────

def _get_over_field(total_goals):
    """Given current total goals, return the over field for 'next goal line'."""
    line = total_goals + 0.5
    mapping = {
        0.5: "back_over05", 1.5: "back_over15", 2.5: "back_over25",
        3.5: "back_over35", 4.5: "back_over45", 5.5: "back_over55",
        6.5: "back_over65",
    }
    return mapping.get(line)

def detect_clustering(rows, min_min=15, max_min=80, sot_min=3, min_dur=1):
    """Replicate goal_clustering trigger. Returns first trigger bet or None."""
    for idx in range(1, len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
        # Check for recent goal (last 3 captures)
        recent_goal = False
        for i in range(idx, max(0, idx - 3), -1):
            if i == 0:
                break
            now = rows[i]
            prev = rows[i - 1]
            gl_now = _i(now.get("goles_local", "")) or 0
            gv_now = _i(now.get("goles_visitante", "")) or 0
            gl_prev = _i(prev.get("goles_local", "")) or 0
            gv_prev = _i(prev.get("goles_visitante", "")) or 0
            if gl_now + gv_now > gl_prev + gv_prev:
                rm = _f(now.get("minuto", ""))
                if rm and min_min <= rm <= max_min:
                    recent_goal = True
                    break
        if not recent_goal:
            continue
        # SoT filter
        sot_l = _f(row.get("tiros_puerta_local", "")) or 0
        sot_v = _f(row.get("tiros_puerta_visitante", "")) or 0
        if max(int(sot_l), int(sot_v)) < sot_min:
            continue
        # Get odds
        gl = _i(row.get("goles_local", "")) or 0
        gv = _i(row.get("goles_visitante", "")) or 0
        total = gl + gv
        over_field = _get_over_field(total)
        if not over_field:
            continue
        entry_idx = min(idx + min_dur - 1, len(rows) - 1)
        odds = _f(rows[entry_idx].get(over_field, ""))
        if odds is None or odds < 1.05 or odds > 10.0:
            continue
        return {
            "minuto": m,
            "odds": odds,
            "total_goals_at_trigger": total,
            "over_field": over_field,
            "entry_idx": entry_idx,
        }
    return None

def detect_pressure(rows, min_min=65, max_min=75, min_dur=1):
    """Replicate pressure_cooker trigger. Returns first trigger bet or None."""
    for idx in range(1, len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
        estado = row.get("estado_partido", "")
        if estado and estado != "en_juego":
            continue
        gl = _f(row.get("goles_local", ""))
        gv = _f(row.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        gl_i, gv_i = int(gl), int(gv)
        if gl_i != gv_i or gl_i == 0:
            continue
        # Score confirmation
        check = rows[max(0, idx - 5):idx + 1]
        confirm = sum(1 for r in check
                      if _f(r.get("goles_local", "")) == gl
                      and _f(r.get("goles_visitante", "")) == gv)
        if confirm < 2:
            continue
        total = gl_i + gv_i
        over_field = _get_over_field(total)
        if not over_field:
            continue
        entry_idx = min(idx + min_dur - 1, len(rows) - 1)
        odds = _f(rows[entry_idx].get(over_field, ""))
        if odds is None or odds < 1.05 or odds > 10.0:
            continue
        return {
            "minuto": m,
            "odds": odds,
            "total_goals_at_trigger": total,
            "over_field": over_field,
            "entry_idx": entry_idx,
        }
    return None

def detect_xg_underperf(rows, min_min=25, max_min=85, xg_excess=0.5, min_dur=1):
    """Replicate xG underperformance trigger."""
    for idx in range(1, len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
        gl = _i(row.get("goles_local", "")) or 0
        gv = _i(row.get("goles_visitante", "")) or 0
        xg_l = _f(row.get("xg_local", ""))
        xg_v = _f(row.get("xg_visitante", ""))
        if xg_l is None or xg_v is None:
            continue
        # Check if any team is losing but has xG excess
        team_losing = None
        if gl < gv and xg_l - gl >= xg_excess:
            team_losing = "local"
        elif gv < gl and xg_v - gv >= xg_excess:
            team_losing = "visitante"
        if team_losing is None:
            continue
        total = gl + gv
        over_field = _get_over_field(total)
        if not over_field:
            continue
        entry_idx = min(idx + min_dur - 1, len(rows) - 1)
        odds = _f(rows[entry_idx].get(over_field, ""))
        if odds is None or odds < 1.05 or odds > 10.0:
            continue
        return {
            "minuto": m,
            "odds": odds,
            "total_goals_at_trigger": total,
            "team_losing": team_losing,
            "entry_idx": entry_idx,
        }
    return None


# ── All SD strategies (simplified triggers) ──────────────────────────────

def detect_any_leader_strategy(rows, min_min=70, max_min=85):
    """Detect leader-late strategies (H59, H67, H70) - BACK match winner."""
    for idx in range(len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
        gl = _i(row.get("goles_local", "")) or 0
        gv = _i(row.get("goles_visitante", "")) or 0
        if gl == gv:
            continue  # No leader
        if gl > gv:
            odds = _f(row.get("back_home", ""))
        else:
            odds = _f(row.get("back_away", ""))
        if odds is None or odds < 1.05 or odds > 10.0:
            continue
        return {
            "minuto": m,
            "odds": odds,
            "leader": "local" if gl > gv else "visitante",
            "gl": gl, "gv": gv,
        }
    return None

def detect_cs_strategy(rows, min_min=75, max_min=90):
    """Detect CS strategies (H49, H53, H77, H79, H81) - BACK correct score."""
    valid_scores = [(1, 0), (0, 1), (2, 1), (1, 2), (1, 1),
                    (2, 0), (0, 2), (3, 0), (0, 3), (3, 1), (1, 3)]
    score_to_field = {
        (0, 0): "back_rc_0_0", (1, 0): "back_rc_1_0", (0, 1): "back_rc_0_1",
        (1, 1): "back_rc_1_1", (2, 0): "back_rc_2_0", (0, 2): "back_rc_0_2",
        (2, 1): "back_rc_2_1", (1, 2): "back_rc_1_2", (2, 2): "back_rc_2_2",
        (3, 0): "back_rc_3_0", (0, 3): "back_rc_0_3", (3, 1): "back_rc_3_1",
        (1, 3): "back_rc_1_3", (3, 2): "back_rc_3_2", (2, 3): "back_rc_2_3",
    }
    for idx in range(len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
        gl = _i(row.get("goles_local", "")) or 0
        gv = _i(row.get("goles_visitante", "")) or 0
        score = (gl, gv)
        if score not in valid_scores:
            continue
        field = score_to_field.get(score)
        if not field:
            continue
        odds = _f(row.get(field, ""))
        if odds is None or odds < 1.05 or odds > 10.0:
            continue
        return {
            "minuto": m,
            "odds": odds,
            "score": score,
            "won": True,  # placeholder - computed later
        }
    return None

def detect_under_strategy(rows, min_min=70, max_min=85):
    """Detect under strategies (H46, H66, H71)."""
    for idx in range(len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
        gl = _i(row.get("goles_local", "")) or 0
        gv = _i(row.get("goles_visitante", "")) or 0
        total = gl + gv
        if total < 1 or total > 3:
            continue
        # Try under 2.5 or under 3.5 or under 4.5
        under_fields = {
            "back_under25": 2.5,
            "back_under35": 3.5,
            "back_under45": 4.5,
        }
        for field, line in under_fields.items():
            if total >= line:
                continue
            odds = _f(row.get(field, ""))
            if odds is None or odds < 1.05 or odds > 10.0:
                continue
            return {
                "minuto": m,
                "odds": odds,
                "under_line": line,
                "total_at_trigger": total,
            }
    return None

def detect_draw_strategy(rows, min_min=60, max_min=85):
    """Detect draw strategies (H58 - draw at 1-1)."""
    for idx in range(len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
        gl = _i(row.get("goles_local", "")) or 0
        gv = _i(row.get("goles_visitante", "")) or 0
        if gl != gv or gl == 0:
            continue
        odds = _f(row.get("back_draw", ""))
        if odds is None or odds < 1.05 or odds > 10.0:
            continue
        return {
            "minuto": m,
            "odds": odds,
            "score": (gl, gv),
        }
    return None


# ── Main analysis ────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("TEAM YIELD FILTER ANALYSIS — H82-H86")
    print("=" * 80)

    team_lookup = load_team_lookup()
    print(f"\nTeam lookup: {len(team_lookup)} entries")

    matches = load_matches()
    print(f"Loaded matches: {len(matches)} (sorted by timestamp)")

    # Map match_id -> (home_team, away_team)
    team_map = {}
    for mid, teams in team_lookup.items():
        team_map[mid] = (teams[0], teams[1])

    # ── Step 1: Generate ALL strategy bets from raw CSVs ─────────────────
    print("\n" + "=" * 80)
    print("STEP 1: Generating strategy bets from raw CSVs")
    print("=" * 80)

    strategies = {
        "goal_clustering": [],
        "pressure_cooker": [],
        "xg_underperf": [],
        "leader_late": [],
        "cs_late": [],
        "under_late": [],
        "draw_late": [],
    }

    for match in matches:
        mid = match["match_id"]
        rows = match["rows"]
        ft_total = match["ft_total"]
        ft_l = match["ft_local"]
        ft_v = match["ft_visitante"]
        ts = match["timestamp"]
        league = match["league"]

        if mid not in team_map:
            continue

        home_team, away_team = team_map[mid]

        # Goal clustering
        trig = detect_clustering(rows, min_min=15, max_min=80, sot_min=3, min_dur=1)
        if trig:
            total_at = trig["total_goals_at_trigger"]
            won = ft_total > total_at
            strategies["goal_clustering"].append({
                "match_id": mid, "timestamp": ts, "league": league,
                "home_team": home_team, "away_team": away_team,
                "minuto": trig["minuto"], "odds": trig["odds"],
                "won": won, "pl": pl_back(trig["odds"], won),
                "strategy": "goal_clustering",
            })

        # Pressure cooker
        trig = detect_pressure(rows, min_min=65, max_min=75, min_dur=1)
        if trig:
            total_at = trig["total_goals_at_trigger"]
            won = ft_total > total_at
            strategies["pressure_cooker"].append({
                "match_id": mid, "timestamp": ts, "league": league,
                "home_team": home_team, "away_team": away_team,
                "minuto": trig["minuto"], "odds": trig["odds"],
                "won": won, "pl": pl_back(trig["odds"], won),
                "strategy": "pressure_cooker",
            })

        # xG underperformance
        trig = detect_xg_underperf(rows, min_min=25, max_min=85, xg_excess=0.5, min_dur=1)
        if trig:
            total_at = trig["total_goals_at_trigger"]
            won = ft_total > total_at
            strategies["xg_underperf"].append({
                "match_id": mid, "timestamp": ts, "league": league,
                "home_team": home_team, "away_team": away_team,
                "minuto": trig["minuto"], "odds": trig["odds"],
                "won": won, "pl": pl_back(trig["odds"], won),
                "strategy": "xg_underperf",
            })

        # Leader late
        trig = detect_any_leader_strategy(rows, min_min=70, max_min=85)
        if trig:
            if trig["leader"] == "local":
                won = ft_l > ft_v
            else:
                won = ft_v > ft_l
            strategies["leader_late"].append({
                "match_id": mid, "timestamp": ts, "league": league,
                "home_team": home_team, "away_team": away_team,
                "minuto": trig["minuto"], "odds": trig["odds"],
                "won": won, "pl": pl_back(trig["odds"], won),
                "strategy": "leader_late",
            })

        # CS late
        trig = detect_cs_strategy(rows, min_min=75, max_min=90)
        if trig:
            score = trig["score"]
            won = (ft_l == score[0] and ft_v == score[1])
            strategies["cs_late"].append({
                "match_id": mid, "timestamp": ts, "league": league,
                "home_team": home_team, "away_team": away_team,
                "minuto": trig["minuto"], "odds": trig["odds"],
                "won": won, "pl": pl_back(trig["odds"], won),
                "strategy": "cs_late",
            })

        # Under late
        trig = detect_under_strategy(rows, min_min=70, max_min=85)
        if trig:
            won = ft_total < trig["under_line"]
            strategies["under_late"].append({
                "match_id": mid, "timestamp": ts, "league": league,
                "home_team": home_team, "away_team": away_team,
                "minuto": trig["minuto"], "odds": trig["odds"],
                "won": won, "pl": pl_back(trig["odds"], won),
                "strategy": "under_late",
            })

        # Draw late
        trig = detect_draw_strategy(rows, min_min=60, max_min=85)
        if trig:
            won = ft_l == ft_v
            strategies["draw_late"].append({
                "match_id": mid, "timestamp": ts, "league": league,
                "home_team": home_team, "away_team": away_team,
                "minuto": trig["minuto"], "odds": trig["odds"],
                "won": won, "pl": pl_back(trig["odds"], won),
                "strategy": "draw_late",
            })

    print("\nStrategy bet counts (raw from CSVs):")
    all_bets = []
    for name, bets in strategies.items():
        s = stats_report(bets, name)
        print_stats(s)
        all_bets.extend(bets)

    print(f"\nTotal bets across all strategies: {len(all_bets)}")

    # ── Step 2: Build chronological team yield ───────────────────────────
    print("\n" + "=" * 80)
    print("STEP 2: Building chronological team yield")
    print("=" * 80)

    # For each match sorted by timestamp, compute the team's ROI in
    # all PRIOR bets where that team was involved
    # team_history[team] = list of (timestamp, won, pl, odds, strategy)
    # We need to be careful: yield is computed ONLY from matches BEFORE the current one

    # First, build ALL bets sorted by timestamp
    all_bets_sorted = sorted(all_bets, key=lambda b: b["timestamp"])

    # Build team -> chronological bets
    team_bets_chrono = defaultdict(list)  # team -> [(ts, won, pl, odds, strategy, match_id)]
    for b in all_bets_sorted:
        team_bets_chrono[b["home_team"]].append(b)
        team_bets_chrono[b["away_team"]].append(b)

    print(f"Unique teams with bets: {len(team_bets_chrono)}")

    # Show team distribution
    team_counts = [(t, len(bs)) for t, bs in team_bets_chrono.items()]
    team_counts.sort(key=lambda x: -x[1])
    print(f"Top 10 teams by bet count:")
    for t, c in team_counts[:10]:
        print(f"  {t}: {c} bets")
    print(f"Teams with >= 10 bets: {sum(1 for _, c in team_counts if c >= 10)}")
    print(f"Teams with >= 5 bets: {sum(1 for _, c in team_counts if c >= 5)}")

    # ── Step 3: Compute team yield for each bet ──────────────────────────
    print("\n" + "=" * 80)
    print("STEP 3: Computing per-bet team yield (chronological, no look-ahead)")
    print("=" * 80)

    # For each bet, compute yield of home_team and away_team using only PRIOR bets
    # We process all_bets_sorted in order, maintaining running totals

    # team -> {"n": int, "wins": int, "pl": float}
    team_running = defaultdict(lambda: {"n": 0, "wins": 0, "pl": 0.0})

    for b in all_bets_sorted:
        home = b["home_team"]
        away = b["away_team"]

        # Snapshot current yield BEFORE updating
        h_stats = team_running[home].copy()
        a_stats = team_running[away].copy()

        b["home_yield_n"] = h_stats["n"]
        b["home_yield_roi"] = (h_stats["pl"] / (h_stats["n"] * STAKE) * 100) if h_stats["n"] > 0 else 0
        b["home_yield_wr"] = (h_stats["wins"] / h_stats["n"] * 100) if h_stats["n"] > 0 else 0

        b["away_yield_n"] = a_stats["n"]
        b["away_yield_roi"] = (a_stats["pl"] / (a_stats["n"] * STAKE) * 100) if a_stats["n"] > 0 else 0
        b["away_yield_wr"] = (a_stats["wins"] / a_stats["n"] * 100) if a_stats["n"] > 0 else 0

        # Combined yield (avg of both teams)
        total_n = h_stats["n"] + a_stats["n"]
        total_pl = h_stats["pl"] + a_stats["pl"]
        b["combined_yield_n"] = total_n
        b["combined_yield_roi"] = (total_pl / (total_n * STAKE) * 100) if total_n > 0 else 0

        # Max yield (best of both teams)
        b["max_yield_roi"] = max(b["home_yield_roi"], b["away_yield_roi"])
        # Min yield (worst of both teams)
        b["min_yield_roi"] = min(b["home_yield_roi"], b["away_yield_roi"])

        # Update running totals (AFTER snapshot)
        team_running[home]["n"] += 1
        team_running[home]["wins"] += 1 if b["won"] else 0
        team_running[home]["pl"] += b["pl"]
        team_running[away]["n"] += 1
        team_running[away]["wins"] += 1 if b["won"] else 0
        team_running[away]["pl"] += b["pl"]

    # How many bets have sufficient history?
    for min_hist in [3, 5, 10, 15]:
        n_with = sum(1 for b in all_bets_sorted
                     if b["home_yield_n"] >= min_hist or b["away_yield_n"] >= min_hist)
        n_both = sum(1 for b in all_bets_sorted
                     if b["home_yield_n"] >= min_hist and b["away_yield_n"] >= min_hist)
        print(f"  Bets with >= {min_hist} history (either team): {n_with} | (both): {n_both}")

    # ── Step 4: Analyze team yield as predictor ──────────────────────────
    print("\n" + "=" * 80)
    print("STEP 4: Team yield as predictor — overall analysis")
    print("=" * 80)

    # For bets where at least one team has >= 5 prior bets
    MIN_HIST = 5
    bets_with_hist = [b for b in all_bets_sorted
                      if b["home_yield_n"] >= MIN_HIST or b["away_yield_n"] >= MIN_HIST]
    print(f"\nBets with >= {MIN_HIST} history for at least one team: {len(bets_with_hist)}")

    # Split by combined yield sign
    for threshold in [-30, -20, -10, 0, 10, 20, 30]:
        above = [b for b in bets_with_hist if b["combined_yield_roi"] >= threshold
                 and b["combined_yield_n"] >= MIN_HIST]
        below = [b for b in bets_with_hist if b["combined_yield_roi"] < threshold
                 and b["combined_yield_n"] >= MIN_HIST]
        sa = stats_report(above, f"combined_roi >= {threshold}%")
        sb = stats_report(below, f"combined_roi < {threshold}%")
        if sa["n"] >= 30 and sb["n"] >= 30:
            print(f"\n  Threshold: combined_yield_roi {'>='}  {threshold}%")
            print_stats(sa)
            print_stats(sb)
            delta_roi = sa["roi"] - sb["roi"] if sa["n"] > 0 and sb["n"] > 0 else 0
            print(f"  Delta ROI: {delta_roi:+.1f}pp")

    # ── Step 5: Per-strategy analysis ────────────────────────────────────
    print("\n" + "=" * 80)
    print("STEP 5: Team yield filter per strategy")
    print("=" * 80)

    for strat_name in ["goal_clustering", "pressure_cooker", "xg_underperf",
                        "leader_late", "cs_late", "under_late", "draw_late"]:
        strat_bets = [b for b in all_bets_sorted if b["strategy"] == strat_name]
        if len(strat_bets) < 20:
            continue

        print(f"\n{'-' * 60}")
        print(f"Strategy: {strat_name} (N={len(strat_bets)})")
        print(f"{'-' * 60}")

        s_base = stats_report(strat_bets, "BASELINE")
        print_stats(s_base)

        # Test various yield filters
        for min_hist in [3, 5, 10]:
            bets_h = [b for b in strat_bets
                      if b["home_yield_n"] >= min_hist or b["away_yield_n"] >= min_hist]
            if len(bets_h) < 20:
                continue

            print(f"\n  Min history: {min_hist} (N with hist: {len(bets_h)})")

            # H82/H83: Filter by min_yield (worst team) — remove toxic teams
            for thr in [-30, -20, -10, 0]:
                kept = [b for b in bets_h if b["min_yield_roi"] >= thr or b["combined_yield_n"] < min_hist * 2]
                removed = [b for b in bets_h if b["min_yield_roi"] < thr and b["combined_yield_n"] >= min_hist * 2]
                if len(kept) >= 20 and len(removed) >= 5:
                    sk = stats_report(kept, f"  KEEP (min_yield >= {thr}%)")
                    sr = stats_report(removed, f"  REMOVE (min_yield < {thr}%)")
                    print_stats(sk)
                    print_stats(sr)
                    if sk["n"] > 0 and sr["n"] > 0:
                        print(f"    Filter removes {sr['n']} bets, delta ROI: {sk['roi'] - s_base['roi']:+.1f}pp vs baseline")

            # H85: Boost by max_yield (best team) — profitable team signal
            for thr in [0, 10, 20, 30]:
                boost = [b for b in bets_h if b["max_yield_roi"] >= thr and b["combined_yield_n"] >= min_hist * 2]
                rest = [b for b in bets_h if not (b["max_yield_roi"] >= thr and b["combined_yield_n"] >= min_hist * 2)]
                if len(boost) >= 15 and len(rest) >= 15:
                    sb = stats_report(boost, f"  BOOST (max_yield >= {thr}%)")
                    srest = stats_report(rest, f"  REST  (max_yield < {thr}%)")
                    print_stats(sb)
                    print_stats(srest)

    # ── Step 6: H84 — Global "Toxic Team" filter ────────────────────────
    print("\n" + "=" * 80)
    print("STEP 6: H84 — Global Toxic Team filter")
    print("=" * 80)

    # Identify teams with bad ROI across all strategies
    print("\nTeams with >= 10 bets and ROI < -30%:")
    toxic_teams = set()
    for team, stats_d in team_running.items():
        if stats_d["n"] >= 10:
            roi = stats_d["pl"] / (stats_d["n"] * STAKE) * 100
            if roi < -30:
                toxic_teams.add(team)
                print(f"  {team}: N={stats_d['n']}, ROI={roi:.1f}%, P/L={stats_d['pl']:.1f}")

    print(f"\nToxic teams (N>=10, ROI<-30%): {len(toxic_teams)}")

    # NOTE: This uses FULL history (look-ahead bias for testing concept).
    # Real implementation would need chronological calculation.
    # For now, just check if the concept has merit before building the proper version.

    # Test: remove bets involving toxic teams (using chronological yield computed above)
    for min_hist in [5, 10]:
        for thr in [-30, -20, -10]:
            filtered = []
            removed = []
            for b in all_bets_sorted:
                # Check if either team has chronological ROI < threshold at time of bet
                home_toxic = b["home_yield_n"] >= min_hist and b["home_yield_roi"] < thr
                away_toxic = b["away_yield_n"] >= min_hist and b["away_yield_roi"] < thr
                if home_toxic or away_toxic:
                    removed.append(b)
                else:
                    filtered.append(b)
            sf = stats_report(filtered, f"KEEP (no toxic, hist>={min_hist}, thr<{thr}%)")
            sr = stats_report(removed, f"REMOVE (toxic)")
            sb = stats_report(all_bets_sorted, "BASELINE (all)")
            if sr["n"] >= 10:
                print(f"\n  Filter: hist>={min_hist}, toxic_thr<{thr}%")
                print_stats(sb)
                print_stats(sf)
                print_stats(sr)
                print(f"    Delta ROI vs baseline: {sf['roi'] - sb['roi']:+.1f}pp (removed {sr['n']} bets)")

    # ── Step 7: H86 — League tier interaction ────────────────────────────
    print("\n" + "=" * 80)
    print("STEP 7: H86 — Team yield x league tier interaction")
    print("=" * 80)

    # Define league tiers
    TIER1_LEAGUES = {"Premier League", "LaLiga", "Serie A", "Bundesliga", "Ligue 1",
                     "Champions League", "Europa League"}
    TIER2_LEAGUES = {"Eredivisie", "Liga Portugal", "Süper Lig", "Championship",
                     "2. Bundesliga", "Serie B", "Ligue 2", "Liga MX", "MLS",
                     "Scottish Premiership", "Belgian Pro League", "Super League"}

    def get_tier(league):
        if league in TIER1_LEAGUES:
            return 1
        elif league in TIER2_LEAGUES:
            return 2
        else:
            return 3

    for tier in [1, 2, 3]:
        tier_bets = [b for b in all_bets_sorted if get_tier(b["league"]) == tier]
        if len(tier_bets) < 30:
            continue
        tier_hist = [b for b in tier_bets
                     if b["combined_yield_n"] >= 5]
        if len(tier_hist) < 20:
            continue

        print(f"\n  Tier {tier}: {len(tier_bets)} total bets, {len(tier_hist)} with history")
        s_all = stats_report(tier_bets, f"Tier {tier} ALL")
        print_stats(s_all)

        # Split by combined yield
        pos = [b for b in tier_hist if b["combined_yield_roi"] >= 0]
        neg = [b for b in tier_hist if b["combined_yield_roi"] < 0]
        if len(pos) >= 10 and len(neg) >= 10:
            sp = stats_report(pos, f"Tier {tier} combined_roi >= 0")
            sn = stats_report(neg, f"Tier {tier} combined_roi < 0")
            print_stats(sp)
            print_stats(sn)
            print(f"    Delta ROI: {sp['roi'] - sn['roi']:+.1f}pp")

    # ── Step 8: Train/Test split for best filters ────────────────────────
    print("\n" + "=" * 80)
    print("STEP 8: Train/Test validation (70/30 chronological)")
    print("=" * 80)

    # For each strategy, find the best yield-based filter and validate
    for strat_name in ["goal_clustering", "pressure_cooker", "xg_underperf",
                        "leader_late", "cs_late", "under_late", "draw_late"]:
        strat_bets = sorted([b for b in all_bets_sorted if b["strategy"] == strat_name],
                            key=lambda b: b["timestamp"])
        if len(strat_bets) < 40:
            continue

        split = int(len(strat_bets) * 0.7)
        train = strat_bets[:split]
        test = strat_bets[split:]

        print(f"\n{'-' * 60}")
        print(f"Strategy: {strat_name}")
        print(f"  Train: {len(train)} | Test: {len(test)}")
        print(f"{'-' * 60}")

        s_train_base = stats_report(train, "TRAIN baseline")
        s_test_base = stats_report(test, "TEST baseline")
        print_stats(s_train_base)
        print_stats(s_test_base)

        # Test filters on train, validate on test
        best_filter = None
        best_train_improvement = -999

        for min_hist in [3, 5]:
            for thr in [-30, -20, -10, 0, 10]:
                for yield_type in ["min_yield_roi", "combined_yield_roi", "max_yield_roi"]:
                    # Filter: KEEP bets where yield >= threshold (or insufficient history)
                    train_kept = [b for b in train
                                  if b.get(yield_type, 0) >= thr or b["combined_yield_n"] < min_hist * 2]
                    if len(train_kept) < 20 or len(train_kept) == len(train):
                        continue

                    s_train_f = stats_report(train_kept, f"TRAIN filtered")
                    improvement = s_train_f["roi"] - s_train_base["roi"]
                    if improvement > best_train_improvement and s_train_f["n"] >= 20:
                        best_train_improvement = improvement
                        best_filter = (min_hist, thr, yield_type)

                    # Also test INVERSE: KEEP bets where yield < threshold
                    train_inv = [b for b in train
                                 if b.get(yield_type, 0) < thr and b["combined_yield_n"] >= min_hist * 2]
                    if len(train_inv) >= 20:
                        s_inv = stats_report(train_inv, "TRAIN inverse")
                        if s_inv["roi"] > s_train_base["roi"] + best_train_improvement:
                            best_train_improvement = s_inv["roi"] - s_train_base["roi"]
                            best_filter = (min_hist, thr, yield_type, "inverse")

        if best_filter and best_train_improvement > 5:
            print(f"\n  Best filter (train): {best_filter}, improvement: +{best_train_improvement:.1f}pp")

            if len(best_filter) == 3:
                mh, th, yt = best_filter
                test_kept = [b for b in test
                             if b.get(yt, 0) >= th or b["combined_yield_n"] < mh * 2]
            else:
                mh, th, yt, _ = best_filter
                test_kept = [b for b in test
                             if b.get(yt, 0) < th and b["combined_yield_n"] >= mh * 2]

            if len(test_kept) >= 5:
                s_test_f = stats_report(test_kept, "TEST filtered")
                print_stats(s_test_f)
                test_improvement = s_test_f["roi"] - s_test_base["roi"]
                print(f"  Test improvement: {test_improvement:+.1f}pp")
                if test_improvement > 0:
                    print(f"  ** FILTER HOLDS IN TEST **")
                else:
                    print(f"  ** FILTER FAILS IN TEST — likely overfitting **")
            else:
                print(f"  Test set too small after filtering: {len(test_kept)}")
        else:
            print(f"\n  No filter found with >5pp improvement on train set")

    # ── Step 9: Comprehensive grid search for best combo ─────────────────
    print("\n" + "=" * 80)
    print("STEP 9: Comprehensive grid search — all strategies combined")
    print("=" * 80)

    # Test if yield filter improves the COMBINED portfolio
    split_idx = int(len(all_bets_sorted) * 0.7)
    train_all = all_bets_sorted[:split_idx]
    test_all = all_bets_sorted[split_idx:]

    s_train_all = stats_report(train_all, "TRAIN all portfolio")
    s_test_all = stats_report(test_all, "TEST all portfolio")
    print(f"\nPortfolio baseline:")
    print_stats(s_train_all)
    print_stats(s_test_all)

    print(f"\nGrid search results (combined portfolio):")
    print(f"{'MinHist':>8} {'Threshold':>10} {'YieldType':>20} {'Direction':>10} | "
          f"{'N_train':>8} {'ROI_tr':>8} {'N_test':>8} {'ROI_te':>8} {'Delta_tr':>10} {'Delta_te':>10}")
    print("-" * 120)

    results = []
    for min_hist in [3, 5, 10]:
        for thr in [-30, -20, -10, 0, 10, 20]:
            for yield_type in ["min_yield_roi", "combined_yield_roi", "max_yield_roi",
                               "home_yield_roi", "away_yield_roi"]:
                for direction in ["keep_above", "keep_below"]:
                    if direction == "keep_above":
                        tr_f = [b for b in train_all
                                if b.get(yield_type, 0) >= thr or b["combined_yield_n"] < min_hist * 2]
                        te_f = [b for b in test_all
                                if b.get(yield_type, 0) >= thr or b["combined_yield_n"] < min_hist * 2]
                    else:
                        tr_f = [b for b in train_all
                                if b.get(yield_type, 0) < thr and b["combined_yield_n"] >= min_hist * 2]
                        te_f = [b for b in test_all
                                if b.get(yield_type, 0) < thr and b["combined_yield_n"] >= min_hist * 2]

                    if len(tr_f) < 30 or len(te_f) < 10:
                        continue

                    s_tr = stats_report(tr_f)
                    s_te = stats_report(te_f)
                    delta_tr = s_tr["roi"] - s_train_all["roi"]
                    delta_te = s_te["roi"] - s_test_all["roi"]

                    if abs(delta_tr) > 3:  # Only show meaningful deltas
                        results.append({
                            "min_hist": min_hist, "thr": thr, "yield_type": yield_type,
                            "direction": direction,
                            "n_train": s_tr["n"], "roi_train": s_tr["roi"],
                            "n_test": s_te["n"], "roi_test": s_te["roi"],
                            "delta_train": delta_tr, "delta_test": delta_te,
                        })
                        print(f"{min_hist:>8} {thr:>10} {yield_type:>20} {direction:>10} | "
                              f"{s_tr['n']:>8} {s_tr['roi']:>7.1f}% {s_te['n']:>8} {s_te['roi']:>7.1f}% "
                              f"{delta_tr:>+9.1f}pp {delta_te:>+9.1f}pp")

    # Sort by test delta
    results.sort(key=lambda r: r["delta_test"], reverse=True)
    if results:
        print(f"\nTop 5 by TEST delta:")
        for r in results[:5]:
            print(f"  hist>={r['min_hist']}, {r['yield_type']} {r['direction']} {r['thr']}%: "
                  f"train ROI={r['roi_train']:.1f}% ({r['delta_train']:+.1f}pp), "
                  f"test ROI={r['roi_test']:.1f}% ({r['delta_test']:+.1f}pp)")

        print(f"\nBottom 5 by TEST delta (worst filters):")
        for r in results[-5:]:
            print(f"  hist>={r['min_hist']}, {r['yield_type']} {r['direction']} {r['thr']}%: "
                  f"train ROI={r['roi_train']:.1f}% ({r['delta_train']:+.1f}pp), "
                  f"test ROI={r['roi_test']:.1f}% ({r['delta_test']:+.1f}pp)")

    # ── Step 10: Rolling window stability ────────────────────────────────
    print("\n" + "=" * 80)
    print("STEP 10: Rolling window stability check")
    print("=" * 80)

    # Check if yield's predictive power is stable across time windows
    # Divide bets into 4 quartiles chronologically
    q_size = len(all_bets_sorted) // 4
    for qi in range(4):
        q_start = qi * q_size
        q_end = (qi + 1) * q_size if qi < 3 else len(all_bets_sorted)
        q_bets = all_bets_sorted[q_start:q_end]
        q_with_hist = [b for b in q_bets if b["combined_yield_n"] >= 5]
        if len(q_with_hist) < 20:
            continue
        pos = [b for b in q_with_hist if b["combined_yield_roi"] >= 0]
        neg = [b for b in q_with_hist if b["combined_yield_roi"] < 0]
        print(f"\n  Q{qi+1} ({q_bets[0]['timestamp'][:10]} to {q_bets[-1]['timestamp'][:10]}):")
        if len(pos) >= 5:
            sp = stats_report(pos, f"yield >= 0")
            print_stats(sp)
        if len(neg) >= 5:
            sn = stats_report(neg, f"yield < 0")
            print_stats(sn)

    # ── Final summary ────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    print("""
Key questions answered:
1. Does team yield (chronological ROI) predict future bet outcomes?
2. Can filtering by team yield improve ROI of existing strategies?
3. Is the signal stable across time and leagues?

See results above for detailed analysis.
If no filter shows consistent improvement in BOTH train and test sets,
team yield is NOT a viable filter and should be DISCARDED.
""")


if __name__ == "__main__":
    main()
