"""
Utilidades para verificar el estado del scraper.
"""

import os
from pathlib import Path
from datetime import datetime

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"


def get_scraper_status() -> dict:
    """Verifica si el scraper está corriendo y su estado."""
    result = {
        "running": False,
        "pid": None,
        "uptime_seconds": None,
        "memory_mb": None,
        "chrome_processes": 0,
        "last_log": None,
        "last_log_lines": [],
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
