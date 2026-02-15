"""
V3 Trading Simulator — Back Draw 0-0 Strategy
==============================================
Simulates minute-by-minute trading through all finished match CSVs.

Compares 4 strategies:
  V1 HOLD:  Entry at 0-0 min 30+, hold until FT
  V2 HOLD:  V1 + xG<0.5, poss_diff<20, shots<8, hold until FT
  V3a HOLD: V2 + danger_score<=20, hold until FT (pure filter improvement)
  V3b TRADE: V3a entry + dynamic exit rules (cash out / stop loss / stat exit)

Trading rules for V3b:
  - Entry: same as V3a
  - Cash out: if back_draw drops to <=1.50, cash out (lock profit)
  - Stop loss: if back_draw rises to >=5.00, exit (cut losses)
  - Stat exit: if at any point after entry, xG of any team >=1.0 or big_chances_total >=3, exit
  - If none of the above, hold until FT (same as V3a)

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

def calc_pl_hold(won: bool, back_odds: Optional[float]) -> float:
    """P/L for holding until FT."""
    if won and back_odds:
        return round((back_odds - 1) * STAKE * (1 - COMMISSION), 2)
    return -STAKE

def calc_pl_cashout(entry_odds: float, exit_odds: float) -> float:
    """
    P/L when cashing out before FT.

    We backed at entry_odds with STAKE. Now the draw odds are exit_odds.
    To cash out, we LAY at exit_odds.

    If exit_odds < entry_odds (price dropped = draw more likely = our bet is winning):
      lay_stake = STAKE * entry_odds / exit_odds
      guaranteed_profit = lay_stake - STAKE (minus commission on profit)

    Simplified: profit = STAKE * (entry_odds / exit_odds - 1) * (1 - COMMISSION)
    But we need to be careful - we use the back price to approximate the lay.
    In practice lay = back + spread. We'll use back as conservative estimate.
    """
    if exit_odds is None or entry_odds is None or exit_odds <= 1:
        return 0

    # Lay stake to fully hedge
    lay_stake = STAKE * entry_odds / exit_odds

    if exit_odds < entry_odds:
        # Draw is more likely now — we're in profit
        # If draw wins: we win (entry_odds-1)*STAKE from back, lose (exit_odds-1)*lay_stake from lay
        # If draw loses: we lose STAKE from back, win lay_stake from lay
        # Both outcomes: profit = lay_stake - STAKE
        profit = lay_stake - STAKE
        return round(profit * (1 - COMMISSION), 2)
    else:
        # Draw is less likely now — we're in loss
        # Both outcomes: loss = STAKE - lay_stake (but lay_stake < STAKE since exit_odds > entry_odds)
        # Actually: loss = STAKE - lay_stake = STAKE * (1 - entry_odds/exit_odds)
        loss = STAKE - lay_stake
        return round(-abs(loss), 2)


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class TriggerData:
    match_name: str
    match_id: str
    trigger_minute: float
    back_draw_entry: Optional[float]
    xg_total: Optional[float]
    xg_max: Optional[float]
    sot_total: Optional[int]
    shots_total: Optional[int]
    poss_diff: Optional[float]
    danger_score: Optional[float]
    big_chances_total: Optional[int]
    corners_total: Optional[int]
    back_over25: Optional[float]
    ft_score: str
    draw_won: bool
    # Pre-match BFE odds (from Football Data enrichment)
    bfeh: Optional[float] = None
    bfed: Optional[float] = None
    bfea: Optional[float] = None
    match_balance: Optional[float] = None  # min(bfeh,bfea)/max(bfeh,bfea)
    # V3b trading fields
    exit_minute: Optional[float] = None
    exit_reason: Optional[str] = None
    exit_odds: Optional[float] = None
    # Odds evolution post-entry (for analysis)
    odds_at_45: Optional[float] = None
    odds_at_60: Optional[float] = None
    odds_at_75: Optional[float] = None
    odds_min_post_entry: Optional[float] = None
    odds_max_post_entry: Optional[float] = None
    goal_minute: Optional[float] = None  # minute first goal scored (None if 0-0 FT)


# ── Main analysis ────────────────────────────────────────────────────────

def analyze_all_matches():
    csv_files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")))
    print(f"Found {len(csv_files)} CSV files\n")

    all_triggers: list[TriggerData] = []
    matches_analyzed = 0

    for csv_path in csv_files:
        rows = read_csv(csv_path)
        if len(rows) < 5:
            continue

        # Check if match is finished (has in-play rows with goals data)
        last_row = rows[-1]
        gl_final = to_float(last_row.get("goles_local"))
        gv_final = to_float(last_row.get("goles_visitante"))
        last_min = to_float(last_row.get("minuto"))

        if gl_final is None or gv_final is None:
            continue
        if last_min is not None and last_min < 80:
            continue  # Probably not finished

        matches_analyzed += 1
        match_id = os.path.basename(csv_path).replace("partido_", "").replace(".csv", "")
        match_name = last_row.get("evento", match_id).strip() or match_id
        if not match_name or match_name == match_id:
            match_name = match_id.replace("-apuestas-", " ").rsplit(" ", 1)[0].replace("-", " ").title()

        ft_score = f"{int(gl_final)}-{int(gv_final)}"
        draw_won = int(gl_final) == int(gv_final)

        # Find trigger row: first row with min>=30 and 0-0
        trigger_idx = None
        for i, row in enumerate(rows):
            m = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))
            if m is not None and gl is not None and gv is not None:
                if m >= 30 and int(gl) == 0 and int(gv) == 0:
                    trigger_idx = i
                    break

        if trigger_idx is None:
            continue

        tr = rows[trigger_idx]

        # Extract stats at trigger
        xg_l = to_float(tr.get("xg_local"))
        xg_v = to_float(tr.get("xg_visitante"))
        xg_total = ((xg_l or 0) + (xg_v or 0)) if (xg_l is not None or xg_v is not None) else None
        xg_max = max(xg_l or 0, xg_v or 0) if (xg_l is not None or xg_v is not None) else None

        sot_l = to_int(tr.get("tiros_puerta_local"))
        sot_v = to_int(tr.get("tiros_puerta_visitante"))
        sot_total = ((sot_l or 0) + (sot_v or 0)) if (sot_l is not None or sot_v is not None) else None

        shots_l = to_int(tr.get("tiros_local"))
        shots_v = to_int(tr.get("tiros_visitante"))
        shots_total = ((shots_l or 0) + (shots_v or 0)) if (shots_l is not None or shots_v is not None) else None

        poss_l = to_float(tr.get("posesion_local"))
        poss_v = to_float(tr.get("posesion_visitante"))
        poss_diff = abs((poss_l or 50) - (poss_v or 50)) if (poss_l is not None or poss_v is not None) else None

        da_l = to_float(tr.get("dangerous_attacks_local"))
        da_v = to_float(tr.get("dangerous_attacks_visitante"))
        bc_l = to_float(tr.get("big_chances_local"))
        bc_v = to_float(tr.get("big_chances_visitante"))
        tb_l = to_float(tr.get("touches_box_local"))
        tb_v = to_float(tr.get("touches_box_visitante"))

        da_total = ((da_l or 0) + (da_v or 0)) if (da_l is not None or da_v is not None) else None
        bc_total = int((bc_l or 0) + (bc_v or 0)) if (bc_l is not None or bc_v is not None) else None
        tb_total = ((tb_l or 0) + (tb_v or 0)) if (tb_l is not None or tb_v is not None) else None

        # Danger score = dangerous_attacks + big_chances + touches_box
        components = [x for x in [da_total, bc_total, tb_total] if x is not None]
        danger_score = sum(components) if components else None

        corn_l = to_int(tr.get("corners_local"))
        corn_v = to_int(tr.get("corners_visitante"))
        corners_total = ((corn_l or 0) + (corn_v or 0)) if (corn_l is not None or corn_v is not None) else None

        back_draw_entry = to_float(tr.get("back_draw"))
        back_over25 = to_float(tr.get("back_over25"))
        trigger_minute = to_float(tr.get("minuto"))

        # Pre-match BFE odds (enriched columns, constant per CSV)
        bfeh = to_float(tr.get("BFEH"))
        bfed = to_float(tr.get("BFED"))
        bfea = to_float(tr.get("BFEA"))
        if bfeh and bfea and max(bfeh, bfea) > 0:
            match_balance = round(min(bfeh, bfea) / max(bfeh, bfea), 3)
        else:
            match_balance = None

        # ── Walk through ALL post-trigger rows for odds evolution + trading sim ──
        exit_minute = None
        exit_reason = None
        exit_odds = None
        odds_at_45 = None
        odds_at_60 = None
        odds_at_75 = None
        odds_post_entry = []
        goal_minute = None

        for j in range(trigger_idx + 1, len(rows)):
            row = rows[j]
            m = to_float(row.get("minuto"))
            bd = to_float(row.get("back_draw"))

            # Track odds evolution regardless of exit
            if bd is not None:
                odds_post_entry.append(bd)
            if m is not None and bd is not None:
                if odds_at_45 is None and m >= 45:
                    odds_at_45 = bd
                if odds_at_60 is None and m >= 60:
                    odds_at_60 = bd
                if odds_at_75 is None and m >= 75:
                    odds_at_75 = bd

            # Detect first goal
            g_l = to_float(row.get("goles_local"))
            g_v = to_float(row.get("goles_visitante"))
            if g_l is not None and g_v is not None and (int(g_l) != 0 or int(g_v) != 0):
                if goal_minute is None:
                    goal_minute = m

            # Trading exit rules (only if not already exited)
            if exit_reason is None:
                # If goal scored, stop evaluating exit rules (hold to FT)
                if g_l is not None and g_v is not None and (int(g_l) != 0 or int(g_v) != 0):
                    continue  # keep walking for odds tracking

                # Cash out: draw odds dropped to <= 1.50
                if bd is not None and bd <= 1.50:
                    exit_minute = m
                    exit_reason = "cashout_profit"
                    exit_odds = bd

                # Stop loss: draw odds rose to >= 5.00
                elif bd is not None and bd >= 5.00:
                    exit_minute = m
                    exit_reason = "stop_loss"
                    exit_odds = bd

                # Stat exit: xG of any team >= 1.0
                else:
                    xg_l_now = to_float(row.get("xg_local"))
                    xg_v_now = to_float(row.get("xg_visitante"))
                    if (xg_l_now is not None and xg_l_now >= 1.0) or (xg_v_now is not None and xg_v_now >= 1.0):
                        exit_minute = m
                        exit_reason = "stat_exit_xg"
                        exit_odds = bd

                    # Stat exit: big chances total >= 3
                    bc_l_now = to_float(row.get("big_chances_local"))
                    bc_v_now = to_float(row.get("big_chances_visitante"))
                    if bc_l_now is not None and bc_v_now is not None:
                        if (bc_l_now + bc_v_now) >= 3:
                            exit_minute = m
                            exit_reason = "stat_exit_bigchances"
                            exit_odds = bd

        odds_min_post = min(odds_post_entry) if odds_post_entry else None
        odds_max_post = max(odds_post_entry) if odds_post_entry else None

        t = TriggerData(
            match_name=match_name,
            match_id=match_id,
            trigger_minute=trigger_minute or 30,
            back_draw_entry=back_draw_entry,
            xg_total=round(xg_total, 2) if xg_total is not None else None,
            xg_max=round(xg_max, 2) if xg_max is not None else None,
            sot_total=sot_total,
            shots_total=shots_total,
            poss_diff=round(poss_diff, 1) if poss_diff is not None else None,
            danger_score=round(danger_score, 1) if danger_score is not None else None,
            big_chances_total=bc_total,
            corners_total=corners_total,
            back_over25=back_over25,
            ft_score=ft_score,
            draw_won=draw_won,
            bfeh=bfeh,
            bfed=bfed,
            bfea=bfea,
            match_balance=match_balance,
            exit_minute=exit_minute,
            exit_reason=exit_reason,
            exit_odds=exit_odds,
            odds_at_45=odds_at_45,
            odds_at_60=odds_at_60,
            odds_at_75=odds_at_75,
            odds_min_post_entry=odds_min_post,
            odds_max_post_entry=odds_max_post,
            goal_minute=goal_minute,
        )
        all_triggers.append(t)

    return matches_analyzed, all_triggers


def passes_v2(t: TriggerData) -> bool:
    return (
        (t.xg_total is not None and t.xg_total < 0.5) and
        (t.poss_diff is not None and t.poss_diff < 20) and
        (t.shots_total is not None and t.shots_total < 8)
    )

def passes_v3a(t: TriggerData, ds_thresh: float = 30) -> bool:
    if not passes_v2(t):
        return False
    if t.danger_score is not None and t.danger_score > ds_thresh:
        return False
    return True


def simulate_hold(triggers: list[TriggerData], label: str, filter_fn=None):
    """Simulate hold-until-FT strategy."""
    bets = [t for t in triggers if (filter_fn is None or filter_fn(t))]
    if not bets:
        return {"label": label, "n": 0, "wins": 0, "wr": 0, "pl": 0, "roi": 0, "bets": []}

    results = []
    cum_pl = 0
    for t in bets:
        pl = calc_pl_hold(t.draw_won, t.back_draw_entry)
        cum_pl += pl
        results.append({
            "match": t.match_name,
            "min": t.trigger_minute,
            "back": t.back_draw_entry,
            "ft": t.ft_score,
            "won": t.draw_won,
            "pl": pl,
            "cum_pl": round(cum_pl, 2),
        })

    wins = sum(1 for r in results if r["won"])
    total_pl = round(sum(r["pl"] for r in results), 2)

    return {
        "label": label,
        "n": len(bets),
        "wins": wins,
        "wr": round(wins / len(bets) * 100, 1),
        "pl": total_pl,
        "roi": round(total_pl / (len(bets) * STAKE) * 100, 1),
        "bets": results,
    }


def simulate_v3b_trading(triggers: list[TriggerData]):
    """Simulate V3b with dynamic exits."""
    bets = [t for t in triggers if passes_v3a(t)]
    if not bets:
        return {"label": "V3b TRADE", "n": 0, "wins": 0, "wr": 0, "pl": 0, "roi": 0, "bets": []}

    results = []
    cum_pl = 0

    for t in bets:
        if t.exit_reason and t.exit_odds is not None and t.back_draw_entry:
            # Exited early via trading rule
            pl = calc_pl_cashout(t.back_draw_entry, t.exit_odds)
            outcome = t.exit_reason
        else:
            # Held until FT
            pl = calc_pl_hold(t.draw_won, t.back_draw_entry)
            outcome = "hold_win" if t.draw_won else "hold_loss"

        cum_pl += pl
        results.append({
            "match": t.match_name,
            "min_entry": t.trigger_minute,
            "back_entry": t.back_draw_entry,
            "exit_min": t.exit_minute,
            "exit_odds": t.exit_odds,
            "exit_reason": outcome,
            "ft": t.ft_score,
            "pl": round(pl, 2),
            "cum_pl": round(cum_pl, 2),
        })

    total_pl = round(sum(r["pl"] for r in results), 2)
    wins = sum(1 for r in results if r["pl"] > 0)

    return {
        "label": "V3b TRADE",
        "n": len(bets),
        "wins": wins,
        "wr": round(wins / len(bets) * 100, 1),
        "pl": total_pl,
        "roi": round(total_pl / (len(bets) * STAKE) * 100, 1),
        "bets": results,
    }


def print_summary(result: dict):
    print(f"  {'Strategy':<12s}: {result['label']}")
    print(f"  {'Bets':<12s}: {result['n']}")
    print(f"  {'Wins':<12s}: {result['wins']} ({result['wr']}%)")
    print(f"  {'P/L':<12s}: {'+' if result['pl'] >= 0 else ''}{result['pl']} EUR")
    print(f"  {'ROI':<12s}: {'+' if result['roi'] >= 0 else ''}{result['roi']}%")
    print()


def main():
    print("=" * 70)
    print("  V3 TRADING SIMULATOR — Back Draw 0-0 Strategy")
    print("  Stake: 10 EUR | Commission: 5% | Data: all finished CSVs")
    print("=" * 70)
    print()

    matches_analyzed, triggers = analyze_all_matches()
    print(f"Matches analyzed: {matches_analyzed}")
    print(f"Triggers (0-0 at min 30+): {len(triggers)}")
    print()

    # ── Simulate all 4 strategies ──
    v1 = simulate_hold(triggers, "V1 HOLD")
    v2 = simulate_hold(triggers, "V2 HOLD", passes_v2)
    v3a = simulate_hold(triggers, "V3a HOLD", passes_v3a)  # DS<=30
    v3b = simulate_v3b_trading(triggers)

    # ── Summary comparison ──
    print("=" * 70)
    print("  STRATEGY COMPARISON")
    print("=" * 70)
    print()

    print(f"{'Strategy':<14s} {'Bets':>5s} {'Wins':>5s} {'WR%':>6s} {'P/L':>10s} {'ROI':>8s}")
    print("-" * 50)
    for s in [v1, v2, v3a, v3b]:
        pl_str = f"{'+' if s['pl'] >= 0 else ''}{s['pl']}"
        roi_str = f"{'+' if s['roi'] >= 0 else ''}{s['roi']}%"
        print(f"{s['label']:<14s} {s['n']:>5d} {s['wins']:>5d} {s['wr']:>5.1f}% {pl_str:>10s} {roi_str:>8s}")
    print()

    # ── V1 detail ──
    print("=" * 70)
    print("  V1 HOLD — All triggers, hold until FT")
    print("=" * 70)
    print_summary(v1)
    print(f"  {'Match':<40s} {'Min':>4s} {'Back':>6s} {'FT':>5s} {'W/L':>4s} {'P/L':>8s} {'Cum':>8s}")
    print(f"  {'-'*40} {'----':>4s} {'------':>6s} {'-----':>5s} {'----':>4s} {'--------':>8s} {'--------':>8s}")
    for b in v1["bets"]:
        m = b["match"][:38]
        w = "W" if b["won"] else "L"
        bk = f"{b['back']:.2f}" if b["back"] else "-"
        print(f"  {m:<40s} {b['min']:>4.0f} {bk:>6s} {b['ft']:>5s} {w:>4s} {b['pl']:>+8.2f} {b['cum_pl']:>+8.2f}")
    print()

    # ── V2 detail ──
    print("=" * 70)
    print("  V2 HOLD — Filtered (xG<0.5, poss<20%, shots<8), hold until FT")
    print("=" * 70)
    print_summary(v2)
    if v2["bets"]:
        print(f"  {'Match':<40s} {'Min':>4s} {'Back':>6s} {'FT':>5s} {'W/L':>4s} {'P/L':>8s} {'Cum':>8s}")
        print(f"  {'-'*40} {'----':>4s} {'------':>6s} {'-----':>5s} {'----':>4s} {'--------':>8s} {'--------':>8s}")
        for b in v2["bets"]:
            m = b["match"][:38]
            w = "W" if b["won"] else "L"
            bk = f"{b['back']:.2f}" if b["back"] else "-"
            print(f"  {m:<40s} {b['min']:>4.0f} {bk:>6s} {b['ft']:>5s} {w:>4s} {b['pl']:>+8.2f} {b['cum_pl']:>+8.2f}")
    print()

    # ── V3a detail ──
    print("=" * 70)
    print("  V3a HOLD — V2 + danger_score<=30, hold until FT")
    print("=" * 70)
    print_summary(v3a)
    if v3a["bets"]:
        print(f"  {'Match':<40s} {'Min':>4s} {'Back':>6s} {'FT':>5s} {'W/L':>4s} {'P/L':>8s} {'Cum':>8s}")
        print(f"  {'-'*40} {'----':>4s} {'------':>6s} {'-----':>5s} {'----':>4s} {'--------':>8s} {'--------':>8s}")
        for b in v3a["bets"]:
            m = b["match"][:38]
            w = "W" if b["won"] else "L"
            bk = f"{b['back']:.2f}" if b["back"] else "-"
            print(f"  {m:<40s} {b['min']:>4.0f} {bk:>6s} {b['ft']:>5s} {w:>4s} {b['pl']:>+8.2f} {b['cum_pl']:>+8.2f}")
    print()

    # ── V3b detail (trading) ──
    print("=" * 70)
    print("  V3b TRADE — V3a entry + dynamic exits")
    print("  Rules: cashout@1.50, stop_loss@5.00, xG>=1.0, big_chances>=3")
    print("=" * 70)
    print_summary(v3b)
    if v3b["bets"]:
        print(f"  {'Match':<32s} {'Entry':>5s} {'Back':>6s} {'Exit':>5s} {'ExOdd':>6s} {'Reason':<20s} {'FT':>5s} {'P/L':>8s} {'Cum':>8s}")
        print(f"  {'-'*32} {'-----':>5s} {'------':>6s} {'-----':>5s} {'------':>6s} {'-'*20} {'-----':>5s} {'--------':>8s} {'--------':>8s}")
        for b in v3b["bets"]:
            m = b["match"][:30]
            bk = f"{b['back_entry']:.2f}" if b["back_entry"] else "-"
            ex_min = f"{b['exit_min']:.0f}" if b["exit_min"] else "FT"
            ex_odd = f"{b['exit_odds']:.2f}" if b["exit_odds"] else "-"
            print(f"  {m:<32s} {b['min_entry']:>5.0f} {bk:>6s} {ex_min:>5s} {ex_odd:>6s} {b['exit_reason']:<20s} {b['ft']:>5s} {b['pl']:>+8.2f} {b['cum_pl']:>+8.2f}")
    print()

    # ── Trading exits analysis ──
    v3b_bets = v3b["bets"]
    if v3b_bets:
        print("=" * 70)
        print("  V3b EXIT ANALYSIS")
        print("=" * 70)
        exit_reasons = {}
        for b in v3b_bets:
            r = b["exit_reason"]
            if r not in exit_reasons:
                exit_reasons[r] = {"count": 0, "pl": 0}
            exit_reasons[r]["count"] += 1
            exit_reasons[r]["pl"] += b["pl"]

        print(f"\n  {'Exit Reason':<22s} {'Count':>6s} {'Total P/L':>10s} {'Avg P/L':>10s}")
        print(f"  {'-'*22} {'------':>6s} {'----------':>10s} {'----------':>10s}")
        for reason, data in sorted(exit_reasons.items()):
            avg = data["pl"] / data["count"]
            print(f"  {reason:<22s} {data['count']:>6d} {data['pl']:>+10.2f} {avg:>+10.2f}")
        print()

    # ── ODDS EVOLUTION ANALYSIS (key for trading value assessment) ──
    print("=" * 70)
    print("  ODDS EVOLUTION — Draw odds journey after entry (ALL V1 triggers)")
    print("  Answers: does the draw odds move in our favor before FT?")
    print("=" * 70)
    print()
    print(f"  {'Match':<32s} {'@30':>5s} {'@45':>5s} {'@60':>5s} {'@75':>5s} {'Min':>5s} {'Max':>5s} {'Goal':>5s} {'FT':>5s} {'W':>2s}")
    print(f"  {'-'*32} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'--':>2s}")
    for t in triggers:
        m = t.match_name[:30]
        e = f"{t.back_draw_entry:.2f}" if t.back_draw_entry else "-"
        o45 = f"{t.odds_at_45:.2f}" if t.odds_at_45 else "-"
        o60 = f"{t.odds_at_60:.2f}" if t.odds_at_60 else "-"
        o75 = f"{t.odds_at_75:.2f}" if t.odds_at_75 else "-"
        omn = f"{t.odds_min_post_entry:.2f}" if t.odds_min_post_entry else "-"
        omx = f"{t.odds_max_post_entry:.2f}" if t.odds_max_post_entry else "-"
        gm = f"{t.goal_minute:.0f}" if t.goal_minute else "-"
        w = "W" if t.draw_won else "L"
        print(f"  {m:<32s} {e:>5s} {o45:>5s} {o60:>5s} {o75:>5s} {omn:>5s} {omx:>5s} {gm:>5s} {t.ft_score:>5s} {w:>2s}")

    # ── Analyze: could we have profited by cashout? ──
    print()
    print("=" * 70)
    print("  CASHOUT ANALYSIS — What if we cashed out at various thresholds?")
    print("  Shows P/L if we exit when draw odds drop below threshold")
    print("=" * 70)
    print()

    # For ALL V1 triggers, simulate cashout at different thresholds
    for version_label, filter_fn in [("V1", None), ("V2", passes_v2), ("V3a", passes_v3a)]:
        filtered = [t for t in triggers if (filter_fn is None or filter_fn(t))]
        if not filtered:
            continue
        print(f"  {version_label} triggers ({len(filtered)} bets):")
        print(f"  {'Threshold':<12s} {'Cashouts':>9s} {'Holds':>6s} {'P/L':>10s} {'ROI':>8s} {'vs Hold':>8s}")
        print(f"  {'-'*12} {'-'*9} {'-'*6} {'-'*10} {'-'*8} {'-'*8}")

        # Hold baseline
        hold_pl = sum(calc_pl_hold(t.draw_won, t.back_draw_entry) for t in filtered)

        for thresh in [1.30, 1.50, 1.80, 2.00, 2.20, 999]:
            label = f"@{thresh:.2f}" if thresh < 999 else "HOLD"
            total_pl = 0
            cashouts = 0
            for t in filtered:
                if thresh < 999 and t.odds_min_post_entry and t.odds_min_post_entry <= thresh and t.back_draw_entry:
                    # Would have hit cashout
                    total_pl += calc_pl_cashout(t.back_draw_entry, thresh)
                    cashouts += 1
                else:
                    total_pl += calc_pl_hold(t.draw_won, t.back_draw_entry)

            holds = len(filtered) - cashouts
            roi = total_pl / (len(filtered) * STAKE) * 100
            diff = total_pl - hold_pl
            diff_str = f"{'+' if diff >= 0 else ''}{diff:.2f}"
            print(f"  {label:<12s} {cashouts:>9d} {holds:>6d} {total_pl:>+10.2f} {roi:>+7.1f}% {diff_str:>8s}")
        print()

    # ── Trigger data table ──
    print("=" * 70)
    print("  ALL TRIGGER DATA (for analysis)")
    print("=" * 70)
    print(f"\n  {'Match':<35s} {'Min':>4s} {'Back':>6s} {'xG':>5s} {'SoT':>4s} {'Sh':>4s} {'PD':>5s} {'DS':>6s} {'BC':>3s} {'Cor':>4s} {'O25':>5s} {'FT':>5s} {'W':>2s} {'V2':>3s} {'V3a':>4s}")
    print(f"  {'-'*35} {'----':>4s} {'------':>6s} {'-----':>5s} {'----':>4s} {'----':>4s} {'-----':>5s} {'------':>6s} {'---':>3s} {'----':>4s} {'-----':>5s} {'-----':>5s} {'--':>2s} {'---':>3s} {'----':>4s}")
    for t in triggers:
        m = t.match_name[:33]
        bk = f"{t.back_draw_entry:.2f}" if t.back_draw_entry else "-"
        xg = f"{t.xg_total:.2f}" if t.xg_total is not None else "-"
        sot = str(t.sot_total) if t.sot_total is not None else "-"
        sh = str(t.shots_total) if t.shots_total is not None else "-"
        pd = f"{t.poss_diff:.0f}" if t.poss_diff is not None else "-"
        ds = f"{t.danger_score:.0f}" if t.danger_score is not None else "-"
        bc = str(t.big_chances_total) if t.big_chances_total is not None else "-"
        cor = str(t.corners_total) if t.corners_total is not None else "-"
        o25 = f"{t.back_over25:.1f}" if t.back_over25 else "-"
        w = "W" if t.draw_won else "L"
        v2_pass = "Y" if passes_v2(t) else "N"
        v3_pass = "Y" if passes_v3a(t) else "N"
        print(f"  {m:<35s} {t.trigger_minute:>4.0f} {bk:>6s} {xg:>5s} {sot:>4s} {sh:>4s} {pd:>5s} {ds:>6s} {bc:>3s} {cor:>4s} {o25:>5s} {t.ft_score:>5s} {w:>2s} {v2_pass:>3s} {v3_pass:>4s}")

    # ── Sensitivity analysis ──
    print()
    print("=" * 70)
    print("  SENSITIVITY: Danger score threshold")
    print("=" * 70)
    print()
    for ds_thresh in [10, 15, 20, 25, 30, 40, 999]:
        label = f"<={ds_thresh}" if ds_thresh < 999 else "any(=V2)"
        filtered = [t for t in triggers if passes_v2(t) and (ds_thresh >= 999 or (t.danger_score is not None and t.danger_score <= ds_thresh))]
        if filtered:
            wins = sum(1 for t in filtered if t.draw_won)
            pl = sum(calc_pl_hold(t.draw_won, t.back_draw_entry) for t in filtered)
            wr = wins / len(filtered) * 100
            roi = pl / (len(filtered) * STAKE) * 100
            print(f"  DS {label:>8s}: N={len(filtered):>3d}, Wins={wins}, WR={wr:>5.1f}%, P/L={pl:>+8.2f}, ROI={roi:>+6.1f}%")

    # ── PRE-MATCH BFED ANALYSIS ──
    print()
    print("=" * 70)
    print("  PRE-MATCH ODDS ANALYSIS (BFEH/BFED/BFEA from Football Data)")
    print("  Testing hypothesis: BFED 2.80-3.20 + balanced match = better WR")
    print("=" * 70)
    print()

    with_bfed = [t for t in triggers if t.bfed is not None]
    without_bfed = [t for t in triggers if t.bfed is None]
    print(f"  Triggers with BFED data:    {len(with_bfed)}")
    print(f"  Triggers without BFED data: {len(without_bfed)}")
    if without_bfed:
        print(f"    (sin datos: {', '.join(t.match_name[:20] for t in without_bfed)})")
    print()

    if with_bfed:
        # Show all triggers with pre-match data
        print(f"  {'Match':<28s} {'BFEH':>5s} {'BFED':>5s} {'BFEA':>5s} {'Bal':>5s} {'Live@30':>7s} {'FT':>5s} {'W':>2s} {'V2':>3s}")
        print(f"  {'-'*28} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'-------':>7s} {'-----':>5s} {'--':>2s} {'---':>3s}")
        for t in with_bfed:
            m = t.match_name[:26]
            bh = f"{t.bfeh:.2f}" if t.bfeh else "-"
            bd = f"{t.bfed:.2f}" if t.bfed else "-"
            ba = f"{t.bfea:.2f}" if t.bfea else "-"
            bl = f"{t.match_balance:.2f}" if t.match_balance else "-"
            ld = f"{t.back_draw_entry:.2f}" if t.back_draw_entry else "-"
            w = "W" if t.draw_won else "L"
            v2_flag = "Y" if passes_v2(t) else "N"
            print(f"  {m:<28s} {bh:>5s} {bd:>5s} {ba:>5s} {bl:>5s} {ld:>7s} {t.ft_score:>5s} {w:>2s} {v2_flag:>3s}")
        print()

        # Hypothesis 1: BFED range
        print("  HIPOTESIS 1: Tramo de cuota BFED pre-match")
        print(f"  {'Tramo BFED':<16s} {'N':>3s} {'Wins':>5s} {'WR%':>6s} {'P/L':>10s} {'ROI':>8s}")
        print(f"  {'-'*16} {'---':>3s} {'-----':>5s} {'------':>6s} {'----------':>10s} {'--------':>8s}")

        bfed_ranges = [
            ("< 2.80", lambda t: t.bfed < 2.80),
            ("2.80-3.20", lambda t: 2.80 <= t.bfed <= 3.20),
            ("3.20-3.80", lambda t: 3.20 < t.bfed <= 3.80),
            ("3.80-4.50", lambda t: 3.80 < t.bfed <= 4.50),
            ("> 4.50", lambda t: t.bfed > 4.50),
        ]
        for label, filt in bfed_ranges:
            group = [t for t in with_bfed if filt(t)]
            if group:
                wins = sum(1 for t in group if t.draw_won)
                pl = sum(calc_pl_hold(t.draw_won, t.back_draw_entry) for t in group)
                wr = wins / len(group) * 100
                roi = pl / (len(group) * STAKE) * 100
                print(f"  {label:<16s} {len(group):>3d} {wins:>5d} {wr:>5.1f}% {pl:>+10.2f} {roi:>+7.1f}%")
            else:
                print(f"  {label:<16s}   0     -      -          -        -")
        print()

        # Hypothesis 2: Match balance
        print("  HIPOTESIS 2: Equilibrio del partido (min(H,A)/max(H,A))")
        print(f"  {'Equilibrio':<20s} {'N':>3s} {'Wins':>5s} {'WR%':>6s} {'P/L':>10s} {'ROI':>8s}")
        print(f"  {'-'*20} {'---':>3s} {'-----':>5s} {'------':>6s} {'----------':>10s} {'--------':>8s}")

        bal_ranges = [
            ("< 0.40 (favorito)", lambda t: t.match_balance is not None and t.match_balance < 0.40),
            ("0.40-0.60", lambda t: t.match_balance is not None and 0.40 <= t.match_balance < 0.60),
            ("0.60-0.80", lambda t: t.match_balance is not None and 0.60 <= t.match_balance < 0.80),
            (">= 0.80 (equilib.)", lambda t: t.match_balance is not None and t.match_balance >= 0.80),
        ]
        for label, filt in bal_ranges:
            group = [t for t in with_bfed if filt(t)]
            if group:
                wins = sum(1 for t in group if t.draw_won)
                pl = sum(calc_pl_hold(t.draw_won, t.back_draw_entry) for t in group)
                wr = wins / len(group) * 100
                roi = pl / (len(group) * STAKE) * 100
                print(f"  {label:<20s} {len(group):>3d} {wins:>5d} {wr:>5.1f}% {pl:>+10.2f} {roi:>+7.1f}%")
            else:
                print(f"  {label:<20s}   0     -      -          -        -")
        print()

        # Hypothesis 3: BFED as V2 filter addition
        print("  HIPOTESIS 3: BFED como filtro adicional a V2")
        v2_with_bfed = [t for t in with_bfed if passes_v2(t)]
        print(f"  V2 triggers con BFED: {len(v2_with_bfed)}")
        if v2_with_bfed:
            print(f"  {'Filtro':<30s} {'N':>3s} {'Wins':>5s} {'WR%':>6s} {'P/L':>10s} {'ROI':>8s}")
            print(f"  {'-'*30} {'---':>3s} {'-----':>5s} {'------':>6s} {'----------':>10s} {'--------':>8s}")

            combos = [
                ("V2 solo", lambda t: True),
                ("V2 + BFED 2.80-3.20", lambda t: 2.80 <= t.bfed <= 3.20),
                ("V2 + BFED 2.80-3.80", lambda t: 2.80 <= t.bfed <= 3.80),
                ("V2 + balance >= 0.60", lambda t: t.match_balance is not None and t.match_balance >= 0.60),
                ("V2 + BFED<3.80 + bal>=0.60", lambda t: t.bfed <= 3.80 and t.match_balance is not None and t.match_balance >= 0.60),
            ]
            for label, filt in combos:
                group = [t for t in v2_with_bfed if filt(t)]
                if group:
                    wins = sum(1 for t in group if t.draw_won)
                    pl = sum(calc_pl_hold(t.draw_won, t.back_draw_entry) for t in group)
                    wr = wins / len(group) * 100
                    roi = pl / (len(group) * STAKE) * 100
                    print(f"  {label:<30s} {len(group):>3d} {wins:>5d} {wr:>5.1f}% {pl:>+10.2f} {roi:>+7.1f}%")
                else:
                    print(f"  {label:<30s}   0     -      -          -        -")
        print()

        # Hypothesis 4: Pre-match odds vs in-play stats correlation
        print("  HIPOTESIS 4: Correlacion BFED pre-match vs stats in-play")
        print(f"  {'Match':<25s} {'BFED':>5s} {'Bal':>5s} {'xG':>5s} {'SoT':>4s} {'DS':>6s} {'W':>2s}")
        print(f"  {'-'*25} {'-----':>5s} {'-----':>5s} {'-----':>5s} {'----':>4s} {'------':>6s} {'--':>2s}")
        for t in with_bfed:
            m = t.match_name[:23]
            bd = f"{t.bfed:.2f}" if t.bfed else "-"
            bl = f"{t.match_balance:.2f}" if t.match_balance else "-"
            xg = f"{t.xg_total:.2f}" if t.xg_total is not None else "-"
            sot = str(t.sot_total) if t.sot_total is not None else "-"
            ds = f"{t.danger_score:.0f}" if t.danger_score is not None else "-"
            w = "W" if t.draw_won else "L"
            print(f"  {m:<25s} {bd:>5s} {bl:>5s} {xg:>5s} {sot:>4s} {ds:>6s} {w:>2s}")

        # Check if high BFED (less expected draw) correlates with higher in-play danger
        bfed_low = [t for t in with_bfed if t.bfed <= 3.50 and t.xg_total is not None]
        bfed_high = [t for t in with_bfed if t.bfed > 3.50 and t.xg_total is not None]
        if bfed_low and bfed_high:
            avg_xg_low = sum(t.xg_total for t in bfed_low) / len(bfed_low)
            avg_xg_high = sum(t.xg_total for t in bfed_high) / len(bfed_high)
            print(f"\n  BFED <= 3.50: avg xG@30 = {avg_xg_low:.3f} (N={len(bfed_low)})")
            print(f"  BFED  > 3.50: avg xG@30 = {avg_xg_high:.3f} (N={len(bfed_high)})")
            if avg_xg_high > avg_xg_low:
                print("  -> Partidos con BFED alto (empate menos esperado) tienen mas xG al min 30")
            else:
                print("  -> No hay correlacion clara entre BFED y xG al min 30")

    print()

    # ── Key conclusions ──
    print("=" * 70)
    print("  CONCLUSIONS")
    print("=" * 70)
    print()
    print(f"  Dataset: {matches_analyzed} finished matches, {len(triggers)} triggers (0-0 at min 30+)")
    print(f"  Pre-match BFE data: {len(with_bfed)} of {len(triggers)} triggers")
    print()
    for s in [v1, v2, v3a, v3b]:
        n = s["n"]
        wr = s["wr"]
        roi = s["roi"]
        print(f"  {s['label']:<14s}: {n:>2d} bets, {wr}% WR, {roi:>+.1f}% ROI")
    print()
    print(f"  WARNING: Sample sizes are very small ({len(triggers)} triggers).")
    print("  Re-run as matches accumulate. Target: 50+ triggers.")
    print()


if __name__ == "__main__":
    main()
