# Sistema de Tracking Basado en Horarios

## Descripción

El scraper ahora soporta **tracking automático basado en horarios**. Esto te permite:
- Dejar el script corriendo todo el día
- Añadir todos los partidos de la semana al inicio
- El script automáticamente abre tabs cuando llega la hora del partido
- Cierra tabs cuando el partido termina
- Sin intervención manual necesaria

## Formato del archivo `games.csv`

El archivo ahora acepta una tercera columna opcional: `fecha_hora_inicio`

```csv
Game,url,fecha_hora_inicio
Real Madrid - Barcelona,https://www.betfair.es/...,2026-02-10 20:00
Manchester City - Liverpool,https://www.betfair.es/...,2026-02-11 18:30
PSG - Bayern,https://www.betfair.es/...,11/02/2026 21:00
```

### Formatos de fecha aceptados:
- **YYYY-MM-DD HH:MM** (ej: `2026-02-10 20:00`)
- **DD/MM/YYYY HH:MM** (ej: `10/02/2026 20:00`)

### Columna `fecha_hora_inicio`:
- **Vacía o sin columna**: Modo legacy, trackea inmediatamente
- **Con fecha/hora**: Modo scheduling, solo trackea en ventana de tiempo

## Ventanas de tracking

Por defecto:
- **10 minutos ANTES** del inicio: El script abre la tab del partido
- **150 minutos DESPUÉS** del inicio: El script cierra la tab del partido

Esto significa que para un partido que empieza a las 20:00:
- Se abre la tab a las 19:50
- Se cierra la tab a las 22:30

### Personalizar ventanas

Puedes ajustar estas ventanas con argumentos de línea de comandos:

```bash
# Abrir 5 min antes, cerrar 120 min después
python main.py --ventana-antes 5 --ventana-despues 120

# Abrir 15 min antes, cerrar 180 min después (3 horas)
python main.py --ventana-antes 15 --ventana-despues 180
```

## Ejemplo de uso completo

### 1. Preparar `games.csv` al inicio del día

```csv
Game,url,fecha_hora_inicio
Partido 1,https://www.betfair.es/...,2026-02-10 15:00
Partido 2,https://www.betfair.es/...,2026-02-10 17:30
Partido 3,https://www.betfair.es/...,2026-02-10 20:00
Partido 4,https://www.betfair.es/...,2026-02-11 12:00
Partido 5,https://www.betfair.es/...,2026-02-11 19:00
```

### 2. Iniciar el script

```bash
python main.py
```

### 3. Qué verás en el log

```
📅 MODO SCHEDULING ACTIVADO
   Ventana tracking: 10 min antes → 150 min después
   Total en CSV: 5 partidos
   ✓ Partidos activos ahora: 1
   ⏰ Partidos futuros: 4
   ✅ Partidos finalizados: 0

📋 Próximos partidos a trackear:
      Partido 2 (en 120 min)
      Partido 3 (en 270 min)
      Partido 4 (en 1200 min)
      Partido 5 (en 1620 min)
```

### 4. Durante el día

El script automáticamente:
- Abre tabs cuando llega la hora de cada partido
- Captura datos cada 60 segundos
- Cierra tabs cuando pasan 150 minutos del inicio
- Revisa `games.csv` cada 5 ciclos por si añades más partidos

## Añadir partidos sobre la marcha

Puedes editar `games.csv` mientras el script corre:

1. Abre `games.csv`
2. Añade nuevos partidos con sus horarios
3. Guarda el archivo
4. En máximo 5 ciclos (~5 minutos), el script detectará los nuevos partidos

## Ventajas

✅ **Desatendido**: Deja el script corriendo sin supervisión
✅ **Eficiente**: Solo trackea cuando hay partidos activos
✅ **Flexible**: Añade/remueve partidos sin reiniciar
✅ **Escalable**: Trackea semanas completas de partidos

## Comportamiento sin scheduling (modo legacy)

Si NO incluyes la columna `fecha_hora_inicio` o la dejas vacía, el script funciona como antes:
- Abre todas las tabs inmediatamente
- Trackea continuamente
- No cierra tabs automáticamente

```csv
Game,url
Partido sin horario,https://www.betfair.es/...
```

## Parámetros adicionales

```bash
python main.py \
  --reload-interval 5 \      # Revisar games.csv cada 5 ciclos (default)
  --ventana-antes 10 \        # Minutos antes del inicio (default: 10)
  --ventana-despues 150 \     # Minutos después del inicio (default: 150)
  --ciclo 60 \                # Segundos entre capturas (default: 60)
  --login-wait 30             # Segundos para login manual (default: 60)
```

## Casos de uso

### Tracking de fin de semana completo

```csv
Game,url,fecha_hora_inicio
Sábado - Partido 1,https://...,2026-02-15 12:00
Sábado - Partido 2,https://...,2026-02-15 14:30
Sábado - Partido 3,https://...,2026-02-15 17:00
Sábado - Partido 4,https://...,2026-02-15 19:30
Domingo - Partido 1,https://...,2026-02-16 12:00
Domingo - Partido 2,https://...,2026-02-16 14:30
Domingo - Partido 3,https://...,2026-02-16 17:00
```

Inicia el viernes por la noche, el script capturará todos los partidos del fin de semana.

### Tracking de Champions League

```csv
Game,url,fecha_hora_inicio
Real Madrid - Man City,https://...,2026-04-08 21:00
Bayern - Arsenal,https://...,2026-04-09 21:00
PSG - Barcelona,https://...,2026-04-09 21:00
```

## Logs útiles

Durante el tracking verás mensajes como:

```
🔄 Revisando games.csv para detectar cambios...
⏰ Partidos futuros: 3
   - Manchester City - Liverpool (en 45 min)
   - PSG - Bayern (en 120 min)

➕ Abriendo 1 nuevos partidos...
   - Real Madrid - Barcelona (inicia en 8 min)

🗑️ Cerrando 1 partidos finalizados/removidos...
   - Cerrando: Atlético - Sevilla
```

## Troubleshooting

**Problema**: El script no abre tabs de partidos futuros
- **Solución**: Esto es normal, esperará hasta que llegue la ventana de tracking

**Problema**: El script cerró una tab muy pronto
- **Solución**: Ajusta `--ventana-despues` a más minutos (ej: 180)

**Problema**: El script abre tabs muy tarde
- **Solución**: Ajusta `--ventana-antes` a más minutos (ej: 15)

**Problema**: Formato de fecha inválido
- **Solución**: Usa `YYYY-MM-DD HH:MM` o `DD/MM/YYYY HH:MM`
