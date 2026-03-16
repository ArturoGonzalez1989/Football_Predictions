"""
Test standalone del bot Betfair — corre FUERA del backend.

Usa un perfil Edge dedicado en betfair_scraper/data/betfair_session/
→ No hay conflicto con Edge/Chrome ya abiertos.
→ Primera vez: se abre la ventana, haces login manual. Betfair guarda sesión por semanas.
→ Siguientes veces: ya logueado, va directo a clickar cuotas + stake.

Uso:
    python auxiliar/test_betfair_bot.py [URL] [RECOMMENDATION] [MATCH_NAME]

Ejemplos:
    python auxiliar/test_betfair_bot.py
    python auxiliar/test_betfair_bot.py "https://www.betfair.es/exchange/plus/es/fútbol/eredivisie-holandesa/feyenoord-excelsior-apuestas-35323384" "BACK HOME" "Feyenoord - Excelsior"
    python auxiliar/test_betfair_bot.py "https://..." "BACK OVER 2.5" "Team A - Team B"
    python auxiliar/test_betfair_bot.py "https://..." "LAY DRAW" "Team A - Team B"
"""

import asyncio
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger("betfair_bot_test")

# Perfil dedicado al bot — no conflicto con Edge/Chrome del usuario
BOT_PROFILE_DIR = Path(__file__).resolve().parent.parent / "betfair_scraper" / "data" / "betfair_session"
DEFAULT_STAKE   = 2.0

DEFAULT_URL        = "https://www.betfair.es/exchange/plus/es/f%C3%BAtbol/ligue-1-francesa/metz-toulouse-apuestas-35324600"
DEFAULT_REC        = "BACK HOME"
DEFAULT_MATCH_NAME = "Metz - Toulouse"


async def _fill_stake(page) -> None:
    await asyncio.sleep(1.0)
    stake_str = str(int(DEFAULT_STAKE) if DEFAULT_STAKE == int(DEFAULT_STAKE) else DEFAULT_STAKE)

    try:
        inp = page.locator("betslip-size-input").get_by_role("textbox").first
        await asyncio.wait_for(inp.wait_for(state="visible"), timeout=4)
        await inp.click()
        await inp.fill(stake_str)
        log.info(f"✓ Stake {stake_str} rellenado via betslip-size-input")
        return
    except Exception as e:
        log.warning(f"betslip-size-input falló: {e}")

    for sel in [
        "betslip-size-input input", "betslip-size-input [role='textbox']",
        ".betslip-bets input", ".betslip input[type='text']",
        "input[class*='stake' i]",
    ]:
        try:
            inp = page.locator(sel).first
            if await asyncio.wait_for(inp.is_visible(), timeout=1):
                await inp.click()
                await inp.fill(stake_str)
                log.info(f"✓ Stake {stake_str} rellenado via {sel}")
                return
        except Exception:
            continue

    log.warning("✗ No se pudo rellenar stake — volcando inputs visibles:")
    try:
        debug = await page.evaluate("""
            () => Array.from(document.querySelectorAll('input, betslip-size-input'))
                       .filter(i => i.getBoundingClientRect().width > 0)
                       .map(i => i.tagName + '|' + i.className + '|' + (i.placeholder||''))
                       .join(' /// ')
        """)
        log.info(f"Inputs visibles: {debug}")
    except Exception:
        pass


async def _navigate_to_market(page, recommendation: str) -> None:
    import re
    rec = recommendation.upper()
    if "OVER" in rec or "UNDER" in rec:
        m = re.search(r'(\d+\.?\d*)', rec)
        if not m:
            return
        goal_total    = m.group(1)
        goal_total_es = goal_total.replace(".", ",")
        candidates = [
            goal_total_es, goal_total,
            f"de {goal_total_es} Goles", f"de {goal_total} Goles",
            f"Más de {goal_total_es} Goles", f"Menos de {goal_total_es} Goles",
        ]
        for variant in candidates:
            try:
                lnk = page.locator(f"a:has-text('{variant}')").first
                if await asyncio.wait_for(lnk.is_visible(), timeout=2):
                    await lnk.click()
                    await asyncio.sleep(1.5)
                    log.info(f"✓ Navegado a mercado: '{variant}'")
                    return
            except Exception:
                continue
        log.info(f"Mercado Over/Under para {goal_total} no encontrado en sidebar")
    elif "CS" in rec:
        for link_text in ["Resultado correcto", "Correct Score"]:
            try:
                lnk = page.locator(f"a:has-text('{link_text}')").first
                if await asyncio.wait_for(lnk.is_visible(), timeout=2):
                    await lnk.click()
                    await asyncio.sleep(1.5)
                    return
            except Exception:
                continue


async def _click_odds(page, recommendation: str, match_name: str) -> None:
    if not recommendation:
        return
    rec      = recommendation.upper()
    is_lay   = rec.startswith("LAY")
    is_match = any(k in rec for k in ("HOME", "AWAY", "DRAW"))
    is_over  = "OVER" in rec
    is_under = "UNDER" in rec

    await _navigate_to_market(page, recommendation)

    log.info(f"URL actual: {page.url}")
    try:
        await asyncio.wait_for(page.wait_for_selector("tr.runner-line", state="visible"), timeout=20)
    except Exception:
        log.warning("✗ Runner rows no visibles después de 20s — mercado cerrado o suspendido")
        # Debug: mostrar qué hay en el DOM
        try:
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 300)")
            log.info(f"Body text: {body_text}")
        except Exception:
            pass
        return

    runner_rows = page.locator("tr.runner-line")
    try:
        count = await asyncio.wait_for(runner_rows.count(), timeout=5)
    except Exception:
        log.warning("✗ No se pudieron contar las runner rows")
        return

    log.info(f"Encontradas {count} runner rows para: {recommendation}")

    # Debug: volcar HTML de la primera runner row para identificar selectores reales
    try:
        first_html = await page.evaluate("() => document.querySelector('tr.runner-line')?.innerHTML || 'NOT FOUND'")
        # Truncar a 800 chars para no saturar el log
        log.info(f"Runner row HTML (truncado): {first_html[:800]}")
    except Exception as e:
        log.warning(f"No se pudo obtener HTML del runner row: {e}")

    if is_match:
        parts      = match_name.split(" - ", 1)
        home_name  = parts[0].strip() if parts else ""
        away_name  = parts[1].strip() if len(parts) > 1 else ""
        target_row = None

        for i in range(count):
            row = runner_rows.nth(i)
            try:
                name_text = (await asyncio.wait_for(row.locator(".runner-name").text_content(), timeout=2) or "").lower()
            except Exception:
                continue
            if "HOME" in rec and home_name and home_name.lower() in name_text:
                target_row = row; break
            if "AWAY" in rec and away_name and away_name.lower() in name_text:
                target_row = row; break
            if "DRAW" in rec and ("empate" in name_text or "draw" in name_text or "the draw" in name_text):
                target_row = row; break

        if target_row is None and count >= 3:
            idx = 0 if "HOME" in rec else (1 if "AWAY" in rec else 2)
            target_row = runner_rows.nth(idx)
            log.info(f"Fallback posicional → fila {idx}")

        if target_row is None:
            log.warning(f"✗ No se encontró fila para: {recommendation}")
            return

        btn_sel = "td.bet-buttons.lay-cell ours-price-button button" if is_lay else "td.bet-buttons.back-cell ours-price-button button"
        try:
            btn = target_row.locator(btn_sel).first
            await asyncio.wait_for(btn.wait_for(state="visible"), timeout=4)
            await btn.click()
            log.info(f"✓ Clicked {'LAY' if is_lay else 'BACK'}: {recommendation}")
        except Exception as e:
            log.warning(f"✗ No se pudo clickar botón de cuotas: {e}")
            return

    elif is_over or is_under:
        target_text = "más" if is_over else "menos"
        clicked = False
        for i in range(count):
            row = runner_rows.nth(i)
            try:
                name_text = (await asyncio.wait_for(row.locator(".runner-name").text_content(), timeout=2) or "").lower()
            except Exception:
                continue
            if target_text in name_text:
                btn_sel = "td.bet-buttons.lay-cell ours-price-button button" if is_lay else "td.bet-buttons.back-cell ours-price-button button"
                try:
                    btn = row.locator(btn_sel).first
                    await asyncio.wait_for(btn.wait_for(state="visible"), timeout=4)
                    await btn.click()
                    log.info(f"✓ Clicked {'LAY' if is_lay else 'BACK'} '{target_text}': {recommendation}")
                    clicked = True
                except Exception as e:
                    log.warning(f"✗ No se pudo clickar over/under: {e}")
                break
        if not clicked:
            log.warning(f"✗ Runner '{target_text}' no encontrado entre {count} filas")
            return
    else:
        log.info(f"Tipo de mercado no manejado automáticamente: {recommendation}")
        return

    await _fill_stake(page)


async def run_test(url: str, recommendation: str, match_name: str) -> None:
    from playwright.async_api import async_playwright

    BOT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    is_first_run = not (BOT_PROFILE_DIR / "Default").exists()

    log.info("=" * 60)
    log.info(f"URL:            {url}")
    log.info(f"Recommendation: {recommendation}")
    log.info(f"Match:          {match_name}")
    log.info(f"Bot profile:    {BOT_PROFILE_DIR}")
    log.info(f"Primera vez:    {is_first_run}")
    log.info("=" * 60)

    if is_first_run:
        log.info("PRIMERA VEZ — abrirá Edge. Inicia sesión manualmente en Betfair.")
        log.info("La sesión quedará guardada para usos futuros.")

    async with async_playwright() as pw:
        log.info("Lanzando Edge con perfil bot dedicado...")
        context = await pw.chromium.launch_persistent_context(
            str(BOT_PROFILE_DIR),
            headless=False,
            channel="msedge",
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
            ],
            no_viewport=True,
            ignore_default_args=["--enable-automation"],
        )
        log.info("Edge lanzado OK")

        page = await context.new_page()
        log.info(f"Navegando a: {url}")
        await asyncio.wait_for(page.goto(url, wait_until="load"), timeout=30)
        await asyncio.sleep(1.5)

        # Detectar si hay login pendiente
        login_btn   = page.locator("input#ssc-lis, input.ssc-cta-primary").first
        needs_login = False
        try:
            needs_login = await asyncio.wait_for(login_btn.is_visible(), timeout=3)
        except Exception:
            pass

        log.info(f"needs_login = {needs_login}")

        if needs_login:
            # Leer credenciales desde fichero local (no trackeado en git)
            creds_file = Path(__file__).parent / "betfair_creds.txt"
            bf_user, bf_pass = "", ""
            if creds_file.exists():
                lines = creds_file.read_text().strip().splitlines()
                if len(lines) >= 2:
                    bf_user = lines[0].strip()
                    bf_pass = lines[1].strip()

            if bf_user and bf_pass:
                log.info("Rellenando credenciales desde betfair_creds.txt...")
                try:
                    await page.locator("input#ssc-liu").first.fill(bf_user)
                    await page.locator("input#ssc-lipw").first.fill(bf_pass)
                    await asyncio.sleep(0.3)
                    await login_btn.click()
                    log.info("Click en Iniciar sesión")
                except Exception as e:
                    log.warning(f"Error rellenando credenciales: {e}")

                # Esperar a que navegue fuera del login (URL cambia o botón desaparece)
                logged_in = False
                for _ in range(20):  # hasta 10s
                    await asyncio.sleep(0.5)
                    try:
                        still_visible = await login_btn.is_visible()
                        if not still_visible:
                            logged_in = True
                            break
                    except Exception:
                        logged_in = True  # botón ya no existe = login OK
                        break
                    if "betfair.es/exchange" in page.url and "login" not in page.url:
                        logged_in = True
                        break

                if logged_in:
                    log.info("✓ Login completado")
                else:
                    log.warning("✗ Login no completado — revisa credenciales en auxiliar/betfair_creds.txt")
                    await context.close()
                    return
            else:
                log.info("=" * 60)
                log.info(">>> Crea auxiliar/betfair_creds.txt con tu usuario en línea 1 y contraseña en línea 2")
                log.info(">>> O inicia sesión manualmente en la ventana de Edge (120s)...")
                log.info("=" * 60)
                # Fallback: esperar login manual detectando cambio de URL
                deadline = asyncio.get_event_loop().time() + 120
                logged_in = False
                while asyncio.get_event_loop().time() < deadline:
                    await asyncio.sleep(1)
                    try:
                        still_visible = await login_btn.is_visible()
                        if not still_visible:
                            logged_in = True
                            break
                    except Exception:
                        logged_in = True
                        break
                if not logged_in:
                    log.warning("✗ Login no detectado — abortando")
                    await context.close()
                    return
                log.info("✓ Login manual detectado")

            # Navegar al partido si fue redirigido tras login
            if url not in page.url:
                log.info(f"Volviendo a: {url}")
                await asyncio.wait_for(page.goto(url, wait_until="load"), timeout=30)
                await asyncio.sleep(3)  # Angular necesita tiempo para renderizar el mercado
        else:
            log.info("✓ Ya logueado via cookies de sesión")

        # Clickar cuotas + stake
        await _click_odds(page, recommendation, match_name)

        log.info("=" * 60)
        log.info("Test terminado. Cierra la ventana cuando quieras.")
        log.info("=" * 60)

        # Mantener abierto para revisar resultado
        await asyncio.sleep(60)
        await context.close()


if __name__ == "__main__":
    url_arg   = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    rec_arg   = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_REC
    match_arg = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_MATCH_NAME
    asyncio.run(run_test(url_arg, rec_arg, match_arg))
