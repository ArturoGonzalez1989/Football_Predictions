# Sistema de Detección de Campos Nuevos

## ¿Qué es esto?

Un sistema **híbrido** que combina:
- ✅ **Whitelist** - Solo captura campos conocidos y validados
- ✅ **Auto-detección** - Alerta cuando aparecen campos nuevos en la API

## Cómo Funciona

### Arquitectura

```
API Stats Perform
    ↓
stats_api.py (parsing)
    ├─ Campos CONOCIDOS → Capturados en CSV
    └─ Campos NUEVOS → Logged como INFO
```

### Ejemplo de Salida

Cuando un partido de liga importante añade nuevas estadísticas:

```
📊 [summary] Campos NUEVOS detectados en API: ['expectedAssists', 'xgPerShot']
💡 Tip: Si estos campos son útiles, añádelos a la whitelist en parse_summary_html()
```

**Importante:** Cada campo nuevo se reporta **solo 1 vez por sesión** para evitar spam en logs.

## Endpoints Monitoreados

| Endpoint | Función | Campos Conocidos |
|----------|---------|------------------|
| **summary** | `parse_summary_html()` | 17 campos (xG, corners, shots, etc.) |
| **attacking** | `parse_attacking_html()` | 15+ campos (bigChances, shotsOffTarget, etc.) |
| **defence** | `parse_defence_html()` | 14+ campos (tackles, saves, etc.) |
| **xg** | `parse_xg_html()` | 7 campos (xgOpenPlay, xgSetPlay, etc.) |
| **momentum** | `parse_momentum_html()` | Estructura variable (chartData, etc.) |

## Añadir Campos Nuevos

Cuando detectes un campo útil, añadirlo es trivial:

### 1. Actualizar stats_api.py

```python
# En parse_summary_html() por ejemplo:

# Añadir a la whitelist
known_fields_api = {
    'goals', 'shots', 'corners',
    'expectedAssists',  # ← NUEVO campo
}

# Añadir al resultado
result = {
    'home': {
        'xG': to_float(home.get('xg')),
        'expectedAssists': to_float(home.get('expectedAssists')),  # ← NUEVO
    }
}
```

### 2. Actualizar main.py

```python
# En extraer_estadisticas():

# Añadir claves al dict
stats = {
    "xg_local": "",
    "expected_assists_local": "",  # ← NUEVO
}

# Mapear el valor
stats["expected_assists_local"] = extract_stat_value(
    all_stats, 'summary', 'home', 'expectedAssists', ""
)
```

**Total:** ~5 líneas de código vs 30+ con CSS selectors.

## Ventajas del Sistema Híbrido

### ✅ Control Total
- CSV con estructura predecible
- Validación de tipos (int, float)
- Solo datos relevantes

### ✅ No Perder Datos
- Alertas cuando aparecen campos nuevos
- No requiere monitoreo manual constante
- Detección automática en producción

### ✅ Fácil Mantenimiento
- Añadir campos es trivial
- No rompe código existente
- Backwards compatible

## Casos de Uso

### Escenario 1: Liga Menor
Partido con pocas estadísticas → No reporta campos nuevos → CSV normal

### Escenario 2: Champions League
Partido con estadísticas avanzadas → Detecta `expectedGoalChain`, `xgBuildup` → Log INFO → Usuario decide si añadirlas

### Escenario 3: Nueva Temporada
API añade `smartPasses`, `progressivePasses` → Sistema detecta automáticamente → Usuario actualiza whitelist → Datos disponibles para todos los partidos futuros

## Logging

Los campos nuevos se loggean como **INFO** (no WARNING) en:

```
betfair_scraper/logs/scraper_YYYYMMDD_HHMMSS.log
```

Buscar en logs:
```bash
grep "Campos NUEVOS detectados" logs/*.log
```

## Estado Actual

✅ **Implementado completamente en:**
- `stats_api.py` - Detección en 5 endpoints
- `main.py` - Integración con sistema API
- Sistema de tracking global (no spam)

✅ **Campos capturados actualmente:**
- Summary: 17 campos core
- Attacking: 10 campos principales
- Defence: 9 campos principales
- xG: 4 campos (breakdown detallado)
- Momentum: Estructura completa

## Próximos Pasos

1. **Monitorear logs** durante 1 semana con partidos en vivo
2. **Analizar campos detectados** en ligas top (Champions, Premier, La Liga)
3. **Priorizar campos nuevos** según relevancia para trading
4. **Actualizar whitelist** con los campos más útiles

---

**Versión:** 1.0
**Fecha:** 2026-02-12
**Estado:** ✅ Activo
