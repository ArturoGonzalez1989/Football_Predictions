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
)

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("betfair_scraper")

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
    # Over/Under 2.5
    "back_over25",
    "lay_over25",
    "back_under25",
    "lay_under25",
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
    """
    resultado = {
        "back_home": "", "lay_home": "",
        "back_draw": "", "lay_draw": "",
        "back_away": "", "lay_away": "",
    }

    # Intentar con selectores principales y alternativos
    for sel_group in [SELECTORES, SELECTORES_ALT]:
        try:
            runners = driver.find_elements(By.CSS_SELECTOR, sel_group["runner_row"])
            if len(runners) < 3:
                continue

            claves = [
                ("back_home", "lay_home"),
                ("back_draw", "lay_draw"),
                ("back_away", "lay_away"),
            ]

            for i, (key_back, key_lay) in enumerate(claves):
                if i >= len(runners):
                    break
                row = runners[i]

                # Precio back
                try:
                    backs = row.find_elements(By.CSS_SELECTOR, sel_group["back_price"])
                    if backs:
                        resultado[key_back] = limpiar_precio(backs[0].text)
                except (NoSuchElementException, StaleElementReferenceException):
                    pass

                # Precio lay
                try:
                    lays = row.find_elements(By.CSS_SELECTOR, sel_group["lay_price"])
                    if lays:
                        resultado[key_lay] = limpiar_precio(lays[0].text)
                except (NoSuchElementException, StaleElementReferenceException):
                    pass

            # Si obtuvimos al menos un precio, devolver
            if any(resultado.values()):
                return resultado

        except (NoSuchElementException, StaleElementReferenceException, WebDriverException):
            continue

    return resultado


def extraer_over_under(driver) -> dict:
    """
    Intenta extraer cuotas Over/Under 2.5 goles.
    NOTA: En Betfair Exchange, Over/Under suele estar en un mercado separado.
    Si la página muestra múltiples mercados, intenta encontrarlo.
    """
    resultado = {
        "back_over25": "", "lay_over25": "",
        "back_under25": "", "lay_under25": "",
    }

    try:
        # Buscar secciones de mercado que contengan "Over/Under" o "Más/Menos"
        mercados = driver.find_elements(
            By.CSS_SELECTOR,
            ".market-container, .mv-market, [data-testid='market']"
        )

        for mercado in mercados:
            texto_mercado = mercado.text.lower()
            if "over" in texto_mercado or "under" in texto_mercado or "más" in texto_mercado:
                for sel_group in [SELECTORES, SELECTORES_ALT]:
                    runners = mercado.find_elements(By.CSS_SELECTOR, sel_group["runner_row"])
                    if len(runners) >= 2:
                        # Runner 0 = Over, Runner 1 = Under (convención Betfair)
                        for j, (key_b, key_l) in enumerate([
                            ("back_over25", "lay_over25"),
                            ("back_under25", "lay_under25"),
                        ]):
                            if j >= len(runners):
                                break
                            row = runners[j]
                            try:
                                backs = row.find_elements(
                                    By.CSS_SELECTOR, sel_group["back_price"]
                                )
                                if backs:
                                    resultado[key_b] = limpiar_precio(backs[0].text)
                            except (NoSuchElementException, StaleElementReferenceException):
                                pass
                            try:
                                lays = row.find_elements(
                                    By.CSS_SELECTOR, sel_group["lay_price"]
                                )
                                if lays:
                                    resultado[key_l] = limpiar_precio(lays[0].text)
                            except (NoSuchElementException, StaleElementReferenceException):
                                pass

                        if any(resultado.values()):
                            return resultado

    except WebDriverException as e:
        log.debug(f"No se pudo extraer Over/Under: {e}")

    return resultado


def extraer_info_partido(driver) -> dict:
    """Extrae información del estado del partido: minuto, marcador, nombre evento."""
    info = {"evento": "", "minuto": "", "goles_local": "", "goles_visitante": ""}

    # Nombre del evento
    info["evento"] = buscar_elemento_texto(driver, SELECTORES["event_name"], timeout=3)

    # Tiempo/minuto del partido
    tiempo_txt = buscar_elemento_texto(driver, SELECTORES["match_time"], timeout=2)
    if tiempo_txt:
        # Extraer número de minuto (ej: "45:00" -> "45", "67'" -> "67")
        match = re.search(r"(\d+)", tiempo_txt)
        if match:
            info["minuto"] = match.group(1)

    # Marcador
    score_txt = buscar_elemento_texto(driver, SELECTORES["match_score"], timeout=2)
    if score_txt:
        # Formato esperado: "2 - 1", "2-1", etc.
        match = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_txt)
        if match:
            info["goles_local"] = match.group(1)
            info["goles_visitante"] = match.group(2)

    return info


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

    opciones.add_argument(f"--user-agent={USER_AGENT}")
    opciones.add_argument(f"--lang={CHROME_LANG}")
    opciones.add_argument("--disable-blink-features=AutomationControlled")
    opciones.add_argument("--disable-extensions")
    opciones.add_argument("--no-sandbox")
    opciones.add_argument("--disable-dev-shm-usage")
    opciones.add_argument("--window-size=1920,1080")
    opciones.add_argument("--start-maximized")

    # Evitar detección de Selenium
    opciones.add_experimental_option("excludeSwitches", ["enable-automation"])
    opciones.add_experimental_option("useAutomationExtension", False)

    # Preferencias para idioma español
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

    driver.implicitly_wait(5)
    return driver


# ── Lógica principal ─────────────────────────────────────────────────────────

def abrir_pestanas(driver: webdriver.Chrome, urls: list) -> list:
    """Abre una pestaña por cada URL. Devuelve lista de (handle, url, tab_id)."""
    tabs = []
    for i, url in enumerate(urls):
        if i == 0:
            # La primera pestaña ya existe
            driver.get(url)
        else:
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(url)

        tab_id = extraer_id_partido(url)
        handle = driver.window_handles[-1]
        tabs.append({"handle": handle, "url": url, "tab_id": tab_id, "index": i})
        log.info(f"Pestaña {i}: {tab_id} -> {url[:80]}...")
        time.sleep(2)  # Pequeña pausa entre aperturas

    return tabs


def capturar_pestaña(driver: webdriver.Chrome, tab_info: dict) -> dict:
    """Captura todos los datos de una pestaña. Devuelve dict con datos CSV."""
    try:
        driver.switch_to.window(tab_info["handle"])
    except WebDriverException as e:
        log.error(f"Error al cambiar a pestaña {tab_info['tab_id']}: {e}")
        return None

    # Pequeña espera para que cargue
    time.sleep(1)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Extraer datos
    info = extraer_info_partido(driver)
    odds_mo = extraer_runners_match_odds(driver)
    odds_ou = extraer_over_under(driver)
    volumen = extraer_volumen(driver)

    datos = {
        "tab_id": tab_info["tab_id"],
        "timestamp_utc": timestamp,
        "evento": info["evento"],
        "minuto": info["minuto"],
        "goles_local": info["goles_local"],
        "goles_visitante": info["goles_visitante"],
        "back_home": odds_mo["back_home"],
        "lay_home": odds_mo["lay_home"],
        "back_draw": odds_mo["back_draw"],
        "lay_draw": odds_mo["lay_draw"],
        "back_away": odds_mo["back_away"],
        "lay_away": odds_mo["lay_away"],
        "back_over25": odds_ou["back_over25"],
        "lay_over25": odds_ou["lay_over25"],
        "back_under25": odds_ou["back_under25"],
        "lay_under25": odds_ou["lay_under25"],
        "volumen_matched": volumen,
        "url": tab_info["url"],
    }

    # Log resumen
    resumen = (
        f"[Tab {tab_info['index']}] {info['evento'] or tab_info['tab_id']} "
        f"| Min:{info['minuto'] or '?'} "
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
    args = parser.parse_args()

    urls = args.urls or MATCH_URLS
    if not urls:
        log.error("No hay URLs configuradas. Edita config.py o usa --urls.")
        sys.exit(1)

    log.info(f"Iniciando observador con {len(urls)} partidos.")
    log.info(f"Ciclo: {args.ciclo}s | Output: {args.output}/")

    # Iniciar Chrome
    log.info("Iniciando Chrome...")
    driver = crear_driver()

    try:
        # Abrir pestañas
        tabs = abrir_pestanas(driver, urls)

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
            ciclo_captura(driver, tabs, writer)

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
        try:
            driver.quit()
        except Exception:
            pass
        log.info("Observador finalizado. Revisa los CSV en la carpeta de salida.")


if __name__ == "__main__":
    main()
