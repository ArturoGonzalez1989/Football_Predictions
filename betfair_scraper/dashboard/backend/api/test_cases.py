"""
Test Cases API — run and view test suite results.

Endpoints:
  GET  /api/test-cases          → last run results + suite list
  POST /api/test-cases/run      → trigger a full run (or single suite)
  POST /api/test-cases/run-bg   → trigger run in background (non-blocking)
"""

import sys
import json
import re
import subprocess
import time
import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/test-cases", tags=["test-cases"])

ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent  # Furbo/
TESTS_DIR = ROOT / "tests"
RESULTS_FILE = ROOT / "betfair_scraper" / "logs" / "test_results.json"

# In-memory state for background runs
_bg_running = False
_bg_lock = threading.Lock()


def _discover_suites() -> list[dict]:
    """Auto-discover test_*.py files in tests/ directory."""
    suites = []
    if not TESTS_DIR.exists():
        return suites
    for script in sorted(TESTS_DIR.glob("test_*.py")):
        label = script.stem.replace("test_", "").replace("_", " ").title()
        suites.append({"id": script.stem, "label": label, "file": script.name})
    return suites


def _run_single_suite(script: Path, timeout: int = 300) -> dict:
    """Run a single test suite and parse results."""
    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
            cwd=str(ROOT),
        )
        elapsed = round(time.time() - t0, 1)
        output = result.stdout + (("\n[stderr]\n" + result.stderr) if result.stderr.strip() else "")

        passed = failed = 0
        for line in output.splitlines():
            m = re.search(r'(\d+)\s*/?\s*\d*\s*pass', line, re.IGNORECASE)
            if m:
                passed = int(m.group(1))
            m = re.search(r'(\d+)\s*fail', line, re.IGNORECASE)
            if m:
                failed = int(m.group(1))

        return {
            "id": script.stem,
            "label": script.stem.replace("test_", "").replace("_", " ").title(),
            "passed": passed,
            "failed": failed,
            "ok": result.returncode == 0,
            "elapsed": elapsed,
            "output": output[-3000:],  # Last 3000 chars to avoid huge payloads
        }
    except subprocess.TimeoutExpired:
        return {
            "id": script.stem,
            "label": script.stem.replace("test_", "").replace("_", " ").title(),
            "passed": 0, "failed": 0, "ok": False,
            "elapsed": round(time.time() - t0, 1),
            "output": f"TIMEOUT after {timeout}s",
        }
    except Exception as e:
        return {
            "id": script.stem,
            "label": script.stem.replace("test_", "").replace("_", " ").title(),
            "passed": 0, "failed": 0, "ok": False,
            "elapsed": round(time.time() - t0, 1),
            "output": str(e),
        }


def _run_all_suites() -> dict:
    """Run all test suites and return consolidated results."""
    suites_results = []
    for script in sorted(TESTS_DIR.glob("test_*.py")):
        suites_results.append(_run_single_suite(script))

    total_pass = sum(s["passed"] for s in suites_results)
    total_fail = sum(s["failed"] for s in suites_results)
    all_ok = all(s["ok"] for s in suites_results)

    return {
        "timestamp": datetime.now().isoformat(),
        "total_passed": total_pass,
        "total_failed": total_fail,
        "all_ok": all_ok,
        "suites": suites_results,
    }


def _save_results(run_result: dict):
    """Save results to JSON, keeping last 30 runs in history."""
    history = []
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            history = data.get("history", [])
        except Exception:
            pass

    # Add current run to history (keep last 30)
    history.insert(0, run_result)
    history = history[:30]

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_run": run_result, "history": history}, f, indent=2, ensure_ascii=False)


def _load_results() -> dict | None:
    """Load saved results from disk."""
    if not RESULTS_FILE.exists():
        return None
    try:
        with open(RESULTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ── Endpoints ───────────────────────────────────────────────────────────

@router.get("")
def get_test_cases():
    """Return available suites + last run results."""
    suites = _discover_suites()
    saved = _load_results()
    return {
        "suites": suites,
        "last_run": saved.get("last_run") if saved else None,
        "history_count": len(saved.get("history", [])) if saved else 0,
        "is_running": _bg_running,
    }


@router.get("/history")
def get_history(limit: int = 10):
    """Return last N test run results."""
    saved = _load_results()
    if not saved:
        return {"history": []}
    history = saved.get("history", [])
    return {"history": history[:limit]}


@router.post("/run")
def run_tests(suite_id: str | None = None):
    """Run all tests (or a single suite) synchronously. Returns results."""
    global _bg_running
    with _bg_lock:
        if _bg_running:
            return JSONResponse({"ok": False, "error": "Tests already running"}, status_code=409)
        _bg_running = True

    try:
        if suite_id:
            script = TESTS_DIR / f"{suite_id}.py"
            if not script.exists():
                return JSONResponse({"ok": False, "error": f"Suite not found: {suite_id}"}, status_code=404)
            result = _run_single_suite(script)
            run_result = {
                "timestamp": datetime.now().isoformat(),
                "total_passed": result["passed"],
                "total_failed": result["failed"],
                "all_ok": result["ok"],
                "suites": [result],
                "partial": True,
            }
        else:
            run_result = _run_all_suites()

        _save_results(run_result)
        return {"ok": True, "result": run_result}
    finally:
        with _bg_lock:
            _bg_running = False


@router.post("/run-bg")
def run_tests_background():
    """Trigger test run in a background thread (non-blocking)."""
    global _bg_running
    with _bg_lock:
        if _bg_running:
            return JSONResponse({"ok": False, "error": "Tests already running"}, status_code=409)
        _bg_running = True

    def _worker():
        global _bg_running
        try:
            result = _run_all_suites()
            _save_results(result)
            print(f"[{datetime.now()}] [TEST-CASES] Background run complete: "
                  f"{result['total_passed']} passed, {result['total_failed']} failed")
        except Exception as e:
            print(f"[{datetime.now()}] [TEST-CASES] Background run error: {e}")
        finally:
            with _bg_lock:
                _bg_running = False

    threading.Thread(target=_worker, daemon=True).start()
    return {"ok": True, "message": "Test run started in background"}
