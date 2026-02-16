from fastapi import APIRouter, Query
from typing import Dict, List, Any
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
async def get_strategy_cartera() -> Dict[str, Any]:
    """Combined portfolio view of all strategies."""
    return csv_reader.analyze_cartera()

@router.get("/strategies/goal-clustering")
async def get_strategy_goal_clustering() -> Dict[str, Any]:
    """Goal Clustering V2: Back Over after goal + SoT >= 3."""
    return csv_reader.analyze_strategy_goal_clustering()

@router.get("/strategies/pressure-cooker")
async def get_strategy_pressure_cooker() -> Dict[str, Any]:
    """Pressure Cooker V1: Back Over on drawn matches (1-1+) at min 65-75."""
    return csv_reader.analyze_strategy_pressure_cooker()


# ==================== BETTING SIGNALS ENDPOINT ====================

@router.get("/signals/betting-opportunities")
async def get_betting_signals() -> Dict[str, Any]:
    """Detect live betting opportunities based on portfolio strategies."""
    return csv_reader.detect_betting_signals()

