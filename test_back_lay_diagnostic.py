"""
Precise diagnostic: call _extraer_best_back_lay on each Match Odds row
and compare with CSS class values AT THE SAME INSTANT.
"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "betfair_scraper"))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

URL = "https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/eredivisie-holandesa/sparta-rotterdam-nec-nijmegen-apuestas-35216684"

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

    from main import _extraer_best_back_lay

    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    for row in rows:
        try:
            h3 = row.find_element(By.TAG_NAME, "h3")
            name = h3.text.strip()
        except:
            continue
        if not name:
            continue
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) != 7:
            continue
        name_lower = name.lower()
        if any(kw in name_lower for kw in ("goles", "goals", "más", "menos")):
            continue
        if re.match(r"^\d+\s*-\s*\d+$", name):
            continue

        # 1) Call _extraer_best_back_lay (what the scraper uses)
        back, lay = _extraer_best_back_lay(row)

        # 2) Read CSS class values directly (ground truth)
        lb = row.find_elements(By.CSS_SELECTOR, "td.last-back-cell button")
        fl = row.find_elements(By.CSS_SELECTOR, "td.first-lay-cell button")
        css_back_text = lb[0].text.strip().replace("\n", " ") if lb else "(not found)"
        css_lay_text = fl[0].text.strip().replace("\n", " ") if fl else "(not found)"

        # 3) Read ALL button texts (to see full depth)
        all_texts = []
        for i, cell in enumerate(cells):
            cls = cell.get_attribute("class") or ""
            btn = cell.find_elements(By.TAG_NAME, "button")
            txt = btn[0].text.strip().replace("\n", " ") if btn and btn[0].text.strip() else ""
            marker = ""
            if "last-back-cell" in cls: marker = "[BB]"
            elif "first-lay-cell" in cls: marker = "[BL]"
            elif "back-cell" in cls: marker = "[b]"
            elif "lay-cell" in cls: marker = "[l]"
            if txt or marker:
                all_texts.append(f"{txt}{marker}")

        match = "OK" if (back == css_back_text.split()[0] if css_back_text != "(not found)" and css_back_text.strip() else back == "") else "MISMATCH"

        print(f"=== {name} ===")
        print(f"  Helper returned: back='{back}', lay='{lay}'")
        print(f"  CSS last-back:   '{css_back_text}'")
        print(f"  CSS first-lay:   '{css_lay_text}'")
        print(f"  All cells:       {' | '.join(all_texts)}")

        # Parse CSS values for comparison
        css_back = ""
        if css_back_text and css_back_text != "(not found)":
            m = re.match(r"^(\d+\.?\d*)", css_back_text.replace(",", "."))
            if m:
                css_back = m.group(1)
        css_lay = ""
        if css_lay_text and css_lay_text != "(not found)":
            m = re.match(r"^(\d+\.?\d*)", css_lay_text.replace(",", "."))
            if m:
                css_lay = m.group(1)

        back_ok = back == css_back
        lay_ok = lay == css_lay
        print(f"  Back: helper={back} vs css={css_back} -> {'OK' if back_ok else 'MISMATCH!'}")
        print(f"  Lay:  helper={lay} vs css={css_lay} -> {'OK' if lay_ok else 'MISMATCH!'}")
        print()

finally:
    driver.quit()
