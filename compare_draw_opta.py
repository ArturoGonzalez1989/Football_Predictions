#!/usr/bin/env python3
"""
Comparacion de estrategias de empate:

  1. DRAW_SOLO   - Estrategia actual (v2r): 0-0, min>=30, xG<0.6, poss_diff<20%, tiros<8
  2. OPTA_SOLO   - Nueva independiente: 0-0, min 30-75, |opta_gap|<=threshold
  3. DRAW + OPTA - Confirmacion: draw v2r AND opta_gap equilibrado (interseccion, mas estricto)
  4. DRAW OR OPTA- Union: cualquiera de las dos (mas señales)

Para cada escenario: señales, WR, cuota media, P&L, ROI (sin comision y con 5%).

La apuesta se toma en la PRIMERA fila que cumple la condicion (trigger unico por partido).
Resultado: empate al final del partido.
"""

import csv
from pathlib import Path

DATA_DIR = Path(__file__).parent / "betfair_scraper" / "data"
STAKE = 10.0
COMMISSION = 0.05

# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(val, default=None):
    try:
        v = float(str(val).strip())
        return v if v == v else default
    except:
        return default

def _result(rows):
    for r in reversed(rows):
        gl = _f(r.get("goles_local", ""))
        gv = _f(r.get("goles_visitante", ""))
        if gl is not None and gv is not None:
            if gl == gv: return "draw"
            return "home" if gl > gv else "away"
    return None

def _pnl(odds, won):
    """P&L neto de una apuesta BACK stake=STAKE con 5% comision en ganancias."""
    if odds is None or odds < 1.01:
        return None, None
    if won:
        gross = (odds - 1) * STAKE
        net = gross * (1 - COMMISSION)
        return net, gross
    return -STAKE, -STAKE

# ── Condiciones de señal ──────────────────────────────────────────────────────

def _draw_v2r(row):
    """Condiciones de la estrategia empate v2r actual."""
    estado = row.get("estado_partido", "").strip()
    if estado != "en_juego":
        return False
    minuto = _f(row.get("minuto", ""))
    if minuto is None or minuto < 30:
        return False
    gl = _f(row.get("goles_local", ""))
    gv = _f(row.get("goles_visitante", ""))
    if gl != 0 or gv != 0:
        return False
    xg_l = _f(row.get("xg_local", ""))
    xg_v = _f(row.get("xg_visitante", ""))
    if xg_l is None or xg_v is None:
        return False
    xg_total = xg_l + xg_v
    if xg_total >= 0.6:
        return False
    pos_l = _f(row.get("posesion_local", "")) or 50
    pos_v = _f(row.get("posesion_visitante", "")) or 50
    poss_diff = abs(pos_l - pos_v)
    if poss_diff >= 20:
        return False
    tiros_l = _f(row.get("tiros_local", "")) or 0
    tiros_v = _f(row.get("tiros_visitante", "")) or 0
    if (tiros_l + tiros_v) >= 8:
        return False
    return True


def _opta_draw(row, gap_threshold=10):
    """Condicion opta: 0-0, min 30-75, |opta_gap| <= threshold."""
    estado = row.get("estado_partido", "").strip()
    if estado != "en_juego":
        return False
    minuto = _f(row.get("minuto", ""))
    if minuto is None or minuto < 30 or minuto > 75:
        return False
    gl = _f(row.get("goles_local", ""))
    gv = _f(row.get("goles_visitante", ""))
    if gl != 0 or gv != 0:
        return False
    og = _f(row.get("opta_points_local", ""))
    ov = _f(row.get("opta_points_visitante", ""))
    if og is None or ov is None:
        return False
    gap = abs(og - ov)
    return gap <= gap_threshold


def _first_trigger(rows, condition_fn):
    """Retorna la primera fila que cumple la condicion, o None."""
    for row in rows:
        if condition_fn(row):
            return row
    return None

# ── Simulacion ────────────────────────────────────────────────────────────────

class Sim:
    def __init__(self, name):
        self.name = name
        self.bets = []  # (odds, won, pnl_net)

    def add(self, odds, won):
        net, _ = _pnl(odds, won)
        if net is not None:
            self.bets.append((odds, won, net))

    def report(self, show_odds_dist=False):
        if not self.bets:
            return f"  {self.name}: sin señales"
        n = len(self.bets)
        wins = sum(1 for _, w, _ in self.bets if w)
        total_stake = n * STAKE
        total_pnl = sum(p for _, _, p in self.bets)
        roi = total_pnl / total_stake * 100
        avg_odds = sum(o for o, _, _ in self.bets) / n
        lines = [
            f"  {self.name}",
            f"    Señales:         {n}",
            f"    Aciertos:        {wins}  ({wins/n*100:.1f}%)",
            f"    Cuota media:     {avg_odds:.2f}",
            f"    Stake total:     {total_stake:.0f} u",
            f"    P&L neto (-5%):  {total_pnl:+.2f} u",
            f"    ROI:             {roi:+.1f}%",
            f"    EV/apuesta:      {total_pnl/n:+.3f} u",
        ]
        if show_odds_dist:
            lines.append("    Distribucion de cuotas:")
            for lo, hi in [(2,3),(3,4),(4,5),(5,7),(7,10),(10,50)]:
                bets = [(o,w,p) for o,w,p in self.bets if lo<=o<hi]
                if bets:
                    nb = len(bets)
                    nw = sum(1 for _,w,_ in bets if w)
                    nr = sum(p for _,_,p in bets)/nb/STAKE*100
                    lines.append(f"      [{lo:.0f}-{hi:.0f}):  n={nb:3d}  wr={nw/nb*100:5.1f}%  ROI={nr:+6.1f}%")
        return "\n".join(lines)


def main():
    csvs = sorted(DATA_DIR.glob("partido_*.csv"))
    print(f"Partidos encontrados: {len(csvs)}")

    # ── Cargar partidos ───────────────────────────────────────────────────────
    matches_data = []
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
        matches_data.append({"rows": rows, "result": result, "file": f.name})

    print(f"Partidos con resultado: {len(matches_data)}")

    # ── Escenarios con threshold fijo ─────────────────────────────────────────
    GAP_TH = 10  # threshold de gap para "equilibrado"

    sim_draw  = Sim("1. DRAW_SOLO    (v2r actual)")
    sim_opta  = Sim("2. OPTA_SOLO    (|gap|<=10, min30-75)")
    sim_and   = Sim("3. DRAW AND OPTA (confirmacion, mas estricto)")
    sim_or    = Sim("4. DRAW OR OPTA  (union, mas señales)")

    for m in matches_data:
        rows   = m["rows"]
        result = m["result"]
        won    = (result == "draw")

        # Triggers individuales
        row_draw = _first_trigger(rows, _draw_v2r)
        row_opta = _first_trigger(rows, lambda r: _opta_draw(r, GAP_TH))

        # AND: ambas condiciones deben cumplirse en el mismo partido
        # Se apuesta cuando la PRIMERA de las dos condiciones se activa,
        # pero solo si la otra tambien llega a cumplirse en algun momento.
        row_and = None
        if row_draw and row_opta:
            # Tomar la fila del primer trigger en ocurrir (el mas temprano)
            min_draw = _f(row_draw.get("minuto", "")) or 999
            min_opta = _f(row_opta.get("minuto", "")) or 999
            # En la practica, se esperaria a tener ambas confirmaciones:
            # apuesta en la fila que llega segunda (ambas confirmadas)
            row_and = row_draw if min_draw >= min_opta else row_opta

        # OR: cualquiera de las dos (la primera en activarse)
        row_or = None
        if row_draw and row_opta:
            min_draw = _f(row_draw.get("minuto", "")) or 999
            min_opta = _f(row_opta.get("minuto", "")) or 999
            row_or = row_draw if min_draw <= min_opta else row_opta
        elif row_draw:
            row_or = row_draw
        elif row_opta:
            row_or = row_opta

        # Registrar apuestas
        if row_draw:
            odds = _f(row_draw.get("back_draw", ""))
            if odds: sim_draw.add(odds, won)

        if row_opta:
            odds = _f(row_opta.get("back_draw", ""))
            if odds: sim_opta.add(odds, won)

        if row_and:
            odds = _f(row_and.get("back_draw", ""))
            if odds: sim_and.add(odds, won)

        if row_or:
            odds = _f(row_or.get("back_draw", ""))
            if odds: sim_or.add(odds, won)

    # ── Resultados ────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("COMPARACION DE ESTRATEGIAS DE EMPATE")
    print(f"  Stake: {STAKE} u | Comision: {int(COMMISSION*100)}%")
    print("="*60)
    for sim in [sim_draw, sim_opta, sim_and, sim_or]:
        print(sim.report(show_odds_dist=(sim in [sim_draw, sim_and])))
        print()

    # ── Tabla resumen ─────────────────────────────────────────────────────────
    print("="*60)
    print("TABLA RESUMEN")
    print("="*60)
    print(f"  {'Estrategia':30} {'N':>5}  {'WR':>7}  {'Odds':>6}  {'ROI':>8}  {'P&L':>9}")
    print(f"  {'-'*65}")
    for sim in [sim_draw, sim_opta, sim_and, sim_or]:
        if not sim.bets:
            print(f"  {sim.name:30} {'n/a':>5}")
            continue
        n = len(sim.bets)
        wins = sum(1 for _, w, _ in sim.bets if w)
        total_pnl = sum(p for _, _, p in sim.bets)
        roi = total_pnl / (n * STAKE) * 100
        avg_odds = sum(o for o, _, _ in sim.bets) / n
        print(f"  {sim.name:30} {n:>5}  {wins/n*100:>6.1f}%  {avg_odds:>6.2f}  {roi:>+7.1f}%  {total_pnl:>+9.2f}u")

    # ── Barrido de threshold opta_gap ─────────────────────────────────────────
    print("\n" + "="*60)
    print("BARRIDO DE THRESHOLD opta_gap (estrategias OPTA_SOLO y DRAW+OPTA)")
    print("="*60)
    print(f"\n  {'Threshold':>10}  {'n_opta':>7}  {'wr_opta':>8}  {'roi_opta':>9}  ||  {'n_and':>6}  {'wr_and':>7}  {'roi_and':>9}")
    print(f"  {'-'*75}")

    for th in [5, 8, 10, 15, 20, 25, 30, 40]:
        so = Sim("")
        sa = Sim("")
        for m in matches_data:
            rows   = m["rows"]
            result = m["result"]
            won    = (result == "draw")
            row_draw = _first_trigger(rows, _draw_v2r)
            row_opta = _first_trigger(rows, lambda r, t=th: _opta_draw(r, t))

            if row_opta:
                odds = _f(row_opta.get("back_draw", ""))
                if odds: so.add(odds, won)

            if row_draw and row_opta:
                min_draw = _f(row_draw.get("minuto", "")) or 999
                min_opta = _f(row_opta.get("minuto", "")) or 999
                row_and = row_draw if min_draw >= min_opta else row_opta
                odds = _f(row_and.get("back_draw", ""))
                if odds: sa.add(odds, won)

        def _s(sim):
            if not sim.bets: return "n/a", "n/a", "n/a"
            n = len(sim.bets)
            w = sum(1 for _, win, _ in sim.bets if win)
            roi = sum(p for _, _, p in sim.bets) / (n * STAKE) * 100
            return n, f"{w/n*100:.1f}%", f"{roi:+.1f}%"

        no, wro, roio = _s(so)
        na, wra, roia = _s(sa)
        print(f"  {th:>10}  {no:>7}  {wro:>8}  {roio:>9}  ||  {na:>6}  {wra:>7}  {roia:>9}")

    # ── Analisis de solapamiento ───────────────────────────────────────────────
    print("\n" + "="*60)
    print("SOLAPAMIENTO ENTRE SEÑALES (threshold=10)")
    print("="*60)
    only_draw = only_opta = both = neither = 0
    draw_only_wins = draw_only_n = 0
    opta_only_wins = opta_only_n = 0
    both_wins = both_n = 0

    for m in matches_data:
        rows   = m["rows"]
        result = m["result"]
        won    = (result == "draw")
        row_draw = _first_trigger(rows, _draw_v2r)
        row_opta = _first_trigger(rows, lambda r: _opta_draw(r, 10))

        has_draw = row_draw is not None
        has_opta = row_opta is not None

        if has_draw and has_opta:
            both += 1
            both_n += 1
            if won: both_wins += 1
        elif has_draw:
            only_draw += 1
            draw_only_n += 1
            if won: draw_only_wins += 1
        elif has_opta:
            only_opta += 1
            opta_only_n += 1
            if won: opta_only_wins += 1
        else:
            neither += 1

    total_w_signal = only_draw + only_opta + both
    print(f"  Partidos con alguna señal:   {total_w_signal}")
    print(f"  Solo DRAW v2r:               {only_draw:3d}  WR={draw_only_wins/max(draw_only_n,1)*100:.1f}%")
    print(f"  Solo OPTA:                   {only_opta:3d}  WR={opta_only_wins/max(opta_only_n,1)*100:.1f}%")
    print(f"  AMBAS a la vez (AND):        {both:3d}  WR={both_wins/max(both_n,1)*100:.1f}%")
    print(f"  Sin señal (ninguna):         {neither}")

    print()


if __name__ == "__main__":
    main()
