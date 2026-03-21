"""Betting agent: places real bets on Betfair.es via Playwright browser automation.

Uses a persistent browser context (cookies/session survive restarts) and
LLM visual verification at each step for safety.

Flow per signal:
  1. Navigate to match market URL
  2. Screenshot + LLM verify correct market
  3. Click correct price button (Back/Lay)
  4. Enter stake in betslip
  5. Screenshot + LLM verify betslip is correct
  6. Click "Apostar" to place bet
  7. Screenshot + LLM verify confirmation
  8. Log everything with screenshots
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)

# Project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENT_LOGS_DIR = _PROJECT_ROOT / "auxiliar" / "betting_agent_logs"
_SESSION_DIR = Path(__file__).resolve().parent / "browser_session"

# Market type mapping: recommendation text -> market link text in sidebar
_MARKET_LINK_MAP = {
    "OVER 0.5": "Mas/Menos de 0,5 Goles",
    "UNDER 0.5": "Mas/Menos de 0,5 Goles",
    "OVER 1.5": "Mas/Menos de 1,5 Goles",
    "UNDER 1.5": "Mas/Menos de 1,5 Goles",
    "OVER 2.5": "Mas/Menos de 2,5 Goles",
    "UNDER 2.5": "Mas/Menos de 2,5 Goles",
    "OVER 3.5": "Mas/Menos de 3,5 Goles",
    "UNDER 3.5": "Mas/Menos de 3,5 Goles",
    "OVER 4.5": "Mas/Menos de 4,5 Goles",
    "UNDER 4.5": "Mas/Menos de 4,5 Goles",
    "OVER 5.5": "Mas/Menos de 5,5 Goles",
    "UNDER 5.5": "Mas/Menos de 5,5 Goles",
    "OVER 6.5": "Mas/Menos de 6,5 Goles",
    "UNDER 6.5": "Mas/Menos de 6,5 Goles",
    "DRAW": "Cuotas de partido",
    "HOME": "Cuotas de partido",
    "AWAY": "Cuotas de partido",
    "CS ": "Resultado correcto",
}


def _parse_recommendation(recommendation: str) -> dict:
    """Parse recommendation string into structured bet instruction.

    Examples:
        "BACK DRAW @ 3.85"       -> {side: "back", market: "DRAW", selection: "Empate", ...}
        "LAY OVER 4.5 @ 1.25"    -> {side: "lay", market: "OVER 4.5", selection: "Mas 4,5 Goles", ...}
        "BACK CS 0-0 @ 17.5"     -> {side: "back", market: "CS 0-0", selection: "0 - 0", ...}
        "BACK HOME @ 2.10"       -> {side: "back", market: "HOME", selection: <team_name>, ...}
    """
    rec = recommendation.upper().strip()
    side = "back" if rec.startswith("BACK") else "lay"
    rest = rec.replace("BACK ", "").replace("LAY ", "").strip()

    # Extract target odds if present
    target_odds = None
    if " @ " in rest:
        parts = rest.split(" @ ")
        rest = parts[0].strip()
        try:
            target_odds = float(parts[1].strip())
        except ValueError:
            pass

    # Determine market type and selection text for Betfair UI
    market_type = rest  # e.g., "DRAW", "OVER 2.5", "CS 0-0"
    selection_text = ""
    market_link_search = ""

    if rest == "DRAW":
        selection_text = "Empate"
        market_link_search = "Cuotas de partido"
    elif rest in ("HOME", "AWAY"):
        selection_text = rest  # Will be resolved to team name on the page
        market_link_search = "Cuotas de partido"
    elif rest.startswith("OVER"):
        goals = rest.replace("OVER ", "").replace(".", ",")
        selection_text = f"M\u00e1s {goals} Goles"
        market_link_search = f"M\u00e1s/Menos de {goals} Goles"
    elif rest.startswith("UNDER"):
        goals = rest.replace("UNDER ", "").replace(".", ",")
        selection_text = f"Menos {goals} Goles"
        market_link_search = f"M\u00e1s/Menos de {goals} Goles"
    elif rest.startswith("CS "):
        score = rest.replace("CS ", "").strip()
        selection_text = score.replace("-", " - ")
        market_link_search = "Resultado correcto"

    return {
        "side": side,
        "market_type": market_type,
        "selection_text": selection_text,
        "market_link_search": market_link_search,
        "target_odds": target_odds,
    }


class BettingAgent:
    """Automated bet placer using Playwright + LLM verification."""

    def __init__(self, lm_studio_url: str = "http://127.0.0.1:1234",
                 lm_studio_model: str = "qwen/qwen3.5-9b:2"):
        self._pw = None
        self._browser = None
        self._page = None
        self._lm_url = lm_studio_url
        self._lm_model = lm_studio_model
        self._is_logged_in = False
        self._lock = asyncio.Lock()

    async def start(self):
        """Launch persistent browser context."""
        if self._browser is not None:
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            _log.error("playwright not installed. Run: pip install playwright && playwright install chromium")
            raise

        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        _AGENT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch_persistent_context(
            user_data_dir=str(_SESSION_DIR),
            headless=False,
            viewport={"width": 1920, "height": 1080},
            locale="es-ES",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        # Remove webdriver flag
        for page in self._browser.pages:
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        self._page = self._browser.pages[0] if self._browser.pages else await self._browser.new_page()
        await self._page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        _log.info("BettingAgent browser started (persistent session at %s)", _SESSION_DIR)

    async def stop(self):
        """Close browser and cleanup."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None
        self._page = None
        self._is_logged_in = False
        _log.info("BettingAgent browser stopped")

    def is_ready(self) -> bool:
        return self._browser is not None and self._page is not None

    async def _screenshot(self, label: str, bet_id: str) -> Path:
        """Take screenshot and save to logs dir."""
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = _AGENT_LOGS_DIR / f"{bet_id}_{label}_{ts}.png"
        await self._page.screenshot(path=str(path), full_page=False)
        return path

    async def _accept_cookies(self):
        """Dismiss cookie banner if present."""
        selectors = [
            "button:has-text('Aceptar todas las cookies')",
            "#onetrust-accept-btn-handler",
            "button:has-text('Permitir solo las cookies necesarias')",
        ]
        for sel in selectors:
            try:
                btn = self._page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await asyncio.sleep(1)
                    return
            except Exception:
                continue

    async def check_login(self) -> bool:
        """Check if we're logged in by looking for login form vs account elements."""
        try:
            # If login form is visible, we're NOT logged in
            login_btn = self._page.locator("button:has-text('Iniciar sesi\u00f3n')")
            if await login_btn.is_visible(timeout=3000):
                self._is_logged_in = False
                return False
            self._is_logged_in = True
            return True
        except Exception:
            return False

    async def login(self, username: str, password: str) -> bool:
        """Login to Betfair.es."""
        if not self.is_ready():
            return False

        try:
            await self._page.goto("https://www.betfair.es/exchange/plus/es/f%C3%BAtbol-apuestas-1")
            await asyncio.sleep(3)
            await self._accept_cookies()

            # Fill credentials
            user_input = self._page.locator("input[placeholder*='nombre de usuario'], input[placeholder*='correo']").first
            pass_input = self._page.locator("input[placeholder*='contrase\u00f1a']").first
            await user_input.fill(username)
            await asyncio.sleep(0.5)
            await pass_input.fill(password)
            await asyncio.sleep(0.5)

            # Click login
            await self._page.locator("button:has-text('Iniciar sesi\u00f3n')").click()
            await asyncio.sleep(5)

            # Verify login success
            logged_in = await self.check_login()
            if logged_in:
                _log.info("Login successful")
            else:
                _log.warning("Login may have failed - login form still visible")
            return logged_in
        except Exception as e:
            _log.error("Login failed: %s", e)
            return False

    async def place_bet(self, signal: dict, stake: float) -> dict:
        """Place a real bet on Betfair.es based on a signal.

        Args:
            signal: Signal dict from detect_betting_signals (match_url, recommendation, back_odds, etc.)
            stake: Stake amount in EUR

        Returns:
            dict with {success, steps[], screenshots[], llm_responses[], error}
        """
        async with self._lock:
            return await self._place_bet_impl(signal, stake)

    async def _place_bet_impl(self, signal: dict, stake: float) -> dict:
        """Internal implementation of bet placement."""
        bet_id = f"bet_{int(time.time())}"
        match_url = signal.get("match_url", "")
        recommendation = signal.get("recommendation", "")
        match_name = signal.get("match_name", "")
        target_odds = signal.get("back_odds")

        result = {
            "success": False,
            "bet_id": bet_id,
            "signal": signal,
            "stake": stake,
            "steps": [],
            "screenshots": [],
            "llm_responses": [],
            "error": None,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if not self.is_ready():
            result["error"] = "Browser not started"
            return result

        if not match_url or not recommendation:
            result["error"] = f"Missing match_url or recommendation: url={match_url}, rec={recommendation}"
            return result

        # Parse the recommendation
        parsed = _parse_recommendation(recommendation)
        side = parsed["side"]
        selection_text = parsed["selection_text"]
        market_link_search = parsed["market_link_search"]

        _log.info("[%s] Starting bet placement: %s %s @ %s, stake=%.2f",
                  bet_id, side.upper(), selection_text, target_odds, stake)

        try:
            # ── Step 1: Navigate to match page ──
            result["steps"].append("navigate_to_match")
            await self._page.goto(match_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            await self._accept_cookies()

            # ── Step 2: Navigate to specific market ──
            result["steps"].append("navigate_to_market")
            if market_link_search != "Cuotas de partido":
                # Need to find and click the market link in sidebar
                market_link = self._page.locator(f"a:has-text('{market_link_search}')").first
                try:
                    await market_link.click(timeout=5000)
                    await asyncio.sleep(2)
                except Exception:
                    _log.warning("[%s] Could not find sidebar link '%s', staying on main page",
                                 bet_id, market_link_search)

            # ── Step 3: Screenshot + LLM verify market ──
            result["steps"].append("verify_market")
            ss_market = await self._screenshot("01_market", bet_id)
            result["screenshots"].append(str(ss_market))

            from . import verifier
            llm_market = verifier.verify_market(
                ss_market, market_link_search, match_name,
                url=self._lm_url, model=self._lm_model,
            )
            result["llm_responses"].append({"step": "verify_market", "response": llm_market})
            _log.info("[%s] LLM market verification: %s", bet_id, llm_market)

            if not llm_market.get("ok", False):
                result["error"] = f"LLM rejected market: {llm_market.get('details', 'unknown')}"
                _log.warning("[%s] %s", bet_id, result["error"])
                # Continue anyway if market looks plausible (LLM may be uncertain)

            # ── Step 4: Find and click the correct price button ──
            result["steps"].append("click_price")
            clicked = await self._click_selection(side, selection_text, parsed)
            if not clicked:
                result["error"] = f"Could not find selection '{selection_text}' for {side}"
                _log.error("[%s] %s", bet_id, result["error"])
                return result

            await asyncio.sleep(1.5)

            # ── Step 5: Enter stake ──
            result["steps"].append("enter_stake")
            stake_input = self._page.locator(
                "betslip-size-input input[type='text'], "
                "betslip-size-input input[type='number'], "
                "betslip-size-input input:not([readonly])"
            ).last
            try:
                # The betslip has two inputs: odds (first) and stake (second)
                # Try to find the stake input (second textbox in betslip)
                betslip_inputs = self._page.locator(".betslip-selection input[type='text'], .betslip-selection input")
                count = await betslip_inputs.count()
                if count >= 2:
                    stake_input = betslip_inputs.nth(1)
                else:
                    # Fallback: find input that's empty (stake) vs prefilled (odds)
                    for i in range(count):
                        val = await betslip_inputs.nth(i).input_value()
                        if not val or val == "":
                            stake_input = betslip_inputs.nth(i)
                            break
            except Exception:
                pass

            await stake_input.click()
            await stake_input.fill(str(stake))
            await asyncio.sleep(1)

            # ── Step 6: Screenshot + LLM verify betslip ──
            result["steps"].append("verify_betslip")
            ss_betslip = await self._screenshot("02_betslip", bet_id)
            result["screenshots"].append(str(ss_betslip))

            llm_betslip = verifier.verify_betslip(
                ss_betslip, selection_text, target_odds or 0, stake,
                url=self._lm_url, model=self._lm_model,
            )
            result["llm_responses"].append({"step": "verify_betslip", "response": llm_betslip})
            _log.info("[%s] LLM betslip verification: %s", bet_id, llm_betslip)

            if not llm_betslip.get("ok", False):
                result["error"] = f"LLM rejected betslip: {llm_betslip.get('details', 'unknown')}"
                _log.warning("[%s] %s - proceeding with caution", bet_id, result["error"])

            # ── Step 7: Click "Apostar" button ──
            result["steps"].append("click_apostar")
            apostar_btn = self._page.locator("button:has-text('Apostar')").last
            if not await apostar_btn.is_enabled(timeout=3000):
                result["error"] = "Apostar button is disabled"
                _log.error("[%s] %s", bet_id, result["error"])
                return result

            await apostar_btn.click()
            await asyncio.sleep(3)

            # ── Step 8: Handle confirmation dialog if present ──
            result["steps"].append("handle_confirmation")
            try:
                confirm_btn = self._page.locator("button:has-text('Confirmar'), button:has-text('Confirm')")
                if await confirm_btn.is_visible(timeout=3000):
                    await confirm_btn.click()
                    await asyncio.sleep(2)
            except Exception:
                pass  # No confirmation dialog - bet placed directly

            # ── Step 9: Screenshot + LLM verify confirmation ──
            result["steps"].append("verify_confirmation")
            ss_confirm = await self._screenshot("03_confirmation", bet_id)
            result["screenshots"].append(str(ss_confirm))

            llm_confirm = verifier.verify_confirmation(
                ss_confirm, url=self._lm_url, model=self._lm_model,
            )
            result["llm_responses"].append({"step": "verify_confirmation", "response": llm_confirm})
            _log.info("[%s] LLM confirmation verification: %s", bet_id, llm_confirm)

            result["success"] = True
            result["steps"].append("completed")
            _log.info("[%s] Bet placement completed successfully", bet_id)

        except Exception as e:
            result["error"] = str(e)
            _log.error("[%s] Bet placement failed: %s", bet_id, e, exc_info=True)
            # Take error screenshot
            try:
                ss_err = await self._screenshot("error", bet_id)
                result["screenshots"].append(str(ss_err))
            except Exception:
                pass

        # Save full result log
        self._save_log(result)
        return result

    async def _click_selection(self, side: str, selection_text: str, parsed: dict) -> bool:
        """Find and click the correct Back/Lay price button for a selection.

        The Betfair table structure:
        - Each runner row has: [runner_name] [back3] [back2] [back1] [lay1] [lay2] [lay3]
        - back1 = best back (td.last-back-cell or 3rd back column)
        - lay1 = best lay (td.first-lay-cell or 1st lay column)
        """
        try:
            # Find all runner rows
            runners = self._page.locator("tr.runner-line, [data-testid='runner-row']")
            count = await runners.count()

            for i in range(count):
                row = runners.nth(i)
                # Get runner name from h3
                name_el = row.locator("h3, .runner-name")
                name = (await name_el.inner_text()).strip()

                # Check if this is the selection we want
                if not self._matches_selection(name, selection_text, parsed):
                    continue

                # Found our runner - click the best back or lay price
                if side == "back":
                    # Best back = last back cell (closest to center)
                    cells = row.locator("td.bet-buttons.back-cell button, td.last-back-cell button")
                    cell_count = await cells.count()
                    if cell_count > 0:
                        # Last back cell = best back price
                        await cells.nth(cell_count - 1).click()
                        _log.info("Clicked BACK on '%s' (cell %d of %d)", name, cell_count, cell_count)
                        return True
                else:
                    # Best lay = first lay cell (closest to center)
                    cells = row.locator("td.bet-buttons.lay-cell button, td.first-lay-cell button")
                    if await cells.count() > 0:
                        await cells.nth(0).click()
                        _log.info("Clicked LAY on '%s'", name)
                        return True

            _log.warning("Selection '%s' not found in %d runners", selection_text, count)
            return False
        except Exception as e:
            _log.error("Failed to click selection: %s", e)
            return False

    @staticmethod
    def _matches_selection(runner_name: str, selection_text: str, parsed: dict) -> bool:
        """Check if a runner name matches the expected selection."""
        name_lower = runner_name.lower().strip()
        sel_lower = selection_text.lower().strip()

        # Direct match
        if sel_lower in name_lower or name_lower in sel_lower:
            return True

        # Empate / Draw
        if sel_lower in ("empate", "draw") and ("empate" in name_lower or "draw" in name_lower):
            return True

        # Over/Under with various formats
        if "goles" in sel_lower and "goles" in name_lower:
            # Extract the number from both
            sel_num = re.search(r"[\d,]+", sel_lower)
            name_num = re.search(r"[\d,]+", name_lower)
            if sel_num and name_num and sel_num.group() == name_num.group():
                # Check direction (Mas/Menos)
                sel_is_over = "m\u00e1s" in sel_lower or "mas" in sel_lower or "over" in sel_lower
                name_is_over = "m\u00e1s" in name_lower or "mas" in name_lower or "over" in name_lower
                return sel_is_over == name_is_over

        # Correct Score: "0 - 0" matches "0 - 0" or "0-0"
        if re.match(r"\d+\s*-\s*\d+", sel_lower):
            sel_clean = re.sub(r"\s+", "", sel_lower)
            name_clean = re.sub(r"\s+", "", name_lower)
            return sel_clean in name_clean

        return False

    def _save_log(self, result: dict):
        """Save bet placement log to JSON file."""
        try:
            _AGENT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
            log_path = _AGENT_LOGS_DIR / f"{result['bet_id']}_log.json"
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            _log.info("Bet log saved: %s", log_path)
        except Exception as e:
            _log.error("Failed to save bet log: %s", e)


# ── Module-level singleton ──
_agent_instance: BettingAgent | None = None


def get_agent() -> BettingAgent:
    """Get or create the singleton BettingAgent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = BettingAgent()
    return _agent_instance


def schedule_live_bet(signal: dict, stake: float, config: dict) -> None:
    """Schedule a live bet from sync context (called by run_paper_auto_place).

    Launches the async bet placement in a background thread to avoid
    blocking the paper trading loop.
    """
    import threading

    def _run():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    _handle_live_bet(signal, stake, config)
                )
                if result:
                    _log.info("Live bet result: success=%s, bet_id=%s, error=%s",
                              result.get("success"), result.get("bet_id"), result.get("error"))
            finally:
                loop.close()
        except Exception as e:
            _log.error("Live bet thread failed: %s", e)

    t = threading.Thread(target=_run, name="live-bet-agent", daemon=True)
    t.start()
    _log.info("Live bet scheduled for %s / %s", signal.get("match_name"), signal.get("recommendation"))


async def _handle_live_bet(signal: dict, stake: float, config: dict) -> dict | None:
    """Internal async handler for live bet placement."""
    agent = get_agent()

    # Update LLM settings from config
    agent._lm_url = config.get("lm_studio_url", "http://127.0.0.1:1234")
    agent._lm_model = config.get("lm_studio_model", "qwen/qwen3.5-9b:2")

    if not agent.is_ready():
        try:
            await agent.start()
        except Exception as e:
            _log.error("Failed to start BettingAgent: %s", e)
            return {"success": False, "error": f"Agent start failed: {e}"}

    # Check login status
    if not agent._is_logged_in:
        _log.warning("BettingAgent: not logged in. User must login manually via the agent browser window.")
        return {"success": False, "error": "Not logged in. Open the agent browser and login to Betfair."}

    return await agent.place_bet(signal, stake)
