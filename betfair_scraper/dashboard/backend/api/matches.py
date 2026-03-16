"""
Endpoints de la API para partidos.
"""

import asyncio
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


def _force_delete(path) -> tuple:
    """Force-delete a file, bypassing OneDrive sync locks on Windows.

    Strategy 1 — direct unlink (fast path, works when file is not locked).
    Strategy 2 — rename to .__del__ then unlink (OneDrive releases the sync lock
                 on the original filename once the rename is issued; the renamed
                 file can then be deleted, or is left as orphan if still locked).
    Strategy 3 — subprocess 'del /f /q' (overrides read-only & some OS locks).
    """
    import os, sys, subprocess

    # Strategy 1: plain unlink
    try:
        path.unlink()
        return True, None
    except Exception:
        pass

    if sys.platform != "win32":
        return False, "Archivo bloqueado"

    # Strategy 2: rename → unlink  (bypasses OneDrive sync hold on the original name)
    tmp = path.with_name(path.name + ".__del__")
    try:
        os.rename(str(path), str(tmp))
    except Exception:
        tmp = path  # rename failed; try to delete the original name directly

    try:
        tmp.unlink()
        return True, None
    except Exception:
        pass

    # Strategy 3: cmd del /f /q
    try:
        subprocess.run(
            ["cmd", "/c", "del", "/f", "/q", str(tmp)],
            capture_output=True, timeout=4,
        )
        if not path.exists() and not tmp.exists():
            return True, None
    except Exception:
        pass

    # If the original is gone (renamed away) treat it as success
    if not path.exists():
        return True, None

    return False, "Archivo bloqueado por OneDrive — pausa OneDrive e inténtalo de nuevo"


@router.post("/bulk-delete")
async def bulk_delete_matches(body: BulkDeleteRequest):
    """Borra los archivos CSV de datos de varios partidos de una vez.
    No toca games.csv — para partidos finalizados (huérfanos) solo importa el CSV."""

    async def _delete_one(match_id: str) -> dict:
        try:
            csv_path = await asyncio.to_thread(_resolve_csv_path, match_id)
            if not csv_path.exists():
                return {"match_id": match_id, "ok": False, "error": "Archivo CSV no encontrado"}
            try:
                ok, err = await asyncio.wait_for(
                    asyncio.to_thread(_force_delete, csv_path), timeout=8.0
                )
                return {"match_id": match_id, "ok": ok, "error": err}
            except asyncio.TimeoutError:
                return {"match_id": match_id, "ok": False, "error": "Timeout (OneDrive no responde)"}
            except Exception as e:
                return {"match_id": match_id, "ok": False, "error": str(e)}
        except Exception as e:
            return {"match_id": match_id, "ok": False, "error": str(e)}

    results = await asyncio.gather(*[_delete_one(mid) for mid in body.match_ids])
    return {
        "results": list(results),
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
