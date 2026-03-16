"""
Endpoints para lanzar scripts auxiliares en una ventana de terminal nueva.
"""

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/scripts", tags=["scripts"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
AUXILIAR_DIR = PROJECT_ROOT / "auxiliar"
SCRIPTS_DIR  = PROJECT_ROOT / "scripts"


def _launch_in_terminal(cmd: list[str], title: str, cwd: Path):
    """Abre una nueva ventana cmd con el script. Al terminar muestra 'Pulsa cualquier tecla...'"""
    # Escribir un .bat temporal para evitar problemas de quoting con rutas con espacios
    bat = cwd / "_tmp_launch.bat"
    inner = " ".join(f'"{c}"' for c in cmd)
    bat.write_text(f"@echo off\ntitle {title}\n{inner}\necho.\npause\n", encoding="utf-8")
    os.startfile(str(bat))


@router.post("/crossref-telegram")
def run_crossref_telegram():
    try:
        script = AUXILIAR_DIR / "crossref_telegram_bt.py"
        _launch_in_terminal(
            [sys.executable, str(script)],
            title="Crossref Telegram vs BT",
            cwd=PROJECT_ROOT,
        )
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/bt-export")
def run_bt_export():
    try:
        script = SCRIPTS_DIR / "bt_optimizer.py"
        _launch_in_terminal(
            [sys.executable, str(script), "--phase", "export"],
            title="BT Export — CSV + XLSX",
            cwd=PROJECT_ROOT,
        )
        return JSONResponse({"ok": True})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
