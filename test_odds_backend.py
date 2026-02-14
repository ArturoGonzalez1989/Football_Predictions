#!/usr/bin/env python3
"""
Script de prueba para verificar que csv_reader está devolviendo las cuotas lay.
"""
import sys
sys.path.insert(0, r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\dashboard\backend')

from utils.csv_reader import load_match_full
import json

# Cargar datos del partido
match_id = "athletico-pr-santos-apuestas-35207628"
result = load_match_full(match_id)

# Mostrar las últimas 3 entradas del odds_timeline
print("=== ÚLTIMAS 3 ENTRADAS DEL ODDS TIMELINE ===\n")
for entry in result['odds_timeline'][-3:]:
    print(json.dumps(entry, indent=2))
    print()

# Verificar qué claves tiene cada entrada
print("=== CLAVES EN LA ÚLTIMA ENTRADA ===")
if result['odds_timeline']:
    print(list(result['odds_timeline'][-1].keys()))
