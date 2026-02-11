#!/usr/bin/env python3
"""
Script para verificar URLs y eliminar partidos con errores 404
Busca en el log del scraper errores de URL inválida
y elimina esos partidos de games.csv
"""

import csv
import re
from pathlib import Path
from datetime import datetime, timedelta

# Configuración
GAMES_CSV = Path("games.csv")
LOGS_DIR = Path("logs")
ERROR_PATTERNS = [
    r"404|no se ha encontrado|not found|URL inválida|invalid url",
    r"partido.*error|error.*partido",
    r"unable to locate element|no such element|stale element"
]


def get_latest_log():
    """Obtiene el log más reciente del scraper"""
    if not LOGS_DIR.exists():
        print("[WARNING] Directorio logs no existe")
        return None

    log_files = sorted(LOGS_DIR.glob("scraper_*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
    return log_files[0] if log_files else None


def extract_partido_id(text):
    """Extrae el ID del partido de una línea de log"""
    # Patrón: apuestas-XXXXX (números al final)
    match = re.search(r"apuestas-(\d+)", text)
    if match:
        return match.group(1)

    # Patrón: [nombre-partido-apuestas-id]
    match = re.search(r"\[([^\]]*apuestas-\d+[^\]]*)\]", text)
    if match:
        return match.group(1)

    return None


def find_404_errors(log_file):
    """Busca errores 404 en el log y extrae los partidos afectados"""
    problematic_parties = set()

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        # Buscar últimas 1000 líneas (últimas ~30-60 min de ejecución)
        recent_lines = lines[-1000:] if len(lines) > 1000 else lines

        for line in recent_lines:
            # Buscar patrones de error
            for pattern in ERROR_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    # Extraer ID del partido
                    partido_id = extract_partido_id(line)
                    if partido_id:
                        problematic_parties.add(partido_id)

                    # También extraer nombre si está disponible
                    name_match = re.search(r"\[([a-z0-9\-]+)\]", line)
                    if name_match:
                        problematic_parties.add(name_match.group(1))

        return problematic_parties

    except Exception as e:
        print(f"[ERROR] Error leyendo log: {e}")
        return set()


def remove_problematic_games(problematic_ids):
    """Elimina partidos problemáticos de games.csv"""
    if not problematic_ids:
        print("[OK] Sin errores 404 detectados")
        return 0

    if not GAMES_CSV.exists():
        print(f"[ERROR] No se encuentra {GAMES_CSV}")
        return 0

    # Leer games.csv
    games = []
    try:
        with open(GAMES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            games = list(reader)
    except Exception as e:
        print(f"[ERROR] Error leyendo games.csv: {e}")
        return 0

    # Identificar juegos a eliminar
    games_to_remove = []
    games_to_keep = []

    for game in games:
        game_name = game.get("Game", "").lower()
        url = game.get("url", "").lower()

        # Verificar si este juego está en la lista de problemáticos
        is_problematic = False
        for prob_id in problematic_ids:
            if prob_id.lower() in game_name or prob_id.lower() in url:
                is_problematic = True
                break

        if is_problematic:
            games_to_remove.append(game)
        else:
            games_to_keep.append(game)

    # Guardar si hay cambios
    if games_to_remove:
        try:
            with open(GAMES_CSV, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["Game", "url", "fecha_hora_inicio"])
                writer.writeheader()
                writer.writerows(games_to_keep)

            print(f"\n[VERIFICACION COMPLETADA]")
            print(f"   - Eliminados: {len(games_to_remove)} partidos con error")
            print(f"   - Activos: {len(games_to_keep)} partidos")
            print(f"\nPartidos eliminados:")
            for game in games_to_remove:
                print(f"   - {game['Game']}")

            return len(games_to_remove)

        except Exception as e:
            print(f"[ERROR] Error guardando games.csv: {e}")
            return 0
    else:
        print(f"[OK] Sin cambios - {len(games_to_keep)} partidos activos")
        return 0


def generate_report(removed_count):
    """Genera un pequeño reporte de la verificación"""
    print("\n[REPORTE DE URLS]")
    if removed_count > 0:
        print(f"   - Problemas detectados: SI")
        print(f"   - Partidos eliminados: {removed_count}")
        print(f"   - Acción: Automática (sin intervención)")
    else:
        print(f"   - Problemas detectados: NO")
        print(f"   - Todos los URLs están válidos")


def main():
    """Función principal"""
    print("\n" + "="*60)
    print("VERIFICACION DE URLs (404s)")
    print("="*60)

    # Obtener log más reciente
    log_file = get_latest_log()
    if not log_file:
        print("[WARNING] No se encontró log del scraper")
        print("[OK] Sin cambios")
        return 0

    print(f"[INFO] Analizando: {log_file.name}")

    # Buscar errores
    problematic_ids = find_404_errors(log_file)

    if problematic_ids:
        print(f"[INFO] Encontrados {len(problematic_ids)} partidos con error:")
        for pid in list(problematic_ids)[:5]:  # Mostrar max 5
            print(f"   - {pid}")
        if len(problematic_ids) > 5:
            print(f"   ... y {len(problematic_ids) - 5} más")

    # Eliminar juegos problemáticos
    removed_count = remove_problematic_games(problematic_ids)

    # Generar reporte
    generate_report(removed_count)

    print("="*60 + "\n")

    return removed_count


if __name__ == "__main__":
    main()
