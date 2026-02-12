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


@router.post("/backend/restart")
def restart_backend():
    """Reinicia el servidor backend (FastAPI/uvicorn)."""
    import os
    import time

    if not HAS_PSUTIL:
        return {"ok": False, "message": "psutil no está instalado"}

    try:
        # Obtener el PID del proceso actual (el backend)
        current_pid = os.getpid()
        current_proc = psutil.Process(current_pid)

        # Obtener el comando usado para iniciar el backend
        cmdline = current_proc.cmdline()

        # Iniciar nuevo proceso backend en background
        # Usar el mismo comando que se usó para iniciar este proceso
        new_proc = subprocess.Popen(
            cmdline,
            cwd=str(SCRAPER_DIR / "dashboard" / "backend"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        # Esperar un momento para que el nuevo proceso arranque
        time.sleep(2)

        # Programar terminación del proceso actual después de responder
        def delayed_shutdown():
            time.sleep(1)
            current_proc.terminate()

        import threading
        threading.Thread(target=delayed_shutdown, daemon=True).start()

        return {
            "ok": True,
            "message": f"Backend reiniciándose (nuevo PID: {new_proc.pid}, terminando PID: {current_pid})",
            "old_pid": current_pid,
            "new_pid": new_proc.pid
        }

    except Exception as e:
        return {"ok": False, "message": f"Error reiniciando backend: {e}"}


def _find_frontend_process():
    """Busca el proceso del frontend (npm/vite)."""
    if not HAS_PSUTIL:
        return None
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline).lower()
            # Buscar procesos de Vite dev server (puerto 5173)
            if "vite" in cmdline_str or (proc.info.get("name", "").lower() in ["node.exe", "node"] and "5173" in cmdline_str):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


@router.post("/frontend/restart")
def restart_frontend():
    """Reinicia el servidor frontend (Vite)."""
    if not HAS_PSUTIL:
        return {"ok": False, "message": "psutil no está instalado"}

    frontend_dir = SCRAPER_DIR / "dashboard" / "frontend"
    if not frontend_dir.exists():
        return {"ok": False, "message": f"Frontend directory not found: {frontend_dir}"}

    try:
        # Detener proceso existente si hay
        existing = _find_frontend_process()
        if existing:
            pid = existing.pid
            existing.terminate()
            try:
                existing.wait(timeout=5)
            except psutil.TimeoutExpired:
                existing.kill()

        # Iniciar nuevo proceso frontend
        import time
        time.sleep(1)  # Esperar a que el puerto se libere

        # Iniciar npm run dev
        proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(frontend_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

        return {
            "ok": True,
            "message": f"Frontend reiniciado (PID: {proc.pid})",
            "pid": proc.pid
        }

    except Exception as e:
        return {"ok": False, "message": f"Error reiniciando frontend: {e}"}
