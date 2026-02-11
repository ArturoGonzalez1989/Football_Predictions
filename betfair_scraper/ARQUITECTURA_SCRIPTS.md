# Arquitectura de Scripts - Separación de Responsabilidades

Documento que explica la nueva arquitectura donde el supervisor es un orquestador simple que ejecuta scripts Python dedicados.

## 🎯 Principio de Diseño

**Un script = Una responsabilidad**

En lugar de que el supervisor implemente toda la lógica:
```
❌ Antes: Supervisor (complejidad alta)
├── Arranca scraper
├── Busca en Betfair
├── Limpia partidos viejos
├── Verifica URLs 404
└── Genera reportes

✅ Ahora: Supervisor (orquestador simple)
├── PASO 1: Verifica scraper (inline - rápido)
├── PASO 2: Ejecuta find_matches.py
├── PASO 3: Ejecuta clean_games.py
├── PASO 4: Verifica URLs 404 (inline - rápido)
└── PASO 5: Genera reportes (inline)
```

## 📁 Estructura de Scripts

### 1. `clean_games.py` - Limpieza de partidos viejos

**Responsabilidad**: Mantener games.csv limpio removiendo partidos que ya terminaron

**Uso**:
```bash
python clean_games.py
```

**Entrada**: `games.csv`
**Salida**: `games.csv` (actualizado)

**Lógica**:
```
Para cada partido en games.csv:
  Si inicio + 120 min < ahora:
    → Eliminar del CSV
  Sino:
    → Mantener en el CSV

Reportar: Cuántos se eliminaron, cuántos quedan
```

**Configuración**:
```python
MATCH_DURATION_MINUTES = 120  # Cambiar si necesitas otro umbral
```

---

### 2. `find_matches.py` - Búsqueda de partidos en Betfair

**Responsabilidad**: Buscar todos los partidos en vivo y próximos, añadirlos a games.csv

**Uso**:
```bash
python find_matches.py
```

**Entrada**: Betfair exchange + `games.csv` (actual)
**Salida**: `games.csv` (con nuevos partidos)

**Lógica**:
```
1. Abre Chrome (invisible)
2. Accede a https://www.betfair.es/exchange/plus/inplay
3. Espera carga dinámica (5s)
4. Extrae TODOS los partidos de fútbol:
   - Nombre (ej: "Real Madrid - Barcelona")
   - URL (https://www.betfair.es/exchange/plus/es/futbol/...)
   - Hora inicio (extrae de página o aproxima)
5. Lee games.csv actual
6. Compara: Solo añade partidos que NO están
7. Guarda games.csv actualizado
8. Reporta: Cuántos nuevos, total

Deduplicación: Por nombre del partido
```

**Configuración**:
```python
BETFAIR_INPLAY_URL = "https://www.betfair.es/exchange/plus/inplay"
HEADLESS = True   # False para ver la búsqueda en tiempo real
TIMEOUT = 10      # Segundos para esperar elementos
```

**Extracción de hora**:
| Patrón | Formato en Betfair | Resultado |
|--------|-------------------|-----------|
| Próximo | "Comienza en 5'" | Ahora + 5 min |
| Horario fijo | "Hoy 18:30" | Hoy a las 18:30 |
| En vivo | "DESC." o "2-1" | Ahora - 30 min (aproximación) |

---

### 3. `main.py` - Captura de datos

**Responsabilidad**: Capturar cuotas y estadísticas de partidos en games.csv

**Uso**:
```bash
python main.py
```

**Entrada**: `games.csv` (lista de partidos a trackear)
**Salida**: `data/partido_*.csv` (datos capturados)

**Notas**:
- Solo procesa partidos que están en su ventana de tracking (10 min antes, 150 min después de inicio)
- Captura in-real-time cuotas y estadísticas
- Genera un CSV por partido
- El supervisor NO toca este script (es la fuente de datos)

---

## 🔄 Flujo del Supervisor

### Cada ciclo de supervisión (PASO 1 a 5):

```
PASO 1: Verificar/arrancar scraper
  └─→ Directamente en agent (sin script)
      - Chequear si main.py está corriendo
      - Si no, arrancarlo
      - Verificar salud del log

PASO 2: Buscar partidos nuevos en Betfair
  └─→ Ejecuta: python find_matches.py
      - Busca en Betfair
      - Añade nuevos a games.csv
      - Reporta cuántos encontró

PASO 3: Limpiar partidos viejos
  └─→ Ejecuta: python clean_games.py
      - Lee games.csv
      - Elimina partidos con inicio + 120 min < ahora
      - Reporta cuántos eliminó

PASO 4: Verificar URLs 404
  └─→ Directamente en agent (sin script)
      - Busca en scraper.log errores 404
      - Si encuentra, elimina partido de games.csv
      - Reporta eliminaciones

PASO 5: Generar reportes
  └─→ Directamente en agent (sin script)
      - Verifica calidad de datos
      - Analiza logs
      - Genera informe final
```

## 📊 Beneficios de esta Arquitectura

| Aspecto | Ventaja |
|--------|---------|
| **Testabilidad** | Cada script se puede probar independientemente |
| **Mantenimiento** | Si Betfair cambia, solo actualizas find_matches.py |
| **Reutilización** | Puedes ejecutar scripts manualmente o con scheduler |
| **Debugging** | Más fácil encontrar problemas (script específico) |
| **Simplicidad** | El supervisor es solo un orquestador |
| **Rendimiento** | Scripts ligeros + ejecutables en paralelo |
| **Documentación** | Cada script tiene su README |

## 🚀 Cómo Usar

### Manualmente

```bash
# Buscar nuevos partidos
cd betfair_scraper
python find_matches.py

# Limpiar partidos viejos
python clean_games.py

# Ambos (orden correcto)
python find_matches.py && python clean_games.py
```

### Automáticamente (Supervisor)

```bash
# El supervisor ejecuta TODO automáticamente
cd betfair_scraper
python main.py  # Scraper capturando

# En otra terminal:
claude code invoke betfair-supervisor  # Cada X horas
```

### Con Windows Task Scheduler

Para ejecutar los scripts cada X minutos:

```batch
# find_matches.py cada 30 minutos
Programa: python.exe
Argumentos: C:\...\betfair_scraper\find_matches.py

# clean_games.py cada 2 horas
Programa: python.exe
Argumentos: C:\...\betfair_scraper\clean_games.py
```

## 📝 Flujo de Datos

```
Betfair Exchange (web)
         ↓
find_matches.py ← Busca partidos
         ↓
   games.csv ← Añade nuevos
    ↙      ↘
   ↙        ↘
main.py    clean_games.py
(captura)  (limpia viejos)
   ↓           ↓
data/*.csv  games.csv
(datos)     (actualizado)
```

## 🔧 Mantenimiento

### Si Betfair cambia su interfaz

1. Abre `find_matches.py`
2. Cambia selectores CSS en función `extract_football_matches()`
3. Prueba: `python find_matches.py --debug` (verá en tiempo real)
4. El supervisor automáticamente usará la versión nueva

### Si necesitas otro umbral de tiempo

1. Abre `clean_games.py`
2. Cambia: `MATCH_DURATION_MINUTES = 150` (por ejemplo)
3. El supervisor automáticamente usará el nuevo valor

### Si quieres cambiar la URL de búsqueda

1. Abre `find_matches.py`
2. Cambia: `BETFAIR_INPLAY_URL = "nueva_url"`
3. El supervisor automáticamente buscará en la nueva URL

## 📋 Checklist de Validación

Cuando añadas un nuevo script:

- [ ] Script tiene una responsabilidad clara
- [ ] Lee entrada (archivos/web)
- [ ] Procesa (lógica)
- [ ] Escribe salida (archivos)
- [ ] Reporta lo que hizo (print en consola)
- [ ] Maneja errores sin fallar (try/except)
- [ ] Compatible con Windows (encoding, paths)
- [ ] Tiene README con instrucciones
- [ ] Configuración es fácil de cambiar (variables al inicio)
- [ ] Se integra en supervisor (nueva línea en PASO correspondiente)

## 🎯 Próximos Scripts Posibles

Siguiendo este patrón, podrías crear:

```
validate_urls.py
├─ Valida URLs en games.csv
└─ Elimina 404s automáticamente

analyze_matches.py
├─ Analiza patrones en datos capturados
└─ Detecta anomalías

export_data.py
├─ Exporta datos a formatos (JSON, Excel, etc)
└─ Genera reportes automáticos

monitor_performance.py
├─ Monitoriza rendimiento del scraper
└─ Alerta si hay problemas
```

Cada uno seguiría el mismo patrón: responsabilidad única, entrada → proceso → salida.

---

**Documento actualizado**: 2026-02-11
**Status**: ✅ Arquitectura implementada
