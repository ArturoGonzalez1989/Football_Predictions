#!/usr/bin/env python3
"""
Test para verificar que la API de momentum funciona correctamente
y que podemos calcular valores agregados desde ella.
"""
import re
import json
import requests
from pprint import pprint

# EventId que sabemos que tiene momentum (del partido Sion vs FC Basel)
event_id = "bomuidcdl673b8rje49cbj40k"
outlet_key = "1hegv772yrv901291e00xzm9rv"

# URL de la API de momentum
momentum_url = f"https://betfair.cpp.statsperform.com/stats/live-stats/momentum"
params = {
    'eventId': event_id,
    'outletkey': outlet_key
}

print("="*70)
print("TEST: API de Momentum")
print("="*70)
print(f"\nEventId: {event_id}")
print(f"URL: {momentum_url}")
print(f"Params: {params}\n")

# Hacer la petición
print(">> Consultando API de momentum...")
try:
    response = requests.get(momentum_url, params=params, timeout=10)
    response.raise_for_status()
    print(f"OK Status: {response.status_code}")
    print(f"OK Content-Type: {response.headers.get('Content-Type')}")
    print(f"OK Content-Length: {len(response.text)} chars\n")

    # Guardar respuesta completa para inspección
    with open("momentum_api_response.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    print("OK Respuesta guardada en momentum_api_response.html\n")

    # Intentar parsear como hace parse_momentum_html()
    print("="*70)
    print("PARSEANDO DATOS (igual que parse_momentum_html)")
    print("="*70)

    # Buscar el script con los datos JSON
    pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
    match = re.search(pattern, response.text, re.DOTALL)

    if not match:
        print("ERROR: No se encontro __NEXT_DATA__ en la respuesta")
        print("\n>> Buscando otros patrones de datos...")
        # Buscar cualquier JSON en la respuesta
        json_patterns = [
            r'var\s+data\s*=\s*({.*?});',
            r'window\.__data__\s*=\s*({.*?});',
            r'"momentum":\s*(\[.*?\])',
            r'"chartData":\s*(\[.*?\])',
        ]
        for p in json_patterns:
            m = re.search(p, response.text, re.DOTALL)
            if m:
                print(f"   Encontrado patron: {p[:50]}...")
                try:
                    data_str = m.group(1)
                    print(f"   Preview: {data_str[:200]}...")
                except:
                    pass
    else:
        print("OK __NEXT_DATA__ encontrado!\n")

        # Parsear JSON
        try:
            data = json.loads(match.group(1))
            print("OK JSON parseado correctamente\n")

            # Guardar JSON completo
            with open("momentum_api_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print("OK JSON guardado en momentum_api_data.json\n")

            # Navegar la estructura
            props = data.get('props', {})
            page_props = props.get('pageProps', {})

            print("Claves disponibles en pageProps:")
            print(f"  {list(page_props.keys())}\n")

            # Buscar momentum en diferentes ubicaciones
            momentum_data = None
            momentum_key = None

            for key in ['momentum', 'momentumData', 'chartData', 'data', 'stats']:
                if key in page_props and page_props[key]:
                    momentum_data = page_props[key]
                    momentum_key = key
                    break

            if momentum_data:
                print(f"OK Datos de momentum encontrados en: '{momentum_key}'")
                print(f"   Tipo: {type(momentum_data)}")

                if isinstance(momentum_data, list):
                    print(f"   Longitud: {len(momentum_data)} elementos")
                    if len(momentum_data) > 0:
                        print(f"\n   Primer elemento:")
                        pprint(momentum_data[0], indent=6)
                        print(f"\n   Ultimo elemento:")
                        pprint(momentum_data[-1], indent=6)

                        # Intentar calcular valores agregados
                        print("\n" + "="*70)
                        print("CALCULANDO VALORES AGREGADOS")
                        print("="*70)

                        home_total = 0
                        away_total = 0

                        for item in momentum_data:
                            # Probar diferentes estructuras
                            home_val = item.get('home') or item.get('homeValue') or item.get('home_value') or 0
                            away_val = item.get('away') or item.get('awayValue') or item.get('away_value') or 0

                            if isinstance(home_val, (int, float)):
                                home_total += home_val
                            if isinstance(away_val, (int, float)):
                                away_total += away_val

                        print(f"OK Momentum Local (agregado): {home_total:.2f}")
                        print(f"OK Momentum Visitante (agregado): {away_total:.2f}")
                        print(f"OK Total puntos de datos: {len(momentum_data)}")

                elif isinstance(momentum_data, dict):
                    print(f"   Claves: {list(momentum_data.keys())}")
                    print(f"\n   Contenido:")
                    pprint(momentum_data, indent=6)
            else:
                print("ERROR: No se encontraron datos de momentum en pageProps")
                print("\n   Estructura completa de pageProps:")
                pprint(page_props, depth=2)

        except json.JSONDecodeError as e:
            print(f"ERROR parseando JSON: {e}")
        except Exception as e:
            print(f"ERROR inesperado: {e}")
            import traceback
            traceback.print_exc()

except requests.exceptions.RequestException as e:
    print(f"ERROR en peticion HTTP: {e}")
except Exception as e:
    print(f"ERROR inesperado: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("FIN DEL TEST")
print("="*70)
