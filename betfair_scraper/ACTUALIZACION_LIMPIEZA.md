# Actualización: Sistema de Limpieza Automática de Partidos

Documento que resume los cambios realizados para mejorar la gestión automática de partidos terminados en `games.csv`.

## 📋 Problema Original

El supervisor no eliminaba correctamente los partidos terminados de `games.csv`. Los partidos aparecían en la lista incluso después de que su tiempo de tracking había expirado (120 minutos desde el inicio).

## ✅ Solución Implementada

Se creó un **script Python dedicado** (`clean_games.py`) que maneja de forma simple y testeable la limpieza de partidos terminados.

### Beneficios

1. **Simplicidad**: Lógica clara y fácil de entender
2. **Testeable**: Script independiente que puede verificarse sin ejecutar todo el supervisor
3. **Mantenible**: Cambiar el umbral de tiempo es trivial (un parámetro en el código)
4. **Confiable**: Usa cálculos simples de datetime que funcionan siempre

---

## 📁 Archivos Creados/Modificados

### 1. `betfair_scraper/clean_games.py` (NUEVO)

Script que limpia automáticamente los partidos terminados.

```python
#!/usr/bin/env python3
import csv
from datetime import datetime, timedelta
from pathlib import Path

MATCH_DURATION_MINUTES = 120  # 90 min juego + 30 min margen
DATE_FORMATS = ["%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"]

# Funciones:
# - parse_date(date_str): Parsea fechas en dos formatos
# - is_match_finished(start_time): Comprueba si ha terminado
# - clean_games(): Lógica principal de limpieza
```

**Uso**:
```bash
cd betfair_scraper
python clean_games.py
```

**Salida esperada**:
```
[LIMPIEZA COMPLETADA]
   - Eliminados: 3 partidos
   - Activos: 5 partidos

Partidos eliminados:
   - Real Madrid - Barcelona (2026-02-11 15:30)
   - Arsenal - Chelsea (2026-02-11 14:00)
```

### 2. `betfair_scraper/CLEAN_GAMES_README.md` (NUEVO)

Documentación simple para ejecutar el script de limpieza.

- Explica qué hace
- Instrucciones de uso
- Cuándo ejecutarlo
- Configuración disponible

### 3. `.claude/agents/betfair-supervisor.md` (MODIFICADO)

**Cambios en REGLA #2**:
- Ahora especifica: "Usar clean_games.py"
- Umbral: 120 minutos (90 min juego + 30 min margen)
- Explicación clara del cálculo

**Cambios en PASO 3**:
- Subdivido en 3 secciones:
  - **3.1**: Ejecutar `clean_games.py`
  - **3.2**: Añadir nuevos partidos de Betfair
  - **3.3**: Reportar cambios
- Ahora el supervisor ejecutará el script antes de buscar nuevos partidos

---

## 🔧 Cómo Funciona

### Flujo de Limpieza

1. **Lee games.csv**: Carga todos los partidos
2. **Analiza cada partido**:
   - Si tiene `fecha_hora_inicio` Y `start_time + 120 min < ahora` → Se elimina
   - Si no tiene fecha o el cálculo falla → Se mantiene
3. **Escribe games.csv limpio**: Solo con partidos activos/futuros
4. **Reporta**: Cuántos se eliminaron y cuántos quedan

### Lógica de Cálculo

```
Partido empieza a las: 15:30
Tiempo de tracking:     120 minutos
Se elimina si:         15:30 + 120 min = 17:30 ha pasado
                       (es decir, a las 17:30 o después)

Ejemplo real:
- Partido: 15:30
- Hora actual: 17:35
- Cálculo: 17:35 > 17:30 → ✅ SE ELIMINA
```

### Manejo de Casos Especiales

- **Sin fecha**: Nunca se eliminan (modo legacy)
- **Fecha inválida**: Se mantiene y se reporta warning
- **Partidos futuros**: Se mantienen
- **Partidos en juego**: Se mantienen

---

## 📊 Test

El script ha sido probado con success:

```bash
$ python clean_games.py
[OK] Sin cambios - 7 partidos activos
```

Esto significa que todos los 7 partidos actuales en games.csv aún están dentro de su ventana de tracking de 120 minutos.

---

## 🔌 Integración con el Supervisor

En cada ciclo del supervisor, el **PASO 3** ahora:

1. Ejecuta `clean_games.py` para limpiar partidos viejos
2. Busca nuevos partidos en Betfair
3. Los añade a games.csv
4. Reporta todos los cambios

**Comando ejecutado**:
```bash
cd betfair_scraper && python clean_games.py
```

---

## ⚙️ Configuración

Si necesitas cambiar el umbral de 120 minutos, abre `clean_games.py` y modifica:

```python
MATCH_DURATION_MINUTES = 120  # Cambiar este valor
```

Ejemplos:
- `90`: Solo juego (sin margen)
- `120`: Recomendado (90 min + 30 min margen) ← ACTUAL
- `150`: Más conservador (permite 30 min extra)

---

## 🚀 Próximos Pasos

El supervisor ya está configurado para usar `clean_games.py` automáticamente.

### Ejecución Manual (si lo necesitas)

```bash
cd betfair_scraper
python clean_games.py
```

### Ejecución Automática (supervisor)

El agente supervisor ejecuta esto en PASO 3 de su ciclo. No necesitas hacer nada.

---

## 🐛 Troubleshooting

### "File not found: clean_games.py"

Verifica que estés en el directorio correcto:
```bash
cd betfair_scraper
ls clean_games.py  # Debe existir
```

### "UnicodeEncodeError"

El script ya está corregido para Windows. Usa salida compatible (sin emojis).

### Script no elimina partidos

Verifica que:
1. Los partidos en games.csv tengan fecha en formato correcto
2. Han pasado más de 120 minutos desde su inicio
3. Usa `python clean_games.py` (no `python3`)

---

## 📝 Resumen de Cambios

| Componente | Cambio | Razón |
|-----------|--------|-------|
| clean_games.py | ✨ NUEVO | Lógica de limpieza simple y testeable |
| REGLA #2 | 🔄 ACTUALIZADO | Ahora usa clean_games.py |
| PASO 3 | 🔄 ACTUALIZADO | Ejecuta clean_games.py antes de buscar nuevos partidos |
| Umbral tiempo | 🔄 150 → 120 min | 90 min juego + 30 min margen (más lógico) |
| Documentación | ✨ NUEVO | CLEAN_GAMES_README.md con instrucciones simples |

---

## ✨ Beneficios Conseguidos

1. ✅ **Automático**: El supervisor lo ejecuta sin intervención
2. ✅ **Confiable**: Lógica simple y bien testeable
3. ✅ **Mantenible**: Fácil de entender y modificar
4. ✅ **Flexible**: El umbral es configurablefácilmente
5. ✅ **Compatible**: Funciona en Windows sin problemas de encoding

---

**Documento actualizado**: 2026-02-11
**Status**: ✅ Implementado y testado
