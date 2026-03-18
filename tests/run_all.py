"""
Run all test suites and show a consolidated summary.

Usage:
    python tests/run_all.py
    python tests/run_all.py --verbose   # pass --verbose to test_system_integrity
"""
import sys, io
import subprocess
import re
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT   = Path(__file__).resolve().parent.parent
TESTS  = Path(__file__).resolve().parent

SUITES = [
    ("NaN Handling",       TESTS / "test_nan_handling.py",           []),
    ("Null Stats",         TESTS / "test_null_stats_handling.py",    []),
    ("Registry Collapse",  TESTS / "test_registry_collapse.py",      []),
    ("System Integrity",   TESTS / "test_system_integrity.py",       ["--verbose"] if "--verbose" in sys.argv else []),
    ("Param Fidelity",     TESTS / "test_param_fidelity.py",         []),
]

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

    sys.exit(0 if suites_failed == 0 else 1)


if __name__ == "__main__":
    main()
