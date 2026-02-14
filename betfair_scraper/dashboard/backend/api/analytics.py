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
