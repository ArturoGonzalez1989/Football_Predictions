import csv
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query
from typing import Dict, List, Any, Optional
from utils import csv_reader
from utils import signals_audit_logger as _audit
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
    key = (match_id, strategy)

    # Dedup en sesión: ya fue colocado en este ciclo de vida del backend
    if key in _auto_placed_keys:
        return

    try:
        # Crear CSV si no existe
        if not _PLACED_BETS_CSV.exists():
            with open(_PLACED_BETS_CSV, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(_PLACED_BETS_HEADERS)

        # Obtener siguiente ID + dedup en CSV (por si backend reinició)
        next_id = 1
        if _PLACED_BETS_CSV.exists():
            with open(_PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
                if rows:
                    # Si ya existe en CSV, no duplicar
                    for row in rows:
                        if row.get("match_id") == match_id and row.get("strategy") == strategy:
                            _auto_placed_keys.add(key)
                            return
                    ids = [int(r['id']) for r in rows if r.get('id', '').isdigit()]
                    if ids:
                        next_id = max(ids) + 1

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(_PLACED_BETS_CSV, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
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
            ])
        # ── Audit log: apuesta colocada ──
        try:
            _audit.log_bet_placed(next_id, sig, stake)
        except Exception:
            pass
        _auto_placed_keys.add(key)
    except Exception as e:
        # Loguear error en fichero para depuración (no interrumpir el endpoint)
        try:
            with open(_AUTO_PLACE_LOG, 'a', encoding='utf-8') as _f:
                _f.write(
                    f"{datetime.utcnow()} | {match_id} | {strategy} | "
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}\n"
                )
        except Exception:
            pass

def run_paper_auto_place() -> dict:
    """Detecta señales live y auto-coloca bets paper maduras.
    Llamado por el background scheduler cada 60s.
    Usa PAPER_REACTION_DELAY_MINS: solo coloca señales con age >= min_dur + 1 min.
    """
    try:
        cfg = load_config()
        v   = cfg.get("versions", {})
        s   = cfg.get("strategies", {})
        md  = cfg.get("min_duration", {})
        adj = cfg.get("adjustments", {})
        risk_filter = cfg.get("risk_filter", "all")
        flat_stake  = float(cfg.get("flat_stake", 10.0))

        tarde_asia_ver = v.get("tarde_asia") or ("v1" if s.get("tarde_asia", {}).get("enabled") else "off")
        momentum_ver   = s.get("momentum_xg", {}).get("version") or v.get("momentum_xg", "off")

        drift_s      = s.get("drift", {})
        clustering_s = s.get("clustering", {})
        xg_s         = s.get("xg", {})
        draw_s       = s.get("draw", {})
        pressure_s   = s.get("pressure", {})
        momentum_s   = s.get("momentum_xg", {})

        def _ver(v_key, s_key, default):
            if v.get(v_key):
                return v.get(v_key)
            strat = s.get(s_key, {})
            if strat.get("enabled") is False:
                return "off"
            if strat.get("version"):
                return strat.get("version")
            return default

        versions = {
            "draw":       _ver("draw",       "draw",       "v2r"),
            "xg":         _ver("xg",         "xg",         "base"),
            "drift":      _ver("drift",      "drift",      "v1"),
            "clustering": _ver("clustering", "clustering", "v2"),
            "pressure":   _ver("pressure",   "pressure",   "v1"),
            "momentum":   momentum_ver,
            "tarde_asia": tarde_asia_ver,
            "draw_min_dur":          str(md.get("draw", 1)),
            "xg_min_dur":            str(md.get("xg", 2)),
            "drift_min_dur":         str(md.get("drift", 2)),
            "clustering_min_dur":    str(md.get("clustering", 4)),
            "pressure_min_dur":      str(md.get("pressure", 2)),
            "drift_threshold":       str(drift_s.get("driftMin", 30)),
            "drift_odds_max":        str(drift_s.get("oddsMax", 999)),
            "drift_goal_diff_min":   str(drift_s.get("goalDiffMin", 0)),
            "drift_minute_min":      str(drift_s.get("minuteMin", 0)),
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
            "momentum_minute_min":   str(momentum_s.get("minuteMin", 0)),
            "momentum_minute_max":   str(momentum_s.get("minuteMax", 90)),
        }

        # ── Audit: contar partidos live para log de ciclo ──
        try:
            _all_games = csv_reader.load_games()
            _n_live = sum(1 for g in _all_games if g.get("status") == "live")
        except Exception:
            _n_live = 0
        try:
            _audit.log_cycle_start(_n_live, source="auto_poller")
        except Exception:
            pass

        result = csv_reader.detect_betting_signals(versions=versions)

        # ── Audit: loguear radar (condiciones parciales) ──
        try:
            _watchlist = csv_reader.detect_watchlist(versions=versions)
            for _item in _watchlist:
                try:
                    _audit.log_radar_item(_item)
                except Exception:
                    pass
        except Exception:
            _watchlist = []

        adj_enabled   = adj.get("enabled", True)
        min_odds_cfg  = float(adj.get("min_odds", 0))   if adj_enabled else 0
        max_odds_cfg  = float(adj.get("max_odds", 999)) if adj_enabled else 999
        drift_min_min = int(adj.get("drift_min_minute", 0)) if adj_enabled else 0

        placed = 0
        checked = 0
        _n_filtered_audit = 0
        for sig in result.get("signals", []):
            # ── Audit: loguear señal activa ──
            try:
                _audit.log_signal_active(sig)
            except Exception:
                pass

            back_odds  = sig.get("back_odds")
            risk_level = (sig.get("risk_info") or {}).get("risk_level", "none")

            _skip_reason = ""
            if back_odds is not None:
                if min_odds_cfg > 0 and back_odds < min_odds_cfg:
                    _skip_reason = f"odds_low({back_odds:.2f}<{min_odds_cfg})"
                elif max_odds_cfg < 999 and back_odds > max_odds_cfg:
                    _skip_reason = f"odds_high({back_odds:.2f}>{max_odds_cfg})"

            if not _skip_reason and drift_min_min > 0 and sig.get("strategy", "").startswith("odds_drift"):
                if (sig.get("minute") or 0) < drift_min_min:
                    _skip_reason = f"drift_too_early(min{sig.get('minute')}<{drift_min_min})"

            if not _skip_reason:
                if risk_filter == "no_risk" and risk_level not in ("none", ""):
                    _skip_reason = f"risk_filter_no_risk(level={risk_level})"
                elif risk_filter == "medium" and risk_level != "medium":
                    _skip_reason = f"risk_filter_medium(level={risk_level})"
                elif risk_filter == "high" and risk_level != "high":
                    _skip_reason = f"risk_filter_high(level={risk_level})"
                elif risk_filter == "with_risk" and risk_level not in ("medium", "high"):
                    _skip_reason = f"risk_filter_with_risk(level={risk_level})"

            if _skip_reason:
                try:
                    _audit.log_signal_filtered(sig, _skip_reason)
                except Exception:
                    pass
                _n_filtered_audit += 1
                continue

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
                except Exception:
                    pass
                _n_filtered_audit += 1

        # ── Audit: fin de ciclo ──
        try:
            _audit.log_cycle_end(
                n_signals=result.get("total_signals", 0),
                n_radar=len(_watchlist),
                n_placed=placed,
                n_filtered=_n_filtered_audit,
            )
        except Exception:
            pass

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


@router.get("/quality/distribution")
async def get_quality_distribution() -> Dict[str, Any]:
    """Get quality distribution histogram across all matches."""
    data = csv_reader.analyze_quality_distribution()
    return {
        "bins": data.get("bins", [])
    }


@router.get("/quality/gaps")
async def get_gap_analysis() -> Dict[str, Any]:
    """Get gap analysis across all finished matches."""
    return csv_reader.analyze_gaps_distribution()


@router.get("/quality/stats-coverage")
async def get_stats_coverage() -> Dict[str, Any]:
    """Get percentage coverage for each stats field across all matches."""
    return csv_reader.analyze_stats_coverage()


@router.get("/quality/low-quality-matches")
async def get_low_quality_matches(threshold: int = Query(50, ge=0, le=100)) -> Dict[str, Any]:
    """Get list of matches below quality threshold (for display only)."""
    return {
        "threshold": threshold,
        "matches": csv_reader.get_low_quality_matches(threshold)
    }


@router.get("/quality/odds-coverage")
async def get_odds_coverage() -> Dict[str, Any]:
    """Get odds scraping coverage distribution across all finished matches."""
    return csv_reader.analyze_odds_coverage()


# ==================== INSIGHTS ENDPOINTS ====================

@router.get("/insights/momentum-patterns")
async def get_momentum_patterns() -> Dict[str, Any]:
    """Analyze momentum swings and comeback patterns."""
    return csv_reader.analyze_momentum_patterns()


@router.get("/insights/xg-accuracy")
async def get_xg_accuracy() -> Dict[str, Any]:
    """Analyze xG prediction accuracy vs actual goals."""
    return csv_reader.analyze_xg_accuracy()


@router.get("/insights/odds-movements")
async def get_odds_movements() -> Dict[str, Any]:
    """Analyze betting odds drift and contraction patterns."""
    return csv_reader.analyze_odds_movements()


@router.get("/insights/over-under")
async def get_over_under_analysis() -> Dict[str, Any]:
    """Analyze Over/Under line hit rates and patterns."""
    return csv_reader.analyze_over_under_patterns()


@router.get("/insights/correlations")
async def get_stat_correlations() -> Dict[str, Any]:
    """Calculate correlations between key match statistics."""
    return csv_reader.calculate_stat_correlations()


# ==================== STRATEGY TRACKING ENDPOINTS ====================

@router.get("/strategies/back-draw-00")
async def get_strategy_back_draw_00() -> Dict[str, Any]:
    """Track the 'Back Draw at 0-0 from min 30' strategy."""
    return csv_reader.analyze_strategy_back_draw_00()


@router.get("/strategies/xg-underperformance")
async def get_strategy_xg_underperformance() -> Dict[str, Any]:
    """Track the 'xG Underperformance - Back Over' strategy."""
    return csv_reader.analyze_strategy_xg_underperformance()


@router.get("/strategies/odds-drift")
async def get_strategy_odds_drift() -> Dict[str, Any]:
    """Track the 'Odds Drift Contrarian - Back Winning Team' strategy."""
    return csv_reader.analyze_strategy_odds_drift()


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


@router.get("/strategies/goal-clustering")
async def get_strategy_goal_clustering() -> Dict[str, Any]:
    """Goal Clustering V2: Back Over after goal + SoT >= 3."""
    return csv_reader.analyze_strategy_goal_clustering()

@router.get("/strategies/pressure-cooker")
async def get_strategy_pressure_cooker() -> Dict[str, Any]:
    """Pressure Cooker V1: Back Over on drawn matches (1-1+) at min 65-75."""
    return csv_reader.analyze_strategy_pressure_cooker()

@router.get("/strategies/tarde-asia")
async def get_strategy_tarde_asia() -> Dict[str, Any]:
    """Tarde Asia V1: Back Over 2.5 in afternoon matches from Asian/German/French leagues."""
    return csv_reader.analyze_strategy_tarde_asia()

@router.get("/strategies/momentum-xg-v1")
async def get_strategy_momentum_xg_v1() -> Dict[str, Any]:
    """Momentum Dominante x xG V1 (Ultra Relajadas): 66.7% WR, 52.2% ROI."""
    return csv_reader.analyze_strategy_momentum_xg(version="v1")

@router.get("/strategies/momentum-xg-v2")
async def get_strategy_momentum_xg_v2() -> Dict[str, Any]:
    """Momentum Dominante x xG V2 (Máximas): 60% WR, 68.7% ROI."""
    return csv_reader.analyze_strategy_momentum_xg(version="v2")


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
    md = cfg.get("min_duration", {})
    adj = cfg.get("adjustments", {})
    risk_filter = cfg.get("risk_filter", "all")
    flat_stake = float(cfg.get("flat_stake", 10.0))

    def _ver(query_param, v_key, s_key, default):
        """Resuelve versión: query > versions.<key> > strategies.<key>.enabled > default."""
        if query_param:
            return query_param
        if v.get(v_key):
            return v.get(v_key)
        strat = s.get(s_key, {})
        if strat.get("enabled") is False:
            return "off"
        if strat.get("version"):
            return strat.get("version")
        return default

    # Tarde asia: usa enabled del bloque strategies
    tarde_asia_ver = v.get("tarde_asia") or ("v1" if s.get("tarde_asia", {}).get("enabled") else "off")
    # Momentum: usa strategies.momentum_xg.version explícitamente
    momentum_ver = momentum or s.get("momentum_xg", {}).get("version") or v.get("momentum_xg", "off")

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
        "momentum":   momentum_ver,
        "tarde_asia": tarde_asia_ver,
        "draw_min_dur":       str(draw_min_dur       if draw_min_dur       is not None else md.get("draw", 1)),
        "xg_min_dur":         str(xg_min_dur         if xg_min_dur         is not None else md.get("xg", 2)),
        "drift_min_dur":      str(drift_min_dur      if drift_min_dur      is not None else md.get("drift", 2)),
        "clustering_min_dur": str(clustering_min_dur if clustering_min_dur is not None else md.get("clustering", 4)),
        "pressure_min_dur":   str(pressure_min_dur   if pressure_min_dur   is not None else md.get("pressure", 2)),
        # ── Strategy thresholds (from cartera_config.json strategies block) ──
        # These make the live detector use the SAME params as the historical analysis.
        "drift_threshold":      str(drift_s.get("driftMin", 30)),
        "drift_odds_max":       str(drift_s.get("oddsMax", 999)),
        "drift_goal_diff_min":  str(drift_s.get("goalDiffMin", 0)),
        "drift_minute_min":     str(drift_s.get("minuteMin", 0)),
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
        "momentum_minute_min":  str(momentum_s.get("minuteMin", 0)),
        "momentum_minute_max":  str(momentum_s.get("minuteMax", 90)),
    }

    result = csv_reader.detect_betting_signals(versions=versions)

    # ── Filtros post-detección (ajustes del modo realista + risk_filter) ──
    adj_enabled = adj.get("enabled", True)
    min_odds_cfg = float(adj.get("min_odds", 0)) if adj_enabled else 0
    max_odds_cfg = float(adj.get("max_odds", 999)) if adj_enabled else 999
    drift_min_min = int(adj.get("drift_min_minute", 0)) if adj_enabled else 0

    filtered: list = []
    for sig in result.get("signals", []):
        back_odds = sig.get("back_odds")
        risk_level = (sig.get("risk_info") or {}).get("risk_level", "none")

        # min_odds / max_odds — solo si hay cuota disponible
        if back_odds is not None:
            if min_odds_cfg > 0 and back_odds < min_odds_cfg:
                continue
            if max_odds_cfg < 999 and back_odds > max_odds_cfg:
                continue

        # drift_min_minute — excluir señales Drift antes del minuto configurado
        if drift_min_min > 0 and sig.get("strategy", "").startswith("odds_drift"):
            if (sig.get("minute") or 0) < drift_min_min:
                continue

        # risk_filter
        if risk_filter == "no_risk" and risk_level not in ("none", ""):
            continue
        if risk_filter == "medium" and risk_level != "medium":
            continue
        if risk_filter == "high" and risk_level != "high":
            continue
        if risk_filter == "with_risk" and risk_level not in ("medium", "high"):
            continue

        filtered.append(sig)

    result["signals"] = filtered
    result["total_signals"] = len(filtered)

    # ── Audit log: señales visibles desde la API (solo lectura, NO coloca bets) ──
    # Las apuestas se colocan EXCLUSIVAMENTE por el background auto-poller (run_paper_auto_place)
    # que corre cada 60s. Esto garantiza que el sistema funciona 24/7 sin necesidad de abrir la UI.
    try:
        for sig in filtered:
            _audit.log_signal_active(sig)
    except Exception:
        pass

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
        if v.get(v_key):
            return v.get(v_key)
        strat = s.get(s_key, {})
        if strat.get("enabled") is False:
            return "off"
        if strat.get("version"):
            return strat.get("version")
        return default

    tarde_asia_ver = v.get("tarde_asia") or ("v1" if s.get("tarde_asia", {}).get("enabled") else "off")
    momentum_ver = momentum or s.get("momentum_xg", {}).get("version") or v.get("momentum_xg", "off")

    versions = {
        "draw":       _ver(draw,      "draw",       "draw",       "v2r"),
        "xg":         _ver(xg,        "xg",         "xg",         "base"),
        "drift":      _ver(drift,      "drift",      "drift",      "v1"),
        "clustering": _ver(clustering, "clustering", "clustering", "v2"),
        "pressure":   _ver(pressure,   "pressure",   "pressure",   "v1"),
        "momentum":   momentum_ver,
        "tarde_asia": tarde_asia_ver,
    }
    return csv_reader.detect_watchlist(versions=versions)


@router.post("/cache/clear")
async def clear_cache():
    """Clear analytics cache to force reload of data."""
    csv_reader.clear_analytics_cache()
    return {"status": "ok", "message": "Cache cleared successfully"}

