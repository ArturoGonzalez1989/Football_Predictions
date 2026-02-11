# Clean Games - Limpieza automática de partidos terminados

Script simple que elimina automáticamente los partidos terminados de `games.csv`.

## 🎯 Qué hace

Lee `games.csv` y elimina los partidos que:
- Comenzaron hace más de 120 minutos (90 min de juego + 30 min de margen)
- Ejemplo: Si un partido empezó a las 15:30, se elimina a las 17:30 o después

Luego reporta:
- Cuántos partidos se eliminaron
- Cuántos partidos siguen siendo activos

## 🚀 Uso

### Ejecución básica

```bash
cd betfair_scraper
python clean_games.py
```

Eso es todo. El script hace el resto automáticamente.

### Ejemplo de salida

```
[LIMPIEZA COMPLETADA]
   - Eliminados: 3 partidos
   - Activos: 5 partidos

Partidos eliminados:
   - Real Madrid - Barcelona (2026-02-11 15:30)
   - Arsenal - Chelsea (2026-02-11 14:00)
   - Ajax - PSV (2026-02-11 16:45)
```

## ⚙️ Configuración

El archivo `clean_games.py` tiene una configuración simple:

```python
MATCH_DURATION_MINUTES = 120  # Minutos hasta considerar terminado
```

- Cambiar este valor si quieres otro umbral (ej: 150 min para partidos más largos)
- Por defecto: 120 minutos es lo recomendado

## 📋 Format de games.csv

El script espera este formato:

```csv
Game,url,fecha_hora_inicio
Equipo A - Equipo B,https://www.betfair.es/exchange/plus/es/fútbol/...,2026-02-11 15:30
```

- `Game`: Nombres de los equipos
- `url`: URL del partido en Betfair
- `fecha_hora_inicio`: Formato YYYY-MM-DD HH:MM o DD/MM/YYYY HH:MM

## ⚠️ Notas importantes

- **Automático**: No pregunta, solo elimina. Esto es intencional.
- **Sin backup**: Los partidos se eliminan directamente de games.csv
- **Partidos futuros**: No se eliminan partidos que aún no han empezado
- **Sin fecha**: Los partidos sin fecha en `fecha_hora_inicio` nunca se eliminan (modo legacy)

## 🔄 ¿Cuándo ejecutarlo?

Ejecútalo regularmente:
- Cada mañana al revisar el estado del scraper
- Después de supervisar nuevos partidos
- Manualmente cuando veas que games.csv tiene muchas entradas antiguas

El supervisor automático lo ejecuta en PASO 3 de su ciclo.

## 💾 CSV actualizado

Después de ejecutar, el archivo `games.csv` queda:
- Con solo los partidos activos/futuros
- Listo para nuevas búsquedas de partidos en Betfair
- Más limpio y manejable
