---
name: check-quality
description: >
  Verifica la calidad general de los datos capturados en los CSVs de salida.
  Revisa cuotas, timestamps, estadísticas y detecta anomalías o datos corruptos.
---

# Check Quality - Verificar Calidad de Datos

## Instrucciones

### 1. Identificar CSVs de salida

Lista los archivos en `betfair_scraper/data/`:
```bash
dir "betfair_scraper\data\*.csv"
```

### 2. Analizar cada CSV

Para cada CSV, lee las últimas 20-30 filas y verifica:

#### Cuotas (Odds)
- `local_odds`, `draw_odds`, `visitante_odds`: deben estar entre 1.01 y 1000
- `back_over_*` / `lay_over_*`: deben ser > 1.0
- Si hay valores 0, vacíos o negativos → problema
- Las cuotas deben cambiar ligeramente entre capturas (no todas iguales)

#### Timestamps
- Formato válido (datetime parseable)
- Diferencia entre capturas consecutivas: ~60 segundos (configurable)
- Sin gaps grandes (> 5 minutos) sin explicación
- Sin timestamps duplicados

#### Marcador y Minuto
- `goles_local` / `goles_visitante`: enteros >= 0
- `minuto_partido`: debe ir incrementando
- El minuto debe ser coherente con el tiempo transcurrido

#### Estadísticas Opta
- Valores numéricos donde corresponde
- Posesión: 0-100%, debe sumar ~100% entre ambos equipos
- Porcentajes (pass_success, shooting_accuracy): 0-100%
- Contadores (corners, tiros, etc.): enteros >= 0, deben ser no-decrecientes

### 3. Detectar anomalías

Buscar:
- Filas donde TODAS las stats están vacías (captura fallida)
- Filas donde las cuotas son exactamente iguales a la fila anterior (posible duplicado)
- Valores imposibles (posesión > 100%, cuotas negativas, etc.)
- Gaps temporales grandes

### 4. Calcular métricas

```
Métricas de Calidad:
- Total de filas: [N]
- Filas con cuotas válidas: [N] ([X%])
- Filas con stats válidas: [N] ([X%])
- Filas con timestamp válido: [N] ([X%])
- Filas completamente vacías: [N]
- Gap temporal máximo: [X minutos]
- Cobertura de estadísticas: [X%]
```

### 5. Reportar

```
Informe de Calidad - [nombre del CSV]
- Período: [primer timestamp] → [último timestamp]
- Total filas: [N]
- Calidad general: [BUENA / ACEPTABLE / MALA]

Cuotas: [OK / X problemas]
Stats: [OK / X problemas]
Timestamps: [OK / X problemas]

Anomalías detectadas:
- [descripción de cada anomalía]

Recomendaciones:
- [acción correctiva si es necesario]
```
