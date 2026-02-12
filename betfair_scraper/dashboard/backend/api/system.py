"""
Endpoints de la API para estado del sistema.
"""

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from utils.scraper_status import get_scraper_status

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

router = APIRouter(prefix="/api/system", tags=["system"])

SCRAPER_DIR = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = SCRAPER_DIR / "scripts"
MAIN_PY = SCRAPER_DIR / "main.py"


@router.get("/status")
def get_status():
    """Estado del scraper y sistema."""
    return get_scraper_status()


@router.post("/refresh-matches")
def refresh_matches():
    """Ejecuta clean_games.py y find_matches.py para actualizar partidos."""
    python = sys.executable
    results = {"clean": None, "find": None}

    # 1. Limpiar partidos terminados
    clean_script = SCRIPTS_DIR / "clean_games.py"
    if clean_script.exists():
        try:
            proc = subprocess.run(
                [python, str(clean_script)],
                capture_output=True, text=True, timeout=30,
            )
            results["clean"] = {
                "ok": proc.returncode == 0,
                "output": (proc.stdout + proc.stderr).strip()[-500:],
            }
        except subprocess.TimeoutExpired:
            results["clean"] = {"ok": False, "output": "Timeout (30s)"}
    else:
        results["clean"] = {"ok": False, "output": f"Script not found: {clean_script}"}

    # 2. Buscar nuevos partidos
    find_script = SCRIPTS_DIR / "find_matches.py"
    if find_script.exists():
        try:
            proc = subprocess.run(
                [python, str(find_script)],
                capture_output=True, text=True, timeout=120,
            )
            results["find"] = {
                "ok": proc.returncode == 0,
                "output": (proc.stdout + proc.stderr).strip()[-500:],
            }
        except subprocess.TimeoutExpired:
            results["find"] = {"ok": False, "output": "Timeout (120s)"}
    else:
        results["find"] = {"ok": False, "output": f"Script not found: {find_script}"}

    return results


def _find_scraper_process():
    """Busca el proceso del scraper main.py."""
    if not HAS_PSUTIL:
        return None
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline).lower()
            if "main.py" in cmdline_str and "betfair" in cmdline_str:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


@router.post("/scraper/start")
def start_scraper():
    """Inicia el scraper (main.py) como proceso en background."""
    existing = _find_scraper_process()
    if existing:
        return {
            "ok": False,
            "message": f"Scraper already running (PID {existing.pid})",
            "pid": existing.pid,
        }

    if not MAIN_PY.exists():
        return {"ok": False, "message": f"main.py not found at {MAIN_PY}", "pid": None}

    try:
        proc = subprocess.Popen(
            [sys.executable, str(MAIN_PY)],
            cwd=str(SCRAPER_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return {"ok": True, "message": f"Scraper started (PID {proc.pid})", "pid": proc.pid}
    except Exception as e:
        return {"ok": False, "message": f"Failed to start: {e}", "pid": None}


@router.post("/scraper/stop")
def stop_scraper():
    """Detiene el scraper main.py y sus procesos Chrome."""
    proc = _find_scraper_process()
    if not proc:
        return {"ok": False, "message": "Scraper is not running"}

    pid = proc.pid
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        # Terminate children first (Chrome, chromedriver)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        parent.terminate()
        # Wait up to 5 seconds for graceful shutdown
        gone, alive = psutil.wait_procs([parent] + children, timeout=5)
        # Force kill any remaining
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
        return {"ok": True, "message": f"Scraper stopped (PID {pid})"}
    except psutil.NoSuchProcess:
        return {"ok": True, "message": "Scraper already stopped"}
    except Exception as e:
        return {"ok": False, "message": f"Error stopping scraper: {e}"}
