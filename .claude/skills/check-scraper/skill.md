---
name: check-scraper
description: >
  Verifica si el scraper de Betfair (main.py) está en ejecución, revisa el log más reciente
  en busca de errores, y reporta el estado general del proceso.
---

# Check Scraper - Verificar Estado del Scraper

## Instrucciones

Realiza las siguientes verificaciones en orden:

### 1. Verificar si el proceso está corriendo

Ejecuta en Bash:
```bash
powershell -Command "Get-Process python -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime | Format-Table -AutoSize"
```

Si no hay resultados, el scraper NO está corriendo.

### 2. Revisar el log más reciente

1. Lista los archivos de log ordenados por fecha:
```bash
powershell -Command "Get-ChildItem 'betfair_scraper\logs\scraper_*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 5 | Select-Object Name, LastWriteTime"
```

2. Lee las últimas 100 líneas del log más reciente buscando:
   - Líneas con "ERROR" o "Error"
   - Líneas con "WARNING" o "Warning"
   - Líneas con "captura exitosa" o "datos guardados"
   - La última línea de actividad (para saber cuándo fue la última acción)

### 3. Verificar antigüedad de datos

Lee el CSV más reciente en `betfair_scraper/data/` y verifica:
- Cuándo fue el último timestamp registrado
- Si han pasado más de 5 minutos sin captura nueva, hay un problema

### 4. Reportar

Presenta un resumen conciso:

```
Estado del Scraper:
- Proceso: [Corriendo (PID: XXXX) / NO corriendo]
- Último log: [nombre del archivo]
- Errores recientes: [X errores en última hora]
- Última captura: [timestamp]
- Diagnóstico: [OK / PROBLEMA - descripción]
```

Si el scraper no está corriendo y debería estarlo, sugiere al usuario:
```bash
cd betfair_scraper && python main.py
```
