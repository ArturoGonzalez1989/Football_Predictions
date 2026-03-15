"""Compare BT vs LIVE estimated performance using reconcile data."""
import sys, os, json
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'betfair_scraper', 'dashboard', 'backend'))

from utils import csv_reader

CFG_PATH = os.path.join(os.path.dirname(__file__), '..', 'betfair_scraper', 'cartera_config.json')

with open(CFG_PATH) as f:
    cfg = json.load(f)

s = cfg.get('strategies', {})

# Strategies enabled in config
ENABLED = {k for k, v in s.items() if isinstance(v, dict) and v.get('enabled', False)}

# --- BT bets ---
if hasattr(csv_reader, '_cartera_cache'):
    csv_reader._cartera_cache.clear()
bt_raw = csv_reader.analyze_cartera()
all_bets = bt_raw.get('bets', [])

# Include all bets for enabled strategies (params already applied by triggers)
bt_filtered = [b for b in all_bets if b.get('strategy') in ENABLED]

# --- Stats ---
n = len(bt_filtered)
wins = sum(1 for b in bt_filtered if b.get('won'))
pl = sum(b.get('pl', 0) for b in bt_filtered)
roi = pl / (n * 10) * 100

run_pl = 0.0
peak = 0.0
max_dd = 0.0
for b in sorted(bt_filtered, key=lambda x: x.get('timestamp_utc', '')):
    run_pl += b.get('pl', 0)
    if run_pl > peak:
        peak = run_pl
    if peak - run_pl > max_dd:
        max_dd = peak - run_pl

strats = defaultdict(lambda: {'n': 0, 'w': 0, 'pl': 0.0})
for b in bt_filtered:
    sn = b.get('strategy', '?')
    strats[sn]['n'] += 1
    if b.get('won'):
        strats[sn]['w'] += 1
    strats[sn]['pl'] += b.get('pl', 0)

print("=" * 65)
print("  BACKTEST COMPLETO (config-filtered)")
print("=" * 65)
print(f"  N={n}  WR={wins/n*100:.1f}%  P/L={pl:.1f}  ROI={roi:.1f}%  MaxDD={max_dd:.1f}")
print()
for sn in sorted(strats):
    d = strats[sn]
    swr = d['w'] / d['n'] * 100
    sroi = d['pl'] / (d['n'] * 10) * 100
    print(f"  {sn:25s} N={d['n']:4d}  WR={swr:5.1f}%  P/L={d['pl']:8.1f}  ROI={sroi:6.1f}%")

# --- Reconcile data (from last run) ---
# BT_ONLY: bets in BT but NOT in LIVE
# LIVE_ONLY: bets in LIVE but NOT in BT
bt_only_counts = {
    'back_draw_00': 9, 'goal_clustering': 8, 'momentum_xg': 15,
    'odds_drift': 0, 'pressure_cooker': 2, 'tarde_asia': 0, 'xg_underperformance': 14,
}
live_only_counts = {
    'back_draw_00': 15, 'goal_clustering': 7, 'momentum_xg': 10,
    'odds_drift': 2, 'pressure_cooker': 1, 'tarde_asia': 5, 'xg_underperformance': 19,
}

print()
print("=" * 65)
print("  ESTIMACION: BT vs LIVE")
print("=" * 65)
print()
print("  Asumiendo que BT_ONLY y LIVE_ONLY tienen el MISMO WR/ROI")
print("  que el promedio de su estrategia:")
print()

header = f"  {'Estrategia':25s} {'BT N':>5s} {'BT P/L':>9s} | {'LIVE N':>6s} {'LIVE P/L':>9s} | {'dN':>4s} {'dP/L':>8s}"
print(header)
print("  " + "-" * len(header.strip()))

live_n_tot = 0
live_pl_tot = 0.0

for sn in sorted(strats):
    d = strats[sn]
    bt_only_n = bt_only_counts.get(sn, 0)
    live_only_n = live_only_counts.get(sn, 0)

    live_n = d['n'] - bt_only_n + live_only_n
    avg_pl = d['pl'] / d['n'] if d['n'] else 0
    live_pl_s = d['pl'] - (bt_only_n * avg_pl) + (live_only_n * avg_pl)

    live_n_tot += live_n
    live_pl_tot += live_pl_s

    dn = live_n - d['n']
    dpl = live_pl_s - d['pl']
    print(f"  {sn:25s} {d['n']:5d} {d['pl']:9.1f} | {live_n:6d} {live_pl_s:9.1f} | {dn:+4d} {dpl:+8.1f}")

live_roi_tot = live_pl_tot / (live_n_tot * 10) * 100 if live_n_tot else 0

print()
print(f"  {'TOTAL':25s} {n:5d} {pl:9.1f} | {live_n_tot:6d} {live_pl_tot:9.1f} | {live_n_tot-n:+4d} {live_pl_tot-pl:+8.1f}")
print()
print(f"  BT  ROI: {roi:.1f}%")
print(f"  LIVE ROI (est): {live_roi_tot:.1f}%")
print(f"  Delta ROI: {live_roi_tot - roi:+.1f}pp")
print()

if live_pl_tot >= pl:
    print("  CONCLUSION: LIVE genera MAS P/L que BT.")
    print("  El BT es CONSERVADOR -- subestima el rendimiento real.")
else:
    print("  CONCLUSION: LIVE genera MENOS P/L que BT.")
    print("  El BT SOBREESTIMA el rendimiento real.")

print()
print("  NOTA: Estimacion basada en asumir que los bets extra/faltantes")
print("  tienen la misma calidad que el promedio de su estrategia.")
print("  La realidad puede variar, pero la direccion es indicativa.")
