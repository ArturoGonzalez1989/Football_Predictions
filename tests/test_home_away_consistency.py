"""
test_home_away_consistency.py — Detecta y opcionalmente corrige CSVs de partidos
donde el orden URL (local/visitante) NO coincide con la designación Betfair HOME/AWAY.

Síntoma:  back_home > back_away cuando goles_local > goles_visitante
          (el equipo que va ganando tiene cuota más alta que el perdedor — imposible en mercado líquido)

Causa:    El scraper construye la URL en un orden, pero Betfair asigna HOME/AWAY
          de forma independiente. En algunos mercados (MLS, torneos neutrales, etc.)
          el equipo URL-first es el Betfair AWAY.

Fix:      Intercambiar los pares de columnas afectados en todo el archivo CSV:
          - back_home  ↔  back_away
          - lay_home   ↔  lay_away
          - back_rc_X_Y ↔ back_rc_Y_X  (para todos los RC no simétricos)
          - lay_rc_X_Y  ↔ lay_rc_Y_X

Uso:
    python tests/test_home_away_consistency.py            # solo detecta
    python tests/test_home_away_consistency.py --fix      # detecta y corrige
    python tests/test_home_away_consistency.py --verbose  # muestra detalle por CSV
"""

import sys
import csv
import shutil
from pathlib import Path
from datetime import datetime

ROOT      = Path(__file__).resolve().parent.parent
DATA_DIR  = ROOT / "betfair_scraper" / "data"

# ── Configuración de detección ────────────────────────────────────────────────
MIN_DECISIVE_ROWS = 3      # Mínimo de filas con marcador definido para evaluar
INVERSION_THRESHOLD = 0.70 # Si >70% de las filas decisivas tienen odds invertidas → flag

# ── Pares de columnas a intercambiar ─────────────────────────────────────────
# Pares simétricos (1-0 ↔ 0-1, 2-0 ↔ 0-2, etc.) — scores donde home≠away
RC_SWAP_PAIRS = [
    ("1_0", "0_1"),
    ("2_0", "0_2"),
    ("2_1", "1_2"),
    ("3_0", "0_3"),
    ("3_1", "1_3"),
    ("3_2", "2_3"),
]

def _build_swap_map() -> dict:
    """Construye el mapping completo de columnas a intercambiar."""
    m = {
        "back_home": "back_away",
        "back_away": "back_home",
        "lay_home":  "lay_away",
        "lay_away":  "lay_home",
    }
    for a, b in RC_SWAP_PAIRS:
        for prefix in ("back_rc_", "lay_rc_"):
            col_a = f"{prefix}{a}"
            col_b = f"{prefix}{b}"
            m[col_a] = col_b
            m[col_b] = col_a
    return m

SWAP_MAP = _build_swap_map()


def _to_float(val: str):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def analyze_csv(path: Path) -> dict:
    """
    Analiza un CSV de partido y devuelve:
      {
        "decisive": int,      # filas con marcador definido y odds disponibles
        "inverted": int,      # de esas, cuántas tienen odds invertidas
        "ratio": float,       # inverted / decisive
        "is_reversed": bool,  # True si ratio > INVERSION_THRESHOLD
        "examples": list,     # hasta 3 filas de ejemplo
      }
    """
    decisive = 0
    inverted = 0
    examples = []

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                gl = _to_float(row.get("goles_local", ""))
                gv = _to_float(row.get("goles_visitante", ""))
                bh = _to_float(row.get("back_home", ""))
                ba = _to_float(row.get("back_away", ""))

                if gl is None or gv is None or bh is None or ba is None:
                    continue
                if gl == gv:
                    continue  # empate: no podemos determinar dirección

                decisive += 1
                min_ = row.get("minuto", "?")

                # Inversión: el equipo ganador tiene cuotas MÁS ALTAS que el perdedor
                # (en un mercado normal, el líder siempre tiene odds menores)
                is_inv = (gl > gv and bh > ba) or (gv > gl and ba > bh)
                if is_inv:
                    inverted += 1
                    if len(examples) < 3:
                        examples.append({
                            "min": min_,
                            "score": f"{int(gl)}-{int(gv)}",
                            "back_home": bh,
                            "back_away": ba,
                        })
    except Exception as e:
        return {"error": str(e), "decisive": 0, "inverted": 0, "ratio": 0.0,
                "is_reversed": False, "examples": []}

    if decisive < MIN_DECISIVE_ROWS:
        return {"decisive": decisive, "inverted": inverted, "ratio": 0.0,
                "is_reversed": False, "examples": []}

    ratio = inverted / decisive
    return {
        "decisive": decisive,
        "inverted": inverted,
        "ratio": ratio,
        "is_reversed": ratio >= INVERSION_THRESHOLD,
        "examples": examples,
    }


def fix_csv(path: Path) -> bool:
    """
    Intercambia las columnas home/away en el CSV. Hace backup antes de escribir.
    Devuelve True si tuvo éxito.
    """
    backup = path.with_suffix(f".csv.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    try:
        shutil.copy2(path, backup)

        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        # Aplicar swap en cada fila
        fixed_rows = []
        for row in rows:
            new_row = dict(row)
            for col_src, col_dst in SWAP_MAP.items():
                if col_src in row and col_dst in row:
                    # Solo intercambiamos una vez por par (el bucle cubre ambas direcciones)
                    pass  # handled below via snapshot
            # Snapshot para hacer el swap sin side-effects
            snapshot = dict(row)
            for col_src, col_dst in SWAP_MAP.items():
                if col_src in snapshot and col_dst in snapshot:
                    new_row[col_src] = snapshot[col_dst]
            fixed_rows.append(new_row)

        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(fixed_rows)

        return True
    except Exception as e:
        print(f"    ERROR al corregir {path.name}: {e}")
        # Restaurar backup si algo falló
        if backup.exists():
            shutil.copy2(backup, path)
        return False


def main():
    fix_mode = "--fix" in sys.argv
    verbose  = "--verbose" in sys.argv

    csvs = sorted(DATA_DIR.glob("partido_*.csv"))
    if not csvs:
        print(f"No se encontraron CSVs en {DATA_DIR}")
        sys.exit(1)

    reversed_files = []
    skipped = 0
    errors  = 0

    for path in csvs:
        result = analyze_csv(path)

        if "error" in result:
            errors += 1
            if verbose:
                print(f"  ERROR  {path.name}: {result['error']}")
            continue

        if result["decisive"] < MIN_DECISIVE_ROWS:
            skipped += 1
            continue

        if result["is_reversed"]:
            reversed_files.append((path, result))

        if verbose and result["decisive"] > 0:
            flag = "⚠ INVERTIDO" if result["is_reversed"] else "✓"
            print(f"  {flag}  {path.name}  "
                  f"({result['inverted']}/{result['decisive']} = {result['ratio']:.0%} invertidas)")
            if result["is_reversed"] and result["examples"]:
                for ex in result["examples"]:
                    print(f"         min={ex['min']} score={ex['score']} "
                          f"back_home={ex['back_home']} back_away={ex['back_away']}")

    # ── Resumen ───────────────────────────────────────────────────────────────
    total = len(csvs)
    print(f"\nCSVs analizados : {total}")
    print(f"Sin datos suficientes: {skipped}")
    print(f"Con errores de lectura: {errors}")
    print(f"Con inversión HOME/AWAY detectada: {len(reversed_files)}")

    if reversed_files:
        print("\nArchivos con odds HOME/AWAY invertidas:")
        for path, result in reversed_files:
            print(f"  ⚠  {path.name}  "
                  f"({result['inverted']}/{result['decisive']} = {result['ratio']:.0%})")
            if result["examples"]:
                ex = result["examples"][0]
                print(f"     Ej. min={ex['min']} score={ex['score']} "
                      f"back_home={ex['back_home']} back_away={ex['back_away']}")

    # ── Fix ───────────────────────────────────────────────────────────────────
    if fix_mode and reversed_files:
        print(f"\nAplicando fix (swap back_home↔back_away + RC simétricos) en "
              f"{len(reversed_files)} archivo(s)…")
        fixed = 0
        for path, result in reversed_files:
            ok = fix_csv(path)
            status = "✓ corregido" if ok else "✗ error"
            print(f"  {status}  {path.name}")
            if ok:
                fixed += 1
        print(f"\n{fixed}/{len(reversed_files)} archivos corregidos.")
        print("Backup de cada archivo guardado junto al original (.csv.bak_*).")
    elif fix_mode and not reversed_files:
        print("\nNo hay archivos que corregir.")
    elif not fix_mode and reversed_files:
        print("\nEjecuta con --fix para aplicar la corrección automáticamente.")

    # ── Resultado del test ────────────────────────────────────────────────────
    passed = total - len(reversed_files) - skipped - errors
    failed = len(reversed_files)
    print(f"\nResultados: {passed} passed, {failed} failed")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
