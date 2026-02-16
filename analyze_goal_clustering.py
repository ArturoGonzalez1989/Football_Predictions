#!/usr/bin/env python3
"""
Análisis: Clustering de Goles

Hipótesis: Después de un gol, apostar a Over (total_actual + 0.5)
porque hay 38.5% probabilidad de otro gol en los próximos 10 minutos.

Versiones:
V1 (base): Tras cualquier gol (min 15-80), back Over
V2: V1 + solo si tiros a puerta >= 3 en algún equipo
V3: V1 + solo si xG total >= 1.0
V4: V1 + solo si diferencia en marcador <= 1 gol (partido igualado)
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

def analyze_goal_clustering():
    """
    Analiza estrategia de apostar a Over inmediatamente después de un gol.
    """

    results = {
        "total_matches": 0,
        "total_goal_events": 0,
        "clustering_triggers": {
            "v1": [],  # base
            "v2": [],  # + SoT >= 3
            "v3": [],  # + xG >= 1.0
            "v4": [],  # + diff <= 1 (partido igualado)
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

            if len(rows) < 10:
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

            # Rastrear goles previos para detectar nuevos goles
            prev_total = 0

            for idx, row in enumerate(rows):
                try:
                    minuto = float(row.get("minuto", ""))
                except (ValueError, TypeError):
                    continue

                # Solo entre minuto 15 y 80 (ventana de apuesta)
                if not (15 <= minuto <= 80):
                    prev_total = 0  # Reset
                    continue

                # Goles actuales
                try:
                    gl = int(float(row.get("goles_local", "")))
                    gv = int(float(row.get("goles_visitante", "")))
                except (ValueError, TypeError):
                    continue

                total_now = gl + gv

                # ¿Hubo un gol nuevo?
                if total_now > prev_total and prev_total > 0:
                    # TRIGGER: acaba de haber un gol
                    results["total_goal_events"] += 1

                    # Extraer datos
                    try:
                        sot_l = int(float(row.get("tiros_puerta_local", "") or 0))
                        sot_v = int(float(row.get("tiros_puerta_visitante", "") or 0))
                        xg_l = float(row.get("xg_local", "") or 0)
                        xg_v = float(row.get("xg_visitante", "") or 0)
                    except (ValueError, TypeError):
                        sot_l = sot_v = 0
                        xg_l = xg_v = 0

                    sot_max = max(sot_l, sot_v)
                    xg_total = xg_l + xg_v
                    score_diff = abs(gl - gv)

                    # Obtener cuotas Over correspondientes
                    over_field = get_over_field(total_now)
                    if not over_field:
                        prev_total = total_now
                        continue

                    try:
                        over_odds = float(row.get(over_field, "") or 0)
                    except (ValueError, TypeError):
                        over_odds = 0

                    # Target: al menos 1 gol más
                    target = total_now + 1
                    over_won = total_final >= target

                    # Tiempo hasta siguiente gol
                    time_to_next_goal = None
                    for future_idx in range(idx + 1, len(rows)):
                        future_row = rows[future_idx]
                        try:
                            future_min = float(future_row.get("minuto", ""))
                            future_gl = int(float(future_row.get("goles_local", "")))
                            future_gv = int(float(future_row.get("goles_visitante", "")))
                            future_total = future_gl + future_gv
                        except (ValueError, TypeError):
                            continue

                        if future_total > total_now:
                            time_to_next_goal = future_min - minuto
                            break

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
                        "score": f"{gl}-{gv}",
                        "sot_max": sot_max,
                        "xg_total": xg_total,
                        "score_diff": score_diff,
                        "time_to_next": time_to_next_goal,
                        "odds": over_odds,
                        "ft": ft_score,
                        "won": over_won,
                        "pl": pl
                    }

                    # V1 (base)
                    results["clustering_triggers"]["v1"].append(bet_data)

                    # V2: + SoT >= 3
                    if sot_max >= 3:
                        results["clustering_triggers"]["v2"].append(bet_data.copy())

                    # V3: + xG >= 1.0
                    if xg_total >= 1.0:
                        results["clustering_triggers"]["v3"].append(bet_data.copy())

                    # V4: + partido igualado (diff <= 1)
                    if score_diff <= 1:
                        results["clustering_triggers"]["v4"].append(bet_data.copy())

                prev_total = total_now

        except Exception as e:
            continue

    # Calcular métricas
    for version, bets in results["clustering_triggers"].items():
        if not bets:
            results["analysis"][version] = {
                "total": 0,
                "wins": 0,
                "wr": 0,
                "pl": 0,
                "roi": 0,
                "avg_odds": 0,
                "avg_time_to_next": 0
            }
            continue

        total = len(bets)
        wins = sum(1 for b in bets if b["won"])
        wr = (wins / total * 100) if total > 0 else 0
        total_pl = sum(b["pl"] for b in bets)
        roi = (total_pl / (total * 10) * 100) if total > 0 else 0
        valid_odds = [b["odds"] for b in bets if b["odds"]]
        avg_odds = sum(valid_odds) / len(valid_odds) if valid_odds else 0

        # Tiempo promedio hasta siguiente gol
        valid_times = [b["time_to_next"] for b in bets if b["time_to_next"] is not None]
        avg_time = sum(valid_times) / len(valid_times) if valid_times else 0

        results["analysis"][version] = {
            "total": total,
            "wins": wins,
            "wr": round(wr, 1),
            "pl": round(total_pl, 2),
            "roi": round(roi, 1),
            "avg_odds": round(avg_odds, 2),
            "avg_time_to_next": round(avg_time, 1)
        }

    return results

def print_results(results):
    """Imprime resultados"""
    print("=" * 90)
    print("ANALISIS: CLUSTERING DE GOLES")
    print("=" * 90)
    print(f"\nPartidos analizados: {results['total_matches']}")
    print(f"Eventos de gol detectados (triggers): {results['total_goal_events']}")

    print("\n" + "=" * 90)
    print("RESULTADOS POR VERSION")
    print("=" * 90)

    versions = {
        "v1": "V1 (Base): Tras cualquier gol (min 15-80)",
        "v2": "V2: V1 + SoT max >= 3",
        "v3": "V3: V1 + xG total >= 1.0",
        "v4": "V4: V1 + Diff marcador <= 1"
    }

    for ver_key, ver_name in versions.items():
        data = results["analysis"][ver_key]

        print(f"\n{ver_name}")
        print("-" * 90)
        print(f"  Apuestas: {data['total']:3} | Wins: {data['wins']:3} ({data['wr']:5.1f}%) | "
              f"Odds: {data['avg_odds']:4.2f} | P/L: {data['pl']:+8.2f} | ROI: {data['roi']:+6.1f}%")
        if data['total'] > 0:
            print(f"  Tiempo promedio hasta siguiente gol: {data['avg_time_to_next']:.1f} min")

        # Status
        if data['total'] >= 20:
            if data['roi'] > 15:
                status = "EXCELENTE (muestra robusta)"
            elif data['roi'] > 5:
                status = "BUENA (muestra robusta)"
            elif data['roi'] > 0:
                status = "POSITIVA (muestra robusta)"
            else:
                status = "NEGATIVA"
            print(f"  -> {status}")
        elif data['total'] >= 10:
            if data['roi'] > 15:
                status = "Prometedor (validar mas)"
            elif data['roi'] > 0:
                status = "Positivo (muestra justa)"
            else:
                status = "Negativa"
            print(f"  -> {status}")
        elif data['total'] > 0:
            print(f"  -> Muestra insuficiente (<10)")

    # Mejor versión
    valid = [(k, v) for k, v in results["analysis"].items() if v["total"] >= 10]
    if valid:
        best = max(valid, key=lambda x: x[1]["roi"])
        best_key, best_data = best

        print(f"\n{'=' * 90}")
        print(f"MEJOR VERSION: {versions[best_key]}")
        print("=" * 90)
        print(f"  Total: {best_data['total']}")
        print(f"  WR: {best_data['wr']:.1f}%")
        print(f"  P/L: {best_data['pl']:+.2f} EUR")
        print(f"  ROI: {best_data['roi']:+.1f}%")

        # Top 5
        bets_sorted = sorted(results["clustering_triggers"][best_key], key=lambda x: x["pl"], reverse=True)
        print(f"\n  Top 5 mejores:")
        for i, bet in enumerate(bets_sorted[:5], 1):
            result = "WIN" if bet["won"] else "LOSS"
            odds_str = f"{bet['odds']:.2f}" if bet['odds'] else "N/A"
            next_str = f"{bet['time_to_next']:.0f}m" if bet['time_to_next'] else "None"
            print(f"  {i}. {bet['match'][:25]:25} | Min {bet['min']:2} | Score: {bet['score']:5} | "
                  f"Next: {next_str:5} | Odds: {odds_str:5} | P/L: {bet['pl']:+6.2f} | {result}")
    else:
        print(f"\n{'=' * 90}")
        print("NO hay versiones con muestra >= 10")
        print("=" * 90)

if __name__ == "__main__":
    results = analyze_goal_clustering()
    print_results(results)

    # Guardar
    output_file = "estrategias/goal_clustering_analysis.json"
    Path("estrategias").mkdir(exist_ok=True)

    results_json = {
        "total_matches": results["total_matches"],
        "total_goal_events": results["total_goal_events"],
        "analysis": results["analysis"]
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)

    print(f"\nResultados guardados en: {output_file}")
