---
name: find-matches
description: >
  Busca partidos de fútbol actualmente en juego o próximos en Betfair Exchange.
  Compara con games.csv para identificar partidos que deberíamos estar trackeando
  pero que aún no están registrados.
---

# Find Matches - Buscar Partidos en Betfair

## Instrucciones

### 1. Leer partidos actuales en games.csv

Lee `betfair_scraper/games.csv` y lista todos los partidos configurados con:
- Nombre del partido
- URL
- Hora de inicio (si tiene)

### 2. Buscar partidos en Betfair

Usa el navegador (Playwright via MCP) para:

1. Navegar a `https://www.betfair.es/sport/football`
2. Buscar la sección "En directo" / "In-Play"
3. Extraer todos los partidos en vivo:
   - Nombre del partido (equipos)
   - Liga/competición
   - Minuto actual
   - URL del partido

4. También buscar partidos próximos (Today / Hoy):
   - Nombre del partido
   - Hora de inicio
   - Liga/competición
   - URL

### 3. Comparar con games.csv

Para cada partido encontrado en Betfair:
- Verificar si ya está en games.csv (comparar URLs)
- Si NO está → marcarlo como "NUEVO - sin registrar"
- Si está → verificar que la hora de inicio coincida

### 4. Verificar partidos finalizados

Para cada partido en games.csv:
- Si la hora de inicio + 150 minutos ya pasó → probablemente terminó
- Si el scraper ya no captura datos de ese partido → confirmar que terminó

### 5. Reportar

```
Partidos en Betfair:
- En vivo: [N partidos]
  - [Partido 1] (min XX) - [En games.csv: SÍ/NO]
  - [Partido 2] (min XX) - [En games.csv: SÍ/NO]

- Próximos hoy: [N partidos]
  - [Partido 1] (HH:MM) - [En games.csv: SÍ/NO]
  - [Partido 2] (HH:MM) - [En games.csv: SÍ/NO]

Acciones recomendadas:
- Añadir a games.csv: [lista de partidos nuevos con URLs]
- Eliminar de games.csv: [lista de partidos terminados]
```

Si hay partidos nuevos para añadir, pregunta al usuario si quiere que los añada a games.csv.
