#!/usr/bin/env python3
"""Buscar partidos en vivo en Betfair."""

from playwright.sync_api import sync_playwright
import time

def search_live_matches():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Ir a Betfair
        print("Navegando a Betfair...")
        page.goto("https://www.betfair.es/exchange/plus/es", timeout=30000)
        time.sleep(3)

        # Aceptar cookies
        try:
            page.click("#onetrust-accept-btn-handler", timeout=5000)
            print("Cookies aceptadas")
        except:
            print("No cookies banner")

        time.sleep(2)

        # Buscar partidos en vivo
        print("\nBuscando partidos EN VIVO...")
        page.goto("https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/en-juego-apuestas-10068362", timeout=30000)
        time.sleep(5)

        # Extraer partidos
        links = page.query_selector_all("a[href*='apuestas-']")
        print(f"\nEncontrados {len(links)} links con 'apuestas-'")

        partidos = []
        for link in links[:20]:
            try:
                text = link.inner_text().strip()
                href = link.get_attribute("href")
                if text and "v " in text.lower() and href and "/exchange/plus/" in href:
                    partidos.append((text, href))
            except:
                pass

        print(f"\n=== PARTIDOS EN VIVO ({len(partidos)}) ===")
        for i, (nombre, url) in enumerate(partidos[:10], 1):
            print(f"{i}. {nombre}")
            print(f"   URL: {url}")

        print("\nPresiona Enter para cerrar...")
        input()
        browser.close()

if __name__ == "__main__":
    search_live_matches()
