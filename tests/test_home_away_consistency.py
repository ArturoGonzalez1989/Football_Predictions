"""
test_home_away_consistency.py -- Detecta y clasifica CSVs de partidos con inconsistencias
entre odds HOME/AWAY y el marcador local/visitante.

Tres categorias de salida:

  FIXABLE  -- >70% de filas decisivas invertidas: el swap global mejora el archivo.
              Accion: python fixes/fix_home_away_swap.py

  DELETE   -- 25-70% invertidas con muestra suficiente (>=10 filas): datos mixtos
              irrecuperables que ensucian el backtest.
              Accion: python fixes/fix_delete_inconsistent.py

  BORDERLINE -- 15-25% invertidas, o >25% con muestra pequeña (<10 filas):
              dudosas, no se toman acciones automaticas.

Uso:
    python tests/test_home_away_consistency.py            # resumen
    python tests/test_home_away_consistency.py --verbose  # detalle por CSV
"""

import sys
import csv
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT     = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "betfair_scraper" / "data"

# Umbrales
MIN_DECISIVE_ROWS  = 3     # minimo de filas decisivas para evaluar
FIXABLE_THRESHOLD  = 0.70  # >= 70%  -> FIXABLE
DELETE_THRESHOLD   = 0.25  # >= 25% (con >=10 filas) -> DELETE
DELETE_MIN_ROWS    = 10    # minimo filas decisivas para marcar DELETE
BORDERLINE_LO      = 0.15  # >= 15% -> al menos BORDERLINE


def _to_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def analyze_csv(path: Path) -> dict:
    """
    Lee un CSV y devuelve:
      decisive    -- filas con marcador definido y ambas odds disponibles
      inverted    -- de esas, cuantas tienen odds inconsistentes con el marcador
      ratio       -- inverted / decisive
      category    -- "clean" | "borderline" | "delete" | "fixable" | "skip"
      examples    -- hasta 2 filas de ejemplo
    """
    ok = bad = 0
    examples = []

    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                gl = _to_float(row.get("goles_local"))
                gv = _to_float(row.get("goles_visitante"))
                bh = _to_float(row.get("back_home"))
                ba = _to_float(row.get("back_away"))

                if None in (gl, gv, bh, ba) or gl == gv:
                    continue

                is_inv = (gl > gv and bh > ba) or (gv > gl and ba > bh)
                if is_inv:
                    bad += 1
                    if len(examples) < 2:
                        examples.append({
                            "min":       row.get("minuto", "?"),
                            "score":     f"{int(gl)}-{int(gv)}",
                            "back_home": bh,
                            "back_away": ba,
                        })
                else:
                    ok += 1

    except Exception as e:
        return {"error": str(e), "decisive": 0, "inverted": 0,
                "ratio": 0.0, "category": "skip", "examples": []}

    decisive = ok + bad
    if decisive < MIN_DECISIVE_ROWS:
        return {"decisive": decisive, "inverted": bad, "ratio": 0.0,
                "category": "skip", "examples": []}

    ratio = bad / decisive

    if ratio >= FIXABLE_THRESHOLD:
        category = "fixable"
    elif ratio >= DELETE_THRESHOLD and decisive >= DELETE_MIN_ROWS:
        category = "delete"
    elif ratio >= BORDERLINE_LO:
        category = "borderline"
    else:
        category = "clean"

    return {
        "decisive":  decisive,
        "inverted":  bad,
        "ratio":     ratio,
        "category":  category,
        "examples":  examples,
    }


def main():
    verbose = "--verbose" in sys.argv

    csvs = sorted(DATA_DIR.glob("partido_*.csv"))
    if not csvs:
        print(f"No se encontraron CSVs en {DATA_DIR}")
        sys.exit(1)

    fixable    = []
    deletable  = []
    borderline = []
    skipped    = 0
    errors     = 0
    clean      = 0

    for path in csvs:
        result = analyze_csv(path)

        if "error" in result:
            errors += 1
            if verbose:
                print(f"  ERROR      {path.name}: {result['error']}")
            continue

        cat = result["category"]

        if cat == "skip":
            skipped += 1
        elif cat == "clean":
            clean += 1
            if verbose:
                print(f"  [clean]    {path.name}")
        elif cat == "fixable":
            fixable.append((path, result))
            if verbose:
                print(f"  [FIXABLE]  {path.name}"
                      f"  ({result['inverted']}/{result['decisive']}"
                      f" = {result['ratio']:.0%})")
        elif cat == "delete":
            deletable.append((path, result))
            if verbose:
                print(f"  [DELETE]   {path.name}"
                      f"  ({result['inverted']}/{result['decisive']}"
                      f" = {result['ratio']:.0%})")
                for ex in result["examples"]:
                    print(f"             min={ex['min']} score={ex['score']}"
                          f" back_home={ex['back_home']} back_away={ex['back_away']}")
        elif cat == "borderline":
            borderline.append((path, result))
            if verbose:
                print(f"  [border]   {path.name}"
                      f"  ({result['inverted']}/{result['decisive']}"
                      f" = {result['ratio']:.0%})")

    # -- Resumen ---------------------------------------------------------------
    total  = len(csvs)
    issues = len(fixable) + len(deletable)

    print(f"\nCSVs analizados  : {total}")
    print(f"  Limpios        : {clean}")
    print(f"  Sin datos      : {skipped}")
    print(f"  Borderline     : {len(borderline)}  (15-25% inconsistencia o muestra pequenya)")
    print(f"  FIXABLE        : {len(fixable)}  (>70% invertidas -- swap global posible)")
    print(f"  DELETE         : {len(deletable)}  (25-70% invertidas, >=10 filas -- irrecuperables)")

    if fixable:
        print(f"\n[FIXABLE] Archivos corregibles por swap ({len(fixable)}):")
        for path, r in fixable:
            print(f"  {path.name}"
                  f"  ({r['inverted']}/{r['decisive']} = {r['ratio']:.0%})")
        print("\n  -> Ejecuta: python fixes/fix_home_away_swap.py")

    if deletable:
        print(f"\n[DELETE] Archivos con datos insalvables ({len(deletable)}):")
        for path, r in sorted(deletable, key=lambda x: x[1]["ratio"], reverse=True):
            print(f"  {path.name}"
                  f"  ({r['inverted']}/{r['decisive']} = {r['ratio']:.0%})")
        print("\n  -> Ejecuta: python fixes/fix_delete_inconsistent.py")

    if borderline and verbose:
        print(f"\n[BORDERLINE] Archivos con inconsistencia leve ({len(borderline)}):")
        for path, r in sorted(borderline, key=lambda x: x[1]["ratio"], reverse=True):
            print(f"  {path.name}"
                  f"  ({r['inverted']}/{r['decisive']} = {r['ratio']:.0%})")

    # -- Resultado del test ----------------------------------------------------
    # El test FALLA si hay FIXABLE o DELETE (requieren accion)
    passed = clean + skipped
    failed = issues
    print(f"\nResultados: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
