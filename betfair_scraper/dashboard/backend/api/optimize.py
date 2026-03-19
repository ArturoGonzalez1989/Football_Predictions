"""
Preset optimizer — Python backend.

Dynamic portfolio optimizer: uses steepest descent over ALL strategies
from the registry (no hardcoded strategy lists).

Phase 1: steepest descent on/off over all strategies + best risk_filter
          (bankroll_mode only tested for min_dd criterion).
Phase 2 (~7,776 combos): finds best RealisticAdjustments.
Phase 3 (5 combos): momentum minute range.
Phase 4: cashout percentage optimization.
"""
import asyncio
import json
import logging
import math
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Make sure backend utils are importable from worker processes
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

router = APIRouter()

# Pre-computed preset CSVs live here (written by optimizer_cli.py after each run).
_PRESETS_DIR = _backend_dir.parent.parent / "data" / "presets"

# ── Options ──────────────────────────────────────────────────────────────────
BR_OPTS  = ["fixed", "half_kelly", "dd_protection", "anti_racha"]
RISK_OPTS = ["all", "no_risk", "with_risk", "medium"]

_PHASE2_TOTAL = 2 * 3 * 3 * 3 * 2 * 2 * 3 * 3 * 3  # = 7776

# Module-level state — updated from the worker thread, read by GET endpoints.
# CPython's GIL makes dict mutation thread-safe for simple key reads/writes.
_opt_result: Optional[Dict] = None   # last completed result (None if not ready yet)
_opt_progress: Dict[str, Any] = {
    "running": False,
    "phase": "",
    "pct": 0,
    "message": "",
}

# ── Wilson CI helper ─────────────────────────────────────────────────────────

def _wilson_ci(wins: int, n: int, z: float = 1.96) -> tuple:
    """Returns (ci_low, ci_high) Wilson 95% CI for a proportion wins/n."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    center = (p + z * z / (2 * n)) / (1 + z * z / n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(max(0.0, center - margin) * 100, 1), round(min(1.0, center + margin) * 100, 1))


# ── Helper: get odds from a bet dict (mirrors getBetOdds in cartera.ts) ──────

_ODDS_KEYS = [
    "back_sot_odds", "back_over15_odds", "lay_false_fav_odds", "lay_draw_odds",
    "lay_over25_odds", "lay_over15_odds", "back_draw", "back_over_odds",
    "over_odds", "back_odds",
    # Additional strategy odds keys
    "lay_over45_odds", "back_leader_odds", "back_over25_odds", "back_draw_eq_odds",
    "back_under25_odds", "back_under35_odds", "back_draw_stl_odds",
    "back_draw_conv_odds", "back_over35_odds", "back_over05_odds",
    "back_longshot_odds", "back_cs_00_odds",
]

def _get_bet_odds(b: Dict) -> float:
    for k in _ODDS_KEYS:
        v = b.get(k)
        if v is not None:
            try:
                fv = float(v)
                if fv > 0:
                    return fv
            except (ValueError, TypeError):
                pass
    return 2.0


def _fv(b: Dict, key: str) -> Optional[float]:
    """Safe float extraction from a bet field (None if missing/invalid)."""
    v = b.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


# ── Dynamic bet collection ────────────────────────────────────────────────────

def _collect_bets_dynamic(bets: List[Dict], disabled: set) -> List[Dict]:
    """Return bets excluding disabled strategies, sorted chronologically."""
    cb = [b for b in bets if b.get("strategy") not in disabled]
    cb.sort(key=lambda b: b.get("timestamp_utc") or "")
    return cb


# Minimum bets for a portfolio to be considered viable in the optimizer.
# Aligned with MIN_PRESET_N in bt_optimizer.py — portfolios below this
# threshold will be rejected by Phase 4 anyway, so no point optimizing them.
MIN_PORTFOLIO_BETS = 200


def _eval_dynamic(bets: List[Dict], disabled: set, adj: Optional[Dict],
                  risk: str, bankroll_init: float, br: str, criterion: str) -> float:
    """Score a portfolio with a given set of disabled strategies."""
    cb = _collect_bets_dynamic(bets, disabled)
    if adj:
        cb = _apply_realistic_adj(cb, adj)
    cb = _filter_by_risk(cb, risk)
    if len(cb) < MIN_PORTFOLIO_BETS:
        return -math.inf
    sim = _simulate_cartera_py(cb, bankroll_init, br)
    return _score_of(sim, criterion)


def _steepest_descent(bets: List[Dict], strategy_keys: List[str],
                      adj: Optional[Dict], risk: str, bankroll_init: float,
                      br: str, criterion: str, max_passes: int = 10) -> set:
    """Forward+backward steepest descent over strategy on/off.

    Backward pass: start with all on, iteratively disable the strategy
    whose removal improves the portfolio score the most.
    Forward pass: try re-enabling each disabled strategy — if it improves,
    re-enable it. Breaks local optima where removing A was good but
    removing A+B together was excessive.

    Returns the set of disabled strategy keys."""
    disabled = set()
    current_score = _eval_dynamic(bets, disabled, adj, risk, bankroll_init, br, criterion)

    # Backward pass: disable strategies that hurt the portfolio
    for _pass in range(max_passes):
        best_key = None
        best_score = current_score
        for key in strategy_keys:
            if key in disabled:
                continue
            trial = disabled | {key}
            score = _eval_dynamic(bets, trial, adj, risk, bankroll_init, br, criterion)
            if score > best_score:
                best_score = score
                best_key = key
        if best_key is None:
            break
        disabled.add(best_key)
        current_score = best_score

    # Forward pass: try re-enabling each disabled strategy
    for _pass in range(max_passes):
        best_key = None
        best_score = current_score
        for key in list(disabled):
            trial = disabled - {key}
            score = _eval_dynamic(bets, trial, adj, risk, bankroll_init, br, criterion)
            if score > best_score:
                best_score = score
                best_key = key
        if best_key is None:
            break
        disabled.remove(best_key)
        current_score = best_score

    return disabled




def _filter_by_risk(bets: List[Dict], risk: str) -> List[Dict]:
    if risk == "all":
        return bets
    result = []
    for b in bets:
        r = b.get("risk_level") or "none"
        if risk == "no_risk" and r == "none":
            result.append(b)
        elif risk == "with_risk" and r in ("medium", "high"):
            result.append(b)
        elif risk == "medium" and r == "medium":
            result.append(b)
        elif risk == "high" and r == "high":
            result.append(b)
    return result


# ── Realistic adjustment helpers (mirrors applyRealisticAdjustments in cartera.ts) ──

def _bet_market_key(b: Dict) -> str:
    strategy = b.get("strategy", "")
    match_id = b.get("match_id", "")
    if strategy == "back_draw_00":
        return f"{match_id}:draw"
    if strategy in ("odds_drift", "momentum_xg"):
        return f"{match_id}:back:{b.get('team') or 'unknown'}"
    # Goal Clustering: deduplicate at strategy level — only the first trigger per match fires.
    # Each goal changes over_line but we only want the first clustering signal per match.
    if strategy == "goal_clustering":
        return f"{match_id}:goal_clustering"
    return f"{match_id}:over:{b.get('over_line') or 'unknown'}"


def _apply_realistic_adj(bets: List[Dict], adj: Dict) -> List[Dict]:
    """Mirrors applyRealisticAdjustments from cartera.ts exactly."""
    result = list(bets)

    # 0. Global minute range filter
    g_min = adj.get("globalMinuteMin")
    g_max = adj.get("globalMinuteMax")
    if g_min is not None or g_max is not None:
        new: List[Dict] = []
        for b in result:
            mn = _fv(b, "minuto")
            if mn is None:
                new.append(b)
                continue
            if g_min is not None and mn < g_min:
                continue
            if g_max is not None and mn >= g_max:
                continue
            new.append(b)
        result = new

    # 1. Drift min minute
    drift_min = adj.get("driftMinMinute")
    if drift_min is not None:
        result = [
            b for b in result
            if b.get("strategy") != "odds_drift" or (_fv(b, "minuto") or 0) >= drift_min
        ]

    # 2. Max odds filter
    max_odds = adj.get("maxOdds")
    if max_odds is not None:
        result = [b for b in result if _get_bet_odds(b) <= max_odds]

    # 3. Min odds filter
    min_odds = adj.get("minOdds")
    if min_odds is not None:
        result = [b for b in result if _get_bet_odds(b) >= min_odds]

    # 4. Dedup (keep first chronologically per market key; bets already sorted)
    if adj.get("dedup"):
        seen_keys: set = set()
        deduped: List[Dict] = []
        for b in result:
            key = _bet_market_key(b)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped.append(b)
        result = deduped

    # 5. Conflict filter: remove MomXG bets from matches that also have xG Underperf
    if adj.get("conflictFilter"):
        xg_matches = {b.get("match_id") for b in result if b.get("strategy") == "xg_underperformance"}
        result = [
            b for b in result
            if b.get("strategy") != "momentum_xg"
            or b.get("match_id") not in xg_matches
        ]

    # 5b. Anti-contrarias: remove later contradictory match-odds bets on same match
    if not adj.get("allowContrarias", True):
        seen_match: Dict[str, str] = {}
        new2: List[Dict] = []
        for b in result:
            strategy = b.get("strategy", "")
            is_match_odds = strategy in ("back_draw_00", "odds_drift", "momentum_xg")
            if not is_match_odds:
                new2.append(b)
                continue
            bet_type = "draw" if strategy == "back_draw_00" else (b.get("team") or "home")
            match_id = b.get("match_id")
            first = seen_match.get(match_id)
            if first is None:
                seen_match[match_id] = bet_type
                new2.append(b)
            elif first == bet_type:
                new2.append(b)
            # else: contraria → skip
        result = new2

    # 6. Stability filter
    min_stability = adj.get("minStability", 1)
    if min_stability and min_stability > 1:
        result = [b for b in result if (b.get("stability_count") or 1) >= min_stability]

    # 7. Slippage (BACK bets only, affects wins only — mirrors cartera.ts)
    slippage_pct = adj.get("slippagePct", 0)
    if slippage_pct and slippage_pct > 0:
        factor = 1.0 - slippage_pct / 100.0
        new3: List[Dict] = []
        for b in result:
            if b.get("bet_type_dir") == "lay" or not b.get("won"):
                new3.append(b)
                continue
            adjusted_odds = _round2(_get_bet_odds(b) * factor)
            new_pl = _round2((adjusted_odds - 1.0) * 10.0 * 0.95)
            nb = dict(b)
            nb["pl"] = new_pl
            new3.append(nb)
        result = new3

    return result


# ── Bankroll simulation (mirrors simulateCartera in cartera.ts) ──────────────

def _calc_max_drawdown(cum: List[float]) -> float:
    """Return max peak-to-trough drawdown from cumulative P/L array."""
    if not cum:
        return 0.0
    max_dd = 0.0
    peak = cum[0]
    for v in cum:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _round2(x: float) -> float:
    return round(x * 100) / 100


def _simulate_cartera_py(bets: List[Dict], bankroll_init: float, mode: str, flat_stake: float = 10.0) -> Dict:
    FLAT_STAKE = flat_stake
    pl_scale = flat_stake / 10.0
    KELLY_MIN_BETS = 5

    flat_cum = 0.0
    bankroll = bankroll_init
    peak_bankroll = bankroll_init
    flat_cum_arr: List[float] = []
    managed_cum_arr: List[float] = []
    flat_wins = 0
    managed_pl = 0.0
    rolling_wins = 0
    consecutive_losses = 0

    for i, b in enumerate(bets):
        pl_raw = b.get("pl")
        try:
            pl_raw = float(pl_raw) if pl_raw is not None else 0.0
        except (ValueError, TypeError):
            pl_raw = 0.0

        won = bool(b.get("won"))
        flat_cum = _round2(flat_cum + pl_raw * pl_scale)
        flat_cum_arr.append(flat_cum)
        if won:
            flat_wins += 1

        rolling_wr = rolling_wins / i if i > 0 else 0.5
        odds = _get_bet_odds(b)
        b_net = max(odds - 1.0, 0.01)

        if mode == "fixed":
            stake_pct = 0.02
        elif mode == "kelly":
            if i < KELLY_MIN_BETS:
                stake_pct = 0.02
            else:
                f = (rolling_wr * b_net - (1.0 - rolling_wr)) / b_net
                stake_pct = max(0.0, min(f, 0.08))
        elif mode == "half_kelly":
            if i < KELLY_MIN_BETS:
                stake_pct = 0.01
            else:
                f = (rolling_wr * b_net - (1.0 - rolling_wr)) / b_net
                stake_pct = max(0.0, min(f / 2.0, 0.04))
        elif mode == "dd_protection":
            dd_from_peak = (peak_bankroll - bankroll) / peak_bankroll if peak_bankroll > 0 else 0.0
            if dd_from_peak > 0.10:
                stake_pct = 0.005
            elif dd_from_peak > 0.05:
                stake_pct = 0.01
            else:
                stake_pct = 0.02
        elif mode == "variable":
            strategy = b.get("strategy", "")
            if strategy == "odds_drift":
                stake_pct = 0.025
            elif strategy == "xg_underperformance":
                stake_pct = 0.03
            elif strategy == "pressure_cooker":
                stake_pct = 0.02
            else:
                stake_pct = 0.015
        elif mode == "anti_racha":
            if consecutive_losses >= 2:
                stake_pct = 0.005
            elif consecutive_losses >= 1:
                stake_pct = 0.01
            else:
                stake_pct = 0.02
        else:
            stake_pct = 0.02

        stake = _round2(bankroll * stake_pct)
        ratio = stake / FLAT_STAKE
        managed_bet_pl = _round2(pl_raw * pl_scale * ratio)
        bankroll = _round2(bankroll + managed_bet_pl)
        if bankroll > peak_bankroll:
            peak_bankroll = bankroll
        managed_pl = _round2(managed_pl + managed_bet_pl)
        managed_cum_arr.append(_round2(bankroll - bankroll_init))

        if won:
            rolling_wins += 1
            consecutive_losses = 0
        else:
            consecutive_losses += 1

    total = len(bets)
    total_staked = total * FLAT_STAKE
    managed_max_dd = _calc_max_drawdown(managed_cum_arr)

    # Normalized metrics: percentages of initial bankroll (bounded, comparable)
    managed_roi = _round2(managed_pl / bankroll_init * 100) if bankroll_init > 0 else 0.0
    managed_dd_pct = _round2(managed_max_dd / max(peak_bankroll, bankroll_init) * 100) if peak_bankroll > 0 else 0.0

    return {
        "total": total,
        "wins": flat_wins,
        "win_pct": _round2(flat_wins / total * 100) if total > 0 else 0.0,
        "flat_pl": flat_cum,
        "flat_roi": _round2(flat_cum / total_staked * 100) if total_staked > 0 else 0.0,
        "managed_pl": managed_pl,
        "managed_max_dd": managed_max_dd,
        "managed_roi": managed_roi,
        "managed_dd_pct": managed_dd_pct,
    }


def _score_of(sim: Dict, criterion: str) -> float:
    # Bayesian confidence weight: penalizes combos with few bets.
    # N=15 → 0.25×, N=30 → 0.50×, N=60 → 1.00×, N>60 → 1.00×
    # Raised from 30 to 60: con dataset de ~743 partidos, N=32 obtenía conf=1.0
    # (mismo que N=300), lo que permitía combos hiper-selectivos de 1 sola
    # estrategia ganar por ROI nominal sin penalización estadística suficiente.
    n = sim["total"]
    conf = min(1.0, n / 60.0)
    if criterion == "max_roi":
        return sim["flat_roi"] * conf
    if criterion == "max_pl":
        return sim["flat_pl"] * conf
    if criterion == "max_wr":
        ci_low, _ = _wilson_ci(sim["wins"], n)
        return ci_low  # Wilson CI lower bound: statistically principled, no magic numbers
    if criterion == "min_dd":
        # Uses flat_roi (bounded, doesn't compound) for return, and
        # managed_dd_pct (varies by bankroll mode) for risk.
        # This way dd_protection/anti_racha can win by reducing drawdown,
        # without half_kelly's exponential growth dominating the score.
        flat_roi = sim["flat_roi"]
        dd_pct = max(sim.get("managed_dd_pct", 0.0), 1.0)  # floor at 1%
        wr = sim["win_pct"]
        calmar = flat_roi / dd_pct
        # Penalty: drawdown > 30% → score multiplied by 0.5^((dd-30)/20)
        dd_penalty = 1.0
        if dd_pct > 30.0:
            dd_penalty = 0.5 ** ((dd_pct - 30.0) / 20.0)
        return calmar * (wr / 100.0) * dd_penalty * conf
    return sim["flat_pl"] * conf


def _phase2_worker(args: tuple) -> tuple:
    """
    Runs Phase 2 search: 7776 realistic adjustment candidates given the fixed Phase 1 combo.
    bets_for_combo must already be: combo-filtered + min_odds + sorted chronologically (no risk filter).
    Risk filter is applied AFTER realistic adjustments — mirrors evaluateCombo order in cartera.ts.
    Returns (best_adj_dict | None, best_score).
    """
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(
            ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)  # BELOW_NORMAL

    bets_for_combo, bankroll_init, br_mode, risk_filter, criterion = args
    best_adj: Optional[Dict] = None
    best_score = -math.inf
    _itr_p2 = 0

    for dedup in (False, True):
      for min_odds_val in (None, 1.15, 1.21):
        for max_odds_val in (6.0, 7.0, 10.0):
          for slippage_pct in (0, 2, 3.5):
            for conflict_filter in (False, True):
              for allow_contrarias in (True, False):
                for min_stability in (1, 2, 3):
                  for drift_min in (None, 15, 30):
                    for g_min, g_max in ((None, None), (15, 85), (20, 80)):
                        adj: Dict = {
                            "dedup": dedup,
                            "minOdds": min_odds_val,
                            "maxOdds": max_odds_val,
                            "slippagePct": slippage_pct,
                            "conflictFilter": conflict_filter,
                            "allowContrarias": allow_contrarias,
                            "minStability": min_stability,
                            "driftMinMinute": drift_min,
                            "globalMinuteMin": g_min,
                            "globalMinuteMax": g_max,
                        }
                        after_adj = _apply_realistic_adj(bets_for_combo, adj)
                        after_risk = _filter_by_risk(after_adj, risk_filter)
                        if len(after_risk) < 15:
                            continue
                        sim = _simulate_cartera_py(after_risk, bankroll_init, br_mode)
                        score = _score_of(sim, criterion)
                        if score > best_score:
                            best_score = score
                            best_adj = adj
                        _itr_p2 += 1
                        if _itr_p2 % 500 == 0:
                            _pct2 = min(99, round(_itr_p2 / _PHASE2_TOTAL * 100))
                            _opt_progress["pct"] = _pct2
                            _opt_progress["message"] = f"Phase 2 — {_pct2}% ({_itr_p2} / {_PHASE2_TOTAL} adj combos)"
                            logger.info("Optimizer Phase 2: %d%%", _pct2)

    return best_adj, best_score


# ── Subprocess runner ────────────────────────────────────────────────────────

_CLI_SCRIPT = Path(__file__).parent / "optimizer_cli.py"
_N_WORKERS   = int(os.environ.get("PRESET_WORKERS", "3"))   # default 3 (~12 min Phase 1). Safe for Chrome. Set PRESET_WORKERS=10 for faster runs without browser open.


def _parse_progress_line(line: str) -> None:
    """Update _opt_progress by parsing a stdout line from optimizer_cli.py."""
    if "Phase 1 —" in line:
        _opt_progress.update({"phase": "Phase 1", "pct": 0, "message": line})
    elif "Steepest descent" in line and "desactiv" in line:
        _opt_progress.update({"message": line})
    elif "Phase 1 completada" in line:
        _opt_progress.update({"phase": "Phase 1", "pct": 99, "message": line})
    elif "Phase 2 —" in line or "Phase 2b —" in line:
        _opt_progress.update({"phase": "Phase 2", "pct": 0, "message": line})
    elif "Phase 2 completada" in line or "Phase 2b completada" in line:
        _opt_progress.update({"phase": "Phase 2", "pct": 99, "message": line})
    elif "Phase 2.5 —" in line:
        _opt_progress.update({"phase": "Phase 2.5", "pct": 0, "message": line})
    elif "Phase 2.5 (pase" in line and "desactivar" in line:
        _opt_progress.update({"message": line})
    elif "Phase 2.5 completada" in line:
        _opt_progress.update({"phase": "Phase 2.5", "pct": 99, "message": line})


def _run_subprocess_sync(cmd: list, out_file: Path) -> int:
    """
    Run optimizer_cli.py synchronously, reading stdout line-by-line to update _opt_progress.
    Called via asyncio.to_thread — avoids asyncio.create_subprocess_exec issues on Windows
    where uvicorn may use SelectorEventLoop (which doesn't support async subprocesses).
    Returns the process returncode.
    """
    import subprocess as _sp
    import os as _os
    # Windows: BELOW_NORMAL_PRIORITY_CLASS (0x4000) so Chrome's renderer doesn't starve.
    # Worker processes spawned by ProcessPoolExecutor inherit this priority from the parent.
    _creation_flags = 0x00004000 if sys.platform == "win32" else 0
    # PYTHONUTF8=1 ensures the subprocess uses UTF-8 for stdout/stderr (avoids cp1252 UnicodeEncodeError).
    _env = {**_os.environ, "PYTHONUTF8": "1"}
    proc = _sp.Popen(
        cmd,
        stdout=_sp.PIPE,
        stderr=_sp.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=_creation_flags,
        env=_env,
    )
    for line in iter(proc.stdout.readline, ""):
        line = line.strip()
        if line:
            logger.info("Optimizer: %s", line)
            _parse_progress_line(line)
    proc.stdout.close()
    proc.wait()
    return proc.returncode


async def _run_optimizer_subprocess(criterion: str, bankroll_init: float) -> Dict:
    """
    Launch optimizer_cli.py as an independent subprocess with _N_WORKERS parallel workers.
    Uses asyncio.to_thread + subprocess.Popen — compatible with all Windows event loop types.
    Reads stdout in real-time to update _opt_progress.
    Returns the result dict read from the output JSON file.
    """
    out_file = Path(tempfile.mktemp(suffix=".json"))
    cmd = [
        sys.executable, str(_CLI_SCRIPT),
        criterion,
        "--bankroll", str(bankroll_init),
        "--workers", str(_N_WORKERS),
        "--out", str(out_file),
    ]

    _opt_progress.update({
        "running": True, "phase": "Phase 1", "pct": 0,
        "message": f"Iniciando optimizador ({_N_WORKERS} workers)…",
    })
    logger.info("Optimizer subprocess: %s", " ".join(str(c) for c in cmd))

    try:
        returncode = await asyncio.to_thread(_run_subprocess_sync, cmd, out_file)

        if returncode != 0:
            _opt_progress.update({"running": False, "phase": "error", "pct": 0,
                                   "message": f"Error en el optimizador (código {returncode})"})
            return

        if not out_file.exists():
            _opt_progress.update({"running": False, "phase": "error", "pct": 0,
                                   "message": "Error: fichero de resultado no encontrado"})
            return

        global _opt_result
        _opt_result = json.loads(out_file.read_text(encoding="utf-8"))
        _opt_progress.update({"running": False, "phase": "done", "pct": 100, "message": "Completado"})
        logger.info("Optimizer done — best_score=%.2f", _opt_result.get("best_score", 0))

    except Exception as exc:
        logger.exception("Optimizer subprocess crashed: %s", exc)
        _opt_progress.update({"running": False, "phase": "error", "pct": 0,
                               "message": f"Error inesperado: {exc}"})
    finally:
        out_file.unlink(missing_ok=True)


# ── FastAPI endpoints ─────────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    criterion: str
    bankroll_init: float = 1000.0


@router.get("/strategies/cartera/optimize/progress")
async def get_optimize_progress() -> Dict[str, Any]:
    """Returns current optimizer progress (running/pct/message)."""
    return dict(_opt_progress)


@router.get("/strategies/cartera/optimize/result")
async def get_optimize_result() -> Dict[str, Any]:
    """Returns the last completed optimizer result, or status=running/idle."""
    if _opt_progress.get("running"):
        return {"status": "running"}
    if _opt_result is not None:
        return {"status": "done", **_opt_result}
    return {"status": "idle"}


@router.post("/strategies/cartera/optimize")
async def optimize_preset(body: OptimizeRequest) -> Dict[str, Any]:
    """
    Starts optimization in background and returns IMMEDIATELY (status=started).
    Chrome never waits 4 minutes — no open HTTP connection, no memory accumulation.
    Poll GET /optimize/progress for live updates, GET /optimize/result for the final result.
    """
    global _opt_result

    if body.criterion == "max_bets":
        _opt_result = {"disabled": set(), "risk_filter": "all", "best_score": 0.0, "br": "fixed"}
        return {"status": "done", **_opt_result}

    if _opt_progress.get("running"):
        return {"status": "already_running"}

    _opt_result = None  # clear previous result
    # Reset progress to "running" synchronously BEFORE spawning the task.
    # This prevents the progress poller from reading a stale phase:"done" from the
    # previous optimization and signalling the while-loop to exit prematurely.
    _opt_progress.update({
        "running": True, "phase": "starting", "pct": 0,
        "message": f"Iniciando optimizador {body.criterion}…",
    })
    asyncio.create_task(_run_optimizer_subprocess(body.criterion, body.bankroll_init))
    return {"status": "started"}


@router.get("/strategies/cartera/optimize/config/{criterion}")
async def get_preset_config(criterion: str) -> Dict[str, Any]:
    """
    Returns the pre-computed cartera_config.json-compatible config for the given preset.
    Generated automatically after each optimizer run.
    404 if the optimizer hasn't run yet for this criterion.
    """
    allowed = {"max_roi", "max_pl", "max_wr", "min_dd"}
    if criterion not in allowed:
        raise HTTPException(status_code=400, detail=f"criterion must be one of {sorted(allowed)}")
    cfg_path = _PRESETS_DIR / f"preset_{criterion}_config.json"
    if not cfg_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No hay config para '{criterion}'. Lanza el optimizador primero."
        )
    return json.loads(cfg_path.read_text(encoding="utf-8"))


@router.get("/strategies/cartera/optimize/presets")
async def list_preset_csvs() -> Dict[str, Any]:
    """Lists all pre-computed preset CSVs available for download."""
    files = []
    if _PRESETS_DIR.exists():
        for p in sorted(_PRESETS_DIR.glob("preset_*.csv")):
            criterion = p.stem.replace("preset_", "")
            cfg_path = _PRESETS_DIR / f"preset_{criterion}_config.json"
            files.append({
                "criterion": criterion,
                "filename": p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "modified": p.stat().st_mtime,
                "has_config": cfg_path.exists(),
            })
    return {"presets": files}


@router.get("/strategies/cartera/optimize/download/{criterion}")
async def download_preset_csv(criterion: str) -> FileResponse:
    """Download pre-computed preset CSV for the given criterion (max_roi | max_pl | max_wr | min_dd)."""
    allowed = {"max_roi", "max_pl", "max_wr", "min_dd"}
    if criterion not in allowed:
        raise HTTPException(status_code=400, detail=f"criterion must be one of {sorted(allowed)}")
    csv_path = _PRESETS_DIR / f"preset_{criterion}.csv"
    if not csv_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No hay CSV para '{criterion}'. Lanza el optimizador primero."
        )
    return FileResponse(
        path=str(csv_path),
        filename=f"preset_{criterion}.csv",
        media_type="text/csv",
    )
