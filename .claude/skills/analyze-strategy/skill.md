---
name: analyze-strategy
description: >
  Lanza el análisis completo de una estrategia o cartera de apuestas Betfair usando el
  agente strategy-analyst. Acepta un CSV como argumento o lo detecta automáticamente.
  Ejemplos: /analyze-strategy, /analyze-strategy analisis/cartera_2026-02-26.csv,
  /analyze-strategy --strategy "Pressure Cooker"
---

# Analyze Strategy — Análisis de Estrategias de Apuestas

## Instrucciones

Cuando el usuario invoca esta skill (con o sin argumentos), debes:

### 1. Parsear argumentos

Si el usuario escribió argumentos después del comando, intérpretalos:
- Si hay una ruta `.csv` → ese es el fichero a analizar
- Si hay `--strategy "nombre"` → filtrar solo esa estrategia
- Si hay `--match partial_id` → analizar solo ese partido
- Si no hay argumentos → detectar automáticamente el CSV más reciente

### 2. Detectar CSV si no se especificó

```bash
# Buscar el CSV más reciente en analisis/
ls -t analisis/*.csv 2>/dev/null | head -5

# Si no hay, usar placed_bets.csv
ls betfair_scraper/placed_bets.csv 2>/dev/null
```

Muestra al usuario qué fichero vas a analizar y cuántas filas tiene:
```bash
wc -l <ruta_csv>
head -1 <ruta_csv>
```

### 3. Confirmar y lanzar

Informa al usuario brevemente:
```
📊 Analizando: analisis/cartera_2026-02-26.csv
   Estrategia filtro: [Pressure Cooker / todas]
   Partido filtro: [match_id / todos]

Lanzando agente strategy-analyst...
```

Luego invoca el **agente `strategy-analyst`** pasándole toda la información necesaria:
- Ruta del CSV
- Filtro de estrategia (si aplica)
- Filtro de partido (si aplica)

### 4. Reportar resultado

Cuando el agente termine, informa al usuario:
- Ruta del informe generado (`aux/analysis_*.md`)
- Resumen de 3-5 puntos clave de los hallazgos
- Estadísticas básicas: N partidos analizados, N apuestas, calidad media de entrada

---

## Ejemplos de uso

```
/analyze-strategy
→ Analiza el CSV más reciente en analisis/

/analyze-strategy analisis/cartera_2026-02-26.csv
→ Analiza ese CSV específico

/analyze-strategy analisis/cartera_2026-02-26.csv --strategy "Pressure Cooker"
→ Solo las bets de Pressure Cooker

/analyze-strategy --strategy "Goal Clustering" --match newells
→ Solo la bet de Goal Clustering en el partido de Newells

/analyze-strategy betfair_scraper/placed_bets.csv
→ Analiza las apuestas paper del sistema live
```
