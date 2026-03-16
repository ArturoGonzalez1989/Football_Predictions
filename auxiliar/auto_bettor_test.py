"""
auto_bettor_test.py — Script de validación de apuestas automáticas via Playwright CDP.

Conecta al Edge ya logueado (puerto 9222), navega al partido, selecciona la cuota
correcta, rellena el stake y confirma la apuesta.

Uso:
    python auxiliar/auto_bettor_test.py                  # usa primera señal activa del backend
    python auxiliar/auto_bettor_test.py --dry-run        # hasta el botón Apostar, sin confirmar
    python auxiliar/auto_bettor_test.py --match "Barracas Central - Atl Tucuman" --rec "BACK DRAW @ 4.1"
    python auxiliar/auto_bettor_test.py --list-signals   # muestra señales activas y sale

Pre-requisitos:
    - Edge abierto con: & msedge.exe --remote-debugging-port=9222 --user-data-dir=...
    - Backend corriendo en localhost:8000
"""

import argparse
import csv
import json
import logging
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

# ── Configuración ─────────────────────────────────────────────────────────────
CDP_URL      = "http://localhost:9222"
BACKEND_URL  = "http://localhost:8000"
STAKE        = 1.0   # € por apuesta (cambiar para producción)
GAMES_CSV    = Path(__file__).parent.parent / "betfair_scraper" / "games.csv"
SCREENSHOT   = Path(__file__).parent / "bet_screenshot.png"


def _sleep(min_s: float, max_s: float) -> None:
    """Pausa aleatoria para simular comportamiento humano."""
    t = random.uniform(min_s, max_s)
    log.debug(f"Esperando {t:.1f}s")
    time.sleep(t)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("auto_bettor")


# ── Helpers: señales del backend ──────────────────────────────────────────────

def fetch_signals() -> list[dict]:
    """Obtiene señales activas del backend."""
    try:
        url = f"{BACKEND_URL}/analytics/signals/betting-opportunities"
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
            return data.get("signals", [])
    except Exception as e:
        log.warning(f"No se pudo conectar al backend: {e}")
        return []


def load_games() -> dict[str, str]:
    """Lee games.csv y devuelve {match_name: url}."""
    games = {}
    if not GAMES_CSV.exists():
        return games
    with open(GAMES_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            games[row["Game"]] = row["url"]
    return games


# ── Helpers: navegación Betfair ───────────────────────────────────────────────

def _navigate_to_submarket(page, rec: str) -> None:
    """Navega al sub-mercado correcto si es CS u Over/Under."""
    rec_up = rec.upper()

    if "OVER" in rec_up or "UNDER" in rec_up:
        m = re.search(r'(\d+\.?\d*)', rec_up)
        if not m:
            return
        goal    = m.group(1)
        goal_es = goal.replace(".", ",")
        for text in [f"de {goal_es} Goles", f"de {goal} Goles", goal_es, goal]:
            try:
                lnk = page.locator(f"a:has-text('{text}')").first
                if lnk.count() > 0 and lnk.is_visible(timeout=2000):
                    lnk.click()
                    _sleep(1.0, 2.5)
                    log.info(f"Mercado Over/Under: {text}")
                    return
            except Exception:
                continue

    elif "CS" in rec_up:
        for text in ["Resultado correcto", "Correct Score"]:
            try:
                lnk = page.locator(f"a:has-text('{text}')").first
                if lnk.count() > 0 and lnk.is_visible(timeout=2000):
                    lnk.click()
                    _sleep(1.0, 2.5)
                    log.info("Mercado: Resultado correcto")
                    return
            except Exception:
                continue


def _click_odds_button(page, rec: str, match_name: str) -> bool:
    """
    Encuentra y hace clic en el botón de cuota correcto.

    Selectores confirmados hoy en Betfair ES:
      - Back buttons: button._5iIjZ.back
      - Lay buttons:  button._5iIjZ.lay

    Estrategia:
      1. Match Odds (HOME/AWAY/DRAW): busca la fila por nombre del equipo en h3,
         luego el primer botón back/lay de esa fila.
      2. Correct Score: busca la fila con el marcador exacto (ej. "1 - 1").
      3. Over/Under: busca la fila con "más" o "menos".
    """
    rec_up   = rec.upper()
    is_lay   = rec_up.startswith("LAY")
    btn_type = "lay" if is_lay else "back"

    # ── 1. Match Odds ──────────────────────────────────────────────────────────
    if any(k in rec_up for k in ("HOME", "AWAY", "DRAW")):
        parts    = match_name.split(" - ", 1)
        home     = parts[0].strip() if parts else ""
        away     = parts[1].strip() if len(parts) > 1 else ""

        if "HOME" in rec_up:
            target_name = home
        elif "AWAY" in rec_up:
            target_name = away
        else:
            target_name = None   # Draw → buscar "Empate"

        # Busca la fila correcta via JS y hace clic en el primer botón back/lay
        result = page.evaluate(f"""
        (() => {{
            const btnType = "{btn_type}";
            const targetName = {json.dumps(target_name)};
            const rows = document.querySelectorAll("tr");
            for (const row of rows) {{
                const h3 = row.querySelector("h3");
                if (!h3) continue;
                const text = h3.innerText.trim().toLowerCase();
                const match = targetName
                    ? text.includes(targetName.toLowerCase())
                    : (text.includes("empate") || text.includes("draw") || text.includes("the draw"));
                if (match) {{
                    const btn = row.querySelector("button._5iIjZ." + btnType);
                    if (btn) {{ btn.click(); return "clicked " + btnType + " for: " + h3.innerText; }}
                    return "row found but no " + btnType + " button";
                }}
            }}
            // Fallback posicional: home=0, away=1, draw=2 (primer btn de cada grupo de 3)
            const allBtns = Array.from(document.querySelectorAll("button._5iIjZ." + btnType));
            if (allBtns.length >= 9) {{
                const idx = "{rec_up}".includes("HOME") ? 0 : "{rec_up}".includes("AWAY") ? 3 : 6;
                allBtns[idx].click();
                return "fallback positional: " + idx;
            }}
            return "not found";
        }})()
        """)
        log.info(f"Match Odds click: {result}")
        return "not found" not in result

    # ── 2. Correct Score ───────────────────────────────────────────────────────
    elif "CS" in rec_up:
        cs_m = re.search(r'CS\s+(\d+)[_\-](\d+)', rec_up)
        if not cs_m:
            log.warning(f"No se pudo parsear CS en: {rec}")
            return False
        score_text = f"{cs_m.group(1)} - {cs_m.group(2)}"
        result = page.evaluate(f"""
        (() => {{
            const btnType = "{btn_type}";
            const target = "{score_text}";
            const rows = document.querySelectorAll("tr");
            for (const row of rows) {{
                const h3 = row.querySelector("h3");
                if (!h3) continue;
                if (h3.innerText.trim() === target) {{
                    const btn = row.querySelector("button._5iIjZ." + btnType);
                    if (btn) {{ btn.click(); return "clicked CS " + target; }}
                    return "row found but no button for CS " + target;
                }}
            }}
            return "CS row not found: " + target;
        }})()
        """)
        log.info(f"Correct Score click: {result}")
        return "clicked" in result

    # ── 3. Over/Under ──────────────────────────────────────────────────────────
    elif "OVER" in rec_up or "UNDER" in rec_up:
        target_text = "más" if "OVER" in rec_up else "menos"
        result = page.evaluate(f"""
        (() => {{
            const btnType = "{btn_type}";
            const target = "{target_text}";
            const rows = document.querySelectorAll("tr");
            for (const row of rows) {{
                const h3 = row.querySelector("h3");
                if (!h3) continue;
                if (h3.innerText.toLowerCase().includes(target)) {{
                    const btn = row.querySelector("button._5iIjZ." + btnType);
                    if (btn) {{ btn.click(); return "clicked " + btnType + " for: " + h3.innerText; }}
                    return "row found but no " + btnType + " button";
                }}
            }}
            return "Over/Under row not found: " + target;
        }})()
        """)
        log.info(f"Over/Under click: {result}")
        return "clicked" in result

    log.warning(f"Tipo de mercado no reconocido en: {rec}")
    return False


def _fill_stake(page, stake: float) -> bool:
    """Rellena el campo de importe. Selector confirmado: input.betslip-size-input"""
    _sleep(0.8, 1.8)
    inp = page.locator("input.betslip-size-input").last  # last = la selección recién añadida
    if inp.count() == 0:
        inp = page.locator("betslip-size-input").get_by_role("textbox").last
    if inp.count() == 0:
        log.warning("No se encontró el campo de stake")
        return False
    inp.click()
    inp.press("Control+a")
    inp.type(str(int(stake) if stake == int(stake) else stake))
    log.info(f"Stake rellenado: {stake}")
    return True


def _click_apostar(page) -> bool:
    """
    Hace clic en el botón 'Apostar' via JS para evitar problemas con el panel
    de vídeo en directo que lo puede tapar visualmente.
    """
    result = page.evaluate("""
    (() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const btn = btns.find(b => b.innerText.trim() === 'Apostar' && !b.disabled);
        if (btn) { btn.click(); return true; }
        return false;
    })()
    """)
    if result:
        log.info("✓ Apostar confirmado")
    else:
        log.warning("Botón Apostar no encontrado o deshabilitado")
    return bool(result)


# ── Función principal ─────────────────────────────────────────────────────────

def place_bet(signal: dict, dry_run: bool = False) -> bool:
    """
    Conecta a Edge via CDP, navega al partido y coloca la apuesta.

    Args:
        signal:  dict con keys: match_name, match_url, recommendation
        dry_run: si True, para antes de confirmar (screenshot del betslip)
    """
    match_url    = signal.get("match_url", "")
    rec          = signal.get("recommendation", "")
    match_name   = signal.get("match_name", "")
    strategy     = signal.get("strategy", "")

    if not match_url:
        log.error("Señal sin match_url")
        return False

    log.info(f"{'[DRY RUN] ' if dry_run else ''}Apuesta: {match_name} | {strategy} | {rec}")
    log.info(f"URL: {match_url}")

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
        except Exception as e:
            log.error(f"No se pudo conectar a Edge en {CDP_URL}: {e}")
            log.error("Asegúrate de que Edge está abierto con --remote-debugging-port=9222")
            return False

        page = browser.contexts[0].pages[0]

        # Navegar al partido — delay inicial: simula que el usuario tardó en ver la señal
        _sleep(2.0, 8.0)
        log.info("Navegando al mercado...")
        page.goto(match_url)
        _sleep(2.5, 5.0)

        # Navegar al sub-mercado si es necesario (CS, Over/Under)
        _navigate_to_submarket(page, rec)

        # Pequeña pausa antes de hacer clic — simula leer la cuota
        _sleep(0.8, 3.0)

        # Hacer clic en la cuota
        if not _click_odds_button(page, rec, match_name):
            log.error("No se pudo seleccionar la cuota")
            page.screenshot(path=str(SCREENSHOT))
            return False

        _sleep(1.0, 2.5)

        # Rellenar stake
        if not _fill_stake(page, STAKE):
            log.error("No se pudo rellenar el stake")
            page.screenshot(path=str(SCREENSHOT))
            return False

        # Pausa antes de confirmar — simula revisar el betslip
        _sleep(1.5, 4.0)

        # Screenshot del betslip listo
        page.screenshot(path=str(SCREENSHOT))
        log.info(f"Screenshot guardado: {SCREENSHOT}")

        if dry_run:
            log.info("DRY RUN completado — betslip listo pero NO confirmado")
            return True

        # Confirmar apuesta
        success = _click_apostar(page)
        _sleep(1.5, 3.0)
        page.screenshot(path=str(SCREENSHOT.parent / "bet_confirmed.png"))
        return success


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    global STAKE
    parser = argparse.ArgumentParser(description="Auto-bettor de validación via Playwright CDP")
    parser.add_argument("--dry-run",      action="store_true", help="No confirmar la apuesta (default: False)")
    parser.add_argument("--list-signals", action="store_true", help="Mostrar señales activas y salir")
    parser.add_argument("--match",        default="",          help="Nombre del partido (override)")
    parser.add_argument("--rec",          default="",          help="Recomendación, ej: 'BACK DRAW @ 3.5'")
    parser.add_argument("--stake",        type=float,          default=STAKE, help=f"Stake en € (default: {STAKE})")
    args = parser.parse_args()

    STAKE = args.stake

    # ── Listar señales activas ─────────────────────────────────────────────────
    if args.list_signals:
        signals = fetch_signals()
        if not signals:
            print("No hay señales activas (o backend no disponible)")
            return
        print(f"\n{'#':<4} {'Partido':<40} {'Estrategia':<25} {'Recomendación':<30} {'Cuota':<8}")
        print("-" * 110)
        for i, s in enumerate(signals):
            print(f"{i:<4} {s.get('match_name',''):<40} {s.get('strategy',''):<25} "
                  f"{s.get('recommendation',''):<30} {s.get('back_odds',''):<8}")
        return

    # ── Señal manual via CLI ───────────────────────────────────────────────────
    if args.match and args.rec:
        games   = load_games()
        url     = games.get(args.match, "")
        if not url:
            # Intenta match parcial
            for name, u in games.items():
                if args.match.lower() in name.lower():
                    url = u
                    break
        if not url:
            log.error(f"Partido no encontrado en games.csv: {args.match}")
            sys.exit(1)

        signal = {"match_name": args.match, "match_url": url, "recommendation": args.rec,
                  "strategy": "manual"}
        success = place_bet(signal, dry_run=args.dry_run)
        sys.exit(0 if success else 1)

    # ── Primera señal activa del backend ──────────────────────────────────────
    log.info("Consultando señales activas al backend...")
    signals = fetch_signals()

    if not signals:
        log.warning("No hay señales activas. Usa --match y --rec para prueba manual.")
        log.info("Ejemplo: python auxiliar/auto_bettor_test.py --dry-run "
                 '--match "Barracas Central - Atl Tucuman" --rec "BACK DRAW @ 4.1"')
        sys.exit(0)

    # Usar la primera señal
    sig = signals[0]
    log.info(f"Señal seleccionada: {sig.get('match_name')} | {sig.get('recommendation')}")

    # Añadir URL si falta (el backend puede no incluirla)
    if not sig.get("match_url"):
        games = load_games()
        for name, url in games.items():
            if sig.get("match_name", "").lower() in name.lower():
                sig["match_url"] = url
                break

    success = place_bet(sig, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
