# Supervisor de Betfair

Script simple para ejecutar el agente supervisor que mantiene el scraper funcionando.

## 🎯 Qué hace el supervisor

Cada vez que lo ejecutas:
- ✅ Verifica que el scraper esté corriendo (lo arranca si está parado)
- ✅ Elimina partidos terminados de games.csv
- ✅ Busca partidos nuevos en Betfair y los añade a games.csv
- ✅ Verifica la calidad de los datos
- ✅ Te muestra un informe de lo que hizo

Todo automático, sin preguntar.

## 🚀 Uso

```bash
python supervisor.py
```

Eso es todo. El script hace el resto.

## 📅 ¿Cuándo ejecutarlo?

Ejecútalo cuando quieras supervisar el sistema:
- Al iniciar tu sesión de trabajo
- Cada vez que añadas partidos manualmente
- Si sospechas que algo no va bien
- Cuando quieras actualizar la lista de partidos de Betfair

**Recomendación**: Ejecútalo cada 1-2 horas mientras el scraper esté capturando datos.

## 🔧 Requisitos

- CLI de Claude instalada y en el PATH
- Agente supervisor configurado en `.claude/agents/betfair-supervisor.md`

## 💡 Automatización (Opcional)

Si quieres que se ejecute automáticamente cada X minutos, puedes usar:

### Windows - Task Scheduler
1. Abre "Programador de tareas" (taskschd.msc)
2. Crea tarea básica
3. Programa: `python.exe`
4. Argumentos: `"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\supervisor.py"`
5. Configurar para repetir cada 30 minutos

### Linux/Mac - Cron
```bash
# Ejecutar cada 30 minutos
*/30 * * * * cd /ruta/al/proyecto && python betfair_scraper/supervisor.py
```

Pero no es necesario. Puedes simplemente ejecutarlo manualmente cuando lo necesites.
