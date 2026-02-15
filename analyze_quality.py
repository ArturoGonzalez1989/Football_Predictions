#!/usr/bin/env python3
"""Analiza la calidad de las estadísticas capturadas en partidos finalizados."""

import csv
from pathlib import Path
import statistics

DATA_DIR = Path("betfair_scraper/data")

# Campos estadísticos importantes (excluir timestamp, minuto, estado)
STAT_FIELDS = [
    "goles_local", "goles_visitante",
    "posesion_local", "posesion_visitante",
    "tiros_local", "tiros_visitante",
    "tiros_puerta_local", "tiros_puerta_visitante",
    "corners_local", "corners_visitante",
    "tarjetas_amarillas_local", "tarjetas_amarillas_visitante",
    "xg_local", "xg_visitante"
    # Excluidos: ataques_peligrosos (nunca se capturan)
]

def calculate_quality(csv_path):
    """Calcula métricas de calidad para un partido."""
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return None

        total_captures = len(rows)

        # Calcular gaps (minutos sin capturar)
        minutos = []
        for row in rows:
            m = row.get("minuto", "").strip()
            if m.isdigit():
                minutos.append(int(m))

        gaps = 0
        if len(minutos) > 1:
            minutos_sorted = sorted(set(minutos))
            for i in range(len(minutos_sorted) - 1):
                gap = minutos_sorted[i+1] - minutos_sorted[i] - 1
                if gap > 0:
                    gaps += gap

        # Calcular % de campos estadísticos no-null
        non_null_counts = {field: 0 for field in STAT_FIELDS}

        for row in rows:
            for field in STAT_FIELDS:
                value = row.get(field, "").strip()
                if value and value != "" and value != "None" and value != "N/A":
                    non_null_counts[field] += 1

        # Calidad = promedio de % no-null de todos los campos
        coverage_percentages = []
        for field in STAT_FIELDS:
            coverage = (non_null_counts[field] / total_captures * 100) if total_captures > 0 else 0
            coverage_percentages.append(coverage)

        avg_coverage = statistics.mean(coverage_percentages) if coverage_percentages else 0

        return {
            "file": csv_path.name,
            "captures": total_captures,
            "gaps": gaps,
            "quality": round(avg_coverage, 1)
        }

    except Exception as e:
        print(f"Error analizando {csv_path.name}: {e}")
        return None


def main():
    print("=" * 80)
    print("ANÁLISIS DE CALIDAD DE PARTIDOS FINALIZADOS")
    print("=" * 80)

    # Analizar todos los CSVs
    results = []
    for csv_file in DATA_DIR.glob("partido_*.csv"):
        quality = calculate_quality(csv_file)
        if quality:
            results.append(quality)

    if not results:
        print("No se encontraron partidos para analizar.")
        return

    # Ordenar por calidad (peor a mejor)
    results.sort(key=lambda x: x["quality"])

    # Estadísticas generales
    avg_quality = statistics.mean([r["quality"] for r in results])
    avg_captures = statistics.mean([r["captures"] for r in results])
    avg_gaps = statistics.mean([r["gaps"] for r in results])

    print(f"\nRESUMEN GENERAL ({len(results)} partidos)")
    print(f"   Calidad promedio:  {avg_quality:.1f}%")
    print(f"   Capturas promedio: {avg_captures:.0f}")
    print(f"   Gaps promedio:     {avg_gaps:.1f}")

    # Top 20 peor calidad
    print(f"\nTOP 20 PEOR CALIDAD:")
    print(f"{'#':<4} {'Partido':<50} {'Capturas':<10} {'Gaps':<8} {'Calidad':<8}")
    print("-" * 80)
    for i, r in enumerate(results[:20], 1):
        partido_name = r["file"].replace("partido_", "").replace(".csv", "")[:48]
        print(f"{i:<4} {partido_name:<50} {r['captures']:<10} {r['gaps']:<8} {r['quality']:.1f}%")

    # Simular eliminación de partidos de baja calidad
    print(f"\nSIMULACION: Impacto de eliminar partidos de baja calidad")
    print("-" * 80)

    for threshold in [10, 20, 30, 40, 50]:
        low_quality = [r for r in results if r["quality"] < threshold]
        remaining = [r for r in results if r["quality"] >= threshold]

        if remaining:
            new_avg = statistics.mean([r["quality"] for r in remaining])
            improvement = new_avg - avg_quality
            print(f"Eliminar partidos con calidad < {threshold}%:")
            print(f"   - Partidos eliminados: {len(low_quality)}")
            print(f"   - Partidos restantes:  {len(remaining)}")
            print(f"   - Nueva calidad:       {new_avg:.1f}% (+{improvement:.1f}%)")
            print()


if __name__ == "__main__":
    main()
