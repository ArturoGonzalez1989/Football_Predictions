---
name: manage-games
description: >
  Gestiona el archivo games.csv: muestra partidos configurados, permite añadir nuevos,
  eliminar partidos terminados y actualizar horarios.
---

# Manage Games - Gestionar games.csv

## Instrucciones

### 1. Leer estado actual

Lee `betfair_scraper/games.csv` y muestra:

```
Partidos en games.csv:
| # | Partido | URL | Hora Inicio | Estado |
|---|---------|-----|-------------|--------|
| 1 | [nombre] | [url corta] | [hora o "sin horario"] | [activo/futuro/finalizado] |
```

Para determinar el estado:
- **Activo**: hora_inicio - 10min <= ahora <= hora_inicio + 150min
- **Futuro**: hora_inicio > ahora + 10min
- **Finalizado**: ahora > hora_inicio + 150min
- **Sin horario**: no tiene fecha_hora_inicio (modo legacy, siempre activo)

### 2. Acciones disponibles

#### Añadir partido
Si el usuario pide añadir un partido:
1. Necesita: nombre del partido, URL de Betfair, hora de inicio (opcional)
2. Verificar que la URL sea válida (formato Betfair)
3. Verificar que no esté ya en games.csv
4. Añadir al final del CSV con formato correcto

Formato de la URL Betfair:
```
https://www.betfair.es/exchange/plus/es/fútbol/[liga]/[partido]-apuestas-[id]
```

Formato CSV:
```csv
Game,url,fecha_hora_inicio
Equipo A - Equipo B,https://www.betfair.es/...,2026-02-10 20:00
```

#### Eliminar partido terminado
Si un partido ya terminó (hora_inicio + 150min < ahora):
1. Preguntar al usuario si quiere eliminarlo
2. Si confirma, editar games.csv eliminando esa fila

#### Actualizar horario
Si el usuario quiere cambiar la hora de inicio de un partido:
1. Editar la fila correspondiente en games.csv
2. Verificar que el formato de fecha sea correcto: `YYYY-MM-DD HH:MM`

### 3. Formatos de fecha soportados

- `2026-02-10 20:00` (recomendado: YYYY-MM-DD HH:MM)
- `10/02/2026 20:00` (alternativo: DD/MM/YYYY HH:MM)
- vacío (modo legacy: trackea siempre)

### 4. Importante

- SIEMPRE preguntar al usuario antes de modificar games.csv
- Mostrar los cambios propuestos antes de aplicarlos
- Hacer backup mental del estado actual antes de modificar
- Verificar que el CSV resultante tenga el formato correcto (headers + datos)
