"""
Analisis de Drawdowns en la Cartera de Estrategias
===================================================
Objetivo: Identificar patrones durante periodos de drawdown
para buscar posibles contra-estrategias o mitigaciones.
"""
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

# Fetch cartera data from API
result = subprocess.run(
    [sys.executable, "-c", """
import sys
sys.path.insert(0, r'c:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/betfair_scraper/dashboard/backend')
from utils import csv_reader
import json
data = csv_reader.analyze_cartera()
print(json.dumps(data))
"""],
    capture_output=True, text=True, timeout=120
)
data = json.loads(result.stdout)
bets = data["bets"]

# Sort chronologically
bets.sort(key=lambda b: b.get("timestamp_utc", ""))

print("=" * 70)
print("ANALISIS DE DRAWDOWNS EN LA CARTERA")
print("=" * 70)
print(f"\nTotal apuestas: {len(bets)}")

# ============================================================
# 1. IDENTIFY DRAWDOWN PERIODS
# ============================================================
print("\n" + "=" * 70)
print("1. PERIODOS DE DRAWDOWN (Flat €10)")
print("=" * 70)

cum = 0
peak = 0
peak_idx = 0
drawdowns = []  # list of (start_idx, end_idx, peak_val, trough_val, bets_in_dd)
in_dd = False
dd_start = 0
dd_peak = 0

cumulative = []
for i, b in enumerate(bets):
    cum += b["pl"]
    cumulative.append(cum)

    if cum > peak:
        if in_dd:
            # DD ended - record it
            drawdowns.append({
                "start": dd_start,
                "end": i - 1,
                "peak": dd_peak,
                "trough": min(cumulative[dd_start:i]),
                "trough_idx": dd_start + cumulative[dd_start:i].index(min(cumulative[dd_start:i])),
                "bets": list(range(dd_start, i)),
                "depth": dd_peak - min(cumulative[dd_start:i]),
                "recovery_bet": i,
            })
            in_dd = False
        peak = cum
        peak_idx = i
    elif cum < peak - 5:  # DD threshold: at least €5 drop
        if not in_dd:
            in_dd = True
            dd_start = peak_idx + 1
            dd_peak = peak

# If still in DD at end
if in_dd:
    drawdowns.append({
        "start": dd_start,
        "end": len(bets) - 1,
        "peak": dd_peak,
        "trough": min(cumulative[dd_start:]),
        "trough_idx": dd_start + cumulative[dd_start:].index(min(cumulative[dd_start:])),
        "bets": list(range(dd_start, len(bets))),
        "depth": dd_peak - min(cumulative[dd_start:]),
        "recovery_bet": None,
    })

print(f"\nDrawdowns detectados (umbral >= €5): {len(drawdowns)}")
for j, dd in enumerate(drawdowns):
    dd_bets = [bets[i] for i in dd["bets"]]
    losses = [b for b in dd_bets if b["pl"] < 0]
    wins = [b for b in dd_bets if b["pl"] > 0]
    strats = defaultdict(int)
    strat_losses = defaultdict(float)
    for b in dd_bets:
        strats[b["strategy"]] += 1
        if b["pl"] < 0:
            strat_losses[b["strategy"]] += b["pl"]

    print(f"\n--- Drawdown #{j+1} ---")
    print(f"  Apuestas #{dd['start']+1} a #{dd['end']+1} ({len(dd['bets'])} apuestas)")
    print(f"  Profundidad: -{dd['depth']:.2f} EUR (de +{dd['peak']:.2f} a +{dd['trough']:.2f})")
    print(f"  Perdedoras: {len(losses)}/{len(dd_bets)} ({len(losses)/len(dd_bets)*100:.0f}%)")
    if dd["recovery_bet"] is not None:
        print(f"  Recuperacion: apuesta #{dd['recovery_bet']+1}")
    else:
        print(f"  Recuperacion: AUN EN DRAWDOWN")

    print(f"  Por estrategia:")
    for s, c in sorted(strats.items()):
        loss = strat_losses.get(s, 0)
        l_count = sum(1 for b in dd_bets if b["strategy"] == s and b["pl"] < 0)
        print(f"    {s}: {c} apuestas, {l_count} perdidas ({loss:.2f} EUR)")

# ============================================================
# 2. LOSING STREAK ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("2. RACHAS PERDEDORAS (3+ consecutivas)")
print("=" * 70)

streaks = []
cur_streak = []
for i, b in enumerate(bets):
    if b["pl"] < 0:
        cur_streak.append(i)
    else:
        if len(cur_streak) >= 3:
            streaks.append(cur_streak[:])
        cur_streak = []
if len(cur_streak) >= 3:
    streaks.append(cur_streak[:])

print(f"\nRachas de 3+ fallos: {len(streaks)}")
for j, streak in enumerate(streaks):
    streak_bets = [bets[i] for i in streak]
    total_loss = sum(b["pl"] for b in streak_bets)
    strats = [b["strategy"] for b in streak_bets]

    print(f"\n--- Racha #{j+1}: {len(streak)} fallos (apuestas #{streak[0]+1}-#{streak[-1]+1}) ---")
    print(f"  Perdida total: {total_loss:.2f} EUR")
    print(f"  Estrategias: {', '.join(strats)}")

    # What happened AFTER the streak?
    next_idx = streak[-1] + 1
    if next_idx < len(bets):
        next_3 = bets[next_idx:next_idx+3]
        next_results = [f"{'W' if b['pl'] > 0 else 'L'} ({b['strategy'][:8]})" for b in next_3]
        print(f"  Siguientes 3: {', '.join(next_results)}")

# ============================================================
# 3. CROSS-STRATEGY CORRELATION
# ============================================================
print("\n" + "=" * 70)
print("3. CORRELACION ENTRE ESTRATEGIAS")
print("=" * 70)
print("  (¿Cuando una pierde, las otras tambien?)")

# Group bets by date
by_date = defaultdict(list)
for b in bets:
    ts = b.get("timestamp_utc", "")
    if ts:
        date = ts[:10]
        by_date[date].append(b)

# Days where multiple strategies bet
multi_strat_days = {d: bs for d, bs in by_date.items() if len(set(b["strategy"] for b in bs)) >= 2}
print(f"\nDias con 2+ estrategias activas: {len(multi_strat_days)}")

# When one strategy loses on a day, does the other also lose?
same_day_correlation = {"both_lose": 0, "both_win": 0, "mixed": 0}
for date, day_bets in multi_strat_days.items():
    strat_results = defaultdict(list)
    for b in day_bets:
        strat_results[b["strategy"]].append(b["pl"] > 0)

    # Check if strategies that bet on same day tend to have correlated results
    results = []
    for s, rs in strat_results.items():
        results.append(all(rs))  # True if all wins for that strategy

    if all(results):
        same_day_correlation["both_win"] += 1
    elif not any(results):
        same_day_correlation["both_lose"] += 1
    else:
        same_day_correlation["mixed"] += 1

print(f"  Dias ambas ganan: {same_day_correlation['both_win']}")
print(f"  Dias ambas pierden: {same_day_correlation['both_lose']}")
print(f"  Dias resultado mixto: {same_day_correlation['mixed']}")

# ============================================================
# 4. ODDS ANALYSIS DURING LOSSES
# ============================================================
print("\n" + "=" * 70)
print("4. ANALISIS DE CUOTAS EN PERDIDAS vs GANANCIAS")
print("=" * 70)

for strat in ["back_draw_00", "xg_underperformance", "odds_drift", "goal_clustering"]:
    strat_bets = [b for b in bets if b["strategy"] == strat]
    if not strat_bets:
        continue

    wins = [b for b in strat_bets if b["pl"] > 0]
    losses = [b for b in strat_bets if b["pl"] < 0]

    def get_odds(b):
        return b.get("back_draw") or b.get("back_over_odds") or b.get("over_odds") or b.get("back_odds") or 0

    win_odds = [get_odds(b) for b in wins if get_odds(b) > 0]
    loss_odds = [get_odds(b) for b in losses if get_odds(b) > 0]

    print(f"\n{strat}:")
    if win_odds:
        print(f"  Cuotas ganadoras: avg={sum(win_odds)/len(win_odds):.2f}, min={min(win_odds):.2f}, max={max(win_odds):.2f}")
    if loss_odds:
        print(f"  Cuotas perdedoras: avg={sum(loss_odds)/len(loss_odds):.2f}, min={min(loss_odds):.2f}, max={max(loss_odds):.2f}")

# ============================================================
# 5. TIME-OF-DAY / DAY-OF-WEEK PATTERNS
# ============================================================
print("\n" + "=" * 70)
print("5. PATRON TEMPORAL - HORA/DIA DE LA SEMANA")
print("=" * 70)

hour_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pl": 0})
dow_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "pl": 0})

for b in bets:
    ts = b.get("timestamp_utc", "")
    if not ts:
        continue
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        h = dt.hour
        dow = dt.strftime("%A")

        if b["pl"] > 0:
            hour_stats[h]["wins"] += 1
            dow_stats[dow]["wins"] += 1
        else:
            hour_stats[h]["losses"] += 1
            dow_stats[dow]["losses"] += 1
        hour_stats[h]["pl"] += b["pl"]
        dow_stats[dow]["pl"] += b["pl"]
    except:
        pass

print("\nPor hora (UTC):")
for h in sorted(hour_stats.keys()):
    s = hour_stats[h]
    total = s["wins"] + s["losses"]
    wr = s["wins"] / total * 100 if total > 0 else 0
    print(f"  {h:02d}h: {total:2d} apuestas, WR {wr:5.1f}%, P/L {s['pl']:+7.2f}")

print("\nPor dia de la semana:")
for dow in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
    if dow in dow_stats:
        s = dow_stats[dow]
        total = s["wins"] + s["losses"]
        wr = s["wins"] / total * 100 if total > 0 else 0
        print(f"  {dow:10s}: {total:2d} apuestas, WR {wr:5.1f}%, P/L {s['pl']:+7.2f}")

# ============================================================
# 6. SCORE CONTEXT DURING LOSSES
# ============================================================
print("\n" + "=" * 70)
print("6. CONTEXTO DE MARCADOR EN PERDIDAS")
print("=" * 70)

for strat in ["back_draw_00", "xg_underperformance", "odds_drift", "goal_clustering"]:
    strat_losses = [b for b in bets if b["strategy"] == strat and b["pl"] < 0]
    strat_wins = [b for b in bets if b["strategy"] == strat and b["pl"] > 0]
    if not strat_losses:
        continue

    print(f"\n{strat} - Perdidas ({len(strat_losses)}):")
    for b in strat_losses:
        score = b.get("score", "?")
        ft = b.get("ft_score", "?")
        minuto = b.get("minuto", "?")
        match = b.get("match", "?")[:35]
        print(f"  {match:35s} | Score: {score} -> FT: {ft} | Min: {minuto}")

# ============================================================
# 7. SEQUENTIAL PATTERN: DOES A LOSS PREDICT THE NEXT?
# ============================================================
print("\n" + "=" * 70)
print("7. PATRON SECUENCIAL: ¿UNA PERDIDA PREDICE LA SIGUIENTE?")
print("=" * 70)

# After a loss, what's the probability of the next bet also being a loss?
after_loss_results = {"win": 0, "loss": 0}
after_win_results = {"win": 0, "loss": 0}
after_2_losses = {"win": 0, "loss": 0}

for i in range(1, len(bets)):
    prev_lost = bets[i-1]["pl"] < 0
    curr_won = bets[i]["pl"] > 0

    if prev_lost:
        after_loss_results["win" if curr_won else "loss"] += 1
    else:
        after_win_results["win" if curr_won else "loss"] += 1

    if i >= 2 and bets[i-1]["pl"] < 0 and bets[i-2]["pl"] < 0:
        after_2_losses["win" if curr_won else "loss"] += 1

total_al = after_loss_results["win"] + after_loss_results["loss"]
total_aw = after_win_results["win"] + after_win_results["loss"]
total_a2l = after_2_losses["win"] + after_2_losses["loss"]

print(f"\nTras 1 PERDIDA: {total_al} apuestas")
if total_al > 0:
    print(f"  WR siguiente: {after_loss_results['win']/total_al*100:.1f}% ({after_loss_results['win']}/{total_al})")
print(f"\nTras 1 GANANCIA: {total_aw} apuestas")
if total_aw > 0:
    print(f"  WR siguiente: {after_win_results['win']/total_aw*100:.1f}% ({after_win_results['win']}/{total_aw})")
print(f"\nTras 2 PERDIDAS consecutivas: {total_a2l} apuestas")
if total_a2l > 0:
    print(f"  WR siguiente: {after_2_losses['win']/total_a2l*100:.1f}% ({after_2_losses['win']}/{total_a2l})")

# ============================================================
# 8. MINUTE ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("8. MINUTO DE ENTRADA vs RESULTADO")
print("=" * 70)

for strat in ["xg_underperformance", "odds_drift", "goal_clustering"]:
    strat_bets = [b for b in bets if b["strategy"] == strat and b.get("minuto")]
    if not strat_bets:
        continue

    wins = [b for b in strat_bets if b["pl"] > 0]
    losses = [b for b in strat_bets if b["pl"] < 0]

    avg_min_win = sum(b["minuto"] for b in wins) / len(wins) if wins else 0
    avg_min_loss = sum(b["minuto"] for b in losses) / len(losses) if losses else 0

    print(f"\n{strat}:")
    print(f"  Minuto medio WINS: {avg_min_win:.1f} (n={len(wins)})")
    print(f"  Minuto medio LOSSES: {avg_min_loss:.1f} (n={len(losses)})")

# ============================================================
# 9. POTENTIAL HEDGE: LAY ON SAME MATCH
# ============================================================
print("\n" + "=" * 70)
print("9. IDEA: ¿PARTIDOS CON MULTIPLES SIGNALS SON MEJORES O PEORES?")
print("=" * 70)

match_bets = defaultdict(list)
for b in bets:
    match_bets[b["match_id"]].append(b)

multi_signal = {m: bs for m, bs in match_bets.items() if len(bs) >= 2}
single_signal = {m: bs for m, bs in match_bets.items() if len(bs) == 1}

print(f"\nPartidos con 1 signal: {len(single_signal)}")
single_all = [b for bs in single_signal.values() for b in bs]
single_wins = sum(1 for b in single_all if b["pl"] > 0)
single_pl = sum(b["pl"] for b in single_all)
print(f"  WR: {single_wins/len(single_all)*100:.1f}%, P/L: {single_pl:+.2f}")

print(f"\nPartidos con 2+ signals: {len(multi_signal)}")
if multi_signal:
    multi_all = [b for bs in multi_signal.values() for b in bs]
    multi_wins = sum(1 for b in multi_all if b["pl"] > 0)
    multi_pl = sum(b["pl"] for b in multi_all)
    print(f"  WR: {multi_wins/len(multi_all)*100:.1f}%, P/L: {multi_pl:+.2f}")

    for m, bs in multi_signal.items():
        strats = [b["strategy"][:10] for b in bs]
        results = ["W" if b["pl"] > 0 else "L" for b in bs]
        match_name = bs[0]["match"][:35]
        pl = sum(b["pl"] for b in bs)
        print(f"    {match_name:35s} | {', '.join(strats)} | {', '.join(results)} | P/L: {pl:+.2f}")

print("\n" + "=" * 70)
print("ANALISIS COMPLETADO")
print("=" * 70)
