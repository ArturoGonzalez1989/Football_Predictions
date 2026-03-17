"""
Compara resultados BT con min_dur=1 (actual) vs min_dur=2 (propuesto)
para las 8 estrategias de señal continua candidatas al cambio.

Uso: python auxiliar/test_min_dur.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "betfair_scraper", "dashboard", "backend"))

import json
from utils import csv_reader
from utils.csv_reader import _STRATEGY_REGISTRY, _analyze_strategy_simple, _cfg_add_snake_keys

TARGET_STRATEGIES = [
    "ud_leading",
    "home_fav_leading",
    "away_fav_leading",
    "longshot",
    "under35_late",
    "under35_3goals",
    "under45_3goals",
    "over25_2goal",
]

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "betfair_scraper", "cartera_config.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def run_strategy(key, trigger_fn, extract_fn, win_fn, cfg, min_dur):
    bets = _analyze_strategy_simple(key, trigger_fn, extract_fn, win_fn, _cfg_add_snake_keys(cfg), min_dur)
    if not bets:
        return {"n": 0, "wins": 0, "wr": 0.0, "roi": 0.0, "pl": 0.0}
    n = len(bets)
    wins = sum(1 for b in bets if b.get("won"))
    pl = sum(b.get("pl", 0) for b in bets)
    roi = pl / n * 100 if n > 0 else 0.0
    return {"n": n, "wins": wins, "wr": wins / n * 100, "roi": roi, "pl": pl}

def main():
    cfg_data = load_config()
    strategies_cfg = cfg_data.get("strategies", {})
    md = cfg_data.get("min_duration", {})

    # Build registry lookup
    # Registry tuple: (key, label, trigger_fn, description_str, extract_fn, win_fn)
    registry = {entry[0]: (entry[2], entry[4], entry[5]) for entry in _STRATEGY_REGISTRY}

    print(f"\n{'Strategy':<22} | {'min_dur':>7} | {'N':>5} | {'WR%':>6} | {'ROI%':>7} | {'PL':>7} | {'dN':>5} | {'dROI':>7}")
    print("-" * 95)

    for key in TARGET_STRATEGIES:
        if key not in registry:
            print(f"{key:<22} | NOT FOUND IN REGISTRY")
            continue
        trigger_fn, extract_fn, win_fn = registry[key]
        s_cfg = strategies_cfg.get(key, {})
        current_md = md.get(key, 1)

        # Run with current min_dur
        r1 = run_strategy(key, trigger_fn, extract_fn, win_fn, s_cfg, current_md)
        # Run with min_dur=2
        r2 = run_strategy(key, trigger_fn, extract_fn, win_fn, s_cfg, 2)

        delta_n   = r2["n"] - r1["n"]
        delta_roi = r2["roi"] - r1["roi"]

        print(f"{key:<22} | {current_md:>7} | {r1['n']:>5} | {r1['wr']:>5.1f}% | {r1['roi']:>6.1f}% | {r1['pl']:>7.2f} |")
        sign_n   = "+" if delta_n >= 0 else ""
        sign_roi = "+" if delta_roi >= 0 else ""
        print(f"{'':22} | {2:>7} | {r2['n']:>5} | {r2['wr']:>5.1f}% | {r2['roi']:>6.1f}% | {r2['pl']:>7.2f} | {sign_n}{delta_n:>4} | {sign_roi}{delta_roi:>5.1f}%")
        print(f"{'':22} |{'-'*68}")

    print()

if __name__ == "__main__":
    main()
