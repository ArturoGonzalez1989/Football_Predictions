import csv
import re
import logging
import traceback
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)

from fastapi import APIRouter, Query
from typing import Dict, List, Any, Optional
from utils import csv_reader
from utils import signals_audit_logger as _audit
from utils import telegram_notifier as _tg
from api.config import load_config

# Path compartido con bets.py
_PLACED_BETS_CSV = Path(__file__).resolve().parent.parent.parent.parent / "placed_bets.csv"
_AUTO_PLACE_LOG = Path(__file__).resolve().parent.parent.parent.parent / "auto_place_errors.log"
_PLACED_BETS_HEADERS = [
    'id', 'timestamp_utc', 'match_id', 'match_name', 'match_url',
    'strategy', 'strategy_name', 'minute', 'score', 'recommendation',
    'back_odds', 'min_odds', 'expected_value', 'confidence',
    'win_rate_historical', 'roi_historical', 'sample_size',
    'bet_type', 'stake', 'notes', 'status', 'result', 'pl'
]

# Dedup en memoria: evita escribir el mismo signal dos veces en la misma sesión de backend
_auto_placed_keys: set = set()

# Minutos de retraso de reacción simulado: la bet se coloca 1 minuto después de madurar
# (simula el tiempo que tarda un operador humano en confirmar y colocar la apuesta real)
PAPER_REACTION_DELAY_MINS = 1


def _auto_place_signal(sig: dict, stake: float) -> None:
    """Registra automáticamente una señal madura como apuesta paper en placed_bets.csv."""
    match_id = sig.get("match_id", "")
    strategy = sig.get("strategy", "")
    market_key = _live_market_key(sig)  # dedup by market, not strategy

    # Dedup en sesión: ya fue colocado en este ciclo de vida del backend
    if market_key in _auto_placed_keys:
        return

    try:
        # Atomic read-check-write: read all rows, check dedup, write full file
        rows = []
        if _PLACED_BETS_CSV.exists():
            with open(_PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))

        # Dedup check (by market key)
        for row in rows:
            if _live_market_key(row) == market_key:
                _auto_placed_keys.add(market_key)
                return

        # Compute next ID
        ids = [int(r['id']) for r in rows if r.get('id', '').isdigit()]
        next_id = (max(ids) + 1) if ids else 1

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [
            next_id, timestamp,
            match_id,
            sig.get("match_name", ""),
            sig.get("match_url", ""),
            strategy,
            sig.get("strategy_name", ""),
            sig.get("minute", ""),
            sig.get("score", ""),
            sig.get("recommendation", ""),
            sig.get("back_odds", ""),
            sig.get("min_odds", ""),
            sig.get("expected_value", ""),
            sig.get("confidence", ""),
            sig.get("win_rate_historical", ""),
            sig.get("roi_historical", ""),
            sig.get("sample_size", ""),
            "paper",
            stake,
            "auto",   # notas: marca automático
            "pending", "", "",
        ]

        # Atomic write: write to temp file, then rename
        tmp_path = _PLACED_BETS_CSV.with_suffix('.csv.tmp')
        with open(tmp_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(_PLACED_BETS_HEADERS)
            for row in rows:
                w.writerow([row.get(h, '') for h in _PLACED_BETS_HEADERS])
            w.writerow(new_row)
        # Atomic rename (on Windows this replaces the target)
        import shutil
        shutil.move(str(tmp_path), str(_PLACED_BETS_CSV))

        # ── Audit log: apuesta colocada ──
        try:
            _audit.log_bet_placed(next_id, sig, stake)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Audit log failed for bet {next_id}: {e}")

        # ── Telegram notification ──
        _tg.send_signal(sig, stake, bet_id=next_id)

        _auto_placed_keys.add(market_key)
    except Exception as e:
        # Loguear error en fichero para depuración (no interrumpir el endpoint)
        logging.getLogger(__name__).error(f"Error placing bet {match_id}/{strategy}: {e}")
        try:
            with open(_AUTO_PLACE_LOG, 'a', encoding='utf-8') as _f:
                _f.write(
                    f"{datetime.utcnow()} | {match_id} | {strategy} | "
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}\n"
                )
        except Exception:
            pass

def _live_market_key(sig: dict) -> str:
    """Derive a dedup key from a live signal: match_id + market type (strips odds).
    Mirrors cartera.ts betMarketKey / getBetType logic.
    """
    match_id = sig.get("match_id", "")
    rec = sig.get("recommendation", "").upper()
    # Correct Score markets: "BACK CS 2-1 @ ..." → cs_2_1
    if " CS " in rec:
        cs_match = re.search(r"CS\s+(\d+)[_-](\d+)", rec)
        if cs_match:
            return f"{match_id}::cs_{cs_match.group(1)}_{cs_match.group(2)}"
    if "OVER" in rec:
        parts = rec.split()
        over_idx = next((i for i, p in enumerate(parts) if p == "OVER"), -1)
        if over_idx >= 0 and over_idx + 1 < len(parts):
            return f"{match_id}::over_{parts[over_idx + 1]}"
    if "UNDER" in rec:
        parts = rec.split()
        under_idx = next((i for i, p in enumerate(parts) if p == "UNDER"), -1)
        if under_idx >= 0 and under_idx + 1 < len(parts):
            return f"{match_id}::under_{parts[under_idx + 1]}"
    if "HOME" in rec:
        return f"{match_id}::home"
    if "AWAY" in rec:
        return f"{match_id}::away"
    if "DRAW" in rec:
        return f"{match_id}::draw"
    return f"{match_id}::{rec}"


def _apply_realistic_adjustments(signals: list, adj: dict, risk_filter: str) -> tuple:
    """Apply ALL realistic adjustments to live signals, mirroring applyRealisticAdjustments in cartera.ts.

    Returns (filtered_signals, skip_reasons) where skip_reasons is a dict mapping
    id(sig) → skip_reason string for audit logging.

    Filters applied (same order as frontend):
      0. Global minute range (global_minute_min/max)
      1. Drift min minute (adjDriftMinMinute)
      2. Odds filters with slippage (min_odds, max_odds, slippage_pct)
      3. Risk filter
      4. Stability global floor (stability)
      5. Conflict filter (MomXG blocked when xGUnderperf on same match)
      6. Anti-contrarias (first match-odds bet type per match wins)
      7. Dedup (same match + same market, keep first)
    """
    adj_enabled = adj.get("enabled", True)

    def _num(val, default, cast):
        if val is None:
            return default
        try:
            return cast(val)
        except Exception:
            return default

    min_odds_cfg     = _num(adj.get("min_odds", 0),   0.0, float)   if adj_enabled else 0.0
    max_odds_cfg     = _num(adj.get("max_odds", 999), 999.0, float) if adj_enabled else 999.0
    slippage_pct     = _num(adj.get("slippage_pct", 0), 0.0, float) if adj_enabled else 0.0
    drift_min_min    = _num(adj.get("drift_min_minute", 0), 0, int) if adj_enabled else 0
    dedup_enabled    = bool(adj.get("dedup", False))                if adj_enabled else False
    conflict_filter  = bool(adj.get("conflict_filter", False))      if adj_enabled else False
    allow_contrarias = bool(adj.get("allow_contrarias", True))      if adj_enabled else True
    stability_cfg    = _num(adj.get("stability", 1), 1, int)        if adj_enabled else 1
    global_min       = adj.get("global_minute_min")                 if adj_enabled else None
    global_max       = adj.get("global_minute_max")                 if adj_enabled else None

    skip_reasons: dict = {}  # id(sig) → reason string

    # Pass 1: per-signal filters (minute, odds, risk)
    pass1: list = []
    for sig in signals:
        back_odds  = sig.get("back_odds")
        minute     = sig.get("minute") or 0
        strategy   = sig.get("strategy", "")
        risk_level = (sig.get("risk_info") or {}).get("risk_level", "none")
        sid        = id(sig)

        if global_min is not None and minute < global_min:
            skip_reasons[sid] = f"global_min_minute({minute}<{global_min})"
            continue
        if global_max is not None and minute >= global_max:
            skip_reasons[sid] = f"global_max_minute({minute}>={global_max})"
            continue

        if drift_min_min > 0 and strategy.startswith("odds_drift"):
            if minute < drift_min_min:
                skip_reasons[sid] = f"drift_too_early(min{minute}<{drift_min_min})"
                continue

        if back_odds is not None:
            effective_odds = back_odds * (1 - slippage_pct / 100) if slippage_pct > 0 else back_odds
            if min_odds_cfg > 0 and effective_odds < min_odds_cfg:
                skip_reasons[sid] = f"odds_low({effective_odds:.2f}<{min_odds_cfg})"
                continue
            # Per-signal min_odds: each strategy has a calculated break-even floor
            per_signal_min = sig.get("min_odds")
            if per_signal_min is not None and effective_odds < per_signal_min:
                skip_reasons[sid] = f"odds_below_signal_min({effective_odds:.2f}<{per_signal_min:.2f})"
                continue
            if max_odds_cfg < 999 and back_odds > max_odds_cfg:
                skip_reasons[sid] = f"odds_high({back_odds:.2f}>{max_odds_cfg})"
                continue

        if risk_filter == "no_risk" and risk_level not in ("none", ""):
            skip_reasons[sid] = f"risk_filter_no_risk(level={risk_level})"
            continue
        if risk_filter == "medium" and risk_level != "medium":
            skip_reasons[sid] = f"risk_filter_medium(level={risk_level})"
            continue
        if risk_filter == "high" and risk_level != "high":
            skip_reasons[sid] = f"risk_filter_high(level={risk_level})"
            continue
        if risk_filter == "with_risk" and risk_level not in ("medium", "high"):
            skip_reasons[sid] = f"risk_filter_with_risk(level={risk_level})"
            continue

        pass1.append(sig)

    # Pass 2: stability global floor (1 capture ≈ 0.5 min)
    if stability_cfg > 1:
        stable = []
        for sig in pass1:
            if sig.get("signal_age_minutes", 0) < stability_cfg * 0.5:
                skip_reasons[id(sig)] = f"stability({sig.get('signal_age_minutes', 0):.1f}min<{stability_cfg * 0.5:.1f}min)"
            else:
                stable.append(sig)
        pass1 = stable

    # Pass 3: conflict filter (MomXG blocked when xGUnderperf present on same match)
    if conflict_filter:
        xg_match_ids = {s["match_id"] for s in pass1 if s.get("strategy", "").startswith("xg_underperformance")}
        filtered3 = []
        for sig in pass1:
            if sig.get("strategy", "").startswith("momentum_xg") and sig.get("match_id") in xg_match_ids:
                skip_reasons[id(sig)] = "conflict_filter(mom_xg+xg_underperf)"
            else:
                filtered3.append(sig)
        pass1 = filtered3

    # Pass 4: anti-contrarias (first match-odds bet type per match wins)
    if not allow_contrarias:
        seen_match_odds: dict = {}  # match_id → first bet type seen
        filtered4 = []
        for sig in pass1:
            strat = sig.get("strategy", "")
            is_match_odds = (strat.startswith("back_draw_00") or strat.startswith("odds_drift")
                             or strat.startswith("momentum_xg"))
            if not is_match_odds:
                filtered4.append(sig)
                continue
            rec = sig.get("recommendation", "").upper()
            bet_type = "home" if "HOME" in rec else ("away" if "AWAY" in rec else "draw")
            mid = sig.get("match_id", "")
            if mid not in seen_match_odds:
                seen_match_odds[mid] = bet_type
                filtered4.append(sig)
            elif seen_match_odds[mid] == bet_type:
                filtered4.append(sig)
            else:
                skip_reasons[id(sig)] = f"contraria({bet_type}!={seen_match_odds[mid]})"
        pass1 = filtered4

    # Pass 5: dedup (same match + same market, keep first).
    # Always applied (market-group deduplication is mandatory, not opt-in).
    # The legacy `dedup_enabled` flag is kept for backwards compatibility but
    # no longer gates this pass.
    seen_markets: set = set()
    filtered5 = []
    for sig in pass1:
        key = _live_market_key(sig)
        if key not in seen_markets:
            seen_markets.add(key)
            filtered5.append(sig)
        else:
            skip_reasons[id(sig)] = f"dedup({key})"
    pass1 = filtered5

    return pass1, skip_reasons


def run_paper_auto_place() -> dict:
    """Detecta señales live y auto-coloca bets paper maduras.
    Llamado por el background scheduler cada 60s.
    Usa PAPER_REACTION_DELAY_MINS: solo coloca señales con age >= min_dur + 1 min.
    """
    try:
        cfg = load_config()
        v   = cfg.get("versions", {})
        s   = cfg.get("strategies", {})
        md      = cfg.get("min_duration", {})
        md_live = cfg.get("min_duration_live", {})
        adj = cfg.get("adjustments", {})
        risk_filter = cfg.get("risk_filter", "all")
        bankroll_mode = cfg.get("bankroll_mode", "fixed")
        if bankroll_mode == "pct":
            bankroll   = float(cfg.get("initial_bankroll", 100.0))
            stake_pct  = float(cfg.get("stake_pct", 1.0))
            flat_stake = round(bankroll * stake_pct / 100, 2)
        else:
            flat_stake = float(cfg.get("flat_stake", 10.0))

        drift_s      = s.get("drift", {})
        clustering_s = s.get("clustering", {})
        xg_s         = s.get("xg", {})
        draw_s       = s.get("draw", {})
        pressure_s   = s.get("pressure", {})
        momentum_s   = s.get("momentum_xg", {})

        def _ver(v_key, s_key, default):
            strat = s.get(s_key, {})
            # enabled: false ALWAYS wins — regardless of version overrides
            if strat.get("enabled") is False:
                return "off"
            if v.get(v_key):
                return v.get(v_key)
            if strat.get("version"):
                return strat.get("version")
            return default

        versions = {
            "draw":       _ver("draw",       "draw",       "v2r"),
            "xg":         _ver("xg",         "xg",         "base"),
            "drift":      _ver("drift",      "drift",      "v1"),
            "clustering": _ver("clustering", "clustering", "v2"),
            "pressure":   _ver("pressure",   "pressure",   "v1"),
            "momentum":   _ver("momentum_xg", "momentum_xg", "off"),
            "tarde_asia": _ver("tarde_asia", "tarde_asia", "off"),
            "draw_min_dur":          str(md_live.get("draw",       md.get("draw", 1))),
            "xg_min_dur":            str(md_live.get("xg",         md.get("xg", 2))),
            "drift_min_dur":         str(md_live.get("drift",      md.get("drift", 2))),
            "clustering_min_dur":    str(md_live.get("clustering", md.get("clustering", 4))),
            "pressure_min_dur":      str(md_live.get("pressure",   md.get("pressure", 2))),
            "tarde_asia_min_dur":    str(md_live.get("tarde_asia", md.get("tarde_asia", 1))),
            "momentum_min_dur":      str(md_live.get("momentum",   md.get("momentum", 1))),
            "drift_threshold":       str(drift_s.get("driftMin", 30)),
            "drift_odds_max":        str(drift_s.get("oddsMax", 999)),
            "drift_goal_diff_min":   str(drift_s.get("goalDiffMin", 0)),
            "drift_minute_min":      str(drift_s.get("minuteMin", 0)),
            "drift_minute_max":      str(drift_s.get("minuteMax", 90)),
            "drift_mom_gap_min":     str(drift_s.get("momGapMin", 0)),
            "clustering_minute_max": str(clustering_s.get("minuteMax", 90)),
            "clustering_xg_rem_min": str(clustering_s.get("xgRemMin", 0)),
            "clustering_sot_min":    str(clustering_s.get("sotMin", 3)),
            "xg_minute_max":         str(xg_s.get("minuteMax", 90)),
            "xg_sot_min":            str(xg_s.get("sotMin", 0)),
            "xg_xg_excess_min":      str(xg_s.get("xgExcessMin", 0.5)),
            "draw_xg_max":           str(draw_s.get("xgMax", 1.0)),
            "draw_poss_max":         str(draw_s.get("possMax", 100)),
            "draw_shots_max":        str(draw_s.get("shotsMax", 20)),
            "draw_minute_min":       str(draw_s.get("minuteMin", 30)),
            "draw_minute_max":       str(draw_s.get("minuteMax", 90)),
            "xg_minute_min":         str(xg_s.get("minuteMin", 0)),
            "clustering_minute_min": str(clustering_s.get("minuteMin", 0)),
            "pressure_minute_min":   str(pressure_s.get("minuteMin", 0)),
            "pressure_minute_max":   str(pressure_s.get("minuteMax", 90)),
            "pressure_xg_sum_min":   str(pressure_s.get("xg_sum_min", 0)),
            "momentum_minute_min":   str(momentum_s.get("minuteMin", 0)),
            "momentum_minute_max":   str(momentum_s.get("minuteMax", 90)),
        }

        # Synthesize per-version registry entries for the 7 original strategies
        _s_configs = dict(s)
        _ORIG_MAP = {
            "draw": [
                ("back_draw_00_v1", "v1"), ("back_draw_00_v15", "v15"),
                ("back_draw_00_v2", "v2"), ("back_draw_00_v2r", "v2r"),
                ("back_draw_00_v3", "v3"), ("back_draw_00_v4",  "v4"),
            ],
            "drift": [
                ("odds_drift_v1", "v1"), ("odds_drift_v2", "v2"), ("odds_drift_v3", "v3"),
                ("odds_drift_v4", "v4"), ("odds_drift_v5", "v5"), ("odds_drift_v6", "v6"),
            ],
            "clustering":  [("goal_clustering",            None)],
            "pressure":    [("pressure_cooker",             None)],
            "xg": [
                ("xg_underperformance_base", "base"),
                ("xg_underperformance_v2",   "v2"),
                ("xg_underperformance_v3",   "v3"),
            ],
            "momentum_xg": [("momentum_xg_v1", "v1"), ("momentum_xg_v2", "v2")],
            "tarde_asia":  [("tarde_asia",                 None)],
        }
        _VER_LOOKUP = {"momentum_xg": "momentum"}
        for _legacy_key, _entries in _ORIG_MAP.items():
            _old_cfg = s.get(_legacy_key, {})
            _ver_key = _VER_LOOKUP.get(_legacy_key, _legacy_key)
            _active_ver = versions.get(_ver_key, "off")
            for (_reg_key, _ver) in _entries:
                _is_active = _active_ver != "off" and (_ver is None or _active_ver == _ver)
                _s_configs[_reg_key] = {**_old_cfg, "enabled": _is_active}
        versions["_strategy_configs"] = _s_configs
        versions["_min_duration"] = md

        # ── Audit: contar partidos live para log de ciclo ──
        try:
            _all_games = csv_reader.load_games()
            _n_live = sum(1 for g in _all_games if g.get("status") == "live")
        except Exception:
            _n_live = 0
        try:
            _audit.log_cycle_start(_n_live, source="auto_poller")
        except Exception as e:
            _log.debug(f"Audit log_cycle_start failed: {e}")

        result = csv_reader.detect_betting_signals(versions=versions)

        # ── Audit: loguear radar (condiciones parciales) ──
        try:
            _watchlist = csv_reader.detect_watchlist(versions=versions)
            for _item in _watchlist:
                try:
                    _audit.log_radar_item(_item)
                except Exception as e:
                    _log.debug(f"Audit log_radar_item failed: {e}")
        except Exception:
            _watchlist = []

        raw_signals = result.get("signals", [])

        # ── Audit: loguear todas las señales activas antes de filtrar ──
        for sig in raw_signals:
            try:
                _audit.log_signal_active(sig)
            except Exception as e:
                _log.debug(f"Audit log_signal_active failed: {e}")

        # ── Aplicar TODOS los filtros realistas (mirrors frontend applyRealisticAdjustments) ──
        filtered_signals, skip_reasons = _apply_realistic_adjustments(raw_signals, adj, risk_filter)

        # ── Audit: loguear señales filtradas con su motivo ──
        for sig in raw_signals:
            reason = skip_reasons.get(id(sig))
            if reason:
                try:
                    _audit.log_signal_filtered(sig, reason)
                except Exception as e:
                    _log.debug(f"Audit log_signal_filtered failed: {e}")

        placed = 0
        checked = 0
        _n_filtered_audit = len(raw_signals) - len(filtered_signals)

        for sig in filtered_signals:
            checked += 1
            sig_age     = sig.get("signal_age_minutes", 0)
            sig_min_dur = sig.get("min_duration_caps", 1)
            if sig.get("odds_favorable", True) and sig_age >= sig_min_dur + PAPER_REACTION_DELAY_MINS:
                _auto_place_signal(sig, flat_stake)
                placed += 1
            else:
                _not_mature = (
                    "odds_not_favorable" if not sig.get("odds_favorable", True)
                    else f"not_mature_yet(age={sig_age:.1f}min,need={sig_min_dur + PAPER_REACTION_DELAY_MINS})"
                )
                try:
                    _audit.log_signal_filtered(sig, _not_mature)
                except Exception as e:
                    _log.debug(f"Audit log_signal_filtered failed: {e}")
                _n_filtered_audit += 1

        # ── Audit: fin de ciclo ──
        try:
            _audit.log_cycle_end(
                n_signals=result.get("total_signals", 0),
                n_radar=len(_watchlist),
                n_placed=placed,
                n_filtered=_n_filtered_audit,
            )
        except Exception as e:
            _log.debug(f"Audit log_cycle_end failed: {e}")

        return {"placed": placed, "signals_checked": checked}

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


router = APIRouter()


# ==================== QUALITY ENDPOINTS ====================

@router.get("/quality/overview")
async def get_quality_overview() -> Dict[str, Any]:
    """Get overall quality metrics for all finished matches."""
    return csv_reader.analyze_quality_distribution()


@router.get("/quality/gaps")
async def get_gap_analysis() -> Dict[str, Any]:
    """Get gap analysis across all finished matches."""
    return csv_reader.analyze_gaps_distribution()


@router.get("/quality/stats-coverage")
async def get_stats_coverage() -> Dict[str, Any]:
    """Get percentage coverage for each stats field across all matches."""
    return csv_reader.analyze_stats_coverage()


@router.get("/quality/odds-coverage")
async def get_odds_coverage() -> Dict[str, Any]:
    """Get odds scraping coverage distribution across all finished matches."""
    return csv_reader.analyze_odds_coverage()


# ==================== STRATEGY CARTERA ENDPOINTS ====================

@router.get("/strategies/cartera")
async def get_strategy_cartera(
    cashout_minute: Optional[int] = Query(None, ge=-1, le=90),
    cashout_lay_pct: Optional[float] = Query(None, ge=5, le=100),
    adaptive_early_pct: Optional[float] = Query(None, ge=1, le=100),
    adaptive_late_pct: Optional[float] = Query(None, ge=1, le=100),
    adaptive_split_min: Optional[int] = Query(70, ge=30, le=90),
    adverse_goal_stop: Optional[bool] = Query(False),
    trailing_stop_pct: Optional[float] = Query(None, ge=1, le=100),
) -> Dict[str, Any]:
    """Combined portfolio view of all strategies.

    cashout_minute: if provided, simulate cash-out for losing bets at this minute.
    cashout_lay_pct: if provided, simulate cash-out when lay rises X% above entry price.
    adaptive_early_pct / adaptive_late_pct: adaptive threshold — loose before adaptive_split_min, tight after.
    adverse_goal_stop: cash out on first adverse goal (back_draw_00, odds_drift, momentum_xg only).
    trailing_stop_pct: trailing stop — fires when lay rises X% above the minimum lay seen since entry.
    Multiple modes can be active simultaneously; the first to trigger wins.
    """
    data = csv_reader.analyze_cartera()
    new_modes = (
        cashout_lay_pct is not None
        or (adaptive_early_pct is not None and adaptive_late_pct is not None)
        or adverse_goal_stop
        or trailing_stop_pct is not None
    )
    if new_modes:
        data = csv_reader.simulate_cashout_cartera(
            data,
            cashout_lay_pct=cashout_lay_pct,
            adaptive_early_pct=adaptive_early_pct,
            adaptive_late_pct=adaptive_late_pct,
            adaptive_split_min=adaptive_split_min or 70,
            adverse_goal_stop=adverse_goal_stop or False,
            trailing_stop_pct=trailing_stop_pct,
        )
    elif cashout_minute is not None:
        data = csv_reader.simulate_cashout_cartera(data, cashout_minute)
    return data


@router.get("/strategies/cartera/optimize")
async def optimize_strategy_cartera(
    top_n: Optional[int] = Query(10, ge=1, le=20),
) -> Dict[str, Any]:
    """Grid search over all CO modes and parameter combinations.
    Reads each match CSV only once for efficiency (~80 configs tested).
    Returns top_n configs ranked by P/L net, plus rescued/penalized metrics.
    """
    data = csv_reader.analyze_cartera()
    return csv_reader.optimize_cashout_cartera(data, top_n=top_n or 10)



# ==================== BETTING SIGNALS ENDPOINT ====================

@router.get("/signals/betting-opportunities")
async def get_betting_signals(
    draw: Optional[str] = None,
    xg: Optional[str] = None,
    drift: Optional[str] = None,
    clustering: Optional[str] = None,
    pressure: Optional[str] = None,
    momentum: Optional[str] = None,
    draw_min_dur: Optional[int] = None,
    xg_min_dur: Optional[int] = None,
    drift_min_dur: Optional[int] = None,
    clustering_min_dur: Optional[int] = None,
    pressure_min_dur: Optional[int] = None,
) -> Dict[str, Any]:
    """Detect live betting opportunities based on portfolio strategies.

    When no parameters are supplied, reads versions and min_duration from
    cartera_config.json. Query params act as explicit overrides.
    Applies adjustments (min_odds, max_odds, drift_min_minute) and risk_filter.
    Auto-places mature signals as paper bets.
    """
    cfg = load_config()
    v = cfg.get("versions", {})       # formato antiguo (puede estar vacío)
    s = cfg.get("strategies", {})     # formato nuevo (enabled + params)
    md      = cfg.get("min_duration", {})
    md_live = cfg.get("min_duration_live", {})
    adj = cfg.get("adjustments", {})
    risk_filter = cfg.get("risk_filter", "all")
    flat_stake = float(cfg.get("flat_stake", 10.0))

    def _ver(query_param, v_key, s_key, default):
        """Resuelve versión: query > enabled check > versions.<key> > strategies.<key>.version > default."""
        if query_param:
            return query_param
        strat = s.get(s_key, {})
        # enabled: false ALWAYS wins — regardless of version overrides
        if strat.get("enabled") is False:
            return "off"
        if v.get(v_key):
            return v.get(v_key)
        if strat.get("version"):
            return strat.get("version")
        return default

    # ── Extraer parámetros por estrategia desde config (single source of truth) ──
    # Estos params fluyen al detector live para garantizar alineación con histórico.
    drift_s       = s.get("drift", {})
    clustering_s  = s.get("clustering", {})
    xg_s          = s.get("xg", {})
    draw_s        = s.get("draw", {})
    pressure_s    = s.get("pressure", {})
    momentum_s    = s.get("momentum_xg", {})

    versions = {
        "draw":       _ver(draw,       "draw",       "draw",       "v2r"),
        "xg":         _ver(xg,         "xg",         "xg",         "base"),
        "drift":      _ver(drift,       "drift",      "drift",      "v1"),
        "clustering": _ver(clustering,  "clustering", "clustering", "v2"),
        "pressure":   _ver(pressure,    "pressure",   "pressure",   "v1"),
        "momentum":   _ver(momentum,    "momentum_xg", "momentum_xg", "off"),
        "tarde_asia": _ver(None,        "tarde_asia", "tarde_asia", "off"),
        "draw_min_dur":       str(draw_min_dur       if draw_min_dur       is not None else md_live.get("draw",       md.get("draw", 1))),
        "xg_min_dur":         str(xg_min_dur         if xg_min_dur         is not None else md_live.get("xg",         md.get("xg", 2))),
        "drift_min_dur":      str(drift_min_dur      if drift_min_dur      is not None else md_live.get("drift",      md.get("drift", 2))),
        "clustering_min_dur": str(clustering_min_dur if clustering_min_dur is not None else md_live.get("clustering", md.get("clustering", 4))),
        "pressure_min_dur":   str(pressure_min_dur   if pressure_min_dur   is not None else md_live.get("pressure",   md.get("pressure", 2))),
        "tarde_asia_min_dur": str(md_live.get("tarde_asia", md.get("tarde_asia", 1))),
        "momentum_min_dur":   str(md_live.get("momentum",   md.get("momentum", 1))),
        # ── Strategy thresholds (from cartera_config.json strategies block) ──
        # These make the live detector use the SAME params as the historical analysis.
        "drift_threshold":      str(drift_s.get("driftMin", 30)),
        "drift_odds_max":       str(drift_s.get("oddsMax", 999)),
        "drift_goal_diff_min":  str(drift_s.get("goalDiffMin", 0)),
        "drift_minute_min":     str(drift_s.get("minuteMin", 0)),
        "drift_minute_max":     str(drift_s.get("minuteMax", 90)),
        "drift_mom_gap_min":    str(drift_s.get("momGapMin", 0)),
        "clustering_minute_max": str(clustering_s.get("minuteMax", 90)),
        "clustering_xg_rem_min": str(clustering_s.get("xgRemMin", 0)),
        "clustering_sot_min":   str(clustering_s.get("sotMin", 3)),
        "xg_minute_max":        str(xg_s.get("minuteMax", 90)),
        "xg_sot_min":           str(xg_s.get("sotMin", 0)),
        "xg_xg_excess_min":     str(xg_s.get("xgExcessMin", 0.5)),
        "draw_xg_max":          str(draw_s.get("xgMax", 1.0)),
        "draw_poss_max":        str(draw_s.get("possMax", 100)),
        "draw_shots_max":       str(draw_s.get("shotsMax", 20)),
        "draw_minute_min":      str(draw_s.get("minuteMin", 30)),
        "draw_minute_max":      str(draw_s.get("minuteMax", 90)),
        "xg_minute_min":        str(xg_s.get("minuteMin", 0)),
        "clustering_minute_min": str(clustering_s.get("minuteMin", 0)),
        "pressure_minute_min":  str(pressure_s.get("minuteMin", 0)),
        "pressure_minute_max":  str(pressure_s.get("minuteMax", 90)),
        "pressure_xg_sum_min":  str(pressure_s.get("xg_sum_min", 0)),
        "momentum_minute_min":  str(momentum_s.get("minuteMin", 0)),
        "momentum_minute_max":  str(momentum_s.get("minuteMax", 90)),
    }

    # Synthesize per-version registry entries for the 7 original strategies
    _s_configs = dict(s)
    _ORIG_MAP = {
        "draw": [
            ("back_draw_00_v1", "v1"), ("back_draw_00_v15", "v15"),
            ("back_draw_00_v2", "v2"), ("back_draw_00_v2r", "v2r"),
            ("back_draw_00_v3", "v3"), ("back_draw_00_v4",  "v4"),
        ],
        "drift": [
            ("odds_drift_v1", "v1"), ("odds_drift_v2", "v2"), ("odds_drift_v3", "v3"),
            ("odds_drift_v4", "v4"), ("odds_drift_v5", "v5"), ("odds_drift_v6", "v6"),
        ],
        "clustering":  [("goal_clustering",            None)],
        "pressure":    [("pressure_cooker",             None)],
        "xg": [
            ("xg_underperformance_base", "base"),
            ("xg_underperformance_v2",   "v2"),
            ("xg_underperformance_v3",   "v3"),
        ],
        "momentum_xg": [("momentum_xg_v1", "v1"), ("momentum_xg_v2", "v2")],
        "tarde_asia":  [("tarde_asia",                 None)],
    }
    _VER_LOOKUP = {"momentum_xg": "momentum"}
    for _legacy_key, _entries in _ORIG_MAP.items():
        _old_cfg = s.get(_legacy_key, {})
        _ver_key = _VER_LOOKUP.get(_legacy_key, _legacy_key)
        _active_ver = versions.get(_ver_key, "off")
        for (_reg_key, _ver) in _entries:
            _is_active = _active_ver != "off" and (_ver is None or _active_ver == _ver)
            _s_configs[_reg_key] = {**_old_cfg, "enabled": _is_active}
    versions["_strategy_configs"] = _s_configs
    versions["_min_duration"] = md

    result = csv_reader.detect_betting_signals(versions=versions)

    # ── Filtros post-detección: aplica TODOS los filtros realistas (mirrors frontend) ──
    filtered, _ = _apply_realistic_adjustments(result.get("signals", []), adj, risk_filter)

    result["signals"] = filtered
    result["total_signals"] = len(filtered)

    # ── Audit log: señales visibles desde la API (solo lectura, NO coloca bets) ──
    # Las apuestas se colocan EXCLUSIVAMENTE por el background auto-poller (run_paper_auto_place)
    # que corre cada 60s. Esto garantiza que el sistema funciona 24/7 sin necesidad de abrir la UI.
    try:
        for sig in filtered:
            _audit.log_signal_active(sig)
    except Exception as e:
        _log.debug(f"Audit log_signal_active failed: {e}")

    return result


@router.get("/signals/watchlist")
async def get_watchlist(
    draw: Optional[str] = None,
    xg: Optional[str] = None,
    drift: Optional[str] = None,
    clustering: Optional[str] = None,
    pressure: Optional[str] = None,
    momentum: Optional[str] = None,
) -> List[Any]:
    """Matches close to triggering a signal but not yet meeting all conditions."""
    cfg = load_config()
    v = cfg.get("versions", {})
    s = cfg.get("strategies", {})

    def _ver(query_param, v_key, s_key, default):
        if query_param:
            return query_param
        strat = s.get(s_key, {})
        # enabled: false ALWAYS wins — regardless of version overrides
        if strat.get("enabled") is False:
            return "off"
        if v.get(v_key):
            return v.get(v_key)
        if strat.get("version"):
            return strat.get("version")
        return default

    versions = {
        "draw":       _ver(draw,      "draw",       "draw",       "v2r"),
        "xg":         _ver(xg,        "xg",         "xg",         "base"),
        "drift":      _ver(drift,      "drift",      "drift",      "v1"),
        "clustering": _ver(clustering, "clustering", "clustering", "v2"),
        "pressure":   _ver(pressure,   "pressure",   "pressure",   "v1"),
        "momentum":   _ver(momentum,   "momentum_xg", "momentum_xg", "off"),
        "tarde_asia": _ver(None,       "tarde_asia", "tarde_asia", "off"),
    }
    return csv_reader.detect_watchlist(versions=versions)


@router.post("/cache/clear")
async def clear_cache():
    """Clear analytics cache to force reload of data."""
    csv_reader.clear_analytics_cache()
    return {"status": "ok", "message": "Cache cleared successfully"}

