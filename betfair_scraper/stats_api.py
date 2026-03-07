#!/usr/bin/env python3
"""
stats_api.py - Cliente para la API de Stats Perform (Opta) de Betfair
======================================================================
Usa la API REST de api.performfeeds.com con Referer-based auth.
Obtiene xG, momentum, corners, tarjetas, posesión, etc. en formato JSON.

Reescrito 2026-03-07: migrado de __NEXT_DATA__ (roto) a api.performfeeds.com.
"""

import re
import json
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Any

log = logging.getLogger("betfair_scraper.stats_api")

# Constantes
OUTLET_KEY = "1hegv772yrv901291e00xzm9rv"
API_BASE = "https://api.performfeeds.com/soccerdata"
API_TIMEOUT = 5

# Headers para autenticar vía Referer (sin Bearer token)
_API_HEADERS = {
    "Referer": "https://betfair.cpp.statsperform.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def extract_event_id(html_source: str, current_url: str = None) -> Optional[str]:
    """
    Extrae el eventId de Opta del HTML de la página de Betfair.

    Flujo: Betfair event ID → videoplayer endpoint → Opta eventId.
    """
    betfair_event_id = None

    match = re.search(r'data-event-id="(\d+)"', html_source) or \
            re.search(r'eventid="(\d+)"', html_source, re.IGNORECASE)
    if match:
        betfair_event_id = match.group(1)

    if not betfair_event_id and current_url:
        match = re.search(r'apuestas-(\d+)', current_url)
        if match:
            betfair_event_id = match.group(1)

    if not betfair_event_id:
        log.warning("No se pudo extraer el Betfair event ID del HTML ni de la URL")
        return None

    try:
        videoplayer_url = f"https://videoplayer.betfair.es/GetPlayer.do?eID={betfair_event_id}&contentType=viz&contentView=mstats"
        response = requests.get(videoplayer_url, timeout=API_TIMEOUT)
        response.raise_for_status()

        opta_id_match = re.search(
            r'(?:providerEventId|performMCCFixtureUUID|streamUUID)\s*[=:]\s*["\']?([a-z0-9]{20,30})["\']?',
            response.text, re.IGNORECASE
        )

        if opta_id_match:
            event_id = opta_id_match.group(1)
            log.info(f"EventId de Opta extraído: {event_id}")
            return event_id
        else:
            log.warning("No se encontró eventId de Opta en la respuesta del videoplayer")
            return None

    except requests.exceptions.RequestException as e:
        log.error(f"Error consultando videoplayer endpoint: {e}")
        return None
    except Exception as e:
        log.error(f"Error inesperado extrayendo eventId: {e}")
        return None


# ── Helpers ────────────────────────────────────────────────────────────────

def _to_float(val):
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def _to_int(val):
    try:
        return int(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def _team_stats_dict(stat_list: list) -> Dict[str, str]:
    """Convierte la lista [{type, value}, ...] de performfeeds a un dict."""
    return {s["type"]: s["value"] for s in stat_list if "type" in s and "value" in s}


def _api_get(endpoint: str, event_id: str, extra_params: str = "") -> Optional[dict]:
    """GET genérico a api.performfeeds.com."""
    url = f"{API_BASE}/{endpoint}/{OUTLET_KEY}/{event_id}?_fmt=json&_rt=c{extra_params}"
    try:
        r = requests.get(url, headers=_API_HEADERS, timeout=API_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        log.error(f"Error en {endpoint}: {e}")
        return None
    except Exception as e:
        log.error(f"Error inesperado en {endpoint}: {e}")
        return None


# ── Fetchers individuales ──────────────────────────────────────────────────

def _fetch_matchstats(event_id: str) -> Optional[dict]:
    """matchstats → summary + attacking + defence data."""
    raw = _api_get("matchstats", event_id, "&detailed=yes")
    if not raw or "liveData" not in raw:
        return None

    lineup = raw["liveData"].get("lineUp", [])
    contestants = raw.get("matchInfo", {}).get("contestant", [])

    # Determinar home/away por matchInfo.contestant[].position
    home_id = away_id = None
    for c in contestants:
        if c.get("position") == "home":
            home_id = c["id"]
        elif c.get("position") == "away":
            away_id = c["id"]

    home_stats = {}
    away_stats = {}
    for team in lineup:
        cid = team.get("contestantId")
        sd = _team_stats_dict(team.get("stat", []))
        if cid == home_id:
            home_stats = sd
        elif cid == away_id:
            away_stats = sd

    def _build(s):
        accurate = _to_int(s.get("accuratePass"))
        total = _to_int(s.get("totalPass"))
        pass_pct = round(accurate / total * 100, 1) if accurate and total and total > 0 else None
        return {
            # summary
            "shots": _to_int(s.get("totalScoringAtt")),
            "shotsOnTarget": _to_int(s.get("ontargetScoringAtt")),
            "corners": _to_int(s.get("wonCorners")),
            "possession": _to_float(s.get("possessionPercentage")),
            "touches": _to_int(s.get("touches")),
            "yellowCards": _to_int(s.get("totalYellowCard")),
            "redCards": _to_int(s.get("totalRedCard")),
            "totalPasses": total,
            "foulsConceded": _to_int(s.get("fkFoulLost")),
            "attacks": _to_int(s.get("totalAttAssist")),
            "dangerousAttacks": _to_int(s.get("attemptsIbox")),
            "goalKicks": _to_int(s.get("accurateGoalKicks")),
            "throwIns": _to_int(s.get("totalThrows")),
            "passSuccessPct": pass_pct,
            "successfulPassesOppHalf": _to_int(s.get("successfulFinalThirdPasses")),
            "successfulPassesFinalThird": _to_int(s.get("successfulFinalThirdPasses")),
            # attacking
            "bigChances": _to_int(s.get("bigChanceCreated")),
            "shotsOffTarget": _to_int(s.get("shotOffTarget")),
            "blockedShots": _to_int(s.get("blockedScoringAtt")),
            "hitWoodwork": _to_int(s.get("hitWoodwork")),
            "shootingAccuracy": (round(_to_int(s.get("ontargetScoringAtt", 0)) /
                                       _to_int(s.get("totalScoringAtt", 0)) * 100, 1)
                                 if _to_int(s.get("totalScoringAtt")) else None),
            "crosses": _to_int(s.get("totalCross")),
            "successfulCrosses": _to_int(s.get("accurateCross")),
            "successfulCrossesPct": (round(_to_int(s.get("accurateCross", 0)) /
                                         _to_int(s.get("totalCross", 0)) * 100, 1)
                                   if _to_int(s.get("totalCross")) else None),
            "shotsInsideBox": _to_int(s.get("attemptsIbox")),
            "shotsOutsideBox": _to_int(s.get("attemptsObox")),
            # defence
            "tackles": _to_int(s.get("totalTackle")),
            "tackleSuccessPct": (round(_to_int(s.get("wonTackle", 0)) /
                                      _to_int(s.get("totalTackle", 0)) * 100, 1)
                                if _to_int(s.get("totalTackle")) else None),
            "duelsWon": _to_int(s.get("duelWon")),
            "aerialDuelsWon": _to_int(s.get("aerialWon")),
            "clearances": _to_int(s.get("totalClearance")),
            "saves": _to_int(s.get("saves")),
            "interceptions": _to_int(s.get("interceptionWon")),
            "blocks": _to_int(s.get("outfielderBlock")),
            "offsides": _to_int(s.get("totalOffside")),
            # booking points: yellow=10, red=25
            "bookingPoints": ((_to_int(s.get("totalYellowCard")) or 0) * 10 +
                              (_to_int(s.get("totalRedCard")) or 0) * 25) or None,
            # opta points not in matchstats, leave None
            "optaPoints": None,
            "touchesInOppBox": _to_int(s.get("touchesInOppBox")),
        }

    return {"home": _build(home_stats), "away": _build(away_stats)}


def _fetch_xg(event_id: str) -> Optional[dict]:
    """matchexpectedgoals → xG data."""
    raw = _api_get("matchexpectedgoals", event_id)
    if not raw or "liveData" not in raw:
        return None

    lineup = raw["liveData"].get("lineUp", [])
    contestants = raw.get("matchInfo", {}).get("contestant", [])

    home_id = away_id = None
    for c in contestants:
        if c.get("position") == "home":
            home_id = c["id"]
        elif c.get("position") == "away":
            away_id = c["id"]

    result = {"home": {}, "away": {}}

    for team in lineup:
        cid = team.get("contestantId")
        sd = _team_stats_dict(team.get("stat", []))
        side = "home" if cid == home_id else "away" if cid == away_id else None
        if not side:
            continue
        result[side] = {
            "xG": _to_float(sd.get("expectedGoals")),
            "xgOpenPlay": _to_float(sd.get("expectedGoalsOpenplay")),
            "xgSetPlay": _to_float(sd.get("expectedGoalsSetplay")),
            "xgPenalty": _to_float(sd.get("expectedGoalsPenalty")),
        }

    return result


def _fetch_momentum(event_id: str) -> Optional[dict]:
    """predictions/momentum → momentum values."""
    raw = _api_get("predictions/momentum", event_id)
    if not raw or "liveData" not in raw:
        return None

    predictions = raw["liveData"].get("predictions", [])
    if not predictions:
        return None

    home_sum = 0.0
    away_sum = 0.0

    for item in predictions:
        if item.get("type") != "Momentum":
            continue
        for pred in item.get("prediction", []):
            prob = float(pred.get("probability", 0))
            if pred.get("type") == "Home":
                home_sum += prob
            elif pred.get("type") == "Away":
                away_sum += prob

    # Escalar ×1000 para compatibilidad con el método visual
    return {
        "home": home_sum * 1000,
        "away": away_sum * 1000,
        "data_points": len(predictions),
    }


# ── Función principal ──────────────────────────────────────────────────────

def get_all_stats(event_id: str) -> Dict[str, Any]:
    """
    Obtiene TODAS las estadísticas disponibles para un partido.

    Usa 3 endpoints de api.performfeeds.com en paralelo:
    - matchstats (summary + attacking + defence)
    - matchexpectedgoals (xG)
    - predictions/momentum (momentum)

    Returns dict con {summary, attacking, defence, momentum, xg, event_id}.
    """
    log.info(f"Obteniendo estadísticas para eventId: {event_id}")

    all_stats = {
        "event_id": event_id,
        "summary": None,
        "momentum": None,
        "attacking": None,
        "defence": None,
        "xg": None,
    }

    # 3 requests en paralelo
    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_stats = pool.submit(_fetch_matchstats, event_id)
        fut_xg = pool.submit(_fetch_xg, event_id)
        fut_mom = pool.submit(_fetch_momentum, event_id)

        try:
            matchstats = fut_stats.result(timeout=API_TIMEOUT + 2)
        except Exception:
            matchstats = None

        try:
            xg_data = fut_xg.result(timeout=API_TIMEOUT + 2)
        except Exception:
            xg_data = None

        try:
            momentum = fut_mom.result(timeout=API_TIMEOUT + 2)
        except Exception:
            momentum = None

    if matchstats:
        # matchstats contiene todo: summary + attacking + defence
        # Para backward-compat, exponemos los mismos datos en las 3 categorías
        all_stats["summary"] = matchstats
        all_stats["attacking"] = matchstats
        all_stats["defence"] = matchstats

    if xg_data:
        # xG sobrescribe los valores de summary si están disponibles
        all_stats["xg"] = xg_data
        if matchstats:
            for side in ("home", "away"):
                if xg_data.get(side, {}).get("xG") is not None:
                    all_stats["summary"][side]["xG"] = xg_data[side]["xG"]

    all_stats["momentum"] = momentum

    success_count = sum(1 for k in ("summary", "momentum", "xg") if all_stats.get(k))
    log.info(f"Estadísticas obtenidas: {success_count}/3 endpoints")

    return all_stats


# ── Utilidad ───────────────────────────────────────────────────────────────

def extract_stat_value(all_stats: Dict[str, Any], category: str, team: str,
                       stat: str, default=None):
    """Extrae un valor específico de las estadísticas."""
    try:
        if category in all_stats and all_stats[category]:
            if team in all_stats[category]:
                return all_stats[category][team].get(stat, default)
    except (KeyError, TypeError):
        pass
    return default


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

    # Test: extraer Opta ID para un partido de ejemplo
    test_betfair_url = "https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/xxx/apuestas-35296048"
    test_html = '<div data-event-id="35296048">test</div>'
    eid = extract_event_id(test_html, test_betfair_url)
    print(f"Event ID: {eid}")

    if eid:
        stats = get_all_stats(eid)
        print(f"\nxG Home: {extract_stat_value(stats, 'summary', 'home', 'xG', 'N/A')}")
        print(f"xG Away: {extract_stat_value(stats, 'summary', 'away', 'xG', 'N/A')}")
        print(f"Possession Home: {extract_stat_value(stats, 'summary', 'home', 'possession', 'N/A')}")
        print(f"Corners Home: {extract_stat_value(stats, 'summary', 'home', 'corners', 'N/A')}")
        if stats.get("momentum"):
            print(f"Momentum Home: {stats['momentum']['home']:.2f}")
            print(f"Momentum Away: {stats['momentum']['away']:.2f}")
