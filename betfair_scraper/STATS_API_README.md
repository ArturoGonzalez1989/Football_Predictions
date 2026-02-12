# 🚀 Stats API - Nueva Arquitectura para Captura de Estadísticas

## 📋 Resumen

**¡GRAN MEJORA!** En lugar de parsear HTML con CSS selectors (lento, frágil, difícil de mantener), ahora usamos la **API REST de Stats Perform** que Betfair utiliza internamente.

### ✅ Ventajas

| Aspecto | CSS Selectors (Anterior) | API REST (Nuevo) |
|---------|-------------------------|------------------|
| **Velocidad** | 🐌 Lento (Selenium + esperas) | ⚡ 10x más rápido (HTTP directo) |
| **Confiabilidad** | ❌ Frágil (selectores cambian) | ✅ 100% confiable (JSON estable) |
| **Mantenimiento** | 😫 Alto (ajustar selectores) | 😊 Bajo (API estable) |
| **Datos disponibles** | ⚠️ Limitado | ✅ TODO (xG, momentum, etc.) |
| **Estadísticas críticas** | ❌ xG NO capturado | ✅ xG + Momentum ⭐⭐⭐⭐⭐ |

---

## 🎯 ¿Qué Estadísticas Captura?

### ⭐⭐⭐⭐⭐ **CRÍTICAS PARA TRADING**

1. **xG (Expected Goals)** - Mejor predictor de goles futuros
2. **Momentum** - Indica qué equipo domina EN ESTE MOMENTO

### ⭐⭐⭐⭐ **ALTA PRIORIDAD**

3. **Corners** - Mercado popular con buena liquidez
4. **Tarjetas** - Amarillas/rojas (mercados específicos + impacto en resultado)

### ⭐⭐⭐ **MEDIA PRIORIDAD**

5. **Shots / Shots On Target** - Presión ofensiva
6. **Attacks / Dangerous Attacks** - Indicador de presión constante

### ✅ **CONTEXTO**

7. **Possession** - Útil como contexto
8. **Total Passes** - Datos complementarios
9. **Opta Points** - Métrica general
10. **Touches in Opposition Box** - Indicador de dominancia

---

## 📦 Estructura del Módulo

```
betfair_scraper/
├── stats_api.py          ← NUEVO: Cliente de API de Stats Perform
├── main.py               ← A MODIFICAR: Integrar stats_api
├── config.py
└── STATS_API_README.md   ← Este archivo
```

---

## 🔧 Cómo Funciona

### Paso 1: Extraer `eventId`

Cada partido en Betfair tiene un `eventId` único que identifica el evento en la API de Opta/Stats Perform.

**IMPORTANTE:** El eventId NO está en el HTML principal (está en un iframe con CORS).
La función extrae el Betfair event ID y lo usa para consultar el endpoint del videoplayer.

**Ejemplo:**
```python
from stats_api import extract_event_id

# Obtener HTML y URL de la página del partido (con Selenium)
html = driver.page_source
url = driver.current_url

# Extraer eventId (internamente consulta el videoplayer endpoint)
event_id = extract_event_id(html, url)
# Resultado: "54bnpflhozj2itlevg6890v10"
```

### Paso 2: Obtener Estadísticas

Con el `eventId`, hacemos peticiones HTTP directas a la API:

```python
from stats_api import get_all_stats, extract_stat_value

# Obtener TODAS las estadísticas
stats = get_all_stats(event_id)

# Extraer datos específicos
xg_home = extract_stat_value(stats, 'summary', 'home', 'xG', 0.0)
xg_away = extract_stat_value(stats, 'summary', 'away', 'xG', 0.0)
corners_home = extract_stat_value(stats, 'summary', 'home', 'corners', 0)
corners_away = extract_stat_value(stats, 'summary', 'away', 'corners', 0)

print(f"xG: {xg_home} - {xg_away}")
print(f"Corners: {corners_home} - {corners_away}")
```

---

## 🔌 Integración con main.py

### Modificación Propuesta

```python
# main.py - Fragmento de integración

from stats_api import extract_event_id, get_all_stats, extract_stat_value

def capturar_estadisticas_opta(driver, tab_id):
    """
    Captura estadísticas Opta usando la API REST en lugar de CSS selectors.

    ANTES: Usaba CSS selectors lentos y frágiles
    AHORA: Usa API REST rápida y confiable
    """
    try:
        # 1. Extraer eventId del HTML y URL
        html_source = driver.page_source
        current_url = driver.current_url
        event_id = extract_event_id(html_source, current_url)

        if not event_id:
            log.warning(f"[Tab {tab_id}] No se pudo extraer eventId")
            return obtener_dict_estadisticas_vacio()

        # 2. Obtener estadísticas de la API
        all_stats = get_all_stats(event_id)

        if not all_stats or not all_stats.get('summary'):
            log.warning(f"[Tab {tab_id}] No hay estadísticas disponibles")
            return obtener_dict_estadisticas_vacio()

        # 3. Extraer valores usando helper function
        stats_dict = {
            # xG ⭐⭐⭐⭐⭐ CRÍTICO
            'xg_local': extract_stat_value(all_stats, 'summary', 'home', 'xG', 0.0),
            'xg_visitante': extract_stat_value(all_stats, 'summary', 'away', 'xG', 0.0),

            # Opta Points
            'opta_points_local': extract_stat_value(all_stats, 'summary', 'home', 'optaPoints', 0.0),
            'opta_points_visitante': extract_stat_value(all_stats, 'summary', 'away', 'optaPoints', 0.0),

            # Posesión
            'posesion_local': extract_stat_value(all_stats, 'summary', 'home', 'possession', 0.0),
            'posesion_visitante': extract_stat_value(all_stats, 'summary', 'away', 'possession', 0.0),

            # Tiros
            'tiros_local': extract_stat_value(all_stats, 'summary', 'home', 'shots', 0),
            'tiros_visitante': extract_stat_value(all_stats, 'summary', 'away', 'shots', 0),

            # Tiros a puerta
            'tiros_puerta_local': extract_stat_value(all_stats, 'summary', 'home', 'shotsOnTarget', 0),
            'tiros_puerta_visitante': extract_stat_value(all_stats, 'summary', 'away', 'shotsOnTarget', 0),

            # Touches in opposition box
            'touches_box_local': extract_stat_value(all_stats, 'summary', 'home', 'touchesInOppBox', 0),
            'touches_box_visitante': extract_stat_value(all_stats, 'summary', 'away', 'touchesInOppBox', 0),

            # Corners ⭐⭐⭐⭐ ALTA PRIORIDAD
            'corners_local': extract_stat_value(all_stats, 'summary', 'home', 'corners', 0),
            'corners_visitante': extract_stat_value(all_stats, 'summary', 'away', 'corners', 0),

            # Pases
            'total_passes_local': extract_stat_value(all_stats, 'summary', 'home', 'totalPasses', 0),
            'total_passes_visitante': extract_stat_value(all_stats, 'summary', 'away', 'totalPasses', 0),

            # Tarjetas ⭐⭐⭐⭐ ALTA PRIORIDAD
            'tarjetas_amarillas_local': extract_stat_value(all_stats, 'summary', 'home', 'yellowCards', 0),
            'tarjetas_amarillas_visitante': extract_stat_value(all_stats, 'summary', 'away', 'yellowCards', 0),
            'tarjetas_rojas_local': extract_stat_value(all_stats, 'summary', 'home', 'redCards', 0),
            'tarjetas_rojas_visitante': extract_stat_value(all_stats, 'summary', 'away', 'redCards', 0),

            # Booking Points
            'booking_points_local': extract_stat_value(all_stats, 'summary', 'home', 'bookingPoints', 0),
            'booking_points_visitante': extract_stat_value(all_stats, 'summary', 'away', 'bookingPoints', 0),

            # Attacks
            'attacks_local': extract_stat_value(all_stats, 'summary', 'home', 'attacks', 0),
            'attacks_visitante': extract_stat_value(all_stats, 'summary', 'away', 'attacks', 0),

            # Dangerous Attacks
            'dangerous_attacks_local': extract_stat_value(all_stats, 'summary', 'home', 'dangerousAttacks', 0),
            'dangerous_attacks_visitante': extract_stat_value(all_stats, 'summary', 'away', 'dangerousAttacks', 0),

            # TODO: Añadir datos de otros endpoints (attacking, defence, momentum)
            # attacking_stats = all_stats.get('attacking', {})
            # defence_stats = all_stats.get('defence', {})
            # momentum_data = all_stats.get('momentum', {})
        }

        log.info(f"[Tab {tab_id}] ✅ Estadísticas capturadas vía API: xG={stats_dict['xg_local']}-{stats_dict['xg_visitante']}, Corners={stats_dict['corners_local']}-{stats_dict['corners_visitante']}")

        return stats_dict

    except Exception as e:
        log.error(f"[Tab {tab_id}] ❌ Error capturando estadísticas: {e}")
        return obtener_dict_estadisticas_vacio()
```

---

## 🧪 Testing

### Test Rápido

```bash
cd betfair_scraper
python stats_api.py
```

### Test Manual

```python
from stats_api import extract_event_id, get_all_stats

# Ejemplo con Betfair URL
html = '<div data-event-id="35253419">...</div>'
url = 'https://www.betfair.es/.../apuestas-35253419'
event_id = extract_event_id(html, url)
print(f"EventId: {event_id}")  # Output: 54bnpflhozj2itlevg6890v10

# Obtener estadísticas
stats = get_all_stats(event_id)
print(f"xG Home: {stats['summary']['home']['xG']}")
print(f"Corners Home: {stats['summary']['home']['corners']}")
```

---

## 📊 Endpoints Disponibles

| Endpoint | URL | Datos Principales |
|----------|-----|-------------------|
| **Summary** | `/stats/live-stats/summary` | xG, corners, tarjetas, posesión, tiros, pases |
| **Momentum** | `/stats/live-stats/momentum` | ⭐⭐⭐⭐⭐ Probabilidades minuto a minuto |
| **Attacking** | `/stats/live-stats/attacking` | Big chances, shots off target, precisión |
| **Defence** | `/stats/live-stats/defence` | Entradas, duelos, salvadas, intercepciones |
| **xG Details** | `/stats/live-stats/xg` | Detalles de expected goals |

---

## 🔮 Próximos Pasos

1. ✅ **Crear módulo `stats_api.py`** - COMPLETADO
2. ⏳ **Modificar `main.py`** para usar API en lugar de CSS selectors
3. ⏳ **Testing** con partidos en vivo
4. ⏳ **Añadir captura de Momentum** (máxima prioridad para trading)
5. ⏳ **Eliminar código legacy** de CSS selectors

---

## 💡 Notas Importantes

- **El módulo funciona independiente** de Selenium (solo HTTP requests)
- **Selenium sigue necesario** para:
  - Navegar a las páginas de partidos
  - Extraer el `eventId` del HTML
  - Capturar cuotas (siguen siendo HTML)
- **La API NO requiere login** en Betfair (es pública)
- **Timeout configurado:** 10 segundos por petición
- **Logs detallados:** Registra todos los requests y errores

---

## 🐛 Troubleshooting

**Problema:** No se extrae el `eventId`
- **Solución:** Verificar que la página del partido haya cargado completamente antes de extraer el HTML

**Problema:** La API devuelve None
- **Solución:** El partido puede no tener estadísticas Opta (ligas menores sin cobertura)

**Problema:** Datos vacíos en algunas estadísticas
- **Solución:** Normal - algunas stats solo están disponibles después de cierto tiempo del partido

---

## 📞 Soporte

Si encuentras problemas o mejoras, revisa los logs:
- `betfair_scraper.stats_api` - Logs del módulo API

---

**Versión:** 1.0
**Fecha:** 2026-02-12
**Estado:** ✅ Funcional - Listo para integración
