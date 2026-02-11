# Manual de Usuario - Betfair Scraper

**Guía completa de uso del sistema automático de captura de cuotas y estadísticas.**

---

## 📚 Tabla de Contenidos

1. [Instalación](#instalación)
2. [Uso Manual](#uso-manual)
3. [Uso Automático con Agente](#uso-automático-con-agente)
4. [Interpretación de Resultados](#interpretación-de-resultados)
5. [Resolución de Problemas](#resolución-de-problemas)
6. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## 🔧 Instalación

### Requisitos Previos

- Python 3.9+
- Google Chrome instalado
- Cuenta en Betfair.es
- Acceso a la línea de comandos (PowerShell, CMD o Terminal)

### Paso 1: Instalar Dependencias

```bash
cd betfair_scraper
pip install -r requirements.txt
```

Esto instala:
- `selenium` - Para automación del navegador
- `webdriver-manager` - Para gestionar ChromeDriver

### Paso 2: Verificar Instalación

```bash
python -c "import selenium; print('OK: Selenium instalado')"
```

Si todo está bien, verás: `OK: Selenium instalado`

---

## 🚀 Uso Manual

### Opción 1: RECOMENDADA - Ejecutar Todo de Una Vez

**Un solo comando ejecuta los 6 PASOS automáticamente:**

```bash
cd betfair_scraper
python supervisor_workflow.py
```

**¿Qué hace?**
1. ✅ PASO 1: Verifica si el scraper está corriendo
2. ✅ PASO 2: Busca nuevos partidos en Betfair
3. ✅ PASO 3: Elimina partidos terminados
4. ✅ PASO 4: Verifica URLs 404
5. ✅ PASO 5: Genera reporte del sistema
6. ✅ PASO 6: Valida estadísticas capturadas

**Salida esperada:**
```
======================================================================
  WORKFLOW DEL SUPERVISOR - ORQUESTACIÓN DE 6 PASOS
======================================================================

Inicio: 2026-02-11 17:47:00

PASO 1: Verificar y arrancar scraper
[EJECUTANDO] start_scraper.py...
[OK] start_scraper.py completado exitosamente

... (PASOS 2-5 similares) ...

PASO 6: Validar estadísticas capturadas (OBLIGATORIO)
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

Fin: 2026-02-11 17:47:32

[OK] Workflow completado - Sistema funcionando

======================================================================
```

---

### Opción 2: Ejecutar PASOS Individuales

Si necesitas ejecutar solo algunos PASOS:

#### PASO 1: Verificar/Arrancar Scraper

```bash
cd betfair_scraper
python start_scraper.py
```

**¿Cuándo usar?**
- Para verificar si el scraper está en ejecución
- Para arrancarlo manualmente
- Para reiniciarlo si está frozen

**Salida posible:**
```
[OK] Scraper está corriendo (PID: 12345)
```

O si no está corriendo:
```
[INFO] Scraper no está corriendo. Arrancando...
[OK] Scraper arrancado (PID: 12346)
```

---

#### PASO 2: Buscar Nuevos Partidos

```bash
cd betfair_scraper
python find_matches.py
```

**¿Cuándo usar?**
- Para buscar nuevos partidos en Betfair
- Para actualizar games.csv con últimos partidos

**Salida posible:**
```
[INFO] Accediendo a Betfair...
[INFO] Buscando partidos de fútbol...
[OK] Encontrados 8 partidos
[OK] Añadidos 3 nuevos a games.csv
[OK] Sin cambios - 5 partidos ya existían
```

---

#### PASO 3: Limpiar Partidos Terminados

```bash
cd betfair_scraper
python clean_games.py
```

**¿Cuándo usar?**
- Para eliminar partidos que ya terminaron
- Para mantener games.csv limpio

**Salida posible:**
```
[OK] Limpieza completada
  - Eliminados 2 partidos terminados
  - Quedan 5 partidos activos
```

---

#### PASO 4: Verificar URLs 404

```bash
cd betfair_scraper
python check_urls.py
```

**¿Cuándo usar?**
- Para buscar URLs inválidas (404)
- Para eliminar partidos con páginas eliminadas

**Salida posible:**
```
[OK] Sin errores 404 detectados
```

O si hay problemas:
```
[VERIFICACION COMPLETADA]
  - Encontrados 1 errores 404
  - Eliminado 1 partido problemático (ID: 12345)
```

---

#### PASO 5: Generar Reporte

```bash
cd betfair_scraper
python generate_report.py
```

**¿Cuándo usar?**
- Para analizar el estado del sistema
- Para ver estadísticas de captura
- Para verificar cobertura de datos

**Salida:**
```
============================================================
INFORME DE SUPERVISION
============================================================

Hora: 2026-02-11 17:47:22

1. PARTIDOS CONFIGURADOS
   Total: 4 partidos
   Activos: 1
   Futuros: 3

2. DATOS CAPTURADOS
   CSVs de partidos: 53
   Filas totales: 347
   Filas con cuotas: 86.2%
   Filas con stats: 34.3%

3. SALUD DEL SCRAPER
   Errores recientes: 0
   Warnings recientes: 11
   Ultima actividad: 17:47:19

4. ESTADO GENERAL
   STATUS: [OK] Sistema funcionando correctamente
   - Scraper capturando datos
   - Partidos configurados activamente
   - Calidad de datos aceptable

============================================================
```

---

#### PASO 6: Validar Estadísticas

```bash
cd betfair_scraper
python validate_stats.py
```

**¿Cuándo usar?**
- Para verificar si se capturan todas las estadísticas disponibles
- Para detectar "brecha de datos"
- Para diagnosticar problemas de captura

**Salida Caso 1 - Sin problemas:**
```
[INFO] Encontrados 1 partidos activos
[VERIFICANDO] Al Ahly Cairo - Ismaily...
  -> Disponibles en Betfair: pases, posesion, tarjetas
  -> Capturadas en CSV: pases, posesion, tarjetas
  -> OK: Todas las estadisticas disponibles se capturaron

[OK] Validacion completada:
  - No se detectaron brechas
  - Las estadísticas disponibles se están capturando
```

**Salida Caso 2 - Brecha detectada:**
```
[ALERTA] Brecha de datos detectada:
  * XG: No capturado en 1 partido(s)
  * PASES: No capturado en 1 partido(s)
  * TIROS_A_PUERTA: No capturado en 1 partido(s)
  * SALVADAS: No capturado en 1 partido(s)

[ACCION RECOMENDADA]
  1. Revisar selectores CSS en main.py
  2. Verificar que busquen en el lugar correcto
  3. Actualizar selectores si Betfair cambió estructura HTML
  4. Ejecutar validate_stats.py nuevamente para confirmar corrección
```

---

## 🤖 Uso Automático con Agente

### ¿Qué es el Agente Supervisor?

El supervisor es un agente autónomo que ejecuta el workflow automáticamente sin intervención manual.

**Características:**
- ✅ Ejecuta los 6 PASOS automáticamente
- ✅ Mantiene el sistema funcionando 24/7
- ✅ Reporta problemas cuando ocurren
- ✅ Toma decisiones sin preguntar

### Cómo Usar el Agente

#### Opción 1: Usar el Skill del Agente

El supervisor tiene un skill llamado `supervisor-report` que ejecuta todo:

```bash
# En Claude Code, ejecutar el skill:
/supervisor-report
```

O via CLI:
```bash
claude invoke supervisor-report
```

**¿Qué hace?**
1. Ejecuta supervisor_workflow.py
2. Analiza resultados
3. Reporta estado al usuario
4. Alerta si hay problemas

#### Opción 2: Usar la Configuración del Agente

El agente está configurado en:
```
.claude/agents/betfair-supervisor.md
```

**Cómo se ejecuta:**
1. El usuario invoca el agente
2. El agente ejecuta: `python supervisor_workflow.py`
3. Lee los outputs
4. Reporta conclusiones

**Características del agente:**
- ACTÚA primero, reporta después
- Nunca pregunta innecesariamente
- Toma decisiones autónomas
- Mantiene el scraper siempre encendido

---

## 📊 Interpretación de Resultados

### Caso 1: Todo OK

**Salida:** `[OK] Workflow completado - Sistema funcionando`

**Significado:**
- Todos los PASOS completaron exitosamente
- El scraper está en ejecución
- Los datos se capturan normalmente
- No hay problemas detectados

**Acción:** Continuar monitoreo normal. Todo está bien.

---

### Caso 2: Brecha de Estadísticas Detectada

**Salida:**
```
[ALERTA] Brecha de datos detectada:
  * XG: No capturado en 1 partido(s)
  * PASES: No capturado en 1 partido(s)
```

**Significado:**
- Las estadísticas SÍ están disponibles en Betfair
- El scraper NO las captura
- Problema en los selectores CSS de main.py

**Acciones Recomendadas:**
1. Abrir main.py
2. Buscar los selectores CSS para xG y pases
3. Verificar que apunten al elemento correcto en Betfair
4. Actualizar si es necesario
5. Ejecutar `python validate_stats.py` nuevamente para confirmar

---

### Caso 3: Sin Estadísticas Disponibles

**Salida:**
```
[INFO] Sin estadísticas disponibles en Betfair
[OK] Sin verificaciones que hacer
```

**Significado:**
- Betfair NO publica estadísticas para esa liga
- Es normal para ligas menores (Camboya, Tailandia, etc.)
- No es problema del scraper

**Acción:** Continuar normalmente. Es esperado.

---

### Caso 4: Scraper No Está Corriendo

**Salida:**
```
[ERROR] Scraper no está corriendo
```

**Significado:**
- El proceso main.py se paró
- Puede haber errores o haber sido terminado

**Acciones:**
1. Ejecutar: `python start_scraper.py`
2. Si falla nuevamente, revisar logs en `logs/`
3. Buscar mensajes de error

---

## 🔧 Resolución de Problemas

### Problema: "No se encuentran partidos"

**Causa:** Posible horario sin partidos

**Solución:**
1. Ejecutar `python find_matches.py`
2. Verificar que Betfair tiene partidos en ese momento
3. Si hay partidos pero no aparecen, revisar selectores CSS

---

### Problema: "CSV vacío o sin datos"

**Causa:** El scraper no captura datos

**Solución:**
1. Verificar que main.py está corriendo: `python start_scraper.py`
2. Ejecutar `python generate_report.py`
3. Revisar logs en `logs/` para mensajes de error
4. Revisar selectores CSS en main.py

---

### Problema: "Chrome no se abre"

**Causa:** Chrome no instalado o ChromeDriver incompatible

**Solución:**
```bash
# Verificar Chrome instalado
google-chrome --version

# Reinstalar webdriver-manager
pip install --upgrade webdriver-manager

# Limpiar caché de ChromeDriver
python -c "from webdriver_manager.chrome import ChromeDriverManager; ChromeDriverManager().install()"
```

---

### Problema: "Brecha de datos detectada"

**Causa:** Selectores CSS desactualizados

**Solución:**
1. Abrir un partido en Betfair
2. Pulsar F12 → Inspector
3. Buscar el selector CSS para la estadística faltante
4. Actualizar main.py con el nuevo selector
5. Ejecutar `python validate_stats.py` nuevamente

---

### Problema: "Error de timeout"

**Causa:** Betfair tarda en cargar o conexión lenta

**Solución:**
1. Aumentar timeouts en config.py
2. Revisar conexión a internet
3. Reintentar más tarde

---

## ❓ Preguntas Frecuentes

### P: ¿Cómo evito que el scraper se pare?
R: El supervisor verifica cada ciclo y lo reinicia si es necesario. Usar `supervisor_workflow.py` automáticamente.

### P: ¿Cómo añado nuevos partidos?
R: Automático. Ejecutar `python find_matches.py` o esperar a que el supervisor lo haga.

### P: ¿Cómo elimino partidos viejos?
R: Automático. El supervisor los limpia en PASO 3 cuando llevan > 120 minutos.

### P: ¿Dónde están los datos capturados?
R: En `data/partido_*.csv`. Cada archivo contiene los datos de un partido.

### P: ¿Cómo veo el estado del scraper?
R: Ejecutar `python generate_report.py`

### P: ¿Qué significa "86.2% cuotas, 34.3% stats"?
R: 86.2% de filas tienen cuotas capturadas. 34.3% tienen estadísticas Opta.
Esto es normal: Betfair no publica stats para todas las ligas.

### P: ¿Cómo se detecta "brecha de datos"?
R: Ejecutar `python validate_stats.py`. Compara stats disponibles en Betfair vs capturadas en CSV.

### P: ¿Puedo detener el scraper?
R: Sí. Pulsar Ctrl+C. Los datos guardados se preservan.

### P: ¿Cómo arranco el scraper nuevamente?
R: `python start_scraper.py` o esperar a que el supervisor lo haga.

### P: ¿Puedo editar games.csv manualmente?
R: Sí. Formato CSV con columnas: Game, url, fecha_hora_inicio
Pero es mejor usar `python find_matches.py` para que busque automáticamente.

### P: ¿Cómo uso el agente supervisor?
R: Ver sección [Uso Automático con Agente](#uso-automático-con-agente)

---

## 📋 Checklist de Configuración Inicial

- [ ] Python 3.9+ instalado
- [ ] Chrome instalado
- [ ] Dependencias instaladas: `pip install -r requirements.txt`
- [ ] Cuenta en Betfair.es disponible
- [ ] Primer ejecutar: `python supervisor_workflow.py`
- [ ] Verificar que se crean archivos en `data/`
- [ ] Revisar `logs/` para mensajes de estado

---

## 🚀 Próximos Pasos

1. **Instalación:** Seguir pasos en [Instalación](#instalación)
2. **Primer uso:** `python supervisor_workflow.py`
3. **Verificar datos:** `python generate_report.py`
4. **Usar agente:** Invocar `/supervisor-report`
5. **Si hay problemas:** Ver [Resolución de Problemas](#resolución-de-problemas)

---

## 📞 Soporte

Para más información:
- Documentación técnica: [README.md](README.md)
- Arquitectura: [ARQUITECTURA_FINAL.txt](ARQUITECTURA_FINAL.txt)
- Scripts individuales: Ver archivos README específicos

---

**Última actualización**: 11 de febrero de 2026

**Status**: ✅ Sistema listo para usar

**Todos los datos se preservan. Confía en la automatización.**
