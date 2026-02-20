"""
Test: extraer_over_under_via_mercado() - Navega a mercados O/U individuales.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "betfair_scraper"))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

# Usar Galatasaray-Juventus (terminado, pero sidebar debería tener mercados)
URL = "https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/uefa-champions-league/galatasaray-juventus-apuestas-35207338"

opciones = Options()
opciones.add_argument("--headless=new")
opciones.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
opciones.add_argument("--lang=es-ES,es;q=0.9")
opciones.add_argument("--disable-blink-features=AutomationControlled")
opciones.add_argument("--no-sandbox")
opciones.add_argument("--disable-dev-shm-usage")
opciones.add_argument("--window-size=1920,1080")
opciones.add_argument("--disable-gpu")
opciones.add_argument("--disable-extensions")

driver = webdriver.Chrome(options=opciones)

try:
    print(f"Navegando a {URL}...")
    driver.get(URL)
    time.sleep(8)

    print(f"Titulo: {driver.title}")
    print(f"URL actual: {driver.current_url}")
    print()

    from main import extraer_over_under, extraer_over_under_via_mercado

    # 1) Método original
    print("=== extraer_over_under() (método original desde página evento) ===")
    ou_old = extraer_over_under(driver)
    count_old = sum(1 for v in ou_old.values() if v)
    for k, v in ou_old.items():
        if v:
            print(f"  {k}: {v}")
    print(f"  Total: {count_old} valores")
    print()

    # 2) Método nuevo (navegación a mercado individual)
    print("=== extraer_over_under_via_mercado() (navegación a mercado individual) ===")
    ou_new = extraer_over_under_via_mercado(driver)
    count_new = sum(1 for v in ou_new.values() if v)
    for k, v in ou_new.items():
        if v:
            print(f"  {k}: {v}")
    print(f"  Total: {count_new} valores")
    print()

    # 3) Verificar que volvimos a la URL original
    print(f"URL después de extraer: {driver.current_url}")
    if "35207338" in driver.current_url:
        print("✓ Volvimos correctamente a la página del evento")
    else:
        print("✗ NO volvimos a la URL original!")
    print()

    # 4) Comparación
    print("=== Comparación ===")
    for k in ou_old:
        old_v = ou_old[k]
        new_v = ou_new[k]
        if old_v or new_v:
            marker = "NEW" if new_v and not old_v else ("SAME" if old_v == new_v else "DIFF")
            print(f"  {k}: old={old_v or '(vacío)'} | new={new_v or '(vacío)'} [{marker}]")

finally:
    driver.quit()
    print("\nDriver cerrado.")
