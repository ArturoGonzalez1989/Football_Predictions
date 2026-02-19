"""
Strategy Explorer API — grid-search sobre minuto × condición × resultado.

Endpoints:
  GET  /results  → lee caché JSON (o ejecuta si no existe)
  POST /run      → fuerza re-ejecución completa
"""

import json
import sys
import importlib
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Query, HTTPException

router = APIRouter()

# betfair_scraper/dashboard/backend/api/explorer.py
# .parent                   = api/
# .parent.parent             = backend/
# .parent.parent.parent      = dashboard/
# .parent.parent.parent.parent = betfair_scraper/
_BETFAIR_DIR  = Path(__file__).resolve().parent.parent.parent.parent
_RESULTS_JSON = _BETFAIR_DIR / "explorer_results.json"
_SCRIPTS_DIR  = _BETFAIR_DIR / "scripts"


def _run_exploration(min_sample: int, max_results: int) -> Dict[str, Any]:
    """Importa y ejecuta el script de exploración."""
    scripts_dir = str(_SCRIPTS_DIR)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    try:
        import strategy_explorer as se
        importlib.reload(se)
        return se.run_strategy_exploration(
            min_sample=min_sample,
            max_results=max_results,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Exploration failed: {exc}",
        ) from exc


@router.get("/results")
async def get_explorer_results(
    min_sample: int = Query(5, ge=1, le=50),
    max_results: int = Query(200, ge=10, le=500),
) -> Dict[str, Any]:
    """Devuelve resultados cacheados; ejecuta si no hay caché."""
    if _RESULTS_JSON.exists():
        try:
            return json.loads(_RESULTS_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass  # caché corrupto → re-ejecutar
    return _run_exploration(min_sample, max_results)


@router.post("/run")
async def run_explorer(
    min_sample: int = Query(5, ge=1, le=50),
    max_results: int = Query(200, ge=10, le=500),
) -> Dict[str, Any]:
    """Fuerza re-ejecución completa y guarda resultados frescos."""
    return _run_exploration(min_sample, max_results)
