#!/usr/bin/env python3
import csv

csv_path = r"betfair_scraper\data\partido_sion-fc-basel-apuestas-35234028.csv"

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)

    found_count = 0
    total_count = 0

    for row in reader:
        total_count += 1
        momentum_local = row.get('momentum_local', '')
        momentum_visitante = row.get('momentum_visitante', '')

        if momentum_local or momentum_visitante:
            found_count += 1
            timestamp = row.get('timestamp_utc', '')
            print(f"Fila {total_count}: {timestamp} - Local: {momentum_local}, Visitante: {momentum_visitante}")

    print(f"\n{'='*70}")
    print(f"Total filas: {total_count}")
    print(f"Filas con momentum: {found_count}")
    print(f"Filas SIN momentum: {total_count - found_count}")
