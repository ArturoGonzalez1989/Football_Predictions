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
python scripts/start_scraper.py       # PASO 1: Control del scraper
python scripts/find_matches.py        # PASO 2: Búsqueda de partidos
python scripts/clean_games.py         # PASO 3: Limpieza
python scripts/check_urls.py          # PASO 4: Verificación de URLs
python scripts/generate_report.py     # PASO 5: Generación de reportes
python scripts/validate_stats.py      # PASO 6: Validación de estadísticas
```

---

## 📁 Estructura del Proyecto

```
betfair_scraper/
│
├── CORE (Scraper Principal)
│   ├── main.py                      # Scraper principal (Selenium) - 125 KB
│   ├── config.py                    # Configuración global
│   ├── __init__.py                  # Inicialización módulo
│   └── supervisor_config.json       # Config del supervisor
│
├── SCRIPTS DE SUPERVISOR (Organizados)
└── scripts/
    ├── start_scraper.py             # PASO 1: Control del scraper (6.6 KB)
    ├── find_matches.py              # PASO 2: Búsqueda de partidos (9.2 KB)
    ├── clean_games.py               # PASO 3: Limpieza de partidos (2.8 KB)
    ├── check_urls.py                # PASO 4: Verificación de URLs (5.8 KB)
    ├── generate_report.py           # PASO 5: Generación de reportes (9.3 KB)
    ├── validate_stats.py            # PASO 6: Validación de estadísticas (8.8 KB)
    └── README.md                    # Documentación de scripts
│
├── MAESTRO (Orquestación)
├── supervisor_workflow.py           # Ejecuta 6 PASOS automáticamente (5.7 KB)
│
├── DATOS Y LOGS (Vivos - No editar manualmente)
├── games.csv                        # Partidos a trackear
├── data/                            # CSVs capturados con datos (53+ archivos)
└── logs/                            # Logs y reportes del sistema
│
├── DEPENDENCIAS
├── requirements.txt                 # Dependencias Python
└── requirements_supervisor.txt      # Dependencias adicionales
│
└── DOCUMENTACIÓN
    ├── README.md                    # Este archivo
    ├── MANUAL_DE_USUARIO.md         # Guía de uso (RECOMENDADO)
    ├── INDEX.md                     # Índice y referencias rápidas
    ├── scripts/README.md            # Documentación de scripts
    ├── SUPERVISOR_WORKFLOW_README.md
    ├── VALIDATE_STATS_README.md
    ├── CLEAN_GAMES_README.md
    ├── FIND_MATCHES_README.md
    ├── SUPERVISOR_ORQUESTADOR.md
    └── ARQUITECTURA_FINAL.txt
```

**Total de código útil**: ~48 KB en scripts (distribuido en 7 archivos)
**Total de código core**: ~130 KB (main.py + config.py)
**Total de datos preservados**: 53+ CSVs + logs históricos

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
