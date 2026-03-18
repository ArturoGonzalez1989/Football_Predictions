"""
Tests for NaN/pre_partido row handling in BT and LIVE pipelines.

Verifies that trailing pre_partido rows with NaN scores (scraper noise after
match end) are correctly stripped and do not cause:
  1. BT to skip entire matches (was: ValueError on rows[-1] with NaN scores)
  2. BT trigger iteration to reset first_seen via NaN-minuto rows
  3. BT/LIVE divergence on matches with this data pattern

Run: python tests/test_nan_handling.py
"""
import sys
import csv
import io
import json
import builtins
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
sys.path.insert(0, str(ROOT / "betfair_scraper"))

from utils.csv_loader import _final_result_row, _strip_trailing_pre_partido_rows, _to_float

PASS = 0
FAIL = 0


def ok(name: str):
    global PASS
    PASS += 1
    print(f"  PASS  {name}")


def fail(name: str, detail: str = ""):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_row(minuto, goles_local, goles_visitante, estado="en_juego", poss_l=None, poss_v=None, back_over05=None):
    return {
        "minuto":            str(minuto) if minuto is not None else "",
        "goles_local":       str(goles_local) if goles_local is not None else "",
        "goles_visitante":   str(goles_visitante) if goles_visitante is not None else "",
        "estado_partido":    estado,
        "posesion_local":    str(poss_l) if poss_l is not None else "",
        "posesion_visitante": str(poss_v) if poss_v is not None else "",
        "back_over05":       str(back_over05) if back_over05 is not None else "",
    }


# ── Tests: _strip_trailing_pre_partido_rows ────────────────────────────────────

def test_strip_removes_trailing_pre_partido_nan():
    """Trailing pre_partido rows with NaN scores are removed."""
    rows = [
        _make_row(80, 1, 0, "en_juego"),
        _make_row(90, 1, 1, "en_juego"),
        _make_row(None, None, None, "pre_partido"),  # trailing noise
        _make_row(None, None, None, "pre_partido"),  # trailing noise
    ]
    result = _strip_trailing_pre_partido_rows(rows)
    if len(result) == 2 and result[-1]["minuto"] == "90":
        ok("strip_removes_trailing_pre_partido_nan")
    else:
        fail("strip_removes_trailing_pre_partido_nan", f"got {len(result)} rows, last minuto={result[-1]['minuto'] if result else 'N/A'}")


def test_strip_preserves_leading_pre_partido():
    """Pre_partido rows at the START (before kickoff) are preserved."""
    rows = [
        _make_row(None, None, None, "pre_partido"),  # pre-kickoff row — keep
        _make_row(1, 0, 0, "en_juego"),
        _make_row(90, 1, 0, "en_juego"),
    ]
    result = _strip_trailing_pre_partido_rows(rows)
    if len(result) == 3:
        ok("strip_preserves_leading_pre_partido")
    else:
        fail("strip_preserves_leading_pre_partido", f"got {len(result)} rows")


def test_strip_keeps_pre_partido_with_scores():
    """A pre_partido row WITH valid scores is preserved (edge case)."""
    rows = [
        _make_row(80, 1, 0, "en_juego"),
        _make_row(None, 1, 0, "pre_partido"),  # has scores — keep
    ]
    result = _strip_trailing_pre_partido_rows(rows)
    if len(result) == 2:
        ok("strip_keeps_pre_partido_with_scores")
    else:
        fail("strip_keeps_pre_partido_with_scores", f"got {len(result)} rows")


def test_strip_all_noise_returns_original():
    """If all rows are pre_partido with NaN scores, return original (fail-safe)."""
    rows = [
        _make_row(None, None, None, "pre_partido"),
        _make_row(None, None, None, "pre_partido"),
    ]
    result = _strip_trailing_pre_partido_rows(rows)
    # Should return original rows rather than empty list (fail-safe)
    if result == rows:
        ok("strip_all_noise_returns_original")
    else:
        fail("strip_all_noise_returns_original", f"got {len(result)} rows")


def test_strip_no_op_on_clean_data():
    """Clean data (no trailing noise) passes through unchanged."""
    rows = [
        _make_row(45, 0, 0, "descanso"),
        _make_row(90, 1, 0, "en_juego"),
    ]
    result = _strip_trailing_pre_partido_rows(rows)
    if result == rows:
        ok("strip_no_op_on_clean_data")
    else:
        fail("strip_no_op_on_clean_data", f"got {len(result)} rows")


# ── Tests: _final_result_row ───────────────────────────────────────────────────

def test_final_result_row_skips_trailing_nan():
    """_final_result_row returns last row with valid scores, skipping NaN tail."""
    rows = [
        _make_row(85, 1, 0, "en_juego"),
        _make_row(90, 1, 1, "en_juego"),
        _make_row(None, None, None, "pre_partido"),
        _make_row(None, None, None, "pre_partido"),
    ]
    result = _final_result_row(rows)
    if result and result["goles_local"] == "1" and result["goles_visitante"] == "1":
        ok("final_result_row_skips_trailing_nan")
    else:
        fail("final_result_row_skips_trailing_nan", f"got {result}")


def test_final_result_row_prefers_finalizado():
    """_final_result_row prefers a 'finalizado' row over last valid row."""
    rows = [
        _make_row(90, 2, 1, "finalizado"),
        _make_row(91, 2, 2, "en_juego"),   # later row but not finalizado
    ]
    result = _final_result_row(rows)
    if result and result["goles_local"] == "2" and result["goles_visitante"] == "1":
        ok("final_result_row_prefers_finalizado")
    else:
        fail("final_result_row_prefers_finalizado", f"got {result}")


def test_final_result_row_returns_none_when_no_scores():
    """_final_result_row returns None if no row has valid scores."""
    rows = [
        _make_row(None, None, None, "pre_partido"),
        _make_row(None, None, None, "pre_partido"),
    ]
    result = _final_result_row(rows)
    if result is None:
        ok("final_result_row_returns_none_when_no_scores")
    else:
        fail("final_result_row_returns_none_when_no_scores", f"got {result}")


# ── Integration tests: affected real matches ───────────────────────────────────

def _check_match_in_bt(match_csv_name: str, expected_min_bets: int = 1):
    """Verify that a given match CSV produces at least expected_min_bets in BT after fix."""
    from utils import csv_reader
    # Clear cache to force re-computation
    try:
        csv_reader.clear_analytics_cache()
    except Exception:
        pass

    DATA_DIR = ROOT / "betfair_scraper" / "data"
    csv_path = DATA_DIR / match_csv_name
    if not csv_path.exists():
        print(f"  SKIP  {match_csv_name} (file not found)")
        return

    bt = csv_reader.analyze_cartera()
    bets = bt.get("bets", [])

    # Extract match_id from filename
    stem = csv_path.stem
    match_id = stem[len("partido_"):] if stem.startswith("partido_") else stem

    match_bets = [b for b in bets if b.get("match_id") == match_id]
    if len(match_bets) >= expected_min_bets:
        ok(f"match_in_bt: {match_id[:50]} ({len(match_bets)} bets)")
    else:
        fail(f"match_in_bt: {match_id[:50]}", f"expected >={expected_min_bets} bets, got {len(match_bets)}")


def test_affected_matches_now_in_bt():
    """
    Regression: these 6 matches previously produced 0 BT bets due to trailing
    pre_partido rows with NaN scores causing rows[-1] to fail score extraction.
    After the fix they must appear in analyze_cartera() results.
    """
    affected = [
        "partido_oxford-united-charlton-apuestas-35334820.csv",
        "partido_coventry-southampton-apuestas-35338316.csv",
        "partido_inter-atalanta-apuestas-35323190.csv",
        # charleroi-oh-leuven removed: no active BACK strategy triggers for this match
        # (previously relied on a LAY strategy that has been permanently disabled)
        "partido_red-star-dunkerque-apuestas-35353636.csv",
        "partido_union-st-gilloise-fcv-dender-apuestas-35347631.csv",
    ]
    for fname in affected:
        _check_match_in_bt(fname, expected_min_bets=1)


# ── Runner ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== test_nan_handling.py ===\n")

    print("--- _strip_trailing_pre_partido_rows ---")
    test_strip_removes_trailing_pre_partido_nan()
    test_strip_preserves_leading_pre_partido()
    test_strip_keeps_pre_partido_with_scores()
    test_strip_all_noise_returns_original()
    test_strip_no_op_on_clean_data()

    print("\n--- _final_result_row ---")
    test_final_result_row_skips_trailing_nan()
    test_final_result_row_prefers_finalizado()
    test_final_result_row_returns_none_when_no_scores()

    print("\n--- Integration: affected matches in BT ---")
    test_affected_matches_now_in_bt()

    print(f"\n=== Result: {PASS} passed, {FAIL} failed ===")
    sys.exit(0 if FAIL == 0 else 1)
