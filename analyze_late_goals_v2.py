#!/usr/bin/env python3
"""
Análisis: Goles Tardíos (75+) - Versión 2 con múltiples umbrales

Prueba diferentes condiciones de goles al minuto 75:
- 0 goles -> Back Over 0.5
- 1 gol -> Back Over 1.5
- 2 goles -> Back Over 2.5
- 1-2 goles -> Back Over (dinámico)
"""

import csv
import json
from pathlib import Path

DATA_DIR = Path("betfair_scraper/data")

def get_over_field(total_goals):
    """Mapea total de goles a campo de cuotas Over"""
    mapping = {
        0: "back_over05",
        1: "back_over15",
        2: "back_over25",
        3: "back_over35",
        4: "back_over45"
    }
    return mapping.get(total_goals, None)

def analyze_late_goals_v2():
    """Analiza goles tardíos con diferentes umbrales de goles al min 75"""

    scenarios = {
        "0_goles": {"min_goals": 0, "max_goals": 0, "label": "0 goles -> Over 0.5"},
        "1_gol": {"min_goals": 1, "max_goals": 1, "label": "1 gol -> Over 1.5"},
        "2_goles": {"min_goals": 2, "max_goals": 2, "label": "2 goles -> Over 2.5"},
        "1_2_goles": {"min_goals": 1, "max_goals": 2, "label": "1-2 goles -> Over dinámico"}
    }

    results = {
        "total_matches": 0,
        "scenarios": {}
    }

    # Inicializar resultados por escenario
    for key, data in scenarios.items():
        results["scenarios"][key] = {
            "label": data["label"],
            "base": [],  # Sin filtros
            "poss55": [],  # + posesión >= 55%
            "tiros3": [],  # + diff tiros >= 3
            "sot6": []  # + SoT total >= 6
        }

    csv_files = list(DATA_DIR.glob("partido_*.csv"))

    for csv_file in csv_files:
        results["total_matches"] += 1

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            if len(rows) < 5:
                continue

            # Resultado final
            last_row = rows[-1]
            try:
                gl_final = int(float(last_row.get("goles_local", "")))
                gv_final = int(float(last_row.get("goles_visitante", "")))
            except (ValueError, TypeError):
                continue

            total_final = gl_final + gv_final
            match_name = csv_file.stem.replace("partido_", "").replace("-apuestas", "")
            ft_score = f"{gl_final}-{gv_final}"

            # Buscar snapshot al minuto 75-80
            for row in rows:
                try:
                    minuto = float(row.get("minuto", ""))
                except (ValueError, TypeError):
                    continue

                if not (75 <= minuto <= 80):
                    continue

                # Goles al momento
                try:
                    gl = int(float(row.get("goles_local", "")))
                    gv = int(float(row.get("goles_visitante", "")))
                except (ValueError, TypeError):
                    continue

                total_at_75 = gl + gv

                # Datos adicionales
                try:
                    poss_l = float(row.get("posesion_local", "") or 0)
                    poss_v = float(row.get("posesion_visitante", "") or 0)
                    tiros_l = int(float(row.get("tiros_local", "") or 0))
                    tiros_v = int(float(row.get("tiros_visitante", "") or 0))
                    sot_l = int(float(row.get("tiros_puerta_local", "") or 0))
                    sot_v = int(float(row.get("tiros_puerta_visitante", "") or 0))
                except (ValueError, TypeError):
                    poss_l = poss_v = 0
                    tiros_l = tiros_v = 0
                    sot_l = sot_v = 0

                poss_max = max(poss_l, poss_v)
                tiros_diff = abs(tiros_l - tiros_v)
                sot_total = sot_l + sot_v

                # Obtener cuotas Over correspondientes
                over_field = get_over_field(total_at_75)
                if not over_field:
                    break

                try:
                    over_odds = float(row.get(over_field, "") or 0)
                except (ValueError, TypeError):
                    over_odds = 0

                # Target: Over (total_at_75 + 0.5)
                target = total_at_75 + 1
                over_won = total_final >= target

                # Calcular P/L
                stake = 10
                if over_odds > 0:
                    if over_won:
                        gross = (over_odds - 1) * stake
                        pl = gross * 0.95
                    else:
                        pl = -stake
                else:
                    pl = 0
                    over_odds = None

                bet_data = {
                    "match": match_name,
                    "min": int(minuto),
                    "score_75": f"{gl}-{gv}",
                    "target": target,
                    "ft_score": ft_score,
                    "poss_max": poss_max,
                    "tiros_diff": tiros_diff,
                    "sot_total": sot_total,
                    "odds": over_odds,
                    "won": over_won,
                    "pl": pl
                }

                # Asignar a escenarios según total_at_75
                for scenario_key, scenario_data in scenarios.items():
                    if scenario_data["min_goals"] <= total_at_75 <= scenario_data["max_goals"]:
                        # Base (sin filtros)
                        results["scenarios"][scenario_key]["base"].append(bet_data.copy())

                        # Filtros
                        if poss_max >= 55:
                            results["scenarios"][scenario_key]["poss55"].append(bet_data.copy())
                        if tiros_diff >= 3:
                            results["scenarios"][scenario_key]["tiros3"].append(bet_data.copy())
                        if sot_total >= 6:
                            results["scenarios"][scenario_key]["sot6"].append(bet_data.copy())

                break  # Solo un trigger por partido

        except Exception as e:
            continue

    # Calcular métricas
    for scenario_key in results["scenarios"]:
        for version_key in ["base", "poss55", "tiros3", "sot6"]:
            bets = results["scenarios"][scenario_key][version_key]

            if not bets:
                results["scenarios"][scenario_key][version_key] = {
                    "total": 0,
                    "wins": 0,
                    "wr": 0,
                    "pl": 0,
                    "roi": 0,
                    "avg_odds": 0,
                    "bets": []
                }
                continue

            total = len(bets)
            wins = sum(1 for b in bets if b["won"])
            wr = (wins / total * 100) if total > 0 else 0
            total_pl = sum(b["pl"] for b in bets)
            roi = (total_pl / (total * 10) * 100) if total > 0 else 0
            valid_odds = [b["odds"] for b in bets if b["odds"]]
            avg_odds = sum(valid_odds) / len(valid_odds) if valid_odds else 0

            results["scenarios"][scenario_key][version_key] = {
                "total": total,
                "wins": wins,
                "wr": round(wr, 1),
                "pl": round(total_pl, 2),
                "roi": round(roi, 1),
                "avg_odds": round(avg_odds, 2),
                "bets": bets
            }

    return results

def print_results(results):
    """Imprime resultados"""
    print("=" * 100)
    print("ANALISIS: GOLES TARDIOS V2 (MULTIPLES UMBRALES)")
    print("=" * 100)
    print(f"\nPartidos analizados: {results['total_matches']}")

    versions_labels = {
        "base": "Base (sin filtros)",
        "poss55": "+ Posesion >= 55%",
        "tiros3": "+ Diff Tiros >= 3",
        "sot6": "+ SoT Total >= 6"
    }

    for scenario_key, scenario_data in results["scenarios"].items():
        label = scenario_data["label"]

        print(f"\n{'=' * 100}")
        print(f"ESCENARIO: {label}")
        print("=" * 100)

        for ver_key, ver_label in versions_labels.items():
            data = scenario_data[ver_key]

            print(f"\n{ver_label}")
            print("-" * 100)
            print(f"  Apuestas: {data['total']:3} | Wins: {data['wins']:3} ({data['wr']:5.1f}%) | "
                  f"Odds: {data['avg_odds']:4.2f} | P/L: {data['pl']:+8.2f} | ROI: {data['roi']:+6.1f}%")

            # Status
            if data['total'] >= 15:
                if data['roi'] > 15:
                    status = "EXCELENTE (muestra suficiente)"
                elif data['roi'] > 5:
                    status = "BUENA (muestra suficiente)"
                elif data['roi'] > 0:
                    status = "POSITIVA (muestra suficiente)"
                else:
                    status = "NEGATIVA"
                print(f"  -> {status}")
            elif data['total'] >= 10:
                if data['roi'] > 15:
                    status = "Prometedor (validar con mas datos)"
                elif data['roi'] > 0:
                    status = "Positivo (muestra justa)"
                else:
                    status = "Negativa"
                print(f"  -> {status}")
            elif data['total'] > 0:
                print(f"  -> Muestra insuficiente (<10)")

    # Mejor versión global
    print(f"\n{'=' * 100}")
    print("MEJOR VERSION GLOBAL")
    print("=" * 100)

    all_versions = []
    for sc_key, sc_data in results["scenarios"].items():
        for ver_key in ["base", "poss55", "tiros3", "sot6"]:
            data = sc_data[ver_key]
            if data["total"] >= 10:
                all_versions.append({
                    "scenario": sc_data["label"],
                    "version": versions_labels[ver_key],
                    "data": data,
                    "sc_key": sc_key,
                    "ver_key": ver_key
                })

    if all_versions:
        best = max(all_versions, key=lambda x: x["data"]["roi"])
        print(f"\n{best['scenario']} - {best['version']}")
        print(f"  Apuestas: {best['data']['total']}")
        print(f"  Win Rate: {best['data']['wr']:.1f}%")
        print(f"  P/L: {best['data']['pl']:+.2f} EUR")
        print(f"  ROI: {best['data']['roi']:+.1f}%")

        # Top 5 mejores
        bets_sorted = sorted(best['data']['bets'], key=lambda x: x['pl'], reverse=True)
        print(f"\n  Top 5 mejores:")
        for i, bet in enumerate(bets_sorted[:5], 1):
            result = "WIN" if bet["won"] else "LOSS"
            odds_str = f"{bet['odds']:.2f}" if bet['odds'] else "N/A"
            print(f"  {i}. {bet['match'][:30]:30} | {bet['score_75']:5} -> {bet['ft_score']:5} | "
                  f"Odds: {odds_str:5} | P/L: {bet['pl']:+6.2f} | {result}")
    else:
        print("\nNO hay versiones con muestra >= 10 apuestas")

if __name__ == "__main__":
    results = analyze_late_goals_v2()
    print_results(results)

    # Guardar
    output_file = "estrategias/late_goals_v2_analysis.json"
    Path("estrategias").mkdir(exist_ok=True)

    # Preparar JSON (sin bets)
    results_json = {
        "total_matches": results["total_matches"],
        "scenarios": {}
    }
    for sc_key, sc_data in results["scenarios"].items():
        results_json["scenarios"][sc_key] = {
            "label": sc_data["label"],
            "base": {k: v for k, v in sc_data["base"].items() if k != "bets"},
            "poss55": {k: v for k, v in sc_data["poss55"].items() if k != "bets"},
            "tiros3": {k: v for k, v in sc_data["tiros3"].items() if k != "bets"},
            "sot6": {k: v for k, v in sc_data["sot6"].items() if k != "bets"}
        }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)

    print(f"\nResultados guardados en: {output_file}")
