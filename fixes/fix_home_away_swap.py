"""
fix_home_away_swap.py -- Corrige CSVs de partidos donde las odds HOME/AWAY estan
invertidas respecto al orden URL local/visitante.

Ejecuta primero el test de deteccion:
    python tests/test_home_away_consistency.py

Luego este script sobre los archivos afectados:
    python fixes/fix_home_away_swap.py                   # corrije todos los detectados
    python fixes/fix_home_away_swap.py --dry-run         # muestra que cambiaria sin tocar nada
    python fixes/fix_home_away_swap.py partido_X.csv     # corrije solo ese archivo

Columnas que se intercambian en cada fila:
    back_home  <-> back_away
    lay_home   <-> lay_away
    back_rc_1_0 <-> back_rc_0_1    (y sus equivalentes lay_)
    back_rc_2_0 <-> back_rc_0_2
    back_rc_2_1 <-> back_rc_1_2
    back_rc_3_0 <-> back_rc_0_3
    back_rc_3_1 <-> back_rc_1_3
    back_rc_3_2 <-> back_rc_2_3

Nota: goles_local/goles_visitante y las estadisticas (_local/_visitante) NO se tocan.
Reflejan lo que ocurrio en el partido segun el orden URL, que es correcto.
Lo unico incorrecto son las odds de mercado HOME/AWAY de Betfair.

SEGURIDAD: se crea un backup .bak antes de modificar cada archivo.
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

MIN_DECISIVE_ROWS   = 3
INVERSION_THRESHOLD = 0.70

# Pares de columnas a intercambiar (RC asimetricos -- home-score != away-score)
RC_SWAP_PAIRS = [
    ("1_0", "0_1"),
    ("2_0", "0_2"),
    ("2_1", "1_2"),
    ("3_0", "0_3"),
    ("3_1", "1_3"),
    ("3_2", "2_3"),
]


def _build_swap_map() -> dict:
    m = {
        "back_home": "back_away",
        "back_away": "back_home",
        "lay_home":  "lay_away",
        "lay_away":  "lay_home",
    }
    for a, b in RC_SWAP_PAIRS:
        for prefix in ("back_rc_", "lay_rc_"):
            m[f"{prefix}{a}"] = f"{prefix}{b}"
            m[f"{prefix}{b}"] = f"{prefix}{a}"
    return m

SWAP_MAP = _build_swap_map()


def _to_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def is_reversed(path: Path) -> tuple[bool, dict]:
    """Devuelve (reversed, stats) para un CSV."""
    decisive = inverted = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                gl = _to_float(row.get("goles_local"))
                gv = _to_float(row.get("goles_visitante"))
                bh = _to_float(row.get("back_home"))
                ba = _to_float(row.get("back_away"))
                if None in (gl, gv, bh, ba) or gl == gv:
                    continue
                decisive += 1
                if (gl > gv and bh > ba) or (gv > gl and ba > bh):
                    inverted += 1
    except Exception as e:
        return False, {"error": str(e)}

    if decisive < MIN_DECISIVE_ROWS:
        return False, {"decisive": decisive, "inverted": inverted, "skipped": True}

    ratio = inverted / decisive
    return ratio >= INVERSION_THRESHOLD, {"decisive": decisive, "inverted": inverted, "ratio": ratio}


def apply_swap(path: Path, dry_run: bool) -> bool:
    """
    Intercambia las columnas home/away en el CSV.
    Crea backup .bak_TIMESTAMP antes de escribir.
    """
    if dry_run:
        print(f"  [DRY-RUN] Se intercambiarian columnas en: {path.name}")
        return True

    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(exist_ok=True)
    backup = BACKUP_DIR / f"{path.stem}.csv.bak_{ts}"

    try:
        shutil.copy2(path, backup)

        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            reader     = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows       = list(reader)

        fixed = []
        for row in rows:
            snapshot = dict(row)
            new_row  = dict(row)
            for src, dst in SWAP_MAP.items():
                if src in snapshot and dst in snapshot:
                    new_row[src] = snapshot[dst]
            fixed.append(new_row)

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(fixed)

        print(f"  [OK] {path.name}  (backup: {backup.name})")
        return True

    except Exception as e:
        print(f"  [ERROR] {path.name}: {e}")
        if backup.exists():
            shutil.copy2(backup, path)
            print(f"         Backup restaurado.")
        return False


def main():
    dry_run    = "--dry-run" in sys.argv
    args       = [a for a in sys.argv[1:] if not a.startswith("--")]

    # Archivos objetivo: los pasados por argumento o todos los del data dir
    if args:
        targets = [DATA_DIR / a if not Path(a).is_absolute() else Path(a) for a in args]
        targets = [p if p.suffix == ".csv" else p.with_suffix(".csv") for p in targets]
    else:
        targets = sorted(DATA_DIR.glob("partido_*.csv"))

    if not targets:
        print("No se encontraron archivos CSV.")
        sys.exit(1)

    print(f"Analizando {len(targets)} archivo(s)…")
    if dry_run:
        print("Modo DRY-RUN: no se modificara ningun archivo.\n")

    to_fix     = []
    skipped    = 0

    for path in targets:
        if not path.exists():
            print(f"  [WARN] No existe: {path}")
            continue

        rev, stats = is_reversed(path)
        if stats.get("skipped"):
            skipped += 1
            continue
        if rev:
            to_fix.append((path, stats))

    if not to_fix:
        print(f"No se detectaron inversiones en {len(targets)} archivos. Nada que corregir.")
        sys.exit(0)

    print(f"\nArchivos con inversion detectada ({len(to_fix)}):")
    for path, stats in to_fix:
        print(f"  {path.name}"
              f"  ({stats['inverted']}/{stats['decisive']}"
              f" = {stats['ratio']:.0%} filas invertidas)")

    print()
    fixed = sum(1 for path, _ in to_fix if apply_swap(path, dry_run))

    if not dry_run:
        print(f"\n{fixed}/{len(to_fix)} archivos corregidos.")
        print("Recuerda re-ejecutar bt_optimizer para recalcular el backtest con datos limpios.")
    else:
        print(f"\n{fixed}/{len(to_fix)} archivos se corregiran al ejecutar sin --dry-run.")


if __name__ == "__main__":
    main()
