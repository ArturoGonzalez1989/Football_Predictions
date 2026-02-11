# Supervisor Agent - Documentación Completa

## 🤖 ¿Qué es el Supervisor Agent?

El **Supervisor Agent** es un agente autónomo que monitoriza, gestiona y optimiza el scraper de Betfair sin necesidad de intervención humana.

### Funcionalidades Principales

✅ **Gestión Automática del Scraper**
- Inicia/detiene el scraper automáticamente
- Monitoriza que esté corriendo correctamente
- Reinicia si detecta problemas

✅ **Descubrimiento de Partidos**
- Usa Playwright para buscar partidos en vivo en Betfair
- Añade automáticamente nuevos partidos a `games.csv`
- Mantiene actualizada la lista de partidos a trackear

✅ **Verificación de Calidad**
- Verifica que las cuotas se estén capturando correctamente
- Verifica que las estadísticas Opta estén completas
- Detecta timestamps inválidos o datos corruptos

✅ **Análisis de Logs**
- Analiza logs del scraper en busca de errores
- Identifica errores recurrentes
- Alerta sobre problemas críticos

✅ **Correcciones Automáticas**
- Reinicia el scraper si hay muchos errores
- Limpia procesos Chrome zombies
- Elimina filas corruptas de CSVs

✅ **Informes Automáticos**
- Genera informes periódicos en Markdown
- Incluye métricas de salud, calidad y logs
- Guardados en carpeta `reports/`

✅ **Health Monitoring**
- Monitoriza uso de CPU, RAM y disco
- Cuenta procesos Chrome activos
- Registra hora de última captura exitosa

---

## 📦 Instalación

### 1. Instalar Dependencias

```bash
pip install -r requirements_supervisor.txt
```

### 2. Instalar Navegador Playwright

```bash
playwright install chromium
```

### 3. Verificar Instalación

```bash
python supervisor_agent.py --help
```

---

## 🚀 Uso Rápido

### Inicio Básico

```bash
python supervisor_agent.py
```

El supervisor:
1. ✅ Carga configuración desde `supervisor_config.json`
2. ✅ Inicia el scraper automáticamente
3. ✅ Ejecuta ciclos de supervisión cada 5 minutos
4. ✅ Genera informes cada hora
5. ✅ Aplica correcciones automáticas si es necesario

### Personalizar Comportamiento

Edita `supervisor_config.json` para cambiar:

```json
{
    "AUTO_START_SCRAPER": true,
    "AUTO_DISCOVER_MATCHES": true,
    "AUTO_CORRECT": true,
    "CHECK_INTERVAL": 300,
    "REPORT_INTERVAL": 12
}
```

---

## ⚙️ Configuración Detallada

### Archivo: `supervisor_config.json`

```json
{
    "BASE_DIR": "C:\\Users\\agonz\\OneDrive\\Documents\\Proyectos\\Furbo\\betfair_scraper",
    "SCRAPER_SCRIPT": "main.py",
    "GAMES_CSV": "games.csv",

    "SCRAPER_VENTANA_ANTES": 10,
    "SCRAPER_VENTANA_DESPUES": 150,
    "SCRAPER_CICLO": 60,

    "AUTO_START_SCRAPER": true,
    "STOP_SCRAPER_ON_EXIT": true,
    "AUTO_DISCOVER_MATCHES": true,
    "AUTO_CORRECT": true,

    "CHECK_INTERVAL": 300,
    "REPORT_INTERVAL": 12,

    "BETFAIR_INPLAY_URL": "https://www.betfair.es/sport/football/in-play",
    "HEADLESS_BROWSER": true,

    "MIN_STATS_COVERAGE": 50.0,
    "MAX_NULL_PERCENTAGE": 30.0,
    "MAX_ERROR_COUNT": 50,

    "DEBUG": false
}
```

### Parámetros Importantes

| Parámetro | Descripción | Default |
|-----------|-------------|---------|
| `AUTO_START_SCRAPER` | Iniciar scraper automáticamente | `true` |
| `AUTO_DISCOVER_MATCHES` | Buscar partidos en Betfair y añadirlos | `true` |
| `AUTO_CORRECT` | Aplicar correcciones automáticas | `true` |
| `CHECK_INTERVAL` | Segundos entre ciclos de supervisión | `300` (5 min) |
| `REPORT_INTERVAL` | Ciclos entre informes | `12` (1 hora) |
| `HEADLESS_BROWSER` | Ejecutar Playwright sin GUI | `true` |
| `MIN_STATS_COVERAGE` | % mínimo de stats capturadas | `50.0` |
| `MAX_ERROR_COUNT` | Errores antes de reiniciar | `50` |

---

## 🔄 Ciclo de Supervisión

Cada ciclo (cada 5 minutos por defecto) el supervisor ejecuta:

### 1. Verificar Estado del Scraper
```
¿Está corriendo? → NO → Iniciar
                 → SÍ → Continuar
```

### 2. Descubrir Partidos (si AUTO_DISCOVER_MATCHES=true)
```
Playwright → Betfair → Extraer partidos en vivo → Añadir a games.csv
```

Si se añaden partidos nuevos → Reiniciar scraper para cargarlos

### 3. Health Check
```
- Uso CPU/RAM/Disco
- Procesos Chrome activos
- Última captura exitosa
```

### 4. Verificar Calidad de Datos
```
- Cuotas válidas (1.01 - 1000)
- Stats con cobertura > 50%
- Timestamps válidos
```

### 5. Analizar Logs
```
- Contar errores/warnings
- Identificar errores comunes
- Detectar problemas críticos
```

### 6. Aplicar Correcciones (si AUTO_CORRECT=true)
```
Errores > 50 → Reiniciar scraper
Chrome > 50 procesos → Limpiar y reiniciar
Timestamps inválidos → Limpiar CSV
```

### 7. Generar Informe (cada 12 ciclos = 1 hora)
```
Crear archivo Markdown en reports/ con todas las métricas
```

---

## 📊 Informes Generados

### Ubicación
`reports/supervisor_report_YYYYMMDD_HHMMSS.md`

### Contenido

```markdown
# Informe del Supervisor

**Fecha**: 2026-02-10 15:30:00

---

## Estado del Sistema

- **Scraper**: 🟢 Running
- **CPU**: 45.2%
- **RAM**: 62.8%
- **Disco libre**: 128.5 GB
- **Procesos Chrome**: 12
- **Última captura**: 2026-02-10 15:28:15

## Calidad de Datos

- **Cuotas**: ✓ OK
- **Estadísticas**: ✓ OK
- **Timestamps**: ✓ OK
- **Cobertura stats**: 87.3%
- **Filas totales**: 1247

## Análisis de Logs

- **Errores**: 3
- **Warnings**: 12
- **Capturas exitosas**: 156

### Errores Más Comunes

1. `TimeoutException: Page load timeout` (2 veces)
2. `NoSuchElementException: stats tab not found` (1 vez)

---

*Generado automáticamente por Supervisor Agent*
```

---

## 🎯 Casos de Uso

### Caso 1: Monitorización 24/7

```bash
# Iniciar supervisor
python supervisor_agent.py

# Dejar corriendo en ventana separada
# El supervisor se encarga de TODO automáticamente
```

**Resultado**: Sistema completamente autónomo que:
- Inicia/detiene el scraper según necesidad
- Descubre y añade partidos nuevos
- Corrige problemas automáticamente
- Genera informes cada hora

### Caso 2: Solo Verificación de Calidad

Editar `supervisor_config.json`:
```json
{
    "AUTO_START_SCRAPER": false,
    "AUTO_DISCOVER_MATCHES": false,
    "AUTO_CORRECT": false
}
```

```bash
python supervisor_agent.py
```

**Resultado**: Supervisor pasivo que solo:
- Monitoriza calidad de datos
- Analiza logs
- Genera informes
- **NO modifica nada**

### Caso 3: Modo Debug

Editar `supervisor_config.json`:
```json
{
    "DEBUG": true,
    "HEADLESS_BROWSER": false,
    "CHECK_INTERVAL": 60
}
```

**Resultado**: Supervisor en modo verbose:
- Logs detallados en consola
- Navegador visible (Playwright)
- Ciclos cada minuto (más frecuentes)

---

## 🔍 Logs del Supervisor

### Ubicación
`logs/supervisor_YYYYMMDD_HHMMSS.log`

### Ejemplo de Log

```
2026-02-10 15:30:00 | INFO     | ===============================================
2026-02-10 15:30:00 | INFO     | 🔄 CICLO DE SUPERVISIÓN
2026-02-10 15:30:00 | INFO     | ===============================================
2026-02-10 15:30:01 | INFO     | ✓ Scraper está corriendo (PID: 12345)
2026-02-10 15:30:02 | INFO     | 🔍 Buscando partidos en vivo...
2026-02-10 15:30:08 | INFO     | ✓ Encontrados 5 partidos en vivo:
2026-02-10 15:30:08 | INFO     |    - Real Madrid - Barcelona (en vivo)
2026-02-10 15:30:08 | INFO     |    - Man City - Liverpool (en vivo)
2026-02-10 15:30:09 | INFO     | 📝 Sincronizando partidos con games.csv...
2026-02-10 15:30:09 | INFO     | ➕ Añadido: Real Madrid - Barcelona
2026-02-10 15:30:09 | INFO     | ✓ Añadidos 1 partidos nuevos a games.csv
2026-02-10 15:30:10 | INFO     | Reiniciando scraper para cargar nuevos partidos...
2026-02-10 15:30:10 | INFO     | 🛑 Deteniendo scraper...
2026-02-10 15:30:15 | INFO     | ✓ Scraper detenido correctamente
2026-02-10 15:30:20 | INFO     | 🚀 Iniciando scraper...
2026-02-10 15:30:25 | INFO     | ✓ Scraper iniciado (PID: 12567)
2026-02-10 15:30:26 | INFO     | ❤️ Verificando salud del sistema...
2026-02-10 15:30:27 | INFO     | ========================================
2026-02-10 15:30:27 | INFO     | HEALTH CHECK
2026-02-10 15:30:27 | INFO     | ========================================
2026-02-10 15:30:27 | INFO     | Estado scraper: 🟢 Running
2026-02-10 15:30:27 | INFO     | Uso CPU: 42.3%
2026-02-10 15:30:27 | INFO     | Uso RAM: 58.9%
2026-02-10 15:30:27 | INFO     | Espacio disco: 135.2 GB disponibles
2026-02-10 15:30:27 | INFO     | Procesos Chrome: 8
2026-02-10 15:30:27 | INFO     | Última captura: 2026-02-10 15:29:45
2026-02-10 15:30:27 | INFO     | ========================================
```

---

## 🛠️ Troubleshooting

### Problema 1: "ModuleNotFoundError: No module named 'playwright'"

**Solución**:
```bash
pip install playwright
playwright install chromium
```

### Problema 2: "ModuleNotFoundError: No module named 'psutil'"

**Solución**:
```bash
pip install psutil
```

### Problema 3: Supervisor no encuentra el scraper

**Solución**:
Editar `supervisor_config.json` y ajustar rutas:
```json
{
    "BASE_DIR": "C:\\ruta\\correcta\\al\\proyecto",
    "SCRAPER_SCRIPT": "C:\\ruta\\correcta\\al\\proyecto\\main.py"
}
```

### Problema 4: Playwright no puede acceder a Betfair

**Posibles causas**:
1. Betfair bloqueando bot → Desactivar `AUTO_DISCOVER_MATCHES`
2. Sin conexión a internet → Verificar red
3. URL de Betfair cambió → Actualizar `BETFAIR_INPLAY_URL` en config

**Solución temporal**:
```json
{
    "AUTO_DISCOVER_MATCHES": false
}
```

### Problema 5: Supervisor reinicia constantemente el scraper

**Causa**: Detecta muchos errores en logs del scraper

**Solución**:
```json
{
    "AUTO_CORRECT": false,
    "MAX_ERROR_COUNT": 100
}
```

---

## 🎛️ Modos de Operación

### Modo 1: Autónomo Completo (Recomendado)
```json
{
    "AUTO_START_SCRAPER": true,
    "AUTO_DISCOVER_MATCHES": true,
    "AUTO_CORRECT": true
}
```
✅ Perfecto para operación desatendida 24/7

### Modo 2: Supervisión Pasiva
```json
{
    "AUTO_START_SCRAPER": false,
    "AUTO_DISCOVER_MATCHES": false,
    "AUTO_CORRECT": false
}
```
✅ Solo monitoriza, no modifica nada

### Modo 3: Gestión Manual de Partidos
```json
{
    "AUTO_START_SCRAPER": true,
    "AUTO_DISCOVER_MATCHES": false,
    "AUTO_CORRECT": true
}
```
✅ Gestiona scraper pero tú añades partidos manualmente

### Modo 4: Debug Intensivo
```json
{
    "DEBUG": true,
    "CHECK_INTERVAL": 60,
    "HEADLESS_BROWSER": false
}
```
✅ Para depuración y desarrollo

---

## 📁 Estructura de Archivos

```
betfair_scraper/
├── supervisor_agent.py          # Agente supervisor principal
├── supervisor_config.py         # Clase de configuración
├── supervisor_utils.py          # Utilidades (LogAnalyzer, CSVManager, etc.)
├── supervisor_config.json       # Configuración (generada automáticamente)
├── requirements_supervisor.txt  # Dependencias
├── SUPERVISOR_README.md         # Esta documentación
│
├── main.py                      # Scraper principal (NO modificar)
├── games.csv                    # Partidos a trackear
│
├── logs/
│   ├── scraper_*.log           # Logs del scraper
│   └── supervisor_*.log        # Logs del supervisor
│
├── reports/
│   └── supervisor_report_*.md  # Informes generados
│
└── output*.csv                  # Datos capturados
```

---

## 🔄 Flujo Completo de Operación

```
INICIO
  │
  ├─→ Cargar configuración (supervisor_config.json)
  │
  ├─→ Inicializar componentes:
  │    - LogAnalyzer
  │    - CSVManager
  │    - PlaywrightMatchFinder
  │    - DataQualityChecker
  │    - ReportGenerator
  │    - ScraperHealthMonitor
  │
  ├─→ Iniciar scraper (si AUTO_START_SCRAPER=true)
  │
  └─→ LOOP PRINCIPAL (cada CHECK_INTERVAL segundos):
       │
       ├─→ 1. Verificar estado scraper
       │    ¿Corriendo? NO → Iniciar
       │
       ├─→ 2. Descubrir partidos (si AUTO_DISCOVER_MATCHES)
       │    Playwright → Betfair → games.csv
       │    ¿Nuevos partidos? SÍ → Reiniciar scraper
       │
       ├─→ 3. Health check
       │    CPU/RAM/Disco/Chrome/Última captura
       │
       ├─→ 4. Verificar calidad
       │    Cuotas/Stats/Timestamps
       │
       ├─→ 5. Analizar logs
       │    Errores/Warnings/Capturas
       │
       ├─→ 6. Aplicar correcciones (si AUTO_CORRECT)
       │    ¿Muchos errores? → Reiniciar
       │    ¿Muchos Chrome? → Limpiar y reiniciar
       │    ¿Timestamps malos? → Limpiar CSV
       │
       ├─→ 7. Generar informe (cada REPORT_INTERVAL ciclos)
       │    reports/supervisor_report_*.md
       │
       └─→ Esperar CHECK_INTERVAL segundos → Repetir
```

---

## 💡 Consejos y Mejores Prácticas

### ✅ DO

1. **Revisa informes periódicamente**
   - Carpeta `reports/` tiene el histórico completo
   - Busca tendencias y patrones

2. **Ajusta umbrales según tu caso**
   - `MIN_STATS_COVERAGE` según tus partidos
   - `MAX_ERROR_COUNT` según estabilidad

3. **Mantén games.csv limpio**
   - El supervisor añade partidos automáticamente
   - Revisa que no haya duplicados

4. **Monitoriza espacio en disco**
   - CSVs crecen rápidamente
   - El supervisor alerta si < 5 GB

5. **Usa modo debug para troubleshooting**
   - `DEBUG: true` da información detallada
   - `HEADLESS_BROWSER: false` para ver Playwright

### ❌ DON'T

1. **No ejecutes múltiples supervisores**
   - Solo 1 instancia a la vez
   - Pueden entrar en conflicto

2. **No modifiques archivos mientras el supervisor corre**
   - Puede causar race conditions
   - Detén supervisor → Modifica → Reinicia

3. **No uses AUTO_CORRECT sin supervisión inicial**
   - Primero observa el comportamiento
   - Luego activa auto-corrección

4. **No desactives STOP_SCRAPER_ON_EXIT**
   - Puede dejar procesos zombies
   - Siempre limpia al salir

5. **No uses CHECK_INTERVAL muy bajo (< 60)**
   - Sobrecarga el sistema
   - 300 segundos (5 min) es óptimo

---

## 🚀 Ventajas del Supervisor

| Antes (Manual) | Ahora (Con Supervisor) |
|----------------|------------------------|
| Revisar logs manualmente | ✅ Análisis automático de logs |
| Añadir partidos a mano | ✅ Descubrimiento automático |
| Reiniciar si hay errores | ✅ Auto-corrección |
| Verificar calidad de datos | ✅ Verificación continua |
| Iniciar/parar scraper | ✅ Gestión automática |
| Sin informes | ✅ Informes cada hora |
| Supervisión constante | ✅ Operación desatendida 24/7 |

---

## 📞 Soporte y Desarrollo

### Extensibilidad

El supervisor está diseñado para ser extensible. Puedes añadir:

1. **Nuevas verificaciones** en `DataQualityChecker`
2. **Nuevos análisis** en `LogAnalyzer`
3. **Nuevas correcciones** en `SupervisorAgent.apply_corrections()`
4. **Nuevas métricas** en `ScraperHealthMonitor`

### Contribuir

Para añadir funcionalidades:
1. Modifica `supervisor_utils.py` (añade nueva clase)
2. Importa en `supervisor_agent.py`
3. Integra en `run_cycle()`
4. Actualiza `supervisor_config.py` si necesitas nuevos parámetros

---

## ✨ Conclusión

El **Supervisor Agent** convierte el scraper de Betfair en un sistema completamente autónomo capaz de:

- 🤖 Operar 24/7 sin supervisión humana
- 🔍 Descubrir y añadir partidos automáticamente
- 🛠️ Corregir problemas sin intervención
- 📊 Generar informes detallados
- ❤️ Monitorizar salud del sistema

**¡Ideal para captura masiva de datos a largo plazo!** ⚽📈

---

*Documentación del Supervisor Agent v1.0 - 2026-02-10*
