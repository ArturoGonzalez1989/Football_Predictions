import csv
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query
from typing import Dict, List, Any, Optional
from utils import csv_reader
from api.config import load_config

# Path compartido con bets.py
_PLACED_BETS_CSV = Path(__file__).resolve().parent.parent.parent.parent / "placed_bets.csv"
_PLACED_BETS_HEADERS = [
    'id', 'timestamp_utc', 'match_id', 'match_name', 'match_url',
    'strategy', 'strategy_name', 'minute', 'score', 'recommendation',
    'back_odds', 'min_odds', 'expected_value', 'confidence',
    'win_rate_historical', 'roi_historical', 'sample_size',
    'bet_type', 'stake', 'notes', 'status', 'result', 'pl'
]


def _auto_place_signal(sig: dict, stake: float) -> None:
    """Registra automáticamente una señal madura como apuesta paper en placed_bets.csv."""
    try:
        # Crear CSV si no existe
        if not _PLACED_BETS_CSV.exists():
            with open(_PLACED_BETS_CSV, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(_PLACED_BETS_HEADERS)

        # Obtener siguiente ID
        next_id = 1
        if _PLACED_BETS_CSV.exists():
            with open(_PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
                if rows:
                    ids = [int(r['id']) for r in rows if r.get('id', '').isdigit()]
                    if ids:
                        next_id = max(ids) + 1

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open(_PLACED_BETS_CSV, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([
                next_id, timestamp,
                sig.get("match_id", ""),
                sig.get("match_name", ""),
                sig.get("match_url", ""),
                sig.get("strategy", ""),
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
    except Exception:
        pass  # No interrumpir el endpoint si falla el auto-place

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
    cashout_minute: Optional[int] = Query(None, ge=0, le=90),
) -> Dict[str, Any]:
    """Combined portfolio view of all strategies.

    cashout_minute: if provided, simulate cash-out for losing bets at this minute.
    """
    data = csv_reader.analyze_cartera()
    if cashout_minute is not None:
        data = csv_reader.simulate_cashout_cartera(data, cashout_minute)
    return data

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

    # ── Auto-place señales maduras como paper bets ──
    for sig in filtered:
        if sig.get("is_mature"):
            _auto_place_signal(sig, flat_stake)

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

