#!/usr/bin/env python3
"""Elimina partidos con calidad < threshold."""

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
    "xg_local", "xg_visitante"
    # Excluidos: ataques_peligrosos (nunca se capturan, reducen calidad artificialmente)
]

def calculate_quality(csv_path):
    """Calcula calidad de un partido."""
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return 0

        total_captures = len(rows)
        non_null_counts = {field: 0 for field in STAT_FIELDS}

        for row in rows:
            for field in STAT_FIELDS:
                value = row.get(field, "").strip()
                if value and value != "" and value != "None" and value != "N/A":
                    non_null_counts[field] += 1

        coverage_percentages = []
        for field in STAT_FIELDS:
            coverage = (non_null_counts[field] / total_captures * 100) if total_captures > 0 else 0
            coverage_percentages.append(coverage)

        return statistics.mean(coverage_percentages) if coverage_percentages else 0

    except Exception:
        return 0


def main():
    THRESHOLD = 70  # Eliminar partidos con calidad < 70% (sin ataques_peligrosos)

    print("=" * 80)
    print(f"ELIMINANDO PARTIDOS CON CALIDAD < {THRESHOLD}%")
    print("=" * 80)

    deleted = []
    kept = []

    for csv_file in DATA_DIR.glob("partido_*.csv"):
        quality = calculate_quality(csv_file)

        if quality < THRESHOLD:
            csv_file.unlink()  # Eliminar archivo
            deleted.append((csv_file.name, quality))
        else:
            kept.append((csv_file.name, quality))

    print(f"\n[OK] Eliminados: {len(deleted)} partidos")
    print(f"[OK] Conservados: {len(kept)} partidos")

    if deleted:
        print(f"\nPartidos eliminados:")
        for name, qual in sorted(deleted, key=lambda x: x[1])[:10]:
            partido = name.replace("partido_", "").replace(".csv", "")[:60]
            print(f"   - {partido:<60} (calidad: {qual:.1f}%)")
        if len(deleted) > 10:
            print(f"   ... y {len(deleted) - 10} mas")

    # Calcular nueva calidad promedio
    if kept:
        avg_quality = statistics.mean([q for _, q in kept])
        print(f"\nNueva calidad promedio: {avg_quality:.1f}%")


if __name__ == "__main__":
    main()
