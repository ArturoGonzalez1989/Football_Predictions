"""
Baseline capture script — run BEFORE the strategy trigger refactor.
Saves: auxiliar/refactor_baseline_cartera.json (analyze_cartera results)
       auxiliar/refactor_baseline_sd.json      (generate_all_new_bets counts)
"""
import sys
import os
import json
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "betfair_scraper", "dashboard", "backend")
AUXILIAR = os.path.join(ROOT, "auxiliar")
sys.path.insert(0, BACKEND)

# ── 1. analyze_cartera() baseline ─────────────────────────────────────────────
print("Running analyze_cartera()...")
from utils import csv_reader
result = csv_reader.analyze_cartera()

bets = result.get("bets", [])
by_strategy = defaultdict(lambda: {"count": 0, "wins": 0, "pl": 0.0})
for b in bets:
    s = b.get("strategy", "unknown")
    by_strategy[s]["count"] += 1
    if b.get("won"):
        by_strategy[s]["wins"] += 1
    by_strategy[s]["pl"] = round(by_strategy[s]["pl"] + b.get("pl", 0.0), 4)

for s in by_strategy:
    c = by_strategy[s]["count"]
    w = by_strategy[s]["wins"]
    by_strategy[s]["wr"] = round(w / c * 100, 2) if c > 0 else 0.0
    by_strategy[s]["roi"] = round(by_strategy[s]["pl"] / c * 10 * 100, 2) if c > 0 else 0.0

total_bets = len(bets)
total_pl = round(sum(b.get("pl", 0.0) for b in bets), 4)
cartera_baseline = {
    "total_bets": total_bets,
    "total_pl": total_pl,
    "by_strategy": dict(by_strategy),
}
out_cartera = os.path.join(AUXILIAR, "refactor_baseline_cartera.json")
with open(out_cartera, "w") as f:
    json.dump(cartera_baseline, f, indent=2)
print(f"  >> {total_bets} bets, P/L={total_pl:.2f} EUR")
for s, d in sorted(by_strategy.items()):
    print(f"    {s:40s}  N={d['count']:4d}  WR={d['wr']:5.1f}%  ROI={d['roi']:6.1f}%")
print(f"  Saved to {out_cartera}")

# ── 2. generate_all_new_bets() baseline ───────────────────────────────────────
print("\nRunning generate_all_new_bets()...")
sys.path.insert(0, AUXILIAR)
from sd_generators import generate_all_new_bets

DATA_DIR = os.path.join(ROOT, "betfair_scraper", "data")
sd_bets = generate_all_new_bets(DATA_DIR)

sd_by_strategy = defaultdict(lambda: {"count": 0, "wins": 0, "pl": 0.0})
for b in sd_bets:
    s = b.get("strategy", "unknown")
    sd_by_strategy[s]["count"] += 1
    if b.get("won"):
        sd_by_strategy[s]["wins"] += 1
    sd_by_strategy[s]["pl"] = round(sd_by_strategy[s]["pl"] + b.get("pl", 0.0), 4)

for s in sd_by_strategy:
    c = sd_by_strategy[s]["count"]
    w = sd_by_strategy[s]["wins"]
    sd_by_strategy[s]["wr"] = round(w / c * 100, 2) if c > 0 else 0.0
    sd_by_strategy[s]["roi"] = round(sd_by_strategy[s]["pl"] / c * 100, 2) if c > 0 else 0.0

sd_baseline = {
    "total_bets": len(sd_bets),
    "by_strategy": dict(sd_by_strategy),
}
out_sd = os.path.join(AUXILIAR, "refactor_baseline_sd.json")
with open(out_sd, "w") as f:
    json.dump(sd_baseline, f, indent=2)

print(f"  >> {len(sd_bets)} total SD bets")
for s, d in sorted(sd_by_strategy.items()):
    print(f"    {s:40s}  N={d['count']:4d}  WR={d['wr']:5.1f}%  ROI={d['roi']:6.1f}%")
print(f"  Saved to {out_sd}")

print("\nBaseline captured successfully.")
