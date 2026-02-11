---
name: check-stats
description: >
  Verifica que las estadísticas capturadas por el scraper sean completas y coherentes.
  Compara las estadísticas del CSV con las disponibles en la interfaz de Betfair para
  detectar estadísticas que no se estén capturando.
---

# Check Stats - Verificar Estadísticas Capturadas

## Instrucciones

### 1. Leer datos capturados

Lee el CSV más reciente de `betfair_scraper/data/` y analiza:

**Columnas de estadísticas a verificar:**
- `posesion_local` / `posesion_visitante` (0-100%)
- `tiros_local` / `tiros_visitante`
- `tiros_puerta_local` / `tiros_puerta_visitante`
- `corners_local` / `corners_visitante`
- `tarjetas_amarillas_local` / `tarjetas_amarillas_visitante`
- `fouls_conceded_local` / `fouls_conceded_visitante`
- `dangerous_attacks_local` / `dangerous_attacks_visitante`
- `big_chances_local` / `big_chances_visitante`
- `shots_off_target_local` / `shots_off_target_visitante`
- `blocked_shots_local` / `blocked_shots_visitante`
- `shooting_accuracy_local` / `shooting_accuracy_visitante`
- `tackles_local` / `tackles_visitante`
- `saves_local` / `saves_visitante`
- `pass_success_pct_local` / `pass_success_pct_visitante`
- `crosses_local` / `crosses_visitante`
- `goal_kicks_local` / `goal_kicks_visitante`
- `throw_ins_local` / `throw_ins_visitante`
- `momentum_local` / `momentum_visitante`

### 2. Calcular cobertura

Para las últimas 10 filas del CSV:
- Contar cuántas columnas de stats tienen valores (no vacíos, no "0" artificial)
- Calcular porcentaje de cobertura
- Identificar qué estadísticas están SIEMPRE vacías

### 3. Verificar coherencia

- Posesión local + visitante debe sumar ~100%
- Tiros a puerta <= tiros totales
- Corners, tarjetas, etc. deben ser números enteros >= 0
- El minuto del partido debe ser coherente con la cantidad de stats

### 4. Comparar con Betfair (si hay partido en vivo)

Si hay un partido activo, usa el navegador (Playwright via MCP) para:
1. Abrir la URL del partido desde `games.csv`
2. Navegar al tab de estadísticas
3. Comparar cada estadística visible con lo que tenemos en el CSV
4. Identificar estadísticas en Betfair que NO estamos capturando

### 5. Reportar

```
Verificación de Estadísticas:
- Partido: [nombre]
- Filas analizadas: [N]
- Cobertura de stats: [X%]
- Stats con datos: [lista]
- Stats VACÍAS: [lista]
- Coherencia: [OK / problemas encontrados]
- Stats en Betfair no capturadas: [lista o "Ninguna"]

Diagnóstico: [OK / PROBLEMA - descripción]
```
