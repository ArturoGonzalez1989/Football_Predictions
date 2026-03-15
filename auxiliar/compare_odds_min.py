"""
compare_odds_min.py — Compare BT results before/after odds_min optimization.

Baseline: analisis/bt_baseline_pre_odds_min.csv  (individual bets, pre-change)
New:      auxiliar/bt_optimizer_results.json      (aggregated metrics, post-change)

Usage:
    python auxiliar/compare_odds_min.py
"""

import csv
import json
import math
from pathlib import Path
from typing import Optional

ROOT     = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "analisis" / "bt_baseline_pre_odds_min.csv"
NEW_JSON = ROOT / "auxiliar" / "bt_optimizer_results.json"

# Verdict thresholds
N_DROP_MAX   = 0.20   # allow up to 20% drop in N
ROI_THRESHOLD = 1.0   # improvement threshold in ROI pp


def _wilson_low(wins: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((centre - margin) / denom * 100, 1)


def _aggregate_baseline(path: Path) -> dict[str, dict]:
    """Aggregate individual bets CSV into per-strategy metrics."""
    buckets: dict[str, list] = {}
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                strat = row.get("strategy", "").strip()
                if not strat:
                    continue
                pl = row.get("pl", "")
                won = row.get("won", "").strip().lower()
                try:
                    pl_f = float(pl)
                except (ValueError, TypeError):
                    continue
                is_win = won in ("true", "1", "yes")
                buckets.setdefault(strat, []).append((pl_f, is_win))
    except FileNotFoundError:
        print(f"Baseline not found: {path}")
        return {}

    results = {}
    for strat, bets in buckets.items():
        n = len(bets)
        wins = sum(1 for _, w in bets if w)
        pl_sum = sum(p for p, _ in bets)
        roi = pl_sum / n * 100 if n else 0
        wr = wins / n * 100 if n else 0
        ci_low = _wilson_low(wins, n)
        results[strat] = {"n": n, "wins": wins, "wr": round(wr, 1),
                          "roi": round(roi, 1), "ci_low": ci_low}
    return results


def _load_new(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("individual", {})


# ── Terminal colors ──────────────────────────────────────────────────────────
RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
ORANGE = "\033[93m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

def _c(text, color): return f"{color}{text}{RESET}"
def _fmt(v, d=1, s=""): return f"{v:.{d}f}{s}" if v is not None else "—"


def main():
    baseline = _aggregate_baseline(BASELINE)
    new_res  = _load_new(NEW_JSON)

    if not baseline:
        print("Baseline CSV vacío o no encontrado.")
        return
    if not new_res:
        print("bt_optimizer_results.json vacío o no encontrado.")
        return

    print(f"\n{BOLD}=== odds_min Optimization: Before vs After ==={RESET}")
    print(f"Baseline : {BASELINE.name}  ({len(baseline)} estrategias)")
    print(f"New      : {NEW_JSON.name}  ({len(new_res)} estrategias)")
    print()

    # Header
    w = 28
    print(f"{'Estrategia':<{w}} {'N_b':>5} {'N_a':>5} {'ROI_b':>7} {'ROI_a':>7} "
          f"{'CI_b':>6} {'CI_a':>6} {'odds_min':>8}  Veredicto")
    print("-" * 105)

    improvements = regressions = unchanged = new_strategies = 0

    all_keys = sorted(set(baseline) | set(new_res))

    for key in all_keys:
        b = baseline.get(key)
        a = new_res.get(key)

        if b is None:
            new_strategies += 1
            print(f"{key:<{w}} {DIM}(nueva estrategia, no en baseline){RESET}")
            continue
        if a is None:
            print(f"{key:<{w}} {DIM}(no aprobó quality gates en nuevo BT){RESET}")
            continue

        n_b, roi_b, ci_b = b["n"], b["roi"], b["ci_low"]
        n_a, roi_a, ci_a = a["n"], a["roi"], a["ci_low"]
        odds_min_a = a.get("params", {}).get("odds_min", 0)

        n_drop = (n_b - n_a) / n_b if n_b else 0

        # Verdict
        if n_b and n_drop > N_DROP_MAX:
            verdict = f"ROJO: N cae {n_drop*100:.0f}% (demasiadas apuestas filtradas)"
            verdict_color = RED
            regressions += 1
        elif roi_a > roi_b + ROI_THRESHOLD:
            verdict = f"VERDE: ROI +{roi_a - roi_b:.1f}pp"
            verdict_color = GREEN
            improvements += 1
        elif ci_a > ci_b + ROI_THRESHOLD and roi_a >= roi_b - 1.0:
            verdict = f"VERDE: CI_low +{ci_a - ci_b:.1f}pp"
            verdict_color = GREEN
            improvements += 1
        elif roi_a < roi_b - ROI_THRESHOLD:
            verdict = f"ROJO: ROI -{roi_b - roi_a:.1f}pp (regresión)"
            verdict_color = RED
            regressions += 1
        else:
            verdict = "NARANJA: sin cambio significativo"
            verdict_color = ORANGE
            unchanged += 1

        odds_min_str = f"{odds_min_a:.2f}" if odds_min_a else "0 (no filtro)"

        print(f"{key:<{w}} {n_b:>5} {n_a:>5} {roi_b:>6.1f}% {roi_a:>6.1f}% "
              f"{ci_b:>5.1f}% {ci_a:>5.1f}% {odds_min_str:>8}  "
              f"{_c(verdict, verdict_color)}")

    print("-" * 105)
    print(f"\nResumen: {_c(str(improvements), GREEN)} mejoras  "
          f"{_c(str(regressions), RED)} regresiones  "
          f"{_c(str(unchanged), ORANGE)} sin cambio  "
          f"{_c(str(new_strategies), DIM)} nuevas")
    print()
    print("Regla: aplicar odds_min solo donde veredicto VERDE y N_drop < 20%")
    print()

    # Show which strategies improved with odds_min > 0
    improved_with_filter = [
        key for key in all_keys
        if key in baseline and key in new_res
        and new_res[key].get("params", {}).get("odds_min", 0) > 0
        and new_res[key]["roi"] > baseline[key]["roi"] + ROI_THRESHOLD
    ]
    if improved_with_filter:
        print(f"{BOLD}Estrategias que mejoran CON odds_min activo:{RESET}")
        for key in improved_with_filter:
            b, a = baseline[key], new_res[key]
            om = a.get("params", {}).get("odds_min", 0)
            print(f"  {key}: ROI {b['roi']:.1f}% -> {a['roi']:.1f}%  (odds_min={om:.2f})")


if __name__ == "__main__":
    main()
