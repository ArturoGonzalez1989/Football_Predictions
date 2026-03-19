"""
fix_delete_inconsistent.py -- Elimina CSVs de partidos con inconsistencias home/away
irrecuperables (datos mixtos que no se pueden corregir con un swap global).

Criterio de eliminacion: >= 25% de filas decisivas invertidas Y >= 10 filas decisivas.
Estos archivos ensucian el backtest y no tienen solucion automatica.

Ejecuta primero el test de deteccion para ver la lista completa:
    python tests/test_home_away_consistency.py

Luego este script:
    python fixes/fix_delete_inconsistent.py              # elimina todos los detectados
    python fixes/fix_delete_inconsistent.py --dry-run    # muestra que eliminaria sin tocar nada
    python fixes/fix_delete_inconsistent.py partido_X.csv  # elimina solo ese archivo

SEGURIDAD: se crea un backup en backup/ antes de eliminar cada archivo.
"""

import sys
import csv
import io
import shutil
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT       = Path(__file__).resolve().parent.parent
DATA_DIR   = ROOT / "betfair_scraper" / "data"
BACKUP_DIR = ROOT / "backup"

MIN_DECISIVE_ROWS  = 3
DELETE_THRESHOLD   = 0.25
DELETE_MIN_ROWS    = 10


def _to_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def is_deletable(path: Path) -> tuple[bool, dict]:
    """Devuelve (deletable, stats) para un CSV."""
    ok = bad = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                gl = _to_float(row.get("goles_local"))
                gv = _to_float(row.get("goles_visitante"))
                bh = _to_float(row.get("back_home"))
                ba = _to_float(row.get("back_away"))
                if None in (gl, gv, bh, ba) or gl == gv:
                    continue
                if (gl > gv and bh > ba) or (gv > gl and ba > bh):
                    bad += 1
                else:
                    ok += 1
    except Exception as e:
        return False, {"error": str(e)}

    decisive = ok + bad
    if decisive < MIN_DECISIVE_ROWS:
        return False, {"decisive": decisive, "inverted": bad, "skipped": True}

    ratio = bad / decisive
    deletable = ratio >= DELETE_THRESHOLD and decisive >= DELETE_MIN_ROWS

    return deletable, {"decisive": decisive, "inverted": bad, "ratio": ratio}


def delete_csv(path: Path, dry_run: bool) -> bool:
    """
    Crea backup del CSV en backup/ y lo elimina del directorio de datos.
    """
    if dry_run:
        print(f"  [DRY-RUN] Se eliminaria: {path.name}")
        return True

    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(exist_ok=True)
    backup = BACKUP_DIR / f"{path.stem}.csv.bak_{ts}"

    try:
        shutil.copy2(path, backup)
        path.unlink()
        print(f"  [OK] Eliminado {path.name}  (backup: {backup.name})")
        return True
    except Exception as e:
        print(f"  [ERROR] {path.name}: {e}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv
    args    = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        targets = [DATA_DIR / a if not Path(a).is_absolute() else Path(a) for a in args]
        targets = [p if p.suffix == ".csv" else p.with_suffix(".csv") for p in targets]
    else:
        targets = sorted(DATA_DIR.glob("partido_*.csv"))

    if not targets:
        print("No se encontraron archivos CSV.")
        sys.exit(1)

    print(f"Analizando {len(targets)} archivo(s)...")
    if dry_run:
        print("Modo DRY-RUN: no se eliminara ningun archivo.\n")

    to_delete = []
    skipped   = 0

    for path in targets:
        if not path.exists():
            print(f"  [WARN] No existe: {path}")
            continue

        deletable, stats = is_deletable(path)
        if stats.get("skipped"):
            skipped += 1
            continue
        if deletable:
            to_delete.append((path, stats))

    if not to_delete:
        print(f"No se detectaron archivos con inconsistencias irrecuperables en {len(targets)} archivos.")
        sys.exit(0)

    print(f"\nArchivos con inconsistencias irrecuperables ({len(to_delete)}):")
    for path, stats in sorted(to_delete, key=lambda x: x[1]["ratio"], reverse=True):
        print(f"  {path.name}"
              f"  ({stats['inverted']}/{stats['decisive']}"
              f" = {stats['ratio']:.0%} filas inconsistentes)")

    print()
    deleted = sum(1 for path, _ in to_delete if delete_csv(path, dry_run))

    if not dry_run:
        print(f"\n{deleted}/{len(to_delete)} archivos eliminados.")
        print("Los backups se guardaron en backup/")
        print("Recuerda re-ejecutar bt_optimizer para recalcular el backtest con datos limpios.")
    else:
        print(f"\n{deleted}/{len(to_delete)} archivos se eliminarian al ejecutar sin --dry-run.")


if __name__ == "__main__":
    main()
