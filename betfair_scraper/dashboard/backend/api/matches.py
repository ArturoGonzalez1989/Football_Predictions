"""
Endpoints de la API para partidos.
"""

from fastapi import APIRouter
from utils.csv_reader import load_games, load_match_detail, load_momentum_data, load_all_stats, load_match_full, delete_match, load_all_captures

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("")
def get_matches():
    """Lista todos los partidos de games.csv con su estado."""
    return load_games()


@router.get("/{match_id}")
def get_match_detail(match_id: str):
    """Detalle de un partido: últimas capturas, quality, gaps."""
    return load_match_detail(match_id)


@router.get("/{match_id}/momentum")
def get_match_momentum(match_id: str):
    """Datos de momentum para gráficos."""
    return load_momentum_data(match_id)


@router.get("/{match_id}/stats")
def get_match_stats(match_id: str):
    """Últimas estadísticas del partido."""
    return load_all_stats(match_id)


@router.get("/{match_id}/full")
def get_match_full(match_id: str):
    """Resumen completo: stats finales, cuotas apertura/cierre, timeline."""
    return load_match_full(match_id)


@router.get("/{match_id}/all-captures")
def get_all_captures(match_id: str):
    """Todas las capturas minuto a minuto del partido."""
    return load_all_captures(match_id)


@router.delete("/{match_id}")
def remove_match(match_id: str):
    """Elimina un partido de games.csv y borra su CSV de datos."""
    return delete_match(match_id)
