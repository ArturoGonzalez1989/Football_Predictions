#!/usr/bin/env python3
"""
Test script to analyze why Momentum x xG shows 0 bets.
Checks partido CSV files for potential triggers.
"""

import csv
from pathlib import Path

DATA_DIR = Path("betfair_scraper/data")

def to_float(val):
    """Convert string to float, return None if invalid."""
    if not val or not str(val).strip():
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def analyze_match_for_momentum_xg(csv_path):
    """Analyze a single match CSV for Momentum x xG triggers.
    Returns:
        None - match not valid/finished
        "finished" - match finished but no triggers
        "trigger" - match finished with triggers
    """
    # Read CSV rows
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        return None

    if len(rows) < 20:
        return None

    # Check if match finished
    last_row = rows[-1]
    last_min = to_float(last_row.get("minuto", ""))
    gl_final = to_float(last_row.get("goles_local", ""))
    gv_final = to_float(last_row.get("goles_visitante", ""))

    if gl_final is None or gv_final is None:
        return None

    if last_min is None or last_min < 85:
        return None

    ft_score = f"{int(gl_final)}-{int(gv_final)}"

    # V1 config
    config = {
        "sot_min": 1,
        "sot_ratio_min": 1.1,
        "xg_underperf_min": 0.15,
        "min_minute": 10,
        "max_minute": 80,
        "min_odds": 1.4,
        "max_odds": 6.0,
    }

    triggers_found = []
    for i, row in enumerate(rows):
        estado = row.get("estado_partido", "").strip()
        if estado != "en_juego":
            continue

        minuto = to_float(row.get("minuto", ""))
        if minuto is None or minuto < config["min_minute"] or minuto > config["max_minute"]:
            continue

        # Get stats
        gl = to_float(row.get("goles_local", ""))
        gv = to_float(row.get("goles_visitante", ""))
        xg_local = to_float(row.get("xg_local", ""))
        xg_visitante = to_float(row.get("xg_visitante", ""))
        sot_local = to_float(row.get("tiros_puerta_local", ""))
        sot_visitante = to_float(row.get("tiros_puerta_visitante", ""))
        back_home = to_float(row.get("back_home", ""))
        back_away = to_float(row.get("back_away", ""))

        if None in [gl, gv, xg_local, xg_visitante, sot_local, sot_visitante, back_home, back_away]:
            continue

        # Calculate xG underperformance
        xg_underperf_local = xg_local - gl
        xg_underperf_visitante = xg_visitante - gv

        # Check home team
        if sot_visitante > 0:
            sot_ratio_local = sot_local / sot_visitante
        else:
            sot_ratio_local = sot_local * 2 if sot_local >= config["sot_min"] else 0

        if (sot_local >= config["sot_min"] and
            sot_ratio_local >= config["sot_ratio_min"] and
            xg_underperf_local > config["xg_underperf_min"] and
            config["min_odds"] <= back_home <= config["max_odds"]):

            triggers_found.append({
                "minute": int(minuto),
                "team": "HOME",
                "score": f"{int(gl)}-{int(gv)}",
                "sot_ratio": round(sot_ratio_local, 2),
                "xg_underperf": round(xg_underperf_local, 2),
                "odds": round(back_home, 2),
                "row_num": i + 2
            })

        # Check away team
        if sot_local > 0:
            sot_ratio_visitante = sot_visitante / sot_local
        else:
            sot_ratio_visitante = sot_visitante * 2 if sot_visitante >= config["sot_min"] else 0

        if (sot_visitante >= config["sot_min"] and
            sot_ratio_visitante >= config["sot_ratio_min"] and
            xg_underperf_visitante > config["xg_underperf_min"] and
            config["min_odds"] <= back_away <= config["max_odds"]):

            triggers_found.append({
                "minute": int(minuto),
                "team": "AWAY",
                "score": f"{int(gl)}-{int(gv)}",
                "sot_ratio": round(sot_ratio_visitante, 2),
                "xg_underperf": round(xg_underperf_visitante, 2),
                "odds": round(back_away, 2),
                "row_num": i + 2
            })

    if triggers_found:
        print(f"\n{csv_path.name}")
        print(f"  [TRIGGER] Match: {ft_score} | Triggers: {len(triggers_found)}")
        for t in triggers_found:
            print(f"    Min {t['minute']:2d} | {t['team']:4s} | {t['score']} | SoT ratio: {t['sot_ratio']:.2f} | xG underperf: {t['xg_underperf']:.2f} | Odds: {t['odds']:.2f}")
        return "trigger"
    else:
        return "finished"


# Main analysis
if __name__ == "__main__":
    print("="*80)
    print("MOMENTUM x xG DIAGNOSTIC TOOL")
    print("="*80)

    csv_files = list(DATA_DIR.glob("partido_*.csv"))
    print(f"\nFound {len(csv_files)} partido CSV files in {DATA_DIR}")

    if not csv_files:
        print("[X] No partido CSV files found!")
        exit(1)

    # Analyze ALL matches
    print(f"\nAnalyzing ALL {len(csv_files)} matches...")

    matches_with_triggers = 0
    finished_matches = 0
    for csv_path in csv_files:
        result = analyze_match_for_momentum_xg(csv_path)
        if result == "finished":
            finished_matches += 1
        elif result == "trigger":
            matches_with_triggers += 1
            finished_matches += 1

    print(f"\n{'='*80}")
    print(f"SUMMARY:")
    print(f"  Total CSVs analyzed: {len(csv_files)}")
    print(f"  Finished matches: {finished_matches}")
    print(f"  Matches with triggers: {matches_with_triggers}")
    print(f"{'='*80}")
