"""
Signals Audit Logger
====================
Registra en tiempo real el ciclo de vida completo de cada señal de apuesta:

  Ciclo de polling:
  - CYCLE_START / CYCLE_END   : cada ciclo de detección (~30s)

  Ciclo de vida de una señal:
  - SIGNAL_NEW                : primera aparición de la señal (age < 1 min)
  - SIGNAL_ACTIVE             : señal activa en ciclo corriente (todas condiciones OK)
  - SIGNAL_MATURING           : activa pero esperando maduración (age < min_dur)
  - SIGNAL_FILTERED           : descartada por filtro real (riesgo, odds, dedup, etc.)
  - SIGNAL_EXPIRED            : desapareció antes de madurar (sin placement)
  - BET_PLACED                : apuesta paper registrada en placed_bets.csv

  Notificaciones Telegram:
  - TELEGRAM_SENT             : mensaje enviado correctamente
  - TELEGRAM_FAILED           : envío fallido en el intento inmediato
  - TELEGRAM_RETRY_OK         : reintento posterior exitoso
  - TELEGRAM_RETRY_FAIL       : reintento posterior fallido (sigue pendiente)

  Liquidación:
  - CASHOUT                   : cashout automático ejecutado
  - SETTLEMENT                : liquidación automática (won/lost)

Log file: betfair_scraper/signals_audit.log  (rotación 50MB x10)
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

# betfair_scraper/signals_audit.log
# __file__ está en betfair_scraper/dashboard/backend/utils/
_LOG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "signals_audit.log"

_logger = None


def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _logger = logging.getLogger("signals_audit")
    _logger.setLevel(logging.DEBUG)

    handler = RotatingFileHandler(
        _LOG_PATH,
        maxBytes=50 * 1024 * 1024,   # 50 MB por fichero
        backupCount=10,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(handler)
    _logger.propagate = False
    return _logger


def _ts() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _fv(v, decimals: int = 2) -> str:
    """Formatea un valor de forma segura."""
    if v is None or v == "":
        return "n/a"
    try:
        if isinstance(v, float):
            return f"{v:.{decimals}f}"
        return str(v)
    except Exception:
        return str(v)


# ──────────────────────────────────────────────────────────────────────────────
# EVENTS DE CICLO
# ──────────────────────────────────────────────────────────────────────────────

def log_cycle_start(n_matches: int, source: str = "auto"):
    """Inicio de un ciclo de detección de señales."""
    _get_logger().info(
        f"\n{'═'*100}\n"
        f"{_ts()} UTC | CYCLE_START | source={source} | matches_live={n_matches}\n"
        f"{'─'*100}"
    )


def log_cycle_end(n_signals: int, n_radar: int, n_placed: int, n_filtered: int):
    """Fin de un ciclo de detección."""
    _get_logger().info(
        f"{_ts()} UTC | CYCLE_END   | "
        f"signals_active={n_signals} | radar_items={n_radar} | "
        f"placed_this_cycle={n_placed} | filtered_out={n_filtered}\n"
        f"{'─'*100}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EVENTS DE SEÑAL
# ──────────────────────────────────────────────────────────────────────────────

def log_signal_new(sig: dict):
    """Primera detección de una señal (signal_age_minutes < 1)."""
    age = sig.get("signal_age_minutes", 0) or 0
    min_dur = sig.get("min_duration_caps", 1) or 1
    _get_logger().info(
        f"{_ts()} UTC | SIGNAL_NEW      | "
        f"match={sig.get('match_id', '')} | "
        f"name=\"{sig.get('match_name', '?')}\" | "
        f"strategy={sig.get('strategy', '')} | "
        f"min={sig.get('minute', '')} | score={sig.get('score', '')} | "
        f"odds={_fv(sig.get('back_odds'))} | min_odds={_fv(sig.get('min_odds'))} | "
        f"odds_ok={sig.get('odds_favorable', '?')} | "
        f"age={_fv(age, 1)}min | min_dur={min_dur} | "
        f"needs={max(0, min_dur - age):.1f}min_more | "
        f"confidence={sig.get('confidence', '?')} | ev={_fv(sig.get('expected_value'))} | "
        f"rec={sig.get('recommendation', '')}"
    )


def log_signal_active(sig: dict):
    """Señal completamente activa (todas las condiciones cumplidas)."""
    ts = _ts()
    age = sig.get("signal_age_minutes", 0) or 0
    min_dur = sig.get("min_duration_caps", 1) or 1
    age_ready = isinstance(age, (int, float)) and isinstance(min_dur, (int, float)) and age >= min_dur + 1

    _get_logger().info(
        f"{ts} UTC | SIGNAL_ACTIVE   | "
        f"match={sig.get('match_id', '')} | "
        f"name=\"{sig.get('match_name', '?')}\" | "
        f"strategy={sig.get('strategy', '')} | "
        f"min={sig.get('minute', '')} | score={sig.get('score', '')} | "
        f"odds={_fv(sig.get('back_odds'))} | min_odds={_fv(sig.get('min_odds'))} | "
        f"odds_ok={sig.get('odds_favorable', '?')} | "
        f"age={_fv(age, 1)}min | min_dur={min_dur} | age_ready={age_ready} | "
        f"confidence={sig.get('confidence', '?')} | ev={_fv(sig.get('expected_value'))} | "
        f"risk={(sig.get('risk_info') or {}).get('risk_level', 'none')} | "
        f"rec={sig.get('recommendation', '')}"
    )


def log_signal_maturing(sig: dict, age: float, needed: float):
    """Señal activa pero esperando min_duration antes de poder colocarse."""
    remaining = max(0.0, needed - age)
    _get_logger().info(
        f"{_ts()} UTC | SIGNAL_MATURING | "
        f"match={sig.get('match_id', '')} | "
        f"name=\"{sig.get('match_name', '?')}\" | "
        f"strategy={sig.get('strategy', '')} | "
        f"min={sig.get('minute', '')} | score={sig.get('score', '')} | "
        f"odds={_fv(sig.get('back_odds'))} | "
        f"age={_fv(age, 1)}min | needed={_fv(needed, 1)}min | "
        f"remaining={_fv(remaining, 1)}min | "
        f"odds_ok={sig.get('odds_favorable', '?')} | "
        f"rec={sig.get('recommendation', '')}"
    )


def log_signal_expired(sig: dict):
    """Señal que desapareció antes de madurar (sin placement). Registra que existió."""
    age = sig.get("signal_age_minutes", 0) or 0
    min_dur = sig.get("min_duration_caps", 1) or 1
    _get_logger().info(
        f"{_ts()} UTC | SIGNAL_EXPIRED  | "
        f"match={sig.get('match_id', '')} | "
        f"name=\"{sig.get('match_name', '?')}\" | "
        f"strategy={sig.get('strategy', '')} | "
        f"min={sig.get('minute', '')} | score={sig.get('score', '')} | "
        f"odds={_fv(sig.get('back_odds'))} | "
        f"age_reached={_fv(age, 1)}min | min_dur_needed={min_dur} | "
        f"rec={sig.get('recommendation', '')}"
    )


def log_signal_filtered(sig: dict, reason: str):
    """Señal detectada pero descartada por filtro real (riesgo, odds, dedup, etc.)."""
    _get_logger().info(
        f"{_ts()} UTC | SIGNAL_FILTERED | "
        f"match={sig.get('match_id', '')} | "
        f"name=\"{sig.get('match_name', '?')}\" | "
        f"strategy={sig.get('strategy', '')} | "
        f"min={sig.get('minute', '')} | score={sig.get('score', '')} | "
        f"odds={_fv(sig.get('back_odds'))} | "
        f"age={_fv(sig.get('signal_age_minutes', 0), 1)}min | "
        f"REASON={reason}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EVENTS DEL RADAR (watchlist)
# ──────────────────────────────────────────────────────────────────────────────

def log_radar_item(item: dict):
    """Partido en el radar: condiciones parcialmente cumplidas."""
    conditions = item.get("conditions", [])
    cond_parts = []
    for c in conditions:
        label = c.get("label", "?")
        c_met = "OK" if c.get("met") else "FAIL"
        current = c.get("current", "")
        target = c.get("target", "")
        if current and target:
            cond_parts.append(f"{label}={current}(req:{target}):{c_met}")
        else:
            cond_parts.append(f"{label}:{c_met}")

    _get_logger().info(
        f"{_ts()} UTC | RADAR           | "
        f"match={item.get('match_id', '')} | "
        f"name=\"{item.get('match_name', '?')}\" | "
        f"strategy={item.get('strategy', '')} {item.get('version', '')} | "
        f"min={item.get('minute', '')} | score={item.get('score', '')} | "
        f"cond={item.get('met', 0)}/{item.get('total', 0)} | "
        f"proximity={item.get('proximity', 0)}% | "
        f"[{' | '.join(cond_parts)}]"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EVENTS DE APUESTA
# ──────────────────────────────────────────────────────────────────────────────

def log_bet_placed(bet_id: int, sig: dict, stake: float):
    """Apuesta paper escrita en placed_bets.csv."""
    age = sig.get("signal_age_minutes", 0) or 0
    min_dur = sig.get("min_duration_caps", "?")
    _get_logger().info(
        f"{_ts()} UTC | BET_PLACED      | "
        f"bet_id={bet_id} | "
        f"match={sig.get('match_id', '')} | "
        f"name=\"{sig.get('match_name', '?')}\" | "
        f"strategy={sig.get('strategy', '')} | "
        f"min={sig.get('minute', '')} | score={sig.get('score', '')} | "
        f"rec={sig.get('recommendation', '')} | "
        f"odds={_fv(sig.get('back_odds'))} | stake={stake} | "
        f"signal_age={_fv(age, 1)}min | min_dur={min_dur} | "
        f"→ Telegram pending (telegram_sent=0)"
    )


# ──────────────────────────────────────────────────────────────────────────────
# EVENTOS DE TELEGRAM
# ──────────────────────────────────────────────────────────────────────────────

def log_telegram_sent(bet_id: int, match_id: str, strategy: str):
    """Notificación Telegram enviada correctamente en el intento inmediato."""
    _get_logger().info(
        f"{_ts()} UTC | TELEGRAM_SENT   | "
        f"bet_id={bet_id} | match={match_id} | strategy={strategy} | "
        f"attempt=immediate | result=OK"
    )


def log_telegram_failed(bet_id: int, match_id: str, strategy: str):
    """Notificación Telegram fallida en el intento inmediato. Se reintentará."""
    _get_logger().warning(
        f"{_ts()} UTC | TELEGRAM_FAILED | "
        f"bet_id={bet_id} | match={match_id} | strategy={strategy} | "
        f"attempt=immediate | result=FAIL → queued for retry (check backend log for error)"
    )


def log_telegram_retry(bet_id: int, match_id: str, strategy: str, success: bool, attempt_n: int):
    """Reintento de notificación Telegram (ciclos posteriores al placement)."""
    result = "OK → telegram_sent=1" if success else "FAIL → will retry next cycle"
    level = "info" if success else "warning"
    msg = (
        f"{_ts()} UTC | TELEGRAM_RETRY  | "
        f"bet_id={bet_id} | match={match_id} | strategy={strategy} | "
        f"retry_attempt={attempt_n} | result={result}"
    )
    if success:
        _get_logger().info(msg)
    else:
        _get_logger().warning(msg)


# ──────────────────────────────────────────────────────────────────────────────
# EVENTS DE CASHOUT Y LIQUIDACIÓN
# ──────────────────────────────────────────────────────────────────────────────

def log_cashout(bet: dict, pl: float, lay_now: float, threshold: float):
    """Cashout automático ejecutado."""
    min_now = bet.get("live_minute")
    _get_logger().info(
        f"{_ts()} UTC | CASHOUT         | "
        f"bet_id={bet.get('id', '')} | "
        f"match={bet.get('match_id', '')} | "
        f"name=\"{bet.get('match_name', '?')}\" | "
        f"strategy={bet.get('strategy', '')} | "
        f"rec={bet.get('recommendation', '')} | "
        f"min_entry={bet.get('minute', '')} | "
        f"min_now={_fv(min_now, 0) if min_now is not None else 'n/a'} | "
        f"score_now={bet.get('live_score', '?')} | "
        f"back_odds={_fv(bet.get('back_odds'))} | "
        f"lay_now={_fv(lay_now)} | threshold={_fv(threshold)} | "
        f"pl={pl:+.2f} | stake={bet.get('stake', '')}"
    )


def log_settlement(bet: dict, result: str, pl: float):
    """Liquidación automática al finalizar el partido (won/lost)."""
    min_now = bet.get("live_minute")
    _get_logger().info(
        f"{_ts()} UTC | SETTLEMENT      | "
        f"bet_id={bet.get('id', '')} | "
        f"match={bet.get('match_id', '')} | "
        f"name=\"{bet.get('match_name', '?')}\" | "
        f"strategy={bet.get('strategy', '')} | "
        f"rec={bet.get('recommendation', '')} | "
        f"min_entry={bet.get('minute', '')} | "
        f"min_final={_fv(min_now, 0) if min_now is not None else 'n/a'} | "
        f"score_final={bet.get('live_score', '?')} | "
        f"result={result} | pl={pl:+.2f} | stake={bet.get('stake', '')}"
    )