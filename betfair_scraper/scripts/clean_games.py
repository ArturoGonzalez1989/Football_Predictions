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
MATCH_DURATION_MINUTES = 105  # 90 min juego + 15 min tiempo añadido máximo
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
