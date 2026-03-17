"""
Estudio: ¿la primera apuesta por partido es más rentable que las siguientes?

Agrupa las apuestas del export BT por match_id, las ordena por minuto,
y compara el rendimiento según el orden de entrada (1ª, 2ª, 3ª, ...).

Uso: python auxiliar/analyze_bet_order.py
"""
import csv
import glob
import os
from collections import defaultdict

# Buscar el export BT más reciente
ANALISIS_DIR = os.path.join(os.path.dirname(__file__), "..", "analisis")
exports = sorted(glob.glob(os.path.join(ANALISIS_DIR, "bt_results_*.csv")))
if not exports:
    print("No se encontró ningún bt_results_*.csv en analisis/")
    exit(1)
CSV_PATH = exports[-1]
print(f"Usando: {os.path.basename(CSV_PATH)}\n")

# Leer bets
with open(CSV_PATH, newline="", encoding="utf-8") as f:
    bets = list(csv.DictReader(f))

# Convertir tipos
for b in bets:
    try:
        b["minuto"] = int(float(b.get("minuto") or 0))
    except (ValueError, TypeError):
        b["minuto"] = 0
    try:
        b["pl"] = float(b.get("pl") or 0)
    except (ValueError, TypeError):
        b["pl"] = 0.0
    b["won"] = b.get("won", "").strip().upper() == "TRUE"

# Agrupar por partido y ordenar por minuto
by_match = defaultdict(list)
for b in bets:
    by_match[b["match_id"]].append(b)
for mid in by_match:
    by_match[mid].sort(key=lambda x: x["minuto"])

# ── Estadísticas por orden de apuesta ─────────────────────────────────────────
order_stats = defaultdict(lambda: {"n": 0, "wins": 0, "pl": 0.0})
for mid, match_bets in by_match.items():
    for rank, b in enumerate(match_bets, 1):
        key = rank if rank <= 4 else "5+"
        order_stats[key]["n"] += 1
        order_stats[key]["wins"] += int(b["won"])
        order_stats[key]["pl"] += b["pl"]

print(f"{'Orden':>6} | {'N':>5} | {'Wins':>5} | {'WR%':>6} | {'ROI%':>7} | {'PL':>8} | {'PL/bet':>7}")
print("-" * 60)
for rank in sorted(order_stats.keys(), key=lambda x: (str(x).replace("+","99"))):
    s = order_stats[rank]
    n = s["n"]
    wins = s["wins"]
    pl = s["pl"]
    wr = wins / n * 100 if n else 0
    roi = pl / n * 100 if n else 0
    print(f"{'#'+str(rank):>6} | {n:>5} | {wins:>5} | {wr:>5.1f}% | {roi:>6.1f}% | {pl:>8.2f} | {pl/n:>7.3f}")

# ── Cartera: solo 1ª apuesta vs todo ──────────────────────────────────────────
first_only = [match_bets[0] for match_bets in by_match.values()]
all_bets = bets

def stats(bets_list, label):
    n = len(bets_list)
    wins = sum(1 for b in bets_list if b["won"])
    pl = sum(b["pl"] for b in bets_list)
    wr = wins / n * 100 if n else 0
    roi = pl / n * 100 if n else 0
    print(f"  {label:<30} N={n:>5}  WR={wr:>5.1f}%  ROI={roi:>6.1f}%  PL={pl:>8.2f}  PL/bet={pl/n:>7.3f}")

print(f"\n── Cartera: primera apuesta vs completa ──")
stats(all_bets,    "Todas las apuestas")
stats(first_only,  "Solo 1ª apuesta/partido")

# ── Partidos con múltiples apuestas: breakdown ────────────────────────────────
multi = {mid: bets for mid, bets in by_match.items() if len(bets) > 1}
single = {mid: bets for mid, bets in by_match.items() if len(bets) == 1}

print(f"\n── Partidos con múltiples apuestas ──")
print(f"  Partidos con 1 apuesta:    {len(single)}")
print(f"  Partidos con 2+ apuestas:  {len(multi)}")
dist = defaultdict(int)
for bets_list in by_match.values():
    dist[len(bets_list)] += 1
for k in sorted(dist):
    print(f"    {k} apuesta(s): {dist[k]} partidos")

# ── En partidos multi-apuesta: 1ª vs resto ────────────────────────────────────
if multi:
    first_in_multi  = [bl[0]  for bl in multi.values()]
    others_in_multi = [b for bl in multi.values() for b in bl[1:]]
    print(f"\n── En partidos con 2+ apuestas ──")
    stats(first_in_multi,  "1ª apuesta")
    stats(others_in_multi, "2ª+ apuestas")

# ── Por estrategia: cuántas veces es 1ª vs no-1ª ─────────────────────────────
strat_order = defaultdict(lambda: {"first": 0, "later": 0, "pl_first": 0.0, "pl_later": 0.0,
                                    "wins_first": 0, "wins_later": 0})
for mid, match_bets in by_match.items():
    for rank, b in enumerate(match_bets):
        st = b["strategy"]
        if rank == 0:
            strat_order[st]["first"] += 1
            strat_order[st]["pl_first"] += b["pl"]
            strat_order[st]["wins_first"] += int(b["won"])
        else:
            strat_order[st]["later"] += 1
            strat_order[st]["pl_later"] += b["pl"]
            strat_order[st]["wins_later"] += int(b["won"])

print(f"\n── Por estrategia: veces que es 1ª vs tardía ──")
print(f"  {'Strategy':<22} | {'1ª(N)':>6} | {'WR1%':>6} | {'ROI1%':>7} | {'Tard(N)':>7} | {'WRt%':>6} | {'ROIt%':>7}")
print("  " + "-" * 80)
for st, d in sorted(strat_order.items(), key=lambda x: -(x[1]["first"] + x[1]["later"])):
    n1 = d["first"]; nl = d["later"]
    wr1 = d["wins_first"] / n1 * 100 if n1 else 0
    wrl = d["wins_later"] / nl * 100 if nl else 0
    roi1 = d["pl_first"] / n1 * 100 if n1 else 0
    roil = d["pl_later"] / nl * 100 if nl else 0
    print(f"  {st:<22} | {n1:>6} | {wr1:>5.1f}% | {roi1:>6.1f}% | {nl:>7} | {wrl:>5.1f}% | {roil:>6.1f}%")
