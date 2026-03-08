"""
Debug API — HTML Snapshot toggle + Memory monitoring.
"""
import logging
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["debug"])

try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _PSUTIL_OK = False
    logger.warning("psutil not installed — /api/debug/memory will return empty data")

# betfair_scraper/data/
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
FLAG_FILE = _DATA_DIR / ".html_snapshots_enabled"
SNAP_DIR  = _DATA_DIR / "html_snapshots"


def _snap_stats() -> dict:
    if not SNAP_DIR.exists():
        return {"count": 0, "size_mb": 0.0, "matches": []}
    files = list(SNAP_DIR.glob("*.html.gz"))
    size_mb = round(sum(f.stat().st_size for f in files) / 1_000_000, 2)
    # Unique match IDs from filename pattern: {match_id}_{timestamp}.html.gz
    match_ids = sorted({f.name.rsplit("_", 1)[0] for f in files})
    return {"count": len(files), "size_mb": size_mb, "matches": match_ids}


@router.get("/api/debug/html-snapshots")
def get_snapshot_status():
    """Devuelve el estado actual del toggle y estadísticas de snapshots guardados."""
    stats = _snap_stats()
    return {
        "enabled": FLAG_FILE.exists(),
        **stats,
    }


@router.post("/api/debug/html-snapshots/enable")
def enable_snapshots():
    """Activa la captura de HTML snapshots. Efectivo en el próximo ciclo del scraper (~60s)."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    FLAG_FILE.touch()
    return {"enabled": True}


@router.post("/api/debug/html-snapshots/disable")
def disable_snapshots():
    """Desactiva la captura. El scraper deja de guardar snapshots en el próximo ciclo."""
    FLAG_FILE.unlink(missing_ok=True)
    return {"enabled": False}


@router.delete("/api/debug/html-snapshots")
def delete_snapshots():
    """Borra todos los snapshots HTML acumulados para liberar disco."""
    deleted = 0
    if SNAP_DIR.exists():
        for f in SNAP_DIR.glob("*.html.gz"):
            f.unlink()
            deleted += 1
    return {"deleted": deleted}


# ── Memory monitoring ──────────────────────────────────────────────────────────

@router.get("/api/debug/memory")
def get_process_memory():
    """
    Devuelve el uso de memoria de todos los procesos Python/Chrome/Node en el sistema.
    Útil para diagnosticar qué proceso está consumiendo RAM antes/después del optimizer.
    """
    if not _PSUTIL_OK:
        return {"error": "psutil not installed — run: pip install psutil", "processes": [], "summary": {}}

    processes = []
    for proc in _psutil.process_iter(["pid", "name", "memory_info", "cmdline"]):
        try:
            name = proc.info["name"] or ""
            name_lower = name.lower()
            if not any(x in name_lower for x in ["python", "chrome", "node", "chromedriver"]):
                continue
            mem_mb = round((proc.info["memory_info"].rss) / 1024 / 1024, 1)
            cmdline = proc.info.get("cmdline") or []
            # Show up to 3 tokens of cmdline for context (avoid leaking full paths)
            cmd_preview = " ".join(str(c) for c in cmdline[:4])[:100] if cmdline else name
            processes.append({"pid": proc.info["pid"], "name": name, "mem_mb": mem_mb, "cmd": cmd_preview})
        except (_psutil.NoSuchProcess, _psutil.AccessDenied):
            pass

    processes.sort(key=lambda x: x["mem_mb"], reverse=True)
    total_python = round(sum(p["mem_mb"] for p in processes if "python" in p["name"].lower()), 1)
    total_chrome = round(sum(p["mem_mb"] for p in processes if "chrome" in p["name"].lower()), 1)
    total_node   = round(sum(p["mem_mb"] for p in processes if "node"   in p["name"].lower()), 1)
    summary = {"total_python_mb": total_python, "total_chrome_mb": total_chrome,
               "total_node_mb": total_node, "process_count": len(processes)}
    logger.info("Memory snapshot: Python=%.1fMB Chrome=%.1fMB Node=%.1fMB (%d procs)",
                total_python, total_chrome, total_node, len(processes))
    return {"processes": processes, "summary": summary}


class BrowserMemReport(BaseModel):
    usedJSHeapSizeMB: float
    totalJSHeapSizeMB: float = 0.0
    jsHeapSizeLimitMB: float
    context: str = ""


@router.post("/api/debug/memory/report")
async def report_browser_memory(body: BrowserMemReport):
    """
    Recibe el reporte de memoria V8 del browser.
    Los logs se escriben en el backend y sobreviven a un crash de Chrome.
    """
    pct = round(body.usedJSHeapSizeMB / body.jsHeapSizeLimitMB * 100, 1) if body.jsHeapSizeLimitMB > 0 else 0
    logger.warning(
        "BROWSER V8 HEAP  used=%.1fMB  total=%.1fMB  limit=%.1fMB  (%.1f%%)  [%s]",
        body.usedJSHeapSizeMB, body.totalJSHeapSizeMB, body.jsHeapSizeLimitMB, pct, body.context,
    )
    return {"ok": True}
