#!/usr/bin/env python3
"""
Script de búsqueda de partidos en Betfair
Busca en el exchange todos los partidos in-play y próximos
y los añade automáticamente a games.csv
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configuración
BETFAIR_INPLAY_URL = "https://www.betfair.es/exchange/plus/inplay"
GAMES_CSV = Path(__file__).parent.parent / "games.csv"  # Ruta al games.csv del proyecto
HEADLESS = True  # Chrome sin GUI
TIMEOUT = 10  # Segundos para esperar elementos


def setup_driver():
    """Configura e inicializa el driver de Chrome"""
    options = webdriver.ChromeOptions()

    if HEADLESS:
        options.add_argument("--headless")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    return driver


def find_matches_on_betfair():
    """
    Accede a Betfair, busca todos los partidos in-play y futuros
    Retorna lista de dicts: {name, url, start_time}
    """
    driver = None
    matches = []

    try:
        print("[INFO] Iniciando búsqueda de partidos en Betfair...")
        driver = setup_driver()

        # Navegar a Betfair
        print(f"[INFO] Accediendo a: {BETFAIR_INPLAY_URL}")
        driver.get(BETFAIR_INPLAY_URL)

        # Esperar a que cargue contenido dinámico
        print("[INFO] Esperando carga de contenido...")
        time.sleep(5)

        # Extraer partidos de fútbol
        matches = extract_football_matches(driver)

        if matches:
            print(f"[OK] Encontrados {len(matches)} partidos:")
            for match in matches:
                print(f"   - {match['name']} ({match['start_time']})")
        else:
            print("[INFO] No hay partidos de fútbol disponibles en este momento")

        return matches

    except Exception as e:
        print(f"[ERROR] Error buscando partidos: {e}")
        return []

    finally:
        if driver:
            driver.quit()


def extract_football_matches(driver):
    """
    Parsea la página de Betfair y extrae todos los partidos de fútbol
    Retorna lista de dicts con: name, url, start_time
    """
    matches = []

    try:
        # Esperar a que carguen los partidos
        # Betfair estructura: Cada partido está en un <ul class="runners">
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "ul.runners"))
        )

        # Obtener todos los elementos que contienen partidos
        runner_uls = driver.find_elements(By.CSS_SELECTOR, "ul.runners")

        print(f"[DEBUG] Encontrados {len(runner_uls)} partidos de fútbol")

        for ul in runner_uls:
            try:
                # Obtener nombres de equipos (están en <li class="name">)
                team_elements = ul.find_elements(By.CSS_SELECTOR, "li.name")
                team_names = [team.text.strip() for team in team_elements if team.text.strip()]

                # Validar que haya exactamente 2 equipos
                if len(team_names) != 2:
                    continue

                # Construir nombre del partido
                match_name = f"{team_names[0]} - {team_names[1]}"

                # Buscar el enlace del partido en la fila
                parent_row = ul.find_element(By.XPATH, "./ancestor::tr")
                match_link = parent_row.find_element(By.CSS_SELECTOR, "a.mod-link")

                href = match_link.get_attribute("href")
                if not href:
                    continue

                # FILTRO: Solo partidos de fútbol
                # Las URLs de fútbol contienen '/fútbol/' o '/futbol/' (puede estar URL encoded como f%C3%BAtbol)
                href_lower = href.lower()
                if not ("/futbol/" in href_lower or "/f%c3%batbol/" in href_lower):
                    continue

                # Extraer hora de inicio
                start_time = extract_start_time(parent_row, match_name)

                # Construir URL completa si es necesario
                if not href.startswith("http"):
                    href = "https://www.betfair.es" + href

                matches.append({
                    "name": match_name,
                    "url": href,
                    "start_time": start_time
                })

            except Exception as e:
                print(f"[DEBUG] Error extrayendo partido individual: {e}")
                continue

        # Eliminar duplicados por nombre
        seen = set()
        unique_matches = []
        for match in matches:
            if match["name"] not in seen:
                seen.add(match["name"])
                unique_matches.append(match)

        return unique_matches

    except TimeoutException:
        print("[WARNING] Timeout esperando elementos de partidos")
        return []
    except Exception as e:
        print(f"[ERROR] Error extrayendo partidos: {e}")
        return []


def extract_start_time(element, match_name):
    """
    Extrae la hora de inicio del partido
    Formatos esperados:
    - "Comienza en 5'" → hora actual + 5 minutos
    - "Hoy 18:30" → hoy a las 18:30
    - "DESC." o marcador → en juego (usar hora actual - 30 min)
    - Sin hora visible → usar hora actual - 30 min (aproximación)
    """
    try:
        # Obtener todo el texto del elemento
        full_text = element.text

        # Buscar patrón "Comienza en X'"
        match_in = re.search(r"Comienza en (\d+)'", full_text)
        if match_in:
            minutes = int(match_in.group(1))
            start_time = datetime.now() + timedelta(minutes=minutes)
            return start_time.strftime("%Y-%m-%d %H:%M")

        # Buscar patrón "Hoy HH:MM"
        match_time = re.search(r"Hoy\s+(\d{1,2}):(\d{2})", full_text)
        if match_time:
            hour = int(match_time.group(1))
            minute = int(match_time.group(2))
            start_time = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            return start_time.strftime("%Y-%m-%d %H:%M")

        # Si tiene "DESC." o marcador (números), está en juego
        if "DESC." in full_text or re.search(r"\d+-\d+", full_text):
            # En juego: aproximar a hace 30 minutos (para estar en ventana de tracking)
            start_time = datetime.now() - timedelta(minutes=30)
            return start_time.strftime("%Y-%m-%d %H:%M")

        # Por defecto: usar hora actual - 30 min (en juego aproximado)
        start_time = datetime.now() - timedelta(minutes=30)
        return start_time.strftime("%Y-%m-%d %H:%M")

    except Exception as e:
        print(f"[DEBUG] Error extrayendo hora: {e}")
        # Valor por defecto: hace 30 minutos
        start_time = datetime.now() - timedelta(minutes=30)
        return start_time.strftime("%Y-%m-%d %H:%M")


def add_new_matches_to_csv(discovered_matches):
    """
    Lee games.csv, compara con partidos descubiertos
    Añade solo los nuevos, mantiene los existentes
    """

    if not discovered_matches:
        print("[OK] Sin partidos nuevos para añadir")
        return 0

    # Leer games.csv actual
    existing_games = {}
    if GAMES_CSV.exists():
        try:
            with open(GAMES_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row and row.get("Game"):
                        existing_games[row["Game"]] = row
        except Exception as e:
            print(f"[WARNING] Error leyendo games.csv: {e}")

    # Identificar nuevos partidos
    added = 0
    for match in discovered_matches:
        game_name = match["name"]

        if game_name not in existing_games:
            # Nuevo partido
            existing_games[game_name] = {
                "Game": game_name,
                "url": match["url"],
                "fecha_hora_inicio": match["start_time"]
            }
            added += 1
            print(f"   + {game_name} ({match['start_time']})")

    # Guardar si hay cambios
    if added > 0:
        try:
            with open(GAMES_CSV, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["Game", "url", "fecha_hora_inicio"])
                writer.writeheader()
                writer.writerows(existing_games.values())

            print(f"\n[BUSQUEDA COMPLETADA]")
            print(f"   - Añadidos: {added} partidos nuevos")
            print(f"   - Total en games.csv: {len(existing_games)} partidos")

        except Exception as e:
            print(f"[ERROR] Error guardando games.csv: {e}")
            return 0
    else:
        print(f"[OK] Sin cambios - {len(existing_games)} partidos en games.csv")

    return added


def main():
    """Función principal"""
    print("\n" + "="*60)
    print("BÚSQUEDA DE PARTIDOS EN BETFAIR")
    print("="*60)

    # Buscar partidos
    matches = find_matches_on_betfair()

    # Añadir a games.csv
    added = add_new_matches_to_csv(matches)

    print("="*60 + "\n")

    return added


if __name__ == "__main__":
    main()
