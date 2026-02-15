#!/usr/bin/env python3
"""Debug script to see what's on the En Juego page."""

from playwright.sync_api import sync_playwright
import time

def debug_live_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Go to Betfair
        print("Navegando a Betfair...")
        page.goto("https://www.betfair.es/exchange/plus/es", timeout=30000)
        time.sleep(3)

        # Accept cookies
        try:
            page.click("#onetrust-accept-btn-handler", timeout=5000)
            print("Cookies aceptadas")
        except:
            pass

        # Go to En Juego
        print("\nAccediendo a 'En Juego'...")
        page.goto("https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/en-juego-apuestas-10068362", timeout=30000)
        time.sleep(5)

        # Get all links with 'apuestas-'
        links = page.query_selector_all("a[href*='apuestas-']")
        print(f"\n=== Encontrados {len(links)} links con 'apuestas-' ===\n")

        for i, link in enumerate(links, 1):
            href = link.get_attribute("href") or ""
            text = link.text_content() or ""
            print(f"{i}. Text: {text[:60]}")
            print(f"   Href: {href}")
            print()

        browser.close()

if __name__ == "__main__":
    debug_live_page()
