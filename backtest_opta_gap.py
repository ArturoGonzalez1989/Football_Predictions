#!/usr/bin/env python3
"""
Backtest de estrategia opta_gap con las cuotas reales del CSV.
Simula apuestas BACK con stake fijo de 1 unidad.

Estrategias evaluadas:
  A: gap > 30 en min 35-55 -> BACK home
  B: gap < -30 en min 35-55 -> BACK away
  C: -5 <= gap <= 5 en min 35-55 -> BACK draw
  D: -15 <= gap <= -5 en min 35-55 -> BACK draw (ligera ventaja away, pero draw domina)
  LAY_A: fav en cuotas PERO dominado en Opta (gap<-15) -> LAY home
  LAY_B: fav en cuotas PERO dominado en Opta (gap>15) -> LAY away

  Ademas: barre thresholds para encontrar el optimo.
"""

import csv
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "betfair_scraper" / "data"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(val):
    try:
        v = float(str(val).strip())
        return v if v == v else None
    except:
        return None

def _result(rows):
    for r in reversed(rows):
        gl = _f(r.get("goles_local", ""))
        gv = _f(r.get("goles_visitante", ""))
        if gl is not None and gv is not None:
            if gl > gv: return "home"
            elif gl == gv: return "draw"
            else: return "away"
    return None

def _get_live_rows(rows):
    live = []
    for r in rows:
        estado = r.get("estado_partido", "").strip()
        if estado not in ("en_juego", "descanso"):
            continue
        minuto = _f(r.get("minuto", ""))
        if minuto is None:
            continue
        live.append((int(minuto), r))
    return live

def _snap(live_rows, min_from, min_to):
    window = [(m, r) for (m, r) in live_rows if min_from <= m <= min_to]
    if not window:
        return None
    _, r = window[-1]
    og = _f(r.get("opta_points_local", ""))
    ov = _f(r.get("opta_points_visitante", ""))
    bh = _f(r.get("back_home", ""))
    ba = _f(r.get("back_away", ""))
    bd = _f(r.get("back_draw", ""))
    if og is None or ov is None:
        return None
    return {
        "opta_gap": round(og - ov, 2),
        "back_home": bh,
        "back_away": ba,
        "back_draw": bd,
        "minuto": window[-1][0],
    }

# ── Simulador de apuesta ─────────────────────────────────────────────────────

def back_result(odds, win):
    """Retorno de una apuesta BACK con stake=1."""
    if odds is None or odds < 1.01:
        return None  # Sin cuota valida, ignorar
    if win:
        return odds - 1  # Ganancia neta
    else:
        return -1.0  # Perdida del stake

def lay_result(lay_odds, win_for_layer):
    """Retorno de una apuesta LAY con stake=1 (responsabilidad = lay_odds-1).
    win_for_layer=True significa que la seleccion NO gano (layer gana)."""
    if lay_odds is None or lay_odds < 1.01:
        return None
    if win_for_layer:
        return 1.0  # Ingreso del stake del backer
    else:
        return -(lay_odds - 1)  # Paga la responsabilidad

# ── Stats de estrategia ───────────────────────────────────────────────────────

class Strategy:
    def __init__(self, name):
        self.name = name
        self.bets = []  # [(odds, win, pnl)]

    def add(self, odds, win, pnl):
        self.bets.append((odds, win, pnl))

    def report(self):
        if not self.bets:
            return f"  {self.name}: sin señales"
        n = len(self.bets)
        wins = sum(1 for _, w, _ in self.bets if w)
        total_pnl = sum(p for _, _, p in self.bets)
        roi = total_pnl / n * 100
        avg_odds = sum(o for o, _, _ in self.bets if o) / n
        ev_per_bet = total_pnl / n
        lines = [
            f"  {self.name}",
            f"    Señales:     {n}",
            f"    Aciertos:    {wins} ({wins/n*100:.1f}%)",
            f"    Cuota media: {avg_odds:.2f}",
            f"    P&L total:   {total_pnl:+.2f} u (stake total {n} u)",
            f"    ROI:         {roi:+.1f}%",
            f"    EV/apuesta:  {ev_per_bet:+.3f} u",
        ]
        return "\n".join(lines)

    def report_short(self):
        if not self.bets:
            return f"{self.name:40} n/a"
        n = len(self.bets)
        wins = sum(1 for _, w, _ in self.bets if w)
        total_pnl = sum(p for _, _, p in self.bets)
        roi = total_pnl / n * 100
        return f"  {self.name:40} n={n:3d}  wr={wins/n*100:5.1f}%  ROI={roi:+6.1f}%  P&L={total_pnl:+7.2f}u"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    csvs = sorted(DATA_DIR.glob("partido_*.csv"))
    print(f"Partidos: {len(csvs)}")

    # Cargar todos los partidos utiles
    matches = []
    for f in csvs:
        try:
            with open(f, encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except:
            continue
        if not rows:
            continue
        result = _result(rows)
        if not result:
            continue
        live = _get_live_rows(rows)
        snap = _snap(live, 35, 55)
        if not snap:
            continue
        matches.append({"file": f.name, "result": result, "snap": snap})

    print(f"Con Opta + resultado (min 35-55): {len(matches)}")

    # ── Estrategias fijas ─────────────────────────────────────────────────────

    strat_home30 = Strategy("A: BACK home  (gap>30, min35-55)")
    strat_away30 = Strategy("B: BACK away  (gap<-30, min35-55)")
    strat_draw5  = Strategy("C: BACK draw  (|gap|<=5, min35-55)")
    strat_draw15 = Strategy("D: BACK draw  (-15<=gap<=-5, min35-55)")
    strat_lay_h  = Strategy("LAY_A: LAY home (home fav, gap<-15)")
    strat_lay_a  = Strategy("LAY_B: LAY away (away fav, gap>15)")

    for m in matches:
        s = m["snap"]
        gap = s["opta_gap"]
        bh, ba, bd = s["back_home"], s["back_away"], s["back_draw"]
        result = m["result"]

        # A: BACK home si gap > 30
        if gap > 30 and bh:
            pnl = back_result(bh, result == "home")
            if pnl is not None:
                strat_home30.add(bh, result == "home", pnl)

        # B: BACK away si gap < -30
        if gap < -30 and ba:
            pnl = back_result(ba, result == "away")
            if pnl is not None:
                strat_away30.add(ba, result == "away", pnl)

        # C: BACK draw si |gap| <= 5
        if abs(gap) <= 5 and bd:
            pnl = back_result(bd, result == "draw")
            if pnl is not None:
                strat_draw5.add(bd, result == "draw", pnl)

        # D: BACK draw si -15 <= gap <= -5
        if -15 <= gap <= -5 and bd:
            pnl = back_result(bd, result == "draw")
            if pnl is not None:
                strat_draw15.add(bd, result == "draw", pnl)

        # LAY_A: home es favorito (bh < ba) pero away domina Opta (gap < -15)
        if bh and ba and bh < ba and gap < -15:
            pnl = lay_result(bh, result != "home")
            if pnl is not None:
                strat_lay_h.add(bh, result != "home", pnl)

        # LAY_B: away es favorito (ba < bh) pero home domina Opta (gap > 15)
        if bh and ba and ba < bh and gap > 15:
            pnl = lay_result(ba, result != "away")
            if pnl is not None:
                strat_lay_a.add(ba, result != "away", pnl)

    print("\n" + "="*60)
    print("BACKTEST - RENDIMIENTO DE CADA ESTRATEGIA")
    print("="*60)
    for s in [strat_home30, strat_away30, strat_draw5, strat_draw15, strat_lay_h, strat_lay_a]:
        print(s.report())
        print()

    # ── Barrido de thresholds ─────────────────────────────────────────────────
    print("="*60)
    print("BARRIDO DE THRESHOLDS - BACK HOME/AWAY (gap positivo=home domina)")
    print("Buscando threshold optimo (min 35-55)")
    print("="*60)
    print(f"\n  {'Threshold':>10}  {'n_home':>6}  {'wr_home':>7}  {'roi_home':>9}  ||  {'n_away':>6}  {'wr_away':>7}  {'roi_away':>9}")
    print(f"  {'-'*75}")

    for threshold in [10, 15, 20, 25, 30, 40, 50, 60, 80]:
        sh = Strategy(f"home>{threshold}")
        sa = Strategy(f"away<-{threshold}")
        for m in matches:
            s = m["snap"]
            gap = s["opta_gap"]
            bh, ba = s["back_home"], s["back_away"]
            result = m["result"]
            if gap > threshold and bh:
                pnl = back_result(bh, result == "home")
                if pnl is not None:
                    sh.add(bh, result == "home", pnl)
            if gap < -threshold and ba:
                pnl = back_result(ba, result == "away")
                if pnl is not None:
                    sa.add(ba, result == "away", pnl)

        def _roi(st):
            if not st.bets: return "n/a", "n/a", "n/a"
            n = len(st.bets)
            w = sum(1 for _, win, _ in st.bets if win)
            roi = sum(p for _, _, p in st.bets) / n * 100
            return n, f"{w/n*100:.1f}%", f"{roi:+.1f}%"

        nh, wrh, roih = _roi(sh)
        na, wra, roia = _roi(sa)
        print(f"  {threshold:>10}  {nh:>6}  {wrh:>7}  {roih:>9}  ||  {na:>6}  {wra:>7}  {roia:>9}")

    # ── Barrido por ventana de tiempo ─────────────────────────────────────────
    print("\n" + "="*60)
    print("BARRIDO POR VENTANA DE TIEMPO (threshold fijo = 30, BACK home/away)")
    print("="*60)

    all_matches_by_window = {}
    for min_from, min_to in [(1,30),(20,45),(35,55),(45,65),(55,75),(60,90)]:
        label = f"min{min_from}-{min_to}"
        snaps = []
        for f in csvs:
            try:
                with open(f, encoding="utf-8") as fh:
                    rows = list(csv.DictReader(fh))
            except:
                continue
            if not rows:
                continue
            result = _result(rows)
            if not result:
                continue
            live = _get_live_rows(rows)
            snap = _snap(live, min_from, min_to)
            if snap:
                snaps.append({"result": result, "snap": snap})
        all_matches_by_window[label] = snaps

    print(f"\n  {'Ventana':>12}  {'n_home':>6}  {'wr_home':>7}  {'roi_home':>9}  ||  {'n_away':>6}  {'wr_away':>7}  {'roi_away':>9}")
    print(f"  {'-'*75}")
    for label, snaps in all_matches_by_window.items():
        sh = Strategy("")
        sa = Strategy("")
        for m in snaps:
            s = m["snap"]
            gap = s["opta_gap"]
            bh, ba = s["back_home"], s["back_away"]
            result = m["result"]
            if gap > 30 and bh:
                pnl = back_result(bh, result == "home")
                if pnl is not None: sh.add(bh, result == "home", pnl)
            if gap < -30 and ba:
                pnl = back_result(ba, result == "away")
                if pnl is not None: sa.add(ba, result == "away", pnl)

        def _roi(st):
            if not st.bets: return "n/a", "n/a", "n/a"
            n = len(st.bets)
            w = sum(1 for _, win, _ in st.bets if win)
            roi = sum(p for _, _, p in st.bets) / n * 100
            return n, f"{w/n*100:.1f}%", f"{roi:+.1f}%"

        nh, wrh, roih = _roi(sh)
        na, wra, roia = _roi(sa)
        print(f"  {label:>12}  {nh:>6}  {wrh:>7}  {roih:>9}  ||  {na:>6}  {wra:>7}  {roia:>9}")

    # ── Distribucion de cuotas en señales ganadoras ───────────────────────────
    print("\n" + "="*60)
    print("DISTRIBUCION DE CUOTAS - Estrategia A (gap>30, BACK home)")
    print("="*60)
    odds_ranges = [(1.01,1.5),(1.5,2.0),(2.0,2.5),(2.5,3.0),(3.0,5.0),(5.0,100)]
    for lo, hi in odds_ranges:
        bets = [(o,w,p) for (o,w,p) in strat_home30.bets if lo <= o < hi]
        if not bets:
            continue
        n = len(bets)
        w = sum(1 for _,win,_ in bets if win)
        roi = sum(p for _,_,p in bets) / n * 100
        print(f"  cuota {lo:.2f}-{hi:.2f}: n={n:3d}  wr={w/n*100:5.1f}%  ROI={roi:+6.1f}%")

    print("\nDistribucion cuotas - Estrategia B (gap<-30, BACK away)")
    for lo, hi in odds_ranges:
        bets = [(o,w,p) for (o,w,p) in strat_away30.bets if lo <= o < hi]
        if not bets:
            continue
        n = len(bets)
        w = sum(1 for _,win,_ in bets if win)
        roi = sum(p for _,_,p in bets) / n * 100
        print(f"  cuota {lo:.2f}-{hi:.2f}: n={n:3d}  wr={w/n*100:5.1f}%  ROI={roi:+6.1f}%")

    print()

if __name__ == "__main__":
    main()
