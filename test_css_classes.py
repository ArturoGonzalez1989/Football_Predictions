"""
Diagnostic: Check if CSS classes (last-back-cell, first-lay-cell) exist in headless Selenium.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "betfair_scraper"))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
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

    # Check global presence of CSS classes
    all_last_back = driver.find_elements(By.CSS_SELECTOR, "td.last-back-cell")
    all_first_lay = driver.find_elements(By.CSS_SELECTOR, "td.first-lay-cell")
    print(f"Global td.last-back-cell count: {len(all_last_back)}")
    print(f"Global td.first-lay-cell count: {len(all_first_lay)}")
    print()

    # Find all runner rows and check their cell classes
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    for row in rows:
        try:
            h3 = row.find_element(By.TAG_NAME, "h3")
            name = h3.text.strip()
            if name not in ("Galatasaray", "Juventus", "Empate"):
                continue
        except:
            continue

        cells = row.find_elements(By.TAG_NAME, "td")
        print(f"=== {name} ({len(cells)} cells) ===")
        for i, cell in enumerate(cells):
            classes = cell.get_attribute("class") or ""
            btn = cell.find_elements(By.TAG_NAME, "button")
            btn_text = btn[0].text.strip().replace("\n", " ") if btn else "(no button)"
            is_last_back = "last-back-cell" in classes
            is_first_lay = "first-lay-cell" in classes
            marker = ""
            if is_last_back:
                marker = " *** LAST-BACK ***"
            elif is_first_lay:
                marker = " *** FIRST-LAY ***"
            print(f"  cell[{i}] class='{classes}' btn='{btn_text or '(empty)'}'{marker}")

        # Try the CSS selectors directly
        lb = row.find_elements(By.CSS_SELECTOR, "td.last-back-cell button")
        fl = row.find_elements(By.CSS_SELECTOR, "td.first-lay-cell button")
        lb_text = lb[0].text.strip() if lb else "(not found)"
        fl_text = fl[0].text.strip() if fl else "(not found)"
        print(f"  -> last-back-cell button: '{lb_text}'")
        print(f"  -> first-lay-cell button: '{fl_text}'")
        print()

finally:
    driver.quit()
