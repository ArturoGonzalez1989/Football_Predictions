"""
Endpoints de la API para estado del sistema.
"""

import subprocess
import sys
from datetime import datetime
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
    # Import global flag from main app
    from main import _is_refreshing

    # Check if auto-refresh is already running
    if _is_refreshing:
        return {
            "clean": {"ok": False, "output": "Refresh already in progress (auto or manual)"},
            "find": {"ok": False, "output": "Refresh already in progress (auto or manual)"}
        }

    # Set flag to prevent concurrent executions
    import main
    main._is_refreshing = True
    main._refresh_started_at = datetime.now()

    try:
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

    finally:
        # Always release the flag
        main._is_refreshing = False
        main._refresh_started_at = None


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
    """Reinicia el servidor backend matando uvicorn y relanzándolo."""
    import os
    import threading

    backend_dir = Path(__file__).resolve().parent.parent
    current_pid = os.getpid()

    # Detect port from sys.argv (default 8000)
    port = "8000"
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = sys.argv[i + 1]
            break
        if arg.startswith("--port="):
            port = arg.split("=", 1)[1]
            break

    # Detect host from sys.argv (default 0.0.0.0)
    host = "0.0.0.0"
    for i, arg in enumerate(sys.argv):
        if arg == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]
            break
        if arg.startswith("--host="):
            host = arg.split("=", 1)[1]
            break

    try:
        # Spawn a helper script that:
        # 1. Waits for the current process to die
        # 2. Starts a new uvicorn with --reload
        restart_code = (
            "import time, subprocess, sys, os\n"
            f"old_pid = {current_pid}\n"
            "for _ in range(15):\n"
            "    time.sleep(1)\n"
            "    try:\n"
            "        os.kill(old_pid, 0)\n"
            "    except OSError:\n"
            "        break\n"
            "time.sleep(1)\n"
            "subprocess.Popen(\n"
            f"    [r'{sys.executable}', '-m', 'uvicorn', 'main:app', '--reload', '--host', '{host}', '--port', '{port}'],\n"
            f"    cwd=r'{backend_dir}',\n"
            "    creationflags=0x00000010,\n"  # CREATE_NEW_CONSOLE
            ")\n"
        )

        # Launch the restart helper as a fully detached process
        subprocess.Popen(
            [sys.executable, "-c", restart_code],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Kill ourselves after a short delay (so the HTTP response can be sent)
        def _delayed_exit():
            import time as _time
            _time.sleep(1)
            # Kill the entire uvicorn process tree
            if HAS_PSUTIL:
                try:
                    parent = psutil.Process(current_pid)
                    # If uvicorn --reload, our parent is the watcher
                    pp = parent.parent()
                    if pp and "uvicorn" in " ".join(pp.cmdline()).lower():
                        # Kill the parent watcher (which kills us too)
                        for child in pp.children(recursive=True):
                            try:
                                child.kill()
                            except psutil.NoSuchProcess:
                                pass
                        pp.kill()
                    else:
                        parent.kill()
                except Exception:
                    pass
            os._exit(0)

        threading.Thread(target=_delayed_exit, daemon=True).start()

        return {
            "ok": True,
            "message": f"Backend reiniciando... Nuevo uvicorn con --reload en puerto {port}",
            "old_pid": current_pid,
        }

    except Exception as e:
        return {"ok": False, "message": f"Error reiniciando backend: {e}"}


@router.post("/chrome/cleanup")
def cleanup_chrome():
    """Mata procesos Chrome huérfanos (no hijos del scraper activo)."""
    if not HAS_PSUTIL:
        return {"ok": False, "killed": 0, "message": "psutil no disponible"}

    import time

    # Proteger los Chrome que son hijos del scraper activo
    scraper_proc = _find_scraper_process()
    protected_pids: set = set()
    if scraper_proc:
        try:
            protected_pids.add(scraper_proc.pid)
            for child in scraper_proc.children(recursive=True):
                protected_pids.add(child.pid)
        except Exception:
            pass

    # Recoger procs Chrome huérfanos
    to_kill = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and "chrome" in proc.info["name"].lower():
                if proc.pid not in protected_pids:
                    to_kill.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Terminate suavemente
    for proc in to_kill:
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    time.sleep(1.5)

    # Force-kill los que sobrevivan
    force_killed = 0
    for proc in to_kill:
        try:
            if proc.is_running():
                proc.kill()
                force_killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    killed = len(to_kill)
    protected = len(protected_pids)
    return {
        "ok": True,
        "killed": killed,
        "protected": protected,
        "message": f"Eliminados {killed} procesos Chrome huérfanos ({protected} protegidos del scraper activo)",
    }


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
