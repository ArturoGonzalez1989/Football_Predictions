# Resumen: Sistema de Tracking Basado en Horarios

## ✅ Implementación Completada

He implementado exitosamente el sistema de scheduling que pediste. Ahora puedes:

1. **Dejar el script corriendo todo el día** sin supervisión
2. **Añadir todos los partidos de la semana** al inicio con sus horarios
3. **El script automáticamente**:
   - Abre tabs cuando llega la hora del partido (10 min antes por defecto)
   - Captura datos cada 60 segundos
   - Cierra tabs cuando el partido termina (150 min después por defecto)
4. **Sin reiniciar**: Añadir partidos sobre la marcha editando games.csv

## 📝 Cambios Realizados

### 1. Archivo `main.py`

#### Función `leer_games_csv()` (líneas 249-297)
- Ahora lee columna `fecha_hora_inicio` del CSV
- Soporta formatos: `YYYY-MM-DD HH:MM` y `DD/MM/YYYY HH:MM`
- Retorna lista de dicts: `[{"url": "...", "game": "...", "fecha_hora_inicio": datetime}, ...]`

#### Nueva función `filtrar_partidos_activos()` (líneas 300-340)
- Filtra partidos según ventana de tracking
- Retorna: (activos, futuros, finalizados)
- Partidos sin `fecha_hora_inicio` → modo legacy (trackea siempre)

#### Función `detectar_cambios_games()` actualizada (líneas 2120-2159)
- Ahora usa `filtrar_partidos_activos()`
- Considera horarios para abrir/cerrar tabs
- Retorna: (partidos_a_abrir, tabs_a_cerrar)

#### Función `main()` actualizada (líneas 2189-2336)
- **Nuevos argumentos**:
  - `--ventana-antes N`: Minutos antes del inicio (default: 10)
  - `--ventana-despues N`: Minutos después del inicio (default: 150)
- **Modo scheduling automático**: Se activa si games.csv tiene `fecha_hora_inicio`
- **Logs informativos**: Muestra partidos activos/futuros/finalizados
- **Loop principal**: Revisa horarios cada `--reload-interval` ciclos

### 2. Archivo `games.csv`

Nueva estructura:
```csv
Game,url,fecha_hora_inicio
Partido 1,https://...,2026-02-10 20:00
Partido 2,https://...,11/02/2026 18:30
Partido sin horario,https://...,
```

- Columna `fecha_hora_inicio` es **opcional**
- Si está vacía → modo legacy (trackea inmediatamente)
- Si tiene fecha → modo scheduling (solo en ventana de tiempo)

### 3. Nuevos Archivos

- **`SCHEDULING.md`**: Documentación completa del sistema
- **`test_scheduling.py`**: Tests automatizados (todos pasan ✅)
- **`RESUMEN_SCHEDULING.md`**: Este archivo

## 🚀 Cómo Usar

### Ejemplo Básico

1. **Edita `games.csv`**:
```csv
Game,url,fecha_hora_inicio
Real Madrid - Barcelona,https://www.betfair.es/...,2026-02-10 20:00
Man City - Liverpool,https://www.betfair.es/...,2026-02-11 18:30
```

2. **Inicia el script**:
```bash
python main.py
```

3. **Output esperado**:
```
📅 MODO SCHEDULING ACTIVADO
   Ventana tracking: 10 min antes → 150 min después
   Total en CSV: 2 partidos
   ✓ Partidos activos ahora: 0
   ⏰ Partidos futuros: 2

📋 Próximos partidos a trackear:
      Real Madrid - Barcelona (en 45 min)
      Man City - Liverpool (en 1230 min)

Iniciando observador con 0 partidos.
⏰ Sin partidos activos para capturar en este ciclo
```

4. **Cuando llegue la hora** (10 min antes del inicio):
```
🔄 Revisando games.csv para detectar cambios...
➕ Abriendo 1 nuevos partidos...
   - Real Madrid - Barcelona (inicia en 8 min)
✓ Tabs actualizadas: 1 partidos activos
```

### Personalizar Ventanas

```bash
# Abrir 5 min antes, cerrar 120 min después
python main.py --ventana-antes 5 --ventana-despues 120

# Abrir 15 min antes, cerrar 180 min después (3 horas)
python main.py --ventana-antes 15 --ventana-despues 180
```

### Caso de Uso Real: Semana Completa

**games.csv**:
```csv
Game,url,fecha_hora_inicio
Lunes - Partido 1,https://...,2026-02-10 19:00
Martes - Partido 1,https://...,2026-02-11 20:00
Miércoles - Partido 1,https://...,2026-02-12 18:30
Jueves - Champions 1,https://...,2026-02-13 21:00
Jueves - Champions 2,https://...,2026-02-13 21:00
Viernes - Partido 1,https://...,2026-02-14 20:30
Sábado - Partido 1,https://...,2026-02-15 12:00
Sábado - Partido 2,https://...,2026-02-15 14:30
Sábado - Partido 3,https://...,2026-02-15 17:00
Domingo - Partido 1,https://...,2026-02-16 12:00
```

Inicias el lunes por la mañana, el script captura TODA la semana automáticamente.

## 🔍 Ventajas del Sistema

### Antes (sin scheduling)
- ❌ Abrir todas las tabs manualmente
- ❌ Script capturando partidos que no han empezado
- ❌ Tabs abiertas de partidos ya terminados
- ❌ Reiniciar script cada vez que añades partidos

### Ahora (con scheduling)
- ✅ **Desatendido**: Funciona sin supervisión
- ✅ **Eficiente**: Solo captura cuando hay partido
- ✅ **Flexible**: Añade partidos sobre la marcha
- ✅ **Escalable**: Semanas completas sin problema
- ✅ **Smart**: Abre/cierra tabs automáticamente

## 📊 Tests

Ejecuta los tests para verificar:
```bash
python test_scheduling.py
```

Resultado esperado:
```
[PASS] TEST PASADO - Parseo de fechas
[PASS] TEST PASADO - filtrar_partidos_activos
[PASS] TEST PASADO - Lectura de games.csv
TODOS LOS TESTS PASARON [OK]
```

## 🎯 Comportamiento por Defecto

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `--ventana-antes` | 10 min | Abrir tab X minutos antes del inicio |
| `--ventana-despues` | 150 min | Cerrar tab X minutos después del inicio |
| `--reload-interval` | 5 ciclos | Revisar games.csv cada X ciclos |
| `--ciclo` | 60 seg | Capturar datos cada X segundos |

Para un partido a las 20:00:
- Tab se abre: 19:50
- Partido empieza: 20:00
- Tab se cierra: 22:30

## 🔧 Compatibilidad

### Modo Legacy (sin cambios)
Si NO usas la columna `fecha_hora_inicio`, el script funciona **exactamente igual** que antes:

```csv
Game,url
Partido,https://...
```
- Abre todas las tabs inmediatamente
- No cierra tabs automáticamente
- Modo tradicional

### Modo Scheduling (nuevo)
Solo añade la columna `fecha_hora_inicio`:

```csv
Game,url,fecha_hora_inicio
Partido,https://...,2026-02-10 20:00
```
- Abre tabs en ventana de tracking
- Cierra tabs cuando termina ventana
- Modo automático

### Modo Mixto
Puedes mezclar ambos en el mismo CSV:

```csv
Game,url,fecha_hora_inicio
Partido con horario,https://...,2026-02-10 20:00
Partido sin horario,https://...,
```
- Partido con horario: Modo scheduling
- Partido sin horario: Modo legacy (trackea siempre)

## 📌 Notas Importantes

1. **Formato de fecha**: Usa `YYYY-MM-DD HH:MM` o `DD/MM/YYYY HH:MM`
2. **Zona horaria**: Usa hora local de tu sistema
3. **Reload interval**: Por defecto revisa cada 5 ciclos (~5 minutos)
4. **Sin tabs activas**: El script espera pacientemente hasta que llegue la hora
5. **Chrome no se cierra**: Mantiene una tab dummy si no hay partidos

## 🐛 Troubleshooting

**P: El script no abre ninguna tab**
- R: Normal si todos los partidos son futuros. Revisa el log para ver "Próximos partidos a trackear"

**P: El script cerró una tab muy pronto**
- R: Ajusta `--ventana-despues` a más minutos (ej: 180 para 3 horas)

**P: El script abre tabs muy tarde (ya empezó el partido)**
- R: Ajusta `--ventana-antes` a más minutos (ej: 15)

**P: No detecta nuevos partidos añadidos al CSV**
- R: Espera hasta el próximo `--reload-interval` (máximo 5 minutos por defecto)

**P: Error "formato de fecha inválido"**
- R: Usa formato `YYYY-MM-DD HH:MM` (ej: `2026-02-10 20:00`)

## 📞 Soporte

Para más detalles, consulta:
- **`SCHEDULING.md`**: Documentación completa
- **`test_scheduling.py`**: Ejemplos de código
- **Logs del script**: `logs/scraper_YYYYMMDD_HHMMSS.log`

---

## ✨ Esto es Exactamente lo que Pediste

> "Es posible ir más allá Y que Ejecute el scrip Y se quede todo el día Corriendo Y reclavando datos y que cuando llegue el momento de iniciarse un partido Lo empiece a traquear? Es decir yo el principio del día anoto Todos los partidos en el fichero games.csv Con la fecha y hora de comienzo del partido y cuando llega Ese momento empieza a registrar datos no antes ni después"

✅ **Implementado completamente**. Ahora puedes:
- Dejar el script corriendo todo el día ✅
- Anotar todos los partidos con horarios en games.csv ✅
- El script trackea solo cuando llega la hora ✅
- No trackea antes ni después de la ventana ✅
- Puedes recopilar semanas de datos sin supervisión ✅

**¡Disfruta del sistema automatizado!** 🎉
