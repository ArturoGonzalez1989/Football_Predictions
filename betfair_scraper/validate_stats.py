#!/usr/bin/env python3
"""
Script para validar estadisticas disponibles vs capturadas
Verifica qué estadisticas estan en Betfair pero NO se capturaron
"""

import csv
import re
import sys
import io
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configurar encoding para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configuracion
GAMES_CSV = Path("games.csv")
DATA_DIR = Path("data")
HEADLESS = True
TIMEOUT = 10

# Estadisticas que buscamos (case-insensitive)
STATS_KEYWORDS = {
    "xg": ["xg", "expected goals", "expected goal"],
    "posesion": ["possession", "posesion", "posession"],
    "pases": ["pass", "passing"],
    "tiros": ["shot", "shooting"],
    "tiros_a_puerta": ["on target", "target"],
    "corners": ["corner", "esquina"],
    "faltas": ["foul", "fouls"],
    "tarjetas": ["card", "yellow", "red"],
    "fuera_de_juego": ["offside"],
    "salvadas": ["save", "saves"],
}


def setup_driver():
    """Configura el driver de Chrome"""
    options = webdriver.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return driver


def get_active_games():
    """Obtiene partidos activos de games.csv"""
    active_games = []

    if not GAMES_CSV.exists():
        return active_games

    try:
        with open(GAMES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            games = list(reader)

        now = datetime.now()
        for game in games:
            fecha_str = game.get("fecha_hora_inicio", "").strip()
            if not fecha_str:
                continue

            try:
                for fmt in ["%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"]:
                    try:
                        game_time = datetime.strptime(fecha_str, fmt)
                        # Consideramos "activo" si empezo hace menos de 150 min
                        diff = (now - game_time).total_seconds() / 60
                        if 0 <= diff <= 150:
                            active_games.append({
                                "name": game.get("Game"),
                                "url": game.get("url"),
                                "time": game_time
                            })
                        break
                    except ValueError:
                        continue
            except:
                pass

    except Exception as e:
        print(f"[ERROR] Error leyendo games.csv: {e}")

    return active_games


def extract_stats_from_page(url):
    """Accede a una URL y extrae las estadisticas visibles en la pagina"""
    available_stats = []
    driver = None

    try:
        driver = setup_driver()
        driver.get(url)

        # Esperar a que cargue
        import time
        time.sleep(3)

        # Obtener todo el texto visible (lowercase para búsqueda)
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        page_html = driver.page_source.lower()

        # Combinar texto y HTML para búsqueda más robusta
        combined_text = page_text + " " + page_html

        # Buscar estadisticas
        for stat_name, keywords in STATS_KEYWORDS.items():
            for keyword in keywords:
                # Búsqueda case-insensitive
                if keyword.lower() in combined_text:
                    available_stats.append(stat_name)
                    break  # Encontrado, pasar al siguiente stat

        return list(set(available_stats))  # Remover duplicados

    except Exception as e:
        print(f"[DEBUG] Error extrayendo stats de {url[:50]}...: {e}")
        return []

    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass


def get_captured_stats_for_game(game_id):
    """Obtiene las estadisticas capturadas para un partido"""
    captured_stats = set()

    # Buscar CSV del partido
    csv_files = list(DATA_DIR.glob(f"*{game_id}*.csv"))
    if not csv_files:
        return list(captured_stats)

    csv_file = csv_files[0]

    try:
        with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if rows:
            row = rows[-1]  # Ultima fila (más reciente)

            # Buscar cualquier campo que tenga valor y sea de estadísticas
            for col_name, col_value in row.items():
                col_value_str = str(col_value).strip()

                # Si la columna tiene un valor no vacío
                if col_value_str and col_value_str != "nan":
                    # Mapear nombre de columna a stat_name
                    col_lower = col_name.lower()

                    for stat_name in STATS_KEYWORDS.keys():
                        if stat_name in col_lower:
                            captured_stats.add(stat_name)
                            break

    except Exception as e:
        print(f"[DEBUG] Error leyendo CSV {csv_file.name}: {e}")

    return list(captured_stats)


def compare_stats(available, captured):
    """Compara estadisticas disponibles vs capturadas"""
    missing = set(available) - set(captured)
    return missing


def main():
    """Funcion principal"""
    print("\n" + "="*60)
    print("VALIDACION DE ESTADISTICAS")
    print("="*60)

    active_games = get_active_games()

    if not active_games:
        print("[INFO] Sin partidos activos en este momento")
        print("[OK] Sin verificaciones que hacer")
        return

    print(f"[INFO] Encontrados {len(active_games)} partidos activos")
    print("[INFO] Verificando estadisticas disponibles en Betfair...")
    print("")

    total_missing = {}
    games_checked = 0
    stats_gap_found = False

    for game in active_games[:3]:  # Verificar max 3 partidos
        print(f"[VERIFICANDO] {game['name']}...")

        # Extraer stats disponibles en Betfair
        available = extract_stats_from_page(game['url'])

        if not available:
            print(f"  -> Sin estadisticas detectadas en la pagina")
            continue

        # Extraer ID del partido de la URL
        match = re.search(r"apuestas-(\d+)", game['url'])
        if not match:
            continue

        game_id = match.group(1)

        # Obtener stats capturadas
        captured = get_captured_stats_for_game(game_id)

        # Comparar
        missing = compare_stats(available, captured)

        if missing:
            stats_gap_found = True
            avail_str = ', '.join(sorted(available)) if available else "(ninguna)"
            capt_str = ', '.join(sorted(captured)) if captured else "(ninguna)"
            miss_str = ', '.join(sorted(missing))
            print(f"  -> Disponibles en Betfair: {avail_str}")
            print(f"  -> Capturadas en CSV: {capt_str}")
            print(f"  -> BRECHA (no capturadas): {miss_str}")

            for stat in missing:
                total_missing[stat] = total_missing.get(stat, 0) + 1
        else:
            print(f"  -> OK: Todas las estadisticas disponibles se capturaron")

        games_checked += 1
        print("")

    # Resumen
    print("="*60)
    print("RESUMEN DE VALIDACION")
    print("="*60)
    print(f"Partidos verificados: {games_checked}")

    if stats_gap_found:
        print(f"\n[ALERTA] Brecha de datos detectada:")
        print("")
        for stat, count in sorted(total_missing.items(), key=lambda x: x[1], reverse=True):
            print(f"  * {stat.upper()}: No capturado en {count} partido(s)")

        print(f"\n[ACCION RECOMENDADA]")
        print(f"  1. Revisar selectores CSS en main.py")
        print(f"  2. Verificar que busquen en el lugar correcto")
        print(f"  3. Actualizar selectores si Betfair cambio estructura HTML")
        print(f"  4. Ejecutar validate_stats.py nuevamente para confirmar correccion")
    else:
        print(f"\n[OK] Validacion completada:")
        print(f"  - No se detectaron brechas")
        print(f"  - Las estadisticas disponibles se estan capturando")
        if games_checked == 0:
            print(f"  - (Sin partidos activos para verificar)")

    print("="*60 + "\n")


if __name__ == "__main__":
    main()
