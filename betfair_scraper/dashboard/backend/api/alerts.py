"""
API endpoint para alertas proactivas del sistema de scraping.
Detecta problemas silenciosos antes de que impacten en los datos.
"""

import json
import csv
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

log = logging.getLogger(__name__)

router = APIRouter()

SCRAPER_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = SCRAPER_DIR / "data"
HEARTBEAT_PATH = DATA_DIR / ".heartbeat"
GAMES_CSV = SCRAPER_DIR / "games.csv"
PLACED_BETS_CSV = SCRAPER_DIR / "placed_bets.csv"
LOG_DIR = SCRAPER_DIR / "logs"
ALERTS_LOG = LOG_DIR / "alerts.jsonl"

# Max alerts log size: 5MB, then rotate
ALERTS_LOG_MAX_SIZE = 5 * 1024 * 1024


def _check_heartbeat() -> List[Dict[str, Any]]:
    """Check scraper heartbeat freshness."""
    alerts = []
    if not HEARTBEAT_PATH.exists():
        alerts.append({
            "level": "critical",
            "category": "heartbeat",
            "message": "No se encontró archivo .heartbeat — scraper puede no estar corriendo",
        })
        return alerts

    try:
        with open(HEARTBEAT_PATH) as f:
            hb = json.load(f)
        hb_time = datetime.fromisoformat(hb["timestamp"])
        age = (datetime.now(timezone.utc) - hb_time).total_seconds()

        if age > 300:
            alerts.append({
                "level": "critical",
                "category": "heartbeat",
                "message": f"Heartbeat stale: {age:.0f}s (>5min) — scraper colgado o muerto",
                "detail": f"Último heartbeat: {hb.get('timestamp', '?')}",
            })
        elif age > 180:
            alerts.append({
                "level": "warning",
                "category": "heartbeat",
                "message": f"Heartbeat stale: {age:.0f}s (>3min) — posible problema",
            })

        # Check alive vs active drivers
        alive = hb.get("alive_drivers", 0)
        active = hb.get("active_drivers", 0)
        if active > 0 and alive == 0:
            alerts.append({
                "level": "critical",
                "category": "drivers",
                "message": f"Todos los drivers muertos: 0/{active} alive",
            })
        elif active > 0 and alive < active * 0.5:
            alerts.append({
                "level": "warning",
                "category": "drivers",
                "message": f"Drivers degradados: {alive}/{active} alive ({alive/active*100:.0f}%)",
            })
    except Exception as e:
        alerts.append({
            "level": "warning",
            "category": "heartbeat",
            "message": f"Error leyendo heartbeat: {e}",
        })
    return alerts


def _check_stats_api() -> List[Dict[str, Any]]:
    """Check if Stats API is responding by testing with a live match."""
    alerts = []
    try:
        import sys
        sys.path.insert(0, str(SCRAPER_DIR))
        from stats_api import _api_get

        if not GAMES_CSV.exists():
            return alerts

        with open(GAMES_CSV, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        # Only test when there are live matches (data CSVs modified in last 5 min)
        import time
        has_live = any(
            f.stat().st_mtime > time.time() - 300
            for f in DATA_DIR.glob("partido_*.csv")
        )
        if not has_live:
            return alerts  # No live matches — skip check

        live_rows = rows  # All games are candidates when scraper is active

        import requests
        for row in live_rows[:2]:  # Test up to 2 live matches
            url = row.get("url", "")
            m = re.search(r'(\d{7,})', url)
            if not m:
                continue
            betfair_id = m.group(1)
            vp_url = f"https://videoplayer.betfair.es/GetPlayer.do?eID={betfair_id}&contentType=viz&contentView=mstats"
            r = requests.get(vp_url, timeout=5)
            opta_match = re.search(
                r'(?:providerEventId|performMCCFixtureUUID|streamUUID)\s*[=:]\s*["\']?([a-z0-9]{20,30})["\']?',
                r.text, re.IGNORECASE
            )
            if opta_match:
                opta_id = opta_match.group(1)
                result = _api_get("matchstats", opta_id, "&detailed=yes")
                if result is None:
                    alerts.append({
                        "level": "critical",
                        "category": "stats_api",
                        "message": f"Stats API no responde para partido live (Opta {opta_id})",
                    })
                return alerts  # Got a valid test, done
            # Opta ID not found for this live match — try next one

        # All live matches failed to resolve Opta ID — normal for leagues
        # without Stats Perform coverage. Not an alert-worthy event.
        log.debug(f"No Opta ID for {len(live_rows)} live match(es) — no Stats Perform coverage")
    except Exception as e:
        alerts.append({
            "level": "warning",
            "category": "stats_api",
            "message": f"Error verificando Stats API: {e}",
        })
    return alerts


def _check_pending_bets() -> List[Dict[str, Any]]:
    """Check for bets stuck in pending state too long."""
    alerts = []
    if not PLACED_BETS_CSV.exists():
        return alerts

    try:
        with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        # Check active match IDs
        active_ids = set()
        if GAMES_CSV.exists():
            with open(GAMES_CSV, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    url = row.get("url", "")
                    m = re.search(r'([^/]+apuestas-\d+)', url)
                    if m:
                        active_ids.add(m.group(1))

        stuck_bets = []
        for row in rows:
            if row.get("status") == "pending":
                match_id = row.get("match_id", "")
                # If match is no longer active and bet is still pending
                if match_id and match_id not in active_ids:
                    ts = row.get("timestamp", "")
                    stuck_bets.append(f"Bet #{row.get('id', '?')} ({row.get('strategy_name', '?')}) - {match_id[:30]}")

        if stuck_bets:
            alerts.append({
                "level": "warning",
                "category": "bets",
                "message": f"{len(stuck_bets)} apuestas pendientes en partidos finalizados",
                "detail": "; ".join(stuck_bets[:5]) + ("..." if len(stuck_bets) > 5 else ""),
            })
    except Exception as e:
        log.warning(f"Error checking pending bets: {e}")
    return alerts


def _check_data_quality() -> List[Dict[str, Any]]:
    """Check recent CSV data quality (gaps, early endings)."""
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    try:
        # Check last 5 active matches for data quality
        csv_files = sorted(DATA_DIR.glob("partido_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        for csv_path in csv_files:
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    rows = list(csv.DictReader(f))
                if len(rows) < 2:
                    continue

                # Check for large time gaps
                prev_ts = None
                max_gap = 0
                for row in rows:
                    ts_str = row.get("timestamp", "")
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            if prev_ts:
                                gap = (ts - prev_ts).total_seconds()
                                max_gap = max(max_gap, gap)
                            prev_ts = ts
                        except Exception:
                            pass

                if max_gap > 600:  # >10 min gap
                    match_id = csv_path.stem
                    alerts.append({
                        "level": "warning",
                        "category": "data_quality",
                        "message": f"Gap de {max_gap/60:.0f}min en {match_id}",
                    })
            except Exception:
                pass
    except Exception as e:
        log.warning(f"Error checking data quality: {e}")
    return alerts


def _check_scraper_log() -> List[Dict[str, Any]]:
    """Check recent scraper log for recurring errors."""
    alerts = []
    if not LOG_DIR.exists():
        return alerts

    try:
        import time
        log_files = sorted(LOG_DIR.glob("scraper_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not log_files:
            return alerts

        latest_log = log_files[0]
        # Only check if log was modified in last 2 hours (skip stale logs)
        if time.time() - latest_log.stat().st_mtime > 7200:
            return alerts

        # Read last 200 lines
        with open(latest_log, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()[-200:]

        error_count = sum(1 for l in lines if "ERROR" in l)
        crash_count = sum(1 for l in lines if "muerto" in l.lower() or "crash" in l.lower() or "💀" in l)

        if crash_count > 2:
            alerts.append({
                "level": "warning",
                "category": "drivers",
                "message": f"{crash_count} drivers muertos/crashes en log reciente",
            })

        if error_count > 20:
            alerts.append({
                "level": "warning",
                "category": "logs",
                "message": f"Alto volumen de errores: {error_count} en últimas 200 líneas del log",
            })
    except Exception as e:
        log.warning(f"Error checking scraper log: {e}")
    return alerts


def _check_frozen_rc_odds() -> List[Dict[str, Any]]:
    """Detect matches where correct score odds are frozen (all live rows have same value)."""
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    import time
    try:
        cutoff = time.time() - 7200  # active in last 2h
        csv_files = [f for f in DATA_DIR.glob("partido_*.csv") if f.stat().st_mtime > cutoff]

        frozen_matches = []
        for csv_path in csv_files:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))

                live_rows = [r for r in rows if r.get("estado_partido") == "en_juego"]
                if len(live_rows) < 5:
                    continue

                # Frozen: 5+ live rows, back_rc_1_0 non-empty but all identical
                rc_vals = [r.get("back_rc_1_0", "") for r in live_rows]
                non_empty = [v for v in rc_vals if v]
                if len(non_empty) >= 5 and len(set(non_empty)) == 1:
                    frozen_matches.append(csv_path.stem.replace("partido_", "")[:50])
            except Exception:
                pass

        if frozen_matches:
            alerts.append({
                "level": "warning",
                "category": "frozen_rc",
                "message": f"Cuotas RC congeladas en {len(frozen_matches)} partido(s) — scraper no accede al mercado RC",
                "detail": "; ".join(frozen_matches),
            })
    except Exception as e:
        log.warning(f"Error checking frozen RC: {e}")
    return alerts


def _check_onedrive_conflicts() -> List[Dict[str, Any]]:
    """Detect OneDrive conflict copies in data/ (partido_*-HOSTNAME-*.csv)."""
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    try:
        conflict_files = [
            f for f in DATA_DIR.glob("partido_*.csv")
            if re.search(r"-[A-Z]+-[A-Z0-9]+(-\d+)?\.csv$", f.name)
        ]
        if conflict_files:
            alerts.append({
                "level": "warning",
                "category": "onedrive",
                "message": f"{len(conflict_files)} archivos de conflicto OneDrive en data/ — datos duplicados en BT",
                "detail": "; ".join(f.name[:50] for f in conflict_files[:5]) + ("..." if len(conflict_files) > 5 else ""),
            })
    except Exception as e:
        log.warning(f"Error checking OneDrive conflicts: {e}")
    return alerts


def _check_missing_stats() -> List[Dict[str, Any]]:
    """Detect active matches where xG/stats are consistently empty in live rows."""
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    import time
    try:
        cutoff = time.time() - 600  # modified in last 10 min
        csv_files = [f for f in DATA_DIR.glob("partido_*.csv") if f.stat().st_mtime > cutoff]

        missing_stats_matches = []
        for csv_path in csv_files:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))

                live_rows = [r for r in rows if r.get("estado_partido") == "en_juego"]
                if len(live_rows) < 3:
                    continue

                empty_xg = sum(1 for r in live_rows if not r.get("xg_local", "").strip())
                if empty_xg / len(live_rows) > 0.8:
                    missing_stats_matches.append(csv_path.stem.replace("partido_", "")[:50])
            except Exception:
                pass

        if missing_stats_matches:
            alerts.append({
                "level": "warning",
                "category": "stats_missing",
                "message": f"xG/estadísticas ausentes en {len(missing_stats_matches)} partido(s) activo(s)",
                "detail": "; ".join(missing_stats_matches),
            })
    except Exception as e:
        log.warning(f"Error checking missing stats: {e}")
    return alerts


def _check_post_finalizado_rows() -> List[Dict[str, Any]]:
    """Detect CSVs where non-finalizado rows appear after a finalizado row."""
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    import time
    try:
        cutoff = time.time() - 7200
        csv_files = [f for f in DATA_DIR.glob("partido_*.csv") if f.stat().st_mtime > cutoff]

        broken_matches = []
        for csv_path in csv_files:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))

                first_final_idx = next(
                    (i for i, r in enumerate(rows) if r.get("estado_partido") == "finalizado"), None
                )
                if first_final_idx is None:
                    continue

                post_bad = [
                    r for r in rows[first_final_idx + 1:]
                    if r.get("estado_partido") not in ("finalizado", "")
                ]
                if post_bad:
                    broken_matches.append(
                        f"{csv_path.stem.replace('partido_', '')[:40]} ({len(post_bad)} filas post-final)"
                    )
            except Exception:
                pass

        if broken_matches:
            alerts.append({
                "level": "warning",
                "category": "state_corruption",
                "message": f"{len(broken_matches)} partido(s) con filas activas tras estado finalizado",
                "detail": "; ".join(broken_matches),
            })
    except Exception as e:
        log.warning(f"Error checking post-finalizado rows: {e}")
    return alerts


def _check_frozen_odds_general() -> List[Dict[str, Any]]:
    """Detect any main market / OU odds column frozen for 10+ consecutive live rows."""
    WATCHED_COLS = [
        "back_home", "lay_home", "back_draw", "lay_draw",
        "back_over25", "lay_over25", "back_over15", "back_over35",
    ]
    FREEZE_THRESHOLD = 10

    alerts = []
    if not DATA_DIR.exists():
        return alerts

    import time
    try:
        cutoff = time.time() - 7200
        csv_files = [f for f in DATA_DIR.glob("partido_*.csv") if f.stat().st_mtime > cutoff]

        frozen_details = []
        for csv_path in csv_files:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))

                # Skip finished/halftime — collapsed or suspended odds are not frozen
                last_state = rows[-1].get("estado_partido", "") if rows else ""
                if last_state in ("finalizado", "descanso"):
                    continue

                live_rows = [r for r in rows if r.get("estado_partido") == "en_juego"]
                if len(live_rows) < FREEZE_THRESHOLD:
                    continue

                recent = live_rows[-FREEZE_THRESHOLD:]
                frozen_cols = []
                for col in WATCHED_COLS:
                    vals = [r.get(col, "") for r in recent]
                    non_empty = [v for v in vals if v]
                    if len(non_empty) == FREEZE_THRESHOLD and len(set(non_empty)) == 1:
                        frozen_cols.append(col)

                if frozen_cols:
                    match_name = csv_path.stem.replace("partido_", "")[:40]
                    frozen_details.append(f"{match_name} [{', '.join(frozen_cols)}]")
            except Exception:
                pass

        if frozen_details:
            alerts.append({
                "level": "warning",
                "category": "frozen_odds",
                "message": f"Cuotas congeladas ({FREEZE_THRESHOLD}+ filas iguales) en {len(frozen_details)} partido(s)",
                "detail": "; ".join(frozen_details),
            })
    except Exception as e:
        log.warning(f"Error checking frozen general odds: {e}")
    return alerts


def _check_duplicate_minutes() -> List[Dict[str, Any]]:
    """Detect matches where the same minute appears 10+ times (scraper stuck at same minute)."""
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    import time
    from collections import Counter
    try:
        cutoff = time.time() - 3600
        csv_files = [f for f in DATA_DIR.glob("partido_*.csv") if f.stat().st_mtime > cutoff]

        stuck_matches = []
        for csv_path in csv_files:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))

                live_rows = [r for r in rows if r.get("estado_partido") == "en_juego"]
                if not live_rows:
                    continue

                counts = Counter(r.get("minuto", "") for r in live_rows if r.get("minuto", "").strip())
                worst = counts.most_common(1)
                if worst and worst[0][1] >= 10:
                    match_name = csv_path.stem.replace("partido_", "")[:40]
                    stuck_matches.append(f"{match_name} (min {worst[0][0]}: {worst[0][1]}x)")
            except Exception:
                pass

        if stuck_matches:
            alerts.append({
                "level": "warning",
                "category": "stuck_minute",
                "message": f"{len(stuck_matches)} partido(s) con scraper atascado en mismo minuto",
                "detail": "; ".join(stuck_matches),
            })
    except Exception as e:
        log.warning(f"Error checking duplicate minutes: {e}")
    return alerts


def _check_long_running_match() -> List[Dict[str, Any]]:
    """Detect matches still in en_juego after 130+ minutes of data."""
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    import time
    try:
        cutoff = time.time() - 600
        csv_files = [f for f in DATA_DIR.glob("partido_*.csv") if f.stat().st_mtime > cutoff]

        long_matches = []
        for csv_path in csv_files:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))

                live_rows = [r for r in rows if r.get("estado_partido") == "en_juego"]
                if not live_rows:
                    continue

                # Check if last row is still en_juego
                last = rows[-1]
                if last.get("estado_partido") != "en_juego":
                    continue

                # Check max minute reached
                minutes = []
                for r in live_rows:
                    try:
                        minutes.append(int(r.get("minuto", "0") or "0"))
                    except ValueError:
                        pass

                if minutes and max(minutes) > 130:
                    match_name = csv_path.stem.replace("partido_", "")[:40]
                    long_matches.append(f"{match_name} (min {max(minutes)})")
            except Exception:
                pass

        if long_matches:
            alerts.append({
                "level": "warning",
                "category": "long_match",
                "message": f"{len(long_matches)} partido(s) en_juego con >130 minutos — ¿no detectó finalizado?",
                "detail": "; ".join(long_matches),
            })
    except Exception as e:
        log.warning(f"Error checking long running matches: {e}")
    return alerts


def _check_odds_outliers() -> List[Dict[str, Any]]:
    """Detect clearly invalid odds values (0, negative, or >500) in recent live rows."""
    ODDS_COLS = ["back_home", "back_draw", "back_away", "back_over25", "back_over15"]
    alerts = []
    if not DATA_DIR.exists():
        return alerts

    import time
    try:
        cutoff = time.time() - 3600
        csv_files = [f for f in DATA_DIR.glob("partido_*.csv") if f.stat().st_mtime > cutoff]

        outlier_details = []
        for csv_path in csv_files:
            try:
                with open(csv_path, "r", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))

                live_rows = [r for r in rows if r.get("estado_partido") == "en_juego"]
                if not live_rows:
                    continue

                bad_cols = []
                for col in ODDS_COLS:
                    for r in live_rows[-20:]:
                        v = r.get(col, "")
                        if not v:
                            continue
                        try:
                            f_val = float(v)
                            if f_val <= 1.0 or f_val > 500:
                                bad_cols.append(f"{col}={v}")
                                break
                        except ValueError:
                            bad_cols.append(f"{col}='{v}'")
                            break

                if bad_cols:
                    match_name = csv_path.stem.replace("partido_", "")[:35]
                    outlier_details.append(f"{match_name} [{'; '.join(bad_cols[:3])}]")
            except Exception:
                pass

        if outlier_details:
            alerts.append({
                "level": "warning",
                "category": "odds_outlier",
                "message": f"Cuotas con valores imposibles en {len(outlier_details)} partido(s)",
                "detail": "; ".join(outlier_details),
            })
    except Exception as e:
        log.warning(f"Error checking odds outliers: {e}")
    return alerts


def _check_games_without_csv() -> List[Dict[str, Any]]:
    """Detect games in games.csv that have no data CSV after 10+ minutes past start time."""
    alerts = []
    if not GAMES_CSV.exists() or not DATA_DIR.exists():
        return alerts

    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with open(GAMES_CSV, "r", encoding="utf-8") as f:
            games = list(csv.DictReader(f))

        missing = []
        for g in games:
            url = g.get("url", "")
            m = re.search(r"([^/]+-apuestas-\d+)", url)
            if not m:
                continue
            match_id = m.group(1)
            csv_path = DATA_DIR / f"partido_{match_id}.csv"
            if csv_path.exists():
                continue

            # Only alert if start time is at least 10 min ago
            start_str = g.get("fecha_hora_inicio", "")
            if start_str:
                try:
                    start = datetime.strptime(start_str.strip(), "%Y-%m-%d %H:%M")
                    if (now - start).total_seconds() < 600:
                        continue  # Not started yet or just started
                except Exception:
                    pass

            missing.append(g.get("Game", match_id)[:40])

        if missing:
            alerts.append({
                "level": "warning",
                "category": "missing_csv",
                "message": f"{len(missing)} partido(s) en games.csv sin archivo de datos",
                "detail": "; ".join(missing),
            })
    except Exception as e:
        log.warning(f"Error checking games without CSV: {e}")
    return alerts


def _get_system_context() -> Dict[str, Any]:
    """Gather system context for detailed logging."""
    ctx: Dict[str, Any] = {}

    # Heartbeat data
    try:
        if HEARTBEAT_PATH.exists():
            with open(HEARTBEAT_PATH) as f:
                hb = json.load(f)
            hb_time = datetime.fromisoformat(hb["timestamp"])
            ctx["heartbeat"] = {
                "timestamp": hb.get("timestamp"),
                "age_seconds": round((datetime.now(timezone.utc) - hb_time).total_seconds(), 1),
                "alive_drivers": hb.get("alive_drivers"),
                "active_drivers": hb.get("active_drivers"),
                "cycle": hb.get("cycle"),
                "captures_ok": hb.get("captures_ok"),
                "matches": hb.get("matches", []),
            }
    except Exception:
        ctx["heartbeat"] = None

    # Games count
    try:
        if GAMES_CSV.exists():
            with open(GAMES_CSV, 'r', encoding='utf-8') as f:
                games = list(csv.DictReader(f))
            ctx["games_count"] = len(games)
            ctx["games_status"] = {}
            for g in games:
                st = g.get("status", "unknown")
                ctx["games_status"][st] = ctx["games_status"].get(st, 0) + 1
    except Exception:
        pass

    # Pending bets count
    try:
        if PLACED_BETS_CSV.exists():
            with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
                bets = list(csv.DictReader(f))
            ctx["bets_total"] = len(bets)
            ctx["bets_pending"] = sum(1 for b in bets if b.get("status") == "pending")
            ctx["bets_won"] = sum(1 for b in bets if b.get("status") == "won")
            ctx["bets_lost"] = sum(1 for b in bets if b.get("status") == "lost")
            ctx["bets_cashout"] = sum(1 for b in bets if b.get("status") == "cashout")
    except Exception:
        pass

    return ctx


def _log_alerts_to_file(alerts: List[Dict[str, Any]], context: Dict[str, Any]):
    """Persist alerts + context to JSONL log file for later analysis."""
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Rotate if too large
        if ALERTS_LOG.exists() and ALERTS_LOG.stat().st_size > ALERTS_LOG_MAX_SIZE:
            rotated = ALERTS_LOG.with_suffix('.jsonl.old')
            if rotated.exists():
                rotated.unlink()
            ALERTS_LOG.rename(rotated)

        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "n_critical": sum(1 for a in alerts if a["level"] == "critical"),
            "n_warning": sum(1 for a in alerts if a["level"] == "warning"),
            "alerts": alerts,
            "context": context,
        }

        with open(ALERTS_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.warning(f"Failed to write alerts log: {e}")


@router.get("/api/alerts")
def run_alert_checks(include_stats_api: bool = True) -> Dict[str, Any]:
    """Run all alert checks, log results, and return structured response.

    Called by the API endpoint and by the background monitor task.
    """
    alerts = []
    alerts.extend(_check_heartbeat())
    alerts.extend(_check_pending_bets())
    alerts.extend(_check_data_quality())
    alerts.extend(_check_scraper_log())
    alerts.extend(_check_frozen_rc_odds())
    alerts.extend(_check_frozen_odds_general())
    alerts.extend(_check_onedrive_conflicts())
    alerts.extend(_check_missing_stats())
    alerts.extend(_check_post_finalizado_rows())
    alerts.extend(_check_duplicate_minutes())
    alerts.extend(_check_long_running_match())
    alerts.extend(_check_odds_outliers())
    alerts.extend(_check_games_without_csv())
    # Stats API check is slow (~2s), only run if no other critical alerts
    if include_stats_api and not any(a["level"] == "critical" for a in alerts):
        alerts.extend(_check_stats_api())

    # Sort: critical first, then warning
    alerts.sort(key=lambda a: 0 if a["level"] == "critical" else 1)

    # Log to file with full context for offline analysis
    context = _get_system_context()
    if alerts:  # Only log when there are alerts (avoid flooding)
        _log_alerts_to_file(alerts, context)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(alerts),
        "critical": sum(1 for a in alerts if a["level"] == "critical"),
        "warning": sum(1 for a in alerts if a["level"] == "warning"),
        "alerts": alerts,
        "context": context,
    }


@router.get("/api/alerts")
async def get_alerts():
    """Returns all active system alerts. Also logs to alerts.jsonl."""
    return run_alert_checks()


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page():
    """Standalone HTML alerts dashboard."""
    return _ALERTS_HTML


_ALERTS_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Furbo Alerts</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; padding: 20px; }
  h1 { font-size: 1.4rem; margin-bottom: 16px; color: #fff; }
  .status-bar { display: flex; gap: 16px; margin-bottom: 20px; padding: 12px 16px; background: #1a1d27; border-radius: 8px; align-items: center; }
  .status-bar .indicator { width: 12px; height: 12px; border-radius: 50%; }
  .status-bar .indicator.ok { background: #22c55e; box-shadow: 0 0 8px #22c55e80; }
  .status-bar .indicator.warn { background: #f59e0b; box-shadow: 0 0 8px #f59e0b80; }
  .status-bar .indicator.crit { background: #ef4444; box-shadow: 0 0 8px #ef444480; animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
  .status-bar .label { font-size: 0.9rem; }
  .status-bar .time { margin-left: auto; font-size: 0.8rem; color: #888; }
  .alert-list { display: flex; flex-direction: column; gap: 8px; }
  .alert { padding: 12px 16px; border-radius: 8px; border-left: 4px solid; }
  .alert.critical { background: #1a0f0f; border-color: #ef4444; }
  .alert.warning { background: #1a170f; border-color: #f59e0b; }
  .alert .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; margin-right: 8px; }
  .alert.critical .badge { background: #ef444433; color: #ef4444; }
  .alert.warning .badge { background: #f59e0b33; color: #f59e0b; }
  .alert .category { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; background: #ffffff11; color: #888; margin-right: 8px; }
  .alert .msg { font-size: 0.9rem; }
  .alert .detail { font-size: 0.8rem; color: #888; margin-top: 4px; }
  .no-alerts { text-align: center; padding: 40px; color: #22c55e; font-size: 1.1rem; }
  .no-alerts .icon { font-size: 3rem; margin-bottom: 12px; }
  .refresh-info { font-size: 0.75rem; color: #555; margin-top: 16px; text-align: center; }
</style>
</head>
<body>
<h1>Sistema de Alertas</h1>
<div class="status-bar" id="statusBar">
  <div class="indicator" id="statusIndicator"></div>
  <span class="label" id="statusLabel">Cargando...</span>
  <span class="time" id="statusTime"></span>
</div>
<div id="alertList" class="alert-list"></div>
<div class="refresh-info">Auto-refresh cada 30s</div>

<script>
async function fetchAlerts() {
  try {
    const r = await fetch('/api/alerts');
    const data = await r.json();

    const ind = document.getElementById('statusIndicator');
    const label = document.getElementById('statusLabel');
    const time = document.getElementById('statusTime');
    const list = document.getElementById('alertList');

    time.textContent = new Date().toLocaleTimeString();

    if (data.critical > 0) {
      ind.className = 'indicator crit';
      label.textContent = `${data.critical} alerta(s) critica(s), ${data.warning} aviso(s)`;
    } else if (data.warning > 0) {
      ind.className = 'indicator warn';
      label.textContent = `${data.warning} aviso(s)`;
    } else {
      ind.className = 'indicator ok';
      label.textContent = 'Sistema OK — sin alertas';
    }

    if (data.alerts.length === 0) {
      list.innerHTML = '<div class="no-alerts"><div class="icon">&#10003;</div>Todo funcionando correctamente</div>';
      return;
    }

    list.innerHTML = data.alerts.map(a => `
      <div class="alert ${a.level}">
        <span class="badge">${a.level}</span>
        <span class="category">${a.category}</span>
        <span class="msg">${a.message}</span>
        ${a.detail ? '<div class="detail">' + a.detail + '</div>' : ''}
      </div>
    `).join('');
  } catch (e) {
    document.getElementById('statusLabel').textContent = 'Error conectando con backend';
    document.getElementById('statusIndicator').className = 'indicator crit';
  }
}

fetchAlerts();
setInterval(fetchAlerts, 30000);
</script>
</body>
</html>"""
