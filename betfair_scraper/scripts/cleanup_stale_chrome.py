#!/usr/bin/env python3
"""
Script inteligente para cerrar ventanas de Chrome huérfanas del scraper.
Cierra solo ventanas con:
- Partidos que ya no están en games.csv (eliminados)
- URLs que devuelven 404
- Partidos terminados (>2h desde inicio)

NO toca ventanas de partidos activos que se están trackeando.
"""

import csv
import psutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Configuración
GAMES_CSV = Path(__file__).parent.parent / "games.csv"
MATCH_DURATION_MINUTES = 120  # Máximo 2h de tracking
DATE_FORMATS = ["%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"]


def parse_date(date_str):
    """Parsea fecha en múltiples formatos"""
    if not date_str or not date_str.strip():
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def load_active_matches():
    """Carga partidos activos desde games.csv"""
    active_urls = set()

    if not GAMES_CSV.exists():
        return active_urls

    try:
        with open(GAMES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("url", "").strip()
                fecha_str = row.get("fecha_hora_inicio", "").strip()

                if not url:
                    continue

                # Verificar si el partido aún está en ventana de tracking
                start_time = parse_date(fecha_str)
                if start_time:
                    ahora = datetime.now()
                    fin_tracking = start_time + timedelta(minutes=MATCH_DURATION_MINUTES)

                    # Solo incluir si está en ventana de tracking
                    if ahora <= fin_tracking:
                        active_urls.add(url.lower())
                else:
                    # Sin fecha, considerarlo activo (legacy)
                    active_urls.add(url.lower())

    except Exception as e:
        print(f"[ERROR] Error leyendo games.csv: {e}")

    return active_urls


def get_chrome_processes_with_betfair():
    """
    Obtiene PIDs de procesos Chrome que tienen Betfair abierto.
    Retorna dict: {pid: url}
    """
    chrome_betfair = {}

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] and 'chrome.exe' in proc.info['name'].lower():
                cmdline = proc.info.get('cmdline', [])
                if cmdline:
                    # Buscar URLs de Betfair en los argumentos
                    for arg in cmdline:
                        if isinstance(arg, str) and 'betfair.es' in arg.lower():
                            chrome_betfair[proc.info['pid']] = arg
                            break
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return chrome_betfair


def check_url_is_404(url):
    """
    Verifica si una URL devuelve 404 usando Selenium headless.
    Retorna True si es 404, False si funciona.
    """
    driver = None
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        driver.set_page_load_timeout(10)
        driver.get(url)

        # Verificar título de error 404
        title = driver.title.lower()
        body_text = driver.find_element("tag name", "body").text.lower()

        is_404 = any([
            "404" in title,
            "not found" in title,
            "no encontrado" in title,
            "404" in body_text[:200],
            "page not found" in body_text[:200],
            "página no encontrada" in body_text[:200]
        ])

        return is_404

    except Exception as e:
        # Si hay timeout o error, asumir que está rota
        print(f"[DEBUG] Error verificando {url[:80]}: {e}")
        return True

    finally:
        if driver:
            driver.quit()


def cleanup_stale_chrome_windows():
    """
    Limpia ventanas de Chrome huérfanas.
    """
    print("\n" + "="*70)
    print("LIMPIEZA INTELIGENTE DE VENTANAS CHROME HUÉRFANAS")
    print("="*70)

    # Cargar partidos activos
    print("\n[1] Cargando partidos activos desde games.csv...")
    active_urls = load_active_matches()
    print(f"    OK: {len(active_urls)} partidos activos en tracking")

    # Encontrar procesos Chrome con Betfair
    print("\n[2] Buscando procesos Chrome con Betfair...")
    chrome_procs = get_chrome_processes_with_betfair()
    print(f"    OK {len(chrome_procs)} procesos Chrome con Betfair")

    if not chrome_procs:
        print("\n[OK] No hay ventanas de Chrome con Betfair abiertas")
        return

    # Clasificar ventanas
    print("\n[3] Clasificando ventanas...")
    to_kill = []
    to_keep = []

    for pid, url in chrome_procs.items():
        url_lower = url.lower()

        # REGLA 1: Si está en partidos activos, MANTENER
        if any(active_url in url_lower for active_url in active_urls):
            to_keep.append((pid, url, "Partido activo"))
            continue

        # REGLA 2: Si no está en activos, es HUÉRFANA
        # Verificar si es 404 (opcional, puede ser lento)
        # is_404 = check_url_is_404(url)
        # if is_404:
        #     to_kill.append((pid, url, "URL 404"))
        #     continue

        # Por defecto: no está en games.csv = huérfana
        to_kill.append((pid, url, "No en games.csv (partido eliminado/terminado)"))

    # Mostrar resumen
    print(f"\n    Ventanas a MANTENER: {len(to_keep)}")
    for pid, url, razon in to_keep[:5]:
        print(f"      [PID {pid}] {url[:70]}... ({razon})")

    print(f"\n    Ventanas a CERRAR: {len(to_kill)}")
    for pid, url, razon in to_kill[:10]:
        print(f"      [PID {pid}] {url[:70]}... ({razon})")

    # Confirmar y cerrar
    if to_kill:
        print(f"\n[4] Cerrando {len(to_kill)} ventanas huérfanas...")
        closed = 0
        for pid, url, razon in to_kill:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=3)
                closed += 1
                print(f"    OK Cerrado PID {pid}")
            except Exception as e:
                print(f"    ERROR Error cerrando PID {pid}: {e}")

        print(f"\n[LIMPIEZA COMPLETADA]")
        print(f"   - Cerradas: {closed} ventanas")
        print(f"   - Mantenidas: {len(to_keep)} ventanas")
    else:
        print(f"\n[OK] No hay ventanas huérfanas para cerrar")

    print("="*70 + "\n")


if __name__ == "__main__":
    cleanup_stale_chrome_windows()
