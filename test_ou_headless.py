"""
Test: ¿Qué ve el scraper en headless mode para Over/Under?
Replica exactamente la configuración del scraper y ejecuta las mismas funciones.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "betfair_scraper"))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

URL = "https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/uefa-champions-league/galatasaray-juventus-apuestas-35207338"

# Misma config que crear_driver() en main.py
opciones = Options()
opciones.add_argument("--headless=new")
opciones.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
opciones.add_argument("--lang=es-ES,es;q=0.9")
opciones.add_argument("--disable-blink-features=AutomationControlled")
opciones.add_argument("--no-sandbox")
opciones.add_argument("--disable-dev-shm-usage")
opciones.add_argument("--window-size=1920,1080")
opciones.add_argument("--start-maximized")
opciones.add_argument("--disable-gpu")
opciones.add_argument("--disable-extensions")

driver = webdriver.Chrome(options=opciones)

try:
    print(f"Navegando a {URL}...")
    driver.get(URL)
    time.sleep(8)  # Esperar carga completa

    print(f"Titulo: {driver.title}")
    print(f"URL: {driver.current_url}")
    print()

    # 0) Buscar links de mercados en el sidebar izquierdo
    print("=== Links de mercados en sidebar ===")
    all_links = driver.find_elements(By.CSS_SELECTOR, "a")
    for link in all_links:
        href = link.get_attribute("href") or ""
        text = link.text.strip()
        if "football/market/" in href:
            print(f"  '{text}' -> {href}")
    print()

    # 1) Contar tbodies
    tbodies = driver.find_elements(By.CSS_SELECTOR, "table tbody")
    print(f"Total table tbody: {len(tbodies)}")
    print()

    # 2) Listar TODOS los h3 que encuentra
    all_h3 = driver.find_elements(By.TAG_NAME, "h3")
    print(f"Total h3 en pagina: {len(all_h3)}")
    for i, h3 in enumerate(all_h3):
        txt = h3.text.strip()
        if txt:
            print(f"  h3[{i}]: '{txt}'")
    print()

    # 3) Buscar específicamente runners con "Goles"
    print("=== Runners con 'Goles' en el nombre ===")
    goles_count = 0
    for tbody in tbodies:
        rows = tbody.find_elements(By.CSS_SELECTOR, "tr")
        for row in rows:
            h3s = row.find_elements(By.TAG_NAME, "h3")
            if not h3s:
                continue
            name = h3s[0].text.strip()
            if "Goles" in name or "Goals" in name:
                goles_count += 1
                buttons = row.find_elements(By.TAG_NAME, "button")
                btn_texts = [b.text.strip().replace('\n', ' ')[:20] for b in buttons if b.text.strip()]
                print(f"  Runner: '{name}' | Buttons: {btn_texts}")
    print(f"  Total runners con Goles: {goles_count}")
    print()

    # 4) Ejecutar extraer_runners_match_odds exactamente como el scraper
    from main import extraer_runners_match_odds, extraer_over_under

    print("=== extraer_runners_match_odds() ===")
    mo = extraer_runners_match_odds(driver)
    for k, v in mo.items():
        print(f"  {k}: {v}")
    print()

    print("=== extraer_over_under() desde pagina evento ===")
    ou = extraer_over_under(driver)
    for k, v in ou.items():
        if v:
            print(f"  {k}: {v}")
    if not any(ou.values()):
        print("  (TODOS VACIOS)")
    print()

    # 5) Extraer URLs de mercados O/U del sidebar y navegar a cada uno
    print("=== Navegando a mercados O/U individuales ===")
    ou_links = {}
    all_links = driver.find_elements(By.CSS_SELECTOR, "a")
    for link in all_links:
        href = link.get_attribute("href") or ""
        text = link.text.strip()
        if "football/market/" in href and "goles" in text.lower():
            ou_links[text] = href

    for name, url in ou_links.items():
        print(f"\n--- Navegando a: {name} ({url}) ---")
        driver.get(url)
        time.sleep(4)

        # Buscar runners con "Goles"
        h3s = driver.find_elements(By.TAG_NAME, "h3")
        for h3 in h3s:
            txt = h3.text.strip()
            if "Goles" in txt or "Goals" in txt:
                row = h3.find_element(By.XPATH, "./ancestor::tr")
                buttons = row.find_elements(By.TAG_NAME, "button")
                prices = [b.text.strip().replace('\n', ' ')[:20] for b in buttons if b.text.strip()]
                print(f"  Runner: '{txt}' | Prices: {prices}")
    print()

finally:
    driver.quit()
    print("Driver cerrado.")