# Supervisor Agent - Guía de Inicio Rápido

## 🚀 5 Pasos para Empezar

### 1. Instalar Dependencias

```bash
pip install -r requirements_supervisor.txt
playwright install chromium
```

### 2. Verificar Configuración

Abre `supervisor_config.json` y verifica que las rutas sean correctas:

```json
{
    "BASE_DIR": "C:\\Users\\agonz\\OneDrive\\Documents\\Proyectos\\Furbo\\betfair_scraper",
    "SCRAPER_SCRIPT": "C:\\Users\\agonz\\OneDrive\\Documents\\Proyectos\\Furbo\\betfair_scraper\\main.py"
}
```

### 3. Probar Instalación

```bash
python test_supervisor.py
```

Deberías ver:
```
✓ Configuración cargada correctamente
✓ Scraper script existe
✓ games.csv existe
✓ Directorios creados
[OK] Instalación correcta
```

### 4. Iniciar Supervisor

```bash
python supervisor_agent.py
```

### 5. Revisar Logs e Informes

- **Logs**: `logs/supervisor_YYYYMMDD_HHMMSS.log`
- **Informes**: `reports/supervisor_report_YYYYMMDD_HHMMSS.md`

---

## ⚙️ Configuración Básica

### Modo Autónomo Completo (Default)

```json
{
    "AUTO_START_SCRAPER": true,
    "AUTO_DISCOVER_MATCHES": true,
    "AUTO_CORRECT": true,
    "CHECK_INTERVAL": 300
}
```

El supervisor:
- ✅ Inicia el scraper automáticamente
- ✅ Busca partidos en Betfair y los añade
- ✅ Corrige problemas automáticamente
- ✅ Ejecuta ciclos cada 5 minutos

### Modo Solo Monitorización

```json
{
    "AUTO_START_SCRAPER": false,
    "AUTO_DISCOVER_MATCHES": false,
    "AUTO_CORRECT": false
}
```

El supervisor:
- ✅ Solo monitoriza (no modifica nada)
- ✅ Genera informes
- ✅ Analiza logs

---

## 📊 Qué Hace el Supervisor

### Cada 5 Minutos (1 Ciclo)

1. ✓ Verifica que el scraper esté corriendo
2. ✓ Busca partidos en vivo en Betfair
3. ✓ Añade nuevos partidos a `games.csv`
4. ✓ Verifica calidad de datos (cuotas, stats)
5. ✓ Analiza logs en busca de errores
6. ✓ Aplica correcciones si es necesario

### Cada Hora (12 Ciclos)

7. ✓ Genera informe completo en `reports/`

---

## 🛑 Detener el Supervisor

### Método 1: Ctrl+C

```
Presiona Ctrl+C en la terminal
El supervisor detendrá el scraper y se cerrará limpiamente
```

### Método 2: Terminar Proceso

```bash
# Windows
taskkill /F /IM python.exe /FI "WINDOWTITLE eq supervisor*"

# Linux/Mac
pkill -f supervisor_agent.py
```

---

## 🔧 Troubleshooting Rápido

### Problema: Errores al importar módulos

```bash
pip install -r requirements_supervisor.txt --upgrade
```

### Problema: Playwright no funciona

```bash
playwright install chromium
```

### Problema: Supervisor no encuentra el scraper

Edita `supervisor_config.json` y ajusta las rutas absolutas.

### Problema: Betfair bloquea el navegador

```json
{
    "AUTO_DISCOVER_MATCHES": false
}
```

---

## 📞 Ayuda Completa

Consulta `SUPERVISOR_README.md` para documentación completa con:
- Configuración avanzada
- Casos de uso detallados
- Troubleshooting exhaustivo
- Extensibilidad y desarrollo

---

## ✨ Ventajas

| Sin Supervisor | Con Supervisor |
|----------------|----------------|
| Manual 🙁 | Automático 😊 |
| Supervisión constante 😰 | Desatendido 24/7 😎 |
| Sin informes 📄 | Informes cada hora 📊 |
| Añadir partidos a mano ✍️ | Auto-descubrimiento 🔍 |
| Reiniciar si hay errores 🔧 | Auto-corrección ✅ |

**¡Empieza a capturar datos de forma completamente autónoma!** 🚀⚽
