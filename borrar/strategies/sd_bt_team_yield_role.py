"""
Team Yield BY ROLE Filter Analysis — H87
Tests whether historical team performance IN ITS SPECIFIC ROLE
(home-as-home, away-as-away) predicts future bet outcomes.

DIFFERENT from H82-H86 (sd_bt_team_yield.py) which mixed roles.
Here we compute:
  - home_team_home_roi: ROI of the home team ONLY in its prior HOME matches
  - away_team_away_roi: ROI of the away team ONLY in its prior AWAY matches
  - role_balance: home_team_home_roi - away_team_away_roi

Edge thesis: Teams have different profiles home vs away.
A team profitable at home but weak away (or vice versa) carries
role-specific information the generic yield ignores.
"""

import os, glob, csv, math, json, sys
from collections import defaultdict, Counter
from datetime import datetime, timedelta

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
    matches.sort(key=lambda m: m["timestamp"])
    return matches

# ── Strategy trigger replication ─────────────────────────────────────────
# (copied from sd_bt_team_yield.py)

def _get_over_field(total_goals):
    line = total_goals + 0.5
    mapping = {
        0.5: "back_over05", 1.5: "back_over15", 2.5: "back_over25",
        3.5: "back_over35", 4.5: "back_over45", 5.5: "back_over55",
        6.5: "back_over65",
    }
    return mapping.get(line)

def detect_clustering(rows, min_min=15, max_min=80, sot_min=3, min_dur=1):
    for idx in range(1, len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
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
        sot_l = _f(row.get("tiros_puerta_local", "")) or 0
        sot_v = _f(row.get("tiros_puerta_visitante", "")) or 0
        if max(int(sot_l), int(sot_v)) < sot_min:
            continue
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
        return {"minuto": m, "odds": odds, "total_goals_at_trigger": total, "over_field": over_field, "entry_idx": entry_idx}
    return None

def detect_pressure(rows, min_min=65, max_min=75, min_dur=1):
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
        return {"minuto": m, "odds": odds, "total_goals_at_trigger": total, "over_field": over_field, "entry_idx": entry_idx}
    return None

def detect_xg_underperf(rows, min_min=25, max_min=85, xg_excess=0.5, min_dur=1):
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
        return {"minuto": m, "odds": odds, "total_goals_at_trigger": total, "team_losing": team_losing, "entry_idx": entry_idx}
    return None

def detect_any_leader_strategy(rows, min_min=70, max_min=85):
    for idx in range(len(rows)):
        row = rows[idx]
        m = _f(row.get("minuto", ""))
        if m is None or m < min_min or m > max_min:
            continue
        gl = _i(row.get("goles_local", "")) or 0
        gv = _i(row.get("goles_visitante", "")) or 0
        if gl == gv:
            continue
        if gl > gv:
            odds = _f(row.get("back_home", ""))
        else:
            odds = _f(row.get("back_away", ""))
        if odds is None or odds < 1.05 or odds > 10.0:
            continue
        return {"minuto": m, "odds": odds, "leader": "local" if gl > gv else "visitante", "gl": gl, "gv": gv}
    return None

def detect_cs_strategy(rows, min_min=75, max_min=90):
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
        return {"minuto": m, "odds": odds, "score": score}
    return None

def detect_under_strategy(rows, min_min=70, max_min=85):
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
        under_fields = {"back_under25": 2.5, "back_under35": 3.5, "back_under45": 4.5}
        for field, line in under_fields.items():
            if total >= line:
                continue
            odds = _f(row.get(field, ""))
            if odds is None or odds < 1.05 or odds > 10.0:
                continue
            return {"minuto": m, "odds": odds, "under_line": line, "total_at_trigger": total}
    return None

def detect_draw_strategy(rows, min_min=60, max_min=85):
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
        return {"minuto": m, "odds": odds, "score": (gl, gv)}
    return None


# ── Main analysis ────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("TEAM YIELD BY ROLE FILTER ANALYSIS — H87")
    print("Different from H82-H86: yield computed PER ROLE")
    print("  home_team -> only prior HOME matches")
    print("  away_team -> only prior AWAY matches")
    print("=" * 80)

    team_lookup = load_team_lookup()
    print(f"\nTeam lookup: {len(team_lookup)} entries")

    matches = load_matches()
    print(f"Loaded matches: {len(matches)} (sorted by timestamp)")

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
        trig = detect_clustering(rows)
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
        trig = detect_pressure(rows)
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
        trig = detect_xg_underperf(rows)
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
        trig = detect_any_leader_strategy(rows)
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
        trig = detect_cs_strategy(rows)
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
        trig = detect_under_strategy(rows)
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
        trig = detect_draw_strategy(rows)
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

    # ── Step 2: Build chronological team yield BY ROLE ──────────────────
    print("\n" + "=" * 80)
    print("STEP 2: Building chronological team yield BY ROLE")
    print("  home_stats[team] = only when team plays as HOME")
    print("  away_stats[team] = only when team plays as AWAY")
    print("=" * 80)

    all_bets_sorted = sorted(all_bets, key=lambda b: b["timestamp"])

    # Role-specific running totals
    # home_running[team] = {n, wins, pl} -- only bets where this team was HOME
    # away_running[team] = {n, wins, pl} -- only bets where this team was AWAY
    home_running = defaultdict(lambda: {"n": 0, "wins": 0, "pl": 0.0})
    away_running = defaultdict(lambda: {"n": 0, "wins": 0, "pl": 0.0})

    for b in all_bets_sorted:
        home = b["home_team"]
        away = b["away_team"]

        # Snapshot BEFORE updating
        h_home = home_running[home].copy()  # home team's history AS HOME
        a_away = away_running[away].copy()  # away team's history AS AWAY

        b["home_as_home_n"] = h_home["n"]
        b["home_as_home_roi"] = (h_home["pl"] / (h_home["n"] * STAKE) * 100) if h_home["n"] > 0 else 0
        b["home_as_home_wr"] = (h_home["wins"] / h_home["n"] * 100) if h_home["n"] > 0 else 0

        b["away_as_away_n"] = a_away["n"]
        b["away_as_away_roi"] = (a_away["pl"] / (a_away["n"] * STAKE) * 100) if a_away["n"] > 0 else 0
        b["away_as_away_wr"] = (a_away["wins"] / a_away["n"] * 100) if a_away["n"] > 0 else 0

        # Role balance: positive = home team historically better at home
        b["role_balance"] = b["home_as_home_roi"] - b["away_as_away_roi"]

        # Also compute: home team's away history and away team's home history (for cross-role comparison)
        h_away = away_running[home].copy()  # home team's history when playing AWAY
        a_home = home_running[away].copy()  # away team's history when playing HOME

        b["home_as_away_n"] = h_away["n"]
        b["home_as_away_roi"] = (h_away["pl"] / (h_away["n"] * STAKE) * 100) if h_away["n"] > 0 else 0

        b["away_as_home_n"] = a_home["n"]
        b["away_as_home_roi"] = (a_home["pl"] / (a_home["n"] * STAKE) * 100) if a_home["n"] > 0 else 0

        # Role divergence: how different is a team's home vs away performance?
        # High divergence = team is very different at home vs away
        if h_home["n"] >= 2 and h_away["n"] >= 2:
            b["home_team_role_divergence"] = abs(b["home_as_home_roi"] - b["home_as_away_roi"])
        else:
            b["home_team_role_divergence"] = None

        if a_home["n"] >= 2 and a_away["n"] >= 2:
            b["away_team_role_divergence"] = abs(b["away_as_away_roi"] - b["away_as_home_roi"])
        else:
            b["away_team_role_divergence"] = None

        # Update running totals (AFTER snapshot)
        # This bet's home team gets a HOME entry
        home_running[home]["n"] += 1
        home_running[home]["wins"] += 1 if b["won"] else 0
        home_running[home]["pl"] += b["pl"]

        # This bet's away team gets an AWAY entry
        away_running[away]["n"] += 1
        away_running[away]["wins"] += 1 if b["won"] else 0
        away_running[away]["pl"] += b["pl"]

    # Coverage stats
    print("\nRole-specific history coverage:")
    for min_hist in [2, 3, 5, 7, 10]:
        n_home = sum(1 for b in all_bets_sorted if b["home_as_home_n"] >= min_hist)
        n_away = sum(1 for b in all_bets_sorted if b["away_as_away_n"] >= min_hist)
        n_both = sum(1 for b in all_bets_sorted
                     if b["home_as_home_n"] >= min_hist and b["away_as_away_n"] >= min_hist)
        print(f"  >= {min_hist} prior role-matches: home={n_home}, away={n_away}, both={n_both}")

    # ── Step 3: Role-based yield analysis ──────────────────────────────
    print("\n" + "=" * 80)
    print("STEP 3: Role-based yield as predictor — overall analysis")
    print("=" * 80)

    # 3A: Role balance (home_as_home_roi - away_as_away_roi) as predictor
    print("\n--- 3A: Role balance as predictor ---")
    for min_hist in [3, 5]:
        bets_h = [b for b in all_bets_sorted
                  if b["home_as_home_n"] >= min_hist and b["away_as_away_n"] >= min_hist]
        if len(bets_h) < 40:
            print(f"  min_hist={min_hist}: only {len(bets_h)} bets with both roles, skipping")
            continue
        print(f"\n  Min role history: {min_hist} (N with both roles: {len(bets_h)})")
        for thr in [-40, -30, -20, -10, 0, 10, 20, 30, 40]:
            above = [b for b in bets_h if b["role_balance"] >= thr]
            below = [b for b in bets_h if b["role_balance"] < thr]
            if len(above) >= 20 and len(below) >= 20:
                sa = stats_report(above, f"balance >= {thr}%")
                sb = stats_report(below, f"balance < {thr}%")
                delta = sa["roi"] - sb["roi"]
                print(f"  thr={thr:+4d}%: ABOVE N={sa['n']},ROI={sa['roi']:+.1f}% | "
                      f"BELOW N={sb['n']},ROI={sb['roi']:+.1f}% | delta={delta:+.1f}pp")

    # 3B: Individual role yields as predictors
    print("\n--- 3B: Individual role yields ---")
    for min_hist in [3, 5]:
        bets_home = [b for b in all_bets_sorted if b["home_as_home_n"] >= min_hist]
        bets_away = [b for b in all_bets_sorted if b["away_as_away_n"] >= min_hist]
        print(f"\n  Min role history: {min_hist}")
        print(f"  Bets with home-as-home history: {len(bets_home)}")
        print(f"  Bets with away-as-away history: {len(bets_away)}")

        for yield_name, yield_key, pool in [
            ("home_as_home_roi", "home_as_home_roi", bets_home),
            ("away_as_away_roi", "away_as_away_roi", bets_away),
        ]:
            if len(pool) < 40:
                continue
            for thr in [-30, -20, -10, 0, 10, 20]:
                above = [b for b in pool if b[yield_key] >= thr]
                below = [b for b in pool if b[yield_key] < thr]
                if len(above) >= 15 and len(below) >= 15:
                    sa = stats_report(above, f"{yield_name} >= {thr}%")
                    sb = stats_report(below, f"{yield_name} < {thr}%")
                    delta = sa["roi"] - sb["roi"]
                    print(f"    {yield_name} thr={thr:+4d}%: ABOVE N={sa['n']},ROI={sa['roi']:+.1f}% | "
                          f"BELOW N={sb['n']},ROI={sb['roi']:+.1f}% | delta={delta:+.1f}pp")

    # ── Step 4: Per-strategy analysis ──────────────────────────────────
    print("\n" + "=" * 80)
    print("STEP 4: Role-based yield filter per strategy")
    print("=" * 80)

    for strat_name in ["goal_clustering", "pressure_cooker", "xg_underperf",
                        "leader_late", "cs_late", "under_late", "draw_late"]:
        strat_bets = [b for b in all_bets_sorted if b["strategy"] == strat_name]
        if len(strat_bets) < 30:
            continue

        print(f"\n{'='*60}")
        print(f"Strategy: {strat_name} (N={len(strat_bets)})")
        print(f"{'='*60}")
        s_base = stats_report(strat_bets, "BASELINE")
        print_stats(s_base)

        for min_hist in [3, 5, 7]:
            bets_h = [b for b in strat_bets
                      if b["home_as_home_n"] >= min_hist and b["away_as_away_n"] >= min_hist]
            if len(bets_h) < 20:
                continue

            print(f"\n  Min role history: {min_hist} (N with both roles: {len(bets_h)})")

            # Role balance filter
            for thr in [-40, -20, 0, 20, 40]:
                for direction in ["above", "below"]:
                    if direction == "above":
                        kept = [b for b in bets_h if b["role_balance"] >= thr]
                    else:
                        kept = [b for b in bets_h if b["role_balance"] < thr]
                    if len(kept) >= 15:
                        sk = stats_report(kept, f"balance {'>='+str(thr) if direction=='above' else '<'+str(thr)}%")
                        delta = sk["roi"] - s_base["roi"]
                        print(f"    balance {direction} {thr:+d}%: N={sk['n']}, ROI={sk['roi']:+.1f}%, delta={delta:+.1f}pp")

            # Individual role filters
            for yield_key in ["home_as_home_roi", "away_as_away_roi"]:
                pool = [b for b in strat_bets if b[yield_key.split("_")[0] + "_as_" + yield_key.split("_")[2] + "_n"] >= min_hist]
                if len(pool) < 20:
                    continue
                for thr in [-20, 0, 20]:
                    above = [b for b in pool if b[yield_key] >= thr]
                    if len(above) >= 10 and len(above) < len(pool):
                        sa = stats_report(above, f"{yield_key} >= {thr}%")
                        delta = sa["roi"] - s_base["roi"]
                        print(f"    {yield_key} >= {thr}%: N={sa['n']}, ROI={sa['roi']:+.1f}%, delta={delta:+.1f}pp")

    # ── Step 5: Directional vs Non-directional analysis ─────────────────
    print("\n" + "=" * 80)
    print("STEP 5: Role balance by market type (directional vs non-directional)")
    print("=" * 80)

    directional = ["leader_late"]  # Market depends on which team
    non_directional = ["goal_clustering", "pressure_cooker", "xg_underperf",
                       "cs_late", "under_late", "draw_late"]  # Market about total/draw

    for label, strat_list in [("DIRECTIONAL (leader)", directional),
                               ("NON-DIRECTIONAL (over/under/draw/cs)", non_directional)]:
        pool = [b for b in all_bets_sorted
                if b["strategy"] in strat_list
                and b["home_as_home_n"] >= 3
                and b["away_as_away_n"] >= 3]
        if len(pool) < 30:
            continue
        print(f"\n  {label}: N={len(pool)}")
        s_base = stats_report(pool, "baseline")
        print_stats(s_base)
        for thr in [-20, 0, 20]:
            above = [b for b in pool if b["role_balance"] >= thr]
            below = [b for b in pool if b["role_balance"] < thr]
            if len(above) >= 10 and len(below) >= 10:
                sa = stats_report(above, f"balance >= {thr}%")
                sb = stats_report(below, f"balance < {thr}%")
                print(f"    thr={thr:+d}%: ABOVE N={sa['n']},ROI={sa['roi']:+.1f}% | "
                      f"BELOW N={sb['n']},ROI={sb['roi']:+.1f}% | delta={sa['roi']-sb['roi']:+.1f}pp")

    # ── Step 6: Comprehensive grid search (all strategies combined) ─────
    print("\n" + "=" * 80)
    print("STEP 6: Comprehensive grid search — all strategies combined")
    print("=" * 80)

    split_idx = int(len(all_bets_sorted) * 0.7)
    train_all = all_bets_sorted[:split_idx]
    test_all = all_bets_sorted[split_idx:]

    s_train_base = stats_report(train_all, "TRAIN baseline")
    s_test_base = stats_report(test_all, "TEST baseline")
    print(f"\nPortfolio baseline:")
    print_stats(s_train_base)
    print_stats(s_test_base)

    print(f"\n{'MinHist':>8} {'Threshold':>10} {'YieldType':>22} {'Dir':>6} | "
          f"{'N_tr':>6} {'ROI_tr':>8} {'N_te':>6} {'ROI_te':>8} {'D_tr':>8} {'D_te':>8}")
    print("-" * 110)

    results = []
    for min_hist in [3, 5, 7, 10]:
        for thr in [-40, -30, -20, -10, 0, 10, 20, 30, 40]:
            for yield_type in ["role_balance", "home_as_home_roi", "away_as_away_roi"]:
                # Determine which N field to check for minimum history
                if yield_type == "role_balance":
                    n_check = lambda b, mh: b["home_as_home_n"] >= mh and b["away_as_away_n"] >= mh
                elif yield_type == "home_as_home_roi":
                    n_check = lambda b, mh: b["home_as_home_n"] >= mh
                else:
                    n_check = lambda b, mh: b["away_as_away_n"] >= mh

                for direction in ["keep_above", "keep_below"]:
                    if direction == "keep_above":
                        tr_f = [b for b in train_all
                                if (n_check(b, min_hist) and b.get(yield_type, 0) >= thr) or not n_check(b, min_hist)]
                        te_f = [b for b in test_all
                                if (n_check(b, min_hist) and b.get(yield_type, 0) >= thr) or not n_check(b, min_hist)]
                    else:
                        tr_f = [b for b in train_all
                                if n_check(b, min_hist) and b.get(yield_type, 0) < thr]
                        te_f = [b for b in test_all
                                if n_check(b, min_hist) and b.get(yield_type, 0) < thr]

                    if len(tr_f) < 30 or len(te_f) < 10:
                        continue

                    s_tr = stats_report(tr_f)
                    s_te = stats_report(te_f)
                    delta_tr = s_tr["roi"] - s_train_base["roi"]
                    delta_te = s_te["roi"] - s_test_base["roi"]

                    if abs(delta_tr) > 3 or abs(delta_te) > 3:
                        results.append({
                            "min_hist": min_hist, "thr": thr, "yield_type": yield_type,
                            "direction": direction,
                            "n_train": s_tr["n"], "roi_train": s_tr["roi"],
                            "n_test": s_te["n"], "roi_test": s_te["roi"],
                            "delta_train": delta_tr, "delta_test": delta_te,
                        })
                        print(f"{min_hist:>8} {thr:>10} {yield_type:>22} {direction:>6} | "
                              f"{s_tr['n']:>6} {s_tr['roi']:>+7.1f}% {s_te['n']:>6} {s_te['roi']:>+7.1f}% "
                              f"{delta_tr:>+7.1f}pp {delta_te:>+7.1f}pp")

    # Sort by test delta
    results.sort(key=lambda r: r["delta_test"], reverse=True)
    if results:
        print(f"\nTop 5 by TEST delta:")
        for r in results[:5]:
            print(f"  hist>={r['min_hist']}, {r['yield_type']} {r['direction']} {r['thr']}%: "
                  f"train ROI={r['roi_train']:.1f}% ({r['delta_train']:+.1f}pp), "
                  f"test ROI={r['roi_test']:.1f}% ({r['delta_test']:+.1f}pp)")

        print(f"\nBottom 5 by TEST delta:")
        for r in results[-5:]:
            print(f"  hist>={r['min_hist']}, {r['yield_type']} {r['direction']} {r['thr']}%: "
                  f"train ROI={r['roi_train']:.1f}% ({r['delta_train']:+.1f}pp), "
                  f"test ROI={r['roi_test']:.1f}% ({r['delta_test']:+.1f}pp)")

        # Find filters that improve BOTH train and test
        both_positive = [r for r in results if r["delta_train"] > 0 and r["delta_test"] > 0]
        print(f"\nFilters that improve BOTH train AND test: {len(both_positive)}")
        for r in both_positive[:10]:
            print(f"  hist>={r['min_hist']}, {r['yield_type']} {r['direction']} {r['thr']}%: "
                  f"train +{r['delta_train']:.1f}pp, test +{r['delta_test']:.1f}pp")

    # ── Step 7: Per-strategy train/test validation ──────────────────────
    print("\n" + "=" * 80)
    print("STEP 7: Per-strategy train/test validation (role-based)")
    print("=" * 80)

    for strat_name in ["goal_clustering", "pressure_cooker", "xg_underperf",
                        "leader_late", "cs_late", "under_late", "draw_late"]:
        strat_bets = sorted([b for b in all_bets_sorted if b["strategy"] == strat_name],
                            key=lambda b: b["timestamp"])
        if len(strat_bets) < 40:
            continue

        split = int(len(strat_bets) * 0.7)
        train = strat_bets[:split]
        test = strat_bets[split:]

        print(f"\n{'='*60}")
        print(f"Strategy: {strat_name} (Train={len(train)}, Test={len(test)})")
        print(f"{'='*60}")

        s_train_b = stats_report(train, "TRAIN baseline")
        s_test_b = stats_report(test, "TEST baseline")
        print_stats(s_train_b)
        print_stats(s_test_b)

        best_filter = None
        best_combo_score = -999

        for min_hist in [3, 5, 7]:
            for thr in [-40, -30, -20, -10, 0, 10, 20, 30]:
                for yield_type in ["role_balance", "home_as_home_roi", "away_as_away_roi"]:
                    if yield_type == "role_balance":
                        n_ok = lambda b, mh=min_hist: b["home_as_home_n"] >= mh and b["away_as_away_n"] >= mh
                    elif yield_type == "home_as_home_roi":
                        n_ok = lambda b, mh=min_hist: b["home_as_home_n"] >= mh
                    else:
                        n_ok = lambda b, mh=min_hist: b["away_as_away_n"] >= mh

                    for direction in ["keep_above", "keep_below"]:
                        if direction == "keep_above":
                            tr_f = [b for b in train if (n_ok(b) and b.get(yield_type, 0) >= thr) or not n_ok(b)]
                            te_f = [b for b in test if (n_ok(b) and b.get(yield_type, 0) >= thr) or not n_ok(b)]
                        else:
                            tr_f = [b for b in train if n_ok(b) and b.get(yield_type, 0) < thr]
                            te_f = [b for b in test if n_ok(b) and b.get(yield_type, 0) < thr]

                        if len(tr_f) < 15 or len(te_f) < 5:
                            continue

                        s_tr = stats_report(tr_f)
                        s_te = stats_report(te_f)
                        d_tr = s_tr["roi"] - s_train_b["roi"]
                        d_te = s_te["roi"] - s_test_b["roi"]

                        # Score: positive in both sets, weighted by test
                        if d_tr > 0 and d_te > 0:
                            combo_score = d_te * 2 + d_tr
                            if combo_score > best_combo_score:
                                best_combo_score = combo_score
                                best_filter = {
                                    "min_hist": min_hist, "thr": thr,
                                    "yield_type": yield_type, "direction": direction,
                                    "train_n": s_tr["n"], "train_roi": s_tr["roi"], "train_delta": d_tr,
                                    "test_n": s_te["n"], "test_roi": s_te["roi"], "test_delta": d_te,
                                }

        if best_filter and best_combo_score > 5:
            bf = best_filter
            print(f"\n  BEST FILTER: hist>={bf['min_hist']}, {bf['yield_type']} {bf['direction']} {bf['thr']}%")
            print(f"    Train: N={bf['train_n']}, ROI={bf['train_roi']:.1f}%, delta={bf['train_delta']:+.1f}pp")
            print(f"    Test:  N={bf['test_n']}, ROI={bf['test_roi']:.1f}%, delta={bf['test_delta']:+.1f}pp")
            if bf['test_delta'] > 5:
                print(f"    ** PROMISING: both train and test positive, test delta > 5pp **")
            else:
                print(f"    ** MARGINAL: test improvement is small **")
        else:
            print(f"\n  No filter found with positive delta in both train and test sets")

    # ── Step 8: Rolling window stability ────────────────────────────────
    print("\n" + "=" * 80)
    print("STEP 8: Rolling window stability (role balance)")
    print("=" * 80)

    q_size = len(all_bets_sorted) // 4
    for qi in range(4):
        q_start = qi * q_size
        q_end = (qi + 1) * q_size if qi < 3 else len(all_bets_sorted)
        q_bets = all_bets_sorted[q_start:q_end]
        q_with_hist = [b for b in q_bets
                       if b["home_as_home_n"] >= 3 and b["away_as_away_n"] >= 3]
        if len(q_with_hist) < 20:
            print(f"  Q{qi+1}: insufficient history ({len(q_with_hist)} bets with role data)")
            continue
        pos = [b for b in q_with_hist if b["role_balance"] >= 0]
        neg = [b for b in q_with_hist if b["role_balance"] < 0]
        ts_start = q_bets[0]['timestamp'][:10] if q_bets else "?"
        ts_end = q_bets[-1]['timestamp'][:10] if q_bets else "?"
        print(f"\n  Q{qi+1} ({ts_start} to {ts_end}): {len(q_with_hist)} bets with role data")
        if len(pos) >= 5:
            sp = stats_report(pos, f"balance >= 0")
            print_stats(sp)
        if len(neg) >= 5:
            sn = stats_report(neg, f"balance < 0")
            print_stats(sn)
        if len(pos) >= 5 and len(neg) >= 5:
            sp = stats_report(pos)
            sn = stats_report(neg)
            print(f"    Delta ROI: {sp['roi'] - sn['roi']:+.1f}pp")

    # ── Step 9: Compare role-specific yield vs generic yield ────────────
    print("\n" + "=" * 80)
    print("STEP 9: Role-specific yield vs generic yield comparison")
    print("=" * 80)

    # Also compute generic yield for comparison
    generic_running = defaultdict(lambda: {"n": 0, "wins": 0, "pl": 0.0})
    for b in all_bets_sorted:
        home = b["home_team"]
        away = b["away_team"]
        g_home = generic_running[home].copy()
        g_away = generic_running[away].copy()

        b["generic_home_roi"] = (g_home["pl"] / (g_home["n"] * STAKE) * 100) if g_home["n"] > 0 else 0
        b["generic_away_roi"] = (g_away["pl"] / (g_away["n"] * STAKE) * 100) if g_away["n"] > 0 else 0
        b["generic_home_n"] = g_home["n"]
        b["generic_away_n"] = g_away["n"]
        b["generic_balance"] = b["generic_home_roi"] - b["generic_away_roi"]

        generic_running[home]["n"] += 1
        generic_running[home]["wins"] += 1 if b["won"] else 0
        generic_running[home]["pl"] += b["pl"]
        generic_running[away]["n"] += 1
        generic_running[away]["wins"] += 1 if b["won"] else 0
        generic_running[away]["pl"] += b["pl"]

    # Compare predictive power
    min_hist = 3
    bets_with_both = [b for b in all_bets_sorted
                      if b["home_as_home_n"] >= min_hist and b["away_as_away_n"] >= min_hist
                      and b["generic_home_n"] >= min_hist and b["generic_away_n"] >= min_hist]

    if len(bets_with_both) >= 40:
        print(f"\nBets with both role and generic history (>= {min_hist}): {len(bets_with_both)}")

        # Correlation between role balance and win
        wins = [1 if b["won"] else 0 for b in bets_with_both]
        role_bals = [b["role_balance"] for b in bets_with_both]
        generic_bals = [b["generic_balance"] for b in bets_with_both]

        # Simple correlation
        def pearson_r(x, y):
            n = len(x)
            if n < 3:
                return 0
            mx = sum(x) / n
            my = sum(y) / n
            num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
            dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
            dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
            if dx == 0 or dy == 0:
                return 0
            return round(num / (dx * dy), 4)

        r_role = pearson_r(role_bals, wins)
        r_generic = pearson_r(generic_bals, wins)
        print(f"  Pearson r (role_balance vs win): {r_role}")
        print(f"  Pearson r (generic_balance vs win): {r_generic}")
        print(f"  Role balance is {'MORE' if abs(r_role) > abs(r_generic) else 'LESS'} "
              f"predictive than generic balance")

        # Also check: role balance vs PL
        pls = [b["pl"] for b in bets_with_both]
        r_role_pl = pearson_r(role_bals, pls)
        r_generic_pl = pearson_r(generic_bals, pls)
        print(f"  Pearson r (role_balance vs P/L): {r_role_pl}")
        print(f"  Pearson r (generic_balance vs P/L): {r_generic_pl}")

    # ── Final summary ────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("FINAL SUMMARY — H87: Team Yield by Role")
    print("=" * 80)
    print("""
Key questions:
1. Does role-specific yield (home-as-home, away-as-away) predict future bet outcomes
   better than generic yield?
2. Does 'role balance' (home_roi_as_home - away_roi_as_away) provide actionable signal?
3. Is the signal stable across time (quarterly windows)?
4. Does it matter more for directional vs non-directional markets?

VERDICT: Check steps 3-9 above.
If no filter shows consistent improvement in BOTH train and test across ALL strategies,
role-specific yield is NOT a viable filter and H87 should be DISCARDED.
""")


if __name__ == "__main__":
    main()
