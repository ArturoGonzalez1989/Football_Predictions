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

# Importar el nuevo módulo de Stats API
from stats_api import extract_event_id, get_all_stats, extract_stat_value

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

# ── Mapeo de País y Liga (URL-based) ─────────────────────────────────────────
from urllib.parse import unquote

URL_LEAGUE_MAPPING = {
    # España
    'la-liga-española': ('España', 'La Liga'),
    'segunda-división-española': ('España', 'Segunda División'),
    'espa%C3%B1a-segunda-divisi%C3%B3n': ('España', 'Segunda División'),
    'españa-segunda-división': ('España', 'Segunda División'),
    'copa-del-rey': ('España', 'Copa del Rey'),
    # Inglaterra
    'fa-cup-inglesa': ('Inglaterra', 'FA Cup'),
    'liga-premiership-inglesa': ('Inglaterra', 'Premier League'),
    'championship-inglés': ('Inglaterra', 'Championship'),
    'league-one-inglés': ('Inglaterra', 'League One'),
    'league-two-inglés': ('Inglaterra', 'League Two'),
    'carabao-cup': ('Inglaterra', 'Carabao Cup'),
    'women-super-league': ('Inglaterra', "Women's Super League"),
    'inglaterra-sky-bet-league-1': ('Inglaterra', 'League One'),
    'inglaterra-sky-bet-league-2': ('Inglaterra', 'League Two'),
    'inglaterra-sky-bet-championship': ('Inglaterra', 'Championship'),
    # Alemania
    'bundesliga': ('Alemania', 'Bundesliga'),
    '2-bundesliga': ('Alemania', '2. Bundesliga'),
    'dfb-pokal': ('Alemania', 'DFB-Pokal'),
    # Italia
    'serie-a-italiana': ('Italia', 'Serie A'),
    'serie-b-italiana': ('Italia', 'Serie B'),
    'coppa-italia': ('Italia', 'Coppa Italia'),
    'serie-a-brasil': ('Brasil', 'Série A'),
    'serie-b-brasil': ('Brasil', 'Série B'),
    # Francia
    'ligue-1-francesa': ('Francia', 'Ligue 1'),
    'ligue-2-francesa': ('Francia', 'Ligue 2'),
    'copa-francesa': ('Francia', 'Coupe de France'),
    # Portugal
    'liga-portuguesa': ('Portugal', 'Primeira Liga'),
    'portugal-primeira-liga': ('Portugal', 'Primeira Liga'),
    'segunda-liga-portuguesa': ('Portugal', 'Segunda Liga'),
    'taça-portugal': ('Portugal', 'Taça de Portugal'),
    'taça-da-liga-portuguesa': ('Portugal', 'Taça da Liga'),
    # Holanda
    'eredivisie-holandesa': ('Holanda', 'Eredivisie'),
    'eerste-divisie': ('Holanda', 'Eerste Divisie'),
    'knvb-beker': ('Holanda', 'KNVB Beker'),
    # Bélgica
    'jupiler-league-pro': ('Bélgica', 'Jupiler Pro League'),
    'b%C3%A9lgica-pro-league': ('Bélgica', 'Jupiler Pro League'),
    'bélgica-pro-league': ('Bélgica', 'Jupiler Pro League'),
    'primera-división-belga': ('Bélgica', 'Primera División'),
    'copa-belga': ('Bélgica', 'Copa Belga'),
    # Suiza
    'super-league-suiza': ('Suiza', 'Super League'),
    'challenge-league-suiza': ('Suiza', 'Challenge League'),
    'copa-suiza': ('Suiza', 'Copa Suiza'),
    # Austria
    'bundesliga-austriaca': ('Austria', 'Bundesliga'),
    'segunda-liga-austriaca': ('Austria', 'Segunda Liga'),
    # República Checa
    'liga-checa': ('República Checa', 'Liga Checa'),
    # Dinamarca
    'superligaen-danesa': ('Dinamarca', 'Superligaen'),
    'dinamarca-superliga': ('Dinamarca', 'Superligaen'),
    'primera-división-danesa': ('Dinamarca', 'Primera División'),
    # Grecia
    'super-league-griega': ('Grecia', 'Super League'),
    'segunda-división-griega': ('Grecia', 'Segunda División'),
    # Turquía
    'superlig-turca': ('Turquía', 'Süper Lig'),
    'superliga-turca': ('Turquía', 'Süper Lig'),
    'primera-división-turca': ('Turquía', 'Primera División'),
    # Bulgaria
    'primera-división-búlgara': ('Bulgaria', 'Primera División'),
    'liga-a-b%C3%BAlgara': ('Bulgaria', 'Liga A'),
    'liga-a-búlgara': ('Bulgaria', 'Liga A'),
    'segunda-división-búlgara': ('Bulgaria', 'Segunda División'),
    # Rumania
    'liga-1-rumana': ('Rumania', 'Liga 1'),
    'romanian-liga-i': ('Rumania', 'Liga 1'),
    # Japón
    'j-league': ('Japón', 'J-League'),
    'j-league-2': ('Japón', 'J-League 2'),
    'japanese-j-league': ('Japón', 'J-League'),
    # Indonesia
    'liga-indonesia': ('Indonesia', 'Liga Indonesia'),
    'indonesia-super-league': ('Indonesia', 'Super League'),
    # América del Sur - Internacional
    'conmebol-copa-libertadores': ('Internacional', 'Copa Libertadores'),
    'conmebol-copa-sudamericana': ('Internacional', 'Copa Sudamericana'),
    'copa-argentina': ('Argentina', 'Copa Argentina'),
    'copa-brasil': ('Brasil', 'Copa do Brasil'),
    # Argentina
    'liga-argentina': ('Argentina', 'Liga Argentina'),
    'argentina-primera-divisi%C3%B3n': ('Argentina', 'Liga Argentina'),
    'argentina-primera-división': ('Argentina', 'Liga Argentina'),
    # Brasil
    'primeira-divisão-brasil': ('Brasil', 'Série A'),
    'paulista-seria-a1-brasil': ('Brasil', 'Paulista Serie A1'),
    # Chile
    'liga-chilena': ('Chile', 'Primera División'),
    'chile-primera-divisi%C3%B3n': ('Chile', 'Primera División'),
    'chile-primera-división': ('Chile', 'Primera División'),
    # Colombia
    'colombia-primera-a': ('Colombia', 'Liga Colombiana'),
    'liga-colombiana': ('Colombia', 'Liga Colombiana'),
    # Ecuador
    'liga-ecuatoriana': ('Ecuador', 'Liga Ecuatoriana'),
    # Perú
    'liga-peruana': ('Perú', 'Liga Peruana'),
    # Uruguay
    'liga-uruguaya': ('Uruguay', 'Liga Uruguaya'),
    'uruguayan-primera-division': ('Uruguay', 'Liga Uruguaya'),
    # Paraguay
    'liga-paraguaya': ('Paraguay', 'Liga Paraguaya'),
    # Bolivia
    'liga-boliviana': ('Bolivia', 'Liga Boliviana'),
    # Venezuela
    'liga-venezolana': ('Venezuela', 'Liga Venezolana'),
    # México
    'liga-mexicana': ('México', 'Liga Mexicana'),
    'liga-mx': ('México', 'Liga MX'),
    # Escocia
    'premiership-escocesa': ('Escocia', 'Premiership'),
    # Corea del Sur
    'k-league': ('Corea del Sur', 'K-League'),
    # Oriente Medio
    'saudi-pro-league': ('Arabia Saudita', 'Saudi Pro League'),
    'saudi-arabia': ('Arabia Saudita', 'Saudi Pro League'),
    'uae-pro-league': ('Emiratos Árabes Unidos', 'UAE Pro League'),
    'qatar-stars-league': ('Qatar', 'Qatar Stars League'),
    'iraqi-premier-league': ('Irak', 'Iraqi Premier League'),
    'iran-pro-league': ('Irán', 'Iran Pro League'),
    # Competiciones Asiáticas
    'champions-league-asiática': ('Internacional', 'AFC Champions League'),
    'champions-league-asi%C3%A1tica': ('Internacional', 'AFC Champions League'),
    # Chipre
    '1st-division-chipre': ('Chipre', 'Primera División'),
    # Egipto
    'egipto-premier-league': ('Egipto', 'Premier League'),
    # Eslovenia
    'premier-league-eslovena': ('Eslovenia', 'Premier League'),
    # ── Añadidos para cubrir "Desconocido" (2026-03-07) ──
    # Arabia Saudita
    'arabia-saudí-liga-profesional': ('Arabia Saudita', 'Saudi Pro League'),
    'arabia-saud%C3%AD-liga-profesional': ('Arabia Saudita', 'Saudi Pro League'),
    # USA - MLS
    'estados-unidos-major-league-soccer': ('USA', 'MLS'),
    'major-league-soccer': ('USA', 'MLS'),
    # Inglaterra (variante URL)
    'premier-league-inglesa': ('Inglaterra', 'Premier League'),
    'national-league-inglesa': ('Inglaterra', 'National League'),
    # Competiciones UEFA
    'europa-conference-league': ('Internacional', 'Conference League'),
    'uefa-europa-league': ('Internacional', 'Europa League'),
    'uefa-champions-league': ('Internacional', 'Champions League'),
    # Sudamérica
    'copa-sudamericana': ('Internacional', 'Copa Sudamericana'),
    'concacaf-champions-league': ('Internacional', 'CONCACAF Champions'),
    'conmebol-recopa-sudamericana': ('Internacional', 'Recopa Sudamericana'),
    # Brasil (estaduales y copa)
    'copa-de-brasil': ('Brasil', 'Copa do Brasil'),
    'partidos-carioca-brasileña': ('Brasil', 'Carioca'),
    'partidos-carioca-brasile%C3%B1a': ('Brasil', 'Carioca'),
    'brasil-partidos-del-campeonato-mineiro': ('Brasil', 'Mineiro'),
    'brasil-partidos-del-campeonato-baiano': ('Brasil', 'Baiano'),
    'partidos-goiano-brasileño': ('Brasil', 'Goiano'),
    'partidos-goiano-brasile%C3%B1o': ('Brasil', 'Goiano'),
    'gaucho-brasileña': ('Brasil', 'Gaúcho'),
    'gaucho-brasile%C3%B1a': ('Brasil', 'Gaúcho'),
    # Italia Serie C
    'serie-c-italiana': ('Italia', 'Serie C'),
    # Ecuador
    'serie-a-ecuatoriana': ('Ecuador', 'Serie A'),
    # Dinamarca 1st Division
    'danish-1st-division': ('Dinamarca', '1st Division'),
    # Tailandia
    'tailandia-liga-2': ('Tailandia', 'Liga 2'),
    'tailandia-liga-1': ('Tailandia', 'Liga 1'),
    'thai-league': ('Tailandia', 'Thai League'),
    # Irlanda
    'irlanda-premier-division': ('Irlanda', 'Premier Division'),
    # China
    'china-superliga': ('China', 'Superliga'),
    # Turquía copa
    'copa-turca': ('Turquía', 'Copa Turca'),
    # Corea del Sur
    'corea-del-sur-k1-league': ('Corea del Sur', 'K1 League'),
    'corea-del-sur-k2-league': ('Corea del Sur', 'K2 League'),
    # Francia copa
    'copa-de-francia': ('Francia', 'Coupe de France'),
    # Bosnia
    'premier-league-bosnia': ('Bosnia', 'Premier League'),
    # Escocia
    'escocia-challenge-cup': ('Escocia', 'Challenge Cup'),
    # México expansión
    'méxico-liga-de-expansión-mx': ('México', 'Liga de Expansión'),
    'm%C3%A9xico-liga-de-expansi%C3%B3n-mx': ('México', 'Liga de Expansión'),
    # FIFA
    'copa-mundial-de-la-fifa-femenino-clasificatorios': ('Internacional', 'FIFA Women WC Qualifiers'),
    # AFC
    'afc-champions-league-2': ('Internacional', 'AFC Champions League 2'),
    # ── Añadidos batch 2 (restantes del backfill) ──
    'albania-kategoria-superiore': ('Albania', 'Kategoria Superiore'),
    'azerbaiy%C3%A1n-premier-league': ('Azerbaiyán', 'Premier League'),
    'azerbaiyán-premier-league': ('Azerbaiyán', 'Premier League'),
    'brasil-pernambucano': ('Brasil', 'Pernambucano'),
    'championship-escocesa': ('Escocia', 'Championship'),
    'escocia-copa': ('Escocia', 'Copa Escocesa'),
    'league-1-escocesa': ('Escocia', 'League One'),
    'fifa-copa-mundial-femenina': ('Internacional', 'FIFA Women World Cup'),
    'i-liga-polaca': ('Polonia', 'I Liga'),
    'italia-copa': ('Italia', 'Coppa Italia'),
    'malaysian-super-league': ('Malasia', 'Super League'),
    'perú-primera-división': ('Perú', 'Primera División'),
    'per%C3%BA-primera-divisi%C3%B3n': ('Perú', 'Primera División'),
    'república-popular-china': ('China', 'Superliga'),
    'rep%C3%BAblica-popular-china': ('China', 'Superliga'),
    'serbia-prva-liga': ('Serbia', 'Prva Liga'),
    'super-league-eslovaca': ('Eslovaquia', 'Super League'),
    'tanzania-premier-league': ('Tanzania', 'Premier League'),
    'virsliga-letona': ('Letonia', 'Virsliga'),
    'zambia-superliga': ('Zambia', 'Superliga'),
    'bolivian-torneo-amistoso': ('Bolivia', 'Torneo Amistoso'),
}

def extraer_pais_liga_de_url(url: str) -> tuple:
    """
    Extrae País y Liga de la URL de Betfair.
    Retorna: (país, liga) o ('Desconocido', 'Desconocida') si no se encuentra.
    """
    if not isinstance(url, str) or not url:
        return ('Desconocido', 'Desconocida')

    url_decoded = unquote(url.lower())

    # Buscar en el mapping
    for league_key, (country, league) in URL_LEAGUE_MAPPING.items():
        if league_key in url_decoded:
            return (country, league)

    return ('Desconocido', 'Desconocida')


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
    # Over/Under 5.5
    "back_over55",
    "lay_over55",
    "back_under55",
    "lay_under55",
    # Over/Under 6.5
    "back_over65",
    "lay_over65",
    "back_under65",
    "lay_under65",
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
    "free_kicks_local",
    "free_kicks_visitante",
    "offsides_local",
    "offsides_visitante",
    "substitutions_local",
    "substitutions_visitante",
    "injuries_local",
    "injuries_visitante",
    "time_in_dangerous_attack_pct_local",
    "time_in_dangerous_attack_pct_visitante",
    "momentum_local",
    "momentum_visitante",
    # Volumen
    "volumen_matched",
    # Meta
    "url",
    "País",
    "Liga",
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


def filtrar_partidos_para_drivers(partidos: list, ventana_antes_min: int = 10, ventana_despues_min: int = 120, output_dir = None) -> list:
    """
    Filtra partidos que necesitan driver Chrome AHORA.

    Criterios:
    - Partidos con capturas recientes (<5 min): SIEMPRE incluir (están en vivo)
    - Partidos sin capturas próximos a empezar (<15 min): incluir
    - Partidos futuros (>15 min): NO incluir
    - Partidos finalizados (>ventana_despues_min): NO incluir

    Args:
        partidos: Lista de dicts con 'url', 'game', 'fecha_hora_inicio'
        ventana_antes_min: Minutos antes del inicio para empezar a trackear
        ventana_despues_min: Minutos después del inicio para dejar de trackear
        output_dir: Directorio donde están los CSVs de partidos (Path o str)

    Returns:
        Lista de partidos que necesitan driver Chrome
    """
    ahora = datetime.now()
    partidos_con_driver = []

    if output_dir is None:
        output_dir = OUTPUT_DIR
    else:
        output_dir = Path(output_dir)

    for partido in partidos:
        # Si no tiene fecha_hora_inicio, trackear siempre (modo legacy)
        if partido["fecha_hora_inicio"] is None:
            partidos_con_driver.append(partido)
            continue

        # Calcular diferencia en minutos
        tiempo_hasta_inicio = (partido["fecha_hora_inicio"] - ahora).total_seconds() / 60

        # Verificar si ya tiene capturas recientes (partido en vivo)
        match_id = extraer_id_partido(partido["url"])
        csv_path = output_dir / f"partido_{match_id}.csv"
        tiene_capturas_recientes = False

        if csv_path.exists():
            try:
                # Verificar última modificación del CSV
                tiempo_desde_modificacion = (ahora.timestamp() - csv_path.stat().st_mtime) / 60
                if tiempo_desde_modificacion < 5:
                    tiene_capturas_recientes = True
            except Exception:
                pass

        # Decisión de incluir:
        if tiene_capturas_recientes:
            # Partido con capturas recientes: mantener driver (está en vivo)
            partidos_con_driver.append(partido)
        elif tiempo_hasta_inicio > 15:
            # Partido futuro (faltan >15 min): NO crear driver
            continue
        elif tiempo_hasta_inicio >= -ventana_despues_min:
            # Partido próximo a empezar o recién empezado: crear driver
            partidos_con_driver.append(partido)
        # else: partido finalizado (>ventana_despues_min), no incluir

    return partidos_con_driver


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


def _extraer_best_back_lay(row) -> tuple:
    """
    Extrae el mejor precio back y lay de una fila de Betfair Exchange.

    Usa selectores CSS (last-back-cell / first-lay-cell) para identificar
    correctamente back vs lay. Fallback al método mid-point si no hay clases CSS.

    Returns: (best_back: str, best_lay: str) - precios como string, vacío si no hay.
    """
    best_back = ""
    best_lay = ""

    # Método 1: Usar clases CSS de Betfair (más fiable)
    try:
        back_cell = row.find_elements(By.CSS_SELECTOR, "td.last-back-cell button")
        if back_cell:
            text = back_cell[0].text.strip()
            if text:
                m = re.match(r"^(\d+\.?\d*)", text.replace(",", "."))
                if m:
                    best_back = m.group(1)

        lay_cell = row.find_elements(By.CSS_SELECTOR, "td.first-lay-cell button")
        if lay_cell:
            text = lay_cell[0].text.strip()
            if text:
                m = re.match(r"^(\d+\.?\d*)", text.replace(",", "."))
                if m:
                    best_lay = m.group(1)
    except (NoSuchElementException, StaleElementReferenceException):
        pass

    if best_back or best_lay:
        return best_back, best_lay

    # Método 2 (fallback): Mid-point de botones con precio
    buttons = row.find_elements(By.TAG_NAME, "button")
    price_buttons = []
    for btn in buttons:
        text = btn.text.strip()
        if text and ("€" in text or text.replace(".", "").replace(",", "").isdigit()):
            price_buttons.append(btn)

    if len(price_buttons) >= 2:
        mid = len(price_buttons) // 2
        back_text = price_buttons[mid - 1].text.strip()
        lay_text = price_buttons[mid].text.strip()

        back_match = re.match(r"^(\d+\.?\d*)", back_text.replace(",", "."))
        lay_match = re.match(r"^(\d+\.?\d*)", lay_text.replace(",", "."))

        if back_match:
            best_back = back_match.group(1)
        if lay_match:
            best_lay = lay_match.group(1)

    return best_back, best_lay


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

                    if not runner_name:
                        continue

                    # Filtro negativo: descartar runners de otros mercados
                    # (Over/Under contienen "Goles"/"Goals", Correct Score "X - Y")
                    name_lower = runner_name.lower()
                    if any(kw in name_lower for kw in (
                        "goles", "goals", "más de", "menos de",
                        "more than", "over", "under",
                    )):
                        continue
                    if re.match(r"^\d+\s*-\s*\d+$", runner_name):
                        continue

                    # Identificar si es Empate/Draw
                    is_draw = "Empate" in runner_name or "Draw" in runner_name

                    back_price, lay_price = _extraer_best_back_lay(row)

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
        "back_over55": "", "lay_over55": "",
        "back_under55": "", "lay_under55": "",
        "back_over65": "", "lay_over65": "",
        "back_under65": "", "lay_under65": "",
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

                    # 5.5 Goles
                    elif "5,5 Goles" in runner_name or "5.5 Goles" in runner_name:
                        if "Más" in runner_name or "Over" in runner_name:
                            runner_key = ("back_over55", "lay_over55")
                        elif "Menos" in runner_name or "Under" in runner_name:
                            runner_key = ("back_under55", "lay_under55")

                    # 6.5 Goles
                    elif "6,5 Goles" in runner_name or "6.5 Goles" in runner_name:
                        if "Más" in runner_name or "Over" in runner_name:
                            runner_key = ("back_over65", "lay_over65")
                        elif "Menos" in runner_name or "Under" in runner_name:
                            runner_key = ("back_under65", "lay_under65")

                    if not runner_key:
                        continue

                    back_price, lay_price = _extraer_best_back_lay(row)
                    if back_price:
                        resultado[runner_key[0]] = back_price
                    if lay_price:
                        resultado[runner_key[1]] = lay_price

                except (NoSuchElementException, StaleElementReferenceException):
                    continue

    except WebDriverException as e:
        log.debug(f"No se pudo extraer Over/Under: {e}")

    return resultado


def extraer_over_under_via_mercado(driver) -> dict:
    """
    Extrae cuotas Over/Under navegando a las URLs individuales de mercado
    desde el sidebar de Betfair. Esto obtiene cuotas en vivo reales,
    a diferencia de la página del evento que puede tener datos congelados.

    Flujo:
    1. Guarda la URL actual (página del evento)
    2. Busca links de mercados O/U en el sidebar
    3. Navega a la primera URL de mercado O/U encontrada
    4. Extrae cuotas de todos los runners O/U en esa página
    5. Navega de vuelta a la página del evento
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
        "back_over55": "", "lay_over55": "",
        "back_under55": "", "lay_under55": "",
        "back_over65": "", "lay_over65": "",
        "back_under65": "", "lay_under65": "",
    }

    # Mapeo de nombre de runner a claves del resultado
    OU_MAP = {
        "0,5": ("05",), "0.5": ("05",),
        "1,5": ("15",), "1.5": ("15",),
        "2,5": ("25",), "2.5": ("25",),
        "3,5": ("35",), "3.5": ("35",),
        "4,5": ("45",), "4.5": ("45",),
        "5,5": ("55",), "5.5": ("55",),
        "6,5": ("65",), "6.5": ("65",),
    }

    original_url = driver.current_url

    try:
        # 1. Buscar links de mercados O/U en el sidebar
        ou_market_urls = []
        all_links = driver.find_elements(By.CSS_SELECTOR, "a")
        for link in all_links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip().lower()
                if "football/market/" in href and "goles" in text:
                    ou_market_urls.append(href)
            except StaleElementReferenceException:
                continue

        if not ou_market_urls:
            log.debug("No se encontraron links de mercados O/U en sidebar")
            return resultado

        # 2. Navegar a la primera URL de mercado O/U (muestra múltiples O/U)
        market_url = ou_market_urls[0]
        log.debug(f"Navegando a mercado O/U: {market_url}")
        driver.get(market_url)
        time.sleep(2)

        # 3. Extraer runners O/U de la página del mercado individual
        tables = driver.find_elements(By.CSS_SELECTOR, "table tbody")
        for tbody in tables:
            rows = tbody.find_elements(By.CSS_SELECTOR, "tr")
            for row in rows:
                try:
                    h3_elements = row.find_elements(By.TAG_NAME, "h3")
                    if not h3_elements:
                        continue

                    runner_name = h3_elements[0].text.strip()
                    if "Goles" not in runner_name and "Goals" not in runner_name:
                        continue

                    # Determinar la línea (0.5, 1.5, ..., 6.5)
                    runner_key = None
                    for pattern, (suffix,) in OU_MAP.items():
                        if pattern in runner_name:
                            if "Más" in runner_name or "More" in runner_name or "Over" in runner_name:
                                runner_key = (f"back_over{suffix}", f"lay_over{suffix}")
                            elif "Menos" in runner_name or "Fewer" in runner_name or "Under" in runner_name:
                                runner_key = (f"back_under{suffix}", f"lay_under{suffix}")
                            break

                    if not runner_key:
                        continue

                    back_price, lay_price = _extraer_best_back_lay(row)
                    if back_price:
                        resultado[runner_key[0]] = back_price
                    if lay_price:
                        resultado[runner_key[1]] = lay_price

                except (NoSuchElementException, StaleElementReferenceException):
                    continue

    except WebDriverException as e:
        log.debug(f"Error navegando a mercado O/U: {e}")

    finally:
        # 4. SIEMPRE volver a la página del evento
        try:
            driver.get(original_url)
            time.sleep(1)
        except WebDriverException:
            log.warning(f"No se pudo volver a URL original: {original_url}")

    ou_count = sum(1 for v in resultado.values() if v)
    if ou_count > 0:
        log.info(f"✓ O/U via mercado: {ou_count} valores capturados")

    return resultado


def extraer_resultado_correcto_via_mercado(driver) -> dict:
    """
    Extrae cuotas Resultado Correcto navegando a la URL del mercado individual.
    Esto obtiene cuotas en vivo reales, a diferencia de la página del evento
    que puede tener datos congelados.

    Flujo:
    1. Guarda la URL actual (página del evento)
    2. Busca el link del mercado Resultado Correcto en el sidebar
    3. Navega a esa URL
    4. Extrae cuotas de todos los runners con formato de marcador
    5. Navega de vuelta a la página del evento
    """
    marcadores = [
        "0-0", "1-0", "0-1", "1-1",
        "2-0", "0-2", "2-1", "1-2", "2-2",
        "3-0", "0-3", "3-1", "1-3", "3-2", "2-3"
    ]
    resultado = {}
    for marcador in marcadores:
        marcador_key = marcador.replace("-", "_")
        resultado[f"back_rc_{marcador_key}"] = ""
        resultado[f"lay_rc_{marcador_key}"] = ""

    original_url = driver.current_url

    try:
        # 1. Buscar link del mercado Resultado Correcto en el sidebar
        rc_market_url = None
        all_links = driver.find_elements(By.CSS_SELECTOR, "a")
        for link in all_links:
            try:
                href = link.get_attribute("href") or ""
                text = link.text.strip().lower()
                if "football/market/" in href and ("resultado" in text or "correct" in text):
                    rc_market_url = href
                    break
            except StaleElementReferenceException:
                continue

        if not rc_market_url:
            log.debug("No se encontró link del mercado Resultado Correcto en sidebar")
            return resultado

        # 2. Navegar a la URL del mercado Resultado Correcto
        log.debug(f"Navegando a mercado RC: {rc_market_url}")
        driver.get(rc_market_url)
        time.sleep(2)

        # 3. Extraer runners con formato de marcador
        tables = driver.find_elements(By.CSS_SELECTOR, "table tbody")
        for tbody in tables:
            rows = tbody.find_elements(By.CSS_SELECTOR, "tr")
            for row in rows:
                try:
                    h3_elements = row.find_elements(By.TAG_NAME, "h3")
                    if not h3_elements:
                        continue

                    runner_name = h3_elements[0].text.strip()
                    marcador_match = re.search(r"(\d+)\s*-\s*(\d+)", runner_name)
                    if not marcador_match:
                        continue

                    marcador = f"{marcador_match.group(1)}-{marcador_match.group(2)}"
                    if marcador not in marcadores:
                        continue

                    marcador_key = marcador.replace("-", "_")
                    back_price, lay_price = _extraer_best_back_lay(row)
                    if back_price:
                        resultado[f"back_rc_{marcador_key}"] = back_price
                    if lay_price:
                        resultado[f"lay_rc_{marcador_key}"] = lay_price

                except (NoSuchElementException, StaleElementReferenceException):
                    continue

    except WebDriverException as e:
        log.debug(f"Error navegando a mercado RC: {e}")

    finally:
        # 4. SIEMPRE volver a la página del evento
        try:
            driver.get(original_url)
            time.sleep(1)
        except WebDriverException:
            log.warning(f"No se pudo volver a URL original: {original_url}")

    rc_count = sum(1 for v in resultado.values() if v)
    if rc_count > 0:
        log.info(f"✓ RC via mercado: {rc_count} valores capturados")

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

                    back_price, lay_price = _extraer_best_back_lay(row)
                    if back_price:
                        resultado[f"back_rc_{marcador_key}"] = back_price
                    if lay_price:
                        resultado[f"lay_rc_{marcador_key}"] = lay_price

                except (NoSuchElementException, StaleElementReferenceException):
                    continue

    except WebDriverException as e:
        log.debug(f"No se pudo extraer Resultado Correcto: {e}")

    return resultado


def extraer_estadisticas(driver, cached_event_id: str = None) -> dict:
    """
    Extrae estadísticas del partido en vivo usando la API REST de Stats Perform.

    NUEVA ARQUITECTURA (2026-02-12):
    - Usa API REST en lugar de CSS selectors (10x más rápido, 100% confiable)
    - Captura xG, momentum, corners, tarjetas, y todas las estadísticas críticas
    - Ver STATS_API_README.md para más detalles

    cached_event_id: Si se proporciona, evita la llamada HTTP a videoplayer.betfair.es
                     (el Opta event_id no cambia durante el partido).
    """
    # Inicializar dict vacío (mismo formato que versión anterior)
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

    event_id = None  # Inicializar para que sea accesible fuera del try

    try:
        # PASO 1: Extraer eventId del HTML (con caché: el Opta event_id no cambia en el partido)
        if cached_event_id:
            event_id = cached_event_id
            log.debug(f"  → Usando eventId cacheado: {event_id}")
        else:
            log.debug("  → Extrayendo eventId del HTML...")
            html_source = driver.page_source
            current_url = driver.current_url
            event_id = extract_event_id(html_source, current_url)

        if not event_id:
            log.warning("  × No se pudo extraer eventId - partido sin estadísticas Opta")

            # FALLBACK: Intentar extraer desde iframe de visualización
            try:
                betfair_event_id = None

                # Intentar desde data-event-id en HTML
                match = re.search(r'data-event-id="(\d+)"', html_source)
                if match:
                    betfair_event_id = match.group(1)
                else:
                    # Intentar desde URL (formato: apuestas-XXXXXXXXX)
                    match = re.search(r'apuestas-(\d+)', current_url)
                    if match:
                        betfair_event_id = match.group(1)

                if betfair_event_id:
                    from extract_iframe_stats import extract_stats_from_iframe
                    iframe_stats = extract_stats_from_iframe(driver, betfair_event_id)

                    # DEBUG: Log what iframe captured
                    iframe_captured = {k: v for k, v in iframe_stats.items() if v != ""}
                    if iframe_captured:
                        log.debug(f"  → Iframe stats capturados: {iframe_captured}")

                    # Actualizar solo los campos que el iframe capturó
                    for key, value in iframe_stats.items():
                        if value and value != "":
                            stats[key] = value

                    captured_count = sum(1 for v in stats.values() if v != "")
                    if captured_count > 0:
                        log.debug(f"  → Total stats en dict tras merge: {captured_count}")
                        return stats
                else:
                    log.warning("  × No se pudo extraer Betfair event ID para fallback")

            except Exception as e:
                log.error(f"  × Error en fallback iframe: {e}")

            return stats

        log.debug(f"  ✓ EventId extraído: {event_id}")

        # PASO 2: Obtener todas las estadísticas de la API
        log.debug("  → Obteniendo estadísticas de la API...")
        all_stats = get_all_stats(event_id)

        if not all_stats or not all_stats.get('summary'):
            log.warning("  × No hay estadísticas disponibles en la API")
            return stats

        # PASO 3: Mapear estadísticas al formato esperado
        log.debug("  → Mapeando estadísticas...")

        # Summary stats (CRÍTICAS PARA TRADING)
        stats["xg_local"] = extract_stat_value(all_stats, 'summary', 'home', 'xG', "")
        stats["xg_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'xG', "")
        stats["opta_points_local"] = extract_stat_value(all_stats, 'summary', 'home', 'optaPoints', "")
        stats["opta_points_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'optaPoints', "")
        stats["posesion_local"] = extract_stat_value(all_stats, 'summary', 'home', 'possession', "")
        stats["posesion_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'possession', "")
        stats["tiros_local"] = extract_stat_value(all_stats, 'summary', 'home', 'shots', "")
        stats["tiros_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'shots', "")
        stats["tiros_puerta_local"] = extract_stat_value(all_stats, 'summary', 'home', 'shotsOnTarget', "")
        stats["tiros_puerta_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'shotsOnTarget', "")
        stats["touches_box_local"] = extract_stat_value(all_stats, 'summary', 'home', 'touchesInOppBox', "")
        stats["touches_box_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'touchesInOppBox', "")
        stats["corners_local"] = extract_stat_value(all_stats, 'summary', 'home', 'corners', "")
        stats["corners_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'corners', "")
        stats["total_passes_local"] = extract_stat_value(all_stats, 'summary', 'home', 'totalPasses', "")
        stats["total_passes_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'totalPasses', "")
        stats["fouls_conceded_local"] = extract_stat_value(all_stats, 'summary', 'home', 'foulsConceded', "")
        stats["fouls_conceded_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'foulsConceded', "")
        stats["tarjetas_amarillas_local"] = extract_stat_value(all_stats, 'summary', 'home', 'yellowCards', "")
        stats["tarjetas_amarillas_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'yellowCards', "")
        stats["tarjetas_rojas_local"] = extract_stat_value(all_stats, 'summary', 'home', 'redCards', "")
        stats["tarjetas_rojas_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'redCards', "")
        stats["booking_points_local"] = extract_stat_value(all_stats, 'summary', 'home', 'bookingPoints', "")
        stats["booking_points_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'bookingPoints', "")

        # Attacking stats
        stats["big_chances_local"] = extract_stat_value(all_stats, 'attacking', 'home', 'bigChances', "")
        stats["big_chances_visitante"] = extract_stat_value(all_stats, 'attacking', 'away', 'bigChances', "")
        stats["shots_off_target_local"] = extract_stat_value(all_stats, 'attacking', 'home', 'shotsOffTarget', "")
        stats["shots_off_target_visitante"] = extract_stat_value(all_stats, 'attacking', 'away', 'shotsOffTarget', "")
        stats["attacks_local"] = extract_stat_value(all_stats, 'summary', 'home', 'attacks', "")
        stats["attacks_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'attacks', "")
        stats["hit_woodwork_local"] = extract_stat_value(all_stats, 'attacking', 'home', 'hitWoodwork', "")
        stats["hit_woodwork_visitante"] = extract_stat_value(all_stats, 'attacking', 'away', 'hitWoodwork', "")
        stats["blocked_shots_local"] = extract_stat_value(all_stats, 'attacking', 'home', 'blockedShots', "")
        stats["blocked_shots_visitante"] = extract_stat_value(all_stats, 'attacking', 'away', 'blockedShots', "")
        stats["shooting_accuracy_local"] = extract_stat_value(all_stats, 'attacking', 'home', 'shootingAccuracy', "")
        stats["shooting_accuracy_visitante"] = extract_stat_value(all_stats, 'attacking', 'away', 'shootingAccuracy', "")
        stats["dangerous_attacks_local"] = extract_stat_value(all_stats, 'summary', 'home', 'dangerousAttacks', "")
        stats["dangerous_attacks_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'dangerousAttacks', "")

        # Defence stats
        stats["tackles_local"] = extract_stat_value(all_stats, 'defence', 'home', 'tackles', "")
        stats["tackles_visitante"] = extract_stat_value(all_stats, 'defence', 'away', 'tackles', "")
        stats["tackle_success_pct_local"] = extract_stat_value(all_stats, 'defence', 'home', 'tackleSuccessPct', "")
        stats["tackle_success_pct_visitante"] = extract_stat_value(all_stats, 'defence', 'away', 'tackleSuccessPct', "")
        stats["duels_won_local"] = extract_stat_value(all_stats, 'defence', 'home', 'duelsWon', "")
        stats["duels_won_visitante"] = extract_stat_value(all_stats, 'defence', 'away', 'duelsWon', "")
        stats["aerial_duels_won_local"] = extract_stat_value(all_stats, 'defence', 'home', 'aerialDuelsWon', "")
        stats["aerial_duels_won_visitante"] = extract_stat_value(all_stats, 'defence', 'away', 'aerialDuelsWon', "")
        stats["clearance_local"] = extract_stat_value(all_stats, 'defence', 'home', 'clearances', "")
        stats["clearance_visitante"] = extract_stat_value(all_stats, 'defence', 'away', 'clearances', "")
        stats["saves_local"] = extract_stat_value(all_stats, 'defence', 'home', 'saves', "")
        stats["saves_visitante"] = extract_stat_value(all_stats, 'defence', 'away', 'saves', "")
        stats["interceptions_local"] = extract_stat_value(all_stats, 'defence', 'home', 'interceptions', "")
        stats["interceptions_visitante"] = extract_stat_value(all_stats, 'defence', 'away', 'interceptions', "")

        # Distribution stats (usando 'summary' ya que no hay endpoint separado)
        stats["pass_success_pct_local"] = extract_stat_value(all_stats, 'summary', 'home', 'passSuccessPct', "")
        stats["pass_success_pct_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'passSuccessPct', "")
        stats["crosses_local"] = extract_stat_value(all_stats, 'attacking', 'home', 'crosses', "")
        stats["crosses_visitante"] = extract_stat_value(all_stats, 'attacking', 'away', 'crosses', "")
        stats["successful_crosses_pct_local"] = extract_stat_value(all_stats, 'attacking', 'home', 'successfulCrossesPct', "")
        stats["successful_crosses_pct_visitante"] = extract_stat_value(all_stats, 'attacking', 'away', 'successfulCrossesPct', "")
        stats["successful_passes_opp_half_local"] = extract_stat_value(all_stats, 'summary', 'home', 'successfulPassesOppHalf', "")
        stats["successful_passes_opp_half_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'successfulPassesOppHalf', "")
        stats["successful_passes_final_third_local"] = extract_stat_value(all_stats, 'summary', 'home', 'successfulPassesFinalThird', "")
        stats["successful_passes_final_third_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'successfulPassesFinalThird', "")
        stats["goal_kicks_local"] = extract_stat_value(all_stats, 'summary', 'home', 'goalKicks', "")
        stats["goal_kicks_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'goalKicks', "")
        stats["throw_ins_local"] = extract_stat_value(all_stats, 'summary', 'home', 'throwIns', "")
        stats["throw_ins_visitante"] = extract_stat_value(all_stats, 'summary', 'away', 'throwIns', "")

        # Momentum (NUEVO: desde API)
        momentum_data = all_stats.get('momentum')
        if momentum_data:
            home_momentum = momentum_data.get('home', 0)
            away_momentum = momentum_data.get('away', 0)

            # Solo asignar si tenemos valores válidos
            if home_momentum or away_momentum:
                stats["momentum_local"] = f"{home_momentum:.2f}" if home_momentum else ""
                stats["momentum_visitante"] = f"{away_momentum:.2f}" if away_momentum else ""
                log.debug(f"    → Momentum vía API: {stats['momentum_local']}-{stats['momentum_visitante']}")

        # Contar cuántas estadísticas se capturaron
        captured_count = sum(1 for v in stats.values() if v != "")
        log.info(f"  ✓ Estadísticas capturadas vía API: {captured_count}/{len(stats)} campos")
        log.debug(f"    → xG: {stats['xg_local']}-{stats['xg_visitante']}, Corners: {stats['corners_local']}-{stats['corners_visitante']}")

    except Exception as e:
        log.error(f"  × Error capturando estadísticas vía API: {e}")

    # Propagar el event_id al caller para que pueda cachearlo en MatchDriver
    if event_id:
        stats["_opta_event_id"] = event_id

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
                        # ACTUALIZADO: Betfair cambió de /stats/live-stats a /watch/pitchView
                        if "stats/live-stats" in src or ("/watch/" in src and "statsperform" in src):
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

        # PASO 2: Construir URL de momentum
        # IMPORTANTE: Aunque el iframe base cambió a /watch/pitchView,
        # la URL de momentum SIEMPRE debe ser /stats/live-stats/momentum
        if "/stats/live-stats/" in stats_iframe_url:
            momentum_url = re.sub(
                r"/stats/live-stats/[^?]+",
                "/stats/live-stats/momentum",
                stats_iframe_url,
            )
        elif "/watch/" in stats_iframe_url:
            # El iframe base usa /watch/, pero momentum sigue usando /stats/live-stats/
            momentum_url = re.sub(
                r"/watch/[^?]+",
                "/stats/live-stats/momentum",
                stats_iframe_url,
            )
        else:
            log.debug(f"  × Formato de URL desconocido: {stats_iframe_url[:80]}")
            return momentum

        log.debug(f"  → URL momentum construida: {momentum_url[:80]}")

        # PASO 3: Abrir URL de momentum en nueva pestaña (sin clickear nada)
        driver.execute_script("window.open(arguments[0]);", momentum_url)
        time.sleep(0.5)

        # Cambiar a la nueva pestaña
        new_handles = [h for h in driver.window_handles if h != original_window]
        if not new_handles:
            log.debug("  × No se pudo abrir nueva pestaña")
            return momentum

        driver.switch_to.window(new_handles[-1])
        time.sleep(1)  # Esperar a que cargue el gráfico

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
        self._finalizados: set = set()  # tab_ids cuyo partido ya llegó a 'finalizado'
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
        # Si el partido ya alcanzó 'finalizado' en esta sesión, no añadir más filas
        if tab_id in self._finalizados:
            return

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

        # Verificar si ya existe una captura para este minuto
        minuto_nuevo = datos.get("minuto", "").strip()
        estado_nuevo = datos.get("estado_partido", "").strip()

        # Solo verificar duplicados si es un partido en juego/descanso/finalizado con minuto
        if minuto_nuevo and minuto_nuevo != "-" and estado_nuevo in ("en_juego", "descanso", "finalizado"):
            # Leer última línea del CSV para comparar minuto
            try:
                with open(ruta, "r", encoding="utf-8") as f_check:
                    lines = f_check.readlines()
                    if len(lines) > 1:  # Si hay más que solo el header
                        ultima_linea = lines[-1].strip()
                        if ultima_linea:
                            # Parsear la última fila
                            reader = csv.DictReader([lines[0], ultima_linea])
                            ultima_fila = list(reader)[-1]
                            minuto_anterior = ultima_fila.get("minuto", "").strip()

                            # Si el minuto es el mismo, saltar escritura
                            if minuto_anterior == minuto_nuevo:
                                log.debug(f"[{tab_id}] Minuto {minuto_nuevo} ya capturado, saltando duplicado")
                                return
            except Exception as e:
                # Si hay error leyendo, continuar con la escritura normal
                log.debug(f"Error verificando duplicados para {tab_id}: {e}")

        self._writers[tab_id].writerow(datos)
        self._archivos_abiertos[tab_id].flush()

        # Si acabamos de escribir el estado finalizado, bloquear escrituras futuras
        if datos.get("estado_partido", "").strip() == "finalizado":
            self._finalizados.add(tab_id)

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

# Retry tracking: {url: failure_count}
_driver_creation_failures: dict = {}
MAX_DRIVER_RETRIES = 5  # Stop retrying after this many consecutive failures per match

# ── Init progress heartbeat ───────────────────────────────────────────────────
# Dict compartido: match_id → MatchDriver (se rellena en __init__, se borra en cerrar())
# Lo lee el hilo _heartbeat_background_writer para escribir .heartbeat en tiempo real
_md_progress_refs: dict = {}
_md_progress_hb_path: str = None   # Se asigna en main() antes de crear drivers
_md_progress_hb_stop = threading.Event()


def _write_progress_heartbeat_now(path: str, cycle: int = 0, captures: int = 0, fail_count: int = 0):
    """Escribe el heartbeat con progreso por partido. Llamable desde cualquier hilo."""
    try:
        import json as _j
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle": cycle,
            "pid": os.getpid(),
            "active_drivers": len(_md_progress_refs),
            "alive_drivers": sum(
                1 for d in _md_progress_refs.values()
                if d._stage not in ("error", "pending")
            ),
            "successful_captures": captures,
            "consecutive_all_fail": fail_count,
            "drivers_progress": {
                mid: {"game": d.game[:50], "stage": d._stage, "pct": d._stage_pct}
                for mid, d in _md_progress_refs.items()
            },
        }
        with open(path, "w", encoding="utf-8") as f:
            _j.dump(data, f)
    except Exception:
        pass


def _heartbeat_background_writer():
    """Hilo demonio: actualiza el heartbeat cada 4s durante la inicialización."""
    while not _md_progress_hb_stop.wait(4):
        if _md_progress_hb_path:
            _write_progress_heartbeat_now(_md_progress_hb_path)


def _get_active_chromedriver_pids(match_drivers: dict) -> set:
    """Get PIDs of chromedriver processes that belong to active MatchDrivers."""
    pids = set()
    for md in match_drivers.values():
        try:
            if md.driver and md.driver.service and md.driver.service.process:
                pids.add(md.driver.service.process.pid)
        except Exception:
            pass
    return pids


def limpiar_chromedrivers_huerfanos(match_drivers: dict):
    """
    Kill orphaned chromedriver.exe processes that don't belong to active MatchDrivers.
    This prevents zombie process accumulation when driver creation fails repeatedly.
    """
    import subprocess
    import platform

    if platform.system() != "Windows":
        return

    try:
        # Get all chromedriver.exe PIDs
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq chromedriver.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10
        )
        if not result.stdout.strip():
            return

        all_pids = set()
        for line in result.stdout.strip().split('\n'):
            parts = line.strip().strip('"').split('","')
            if len(parts) >= 2:
                try:
                    all_pids.add(int(parts[1].strip('"')))
                except ValueError:
                    pass

        active_pids = _get_active_chromedriver_pids(match_drivers)
        orphan_pids = all_pids - active_pids

        if orphan_pids:
            log.info(f"🧹 Limpiando {len(orphan_pids)} chromedrivers huérfanos + sus chrome hijos (activos: {len(active_pids)})...")
            for pid in orphan_pids:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True, timeout=5
                    )
                except Exception:
                    pass
            log.info(f"✓ Limpieza completada")

    except Exception as e:
        log.debug(f"Error en limpieza de chromedrivers: {e}")


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
    servicio = None
    if ChromeDriverManager is not None:
        try:
            servicio = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=servicio, options=opciones)
        except Exception as e:
            log.warning(f"webdriver-manager falló ({e}), intentando chromedriver del PATH...")
            # Clean up any orphaned service process from the failed attempt
            try:
                if servicio and hasattr(servicio, 'process') and servicio.process:
                    servicio.process.kill()
            except Exception:
                pass
            try:
                driver = webdriver.Chrome(options=opciones)
            except Exception as e2:
                log.error(f"Chromedriver del PATH también falló: {e2}")
                raise
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
        self._consecutive_failures = 0
        self._opta_event_id: str = None  # Cache: el Opta event_id no cambia durante el partido
        # ── Init progress tracking ──────────────────────────────────────────
        self._stage: str = "pending"   # Etapa actual de inicialización
        self._stage_pct: int = 0       # Porcentaje 0-100
        _md_progress_refs[self.match_id] = self  # Registrar para heartbeat en tiempo real

    def iniciar(self):
        """Crea el driver Chrome y abre el partido."""
        try:
            self._stage, self._stage_pct = "chrome_init", 10
            log.info(f"🔧 Creando driver para: {self.game[:50]}")
            self.driver = crear_driver()
            self._stage, self._stage_pct = "loading_url", 40
            self.driver.get(self.url)
            self._stage, self._stage_pct = "accepting_cookies", 70
            aceptar_cookies(self.driver)
            self._stage, self._stage_pct = "ready", 85
            log.info(f"✓ Driver listo: {self.match_id}")
            self._consecutive_failures = 0
            return True
        except Exception as e:
            self._stage, self._stage_pct = "error", 0
            log.error(f"✗ Error creando driver para {self.match_id}: {e}")
            return False

    def reiniciar(self):
        """Close and recreate the driver after a crash. Returns True on success."""
        log.warning(f"🔄 Reiniciando driver para: {self.game[:50]}")
        self.cerrar()
        return self.iniciar()

    def esta_vivo(self):
        """Check if the driver is still responsive."""
        if not self.driver:
            return False
        try:
            # Quick check - just access the title (fast, doesn't navigate)
            _ = self.driver.title
            return True
        except Exception:
            return False

    def cerrar(self):
        """Cierra el driver de forma segura, matando procesos zombie en Windows."""
        _md_progress_refs.pop(self.match_id, None)  # Desregistrar del tracking
        service_pid = None
        try:
            if self.driver:
                # Capture chromedriver PID before quit() so we can force-kill zombies
                try:
                    if self.driver.service and self.driver.service.process:
                        service_pid = self.driver.service.process.pid
                except Exception:
                    pass
                self.driver.quit()
                log.debug(f"✓ Driver cerrado: {self.match_id}")
        except Exception as e:
            log.debug(f"Error cerrando driver {self.match_id}: {e}")
        finally:
            self.driver = None
            # Force-kill entire process tree (chromedriver + all chrome children)
            if service_pid:
                import subprocess, platform
                if platform.system() == "Windows":
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(service_pid)],
                            capture_output=True, timeout=5
                        )
                    except Exception:
                        pass

    def capturar(self) -> dict:
        """Captura datos del partido usando el driver dedicado."""
        with self._lock:
            if not self.driver:
                log.error(f"Driver no disponible para {self.match_id}")
                return None
            # Marcar como "capturando" si aún no ha llegado a live
            if self._stage_pct < 100:
                self._stage, self._stage_pct = "capturing", 95

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
                ou_count = sum(1 for v in odds_ou.values() if v)
                if ou_count < 4:
                    log.debug(f"[{self.match_id}] O/U escasos ({ou_count}), intentando via mercado individual...")
                    odds_ou_market = extraer_over_under_via_mercado(self.driver)
                    # Merge: preferir valores del mercado individual (en vivo)
                    for k, v in odds_ou_market.items():
                        if v:
                            odds_ou[k] = v

                log.debug(f"[{self.match_id}] → Extrayendo cuotas Resultado Correcto (via mercado, cuotas live)...")
                odds_rc = extraer_resultado_correcto_via_mercado(self.driver)
                rc_count_check = sum(1 for v in odds_rc.values() if v)
                if rc_count_check == 0:
                    log.debug(f"[{self.match_id}] RC via mercado sin datos (mercado no encontrado/suspendido), fallback a página evento...")
                    odds_rc = extraer_resultado_correcto(self.driver)

                log.debug(f"[{self.match_id}] → Extrayendo estadísticas del partido...")
                stats = extraer_estadisticas(self.driver, cached_event_id=self._opta_event_id)
                # Actualizar caché del event_id si se capturó uno nuevo
                _new_opta_id = stats.pop("_opta_event_id", None)
                if _new_opta_id:
                    self._opta_event_id = _new_opta_id

                log.debug(f"[{self.match_id}] → Extrayendo volumen matched...")
                volumen = extraer_volumen(self.driver)

                # Momentum: Primero intentar desde API (ya viene en stats), fallback a método visual
                momentum_local = stats.get("momentum_local", "")
                momentum_visitante = stats.get("momentum_visitante", "")

                if not momentum_local and not momentum_visitante:
                    # Fallback visual: extrae momentum del iframe de Betfair
                    mom_result = extraer_momentum(self.driver)
                    momentum_local = mom_result.get("momentum_local", "")
                    momentum_visitante = mom_result.get("momentum_visitante", "")
                    if momentum_local or momentum_visitante:
                        stats["momentum_local"] = momentum_local
                        stats["momentum_visitante"] = momentum_visitante
                        log.debug(f"[{self.match_id}] ✓ Momentum obtenido vía fallback visual: {momentum_local}-{momentum_visitante}")
                    else:
                        log.debug(f"[{self.match_id}] → Momentum no disponible (API ni visual)")
                else:
                    log.debug(f"[{self.match_id}] ✓ Momentum obtenido de API: {momentum_local}-{momentum_visitante}")

                # Determinar estado del partido
                if info["estado_partido"]:
                    estado_partido = info["estado_partido"]
                elif info["minuto"] or (info["goles_local"] and info["goles_visitante"]):
                    estado_partido = "en_juego"
                else:
                    estado_partido = "pre_partido"

                # Extraer País y Liga de la URL
                pais, liga = extraer_pais_liga_de_url(self.url)

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
                    # Estadísticas (incluye momentum si API lo proporcionó)
                    **stats,
                    # Volumen
                    "volumen_matched": volumen,
                    # Momentum (sobrescribir con valores actualizados, ya sea de API o fallback visual)
                    "momentum_local": momentum_local,
                    "momentum_visitante": momentum_visitante,
                    # Meta
                    "url": self.url,
                    "País": pais,
                    "Liga": liga,
                }

                self.last_capture = time.time()
                self._consecutive_failures = 0
                self._stage, self._stage_pct = "live", 100  # Primera (o siguiente) captura exitosa
                log.info(f"✓ [{self.match_id}] Captura exitosa: {estado_partido}, min {info['minuto']}, {info['goles_local']}-{info['goles_visitante']}")

                # Guardar screenshot por minuto para evidencias (el backend busca por minuto exacto)
                try:
                    minuto_actual = info.get("minuto", "0")
                    screenshot_path = os.path.join(OUTPUT_DIR, f"screenshot_{self.match_id}_{minuto_actual}.png")
                    self.driver.save_screenshot(screenshot_path)
                    # Limpiar screenshots antiguos del mismo partido (conservar últimos 3 minutos)
                    import glob as _glob
                    existing = sorted(_glob.glob(os.path.join(OUTPUT_DIR, f"screenshot_{self.match_id}_*.png")))
                    for old in existing[:-3]:
                        try:
                            os.remove(old)
                        except Exception:
                            pass
                except Exception as _e:
                    log.debug(f"[{self.match_id}] Screenshot omitido: {_e}")

                return datos

            except WebDriverException as e:
                self._consecutive_failures += 1
                log.error(f"Error de driver capturando {self.match_id} (fallo #{self._consecutive_failures}): {e}")
                # Mark driver as dead so it can be restarted
                if self._consecutive_failures >= 3:
                    log.warning(f"💀 [{self.match_id}] Driver muerto tras {self._consecutive_failures} fallos consecutivos, marcando para reinicio")
                    try:
                        if self.driver:
                            self.driver.quit()
                    except Exception:
                        pass
                    self.driver = None
                return None
            except Exception as e:
                self._consecutive_failures += 1
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


def captura_paralela_multidriver(match_drivers: list, writer: CSVWriter) -> int:
    """
    Captura datos de todos los match_drivers en paralelo usando ThreadPoolExecutor.
    Returns: number of successful captures.
    """
    if not match_drivers:
        return 0

    log.info(f"📸 Capturando {len(match_drivers)} partidos en paralelo...")
    inicio = time.time()

    # Cap parallelism to avoid resource contention (RAM/CPU/network) when tracking many matches.
    # Too many simultaneous Chrome navigations cause system thrashing and slow EVERY browser down.
    # 16 workers: with ~12s per capture → 46 matches in ~35s (3 batches vs 6 with MAX=8).
    MAX_CONCURRENT = min(16, len(match_drivers))
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        # Lanzar capturas en paralelo (limitadas a MAX_CONCURRENT simultáneas)
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
    return len(resultados)


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
    ou_count = sum(1 for v in odds_ou.values() if v)
    if ou_count < 4:
        log.info(f"[Tab {tab_info['index']}]   O/U escasos ({ou_count}), intentando via mercado individual...")
        odds_ou_market = extraer_over_under_via_mercado(driver)
        for k, v in odds_ou_market.items():
            if v:
                odds_ou[k] = v
        ou_count = sum(1 for v in odds_ou.values() if v)
    log.info(f"[Tab {tab_info['index']}]   ✓ Over/Under: {ou_count}/28 valores capturados")

    log.info(f"[Tab {tab_info['index']}] → Extrayendo cuotas Resultado Correcto (via mercado, cuotas live)...")
    odds_rc = extraer_resultado_correcto_via_mercado(driver)
    rc_count = sum([1 for k, v in odds_rc.items() if v])
    if rc_count == 0:
        log.info(f"[Tab {tab_info['index']}]   RC via mercado sin datos (mercado no encontrado/suspendido), fallback a página evento...")
        odds_rc = extraer_resultado_correcto(driver)
        rc_count = sum([1 for k, v in odds_rc.items() if v])
    log.info(f"[Tab {tab_info['index']}]   ✓ Resultado Correcto: {rc_count}/30 valores capturados")

    # Saltar estadísticas en partidos pre_partido para acelerar ciclos
    estado_partido = info.get("estado_partido", "").strip()
    if estado_partido in ("pre_partido", ""):
        log.debug(f"[Tab {tab_info['index']}] Partido en pre_partido, saltando extracción de estadísticas")
        stats = {k: "" for k in [
            "xg_local", "xg_visitante", "posesion_local", "posesion_visitante",
            "corners_local", "corners_visitante", "tiros_local", "tiros_visitante",
            "tiros_puerta_local", "tiros_puerta_visitante", "faltas_local", "faltas_visitante",
            "saques_esquina_local", "saques_esquina_visitante", "fueras_juego_local", "fueras_juego_visitante",
            "momentum_local", "momentum_visitante", "opta_points_local", "opta_points_visitante",
            "big_chances_local", "big_chances_visitante", "shots_off_target_local", "shots_off_target_visitante",
            "attacks_local", "attacks_visitante", "dangerous_attacks_local", "dangerous_attacks_visitante",
            "hit_woodwork_local", "hit_woodwork_visitante", "tackles_local", "tackles_visitante",
            "duels_won_local", "duels_won_visitante", "saves_local", "saves_visitante",
            "interceptions_local", "interceptions_visitante", "pass_success_pct_local", "pass_success_pct_visitante",
            "crosses_local", "crosses_visitante", "successful_passes_opp_half_local", "successful_passes_opp_half_visitante",
            "throw_ins_local", "throw_ins_visitante", "goal_kicks_local", "goal_kicks_visitante",
            "free_kicks_local", "free_kicks_visitante", "injuries_local", "injuries_visitante",
            "shots_blocked_local", "shots_blocked_visitante", "substitutions_local", "substitutions_visitante"
        ]}
        stats_count = 0
    else:
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

    # Momentum: Primero intentar desde API (ya viene en stats), fallback a método visual
    momentum_local = stats.get("momentum_local", "")
    momentum_visitante = stats.get("momentum_visitante", "")

    if not momentum_local and not momentum_visitante:
        # Fallback visual: extrae momentum del iframe de Betfair
        mom_result = extraer_momentum(driver)
        momentum_local = mom_result.get("momentum_local", "")
        momentum_visitante = mom_result.get("momentum_visitante", "")
        if momentum_local or momentum_visitante:
            stats["momentum_local"] = momentum_local
            stats["momentum_visitante"] = momentum_visitante
            log.info(f"[Tab {tab_info['index']}] ✓ Momentum obtenido vía fallback visual")
        else:
            log.info(f"[Tab {tab_info['index']}] → Momentum no disponible (API ni visual)")
    else:
        log.info(f"[Tab {tab_info['index']}] ✓ Momentum obtenido de API")

    if momentum_local or momentum_visitante:
        log.info(f"[Tab {tab_info['index']}]     - Local: {momentum_local} | Visitante: {momentum_visitante}")

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
        # Over/Under 5.5
        "back_over55": odds_ou["back_over55"],
        "lay_over55": odds_ou["lay_over55"],
        "back_under55": odds_ou["back_under55"],
        "lay_under55": odds_ou["lay_under55"],
        # Over/Under 6.5
        "back_over65": odds_ou["back_over65"],
        "lay_over65": odds_ou["lay_over65"],
        "back_under65": odds_ou["back_under65"],
        "lay_under65": odds_ou["lay_under65"],
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
        "fouls_conceded_local": stats["fouls_conceded_local"],
        "fouls_conceded_visitante": stats["fouls_conceded_visitante"],
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
        "blocked_shots_local": stats["blocked_shots_local"],
        "blocked_shots_visitante": stats["blocked_shots_visitante"],
        "shooting_accuracy_local": stats["shooting_accuracy_local"],
        "shooting_accuracy_visitante": stats["shooting_accuracy_visitante"],
        "dangerous_attacks_local": stats["dangerous_attacks_local"],
        "dangerous_attacks_visitante": stats["dangerous_attacks_visitante"],
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
        "goal_kicks_local": stats["goal_kicks_local"],
        "goal_kicks_visitante": stats["goal_kicks_visitante"],
        "throw_ins_local": stats["throw_ins_local"],
        "throw_ins_visitante": stats["throw_ins_visitante"],
        "momentum_local": momentum_local,
        "momentum_visitante": momentum_visitante,
        # Volumen y meta
        "volumen_matched": volumen,
        "url": tab_info["url"],
    }

    # Extraer País y Liga de la URL
    pais, liga = extraer_pais_liga_de_url(tab_info["url"])
    datos["País"] = pais
    datos["Liga"] = liga

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
        "--ventana-despues", type=int, default=120,
        help="Minutos después del inicio del partido para dejar de trackear (default: 120)"
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
    # Also clean up orphaned chromedriver processes from previous runs
    limpiar_chromedrivers_huerfanos({})

    # Reset retry counters on fresh start
    _driver_creation_failures.clear()

    # Crear lista de partidos inicial para MatchDrivers
    partidos_csv = leer_games_csv("games.csv")
    # Filtrar partidos que necesitan driver Chrome (en vivo o próximos a empezar)
    partidos_para_drivers = filtrar_partidos_para_drivers(
        partidos_csv, args.ventana_antes, args.ventana_despues, args.output
    ) if partidos_csv else []

    # Si no hay scheduling, crear partidos desde urls_iniciales
    if not usar_scheduling and urls_iniciales:
        partidos_para_drivers = [
            {"url": url, "game": extraer_id_partido(url), "fecha_hora_inicio": None}
            for url in urls_iniciales
        ]

    # Crear MatchDrivers solo para partidos que necesitan driver (en vivo o próximos)
    log.info(f"\n🚀 Iniciando {len(partidos_para_drivers)} drivers Chrome (partidos en vivo o próximos)...")
    match_drivers = {}
    driver_login = None  # Driver para login manual

    # Heartbeat path (definido aquí para que el hilo de progreso lo use durante la init)
    heartbeat_path = os.path.join(args.output, ".heartbeat")
    global _md_progress_hb_path
    _md_progress_hb_path = heartbeat_path
    _md_progress_hb_stop.clear()
    _hb_writer_thread = threading.Thread(
        target=_heartbeat_background_writer, daemon=True, name="hb-writer"
    )
    _hb_writer_thread.start()
    log.info("📡 Heartbeat writer iniciado (actualiza progreso cada 4s)")

    try:
        # Crear primer driver para login manual
        if partidos_para_drivers:
            primer_partido = partidos_para_drivers[0]
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
        if len(partidos_para_drivers) > 1:
            log.info(f"🔧 Creando {len(partidos_para_drivers) - 1} drivers adicionales en paralelo...")

            def crear_driver_worker(partido):
                md = crear_match_driver(partido)
                return (partido["url"], md) if md else (partido["url"], None)

            executor = ThreadPoolExecutor(max_workers=min(16, len(partidos_para_drivers) - 1))
            futures = [
                executor.submit(crear_driver_worker, p)
                for p in partidos_para_drivers[1:]
            ]

            # Timeout proporcional al número de partidos (8s/partido, mínimo 180s)
            _init_timeout = max(180, len(partidos_para_drivers) * 8)
            log.info(f"⏳ Timeout de inicialización: {_init_timeout}s para {len(partidos_para_drivers)} drivers")
            try:
                for future in as_completed(futures, timeout=_init_timeout):
                    try:
                        url, md = future.result(timeout=10)
                        if md:
                            match_drivers[md.match_id] = md
                    except Exception as e:
                        log.warning(f"Error obteniendo resultado de driver: {e}")
            except TimeoutError:
                log.warning(f"Timeout esperando drivers. Continuando con {len(match_drivers)} drivers creados.")
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

        log.info(f"✓ {len(match_drivers)} drivers creados exitosamente")

        # Iniciar CSV writer
        writer = CSVWriter(args.output)
        ciclo_num = 0

        log.info("=" * 60)
        log.info("CAPTURA INICIADA - Presiona Ctrl+C para detener")
        log.info("=" * 60)

        consecutive_all_fail = 0  # Track cycles where ALL drivers fail

        # Loop principal
        while ejecutando:
            ciclo_num += 1
            inicio_ciclo = time.time()

            try:
                log.info(f"\n--- Ciclo #{ciclo_num} ---")

                # ── Captura paralela ──
                capturas_exitosas = 0
                if match_drivers:
                    capturas_exitosas = captura_paralela_multidriver(list(match_drivers.values()), writer)
                else:
                    log.info("⏰ Sin partidos activos para capturar en este ciclo")

                # ── P0: Detect silent failure (all drivers dead) ──
                if match_drivers and capturas_exitosas == 0:
                    consecutive_all_fail += 1
                    if consecutive_all_fail >= 3:
                        log.error(f"🚨 {consecutive_all_fail} ciclos consecutivos sin capturas exitosas! Intentando recuperación...")
                        limpiar_chromedrivers_huerfanos(match_drivers)
                        # Try to restart all dead drivers
                        for match_id, md in list(match_drivers.items()):
                            if not md.esta_vivo():
                                if md.reiniciar():
                                    log.info(f"   ✓ Recuperado: {md.game[:40]}")
                                else:
                                    log.warning(f"   ✗ No se pudo recuperar: {md.game[:40]}")
                        consecutive_all_fail = 0
                else:
                    consecutive_all_fail = 0

                # ── P0: Auto-restart dead drivers ──
                drivers_muertos = [
                    (match_id, md) for match_id, md in match_drivers.items()
                    if md.driver is None and md._consecutive_failures >= 3
                ]
                if drivers_muertos:
                    log.info(f"🔄 Reiniciando {len(drivers_muertos)} drivers muertos...")
                    limpiar_chromedrivers_huerfanos(match_drivers)
                    for match_id, md in drivers_muertos:
                        if md.reiniciar():
                            log.info(f"   ✓ Reiniciado: {md.game[:40]}")
                        else:
                            log.warning(f"   ✗ Reinicio fallido: {md.game[:40]}")

                # ── P2: Periodic zombie cleanup (every 30 cycles) ──
                if ciclo_num % 30 == 0:
                    limpiar_chromedrivers_huerfanos(match_drivers)

                # ── Recarga periódica de games.csv ──
                if args.reload_interval > 0 and ciclo_num % args.reload_interval == 0:
                    log.info(f"🔄 Revisando games.csv para detectar cambios...")

                    partidos_csv = leer_games_csv("games.csv")
                    if partidos_csv:
                        # Filtrar partidos que necesitan driver (en vivo o próximos)
                        partidos_necesitan_driver = filtrar_partidos_para_drivers(
                            partidos_csv, args.ventana_antes, args.ventana_despues, args.output
                        )

                        # Identificar drivers a cerrar (partidos que ya no necesitan driver)
                        urls_necesitan_driver = {p["url"] for p in partidos_necesitan_driver}
                        drivers_a_cerrar = [
                            match_id for match_id, md in match_drivers.items()
                            if md.url not in urls_necesitan_driver
                        ]

                        if drivers_a_cerrar:
                            log.info(f"🗑️  Cerrando {len(drivers_a_cerrar)} drivers (partidos finalizados o futuros)...")
                            for match_id in drivers_a_cerrar:
                                md = match_drivers.pop(match_id)
                                md.cerrar()
                                log.debug(f"   - Cerrado: {match_id}")

                        # Reset retry counters when drivers are freed (resources available again)
                        if drivers_a_cerrar and _driver_creation_failures:
                            log.info(f"Reseteando {len(_driver_creation_failures)} contadores de reintentos (se liberaron {len(drivers_a_cerrar)} drivers)")
                            _driver_creation_failures.clear()

                        # Clean up retry counters for URLs no longer in games.csv
                        urls_csv = {p["url"] for p in partidos_csv}
                        stale_urls = [u for u in _driver_creation_failures if u not in urls_csv]
                        for u in stale_urls:
                            del _driver_creation_failures[u]

                        # Identificar partidos nuevos a abrir (próximos que ahora necesitan driver)
                        urls_existentes = {md.url for md in match_drivers.values()}
                        partidos_nuevos = [
                            p for p in partidos_necesitan_driver
                            if p["url"] not in urls_existentes
                        ]

                        # Filter out matches that have exceeded retry limit
                        if partidos_nuevos:
                            partidos_a_intentar = []
                            for p in partidos_nuevos:
                                url = p["url"]
                                failures = _driver_creation_failures.get(url, 0)
                                if failures >= MAX_DRIVER_RETRIES:
                                    log.debug(f"⏭️  Saltando {p['game'][:40]} ({failures} intentos fallidos)")
                                    continue
                                partidos_a_intentar.append(p)

                            if not partidos_a_intentar and partidos_nuevos:
                                log.warning(f"⚠️  {len(partidos_nuevos)} partidos pendientes excedieron el límite de reintentos ({MAX_DRIVER_RETRIES})")
                            partidos_nuevos = partidos_a_intentar

                        if partidos_nuevos:
                            # Clean up zombie chromedriver processes before creating new ones
                            limpiar_chromedrivers_huerfanos(match_drivers)

                            log.info(f"➕ Abriendo {len(partidos_nuevos)} nuevos partidos...")

                            with ThreadPoolExecutor(max_workers=min(8, len(partidos_nuevos))) as executor:
                                futures = {
                                    executor.submit(crear_match_driver, p): p
                                    for p in partidos_nuevos
                                }

                                for future in as_completed(futures):
                                    partido = futures[future]
                                    md = future.result()
                                    if md:
                                        match_drivers[md.match_id] = md
                                        # Reset failure counter on success
                                        _driver_creation_failures.pop(partido["url"], None)
                                        log.info(f"   - {md.game[:40]}")
                                    else:
                                        # Track failure
                                        url = partido["url"]
                                        _driver_creation_failures[url] = _driver_creation_failures.get(url, 0) + 1
                                        count = _driver_creation_failures[url]
                                        log.warning(f"   ✗ {partido['game'][:40]} (intento {count}/{MAX_DRIVER_RETRIES})")

                        if drivers_a_cerrar or partidos_nuevos:
                            log.info(f"✓ Drivers actualizados: {len(match_drivers)} partidos activos")

                # ── P2: Write heartbeat file ──
                _write_progress_heartbeat_now(
                    heartbeat_path,
                    cycle=ciclo_num,
                    captures=capturas_exitosas if match_drivers else -1,
                    fail_count=consecutive_all_fail,
                )

            except Exception as e:
                # P0: Single cycle failure should NOT kill the scraper
                log.error(f"❌ Error en ciclo #{ciclo_num}: {e}", exc_info=True)
                log.info("Continuando al siguiente ciclo...")
                time.sleep(2)  # Brief pause to avoid tight error loops
                continue

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
