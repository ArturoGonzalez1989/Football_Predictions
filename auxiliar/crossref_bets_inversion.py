"""
Cruza el export BT con la deteccion de inversion de cuotas.
Identifica apuestas BT colocadas en minutos con cuotas anomalas.

Uso: python auxiliar/crossref_bets_inversion.py
"""
import csv, glob, os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR  = ROOT / "betfair_scraper" / "data"
ANALISIS  = ROOT / "analisis"

# -- 1. Cargar el export BT mas reciente ---------------------------------------
exports = sorted(ANALISIS.glob("bt_results_*.csv"))
if not exports:
    print("No se encontro ningun bt_results_*.csv en analisis/")
    exit(1)
BT_PATH = exports[-1]
print(f"BT export : {BT_PATH.name}")

with open(BT_PATH, newline="", encoding="utf-8") as f:
    bt_bets = list(csv.DictReader(f))

# match_id en BT es p.ej. "seattle-sounders-colorado-apuestas-12345"
# CSV en data/ es "partido_seattle-sounders-colorado-apuestas-12345.csv"
# Construimos indice match_id -> lista de bets
bt_by_match = defaultdict(list)
for b in bt_bets:
    try:
        b["_minuto"] = int(float(b.get("minuto") or 0))
    except (ValueError, TypeError):
        b["_minuto"] = 0
    bt_by_match[b["match_id"]].append(b)

# -- 2. Detectar minutos anomalos por partido (misma logica que el endpoint) --
RATIO_THRESHOLD = 5.0
anomalous_minutes = {}   # match_id -> set de minutos int con inversion

csv_files = sorted(DATA_DIR.glob("partido_*.csv"))
print(f"CSVs data : {len(csv_files)}")

for fp in csv_files:
    match_id = fp.stem.replace("partido_", "")
    try:
        with open(fp, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            h = {hdr: i for i, hdr in enumerate(headers)}
            rows = list(reader)
    except Exception:
        continue

    bad_minutes = set()
    for row in rows:
        estado = row[h["estado_partido"]] if "estado_partido" in h and h["estado_partido"] < len(row) else ""
        if estado != "en_juego":
            continue

        def _g(col):
            i = h.get(col)
            if i is None or i >= len(row):
                return None
            try: return float(row[i])
            except: return None

        gl = _g("goles_local"); gv = _g("goles_visitante")
        bh = _g("back_home");   ba = _g("back_away")
        if None in (gl, gv, bh, ba):
            continue

        minute_raw = row[h["minuto"]] if "minuto" in h else ""
        try:
            minute = int(float(minute_raw))
        except (ValueError, TypeError):
            continue

        if gv > gl and bh > 0 and ba / bh > RATIO_THRESHOLD:
            bad_minutes.add(minute)
        elif gl > gv and ba > 0 and bh / ba > RATIO_THRESHOLD:
            bad_minutes.add(minute)

    if bad_minutes:
        anomalous_minutes[match_id] = bad_minutes

print(f"Partidos con inversion detectada: {len(anomalous_minutes)}\n")

# -- 3. Cruce: apuestas BT en minutos anomalos ---------------------------------
flagged = []
for match_id, bets in bt_by_match.items():
    bad_mins = anomalous_minutes.get(match_id, set())
    if not bad_mins:
        continue
    for b in bets:
        m = b["_minuto"]
        # Ventana: el minuto exacto o el anterior (min_dur=2 puede usar first_seen-1)
        if m in bad_mins or (m - 1) in bad_mins or (m + 1) in bad_mins:
            flagged.append({
                "match_id":      match_id,
                "match_name":    b.get("match_name", ""),
                "strategy":      b.get("strategy", ""),
                "strategy_label":b.get("strategy_label", ""),
                "minuto":        m,
                "mercado":       b.get("mercado", ""),
                "back_odds":     b.get("back_odds", ""),
                "score_bet":     b.get("score_bet", ""),
                "score_final":   b.get("score_final", ""),
                "won":           b.get("won", ""),
                "pl":            b.get("pl", ""),
                "bad_minutes":   sorted(bad_mins),
            })

# -- 4. Reporte ----------------------------------------------------------------
if not flagged:
    print("Ninguna apuesta BT coincide con minutos de inversion detectada.")
else:
    print(f"APUESTAS BT CON POSIBLE DATO CORRUPTO: {len(flagged)}\n")
    print(f"{'Partido':<35} {'Strategy':<20} {'Min':>4} {'Mercado':<18} {'Odds':>5} {'Score':>5} {'FT':>5} {'Won':<5} {'PL':>6}")
    print("-" * 110)
    for b in sorted(flagged, key=lambda x: x["match_name"]):
        name = b["match_name"][:34]
        print(f"{name:<35} {b['strategy']:<20} {b['minuto']:>4} {b['mercado']:<18} "
              f"{b['back_odds']:>5} {b['score_bet']:>5} {b['score_final']:>5} "
              f"{b['won']:<5} {float(b['pl'] or 0):>6.2f}")

    total_pl = sum(float(b["pl"] or 0) for b in flagged)
    wins = sum(1 for b in flagged if str(b["won"]).upper() == "TRUE")
    n = len(flagged)
    print(f"\nResumen: N={n}, Wins={wins}, WR={wins/n*100:.1f}%, PL={total_pl:.2f}, ROI={total_pl/n*100:.1f}%")
    print(f"PL si se excluyen estas apuestas del portfolio: {929.25 - total_pl:.2f}")
