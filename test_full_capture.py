"""
Captura completa de TODOS los datos del scraper para Galatasaray-Juventus.
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "betfair_scraper"))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

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
    driver.get(URL)
    time.sleep(8)

    from main import (extraer_runners_match_odds, extraer_over_under,
                      extraer_over_under_via_mercado, extraer_resultado_correcto,
                      extraer_info_partido, extraer_volumen)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    info = extraer_info_partido(driver)
    odds_mo = extraer_runners_match_odds(driver)
    odds_ou_event = extraer_over_under(driver)
    odds_ou_market = extraer_over_under_via_mercado(driver)
    odds_rc = extraer_resultado_correcto(driver)

    # Merge O/U
    odds_ou_merged = dict(odds_ou_event)
    for k, v in odds_ou_market.items():
        if v:
            odds_ou_merged[k] = v

    print(f"TIMESTAMP: {timestamp}")
    print()
    print("=== INFO PARTIDO ===")
    for k, v in info.items():
        print(f"  {k}: {v}")
    print()
    print("=== MATCH ODDS ===")
    for k, v in odds_mo.items():
        print(f"  {k}: {v}")
    print()
    print("=== OVER/UNDER (evento) ===")
    for k, v in odds_ou_event.items():
        if v:
            print(f"  {k}: {v}")
    c1 = sum(1 for v in odds_ou_event.values() if v)
    print(f"  Total: {c1}")
    print()
    print("=== OVER/UNDER (mercado individual) ===")
    for k, v in odds_ou_market.items():
        if v:
            print(f"  {k}: {v}")
    c2 = sum(1 for v in odds_ou_market.values() if v)
    print(f"  Total: {c2}")
    print()
    print("=== OVER/UNDER (merged) ===")
    for k, v in odds_ou_merged.items():
        if v:
            print(f"  {k}: {v}")
    print()
    print("=== RESULTADO CORRECTO ===")
    for k, v in odds_rc.items():
        if v:
            print(f"  {k}: {v}")
    c3 = sum(1 for v in odds_rc.values() if v)
    print(f"  Total: {c3}")

finally:
    driver.quit()
