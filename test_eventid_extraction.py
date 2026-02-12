#!/usr/bin/env python3
"""
Test para diagnosticar por qué el eventId se está truncando
"""
import re
import requests

# Betfair event ID del partido Sion vs FC Basel
betfair_event_id = "35234028"

# URL del videoplayer (igual que en stats_api.py)
videoplayer_url = f"https://videoplayer.betfair.es/GetPlayer.do?eID={betfair_event_id}&contentType=viz&contentView=mstats"

print(f">> Descargando: {videoplayer_url}")
response = requests.get(videoplayer_url, timeout=10)
response.raise_for_status()

content = response.text

# Guardar el HTML completo para inspección
with open("videoplayer_response.html", "w", encoding="utf-8") as f:
    f.write(content)
print(f"OK HTML guardado en videoplayer_response.html ({len(content)} chars)")

# Regex ACTUAL que usa stats_api.py
regex_actual = r'(?:providerEventId|performMCCFixtureUUID|streamUUID)\s*[=:]\s*["\']?([a-z0-9]{20,30})["\']?'
match_actual = re.search(regex_actual, content, re.IGNORECASE)

print("\n" + "="*70)
print("REGEX ACTUAL (stats_api.py):")
print("="*70)
print(f"Patron: {regex_actual}")
if match_actual:
    print(f"OK Match encontrado: '{match_actual.group(1)}'")
    print(f"   Longitud: {len(match_actual.group(1))} caracteres")
    print(f"   Contexto: ...{content[max(0, match_actual.start()-30):match_actual.end()+30]}...")
else:
    print("ERROR No se encontro match")

# Buscar TODAS las apariciones de bomuidcd en el contenido
print("\n" + "="*70)
print("BUSQUEDA DE 'bomuidcd' EN EL CONTENIDO:")
print("="*70)
for match in re.finditer(r'bomuidcd[a-z0-9]*', content, re.IGNORECASE):
    text = match.group(0)
    start = match.start()
    context_start = max(0, start - 50)
    context_end = min(len(content), start + len(text) + 50)
    context = content[context_start:context_end]

    print(f"\nEncontrado: '{text}' (longitud: {len(text)})")
    print(f"   Posicion: {start}")
    print(f"   Contexto: ...{context}...")

# Buscar todos los posibles campos que podrían contener el eventId
print("\n" + "="*70)
print("BUSQUEDA DE CAMPOS CONOCIDOS:")
print("="*70)
for field in ['providerEventId', 'performMCCFixtureUUID', 'streamUUID', 'eventId', 'fixtureId']:
    pattern = rf'{field}\s*[=:]\s*["\']?([a-zA-Z0-9]+)["\']?'
    matches = re.findall(pattern, content, re.IGNORECASE)
    if matches:
        print(f"\n{field}:")
        for m in matches[:5]:  # Mostrar primeros 5
            print(f"  - {m} (longitud: {len(m)})")

print("\nOK Analisis completo")
