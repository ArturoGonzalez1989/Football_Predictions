"""
Furbo Monitor - Dashboard Backend
FastAPI server para monitorear el scraper de Betfair.
"""

import sys
# Prevent stale .pyc bytecode cache (OneDrive/Windows can cause mismatch)
sys.dont_write_bytecode = True

import asyncio
import subprocess
import importlib
from pathlib import Path
from datetime import datetime

# Asegurar que el directorio backend está en sys.path
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.matches import router as matches_router
from api.system import router as system_router
from api.analytics import router as analytics_router
from api.bets import router as bets_router
from api.config import router as config_router

# Force fresh reload of csv_reader to avoid stale module cache
try:
    from utils import csv_reader as _csv_reader_mod
    importlib.reload(_csv_reader_mod)
    print(f"[STARTUP] csv_reader reloaded OK — has momentum_xg: {hasattr(_csv_reader_mod, 'analyze_strategy_momentum_xg')}")
except Exception as _reload_err:
    print(f"[STARTUP] csv_reader reload FAILED: {_reload_err}")

app = FastAPI(title="Furbo Monitor API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches_router)
app.include_router(system_router)
app.include_router(analytics_router, prefix="/api/analytics", tags=["analytics"])
app.include_router(bets_router, tags=["bets"])
app.include_router(config_router, prefix="/api", tags=["config"])


# ==================== AUTO REFRESH SCHEDULER ====================

# Global state for scheduler
_scheduler_task = None
_is_refreshing = False
_refresh_started_at = None  # Track when refresh started to detect stuck state
_last_refresh_time = None
_last_refresh_result = None
_refresh_count = 0
MAX_REFRESH_DURATION_SECONDS = 180  # Force-reset flag after 3 minutes

SCRAPER_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = SCRAPER_DIR / "scripts"
REFRESH_INTERVAL_SECONDS = 10 * 60  # 10 minutes


def _run_script_sync(script_path: Path, timeout: int = 120) -> dict:
    """Run a script using subprocess.run (reliable on Windows).
    This is the same method that manual refresh uses and is proven to work."""
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True,
            timeout=timeout,
            cwd=str(SCRAPER_DIR),
        )
        return {
            "ok": proc.returncode == 0,
            "output": (proc.stdout + proc.stderr).strip()[-1000:],
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"Timeout ({timeout}s)", "returncode": -1}
    except Exception as e:
        return {"ok": False, "output": str(e), "returncode": -1}


async def _run_script_async(script_path: Path, timeout: int = 120) -> dict:
    """Run a script in a thread pool to not block the event loop.
    Uses subprocess.run internally (proven reliable on Windows)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_script_sync, script_path, timeout)


async def auto_refresh_matches():
    """Background task que ejecuta clean_games + find_matches cada 10 minutos."""
    global _is_refreshing, _last_refresh_time, _last_refresh_result, _refresh_count

    # Wait initial delay before first execution
    print(f"[{datetime.now()}] Auto-refresh: Waiting 30s before first execution...")
    await asyncio.sleep(30)

    while True:
        try:
            # Check if manual refresh is running (with stuck detection)
            if _is_refreshing:
                if _refresh_started_at:
                    elapsed = (datetime.now() - _refresh_started_at).total_seconds()
                    if elapsed > MAX_REFRESH_DURATION_SECONDS:
                        print(f"[{datetime.now()}] WARNING: Refresh stuck for {elapsed:.0f}s — force-resetting flag")
                        _is_refreshing = False
                        _refresh_started_at = None
                    else:
                        print(f"[{datetime.now()}] Auto-refresh skipped: refresh in progress ({elapsed:.0f}s)")
                        await asyncio.sleep(60)
                        continue
                else:
                    print(f"[{datetime.now()}] Auto-refresh skipped: refresh in progress (no timestamp)")
                    _is_refreshing = False

            _is_refreshing = True
            _refresh_started_at = datetime.now()
            _refresh_count += 1
            cycle = _refresh_count
            print(f"\n{'='*60}")
            print(f"[{datetime.now()}] AUTO-REFRESH CYCLE #{cycle} STARTING")
            print(f"{'='*60}")

            results = {}

            # 1. Execute clean_games.py
            clean_script = SCRIPTS_DIR / "clean_games.py"
            if clean_script.exists():
                print(f"[{datetime.now()}] [1/2] Running clean_games.py...")
                r = await _run_script_async(clean_script, timeout=30)
                results["clean"] = r
                if r["output"]:
                    for line in r["output"].split("\n"):
                        print(f"  | {line}")
                print(f"[{datetime.now()}] clean_games: {'OK' if r['ok'] else 'FAILED (code ' + str(r['returncode']) + ')'}")
            else:
                print(f"[{datetime.now()}] clean_games.py not found at {clean_script}")

            # 2. Execute find_matches.py
            find_script = SCRIPTS_DIR / "find_matches.py"
            if find_script.exists():
                print(f"[{datetime.now()}] [2/2] Running find_matches.py...")
                r = await _run_script_async(find_script, timeout=120)
                results["find"] = r
                if r["output"]:
                    for line in r["output"].split("\n"):
                        print(f"  | {line}")
                print(f"[{datetime.now()}] find_matches: {'OK' if r['ok'] else 'FAILED (code ' + str(r['returncode']) + ')'}")
            else:
                print(f"[{datetime.now()}] find_matches.py not found at {find_script}")

            _last_refresh_time = datetime.now().isoformat()
            _last_refresh_result = results

            print(f"[{datetime.now()}] Cycle #{cycle} completed. Next in {REFRESH_INTERVAL_SECONDS // 60} min")
            print(f"{'='*60}\n")

        except Exception as e:
            print(f"[{datetime.now()}] Auto-refresh error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            _is_refreshing = False
            _refresh_started_at = None

        # Wait for next execution
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)


async def _scheduler_watchdog():
    """Watchdog: reinicia el scheduler si se cae inesperadamente."""
    global _scheduler_task
    while True:
        await asyncio.sleep(30)
        if _scheduler_task is None or _scheduler_task.done():
            if _scheduler_task and _scheduler_task.done():
                try:
                    exc = _scheduler_task.exception()
                    print(f"[{datetime.now()}] Scheduler task died! Exception: {exc}")
                except (asyncio.CancelledError, asyncio.InvalidStateError):
                    pass
            print(f"[{datetime.now()}] Restarting auto-refresh scheduler...")
            _scheduler_task = asyncio.create_task(auto_refresh_matches())


# ==================== SCRAPER WATCHDOG ====================

HEARTBEAT_PATH = SCRAPER_DIR / "data" / ".heartbeat"
SCRAPER_WATCHDOG_INTERVAL = 60  # Check every 60 seconds
HEARTBEAT_STALE_THRESHOLD = 120  # Heartbeat older than 2 min = scraper is dead/stuck
_scraper_watchdog_task = None
_scraper_auto_restarts = 0


async def _scraper_watchdog():
    """Monitor the scraper heartbeat and auto-restart if dead."""
    global _scraper_auto_restarts
    import json

    # Wait for scraper to have time to start
    await asyncio.sleep(90)

    while True:
        try:
            # Read heartbeat file
            heartbeat = None
            if HEARTBEAT_PATH.exists():
                try:
                    with open(HEARTBEAT_PATH) as f:
                        heartbeat = json.load(f)
                except Exception:
                    pass

            # Check if scraper process is running
            scraper_running = False
            try:
                import psutil
                for proc in psutil.process_iter(["pid", "cmdline"]):
                    cmdline = proc.info.get("cmdline") or []
                    if any("main.py" in str(c) for c in cmdline) and any("python" in str(c).lower() for c in cmdline):
                        if str(SCRAPER_DIR) in " ".join(str(c) for c in cmdline):
                            scraper_running = True
                            break
            except Exception:
                pass

            if not scraper_running:
                # Scraper process is not running — auto-restart
                print(f"[{datetime.now()}] WATCHDOG: Scraper process not running! Auto-restarting...")
                try:
                    proc = subprocess.Popen(
                        [sys.executable, str(SCRAPER_DIR / "main.py")],
                        cwd=str(SCRAPER_DIR),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    )
                    _scraper_auto_restarts += 1
                    print(f"[{datetime.now()}] WATCHDOG: Scraper restarted (PID {proc.pid}), auto-restart #{_scraper_auto_restarts}")
                except Exception as e:
                    print(f"[{datetime.now()}] WATCHDOG: Failed to restart scraper: {e}")

            elif heartbeat:
                # Scraper is running — check if heartbeat is stale
                try:
                    hb_time = datetime.fromisoformat(heartbeat["timestamp"])
                    from datetime import timezone as tz
                    age_seconds = (datetime.now(tz.utc) - hb_time).total_seconds()
                    if age_seconds > HEARTBEAT_STALE_THRESHOLD:
                        print(f"[{datetime.now()}] WATCHDOG: Scraper heartbeat stale ({age_seconds:.0f}s old), drivers alive: {heartbeat.get('alive_drivers', '?')}/{heartbeat.get('active_drivers', '?')}")
                except Exception:
                    pass

        except Exception as e:
            print(f"[{datetime.now()}] WATCHDOG error: {e}")

        await asyncio.sleep(SCRAPER_WATCHDOG_INTERVAL)


@app.on_event("startup")
async def start_scheduler():
    """Start the auto-refresh scheduler and scraper watchdog on app startup."""
    global _scheduler_task, _scraper_watchdog_task
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] STARTING AUTO-REFRESH SCHEDULER")
    print(f"  Interval: {REFRESH_INTERVAL_SECONDS // 60} minutes")
    print(f"  First execution in 30 seconds")
    print(f"  Scripts dir: {SCRIPTS_DIR}")
    print(f"  clean_games.py exists: {(SCRIPTS_DIR / 'clean_games.py').exists()}")
    print(f"  find_matches.py exists: {(SCRIPTS_DIR / 'find_matches.py').exists()}")
    print(f"  Python: {sys.executable}")
    print(f"{'='*60}\n")
    _scheduler_task = asyncio.create_task(auto_refresh_matches())
    # Watchdog to auto-restart if scheduler crashes
    asyncio.create_task(_scheduler_watchdog())
    # Scraper watchdog: auto-restart if scraper dies
    _scraper_watchdog_task = asyncio.create_task(_scraper_watchdog())
    print(f"[{datetime.now()}] Scraper watchdog started (checks every {SCRAPER_WATCHDOG_INTERVAL}s)")


@app.on_event("shutdown")
async def stop_scheduler():
    """Stop the auto-refresh scheduler on app shutdown."""
    global _scheduler_task
    if _scheduler_task:
        print(f"[{datetime.now()}] Stopping auto-refresh scheduler...")
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass


# ==================== HEALTH CHECK ====================

@app.get("/api/health")
def health_check():
    import json

    # Read scraper heartbeat
    scraper_heartbeat = None
    if HEARTBEAT_PATH.exists():
        try:
            with open(HEARTBEAT_PATH) as f:
                scraper_heartbeat = json.load(f)
        except Exception:
            pass

    return {
        "status": "ok",
        "auto_refresh_enabled": True,
        "refresh_interval_minutes": REFRESH_INTERVAL_SECONDS // 60,
        "is_refreshing": _is_refreshing,
        "refresh_count": _refresh_count,
        "last_refresh_time": _last_refresh_time,
        "last_refresh_result": _last_refresh_result,
        "scheduler_alive": _scheduler_task is not None and not _scheduler_task.done() if _scheduler_task else False,
        "scraper_watchdog_alive": _scraper_watchdog_task is not None and not _scraper_watchdog_task.done() if _scraper_watchdog_task else False,
        "scraper_auto_restarts": _scraper_auto_restarts,
        "scraper_heartbeat": scraper_heartbeat,
    }
