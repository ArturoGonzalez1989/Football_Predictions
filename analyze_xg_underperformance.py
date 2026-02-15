"""
xG Underperformance Analyzer - Regression to the Mean Strategy
================================================================
Scans all finished match CSVs to find moments where a team's xG
significantly exceeds their actual goals (underperformance), then
evaluates whether betting on "more goals" or "team scores" is profitable.

Key concept:
  If a team creates chances worth xG=1.5 but has scored 0 goals,
  regression to the mean suggests they WILL score. The market may
  under-price this probability.

Simulated bets:
  A) Back Over (current_total + 0.5) goals - most liquid, practical
  B) Back the underperforming team (match winner) - higher odds/risk
  C) Lay Draw - if one team should score, draw becomes less likely

Stake: 10 EUR flat
Commission: 5% on winnings (Betfair Exchange)
"""

import csv
import glob
import os
from dataclasses import dataclass, field
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "betfair_scraper", "data")
STAKE = 10.0
COMMISSION = 0.05

# ── Helpers ──────────────────────────────────────────────────────────────

def to_float(val):
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def to_int(val):
    f = to_float(val)
    return int(f) if f is not None else None

def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

def calc_pl(won: bool, odds: Optional[float]) -> float:
    """P/L for holding until FT."""
    if won and odds and odds > 1:
        return round((odds - 1) * STAKE * (1 - COMMISSION), 2)
    return -STAKE


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class XGTrigger:
    match_name: str
    match_id: str
    trigger_minute: float
    # Which team is underperforming
    team: str                     # "home" or "away"
    team_xg: float                # xG of underperforming team at trigger
    team_goals: int               # goals of that team at trigger
    xg_excess: float              # xG - goals
    opp_xg: float                 # opponent xG at trigger
    opp_goals: int                # opponent goals at trigger
    # Score at trigger
    score_at_trigger: str         # e.g., "0-0", "1-0"
    total_goals_at_trigger: int
    # Stats at trigger
    shots_team: Optional[int] = None
    sot_team: Optional[int] = None
    big_chances_team: Optional[int] = None
    dangerous_attacks_team: Optional[int] = None
    poss_team: Optional[float] = None
    momentum_team: Optional[float] = None
    # Odds at trigger
    back_team: Optional[float] = None      # back odds for the underperforming team
    back_over_next: Optional[float] = None  # back Over (total+0.5) at trigger
    back_draw: Optional[float] = None       # back draw at trigger
    lay_draw: Optional[float] = None        # lay draw at trigger
    # Final result
    ft_score: str = ""
    ft_goals_home: int = 0
    ft_goals_away: int = 0
    # Outcomes
    team_scored_after: bool = False       # did the team score at least 1 more goal?
    team_goals_after: int = 0             # how many more goals did the team score?
    total_goals_after: int = 0            # total goals scored after trigger
    more_goals_scored: bool = False       # was at least 1 more goal scored by anyone?
    team_won: bool = False                # did the underperforming team win?
    draw_result: bool = False             # did match end in draw?
    next_goal_team: Optional[str] = None  # who scored next: "home", "away", None
    next_goal_minute: Optional[float] = None


# ── Match analysis ───────────────────────────────────────────────────────

def get_over_odds_field(total_goals_at_trigger: int) -> str:
    """Return the CSV column for Back Over (total+0.5)."""
    target = total_goals_at_trigger + 0.5
    field_map = {
        0.5: "back_over05",
        1.5: "back_over15",
        2.5: "back_over25",
        3.5: "back_over35",
        4.5: "back_over45",
    }
    return field_map.get(target, "")


def analyze_all_matches():
    csv_files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")))
    print(f"Found {len(csv_files)} CSV files\n")

    all_triggers: list[XGTrigger] = []
    matches_analyzed = 0
    matches_with_xg = 0

    for csv_path in csv_files:
        rows = read_csv(csv_path)
        if len(rows) < 5:
            continue

        # Check if match is finished
        last_row = rows[-1]
        gl_final = to_float(last_row.get("goles_local"))
        gv_final = to_float(last_row.get("goles_visitante"))
        last_min = to_float(last_row.get("minuto"))

        if gl_final is None or gv_final is None:
            continue
        if last_min is not None and last_min < 80:
            continue

        matches_analyzed += 1
        match_id = os.path.basename(csv_path).replace("partido_", "").replace(".csv", "")
        match_name = last_row.get("evento", match_id).strip() or match_id
        if not match_name or match_name == match_id:
            match_name = match_id.replace("-apuestas-", " ").rsplit(" ", 1)[0].replace("-", " ").title()

        ft_gl = int(gl_final)
        ft_gv = int(gv_final)
        ft_score = f"{ft_gl}-{ft_gv}"

        # Check if match has xG data at all
        has_xg = False
        for row in rows:
            if to_float(row.get("xg_local")) is not None:
                has_xg = True
                break
        if not has_xg:
            continue
        matches_with_xg += 1

        # Scan minute-by-minute for xG underperformance triggers
        # We want the FIRST occurrence for each team where xG - goals >= threshold
        # We'll collect all thresholds at once for analysis
        triggered_home = set()  # set of threshold values already triggered for home
        triggered_away = set()

        for i, row in enumerate(rows):
            m = to_float(row.get("minuto"))
            if m is None or m < 15:
                continue  # Too early for meaningful xG

            xg_h = to_float(row.get("xg_local"))
            xg_a = to_float(row.get("xg_visitante"))
            gl = to_int(row.get("goles_local"))
            gv = to_int(row.get("goles_visitante"))

            if xg_h is None or xg_a is None or gl is None or gv is None:
                continue

            # Check home team underperformance
            excess_h = xg_h - gl
            excess_a = xg_a - gv

            for team, excess, team_xg, team_goals, opp_xg, opp_goals, triggered_set in [
                ("home", excess_h, xg_h, gl, xg_a, gv, triggered_home),
                ("away", excess_a, xg_a, gv, xg_h, gl, triggered_away),
            ]:
                # Use 0.5 as base threshold (we'll filter later for sensitivity)
                threshold = 0.5
                if excess >= threshold and threshold not in triggered_set:
                    triggered_set.add(threshold)

                    total_at_trigger = gl + gv
                    score_at_trigger = f"{gl}-{gv}"

                    # Team-specific stats
                    suffix_t = "_local" if team == "home" else "_visitante"
                    shots_t = to_int(row.get(f"tiros{suffix_t}"))
                    sot_t = to_int(row.get(f"tiros_puerta{suffix_t}"))
                    bc_t = to_int(row.get(f"big_chances{suffix_t}"))
                    da_t = to_int(row.get(f"dangerous_attacks{suffix_t}"))
                    poss_t = to_float(row.get(f"posesion{suffix_t}"))
                    mom_t = to_float(row.get(f"momentum{suffix_t}"))

                    # Odds at trigger
                    back_team = to_float(row.get("back_home" if team == "home" else "back_away"))
                    back_draw_val = to_float(row.get("back_draw"))
                    lay_draw_val = to_float(row.get("lay_draw"))

                    over_field = get_over_odds_field(total_at_trigger)
                    back_over = to_float(row.get(over_field)) if over_field else None

                    # Track what happens AFTER trigger
                    team_goals_after_trigger = (ft_gl - gl) if team == "home" else (ft_gv - gv)
                    total_goals_after = (ft_gl + ft_gv) - total_at_trigger
                    team_scored = team_goals_after_trigger > 0
                    more_goals = total_goals_after > 0
                    team_won = (ft_gl > ft_gv) if team == "home" else (ft_gv > ft_gl)
                    draw_ft = ft_gl == ft_gv

                    # Next goal after trigger
                    next_goal_team_val = None
                    next_goal_min = None
                    for j in range(i + 1, len(rows)):
                        r2 = rows[j]
                        m2 = to_float(r2.get("minuto"))
                        g2h = to_int(r2.get("goles_local"))
                        g2v = to_int(r2.get("goles_visitante"))
                        if g2h is not None and g2v is not None:
                            if g2h > gl or g2v > gv:
                                if g2h > gl:
                                    next_goal_team_val = "home"
                                else:
                                    next_goal_team_val = "away"
                                next_goal_min = m2
                                break

                    t = XGTrigger(
                        match_name=match_name,
                        match_id=match_id,
                        trigger_minute=m,
                        team=team,
                        team_xg=round(team_xg, 4),
                        team_goals=team_goals,
                        xg_excess=round(excess, 4),
                        opp_xg=round(opp_xg, 4),
                        opp_goals=opp_goals,
                        score_at_trigger=score_at_trigger,
                        total_goals_at_trigger=total_at_trigger,
                        shots_team=shots_t,
                        sot_team=sot_t,
                        big_chances_team=bc_t,
                        dangerous_attacks_team=da_t,
                        poss_team=poss_t,
                        momentum_team=mom_t,
                        back_team=back_team,
                        back_over_next=back_over,
                        back_draw=back_draw_val,
                        lay_draw=lay_draw_val,
                        ft_score=ft_score,
                        ft_goals_home=ft_gl,
                        ft_goals_away=ft_gv,
                        team_scored_after=team_scored,
                        team_goals_after=team_goals_after_trigger,
                        total_goals_after=total_goals_after,
                        more_goals_scored=more_goals,
                        team_won=team_won,
                        draw_result=draw_ft,
                        next_goal_team=next_goal_team_val,
                        next_goal_minute=next_goal_min,
                    )
                    all_triggers.append(t)

    return matches_analyzed, matches_with_xg, all_triggers


# ── Simulation functions ─────────────────────────────────────────────────

def simulate_back_over(triggers: list[XGTrigger], label: str):
    """Simulate: Back Over (total_at_trigger + 0.5) goals."""
    bets = [t for t in triggers if t.back_over_next and t.back_over_next > 1.01]
    if not bets:
        return {"label": label, "n": 0, "wins": 0, "wr": 0, "pl": 0, "roi": 0, "bets": []}

    results = []
    cum_pl = 0
    for t in bets:
        won = t.more_goals_scored
        pl = calc_pl(won, t.back_over_next)
        cum_pl += pl
        results.append({
            "match": t.match_name, "team": t.team, "min": t.trigger_minute,
            "score": t.score_at_trigger, "xg_ex": t.xg_excess,
            "odds": t.back_over_next, "ft": t.ft_score, "won": won,
            "pl": pl, "cum_pl": round(cum_pl, 2),
        })

    wins = sum(1 for r in results if r["won"])
    total_pl = round(sum(r["pl"] for r in results), 2)
    return {
        "label": label, "n": len(bets), "wins": wins,
        "wr": round(wins / len(bets) * 100, 1),
        "pl": total_pl,
        "roi": round(total_pl / (len(bets) * STAKE) * 100, 1),
        "bets": results,
    }


def simulate_back_team(triggers: list[XGTrigger], label: str):
    """Simulate: Back the underperforming team (match winner)."""
    bets = [t for t in triggers if t.back_team and t.back_team > 1.01]
    if not bets:
        return {"label": label, "n": 0, "wins": 0, "wr": 0, "pl": 0, "roi": 0, "bets": []}

    results = []
    cum_pl = 0
    for t in bets:
        won = t.team_won
        pl = calc_pl(won, t.back_team)
        cum_pl += pl
        results.append({
            "match": t.match_name, "team": t.team, "min": t.trigger_minute,
            "score": t.score_at_trigger, "xg_ex": t.xg_excess,
            "odds": t.back_team, "ft": t.ft_score, "won": won,
            "pl": pl, "cum_pl": round(cum_pl, 2),
        })

    wins = sum(1 for r in results if r["won"])
    total_pl = round(sum(r["pl"] for r in results), 2)
    return {
        "label": label, "n": len(bets), "wins": wins,
        "wr": round(wins / len(bets) * 100, 1),
        "pl": total_pl,
        "roi": round(total_pl / (len(bets) * STAKE) * 100, 1),
        "bets": results,
    }


def simulate_lay_draw(triggers: list[XGTrigger], label: str):
    """Simulate: Lay the Draw (expecting underperforming team to break it)."""
    bets = [t for t in triggers if t.lay_draw and t.lay_draw > 1.01]
    if not bets:
        return {"label": label, "n": 0, "wins": 0, "wr": 0, "pl": 0, "roi": 0, "bets": []}

    results = []
    cum_pl = 0
    for t in bets:
        # Lay draw wins if match does NOT end in draw
        won = not t.draw_result
        if won:
            # We win the lay stake (STAKE)
            pl = round(STAKE * (1 - COMMISSION), 2)
        else:
            # We lose (lay_odds - 1) * STAKE
            pl = round(-(t.lay_draw - 1) * STAKE, 2)
        cum_pl += pl
        results.append({
            "match": t.match_name, "team": t.team, "min": t.trigger_minute,
            "score": t.score_at_trigger, "xg_ex": t.xg_excess,
            "odds": t.lay_draw, "ft": t.ft_score, "won": won,
            "pl": pl, "cum_pl": round(cum_pl, 2),
        })

    wins = sum(1 for r in results if r["won"])
    total_pl = round(sum(r["pl"] for r in results), 2)
    return {
        "label": label, "n": len(bets), "wins": wins,
        "wr": round(wins / len(bets) * 100, 1),
        "pl": total_pl,
        "roi": round(total_pl / (len(bets) * STAKE) * 100, 1),
        "bets": results,
    }


# ── Print helpers ────────────────────────────────────────────────────────

def print_summary(result: dict):
    print(f"  {'Strategy':<16s}: {result['label']}")
    print(f"  {'Bets':<16s}: {result['n']}")
    print(f"  {'Wins':<16s}: {result['wins']} ({result['wr']}%)")
    print(f"  {'P/L':<16s}: {'+' if result['pl'] >= 0 else ''}{result['pl']} EUR")
    print(f"  {'ROI':<16s}: {'+' if result['roi'] >= 0 else ''}{result['roi']}%")
    print()


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("  xG UNDERPERFORMANCE ANALYZER - Regression to the Mean Strategy")
    print("  Stake: 10 EUR | Commission: 5% | Data: all finished CSVs")
    print("=" * 80)
    print()

    matches_analyzed, matches_with_xg, all_triggers = analyze_all_matches()
    print(f"Matches analyzed:    {matches_analyzed}")
    print(f"Matches with xG:     {matches_with_xg}")
    print(f"xG Triggers (>=0.5): {len(all_triggers)}")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 1: RAW TRIGGER DATA
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 1: ALL TRIGGERS - xG excess >= 0.5")
    print("=" * 80)
    print()
    print(f"  {'Match':<28s} {'Team':>4s} {'Min':>4s} {'Score':>5s} {'xG':>5s} {'Gol':>3s} {'Exc':>5s} "
          f"{'SoT':>3s} {'BC':>3s} {'Sc?':>3s} {'+Gol':>4s} {'FT':>5s} {'Next':>4s}")
    print(f"  {'-'*28} {'----':>4s} {'----':>4s} {'-----':>5s} {'-----':>5s} {'---':>3s} {'-----':>5s} "
          f"{'---':>3s} {'---':>3s} {'---':>3s} {'----':>4s} {'-----':>5s} {'----':>4s}")

    for t in sorted(all_triggers, key=lambda x: x.trigger_minute):
        m = t.match_name[:26]
        tm = "H" if t.team == "home" else "A"
        sc = "Y" if t.team_scored_after else "N"
        sot = str(t.sot_team) if t.sot_team is not None else "-"
        bc = str(t.big_chances_team) if t.big_chances_team is not None else "-"
        ng = t.next_goal_team[0].upper() if t.next_goal_team else "-"
        print(f"  {m:<28s} {tm:>4s} {t.trigger_minute:>4.0f} {t.score_at_trigger:>5s} "
              f"{t.team_xg:>5.2f} {t.team_goals:>3d} {t.xg_excess:>5.2f} "
              f"{sot:>3s} {bc:>3s} {sc:>3s} {t.team_goals_after:>4d} {t.ft_score:>5s} {ng:>4s}")

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 2: CORE OUTCOME ANALYSIS
    # ══════════════════════════════════════════════════════════════════════
    print()
    print("=" * 80)
    print("  SECTION 2: OUTCOME ANALYSIS - Does the underperforming team score?")
    print("=" * 80)
    print()

    total = len(all_triggers)
    scored = sum(1 for t in all_triggers if t.team_scored_after)
    any_goal = sum(1 for t in all_triggers if t.more_goals_scored)
    team_won = sum(1 for t in all_triggers if t.team_won)
    next_is_team = sum(1 for t in all_triggers if t.next_goal_team == t.team)

    print(f"  Total triggers:                        {total}")
    print(f"  Team scores again:                     {scored}/{total} ({scored/total*100:.1f}%)")
    print(f"  At least 1 more goal (any team):       {any_goal}/{total} ({any_goal/total*100:.1f}%)")
    print(f"  Underperforming team wins:              {team_won}/{total} ({team_won/total*100:.1f}%)")
    print(f"  Next goal is by underperforming team:   {next_is_team}/{total} ({next_is_team/total*100:.1f}%)")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 3: DETECTION TIMING
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 3: DETECTION TIMING - When is underperformance detected?")
    print("=" * 80)
    print()

    time_ranges = [
        ("Min 15-29", 15, 30),
        ("Min 30-44", 30, 45),
        ("Min 45-59", 45, 60),
        ("Min 60-74", 60, 75),
        ("Min 75+  ", 75, 120),
    ]
    print(f"  {'Rango':>10s} {'N':>4s} {'Marca':>6s} {'%':>6s} {'AnyGol':>7s} {'%':>6s} {'Gana':>5s} {'%':>6s}")
    print(f"  {'----------':>10s} {'----':>4s} {'------':>6s} {'------':>6s} {'-------':>7s} {'------':>6s} {'-----':>5s} {'------':>6s}")

    for label, lo, hi in time_ranges:
        group = [t for t in all_triggers if lo <= t.trigger_minute < hi]
        if group:
            sc = sum(1 for t in group if t.team_scored_after)
            ag = sum(1 for t in group if t.more_goals_scored)
            tw = sum(1 for t in group if t.team_won)
            n = len(group)
            print(f"  {label:>10s} {n:>4d} {sc:>6d} {sc/n*100:>5.1f}% {ag:>7d} {ag/n*100:>5.1f}% {tw:>5d} {tw/n*100:>5.1f}%")
        else:
            print(f"  {label:>10s}    0      -      -       -      -     -      -")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 4: xG EXCESS MAGNITUDE
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 4: xG EXCESS MAGNITUDE - Does bigger excess = better signal?")
    print("=" * 80)
    print()

    excess_ranges = [
        ("0.50-0.74", 0.50, 0.75),
        ("0.75-0.99", 0.75, 1.00),
        ("1.00-1.49", 1.00, 1.50),
        ("1.50+    ", 1.50, 99),
    ]
    print(f"  {'Exceso':>10s} {'N':>4s} {'Marca':>6s} {'%':>6s} {'AvgOdds':>8s} {'NextTeam':>9s} {'%':>6s}")
    print(f"  {'----------':>10s} {'----':>4s} {'------':>6s} {'------':>6s} {'--------':>8s} {'---------':>9s} {'------':>6s}")

    for label, lo, hi in excess_ranges:
        group = [t for t in all_triggers if lo <= t.xg_excess < hi]
        if group:
            sc = sum(1 for t in group if t.team_scored_after)
            nt = sum(1 for t in group if t.next_goal_team == t.team)
            n = len(group)
            with_odds = [t for t in group if t.back_team]
            avg_odds = sum(t.back_team for t in with_odds) / len(with_odds) if with_odds else 0
            print(f"  {label:>10s} {n:>4d} {sc:>6d} {sc/n*100:>5.1f}% {avg_odds:>8.2f} {nt:>9d} {nt/n*100:>5.1f}%")
        else:
            print(f"  {label:>10s}    0      -      -        -         -      -")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 5: SCORE CONTEXT - Does the current score matter?
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 5: SCORE AT TRIGGER - Does the current score affect outcomes?")
    print("=" * 80)
    print()

    # Group by team's relative position: winning, drawing, losing
    def team_position(t: XGTrigger) -> str:
        if t.team == "home":
            if t.team_goals > t.opp_goals: return "winning"
            elif t.team_goals < t.opp_goals: return "losing"
            else: return "drawing"
        else:
            if t.team_goals > t.opp_goals: return "winning"
            elif t.team_goals < t.opp_goals: return "losing"
            else: return "drawing"

    print(f"  {'Position':>10s} {'N':>4s} {'Marca':>6s} {'%':>6s} {'Gana':>5s} {'%':>6s} {'AvgExc':>7s}")
    print(f"  {'----------':>10s} {'----':>4s} {'------':>6s} {'------':>6s} {'-----':>5s} {'------':>6s} {'-------':>7s}")

    for pos in ["drawing", "winning", "losing"]:
        group = [t for t in all_triggers if team_position(t) == pos]
        if group:
            sc = sum(1 for t in group if t.team_scored_after)
            tw = sum(1 for t in group if t.team_won)
            n = len(group)
            avg_exc = sum(t.xg_excess for t in group) / n
            print(f"  {pos:>10s} {n:>4d} {sc:>6d} {sc/n*100:>5.1f}% {tw:>5d} {tw/n*100:>5.1f}% {avg_exc:>7.2f}")
    print()

    # Group by absolute score at trigger
    scores = sorted(set(t.score_at_trigger for t in all_triggers))
    print(f"  {'Score':>6s} {'N':>4s} {'TeamSc':>7s} {'%':>6s} {'AnyGol':>7s} {'%':>6s}")
    print(f"  {'------':>6s} {'----':>4s} {'-------':>7s} {'------':>6s} {'-------':>7s} {'------':>6s}")
    for sc in scores:
        group = [t for t in all_triggers if t.score_at_trigger == sc]
        n = len(group)
        team_sc = sum(1 for t in group if t.team_scored_after)
        any_g = sum(1 for t in group if t.more_goals_scored)
        print(f"  {sc:>6s} {n:>4d} {team_sc:>7d} {team_sc/n*100:>5.1f}% {any_g:>7d} {any_g/n*100:>5.1f}%")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 6: BET SIMULATION - Back Over (total+0.5)
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 6A: BET SIMULATION - Back Over (total+0.5) goals")
    print("  Bet: at least 1 more goal will be scored after trigger")
    print("=" * 80)
    print()

    over_all = simulate_back_over(all_triggers, "Over - All triggers")
    print_summary(over_all)

    if over_all["bets"]:
        print(f"  {'Match':<28s} {'Tm':>2s} {'Min':>4s} {'Sc':>5s} {'xGEx':>5s} {'Odds':>6s} {'FT':>5s} {'W':>2s} {'P/L':>8s} {'Cum':>8s}")
        print(f"  {'-'*28} {'--':>2s} {'----':>4s} {'-----':>5s} {'-----':>5s} {'------':>6s} {'-----':>5s} {'--':>2s} {'--------':>8s} {'--------':>8s}")
        for b in over_all["bets"]:
            m = b["match"][:26]
            tm = "H" if b["team"] == "home" else "A"
            w = "W" if b["won"] else "L"
            print(f"  {m:<28s} {tm:>2s} {b['min']:>4.0f} {b['score']:>5s} {b['xg_ex']:>5.2f} {b['odds']:>6.2f} {b['ft']:>5s} {w:>2s} {b['pl']:>+8.2f} {b['cum_pl']:>+8.2f}")
    print()

    # By detection minute
    print("  Desglose por minuto de deteccion:")
    print(f"  {'Rango':>10s} {'N':>4s} {'Wins':>5s} {'WR%':>6s} {'P/L':>10s} {'ROI':>8s}")
    print(f"  {'-'*10} {'----':>4s} {'-----':>5s} {'------':>6s} {'----------':>10s} {'--------':>8s}")
    for label, lo, hi in time_ranges:
        group = [t for t in all_triggers if lo <= t.trigger_minute < hi and t.back_over_next and t.back_over_next > 1.01]
        if group:
            r = simulate_back_over(group, label)
            print(f"  {label:>10s} {r['n']:>4d} {r['wins']:>5d} {r['wr']:>5.1f}% {r['pl']:>+10.2f} {r['roi']:>+7.1f}%")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 6B: BET SIMULATION - Back Team (match winner)
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 6B: BET SIMULATION - Back underperforming team (match winner)")
    print("  Bet: the team with xG excess will win the match")
    print("=" * 80)
    print()

    team_all = simulate_back_team(all_triggers, "Team - All triggers")
    print_summary(team_all)

    if team_all["bets"]:
        print(f"  {'Match':<28s} {'Tm':>2s} {'Min':>4s} {'Sc':>5s} {'xGEx':>5s} {'Odds':>6s} {'FT':>5s} {'W':>2s} {'P/L':>8s} {'Cum':>8s}")
        print(f"  {'-'*28} {'--':>2s} {'----':>4s} {'-----':>5s} {'-----':>5s} {'------':>6s} {'-----':>5s} {'--':>2s} {'--------':>8s} {'--------':>8s}")
        for b in team_all["bets"]:
            m = b["match"][:26]
            tm = "H" if b["team"] == "home" else "A"
            w = "W" if b["won"] else "L"
            print(f"  {m:<28s} {tm:>2s} {b['min']:>4.0f} {b['score']:>5s} {b['xg_ex']:>5.2f} {b['odds']:>6.2f} {b['ft']:>5s} {w:>2s} {b['pl']:>+8.2f} {b['cum_pl']:>+8.2f}")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 6C: BET SIMULATION - Lay Draw
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 6C: BET SIMULATION - Lay Draw")
    print("  Bet: match will NOT end in draw (underperforming team breaks it)")
    print("=" * 80)
    print()

    lay_all = simulate_lay_draw(all_triggers, "Lay Draw - All triggers")
    print_summary(lay_all)

    if lay_all["bets"]:
        print(f"  {'Match':<28s} {'Tm':>2s} {'Min':>4s} {'Sc':>5s} {'xGEx':>5s} {'LayD':>6s} {'FT':>5s} {'W':>2s} {'P/L':>8s} {'Cum':>8s}")
        print(f"  {'-'*28} {'--':>2s} {'----':>4s} {'-----':>5s} {'-----':>5s} {'------':>6s} {'-----':>5s} {'--':>2s} {'--------':>8s} {'--------':>8s}")
        for b in lay_all["bets"]:
            m = b["match"][:26]
            tm = "H" if b["team"] == "home" else "A"
            w = "W" if b["won"] else "L"
            print(f"  {m:<28s} {tm:>2s} {b['min']:>4.0f} {b['score']:>5s} {b['xg_ex']:>5.2f} {b['odds']:>6.2f} {b['ft']:>5s} {w:>2s} {b['pl']:>+8.2f} {b['cum_pl']:>+8.2f}")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 7: SENSITIVITY - xG Excess Thresholds
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 7: SENSITIVITY - xG excess threshold")
    print("  Does requiring a bigger excess improve results?")
    print("=" * 80)
    print()

    thresholds = [0.30, 0.40, 0.50, 0.60, 0.75, 1.00]
    print(f"  {'Thresh':>7s} {'N':>4s} {'TeamSc%':>8s} {'AnyGol%':>8s}  |  {'Over ROI':>9s} {'Team ROI':>9s} {'LayD ROI':>9s}")
    print(f"  {'-------':>7s} {'----':>4s} {'--------':>8s} {'--------':>8s}  |  {'---------':>9s} {'---------':>9s} {'---------':>9s}")

    for thresh in thresholds:
        # For thresholds below 0.5 we need to re-scan (our triggers use 0.5)
        # For thresholds >= 0.5 we filter existing triggers
        if thresh >= 0.5:
            group = [t for t in all_triggers if t.xg_excess >= thresh]
        else:
            # We only have >= 0.5 triggers, so for lower thresholds we'd need re-scan
            # Skip for now and note it
            group = all_triggers  # 0.5 is our minimum anyway
            if thresh < 0.5:
                continue  # Can't filter below our detection threshold

        n = len(group)
        if n == 0:
            continue
        team_sc = sum(1 for t in group if t.team_scored_after)
        any_g = sum(1 for t in group if t.more_goals_scored)

        over_r = simulate_back_over(group, "")
        team_r = simulate_back_team(group, "")
        lay_r = simulate_lay_draw(group, "")

        over_roi = f"{over_r['roi']:>+.1f}%" if over_r['n'] > 0 else "-"
        team_roi = f"{team_r['roi']:>+.1f}%" if team_r['n'] > 0 else "-"
        lay_roi = f"{lay_r['roi']:>+.1f}%" if lay_r['n'] > 0 else "-"

        print(f"  {thresh:>7.2f} {n:>4d} {team_sc/n*100:>7.1f}% {any_g/n*100:>7.1f}%  |  {over_roi:>9s} {team_roi:>9s} {lay_roi:>9s}")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 8: FILTER EXPLORATION - Which additional filters help?
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 8: FILTER EXPLORATION - Additional filters")
    print("=" * 80)
    print()

    # Filter A: Only early detection (minute < 45)
    early = [t for t in all_triggers if t.trigger_minute < 45]
    late = [t for t in all_triggers if t.trigger_minute >= 45]

    print("  A) Deteccion temprana vs tardia:")
    for label, group in [("Min < 45", early), ("Min >= 45", late)]:
        if group:
            n = len(group)
            sc = sum(1 for t in group if t.team_scored_after)
            over_r = simulate_back_over(group, "")
            print(f"     {label:>10s}: N={n:>3d}, TeamSc={sc/n*100:.1f}%, Over ROI={over_r['roi']:>+.1f}%")
    print()

    # Filter B: Score at trigger (0-0 vs other)
    at_00 = [t for t in all_triggers if t.score_at_trigger == "0-0"]
    not_00 = [t for t in all_triggers if t.score_at_trigger != "0-0"]
    print("  B) Score al trigger (0-0 vs otros):")
    for label, group in [("0-0", at_00), ("No 0-0", not_00)]:
        if group:
            n = len(group)
            sc = sum(1 for t in group if t.team_scored_after)
            over_r = simulate_back_over(group, "")
            print(f"     {label:>10s}: N={n:>3d}, TeamSc={sc/n*100:.1f}%, Over ROI={over_r['roi']:>+.1f}%")
    print()

    # Filter C: Team is losing (more motivated to score)
    losing = [t for t in all_triggers if team_position(t) == "losing"]
    not_losing = [t for t in all_triggers if team_position(t) != "losing"]
    print("  C) Equipo va perdiendo (mas motivacion):")
    for label, group in [("Perdiendo", losing), ("No pierde", not_losing)]:
        if group:
            n = len(group)
            sc = sum(1 for t in group if t.team_scored_after)
            over_r = simulate_back_over(group, "")
            team_r = simulate_back_team(group, "")
            print(f"     {label:>10s}: N={n:>3d}, TeamSc={sc/n*100:.1f}%, Over ROI={over_r['roi']:>+.1f}%, Team ROI={team_r['roi']:>+.1f}%")
    print()

    # Filter D: Shots on target (has the team actually tested the keeper?)
    with_sot = [t for t in all_triggers if t.sot_team is not None and t.sot_team >= 2]
    low_sot = [t for t in all_triggers if t.sot_team is not None and t.sot_team < 2]
    print("  D) Tiros a puerta del equipo (SoT >= 2 vs < 2):")
    for label, group in [("SoT >= 2", with_sot), ("SoT < 2", low_sot)]:
        if group:
            n = len(group)
            sc = sum(1 for t in group if t.team_scored_after)
            over_r = simulate_back_over(group, "")
            print(f"     {label:>10s}: N={n:>3d}, TeamSc={sc/n*100:.1f}%, Over ROI={over_r['roi']:>+.1f}%")
    print()

    # Filter E: Big chances (has the team had clear-cut chances?)
    with_bc = [t for t in all_triggers if t.big_chances_team is not None and t.big_chances_team >= 1]
    no_bc = [t for t in all_triggers if t.big_chances_team is not None and t.big_chances_team == 0]
    print("  E) Big chances del equipo (>= 1 vs 0):")
    for label, group in [("BC >= 1", with_bc), ("BC = 0", no_bc)]:
        if group:
            n = len(group)
            sc = sum(1 for t in group if t.team_scored_after)
            over_r = simulate_back_over(group, "")
            print(f"     {label:>10s}: N={n:>3d}, TeamSc={sc/n*100:.1f}%, Over ROI={over_r['roi']:>+.1f}%")
    print()

    # Filter F: Possession dominance
    high_poss = [t for t in all_triggers if t.poss_team is not None and t.poss_team >= 55]
    low_poss = [t for t in all_triggers if t.poss_team is not None and t.poss_team < 55]
    print("  F) Posesion del equipo (>= 55% vs < 55%):")
    for label, group in [("Poss>=55%", high_poss), ("Poss<55%", low_poss)]:
        if group:
            n = len(group)
            sc = sum(1 for t in group if t.team_scored_after)
            over_r = simulate_back_over(group, "")
            print(f"     {label:>10s}: N={n:>3d}, TeamSc={sc/n*100:.1f}%, Over ROI={over_r['roi']:>+.1f}%")
    print()

    # Filter G: Combined - early + SoT >= 2 + excess >= 0.5
    combined_a = [t for t in all_triggers if t.trigger_minute < 45 and t.sot_team is not None and t.sot_team >= 2]
    print("  G) Combinado: Min<45 + SoT>=2:")
    if combined_a:
        n = len(combined_a)
        sc = sum(1 for t in combined_a if t.team_scored_after)
        over_r = simulate_back_over(combined_a, "")
        team_r = simulate_back_team(combined_a, "")
        print(f"     N={n}, TeamSc={sc/n*100:.1f}%, Over ROI={over_r['roi']:>+.1f}%, Team ROI={team_r['roi']:>+.1f}%")
    print()

    # Filter H: Combined - losing + SoT >= 2
    combined_b = [t for t in all_triggers if team_position(t) == "losing" and t.sot_team is not None and t.sot_team >= 2]
    print("  H) Combinado: Perdiendo + SoT>=2:")
    if combined_b:
        n = len(combined_b)
        sc = sum(1 for t in combined_b if t.team_scored_after)
        over_r = simulate_back_over(combined_b, "")
        team_r = simulate_back_team(combined_b, "")
        print(f"     N={n}, TeamSc={sc/n*100:.1f}%, Over ROI={over_r['roi']:>+.1f}%, Team ROI={team_r['roi']:>+.1f}%")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 9: DUPLICATE TRIGGER ANALYSIS
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 9: DUPLICATE CHECK - Same match, both teams trigger?")
    print("=" * 80)
    print()

    # Group by match_id
    matches_dict = {}
    for t in all_triggers:
        if t.match_id not in matches_dict:
            matches_dict[t.match_id] = []
        matches_dict[t.match_id].append(t)

    dual_triggers = {k: v for k, v in matches_dict.items() if len(v) > 1}
    single_triggers = {k: v for k, v in matches_dict.items() if len(v) == 1}

    print(f"  Matches con 1 trigger:  {len(single_triggers)}")
    print(f"  Matches con 2 triggers: {len(dual_triggers)}")
    if dual_triggers:
        print()
        for mid, trigs in dual_triggers.items():
            for t in trigs:
                tm = "H" if t.team == "home" else "A"
                print(f"    {t.match_name[:30]:<30s} {tm} min {t.trigger_minute:.0f} xGex={t.xg_excess:.2f} -> FT {t.ft_score}")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # SECTION 10: BEST COMBINATION SEARCH
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  SECTION 10: BEST COMBINATION - Systematic filter search")
    print("  Finding the best filter combo for Back Over strategy")
    print("=" * 80)
    print()

    combos = []
    # Minute thresholds
    for min_max in [44, 59, 74, 120]:
        # xG excess thresholds
        for xg_min in [0.50, 0.60, 0.75, 1.00]:
            # Score filters
            for score_filter in ["any", "0-0", "losing", "not_winning"]:
                # SoT filters
                for sot_min in [0, 1, 2, 3]:
                    group = [t for t in all_triggers
                             if t.trigger_minute <= min_max
                             and t.xg_excess >= xg_min
                             and (score_filter == "any"
                                  or (score_filter == "0-0" and t.score_at_trigger == "0-0")
                                  or (score_filter == "losing" and team_position(t) == "losing")
                                  or (score_filter == "not_winning" and team_position(t) != "winning"))
                             and (t.sot_team is not None and t.sot_team >= sot_min)]

                    if len(group) >= 3:  # Minimum sample
                        r = simulate_back_over(group, "")
                        if r["n"] >= 3:
                            combos.append({
                                "desc": f"Min<={min_max} xG>={xg_min:.2f} Score={score_filter} SoT>={sot_min}",
                                "n": r["n"],
                                "wr": r["wr"],
                                "roi": r["roi"],
                                "pl": r["pl"],
                            })

    # Sort by ROI descending
    combos.sort(key=lambda x: x["roi"], reverse=True)
    print(f"  Top 20 combinations (min 3 bets):")
    print(f"  {'#':>3s} {'Description':<50s} {'N':>4s} {'WR%':>6s} {'ROI':>8s} {'P/L':>10s}")
    print(f"  {'---':>3s} {'-'*50} {'----':>4s} {'------':>6s} {'--------':>8s} {'----------':>10s}")
    for i, c in enumerate(combos[:20]):
        print(f"  {i+1:>3d} {c['desc']:<50s} {c['n']:>4d} {c['wr']:>5.1f}% {c['roi']:>+7.1f}% {c['pl']:>+10.2f}")
    print()

    # ══════════════════════════════════════════════════════════════════════
    # CONCLUSIONS
    # ══════════════════════════════════════════════════════════════════════
    print("=" * 80)
    print("  CONCLUSIONS")
    print("=" * 80)
    print()
    print(f"  Dataset: {matches_analyzed} matches analyzed, {matches_with_xg} with xG data")
    print(f"  Triggers (xG excess >= 0.5): {len(all_triggers)}")
    print()
    print(f"  Base outcomes:")
    print(f"    Team scores again:    {scored}/{total} ({scored/total*100:.1f}%)")
    print(f"    At least 1 more goal: {any_goal}/{total} ({any_goal/total*100:.1f}%)")
    print(f"    Next goal is team's:  {next_is_team}/{total} ({next_is_team/total*100:.1f}%)")
    print()
    print(f"  Simulated P/L (all triggers, hold to FT):")
    print(f"    Back Over:  {over_all['n']:>3d} bets, {over_all['wr']}% WR, {over_all['roi']:>+.1f}% ROI")
    print(f"    Back Team:  {team_all['n']:>3d} bets, {team_all['wr']}% WR, {team_all['roi']:>+.1f}% ROI")
    print(f"    Lay Draw:   {lay_all['n']:>3d} bets, {lay_all['wr']}% WR, {lay_all['roi']:>+.1f}% ROI")
    print()

    if combos:
        best = combos[0]
        print(f"  Best filter combo found:")
        print(f"    {best['desc']}")
        print(f"    N={best['n']}, WR={best['wr']}%, ROI={best['roi']:>+.1f}%, P/L={best['pl']:>+.2f}")
    print()

    print("  WARNING: Sample sizes are small. Results may be noise.")
    print("  Target: 200+ triggers to validate any strategy.")
    print()


if __name__ == "__main__":
    main()
