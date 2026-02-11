---
name: supervisor-report
description: >
  Genera un informe completo de supervisión del proyecto. Ejecuta todas las verificaciones
  (scraper, estadísticas, calidad, partidos) y presenta un resumen consolidado con
  hallazgos, problemas y acciones recomendadas.
---

# Supervisor Report - Informe Completo de Supervisión

## Instrucciones

Ejecuta una ronda completa de supervisión. Este skill orquesta todas las verificaciones
del proyecto y genera un informe consolidado.

### Paso 1: Verificar Estado del Scraper

1. Comprobar si main.py está corriendo:
```bash
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Select-Object Id,ProcessName | Format-Table -AutoSize"
```

2. Leer las últimas 50 líneas del log más reciente en `betfair_scraper/logs/`
3. Contar errores y warnings

### Paso 2: Verificar Datos Capturados

1. Listar CSVs en `betfair_scraper/data/`
2. Para cada CSV activo (con datos recientes):
   - Leer últimas 10 filas
   - Verificar que cuotas tengan valores razonables
   - Verificar que estadísticas se estén capturando
   - Calcular cobertura de estadísticas

### Paso 3: Verificar games.csv

1. Leer `betfair_scraper/games.csv`
2. Clasificar partidos: activos, futuros, finalizados
3. Detectar partidos sin horario (modo legacy)

### Paso 4: Analizar Logs

1. Leer el log más reciente completo
2. Buscar patrones de error con Grep:
   - `ERROR` / `Error` / `Exception`
   - `timeout` / `TimeoutException`
   - `NoSuchElement` / `StaleElement`
   - `captura exitosa` / `datos guardados`

### Paso 5: Generar Informe

Presenta el informe final con este formato:

```markdown
---
## Informe de Supervisión
**Fecha**: [YYYY-MM-DD HH:MM]

---

### 1. Estado del Scraper
| Métrica | Valor |
|---------|-------|
| Proceso | [Corriendo / Parado] |
| PID | [número o N/A] |
| Último log | [nombre archivo] |
| Errores (última hora) | [número] |
| Warnings (última hora) | [número] |
| Última actividad | [timestamp] |

### 2. Partidos
| Partido | Estado | Última Captura |
|---------|--------|----------------|
| [nombre] | [activo/futuro/finalizado] | [timestamp] |

### 3. Calidad de Datos
| CSV | Filas | Cobertura Stats | Cuotas OK | Última Fila |
|-----|-------|-----------------|-----------|-------------|
| [nombre] | [N] | [X%] | [Sí/No] | [timestamp] |

### 4. Problemas Detectados

#### Críticos
- [problema crítico si hay]

#### Warnings
- [warning si hay]

#### Informativos
- [info si hay]

### 5. Acciones Recomendadas
1. [Acción concreta con instrucciones]
2. [Acción concreta con instrucciones]

### 6. Conclusión
[Estado general: Todo OK / Hay problemas que atender / Situación crítica]
[Resumen de 1-2 frases]
---
```

### Directrices

- Si TODO está bien: indica "Todo en orden" con datos que lo respalden
- Si hay problemas menores: lista como warnings con sugerencias
- Si hay problemas críticos: destácalos prominentemente con acciones urgentes
- Si no puedes verificar algo (ej: Betfair no responde): indícalo como "No verificado"
- Sé conciso pero completo - el usuario quiere un resumen rápido pero fiable
