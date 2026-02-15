#!/usr/bin/env python3
"""
Análisis: Momentum del Scraper como predictor de victoria local

Hipótesis: Cuando el momentum favorece claramente al local (top 25%),
el equipo local tiene mayor probabilidad de ganar.

Estrategia potencial: Back Home cuando momentum_local >> momentum_visitante
"""

import csv
import json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("betfair_scraper/data")

def analyze_momentum_strategy():
    """
    Analiza la correlación entre momentum del scraper y resultado final.

    Versiones a probar:
    V1 (base): momentum_local - momentum_visitante >= 30% en algún minuto 15-75
    V2: V1 + posesión_local >= 50%
    V3: V1 + tiros_local - tiros_visitante >= 3
    V4: V1 + xG_local - xG_visitante >= 0.3
    """

    results = {
        "total_matches": 0,
        "with_momentum_data": 0,
        "momentum_triggers": {
            "v1": [],  # momentum diff >= 30%
            "v2": [],  # v1 + poss >= 50%
            "v3": [],  # v1 + tiros diff >= 3
            "v4": [],  # v1 + xG diff >= 0.3
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

            home_won = gl_final > gv_final
            draw = gl_final == gv_final
            away_won = gl_final < gv_final

            match_name = csv_file.stem.replace("partido_", "").replace("-apuestas", "")
            ft_score = f"{gl_final}-{gv_final}"

            # Buscar trigger de momentum en minutos 15-75
            trigger_found = False
            for row in rows:
                try:
                    minuto = float(row.get("minuto", ""))
                except (ValueError, TypeError):
                    continue

                if not (15 <= minuto <= 75):
                    continue

                # Extraer momentum
                try:
                    mom_l = float(row.get("momentum_local", ""))
                    mom_v = float(row.get("momentum_visitante", ""))
                except (ValueError, TypeError):
                    continue

                if mom_l == 0 and mom_v == 0:
                    continue

                results["with_momentum_data"] += 1

                # Calcular diferencia de momentum
                mom_diff = mom_l - mom_v

                # V1: momentum diff >= 30%
                if mom_diff >= 30 and not trigger_found:
                    trigger_found = True

                    # Extraer datos adicionales para filtros
                    try:
                        poss_l = float(row.get("posesion_local", "") or 0)
                        tiros_l = int(float(row.get("tiros_local", "") or 0))
                        tiros_v = int(float(row.get("tiros_visitante", "") or 0))
                        xg_l = float(row.get("xg_local", "") or 0)
                        xg_v = float(row.get("xg_visitante", "") or 0)
                        back_home = float(row.get("back_home", "") or 0)
                    except (ValueError, TypeError):
                        poss_l = 0
                        tiros_l = tiros_v = 0
                        xg_l = xg_v = 0
                        back_home = 0

                    tiros_diff = tiros_l - tiros_v
                    xg_diff = xg_l - xg_v

                    # Calcular P/L para back home (stake 10, comisión 5%)
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

                    bet_data = {
                        "match": match_name,
                        "minuto": int(minuto),
                        "mom_local": mom_l,
                        "mom_visit": mom_v,
                        "mom_diff": mom_diff,
                        "poss_local": poss_l,
                        "tiros_diff": tiros_diff,
                        "xg_diff": xg_diff,
                        "back_home_odds": back_home,
                        "ft_score": ft_score,
                        "home_won": home_won,
                        "draw": draw,
                        "pl": pl
                    }

                    # V1 (base)
                    results["momentum_triggers"]["v1"].append(bet_data)

                    # V2: + posesión local >= 50%
                    if poss_l >= 50:
                        results["momentum_triggers"]["v2"].append(bet_data.copy())

                    # V3: + diferencia tiros >= 3
                    if tiros_diff >= 3:
                        results["momentum_triggers"]["v3"].append(bet_data.copy())

                    # V4: + diferencia xG >= 0.3
                    if xg_diff >= 0.3:
                        results["momentum_triggers"]["v4"].append(bet_data.copy())

                    break  # Solo un trigger por partido

        except Exception as e:
            print(f"Error procesando {csv_file.name}: {e}")
            continue

    # Calcular métricas para cada versión
    for version, bets in results["momentum_triggers"].items():
        if not bets:
            results["analysis"][version] = {
                "total_bets": 0,
                "home_wins": 0,
                "draws": 0,
                "away_wins": 0,
                "win_rate": 0,
                "total_pl": 0,
                "roi": 0,
                "avg_odds": 0
            }
            continue

        total = len(bets)
        home_wins = sum(1 for b in bets if b["home_won"])
        draws = sum(1 for b in bets if b["draw"])
        away_wins = total - home_wins - draws
        wr = (home_wins / total * 100) if total > 0 else 0

        total_pl = sum(b["pl"] for b in bets)
        total_stake = total * 10
        roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

        valid_odds = [b["back_home_odds"] for b in bets if b["back_home_odds"]]
        avg_odds = sum(valid_odds) / len(valid_odds) if valid_odds else 0

        results["analysis"][version] = {
            "total_bets": total,
            "home_wins": home_wins,
            "draws": draws,
            "away_wins": away_wins,
            "win_rate": round(wr, 1),
            "total_pl": round(total_pl, 2),
            "roi": round(roi, 1),
            "avg_odds": round(avg_odds, 2)
        }

    return results

def print_results(results):
    """Imprime resultados formateados"""
    print("=" * 80)
    print("ANÁLISIS: MOMENTUM DEL SCRAPER")
    print("=" * 80)
    print(f"\nPartidos analizados: {results['total_matches']}")
    print(f"Partidos con datos de momentum: {results['with_momentum_data']}")

    print("\n" + "=" * 80)
    print("RESULTADOS POR VERSIÓN")
    print("=" * 80)

    versions = {
        "v1": "V1 (Base): Momentum diff >= 30%",
        "v2": "V2: V1 + Posesión local >= 50%",
        "v3": "V3: V1 + Diferencia tiros >= 3",
        "v4": "V4: V1 + Diferencia xG >= 0.3"
    }

    for ver_key, ver_name in versions.items():
        analysis = results["analysis"][ver_key]
        print(f"\n{ver_name}")
        print("-" * 80)
        print(f"  Total apuestas: {analysis['total_bets']}")
        print(f"  Victoria local: {analysis['home_wins']} ({analysis['win_rate']}%)")
        print(f"  Empate: {analysis['draws']}")
        print(f"  Victoria visitante: {analysis['away_wins']}")
        print(f"  Cuotas medias: {analysis['avg_odds']}")
        print(f"  P/L total: {analysis['total_pl']:+.2f} EUR")
        print(f"  ROI: {analysis['roi']:+.1f}%")

        # Evaluación
        if analysis["total_bets"] > 0:
            if analysis["roi"] > 20:
                status = "EXCELENTE"
            elif analysis["roi"] > 10:
                status = "BUENA"
            elif analysis["roi"] > 0:
                status = "POSITIVA (marginal)"
            else:
                status = "NEGATIVA"
            print(f"  -> {status}")

    # Mostrar mejores apuestas de la mejor versión
    best_version = max(results["analysis"].items(), key=lambda x: x[1]["roi"])
    if best_version[1]["total_bets"] > 0:
        print(f"\n{'=' * 80}")
        print(f"DETALLE MEJOR VERSIÓN: {versions[best_version[0]]}")
        print("=" * 80)

        bets = results["momentum_triggers"][best_version[0]]
        bets_sorted = sorted(bets, key=lambda x: x["pl"], reverse=True)

        print("\nTop 10 mejores apuestas:")
        for i, bet in enumerate(bets_sorted[:10], 1):
            result = "WIN" if bet["home_won"] else "LOSS"
            print(f"{i:2}. {bet['match'][:40]:40} | Min {bet['minuto']:2} | "
                  f"Momentum: {bet['mom_diff']:+.1f} | Odds: {bet['back_home_odds']:.2f} | "
                  f"FT: {bet['ft_score']:5} | P/L: {bet['pl']:+6.2f} | {result}")

        print("\nTop 10 peores apuestas:")
        for i, bet in enumerate(bets_sorted[-10:], 1):
            result = "WIN" if bet["home_won"] else "LOSS"
            print(f"{i:2}. {bet['match'][:40]:40} | Min {bet['minuto']:2} | "
                  f"Momentum: {bet['mom_diff']:+.1f} | Odds: {bet['back_home_odds']:.2f} | "
                  f"FT: {bet['ft_score']:5} | P/L: {bet['pl']:+6.2f} | {result}")

if __name__ == "__main__":
    results = analyze_momentum_strategy()
    print_results(results)

    # Guardar resultados
    output_file = "estrategias/momentum_analysis.json"
    Path("estrategias").mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResultados guardados en: {output_file}")
