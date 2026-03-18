"""
Tests for null/missing statistics handling in strategy triggers.

Verifies that when key stats (xG, possession, SoT…) are absent from a CSV row,
the trigger returns None instead of treating the missing value as 0 and firing
a false positive.

Covers:
  - under35_late     (ACTIVE) — xG guard changed from 'both null' to 'any null'
  - under35_3goals   (ACTIVE) — xG guard added (previously used `or 0` default)
  - cs_00            (INACTIVE, preventive) — xG guard added
  - _detect_draw_filters — null xG now blocks when filter is active (xg_max < 1.0)
  - Regression: strategies already correctly guarded (under45_3goals, draw_xg_conv,
    momentum_xg, poss_extreme) still behave as expected.

Run: python tests/test_null_stats_handling.py
"""
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "betfair_scraper" / "dashboard" / "backend"))
sys.path.insert(0, str(ROOT / "betfair_scraper"))

from utils.strategy_triggers import (
    _detect_under35_late_trigger,
    _detect_under35_3goals_trigger,
    _detect_cs_00_trigger,
    _detect_draw_filters,
    _detect_under45_3goals_trigger,
    _detect_draw_xg_conv_trigger,
    _detect_momentum_xg_trigger,
    _detect_poss_extreme_trigger,
)

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


# ── Row builder ────────────────────────────────────────────────────────────────

def _row(
    minuto=70, gl=1, gv=1,
    xg_l=None, xg_v=None,
    poss_l=None, poss_v=None,
    sot_l=None, sot_v=None,
    back_under35=None, back_under45=None,
    back_draw=None, back_over25=None,
    back_rc_0_0=None, back_home=None, back_away=None,
    back_over05=None,
    estado="en_juego",
) -> dict:
    """Build a CSV-style row dict with string values (mirrors scraper output)."""
    def s(v):
        return str(v) if v is not None else ""
    return {
        "minuto":                  s(minuto),
        "goles_local":             s(gl),
        "goles_visitante":         s(gv),
        "xg_local":                s(xg_l),
        "xg_visitante":            s(xg_v),
        "posesion_local":          s(poss_l),
        "posesion_visitante":      s(poss_v),
        "tiros_puerta_local":      s(sot_l),
        "tiros_puerta_visitante":  s(sot_v),
        "back_under35":            s(back_under35),
        "back_under45":            s(back_under45),
        "back_draw":               s(back_draw),
        "back_over25":             s(back_over25),
        "back_rc_0_0":             s(back_rc_0_0),
        "back_home":               s(back_home),
        "back_away":               s(back_away),
        "back_over05":             s(back_over05),
        "estado_partido":          estado,
    }


# ── under35_late ───────────────────────────────────────────────────────────────

def test_under35_late_both_xg_null_rejects():
    """Both xG null -> trigger must return None (no false positive)."""
    row = _row(minuto=70, gl=1, gv=1, xg_l=None, xg_v=None, back_under35=1.5)
    result = _detect_under35_late_trigger([row], 0, {"xg_max": 2.5, "m_min": 65, "m_max": 81, "goals_exact": 2})
    if result is None:
        ok("under35_late: both xG null -> rejects")
    else:
        fail("under35_late: both xG null -> rejects", f"got {result}")


def test_under35_late_one_xg_null_rejects():
    """One xG null -> trigger must return None (partial data is insufficient)."""
    row = _row(minuto=70, gl=1, gv=1, xg_l=None, xg_v=1.0, back_under35=1.5)
    result = _detect_under35_late_trigger([row], 0, {"xg_max": 2.5, "m_min": 65, "m_max": 81, "goals_exact": 2})
    if result is None:
        ok("under35_late: one xG null -> rejects")
    else:
        fail("under35_late: one xG null -> rejects", f"got {result}")


def test_under35_late_both_xg_present_below_max_triggers():
    """Both xG present and below xg_max -> trigger fires normally."""
    row = _row(minuto=70, gl=1, gv=1, xg_l=1.0, xg_v=1.0, back_under35=1.5)
    result = _detect_under35_late_trigger([row], 0, {"xg_max": 2.5, "m_min": 65, "m_max": 81, "goals_exact": 2})
    if result is not None and abs(result["xg_total"] - 2.0) < 0.001:
        ok("under35_late: both xG present, below max -> triggers")
    else:
        fail("under35_late: both xG present, below max -> triggers", f"got {result}")


def test_under35_late_both_xg_present_above_max_rejects():
    """Both xG present but xg_total > xg_max -> trigger correctly rejects."""
    row = _row(minuto=70, gl=1, gv=1, xg_l=1.5, xg_v=1.5, back_under35=1.5)
    result = _detect_under35_late_trigger([row], 0, {"xg_max": 2.5, "m_min": 65, "m_max": 81, "goals_exact": 2})
    if result is None:
        ok("under35_late: xg_total > xg_max -> rejects")
    else:
        fail("under35_late: xg_total > xg_max -> rejects", f"got {result}")


def test_under35_late_previously_false_positive():
    """
    Regression: the old 'and' guard would let this through.
    xg_l=None, xg_v=1.0 -> old code: xg_total=1.0 -> passes xg_max=2.5.
    If real xg_l were 2.0, actual total=3.0 would fail. Must now reject.
    """
    row = _row(minuto=70, gl=1, gv=1, xg_l=None, xg_v=1.0, back_under35=1.5)
    result = _detect_under35_late_trigger([row], 0, {"xg_max": 2.5, "m_min": 65, "m_max": 81, "goals_exact": 2})
    if result is None:
        ok("under35_late: old false-positive case now correctly rejected")
    else:
        fail("under35_late: old false-positive case now correctly rejected", f"got {result}")


# ── under35_3goals ─────────────────────────────────────────────────────────────

def test_under35_3goals_both_xg_null_rejects():
    """Both xG null -> trigger must return None."""
    row = _row(minuto=70, gl=2, gv=1, xg_l=None, xg_v=None, back_under35=1.5)
    result = _detect_under35_3goals_trigger([row], 0, {"xg_max": 2.0, "m_min": 60, "m_max": 88})
    if result is None:
        ok("under35_3goals: both xG null -> rejects")
    else:
        fail("under35_3goals: both xG null -> rejects", f"got {result}")


def test_under35_3goals_one_xg_null_rejects():
    """One xG null -> trigger must return None."""
    row = _row(minuto=70, gl=2, gv=1, xg_l=0.8, xg_v=None, back_under35=1.5)
    result = _detect_under35_3goals_trigger([row], 0, {"xg_max": 2.0, "m_min": 60, "m_max": 88})
    if result is None:
        ok("under35_3goals: one xG null -> rejects")
    else:
        fail("under35_3goals: one xG null -> rejects", f"got {result}")


def test_under35_3goals_both_xg_present_below_max_triggers():
    """Both xG present and below xg_max -> trigger fires normally."""
    row = _row(minuto=70, gl=2, gv=1, xg_l=0.9, xg_v=0.8, back_under35=1.5)
    result = _detect_under35_3goals_trigger([row], 0, {"xg_max": 2.0, "m_min": 60, "m_max": 88})
    if result is not None and abs(result["xg_total"] - 1.7) < 0.001:
        ok("under35_3goals: both xG present, below max -> triggers")
    else:
        fail("under35_3goals: both xG present, below max -> triggers", f"got {result}")


def test_under35_3goals_both_xg_present_above_max_rejects():
    """Both xG present but xg_total > xg_max -> correctly rejects."""
    row = _row(minuto=70, gl=2, gv=1, xg_l=1.2, xg_v=1.2, back_under35=1.5)
    result = _detect_under35_3goals_trigger([row], 0, {"xg_max": 2.0, "m_min": 60, "m_max": 88})
    if result is None:
        ok("under35_3goals: xg_total > xg_max -> rejects")
    else:
        fail("under35_3goals: xg_total > xg_max -> rejects", f"got {result}")


def test_under35_3goals_previously_false_positive():
    """
    Regression: old code `(_to_float(...) or 0) + (_to_float(...) or 0)`
    would produce xg_total=0.0 when both null -> passes xg_max=2.0 filter.
    Must now reject.
    """
    row = _row(minuto=70, gl=2, gv=1, xg_l=None, xg_v=None, back_under35=1.5)
    result = _detect_under35_3goals_trigger([row], 0, {"xg_max": 2.0, "m_min": 60, "m_max": 88})
    if result is None:
        ok("under35_3goals: old false-positive (null->0->passes) now correctly rejected")
    else:
        fail("under35_3goals: old false-positive (null->0->passes) now correctly rejected", f"got {result}")


# ── cs_00 (preventive — strategy currently disabled) ──────────────────────────

def test_cs_00_both_xg_null_rejects():
    """cs_00: both xG null -> trigger must return None (preventive guard)."""
    row = _row(minuto=30, gl=0, gv=0, xg_l=None, xg_v=None, back_rc_0_0=8.0, sot_l=1, sot_v=1)
    result = _detect_cs_00_trigger([row], 0, {"xg_max": 1.5, "m_min": 28, "m_max": 33, "odds_min": 5.0, "odds_max": 12.0})
    if result is None:
        ok("cs_00: both xG null -> rejects")
    else:
        fail("cs_00: both xG null -> rejects", f"got {result}")


def test_cs_00_one_xg_null_rejects():
    """cs_00: one xG null -> trigger must return None."""
    row = _row(minuto=30, gl=0, gv=0, xg_l=None, xg_v=0.4, back_rc_0_0=8.0, sot_l=1, sot_v=1)
    result = _detect_cs_00_trigger([row], 0, {"xg_max": 1.5, "m_min": 28, "m_max": 33, "odds_min": 5.0, "odds_max": 12.0})
    if result is None:
        ok("cs_00: one xG null -> rejects")
    else:
        fail("cs_00: one xG null -> rejects", f"got {result}")


def test_cs_00_both_xg_present_below_max_triggers():
    """cs_00: both xG present and below xg_max -> fires normally."""
    row = _row(minuto=30, gl=0, gv=0, xg_l=0.3, xg_v=0.3, back_rc_0_0=8.0, sot_l=1, sot_v=1)
    result = _detect_cs_00_trigger([row], 0, {"xg_max": 1.5, "m_min": 28, "m_max": 33, "odds_min": 5.0, "odds_max": 12.0})
    if result is not None:
        ok("cs_00: both xG present, below max -> triggers")
    else:
        fail("cs_00: both xG present, below max -> triggers", f"got None")


def test_cs_00_previously_false_positive():
    """
    Regression: old code `_to_float(...) or 0` -> xg_total=0.0 when both null,
    passing xg_max=1.5 filter. Must now reject.
    """
    row = _row(minuto=30, gl=0, gv=0, xg_l=None, xg_v=None, back_rc_0_0=8.0, sot_l=0, sot_v=0)
    result = _detect_cs_00_trigger([row], 0, {"xg_max": 1.5, "m_min": 28, "m_max": 33, "odds_min": 5.0, "odds_max": 12.0})
    if result is None:
        ok("cs_00: old false-positive (null->0->passes) now correctly rejected")
    else:
        fail("cs_00: old false-positive (null->0->passes) now correctly rejected", f"got {result}")


# ── _detect_draw_filters ───────────────────────────────────────────────────────

def test_draw_filters_null_xg_blocks_when_filter_active():
    """Null xG must block when xg_max < 1.0 (filter is active)."""
    result = _detect_draw_filters(xg_total=None, poss_diff=None, shots_total=None, cfg={"xg_max": 0.6})
    if not result["passes"]:
        ok("draw_filters: null xG blocks when xg_max=0.6 (active filter)")
    else:
        fail("draw_filters: null xG blocks when xg_max=0.6 (active filter)", "passes=True, expected False")


def test_draw_filters_null_xg_passes_when_sentinel():
    """Null xG passes when xg_max >= 1.0 (sentinel = filter off)."""
    result = _detect_draw_filters(xg_total=None, poss_diff=None, shots_total=None, cfg={"xg_max": 1.0})
    if result["passes"]:
        ok("draw_filters: null xG passes when xg_max=1.0 (sentinel/off)")
    else:
        fail("draw_filters: null xG passes when xg_max=1.0 (sentinel/off)", "passes=False, expected True")


def test_draw_filters_present_xg_below_max_passes():
    """xG present and below xg_max -> passes."""
    result = _detect_draw_filters(xg_total=0.4, poss_diff=None, shots_total=None, cfg={"xg_max": 0.6})
    if result["passes"]:
        ok("draw_filters: xg_total=0.4 < xg_max=0.6 -> passes")
    else:
        fail("draw_filters: xg_total=0.4 < xg_max=0.6 -> passes", "passes=False")


def test_draw_filters_present_xg_above_max_rejects():
    """xG present and above xg_max -> rejects."""
    result = _detect_draw_filters(xg_total=0.8, poss_diff=None, shots_total=None, cfg={"xg_max": 0.6})
    if not result["passes"]:
        ok("draw_filters: xg_total=0.8 > xg_max=0.6 -> rejects")
    else:
        fail("draw_filters: xg_total=0.8 > xg_max=0.6 -> rejects", "passes=True, expected False")


def test_draw_filters_previously_false_positive():
    """
    Regression: old code `xg_total is None` counted as passing the filter even
    when xg_max=0.6 (active). Must now block.
    """
    result = _detect_draw_filters(xg_total=None, poss_diff=None, shots_total=None, cfg={"xg_max": 0.6})
    if not result["passes"]:
        ok("draw_filters: old false-positive (null bypassed active filter) now correctly blocked")
    else:
        fail("draw_filters: old false-positive (null bypassed active filter) now correctly blocked", "passes=True")


# ── Regression: already-guarded strategies ────────────────────────────────────

def test_under45_3goals_null_xg_still_rejects():
    """under45_3goals already had correct guard — verify it still rejects null xG."""
    row = _row(minuto=70, gl=2, gv=1, xg_l=None, xg_v=None, back_under45=1.5)
    result = _detect_under45_3goals_trigger([row], 0, {"xg_max": 2.5, "m_min": 62, "m_max": 88})
    if result is None:
        ok("under45_3goals: null xG still rejects (regression)")
    else:
        fail("under45_3goals: null xG still rejects (regression)", f"got {result}")


def test_draw_xg_conv_null_xg_still_rejects():
    """draw_xg_conv already had correct guard — verify it still rejects null xG."""
    row = _row(minuto=70, gl=1, gv=1, xg_l=None, xg_v=None, back_draw=3.5)
    result = _detect_draw_xg_conv_trigger([row], 0, {"xg_diff_max": 1.0, "m_min": 60, "m_max": 83})
    if result is None:
        ok("draw_xg_conv: null xG still rejects (regression)")
    else:
        fail("draw_xg_conv: null xG still rejects (regression)", f"got {result}")


def test_draw_xg_conv_one_xg_null_still_rejects():
    """draw_xg_conv: one xG null -> rejects (regression)."""
    row = _row(minuto=70, gl=1, gv=1, xg_l=1.0, xg_v=None, back_draw=3.5)
    result = _detect_draw_xg_conv_trigger([row], 0, {"xg_diff_max": 1.0, "m_min": 60, "m_max": 83})
    if result is None:
        ok("draw_xg_conv: one xG null still rejects (regression)")
    else:
        fail("draw_xg_conv: one xG null still rejects (regression)", f"got {result}")


def test_momentum_xg_null_xg_still_rejects():
    """momentum_xg already had correct guard — verify it still rejects null xG."""
    row = _row(minuto=50, gl=0, gv=1, xg_l=None, xg_v=None,
               sot_l=3, sot_v=1, back_home=2.5, back_away=1.8)
    result = _detect_momentum_xg_trigger([row], 0, {
        "min_m": 10, "max_m": 80,
        "sot_min": 2, "sot_ratio_min": 1.5,
        "xg_underperf_min": 0.3, "odds_min": 1.5, "odds_max": 4.0,
    })
    if result is None:
        ok("momentum_xg: null xG still rejects (regression)")
    else:
        fail("momentum_xg: null xG still rejects (regression)", f"got {result}")


def test_poss_extreme_null_poss_still_rejects():
    """poss_extreme already had correct guard — verify it still rejects null possession."""
    row = _row(minuto=40, gl=0, gv=0, poss_l=None, poss_v=None, back_over05=1.3)
    result = _detect_poss_extreme_trigger([row], 0, {"poss_min": 55, "m_min": 30, "m_max": 53})
    if result is None:
        ok("poss_extreme: null possession still rejects (regression)")
    else:
        fail("poss_extreme: null possession still rejects (regression)", f"got {result}")


# ── Runner ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n=== test_null_stats_handling.py ===\n")

    print("--- under35_late (ACTIVE) ---")
    test_under35_late_both_xg_null_rejects()
    test_under35_late_one_xg_null_rejects()
    test_under35_late_both_xg_present_below_max_triggers()
    test_under35_late_both_xg_present_above_max_rejects()
    test_under35_late_previously_false_positive()

    print("\n--- under35_3goals (ACTIVE) ---")
    test_under35_3goals_both_xg_null_rejects()
    test_under35_3goals_one_xg_null_rejects()
    test_under35_3goals_both_xg_present_below_max_triggers()
    test_under35_3goals_both_xg_present_above_max_rejects()
    test_under35_3goals_previously_false_positive()

    print("\n--- cs_00 (preventive, currently disabled) ---")
    test_cs_00_both_xg_null_rejects()
    test_cs_00_one_xg_null_rejects()
    test_cs_00_both_xg_present_below_max_triggers()
    test_cs_00_previously_false_positive()

    print("\n--- _detect_draw_filters (preventive) ---")
    test_draw_filters_null_xg_blocks_when_filter_active()
    test_draw_filters_null_xg_passes_when_sentinel()
    test_draw_filters_present_xg_below_max_passes()
    test_draw_filters_present_xg_above_max_rejects()
    test_draw_filters_previously_false_positive()

    print("\n--- Regression: already-guarded strategies ---")
    test_under45_3goals_null_xg_still_rejects()
    test_draw_xg_conv_null_xg_still_rejects()
    test_draw_xg_conv_one_xg_null_still_rejects()
    test_momentum_xg_null_xg_still_rejects()
    test_poss_extreme_null_poss_still_rejects()

    print(f"\n=== Result: {PASS} passed, {FAIL} failed ===")
    sys.exit(0 if FAIL == 0 else 1)
