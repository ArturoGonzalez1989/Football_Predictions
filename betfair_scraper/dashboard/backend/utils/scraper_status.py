"""
Utilidades para verificar el estado del scraper.
"""

import json
import os
import re as _re
from pathlib import Path
from datetime import datetime

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
HEARTBEAT_PATH = BASE_DIR / "data" / ".heartbeat"


def get_scraper_status() -> dict:
    """Verifica si el scraper está corriendo y su estado."""
    # Import auto-refresh status from main
    try:
        from main import _is_refreshing, REFRESH_INTERVAL_SECONDS
        auto_refresh_info = {
            "auto_refresh_enabled": True,
            "refresh_interval_minutes": REFRESH_INTERVAL_SECONDS // 60,
            "is_refreshing": _is_refreshing,
        }
    except ImportError:
        auto_refresh_info = {
            "auto_refresh_enabled": False,
            "refresh_interval_minutes": None,
            "is_refreshing": False,
        }

    result = {
        "running": False,
        "pid": None,
        "uptime_seconds": None,
        "memory_mb": None,
        "chrome_processes": 0,
        "last_log": None,
        "last_log_lines": [],
        "drivers_progress": {},
        **auto_refresh_info,
    }

    if HAS_PSUTIL:
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time", "memory_info"]):
            try:
                cmdline = proc.info.get("cmdline") or []
                cmdline_str = " ".join(cmdline).lower()
                if "main.py" in cmdline_str and "betfair" in cmdline_str:
                    result["running"] = True
                    result["pid"] = proc.info["pid"]
                    create_time = proc.info.get("create_time")
                    if create_time:
                        result["uptime_seconds"] = int(datetime.now().timestamp() - create_time)
                    mem = proc.info.get("memory_info")
                    if mem:
                        result["memory_mb"] = round(mem.rss / 1024 / 1024, 1)
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"] and "chrome" in proc.info["name"].lower():
                    result["chrome_processes"] += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    # Heartbeat: progreso de inicialización por partido
    try:
        if HEARTBEAT_PATH.exists():
            with open(HEARTBEAT_PATH, "r", encoding="utf-8") as f:
                hb = json.load(f)
            result["drivers_progress"] = hb.get("drivers_progress", {})
    except Exception:
        pass

    # Último log
    if LOGS_DIR.exists():
        log_files = sorted(LOGS_DIR.glob("scraper_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        if log_files:
            latest = log_files[0]
            result["last_log"] = latest.name
            try:
                with open(latest, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                result["last_log_lines"] = [l.rstrip() for l in lines[-20:]]
            except Exception:
                pass

    return result


# ── Per-match log health ──────────────────────────────────────────────────────

# Extraer el market ID numérico del match_id (robusto a URL-encoding)
_MARKET_ID_RE = _re.compile(r'apuestas-(\d+)')

# Log line patterns
_CAPTURE_OK_RE  = _re.compile(r'✓\s+\[([^\]]+)\]\s+Captura exitosa[^,]*,\s*min\s+(\d+)')
_SCORE_RE        = _re.compile(r'(\d+-\d+)')
_DRIVER_INIT_RE  = _re.compile(r'✓\s+Driver listo:\s+(.+)')
_CREATING_RE     = _re.compile(r'(?:Creando|creando) driver para:\s+(.+)')
# Error / warning patterns that contain a match_id bracket
_ERROR_ID_RE     = _re.compile(r'\[(ERROR|WARNING)\].*?\[([^\]]+apuestas-\d+[^\]]*)\]\s*(.*)')
# URL-related errors (no match_id bracket, but contain error keywords)
_URL_ERROR_RE    = _re.compile(
    r'(?:404|URL no encontrada|no encontr[oó]|intentos|timeout|Timeout|HTTPSConnectionPool|'
    r'WebDriverException|connection.*refused|ERR_|unable to connect)',
    _re.IGNORECASE,
)


def _market_id(match_id: str) -> str | None:
    """Extrae el ID numérico del partido (ej. '35263813') del match_id slug."""
    m = _MARKET_ID_RE.search(match_id)
    return m.group(1) if m else None


def parse_per_match_log(log_path: Path, match_ids: set) -> dict:
    """
    Escanea las últimas N líneas del log del scraper y devuelve un dict
    con el estado de la última captura conocida por partido.

    match_ids: set de match_id slugs (ej. {'annecy-red-star-apuestas-35263813', ...})

    Devuelve: { match_id → { log_status, log_minute, log_score, log_ts, log_msg } }
      log_status: "ok" | "error" | "init" | "creating"
    """
    result: dict = {}
    if not log_path or not log_path.exists() or not match_ids:
        return result

    # Build fast lookup: market_id (numeric) → match_id_slug
    id_map: dict[str, str] = {}
    for mid in match_ids:
        num = _market_id(mid)
        if num:
            id_map[num] = mid

    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception:
        return result

    # Scan newest first — stop early once all matches accounted for
    pending = set(match_ids)
    for raw in reversed(lines[-1500:]):
        if not pending:
            break
        line = raw.rstrip()
        ts = line[:8] if len(line) >= 8 else ""

        # ── Successful capture ──
        m = _CAPTURE_OK_RE.search(line)
        if m:
            log_slug = m.group(1)
            num = _market_id(log_slug)
            slug = id_map.get(num, "") if num else ""
            if not slug:
                # Try direct slug match
                slug = log_slug if log_slug in pending else ""
            if slug and slug in pending:
                score_m = _SCORE_RE.search(line[m.end():])
                result[slug] = {
                    "log_status": "ok",
                    "log_minute": int(m.group(2)),
                    "log_score": score_m.group(1) if score_m else None,
                    "log_ts": ts,
                }
                pending.discard(slug)
            continue

        # ── Error / Warning with match_id ──
        m = _ERROR_ID_RE.search(line)
        if m:
            log_slug = m.group(2).strip()
            num = _market_id(log_slug)
            slug = id_map.get(num, "") if num else ""
            if not slug:
                slug = log_slug if log_slug in pending else ""
            if slug and slug in pending:
                result[slug] = {
                    "log_status": "error",
                    "log_ts": ts,
                    "log_msg": m.group(3)[:100].strip(),
                }
                pending.discard(slug)
            continue

        # ── Driver listo: match_id (init finished, waiting for first capture) ──
        m = _DRIVER_INIT_RE.search(line)
        if m:
            log_slug = m.group(1).strip()
            num = _market_id(log_slug)
            slug = id_map.get(num, "") if num else log_slug
            if slug in pending:
                result[slug] = {"log_status": "init", "log_ts": ts}
                pending.discard(slug)
            continue

        # ── URL errors (not tagged with match_id but clearly problematic) ──
        if _URL_ERROR_RE.search(line) and "[ERROR]" in line:
            # Try to extract any match_id from the line
            any_id = _re.search(r'([a-zA-Z0-9%-]+-apuestas-\d+)', line)
            if any_id:
                log_slug = any_id.group(1)
                num = _market_id(log_slug)
                slug = id_map.get(num, "") if num else log_slug
                if slug in pending:
                    result[slug] = {
                        "log_status": "error",
                        "log_ts": ts,
                        "log_msg": line[20:][:100].strip() if len(line) > 20 else line,
                    }
                    pending.discard(slug)

    # Remaining (not in log at all) → unknown
    for slug in pending:
        result[slug] = {"log_status": "unknown"}

    return result
