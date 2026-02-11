# PASO 6 (Opcional) - Validación de Estadísticas

Documento que explica cómo integrar `validate_stats.py` como un PASO 6 opcional en el supervisor.

## 📊 Por Qué Este Paso

El supervisor genera un informe mostrando que solo el 32.1% de filas tienen estadísticas. Pero la pregunta es:

**¿Es un problema del scraper o simplemente Betfair no publica esas stats?**

`validate_stats.py` responde esta pregunta accediendo a Betfair y verificando qué estadísticas REALMENTE están disponibles.

## 🔄 Nueva Estructura del Supervisor

```
PASO 1: start_scraper.py           (Verificar/arrancar scraper)
PASO 2: find_matches.py            (Buscar nuevos partidos)
PASO 3: clean_games.py             (Limpiar viejos)
PASO 4: check_urls.py              (Verificar 404s)
PASO 5: generate_report.py         (Analizar todo)
[PASO 6 OPCIONAL: validate_stats.py] (Validar stats capturadas)
```

## 🎯 Flujo de PASO 6

```
Si el informe muestra poca cobertura de stats (< 50%):
  └─ Ejecutar validate_stats.py
     ├─ ¿Hay brecha (stats disponibles pero no capturadas)?
     │  └─ YES: Problema del scraper → Reportar necesidad de actualizar selectores
     │  └─ NO: Estadísticas simplemente no disponibles → OK normal
     └─ Reportar conclusión al usuario
```

## 📋 Decisión: ¿Ejecutar PASO 6?

El supervisor debe decidir:

```
Si stats_coverage < 50%:
  └─ Ejecutar validate_stats.py
     ├─ Leer resultado
     └─ Si hay brecha: Reportar al usuario

Else (stats_coverage >= 50%):
  └─ PASO 6 no necesario
  └─ Continuar
```

## 💾 Configuración en Supervisor

En `.claude/agents/betfair-supervisor.md` agregar:

```markdown
### PASO 6: Validar Estadísticas Capturadas (CONDICIONAL)

**Este paso es OPCIONAL. Solo se ejecuta si la cobertura de stats es baja.**

**Condición para ejecutar**:
- Si el reporte del PASO 5 muestra stats_coverage < 50%
- Si el usuario reporta que faltan estadísticas

**6.1 - EJECUTAR script de validacion**:
```bash
cd betfair_scraper && python validate_stats.py
```

**6.2 - Interpretar resultado**:
- Si reporta "Brecha de datos" → Problema del scraper (selectores CSS)
- Si reporta "[OK] Todas capturadas" → Scraper funciona bien
- Si reporta "Sin estadísticas disponibles" → Betfair no publica para esa liga

**6.3 - Reportar**:
- Si hay brecha: "Se detectó brecha de datos en [X] estadísticas. Revisar selectores CSS."
- Si no hay: "Validacion OK: El scraper captura todas las estadísticas disponibles."
```

## 🔧 Integración Automática

El supervisor podría implementar lógica condicional:

```python
# En PASO 5, generar_report() retorna stats_coverage

if stats_coverage < 0.50:  # 50%
    print("[ALERTA] Baja cobertura de estadísticas detectada")
    print("[INFO] Ejecutando PASO 6: Validación de estadísticas...")

    # Ejecutar validate_stats.py
    result = subprocess.run(['python', 'validate_stats.py'], ...)

    # Leer output
    if "Brecha de datos detectada" in output:
        print("[PROBLEMA] Se detectó brecha de datos")
        print("Acción recomendada: Actualizar selectores CSS en main.py")
    else:
        print("[OK] No hay brecha. Las stats simplemente no están disponibles.")
else:
    print("[OK] Cobertura de stats adecuada. PASO 6 no necesario.")
```

## 📊 Casos de Uso

### Caso 1: Alto Porcentaje de Stats (Normal)
```
PASO 5 Resultado: stats_coverage = 85%

Status: OK
Acciones:
├─ PASO 6 no se ejecuta (no necesario)
└─ Continuar normalmente
```

### Caso 2: Bajo Porcentaje de Stats (Investigar)
```
PASO 5 Resultado: stats_coverage = 32%

Status: INVESTIGAR
Acciones:
├─ Ejecutar PASO 6: validate_stats.py
├─ Resultado: "Brecha de datos: xG no se captura"
├─ Conclusion: Problema del scraper
└─ Acción: Reportar necesidad de actualizar main.py
```

### Caso 3: Sin Stats Disponibles (Normal para Ligas Menores)
```
PASO 5 Resultado: stats_coverage = 0% (partidos de Camboya)

Status: ESPERADO
Acciones:
├─ Ejecutar PASO 6: validate_stats.py
├─ Resultado: "Sin estadísticas disponibles en la página"
├─ Conclusion: Betfair no publica stats para esta liga
└─ Acción: Ninguna. Es normal.
```

## 🎛️ Control Manual del Supervisor

El usuario puede también ejecutar manualmente:

```bash
# Ejecutar PASO 6 bajo demanda
python validate_stats.py

# Interpretar resultado
# ├─ Brecha detectada → Problema del scraper
# ├─ Todas capturadas → Scraper OK
# └─ Sin estadísticas → Betfair no publica para esa liga
```

## 🚀 Ventajas de PASO 6

1. **Diagnóstico Automático**: Diferencia entre "scraper no captura" vs "no disponible"
2. **Reducción de Incertidumbre**: Responde "¿por qué 32% de stats?"
3. **Mejora Proactiva**: Identifica cuando los selectores CSS fallan
4. **Documentación**: Genera evidencia de dónde está el problema
5. **Descarga del Agente**: El script hace toda la investigación

## 📈 Visibilidad Mejorada

**Antes (sin PASO 6)**:
```
Informe: "Stats: 32.1% capturadas"
Usuario: "¿Por qué tan bajo? ¿Es un bug?"
Acción: Investigación manual tediosa
```

**Después (con PASO 6)**:
```
Informe: "Stats: 32.1% capturadas"
PASO 6: "Validación: Sin estadísticas disponibles en Betfair"
Usuario: "OK, es normal para ligas menores"
Acción: Ninguna necesaria
```

## ✅ Próximos Pasos

1. ✅ Script `validate_stats.py` creado
2. ✅ Documentación creada
3. ⏳ Integración en supervisor (decidida por usuario)
4. ⏳ Ejecución automática condicional (opcional)

## 🔗 Relación con Otros Scripts

```
generate_report.py (PASO 5)
    ↓ (detecta baja cobertura de stats)
validate_stats.py (PASO 6)
    ↓ (identifica causa)
Usuario:
    ├─ Si es brecha: Actualiza main.py
    └─ Si no disponible: Continúa normalmente
```

---

**Propósito**: Responder automáticamente "¿por qué hay tan pocas estadísticas?"
**Status**: ✅ Listo para integración
**Ejecución**: Condicional o bajo demanda
