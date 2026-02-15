#!/usr/bin/env python3
"""
Script de busqueda de partidos en Betfair
Usa Playwright (no Selenium) para evitar deteccion anti-bot.
Usa la pagina "Todos" (/futbol-apuestas-1) que muestra TODOS los partidos
y recorre la paginacion (/2, /3...) para no perderse ninguno.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlparse
import time
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Configuracion
# La pagina "Todos" muestra todos los partidos (en juego + hoy + proximos).
# La pagina "En Juego" muestra solo partidos que estan en vivo AHORA.
BETFAIR_TODOS_URL = "https://www.betfair.es/exchange/plus/es/f%C3%BAtbol-apuestas-1"
BETFAIR_EN_JUEGO_URL = "https://www.betfair.es/exchange/plus/inplay/football"
GAMES_CSV = Path(__file__).parent.parent / "games.csv"
HEADLESS = True
TIMEOUT = 15000  # ms para Playwright
MAX_PAGES = 10   # Maximo de paginas de paginacion a recorrer


def setup_browser(playwright):
    """Lanza Chromium con Playwright y calienta la sesion en Betfair."""
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-web-security",
        ]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080},
        locale="es-ES",
    )
    # Eliminar navigator.webdriver para evitar deteccion
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)
    page = context.new_page()

    # Calentar sesion: navegar primero a la home de Betfair Exchange
    print("[INFO] Calentando sesion en Betfair...")
    page.goto("https://www.betfair.es/exchange/plus/es", wait_until="domcontentloaded", timeout=30000)
    time.sleep(3)
    _accept_cookies(page)
    time.sleep(2)

    return browser, context, page


def _accept_cookies(page):
    """Acepta cookies si aparece el banner de consentimiento."""
    try:
        for selector in [
            "#onetrust-accept-btn-handler",
            "button#onetrust-accept-btn-handler",
            "button:has-text('Aceptar todas')",
            "button:has-text('Aceptar')",
            "button:has-text('Accept')",
        ]:
            btn = page.query_selector(selector)
            if btn:
                try:
                    if btn.is_visible():
                        btn.click()
                        print("[INFO] Cookie consent aceptado")
                        time.sleep(1)
                        return
                except Exception:
                    continue
    except Exception:
        pass


def _scrape_page(page, url, label):
    """Navega a una URL y extrae partidos."""
    print(f"[INFO] [{label}] Accediendo a: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)

    # Aceptar cookies (por si no se acepto antes)
    _accept_cookies(page)

    # Esperar a que cargue contenido dinamico (SPA de Betfair)
    time.sleep(5)

    # Verificar si dice "No hay eventos"
    no_events = page.query_selector("//*[contains(text(), 'No hay eventos')]")
    if no_events:
        print(f"[INFO] [{label}] No hay eventos que mostrar")
        return []

    # Esperar links de partidos
    try:
        page.wait_for_selector("a[href*='apuestas-']", timeout=TIMEOUT)
    except PlaywrightTimeout:
        print(f"[WARNING] [{label}] Timeout esperando links de partidos")
        return []

    # Esperar un poco mas para que se renderice todo el contenido SPA
    time.sleep(3)

    # Scroll para cargar lazy content
    prev_height = 0
    for _ in range(10):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == prev_height:
            break
        prev_height = new_height
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(1)

    return extract_football_matches(page)


def _scrape_with_pagination(page, base_url, label):
    """Recorre todas las paginas de paginacion de Betfair.

    Ejemplo: /futbol-apuestas-1 -> /futbol-apuestas-1/2 -> /3 -> ...
    """
    all_matches = {}  # name -> match dict (dedup)

    for page_num in range(1, MAX_PAGES + 1):
        if page_num == 1:
            url = base_url
        else:
            url = f"{base_url}/{page_num}"

        found = _scrape_page(page, url, f"{label} p{page_num}")
        print(f"[INFO] [{label} p{page_num}] Encontrados {len(found)} partidos")

        if not found:
            break

        new_count = 0
        for m in found:
            if m["name"] not in all_matches:
                all_matches[m["name"]] = m
                new_count += 1

        if new_count == 0:
            print(f"[INFO] [{label}] Pagina {page_num}: sin partidos nuevos, fin de paginacion")
            break

        # Verificar si hay boton "Siguiente"
        next_btn = page.query_selector("a[title='Siguiente']")
        if not next_btn:
            print(f"[INFO] [{label}] No hay boton 'Siguiente' - fin de paginacion")
            break

    return list(all_matches.values())


def find_matches_on_betfair():
    """
    Busca partidos de futbol en Betfair usando Playwright.
    Busca en DOS paginas:
    1. "En Juego" - partidos en vivo AHORA
    2. "Todos" - todos los partidos (en juego + futuros)
    """
    all_matches = {}

    try:
        print("[INFO] Iniciando busqueda de partidos en Betfair (Playwright)...")

        with sync_playwright() as pw:
            browser, context, page = setup_browser(pw)

            try:
                # 1. Buscar primero en "En Juego" (partidos en vivo)
                print("\n[INFO] === Buscando en 'En Juego' (partidos en vivo) ===")
                for m in _scrape_with_pagination(page, BETFAIR_EN_JUEGO_URL, "EN_JUEGO"):
                    # Confiar en extract_start_time_from_text() para detectar si es en vivo
                    all_matches.setdefault(m["name"], m)

                # 2. Buscar en "Todos" (partidos futuros + en juego)
                print("\n[INFO] === Buscando en 'Todos' (partidos futuros) ===")
                for m in _scrape_with_pagination(page, BETFAIR_TODOS_URL, "TODOS"):
                    all_matches.setdefault(m["name"], m)

            finally:
                context.close()
                browser.close()

        matches = list(all_matches.values())

        if matches:
            print(f"\n[OK] Total: {len(matches)} partidos encontrados:")
            for match in matches:
                print(f"   - {match['name']} ({match['start_time']})")
        else:
            print("[INFO] No hay partidos de futbol disponibles en este momento")

        return matches

    except Exception as e:
        print(f"[ERROR] Error buscando partidos: {e}")
        import traceback
        traceback.print_exc()
        return list(all_matches.values())


def extract_football_matches(page):
    """
    Parsea la pagina de Betfair y extrae todos los partidos de futbol.
    Busca links <a> con URL que contenga 'apuestas-' + ID numerico largo.
    """
    matches = []

    try:
        all_links = page.query_selector_all("a[href*='apuestas-']")
        print(f"[DEBUG] Links con 'apuestas-': {len(all_links)}")

        skip_count = {"no_futbol": 0, "no_id": 0, "no_text": 0, "no_teams": 0}

        for link in all_links:
            try:
                href = link.get_attribute("href") or ""

                # Filtro: solo futbol (URL encoded o texto plano con tilde)
                href_lower = href.lower()
                if not ("/futbol/" in href_lower or "/f%c3%batbol/" in href_lower
                        or "tbol/" in href_lower or "/football/" in href_lower):
                    skip_count["no_futbol"] += 1
                    # print(f"[DEBUG] Skipped (no futbol): {href}")  # Uncomment for debugging
                    continue

                # Filtro: partido especifico con ID numerico largo
                id_match = re.search(r"apuestas-(\d{7,})", href)
                if not id_match:
                    skip_count["no_id"] += 1
                    continue

                # Extraer texto del link
                link_text = (link.text_content() or "").strip()
                if not link_text:
                    skip_count["no_text"] += 1
                    continue

                # Extraer equipos de sub-elementos <li>
                li_elements = link.query_selector_all("li")
                team_names = []
                for li in li_elements:
                    name = (li.text_content() or "").strip()
                    if (name and len(name) > 1
                            and not name.startswith("$")
                            and "Apuestas" not in name
                            and not name.startswith("Igualado")
                            and "Betfair" not in name
                            and "DAZN" not in name
                            and "Movistar" not in name
                            and "TV" not in name
                            and "guelo" not in name):
                        team_names.append(name)

                if len(team_names) < 2:
                    skip_count["no_teams"] += 1
                    continue

                match_name = f"{team_names[0]} - {team_names[1]}"

                # URL completa
                if href.startswith("http"):
                    pass  # ya es absoluta
                elif href.startswith("/"):
                    # Absoluta sin dominio: /exchange/plus/es/...
                    href = "https://www.betfair.es" + href
                else:
                    # Relativa: es/futbol/... -> necesita /exchange/plus/ prefijo
                    href = "https://www.betfair.es/exchange/plus/" + href

                # URL-encode caracteres Unicode (futbol -> f%C3%BAtbol, etc.)
                parsed = urlparse(href)
                encoded_path = quote(parsed.path, safe="/:@!$&'()*+,;=-._~")
                href = f"{parsed.scheme}://{parsed.netloc}{encoded_path}"

                # Extraer hora de inicio
                start_time = extract_start_time_from_text(link_text)

                matches.append({
                    "name": match_name,
                    "url": href,
                    "start_time": start_time,
                })

            except Exception as e:
                print(f"[DEBUG] Error extrayendo partido: {e}")
                continue

        print(f"[DEBUG] Skipped: {skip_count}")

        # Deduplicar por nombre
        seen = set()
        unique = []
        for m in matches:
            if m["name"] not in seen:
                seen.add(m["name"])
                unique.append(m)

        return unique

    except Exception as e:
        print(f"[ERROR] Error extrayendo partidos: {e}")
        return []


_DAY_ABBR_MAP = {"lun": 0, "mar": 1, "mié": 2, "mie": 2, "mi\u00e9": 2,
                  "jue": 3, "vie": 4, "sáb": 5, "sab": 5, "s\u00e1b": 5, "dom": 6}
_MONTH_ABBR_MAP = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
                    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}


def _next_weekday(day_abbr, hour, minute):
    """Calcula la proxima fecha que corresponde a un dia de la semana."""
    target_wd = _DAY_ABBR_MAP.get(day_abbr.lower().rstrip("."))
    if target_wd is None:
        return None
    now = datetime.now()
    current_wd = now.weekday()
    days_ahead = (target_wd - current_wd) % 7
    if days_ahead == 0:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate < now - timedelta(hours=2):
            days_ahead = 7  # ya paso hoy, sera la proxima semana
    result = now + timedelta(days=days_ahead)
    return result.replace(hour=hour, minute=minute, second=0, microsecond=0)


def extract_start_time_from_text(text):
    """Extrae hora de inicio a partir del texto visible del link.

    Formatos de Betfair:
    - "Comienza en X'"                        → ahora + X minutos
    - "Hoy 20:45"                             → hoy a esa hora
    - "mar. 17 feb., 20:45"                   → fecha completa
    - "mar. 20:45"                            → proximo martes a esa hora
    - "Proximamente"                          → ~15 min
    - "45' 1 0", "DESC.", "90' +3"            → en juego
    """
    try:
        # "Comienza en X'"
        m = re.search(r"Comienza en (\d+)'", text)
        if m:
            return (datetime.now() + timedelta(minutes=int(m.group(1)))).strftime("%Y-%m-%d %H:%M")

        # "Hoy HH:MM"
        m = re.search(r"Hoy\s+(\d{1,2}):(\d{2})", text)
        if m:
            return datetime.now().replace(
                hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0
            ).strftime("%Y-%m-%d %H:%M")

        # "mar. 17 feb., 20:45" — dia semana + dia mes + mes + hora
        m = re.search(
            r"(?:dom|lun|mar|mi[eé]|jue|vie|s[aá]b)\.?\s+(\d{1,2})\s+"
            r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)\.?,?\s+"
            r"(\d{1,2}):(\d{2})", text
        )
        if m:
            day = int(m.group(1))
            month = _MONTH_ABBR_MAP.get(m.group(2).lower(), 1)
            hour = int(m.group(3))
            minute = int(m.group(4))
            year = datetime.now().year
            # Si la fecha ya paso este año, sera el proximo
            candidate = datetime(year, month, day, hour, minute)
            if candidate < datetime.now() - timedelta(days=1):
                candidate = datetime(year + 1, month, day, hour, minute)
            return candidate.strftime("%Y-%m-%d %H:%M")

        # "dom. 20:45", "lun. 18:00" — dia semana + hora (sin fecha)
        m = re.search(
            r"(dom|lun|mar|mi[eé]|jue|vie|s[aá]b)\.?\s+(\d{1,2}):(\d{2})", text
        )
        if m:
            result = _next_weekday(m.group(1), int(m.group(2)), int(m.group(3)))
            if result:
                return result.strftime("%Y-%m-%d %H:%M")

        # "Proximamente"
        if "ximamente" in text.lower():
            return (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M")

        # En juego (marcador, minuto visible, descanso)
        # Patrones: "90' +3", "DESC.", "71' 2 0", etc.
        if ("DESC." in text or
            re.search(r"\d+'\s*\+", text) or  # "90' +3"
            re.search(r"^\d+'\s", text) or     # "71' " al inicio
            re.search(r"\s\d+'\s", text)):     # " 71' " en medio
            return (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")

        # Default: NO asumir en juego — marcar como futuro lejano para que
        # _is_relevant_match lo descarte
        print(f"[DEBUG] Hora no reconocida, descartando: {text[:80]!r}")
        return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")


def _is_relevant_match(start_time_str):
    """Determina si un partido es relevante para trackear.
    Solo partidos en juego (pasados) o que empiezan dentro de 3 horas.
    Excluye partidos de manana o mas alla."""
    try:
        start = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
        now = datetime.now()
        cutoff = now + timedelta(hours=3)
        # Partidos en juego (start_time en el pasado) o empezando pronto
        return start <= cutoff
    except Exception:
        return True  # En caso de error, incluir por si acaso


def add_new_matches_to_csv(discovered_matches):
    """
    Lee games.csv, compara con partidos descubiertos.
    Añade solo los nuevos que sean relevantes (en juego o proximos 3h).
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

    # Identificar nuevos partidos (solo relevantes: en juego o proximos 3h)
    added = 0
    skipped_future = 0
    for match in discovered_matches:
        game_name = match["name"]

        if game_name not in existing_games:
            if not _is_relevant_match(match["start_time"]):
                skipped_future += 1
                continue
            existing_games[game_name] = {
                "Game": game_name,
                "url": match["url"],
                "fecha_hora_inicio": match["start_time"],
            }
            added += 1
            print(f"   + {game_name} ({match['start_time']})")
    if skipped_future:
        print(f"   (omitidos {skipped_future} partidos futuros >3h)")

    # Guardar si hay cambios
    if added > 0:
        try:
            with open(GAMES_CSV, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["Game", "url", "fecha_hora_inicio"])
                writer.writeheader()
                writer.writerows(existing_games.values())

            print(f"\n[BUSQUEDA COMPLETADA]")
            print(f"   - Nuevos: {added} partidos")
            print(f"   - Total en games.csv: {len(existing_games)} partidos")

        except Exception as e:
            print(f"[ERROR] Error guardando games.csv: {e}")
            return 0
    else:
        print(f"[OK] Sin cambios - {len(existing_games)} partidos en games.csv")

    return added


def main():
    """Funcion principal"""
    print("\n" + "=" * 60)
    print("BUSQUEDA DE PARTIDOS EN BETFAIR (Playwright + paginacion)")
    print("=" * 60)

    matches = find_matches_on_betfair()
    added = add_new_matches_to_csv(matches)

    print("=" * 60 + "\n")
    return added


if __name__ == "__main__":
    main()
