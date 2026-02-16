#!/usr/bin/env python3
"""
Análisis: Momentum + xG - Búsqueda de thresholds óptimos

Objetivo: Encontrar combinación de thresholds que maximice ROI
manteniendo muestra suficiente (>= 15 apuestas)
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("betfair_scraper/data")

def analyze_momentum_thresholds():
    """
    Prueba múltiples combinaciones de thresholds:
    - Momentum diff: [20%, 25%, 30%]
    - xG diff: [0.15, 0.2, 0.25, 0.3]
    """

    # Configuración de thresholds a probar
    mom_thresholds = [20, 25, 30]
    xg_thresholds = [0.15, 0.2, 0.25, 0.3]

    results = {
        "total_matches": 0,
        "with_data": 0,
        "combinations": {}
    }

    csv_files = list(DATA_DIR.glob("partido_*.csv"))

    # Recopilar TODOS los triggers posibles
    all_triggers = []

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

            home_won = gl_final > gv_final
            draw = gl_final == gv_final

            match_name = csv_file.stem.replace("partido_", "").replace("-apuestas", "")
            ft_score = f"{gl_final}-{gv_final}"

            # Buscar trigger en minutos 15-75
            for row in rows:
                try:
                    minuto = float(row.get("minuto", ""))
                except (ValueError, TypeError):
                    continue

                if not (15 <= minuto <= 75):
                    continue

                # Extraer momentum y xG
                try:
                    mom_l = float(row.get("momentum_local", ""))
                    mom_v = float(row.get("momentum_visitante", ""))
                    xg_l = float(row.get("xg_local", "") or 0)
                    xg_v = float(row.get("xg_visitante", "") or 0)
                    back_home = float(row.get("back_home", "") or 0)
                except (ValueError, TypeError):
                    continue

                if mom_l == 0 and mom_v == 0:
                    continue

                if xg_l == 0 and xg_v == 0:
                    continue

                results["with_data"] += 1

                mom_diff = mom_l - mom_v
                xg_diff = xg_l - xg_v

                # Calcular P/L para back home
                stake = 10
                if back_home > 0:
                    if home_won:
                        gross = (back_home - 1) * stake
                        pl = gross * 0.95
                    else:
                        pl = -stake
                else:
                    pl = 0
                    back_home = None

                # Guardar trigger
                all_triggers.append({
                    "match": match_name,
                    "minuto": int(minuto),
                    "mom_diff": mom_diff,
                    "xg_diff": xg_diff,
                    "back_home_odds": back_home,
                    "ft_score": ft_score,
                    "home_won": home_won,
                    "draw": draw,
                    "pl": pl
                })

                break  # Solo un trigger por partido

        except Exception as e:
            continue

    # Evaluar todas las combinaciones
    for mom_thresh in mom_thresholds:
        for xg_thresh in xg_thresholds:
            key = f"Mom>={mom_thresh}_xG>={xg_thresh}"

            # Filtrar triggers que cumplen esta combinación
            bets = [
                t for t in all_triggers
                if t["mom_diff"] >= mom_thresh and t["xg_diff"] >= xg_thresh
            ]

            if not bets:
                results["combinations"][key] = {
                    "mom_threshold": mom_thresh,
                    "xg_threshold": xg_thresh,
                    "total_bets": 0,
                    "home_wins": 0,
                    "draws": 0,
                    "win_rate": 0,
                    "total_pl": 0,
                    "roi": 0,
                    "avg_odds": 0
                }
                continue

            total = len(bets)
            home_wins = sum(1 for b in bets if b["home_won"])
            draws = sum(1 for b in bets if b["draw"])
            wr = (home_wins / total * 100) if total > 0 else 0

            total_pl = sum(b["pl"] for b in bets)
            total_stake = total * 10
            roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

            valid_odds = [b["back_home_odds"] for b in bets if b["back_home_odds"]]
            avg_odds = sum(valid_odds) / len(valid_odds) if valid_odds else 0

            results["combinations"][key] = {
                "mom_threshold": mom_thresh,
                "xg_threshold": xg_thresh,
                "total_bets": total,
                "home_wins": home_wins,
                "draws": draws,
                "win_rate": round(wr, 1),
                "total_pl": round(total_pl, 2),
                "roi": round(roi, 1),
                "avg_odds": round(avg_odds, 2),
                "bets": bets  # Guardar bets para análisis posterior
            }

    return results

def print_results(results):
    """Imprime resultados en formato tabla"""
    print("=" * 100)
    print("ANALISIS: MOMENTUM + xG - BUSQUEDA DE THRESHOLDS OPTIMOS")
    print("=" * 100)
    print(f"\nPartidos analizados: {results['total_matches']}")
    print(f"Partidos con datos momentum+xG: {results['with_data']}")

    print("\n" + "=" * 100)
    print("RESULTADOS POR COMBINACION DE THRESHOLDS")
    print("=" * 100)

    # Ordenar por ROI descendente
    sorted_combos = sorted(
        results["combinations"].items(),
        key=lambda x: (x[1]["total_bets"] >= 10, x[1]["roi"]),
        reverse=True
    )

    print(f"\n{'Combinacion':30} | {'Apuestas':9} | {'WR':6} | {'P/L':10} | {'ROI':7} | {'Odds':5} | {'Estado':20}")
    print("-" * 100)

    for key, data in sorted_combos:
        combo = f"Mom>={data['mom_threshold']} xG>={data['xg_threshold']}"
        apuestas = f"{data['total_bets']}"
        wr = f"{data['win_rate']:.1f}%"
        pl = f"{data['total_pl']:+.2f}€"
        roi = f"{data['roi']:+.1f}%"
        odds = f"{data['avg_odds']:.2f}"

        # Evaluación
        if data["total_bets"] < 10:
            status = "Muestra insuficiente"
        elif data["roi"] > 30:
            status = "EXCELENTE"
        elif data["roi"] > 15:
            status = "BUENA"
        elif data["roi"] > 5:
            status = "POSITIVA"
        elif data["roi"] > 0:
            status = "Marginal"
        else:
            status = "NEGATIVA"

        print(f"{combo:30} | {apuestas:9} | {wr:6} | {pl:10} | {roi:7} | {odds:5} | {status:20}")

    # Análisis de mejor candidato
    print("\n" + "=" * 100)
    print("ANALISIS DE MEJOR CANDIDATO")
    print("=" * 100)

    # Filtrar solo las que tienen >= 10 apuestas
    valid_combos = [(k, v) for k, v in results["combinations"].items() if v["total_bets"] >= 10]

    if valid_combos:
        best = max(valid_combos, key=lambda x: x[1]["roi"])
        best_key, best_data = best

        print(f"\nMejor combinacion con muestra >= 10:")
        print(f"  {best_key}")
        print(f"  Total apuestas: {best_data['total_bets']}")
        print(f"  Victoria local: {best_data['home_wins']} ({best_data['win_rate']:.1f}%)")
        print(f"  Empates: {best_data['draws']}")
        print(f"  Cuotas medias: {best_data['avg_odds']:.2f}")
        print(f"  P/L total: {best_data['total_pl']:+.2f} EUR")
        print(f"  ROI: {best_data['roi']:+.1f}%")

        # Top 5 mejores y peores apuestas
        bets_sorted = sorted(best_data["bets"], key=lambda x: x["pl"], reverse=True)

        print(f"\n  Top 5 mejores apuestas:")
        for i, bet in enumerate(bets_sorted[:5], 1):
            result = "WIN" if bet["home_won"] else "DRAW" if bet["draw"] else "LOSS"
            print(f"  {i}. {bet['match'][:35]:35} | Min {bet['minuto']:2} | "
                  f"Mom: {bet['mom_diff']:+5.1f} | xG: {bet['xg_diff']:+4.2f} | "
                  f"Odds: {bet['back_home_odds']:.2f} | FT: {bet['ft_score']:5} | "
                  f"P/L: {bet['pl']:+6.2f} | {result}")

        print(f"\n  Top 5 peores apuestas:")
        for i, bet in enumerate(bets_sorted[-5:], 1):
            result = "WIN" if bet["home_won"] else "DRAW" if bet["draw"] else "LOSS"
            print(f"  {i}. {bet['match'][:35]:35} | Min {bet['minuto']:2} | "
                  f"Mom: {bet['mom_diff']:+5.1f} | xG: {bet['xg_diff']:+4.2f} | "
                  f"Odds: {bet['back_home_odds']:.2f} | FT: {bet['ft_score']:5} | "
                  f"P/L: {bet['pl']:+6.2f} | {result}")

    else:
        print("\nNO hay combinaciones con muestra >= 10 apuestas.")
        print("La estrategia Momentum + xG no es viable con estos thresholds.")

    # Mejor combinación SIN restricción de muestra (para comparar)
    best_overall = max(results["combinations"].items(), key=lambda x: x[1]["roi"])
    if best_overall[1]["total_bets"] < 10:
        print(f"\n" + "=" * 100)
        print("MEJOR ROI (sin restriccion de muestra):")
        print("=" * 100)
        print(f"\n  {best_overall[0]}")
        print(f"  Total apuestas: {best_overall[1]['total_bets']}")
        print(f"  ROI: {best_overall[1]['roi']:+.1f}%")
        print(f"\n  -> ATENCION: Muestra demasiado pequeña, alto riesgo de sobreajuste")

if __name__ == "__main__":
    results = analyze_momentum_thresholds()
    print_results(results)

    # Guardar resultados
    output_file = "estrategias/momentum_thresholds_analysis.json"
    Path("estrategias").mkdir(exist_ok=True)

    # Preparar resultados para JSON (sin los bets detallados)
    results_for_json = {
        "total_matches": results["total_matches"],
        "with_data": results["with_data"],
        "combinations": {}
    }

    for key, data in results["combinations"].items():
        results_for_json["combinations"][key] = {
            k: v for k, v in data.items() if k != "bets"
        }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_for_json, f, indent=2, ensure_ascii=False)

    print(f"\nResultados guardados en: {output_file}")
