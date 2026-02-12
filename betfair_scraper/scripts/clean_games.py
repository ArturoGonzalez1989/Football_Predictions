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
MATCH_DURATION_MINUTES = 120  # 90 min juego + 30 min margen
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


def is_match_finished(start_time):
    """Verifica si un partido ha terminado (inicio + MATCH_DURATION_MINUTES < ahora)"""
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

        # Verificar si terminó
        if is_match_finished(start_time):
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
