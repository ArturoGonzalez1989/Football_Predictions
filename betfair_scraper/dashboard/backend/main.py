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
from api.analytics import router as analytics_router, run_paper_auto_place
from api.bets import router as bets_router, run_auto_cashout
from api.config import router as config_router
from api.alerts import router as alerts_router, run_alert_checks

# Force fresh reload of csv_reader to avoid stale module cache
try:
    from utils import csv_reader as _csv_reader_mod
    importlib.reload(_csv_reader_mod)
    print(f"[STARTUP] csv_reader reloaded OK — has analyze_cartera: {hasattr(_csv_reader_mod, 'analyze_cartera')}")
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
app.include_router(alerts_router, tags=["alerts"])


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


# ==================== PAPER TRADING AUTO-POLLER ====================

PAPER_TRADING_INTERVAL_SECONDS = 30  # Pollea señales cada 30s
_paper_trading_task = None
_paper_trading_cycle_count = 0
_paper_trading_last_run = None
_paper_trading_errors = 0


async def auto_paper_trading():
    """Background task: detecta señales, auto-coloca bets y gestiona cashout/settle cada 60s.
    ÚNICA fuente de auto-colocación de apuestas — no depende de que la UI esté abierta.
      1. Detecta señales maduras (age >= min_dur + 1min de reacción) y las coloca
      2. Revisa bets pendientes: cashout si lay >= threshold, settle si partido terminado
    """
    global _paper_trading_cycle_count, _paper_trading_last_run, _paper_trading_errors
    print(f"[{datetime.now()}] Paper auto-poller: esperando 90s antes del primer ciclo...")
    await asyncio.sleep(90)

    while True:
        loop = asyncio.get_event_loop()
        _paper_trading_cycle_count += 1
        _paper_trading_last_run = datetime.now().isoformat()
        cycle = _paper_trading_cycle_count
        print(f"[{datetime.now()}] [PAPER] Ciclo #{cycle} — detectando señales...")

        try:
            # 1. Detectar y colocar nuevas bets
            place_result = await loop.run_in_executor(None, run_paper_auto_place)
            if place_result.get("error"):
                _paper_trading_errors += 1
                print(f"[{datetime.now()}] [PAPER] #{cycle} Error en place: {place_result['error']}")
            else:
                placed = place_result.get("placed", 0)
                checked = place_result.get("signals_checked", 0)
                print(f"[{datetime.now()}] [PAPER] #{cycle} Place OK — "
                      f"señales_activas={checked} | colocadas={placed}")
        except Exception as e:
            _paper_trading_errors += 1
            print(f"[{datetime.now()}] [PAPER] #{cycle} Place excepción: {e}")

        try:
            # 2. Cashout/settle de bets pendientes
            co_result = await loop.run_in_executor(None, run_auto_cashout)
            if co_result.get("cashed_out", 0) > 0:
                print(f"[{datetime.now()}] [PAPER] #{cycle} Cashout {co_result['cashed_out']} bet(s)")
            if co_result.get("settled", 0) > 0:
                print(f"[{datetime.now()}] [PAPER] #{cycle} Settled {co_result['settled']} bet(s)")
        except Exception as e:
            _paper_trading_errors += 1
            print(f"[{datetime.now()}] [PAPER] #{cycle} Cashout excepción: {e}")

        await asyncio.sleep(PAPER_TRADING_INTERVAL_SECONDS)


async def _paper_trading_watchdog():
    """Watchdog: reinicia el paper trading task si se cae inesperadamente."""
    global _paper_trading_task
    await asyncio.sleep(120)  # Dar tiempo al primer ciclo antes de empezar a vigilar
    while True:
        await asyncio.sleep(90)
        if _paper_trading_task is None or _paper_trading_task.done():
            if _paper_trading_task and _paper_trading_task.done():
                try:
                    exc = _paper_trading_task.exception()
                    print(f"[{datetime.now()}] [PAPER WATCHDOG] Task muerta! Excepción: {exc}")
                except (asyncio.CancelledError, asyncio.InvalidStateError):
                    pass
            print(f"[{datetime.now()}] [PAPER WATCHDOG] Reiniciando paper trading task...")
            _paper_trading_task = asyncio.create_task(auto_paper_trading())


# ==================== SCRAPER WATCHDOG ====================

HEARTBEAT_PATH = SCRAPER_DIR / "data" / ".heartbeat"
SCRAPER_WATCHDOG_INTERVAL = 60  # Check every 60 seconds
HEARTBEAT_STALE_THRESHOLD = 180  # Heartbeat older than 3 min = scraper is stuck
HEARTBEAT_FORCE_RESTART_THRESHOLD = 300  # >5 min stale = force kill + restart
_scraper_watchdog_task = None
_scraper_auto_restarts = 0
_consecutive_stale_checks = 0


async def _scraper_watchdog():
    """Monitor the scraper heartbeat and auto-restart if dead or stuck."""
    global _scraper_auto_restarts, _consecutive_stale_checks
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
                except Exception as e:
                    print(f"[{datetime.now()}] WATCHDOG: Error reading heartbeat: {e}")

            # Check if scraper process is running
            scraper_pid = None
            try:
                import psutil
                for proc in psutil.process_iter(["pid", "cmdline"]):
                    cmdline = proc.info.get("cmdline") or []
                    if any("main.py" in str(c) for c in cmdline) and any("python" in str(c).lower() for c in cmdline):
                        if str(SCRAPER_DIR) in " ".join(str(c) for c in cmdline):
                            scraper_pid = proc.info["pid"]
                            break
            except Exception:
                pass

            if scraper_pid is None:
                # Scraper process is not running — auto-restart
                _consecutive_stale_checks = 0
                print(f"[{datetime.now()}] WATCHDOG: Scraper process not running! Auto-restarting...")
                _restart_scraper()

            elif heartbeat:
                # Scraper is running — check if heartbeat is stale
                try:
                    hb_time = datetime.fromisoformat(heartbeat["timestamp"])
                    from datetime import timezone as tz
                    age_seconds = (datetime.now(tz.utc) - hb_time).total_seconds()
                    if age_seconds > HEARTBEAT_FORCE_RESTART_THRESHOLD:
                        _consecutive_stale_checks += 1
                        print(f"[{datetime.now()}] WATCHDOG: Heartbeat stale {age_seconds:.0f}s "
                              f"(>{HEARTBEAT_FORCE_RESTART_THRESHOLD}s), consecutive={_consecutive_stale_checks}")
                        if _consecutive_stale_checks >= 2:
                            # Force kill and restart
                            print(f"[{datetime.now()}] WATCHDOG: Force-killing stuck scraper (PID {scraper_pid})...")
                            _force_kill_scraper(scraper_pid)
                            await asyncio.sleep(5)
                            _restart_scraper()
                            _consecutive_stale_checks = 0
                    elif age_seconds > HEARTBEAT_STALE_THRESHOLD:
                        print(f"[{datetime.now()}] WATCHDOG: Heartbeat stale ({age_seconds:.0f}s), "
                              f"drivers alive: {heartbeat.get('alive_drivers', '?')}/{heartbeat.get('active_drivers', '?')}")
                    else:
                        _consecutive_stale_checks = 0
                except Exception as e:
                    print(f"[{datetime.now()}] WATCHDOG: Error checking heartbeat age: {e}")

        except Exception as e:
            print(f"[{datetime.now()}] WATCHDOG error: {e}")

        await asyncio.sleep(SCRAPER_WATCHDOG_INTERVAL)


def _restart_scraper():
    """Start a new scraper process."""
    global _scraper_auto_restarts
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


def _force_kill_scraper(pid: int):
    """Force-kill a stuck scraper process and its children."""
    try:
        import psutil
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
            except Exception:
                pass
        parent.kill()
        print(f"[{datetime.now()}] WATCHDOG: Killed scraper PID {pid} + {len(children)} children")
    except Exception as e:
        print(f"[{datetime.now()}] WATCHDOG: Error killing PID {pid}: {e}")


ALERTS_MONITOR_INTERVAL = 60  # Check alerts every 60 seconds


async def _alerts_monitor():
    """Background task: runs alert checks every 60s and logs to alerts.jsonl.

    Ensures alerts are captured even when nobody is viewing the dashboard.
    Skips the Stats API check (slow) to keep the loop lightweight.
    """
    await asyncio.sleep(45)  # Initial delay to let other services start
    while True:
        try:
            run_alert_checks(include_stats_api=False)
        except Exception as e:
            print(f"[{datetime.now()}] [ALERTS MONITOR] Error: {e}")
        await asyncio.sleep(ALERTS_MONITOR_INTERVAL)


@app.on_event("startup")
async def start_scheduler():
    """Start the auto-refresh scheduler and scraper watchdog on app startup."""
    global _scheduler_task, _scraper_watchdog_task, _paper_trading_task
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
    # Paper trading auto-poller: detecta señales y coloca bets sin necesidad de abrir el dashboard
    _paper_trading_task = asyncio.create_task(auto_paper_trading())
    print(f"[{datetime.now()}] Paper auto-poller started (cada {PAPER_TRADING_INTERVAL_SECONDS}s, delay reacción +1min)")
    # Watchdog para el paper trading task — lo reinicia si muere inesperadamente
    asyncio.create_task(_paper_trading_watchdog())
    print(f"[{datetime.now()}] Paper trading watchdog started")
    # Alerts monitor: logs system alerts every 60s (even when nobody is viewing the dashboard)
    asyncio.create_task(_alerts_monitor())
    print(f"[{datetime.now()}] Alerts monitor started (logs to alerts.jsonl every 60s)")


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
        # ── Paper trading auto-poller state ──
        "paper_trading_alive": _paper_trading_task is not None and not _paper_trading_task.done() if _paper_trading_task else False,
        "paper_trading_cycle_count": _paper_trading_cycle_count,
        "paper_trading_last_run": _paper_trading_last_run,
        "paper_trading_errors": _paper_trading_errors,
        "paper_trading_interval_seconds": PAPER_TRADING_INTERVAL_SECONDS,
    }
