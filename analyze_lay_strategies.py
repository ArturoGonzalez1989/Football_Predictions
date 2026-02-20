"""
Análisis exhaustivo de estrategias LAY sobre 200+ partidos de Betfair Exchange.

Cada apuesta lay usa LIABILITY fija de €10 (máxima pérdida = €10 siempre).
- Si ganas (selección NO ocurre): profit = 10 / (odds-1) * 0.95
- Si pierdes (selección SÍ ocurre): loss = -€10

Esto hace el riesgo comparable con las estrategias back (stake €10, max loss €10).
"""
import os, sys, csv, glob
from collections import defaultdict

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DATA_DIR = r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data"
COMMISSION = 0.05
LIABILITY = 10.0  # Max loss per bet = €10


def to_float(val):
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return None


def load_match(csv_path):
    """Load and parse a match CSV, returning list of row dicts."""
    rows = []
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        return []
    return rows


def get_final_score(rows):
    """Get final score from last row."""
    if not rows:
        return None, None
    last = rows[-1]
    gl = to_float(last.get("goles_local"))
    gv = to_float(last.get("goles_visitante"))
    if gl is None or gv is None:
        return None, None
    return int(gl), int(gv)


def get_final_result(gl, gv):
    """H=home win, D=draw, A=away win."""
    if gl > gv:
        return "H"
    elif gl == gv:
        return "D"
    return "A"


def lay_pl(odds, selection_happened):
    """Calculate lay P/L with fixed €10 liability."""
    if odds is None or odds <= 1.0:
        return None
    if selection_happened:
        return -LIABILITY
    else:
        backers_stake = LIABILITY / (odds - 1.0)
        return backers_stake * (1 - COMMISSION)


def print_strategy(name, bets, desc=""):
    """Print strategy summary."""
    if not bets:
        print(f"\n{'='*70}")
        print(f"  {name}")
        if desc:
            print(f"  {desc}")
        print(f"  SIN DATOS (0 apuestas)")
        return

    wins = [b for b in bets if b["pl"] > 0]
    losses = [b for b in bets if b["pl"] <= 0]
    total_pl = sum(b["pl"] for b in bets)
    total_liability = len(bets) * LIABILITY
    roi = (total_pl / total_liability) * 100 if total_liability > 0 else 0
    avg_odds = sum(b["odds"] for b in bets) / len(bets)
    avg_win = sum(b["pl"] for b in wins) / len(wins) if wins else 0
    avg_loss = sum(b["pl"] for b in losses) / len(losses) if losses else 0

    print(f"\n{'='*70}")
    print(f"  {name}")
    if desc:
        print(f"  {desc}")
    print(f"{'='*70}")
    print(f"  Apuestas: {len(bets)}  |  Wins: {len(wins)}  |  Losses: {len(losses)}")
    print(f"  Win Rate: {len(wins)/len(bets)*100:.1f}%")
    print(f"  P/L Total: €{total_pl:.2f}  |  ROI: {roi:.1f}%")
    print(f"  Odds medio lay: {avg_odds:.2f}")
    print(f"  Avg win: €{avg_win:.2f}  |  Avg loss: €{avg_loss:.2f}")

    # Show breakdown by odds ranges
    ranges = [(1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 100)]
    range_data = []
    for lo, hi in ranges:
        subset = [b for b in bets if lo <= b["odds"] < hi]
        if subset:
            w = sum(1 for b in subset if b["pl"] > 0)
            pl = sum(b["pl"] for b in subset)
            range_data.append((f"{lo}-{hi}", len(subset), w, pl))
    if range_data:
        print(f"  --- Por rango de odds ---")
        for label, n, w, pl in range_data:
            print(f"    Odds {label}: {n} bets, WR={w/n*100:.0f}%, P/L=€{pl:.2f}")


def main():
    csv_files = glob.glob(os.path.join(DATA_DIR, "partido_*.csv"))
    print(f"Cargando {len(csv_files)} partidos...")

    all_matches = []
    skipped = 0
    for fp in csv_files:
        rows = load_match(fp)
        if len(rows) < 10:
            skipped += 1
            continue
        gl, gv = get_final_score(rows)
        if gl is None:
            skipped += 1
            continue
        match_name = os.path.basename(fp).replace("partido_", "").replace(".csv", "")
        all_matches.append({
            "name": match_name,
            "rows": rows,
            "ft_gl": gl,
            "ft_gv": gv,
            "ft_total": gl + gv,
            "ft_result": get_final_result(gl, gv),
        })

    print(f"Partidos válidos: {len(all_matches)} (descartados: {skipped})")
    print(f"Resultados: H={sum(1 for m in all_matches if m['ft_result']=='H')}, "
          f"D={sum(1 for m in all_matches if m['ft_result']=='D')}, "
          f"A={sum(1 for m in all_matches if m['ft_result']=='A')}")
    print(f"Goles totales promedio: {sum(m['ft_total'] for m in all_matches)/len(all_matches):.2f}")

    # ================================================================
    # STRATEGY 1: LAY THE DRAW - Equipo dominante a 0-0
    # ================================================================
    # Cuando un equipo domina claramente (xG alto, muchos tiros) y sigue 0-0,
    # apostar CONTRA el empate (lay draw).
    # El empate NO ocurre → ganamos. El empate SÍ ocurre → perdemos.
    s1_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))
            xg_l = to_float(row.get("xg_local"))
            xg_v = to_float(row.get("xg_visitante"))
            shots_l = to_float(row.get("tiros_local"))
            shots_v = to_float(row.get("tiros_visitante"))
            lay_draw = to_float(row.get("lay_draw"))

            if mi is None or gl is None or gv is None:
                continue
            if not (30 <= mi <= 60 and int(gl) == 0 and int(gv) == 0):
                continue
            if xg_l is None or xg_v is None or lay_draw is None:
                continue
            if lay_draw <= 1.0 or lay_draw > 6.0:
                continue

            xg_total = xg_l + xg_v
            xg_max = max(xg_l, xg_v)
            shots_total = (shots_l or 0) + (shots_v or 0)

            # Condición: xG total > 0.5 y al menos un equipo tiene xG > 0.3
            if xg_total >= 0.5 and xg_max >= 0.3 and shots_total >= 6:
                draw_happened = m["ft_result"] == "D"
                pl = lay_pl(lay_draw, draw_happened)
                if pl is not None:
                    s1_bets.append({"match": m["name"], "odds": lay_draw, "pl": pl,
                                    "min": mi, "xg_total": xg_total, "won": not draw_happened})
                    triggered = True

    print_strategy(
        "1. LAY THE DRAW (Dominancia a 0-0)",
        s1_bets,
        "Min 30-60, score 0-0, xG total >= 0.5, xG max >= 0.3, tiros >= 6 → Lay Draw"
    )

    # Variante más estricta
    s1b_bets = [b for b in s1_bets if b["xg_total"] >= 0.8]
    print_strategy(
        "1b. LAY THE DRAW (xG total >= 0.8)",
        s1b_bets,
        "Igual que 1 pero xG total >= 0.8"
    )

    s1c_bets = [b for b in s1_bets if b["odds"] <= 3.5]
    print_strategy(
        "1c. LAY THE DRAW (Odds lay <= 3.5)",
        s1c_bets,
        "Igual que 1 pero lay odds <= 3.5 (riesgo bajo)"
    )

    # ================================================================
    # STRATEGY 2: LAY THE LOSING TEAM (equipo perdiendo y sin juego)
    # ================================================================
    s2_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))
            xg_l = to_float(row.get("xg_local"))
            xg_v = to_float(row.get("xg_visitante"))
            sot_l = to_float(row.get("tiros_puerta_local"))
            sot_v = to_float(row.get("tiros_puerta_visitante"))
            lay_home = to_float(row.get("lay_home"))
            lay_away = to_float(row.get("lay_away"))

            if mi is None or gl is None or gv is None:
                continue
            if not (45 <= mi <= 80):
                continue
            if xg_l is None or xg_v is None:
                continue

            gl, gv = int(gl), int(gv)

            # Local pierde y no ataca
            if gl < gv and lay_home and lay_home > 1.0 and lay_home <= 15.0:
                if xg_l < 0.5 and (sot_l is not None and sot_l <= 2):
                    home_won = m["ft_result"] == "H"
                    pl = lay_pl(lay_home, home_won)
                    if pl is not None:
                        s2_bets.append({"match": m["name"], "odds": lay_home, "pl": pl,
                                        "min": mi, "team": "home", "won": not home_won})
                        triggered = True
                        continue

            # Visitante pierde y no ataca
            if gv < gl and lay_away and lay_away > 1.0 and lay_away <= 15.0:
                if xg_v < 0.5 and (sot_v is not None and sot_v <= 2):
                    away_won = m["ft_result"] == "A"
                    pl = lay_pl(lay_away, away_won)
                    if pl is not None:
                        s2_bets.append({"match": m["name"], "odds": lay_away, "pl": pl,
                                        "min": mi, "team": "away", "won": not away_won})
                        triggered = True

    print_strategy(
        "2. LAY EQUIPO PERDEDOR SIN JUEGO",
        s2_bets,
        "Min 45-80, equipo perdiendo, xG < 0.5, SoT <= 2 → Lay su victoria"
    )

    # Variante: odds bajos (menos riesgo)
    s2b = [b for b in s2_bets if b["odds"] <= 5.0]
    print_strategy("2b. LAY PERDEDOR (Odds <= 5)", s2b,
                   "Igual que 2 pero odds lay <= 5")

    # ================================================================
    # STRATEGY 3: LAY OVER EN PARTIDOS MUERTOS (0-0 tardío)
    # ================================================================
    s3_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))
            xg_l = to_float(row.get("xg_local"))
            xg_v = to_float(row.get("xg_visitante"))

            if mi is None or gl is None or gv is None:
                continue
            gl, gv = int(gl), int(gv)
            total = gl + gv

            if not (65 <= mi <= 80):
                continue

            # 3a: Score 0-0, lay Over 1.5
            if total == 0:
                lay_o15 = to_float(row.get("lay_over15"))
                if lay_o15 and 1.0 < lay_o15 <= 10.0:
                    o15_happened = m["ft_total"] >= 2
                    pl = lay_pl(lay_o15, o15_happened)
                    if pl is not None:
                        xg_t = (xg_l or 0) + (xg_v or 0)
                        s3_bets.append({"match": m["name"], "odds": lay_o15, "pl": pl,
                                        "min": mi, "line": "O1.5", "xg": xg_t,
                                        "won": not o15_happened})
                        triggered = True
                        continue

            # 3b: Score 0-0 o 1-0/0-1, lay Over 2.5
            if total <= 1:
                lay_o25 = to_float(row.get("lay_over25"))
                if lay_o25 and 1.0 < lay_o25 <= 8.0:
                    o25_happened = m["ft_total"] >= 3
                    pl = lay_pl(lay_o25, o25_happened)
                    if pl is not None:
                        xg_t = (xg_l or 0) + (xg_v or 0)
                        s3_bets.append({"match": m["name"], "odds": lay_o25, "pl": pl,
                                        "min": mi, "line": "O2.5", "xg": xg_t,
                                        "won": not o25_happened})
                        triggered = True

    print_strategy(
        "3. LAY OVER EN PARTIDO MUERTO",
        s3_bets,
        "Min 65-80, pocos goles → Lay Over 1.5/2.5"
    )

    # Split by line
    s3_o15 = [b for b in s3_bets if b["line"] == "O1.5"]
    s3_o25 = [b for b in s3_bets if b["line"] == "O2.5"]
    print_strategy("3a. LAY OVER 1.5 (0-0 min 65-80)", s3_o15)
    print_strategy("3b. LAY OVER 2.5 (0-1 goles min 65-80)", s3_o25)

    # Variante con xG bajo
    s3c = [b for b in s3_bets if b.get("xg", 999) < 1.0]
    print_strategy("3c. LAY OVER + xG total < 1.0", s3c,
                   "Partido muerto con pocas ocasiones reales")

    # ================================================================
    # STRATEGY 4: LAY FAVORITO QUE NO MARCA
    # ================================================================
    # Si un equipo es fuerte favorito (lay < 1.8 al inicio) y no ha marcado
    # al minuto 55-70, su odds de victoria sube → lay
    s4_bets = []
    for m in all_matches:
        rows = m["rows"]
        if len(rows) < 5:
            continue

        # Determine pre-match favorite from early rows
        early_lay_home = None
        early_lay_away = None
        for row in rows[:5]:
            lh = to_float(row.get("lay_home"))
            la = to_float(row.get("lay_away"))
            if lh and lh > 1.0:
                early_lay_home = lh
            if la and la > 1.0:
                early_lay_away = la

        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))

            if mi is None or gl is None or gv is None:
                continue
            gl, gv = int(gl), int(gv)
            if not (55 <= mi <= 75):
                continue

            # Home was strong favorite and hasn't scored
            if early_lay_home and early_lay_home <= 1.8 and gl == 0:
                lay_h = to_float(row.get("lay_home"))
                if lay_h and lay_h > 1.5 and lay_h <= 8.0:
                    home_won = m["ft_result"] == "H"
                    pl = lay_pl(lay_h, home_won)
                    if pl is not None:
                        s4_bets.append({"match": m["name"], "odds": lay_h, "pl": pl,
                                        "min": mi, "early_odds": early_lay_home,
                                        "team": "home", "won": not home_won})
                        triggered = True
                        continue

            # Away was strong favorite and hasn't scored
            if early_lay_away and early_lay_away <= 1.8 and gv == 0:
                lay_a = to_float(row.get("lay_away"))
                if lay_a and lay_a > 1.5 and lay_a <= 8.0:
                    away_won = m["ft_result"] == "A"
                    pl = lay_pl(lay_a, away_won)
                    if pl is not None:
                        s4_bets.append({"match": m["name"], "odds": lay_a, "pl": pl,
                                        "min": mi, "early_odds": early_lay_away,
                                        "team": "away", "won": not away_won})
                        triggered = True

    print_strategy(
        "4. LAY FAVORITO QUE NO MARCA",
        s4_bets,
        "Favorito (lay inicio <= 1.8) no ha marcado min 55-75, lay actual > 1.5 → Lay"
    )

    s4b = [b for b in s4_bets if b["odds"] <= 4.0]
    print_strategy("4b. LAY FAV NO MARCA (odds <= 4.0)", s4b)

    # ================================================================
    # STRATEGY 5: LAY UNDER CUANDO HAY MOMENTUM DE GOLES
    # ================================================================
    # Después de un gol, hay clusters de goles. Lay Under.
    s5_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        prev_total = 0

        for ri, row in enumerate(rows):
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))

            if mi is None or gl is None or gv is None:
                continue
            gl, gv = int(gl), int(gv)
            total = gl + gv

            # Detect goal just scored
            if total > prev_total and mi <= 75:
                prev_total = total
                # Lay Under (total + 0.5) → betting MORE goals will come
                line_key = f"lay_under{int(total)}5"  # e.g., lay_under15, lay_under25
                lay_under = to_float(row.get(line_key))

                if lay_under and lay_under > 1.0 and lay_under <= 6.0:
                    # Under happened = ft_total <= total (no more goals)
                    under_happened = m["ft_total"] <= total
                    pl = lay_pl(lay_under, under_happened)
                    if pl is not None:
                        s5_bets.append({"match": m["name"], "odds": lay_under, "pl": pl,
                                        "min": mi, "goals_at_trigger": total,
                                        "line": f"U{total}.5", "won": not under_happened})
                        triggered = True
                continue
            prev_total = total

    print_strategy(
        "5. LAY UNDER POST-GOL (Momentum)",
        s5_bets,
        "Justo después de un gol (min <= 75), lay Under X.5 → apostar que habrá más goles"
    )

    # Split by current goals
    s5_1g = [b for b in s5_bets if b["goals_at_trigger"] == 1]
    s5_2g = [b for b in s5_bets if b["goals_at_trigger"] >= 2]
    print_strategy("5a. LAY UNDER POST-GOL (1er gol)", s5_1g)
    print_strategy("5b. LAY UNDER POST-GOL (2+ goles)", s5_2g)

    # ================================================================
    # STRATEGY 6: LAY THE DRAW EN EMPATE CON GOLES (espejo pressure_cooker)
    # ================================================================
    s6_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))
            lay_draw = to_float(row.get("lay_draw"))

            if mi is None or gl is None or gv is None:
                continue
            gl, gv = int(gl), int(gv)
            if not (60 <= mi <= 78):
                continue
            if gl != gv or gl == 0:
                continue  # Only tied games WITH goals (1-1, 2-2, etc.)
            if lay_draw is None or lay_draw <= 1.0 or lay_draw > 5.0:
                continue

            draw_happened = m["ft_result"] == "D"
            pl = lay_pl(lay_draw, draw_happened)
            if pl is not None:
                s6_bets.append({"match": m["name"], "odds": lay_draw, "pl": pl,
                                "min": mi, "score": f"{gl}-{gv}", "won": not draw_happened})
                triggered = True

    print_strategy(
        "6. LAY DRAW EN EMPATE CON GOLES (1-1+, min 60-78)",
        s6_bets,
        "Empate 1-1 o superior entre min 60-78 → Lay draw (esperamos que se rompa)"
    )

    s6b = [b for b in s6_bets if b["odds"] <= 3.0]
    print_strategy("6b. LAY DRAW 1-1+ (odds <= 3.0)", s6b)

    # ================================================================
    # STRATEGY 7: LAY AWAY EN PARTIDOS CON EQUIPO LOCAL DOMINANTE
    # ================================================================
    s7_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))
            xg_l = to_float(row.get("xg_local"))
            xg_v = to_float(row.get("xg_visitante"))
            pos_l = to_float(row.get("posesion_local"))
            sot_l = to_float(row.get("tiros_puerta_local"))
            sot_v = to_float(row.get("tiros_puerta_visitante"))
            lay_away = to_float(row.get("lay_away"))

            if mi is None or gl is None or gv is None:
                continue
            gl, gv = int(gl), int(gv)
            if not (35 <= mi <= 70):
                continue
            if gl < gv:
                continue  # Local no está perdiendo
            if xg_l is None or pos_l is None or lay_away is None:
                continue
            if lay_away <= 1.0 or lay_away > 12.0:
                continue

            # Local domina: xG alto, posesión alta, SoT alto
            sot_l_val = sot_l or 0
            sot_v_val = sot_v or 0
            xg_v_val = xg_v or 0

            if xg_l >= 0.6 and pos_l >= 55 and sot_l_val >= 3 and sot_l_val > sot_v_val:
                away_won = m["ft_result"] == "A"
                pl = lay_pl(lay_away, away_won)
                if pl is not None:
                    s7_bets.append({"match": m["name"], "odds": lay_away, "pl": pl,
                                    "min": mi, "xg_l": xg_l, "pos": pos_l,
                                    "won": not away_won})
                    triggered = True

    print_strategy(
        "7. LAY AWAY CON LOCAL DOMINANTE",
        s7_bets,
        "Min 35-70, local no pierde, xG local >= 0.6, posesión >= 55%, SoT local >= 3 → Lay Away"
    )

    s7b = [b for b in s7_bets if b["odds"] <= 6.0]
    print_strategy("7b. LAY AWAY DOMINANCIA (odds <= 6)", s7b)

    # ================================================================
    # STRATEGY 8: LAY EMPATE PURO (mercado genérico)
    # ================================================================
    # El draw pierde en ~70% de partidos. ¿Es rentable simplemente lay draw?
    s8_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            lay_draw = to_float(row.get("lay_draw"))
            if mi is None or lay_draw is None:
                continue
            if not (25 <= mi <= 35):
                continue
            if lay_draw <= 1.0 or lay_draw > 5.0:
                continue
            draw_happened = m["ft_result"] == "D"
            pl = lay_pl(lay_draw, draw_happened)
            if pl is not None:
                s8_bets.append({"match": m["name"], "odds": lay_draw, "pl": pl,
                                "min": mi, "won": not draw_happened})
                triggered = True

    print_strategy(
        "8. LAY DRAW GENÉRICO (min 25-35, odds <= 5)",
        s8_bets,
        "Simplemente lay draw en cualquier partido entre min 25-35"
    )

    # ================================================================
    # STRATEGY 9: LAY OVER 2.5 LATE (0-0/1-0 late game)
    # ================================================================
    s9_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))
            xg_l = to_float(row.get("xg_local"))
            xg_v = to_float(row.get("xg_visitante"))
            sot_l = to_float(row.get("tiros_puerta_local"))
            sot_v = to_float(row.get("tiros_puerta_visitante"))

            if mi is None or gl is None or gv is None:
                continue
            gl, gv = int(gl), int(gv)
            total = gl + gv
            if not (70 <= mi <= 82):
                continue
            if total > 1:
                continue  # Only 0 or 1 goals

            lay_o25 = to_float(row.get("lay_over25"))
            if lay_o25 is None or lay_o25 <= 1.0 or lay_o25 > 15.0:
                continue

            xg_t = (xg_l or 0) + (xg_v or 0)
            sot_t = (sot_l or 0) + (sot_v or 0)

            # Extra filter: low intensity
            if xg_t < 1.5 and sot_t <= 6:
                o25_happened = m["ft_total"] >= 3
                pl = lay_pl(lay_o25, o25_happened)
                if pl is not None:
                    s9_bets.append({"match": m["name"], "odds": lay_o25, "pl": pl,
                                    "min": mi, "goals": total, "xg": xg_t, "sot": sot_t,
                                    "won": not o25_happened})
                    triggered = True

    print_strategy(
        "9. LAY OVER 2.5 LATE + BAJA INTENSIDAD",
        s9_bets,
        "Min 70-82, 0-1 goles, xG < 1.5, SoT <= 6 → Lay Over 2.5"
    )

    # ================================================================
    # STRATEGY 10: LAY HOME EN EMPATE 0-0 TARDÍO CON VISITANTE SÓLIDO
    # ================================================================
    s10_bets = []
    for m in all_matches:
        rows = m["rows"]
        triggered = False
        for row in rows:
            if triggered:
                break
            mi = to_float(row.get("minuto"))
            gl = to_float(row.get("goles_local"))
            gv = to_float(row.get("goles_visitante"))
            xg_v = to_float(row.get("xg_visitante"))
            pos_v = to_float(row.get("posesion_visitante"))
            lay_home = to_float(row.get("lay_home"))

            if mi is None or gl is None or gv is None:
                continue
            gl, gv = int(gl), int(gv)
            if not (55 <= mi <= 75 and gl == 0 and gv == 0):
                continue
            if lay_home is None or lay_home <= 1.5 or lay_home > 6.0:
                continue
            if pos_v is None:
                continue

            # Visitante no está siendo dominado (>= 45% posesión)
            if pos_v >= 45 and (xg_v or 0) >= 0.2:
                home_won = m["ft_result"] == "H"
                pl = lay_pl(lay_home, home_won)
                if pl is not None:
                    s10_bets.append({"match": m["name"], "odds": lay_home, "pl": pl,
                                     "min": mi, "pos_v": pos_v, "won": not home_won})
                    triggered = True

    print_strategy(
        "10. LAY HOME EN 0-0 TARDÍO (visitante sólido)",
        s10_bets,
        "Min 55-75, 0-0, visitante posesión >= 45% + xG >= 0.2 → Lay Home"
    )

    # ================================================================
    # RESUMEN TOP STRATEGIES
    # ================================================================
    print(f"\n{'#'*70}")
    print(f"  RESUMEN - MEJORES ESTRATEGIAS LAY")
    print(f"{'#'*70}")

    all_strategies = [
        ("1. LTD Dominancia 0-0", s1_bets),
        ("1b. LTD xG >= 0.8", s1b_bets),
        ("1c. LTD odds <= 3.5", s1c_bets),
        ("2. Lay Perdedor Sin Juego", s2_bets),
        ("2b. Lay Perdedor odds<=5", s2b),
        ("3. Lay Over Muerto", s3_bets),
        ("3a. Lay O1.5 (0-0)", s3_o15),
        ("3b. Lay O2.5 (0-1g)", s3_o25),
        ("3c. Lay Over xG<1", s3c),
        ("4. Lay Fav No Marca", s4_bets),
        ("4b. Lay Fav odds<=4", s4b),
        ("5. Lay Under Post-Gol", s5_bets),
        ("5a. Post 1er Gol", s5_1g),
        ("5b. Post 2+ Goles", s5_2g),
        ("6. Lay Draw 1-1+ (60-78)", s6_bets),
        ("6b. Lay Draw 1-1+ odds<=3", s6b),
        ("7. Lay Away Dominancia", s7_bets),
        ("7b. Lay Away odds<=6", s7b),
        ("8. Lay Draw Genérico", s8_bets),
        ("9. Lay O2.5 Late LowInt", s9_bets),
        ("10. Lay Home 0-0 Tardío", s10_bets),
    ]

    # Sort by ROI (only strategies with >= 5 bets)
    summary = []
    for name, bets in all_strategies:
        if len(bets) >= 5:
            total_pl = sum(b["pl"] for b in bets)
            roi = (total_pl / (len(bets) * LIABILITY)) * 100
            wr = sum(1 for b in bets if b["pl"] > 0) / len(bets) * 100
            summary.append((name, len(bets), wr, total_pl, roi))

    summary.sort(key=lambda x: x[4], reverse=True)

    print(f"\n{'Estrategia':<35} {'N':>4} {'WR%':>6} {'P/L':>9} {'ROI%':>7}")
    print("-" * 65)
    for name, n, wr, pl, roi in summary:
        marker = " ***" if roi > 10 and n >= 8 else ""
        print(f"{name:<35} {n:>4} {wr:>5.1f}% €{pl:>7.2f} {roi:>6.1f}%{marker}")

    print(f"\n*** = ROI > 10% con N >= 8 apuestas (candidatas a implementar)")


if __name__ == "__main__":
    main()