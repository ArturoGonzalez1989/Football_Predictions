# Betfair Scraper - Sistema Automático de Captura de Cuotas y Estadísticas

**Proyecto**: Captura de cuotas y estadísticas Opta de partidos de fútbol en tiempo real desde Betfair Exchange.

**Status**: ✅ Producción - 6 Scripts Orquestados

Sistema automático que busca partidos, captura cuotas, extrae estadísticas y valida los datos **sin intervención manual**.

---

## 📋 Tabla de Contenidos

1. [Descripción](#descripción)
2. [Uso Rápido](#uso-rápido)
3. [Estructura del Proyecto](#estructura-del-proyecto)
4. [Scripts Disponibles](#scripts-disponibles)
5. [Documentación](#documentación)

---

## 🎯 Descripción

Sistema que:
- **Busca** partidos en Betfair Exchange
- **Captura** cuotas Match Odds, Over/Under, Resultado Correcto
- **Extrae** estadísticas Opta (xG, pases, tiros, etc.)
- **Valida** que datos se capturen correctamente
- **Reporta** estado del sistema

Funciona **24/7 automáticamente** mediante 6 scripts orquestados.

---

## 🚀 Uso Rápido

### Opción 1: RECOMENDADA - Ejecutar Todo con Un Comando

```bash
cd betfair_scraper
python supervisor_workflow.py
```

Ejecuta automáticamente los 6 PASOS y reporta el estado.

### Opción 2: Con el Agente Supervisor

Ver: [MANUAL_DE_USUARIO.md](MANUAL_DE_USUARIO.md)

### Opción 3: Ejecutar Script Individual

```bash
python start_scraper.py       # PASO 1: Control del scraper
python find_matches.py        # PASO 2: Búsqueda de partidos
python clean_games.py         # PASO 3: Limpieza
python check_urls.py          # PASO 4: Verificación de URLs
python generate_report.py     # PASO 5: Generación de reportes
python validate_stats.py      # PASO 6: Validación de estadísticas
```

---

## 📁 Estructura del Proyecto

```
betfair_scraper/
├── main.py                          # Scraper principal (Selenium)
├── config.py                        # Configuración
├── requirements.txt                 # Dependencias
│
├── SCRIPTS DE SUPERVISOR (6 PASOS)
├── start_scraper.py                 # PASO 1: Control del scraper
├── find_matches.py                  # PASO 2: Búsqueda de partidos
├── clean_games.py                   # PASO 3: Limpieza de partidos
├── check_urls.py                    # PASO 4: Verificación de URLs
├── generate_report.py               # PASO 5: Generación de reportes
├── validate_stats.py                # PASO 6: Validación de estadísticas (NUEVO)
│
├── supervisor_workflow.py           # MAESTRO: Ejecuta 6 PASOS automáticamente
│
├── DATOS Y LOGS
├── games.csv                        # Partidos a trackear
├── data/                            # CSVs capturados con datos
└── logs/                            # Logs del sistema
│
└── DOCUMENTACIÓN
    ├── README.md                    # Este archivo
    ├── MANUAL_DE_USUARIO.md         # Guía de uso (RECOMENDADO)
    ├── SUPERVISOR_WORKFLOW_README.md
    ├── VALIDATE_STATS_README.md
    ├── CLEAN_GAMES_README.md
    ├── FIND_MATCHES_README.md
    └── ARQUITECTURA_FINAL.txt
```

## 🔧 Scripts Disponibles

### PASO 1: start_scraper.py
**Responsabilidad**: ¿Está main.py corriendo?
- Verifica si el scraper está en ejecución
- Si no → Lo arranca automáticamente
- Si sí → Verifica su salud

### PASO 2: find_matches.py
**Responsabilidad**: ¿Hay nuevos partidos en Betfair?
- Accede a Betfair y extrae todos los partidos
- Añade solo nuevos a games.csv

### PASO 3: clean_games.py
**Responsabilidad**: ¿Hay partidos que terminaron?
- Elimina partidos antiguos automáticamente
- Mantiene games.csv limpio

### PASO 4: check_urls.py
**Responsabilidad**: ¿Hay errores 404?
- Busca URLs inválidas en logs
- Elimina partidos problemáticos

### PASO 5: generate_report.py
**Responsabilidad**: ¿Cuál es el estado del sistema?
- Analiza games.csv y datos capturados
- Genera informe consolidado

### PASO 6: validate_stats.py ⭐ NUEVO
**Responsabilidad**: ¿Se capturan las estadísticas disponibles?
- Detecta automáticamente "brecha de datos"
- Alerta si hay estadísticas no capturadas

### MAESTRO: supervisor_workflow.py
Ejecuta los 6 PASOS automáticamente y reporta resultados.

---

## 📊 Archivos Clave

**games.csv** - Partidos a trackear
```csv
Game,url,fecha_hora_inicio
Real Madrid - Barcelona,https://www.betfair.es/.../apuestas-12345,2026-02-11 20:00
```

**data/partido_*.csv** - Datos capturados (133 columnas con cuotas y estadísticas)

**logs/** - Logs del sistema y reportes

---

## 📖 Documentación

**IMPORTANTE**: Lee [MANUAL_DE_USUARIO.md](MANUAL_DE_USUARIO.md) para instrucciones completas.

Documentación por tema:
- **MANUAL_DE_USUARIO.md** - Guía completa (RECOMENDADO)
- **SUPERVISOR_WORKFLOW_README.md** - Documentación técnica del workflow
- **VALIDATE_STATS_README.md** - Validación de estadísticas
- **CLEAN_GAMES_README.md** - Limpieza de partidos
- **FIND_MATCHES_README.md** - Búsqueda de partidos
- **ARQUITECTURA_FINAL.txt** - Diagrama visual

---

## ✅ Estado del Sistema

Ejecuta para verificar estado actual:

```bash
python supervisor_workflow.py
```

---

## 🚀 Próximos Pasos

1. Lee: [MANUAL_DE_USUARIO.md](MANUAL_DE_USUARIO.md)
2. Ejecuta: `python supervisor_workflow.py`
3. Si hay problemas, revisa los logs en `logs/`

---

**Status**: ✅ Producción - 6 Scripts Orquestados

**Última actualización**: 11 de febrero de 2026
