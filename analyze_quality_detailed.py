#!/usr/bin/env python3
"""Análisis detallado de calidad para identificar oportunidades de mejora."""

import csv
from pathlib import Path
import statistics

DATA_DIR = Path("betfair_scraper/data")

STAT_FIELDS = [
    "goles_local", "goles_visitante",
    "posesion_local", "posesion_visitante",
    "tiros_local", "tiros_visitante",
    "tiros_puerta_local", "tiros_puerta_visitante",
    "corners_local", "corners_visitante",
    "tarjetas_amarillas_local", "tarjetas_amarillas_visitante",
    "xg_local", "xg_visitante",
    "ataques_peligrosos_local", "ataques_peligrosos_visitante"
]

def analyze_match(csv_path):
    """Análisis detallado de un partido."""
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return None

        total_captures = len(rows)

        # Calcular gaps
        minutos = []
        for row in rows:
            m = row.get("minuto", "").strip()
            if m.isdigit():
                minutos.append(int(m))

        gaps = 0
        max_gap = 0
        if len(minutos) > 1:
            minutos_sorted = sorted(set(minutos))
            for i in range(len(minutos_sorted) - 1):
                gap = minutos_sorted[i+1] - minutos_sorted[i] - 1
                if gap > 0:
                    gaps += gap
                    max_gap = max(max_gap, gap)

        # Calcular cobertura por campo
        field_coverage = {}
        for field in STAT_FIELDS:
            non_null = 0
            for row in rows:
                value = row.get(field, "").strip()
                if value and value != "" and value != "None" and value != "N/A":
                    non_null += 1
            field_coverage[field] = (non_null / total_captures * 100) if total_captures > 0 else 0

        avg_quality = statistics.mean(field_coverage.values())

        return {
            "file": csv_path.name,
            "captures": total_captures,
            "gaps": gaps,
            "max_gap": max_gap,
            "quality": round(avg_quality, 1),
            "field_coverage": field_coverage
        }

    except Exception:
        return None


def main():
    print("=" * 80)
    print("ANALISIS DETALLADO DE CALIDAD")
    print("=" * 80)

    results = []
    for csv_file in DATA_DIR.glob("partido_*.csv"):
        analysis = analyze_match(csv_file)
        if analysis:
            results.append(analysis)

    if not results:
        print("No se encontraron partidos.")
        return

    # Estadísticas generales
    avg_quality = statistics.mean([r["quality"] for r in results])
    avg_captures = statistics.mean([r["captures"] for r in results])
    avg_gaps = statistics.mean([r["gaps"] for r in results])

    print(f"\nRESUMEN ACTUAL ({len(results)} partidos)")
    print(f"   Calidad promedio:  {avg_quality:.1f}%")
    print(f"   Capturas promedio: {avg_captures:.0f}")
    print(f"   Gaps promedio:     {avg_gaps:.1f}")

    # Análisis de cobertura por campo (promedio entre todos los partidos)
    print(f"\nCOBERTURA POR CAMPO ESTADISTICO:")
    print(f"{'Campo':<30} {'Cobertura Promedio':<20}")
    print("-" * 50)

    field_avg_coverage = {}
    for field in STAT_FIELDS:
        coverages = [r["field_coverage"][field] for r in results]
        avg_cov = statistics.mean(coverages)
        field_avg_coverage[field] = avg_cov

    # Ordenar por cobertura (de peor a mejor)
    sorted_fields = sorted(field_avg_coverage.items(), key=lambda x: x[1])
    for field, cov in sorted_fields:
        print(f"{field:<30} {cov:>6.1f}%")

    # Identificar partidos problemáticos por diferentes criterios
    print(f"\nPARTIDOS PROBLEMATICOS:")

    low_captures = [r for r in results if r["captures"] < 50]
    high_gaps = [r for r in results if r["gaps"] > 30]
    very_high_gaps = [r for r in results if r["max_gap"] > 20]

    print(f"\n1. Partidos con <50 capturas: {len(low_captures)}")
    for r in sorted(low_captures, key=lambda x: x["captures"])[:5]:
        name = r["file"].replace("partido_", "").replace(".csv", "")[:50]
        print(f"   - {name:<50} ({r['captures']} capturas)")

    print(f"\n2. Partidos con >30 gaps totales: {len(high_gaps)}")
    for r in sorted(high_gaps, key=lambda x: x["gaps"], reverse=True)[:5]:
        name = r["file"].replace("partido_", "").replace(".csv", "")[:50]
        print(f"   - {name:<50} ({r['gaps']} gaps)")

    print(f"\n3. Partidos con gap maximo >20 min: {len(very_high_gaps)}")
    for r in sorted(very_high_gaps, key=lambda x: x["max_gap"], reverse=True)[:5]:
        name = r["file"].replace("partido_", "").replace(".csv", "")[:50]
        print(f"   - {name:<50} (gap max: {r['max_gap']} min)")

    # Simulación: combinar múltiples criterios
    print(f"\nSIMULACION: Eliminacion con criterios combinados")
    print("-" * 80)

    # Criterio 1: Calidad < 60%
    remaining_1 = [r for r in results if r["quality"] >= 60]
    if remaining_1:
        new_avg_1 = statistics.mean([r["quality"] for r in remaining_1])
        print(f"Eliminar partidos con calidad < 60%:")
        print(f"   - Eliminados: {len(results) - len(remaining_1)}")
        print(f"   - Restantes:  {len(remaining_1)}")
        print(f"   - Nueva calidad: {new_avg_1:.1f}% (+{new_avg_1 - avg_quality:.1f}%)")
        print()

    # Criterio 2: Calidad < 70%
    remaining_2 = [r for r in results if r["quality"] >= 70]
    if remaining_2:
        new_avg_2 = statistics.mean([r["quality"] for r in remaining_2])
        print(f"Eliminar partidos con calidad < 70%:")
        print(f"   - Eliminados: {len(results) - len(remaining_2)}")
        print(f"   - Restantes:  {len(remaining_2)}")
        print(f"   - Nueva calidad: {new_avg_2:.1f}% (+{new_avg_2 - avg_quality:.1f}%)")
        print()

    # Criterio 3: Múltiples criterios (calidad >= 60% Y gaps <= 35 Y capturas >= 40)
    remaining_3 = [r for r in results if r["quality"] >= 60 and r["gaps"] <= 35 and r["captures"] >= 40]
    if remaining_3:
        new_avg_3 = statistics.mean([r["quality"] for r in remaining_3])
        new_gaps_3 = statistics.mean([r["gaps"] for r in remaining_3])
        new_caps_3 = statistics.mean([r["captures"] for r in remaining_3])
        print(f"Eliminar con criterios: calidad>=60% Y gaps<=35 Y capturas>=40:")
        print(f"   - Eliminados: {len(results) - len(remaining_3)}")
        print(f"   - Restantes:  {len(remaining_3)}")
        print(f"   - Nueva calidad: {new_avg_3:.1f}% (+{new_avg_3 - avg_quality:.1f}%)")
        print(f"   - Nuevos gaps:   {new_gaps_3:.1f} (-{avg_gaps - new_gaps_3:.1f})")
        print(f"   - Nuevas capturas: {new_caps_3:.0f} (+{new_caps_3 - avg_captures:.0f})")


if __name__ == "__main__":
    main()
