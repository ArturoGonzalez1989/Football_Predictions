"""
analyze_cashout.py
==================
Para cada apuesta perdedora con partido CSV disponible:
1. Identifica el mercado apostado (draw, home, away, over X.5)
2. Carga la evolución de cuotas en-play del partido
3. Simula el cash-out (lay en contra) en cada captura posterior al trigger
4. Calcula cuándo habría sido óptimo hacer cash-out y cuánto se recuperaría
5. Busca patrones: ¿qué score/minuto indica el mejor momento de salida?

Cash-out formula:
  lay_stake = back_stake * back_odds / lay_odds
  cashout_pl = -back_stake + lay_stake   (garantiza 0 independientemente del resultado)
             = back_stake * (back_odds / lay_odds - 1)
  Si lay_odds > back_odds → cashout_pl < 0  (pérdida parcial, menor que la total)
  Si lay_odds < back_odds → cashout_pl > 0  (ganancia garantizada)
"""

import csv
import os
import re
from collections import defaultdict

PLACED_BETS = r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\placed_bets.csv"
DATA_DIR    = r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data"
STAKE       = 10.0

# ── helpers ──────────────────────────────────────────────────────────────────

def parse_float(v):
    try:
        return float(v) if v and v.strip() else None
    except:
        return None

def market_from_recommendation(rec):
    """
    Returns (market_key, back_col, lay_col) based on the recommendation string.
    market_key: 'draw' | 'home' | 'away' | 'over15' | 'over25' | 'over35' | 'over45'
    """
    rec_up = rec.upper()
    if "DRAW" in rec_up:
        return "draw", "back_draw", "lay_draw"
    if "HOME" in rec_up:
        return "home", "back_home", "lay_home"
    if "AWAY" in rec_up:
        return "away", "back_away", "lay_away"
    if "OVER 4.5" in rec_up or "O 4.5" in rec_up:
        return "over45", "back_over45", "lay_over45"
    if "OVER 3.5" in rec_up or "O 3.5" in rec_up:
        return "over35", "back_over35", "lay_over35"
    if "OVER 2.5" in rec_up or "O 2.5" in rec_up:
        return "over25", "back_over25", "lay_over25"
    if "OVER 1.5" in rec_up or "O 1.5" in rec_up:
        return "over15", "back_over15", "lay_over15"
    return None, None, None

def cashout_pl(back_odds, lay_odds, stake=STAKE):
    """P&L if you cash-out now (guaranteed regardless of result)."""
    return round(stake * (back_odds / lay_odds - 1), 2)

def pct_recovered(cashout_val, stake=STAKE):
    """% of stake recovered vs full loss (-stake)."""
    return round((cashout_val + stake) / stake * 100, 1)

def load_partido(match_id):
    path = os.path.join(DATA_DIR, f"partido_{match_id}.csv")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))

# ── main analysis ────────────────────────────────────────────────────────────

def analyze():
    with open(PLACED_BETS, encoding="utf-8") as f:
        bets = list(csv.DictReader(f))

    losing_bets = [b for b in bets if parse_float(b.get("pl", 0)) is not None and parse_float(b["pl"]) < 0]
    print(f"Apuestas perdedoras: {len(losing_bets)}\n")

    results = []

    for bet in losing_bets:
        match_id   = bet["match_id"]
        match_name = bet["match_name"]
        strategy   = bet["strategy"]
        rec        = bet.get("recommendation", "")
        back_odds  = parse_float(bet.get("back_odds"))
        bet_minute = parse_float(bet.get("minute"))
        bet_score  = bet.get("score", "")
        pl_actual  = parse_float(bet["pl"])

        if back_odds is None or bet_minute is None:
            continue

        market_key, back_col, lay_col = market_from_recommendation(rec)
        if market_key is None:
            print(f"  [SKIP] {match_name}: no se pudo detectar mercado de '{rec}'")
            continue

        rows = load_partido(match_id)
        if rows is None:
            print(f"  [SKIP] {match_name}: no hay partido CSV")
            continue

        # Filter rows AFTER the bet trigger minute
        post_rows = []
        for r in rows:
            m = parse_float(r.get("minuto"))
            if m is not None and m > bet_minute:
                lay = parse_float(r.get(lay_col))
                if lay and lay > 1.01:
                    post_rows.append((m, r))

        if not post_rows:
            print(f"  [SKIP] {match_name}: sin filas post-trigger con cuotas válidas")
            continue

        # Compute cash-out value at each post-trigger point
        cashout_series = []
        for (m, r) in post_rows:
            gl = parse_float(r.get("goles_local")) or 0
            gv = parse_float(r.get("goles_visitante")) or 0
            score_now = f"{int(gl)}-{int(gv)}"
            lay = parse_float(r.get(lay_col))
            bk  = parse_float(r.get(back_col))
            co_pl = cashout_pl(back_odds, lay)
            cashout_series.append({
                "minute": m,
                "score": score_now,
                "lay_odds": lay,
                "back_odds_now": bk,
                "cashout_pl": co_pl,
                "pct_recovered": pct_recovered(co_pl),
            })

        if not cashout_series:
            continue

        # Best cash-out = maximum P&L (least negative / most positive)
        best = max(cashout_series, key=lambda x: x["cashout_pl"])
        # Last available cash-out (close to end of match)
        last = cashout_series[-1]
        # Midpoint reference (~min 70)
        mid70 = min(cashout_series, key=lambda x: abs(x["minute"] - 70)) if cashout_series else None

        results.append({
            "match_name":    match_name,
            "strategy":      strategy,
            "market":        market_key,
            "back_odds":     back_odds,
            "bet_minute":    bet_minute,
            "bet_score":     bet_score,
            "pl_actual":     pl_actual,
            "best_co":       best,
            "last_co":       last,
            "mid70_co":      mid70,
            "series_len":    len(cashout_series),
            "series":        cashout_series,
        })

    # ── Print results ─────────────────────────────────────────────────────────
    print("=" * 90)
    print(f"{'PARTIDO':<32} {'ESTRATEGIA':<20} {'MERC':6} {'BACK':5} {'MIN':4}  RESULTADO REAL → MEJOR CASHOUT")
    print("=" * 90)

    total_loss_full    = 0.0
    total_loss_best_co = 0.0
    total_loss_70      = 0.0
    total_loss_last    = 0.0

    for r in results:
        b = r["best_co"]
        l = r["last_co"]
        m70 = r["mid70_co"]

        total_loss_full    += r["pl_actual"]
        total_loss_best_co += b["cashout_pl"]
        total_loss_70      += m70["cashout_pl"] if m70 else r["pl_actual"]
        total_loss_last    += l["cashout_pl"]

        print(f"\n{r['match_name'][:31]:<32} {r['strategy'][:19]:<20} {r['market']:6} @{r['back_odds']:<4} min{r['bet_minute']:.0f}")
        print(f"  Score al trigger: {r['bet_score']}  |  Resultado real: {r['pl_actual']:+.2f}€")
        print(f"  MEJOR cashout: min {b['minute']:.0f} ({b['score']}) lay={b['lay_odds']} → P&L {b['cashout_pl']:+.2f}€  ({b['pct_recovered']}% recuperado)")
        if m70:
            print(f"  Cashout ~min70:  min {m70['minute']:.0f} ({m70['score']}) lay={m70['lay_odds']} → P&L {m70['cashout_pl']:+.2f}€  ({m70['pct_recovered']}% recuperado)")
        print(f"  Cashout al final: min {l['minute']:.0f} ({l['score']}) lay={l['lay_odds']} → P&L {l['cashout_pl']:+.2f}€  ({l['pct_recovered']}% recuperado)")

        # Print key moments in the series (every ~10 minutes)
        milestones = {}
        for pt in r["series"]:
            bucket = int(pt["minute"] // 10) * 10
            if bucket not in milestones:
                milestones[bucket] = pt
        print(f"  Evolucion cada ~10min:")
        for bkt in sorted(milestones.keys()):
            pt = milestones[bkt]
            print(f"    min {pt['minute']:.0f} | {pt['score']} | lay {pt['lay_odds']} | CO {pt['cashout_pl']:+.2f}€ ({pt['pct_recovered']}%)")

    print("\n" + "=" * 90)
    print("RESUMEN GLOBAL")
    print("=" * 90)
    n = len(results)
    print(f"Apuestas analizadas: {n}")
    print(f"Pérdida total sin cashout:       {total_loss_full:+.2f}€   (promedio {total_loss_full/n:+.2f}€/apuesta)")
    print(f"Pérdida con cashout óptimo:      {total_loss_best_co:+.2f}€   (promedio {total_loss_best_co/n:+.2f}€/apuesta)")
    savings_best = total_loss_full - total_loss_best_co
    print(f"Ahorro vs no cashout (óptimo):   +{savings_best:.2f}€  ({savings_best/abs(total_loss_full)*100:.1f}% del total perdido)")
    if n > 0:
        print(f"Pérdida con cashout ~min70:      {total_loss_70:+.2f}€   (promedio {total_loss_70/n:+.2f}€/apuesta)")
        savings_70 = total_loss_full - total_loss_70
        print(f"Ahorro vs no cashout (min70):    +{savings_70:.2f}€  ({savings_70/abs(total_loss_full)*100:.1f}% del total perdido)")

    # ── Pattern analysis: when is cash-out optimal? ────────────────────────
    print("\n" + "=" * 90)
    print("PATRONES: ¿CUÁNDO Y EN QUÉ SCORE SERÍA ÓPTIMO HACER CASHOUT?")
    print("=" * 90)
    print(f"\n{'PARTIDO':<32} {'MERC':6} {'MEJOR MIN':9} {'MEJOR SCORE':12} {'CO PL':8} {'RECUPERADO'}")
    print("-" * 80)
    for r in results:
        b = r["best_co"]
        print(f"{r['match_name'][:31]:<32} {r['market']:6} {b['minute']:9.0f} {b['score']:12} {b['cashout_pl']:+8.2f}€  {b['pct_recovered']}%")

    # Stats on best cash-out minute
    best_minutes = [r["best_co"]["minute"] for r in results]
    if best_minutes:
        avg_min = sum(best_minutes) / len(best_minutes)
        print(f"\nMinuto promedio de cashout óptimo: {avg_min:.0f}'")
        print(f"Rango: min {min(best_minutes):.0f}' - max {max(best_minutes):.0f}'")

    # Count by best cash-out score
    score_counts = defaultdict(list)
    for r in results:
        score_counts[r["best_co"]["score"]].append(r["best_co"]["cashout_pl"])
    print(f"\nDistribucion por score al cashout óptimo:")
    for score, vals in sorted(score_counts.items()):
        avg_pl = sum(vals) / len(vals)
        print(f"  {score}: {len(vals)} casos, promedio CO {avg_pl:+.2f}€")

    # By strategy
    print(f"\nPor estrategia:")
    strat_groups = defaultdict(list)
    for r in results:
        strat_groups[r["strategy"]].append(r)
    for strat, rs in strat_groups.items():
        loss_total   = sum(r["pl_actual"] for r in rs)
        loss_best_co = sum(r["best_co"]["cashout_pl"] for r in rs)
        savings      = loss_total - loss_best_co
        avg_best_min = sum(r["best_co"]["minute"] for r in rs) / len(rs)
        print(f"  {strat[:30]:30}: {len(rs)} apuestas | pérdida real {loss_total:+.2f}€ | CO óptimo {loss_best_co:+.2f}€ | ahorro {savings:+.2f}€ | min óptimo avg {avg_best_min:.0f}'")

if __name__ == "__main__":
    analyze()