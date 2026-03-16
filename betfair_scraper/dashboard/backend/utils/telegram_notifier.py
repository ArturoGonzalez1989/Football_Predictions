"""
Telegram notification helper for Furbo Signals bot.
Sends a message when a new signal is auto-placed.
Non-blocking: errors are logged but never raise to the caller.
"""

import os
import logging
import urllib.request
import urllib.parse
import json
from pathlib import Path

log = logging.getLogger(__name__)

# Load from env (set at process start from .env file or system env)
_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "cartera_config.json"
_strategy_cfg_cache: dict = {}


def _get_strategy_cfg(strategy_key: str) -> dict:
    """Returns config dict for a strategy key, cached. Empty dict if not found."""
    global _strategy_cfg_cache
    if not _strategy_cfg_cache:
        try:
            raw = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            _strategy_cfg_cache = raw.get("strategies", {})
        except Exception:
            pass
    return _strategy_cfg_cache.get(strategy_key, {})


def _build_valid_until(strategy_key: str, current_minute) -> str | None:
    """
    Returns a 'Válida hasta' string based on minuteMax of the strategy.
    Returns None if no useful info is available.
    """
    cfg = _get_strategy_cfg(strategy_key)
    minute_max = cfg.get("minuteMax")

    if minute_max and minute_max < 90:
        return f"Min {minute_max}' o cambio de marcador"
    else:
        return "cambio de marcador"


def _load_env_if_needed() -> None:
    """Load .env file once if TOKEN not already set via environment."""
    global _TOKEN, _CHAT_ID
    if _TOKEN:
        return
    env_path = Path(__file__).resolve().parents[4] / ".env"
    if not env_path.exists():
        return
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if key == "TELEGRAM_BOT_TOKEN" and not _TOKEN:
                _TOKEN = val
            elif key == "TELEGRAM_CHAT_ID" and not _CHAT_ID:
                _CHAT_ID = val
    except Exception as e:
        log.debug(f"Telegram: could not load .env: {e}")


def send_signal(sig: dict, stake: float, bet_id: int | None = None) -> None:
    """Send a Telegram message for a newly placed signal. Never raises."""
    _load_env_if_needed()
    if not _TOKEN or not _CHAT_ID:
        return

    try:
        bet_type = sig.get("bet_type", "BACK").upper()
        rec = sig.get("recommendation", "")
        match_name = sig.get("match_name", "")
        match_url = sig.get("match_url", "")
        strategy_name = sig.get("strategy_name", "")
        strategy_key = sig.get("strategy", "")
        minute = sig.get("minute", "?")
        score = sig.get("score", "?")
        back_odds = sig.get("back_odds", "?")
        min_odds = sig.get("min_odds")
        wr = sig.get("win_rate_historical")
        roi = sig.get("roi_historical")
        sample_size = sig.get("sample_size")
        confidence = (sig.get("confidence") or "").upper()
        entry_conditions = sig.get("entry_conditions") or {}

        icon = "🔴" if bet_type == "LAY" else "🟢"

        # Match name as clickable Telegram link
        match_line = f"[{match_name}]({match_url})" if match_url else match_name

        # Odds line — rec already contains "@ X.XX" from the backend, strip it to avoid duplicate
        rec_action = rec.rsplit(" @ ", 1)[0]  # e.g. "BACK Over 2.5" without the odds suffix
        odds_str = f"{back_odds:.2f}" if isinstance(back_odds, (int, float)) else str(back_odds)
        min_str = f" | mín: {min_odds:.2f}" if min_odds is not None else ""
        odds_line = f"· *{rec_action}* @ {odds_str}{min_str}"

        # Context line
        conf_str = f" | {confidence}" if confidence else ""
        context_line = f"· Min {minute}' | {score}{conf_str}"

        # Stats line
        stats_parts = []
        if wr:
            stats_parts.append(f"WR {wr:.0f}%")
        if roi is not None:
            sign = "+" if roi >= 0 else ""
            stats_parts.append(f"ROI {sign}{roi:.0f}%")
        if sample_size:
            stats_parts.append(f"N={sample_size}")
        stats_line = f"· {' | '.join(stats_parts)}" if stats_parts else None

        stake_line = f"· Stake {stake:.2f} EUR"

        # Entry conditions (RADAR params snapshot at trigger time)
        cond_lines = []
        for k, v in entry_conditions.items():
            if k == "odds":
                continue  # already in odds_line
            label = k.replace("_", " ").title()
            val_str = f"{v:.2f}" if isinstance(v, float) else str(v)
            cond_lines.append(f"  {label}: {val_str}")

        valid_until = _build_valid_until(strategy_key, minute)
        valid_line = f"· ⏳ Válida hasta: {valid_until}" if valid_until else None

        lines = [f"{icon} *{strategy_name}*", "", match_line, odds_line, context_line]
        if stats_line:
            lines.append(stats_line)
        lines.append(stake_line)
        if valid_line:
            lines.append(valid_line)
        if cond_lines:
            lines.append("· Params:")
            lines.extend(cond_lines)

        text = "\n".join(lines)

        url = f"https://api.telegram.org/bot{_TOKEN}/sendMessage"
        msg: dict = {
            "chat_id": _CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        if bet_id is not None:
            msg["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "✅ Añadir a MI PAPER", "callback_data": f"add_manual:{bet_id}"}
                ]]
            }
        payload = json.dumps(msg).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status != 200:
                log.warning(f"Telegram sendMessage returned {resp.status}")

    except Exception as e:
        log.debug(f"Telegram notification failed (non-critical): {e}")
