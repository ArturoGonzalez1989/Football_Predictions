from fastapi import APIRouter, Query
from typing import Dict, List, Any, Optional
from utils import csv_reader

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
    draw: str = "v2r",
    xg: str = "v2",
    drift: str = "v1",
    clustering: str = "v2",
    pressure: str = "v1",
    momentum: str = "v1",
    draw_min_dur: int = 1,
    xg_min_dur: int = 2,
    drift_min_dur: int = 2,
    clustering_min_dur: int = 4,
    pressure_min_dur: int = 2,
) -> Dict[str, Any]:
    """Detect live betting opportunities based on portfolio strategies.

    Each parameter specifies the version of the strategy to use.
    Use "off" to disable a strategy.
    xxx_min_dur: minimum minutes a signal must be active to be considered mature.
    """
    versions = {
        "draw": draw, "xg": xg, "drift": drift, "clustering": clustering,
        "pressure": pressure, "momentum": momentum,
        "draw_min_dur": str(draw_min_dur), "xg_min_dur": str(xg_min_dur),
        "drift_min_dur": str(drift_min_dur), "clustering_min_dur": str(clustering_min_dur),
        "pressure_min_dur": str(pressure_min_dur),
    }
    return csv_reader.detect_betting_signals(versions=versions)


@router.get("/signals/watchlist")
async def get_watchlist(
    draw: str = "v2r",
    xg: str = "v2",
    drift: str = "v1",
    clustering: str = "v2",
    pressure: str = "v1",
    momentum: str = "v1",
) -> List[Any]:
    """Matches close to triggering a signal but not yet meeting all conditions."""
    versions = {"draw": draw, "xg": xg, "drift": drift, "clustering": clustering, "pressure": pressure, "momentum": momentum}
    return csv_reader.detect_watchlist(versions=versions)


@router.post("/cache/clear")
async def clear_cache():
    """Clear analytics cache to force reload of data."""
    csv_reader.clear_analytics_cache()
    return {"status": "ok", "message": "Cache cleared successfully"}

