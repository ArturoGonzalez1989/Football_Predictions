# Índice de Archivos y Documentación

**Referencia rápida de qué archivo leer para cada necesidad.**

---

## 🎯 ¿Por Dónde Empezar?

**Eres nuevo en el proyecto:**
→ Lee: [README.md](README.md)

**Quieres usar el sistema:**
→ Lee: [MANUAL_DE_USUARIO.md](MANUAL_DE_USUARIO.md) ⭐ RECOMENDADO

**Quieres entender la arquitectura:**
→ Lee: [ARQUITECTURA_FINAL.txt](ARQUITECTURA_FINAL.txt)

**Necesitas resolver un problema:**
→ Ir a: [Resolución de Problemas](#resolución-de-problemas)

---

## 📚 Documentación Principal

| Archivo | Propósito | Cuándo Leer |
|---------|-----------|-----------|
| **README.md** | Visión general del proyecto | Primer contacto |
| **MANUAL_DE_USUARIO.md** ⭐ | Guía completa de uso | Antes de usar el sistema |
| **ARQUITECTURA_FINAL.txt** | Diagrama visual y flujo completo | Para entender cómo funciona |
| **INTEGRACION_PASO_6_COMPLETADA.md** | Resumen de integración PASO 6 | Para entender qué es nuevo |

---

## 🔧 Documentación de Scripts

### Scripts de Supervisor (PASO 1-6)

| Script | Archivo | Propósito |
|--------|---------|-----------|
| **PASO 1** | start_scraper.py | Verificar/arrancar scraper |
| **PASO 2** | [FIND_MATCHES_README.md](FIND_MATCHES_README.md) | Buscar nuevos partidos |
| **PASO 3** | [CLEAN_GAMES_README.md](CLEAN_GAMES_README.md) | Limpiar partidos terminados |
| **PASO 4** | check_urls.py | Verificar URLs 404 |
| **PASO 5** | generate_report.py | Generar reportes |
| **PASO 6** | [VALIDATE_STATS_README.md](VALIDATE_STATS_README.md) ⭐ NUEVO | Validar estadísticas |

### Script Maestro

| Script | Propósito |
|--------|-----------|
| **supervisor_workflow.py** | Ejecuta los 6 PASOS automáticamente |

### Scripts Core

| Script | Propósito |
|--------|-----------|
| **main.py** | Scraper principal (Selenium) |
| **config.py** | Configuración global |

---

## 📊 Datos y Configuración

| Archivo | Descripción |
|---------|-------------|
| **games.csv** | Partidos a trackear (Entrada) |
| **data/** | CSVs con datos capturados (Salida) |
| **logs/** | Logs y reportes del sistema |
| **config.py** | Parámetros del scraper |
| **requirements.txt** | Dependencias Python |

---

## 🚀 Acciones Rápidas

### Quiero Ejecutar Todo de Una Vez
```bash
python supervisor_workflow.py
```
📖 Ver: [MANUAL_DE_USUARIO.md#opción-1-recomendada](MANUAL_DE_USUARIO.md#opción-1-recomendada)

### Quiero Buscar Nuevos Partidos
```bash
python find_matches.py
```
📖 Ver: [FIND_MATCHES_README.md](FIND_MATCHES_README.md)

### Quiero Ver el Estado del Sistema
```bash
python generate_report.py
```
📖 Ver: [MANUAL_DE_USUARIO.md#paso-5-generar-reporte](MANUAL_DE_USUARIO.md#paso-5-generar-reporte)

### Quiero Validar Estadísticas
```bash
python validate_stats.py
```
📖 Ver: [VALIDATE_STATS_README.md](VALIDATE_STATS_README.md)

### Quiero Limpiar Partidos Viejos
```bash
python clean_games.py
```
📖 Ver: [CLEAN_GAMES_README.md](CLEAN_GAMES_README.md)

### Quiero Usar el Agente Supervisor
📖 Ver: [MANUAL_DE_USUARIO.md#uso-automático-con-agente](MANUAL_DE_USUARIO.md#uso-automático-con-agente)

---

## 🔍 Resolución de Problemas

| Problema | Solución |
|----------|----------|
| **No sé por dónde empezar** | [README.md](README.md) |
| **No funciona nada** | [MANUAL_DE_USUARIO.md#resolución-de-problemas](MANUAL_DE_USUARIO.md#resolución-de-problemas) |
| **Error de scraper** | Revisa `logs/scraper_*.log` |
| **No hay partidos encontrados** | `python find_matches.py` |
| **No se capturan estadísticas** | `python validate_stats.py` |
| **Brecha de datos detectada** | [VALIDATE_STATS_README.md](VALIDATE_STATS_README.md) |
| **Scraper está parado** | `python start_scraper.py` |

---

## 📋 Estructura de Directorios Vigentes

```
betfair_scraper/
├── SCRIPTS CORE
├── main.py                          # Scraper (NO EDITAR sin autorización)
├── config.py                        # Configuración
│
├── SCRIPTS DE SUPERVISOR (6 PASOS)
├── start_scraper.py                 # PASO 1
├── find_matches.py                  # PASO 2
├── clean_games.py                   # PASO 3
├── check_urls.py                    # PASO 4
├── generate_report.py               # PASO 5
├── validate_stats.py                # PASO 6 (NUEVO)
│
├── supervisor_workflow.py           # Maestro
│
├── DATOS (Vivos - NUNCA ELIMINAR)
├── games.csv                        # Partidos
├── data/                            # CSVs capturados
└── logs/                            # Logs y reportes
│
├── DOCUMENTACIÓN (Vigente)
├── README.md                        # Visión general
├── MANUAL_DE_USUARIO.md             # Guía de uso ⭐
├── INDEX.md                         # Este archivo
├── SUPERVISOR_WORKFLOW_README.md
├── VALIDATE_STATS_README.md
├── CLEAN_GAMES_README.md
├── FIND_MATCHES_README.md
├── SUPERVISOR_ORQUESTADOR.md
├── PASO_6_VALIDACION.md
└── ARQUITECTURA_FINAL.txt
```

---

## 🔗 Rutas de Navegación

### Ruta del Usuario Final
1. README.md → Entender qué es el proyecto
2. MANUAL_DE_USUARIO.md → Aprender a usarlo
3. Ejecutar: `python supervisor_workflow.py`
4. Si hay problemas: MANUAL_DE_USUARIO.md#resolución

### Ruta del Desarrollador
1. README.md → Visión general
2. ARQUITECTURA_FINAL.txt → Diagrama completo
3. SUPERVISOR_WORKFLOW_README.md → Detalles técnicos
4. Código de scripts específicos

### Ruta de Diagnóstico
1. `python generate_report.py` → Ver estado actual
2. `python validate_stats.py` → Detectar problemas
3. Revisar `logs/` → Mensajes de error
4. MANUAL_DE_USUARIO.md#resolución → Encontrar solución

---

## 🎯 Referencias Rápidas

### Comandos Más Usados

```bash
# Ejecutar todo
python supervisor_workflow.py

# Ver estado del sistema
python generate_report.py

# Buscar nuevos partidos
python find_matches.py

# Validar estadísticas
python validate_stats.py

# Verificar scraper
python start_scraper.py

# Limpiar partidos viejos
python clean_games.py

# Verificar URLs
python check_urls.py
```

### Archivos Más Importantes

**Leer primero:**
- README.md
- MANUAL_DE_USUARIO.md

**Entender arquitectura:**
- ARQUITECTURA_FINAL.txt
- SUPERVISOR_WORKFLOW_README.md

**Resolver problemas:**
- VALIDATE_STATS_README.md
- MANUAL_DE_USUARIO.md#resolución-de-problemas

**Datos vivos (NUNCA TOCAR):**
- games.csv
- data/*
- logs/*

---

## 📞 ¿Dónde Está?

### Configuración del Agente Supervisor
```
.claude/agents/betfair-supervisor.md
```

### Skills del Supervisor
```
.claude/skills/
├── supervisor-report/
├── check-scraper/
├── check-stats/
├── find-matches/
├── check-quality/
└── manage-games/
```

### Documentación del Proyecto
```
INTEGRACION_PASO_6_COMPLETADA.md  (Raíz del proyecto)
```

---

## ✅ Checklist Rápido

**Antes de empezar:**
- [ ] Instalé dependencias: `pip install -r requirements.txt`
- [ ] Leí: README.md
- [ ] Leí: MANUAL_DE_USUARIO.md

**Primer uso:**
- [ ] Ejecuté: `python supervisor_workflow.py`
- [ ] Vi los resultados en pantalla
- [ ] Verifiqué que se crearon archivos en `data/`

**Verificación:**
- [ ] Ejecuté: `python generate_report.py`
- [ ] Leí el informe del estado del sistema
- [ ] Ejecuté: `python validate_stats.py`
- [ ] Revisé si hay "brecha de datos"

---

## 🚀 Próximos Pasos

1. **Si es tu primer uso:**
   - Lee: README.md → MANUAL_DE_USUARIO.md
   - Ejecuta: `python supervisor_workflow.py`

2. **Si tienes un problema:**
   - Ejecuta: `python generate_report.py`
   - Va a: MANUAL_DE_USUARIO.md#resolución-de-problemas
   - Busca tu problema específico

3. **Si quieres automatizar:**
   - Lee: MANUAL_DE_USUARIO.md#uso-automático-con-agente
   - Usa el supervisor agent

4. **Si quieres entender todo:**
   - Lee: ARQUITECTURA_FINAL.txt
   - Lee: SUPERVISOR_WORKFLOW_README.md
   - Revisa el código de los scripts

---

**Última actualización**: 11 de febrero de 2026

**Todos los archivos listados están actualizados y en uso.**
