"""
Endpoints de la API para partidos.
"""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.csv_reader import load_games, load_match_detail, load_momentum_data, load_all_stats, load_match_full, delete_match, load_all_captures, _resolve_csv_path
from utils.scraper_status import parse_per_match_log, LOGS_DIR

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("")
def get_matches():
    """Lista todos los partidos de games.csv separados por estado (live/upcoming/finished)."""
    all_games = load_games()

    # Separar por estado
    live = [g for g in all_games if g["status"] == "live"]
    upcoming = [g for g in all_games if g["status"] == "upcoming"]
    finished = [g for g in all_games if g["status"] == "finished"]

    # Enriquecer live matches con estado del log por partido
    if live:
        try:
            log_files = sorted(
                LOGS_DIR.glob("scraper_*.log"),
                key=lambda x: x.stat().st_mtime,
                reverse=True,
            )
            if log_files:
                match_ids = {g["match_id"] for g in live}
                log_health = parse_per_match_log(log_files[0], match_ids)
                for g in live:
                    health = log_health.get(g["match_id"], {"log_status": "unknown"})
                    g.update(health)
        except Exception:
            pass  # No bloqueamos la respuesta si el parsing falla

    return {
        "live": live,
        "upcoming": upcoming,
        "finished": finished
    }


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


class BulkDeleteRequest(BaseModel):
    match_ids: List[str]


@router.post("/bulk-delete")
def bulk_delete_matches(body: BulkDeleteRequest):
    """Borra los archivos CSV de datos de varios partidos de una vez.
    No toca games.csv — para partidos finalizados (huérfanos) solo importa el CSV."""
    results = []
    for match_id in body.match_ids:
        deleted = False
        error = None
        try:
            csv_path = _resolve_csv_path(match_id)
            if not csv_path.exists():
                error = "Archivo CSV no encontrado"
            else:
                try:
                    csv_path.unlink()
                    deleted = True
                except PermissionError:
                    import gc
                    gc.collect()
                    try:
                        csv_path.unlink()
                        deleted = True
                    except PermissionError:
                        error = "Archivo bloqueado (OneDrive o scraper activo)"
        except Exception as e:
            error = str(e)
        results.append({"match_id": match_id, "ok": deleted, "error": error})
    return {
        "results": results,
        "deleted": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
    }


@router.delete("/{match_id}")
def remove_match(match_id: str):
    """Elimina un partido de games.csv y borra su CSV de datos."""
    result = delete_match(match_id)
    # If CSV still exists after deletion attempt, it's locked by another process
    if not result["deleted_data"] and not result["deleted_from_csv"]:
        raise HTTPException(
            status_code=409,
            detail="No se pudo eliminar el archivo CSV. Puede estar bloqueado por el scraper o por OneDrive. Para a el scraper e inténtalo de nuevo."
        )
    if not result["deleted_data"]:
        # Removed from games.csv but file is still locked
        raise HTTPException(
            status_code=409,
            detail="Eliminado de games.csv pero el archivo CSV sigue en uso. Para el scraper e inténtalo de nuevo."
        )
    return result
