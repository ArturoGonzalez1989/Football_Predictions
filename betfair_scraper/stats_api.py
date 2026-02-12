#!/usr/bin/env python3
"""
stats_api.py - Cliente para la API de Stats Perform (Opta) de Betfair
======================================================================
Este módulo maneja todas las peticiones a la API de estadísticas de Betfair,
proporcionando datos de Opta (xG, momentum, corners, tarjetas, etc.) en formato JSON.

VENTAJAS sobre CSS selectors:
- 10x más rápido (HTTP vs Selenium)
- 100% confiable (JSON vs HTML parsing)
- Fácil mantenimiento (no depende de cambios en HTML)
- Todos los datos disponibles (xG, momentum, salvadas, etc.)
"""

import re
import json
import logging
import requests
from typing import Dict, Optional, Any

log = logging.getLogger("betfair_scraper.stats_api")

# Constantes de la API
BASE_URL = "https://betfair.cpp.statsperform.com/stats"

# Set global para trackear campos desconocidos ya reportados (evitar spam en logs)
_REPORTED_UNKNOWN_FIELDS = set()
OUTLET_KEY = "1hegv772yrv901291e00xzm9rv"

# Timeout para peticiones HTTP (segundos)
API_TIMEOUT = 10


def extract_event_id(html_source: str, current_url: str = None) -> Optional[str]:
    """
    Extrae el eventId de Opta del HTML de la página de Betfair.

    El eventId NO está en el HTML principal (está en un iframe con CORS).
    En su lugar, extraemos el Betfair event ID y lo usamos para obtener
    el Opta eventId desde el endpoint del videoplayer.

    Args:
        html_source: Código HTML de la página del partido
        current_url: URL actual de la página (para extraer el Betfair event ID)

    Returns:
        str: El eventId extraído, o None si no se encuentra

    Example:
        >>> html = '<div data-event-id="35253419">...</div>'
        >>> url = 'https://www.betfair.es/.../apuestas-35253419'
        >>> extract_event_id(html, url)
        '54bnpflhozj2itlevg6890v10'
    """
    # PASO 1: Extraer el Betfair event ID del HTML o URL
    betfair_event_id = None

    # Intentar desde atributo data-event-id
    match = re.search(r'data-event-id="(\d+)"', html_source) or re.search(r'eventid="(\d+)"', html_source, re.IGNORECASE)
    if match:
        betfair_event_id = match.group(1)
        log.debug(f"Betfair event ID extraído del HTML: {betfair_event_id}")

    # Si no se encuentra, intentar desde la URL
    if not betfair_event_id and current_url:
        match = re.search(r'apuestas-(\d+)', current_url)
        if match:
            betfair_event_id = match.group(1)
            log.debug(f"Betfair event ID extraído de la URL: {betfair_event_id}")

    if not betfair_event_id:
        log.warning("No se pudo extraer el Betfair event ID del HTML ni de la URL")
        return None

    # PASO 2: Obtener el Opta eventId desde el videoplayer endpoint
    try:
        videoplayer_url = f"https://videoplayer.betfair.es/GetPlayer.do?eID={betfair_event_id}&contentType=viz&contentView=mstats"
        log.debug(f"Consultando videoplayer: {videoplayer_url}")

        response = requests.get(videoplayer_url, timeout=API_TIMEOUT)
        response.raise_for_status()

        # Buscar el eventId en el config del videoplayer
        # Puede aparecer como providerEventId, performMCCFixtureUUID, o streamUUID
        # Formato: JavaScript object literal (key=value) o JSON (key: value)
        content = response.text

        # Buscar patrones de eventId de Opta (20-30 caracteres alfanuméricos)
        # Soporta tanto formato JavaScript (=) como JSON (:)
        opta_id_match = re.search(
            r'(?:providerEventId|performMCCFixtureUUID|streamUUID)\s*[=:]\s*["\']?([a-z0-9]{20,30})["\']?',
            content,
            re.IGNORECASE
        )

        if opta_id_match:
            event_id = opta_id_match.group(1)
            log.info(f"EventId de Opta extraído: {event_id}")
            return event_id
        else:
            log.warning(f"No se encontró eventId de Opta en la respuesta del videoplayer")
            return None

    except requests.exceptions.RequestException as e:
        log.error(f"Error consultando videoplayer endpoint: {e}")
        return None
    except Exception as e:
        log.error(f"Error inesperado extrayendo eventId: {e}")
        return None


def get_summary_stats(event_id: str, stage: str = "halfTime") -> Optional[Dict[str, Any]]:
    """
    Obtiene estadísticas generales del partido (xG, corners, tarjetas, posesión, etc.)

    Args:
        event_id: ID del evento de Opta
        stage: Estado del partido ("preview", "halfTime", "fullTime", etc.)

    Returns:
        dict: Estadísticas del partido, o None si falla

    Estructura de retorno:
        {
            'home': {
                'xG': 1.10,
                'possession': 41.3,
                'shots': 8,
                'shotsOnTarget': 3,
                'corners': 1,
                'yellowCards': 0,
                'redCards': 0,
                'totalPasses': 203,
                'optaPoints': 87.0,
                ...
            },
            'away': { ... }
        }
    """
    url = f"{BASE_URL}/live-stats/summary"
    params = {
        'eventId': event_id,
        'outletkey': OUTLET_KEY,
        'hideHeader': 'false',
        'noredirect': 'true',
        'stage': stage
    }

    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        # La API devuelve HTML con JSON embebido
        # Necesitamos parsear el contenido
        data = parse_stats_response(response.text, 'summary')

        if data:
            log.debug(f"✅ Summary stats obtenidas para {event_id}")

        return data

    except requests.exceptions.RequestException as e:
        log.error(f"❌ Error obteniendo summary stats: {e}")
        return None


def get_momentum_data(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene datos de momentum del partido (probabilidades minuto a minuto).

    ⭐⭐⭐⭐⭐ CRÍTICO PARA TRADING - Indica qué equipo domina EN ESTE MOMENTO

    Args:
        event_id: ID del evento de Opta

    Returns:
        dict: Datos de momentum, o None si falla
    """
    url = f"{BASE_URL}/live-stats/momentum"
    params = {
        'eventId': event_id,
        'outletkey': OUTLET_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = parse_stats_response(response.text, 'momentum')

        if data:
            log.debug(f"✅ Momentum data obtenida para {event_id}")

        return data

    except requests.exceptions.RequestException as e:
        log.error(f"❌ Error obteniendo momentum: {e}")
        return None


def get_attacking_stats(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene estadísticas de ataque (tiros, precisión, grandes ocasiones, etc.)

    Args:
        event_id: ID del evento de Opta

    Returns:
        dict: Estadísticas de ataque, o None si falla
    """
    url = f"{BASE_URL}/live-stats/attacking"
    params = {
        'eventId': event_id,
        'outletkey': OUTLET_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = parse_stats_response(response.text, 'attacking')

        if data:
            log.debug(f"✅ Attacking stats obtenidas para {event_id}")

        return data

    except requests.exceptions.RequestException as e:
        log.error(f"❌ Error obteniendo attacking stats: {e}")
        return None


def get_defence_stats(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene estadísticas defensivas (entradas, duelos, salvadas, etc.)

    Args:
        event_id: ID del evento de Opta

    Returns:
        dict: Estadísticas defensivas, o None si falla
    """
    url = f"{BASE_URL}/live-stats/defence"
    params = {
        'eventId': event_id,
        'outletkey': OUTLET_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = parse_stats_response(response.text, 'defence')

        if data:
            log.debug(f"✅ Defence stats obtenidas para {event_id}")

        return data

    except requests.exceptions.RequestException as e:
        log.error(f"❌ Error obteniendo defence stats: {e}")
        return None


def get_xg_details(event_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene detalles de xG (Expected Goals) del partido.

    ⭐⭐⭐⭐⭐ CRÍTICO - Mejor predictor de goles futuros que el marcador actual

    Args:
        event_id: ID del evento de Opta

    Returns:
        dict: Datos detallados de xG, o None si falla
    """
    url = f"{BASE_URL}/live-stats/xg"
    params = {
        'eventId': event_id,
        'outletkey': OUTLET_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()

        data = parse_stats_response(response.text, 'xg')

        if data:
            log.debug(f"✅ xG details obtenidos para {event_id}")

        return data

    except requests.exceptions.RequestException as e:
        log.error(f"❌ Error obteniendo xG details: {e}")
        return None


def parse_stats_response(html_content: str, stats_type: str) -> Optional[Dict[str, Any]]:
    """
    Parsea la respuesta HTML de la API y extrae los datos JSON.

    La API de Stats Perform devuelve HTML con JavaScript embebido que contiene
    los datos en formato JSON. Esta función extrae esos datos.

    Args:
        html_content: Contenido HTML de la respuesta
        stats_type: Tipo de estadísticas ('summary', 'momentum', etc.)

    Returns:
        dict: Datos parseados, o None si falla
    """
    try:
        # Buscar patrones comunes de datos en el HTML
        # Por ejemplo: var data = {...}

        # Para summary: buscar estadísticas directas en el HTML
        if stats_type == 'summary':
            return parse_summary_html(html_content)
        elif stats_type == 'momentum':
            return parse_momentum_html(html_content)
        elif stats_type == 'attacking':
            return parse_attacking_html(html_content)
        elif stats_type == 'defence':
            return parse_defence_html(html_content)
        elif stats_type == 'xg':
            return parse_xg_html(html_content)

        return None

    except Exception as e:
        log.error(f"❌ Error parseando respuesta {stats_type}: {e}")
        return None


def _detect_unknown_fields(api_data: Dict[str, Any], known_fields: set, endpoint_name: str):
    """
    Detecta campos disponibles en la API que no están en nuestra whitelist.

    Args:
        api_data: Dict con datos crudos de la API (home/away)
        known_fields: Set de campos conocidos que ya capturamos
        endpoint_name: Nombre del endpoint para logging (ej: "summary", "attacking")
    """
    global _REPORTED_UNKNOWN_FIELDS

    if not api_data:
        return

    # Obtener todos los campos disponibles en la API
    available_fields = set(api_data.keys())

    # Campos desconocidos = disponibles - conocidos
    unknown_fields = available_fields - known_fields

    # Filtrar campos que ya reportamos antes
    new_unknown_fields = unknown_fields - _REPORTED_UNKNOWN_FIELDS

    if new_unknown_fields:
        # Reportar como INFO (no WARNING para no alarmar innecesariamente)
        log.info(
            f"📊 [{endpoint_name}] Campos NUEVOS detectados en API: {sorted(new_unknown_fields)}"
        )
        log.info(
            f"💡 Tip: Si estos campos son útiles, añádelos a la whitelist en parse_{endpoint_name}_html()"
        )

        # Añadir al set de reportados
        _REPORTED_UNKNOWN_FIELDS.update(new_unknown_fields)


def parse_summary_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Parsea el HTML de summary para extraer estadísticas clave.

    Los datos están en un objeto JSON dentro de un tag <script id="__NEXT_DATA__">
    """
    try:
        # Buscar el script con los datos JSON
        pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            log.warning("No se encontró __NEXT_DATA__ en la respuesta")
            return None

        # Parsear el JSON
        data = json.loads(match.group(1))

        # Navegar a las estadísticas
        props = data.get('props', {}).get('pageProps', {})
        stats = props.get('teamStatsSummaryLv', {})

        if not stats:
            log.warning("No se encontró teamStatsSummaryLv en los datos")
            return None

        # Convertir strings a números
        home = stats.get('home', {})
        away = stats.get('away', {})

        def to_float(val):
            """Convierte a float, retorna None si falla"""
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        def to_int(val):
            """Convierte a int, retorna None si falla"""
            try:
                return int(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        # Whitelist de campos conocidos (para detección de nuevos campos)
        # Nota: usamos nombres de la API, no los nombres que usamos en result
        known_fields_api = {
            'goals', 'goalsConceded', 'shots', 'shotsOnTarget', 'corners',
            'possession', 'touches', 'xg', 'yellowCards', 'redCards',
            'bookingPoints', 'passes', 'attacks', 'dangerousAttacks',
            'foulsConceded', 'touchesInOppBox', 'optaPoints'
        }

        # Detectar campos nuevos en la API
        _detect_unknown_fields(home, known_fields_api, 'summary')

        # Construir dict con datos convertidos
        result = {
            'home': {
                'goals': to_int(home.get('goals')),
                'goalsConceded': to_int(home.get('goalsConceded')),
                'shots': to_int(home.get('shots')),
                'shotsOnTarget': to_int(home.get('shotsOnTarget')),
                'corners': to_int(home.get('corners')),
                'possession': to_float(home.get('possession')),
                'touches': to_int(home.get('touches')),
                'xG': to_float(home.get('xg')),  # API usa 'xg' minúscula
                'yellowCards': to_int(home.get('yellowCards')),
                'redCards': to_int(home.get('redCards')),
                'bookingPoints': to_int(home.get('bookingPoints')),
                'totalPasses': to_int(home.get('passes')),  # API usa 'passes'
                'attacks': to_int(home.get('attacks')),
                'dangerousAttacks': to_int(home.get('dangerousAttacks')),
                'foulsConceded': to_int(home.get('foulsConceded')),
                'touchesInOppBox': to_int(home.get('touchesInOppBox')),
                'optaPoints': to_float(home.get('optaPoints')),
            },
            'away': {
                'goals': to_int(away.get('goals')),
                'goalsConceded': to_int(away.get('goalsConceded')),
                'shots': to_int(away.get('shots')),
                'shotsOnTarget': to_int(away.get('shotsOnTarget')),
                'corners': to_int(away.get('corners')),
                'possession': to_float(away.get('possession')),
                'touches': to_int(away.get('touches')),
                'xG': to_float(away.get('xg')),
                'yellowCards': to_int(away.get('yellowCards')),
                'redCards': to_int(away.get('redCards')),
                'bookingPoints': to_int(away.get('bookingPoints')),
                'totalPasses': to_int(away.get('passes')),
                'attacks': to_int(away.get('attacks')),
                'dangerousAttacks': to_int(away.get('dangerousAttacks')),
                'foulsConceded': to_int(away.get('foulsConceded')),
                'touchesInOppBox': to_int(away.get('touchesInOppBox')),
                'optaPoints': to_float(away.get('optaPoints')),
            },
            'coverage': stats.get('coverage'),
            'source': stats.get('source')
        }

        return result

    except json.JSONDecodeError as e:
        log.error(f"Error parseando JSON: {e}")
        return None
    except Exception as e:
        log.error(f"Error inesperado en parse_summary_html: {e}")
        return None


def parse_momentum_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Parsea datos de momentum del HTML.

    El momentum muestra probabilidades minuto a minuto de qué equipo domina.
    Es CRÍTICO para trading en vivo.
    """
    try:
        # Buscar el script con los datos JSON
        pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            log.warning("No se encontró __NEXT_DATA__ en momentum")
            return None

        data = json.loads(match.group(1))
        props = data.get('props', {}).get('pageProps', {})

        # Momentum puede venir en diferentes estructuras
        momentum_data = props.get('momentum', {}) or props.get('momentumData', {}) or props.get('chartData', {})

        if not momentum_data:
            log.debug("No se encontró datos de momentum")
            return None

        # Detectar campos nuevos si momentum_data es un dict
        if isinstance(momentum_data, dict):
            known_fields_api = {
                'home', 'away', 'time', 'minute', 'period', 'homeValue',
                'awayValue', 'timestamp', 'chartPoints', 'dataPoints'
            }
            _detect_unknown_fields(momentum_data, known_fields_api, 'momentum')

        # Retornar los datos tal cual (puede ser array o dict según la API)
        result = {
            'momentum_data': momentum_data,
            'available': momentum_data is not None and len(momentum_data) > 0
        }

        return result

    except json.JSONDecodeError as e:
        log.error(f"Error parseando JSON momentum: {e}")
        return None
    except Exception as e:
        log.error(f"Error inesperado en parse_momentum_html: {e}")
        return None


def parse_attacking_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Parsea estadísticas de ataque del HTML.

    Campos esperados: bigChances, shotsOffTarget, blockedShots, hitWoodwork,
    shootingAccuracy, crosses, successfulCrossesPct, etc.
    """
    try:
        # Buscar el script con los datos JSON
        pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            log.warning("No se encontró __NEXT_DATA__ en attacking")
            return None

        data = json.loads(match.group(1))
        props = data.get('props', {}).get('pageProps', {})
        stats = props.get('teamStatsAttackingLv', {})

        if not stats:
            log.debug("No se encontró teamStatsAttackingLv")
            return None

        home = stats.get('home', {})
        away = stats.get('away', {})

        def to_float(val):
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        def to_int(val):
            try:
                return int(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        # Whitelist de campos conocidos
        known_fields_api = {
            'bigChances', 'shotsOffTarget', 'blockedShots', 'hitWoodwork',
            'shootingAccuracy', 'crosses', 'successfulCrossesPct',
            'successfulCrosses', 'shotsInsideBox', 'shotsOutsideBox',
            'headedShots', 'leftFootShots', 'rightFootShots', 'otherShots',
            'shotsFromCentreBox', 'shotsFromLeftChannel', 'shotsFromRightChannel'
        }

        # Detectar campos nuevos
        _detect_unknown_fields(home, known_fields_api, 'attacking')

        # Construir resultado
        result = {
            'home': {
                'bigChances': to_int(home.get('bigChances')),
                'shotsOffTarget': to_int(home.get('shotsOffTarget')),
                'blockedShots': to_int(home.get('blockedShots')),
                'hitWoodwork': to_int(home.get('hitWoodwork')),
                'shootingAccuracy': to_float(home.get('shootingAccuracy')),
                'crosses': to_int(home.get('crosses')),
                'successfulCrossesPct': to_float(home.get('successfulCrossesPct')),
                'successfulCrosses': to_int(home.get('successfulCrosses')),
                'shotsInsideBox': to_int(home.get('shotsInsideBox')),
                'shotsOutsideBox': to_int(home.get('shotsOutsideBox')),
            },
            'away': {
                'bigChances': to_int(away.get('bigChances')),
                'shotsOffTarget': to_int(away.get('shotsOffTarget')),
                'blockedShots': to_int(away.get('blockedShots')),
                'hitWoodwork': to_int(away.get('hitWoodwork')),
                'shootingAccuracy': to_float(away.get('shootingAccuracy')),
                'crosses': to_int(away.get('crosses')),
                'successfulCrossesPct': to_float(away.get('successfulCrossesPct')),
                'successfulCrosses': to_int(away.get('successfulCrosses')),
                'shotsInsideBox': to_int(away.get('shotsInsideBox')),
                'shotsOutsideBox': to_int(away.get('shotsOutsideBox')),
            }
        }

        return result

    except json.JSONDecodeError as e:
        log.error(f"Error parseando JSON attacking: {e}")
        return None
    except Exception as e:
        log.error(f"Error inesperado en parse_attacking_html: {e}")
        return None


def parse_defence_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Parsea estadísticas defensivas del HTML.

    Campos esperados: tackles, tackleSuccessPct, duelsWon, aerialDuelsWon,
    clearances, saves, interceptions, etc.
    """
    try:
        # Buscar el script con los datos JSON
        pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            log.warning("No se encontró __NEXT_DATA__ en defence")
            return None

        data = json.loads(match.group(1))
        props = data.get('props', {}).get('pageProps', {})
        stats = props.get('teamStatsDefenceLv', {})

        if not stats:
            log.debug("No se encontró teamStatsDefenceLv")
            return None

        home = stats.get('home', {})
        away = stats.get('away', {})

        def to_float(val):
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        def to_int(val):
            try:
                return int(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        # Whitelist de campos conocidos
        known_fields_api = {
            'tackles', 'tackleSuccessPct', 'duelsWon', 'aerialDuelsWon',
            'clearances', 'saves', 'interceptions', 'blocks', 'offsides',
            'goalsConceded', 'goalkeeperSaves', 'lastManTackles',
            'errorLeadToGoal', 'errorLeadToShot', 'penaltiesConceded'
        }

        # Detectar campos nuevos
        _detect_unknown_fields(home, known_fields_api, 'defence')

        # Construir resultado
        result = {
            'home': {
                'tackles': to_int(home.get('tackles')),
                'tackleSuccessPct': to_float(home.get('tackleSuccessPct')),
                'duelsWon': to_int(home.get('duelsWon')),
                'aerialDuelsWon': to_int(home.get('aerialDuelsWon')),
                'clearances': to_int(home.get('clearances')),
                'saves': to_int(home.get('saves')),
                'interceptions': to_int(home.get('interceptions')),
                'blocks': to_int(home.get('blocks')),
                'offsides': to_int(home.get('offsides')),
            },
            'away': {
                'tackles': to_int(away.get('tackles')),
                'tackleSuccessPct': to_float(away.get('tackleSuccessPct')),
                'duelsWon': to_int(away.get('duelsWon')),
                'aerialDuelsWon': to_int(away.get('aerialDuelsWon')),
                'clearances': to_int(away.get('clearances')),
                'saves': to_int(away.get('saves')),
                'interceptions': to_int(away.get('interceptions')),
                'blocks': to_int(away.get('blocks')),
                'offsides': to_int(away.get('offsides')),
            }
        }

        return result

    except json.JSONDecodeError as e:
        log.error(f"Error parseando JSON defence: {e}")
        return None
    except Exception as e:
        log.error(f"Error inesperado en parse_defence_html: {e}")
        return None


def parse_xg_html(html: str) -> Optional[Dict[str, Any]]:
    """
    Parsea detalles de xG del HTML.

    Este endpoint puede contener breakdown detallado de xG por situación
    (open play, set pieces, penalties, etc.)
    """
    try:
        # Buscar el script con los datos JSON
        pattern = r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            log.warning("No se encontró __NEXT_DATA__ en xG")
            return None

        data = json.loads(match.group(1))
        props = data.get('props', {}).get('pageProps', {})
        stats = props.get('teamStatsXgLv', {}) or props.get('xgData', {})

        if not stats:
            log.debug("No se encontró teamStatsXgLv ni xgData")
            return None

        home = stats.get('home', {})
        away = stats.get('away', {})

        def to_float(val):
            try:
                return float(val) if val is not None else None
            except (ValueError, TypeError):
                return None

        # Whitelist de campos conocidos
        known_fields_api = {
            'xG', 'xgOpenPlay', 'xgSetPlay', 'xgPenalty',
            'xgShots', 'xgGoals', 'xgPerShot'
        }

        # Detectar campos nuevos
        _detect_unknown_fields(home, known_fields_api, 'xg')

        # Construir resultado
        result = {
            'home': {
                'xG': to_float(home.get('xG') or home.get('xg')),
                'xgOpenPlay': to_float(home.get('xgOpenPlay')),
                'xgSetPlay': to_float(home.get('xgSetPlay')),
                'xgPenalty': to_float(home.get('xgPenalty')),
            },
            'away': {
                'xG': to_float(away.get('xG') or away.get('xg')),
                'xgOpenPlay': to_float(away.get('xgOpenPlay')),
                'xgSetPlay': to_float(away.get('xgSetPlay')),
                'xgPenalty': to_float(away.get('xgPenalty')),
            }
        }

        return result

    except json.JSONDecodeError as e:
        log.error(f"Error parseando JSON xG: {e}")
        return None
    except Exception as e:
        log.error(f"Error inesperado en parse_xg_html: {e}")
        return None


def get_all_stats(event_id: str) -> Dict[str, Any]:
    """
    Obtiene TODAS las estadísticas disponibles para un partido.

    Esta es la función principal que debe usar main.py.

    Args:
        event_id: ID del evento de Opta

    Returns:
        dict: Todas las estadísticas del partido

    Example:
        >>> stats = get_all_stats("cy3rapvvia3y1s6nrg776z85w")
        >>> print(stats['summary']['home']['xG'])
        1.10
    """
    log.info(f"📊 Obteniendo todas las estadísticas para eventId: {event_id}")

    all_stats = {
        'event_id': event_id,
        'summary': None,
        'momentum': None,
        'attacking': None,
        'defence': None,
        'xg': None
    }

    # Obtener cada tipo de estadística
    all_stats['summary'] = get_summary_stats(event_id)
    all_stats['momentum'] = get_momentum_data(event_id)
    all_stats['attacking'] = get_attacking_stats(event_id)
    all_stats['defence'] = get_defence_stats(event_id)
    all_stats['xg'] = get_xg_details(event_id)

    # Contar cuántas se obtuvieron exitosamente
    success_count = sum(1 for v in all_stats.values() if v is not None and v != event_id)
    log.info(f"✅ Estadísticas obtenidas: {success_count}/5 endpoints")

    return all_stats


# ── Función auxiliar para extraer datos del all_stats ───────────────────────

def extract_stat_value(all_stats: Dict[str, Any], category: str, team: str, stat: str, default=None):
    """
    Extrae un valor específico de las estadísticas.

    Args:
        all_stats: Dict retornado por get_all_stats()
        category: Categoría ('summary', 'attacking', 'defence', etc.)
        team: 'home' o 'away'
        stat: Nombre de la estadística (ej: 'xG', 'corners', etc.)
        default: Valor por defecto si no se encuentra

    Returns:
        El valor de la estadística, o default si no existe

    Example:
        >>> xg_home = extract_stat_value(stats, 'summary', 'home', 'xG', 0.0)
    """
    try:
        if category in all_stats and all_stats[category]:
            if team in all_stats[category]:
                return all_stats[category][team].get(stat, default)
    except (KeyError, TypeError):
        pass

    return default


def extract_iframe_stats(driver, betfair_event_id: str) -> dict:
    """
    Extrae estadísticas del iframe de visualización cuando no hay Opta disponible.

    Fallback para partidos sin eventId de Opta. Navega al iframe de estadísticas
    y scrape los valores directamente del HTML renderizado.

    Args:
        driver: Instancia de Selenium WebDriver
        betfair_event_id: ID del evento en Betfair (extraído de URL o HTML)

    Returns:
        dict: Diccionario con estadísticas extraídas (mismo formato que get_all_stats)
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException

    stats = {}

    try:
        # Construir URL del iframe
        iframe_url = (
            f"https://videoplayer.betfair.es/GetPlayer.do"
            f"?eID={betfair_event_id}"
            f"&contentType=viz&contentView=mstats"
            f"&statsToggle=hide&contentOnly=true"
        )

        log.debug(f"  → Extrayendo stats del iframe: {iframe_url}")

        # Guardar ventana actual
        original_window = driver.current_window_handle

        # Abrir iframe en nueva pestaña (evita perder contexto del partido principal)
        driver.execute_script(f"window.open('{iframe_url}', '_blank');")

        # Cambiar a la nueva pestaña
        new_window = [w for w in driver.window_handles if w != original_window][0]
        driver.switch_to.window(new_window)

        # Esperar a que carguen las stats (máximo 10s)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[class*='stat']")))

        # Helper para extraer stats de formato "X LABEL Y"
        def extract_dual_stat(label_text):
            try:
                elems = driver.find_elements(By.XPATH, f"//*[contains(text(), '{label_text}')]")
                if not elems:
                    return None, None
                parent = elems[0].find_element(By.XPATH, "..")
                nums = parent.find_elements(By.TAG_NAME, "div")
                if len(nums) >= 2:
                    home = nums[0].text.strip()
                    away = nums[-1].text.strip()
                    return home, away
            except Exception:
                pass
            return None, None

        # Helper para extraer stats de porcentaje "X% LABEL Y%"
        def extract_percentage_stat(label_text):
            try:
                elems = driver.find_elements(By.XPATH, f"//*[contains(text(), '{label_text}')]")
                if not elems:
                    return None, None
                parent = elems[0].find_element(By.XPATH, "..")
                # Buscar elementos que contengan "%"
                pcts = parent.find_elements(By.XPATH, ".//*[contains(text(), '%')]")
                if len(pcts) >= 2:
                    home = pcts[0].text.strip().replace("%", "")
                    away = pcts[1].text.strip().replace("%", "")
                    return home, away
            except Exception:
                pass
            return None, None

        # Extraer estadísticas disponibles en el iframe
        # Mapeo de labels del iframe a campos del CSV

        # Stats básicas (numéricas)
        home_shots_on, away_shots_on = extract_dual_stat("Shots on target")
        home_shots_off, away_shots_off = extract_dual_stat("Shots off target")
        home_shots_blocked, away_shots_blocked = extract_dual_stat("Shots blocked")
        home_corners, away_corners = extract_dual_stat("Corner kicks")
        home_free_kicks, away_free_kicks = extract_dual_stat("Free kicks")
        home_offsides, away_offsides = extract_dual_stat("Offsides")
        home_goal_kicks, away_goal_kicks = extract_dual_stat("Goal kicks")
        home_saves, away_saves = extract_dual_stat("Saves")
        home_throw_ins, away_throw_ins = extract_dual_stat("Throw-ins")
        home_fouls, away_fouls = extract_dual_stat("Fouls")

        # Tarjetas (del componente "Cards")
        try:
            cards_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'Cards')]")
            cards_parent = cards_elem.find_element(By.XPATH, "..")
            card_imgs = cards_parent.find_elements(By.TAG_NAME, "img")
            # Contar amarillas y rojas por posición (las primeras son local, las últimas visitante)
            # Este es un aproximado - puede necesitar ajuste según el HTML real
            home_yellow = cards_parent.find_elements(By.XPATH, ".//img[contains(@src, 'yellow')]")[0:1]
            away_yellow = cards_parent.find_elements(By.XPATH, ".//img[contains(@src, 'yellow')]")[1:2]
            home_red = cards_parent.find_elements(By.XPATH, ".//img[contains(@src, 'red')]")[0:1]
            away_red = cards_parent.find_elements(By.XPATH, ".//img[contains(@src, 'red')]")[1:2]
        except Exception:
            home_yellow = away_yellow = home_red = away_red = None

        # Stats de porcentaje
        home_poss, away_poss = extract_percentage_stat("Ball possession")
        home_dangerous, away_dangerous = extract_percentage_stat("Time in dangerous attack")

        # Ataques peligrosos (dangerous attacks)
        try:
            dangerous_elem = driver.find_element(By.XPATH, "//*[contains(text(), 'Dangerous Attack')]")
            dangerous_parent = dangerous_elem.find_element(By.XPATH, "..")
            nums = dangerous_parent.find_elements(By.CSS_SELECTOR, "[class*='number'], div")
            if len(nums) >= 2:
                home_attacks = nums[0].text.strip()
                away_attacks = nums[-1].text.strip()
            else:
                home_attacks = away_attacks = None
        except Exception:
            home_attacks = away_attacks = None

        # Construir diccionario de stats (mapeo a campos del CSV)
        stats = {
            # Básicas disponibles en iframe
            "tiros_puerta_local": home_shots_on or "",
            "tiros_puerta_visitante": away_shots_on or "",
            "corners_local": home_corners or "",
            "corners_visitante": away_corners or "",
            "posesion_local": home_poss or "",
            "posesion_visitante": away_poss or "",
            "fouls_conceded_local": home_fouls or "",
            "fouls_conceded_visitante": away_fouls or "",
            "saves_local": home_saves or "",
            "saves_visitante": away_saves or "",
            "dangerous_attacks_local": home_attacks or "",
            "dangerous_attacks_visitante": away_attacks or "",

            # Calcular tiros totales (on + off + blocked)
            "tiros_local": "",
            "tiros_visitante": "",
        }

        # Calcular tiros totales si tenemos los componentes
        try:
            if home_shots_on and home_shots_off and home_shots_blocked:
                stats["tiros_local"] = str(int(home_shots_on) + int(home_shots_off) + int(home_shots_blocked))
            if away_shots_on and away_shots_off and away_shots_blocked:
                stats["tiros_visitante"] = str(int(away_shots_on) + int(away_shots_off) + int(away_shots_blocked))
        except (ValueError, TypeError):
            pass

        # Cerrar pestaña del iframe y volver a la original
        driver.close()
        driver.switch_to.window(original_window)

        captured_count = sum(1 for v in stats.values() if v != "")
        log.info(f"  ✓ Estadísticas del iframe capturadas: {captured_count} campos")

    except TimeoutException:
        log.warning("  × Timeout esperando estadísticas del iframe")
        driver.switch_to.window(original_window)
    except Exception as e:
        log.error(f"  × Error extrayendo stats del iframe: {e}")
        try:
            driver.switch_to.window(original_window)
        except Exception:
            pass

    return stats


if __name__ == "__main__":
    """
    Test del módulo stats_api.

    Uso:
        python stats_api.py
    """
    import sys

    # Configurar logging para tests
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    # Test con eventId de ejemplo (Chapecoense - Coritiba)
    test_event_id = "d1m0guhs75k0vu39dg7qoanmc"

    print(f"\n{'='*70}")
    print(f"TEST: Obtener estadísticas para eventId: {test_event_id}")
    print(f"{'='*70}\n")

    # Obtener todas las estadísticas
    stats = get_all_stats(test_event_id)

    # Mostrar resultados
    print("\n📊 RESULTADOS:\n")

    if stats['summary']:
        print("✅ Summary:")
        print(f"   Home xG: {extract_stat_value(stats, 'summary', 'home', 'xG', 'N/A')}")
        print(f"   Away xG: {extract_stat_value(stats, 'summary', 'away', 'xG', 'N/A')}")
        print(f"   Home Corners: {extract_stat_value(stats, 'summary', 'home', 'corners', 'N/A')}")
        print(f"   Away Corners: {extract_stat_value(stats, 'summary', 'away', 'corners', 'N/A')}")
    else:
        print("❌ Summary: No disponible")

    if stats['momentum']:
        print("\n✅ Momentum: Datos obtenidos")
    else:
        print("\n❌ Momentum: No disponible")

    print(f"\n{'='*70}\n")
