#!/usr/bin/env python3
"""
main.py - Observador local de cuotas Betfair Exchange (multi-pestaña)
=====================================================================
Abre múltiples pestañas en Chrome con partidos de Betfair.es,
captura cuotas back/lay cada 60 segundos y guarda en CSV.

Uso:
    python main.py
    python main.py --urls URL1 URL2 URL3
    python main.py --ciclo 90 --login-wait 120

Detener: Ctrl+C (guarda datos pendientes antes de cerrar).
"""

import argparse
import csv
import logging
import os
import re
import signal
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from random import uniform

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
    ElementNotInteractableException,
)

try:
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    ChromeDriverManager = None

from config import (
    MATCH_URLS,
    CICLO_TOTAL_SEG,
    DELAY_MIN_SEG,
    DELAY_MAX_SEG,
    TIMEOUT_ELEMENTO_SEG,
    PAUSA_LOGIN_SEG,
    OUTPUT_DIR,
    HEADLESS,
    USER_AGENT,
    CHROME_LANG,
    SELECTORES,
    SELECTORES_ALT,
    USE_CHROME_PROFILE,
    CHROME_PROFILE_PATH,
    CHROME_PROFILE_NAME,
)

# ── Logging ─────────────────────────────────────────────────────────────────
# Crear carpeta de logs si no existe
Path("logs").mkdir(exist_ok=True)

# Configurar logging con salida a consola y archivo
log = logging.getLogger("betfair_scraper")
log.setLevel(logging.DEBUG)

# Formato
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)

# Handler para consola
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

# Handler para archivo (con timestamp en el nombre)
log_filename = f"logs/scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
file_handler = logging.FileHandler(log_filename, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Añadir handlers
log.addHandler(console_handler)
log.addHandler(file_handler)

log.info(f"📝 Log guardándose en: {log_filename}")

# ── Variables globales de control ────────────────────────────────────────────
ejecutando = True


def signal_handler(sig, frame):
    """Maneja Ctrl+C para cierre limpio."""
    global ejecutando
    log.info("Señal de parada recibida. Finalizando ciclo actual...")
    ejecutando = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# ── Columnas CSV ─────────────────────────────────────────────────────────────
CSV_COLUMNS = [
    "tab_id",
    "timestamp_utc",
    "evento",
    "hora_comienzo",
    "estado_partido",
    "minuto",
    "goles_local",
    "goles_visitante",
    # Match Odds
    "back_home",
    "lay_home",
    "back_draw",
    "lay_draw",
    "back_away",
    "lay_away",
    # Over/Under 0.5
    "back_over05",
    "lay_over05",
    "back_under05",
    "lay_under05",
    # Over/Under 1.5
    "back_over15",
    "lay_over15",
    "back_under15",
    "lay_under15",
    # Over/Under 2.5
    "back_over25",
    "lay_over25",
    "back_under25",
    "lay_under25",
    # Over/Under 3.5
    "back_over35",
    "lay_over35",
    "back_under35",
    "lay_under35",
    # Over/Under 4.5
    "back_over45",
    "lay_over45",
    "back_under45",
    "lay_under45",
    # Resultado Correcto
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
    # Estadísticas del partido
    "xg_local",
    "xg_visitante",
    "opta_points_local",
    "opta_points_visitante",
    "posesion_local",
    "posesion_visitante",
    "tiros_local",
    "tiros_visitante",
    "tiros_puerta_local",
    "tiros_puerta_visitante",
    "touches_box_local",
    "touches_box_visitante",
    "corners_local",
    "corners_visitante",
    "total_passes_local",
    "total_passes_visitante",
    "fouls_conceded_local",
    "fouls_conceded_visitante",
    "tarjetas_amarillas_local",
    "tarjetas_amarillas_visitante",
    "tarjetas_rojas_local",
    "tarjetas_rojas_visitante",
    "booking_points_local",
    "booking_points_visitante",
    # Attacking tab
    "big_chances_local",
    "big_chances_visitante",
    "shots_off_target_local",
    "shots_off_target_visitante",
    "attacks_local",
    "attacks_visitante",
    "hit_woodwork_local",
    "hit_woodwork_visitante",
    "blocked_shots_local",
    "blocked_shots_visitante",
    "shooting_accuracy_local",
    "shooting_accuracy_visitante",
    "dangerous_attacks_local",
    "dangerous_attacks_visitante",
    # Defence tab
    "tackles_local",
    "tackles_visitante",
    "tackle_success_pct_local",
    "tackle_success_pct_visitante",
    "duels_won_local",
    "duels_won_visitante",
    "aerial_duels_won_local",
    "aerial_duels_won_visitante",
    "clearance_local",
    "clearance_visitante",
    "saves_local",
    "saves_visitante",
    "interceptions_local",
    "interceptions_visitante",
    # Distribution tab
    "pass_success_pct_local",
    "pass_success_pct_visitante",
    "crosses_local",
    "crosses_visitante",
    "successful_crosses_pct_local",
    "successful_crosses_pct_visitante",
    "successful_passes_opp_half_local",
    "successful_passes_opp_half_visitante",
    "successful_passes_final_third_local",
    "successful_passes_final_third_visitante",
    "goal_kicks_local",
    "goal_kicks_visitante",
    "throw_ins_local",
    "throw_ins_visitante",
    "momentum_local",
    "momentum_visitante",
    # Volumen
    "volumen_matched",
    # Meta
    "url",
]


# ── Utilidades ───────────────────────────────────────────────────────────────

def extraer_id_partido(url: str) -> str:
    """Extrae un identificador del partido a partir de la URL."""
    # Betfair usa IDs numéricos al final de la URL del evento
    match = re.search(r"/(\d{7,12})(?:\?|$|#)", url)
    if match:
        return match.group(1)
    # Fallback: últimos segmentos de la URL
    partes = url.rstrip("/").split("/")
    return partes[-1][:50] if partes else "desconocido"


def leer_games_csv(ruta_csv: str = "games.csv") -> list:
    """
    Lee el archivo games.csv y devuelve lista de dicts con información de partidos.
    Formato esperado: Game,url,fecha_hora_inicio (opcional)

    Si fecha_hora_inicio existe, se parsea como datetime.
    Formato: "YYYY-MM-DD HH:MM" o "DD/MM/YYYY HH:MM"

    Retorna: [{"url": "...", "game": "...", "fecha_hora_inicio": datetime_obj}, ...]
    """
    partidos = []
    ruta = Path(ruta_csv)

    if not ruta.exists():
        log.warning(f"Archivo {ruta_csv} no encontrado. Usando config.MATCH_URLS.")
        return None

    try:
        with open(ruta, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "url" in row and row["url"].strip():
                    partido = {
                        "url": row["url"].strip(),
                        "game": row.get("Game", "").strip() or extraer_id_partido(row["url"].strip()),
                        "fecha_hora_inicio": None
                    }

                    # Intentar parsear fecha_hora_inicio si existe
                    if "fecha_hora_inicio" in row and row["fecha_hora_inicio"].strip():
                        fecha_str = row["fecha_hora_inicio"].strip()
                        try:
                            # Intentar formato YYYY-MM-DD HH:MM
                            partido["fecha_hora_inicio"] = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            try:
                                # Intentar formato DD/MM/YYYY HH:MM
                                partido["fecha_hora_inicio"] = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
                            except ValueError:
                                log.warning(f"Formato de fecha inválido para {partido['game']}: {fecha_str}")

                    partidos.append(partido)

        log.info(f"Cargados {len(partidos)} partidos desde {ruta_csv}")
        return partidos
    except Exception as e:
        log.error(f"Error leyendo {ruta_csv}: {e}")
        return None


def filtrar_partidos_activos(partidos: list, ventana_antes_min: int = 10, ventana_despues_min: int = 150) -> tuple:
    """
    Filtra partidos que deben estar activos en este momento.

    Args:
        partidos: Lista de dicts con 'url', 'game', 'fecha_hora_inicio'
        ventana_antes_min: Minutos antes del inicio para empezar a trackear
        ventana_despues_min: Minutos después del inicio para dejar de trackear

    Returns:
        (partidos_activos, partidos_futuros, partidos_finalizados)
        - partidos_activos: Deben estar siendo trackeados ahora
        - partidos_futuros: Aún no han empezado
        - partidos_finalizados: Ya terminaron la ventana de tracking
    """
    ahora = datetime.now()
    activos = []
    futuros = []
    finalizados = []

    for partido in partidos:
        # Si no tiene fecha_hora_inicio, trackear siempre (modo legacy)
        if partido["fecha_hora_inicio"] is None:
            activos.append(partido)
            continue

        # Calcular diferencia en minutos
        tiempo_hasta_inicio = (partido["fecha_hora_inicio"] - ahora).total_seconds() / 60

        if tiempo_hasta_inicio > ventana_antes_min:
            # Partido futuro (no ha llegado la ventana de tracking)
            futuros.append(partido)
        elif tiempo_hasta_inicio >= -ventana_despues_min:
            # Partido activo (dentro de ventana de tracking)
            activos.append(partido)
        else:
            # Partido finalizado (fuera de ventana de tracking)
            finalizados.append(partido)

    return (activos, futuros, finalizados)


def limpiar_precio(texto: str) -> str:
    """Limpia texto de precio: elimina espacios, convierte coma a punto."""
    if not texto:
        return ""
    texto = texto.strip().replace(",", ".").replace("\xa0", "")
    # Verificar que parece un número
    try:
        float(texto)
        return texto
    except ValueError:
        return ""


def buscar_elemento_texto(driver, selectores_css: str, timeout: int = 3) -> str:
    """
    Intenta encontrar un elemento con múltiples selectores CSS separados por coma.
    Devuelve el texto del primer elemento encontrado, o cadena vacía.
    """
    for selector in selectores_css.split(","):
        selector = selector.strip()
        if not selector:
            continue
        try:
            elem = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return elem.text.strip()
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException):
            continue
    return ""


def extraer_runners_match_odds(driver, timeout: int = 5) -> dict:
    """
    Extrae cuotas back/lay del mercado Match Odds (3 runners: Local, Empate, Visitante).
    Devuelve dict con claves back_home, lay_home, back_draw, lay_draw, back_away, lay_away.

    Estrategia actualizada 2026:
    - Busca todas las tablas tbody
    - Identifica runners por h3, detectando genéricamente Home/Draw/Away
    - Extrae precios de botones que contienen formato "número €cantidad"
    """
    resultado = {
        "back_home": "", "lay_home": "",
        "back_draw": "", "lay_draw": "",
        "back_away": "", "lay_away": "",
    }

    try:
        # Buscar todas las tablas
        tables = driver.find_elements(By.CSS_SELECTOR, "table tbody")

        runners_found = []  # Lista de (runner_name, back_price, lay_price)

        for tbody in tables:
            rows = tbody.find_elements(By.CSS_SELECTOR, "tr")

            for row in rows:
                try:
                    # Buscar el h3 que contiene el nombre del runner
                    h3_elements = row.find_elements(By.TAG_NAME, "h3")
                    if not h3_elements:
                        continue

                    runner_name = h3_elements[0].text.strip()

                    # Identificar si es Empate/Draw (más fácil de detectar)
                    is_draw = "Empate" in runner_name or "Draw" in runner_name

                    # Si no es empate, asumir que es Home o Away
                    # Los almacenaremos y luego asignaremos por orden
                    if not runner_name:
                        continue

                    # Buscar botones con precios
                    buttons = row.find_elements(By.TAG_NAME, "button")
                    price_buttons = []

                    for btn in buttons:
                        text = btn.text.strip()
                        # Buscar botones que tengan formato "número €cantidad" o "número.decimales €cantidad"
                        if text and ("€" in text or text.replace(".", "").replace(",", "").isdigit()):
                            price_buttons.append(btn)

                    # Los primeros 2 botones con precio son back y lay
                    if len(price_buttons) >= 2:
                        import re

                        back_text = price_buttons[0].text.strip()
                        lay_text = price_buttons[1].text.strip()

                        # Extraer el número antes del símbolo € o espacios
                        back_match = re.match(r"^(\d+\.?\d*)", back_text.replace(",", "."))
                        lay_match = re.match(r"^(\d+\.?\d*)", lay_text.replace(",", "."))

                        back_price = back_match.group(1) if back_match else ""
                        lay_price = lay_match.group(1) if lay_match else ""

                        # Guardar runner con sus precios
                        runners_found.append((runner_name, back_price, lay_price, is_draw))

                except (NoSuchElementException, StaleElementReferenceException):
                    continue

            # Si ya encontramos 3 runners, salir de este tbody
            if len(runners_found) >= 3:
                break

        # Asignar runners: primero el Empate, luego los otros 2 como Home/Away
        draw_assigned = False
        teams_assigned = []

        for runner_name, back_price, lay_price, is_draw in runners_found:
            if is_draw and not draw_assigned:
                resultado["back_draw"] = back_price
                resultado["lay_draw"] = lay_price
                draw_assigned = True
            elif not is_draw:
                teams_assigned.append((runner_name, back_price, lay_price))

        # Los equipos: el primero es Home, el segundo es Away
        if len(teams_assigned) >= 1:
            resultado["back_home"] = teams_assigned[0][1]
            resultado["lay_home"] = teams_assigned[0][2]
        if len(teams_assigned) >= 2:
            resultado["back_away"] = teams_assigned[1][1]
            resultado["lay_away"] = teams_assigned[1][2]

    except WebDriverException as e:
        log.debug(f"Error extrayendo Match Odds: {e}")

    return resultado


def extraer_over_under(driver) -> dict:
    """
    Extrae cuotas Over/Under para 0.5, 1.5, 2.5, 3.5, 4.5 goles.

    Estrategia actualizada 2026:
    - Busca todas las tablas tbody
    - Identifica runners por h3 que contengan "X,5 Goles" o "X.5 Goles"
    - Extrae precios de botones igual que Match Odds
    """
    resultado = {
        "back_over05": "", "lay_over05": "",
        "back_under05": "", "lay_under05": "",
        "back_over15": "", "lay_over15": "",
        "back_under15": "", "lay_under15": "",
        "back_over25": "", "lay_over25": "",
        "back_under25": "", "lay_under25": "",
        "back_over35": "", "lay_over35": "",
        "back_under35": "", "lay_under35": "",
        "back_over45": "", "lay_over45": "",
        "back_under45": "", "lay_under45": "",
    }

    try:
        # Buscar todas las tablas
        tables = driver.find_elements(By.CSS_SELECTOR, "table tbody")

        for tbody in tables:
            rows = tbody.find_elements(By.CSS_SELECTOR, "tr")

            for row in rows:
                try:
                    h3_elements = row.find_elements(By.TAG_NAME, "h3")
                    if not h3_elements:
                        continue

                    runner_name = h3_elements[0].text.strip()

                    # Identificar Over o Under para cada línea
                    runner_key = None

                    # 0.5 Goles
                    if "0,5 Goles" in runner_name or "0.5 Goles" in runner_name:
                        if "Más" in runner_name or "Over" in runner_name:
                            runner_key = ("back_over05", "lay_over05")
                        elif "Menos" in runner_name or "Under" in runner_name:
                            runner_key = ("back_under05", "lay_under05")

                    # 1.5 Goles
                    elif "1,5 Goles" in runner_name or "1.5 Goles" in runner_name:
                        if "Más" in runner_name or "Over" in runner_name:
                            runner_key = ("back_over15", "lay_over15")
                        elif "Menos" in runner_name or "Under" in runner_name:
                            runner_key = ("back_under15", "lay_under15")

                    # 2.5 Goles
                    elif "2,5 Goles" in runner_name or "2.5 Goles" in runner_name:
                        if "Más" in runner_name or "Over" in runner_name:
                            runner_key = ("back_over25", "lay_over25")
                        elif "Menos" in runner_name or "Under" in runner_name:
                            runner_key = ("back_under25", "lay_under25")

                    # 3.5 Goles
                    elif "3,5 Goles" in runner_name or "3.5 Goles" in runner_name:
                        if "Más" in runner_name or "Over" in runner_name:
                            runner_key = ("back_over35", "lay_over35")
                        elif "Menos" in runner_name or "Under" in runner_name:
                            runner_key = ("back_under35", "lay_under35")

                    # 4.5 Goles
                    elif "4,5 Goles" in runner_name or "4.5 Goles" in runner_name:
                        if "Más" in runner_name or "Over" in runner_name:
                            runner_key = ("back_over45", "lay_over45")
                        elif "Menos" in runner_name or "Under" in runner_name:
                            runner_key = ("back_under45", "lay_under45")

                    if not runner_key:
                        continue

                    # Buscar botones con precios
                    buttons = row.find_elements(By.TAG_NAME, "button")
                    price_buttons = []

                    for btn in buttons:
                        text = btn.text.strip()
                        if text and ("€" in text or text.replace(".", "").replace(",", "").isdigit()):
                            price_buttons.append(btn)

                    if len(price_buttons) >= 2:
                        import re

                        back_text = price_buttons[0].text.strip()
                        lay_text = price_buttons[1].text.strip()

                        back_match = re.match(r"^(\d+\.?\d*)", back_text.replace(",", "."))
                        lay_match = re.match(r"^(\d+\.?\d*)", lay_text.replace(",", "."))

                        if back_match:
                            resultado[runner_key[0]] = back_match.group(1)
                        if lay_match:
                            resultado[runner_key[1]] = lay_match.group(1)

                except (NoSuchElementException, StaleElementReferenceException):
                    continue

    except WebDriverException as e:
        log.debug(f"No se pudo extraer Over/Under: {e}")

    return resultado


def extraer_info_partido(driver) -> dict:
    """Extrae información del estado del partido: minuto, marcador, nombre evento, hora comienzo, estado."""
    info = {
        "evento": "",
        "hora_comienzo": "",
        "estado_partido": "",  # Nuevo: descanso, en_juego, finalizado, pre_partido
        "minuto": "",
        "goles_local": "",
        "goles_visitante": ""
    }

    # Nombre del evento (timeout reducido)
    info["evento"] = buscar_elemento_texto(driver, SELECTORES["event_name"], timeout=1)

    # Hora de comienzo (OPTIMIZADO: solo 1 selector principal)
    try:
        elementos = driver.find_elements(By.CSS_SELECTOR, ".market-information time, time[datetime]")
        for elem in elementos[:3]:  # Solo primeros 3
            texto = elem.text.strip()
            if re.search(r"\d{1,2}:\d{2}", texto):
                info["hora_comienzo"] = texto
                break
    except Exception:
        pass

    # Detectar estado del partido (ULTRA-OPTIMIZADO: XPATH directo primero, luego CSS mínimo)
    # Estrategia: XPATH con contains() es más rápido para text matching que iterar elementos
    if not info["estado_partido"]:
        try:
            # XPATH directo: buscar texto "Descanso" (más rápido que CSS + loop)
            xpath_queries = [
                "//*[contains(text(), 'Descanso') or contains(text(), 'DESCANSO') or contains(text(), 'Half-time') or contains(text(), 'HT')]",
                "//*[contains(text(), 'Finalizado') or contains(text(), 'FINALIZADO') or contains(text(), 'Full-time') or contains(text(), 'FT')]",
            ]

            # Buscar descanso primero
            try:
                elem = driver.find_element(By.XPATH, xpath_queries[0])
                if elem and elem.is_displayed():
                    info["estado_partido"] = "descanso"
                    log.debug(f"  ✓ Estado detectado: DESCANSO (XPATH: texto '{elem.text.strip()}')")
            except NoSuchElementException:
                pass

            # Si no encontró descanso, buscar finalizado
            if not info["estado_partido"]:
                try:
                    elem = driver.find_element(By.XPATH, xpath_queries[1])
                    if elem and elem.is_displayed():
                        info["estado_partido"] = "finalizado"
                        log.debug(f"  ✓ Estado detectado: FINALIZADO (XPATH: texto '{elem.text.strip()}')")
                except NoSuchElementException:
                    pass
        except Exception as e:
            log.debug(f"  × Error en búsqueda XPATH de estado: {e}")

    # Fallback CSS (solo si XPATH falló): búsqueda rápida en 3 selectores clave
    if not info["estado_partido"]:
        selectores_estado = ["p.time-elapsed", ".time-elapsed", ".match-status"]
        for selector in selectores_estado:
            try:
                elementos = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elementos[:5]:  # Solo primeros 5 (reducido de 30)
                    try:
                        texto = elem.text.strip().lower()
                        if not texto or len(texto) > 50:
                            continue
                        if any(k in texto for k in ["descanso", "half-time", "halftime", "ht"]):
                            info["estado_partido"] = "descanso"
                            log.debug(f"  ✓ Estado detectado: DESCANSO (CSS: '{elem.text.strip()}')")
                            break
                        elif any(k in texto for k in ["finalizado", "full-time", "fulltime", "ft"]) and "minut" not in texto:
                            info["estado_partido"] = "finalizado"
                            log.debug(f"  ✓ Estado detectado: FINALIZADO (CSS: '{elem.text.strip()}')")
                            break
                    except (StaleElementReferenceException, AttributeError):
                        continue
                if info["estado_partido"]:
                    break
            except Exception:
                continue

    # Tiempo/minuto del partido (timeout reducido)
    tiempo_txt = buscar_elemento_texto(driver, SELECTORES["match_time"], timeout=0.5)
    if tiempo_txt:
        # Extraer número de minuto (ej: "45:00" -> "45", "67'" -> "67")
        match = re.search(r"(\d+)", tiempo_txt)
        if match:
            info["minuto"] = match.group(1)

    # Marcador (timeout reducido)
    score_txt = buscar_elemento_texto(driver, SELECTORES["match_score"], timeout=0.5)
    if score_txt:
        # Formato esperado: "2 - 1", "2-1", etc.
        match = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_txt)
        if match:
            info["goles_local"] = match.group(1)
            info["goles_visitante"] = match.group(2)

    return info


def extraer_resultado_correcto(driver) -> dict:
    """
    Extrae cuotas back/lay del mercado Resultado Correcto.
    Captura los marcadores más comunes: 0-0, 1-0, 0-1, 1-1, 2-0, 0-2, 2-1, 1-2, 2-2, 3-0, 0-3, 3-1, 1-3, 3-2, 2-3
    """
    resultado = {}

    # Inicializar todos los marcadores comunes
    marcadores = [
        "0-0", "1-0", "0-1", "1-1",
        "2-0", "0-2", "2-1", "1-2", "2-2",
        "3-0", "0-3", "3-1", "1-3", "3-2", "2-3"
    ]

    for marcador in marcadores:
        marcador_key = marcador.replace("-", "_")
        resultado[f"back_rc_{marcador_key}"] = ""
        resultado[f"lay_rc_{marcador_key}"] = ""

    try:
        # Buscar todas las tablas
        tables = driver.find_elements(By.CSS_SELECTOR, "table tbody")

        for tbody in tables:
            rows = tbody.find_elements(By.CSS_SELECTOR, "tr")

            for row in rows:
                try:
                    h3_elements = row.find_elements(By.TAG_NAME, "h3")
                    if not h3_elements:
                        continue

                    runner_name = h3_elements[0].text.strip()

                    # Buscar si el runner es un marcador (ej: "0 - 0", "1 - 0", etc.)
                    marcador_match = re.search(r"(\d+)\s*-\s*(\d+)", runner_name)
                    if not marcador_match:
                        continue

                    marcador = f"{marcador_match.group(1)}-{marcador_match.group(2)}"
                    if marcador not in marcadores:
                        continue

                    marcador_key = marcador.replace("-", "_")

                    # Buscar botones con precios
                    buttons = row.find_elements(By.TAG_NAME, "button")
                    price_buttons = []

                    for btn in buttons:
                        text = btn.text.strip()
                        if text and ("€" in text or text.replace(".", "").replace(",", "").isdigit()):
                            price_buttons.append(btn)

                    if len(price_buttons) >= 2:
                        back_text = price_buttons[0].text.strip()
                        lay_text = price_buttons[1].text.strip()

                        back_match = re.match(r"^(\d+\.?\d*)", back_text.replace(",", "."))
                        lay_match = re.match(r"^(\d+\.?\d*)", lay_text.replace(",", "."))

                        if back_match:
                            resultado[f"back_rc_{marcador_key}"] = back_match.group(1)
                        if lay_match:
                            resultado[f"lay_rc_{marcador_key}"] = lay_match.group(1)

                except (NoSuchElementException, StaleElementReferenceException):
                    continue

    except WebDriverException as e:
        log.debug(f"No se pudo extraer Resultado Correcto: {e}")

    return resultado


def extraer_estadisticas(driver) -> dict:
    """
    Extrae estadísticas del partido en vivo desde iframe de Opta (xG, Opta Points, posesión, tiros, corners, tarjetas).
    Estas estadísticas aparecen en la pestaña "Estadísticas del partido" dentro del iframe de Betfair.
    Ahora también captura datos de tabs: Attacking, Defence, Distribution.
    """
    stats = {
        # Summary tab
        "xg_local": "",
        "xg_visitante": "",
        "opta_points_local": "",
        "opta_points_visitante": "",
        "posesion_local": "",
        "posesion_visitante": "",
        "tiros_local": "",
        "tiros_visitante": "",
        "tiros_puerta_local": "",
        "tiros_puerta_visitante": "",
        "touches_box_local": "",
        "touches_box_visitante": "",
        "corners_local": "",
        "corners_visitante": "",
        "total_passes_local": "",
        "total_passes_visitante": "",
        "fouls_conceded_local": "",
        "fouls_conceded_visitante": "",
        "tarjetas_amarillas_local": "",
        "tarjetas_amarillas_visitante": "",
        "tarjetas_rojas_local": "",
        "tarjetas_rojas_visitante": "",
        "booking_points_local": "",
        "booking_points_visitante": "",
        # Attacking tab
        "big_chances_local": "",
        "big_chances_visitante": "",
        "shots_off_target_local": "",
        "shots_off_target_visitante": "",
        "attacks_local": "",
        "attacks_visitante": "",
        "hit_woodwork_local": "",
        "hit_woodwork_visitante": "",
        "blocked_shots_local": "",
        "blocked_shots_visitante": "",
        "shooting_accuracy_local": "",
        "shooting_accuracy_visitante": "",
        "dangerous_attacks_local": "",
        "dangerous_attacks_visitante": "",
        # Defence tab
        "tackles_local": "",
        "tackles_visitante": "",
        "tackle_success_pct_local": "",
        "tackle_success_pct_visitante": "",
        "duels_won_local": "",
        "duels_won_visitante": "",
        "aerial_duels_won_local": "",
        "aerial_duels_won_visitante": "",
        "clearance_local": "",
        "clearance_visitante": "",
        "saves_local": "",
        "saves_visitante": "",
        "interceptions_local": "",
        "interceptions_visitante": "",
        # Distribution tab
        "pass_success_pct_local": "",
        "pass_success_pct_visitante": "",
        "crosses_local": "",
        "crosses_visitante": "",
        "successful_crosses_pct_local": "",
        "successful_crosses_pct_visitante": "",
        "successful_passes_opp_half_local": "",
        "successful_passes_opp_half_visitante": "",
        "successful_passes_final_third_local": "",
        "successful_passes_final_third_visitante": "",
        "goal_kicks_local": "",
        "goal_kicks_visitante": "",
        "throw_ins_local": "",
        "throw_ins_visitante": "",
    }

    # PASO 1: Hacer clic en pestaña "Estadísticas del partido"
    log.debug("  → Buscando pestaña 'Estadísticas del partido'...")
    try:
        stats_tab_selectors = [
            "//li[contains(text(), 'Estadísticas del partido')]",
            "//button[contains(text(), 'Estadísticas del partido')]",
            "//a[contains(text(), 'Estadísticas del partido')]",
            "//*[contains(text(), 'Estadísticas del partido')]",
        ]

        tab_clicked = False
        for selector in stats_tab_selectors:
            try:
                tab_element = WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                # Usar JavaScript click para evitar "element click intercepted"
                driver.execute_script("arguments[0].click();", tab_element)
                log.debug(f"  ✓ Clic en pestaña 'Estadísticas del partido' (JS click)")
                time.sleep(1)  # Esperar a que cargue el iframe con las estadísticas
                tab_clicked = True
                break
            except (TimeoutException, NoSuchElementException, WebDriverException):
                continue

        if not tab_clicked:
            log.debug("  × Pestaña 'Estadísticas del partido' no encontrada (partido puede no tener estadísticas)")
    except Exception as e:
        log.debug(f"  × No se pudo hacer clic en pestaña de estadísticas: {e}")

    # PASO 2: Intentar extraer desde iframe de estadísticas (OPTIMIZADO: limitar a primeros 5 iframes)
    original_window = driver.current_window_handle

    try:
        # Buscar iframes con timeout corto
        try:
            iframes = WebDriverWait(driver, 2).until(
                EC.presence_of_all_elements_located((By.TAG_NAME, "iframe"))
            )
            log.debug(f"  → Total iframes encontrados: {len(iframes)}")
        except TimeoutException:
            iframes = []
            log.debug("  × No se encontraron iframes")

        # OPTIMIZACIÓN: Limitar a primeros 5 iframes para evitar demoras
        for idx, iframe in enumerate(iframes[:5]):
            try:
                driver.switch_to.frame(iframe)
                log.debug(f"  → Iframe #{idx+1}: accediendo...")

                # IMPORTANTE: Buscar iframes ANIDADOS (iframes dentro de este iframe)
                # Las estadísticas de Betfair están en un iframe de segundo nivel
                nested_iframes = driver.find_elements(By.TAG_NAME, "iframe")

                if nested_iframes:
                    log.debug(f"    → Encontrados {len(nested_iframes)} iframes anidados, revisando...")
                    paragraphs = []  # Inicializar para evitar error si todos los nested iframes fallan
                    for nested_idx, nested_iframe in enumerate(nested_iframes[:3]):  # Limitar a 3 nested iframes
                        try:
                            driver.switch_to.frame(nested_iframe)
                            log.debug(f"      → Iframe anidado #{nested_idx+1}: accediendo...")

                            # Buscar párrafos en iframe anidado
                            try:
                                paragraphs = WebDriverWait(driver, 1).until(
                                    EC.presence_of_all_elements_located((By.TAG_NAME, "p"))
                                )
                                log.debug(f"        - Párrafos encontrados: {len(paragraphs)}")
                            except TimeoutException:
                                log.debug(f"        × Sin párrafos")
                                driver.switch_to.parent_frame()
                                continue

                            # Filtrar nombres de tabs del DOM
                            TAB_NAMES = {"summary", "momentum", "xg", "attacking", "defence",
                                        "distribution", "discipline", "live stats", "player stats",
                                        "season avg", "top scorers", "powered by"}

                            paragraphs_filtered = [
                                p for p in paragraphs
                                if p.text.strip().lower() not in TAB_NAMES
                            ]

                            # Usar paragraphs_filtered para verificación y procesamiento
                            paragraphs = paragraphs_filtered

                            # Verificar si contiene estadísticas (buscar palabras clave)
                            all_text = " ".join([p.text.lower() for p in paragraphs[:50]])
                            has_stats = any(keyword in all_text for keyword in ["xg", "opta", "possession", "shots", "corners"])

                            if has_stats:
                                log.debug(f"        ✓ Contiene estadísticas! Extrayendo...")
                                break  # Salir del loop de nested iframes, usar estos paragraphs
                            else:
                                log.debug(f"        × No contiene estadísticas reconocidas")
                                driver.switch_to.parent_frame()
                                paragraphs = []
                        except Exception as nested_e:
                            log.debug(f"        × Error en nested iframe: {type(nested_e).__name__}")
                            try:
                                driver.switch_to.parent_frame()
                            except:
                                pass
                            paragraphs = []
                else:
                    # Si no hay iframes anidados, buscar párrafos directamente
                    log.debug(f"    → Sin iframes anidados, buscando párrafos directamente...")
                    try:
                        paragraphs = WebDriverWait(driver, 1).until(
                            EC.presence_of_all_elements_located((By.TAG_NAME, "p"))
                        )
                        log.debug(f"    - Párrafos encontrados: {len(paragraphs)}")
                    except TimeoutException:
                        log.debug(f"    × Sin párrafos")
                        driver.switch_to.default_content()
                        continue

                    # Filtrar nombres de tabs del DOM
                    TAB_NAMES = {"summary", "momentum", "xg", "attacking", "defence",
                                "distribution", "discipline", "live stats", "player stats",
                                "season avg", "top scorers", "powered by"}

                    paragraphs_filtered = [
                        p for p in paragraphs
                        if p.text.strip().lower() not in TAB_NAMES
                    ]

                    # Usar paragraphs_filtered para verificación y procesamiento
                    paragraphs = paragraphs_filtered

                    # Verificar si contiene estadísticas
                    all_text = " ".join([p.text.lower() for p in paragraphs[:50]])
                    has_stats = any(keyword in all_text for keyword in ["xg", "opta", "possession", "shots", "corners"])

                    if not has_stats:
                        log.debug(f"    × No contiene estadísticas reconocidas")
                        driver.switch_to.default_content()
                        continue

                    log.debug(f"    ✓ Contiene estadísticas! Extrayendo...")

                # Si no encontramos párrafos, saltar
                if not paragraphs:
                    log.debug(f"    × No se encontraron párrafos con estadísticas")
                    driver.switch_to.default_content()
                    continue

                # Procesar párrafos en grupos de 3 (valor_local, nombre_stat, valor_visitante)
                i = 0
                stats_encontradas = 0
                while i < len(paragraphs) - 2 and i < 150:  # Limitar a primeros 150 párrafos
                    try:
                        valor_local = paragraphs[i].text.strip()
                        nombre_stat = paragraphs[i + 1].text.strip().lower()
                        valor_visitante = paragraphs[i + 2].text.strip()

                        # Solo procesar si nombre_stat es texto reconocible (no números)
                        if not nombre_stat or nombre_stat.replace(".", "").replace("%", "").isdigit():
                            i += 1
                            continue

                        stat_found = False

                        # Función auxiliar para verificar si un valor es numérico (incluyendo decimales y porcentajes)
                        def es_valor_numerico(texto):
                            """Verifica si el texto es un valor numérico válido (ej: 2.30, 60%, 14)."""
                            if not texto:
                                return False
                            # Remover % si existe
                            texto_limpio = texto.replace("%", "").strip()
                            # Intentar convertir a float
                            try:
                                float(texto_limpio)
                                return True
                            except ValueError:
                                return False

                        # xG (Expected Goals)
                        if nombre_stat == "xg":
                            # Verificar que los valores sean numéricos
                            if es_valor_numerico(valor_local) and es_valor_numerico(valor_visitante):
                                stats["xg_local"] = valor_local
                                stats["xg_visitante"] = valor_visitante
                                stats_encontradas += 1
                                log.debug(f"      ✓ xG: {valor_local} - {valor_visitante}")
                                stat_found = True
                            else:
                                log.debug(f"      × xG rechazado (valores no numéricos): {valor_local} - {valor_visitante}")
                                stat_found = False

                        # Opta Points
                        elif "opta points" in nombre_stat or nombre_stat == "opta points":
                            stats["opta_points_local"] = valor_local
                            stats["opta_points_visitante"] = valor_visitante
                            stats_encontradas += 1
                            log.debug(f"      ✓ Opta Points: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Possession
                        elif "possession" in nombre_stat or "posesión" in nombre_stat:
                            stats["posesion_local"] = valor_local.replace("%", "")
                            stats["posesion_visitante"] = valor_visitante.replace("%", "")
                            stats_encontradas += 1
                            log.debug(f"      ✓ Possession: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Shots (total)
                        elif nombre_stat == "shots" or nombre_stat == "tiros":
                            stats["tiros_local"] = valor_local
                            stats["tiros_visitante"] = valor_visitante
                            stats_encontradas += 1
                            log.debug(f"      ✓ Shots: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Shots On Target
                        elif "shots on target" in nombre_stat or "on target" in nombre_stat:
                            stats["tiros_puerta_local"] = valor_local
                            stats["tiros_puerta_visitante"] = valor_visitante
                            stats_encontradas += 1
                            log.debug(f"      ✓ Shots On Target: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Touches in Opposition Box
                        elif "touches in opposition box" in nombre_stat or "opposition box" in nombre_stat:
                            stats["touches_box_local"] = valor_local
                            stats["touches_box_visitante"] = valor_visitante
                            stats_encontradas += 1
                            log.debug(f"      ✓ Touches in Box: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Corners
                        elif nombre_stat == "corners" or "corner" in nombre_stat:
                            stats["corners_local"] = valor_local
                            stats["corners_visitante"] = valor_visitante
                            stats_encontradas += 1
                            log.debug(f"      ✓ Corners: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Total Passes
                        elif "total passes" in nombre_stat or nombre_stat == "total passes":
                            stats["total_passes_local"] = valor_local
                            stats["total_passes_visitante"] = valor_visitante
                            stats_encontradas += 1
                            log.debug(f"      ✓ Total Passes: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Yellow Cards
                        elif "yellow cards" in nombre_stat or "yellow" in nombre_stat:
                            # Verificar que los valores sean numéricos
                            if es_valor_numerico(valor_local) and es_valor_numerico(valor_visitante):
                                stats["tarjetas_amarillas_local"] = valor_local
                                stats["tarjetas_amarillas_visitante"] = valor_visitante
                                stats_encontradas += 1
                                log.debug(f"      ✓ Yellow Cards: {valor_local} - {valor_visitante}")
                                stat_found = True
                            else:
                                log.debug(f"      × Yellow Cards rechazado (valores no numéricos): {valor_local} - {valor_visitante}")
                                stat_found = False

                        # Red Cards
                        elif "red cards" in nombre_stat or "red" in nombre_stat:
                            # Verificar que los valores sean numéricos
                            if es_valor_numerico(valor_local) and es_valor_numerico(valor_visitante):
                                stats["tarjetas_rojas_local"] = valor_local
                                stats["tarjetas_rojas_visitante"] = valor_visitante
                                stats_encontradas += 1
                                log.debug(f"      ✓ Red Cards: {valor_local} - {valor_visitante}")
                                stat_found = True
                            else:
                                log.debug(f"      × Red Cards rechazado (valores no numéricos): {valor_local} - {valor_visitante}")
                                stat_found = False

                        # Booking Points
                        elif "booking points" in nombre_stat or "booking" in nombre_stat:
                            # Verificar que los valores sean numéricos
                            if es_valor_numerico(valor_local) and es_valor_numerico(valor_visitante):
                                stats["booking_points_local"] = valor_local
                                stats["booking_points_visitante"] = valor_visitante
                                stats_encontradas += 1
                                log.debug(f"      ✓ Booking Points: {valor_local} - {valor_visitante}")
                                stat_found = True
                            else:
                                log.debug(f"      × Booking Points rechazado (valores no numéricos): {valor_local} - {valor_visitante}")
                                stat_found = False

                        # Fouls Conceded
                        elif "fouls conceded" in nombre_stat or "fouls" in nombre_stat:
                            stats["fouls_conceded_local"] = valor_local
                            stats["fouls_conceded_visitante"] = valor_visitante
                            stats_encontradas += 1
                            log.debug(f"      ✓ Fouls Conceded: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Dangerous Attacks
                        elif "dangerous attacks" in nombre_stat or "dangerous attack" in nombre_stat:
                            stats["dangerous_attacks_local"] = valor_local
                            stats["dangerous_attacks_visitante"] = valor_visitante
                            stats_encontradas += 1
                            log.debug(f"      ✓ Dangerous Attacks: {valor_local} - {valor_visitante}")
                            stat_found = True

                        # Si encontramos una estadística válida, saltar 3 posiciones (valor_local, nombre, valor_visitante)
                        # Si no, avanzar solo 1 para seguir buscando
                        if stat_found:
                            i += 3
                        else:
                            i += 1

                    except (IndexError, AttributeError, StaleElementReferenceException):
                        i += 1

                # Mostrar stats capturadas
                if stats_encontradas > 0:
                    log.debug(f"  ✓✓ Total: {stats_encontradas} estadísticas Summary capturadas")

                    # ═══════════════════════════════════════════════════════════════════════
                    # NUEVO: Capturar estadísticas de tabs adicionales (Attacking, Defence, Distribution)
                    # IMPORTANTE: Estamos dentro del iframe, NO hacer switch_to.default_content() todavía
                    # ═══════════════════════════════════════════════════════════════════════

                    log.debug("  → Buscando tabs adicionales: Attacking, Defence, Distribution...")

                    # Función auxiliar para parsear estadísticas de un tab (misma lógica de grupos de 3)
                    def parsear_stats_tab(paragraphs, keywords_map, tab_name):
                        """
                        Parsea estadísticas de un tab específico.
                        Args:
                            paragraphs: lista de elementos <p>
                            keywords_map: dict {nombre_stat_lower: (key_local, key_visitante)}
                            tab_name: nombre del tab para logging
                        Returns:
                            dict con las stats capturadas
                        """
                        tab_stats = {}
                        stats_capturadas = 0
                        i = 0

                        def es_valor_numerico(texto):
                            if not texto:
                                return False
                            texto_limpio = texto.replace("%", "").strip()
                            try:
                                float(texto_limpio)
                                return True
                            except ValueError:
                                return False

                        while i < len(paragraphs) - 2 and i < 150:
                            try:
                                valor_local = paragraphs[i].text.strip()
                                nombre_stat = paragraphs[i + 1].text.strip().lower()
                                valor_visitante = paragraphs[i + 2].text.strip()

                                # Solo procesar si nombre_stat es texto reconocible (no números)
                                if not nombre_stat or nombre_stat.replace(".", "").replace("%", "").isdigit():
                                    i += 1
                                    continue

                                stat_found = False

                                # Buscar coincidencia con keywords
                                for keyword, (key_local, key_visitante) in keywords_map.items():
                                    if keyword in nombre_stat:
                                        # Limpiar porcentajes si es necesario
                                        val_local_limpio = valor_local.replace("%", "").strip()
                                        val_visitante_limpio = valor_visitante.replace("%", "").strip()

                                        # Validar que sean numéricos
                                        if es_valor_numerico(valor_local) and es_valor_numerico(valor_visitante):
                                            tab_stats[key_local] = val_local_limpio
                                            tab_stats[key_visitante] = val_visitante_limpio
                                            stats_capturadas += 1
                                            log.debug(f"      ✓ {tab_name} - {nombre_stat}: {val_local_limpio} - {val_visitante_limpio}")
                                            stat_found = True
                                            break
                                        else:
                                            log.debug(f"      × {tab_name} - {nombre_stat} rechazado (valores no numéricos): {valor_local} - {valor_visitante}")

                                # Avanzar según si encontramos una stat válida
                                if stat_found:
                                    i += 3
                                else:
                                    i += 1

                            except (IndexError, AttributeError, StaleElementReferenceException):
                                i += 1

                        log.debug(f"  ✓ {tab_name}: {stats_capturadas} estadísticas capturadas")
                        return tab_stats

                    # ─────────────────────────────────────────────────────────────────
                    # TAB: Attacking
                    # ─────────────────────────────────────────────────────────────────
                    try:
                        log.debug("  → Buscando tab 'Attacking'...")

                        # Buscar y hacer click en el tab "Attacking"
                        attacking_tab_clicked = False
                        attacking_selectors = [
                            "//p[contains(text(), 'Attacking')]",
                            "//button[contains(text(), 'Attacking')]",
                            "//a[contains(text(), 'Attacking')]",
                            "//*[contains(text(), 'Attacking')]",
                        ]

                        for selector in attacking_selectors:
                            try:
                                tab_element = WebDriverWait(driver, 2).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                                driver.execute_script("arguments[0].click();", tab_element)
                                log.debug(f"  ✓ Clic en tab 'Attacking'")
                                time.sleep(1.5)  # Esperar a que carguen las estadísticas
                                attacking_tab_clicked = True
                                break
                            except (TimeoutException, NoSuchElementException, WebDriverException):
                                continue

                        if attacking_tab_clicked:
                            # Re-leer los párrafos (contenido ha cambiado)
                            try:
                                attacking_paragraphs = WebDriverWait(driver, 2).until(
                                    EC.presence_of_all_elements_located((By.TAG_NAME, "p"))
                                )

                                # Keywords para Attacking
                                attacking_keywords = {
                                    "big chances": ("big_chances_local", "big_chances_visitante"),
                                    "shots off target": ("shots_off_target_local", "shots_off_target_visitante"),
                                    "blocked shots": ("blocked_shots_local", "blocked_shots_visitante"),
                                    "shots on target": ("tiros_puerta_local", "tiros_puerta_visitante"),
                                    "shooting accuracy": ("shooting_accuracy_local", "shooting_accuracy_visitante"),
                                    "dangerous attacks": ("dangerous_attacks_local", "dangerous_attacks_visitante"),
                                    "attacks": ("attacks_local", "attacks_visitante"),
                                    "hit woodwork": ("hit_woodwork_local", "hit_woodwork_visitante"),
                                }

                                attacking_stats = parsear_stats_tab(attacking_paragraphs, attacking_keywords, "Attacking")
                                stats.update(attacking_stats)

                            except TimeoutException:
                                log.debug("  × No se encontraron párrafos en tab Attacking")
                        else:
                            log.debug("  × Tab 'Attacking' no encontrado")

                    except Exception as e:
                        log.debug(f"  × Error procesando tab Attacking: {type(e).__name__}")

                    # ─────────────────────────────────────────────────────────────────
                    # TAB: Defence
                    # ─────────────────────────────────────────────────────────────────
                    try:
                        log.debug("  → Buscando tab 'Defence'...")

                        defence_tab_clicked = False
                        defence_selectors = [
                            "//p[contains(text(), 'Defence')]",
                            "//button[contains(text(), 'Defence')]",
                            "//a[contains(text(), 'Defence')]",
                            "//*[contains(text(), 'Defence')]",
                        ]

                        for selector in defence_selectors:
                            try:
                                tab_element = WebDriverWait(driver, 2).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                                driver.execute_script("arguments[0].click();", tab_element)
                                log.debug(f"  ✓ Clic en tab 'Defence'")
                                time.sleep(1.5)
                                defence_tab_clicked = True
                                break
                            except (TimeoutException, NoSuchElementException, WebDriverException):
                                continue

                        if defence_tab_clicked:
                            try:
                                defence_paragraphs = WebDriverWait(driver, 2).until(
                                    EC.presence_of_all_elements_located((By.TAG_NAME, "p"))
                                )

                                # Keywords para Defence
                                defence_keywords = {
                                    "tackles": ("tackles_local", "tackles_visitante"),
                                    "tackle success": ("tackle_success_pct_local", "tackle_success_pct_visitante"),
                                    "duels won": ("duels_won_local", "duels_won_visitante"),
                                    "aerial duels won": ("aerial_duels_won_local", "aerial_duels_won_visitante"),
                                    "aerial duels": ("aerial_duels_won_local", "aerial_duels_won_visitante"),  # Fallback
                                    "clearance": ("clearance_local", "clearance_visitante"),
                                    "saves": ("saves_local", "saves_visitante"),
                                    "interceptions": ("interceptions_local", "interceptions_visitante"),
                                }

                                defence_stats = parsear_stats_tab(defence_paragraphs, defence_keywords, "Defence")
                                stats.update(defence_stats)

                            except TimeoutException:
                                log.debug("  × No se encontraron párrafos en tab Defence")
                        else:
                            log.debug("  × Tab 'Defence' no encontrado")

                    except Exception as e:
                        log.debug(f"  × Error procesando tab Defence: {type(e).__name__}")

                    # ─────────────────────────────────────────────────────────────────
                    # TAB: Distribution
                    # ─────────────────────────────────────────────────────────────────
                    try:
                        log.debug("  → Buscando tab 'Distribution'...")

                        distribution_tab_clicked = False
                        distribution_selectors = [
                            "//p[contains(text(), 'Distribution')]",
                            "//button[contains(text(), 'Distribution')]",
                            "//a[contains(text(), 'Distribution')]",
                            "//*[contains(text(), 'Distribution')]",
                        ]

                        for selector in distribution_selectors:
                            try:
                                tab_element = WebDriverWait(driver, 2).until(
                                    EC.presence_of_element_located((By.XPATH, selector))
                                )
                                driver.execute_script("arguments[0].click();", tab_element)
                                log.debug(f"  ✓ Clic en tab 'Distribution'")
                                time.sleep(1.5)
                                distribution_tab_clicked = True
                                break
                            except (TimeoutException, NoSuchElementException, WebDriverException):
                                continue

                        if distribution_tab_clicked:
                            try:
                                distribution_paragraphs = WebDriverWait(driver, 2).until(
                                    EC.presence_of_all_elements_located((By.TAG_NAME, "p"))
                                )

                                # Keywords para Distribution
                                distribution_keywords = {
                                    "pass success": ("pass_success_pct_local", "pass_success_pct_visitante"),
                                    "successful crosses": ("successful_crosses_pct_local", "successful_crosses_pct_visitante"),
                                    "crosses": ("crosses_local", "crosses_visitante"),
                                    "successful passes in opposition half": ("successful_passes_opp_half_local", "successful_passes_opp_half_visitante"),
                                    "successful passes in final third": ("successful_passes_final_third_local", "successful_passes_final_third_visitante"),
                                    "successful passes in final 3rd": ("successful_passes_final_third_local", "successful_passes_final_third_visitante"),
                                    "goal kicks": ("goal_kicks_local", "goal_kicks_visitante"),
                                    "goal kick": ("goal_kicks_local", "goal_kicks_visitante"),
                                    "throw ins": ("throw_ins_local", "throw_ins_visitante"),
                                    "throw in": ("throw_ins_local", "throw_ins_visitante"),
                                    "dangerous attacks": ("dangerous_attacks_local", "dangerous_attacks_visitante"),
                                }

                                distribution_stats = parsear_stats_tab(distribution_paragraphs, distribution_keywords, "Distribution")
                                stats.update(distribution_stats)

                            except TimeoutException:
                                log.debug("  × No se encontraron párrafos en tab Distribution")
                        else:
                            log.debug("  × Tab 'Distribution' no encontrado")

                    except Exception as e:
                        log.debug(f"  × Error procesando tab Distribution: {type(e).__name__}")

                    # ═══════════════════════════════════════════════════════════════════════
                    # FIN de captura de tabs adicionales
                    # ═══════════════════════════════════════════════════════════════════════

                    driver.switch_to.default_content()
                    break
                else:
                    log.debug(f"    × No se pudieron extraer estadísticas de este iframe")

            except (NoSuchElementException, StaleElementReferenceException, WebDriverException) as e:
                log.debug(f"  × Error en iframe #{idx+1}: {type(e).__name__}")
            finally:
                # Volver al contenido principal
                try:
                    driver.switch_to.default_content()
                except:
                    pass

    except Exception as e:
        log.debug(f"  × Error general extrayendo estadísticas: {e}")
    finally:
        # Asegurar que volvemos a la ventana principal
        try:
            driver.switch_to.window(original_window)
            driver.switch_to.default_content()
        except:
            pass

    return stats


def extraer_momentum(driver) -> dict:
    """
    Extrae valores de Momentum del gráfico visual de Betfair.

    Estrategia: En lugar de clickear tabs dentro de iframes anidados (poco fiable),
    encontramos la URL del iframe de stats y la abrimos directamente cambiando
    'summary' por 'momentum' en la URL. Esto carga el gráfico de momentum
    en una pestaña nueva donde podemos leer los div[height] directamente.

    Returns:
        dict: {"momentum_local": "XX.XX", "momentum_visitante": "YY.YY"}
    """
    momentum = {
        "momentum_local": "",
        "momentum_visitante": "",
    }

    original_window = driver.current_window_handle

    try:
        # PASO 1: Encontrar la URL del iframe de stats (statsperform.com)
        # La URL tiene formato: .../stats/live-stats/summary?eventId=XXX&outletkey=YYY...
        # Solo necesitamos reemplazar "summary" por "momentum"
        log.debug("  → Buscando URL del iframe de stats para Momentum...")

        stats_iframe_url = None

        # Buscar en iframes de la página
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for idx, iframe in enumerate(iframes):
            try:
                driver.switch_to.frame(iframe)

                # Buscar iframes anidados y leer su atributo src
                nested_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                for nested in nested_iframes:
                    try:
                        src = nested.get_attribute("src") or ""
                        if "stats/live-stats" in src:
                            stats_iframe_url = src
                            log.debug(f"  ✓ URL stats encontrada en iframe #{idx+1}: {src[:80]}")
                            break
                    except (StaleElementReferenceException, WebDriverException):
                        continue

                driver.switch_to.default_content()

                if stats_iframe_url:
                    break

            except (NoSuchElementException, StaleElementReferenceException, WebDriverException):
                try:
                    driver.switch_to.default_content()
                except:
                    pass

        if not stats_iframe_url:
            log.debug("  × No se encontró URL del iframe de stats")
            return momentum

        # PASO 2: Construir URL de momentum reemplazando el path
        momentum_url = re.sub(
            r"/stats/live-stats/[^?]+",
            "/stats/live-stats/momentum",
            stats_iframe_url,
        )
        log.debug(f"  → URL momentum construida: {momentum_url[:80]}")

        # PASO 3: Abrir URL de momentum en nueva pestaña (sin clickear nada)
        driver.execute_script("window.open(arguments[0]);", momentum_url)
        time.sleep(1)

        # Cambiar a la nueva pestaña
        new_handles = [h for h in driver.window_handles if h != original_window]
        if not new_handles:
            log.debug("  × No se pudo abrir nueva pestaña")
            return momentum

        driver.switch_to.window(new_handles[-1])
        time.sleep(3)  # Esperar a que cargue el gráfico completamente

        # Verificar que no hubo redirect (si momentum no está disponible, redirige a otra página)
        current_url = driver.current_url
        if "momentum" not in current_url:
            log.debug(f"  × Momentum no disponible (redirect a: {current_url[:80]})")
            driver.close()
            driver.switch_to.window(original_window)
            return momentum

        # PASO 4: Extraer div[height] directamente de la página (sin iframes!)
        result = driver.execute_script("""
            var divs = document.querySelectorAll('div[height]');
            var localH = [], visitH = [];
            for (var i = 0; i < divs.length; i++) {
                var h = divs[i].getAttribute('height');
                if (h === '0') continue;
                var val = parseFloat(h);
                if (isNaN(val)) continue;
                var bg = window.getComputedStyle(divs[i]).backgroundColor;
                if (bg.indexOf('42, 112, 233') !== -1) localH.push(val);
                else if (bg.indexOf('255, 128, 22') !== -1) visitH.push(val);
            }
            return {
                total: divs.length,
                localCount: localH.length,
                localSum: localH.reduce(function(a,b){return a+b;}, 0),
                visitCount: visitH.length,
                visitSum: visitH.reduce(function(a,b){return a+b;}, 0)
            };
        """)

        log.debug(f"  → Divs: {result['total']}, Local: {result['localCount']}, Visit: {result['visitCount']}")

        if result["localCount"] > 0 or result["visitCount"] > 0:
            if result["localCount"] > 0:
                momentum["momentum_local"] = f"{result['localSum']:.2f}"
                log.debug(f"  ✓ Momentum Local: {momentum['momentum_local']} ({result['localCount']} barras)")

            if result["visitCount"] > 0:
                momentum["momentum_visitante"] = f"{result['visitSum']:.2f}"
                log.debug(f"  ✓ Momentum Visitante: {momentum['momentum_visitante']} ({result['visitCount']} barras)")

        # Cerrar la pestaña de momentum y volver
        driver.close()
        driver.switch_to.window(original_window)

    except Exception as e:
        log.debug(f"  × Error extrayendo Momentum: {e}")

    finally:
        # Asegurar que volvemos a la ventana principal
        try:
            # Cerrar pestañas extras que hayan quedado abiertas
            for handle in driver.window_handles:
                if handle != original_window:
                    try:
                        driver.switch_to.window(handle)
                        driver.close()
                    except:
                        pass
            driver.switch_to.window(original_window)
            driver.switch_to.default_content()
        except:
            pass

    return momentum


def extraer_volumen(driver) -> str:
    """Extrae el volumen total matched del mercado."""
    for sel_group in [SELECTORES, SELECTORES_ALT]:
        texto = buscar_elemento_texto(driver, sel_group["matched_amount"], timeout=2)
        if texto:
            # Limpiar: "€1,234,567" -> "1234567"
            limpio = re.sub(r"[€$£\s,.]", "", texto)
            # Si tiene K/M multiplicar
            if "K" in texto.upper():
                try:
                    num = float(re.sub(r"[^\d.]", "", texto.replace(",", ".")))
                    return str(int(num * 1000))
                except ValueError:
                    pass
            elif "M" in texto.upper():
                try:
                    num = float(re.sub(r"[^\d.]", "", texto.replace(",", ".")))
                    return str(int(num * 1_000_000))
                except ValueError:
                    pass
            return limpio if limpio else ""
    return ""


# ── CSV Writer ───────────────────────────────────────────────────────────────

class CSVWriter:
    """Gestiona escritura de datos a CSVs individuales y unificado."""

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._archivos_abiertos = {}
        self._writers = {}
        self._inicializar_unificado()

    def _inicializar_unificado(self):
        """Crea/abre el archivo CSV unificado."""
        ruta = self.output_dir / "unificado.csv"
        existe = ruta.exists() and ruta.stat().st_size > 0
        self._f_unificado = open(ruta, "a", newline="", encoding="utf-8")
        self._w_unificado = csv.DictWriter(self._f_unificado, fieldnames=CSV_COLUMNS)
        if not existe:
            self._w_unificado.writeheader()
            self._f_unificado.flush()

    def escribir(self, tab_id: str, datos: dict):
        """Escribe una fila al CSV individual del partido y al unificado."""
        # CSV individual
        nombre = f"partido_{tab_id}.csv"
        ruta = self.output_dir / nombre

        if tab_id not in self._archivos_abiertos:
            existe = ruta.exists() and ruta.stat().st_size > 0
            f = open(ruta, "a", newline="", encoding="utf-8")
            w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            if not existe:
                w.writeheader()
                f.flush()
            self._archivos_abiertos[tab_id] = f
            self._writers[tab_id] = w

        self._writers[tab_id].writerow(datos)
        self._archivos_abiertos[tab_id].flush()

        # CSV unificado
        self._w_unificado.writerow(datos)
        self._f_unificado.flush()

    def cerrar(self):
        """Cierra todos los archivos abiertos."""
        for f in self._archivos_abiertos.values():
            try:
                f.close()
            except Exception:
                pass
        try:
            self._f_unificado.close()
        except Exception:
            pass
        log.info("Archivos CSV cerrados correctamente.")


# ── Driver Chrome ────────────────────────────────────────────────────────────

def crear_driver() -> webdriver.Chrome:
    """Crea instancia de Chrome con opciones anti-detección básicas."""
    opciones = Options()

    if HEADLESS:
        opciones.add_argument("--headless=new")

    # Si se usa perfil de Chrome existente
    if USE_CHROME_PROFILE:
        log.info(f"Usando perfil de Chrome: {CHROME_PROFILE_PATH}/{CHROME_PROFILE_NAME}")
        opciones.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
        opciones.add_argument(f"--profile-directory={CHROME_PROFILE_NAME}")
        # Opciones para acelerar inicio con perfil
        opciones.add_argument("--disable-session-crashed-bubble")
        opciones.add_argument("--disable-infobars")
        opciones.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        # IMPORTANTE: Con perfil de usuario, NO usar --disable-extensions (o no funcionará el login guardado)
    else:
        opciones.add_argument("--disable-extensions")

    opciones.add_argument(f"--user-agent={USER_AGENT}")
    opciones.add_argument(f"--lang={CHROME_LANG}")
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--window-size=1920,1080")
    opciones.add_argument("--start-maximized")
    # Optimización de memoria para múltiples tabs
    opciones.add_argument("--disable-gpu")
    opciones.add_argument("--disable-software-rasterizer")
    opciones.add_argument("--renderer-process-limit=6")
    opciones.add_argument("--js-flags=--max-old-space-size=512")

    # Evitar detección de Selenium
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)

    # Preferencias para idioma español
    if not USE_CHROME_PROFILE:  # Solo si NO usamos perfil (para no sobreescribir)
        opciones.add_experimental_option("prefs", {
            "intl.accept_languages": "es-ES,es",
            "profile.default_content_setting_values.notifications": 2,
        })

    # Usar webdriver-manager si está disponible
    if ChromeDriverManager is not None:
        try:
            servicio = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=servicio, options=opciones)
        except Exception as e:
            log.warning(f"webdriver-manager falló ({e}), intentando chromedriver del PATH...")
            driver = webdriver.Chrome(options=opciones)
    else:
        log.info("webdriver-manager no instalado, usando chromedriver del PATH.")
        driver = webdriver.Chrome(options=opciones)

    # Eliminar flag webdriver de navigator
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    # OPTIMIZACIÓN: Reducir implicit wait de 5s a 1s para evitar delays largos
    driver.implicitly_wait(1)
    return driver


# ── Sistema Multi-Driver Paralelo ────────────────────────────────────────────

def limpiar_ventanas_betfair_existentes():
    """
    Cierra todas las ventanas de Chrome con Betfair usando PowerShell.
    Solo cierra ventanas con "betfair" en el título, sin tocar el navegador normal del usuario.
    """
    import subprocess
    import platform
    import os

    try:
        if platform.system() == "Windows":
            log.info("🧹 Limpiando ventanas Betfair antiguas...")

            # Ejecutar el script PowerShell
            script_path = os.path.join(os.path.dirname(__file__), "close_betfair_windows.ps1")

            if not os.path.exists(script_path):
                log.warning(f"Script de limpieza no encontrado: {script_path}")
                return

            result = subprocess.run(
                ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", script_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Mostrar el output del script
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        log.info(f"  {line}")

            if result.returncode != 0 and result.stderr:
                log.warning(f"Error en script de limpieza: {result.stderr}")

        else:
            # Linux/Mac - usar pkill directamente
            log.info("🧹 Limpiando ventanas Betfair antiguas (Linux/Mac)...")
            try:
                subprocess.run(["pkill", "-9", "chromedriver"], capture_output=True, timeout=5)
                subprocess.run(["pkill", "-9", "-f", "chrome.*betfair"], capture_output=True, timeout=5)
                log.info("✓ Procesos de scraping limpiados")
            except Exception as e:
                log.debug(f"Error en limpieza: {e}")

    except Exception as e:
        log.warning(f"Error en limpieza de ventanas: {e}")
        # No es crítico, continuar de todas formas


class MatchDriver:
    """Encapsula un driver Chrome dedicado a un partido específico."""

    def __init__(self, url: str, game: str, fecha_hora_inicio=None):
        self.url = url
        self.game = game
        self.fecha_hora_inicio = fecha_hora_inicio
        self.match_id = extraer_id_partido(url)
        self.driver = None
        self.created_at = time.time()
        self.last_capture = None
        self._lock = threading.Lock()

    def iniciar(self):
        """Crea el driver Chrome y abre el partido."""
        try:
            log.info(f"🔧 Creando driver para: {self.game[:50]}")
            self.driver = crear_driver()
            self.driver.get(self.url)
            aceptar_cookies(self.driver)
            log.info(f"✓ Driver listo: {self.match_id}")
            return True
        except Exception as e:
            log.error(f"✗ Error creando driver para {self.match_id}: {e}")
            return False

    def cerrar(self):
        """Cierra el driver de forma segura."""
        try:
            if self.driver:
                self.driver.quit()
                log.debug(f"✓ Driver cerrado: {self.match_id}")
        except Exception as e:
            log.debug(f"Error cerrando driver {self.match_id}: {e}")
        finally:
            self.driver = None

    def capturar(self) -> dict:
        """Captura datos del partido usando el driver dedicado."""
        with self._lock:
            if not self.driver:
                log.error(f"Driver no disponible para {self.match_id}")
                return None

            try:
                # Mismo código que capturar_pestaña pero sin switch_to.window
                time.sleep(0.3)

                # Clic en botón "Actualizar"
                try:
                    actualizar_selectors = [
                        "//button[contains(text(), 'Actualizar')]",
                        "//button[contains(text(), 'Refresh')]",
                        "button[class*='refresh']",
                    ]

                    for selector in actualizar_selectors:
                        try:
                            if selector.startswith("//"):
                                boton = WebDriverWait(self.driver, 2).until(
                                    EC.element_to_be_clickable((By.XPATH, selector))
                                )
                            else:
                                boton = WebDriverWait(self.driver, 2).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                                )

                            boton.click()
                            log.debug(f"✓ Actualizar clickeado: {self.match_id}")
                            time.sleep(0.3)
                            break
                        except TimeoutException:
                            continue
                except Exception as e:
                    log.debug(f"Actualizar omitido para {self.match_id}: {e}")

                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

                # Extraer datos (mismo flujo que capturar_pestaña original)
                log.debug(f"[{self.match_id}] → Extrayendo información del partido...")
                info = extraer_info_partido(self.driver)

                log.debug(f"[{self.match_id}] → Extrayendo cuotas Match Odds...")
                odds_mo = extraer_runners_match_odds(self.driver)

                # MECANISMO F5: Si Match Odds críticos no se capturaron, refrescar y reintentar
                critical_fields_filled = sum([
                    bool(odds_mo["back_home"]),
                    bool(odds_mo["back_draw"]),
                    bool(odds_mo["back_away"])
                ])

                if critical_fields_filled < 2:
                    log.warning(f"⟳ [{self.match_id}] Match Odds incompletos ({critical_fields_filled}/3), refrescando...")
                    try:
                        self.driver.refresh()
                        time.sleep(3)
                        aceptar_cookies(self.driver)
                        time.sleep(1)
                        info = extraer_info_partido(self.driver)
                        odds_mo = extraer_runners_match_odds(self.driver)
                    except Exception as e:
                        log.error(f"Error al refrescar {self.match_id}: {e}")

                log.debug(f"[{self.match_id}] → Extrayendo cuotas Over/Under...")
                odds_ou = extraer_over_under(self.driver)

                log.debug(f"[{self.match_id}] → Extrayendo cuotas Resultado Correcto...")
                odds_rc = extraer_resultado_correcto(self.driver)

                log.debug(f"[{self.match_id}] → Extrayendo estadísticas del partido...")
                stats = extraer_estadisticas(self.driver)

                log.debug(f"[{self.match_id}] → Extrayendo volumen matched...")
                volumen = extraer_volumen(self.driver)

                log.debug(f"[{self.match_id}] → Extrayendo momentum...")
                momentum = extraer_momentum(self.driver)

                # Determinar estado del partido
                if info["estado_partido"]:
                    estado_partido = info["estado_partido"]
                elif info["minuto"] or (info["goles_local"] and info["goles_visitante"]):
                    estado_partido = "en_juego"
                else:
                    estado_partido = "pre_partido"

                # Combinar todos los datos (mismo formato que capturar_pestaña)
                datos = {
                    "tab_id": self.match_id,
                    "timestamp_utc": timestamp,
                    "evento": info["evento"],
                    "hora_comienzo": info["hora_comienzo"],
                    "estado_partido": estado_partido,
                    "minuto": info["minuto"],
                    "goles_local": info["goles_local"],
                    "goles_visitante": info["goles_visitante"],
                    # Match Odds
                    "back_home": odds_mo["back_home"],
                    "lay_home": odds_mo["lay_home"],
                    "back_draw": odds_mo["back_draw"],
                    "lay_draw": odds_mo["lay_draw"],
                    "back_away": odds_mo["back_away"],
                    "lay_away": odds_mo["lay_away"],
                    # Over/Under
                    **odds_ou,
                    # Resultado Correcto
                    **odds_rc,
                    # Estadísticas
                    **stats,
                    # Volumen y Momentum
                    "volumen_matched": volumen,
                    "momentum_local": momentum["momentum_local"],
                    "momentum_visitante": momentum["momentum_visitante"],
                    # Meta
                    "url": self.url,
                }

                self.last_capture = time.time()
                log.info(f"✓ [{self.match_id}] Captura exitosa: {estado_partido}, min {info['minuto']}, {info['goles_local']}-{info['goles_visitante']}")
                return datos

            except Exception as e:
                log.error(f"Error capturando {self.match_id}: {e}", exc_info=True)
                return None


def crear_match_driver(partido: dict) -> MatchDriver:
    """
    Crea un MatchDriver para un partido.
    partido: dict con keys 'url', 'game', 'fecha_hora_inicio'
    """
    md = MatchDriver(
        url=partido["url"],
        game=partido["game"],
        fecha_hora_inicio=partido.get("fecha_hora_inicio")
    )
    if md.iniciar():
        return md
    else:
        md.cerrar()
        return None


def capturar_match_driver(match_driver: MatchDriver) -> tuple:
    """
    Función worker para ThreadPoolExecutor.
    Retorna: (match_id, datos)
    """
    if not match_driver:
        return (None, None)

    try:
        datos = match_driver.capturar()
        return (match_driver.match_id, datos)
    except Exception as e:
        log.error(f"Error en thread de {match_driver.match_id}: {e}")
        return (match_driver.match_id, None)


def captura_paralela_multidriver(match_drivers: list, writer: CSVWriter):
    """
    Captura datos de todos los match_drivers en paralelo usando ThreadPoolExecutor.
    """
    if not match_drivers:
        return

    log.info(f"📸 Capturando {len(match_drivers)} partidos en paralelo...")
    inicio = time.time()

    with ThreadPoolExecutor(max_workers=len(match_drivers)) as executor:
        # Lanzar todas las capturas en paralelo
        futures = {
            executor.submit(capturar_match_driver, md): md
            for md in match_drivers
        }

        # Recoger resultados
        resultados = []
        for future in as_completed(futures):
            match_id, datos = future.result()
            if datos:
                writer.escribir(match_id, datos)
                resultados.append(match_id)

    duracion = time.time() - inicio
    log.info(f"✓ Captura paralela completada en {duracion:.1f}s ({len(resultados)}/{len(match_drivers)} exitosos)")


# ── Lógica principal ─────────────────────────────────────────────────────────

def aceptar_cookies(driver: webdriver.Chrome):
    """Intenta aceptar el banner de cookies automáticamente."""
    try:
        # Esperar un poco para que el banner de cookies aparezca
        time.sleep(0.5)  # Reducido de 2s a 0.5s

        # Selectores específicos para Betfair
        selectores_aceptar = [
            # XPath para texto exacto
            "//button[contains(text(), 'Aceptar todas las cookies')]",
            "//button[contains(text(), 'Permitir solo las cookies necesarias')]",
            # CSS genéricos
            "button[id*='onetrust-accept']",
            "button[id*='accept-recommended']",
            "#onetrust-accept-btn-handler",
            ".onetrust-close-btn-handler",
            "button.accept-all",
        ]

        for selector in selectores_aceptar:
            try:
                if selector.startswith("//"):
                    # Es un XPath
                    boton = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    # Es un CSS selector
                    boton = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                boton.click()
                log.info("✓ Cookies aceptadas automáticamente")
                time.sleep(1)
                return True

            except (NoSuchElementException, TimeoutException, WebDriverException):
                continue

        log.debug("No se encontró banner de cookies (puede que ya esté aceptado)")
        return False

    except Exception as e:
        log.debug(f"Error aceptando cookies: {e}")
        return False


def abrir_pestanas(driver: webdriver.Chrome, urls: list) -> list:
    """Abre una pestaña por cada URL. Devuelve lista de (handle, url, tab_id)."""
    tabs = []
    for i, url in enumerate(urls):
        if i == 0:
            # La primera pestaña ya existe
            driver.get(url)
            # Aceptar cookies en la primera pestaña
            aceptar_cookies(driver)
        else:
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(url)
            # Aceptar cookies en cada pestaña nueva también
            aceptar_cookies(driver)

        tab_id = extraer_id_partido(url)
        handle = driver.window_handles[-1]
        tabs.append({"handle": handle, "url": url, "tab_id": tab_id, "index": i, "opened_at": time.time()})
        log.info(f"Pestaña {i}: {tab_id} -> {url[:80]}...")
        time.sleep(0.5)  # Reducido de 2s a 0.5s

    return tabs


def capturar_pestaña(driver: webdriver.Chrome, tab_info: dict) -> dict:
    """Captura todos los datos de una pestaña. Devuelve dict con datos CSV."""
    try:
        driver.switch_to.window(tab_info["handle"])
    except WebDriverException as e:
        log.warning(f"Tab {tab_info['tab_id']} muerta ('no such window'). Intentando recuperar...")
        try:
            nueva_tab = abrir_tab_adicional(driver, tab_info["url"], tab_info["index"])
            if nueva_tab:
                tab_info["handle"] = nueva_tab["handle"]
                tab_info["opened_at"] = time.time()
                log.info(f"✓ Tab {tab_info['tab_id']} recuperada exitosamente")
            else:
                log.error(f"✗ No se pudo recuperar tab {tab_info['tab_id']}")
                return None
        except Exception as e2:
            log.error(f"✗ Error en recovery de tab {tab_info['tab_id']}: {e2}")
            return None

    # Pequeña espera para que cargue (reducida de 1s a 0.3s)
    time.sleep(0.3)

    # Clic en botón "Actualizar" para refrescar precios (OPTIMIZADO con explicit wait)
    try:
        actualizar_selectors = [
            "//button[contains(text(), 'Actualizar')]",
            "//button[contains(text(), 'Refresh')]",
            "button[class*='refresh']",
        ]

        actualizar_clicked = False
        for selector in actualizar_selectors:
            try:
                if selector.startswith("//"):
                    # XPath con timeout corto (2s en lugar de 5s implicit)
                    boton = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    # CSS con timeout corto
                    boton = WebDriverWait(driver, 2).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                boton.click()
                log.debug(f"✓ Clic en botón 'Actualizar' con selector: {selector[:30]}")
                time.sleep(0.3)
                actualizar_clicked = True
                break
            except TimeoutException:
                continue

        if not actualizar_clicked:
            log.debug("Botón 'Actualizar' no encontrado (probablemente no necesario)")

    except Exception as e:
        log.debug(f"Búsqueda de 'Actualizar' omitida: {e}")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Extraer datos
    log.info(f"[Tab {tab_info['index']}] → Extrayendo información del partido...")
    info = extraer_info_partido(driver)
    log.info(f"[Tab {tab_info['index']}] → Extrayendo cuotas Match Odds...")
    odds_mo = extraer_runners_match_odds(driver)
    log.info(f"[Tab {tab_info['index']}]   ✓ Match Odds: Home={odds_mo['back_home']}/{odds_mo['lay_home']} | Draw={odds_mo['back_draw']}/{odds_mo['lay_draw']} | Away={odds_mo['back_away']}/{odds_mo['lay_away']}")

    # MECANISMO F5: Si Match Odds críticos no se capturaron, refrescar y reintentar
    critical_fields_filled = sum([
        bool(odds_mo["back_home"]),
        bool(odds_mo["back_draw"]),
        bool(odds_mo["back_away"])
    ])

    if critical_fields_filled < 2:  # Si faltan 2 o más cuotas principales
        log.warning(f"⟳ Match Odds incompletos ({critical_fields_filled}/3), refrescando pestaña...")
        try:
            driver.refresh()
            time.sleep(3)  # Esperar a que recargue
            aceptar_cookies(driver)  # Por si aparece banner de nuevo
            time.sleep(1)

            # Reintentar extracción
            info = extraer_info_partido(driver)
            odds_mo = extraer_runners_match_odds(driver)

            critical_fields_filled_retry = sum([
                bool(odds_mo["back_home"]),
                bool(odds_mo["back_draw"]),
                bool(odds_mo["back_away"])
            ])

            if critical_fields_filled_retry > critical_fields_filled:
                log.info(f"✓ Refresco exitoso: {critical_fields_filled_retry}/3 cuotas capturadas")
            else:
                log.warning(f"⚠ Refresco no mejoró captura: {critical_fields_filled_retry}/3")

        except Exception as e:
            log.error(f"Error al refrescar pestaña: {e}")

    log.info(f"[Tab {tab_info['index']}] → Extrayendo cuotas Over/Under...")
    odds_ou = extraer_over_under(driver)
    ou_count = sum([1 for k, v in odds_ou.items() if v])
    log.info(f"[Tab {tab_info['index']}]   ✓ Over/Under: {ou_count}/20 valores capturados")

    log.info(f"[Tab {tab_info['index']}] → Extrayendo cuotas Resultado Correcto...")
    odds_rc = extraer_resultado_correcto(driver)
    rc_count = sum([1 for k, v in odds_rc.items() if v])
    log.info(f"[Tab {tab_info['index']}]   ✓ Resultado Correcto: {rc_count}/30 valores capturados")

    log.info(f"[Tab {tab_info['index']}] → Extrayendo estadísticas del partido...")
    stats = extraer_estadisticas(driver)
    stats_count = sum([1 for k, v in stats.items() if v])
    log.info(f"[Tab {tab_info['index']}]   ✓ Estadísticas: {stats_count}/54 valores capturados")
    log.info(f"[Tab {tab_info['index']}]     - Summary: xG {stats['xg_local']}/{stats['xg_visitante']} | Opta {stats['opta_points_local']}/{stats['opta_points_visitante']} | Posesión {stats['posesion_local']}/{stats['posesion_visitante']}")

    # Log de Attacking stats (si se capturaron)
    attacking_captured = sum([1 for k in ["big_chances_local", "shots_off_target_local", "attacks_local", "hit_woodwork_local"] if stats[k]])
    if attacking_captured > 0:
        log.info(f"[Tab {tab_info['index']}]     - Attacking: Big Chances {stats['big_chances_local']}/{stats['big_chances_visitante']} | Attacks {stats['attacks_local']}/{stats['attacks_visitante']}")

    # Log de Defence stats (si se capturaron)
    defence_captured = sum([1 for k in ["tackles_local", "duels_won_local", "saves_local", "interceptions_local"] if stats[k]])
    if defence_captured > 0:
        log.info(f"[Tab {tab_info['index']}]     - Defence: Tackles {stats['tackles_local']}/{stats['tackles_visitante']} | Duels Won {stats['duels_won_local']}/{stats['duels_won_visitante']}")

    # Log de Distribution stats (si se capturaron)
    distribution_captured = sum([1 for k in ["pass_success_pct_local", "crosses_local", "successful_passes_opp_half_local"] if stats[k]])
    if distribution_captured > 0:
        log.info(f"[Tab {tab_info['index']}]     - Distribution: Pass Success {stats['pass_success_pct_local']}/{stats['pass_success_pct_visitante']}% | Crosses {stats['crosses_local']}/{stats['crosses_visitante']}")

    log.info(f"[Tab {tab_info['index']}] → Extrayendo volumen matched...")
    volumen = extraer_volumen(driver)
    log.info(f"[Tab {tab_info['index']}]   ✓ Volumen: {volumen or 'No capturado'}")

    log.info(f"[Tab {tab_info['index']}] → Extrayendo momentum...")
    momentum = extraer_momentum(driver)
    momentum_count = sum([1 for v in momentum.values() if v])
    log.info(f"[Tab {tab_info['index']}]   ✓ Momentum: {momentum_count}/2 valores capturados")
    if momentum["momentum_local"] or momentum["momentum_visitante"]:
        log.info(f"[Tab {tab_info['index']}]     - Local: {momentum['momentum_local']} | Visitante: {momentum['momentum_visitante']}")

    # Determinar estado del partido
    # Primero intentar usar el estado detectado automáticamente
    if info["estado_partido"]:
        estado_partido = info["estado_partido"]
    # Si no se detectó automáticamente, inferir del minuto/marcador
    elif info["minuto"] or (info["goles_local"] and info["goles_visitante"]):
        estado_partido = "en_juego"
    else:
        estado_partido = "pre_partido"

    datos = {
        "tab_id": tab_info["tab_id"],
        "timestamp_utc": timestamp,
        "evento": info["evento"],
        "hora_comienzo": info["hora_comienzo"],
        "estado_partido": estado_partido,
        "minuto": info["minuto"],
        "goles_local": info["goles_local"],
        "goles_visitante": info["goles_visitante"],
        # Match Odds
        "back_home": odds_mo["back_home"],
        "lay_home": odds_mo["lay_home"],
        "back_draw": odds_mo["back_draw"],
        "lay_draw": odds_mo["lay_draw"],
        "back_away": odds_mo["back_away"],
        "lay_away": odds_mo["lay_away"],
        # Over/Under 0.5
        "back_over05": odds_ou["back_over05"],
        "lay_over05": odds_ou["lay_over05"],
        "back_under05": odds_ou["back_under05"],
        "lay_under05": odds_ou["lay_under05"],
        # Over/Under 1.5
        "back_over15": odds_ou["back_over15"],
        "lay_over15": odds_ou["lay_over15"],
        "back_under15": odds_ou["back_under15"],
        "lay_under15": odds_ou["lay_under15"],
        # Over/Under 2.5
        "back_over25": odds_ou["back_over25"],
        "lay_over25": odds_ou["lay_over25"],
        "back_under25": odds_ou["back_under25"],
        "lay_under25": odds_ou["lay_under25"],
        # Over/Under 3.5
        "back_over35": odds_ou["back_over35"],
        "lay_over35": odds_ou["lay_over35"],
        "back_under35": odds_ou["back_under35"],
        "lay_under35": odds_ou["lay_under35"],
        # Over/Under 4.5
        "back_over45": odds_ou["back_over45"],
        "lay_over45": odds_ou["lay_over45"],
        "back_under45": odds_ou["back_under45"],
        "lay_under45": odds_ou["lay_under45"],
        # Resultado Correcto
        "back_rc_0_0": odds_rc["back_rc_0_0"],
        "lay_rc_0_0": odds_rc["lay_rc_0_0"],
        "back_rc_1_0": odds_rc["back_rc_1_0"],
        "lay_rc_1_0": odds_rc["lay_rc_1_0"],
        "back_rc_0_1": odds_rc["back_rc_0_1"],
        "lay_rc_0_1": odds_rc["lay_rc_0_1"],
        "back_rc_1_1": odds_rc["back_rc_1_1"],
        "lay_rc_1_1": odds_rc["lay_rc_1_1"],
        "back_rc_2_0": odds_rc["back_rc_2_0"],
        "lay_rc_2_0": odds_rc["lay_rc_2_0"],
        "back_rc_0_2": odds_rc["back_rc_0_2"],
        "lay_rc_0_2": odds_rc["lay_rc_0_2"],
        "back_rc_2_1": odds_rc["back_rc_2_1"],
        "lay_rc_2_1": odds_rc["lay_rc_2_1"],
        "back_rc_1_2": odds_rc["back_rc_1_2"],
        "lay_rc_1_2": odds_rc["lay_rc_1_2"],
        "back_rc_2_2": odds_rc["back_rc_2_2"],
        "lay_rc_2_2": odds_rc["lay_rc_2_2"],
        "back_rc_3_0": odds_rc["back_rc_3_0"],
        "lay_rc_3_0": odds_rc["lay_rc_3_0"],
        "back_rc_0_3": odds_rc["back_rc_0_3"],
        "lay_rc_0_3": odds_rc["lay_rc_0_3"],
        "back_rc_3_1": odds_rc["back_rc_3_1"],
        "lay_rc_3_1": odds_rc["lay_rc_3_1"],
        "back_rc_1_3": odds_rc["back_rc_1_3"],
        "lay_rc_1_3": odds_rc["lay_rc_1_3"],
        "back_rc_3_2": odds_rc["back_rc_3_2"],
        "lay_rc_3_2": odds_rc["lay_rc_3_2"],
        "back_rc_2_3": odds_rc["back_rc_2_3"],
        "lay_rc_2_3": odds_rc["lay_rc_2_3"],
        # Estadísticas
        "xg_local": stats["xg_local"],
        "xg_visitante": stats["xg_visitante"],
        "opta_points_local": stats["opta_points_local"],
        "opta_points_visitante": stats["opta_points_visitante"],
        "posesion_local": stats["posesion_local"],
        "posesion_visitante": stats["posesion_visitante"],
        "tiros_local": stats["tiros_local"],
        "tiros_visitante": stats["tiros_visitante"],
        "tiros_puerta_local": stats["tiros_puerta_local"],
        "tiros_puerta_visitante": stats["tiros_puerta_visitante"],
        "touches_box_local": stats["touches_box_local"],
        "touches_box_visitante": stats["touches_box_visitante"],
        "corners_local": stats["corners_local"],
        "corners_visitante": stats["corners_visitante"],
        "total_passes_local": stats["total_passes_local"],
        "total_passes_visitante": stats["total_passes_visitante"],
        "tarjetas_amarillas_local": stats["tarjetas_amarillas_local"],
        "tarjetas_amarillas_visitante": stats["tarjetas_amarillas_visitante"],
        "tarjetas_rojas_local": stats["tarjetas_rojas_local"],
        "tarjetas_rojas_visitante": stats["tarjetas_rojas_visitante"],
        "booking_points_local": stats["booking_points_local"],
        "booking_points_visitante": stats["booking_points_visitante"],
        # Attacking stats
        "big_chances_local": stats["big_chances_local"],
        "big_chances_visitante": stats["big_chances_visitante"],
        "shots_off_target_local": stats["shots_off_target_local"],
        "shots_off_target_visitante": stats["shots_off_target_visitante"],
        "attacks_local": stats["attacks_local"],
        "attacks_visitante": stats["attacks_visitante"],
        "hit_woodwork_local": stats["hit_woodwork_local"],
        "hit_woodwork_visitante": stats["hit_woodwork_visitante"],
        # Defence stats
        "tackles_local": stats["tackles_local"],
        "tackles_visitante": stats["tackles_visitante"],
        "tackle_success_pct_local": stats["tackle_success_pct_local"],
        "tackle_success_pct_visitante": stats["tackle_success_pct_visitante"],
        "duels_won_local": stats["duels_won_local"],
        "duels_won_visitante": stats["duels_won_visitante"],
        "aerial_duels_won_local": stats["aerial_duels_won_local"],
        "aerial_duels_won_visitante": stats["aerial_duels_won_visitante"],
        "clearance_local": stats["clearance_local"],
        "clearance_visitante": stats["clearance_visitante"],
        "saves_local": stats["saves_local"],
        "saves_visitante": stats["saves_visitante"],
        "interceptions_local": stats["interceptions_local"],
        "interceptions_visitante": stats["interceptions_visitante"],
        # Distribution stats
        "pass_success_pct_local": stats["pass_success_pct_local"],
        "pass_success_pct_visitante": stats["pass_success_pct_visitante"],
        "crosses_local": stats["crosses_local"],
        "crosses_visitante": stats["crosses_visitante"],
        "successful_crosses_pct_local": stats["successful_crosses_pct_local"],
        "successful_crosses_pct_visitante": stats["successful_crosses_pct_visitante"],
        "successful_passes_opp_half_local": stats["successful_passes_opp_half_local"],
        "successful_passes_opp_half_visitante": stats["successful_passes_opp_half_visitante"],
        "successful_passes_final_third_local": stats["successful_passes_final_third_local"],
        "successful_passes_final_third_visitante": stats["successful_passes_final_third_visitante"],
        "momentum_local": momentum["momentum_local"],
        "momentum_visitante": momentum["momentum_visitante"],
        # Volumen y meta
        "volumen_matched": volumen,
        "url": tab_info["url"],
    }

    # Log resumen
    # Emojis según estado: ⚽ en juego, ☕ descanso, 🏁 finalizado, ⏰ pre-partido
    if estado_partido == "en_juego":
        estado_emoji = "⚽"
    elif estado_partido == "descanso":
        estado_emoji = "☕"
    elif estado_partido == "finalizado":
        estado_emoji = "🏁"
    else:
        estado_emoji = "⏰"

    resumen = (
        f"[Tab {tab_info['index']}] {estado_emoji} {info['evento'] or tab_info['tab_id']} "
        f"| {estado_partido.upper()} | Min:{info['minuto'] or '?'} "
        f"| {info['goles_local'] or '?'}-{info['goles_visitante'] or '?'} "
        f"| BH:{odds_mo['back_home'] or '-'} LH:{odds_mo['lay_home'] or '-'}"
    )
    log.info(resumen)

    return datos


def ciclo_captura(driver: webdriver.Chrome, tabs: list, writer: CSVWriter):
    """Ejecuta un ciclo completo de captura en todas las pestañas."""
    for tab_info in tabs:
        if not ejecutando:
            break

        datos = capturar_pestaña(driver, tab_info)
        if datos:
            writer.escribir(tab_info["tab_id"], datos)

        # Delay aleatorio entre pestañas (anti-bot)
        if tab_info != tabs[-1]:  # No esperar después de la última
            delay = uniform(DELAY_MIN_SEG, DELAY_MAX_SEG)
            log.debug(f"Espera {delay:.1f}s antes de siguiente pestaña...")
            time.sleep(delay)


def detectar_cambios_games(tabs_actuales: list, ruta_csv: str = "games.csv", ventana_antes_min: int = 10, ventana_despues_min: int = 150) -> tuple:
    """
    Compara las tabs actuales con games.csv considerando horarios de partidos.
    Retorna: (partidos_a_abrir, tabs_a_cerrar)

    - partidos_a_abrir: Partidos que deben estar siendo trackeados pero no tienen tab abierta
    - tabs_a_cerrar: Tabs que deben cerrarse (partido finalizado o removido del CSV)
    """
    # Leer partidos del CSV
    partidos_csv = leer_games_csv(ruta_csv)
    if partidos_csv is None:
        log.warning("No se pudo leer games.csv, manteniendo tabs actuales")
        return ([], [])

    # Filtrar partidos activos según horario
    partidos_activos, partidos_futuros, partidos_finalizados = filtrar_partidos_activos(
        partidos_csv, ventana_antes_min, ventana_despues_min
    )

    # Log de estado de partidos
    if partidos_futuros:
        log.debug(f"⏰ Partidos futuros: {len(partidos_futuros)}")
        for p in partidos_futuros:
            tiempo_hasta = (p["fecha_hora_inicio"] - datetime.now()).total_seconds() / 60
            log.debug(f"   - {p['game'][:40]} (en {tiempo_hasta:.0f} min)")

    if partidos_finalizados:
        log.debug(f"✅ Partidos finalizados: {len(partidos_finalizados)}")

    # Extraer URLs de tabs actuales y partidos activos
    urls_actuales = {tab["url"] for tab in tabs_actuales}
    urls_activas = {p["url"] for p in partidos_activos}

    # Detectar nuevos partidos a abrir (activos pero sin tab)
    partidos_a_abrir = [p for p in partidos_activos if p["url"] not in urls_actuales]

    # Detectar tabs a cerrar (tabs que NO están en partidos activos)
    tabs_a_cerrar = [tab for tab in tabs_actuales if tab["url"] not in urls_activas]

    return (partidos_a_abrir, tabs_a_cerrar)


def abrir_tab_adicional(driver: webdriver.Chrome, url: str, nuevo_index: int) -> dict:
    """
    Abre una nueva tab para una URL específica.
    Retorna: tab_info dict
    """
    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(url)
        aceptar_cookies(driver)

        tab_id = extraer_id_partido(url)
        handle = driver.current_window_handle
        tab_info = {"handle": handle, "url": url, "tab_id": tab_id, "index": nuevo_index, "opened_at": time.time()}

        log.info(f"✓ Nueva pestaña añadida: {tab_id} -> {url[:80]}...")
        time.sleep(0.5)

        return tab_info
    except Exception as e:
        log.error(f"Error abriendo nueva tab para {url[:80]}: {e}")
        return None


def cerrar_tab_partido(driver: webdriver.Chrome, tab_info: dict):
    """
    Cierra una tab específica.
    """
    try:
        driver.switch_to.window(tab_info["handle"])
        driver.close()
        log.info(f"✓ Pestaña cerrada: {tab_info['tab_id']}")
    except Exception as e:
        log.warning(f"Error cerrando tab {tab_info['tab_id']}: {e}")


def main():
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Observador de cuotas Betfair Exchange - Multi-pestaña"
    )
    parser.add_argument(
        "--urls", nargs="+", default=None,
        help="URLs de partidos (sobreescribe config.py)"
    )
    parser.add_argument(
        "--ciclo", type=int, default=CICLO_TOTAL_SEG,
        help=f"Segundos entre ciclos (default: {CICLO_TOTAL_SEG})"
    )
    parser.add_argument(
        "--login-wait", type=int, default=PAUSA_LOGIN_SEG,
        help=f"Segundos para login manual (default: {PAUSA_LOGIN_SEG})"
    )
    parser.add_argument(
        "--output", type=str, default=OUTPUT_DIR,
        help=f"Directorio de salida CSV (default: {OUTPUT_DIR})"
    )
    parser.add_argument(
        "--reload-interval", type=int, default=5,
        help="Cada cuántos ciclos revisar games.csv para detectar cambios (default: 5, 0=desactivar)"
    )
    parser.add_argument(
        "--ventana-antes", type=int, default=10,
        help="Minutos antes del inicio del partido para empezar a trackear (default: 10)"
    )
    parser.add_argument(
        "--ventana-despues", type=int, default=150,
        help="Minutos después del inicio del partido para dejar de trackear (default: 150)"
    )
    parser.add_argument(
        "--max-tabs", type=int, default=8,
        help="[DEPRECADO] Sistema multi-driver no usa límite de tabs. Cada partido = 1 Chrome independiente."
    )
    args = parser.parse_args()

    # Prioridad: 1) --urls, 2) games.csv, 3) config.MATCH_URLS
    urls_iniciales = []
    usar_scheduling = False

    if args.urls:
        # URLs desde línea de comandos: sin scheduling
        urls_iniciales = args.urls
        log.info("Usando URLs desde línea de comandos (sin scheduling)")
    else:
        # Intentar leer games.csv
        partidos_csv = leer_games_csv("games.csv")
        if partidos_csv:
            # Filtrar partidos activos según horarios
            partidos_activos, partidos_futuros, partidos_finalizados = filtrar_partidos_activos(
                partidos_csv, args.ventana_antes, args.ventana_despues
            )

            # Determinar si hay algún partido con fecha_hora_inicio
            usar_scheduling = any(p["fecha_hora_inicio"] is not None for p in partidos_csv)

            if usar_scheduling:
                log.info("📅 MODO SCHEDULING ACTIVADO")
                log.info(f"   Ventana tracking: {args.ventana_antes} min antes → {args.ventana_despues} min después")
                log.info(f"   Total en CSV: {len(partidos_csv)} partidos")
                log.info(f"   ✓ Partidos activos ahora: {len(partidos_activos)}")
                log.info(f"   ⏰ Partidos futuros: {len(partidos_futuros)}")
                log.info(f"   ✅ Partidos finalizados: {len(partidos_finalizados)}")

                # Mostrar próximos partidos
                if partidos_futuros:
                    log.info("\n📋 Próximos partidos a trackear:")
                    for p in sorted(partidos_futuros, key=lambda x: x["fecha_hora_inicio"])[:5]:
                        tiempo_hasta = (p["fecha_hora_inicio"] - datetime.now()).total_seconds() / 60
                        log.info(f"      {p['game'][:50]} (en {tiempo_hasta:.0f} min)")

                if not partidos_activos and not partidos_futuros:
                    log.warning("⚠️  No hay partidos activos ni futuros para trackear.")
                    log.warning("   El script esperará a que llegue la hora de algún partido...")

            urls_iniciales = [p["url"] for p in partidos_activos]
            # NOTA: Sistema multi-driver NO requiere límite max_tabs
            # Cada partido tiene su propio Chrome independiente
            log.info(f"🚀 Sistema multi-driver: Creando {len(urls_iniciales)} drivers independientes (sin límite de tabs)")
        else:
            # Fallback a config.MATCH_URLS
            urls_iniciales = MATCH_URLS
            if urls_iniciales:
                log.info("Usando URLs desde config.MATCH_URLS (sin scheduling)")

    if not urls_iniciales and not usar_scheduling:
        log.error("No hay URLs configuradas. Crea games.csv, edita config.py o usa --urls.")
        sys.exit(1)

    log.info(f"\nIniciando observador con {len(urls_iniciales)} partidos.")
    log.info(f"Ciclo: {args.ciclo}s | Output: {args.output}/")
    if args.reload_interval > 0:
        modo_reload = "scheduling" if usar_scheduling else "detección de cambios"
        log.info(f"🔄 Recarga dinámica: Revisando games.csv cada {args.reload_interval} ciclos ({modo_reload})")
    else:
        log.info("🔄 Recarga dinámica: Desactivada")

    # Limpiar ventanas Betfair antiguas antes de crear nuevos drivers
    limpiar_ventanas_betfair_existentes()

    # Crear lista de partidos inicial para MatchDrivers
    partidos_csv = leer_games_csv("games.csv")
    partidos_activos, _, _ = filtrar_partidos_activos(
        partidos_csv, args.ventana_antes, args.ventana_despues
    ) if partidos_csv else ([], [], [])

    # Si no hay scheduling, crear partidos desde urls_iniciales
    if not usar_scheduling and urls_iniciales:
        partidos_activos = [
            {"url": url, "game": extraer_id_partido(url), "fecha_hora_inicio": None}
            for url in urls_iniciales
        ]

    # Crear MatchDrivers para partidos activos (sin límite max_tabs)
    log.info(f"\n🚀 Iniciando {len(partidos_activos)} drivers Chrome (sistema multi-driver paralelo)...")
    match_drivers = {}
    driver_login = None  # Driver para login manual

    try:
        # Crear primer driver para login manual
        if partidos_activos:
            primer_partido = partidos_activos[0]
            log.info(f"🔧 Creando driver de login: {primer_partido['game'][:50]}")
            driver_login = MatchDriver(
                url=primer_partido["url"],
                game=primer_partido["game"],
                fecha_hora_inicio=primer_partido.get("fecha_hora_inicio")
            )
            if driver_login.iniciar():
                match_drivers[driver_login.match_id] = driver_login

        if not match_drivers and not usar_scheduling:
            log.error("No se pudo crear ningún driver. Abortando.")
            return

        # Espera para login manual
        log.info("=" * 60)
        log.info(f"HAZ LOGIN MANUAL en Betfair.es ahora.")
        log.info(f"Tienes {args.login_wait} segundos...")
        log.info("El scraper comenzará automáticamente después.")
        log.info("=" * 60)

        # Cuenta atrás visible
        for i in range(args.login_wait, 0, -10):
            if not ejecutando:
                break
            log.info(f"  Comenzando en {i}s...")
            time.sleep(min(10, i))

        if not ejecutando:
            log.info("Cancelado antes de iniciar.")
            return

        # Crear resto de drivers en paralelo
        if len(partidos_activos) > 1:
            log.info(f"🔧 Creando {len(partidos_activos) - 1} drivers adicionales en paralelo...")

            def crear_driver_worker(partido):
                md = crear_match_driver(partido)
                return (partido["url"], md) if md else (partido["url"], None)

            with ThreadPoolExecutor(max_workers=min(8, len(partidos_activos) - 1)) as executor:
                futures = [
                    executor.submit(crear_driver_worker, p)
                    for p in partidos_activos[1:]
                ]

                for future in as_completed(futures):
                    url, md = future.result()
                    if md:
                        match_drivers[md.match_id] = md

        log.info(f"✓ {len(match_drivers)} drivers creados exitosamente")

        # Iniciar CSV writer
        writer = CSVWriter(args.output)
        ciclo_num = 0

        log.info("=" * 60)
        log.info("CAPTURA INICIADA - Presiona Ctrl+C para detener")
        log.info("=" * 60)

        # Loop principal
        while ejecutando:
            ciclo_num += 1
            inicio_ciclo = time.time()

            log.info(f"\n--- Ciclo #{ciclo_num} ---")

            # Captura paralela de todos los match_drivers
            if match_drivers:
                captura_paralela_multidriver(list(match_drivers.values()), writer)
            else:
                log.info("⏰ Sin partidos activos para capturar en este ciclo")

            # Recarga periódica de games.csv para detectar cambios
            if args.reload_interval > 0 and ciclo_num % args.reload_interval == 0:
                log.info(f"🔄 Revisando games.csv para detectar cambios...")

                partidos_csv = leer_games_csv("games.csv")
                if partidos_csv:
                    partidos_activos_nuevos, _, _ = filtrar_partidos_activos(
                        partidos_csv, args.ventana_antes, args.ventana_despues
                    )

                    # Identificar drivers a cerrar (partidos finalizados)
                    urls_activas = {p["url"] for p in partidos_activos_nuevos}
                    drivers_a_cerrar = [
                        match_id for match_id, md in match_drivers.items()
                        if md.url not in urls_activas
                    ]

                    if drivers_a_cerrar:
                        log.info(f"🗑️  Cerrando {len(drivers_a_cerrar)} drivers de partidos finalizados...")
                        for match_id in drivers_a_cerrar:
                            md = match_drivers.pop(match_id)
                            md.cerrar()
                            log.debug(f"   - Cerrado: {match_id}")

                    # Identificar partidos nuevos a abrir
                    urls_existentes = {md.url for md in match_drivers.values()}
                    partidos_nuevos = [
                        p for p in partidos_activos_nuevos
                        if p["url"] not in urls_existentes
                    ]

                    if partidos_nuevos:
                        log.info(f"➕ Abriendo {len(partidos_nuevos)} nuevos partidos...")

                        with ThreadPoolExecutor(max_workers=min(8, len(partidos_nuevos))) as executor:
                            futures = [
                                executor.submit(crear_match_driver, p)
                                for p in partidos_nuevos
                            ]

                            for future in as_completed(futures):
                                md = future.result()
                                if md:
                                    match_drivers[md.match_id] = md
                                    log.info(f"   - {md.game[:40]}")

                    if drivers_a_cerrar or partidos_nuevos:
                        log.info(f"✓ Drivers actualizados: {len(match_drivers)} partidos activos")

            # Calcular tiempo restante del ciclo
            duracion = time.time() - inicio_ciclo
            espera = max(0, args.ciclo - duracion)

            if espera > 0 and ejecutando:
                log.info(
                    f"Ciclo completado en {duracion:.1f}s. "
                    f"Esperando {espera:.1f}s para siguiente ciclo..."
                )
                # Esperar en intervalos pequeños para responder rápido a Ctrl+C
                esperado = 0
                while esperado < espera and ejecutando:
                    time.sleep(min(1, espera - esperado))
                    esperado += 1
            else:
                log.warning(
                    f"Ciclo tardó {duracion:.1f}s (> {args.ciclo}s). "
                    f"Iniciando siguiente ciclo inmediatamente."
                )

    except KeyboardInterrupt:
        log.info("Interrupción manual detectada.")
    except Exception as e:
        log.error(f"Error fatal: {e}", exc_info=True)
    finally:
        log.info("Cerrando...")
        try:
            writer.cerrar()
        except Exception:
            pass

        # Cerrar todos los match_drivers
        log.info(f"🔧 Cerrando {len(match_drivers)} drivers...")
        for match_id, md in match_drivers.items():
            try:
                md.cerrar()
            except Exception:
                pass
        log.info("Observador finalizado. Revisa los CSV en la carpeta de salida.")


if __name__ == "__main__":
    main()
