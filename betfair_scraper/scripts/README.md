# Scripts del Supervisor - 6 PASOS Orquestados

**Ubicación**: `betfair_scraper/scripts/`

Carpeta que contiene los 6 scripts de supervisor que se ejecutan automáticamente.

---

## 📋 Scripts Disponibles

### PASO 1: start_scraper.py (6.6 KB)
**Responsabilidad**: ¿Está el scraper main.py corriendo?

Verifica si el proceso está en ejecución:
- Si NO está → Lo arranca automáticamente
- Si SÍ está → Verifica su salud (actividad reciente)
- Si hay problemas → Lo reinicia

```bash
python scripts/start_scraper.py
```

---

### PASO 2: find_matches.py (9.2 KB)
**Responsabilidad**: ¿Hay nuevos partidos en Betfair?

Busca en Betfair y añade nuevos partidos:
- Accede a https://www.betfair.es/exchange/plus/inplay
- Extrae TODOS los partidos de fútbol (in-play + próximos)
- Compara con games.csv
- Añade solo nuevos (evita duplicados)

```bash
python scripts/find_matches.py
```

---

### PASO 3: clean_games.py (2.8 KB)
**Responsabilidad**: ¿Hay partidos que terminaron?

Limpia partidos terminados:
- Lee games.csv
- Elimina partidos donde: `inicio + 120 minutos < ahora`
- Mantiene games.csv limpio y actualizado

```bash
python scripts/clean_games.py
```

---

### PASO 4: check_urls.py (5.8 KB)
**Responsabilidad**: ¿Hay errores 404?

Busca URLs inválidas:
- Lee logs del scraper
- Busca errores 404 y URLs problemáticas
- Identifica partidos afectados
- Los elimina automáticamente de games.csv

```bash
python scripts/check_urls.py
```

---

### PASO 5: generate_report.py (9.3 KB)
**Responsabilidad**: ¿Cuál es el estado general del sistema?

Genera informe consolidado:
- Analiza games.csv (total, activos, futuros)
- Verifica datos capturados (CSVs, filas, cuotas %, stats %)
- Analiza logs (errores, warnings, actividad)
- Genera informe con conclusiones
- Guarda en logs/report_TIMESTAMP.txt

```bash
python scripts/generate_report.py
```

---

### PASO 6: validate_stats.py (8.8 KB) ⭐ NUEVO
**Responsabilidad**: ¿Se capturan las estadísticas disponibles?

Valida y detecta "brecha de datos":
- Accede a partidos activos en Betfair
- Extrae estadísticas VISIBLES en la página
- Compara con estadísticas CAPTURADAS en CSVs
- Reporta qué falta (brecha de datos)
- Alerta si hay problemas

```bash
python scripts/validate_stats.py
```

**Salida posible:**
```
[ALERTA] Brecha de datos detectada:
  * XG: No capturado en 1 partido(s)
  * PASES: No capturado en 1 partido(s)

[ACCION RECOMENDADA]
  1. Revisar selectores CSS en main.py
  2. Actualizar selectores si Betfair cambió HTML
  3. Ejecutar validate_stats.py nuevamente para confirmar corrección
```

---

## 🎯 Script Maestro: supervisor_workflow.py (5.7 KB)

**Responsabilidad**: Ejecutar los 6 PASOS automáticamente

Orquesta la ejecución en orden:
1. PASO 1: start_scraper.py
2. PASO 2: find_matches.py
3. PASO 3: clean_games.py
4. PASO 4: check_urls.py
5. PASO 5: generate_report.py
6. PASO 6: validate_stats.py

Valida que cada PASO completó exitosamente y genera resumen final.

```bash
python supervisor_workflow.py
```

O desde la raíz:
```bash
python scripts/supervisor_workflow.py
```

---

## 📊 Total de Scripts

```
Scripts en /scripts/: 7
├── PASO 1: start_scraper.py        (6.6 KB)
├── PASO 2: find_matches.py         (9.2 KB)
├── PASO 3: clean_games.py          (2.8 KB)
├── PASO 4: check_urls.py           (5.8 KB)
├── PASO 5: generate_report.py      (9.3 KB)
├── PASO 6: validate_stats.py       (8.8 KB)
└── MAESTRO: supervisor_workflow.py (5.7 KB)

Total: 48 KB de código supervisor
```

---

## 🚀 Cómo Usar

### Opción 1: RECOMENDADA - Ejecutar Todo
```bash
cd betfair_scraper
python scripts/supervisor_workflow.py
```

Ejecuta los 6 PASOS automáticamente y reporta estado.

### Opción 2: Ejecutar Paso Individual
```bash
# PASO específico
python scripts/start_scraper.py
python scripts/find_matches.py
python scripts/clean_games.py
python scripts/check_urls.py
python scripts/generate_report.py
python scripts/validate_stats.py
```

---

## 📁 Estructura General del Proyecto

```
betfair_scraper/
├── CORE (NO MOVER)
│   ├── main.py              # Scraper principal
│   ├── config.py            # Configuración
│   ├── __init__.py          # Inicialización
│   ├── requirements.txt      # Dependencias
│   └── requirements_supervisor.txt
│
├── SUPERVISOR SCRIPTS (Organizado)
└── scripts/
    ├── README.md (este archivo)
    ├── start_scraper.py     (PASO 1)
    ├── find_matches.py      (PASO 2)
    ├── clean_games.py       (PASO 3)
    ├── check_urls.py        (PASO 4)
    ├── generate_report.py   (PASO 5)
    ├── validate_stats.py    (PASO 6)
    └── supervisor_workflow.py (MAESTRO)

DATOS (Preservados)
├── games.csv                # Partidos
├── data/                    # CSVs capturados
└── logs/                    # Reportes y logs
```

---

## 💡 Notas

- ✅ Todos los scripts son independientes
- ✅ Cada script puede ejecutarse manualmente
- ✅ El supervisor_workflow.py los orquesta automáticamente
- ✅ Los datos NO se pierden si se elimina esta carpeta (están en data/ y logs/)
- ✅ El core (main.py, config.py) permanece en la raíz

---

## 📚 Documentación

Para más información ver:
- `README.md` - Visión general del proyecto
- `MANUAL_DE_USUARIO.md` - Guía completa de uso
- `INDEX.md` - Índice de referencias

---

**Última actualización**: 11 de febrero de 2026
