# Supervisor Workflow - Orquestación Automática de 6 PASOS

Script maestro que ejecuta automáticamente los 6 PASOS del supervisor en orden.

## 🎯 Qué Hace

Ejecuta secuencialmente:
1. **PASO 1**: `start_scraper.py` - Verifica/arranca scraper
2. **PASO 2**: `find_matches.py` - Busca nuevos partidos en Betfair
3. **PASO 3**: `clean_games.py` - Elimina partidos terminados
4. **PASO 4**: `check_urls.py` - Verifica errores 404
5. **PASO 5**: `generate_report.py` - Genera informe completo
6. **PASO 6**: `validate_stats.py` - Valida estadísticas (OBLIGATORIO)

## 🚀 Uso

### Ejecución Manual

```bash
cd betfair_scraper
python supervisor_workflow.py
```

### Salida Esperada

El script imprime:
- Progreso de cada PASO
- Resultado de cada ejecución [OK] o [ERROR]
- Resumen final consolidado

Ejemplo:
```
======================================================================
  PASO 1: Verificar y arrancar scraper
======================================================================
[EJECUTANDO] start_scraper.py...
[OK] start_scraper.py completado exitosamente

... (PASOS 2-5 similares) ...

======================================================================
  PASO 6: Validar estadísticas capturadas (OBLIGATORIO)
======================================================================
[EJECUTANDO] validate_stats.py...
[OK] validate_stats.py completado exitosamente

======================================================================
  RESUMEN FINAL DE EJECUCIÓN
======================================================================

PASOS EJECUTADOS:
  PASO 1 (start_scraper.py):    [OK]
  PASO 2 (find_matches.py):     [OK]
  PASO 3 (clean_games.py):      [OK]
  PASO 4 (check_urls.py):       [OK]
  PASO 5 (generate_report.py):  [OK]
  PASO 6 (validate_stats.py):   [OK] [OBLIGATORIO]

[OK] Workflow completado - Sistema funcionando
```

## 🔍 Interpretación de Resultados

### Todo [OK]
```
[OK] Workflow completado - Sistema funcionando
```
Significa:
- Scraper funcionando
- Partidos buscados/limpiados
- URLs verificadas
- Estadísticas validadas
- Sistema en estado saludable

### Con [ALERTA]
```
[ALERTA] Workflow completado con problemas
  - PASO 1: Scraper puede no estar corriendo
  - PASO 6: Validación de estadísticas falló
```
Significa:
- Algún PASO falló
- Revisar el output específico de ese PASO para más detalles

## 📊 Información Clave de PASO 6

Cuando `validate_stats.py` se ejecuta:

### Si detecta "Brecha de datos":
```
[ALERTA] Brecha de datos detectada:
  * PASES: No capturado en 1 partido(s)
  * XG: No capturado en 1 partido(s)
  * TIROS_A_PUERTA: No capturado en 1 partido(s)
  * SALVADAS: No capturado en 1 partido(s)

[ACCION RECOMENDADA]
  1. Revisar selectores CSS en main.py
  2. Verificar que busquen en el lugar correcto
  3. Actualizar selectores si Betfair cambió estructura HTML
  4. Ejecutar validate_stats.py nuevamente para confirmar corrección
```

**Significado**: Las estadísticas EXISTEN en Betfair pero NO se están capturando en los CSVs. Problema en los selectores CSS de main.py.

### Si todo está OK:
```
[OK] Validacion completada:
  - No se detectaron brechas
  - Las estadísticas disponibles se están capturando
```

Significa: El scraper captura correctamente todo lo disponible.

### Si no hay stats disponibles:
```
[INFO] Sin partidos activos en este momento
[OK] Sin verificaciones que hacer
```

Significa: Betfair no publica estadísticas para esa liga (normal en ligas menores).

## ⏱️ Cuándo Ejecutar

### Recomendado:
- **Cada 1-2 horas**: Monitoreo continuo
- **Después de cambios**: Cambios en main.py, config.py o selectores
- **Cuando Betfair actualiza**: Si sospechas cambios en la interfaz

### Automático:
- Programar con Windows Task Scheduler para ejecución periódica
- O llamar desde supervisor agent

## 🔄 Relación con el Supervisor

El supervisor agent debe ejecutar este script:

```bash
cd betfair_scraper && python supervisor_workflow.py
```

Este script se encarga de:
1. Ejecutar los 6 scripts en orden
2. Validar que cada uno completó
3. Reportar resultados consolidados
4. **ALERTAR si hay brecha de estadísticas** (PASO 6)

## 📝 Características

- ✅ Ejecución automática de 6 PASOS
- ✅ Detección de errores en cada PASO
- ✅ Timeout de 5 minutos por PASO (evita cuelgues)
- ✅ Validación automática de estadísticas (OBLIGATORIO)
- ✅ Alerta clara si hay brecha de datos
- ✅ Resumen consolidado final
- ✅ Compatible con Windows

## 🛠️ Configuración

No requiere configuración. El script usa los mismos parámetros que los scripts individuales.

Si necesitas cambiar comportamiento:
- Edita los scripts individuales (PASO 1-6)
- Este script solo los ejecuta en orden

## 📚 Scripts Utilizados

| Script | Responsabilidad |
|--------|-----------------|
| start_scraper.py | Controlar proceso del scraper |
| find_matches.py | Buscar partidos en Betfair |
| clean_games.py | Limpiar partidos terminados |
| check_urls.py | Verificar URLs 404 |
| generate_report.py | Generar informe de supervisión |
| validate_stats.py | Validar estadísticas capturadas |

## 🎯 Próximos Pasos

1. ✅ Supervisor_workflow.py creado y probado
2. ⏳ Integrar en agente supervisor
3. ⏳ Programar ejecución automática (Task Scheduler)
4. ⏳ Si hay brecha: Actualizar selectores CSS en main.py
