import csv
import re
import logging
import traceback
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)

from fastapi import APIRouter, Query
from typing import Dict, List, Any, Optional
from utils import csv_reader
from utils import signals_audit_logger as _audit
from utils import telegram_notifier as _tg
from api.config import load_config

# Path compartido con bets.py
_PLACED_BETS_CSV = Path(__file__).resolve().parent.parent.parent.parent / "placed_bets.csv"
_AUTO_PLACE_LOG = Path(__file__).resolve().parent.parent.parent.parent / "auto_place_errors.log"
_PLACED_BETS_HEADERS = [
    'id', 'timestamp_utc', 'match_id', 'match_name', 'match_url',
    'strategy', 'strategy_name', 'minute', 'score', 'recommendation',
    'back_odds', 'min_odds', 'expected_value', 'confidence',
    'win_rate_historical', 'roi_historical', 'sample_size',
    'bet_type', 'stake', 'notes', 'status', 'result', 'pl', 'telegram_sent'
]

# Dedup en memoria: evita escribir el mismo signal dos veces en la misma sesión de backend
_auto_placed_keys: set = set()

# Dedup para capture requests: evita escribir el mismo trigger más de una vez por señal
_capture_requested_keys: set = set()

# Tracking del ciclo de vida de señales activas:
#   clave  → signal_key (match_id + strategy)
#   valor  → dict con {first_seen_utc, last_seen_utc, cycles, sig_snapshot}
_active_signal_tracker: dict = {}  # type: dict[str, dict]

# Retraso adicional tras madurez de señal antes de colocar la apuesta paper.
# 0 = se coloca en cuanto la señal alcanza min_dur (sin delay artificial).
PAPER_REACTION_DELAY_MINS = 0

# ── Evidencias: snapshot de datos CSV al colocar una apuesta paper ──
_EVIDENCIAS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "evidencias"
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


def _auto_place_signal(sig: dict, stake: float) -> None:
    """Registra automáticamente una señal madura como apuesta paper en placed_bets.csv."""
    match_id = sig.get("match_id", "")
    strategy = sig.get("strategy", "")
    market_key = _live_market_key(sig)  # dedup by market, not strategy

    # Dedup en sesión: ya fue colocado en este ciclo de vida del backend
    if market_key in _auto_placed_keys:
        return

    try:
        # Atomic read-check-write: read all rows, check dedup, write full file
        rows = []
        if _PLACED_BETS_CSV.exists():
            with open(_PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))

        # Dedup check (by market key)
        for row in rows:
            if _live_market_key(row) == market_key:
                _auto_placed_keys.add(market_key)
                return

        # Compute next ID
        ids = [int(r['id']) for r in rows if r.get('id', '').isdigit()]
        next_id = (max(ids) + 1) if ids else 1

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [
            next_id, timestamp,
            match_id,
            sig.get("match_name", ""),
            sig.get("match_url", ""),
            strategy,
            sig.get("strategy_name", ""),
            sig.get("minute", ""),
            sig.get("score", ""),
            sig.get("recommendation", ""),
            sig.get("back_odds", ""),
            sig.get("min_odds", ""),
            sig.get("expected_value", ""),
            sig.get("confidence", ""),
            sig.get("win_rate_historical", ""),
            sig.get("roi_historical", ""),
            sig.get("sample_size", ""),
            "paper",
            stake,
            "auto",   # notas: marca automático
            "pending", "", "", 0,  # telegram_sent=0: pendiente de notificar
        ]

        # Atomic write: write to temp file, then rename
        tmp_path = _PLACED_BETS_CSV.with_suffix('.csv.tmp')
        with open(tmp_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(_PLACED_BETS_HEADERS)
            for row in rows:
                w.writerow([row.get(h, '') for h in _PLACED_BETS_HEADERS])
            w.writerow(new_row)
        # Atomic rename (on Windows this replaces the target)
        import shutil
        shutil.move(str(tmp_path), str(_PLACED_BETS_CSV))

        # ── Audit log: apuesta colocada ──
        try:
            _audit.log_bet_placed(next_id, sig, stake)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Audit log failed for bet {next_id}: {e}")

        # ── Telegram notification ──
        if _tg.send_signal(sig, stake):
            _mark_telegram_sent(next_id)
            try:
                _audit.log_telegram_sent(next_id, match_id, strategy)
            except Exception:
                pass
        else:
            try:
                _audit.log_telegram_failed(next_id, match_id, strategy)
            except Exception:
                pass

        # ── Guardar snapshot de evidencia desde CSV ──
        _save_evidence_snapshot(sig)

        _auto_placed_keys.add(market_key)
    except Exception as e:
        # Loguear error en fichero para depuración (no interrumpir el endpoint)
        logging.getLogger(__name__).error(f"Error placing bet {match_id}/{strategy}: {e}")
        try:
            with open(_AUTO_PLACE_LOG, 'a', encoding='utf-8') as _f:
                _f.write(
                    f"{datetime.utcnow()} | {match_id} | {strategy} | "
                    f"{type(e).__name__}: {e}\n{traceback.format_exc()}\n"
                )
        except Exception:
            pass

def _mark_telegram_sent(bet_id: int) -> None:
    """Actualiza telegram_sent=1 para la apuesta indicada en placed_bets.csv."""
    try:
        if not _PLACED_BETS_CSV.exists():
            return
        with open(_PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            if row.get('id', '') == str(bet_id):
                row['telegram_sent'] = '1'
                break
        tmp_path = _PLACED_BETS_CSV.with_suffix('.csv.tmp')
        with open(tmp_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=_PLACED_BETS_HEADERS, extrasaction='ignore', restval='')
            w.writeheader()
            w.writerows(rows)
        import shutil
        shutil.move(str(tmp_path), str(_PLACED_BETS_CSV))
    except Exception as e:
        logging.getLogger(__name__).debug(f"_mark_telegram_sent failed for bet {bet_id}: {e}")


# Contador de reintentos Telegram por bet_id para loguear attempt_n
_telegram_retry_counts: dict = {}  # type: dict[str, int]


def _retry_telegram_notifications() -> None:
    """Reintenta el envío de Telegram para bets recientes (< 2h) con telegram_sent=0.
    Llamado al inicio de cada ciclo de paper trading.
    """
    try:
        if not _PLACED_BETS_CSV.exists():
            return
        with open(_PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        now = datetime.utcnow()
        updated = False
        for row in rows:
            # Solo filas explícitamente marcadas como no enviadas
            if row.get('telegram_sent', '') != '0':
                continue
            bet_id_str = row.get('id', '?')
            try:
                ts = datetime.strptime(row['timestamp_utc'], "%Y-%m-%d %H:%M:%S")
                age_secs = (now - ts).total_seconds()
                if age_secs > 7200:  # ventana 2h
                    continue
            except Exception:
                continue

            _telegram_retry_counts[bet_id_str] = _telegram_retry_counts.get(bet_id_str, 0) + 1
            attempt_n = _telegram_retry_counts[bet_id_str]

            sig = {
                'match_id':            row.get('match_id', ''),
                'match_name':          row.get('match_name', ''),
                'match_url':           row.get('match_url', ''),
                'strategy':            row.get('strategy', ''),
                'strategy_name':       row.get('strategy_name', ''),
                'minute':              row.get('minute', ''),
                'score':               row.get('score', ''),
                'recommendation':      row.get('recommendation', ''),
                'back_odds':           float(row['back_odds']) if row.get('back_odds') else None,
                'min_odds':            float(row['min_odds']) if row.get('min_odds') else None,
                'win_rate_historical': float(row['win_rate_historical']) if row.get('win_rate_historical') else None,
                'roi_historical':      float(row['roi_historical']) if row.get('roi_historical') else None,
                'sample_size':         int(row['sample_size']) if row.get('sample_size') else None,
                'confidence':          row.get('confidence', ''),
                'bet_type':            row.get('bet_type', 'paper'),
            }
            stake = float(row['stake']) if row.get('stake') else 1.0
            sent = _tg.send_signal(sig, stake)
            match_id = row.get('match_id', '?')
            strategy = row.get('strategy', '?')

            try:
                _audit.log_telegram_retry(
                    bet_id=int(bet_id_str) if bet_id_str.isdigit() else 0,
                    match_id=match_id,
                    strategy=strategy,
                    success=sent,
                    attempt_n=attempt_n,
                )
            except Exception:
                pass

            if sent:
                row['telegram_sent'] = '1'
                updated = True
                _log.info(f"[TG-RETRY] OK bet={bet_id_str} attempt={attempt_n} ({row.get('match_name')})")
            else:
                _log.warning(f"[TG-RETRY] FAIL bet={bet_id_str} attempt={attempt_n} — will retry next cycle")

        if updated:
            tmp_path = _PLACED_BETS_CSV.with_suffix('.csv.tmp')
            with open(tmp_path, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=_PLACED_BETS_HEADERS, extrasaction='ignore', restval='')
                w.writeheader()
                w.writerows(rows)
            import shutil
            shutil.move(str(tmp_path), str(_PLACED_BETS_CSV))
    except Exception as e:
        _log.debug(f"_retry_telegram_notifications failed: {e}")


def _live_market_key(sig: dict) -> str:
    """Derive a dedup key from a live signal: match_id + market type (strips odds).
    Mirrors cartera.ts betMarketKey / getBetType logic.
    """
    match_id = sig.get("match_id", "")
    rec = sig.get("recommendation", "").upper()
    # Correct Score markets: "BACK CS 2-1 @ ..." → cs_2_1
    if " CS " in rec:
        cs_match = re.search(r"CS\s+(\d+)[_-](\d+)", rec)
        if cs_match:
            return f"{match_id}::cs_{cs_match.group(1)}_{cs_match.group(2)}"
    if "OVER" in rec:
        parts = rec.split()
        over_idx = next((i for i, p in enumerate(parts) if p == "OVER"), -1)
        if over_idx >= 0 and over_idx + 1 < len(parts):
            return f"{match_id}::over_{parts[over_idx + 1]}"
    if "UNDER" in rec:
        parts = rec.split()
        under_idx = next((i for i, p in enumerate(parts) if p == "UNDER"), -1)
        if under_idx >= 0 and under_idx + 1 < len(parts):
            return f"{match_id}::under_{parts[under_idx + 1]}"
    if "HOME" in rec:
        return f"{match_id}::home"
    if "AWAY" in rec:
        return f"{match_id}::away"
    if "DRAW" in rec:
        return f"{match_id}::draw"
    return f"{match_id}::{rec}"


def _apply_realistic_adjustments(signals: list, adj: dict, risk_filter: str) -> tuple:
    """Apply ALL realistic adjustments to live signals, mirroring applyRealisticAdjustments in cartera.ts.

    Returns (filtered_signals, skip_reasons) where skip_reasons is a dict mapping
    id(sig) → skip_reason string for audit logging.

    Filters applied (same order as frontend):
      0. Global minute range (global_minute_min/max)
      1. Drift min minute (adjDriftMinMinute)
      2. Odds filters with slippage (min_odds, max_odds, slippage_pct)
      3. Risk filter
      4. Stability global floor (stability)
      5. Conflict filter (MomXG blocked when xGUnderperf on same match)
      6. Anti-contrarias (first match-odds bet type per match wins)
      7. Dedup (same match + same market, keep first)
    """
    adj_enabled = adj.get("enabled", True)

    def _num(val, default, cast):
        if val is None:
            return default
        try:
            return cast(val)
        except Exception:
            return default

    min_odds_cfg     = _num(adj.get("min_odds", 0),   0.0, float)   if adj_enabled else 0.0
    max_odds_cfg     = _num(adj.get("max_odds", 999), 999.0, float) if adj_enabled else 999.0
    slippage_pct     = _num(adj.get("slippage_pct", 0), 0.0, float) if adj_enabled else 0.0
    drift_min_min    = _num(adj.get("drift_min_minute", 0), 0, int) if adj_enabled else 0
    dedup_enabled    = bool(adj.get("dedup", False))                if adj_enabled else False
    conflict_filter  = bool(adj.get("conflict_filter", False))      if adj_enabled else False
    allow_contrarias = bool(adj.get("allow_contrarias", True))      if adj_enabled else True
    stability_cfg    = _num(adj.get("stability", 1), 1, int)        if adj_enabled else 1
    global_min       = adj.get("global_minute_min")                 if adj_enabled else None
    global_max       = adj.get("global_minute_max")                 if adj_enabled else None

    skip_reasons: dict = {}  # id(sig) → reason string

    # Pass 1: per-signal filters (minute, odds, risk)
    pass1: list = []
    for sig in signals:
        back_odds  = sig.get("back_odds")
        minute     = sig.get("minute") or 0
        strategy   = sig.get("strategy", "")
        risk_level = (sig.get("risk_info") or {}).get("risk_level", "none")
        sid        = id(sig)

        if global_min is not None and minute < global_min:
            skip_reasons[sid] = f"global_min_minute({minute}<{global_min})"
            continue
        if global_max is not None and minute >= global_max:
            skip_reasons[sid] = f"global_max_minute({minute}>={global_max})"
            continue

        if drift_min_min > 0 and strategy.startswith("odds_drift"):
            if minute < drift_min_min:
                skip_reasons[sid] = f"drift_too_early(min{minute}<{drift_min_min})"
                continue

        if back_odds is not None:
            effective_odds = back_odds * (1 - slippage_pct / 100) if slippage_pct > 0 else back_odds
            if min_odds_cfg > 0 and effective_odds < min_odds_cfg:
                skip_reasons[sid] = f"odds_low({effective_odds:.2f}<{min_odds_cfg})"
                continue
            # Per-signal min_odds: each strategy has a calculated break-even floor
            per_signal_min = sig.get("min_odds")
            if per_signal_min is not None and effective_odds < per_signal_min:
                skip_reasons[sid] = f"odds_below_signal_min({effective_odds:.2f}<{per_signal_min:.2f})"
                continue
            if max_odds_cfg < 999 and back_odds > max_odds_cfg:
                skip_reasons[sid] = f"odds_high({back_odds:.2f}>{max_odds_cfg})"
                continue

        if risk_filter == "no_risk" and risk_level not in ("none", ""):
            skip_reasons[sid] = f"risk_filter_no_risk(level={risk_level})"
            continue
        if risk_filter == "medium" and risk_level != "medium":
            skip_reasons[sid] = f"risk_filter_medium(level={risk_level})"
            continue
        if risk_filter == "high" and risk_level != "high":
            skip_reasons[sid] = f"risk_filter_high(level={risk_level})"
            continue
        if risk_filter == "with_risk" and risk_level not in ("medium", "high"):
            skip_reasons[sid] = f"risk_filter_with_risk(level={risk_level})"
            continue

        pass1.append(sig)

    # Pass 2: stability global floor (1 capture ≈ 0.5 min)
    if stability_cfg > 1:
        stable = []
        for sig in pass1:
            if sig.get("signal_age_minutes", 0) < stability_cfg * 0.5:
                skip_reasons[id(sig)] = f"stability({sig.get('signal_age_minutes', 0):.1f}min<{stability_cfg * 0.5:.1f}min)"
            else:
                stable.append(sig)
        pass1 = stable

    # Pass 3: conflict filter (MomXG blocked when xGUnderperf present on same match)
    if conflict_filter:
        xg_match_ids = {s["match_id"] for s in pass1 if s.get("strategy", "").startswith("xg_underperformance")}
        filtered3 = []
        for sig in pass1:
            if sig.get("strategy", "").startswith("momentum_xg") and sig.get("match_id") in xg_match_ids:
                skip_reasons[id(sig)] = "conflict_filter(mom_xg+xg_underperf)"
            else:
                filtered3.append(sig)
        pass1 = filtered3

    # Pass 4: anti-contrarias (first match-odds bet type per match wins)
    if not allow_contrarias:
        seen_match_odds: dict = {}  # match_id → first bet type seen
        filtered4 = []
        for sig in pass1:
            strat = sig.get("strategy", "")
            is_match_odds = (strat.startswith("back_draw_00") or strat.startswith("odds_drift")
                             or strat.startswith("momentum_xg"))
            if not is_match_odds:
                filtered4.append(sig)
                continue
            rec = sig.get("recommendation", "").upper()
            bet_type = "home" if "HOME" in rec else ("away" if "AWAY" in rec else "draw")
            mid = sig.get("match_id", "")
            if mid not in seen_match_odds:
                seen_match_odds[mid] = bet_type
                filtered4.append(sig)
            elif seen_match_odds[mid] == bet_type:
                filtered4.append(sig)
            else:
                skip_reasons[id(sig)] = f"contraria({bet_type}!={seen_match_odds[mid]})"
        pass1 = filtered4

    # Pass 5: dedup (same match + same market, keep first).
    # Always applied (market-group deduplication is mandatory, not opt-in).
    # The legacy `dedup_enabled` flag is kept for backwards compatibility but
    # no longer gates this pass.
    seen_markets: set = set()
    filtered5 = []
    for sig in pass1:
        key = _live_market_key(sig)
        if key not in seen_markets:
            seen_markets.add(key)
            filtered5.append(sig)
        else:
            skip_reasons[id(sig)] = f"dedup({key})"
    pass1 = filtered5

    return pass1, skip_reasons


def run_paper_auto_place() -> dict:
    """Detecta señales live y auto-coloca bets paper maduras.
    Llamado por el background scheduler cada 60s.
    Usa PAPER_REACTION_DELAY_MINS: solo coloca señales con age >= min_dur min.
    """
    # Reintentar notificaciones Telegram pendientes de ciclos anteriores
    _retry_telegram_notifications()

    try:
        cfg = load_config()
        s   = cfg.get("strategies", {})
        md      = cfg.get("min_duration", {})
        md_live = cfg.get("min_duration_live", {})
        adj = cfg.get("adjustments", {})
        risk_filter = cfg.get("risk_filter", "all")
        bankroll_mode = cfg.get("bankroll_mode", "fixed")
        if bankroll_mode == "pct":
            bankroll   = float(cfg.get("initial_bankroll", 100.0))
            stake_pct  = float(cfg.get("stake_pct", 1.0))
            flat_stake = round(bankroll * stake_pct / 100, 2)
        else:
            flat_stake = float(cfg.get("flat_stake", 10.0))

        # Build min_duration with live overrides
        _md = dict(md)
        for k, v in md_live.items():
            _md[k] = v

        versions = {
            "_strategy_configs": s,
            "_min_duration": _md,
        }

        # ── Audit: contar partidos live para log de ciclo ──
        try:
            _all_games = csv_reader.load_games()
            _n_live = sum(1 for g in _all_games if g.get("status") == "live")
        except Exception:
            _n_live = 0
        try:
            _audit.log_cycle_start(_n_live, source="auto_poller")
        except Exception as e:
            _log.debug(f"Audit log_cycle_start failed: {e}")

        result = csv_reader.detect_betting_signals(versions=versions)

        # ── Audit: loguear radar (condiciones parciales) ──
        try:
            _watchlist = csv_reader.detect_watchlist(versions=versions)
            for _item in _watchlist:
                try:
                    _audit.log_radar_item(_item)
                except Exception as e:
                    _log.debug(f"Audit log_radar_item failed: {e}")
        except Exception:
            _watchlist = []

        raw_signals = result.get("signals", [])
        current_signal_keys = {f"{s.get('match_id')}_{s.get('strategy')}" for s in raw_signals}

        # ── Audit: ciclo de vida de señales — SIGNAL_NEW, SIGNAL_ACTIVE, SIGNAL_EXPIRED ──
        for sig in raw_signals:
            sig_key = f"{sig.get('match_id')}_{sig.get('strategy')}"
            age = sig.get("signal_age_minutes") or 0
            try:
                if sig_key not in _active_signal_tracker:
                    # Primera vez que vemos esta señal en esta sesión
                    _active_signal_tracker[sig_key] = {
                        "first_seen_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "cycles": 1,
                        "sig_snapshot": sig,
                    }
                    _audit.log_signal_new(sig)
                else:
                    _active_signal_tracker[sig_key]["cycles"] += 1
                    _active_signal_tracker[sig_key]["sig_snapshot"] = sig
                    _audit.log_signal_active(sig)
            except Exception as e:
                _log.debug(f"Audit signal lifecycle failed: {e}")

        # ── Detectar señales que desaparecieron sin haber sido colocadas (SIGNAL_EXPIRED) ──
        expired_keys = set(_active_signal_tracker.keys()) - current_signal_keys - _auto_placed_keys
        for exp_key in expired_keys:
            try:
                snap = _active_signal_tracker[exp_key].get("sig_snapshot", {})
                _audit.log_signal_expired(snap)
            except Exception as e:
                _log.debug(f"Audit signal_expired failed: {e}")
            del _active_signal_tracker[exp_key]

        # ── Capture request: señales nuevas (age < 1 min) → trigger screenshot al scraper ──
        for sig in raw_signals:
            try:
                cap_key = f"{sig.get('match_id')}_{sig.get('strategy')}"
                if cap_key not in _capture_requested_keys and sig.get("signal_age_minutes", 99) < 1:
                    import json as _json
                    req = {
                        "match_id": sig.get("match_id"),
                        "strategy": sig.get("strategy"),
                        "minute": sig.get("minute"),
                        "score": sig.get("score"),
                        "odds": sig.get("back_odds"),
                    }
                    req_path = _DATA_DIR / f"capture_request_{sig.get('match_id')}_{sig.get('strategy')}.json"
                    req_path.write_text(_json.dumps(req), encoding="utf-8")
                    _capture_requested_keys.add(cap_key)
                    _log.info(f"[EVIDENCIA] Capture request escrito: {req_path.name}")
            except Exception as e:
                _log.debug(f"Capture request write failed: {e}")

        # ── Aplicar TODOS los filtros realistas (mirrors frontend applyRealisticAdjustments) ──
        filtered_signals, skip_reasons = _apply_realistic_adjustments(raw_signals, adj, risk_filter)

        # ── Audit: loguear señales descartadas por filtros reales ──
        for sig in raw_signals:
            reason = skip_reasons.get(id(sig))
            if reason:
                try:
                    _audit.log_signal_filtered(sig, reason)
                except Exception as e:
                    _log.debug(f"Audit log_signal_filtered failed: {e}")

        placed = 0
        checked = 0
        _n_filtered_audit = len(raw_signals) - len(filtered_signals)

        for sig in filtered_signals:
            checked += 1
            sig_age     = sig.get("signal_age_minutes", 0)
            sig_min_dur = sig.get("min_duration_caps", 1)
            needed = sig_min_dur + PAPER_REACTION_DELAY_MINS
            if sig.get("odds_favorable", True) and sig_age >= needed:
                _auto_place_signal(sig, flat_stake)
                placed += 1
            else:
                # Señal activa pero no madura aún (espera min_duration) o cuota desfavorable
                if not sig.get("odds_favorable", True):
                    try:
                        _audit.log_signal_filtered(sig, "odds_not_favorable")
                    except Exception as e:
                        _log.debug(f"Audit log_signal_filtered failed: {e}")
                else:
                    try:
                        _audit.log_signal_maturing(sig, age=sig_age, needed=needed)
                    except Exception as e:
                        _log.debug(f"Audit log_signal_maturing failed: {e}")
                _n_filtered_audit += 1

        # ── Audit: fin de ciclo ──
        try:
            _audit.log_cycle_end(
                n_signals=result.get("total_signals", 0),
                n_radar=len(_watchlist),
                n_placed=placed,
                n_filtered=_n_filtered_audit,
            )
        except Exception as e:
            _log.debug(f"Audit log_cycle_end failed: {e}")

        return {"placed": placed, "signals_checked": checked}

    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


router = APIRouter()


# ==================== QUALITY ENDPOINTS ====================

@router.get("/quality/overview")
async def get_quality_overview() -> Dict[str, Any]:
    """Get overall quality metrics for all finished matches."""
    return csv_reader.analyze_quality_distribution()


@router.get("/quality/gaps")
async def get_gap_analysis() -> Dict[str, Any]:
    """Get gap analysis across all finished matches."""
    return csv_reader.analyze_gaps_distribution()


@router.get("/quality/stats-coverage")
async def get_stats_coverage() -> Dict[str, Any]:
    """Get percentage coverage for each stats field across all matches."""
    return csv_reader.analyze_stats_coverage()


@router.get("/quality/odds-coverage")
async def get_odds_coverage() -> Dict[str, Any]:
    """Get odds scraping coverage distribution across all finished matches."""
    return csv_reader.analyze_odds_coverage()


@router.get("/quality/odds-inversion")
async def get_odds_inversion() -> Dict[str, Any]:
    """Detect matches with suspected home/away odds column inversion.

    An inversion is flagged when the WINNING team's back odds are very high (>15)
    while the LOSING team's back odds are very low (<3.0), which is physically impossible
    in a correct market reading and indicates a CSS selector desync during market suspension.
    """
    import glob as _glob

    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "data"
    csv_files = sorted(data_dir.glob("partido_*.csv"))

    total_matches = len(csv_files)
    cases = []

    for fp in csv_files:
        try:
            with open(fp, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = next(reader)
                h = {hdr: i for i, hdr in enumerate(headers)}
                rows = list(reader)
        except Exception:
            continue

        anomalous = []
        en_juego_count = 0

        for row in rows:
            if len(row) < 8 or (row[4] if len(row) > 4 else "") != "en_juego":
                continue
            en_juego_count += 1

            def _g(col: str, _row=row, _h=h) -> float | None:
                i = _h.get(col)
                if i is None or i >= len(_row):
                    return None
                try:
                    return float(_row[i])
                except (ValueError, TypeError):
                    return None

            gl = _g("goles_local")
            gv = _g("goles_visitante")
            bh = _g("back_home")
            ba = _g("back_away")

            if gl is None or gv is None or bh is None or ba is None:
                continue

            # Away leading: back_away/back_home ratio > 5 means the winning team's odds
            # are anomalously high relative to the losing team — regardless of absolute values.
            # This catches both full column swaps (bh≈1.7, ba≈28) and partial desyncs
            # (bh≈4.8, ba≈40). Big-favorite-trailing cases are not caught because their
            # ratio is inverted (ba << bh when away is the big favorite losing).
            if gv > gl and bh > 0 and ba / bh > 5:
                anomalous.append({
                    "minute": row[5] if len(row) > 5 else "",
                    "score": f"{int(gl)}-{int(gv)}",
                    "back_home": bh,
                    "back_away": ba,
                    "type": "away_leading",
                })
            # Home leading: same logic mirrored
            elif gl > gv and ba > 0 and bh / ba > 5:
                anomalous.append({
                    "minute": row[5] if len(row) > 5 else "",
                    "score": f"{int(gl)}-{int(gv)}",
                    "back_home": bh,
                    "back_away": ba,
                    "type": "home_leading",
                })

        if not anomalous:
            continue

        n = len(anomalous)
        severity = "high" if n >= 5 else "medium" if n >= 3 else "low"
        from urllib.parse import unquote
        stem = fp.stem  # partido_team1-team2-apuestas-XXXXX
        parts = stem.replace("partido_", "").split("-apuestas-")
        match_name = unquote(parts[0]).replace("-", " ").title() if parts else stem

        cases.append({
            "match_id": stem,
            "match_name": match_name,
            "anomalous_rows": n,
            "total_en_juego": en_juego_count,
            "pct_affected": round(n / en_juego_count * 100, 1) if en_juego_count > 0 else 0,
            "severity": severity,
            "examples": anomalous[:3],
        })

    cases.sort(key=lambda x: (-x["anomalous_rows"], x["match_id"]))

    high = sum(1 for c in cases if c["severity"] == "high")
    medium = sum(1 for c in cases if c["severity"] == "medium")
    low = sum(1 for c in cases if c["severity"] == "low")

    return {
        "total_matches": total_matches,
        "affected_matches": len(cases),
        "affected_pct": round(len(cases) / total_matches * 100, 1) if total_matches > 0 else 0,
        "high_severity": high,
        "medium_severity": medium,
        "low_severity": low,
        "cases": cases[:50],
    }


# ==================== STRATEGY CARTERA ENDPOINTS ====================

@router.get("/strategies/cartera")
async def get_strategy_cartera(
    cashout_minute: Optional[int] = Query(None, ge=-1, le=90),
    cashout_lay_pct: Optional[float] = Query(None, ge=5, le=100),
    adaptive_early_pct: Optional[float] = Query(None, ge=1, le=100),
    adaptive_late_pct: Optional[float] = Query(None, ge=1, le=100),
    adaptive_split_min: Optional[int] = Query(70, ge=30, le=90),
    adverse_goal_stop: Optional[bool] = Query(False),
    trailing_stop_pct: Optional[float] = Query(None, ge=1, le=100),
) -> Dict[str, Any]:
    """Combined portfolio view of all strategies.

    cashout_minute: if provided, simulate cash-out for losing bets at this minute.
    cashout_lay_pct: if provided, simulate cash-out when lay rises X% above entry price.
    adaptive_early_pct / adaptive_late_pct: adaptive threshold — loose before adaptive_split_min, tight after.
    adverse_goal_stop: cash out on first adverse goal (back_draw_00, odds_drift, momentum_xg only).
    trailing_stop_pct: trailing stop — fires when lay rises X% above the minimum lay seen since entry.
    Multiple modes can be active simultaneously; the first to trigger wins.
    """
    data = csv_reader.analyze_cartera()
    new_modes = (
        cashout_lay_pct is not None
        or (adaptive_early_pct is not None and adaptive_late_pct is not None)
        or adverse_goal_stop
        or trailing_stop_pct is not None
    )
    if new_modes:
        data = csv_reader.simulate_cashout_cartera(
            data,
            cashout_lay_pct=cashout_lay_pct,
            adaptive_early_pct=adaptive_early_pct,
            adaptive_late_pct=adaptive_late_pct,
            adaptive_split_min=adaptive_split_min or 70,
            adverse_goal_stop=adverse_goal_stop or False,
            trailing_stop_pct=trailing_stop_pct,
        )
    elif cashout_minute is not None:
        data = csv_reader.simulate_cashout_cartera(data, cashout_minute)
    return data


@router.get("/strategies/cartera/optimize")
async def optimize_strategy_cartera(
    top_n: Optional[int] = Query(10, ge=1, le=20),
) -> Dict[str, Any]:
    """Grid search over all CO modes and parameter combinations.
    Reads each match CSV only once for efficiency (~80 configs tested).
    Returns top_n configs ranked by P/L net, plus rescued/penalized metrics.
    """
    data = csv_reader.analyze_cartera()
    return csv_reader.optimize_cashout_cartera(data, top_n=top_n or 10)



# ==================== BETTING SIGNALS ENDPOINT ====================

@router.get("/signals/betting-opportunities")
async def get_betting_signals(
    draw: Optional[str] = None,
    xg: Optional[str] = None,
    drift: Optional[str] = None,
    clustering: Optional[str] = None,
    pressure: Optional[str] = None,
    momentum: Optional[str] = None,
    draw_min_dur: Optional[int] = None,
    xg_min_dur: Optional[int] = None,
    drift_min_dur: Optional[int] = None,
    clustering_min_dur: Optional[int] = None,
    pressure_min_dur: Optional[int] = None,
) -> Dict[str, Any]:
    """Detect live betting opportunities based on portfolio strategies.

    When no parameters are supplied, reads strategies and min_duration from
    cartera_config.json. Query params act as on/off overrides.
    Applies adjustments (min_odds, max_odds, drift_min_minute) and risk_filter.
    """
    cfg = load_config()
    s   = cfg.get("strategies", {})
    md      = cfg.get("min_duration", {})
    md_live = cfg.get("min_duration_live", {})
    adj = cfg.get("adjustments", {})
    risk_filter = cfg.get("risk_filter", "all")

    # Apply query param overrides (on/off toggles for legacy compat)
    _QUERY_MAP = {
        "back_draw_00": draw, "xg_underperformance": xg,
        "odds_drift": drift, "goal_clustering": clustering,
        "pressure_cooker": pressure, "momentum_xg": momentum,
    }
    _s = dict(s)
    for _reg_key, _qp in _QUERY_MAP.items():
        if _qp is not None:
            _s.setdefault(_reg_key, {})
            _s[_reg_key] = {**_s[_reg_key], "enabled": _qp != "off"}

    # Apply min_dur query param overrides
    _md = dict(md)
    for k, v in md_live.items():
        _md[k] = v
    _MIN_DUR_MAP = {
        "back_draw_00": draw_min_dur, "xg_underperformance": xg_min_dur,
        "odds_drift": drift_min_dur, "goal_clustering": clustering_min_dur,
        "pressure_cooker": pressure_min_dur,
    }
    for _reg_key, _qp in _MIN_DUR_MAP.items():
        if _qp is not None:
            _md[_reg_key] = _qp

    versions = {
        "_strategy_configs": _s,
        "_min_duration": _md,
    }

    result = csv_reader.detect_betting_signals(versions=versions)

    # ── Filtros post-detección: aplica TODOS los filtros realistas (mirrors frontend) ──
    filtered, _ = _apply_realistic_adjustments(result.get("signals", []), adj, risk_filter)

    result["signals"] = filtered
    result["total_signals"] = len(filtered)

    # ── Audit log: señales visibles desde la API (solo lectura, NO coloca bets) ──
    # Las apuestas se colocan EXCLUSIVAMENTE por el background auto-poller (run_paper_auto_place)
    # que corre cada 60s. Esto garantiza que el sistema funciona 24/7 sin necesidad de abrir la UI.
    try:
        for sig in filtered:
            _audit.log_signal_active(sig)
    except Exception as e:
        _log.debug(f"Audit log_signal_active failed: {e}")

    return result


@router.get("/signals/watchlist")
async def get_watchlist(
    draw: Optional[str] = None,
    xg: Optional[str] = None,
    drift: Optional[str] = None,
    clustering: Optional[str] = None,
    pressure: Optional[str] = None,
    momentum: Optional[str] = None,
) -> List[Any]:
    """Matches close to triggering a signal but not yet meeting all conditions."""
    cfg = load_config()
    s = cfg.get("strategies", {})

    # Apply query param overrides (on/off toggles)
    _QUERY_MAP = {
        "back_draw_00": draw, "xg_underperformance": xg,
        "odds_drift": drift, "goal_clustering": clustering,
        "pressure_cooker": pressure, "momentum_xg": momentum,
    }
    _s = dict(s)
    for _reg_key, _qp in _QUERY_MAP.items():
        if _qp is not None:
            _s.setdefault(_reg_key, {})
            _s[_reg_key] = {**_s[_reg_key], "enabled": _qp != "off"}

    versions = {"_strategy_configs": _s}
    return csv_reader.detect_watchlist(versions=versions)


@router.post("/cache/clear")
async def clear_cache():
    """Clear analytics cache to force reload of data."""
    csv_reader.clear_analytics_cache()
    return {"status": "ok", "message": "Cache cleared successfully"}


def _save_evidence_snapshot(sig: dict) -> None:
    """Copia el screenshot del minuto exacto de la señal a evidencias/.
    Para señales CS usa screenshot_*_rc.png (capturado desde la página del mercado RC).
    Para el resto usa screenshot_*.png (capturado desde la página principal).
    """
    import shutil

    match_id = sig.get("match_id", "unknown")
    minuto   = sig.get("minute", "??")
    strategy = sig.get("strategy", "unknown")

    # Señales CS: usar screenshot desde la página del mercado Resultado Correcto
    is_cs = strategy.startswith("cs_") or strategy in ("lay_cs11",)
    suffix = "_rc" if is_cs else ""

    def _find_src(min_str):
        p = _DATA_DIR / f"screenshot_{match_id}_{min_str}{suffix}.png"
        return p if p.exists() else None

    src = _find_src(str(minuto))
    if src is None:
        # Fallback: minuto anterior
        try:
            src = _find_src(str(int(minuto) - 1))
        except (ValueError, TypeError):
            src = None

    if src is None:
        _log.warning(f"[EVIDENCIA] Screenshot{suffix} min {minuto} no disponible para {match_id}")
        return

    try:
        _EVIDENCIAS_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{match_id}_min{minuto}_{strategy}_{ts}.png"
        shutil.copy2(str(src), str(_EVIDENCIAS_DIR / filename))
        _log.info(f"[EVIDENCIA] Screenshot guardado: {filename}")
    except Exception as e:
        _log.warning(f"[EVIDENCIA] Error copiando screenshot: {e}")


_BETFAIR_SESSION_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "betfair_session"
_pw_instance = None
_pw_context = None


_PW_DEFAULT_STAKE = 2.0  # Default stake in £ — user reviews and confirms before placing


async def _pw_fill_stake(page) -> None:
    """Fill stake input. Betfair uses <betslip-size-input> custom element (confirmed via DOM inspection)."""
    import asyncio
    await asyncio.sleep(1.0)

    stake_str = str(int(_PW_DEFAULT_STAKE) if _PW_DEFAULT_STAKE == int(_PW_DEFAULT_STAKE) else _PW_DEFAULT_STAKE)

    # Primary: betslip-size-input custom element
    try:
        inp = page.locator("betslip-size-input").get_by_role("textbox").first
        await asyncio.wait_for(inp.wait_for(state="visible"), timeout=4)
        await inp.click()
        await inp.fill(stake_str)
        _log.info(f"Stake {stake_str} filled via betslip-size-input")
        return
    except Exception as e:
        _log.warning(f"betslip-size-input fill failed: {e}")

    # Fallback selectors
    for sel in [
        "betslip-size-input input", "betslip-size-input [role='textbox']",
        ".betslip-bets input", ".betslip input[type='text']",
        "input[class*='stake' i]", "input[class*='Stake']",
    ]:
        try:
            inp = page.locator(sel).first
            if await asyncio.wait_for(inp.is_visible(), timeout=1):
                await inp.click()
                await inp.fill(stake_str)
                _log.info(f"Stake {stake_str} filled via {sel}")
                return
        except Exception:
            continue

    _log.warning("Could not fill stake — dumping visible inputs:")
    try:
        debug = await page.evaluate("""
            () => Array.from(document.querySelectorAll('input, betslip-size-input'))
                       .filter(i => i.getBoundingClientRect().width > 0)
                       .map(i => i.tagName + '|' + i.className + '|' + (i.placeholder||''))
                       .join(' /// ')
        """)
        _log.info(f"Visible inputs: {debug}")
    except Exception:
        pass


async def _pw_navigate_to_market(page, recommendation: str) -> None:
    """Navigate sidebar to Over/Under or Correct Score market when needed."""
    import asyncio
    import re
    rec = recommendation.upper()
    if "OVER" in rec or "UNDER" in rec:
        m = re.search(r'(\d+\.?\d*)', rec)
        if not m:
            return
        goal_total = m.group(1)
        # Betfair ES uses comma as decimal separator (0,5 not 0.5)
        goal_total_es = goal_total.replace(".", ",")
        candidates = [
            goal_total_es, goal_total,  # "0,5" then "0.5"
            f"de {goal_total_es} Goles", f"de {goal_total} Goles",
        ]
        for variant in candidates:
            try:
                lnk = page.locator(f"a:has-text('{variant}')").first
                if await asyncio.wait_for(lnk.is_visible(), timeout=2):
                    await lnk.click()
                    await asyncio.sleep(1.5)
                    _log.info(f"Navigated to market matching: '{variant}'")
                    return
            except Exception:
                continue
        _log.info(f"Over/Under market for {goal_total} not found in sidebar")
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


async def _pw_click_odds(page, recommendation: str, match_name: str) -> None:
    """Click BACK/LAY odds button for the correct selection, then fill stake."""
    import asyncio
    if not recommendation:
        return
    rec = recommendation.upper()
    is_lay = rec.startswith("LAY")
    is_match_odds = any(k in rec for k in ("HOME", "AWAY", "DRAW"))
    is_over = "OVER" in rec
    is_under = "UNDER" in rec

    # Navigate to the correct sub-market if needed
    await _pw_navigate_to_market(page, recommendation)

    # Wait for runner rows to be visible (up to 10s for React to render)
    try:
        await asyncio.wait_for(page.wait_for_selector("tr.runner-line", state="visible"), timeout=10)
    except Exception:
        _log.warning("Runner rows not visible after 10s — page may not have loaded correctly")
        return

    runner_rows = page.locator("tr.runner-line")
    try:
        count = await asyncio.wait_for(runner_rows.count(), timeout=5)
    except Exception:
        _log.warning("Could not count runner rows")
        return
    _log.info(f"Found {count} runner rows for: {recommendation}")

    if is_match_odds:
        parts = match_name.split(" - ", 1)
        home_name = parts[0].strip() if parts else ""
        away_name = parts[1].strip() if len(parts) > 1 else ""

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

        # Positional fallback: home=0, away=1, draw=2
        if target_row is None and count >= 3:
            idx = 0 if "HOME" in rec else (1 if "AWAY" in rec else 2)
            target_row = runner_rows.nth(idx)
            _log.info(f"Using positional fallback row {idx} for: {recommendation}")

        if target_row is None:
            _log.warning(f"No target row found for: {recommendation}")
            return

        btn_sel = "td.bet-buttons.lay-cell ours-price-button button" if is_lay else "td.bet-buttons.back-cell ours-price-button button"
        try:
            btn = target_row.locator(btn_sel).first
            await asyncio.wait_for(btn.wait_for(state="visible"), timeout=4)
            await btn.click()
            _log.info(f"Clicked {'LAY' if is_lay else 'BACK'} for: {recommendation}")
        except Exception as e:
            _log.warning(f"Could not click odds button ({btn_sel}): {e}")
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
                    _log.info(f"Clicked {'LAY' if is_lay else 'BACK'} '{target_text}' for: {recommendation}")
                    clicked = True
                except Exception as e:
                    _log.warning(f"Could not click over/under button: {e}")
                break
        if not clicked:
            _log.warning(f"Runner '{target_text}' not found among {count} rows for: {recommendation}")
            return
    else:
        _log.info(f"Market type not auto-handled for: {recommendation} — user must click manually")
        return

    # Fill stake after clicking odds
    await _pw_fill_stake(page)


async def _pw_open_and_login(url: str, recommendation: str = "", match_name: str = "") -> None:
    """Open URL in real Chrome profile (saved credentials), login if needed, click odds."""
    import asyncio
    global _pw_instance, _pw_context
    try:
        if _pw_context is not None:
            try:
                _ = _pw_context.pages
            except Exception:
                _pw_context = None
        if _pw_context is None:
            from playwright.async_api import async_playwright
            if _pw_instance is None:
                _pw_instance = await async_playwright().start()
            _BETFAIR_SESSION_DIR.mkdir(parents=True, exist_ok=True)
            _pw_context = await asyncio.wait_for(
                _pw_instance.chromium.launch_persistent_context(
                    str(_BETFAIR_SESSION_DIR),
                    headless=False,
                    channel="msedge",
                    args=[
                        "--start-maximized",
                        "--disable-blink-features=AutomationControlled",
                    ],
                    no_viewport=True,
                    ignore_default_args=["--enable-automation"],
                ),
                timeout=30,
            )
            _log.info(f"Playwright launched with dedicated bot profile: {_BETFAIR_SESSION_DIR}")

        page = await _pw_context.new_page()
        await asyncio.wait_for(page.goto(url, wait_until="load"), timeout=25)
        await asyncio.sleep(1.5)

        # Check if login is needed — Betfair uses <input type="submit" id="ssc-lis">
        login_btn = page.locator("input#ssc-lis, input.ssc-cta-primary").first
        needs_login = False
        try:
            needs_login = await asyncio.wait_for(login_btn.is_visible(), timeout=3)
        except Exception:
            pass

        if needs_login:
            # Dedicated bot profile — no auto-fill. Wait up to 60s for user to log in manually.
            # After first login, Betfair session cookies persist for weeks.
            _log.info("Login required — waiting up to 60s for user to log in manually in the bot window")
            try:
                await asyncio.wait_for(login_btn.wait_for(state="hidden"), timeout=60)
                _log.info("Login detected — session will be reused on next runs")
            except Exception:
                _log.warning("Login not detected after 60s — skipping odds click")
                return

            # Navigate to match URL if redirected after login
            if url not in page.url:
                _log.info(f"Navigating back to match: {url}")
                await asyncio.wait_for(page.goto(url, wait_until="load"), timeout=25)
                await asyncio.sleep(1)
        else:
            _log.info("Already logged in via session cookies — proceeding to click odds")

        # Click odds and fill stake
        await _pw_click_odds(page, recommendation, match_name)

    except Exception as e:
        _log.warning(f"Playwright open_bet error: {e}")
        _pw_context = None


@router.post("/open-bet")
async def open_bet(payload: dict):
    """Opens Betfair in real Chrome (with saved credentials) and clicks the odds button via Playwright."""
    import asyncio
    url = payload.get("match_url", "")
    if not url:
        return {"ok": False, "error": "No URL provided"}
    recommendation = payload.get("recommendation", "")
    match_name = payload.get("match_name", "")
    asyncio.create_task(_pw_open_and_login(url, recommendation, match_name))
    return {"ok": True}

