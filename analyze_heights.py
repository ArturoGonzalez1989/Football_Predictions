import json
from collections import Counter

# Leer el archivo con el resultado de Playwright
with open(r'C:\Users\agonz\.claude\projects\c--Users-agonz-OneDrive-Documents-Proyectos-Furbo\9f2699c6-5f83-4e13-adf6-1ce651c8a6f2\tool-results\mcp-plugin_playwright_playwright-browser_run_code-1770588942772.txt', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Extraer el JSON del resultado
result_text = data[0]['text']
result_json = json.loads(result_text.split('### Result\n')[1])

# Obtener todos los heights
heights = [d['height'] for d in result_json['divs']]
classes = [d['className'] for d in result_json['divs']]

print(f'Total divs con height: {len(heights)}')
print(f'Divs con height="0": {heights.count("0")}')
print(f'Divs con height != "0": {len([h for h in heights if h != "0"])}')

# Contar valores únicos
counter = Counter(heights)
print(f'\nTotal valores únicos de height: {len(counter)}')

print('\n=== Top 30 valores más comunes ===')
for height, count in counter.most_common(30):
    print(f'{height}: {count} veces')

# Analizar clases
print('\n=== Clases encontradas ===')
class_counter = Counter(classes)
for cls, count in class_counter.most_common(10):
    print(f'{cls}: {count} veces')

# Mostrar algunos ejemplos con height != 0
print('\n=== Primeros 20 divs con height != "0" ===')
non_zero_divs = [d for d in result_json['divs'] if d['height'] != '0']
for i, div in enumerate(non_zero_divs[:20]):
    print(f"{i}: height={div['height']}, class={div['className']}")
