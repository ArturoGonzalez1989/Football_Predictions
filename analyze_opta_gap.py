#!/usr/bin/env python3
"""
Analisis historico de opta_points como señal de apuestas.
Preguntas:
  1. Cobertura: que % de partidos/minutos tienen datos Opta?
  2. Gap vs resultado: si home domina en Opta, gana mas?
  3. Señal LAY: cuando el favorito de las cuotas esta siendo DOMINADO en Opta?
  4. Señal DRAW: cuando opta_gap es pequeño (ambos equipos igualados)?
  5. Timing: gap en el minuto 30-60 vs resultado final.
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "betfair_scraper" / "data"

# ── Helpers ──────────────────────────────────────────────────────────────────

def _f(val):
    try:
        v = float(str(val).strip())
        return v if v == v else None  # NaN check
    except:
        return None

def _last_valid(rows, field):
    for r in reversed(rows):
        v = _f(r.get(field, ""))
        if v is not None:
            return v
    return None

def _result(rows):
    """Resultado final: 'home', 'draw', 'away' o None."""
    goles_l = _last_valid(rows, "goles_local")
    goles_v = _last_valid(rows, "goles_visitante")
    if goles_l is None or goles_v is None:
        # Try to infer from odds at the end (very long-shot fallback)
        return None
    if goles_l > goles_v:
        return "home"
    elif goles_l == goles_v:
        return "draw"
    else:
        return "away"

def _get_live_rows(rows):
    """Solo filas en juego (minuto conocido, no pre ni post)."""
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
    """Snapshot de stats en una ventana de minutos."""
    window = [(m, r) for (m, r) in live_rows if min_from <= m <= min_to]
    if not window:
        return None
    # Tomar la fila mas representativa (ultima del bloque)
    _, r = window[-1]
    og = _f(r.get("opta_points_local", ""))
    ov = _f(r.get("opta_points_visitante", ""))
    bh = _f(r.get("back_home", ""))
    ba = _f(r.get("back_away", ""))
    bd = _f(r.get("back_draw", ""))
    if og is None or ov is None:
        return None
    return {
        "opta_gap": round(og - ov, 2),   # + = home domina, - = away domina
        "opta_home": og,
        "opta_away": ov,
        "back_home": bh,
        "back_away": ba,
        "back_draw": bd,
        "minuto": window[-1][0],
    }

# ── Buckets de analisis ───────────────────────────────────────────────────────

class Bucket:
    def __init__(self):
        self.n = 0
        self.wins = 0
    def add(self, win):
        self.n += 1
        if win:
            self.wins += 1
    def pct(self):
        return self.wins / self.n * 100 if self.n else 0
    def __repr__(self):
        return f"{self.pct():.1f}% ({self.wins}/{self.n})"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    csvs = sorted(DATA_DIR.glob("partido_*.csv"))
    print(f"CSVs encontrados: {len(csvs)}")

    # --- Cobertura ---
    total = 0
    has_opta = 0
    has_result = 0
    has_opta_and_result = 0

    # --- Gap vs resultado (por ventana de minutos) ---
    # Ventanas: 1-30, 31-60, 61-90
    windows = [(1, 30, "min1-30"), (31, 60, "min31-60"), (61, 90, "min61-90")]

    # Gap categories: negative (<-20), small (-20 to -5), neutral (-5 to 5), small (5-20), large (>20)
    # Simplificado: home_dom (gap>10), neutral (-10 to 10), away_dom (gap<-10)
    # Resultado esperado si home_dom -> home win?
    gap_result_home_dom = Bucket()  # gap>10 -> home win?
    gap_result_away_dom = Bucket()  # gap<-10 -> away win?
    gap_result_neutral_draw = Bucket()  # -10<=gap<=10 -> draw?

    # Por ventana de tiempo
    win_buckets = {label: {"home_dom_win": Bucket(), "away_dom_win": Bucket(), "neutral_draw": Bucket()}
                   for _, _, label in windows}

    # --- Señal LAY: favorito en cuotas siendo dominado en Opta ---
    # Definicion: back_home < back_away (home es favorito) PERO opta_gap < -10 (away domina)
    # -> LAY home (apostar a que home NO gana)
    lay_home_bucket = Bucket()   # home era fav en cuotas, away domina Opta -> HOME NO gana?
    lay_away_bucket = Bucket()   # away era fav en cuotas, home domina Opta -> AWAY NO gana?

    # Threshold de gap para considerar "dominio claro"
    GAP_THRESHOLD = 15

    # --- Señal DRAW: opta_gap muy pequeno + cuota draw alta (ignorada por mercado) ---
    draw_signal_bucket = Bucket()

    # Tracking partidos
    partidos_procesados = []

    for f in csvs:
        try:
            with open(f, encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
        except Exception:
            continue

        if not rows:
            continue

        total += 1
        live_rows = _get_live_rows(rows)

        # Check opta coverage
        opta_ok = any(_f(r.get("opta_points_local", "")) is not None for _, r in live_rows)
        if opta_ok:
            has_opta += 1

        result = _result(rows)
        if result:
            has_result += 1

        if not (opta_ok and result):
            continue

        has_opta_and_result += 1

        # Snapshot en el minuto 35-55 (corazon del partido, datos estables)
        snap_mid = _snap(live_rows, 35, 55)
        if snap_mid:
            gap = snap_mid["opta_gap"]
            bh = snap_mid["back_home"]
            ba = snap_mid["back_away"]
            bd = snap_mid["back_draw"]

            # Gap vs resultado global
            if gap > GAP_THRESHOLD:
                gap_result_home_dom.add(result == "home")
            elif gap < -GAP_THRESHOLD:
                gap_result_away_dom.add(result == "away")
            else:
                gap_result_neutral_draw.add(result == "draw")

            # Señal LAY: favorito en cuotas siendo dominado
            if bh is not None and ba is not None:
                if bh < ba and gap < -GAP_THRESHOLD:
                    # Home era fav en cuotas pero away domina Opta -> LAY home
                    lay_home_bucket.add(result != "home")  # "ganas" si home NO gana
                if ba < bh and gap > GAP_THRESHOLD:
                    # Away era fav en cuotas pero home domina Opta -> LAY away
                    lay_away_bucket.add(result != "away")

            # Señal DRAW: gap pequeno + cuota draw >= 3.5 (mercado ignora el empate)
            if abs(gap) <= 8 and bd is not None and bd >= 3.5:
                draw_signal_bucket.add(result == "draw")

        # Por ventana de tiempo
        for min_from, min_to, label in windows:
            snap = _snap(live_rows, min_from, min_to)
            if not snap:
                continue
            gap = snap["opta_gap"]
            if gap > GAP_THRESHOLD:
                win_buckets[label]["home_dom_win"].add(result == "home")
                win_buckets[label]["away_dom_win"].add(False)  # N/A
            elif gap < -GAP_THRESHOLD:
                win_buckets[label]["away_dom_win"].add(result == "away")
                win_buckets[label]["home_dom_win"].add(False)  # N/A
            else:
                win_buckets[label]["neutral_draw"].add(result == "draw")

        partidos_procesados.append({
            "file": f.name,
            "result": result,
            "snap_mid": snap_mid,
        })

    # ── REPORTE ──────────────────────────────────────────────────────────────

    print("\n" + "="*60)
    print("ANALISIS OPTA_POINTS - COBERTURA")
    print("="*60)
    print(f"  Total partidos:              {total}")
    print(f"  Con datos Opta:              {has_opta} ({has_opta/total*100:.1f}%)")
    print(f"  Con resultado conocido:      {has_result} ({has_result/total*100:.1f}%)")
    print(f"  Con Opta + resultado:        {has_opta_and_result} ({has_opta_and_result/total*100:.1f}%)")

    print("\n" + "="*60)
    print("GAP OPTA (min 35-55) vs RESULTADO FINAL")
    print(f"  (Threshold dominio = >{GAP_THRESHOLD} puntos)")
    print("="*60)
    print(f"  Home domina (gap>{GAP_THRESHOLD}) -> home gana:   {gap_result_home_dom}")
    print(f"  Away domina (gap<-{GAP_THRESHOLD}) -> away gana:  {gap_result_away_dom}")
    print(f"  Igualados (|gap|<={GAP_THRESHOLD}) -> empate:     {gap_result_neutral_draw}")

    print("\n" + "="*60)
    print("GAP OPTA vs RESULTADO - POR VENTANA DE TIEMPO")
    print("="*60)
    for _, _, label in windows:
        b = win_buckets[label]
        print(f"\n  [{label}]")
        print(f"    Home domina -> home gana:    {b['home_dom_win']}")
        print(f"    Away domina -> away gana:    {b['away_dom_win']}")
        print(f"    Igualados -> empate:         {b['neutral_draw']}")

    print("\n" + "="*60)
    print("SEÑAL LAY - FAVORITO EN CUOTAS DOMINADO EN OPTA")
    print("="*60)
    total_lay = lay_home_bucket.n + lay_away_bucket.n
    print(f"  LAY home (home fav cuotas, away domina Opta):")
    print(f"    -> home NO gana:   {lay_home_bucket}  (ganas el lay)")
    print(f"  LAY away (away fav cuotas, home domina Opta):")
    print(f"    -> away NO gana:   {lay_away_bucket}  (ganas el lay)")
    print(f"  Total señales LAY evaluadas: {total_lay}")

    print("\n" + "="*60)
    print("SEÑAL DRAW - OPTA IGUALADO + CUOTA DRAW >= 3.5")
    print("="*60)
    print(f"  |gap|<=8 + back_draw>=3.5 -> empate: {draw_signal_bucket}")

    # Detalle de los casos LAY para entender la distribucion de gaps
    print("\n" + "="*60)
    print("DISTRIBUCION DE GAPS (min 35-55) EN PARTIDOS CON OPTA")
    print("="*60)
    gaps = [p["snap_mid"]["opta_gap"] for p in partidos_procesados if p["snap_mid"]]
    if gaps:
        gaps_sorted = sorted(gaps)
        n = len(gaps_sorted)
        p25 = gaps_sorted[n//4]
        p50 = gaps_sorted[n//2]
        p75 = gaps_sorted[3*n//4]
        avg = sum(gaps) / n
        print(f"  N partidos con snap:  {n}")
        print(f"  Media:                {avg:.1f}")
        print(f"  P25 / P50 / P75:      {p25:.1f} / {p50:.1f} / {p75:.1f}")
        print(f"  Min / Max:            {gaps_sorted[0]:.1f} / {gaps_sorted[-1]:.1f}")
        print(f"  |gap| > {GAP_THRESHOLD} (dominio claro): {sum(1 for g in gaps if abs(g)>GAP_THRESHOLD)} ({sum(1 for g in gaps if abs(g)>GAP_THRESHOLD)/n*100:.1f}%)")
        print(f"  |gap| <= 8 (igualado): {sum(1 for g in gaps if abs(g)<=8)} ({sum(1 for g in gaps if abs(g)<=8)/n*100:.1f}%)")

    # Tabla de gaps por buckets vs resultado
    print("\n" + "="*60)
    print("TABLA DETALLADA: RANGOS DE GAP vs RESULTADO")
    print("="*60)
    ranges = [
        ("<-30",  None, -30),
        ("-30 a -15", -30, -15),
        ("-15 a -5",  -15, -5),
        ("-5 a 5",    -5,  5),
        ("5 a 15",    5,   15),
        ("15 a 30",   15,  30),
        (">30",       30,  None),
    ]
    print(f"  {'Rango':15} {'N':>5} {'Home%':>7} {'Draw%':>7} {'Away%':>7}")
    print(f"  {'-'*45}")
    for label, lo, hi in ranges:
        bucket_rows = [p for p in partidos_procesados
                       if p["snap_mid"] and
                       (lo is None or p["snap_mid"]["opta_gap"] >= lo) and
                       (hi is None or p["snap_mid"]["opta_gap"] < hi)]
        if not bucket_rows:
            continue
        n = len(bucket_rows)
        nh = sum(1 for p in bucket_rows if p["result"] == "home")
        nd = sum(1 for p in bucket_rows if p["result"] == "draw")
        na = sum(1 for p in bucket_rows if p["result"] == "away")
        print(f"  {label:15} {n:>5} {nh/n*100:>6.1f}% {nd/n*100:>6.1f}% {na/n*100:>6.1f}%")

    print("\n" + "="*60)
    print("CONCLUSION")
    print("="*60)

if __name__ == "__main__":
    main()
