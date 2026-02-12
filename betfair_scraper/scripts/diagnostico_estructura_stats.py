#!/usr/bin/env python3
"""
Script de diagnóstico para investigar la estructura REAL actual de las estadísticas en Betfair.
Navega a un partido de Premier League y reporta:
- Cuántos iframes hay (y si son anidados)
- Qué elementos contienen las estadísticas (p, div, span, etc.)
- Qué selectores CSS funcionan actualmente
- Estructura completa del DOM de estadísticas
"""

import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# URL de partido de Premier League a investigar
PARTIDO_URL = "https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/premier-league-inglesa/manchester-city-fulham-apuestas-35212169"

def setup_driver():
    """Configura Chrome con opciones para diagnóstico"""
    options = webdriver.ChromeOptions()
    # NO headless para poder ver qué pasa
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    return driver

def investigar_estructura(driver):
    """Investiga y reporta la estructura completa de las estadísticas"""

    print("\n" + "="*80)
    print("DIAGNÓSTICO DE ESTRUCTURA DE ESTADÍSTICAS EN BETFAIR")
    print("="*80)

    # Navegar al partido
    print(f"\n[1] Navegando a partido...")
    print(f"    URL: {PARTIDO_URL}")
    driver.get(PARTIDO_URL)

    # Esperar carga completa
    print(f"\n[2] Esperando carga de página...")
    time.sleep(8)  # Espera generosa para carga dinámica

    # PASO 1: Buscar botón de estadísticas
    print(f"\n[3] Buscando botón de estadísticas...")
    try:
        # Buscar posibles botones/enlaces que contengan "Estadísticas", "Stats", etc.
        posibles_botones = driver.find_elements(By.XPATH,
            "//*[contains(text(), 'Estadísticas') or contains(text(), 'Stats') or contains(text(), 'estadísticas')]")

        print(f"    ✓ Encontrados {len(posibles_botones)} elementos con texto 'Estadísticas'")
        for idx, boton in enumerate(posibles_botones[:5]):
            print(f"      [{idx+1}] Tag: {boton.tag_name} | Texto: '{boton.text[:50]}' | Visible: {boton.is_displayed()}")
    except Exception as e:
        print(f"    × Error buscando botones: {e}")

    # PASO 2: Investigar iframes
    print(f"\n[4] Investigando iframes...")
    try:
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"    ✓ Total de iframes encontrados: {len(iframes)}")

        for idx, iframe in enumerate(iframes[:10]):  # Limitar a primeros 10
            try:
                src = iframe.get_attribute("src") or "(sin src)"
                name = iframe.get_attribute("name") or "(sin name)"
                id_attr = iframe.get_attribute("id") or "(sin id)"
                print(f"\n    [IFRAME #{idx+1}]")
                print(f"      - ID: {id_attr}")
                print(f"      - Name: {name}")
                print(f"      - Src: {src[:100]}")

                # Intentar acceder al iframe
                try:
                    driver.switch_to.frame(iframe)

                    # Buscar iframes anidados
                    nested_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    print(f"      - Iframes anidados: {len(nested_iframes)}")

                    if nested_iframes:
                        for n_idx, n_iframe in enumerate(nested_iframes[:3]):
                            n_src = n_iframe.get_attribute("src") or "(sin src)"
                            print(f"        [NESTED #{n_idx+1}] Src: {n_src[:80]}")

                            # Acceder al nested iframe
                            try:
                                driver.switch_to.frame(n_iframe)

                                # Buscar elementos con estadísticas
                                body_text = driver.find_element(By.TAG_NAME, "body").text
                                tiene_stats = any(keyword in body_text.lower() for keyword in
                                    ["xg", "momentum", "opta", "possession", "shots", "corners", "expected"])

                                if tiene_stats:
                                    print(f"          ✓ CONTIENE ESTADÍSTICAS!")
                                    print(f"          Texto (primeros 200 chars): {body_text[:200]}")

                                    # Analizar estructura de elementos
                                    print(f"\n          [ESTRUCTURA]")
                                    paragraphs = driver.find_elements(By.TAG_NAME, "p")
                                    divs = driver.find_elements(By.TAG_NAME, "div")
                                    spans = driver.find_elements(By.TAG_NAME, "span")

                                    print(f"          - <p> tags: {len(paragraphs)}")
                                    print(f"          - <div> tags: {len(divs)}")
                                    print(f"          - <span> tags: {len(spans)}")

                                    # Mostrar primeros párrafos
                                    if paragraphs:
                                        print(f"\n          [PRIMEROS 10 PÁRRAFOS <p>]")
                                        for p_idx, p in enumerate(paragraphs[:10]):
                                            texto = p.text.strip()
                                            if texto:
                                                print(f"          [{p_idx+1}] {texto}")

                                    # Buscar clases CSS útiles
                                    print(f"\n          [BUSCANDO SELECTORES CSS ÚTILES]")
                                    elementos_con_clase = driver.find_elements(By.XPATH, "//*[@class]")
                                    clases_unicas = set()
                                    for elem in elementos_con_clase[:50]:
                                        clase = elem.get_attribute("class")
                                        if clase and any(k in clase.lower() for k in ["stat", "value", "momentum", "opta"]):
                                            clases_unicas.add(clase)

                                    if clases_unicas:
                                        print(f"          Clases CSS relacionadas con stats:")
                                        for clase in list(clases_unicas)[:10]:
                                            print(f"            - {clase}")

                                driver.switch_to.parent_frame()
                            except Exception as nested_e:
                                print(f"          × Error accediendo nested iframe: {nested_e}")
                                driver.switch_to.parent_frame()

                    driver.switch_to.default_content()

                except Exception as iframe_e:
                    print(f"      × Error accediendo iframe: {iframe_e}")
                    driver.switch_to.default_content()

            except Exception as e:
                print(f"    × Error procesando iframe #{idx+1}: {e}")

    except Exception as e:
        print(f"    × Error investigando iframes: {e}")

    # PASO 3: Buscar elementos directamente en la página principal
    print(f"\n[5] Buscando estadísticas en página principal (fuera de iframes)...")
    try:
        driver.switch_to.default_content()

        # Buscar todos los textos que contengan keywords de stats
        all_text_elements = driver.find_elements(By.XPATH,
            "//*[contains(text(), 'xG') or contains(text(), 'Momentum') or contains(text(), 'Expected') or contains(text(), 'Opta')]")

        print(f"    ✓ Encontrados {len(all_text_elements)} elementos con keywords de stats")
        for idx, elem in enumerate(all_text_elements[:10]):
            print(f"      [{idx+1}] Tag: {elem.tag_name} | Texto: '{elem.text[:60]}'")

    except Exception as e:
        print(f"    × Error: {e}")

    print(f"\n" + "="*80)
    print("DIAGNÓSTICO COMPLETADO")
    print("="*80 + "\n")

def main():
    driver = None
    try:
        print("\nIniciando diagnóstico de estructura de estadísticas...")
        driver = setup_driver()
        investigar_estructura(driver)

        print("\n[INFO] Navegador quedará abierto para inspección manual.")
        print("[INFO] Presiona Ctrl+C para cerrar cuando termines de inspeccionar.")

        # Mantener navegador abierto
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nCerrando navegador...")

    except Exception as e:
        print(f"\n[ERROR] Error en diagnóstico: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
