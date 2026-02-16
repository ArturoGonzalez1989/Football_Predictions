#!/usr/bin/env python3
"""
Análisis: Goles Tardíos (75+)

Hipótesis: Cuando al minuto 75 hay exactamente 2 goles y un equipo domina,
es probable que haya más goles (Back Over 2.5).

Basado en patrón complementario identificado:
- 52.2% de partidos tienen gol después del min 75
- Con 2 goles al min 75: 71.4% tienen gol tardío
- Con posesión >55% al min 75: 68.8% tienen gol tardío
"""

import csv
import json
from pathlib import Path

DATA_DIR = Path("betfair_scraper/data")

def analyze_late_goals_strategy():
    """
    Analiza múltiples variaciones de goles tardíos según goles al min 75.

    Umbrales de goles:
    - 0 goles -> Back Over 0.5
    - 1 gol -> Back Over 1.5
    - 2 goles -> Back Over 2.5
    - 1-2 goles -> Back Over según corresponda

    Para cada umbral, versiones con filtros adicionales.
    """

    results = {
        "total_matches": 0,
        "triggers_by_goals": {
            "0_goals": [],  # Back Over 0.5
            "1_goal": [],   # Back Over 1.5
            "2_goals": [],  # Back Over 2.5
            "1_or_2_goals": []  # Back Over según goles
        },
        "analysis": {}
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

            total_goles_final = gl_final + gv_final
            match_name = csv_file.stem.replace("partido_", "").replace("-apuestas", "")
            ft_score = f"{gl_final}-{gv_final}"

            # Buscar snapshot al minuto 75+
            trigger_found = False
            for row in rows:
                try:
                    minuto = float(row.get("minuto", ""))
                except (ValueError, TypeError):
                    continue

                # Buscamos entre minuto 75 y 80 (ventana de trigger)
                if not (75 <= minuto <= 80):
                    continue

                # Goles al momento del trigger
                try:
                    gl_trigger = int(float(row.get("goles_local", "")))
                    gv_trigger = int(float(row.get("goles_visitante", "")))
                except (ValueError, TypeError):
                    continue

                total_goles_trigger = gl_trigger + gv_trigger

                # TRIGGER: Exactamente 2 goles al min 75
                if total_goles_trigger != 2 or trigger_found:
                    continue

                trigger_found = True
                results["matches_with_data_75"] += 1

                # Extraer datos adicionales
                try:
                    poss_l = float(row.get("posesion_local", "") or 0)
                    poss_v = float(row.get("posesion_visitante", "") or 0)
                    tiros_l = int(float(row.get("tiros_local", "") or 0))
                    tiros_v = int(float(row.get("tiros_visitante", "") or 0))
                    sot_l = int(float(row.get("tiros_puerta_local", "") or 0))
                    sot_v = int(float(row.get("tiros_puerta_visitante", "") or 0))
                    xg_l = float(row.get("xg_local", "") or 0)
                    xg_v = float(row.get("xg_visitante", "") or 0)
                    back_over25 = float(row.get("back_over25", "") or 0)
                except (ValueError, TypeError):
                    poss_l = poss_v = 0
                    tiros_l = tiros_v = 0
                    sot_l = sot_v = 0
                    xg_l = xg_v = 0
                    back_over25 = 0

                # Métricas
                poss_dominante = max(poss_l, poss_v)
                tiros_diff = abs(tiros_l - tiros_v)
                xg_total = xg_l + xg_v
                sot_total = sot_l + sot_v

                # Resultado: ¿Hubo Over 2.5? (al menos 3 goles)
                over25_won = total_goles_final >= 3

                # Calcular P/L (stake 10, comisión 5%)
                stake = 10
                if back_over25 > 0:
                    if over25_won:
                        gross = (back_over25 - 1) * stake
                        pl = gross * 0.95
                    else:
                        pl = -stake
                else:
                    pl = 0
                    back_over25 = None

                bet_data = {
                    "match": match_name,
                    "minuto_trigger": int(minuto),
                    "score_at_75": f"{gl_trigger}-{gv_trigger}",
                    "poss_dominante": poss_dominante,
                    "tiros_diff": tiros_diff,
                    "xg_total": xg_total,
                    "sot_total": sot_total,
                    "back_over25_odds": back_over25,
                    "ft_score": ft_score,
                    "over25_won": over25_won,
                    "pl": pl
                }

                # V1 (base): Solo el trigger de 2 goles al min 75
                results["late_goal_triggers"]["v1"].append(bet_data)

                # V2: + posesión dominante >= 55%
                if poss_dominante >= 55:
                    results["late_goal_triggers"]["v2"].append(bet_data.copy())

                # V3: + diferencia de tiros >= 3
                if tiros_diff >= 3:
                    results["late_goal_triggers"]["v3"].append(bet_data.copy())

                # V4: + xG total >= 2.0
                if xg_total >= 2.0:
                    results["late_goal_triggers"]["v4"].append(bet_data.copy())

                # V5: + tiros a puerta >= 6
                if sot_total >= 6:
                    results["late_goal_triggers"]["v5"].append(bet_data.copy())

                break  # Solo un trigger por partido

        except Exception as e:
            continue

    # Calcular métricas para cada versión
    for version, bets in results["late_goal_triggers"].items():
        if not bets:
            results["analysis"][version] = {
                "total_bets": 0,
                "over25_wins": 0,
                "win_rate": 0,
                "total_pl": 0,
                "roi": 0,
                "avg_odds": 0
            }
            continue

        total = len(bets)
        wins = sum(1 for b in bets if b["over25_won"])
        wr = (wins / total * 100) if total > 0 else 0

        total_pl = sum(b["pl"] for b in bets)
        total_stake = total * 10
        roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

        valid_odds = [b["back_over25_odds"] for b in bets if b["back_over25_odds"]]
        avg_odds = sum(valid_odds) / len(valid_odds) if valid_odds else 0

        results["analysis"][version] = {
            "total_bets": total,
            "over25_wins": wins,
            "win_rate": round(wr, 1),
            "total_pl": round(total_pl, 2),
            "roi": round(roi, 1),
            "avg_odds": round(avg_odds, 2)
        }

    return results

def print_results(results):
    """Imprime resultados formateados"""
    print("=" * 90)
    print("ANALISIS: GOLES TARDIOS (75+)")
    print("=" * 90)
    print(f"\nPartidos analizados: {results['total_matches']}")
    print(f"Partidos con 2 goles al min 75: {results['matches_with_data_75']}")

    print("\n" + "=" * 90)
    print("RESULTADOS POR VERSION")
    print("=" * 90)

    versions = {
        "v1": "V1 (Base): 2 goles al min 75, back Over 2.5",
        "v2": "V2: V1 + Posesion dominante >= 55%",
        "v3": "V3: V1 + Diferencia tiros >= 3",
        "v4": "V4: V1 + xG total >= 2.0",
        "v5": "V5: V1 + Tiros a puerta total >= 6"
    }

    for ver_key, ver_name in versions.items():
        analysis = results["analysis"][ver_key]
        print(f"\n{ver_name}")
        print("-" * 90)
        print(f"  Total apuestas: {analysis['total_bets']}")
        print(f"  Over 2.5 wins: {analysis['over25_wins']} ({analysis['win_rate']}%)")
        print(f"  Cuotas medias: {analysis['avg_odds']}")
        print(f"  P/L total: {analysis['total_pl']:+.2f} EUR")
        print(f"  ROI: {analysis['roi']:+.1f}%")

        # Evaluación
        if analysis["total_bets"] >= 15:
            if analysis["roi"] > 20:
                status = "EXCELENTE (muestra suficiente)"
            elif analysis["roi"] > 10:
                status = "BUENA (muestra suficiente)"
            elif analysis["roi"] > 0:
                status = "POSITIVA (muestra suficiente)"
            else:
                status = "NEGATIVA"
        elif analysis["total_bets"] >= 10:
            if analysis["roi"] > 20:
                status = "EXCELENTE (muestra aceptable)"
            elif analysis["roi"] > 10:
                status = "BUENA (muestra aceptable)"
            elif analysis["roi"] > 0:
                status = "POSITIVA (muestra aceptable)"
            else:
                status = "NEGATIVA"
        elif analysis["total_bets"] > 0:
            status = "Muestra insuficiente (<10)"
        else:
            status = "Sin datos"

        print(f"  -> {status}")

    # Detalle de mejor versión
    valid_versions = [(k, v) for k, v in results["analysis"].items() if v["total_bets"] >= 10]

    if valid_versions:
        best = max(valid_versions, key=lambda x: x[1]["roi"])
        best_key, best_data = best

        print(f"\n{'=' * 90}")
        print(f"DETALLE MEJOR VERSION: {versions[best_key]}")
        print("=" * 90)

        bets = results["late_goal_triggers"][best_key]
        bets_sorted = sorted(bets, key=lambda x: x["pl"], reverse=True)

        print(f"\nTop 10 mejores apuestas:")
        for i, bet in enumerate(bets_sorted[:10], 1):
            result = "WIN" if bet["over25_won"] else "LOSS"
            print(f"{i:2}. {bet['match'][:35]:35} | Min {bet['minuto_trigger']:2} | "
                  f"Score: {bet['score_at_75']:5} | Poss: {bet['poss_dominante']:4.1f}% | "
                  f"Odds: {bet['back_over25_odds']:.2f} | FT: {bet['ft_score']:5} | "
                  f"P/L: {bet['pl']:+6.2f} | {result}")

        print(f"\nTop 10 peores apuestas:")
        for i, bet in enumerate(bets_sorted[-10:], 1):
            result = "WIN" if bet["over25_won"] else "LOSS"
            print(f"{i:2}. {bet['match'][:35]:35} | Min {bet['minuto_trigger']:2} | "
                  f"Score: {bet['score_at_75']:5} | Poss: {bet['poss_dominante']:4.1f}% | "
                  f"Odds: {bet['back_over25_odds']:.2f} | FT: {bet['ft_score']:5} | "
                  f"P/L: {bet['pl']:+6.2f} | {result}")
    else:
        print(f"\n{'=' * 90}")
        print("NO hay versiones con muestra >= 10 apuestas")
        print("=" * 90)

if __name__ == "__main__":
    results = analyze_late_goals_strategy()
    print_results(results)

    # Guardar resultados
    output_file = "estrategias/late_goals_analysis.json"
    Path("estrategias").mkdir(exist_ok=True)

    # Preparar para JSON (sin bets detallados)
    results_for_json = {
        "total_matches": results["total_matches"],
        "matches_with_data_75": results["matches_with_data_75"],
        "analysis": results["analysis"]
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_for_json, f, indent=2, ensure_ascii=False)

    print(f"\nResultados guardados en: {output_file}")
