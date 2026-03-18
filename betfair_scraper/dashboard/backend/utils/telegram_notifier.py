"""
Telegram notification helper for Furbo Signals bot.
Manages the full lifecycle of signal messages:
  - send_signal_preview(): new pre-mature signal → sends message, returns message_id
  - update_signal_preview(): signal still maturing → edits existing message
  - send_signal() / edit to placed: signal placed → edits or sends new placed message
  - delete_message(): signal expired → deletes message
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


def _telegram_api(method: str, params: dict) -> dict | None:
    """Generic helper to call Telegram Bot API. Returns parsed JSON or None on error."""
    _load_env_if_needed()
    if not _TOKEN or not _CHAT_ID:
        return None
    try:
        url = f"https://api.telegram.org/bot{_TOKEN}/{method}"
        payload = json.dumps(params).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log.debug(f"Telegram {method} failed: {e}")
        return None


def _build_preview_text(sig: dict, needed: float, stake: float) -> str:
    """Build pre-maturity preview message — misma estructura que el mensaje de colocación,
    con título ⏳ ... — pre-madura y línea extra de madurez en lugar de 'Válida hasta'."""
    bet_type      = sig.get("bet_type", "BACK").upper()
    strategy_name = sig.get("strategy_name", "")
    strategy_key  = sig.get("strategy", "")
    match_name    = sig.get("match_name", "")
    match_url     = sig.get("match_url", "")
    minute        = sig.get("minute", "?")
    score         = sig.get("score", "?")
    back_odds     = sig.get("back_odds", "?")
    min_odds      = sig.get("min_odds")
    wr            = sig.get("win_rate_historical")
    sample_size   = sig.get("sample_size")
    sig_age       = sig.get("signal_age_minutes", 0) or 0
    rec           = sig.get("recommendation", "")
    rec_action    = rec.rsplit(" @ ", 1)[0]
    entry_conditions = sig.get("entry_conditions") or {}

    match_line = f"[{match_name}]({match_url})" if match_url else match_name
    odds_str   = f"{back_odds:.2f}" if isinstance(back_odds, (int, float)) else str(back_odds)

    if min_odds is not None:
        _min_fmt = str(int(min_odds)) if min_odds == int(min_odds) else f"{min_odds:.2f}"
        min_str = f" | mín: {_min_fmt}"
    else:
        min_str = ""

    # Línea de madurez: cuándo se colocará
    remaining = max(0.0, needed - sig_age)
    if isinstance(minute, (int, float)) and isinstance(sig_age, (int, float)):
        target_min  = int(minute) + int(max(0, needed - sig_age))
        maturity_line = f"· ⏳ Madura en: ~min {target_min}' (faltan ~{remaining:.0f} min)"
    else:
        maturity_line = f"· ⏳ Madura en: ~{remaining:.0f} min"

    # Stats
    stats_parts = []
    if wr:
        stats_parts.append(f"WR {wr:.0f}%")
    if sample_size:
        stats_parts.append(f"N={sample_size}")
    stats_line = f"· {' | '.join(stats_parts)}" if stats_parts else None

    # Entry conditions
    cond_lines = []
    for k, v in entry_conditions.items():
        if k == "odds":
            continue
        label   = k.replace("_", " ").title()
        val_str = f"{v:.2f}" if isinstance(v, float) else str(v)
        cond_lines.append(f"  {label}: {val_str}")

    icon = "🔴" if bet_type == "LAY" else "🟢"
    lines = [
        f"⏳ {icon} *{strategy_name}* — pre-madura",
        "",
        match_line,
        f"· {rec_action} @ {odds_str}{min_str}",
        f"· Min {minute}' | {score}",
    ]
    if stats_line:
        lines.append(stats_line)
    lines.append(f"· Stake {stake:.2f} EUR")
    lines.append(maturity_line)
    if cond_lines:
        lines.append("· Params:")
        lines.extend(cond_lines)

    return "\n".join(lines)


def send_signal_preview(sig: dict, needed: float, stake: float) -> int | None:
    """Send a pre-maturity preview message. Returns message_id or None on failure."""
    _load_env_if_needed()
    if not _TOKEN or not _CHAT_ID:
        return None
    try:
        text   = _build_preview_text(sig, needed, stake)
        result = _telegram_api("sendMessage", {
            "chat_id": _CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        })
        if result and result.get("ok"):
            return result["result"]["message_id"]
    except Exception as e:
        log.debug(f"Telegram send_signal_preview failed: {e}")
    return None


def update_signal_preview(message_id: int, sig: dict, needed: float, stake: float) -> bool:
    """Edit an existing preview message with updated minute/state. Returns True if successful."""
    if not message_id:
        return False
    _load_env_if_needed()
    if not _TOKEN or not _CHAT_ID:
        return False
    try:
        text   = _build_preview_text(sig, needed, stake)
        result = _telegram_api("editMessageText", {
            "chat_id": _CHAT_ID,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        })
        # "message is not modified" (400) is expected when text didn't change — not a real error
        return bool(result and result.get("ok"))
    except Exception as e:
        log.debug(f"Telegram update_signal_preview failed: {e}")
        return False


def delete_message(message_id: int) -> bool:
    """Delete a Telegram message by ID. Used when a signal expires. Returns True if successful."""
    if not message_id:
        return False
    _load_env_if_needed()
    if not _TOKEN or not _CHAT_ID:
        return False
    try:
        result = _telegram_api("deleteMessage", {
            "chat_id": _CHAT_ID,
            "message_id": message_id,
        })
        return bool(result and result.get("ok"))
    except Exception as e:
        log.debug(f"Telegram delete_message failed: {e}")
        return False


def send_signal(sig: dict, stake: float, message_id: int | None = None) -> bool:
    """Send or edit a Telegram message for a newly placed signal. Never raises.
    If message_id is provided, edits the existing pre-maturity preview.
    Returns True if message was sent/edited successfully, False otherwise."""
    _load_env_if_needed()
    if not _TOKEN or not _CHAT_ID:
        return False

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
        if min_odds is not None:
            _min_fmt = str(int(min_odds)) if min_odds == int(min_odds) else f"{min_odds:.2f}"
            min_str = f" | mín: {_min_fmt}"
        else:
            min_str = ""
        odds_line = f"· *{rec_action}* @ {odds_str}{min_str}"

        # Context line
        context_line = f"· Min {minute}' | {score}"

        # Stats line
        stats_parts = []
        if wr:
            stats_parts.append(f"WR {wr:.0f}%")
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

        if message_id:
            # Edit the existing pre-maturity preview message
            result = _telegram_api("editMessageText", {
                "chat_id": _CHAT_ID,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            })
            return bool(result and result.get("ok"))
        else:
            # Send a new message (fallback / first-time placement without prior preview)
            result = _telegram_api("sendMessage", {
                "chat_id": _CHAT_ID,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            })
            return bool(result and result.get("ok"))

    except Exception as e:
        log.debug(f"Telegram notification failed (non-critical): {e}")
        return False