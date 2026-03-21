"""
Run all test suites and show a consolidated summary.

Usage:
    python tests/run_all.py
    python tests/run_all.py --verbose   # pass --verbose to test_system_integrity

Results are saved to betfair_scraper/logs/test_results.json so the
dashboard Test Cases view can display them.
"""
import sys, io
import json
import subprocess
import re
import time
from datetime import datetime
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT   = Path(__file__).resolve().parent.parent
TESTS  = Path(__file__).resolve().parent

def _discover_suites():
    """Auto-discover all test_*.py files in the tests/ directory."""
    verbose = "--verbose" in sys.argv
    suites = []
    for script in sorted(TESTS.glob("test_*.py")):
        # Derive label from filename: test_nan_handling.py -> "NaN Handling"
        label = script.stem.replace("test_", "").replace("_", " ").title()
        args = ["--verbose"] if verbose and script.name == "test_system_integrity.py" else []
        suites.append((label, script, args))
    return suites

SUITES = _discover_suites()

SEP = "─" * 70

def run_suite(label: str, script: Path, extra_args: list) -> tuple[int, int, bool, str]:
    """Run a test script, return (passed, failed, ok, output)."""
    cmd = [sys.executable, str(script)] + extra_args
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", cwd=str(ROOT))
    elapsed = time.time() - t0
    output = result.stdout + (("\n[stderr]\n" + result.stderr) if result.stderr.strip() else "")

    # Try to parse pass/fail counts from common patterns
    passed = failed = 0
    for line in output.splitlines():
        # "14 passed, 0 failed"  /  "Results: 14 passed, 0 failed"  /  "RESULTADO: 73/73 passed"
        m = re.search(r'(\d+)\s*/?\s*\d*\s*pass', line, re.IGNORECASE)
        if m:
            passed = int(m.group(1))
        m = re.search(r'(\d+)\s*fail', line, re.IGNORECASE)
        if m:
            failed = int(m.group(1))

    ok = result.returncode == 0
    return passed, failed, ok, output, round(elapsed, 1)


def main():
    print(f"\n{'='*70}")
    print("  RUN ALL TESTS — Betfair Dashboard")
    print(f"{'='*70}\n")

    results = []
    for label, script, args in SUITES:
        print(f"{SEP}")
        print(f"  ▶  {label}  ({script.name})")
        print(SEP)
        passed, failed, ok, output, elapsed = run_suite(label, script, args)
        print(output.rstrip())
        results.append((label, passed, failed, ok, elapsed))
        print()

    # ── Consolidated summary ────────────────────────────────────────────────
    print(f"{'='*70}")
    print("  RESUMEN CONSOLIDADO")
    print(f"{'='*70}")

    total_pass = total_fail = 0
    suites_failed = 0
    for label, passed, failed, ok, elapsed in results:
        status = "✓ PASS" if ok else "✗ FAIL"
        detail = f"{passed} passed, {failed} failed" if (passed or failed) else ("exit 0" if ok else "exit 1 (crash)")
        print(f"  {status}  {label:<25}  {detail}  ({elapsed}s)")
        total_pass += passed
        total_fail += failed
        if not ok:
            suites_failed += 1

    print(SEP)
    grand = total_pass + total_fail
    if suites_failed == 0:
        print(f"  TOTAL: {total_pass}/{grand} passed — ALL PASS ✓")
    else:
        fail_detail = f"{total_fail} checks failed" if total_fail else f"{suites_failed} suite(s) crashed"
        print(f"  TOTAL: {total_pass}/{grand} passed — {fail_detail} ✗")
    print(f"{'='*70}\n")

    # ── Save results to JSON for dashboard consumption ────────────────────
    _save_dashboard_results(results)

    sys.exit(0 if suites_failed == 0 else 1)


def _save_dashboard_results(results: list):
    """Persist run results to test_results.json so the dashboard can display them."""
    results_file = ROOT / "betfair_scraper" / "logs" / "test_results.json"
    results_file.parent.mkdir(parents=True, exist_ok=True)

    suites_data = []
    for label, passed, failed, ok, elapsed in results:
        suite_id = "test_" + label.lower().replace(" ", "_")
        suites_data.append({
            "id": suite_id,
            "label": label,
            "passed": passed,
            "failed": failed,
            "ok": ok,
            "elapsed": elapsed,
            "output": "",  # CLI runs don't capture per-suite output here
        })

    run_result = {
        "timestamp": datetime.now().isoformat(),
        "total_passed": sum(s["passed"] for s in suites_data),
        "total_failed": sum(s["failed"] for s in suites_data),
        "all_ok": all(s["ok"] for s in suites_data),
        "suites": suites_data,
    }

    # Load existing history
    history = []
    if results_file.exists():
        try:
            with open(results_file, encoding="utf-8") as f:
                data = json.load(f)
            history = data.get("history", [])
        except Exception:
            pass

    history.insert(0, run_result)
    history = history[:30]

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump({"last_run": run_result, "history": history}, f, indent=2, ensure_ascii=False)

    print(f"  Results saved to {results_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
