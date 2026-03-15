"""
analyze_odds_sweet_spot.py — Análisis de rendimiento por tramo de cuotas

Objetivo: identificar si existe un floor global de odds por debajo del cual
el sistema pierde dinero sistemáticamente, independientemente de la estrategia.

Especialmente útil para estrategias con oddsMin=0 en config (sin filtro propio).
"""
import sys
import os
import json
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "betfair_scraper", "dashboard", "backend"))

from utils.csv_reader import analyze_cartera

CFG_PATH = os.path.join(ROOT, "betfair_scraper", "cartera_config.json")


def main():
    cfg = json.load(open(CFG_PATH, encoding="utf-8"))
    strategies = cfg.get("strategies", {})

    # Estrategias sin oddsMin propio (o con oddsMin=0)
    no_filter_strats = {
        k for k, v in strategies.items()
        if isinstance(v, dict) and v.get("enabled") and (v.get("oddsMin") or 0) == 0
    }
    has_filter_strats = {
        k for k, v in strategies.items()
        if isinstance(v, dict) and v.get("enabled") and (v.get("oddsMin") or 0) > 0
    }

    print(f"Estrategias sin oddsMin propio ({len(no_filter_strats)}): {sorted(no_filter_strats)}")
    print(f"Estrategias con oddsMin propio ({len(has_filter_strats)}): "
          f"{sorted(has_filter_strats)}")
    print()

    # Inyectar config temporalmente para que analyze_cartera() la use
    import utils.csv_reader as _cr
    _orig_cfg = getattr(_cr, "_cartera_config_override", None)
    # analyze_cartera() lee cartera_config.json internamente — usar tal cual
    print("Cargando analyze_cartera()...")
    result = analyze_cartera()
    bets = result.get("bets", [])
    print(f"Total bets BT: {len(bets)}")
    print()

    # ── Tramos de cuota ────────────────────────────────────────────────────────
    BRACKETS = [
        (0.0,  1.20, "<1.20"),
        (1.20, 1.30, "1.20–1.30"),
        (1.30, 1.40, "1.30–1.40"),
        (1.40, 1.50, "1.40–1.50"),
        (1.50, 1.60, "1.50–1.60"),
        (1.60, 1.80, "1.60–1.80"),
        (1.80, 2.00, "1.80–2.00"),
        (2.00, 2.50, "2.00–2.50"),
        (2.50, 3.50, "2.50–3.50"),
        (3.50, 6.00, "3.50–6.00"),
        (6.00, 999,  "6.00+"),
    ]

    def bracket(odds):
        for lo, hi, label in BRACKETS:
            if lo <= odds < hi:
                return label
        return "?"

    # ── Acumuladores ──────────────────────────────────────────────────────────
    # Global / solo-sin-filtro / por estrategia
    global_data   = defaultdict(lambda: {"n": 0, "wins": 0, "pl": 0.0})
    nofilter_data = defaultdict(lambda: {"n": 0, "wins": 0, "pl": 0.0})
    strat_odds    = defaultdict(lambda: defaultdict(lambda: {"n": 0, "wins": 0, "pl": 0.0}))

    for bet in bets:
        odds  = bet.get("odds") or bet.get("back_odds") or 0
        pl    = bet.get("pl") or 0
        strat = bet.get("strategy", "")
        win   = 1 if (pl or 0) > 0 else 0
        if not odds:
            continue
        b = bracket(odds)
        global_data[b]["n"]    += 1
        global_data[b]["wins"] += win
        global_data[b]["pl"]   += pl
        if strat in no_filter_strats:
            nofilter_data[b]["n"]    += 1
            nofilter_data[b]["wins"] += win
            nofilter_data[b]["pl"]   += pl
        strat_odds[strat][b]["n"]    += 1
        strat_odds[strat][b]["wins"] += win
        strat_odds[strat][b]["pl"]   += pl

    def print_table(title, data):
        print(f"\n{'─'*65}")
        print(f"  {title}")
        print(f"{'─'*65}")
        print(f"  {'Tramo':<14} {'N':>5} {'Wins':>5} {'WR%':>7} {'P/L':>8} {'ROI%':>7}")
        print(f"  {'─'*14} {'─'*5} {'─'*5} {'─'*7} {'─'*8} {'─'*7}")
        total_n = total_wins = 0
        total_pl = 0.0
        for lo, hi, label in BRACKETS:
            d = data.get(label)
            if not d or d["n"] == 0:
                continue
            n    = d["n"]
            wins = d["wins"]
            pl   = d["pl"]
            wr   = wins / n * 100
            roi  = pl / n * 100
            flag = " ⚠" if roi < -5 else (" ✓" if roi > 5 else "")
            print(f"  {label:<14} {n:>5} {wins:>5} {wr:>6.1f}% {pl:>8.2f} {roi:>6.1f}%{flag}")
            total_n    += n
            total_wins += wins
            total_pl   += pl
        if total_n:
            print(f"  {'─'*14} {'─'*5} {'─'*5} {'─'*7} {'─'*8} {'─'*7}")
            print(f"  {'TOTAL':<14} {total_n:>5} {total_wins:>5} "
                  f"{total_wins/total_n*100:>6.1f}% {total_pl:>8.2f} "
                  f"{total_pl/total_n*100:>6.1f}%")

    print_table("GLOBAL — todas las estrategias por tramo de cuota", global_data)
    print_table("SIN FILTRO PROPIO — solo estrategias con oddsMin=0", nofilter_data)

    # ── Por estrategia (solo las sin filtro) ─────────────────────────────────
    print(f"\n{'─'*65}")
    print("  POR ESTRATEGIA (sin oddsMin) — bets por debajo de 1.50")
    print(f"{'─'*65}")
    for strat in sorted(no_filter_strats):
        low_bets = []
        for lo, hi, label in BRACKETS:
            if hi <= 1.50:
                d = strat_odds[strat].get(label)
                if d and d["n"] > 0:
                    low_bets.append((label, d))
        if low_bets:
            print(f"\n  {strat}")
            for label, d in low_bets:
                n, wins, pl = d["n"], d["wins"], d["pl"]
                wr  = wins / n * 100
                roi = pl / n * 100
                print(f"    {label:<14} N={n:>3}  WR={wr:>5.1f}%  ROI={roi:>+6.1f}%")


if __name__ == "__main__":
    main()
