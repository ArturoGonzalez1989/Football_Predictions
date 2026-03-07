"""
API endpoint para alertas proactivas del sistema de scraping.
Detecta problemas silenciosos antes de que impacten en los datos.
"""

import json
import csv
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

log = logging.getLogger(__name__)

router = APIRouter()

SCRAPER_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = SCRAPER_DIR / "data"
HEARTBEAT_PATH = DATA_DIR / ".heartbeat"
GAMES_CSV = SCRAPER_DIR / "games.csv"
PLACED_BETS_CSV = SCRAPER_DIR / "placed_bets.csv"
LOG_DIR = SCRAPER_DIR / "logs"


def _check_heartbeat() -> List[Dict[str, Any]]:
    """Check scraper heartbeat freshness."""
    alerts = []
    if not HEARTBEAT_PATH.exists():
        alerts.append({
            "level": "critical",
            "category": "heartbeat",
            "message": "No se encontró archivo .heartbeat — scraper puede no estar corriendo",
        })
        return alerts

    try:
        with open(HEARTBEAT_PATH) as f:
            hb = json.load(f)
        hb_time = datetime.fromisoformat(hb["timestamp"])
        age = (datetime.now(timezone.utc) - hb_time).total_seconds()

        if age > 300:
            alerts.append({
                "level": "critical",
                "category": "heartbeat",
                "message": f"Heartbeat stale: {age:.0f}s (>5min) — scraper colgado o muerto",
                "detail": f"Último heartbeat: {hb.get('timestamp', '?')}",
            })
        elif age > 180:
            alerts.append({
                "level": "warning",
                "category": "heartbeat",
                "message": f"Heartbeat stale: {age:.0f}s (>3min) — posible problema",
            })

        # Check alive vs active drivers
        alive = hb.get("alive_drivers", 0)
        active = hb.get("active_drivers", 0)
        if active > 0 and alive == 0:
            alerts.append({
                "level": "critical",
                "category": "drivers",
                "message": f"Todos los drivers muertos: 0/{active} alive",
            })
        elif active > 0 and alive < active * 0.5:
            alerts.append({
                "level": "warning",
                "category": "drivers",
                "message": f"Drivers degradados: {alive}/{active} alive ({alive/active*100:.0f}%)",
            })
    except Exception as e:
        alerts.append({
            "level": "warning",
            "category": "heartbeat",
            "message": f"Error leyendo heartbeat: {e}",
        })
    return alerts


def _check_stats_api() -> List[Dict[str, Any]]:
    """Check if Stats API is responding by testing a quick call."""
    alerts = []
    try:
        import sys
        sys.path.insert(0, str(SCRAPER_DIR))
        from stats_api import _api_get

        # Try to get a match that's currently active
        if GAMES_CSV.exists():
            with open(GAMES_CSV, 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
            if rows:
                url = rows[0].get("url", "")
                m = re.search(r'(\d{7,})', url)
                if m:
                    betfair_id = m.group(1)
                    # Quick check: can we get Opta ID?
                    import requests
                    vp_url = f"https://videoplayer.betfair.es/GetPlayer.do?eID={betfair_id}&contentType=viz&contentView=mstats"
                    r = requests.get(vp_url, timeout=5)
                    opta_match = re.search(
                        r'(?:providerEventId|performMCCFixtureUUID|streamUUID)\s*[=:]\s*["\']?([a-z0-9]{20,30})["\']?',
                        r.text, re.IGNORECASE
                    )
                    if opta_match:
                        opta_id = opta_match.group(1)
                        result = _api_get("matchstats", opta_id, "&detailed=yes")
                        if result is None:
                            alerts.append({
                                "level": "critical",
                                "category": "stats_api",
                                "message": "Stats API no responde — estadísticas no disponibles",
                            })
                    else:
                        alerts.append({
                            "level": "warning",
                            "category": "stats_api",
                            "message": "No se pudo obtener Opta ID del videoplayer",
                        })
    except Exception as e:
        alerts.append({
            "level": "warning",
            "category": "stats_api",
            "message": f"Error verificando Stats API: {e}",
        })
    return alerts


def _check_pending_bets() -> List[Dict[str, Any]]:
    """Check for bets stuck in pending state too long."""
    alerts = []
    if not PLACED_BETS_CSV.exists():
        return alerts

    try:
        with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        # Check active match IDs
        active_ids = set()
        if GAMES_CSV.exists():
            with open(GAMES_CSV, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    url = row.get("url", "")
                    m = re.search(r'([^/]+apuestas-\d+)', url)
                    if m:
                        active_ids.add(m.group(1))

        stuck_bets = []
        for row in rows:
            if row.get("status") == "pending":
                match_id = row.get("match_id", "")
                # If match is no longer active and bet is still pending
                if match_id and match_id not in active_ids:
                    ts = row.get("timestamp", "")
                    stuck_bets.append(f"Bet #{row.get('id', '?')} ({row.get('strategy_name', '?')}) - {match_id[:30]}")

        if stuck_bets:
            alerts.append({
                "level": "warning",
                "category": "bets",
                "message": f"{len(stuck_bets)} apuestas pendientes en partidos finalizados",
                "detail": "; ".join(stuck_bets[:5]) + ("..." if len(stuck_bets) > 5 else ""),
            })
    except Exception as e:
        log.warning(f"Error checking pending bets: {e}")
    return alerts


def _check_data_quality() -> List[Dict[str, Any]]:
    """Check recent CSV data quality (gaps, early endings)."""
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    try:
        # Check last 5 active matches for data quality
        csv_files = sorted(DATA_DIR.glob("partido_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for csv_path in csv_files:
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    rows = list(csv.DictReader(f))
                if len(rows) < 2:
                    continue

                # Check for large time gaps
                prev_ts = None
                max_gap = 0
                for row in rows:
                    ts_str = row.get("timestamp", "")
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            if prev_ts:
                                gap = (ts - prev_ts).total_seconds()
                                max_gap = max(max_gap, gap)
                            prev_ts = ts
                        except Exception:
                            pass

                if max_gap > 600:  # >10 min gap
                    match_id = csv_path.stem
                    alerts.append({
                        "level": "warning",
                        "category": "data_quality",
                        "message": f"Gap de {max_gap/60:.0f}min en {match_id}",
                    })
            except Exception:
                pass
    except Exception as e:
        log.warning(f"Error checking data quality: {e}")
    return alerts


def _check_scraper_log() -> List[Dict[str, Any]]:
    """Check recent scraper log for recurring errors."""
    alerts = []
    if not LOG_DIR.exists():
        return alerts

    try:
        log_files = sorted(LOG_DIR.glob("scraper_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not log_files:
            return alerts

        latest_log = log_files[0]
        # Read last 200 lines
        with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()[-200:]

        error_count = sum(1 for l in lines if "ERROR" in l)
        crash_count = sum(1 for l in lines if "muerto" in l.lower() or "crash" in l.lower() or "💀" in l)
        stats_fail = sum(1 for l in lines if "0/5 endpoints" in l or "0/3 endpoints" in l)

        if stats_fail > 3:
            alerts.append({
                "level": "critical",
                "category": "stats_api",
                "message": f"Stats API fallando repetidamente: {stats_fail} fallos en log reciente",
            })

        if crash_count > 2:
            alerts.append({
                "level": "warning",
                "category": "drivers",
                "message": f"{crash_count} drivers muertos/crashes en log reciente",
            })

        if error_count > 20:
            alerts.append({
                "level": "warning",
                "category": "logs",
                "message": f"Alto volumen de errores: {error_count} en últimas 200 líneas del log",
            })
    except Exception as e:
        log.warning(f"Error checking scraper log: {e}")
    return alerts


@router.get("/api/alerts")
async def get_alerts():
    """Returns all active system alerts."""
    alerts = []
    alerts.extend(_check_heartbeat())
    alerts.extend(_check_pending_bets())
    alerts.extend(_check_data_quality())
    alerts.extend(_check_scraper_log())
    # Stats API check is slow (~2s), only run if no other critical alerts
    if not any(a["level"] == "critical" for a in alerts):
        alerts.extend(_check_stats_api())

    # Sort: critical first, then warning
    alerts.sort(key=lambda a: 0 if a["level"] == "critical" else 1)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a["level"] == "critical"),
        "warning": sum(1 for a in alerts if a["level"] == "warning"),
        "alerts": alerts,
    }


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page():
    """Standalone HTML alerts dashboard."""
    return _ALERTS_HTML


_ALERTS_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Furbo Alerts</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; padding: 20px; }
  h1 { font-size: 1.4rem; margin-bottom: 16px; color: #fff; }
  .status-bar { display: flex; gap: 16px; margin-bottom: 20px; padding: 12px 16px; background: #1a1d27; border-radius: 8px; align-items: center; }
  .status-bar .indicator { width: 12px; height: 12px; border-radius: 50%; }
  .status-bar .indicator.ok { background: #22c55e; box-shadow: 0 0 8px #22c55e80; }
  .status-bar .indicator.warn { background: #f59e0b; box-shadow: 0 0 8px #f59e0b80; }
  .status-bar .indicator.crit { background: #ef4444; box-shadow: 0 0 8px #ef444480; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
  .status-bar .label { font-size: 0.9rem; }
  .status-bar .time { margin-left: auto; font-size: 0.8rem; color: #888; }
  .alert-list { display: flex; flex-direction: column; gap: 8px; }
  .alert { padding: 12px 16px; border-radius: 8px; border-left: 4px solid; }
  .alert.critical { background: #1a0f0f; border-color: #ef4444; }
  .alert.warning { background: #1a170f; border-color: #f59e0b; }
  .alert .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-right: 8px; }
  .alert.critical .badge { background: #ef444433; color: #ef4444; }
  .alert.warning .badge { background: #f59e0b33; color: #f59e0b; }
  .alert .category { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; background: #ffffff11; color: #888; margin-right: 8px; }
  .alert .msg { font-size: 0.9rem; }
  .alert .detail { font-size: 0.8rem; color: #888; margin-top: 4px; }
  .no-alerts { text-align: center; padding: 40px; color: #22c55e; font-size: 1.1rem; }
  .no-alerts .icon { font-size: 3rem; margin-bottom: 12px; }
  .refresh-info { font-size: 0.75rem; color: #555; margin-top: 16px; text-align: center; }
</style>
</head>
<body>
<h1>Sistema de Alertas</h1>
<div class="status-bar" id="statusBar">
  <div class="indicator" id="statusIndicator"></div>
  <span class="label" id="statusLabel">Cargando...</span>
  <span class="time" id="statusTime"></span>
</div>
<div id="alertList" class="alert-list"></div>
<div class="refresh-info">Auto-refresh cada 30s</div>

<script>
async function fetchAlerts() {
  try {
    const r = await fetch('/api/alerts');
    const data = await r.json();

    const ind = document.getElementById('statusIndicator');
    const label = document.getElementById('statusLabel');
    const time = document.getElementById('statusTime');
    const list = document.getElementById('alertList');

    time.textContent = new Date().toLocaleTimeString();

    if (data.critical > 0) {
      ind.className = 'indicator crit';
      label.textContent = `${data.critical} alerta(s) critica(s), ${data.warning} aviso(s)`;
    } else if (data.warning > 0) {
      ind.className = 'indicator warn';
      label.textContent = `${data.warning} aviso(s)`;
    } else {
      ind.className = 'indicator ok';
      label.textContent = 'Sistema OK — sin alertas';
    }

    if (data.alerts.length === 0) {
      list.innerHTML = '<div class="no-alerts"><div class="icon">&#10003;</div>Todo funcionando correctamente</div>';
      return;
    }

    list.innerHTML = data.alerts.map(a => `
      <div class="alert ${a.level}">
        <span class="badge">${a.level}</span>
        <span class="category">${a.category}</span>
        <span class="msg">${a.message}</span>
        ${a.detail ? '<div class="detail">' + a.detail + '</div>' : ''}
      </div>
    `).join('');
  } catch (e) {
    document.getElementById('statusLabel').textContent = 'Error conectando con backend';
    document.getElementById('statusIndicator').className = 'indicator crit';
  }
}

fetchAlerts();
setInterval(fetchAlerts, 30000);
</script>
</body>
</html>"""
