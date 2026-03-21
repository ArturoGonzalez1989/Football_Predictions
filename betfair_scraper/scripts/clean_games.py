#!/usr/bin/env python3
"""
Script de limpieza de games.csv
Elimina partidos que han terminado (inicio + 120 minutos < ahora)
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

# Configuración
GAMES_CSV = Path(__file__).parent.parent / "games.csv"
MATCH_DURATION_MINUTES = 120  # 90 min juego + 30 min margen de seguridad
DATE_FORMATS = ["%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"]  # Formatos soportados


def parse_date(date_str):
    """Intenta parsear la fecha en múltiples formatos"""
    if not date_str or not date_str.strip():
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    print(f"⚠️  Formato de fecha no reconocido: {date_str}")
    return None


DATA_DIR = Path(__file__).parent.parent / "data"


def is_match_finished(start_time, url=""):
    """Verifica si un partido ha terminado: por CSV status o por tiempo transcurrido."""
    # Check 1: Look at the match CSV for actual status
    if url:
        match_id = url.rstrip("/").split("/")[-1]
        csv_candidates = list(DATA_DIR.glob(f"partido_{match_id[:50]}*"))
        if not csv_candidates:
            # Try shorter prefix
            csv_candidates = list(DATA_DIR.glob(f"partido_{match_id[:30]}*"))
        for csv_path in csv_candidates:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if not rows:
                        continue
                    # If any row has "finalizado" → match is done
                    if any(r.get("estado_partido", "").strip() == "finalizado" for r in rows):
                        return True
                    # If was live but reverted to pre_partido → match ended
                    was_live = any(r.get("estado_partido", "").strip() in ("en_juego", "descanso") for r in rows)
                    last_status = rows[-1].get("estado_partido", "").strip()
                    if was_live and last_status == "pre_partido":
                        return True
            except Exception:
                pass

    # Check 2: Fallback to time-based
    if start_time is None:
        return False

    ahora = datetime.now()
    fin_tracking = start_time + timedelta(minutes=MATCH_DURATION_MINUTES)
    return ahora > fin_tracking


def _sanitize_match_csv(url):
    """Sanitiza el CSV de un partido eliminado: trunca filas post-finalizado.

    Caso 1: Existe fila 'finalizado' → elimina todo lo posterior.
    Caso 2: No hay 'finalizado' pero hubo 'en_juego'/'descanso' y termina en
            'pre_partido' → marca última fila en_juego como finalizado y
            elimina las pre_partido trailing.
    """
    if not url:
        return
    match_id = url.rstrip("/").split("/")[-1]
    csv_candidates = list(DATA_DIR.glob(f"partido_{match_id[:50]}*"))
    if not csv_candidates:
        csv_candidates = list(DATA_DIR.glob(f"partido_{match_id[:30]}*"))
    if not csv_candidates:
        return

    csv_path = csv_candidates[0]
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return

    if len(lines) < 2:  # solo header o vacío
        return

    # Caso 1: buscar primer 'finalizado'
    first_final = -1
    for i, line in enumerate(lines):
        if i == 0:  # header
            continue
        if ",finalizado," in line:
            first_final = i
            break

    if first_final > 0 and first_final < len(lines) - 1:
        removed = len(lines) - (first_final + 1)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            f.writelines(lines[: first_final + 1])
        print(f"   [CSV] {csv_path.name}: {removed} filas post-finalizado eliminadas")
        return

    if first_final > 0:
        # finalizado es la última fila, nada que limpiar
        return

    # Caso 2: sin finalizado, pero was_live + trailing pre_partido
    last_live_idx = -1
    for i in range(len(lines) - 1, 0, -1):
        fields = lines[i].split(",")
        estado = fields[4].strip() if len(fields) > 4 else ""
        if estado in ("en_juego", "descanso"):
            last_live_idx = i
            break

    if last_live_idx == -1:
        return

    # Verificar que todo lo posterior son pre_partido
    all_trailing_pre = True
    for i in range(last_live_idx + 1, len(lines)):
        fields = lines[i].split(",")
        estado = fields[4].strip() if len(fields) > 4 else ""
        if estado != "pre_partido":
            all_trailing_pre = False
            break

    if not all_trailing_pre or last_live_idx == len(lines) - 1:
        return

    # Marcar última fila en_juego como finalizado y truncar
    lines[last_live_idx] = lines[last_live_idx].replace(",en_juego,", ",finalizado,").replace(",descanso,", ",finalizado,")
    removed = len(lines) - (last_live_idx + 1)
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        f.writelines(lines[: last_live_idx + 1])
    print(f"   [CSV] {csv_path.name}: estado→finalizado + {removed} filas pre_partido eliminadas")


def clean_games():
    """Limpia games.csv eliminando partidos terminados"""

    if not GAMES_CSV.exists():
        print(f"[ERROR] No se encuentra {GAMES_CSV}")
        return

    # Leer games.csv
    partidos = []
    with open(GAMES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        partidos = list(reader)

    if not partidos:
        print("[OK] games.csv está vacío")
        return

    # Clasificar partidos
    activos = []
    eliminados = []

    for partido in partidos:
        fecha_str = partido.get("fecha_hora_inicio", "").strip()

        # Si no tiene fecha, considerarlo activo (modo legacy)
        if not fecha_str:
            activos.append(partido)
            continue

        start_time = parse_date(fecha_str)
        if start_time is None:
            activos.append(partido)
            continue

        # Verificar si terminó (por CSV status o por tiempo)
        url = partido.get("url", "")
        if is_match_finished(start_time, url):
            eliminados.append(partido)
        else:
            activos.append(partido)

    # Sanitizar CSVs de partidos eliminados
    if eliminados:
        for p in eliminados:
            _sanitize_match_csv(p.get("url", ""))

    # Guardar si hay cambios
    if eliminados:
        with open(GAMES_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Game", "url", "fecha_hora_inicio"])
            writer.writeheader()
            writer.writerows(activos)

        print(f"\n[LIMPIEZA COMPLETADA]")
        print(f"   - Eliminados: {len(eliminados)} partidos")
        print(f"   - Activos: {len(activos)} partidos")
        print(f"\nPartidos eliminados:")
        for p in eliminados:
            print(f"   - {p['Game']} ({p['fecha_hora_inicio']})")
    else:
        print(f"[OK] Sin cambios - {len(activos)} partidos activos")


if __name__ == "__main__":
    clean_games()
