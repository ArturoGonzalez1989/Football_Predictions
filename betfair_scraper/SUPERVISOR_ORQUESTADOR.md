# Supervisor como Orquestador Puro

Documento que explica la arquitectura final donde el supervisor solo ORQUESTA scripts Python dedicados.

## 🎯 Filosofía

**El supervisor = Orquestador de flujo**
- Solo ejecuta scripts
- Lee outputs
- Toma decisiones basadas en resultados
- NO implementa lógica de negocio

## 📊 Estructura de 5 Pasos

```
PASO 1: start_scraper.py
  ↓ (Si no está corriendo → lo arranca)
PASO 2: find_matches.py
  ↓ (Busca nuevos partidos)
PASO 3: clean_games.py
  ↓ (Elimina partidos viejos)
PASO 4: check_urls.py
  ↓ (Busca y elimina 404s)
PASO 5: generate_report.py
  ↓ (Analiza todo y genera informe)
INFORME FINAL
  ↓
TOMA DE DECISIONES (si hay problemas)
```

## 📁 Los 5 Scripts

### 1. `start_scraper.py` (Líneas: 126)

**Responsabilidad**: Verificar, arrancar y reiniciar main.py

**Entrada**: Sistema (procesos, logs)
**Salida**: Mensajes [OK]/[ERROR]

**Lógica**:
```
Si main.py no está corriendo:
  → Arrancarlo

Si está corriendo:
  → Verificar log reciente
  → Si sin actividad > 5 min: REINICIAR
  → Si muchos errores: REINICIAR
  → Sino: Continuar

Reportar: Estado actual
```

**Test**:
```bash
$ python start_scraper.py
[OK] Scraper está corriendo (PID: 23656)
```

---

### 2. `find_matches.py` (Líneas: 280)

**Responsabilidad**: Buscar en Betfair y añadir nuevos partidos a games.csv

**Entrada**: https://www.betfair.es/exchange/plus/inplay
**Salida**: games.csv actualizado + mensajes

**Lógica**:
```
1. Abre Chrome (invisible)
2. Accede a Betfair
3. Espera carga dinámica (5s)
4. Extrae TODOS los partidos de fútbol
5. Lee games.csv actual
6. Compara: solo añade nuevos
7. Guarda CSV
8. Reporta: Cuántos encontró/añadió
```

**Test**:
```bash
$ python find_matches.py
[OK] Encontrados 12 partidos / Sin partidos nuevos
```

---

### 3. `clean_games.py` (Líneas: 100)

**Responsabilidad**: Eliminar partidos que ya terminaron (inicio + 120 min < ahora)

**Entrada**: games.csv
**Salida**: games.csv limpio + mensajes

**Lógica**:
```
Para cada partido en games.csv:
  Si inicio + 120 min < ahora:
    → Eliminar
  Sino:
    → Mantener

Reportar: Cuántos eliminó
```

**Test**:
```bash
$ python clean_games.py
[OK] Sin cambios - 7 partidos activos
```

---

### 4. `check_urls.py` (Líneas: 170)

**Responsabilidad**: Buscar errores 404 en logs y eliminar esos partidos

**Entrada**: scraper_*.log + games.csv
**Salida**: games.csv actualizado + mensajes

**Lógica**:
```
1. Lee log más reciente
2. Busca patrones de error:
   - 404, "no encontrado", "not found"
   - "URL inválida", "no such element"
3. Extrae IDs de partidos afectados
4. Elimina esos partidos de games.csv
5. Reporta: Cuántos eliminó
```

**Test**:
```bash
$ python check_urls.py
[OK] Sin errores 404 detectados
```

---

### 5. `generate_report.py` (Líneas: 310)

**Responsabilidad**: Generar informe completo analizando todo el sistema

**Entrada**: games.csv + data/*.csv + scraper_*.log
**Salida**: Informe + archivo report_*.txt

**Lógica**:
```
1. Analiza games.csv
   → Total, activos, futuros
2. Analiza data files
   → CSVs, filas, cuotas, stats
3. Analiza logs
   → Errores, warnings, actividad
4. Genera conclusiones
5. Imprime informe
6. Guarda en logs/report_TIMESTAMP.txt
```

**Ejemplo de salida**:
```
INFORME DE SUPERVISION

1. PARTIDOS CONFIGURADOS
   Total: 5 partidos
   Activos: 2
   Futuros: 3

2. DATOS CAPTURADOS
   CSVs: 53
   Filas: 216
   Cuotas: 84.3%
   Stats: 32.4%

3. SALUD DEL SCRAPER
   Errores: 0
   Warnings: 8
   Actividad: Activo

4. ESTADO GENERAL
   STATUS: [OK] Sistema funcionando correctamente
```

---

## 🔄 Flujo de Ejecución Completo

```
Supervisor ejecuta PASO 1:
├─ start_scraper.py
│  └─ [OK] Scraper corriendo
├─ Continúa a PASO 2

Supervisor ejecuta PASO 2:
├─ find_matches.py
│  └─ [OK] Encontrados 5 partidos
├─ Continúa a PASO 3

Supervisor ejecuta PASO 3:
├─ clean_games.py
│  └─ [OK] Eliminados 2 partidos viejos
├─ Continúa a PASO 4

Supervisor ejecuta PASO 4:
├─ check_urls.py
│  └─ [OK] Sin errores 404
├─ Continúa a PASO 5

Supervisor ejecuta PASO 5:
├─ generate_report.py
│  ├─ [Informe analizado]
│  └─ [OK] Sistema funcionando
├─ Lee informe

Supervisor toma decisiones:
└─ "Todo bien" → Continuar
   O
   "Problema crítico" → Reportar al usuario
```

---

## 📋 Ventajas de esta Arquitectura

| Aspecto | Beneficio |
|---------|-----------|
| **Simplicidad** | El supervisor es un orquestador, no implementa lógica |
| **Testabilidad** | Cada script se prueba independientemente |
| **Mantenimiento** | Cambios localizados en cada script |
| **Debugging** | Errores asociados a su script específico |
| **Reutilización** | Scripts ejecutables manualmente o con scheduler |
| **Extensibilidad** | Fácil añadir nuevos scripts |
| **Responsabilidad** | Cada script tiene UNA responsabilidad |
| **Robustez** | Si un script falla, el siguiente puede continuar |

---

## 🚀 Cómo Usar

### Manual (ejecutar scripts directamente)

```bash
cd betfair_scraper

# Ejecutar todos en orden
python start_scraper.py && python find_matches.py && python clean_games.py && python check_urls.py && python generate_report.py
```

### Automático (supervisor orquesta)

El supervisor ejecuta automáticamente todos los scripts en cada ciclo. El usuario solo ve el informe final.

### Con Windows Task Scheduler

Programar ejecución de cada script:
```
Programa: python.exe
Argumentos: C:\...\betfair_scraper\<script>.py
Repetir cada: 30-60 minutos
```

---

## 🔧 Configuración

Cada script tiene parámetros configurables al inicio:

**start_scraper.py**:
```python
MIN_ACTIVITY_THRESHOLD = 5 * 60  # 5 minutos sin actividad
```

**clean_games.py**:
```python
MATCH_DURATION_MINUTES = 120  # 120 min = 90 juego + 30 margen
```

**find_matches.py**:
```python
HEADLESS = True   # False para ver búsqueda en tiempo real
TIMEOUT = 10      # Segundos para esperar elementos
```

---

## 📊 Responsabilidades Claras

```
start_scraper.py:    ¿Está main.py corriendo?
find_matches.py:     ¿Hay nuevos partidos en Betfair?
clean_games.py:      ¿Hay partidos viejos que eliminar?
check_urls.py:       ¿Hay URLs con error 404?
generate_report.py:  ¿Cuál es el estado general del sistema?

SUPERVISOR:          Ejecuta en orden, lee resultados, reporta
```

---

## ✨ Beneficios Conseguidos

1. ✅ **Supervisor es un orquestador puro**
   - No implementa lógica de negocio
   - Solo ejecuta scripts y lee outputs
   - Fácil de entender y mantener

2. ✅ **Scripts independientes**
   - Cada uno tiene una responsabilidad clara
   - Se prueban sin ejecutar todo el supervisor
   - Se ejecutan manualmente cuando sea necesario

3. ✅ **Sistema modular**
   - Añadir nuevo script = Añadir nuevo PASO
   - Cambios localizados = Menos riesgo

4. ✅ **Información clara**
   - Cada script reporta qué hizo
   - El informe final consolida todo
   - El usuario solo ve conclusiones

5. ✅ **Preparado para el futuro**
   - Fácil cambiar un script sin afectar otros
   - Fácil mover scripts a diferentes máquinas
   - Fácil programar ejecución independiente

---

## 📚 Documentación de Cada Script

- [start_scraper.py](https://tu-url) - Control del scraper
- [find_matches.py](FIND_MATCHES_README.md) - Búsqueda de partidos
- [clean_games.py](CLEAN_GAMES_README.md) - Limpieza de partidos
- [check_urls.py](https://tu-url) - Verificación de URLs
- [generate_report.py](https://tu-url) - Generación de reportes

---

## 🎯 Próximos Scripts Posibles

Siguiendo este patrón:

```
predict_matches.py    → Predice cuotas/resultados
optimize_resources.py → Optimiza uso de memoria/CPU
backup_data.py        → Respalda datos capturados
export_data.py        → Exporta a JSON/Excel/etc
validate_stats.py     → Valida consistencia de datos
```

Cada uno seguiría el patrón: entrada → proceso → salida → informe.

---

**Arquitectura**: Supervisor como Orquestador Puro
**Status**: ✅ IMPLEMENTADA Y PROBADA
**Fecha**: 2026-02-11
**Scripts**: 5 (+ main.py del scraper)
**Líneas de código**: ~1000 (distribuidas en 5 scripts)
**Complejidad del supervisor**: BAJA (solo orquesta)
