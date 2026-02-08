"""
config.py - Configuración central del scraper de Betfair.es
============================================================
Ajusta estos valores según tus necesidades antes de ejecutar main.py.
"""

# ── URLs de partidos a monitorizar ──────────────────────────────────────────
# Reemplaza con URLs reales de Betfair Exchange.
# Formato típico: https://www.betfair.es/exchange/plus/es/futbol/...
# Puedes añadir hasta 10. El script abrirá una pestaña por cada URL.
MATCH_URLS = [
    "https://www.betfair.es/exchange/plus/es/futbol/partido-placeholder-1",
    "https://www.betfair.es/exchange/plus/es/futbol/partido-placeholder-2",
    "https://www.betfair.es/exchange/plus/es/futbol/partido-placeholder-3",
    # Añade más URLs aquí...
]

# ── Tiempos y frecuencias ───────────────────────────────────────────────────
CICLO_TOTAL_SEG = 60          # Segundos entre ciclos completos de captura
DELAY_MIN_SEG = 8             # Delay mínimo aleatorio entre pestañas (anti-bot)
DELAY_MAX_SEG = 12            # Delay máximo aleatorio entre pestañas
TIMEOUT_ELEMENTO_SEG = 10     # Timeout al buscar elementos en cada pestaña
PAUSA_LOGIN_SEG = 60          # Segundos de espera para login manual al inicio

# ── Directorio de salida ────────────────────────────────────────────────────
OUTPUT_DIR = "data"           # Carpeta donde se guardan los CSV

# ── Chrome / Selenium ───────────────────────────────────────────────────────
HEADLESS = False              # False = ventana visible (recomendado para login)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
# Idioma del navegador
CHROME_LANG = "es-ES,es;q=0.9"

# ── Selectores CSS (Betfair Exchange) ───────────────────────────────────────
# NOTA: Los selectores de Betfair cambian con frecuencia. Si fallan,
# abre F12 → Inspector → busca los elementos manualmente.
# Ver sección "Troubleshooting selectores" en README.md.

SELECTORES = {
    # Contenedor de cada runner (selección) en el mercado
    "runner_row": "tr.runner-line",

    # Nombre del runner dentro de su fila
    "runner_name": ".runner-name",

    # Mejor precio back (primera celda back)
    "back_price": "td.bet-buttons.back-cell button.bet-button-price",

    # Mejor precio lay (primera celda lay)
    "lay_price": "td.bet-buttons.lay-cell button.bet-button-price",

    # Volumen matched del mercado
    "matched_amount": ".matched-amount .size-value, .total-matched .matched-value",

    # Tiempo del partido (reloj in-play)
    "match_time": ".elapsed-time, .event-header .time, .inplay-indicator .time",

    # Marcador del partido
    "match_score": ".score, .event-header .score-home, .event-header .score-away",

    # Nombre del evento/partido
    "event_name": ".event-header .title, .event-name, h1.event-name",

    # Navegación de mercados (para buscar Over/Under)
    "market_tab": ".market-tabs .tab, .market-selector .tab-item",
}

# Selectores alternativos (React/Angular de Betfair Exchange Plus)
SELECTORES_ALT = {
    "runner_row": "[data-testid='runner-row'], .runner-line, .mv-runner",
    "runner_name": "[data-testid='runner-name'], .runner-name, .mv-runner-name",
    "back_price": (
        "[data-testid='back-button-price'], "
        ".mv-bet-button-back .bet-button-price, "
        ".back-selection-button .bet-button-price"
    ),
    "lay_price": (
        "[data-testid='lay-button-price'], "
        ".mv-bet-button-lay .bet-button-price, "
        ".lay-selection-button .bet-button-price"
    ),
    "matched_amount": (
        "[data-testid='matched-amount'], "
        ".mv-matched-amount, "
        ".matched-amount"
    ),
}
