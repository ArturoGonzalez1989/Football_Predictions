"""
Anula las cuotas back_rc_* / lay_rc_* en filas in-play de todos los CSVs históricos.

Problema: el scraper capturaba cuotas RC de la página del evento (datos pre-partido
congelados) y las repetía en todas las filas in-play. Esto infla el BT de estrategias
CS porque usan cuotas pre-partido (~8-15) en lugar de las cuotas live reales (~1.5-4).

Solución: dejar las filas pre-partido intactas (cuotas RC genuinas) y poner a vacío
las filas in-play (minuto >= 1) para que los generadores CS no disparen en ellas.

Los partidos NO se borran. Solo se anulan las columnas RC comprometidas.
"""

import glob
import csv
import io
import os

DATA_DIR = "C:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/betfair_scraper/data"
RC_COLS = [
    "back_rc_0_0", "lay_rc_0_0",
    "back_rc_1_0", "lay_rc_1_0",
    "back_rc_0_1", "lay_rc_0_1",
    "back_rc_1_1", "lay_rc_1_1",
    "back_rc_2_0", "lay_rc_2_0",
    "back_rc_0_2", "lay_rc_0_2",
    "back_rc_2_1", "lay_rc_2_1",
    "back_rc_1_2", "lay_rc_1_2",
    "back_rc_2_2", "lay_rc_2_2",
    "back_rc_3_0", "lay_rc_3_0",
    "back_rc_0_3", "lay_rc_0_3",
    "back_rc_3_1", "lay_rc_3_1",
    "back_rc_1_3", "lay_rc_1_3",
    "back_rc_3_2", "lay_rc_3_2",
    "back_rc_2_3", "lay_rc_2_3",
]


def is_inplay(row: dict) -> bool:
    """Devuelve True si la fila es in-play (minuto >= 1)."""
    m = row.get("minuto", "").strip()
    if not m:
        return False
    try:
        return int(float(m)) >= 1
    except ValueError:
        return False


def rc_is_stale(rows: list, rc_col: str) -> bool:
    """
    Devuelve True si las cuotas RC in-play son idénticas a las pre-partido:
    indica datos congelados del scraper (no live).

    Comprobación: el valor RC en filas in-play debe ser el mismo que el
    valor RC pre-partido. Si difiere >20%, se considera dato live y NO se anula.
    """
    pre_vals = []
    inplay_vals = []
    for row in rows:
        v = row.get(rc_col, "").strip()
        if not v:
            continue
        try:
            fv = float(v)
        except ValueError:
            continue
        if is_inplay(row):
            inplay_vals.append(fv)
        else:
            pre_vals.append(fv)

    if not pre_vals or not inplay_vals:
        return True  # sin referencia, asumir stale por seguridad

    pre_median = sorted(pre_vals)[len(pre_vals) // 2]
    inplay_median = sorted(inplay_vals)[len(inplay_vals) // 2]

    if pre_median == 0:
        return True

    pct_change = abs(inplay_median - pre_median) / pre_median
    return pct_change < 0.20  # <20% de cambio = cuotas congeladas


def process_file(path: str) -> tuple[int, int]:
    """
    Procesa un CSV: anula RC en filas in-play.
    Devuelve (filas_total, filas_anuladas).
    """
    with open(path, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = reader.fieldnames or []
        rows = list(reader)

    # Detectar qué columnas RC existen en este CSV
    rc_present = [c for c in RC_COLS if c in headers]
    if not rc_present:
        return len(rows), 0

    # Verificar qué columnas RC tienen datos realmente congelados (stale)
    stale_cols = [c for c in rc_present if rc_is_stale(rows, c)]

    nullified = 0
    for row in rows:
        if is_inplay(row):
            for col in stale_cols:
                row[col] = ""
            if stale_cols:
                nullified += 1

    # Escribir de vuelta (mismo fichero, mismos headers)
    with open(path, encoding="utf-8", newline="") as fh:
        pass  # solo para verificar que existe antes de sobreescribir

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)

    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(buf.getvalue())

    return len(rows), nullified


def main():
    files = sorted(glob.glob(f"{DATA_DIR}/partido_*.csv"))
    print(f"CSVs encontrados: {len(files)}")
    print("Procesando...\n")

    total_files = 0
    total_rows = 0
    total_nullified = 0
    skipped = 0

    for path in files:
        try:
            n_rows, n_null = process_file(path)
            total_files += 1
            total_rows += n_rows
            total_nullified += n_null
        except Exception as e:
            print(f"  ERROR {os.path.basename(path)}: {e}")
            skipped += 1

    print(f"Procesados: {total_files} CSVs ({skipped} errores)")
    print(f"Filas totales:    {total_rows:,}")
    print(f"Filas anuladas:   {total_nullified:,} ({total_nullified/total_rows*100:.1f}%)")
    print(f"Filas pre-party:  {total_rows - total_nullified:,} (RC intacto)")
    print("\nListo. Los generadores CS no dispararán en partidos históricos comprometidos.")


if __name__ == "__main__":
    main()
