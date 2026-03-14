"""
Background Telegram bot polling task.
Handles inline keyboard callback queries (e.g. "Añadir a MI PAPER").
Uses long-polling (getUpdates with timeout=25) — no public URL needed.
Non-blocking: errors never propagate to the main app.
"""

import asyncio
import json
import logging
import urllib.request
from typing import Optional

log = logging.getLogger(__name__)

_update_offset: int = 0


def _tg_post(token: str, method: str, payload: dict) -> dict:
    """Synchronous Telegram API POST. Returns parsed JSON response."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=35) as resp:
        return json.loads(resp.read())


def _get_updates(token: str, offset: int) -> list:
    """Long-poll Telegram for new updates (blocks up to 25s)."""
    result = _tg_post(token, "getUpdates", {
        "offset": offset,
        "timeout": 25,
        "allowed_updates": ["callback_query"],
    })
    return result.get("result", [])


def _answer_callback(token: str, callback_query_id: str, text: str) -> None:
    """Show a toast notification and dismiss the loading spinner."""
    try:
        _tg_post(token, "answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": False,
        })
    except Exception as e:
        log.debug(f"answerCallbackQuery failed: {e}")


def _handle_callback(token: str, cq: dict) -> None:
    """Process one callback query. Never raises."""
    cq_id = cq.get("id", "")
    data = cq.get("data", "")

    if not data.startswith("add_manual:"):
        return

    try:
        bet_id = int(data.split(":", 1)[1])
    except (ValueError, IndexError):
        _answer_callback(token, cq_id, "❌ Error: ID inválido")
        return

    try:
        from api.bets import _add_to_manual_impl
        _add_to_manual_impl(bet_id)
        _answer_callback(token, cq_id, "✅ Añadida a MI PAPER")
    except ValueError as e:
        msg = str(e)
        if msg.startswith("409:"):
            _answer_callback(token, cq_id, "✓ Ya estaba en MI PAPER")
        else:
            _answer_callback(token, cq_id, f"❌ {msg}")
    except Exception as e:
        log.debug(f"Telegram callback handler error: {e}")
        _answer_callback(token, cq_id, "❌ Error interno")


async def start_polling() -> None:
    """Async background task: poll Telegram for callbacks. Never raises."""
    global _update_offset

    from utils import telegram_notifier as _tg_mod
    loop = asyncio.get_event_loop()

    log.info("Telegram bot callback polling started")

    while True:
        try:
            _tg_mod._load_env_if_needed()
            token: str = _tg_mod._TOKEN

            if not token:
                await asyncio.sleep(60)
                continue

            updates = await loop.run_in_executor(
                None, _get_updates, token, _update_offset
            )

            for update in updates:
                _update_offset = update["update_id"] + 1
                cq = update.get("callback_query")
                if cq:
                    await loop.run_in_executor(None, _handle_callback, token, cq)

        except asyncio.CancelledError:
            break
        except Exception as e:
            log.debug(f"Telegram polling loop error: {e}")
            await asyncio.sleep(5)
