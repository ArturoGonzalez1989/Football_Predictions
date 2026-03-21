"""
Data loading utilities: CSV I/O, type conversion, row analysis, and match metadata.
Imported by csv_reader.py (re-exported) and potentially other modules.
"""

import csv
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import quote, unquote

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
GAMES_CSV = BASE_DIR / "games.csv"
DATA_DIR = BASE_DIR / "data"

# Load corrupted Over/Under matches list
CORRUPTED_OVER_MATCHES = set()
_corrupted_file = BASE_DIR / "corrupted_over_matches.txt"
if _corrupted_file.exists():
    with open(_corrupted_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                CORRUPTED_OVER_MATCHES.add(line)

# Cache para load_games() — evita releer 1440+ CSVs en cada ciclo de paper trading
_load_games_cache: list | None = None
_load_games_cache_time: datetime | None = None
_load_games_scanning: bool = False  # Evita scans concurrentes cuando el caché expira
_LOAD_GAMES_TTL_SECONDS = 120


STAT_COLUMNS = [
    "xg_local", "xg_visitante", "posesion_local", "posesion_visitante",
    "tiros_local", "tiros_visitante", "tiros_puerta_local", "tiros_puerta_visitante",
    "corners_local", "corners_visitante", "total_passes_local", "total_passes_visitante",
    "fouls_conceded_local", "fouls_conceded_visitante",
    "tarjetas_amarillas_local", "tarjetas_amarillas_visitante",
    "tarjetas_rojas_local", "tarjetas_rojas_visitante",
    "big_chances_local", "big_chances_visitante",
    "attacks_local", "attacks_visitante",
    "dangerous_attacks_local", "dangerous_attacks_visitante",
    "tackles_local", "tackles_visitante",
    "saves_local", "saves_visitante",
    "momentum_local", "momentum_visitante",
]


def _resolve_csv_path(match_id: str) -> Path:
    """Find the CSV file for a match_id, handling URL-encoded filenames and truncated IDs."""
    path = DATA_DIR / f"partido_{match_id}.csv"
    if path.exists():
        return path
    # Try URL-encoded version (FastAPI decodes path params)
    encoded = quote(match_id, safe="-")
    path2 = DATA_DIR / f"partido_{encoded}.csv"
    if path2.exists():
        return path2
    # Fuzzy match: scraper sometimes truncates the numeric ID at the end
    # e.g. match_id="team-apuestas-35241340" but file is "partido_team-apuestas-352413.csv"
    #      or match_id="team-apuestas-35241340" but file is "partido_team-apuestas.csv"
    prefix = re.sub(r"-?\d+$", "", match_id)  # "team-apuestas" (remove trailing dash and digits)
    if DATA_DIR.exists() and prefix:
        # Try with trailing wildcard (matches "apuestas.csv" and "apuestas-123.csv")
        for csv_file in DATA_DIR.glob(f"partido_{prefix}*.csv"):
            return csv_file
        # Also try with encoded prefix
        encoded_prefix = re.sub(r"-?\d+$", "", encoded)
        if encoded_prefix != prefix:
            for csv_file in DATA_DIR.glob(f"partido_{encoded_prefix}*.csv"):
                return csv_file
    return path  # fallback to original (will not exist)


def _to_float(val) -> Optional[float]:
    # Fast path for pre-parsed numeric values (avoids redundant str→float)
    if isinstance(val, float):
        return val
    if isinstance(val, int):
        return float(val)
    if val is None:
        return None
    # Original string path
    if not val or val.strip() in ("", "N/A", "None"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _median(values: list) -> float:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2 if n % 2 == 0 else sorted_vals[n // 2]


def _final_match_minute(rows: list[dict]) -> Optional[float]:
    """Return the last valid minute from the match rows.

    _final_result_row returns 'finalizado' rows whose minuto field is often
    empty.  This helper scans backwards to find the last row with a real
    minute value, which is needed by strategies that check whether the match
    reached a certain minute threshold.
    """
    for row in reversed(rows):
        m = _to_float(row.get("minuto", ""))
        if m is not None and m > 0:
            return m
    return None


def _final_result_row(rows: list[dict]) -> Optional[dict]:
    """Return the row that represents the final match result.

    Priority:
    1. First row with estado_partido == 'finalizado' and valid scores.
    2. Fallback: last row with any valid numeric scores (for older CSVs
       that may lack an explicit 'finalizado' state).
    """
    # 1. Look for an explicit 'finalizado' row with valid scores
    for row in rows:
        if row.get("estado_partido", "").strip() == "finalizado":
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            if gl is not None and gv is not None:
                return row
    # 2. Fallback: last row with valid scores (skips trailing pre_partido rows)
    for row in reversed(rows):
        gl = _to_float(row.get("goles_local", ""))
        gv = _to_float(row.get("goles_visitante", ""))
        if gl is not None and gv is not None:
            return row
    return None


def _strip_trailing_pre_partido_rows(rows: list[dict]) -> list[dict]:
    """Remove trailing pre_partido rows with missing scores.

    The scraper sometimes continues polling after a match ends, writing rows
    where estado_partido='pre_partido' and goles_local/goles_visitante are
    empty (the API has switched to a different pre-match event on the same tab).
    These rows contain no useful match data and cause two problems:
      1. BT reads rows[-1] for the final score → ValueError → entire match skipped.
      2. NaN minuto values in these rows reset first_seen counters in strategies
         with min_dur > 1, potentially causing missed bets.
    """
    i = len(rows) - 1
    while i >= 0:
        row = rows[i]
        estado = row.get("estado_partido", "").strip()
        has_score = (
            _to_float(row.get("goles_local", "")) is not None
            and _to_float(row.get("goles_visitante", "")) is not None
        )
        if estado == "pre_partido" and not has_score:
            i -= 1
        else:
            break
    return rows[: i + 1] if i >= 0 else rows


def _check_min_dur(rows: list[dict], start_idx: int, min_dur: int, condition_fn) -> Optional[dict]:
    """
    Starting at start_idx, check that condition_fn(row) holds for min_dur consecutive rows.
    Returns the min_dur-th row (entry row) if condition persists, else None.
    Stops early if rows run out.
    """
    if min_dur <= 1:
        return rows[start_idx] if start_idx < len(rows) else None
    count = 0
    for i in range(start_idx, len(rows)):
        if condition_fn(rows[i]):
            count += 1
            if count >= min_dur:
                return rows[i]
        else:
            return None  # signal broke before reaching min_dur
    return None  # ran out of rows


def _count_odds_stability(rows: list[dict], trigger_idx: int, odds_col: str, trigger_value: float, window: int = 10) -> tuple:
    """Count consecutive rows BACKWARD from trigger_idx where odds_col was within 30% of trigger_value.
    Returns (stability_count, min_odds_in_window):
      - stability_count: 1 = single-capture spike, N = N consecutive stable rows
      - min_odds_in_window: minimum odds seen in those consecutive rows (conservative P/L reference)
    A value is considered stable if it is within [trigger_value * 0.70, trigger_value * 1.30].
    The +/-30% window rejects jumps like 1.14->1.85 (63%) while accepting drift like 1.70->1.85 (9%).
    """
    if trigger_value <= 0 or trigger_idx < 0 or trigger_idx >= len(rows):
        return 1, trigger_value
    low = trigger_value * 0.70
    high = trigger_value * 1.30
    count = 0
    min_odds = trigger_value
    for i in range(trigger_idx, max(-1, trigger_idx - window - 1), -1):
        v = _to_float(rows[i].get(odds_col, ""))
        if v is not None and v > 0 and low <= v <= high:
            count += 1
            if v < min_odds:
                min_odds = v
        else:
            break
    return max(1, count), min_odds


def _lookback_val(rows: list[dict], idx: int, col: str, minutes_back: int) -> Optional[float]:
    """Get value of *col* from approximately *minutes_back* minutes before rows[idx]."""
    cur_min = _to_float(rows[idx].get("minuto", "")) or 0
    target = cur_min - minutes_back
    best, best_dist = None, float("inf")
    for i in range(max(0, idx - minutes_back - 5), idx):
        m = _to_float(rows[i].get("minuto", "")) or 0
        d = abs(m - target)
        if d < best_dist:
            best_dist = d
            best = rows[i]
    if best and best_dist < minutes_back * 0.5 + 2:
        return _to_float(best.get(col, ""))
    return None


def _compute_synthetic_at_trigger(rows: list[dict], trigger_idx: int) -> dict:
    """Compute synthetic derived attributes at a trigger row.

    Uses the in-play rows list and the index of the trigger row.
    Returns a dict with only the synthetic attrs used by version filters.
    """
    row = rows[trigger_idx]
    s: dict = {}

    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    mom_l = _to_float(row.get("momentum_local", ""))
    mom_v = _to_float(row.get("momentum_visitante", ""))
    opta_l = _to_float(row.get("opta_points_local", ""))
    opta_v = _to_float(row.get("opta_points_visitante", ""))
    shots_l = _to_float(row.get("tiros_local", ""))
    shots_v = _to_float(row.get("tiros_visitante", ""))
    sot_l = _to_float(row.get("tiros_puerta_local", ""))
    sot_v = _to_float(row.get("tiros_puerta_visitante", ""))
    corn_l = _to_float(row.get("corners_local", ""))
    corn_v = _to_float(row.get("corners_visitante", ""))
    gl = _to_float(row.get("goles_local", "")) or 0
    gv = _to_float(row.get("goles_visitante", "")) or 0
    minute = _to_float(row.get("minuto", "")) or 0

    # xG dominance (0..1, 0.5 = balanced)
    if xg_l is not None and xg_v is not None and (xg_l + xg_v) > 0:
        s["xg_dominance"] = round(xg_l / (xg_l + xg_v), 4)
    else:
        s["xg_dominance"] = None

    # Opta gap
    s["opta_gap"] = round(opta_l - opta_v, 2) if opta_l is not None and opta_v is not None else None

    # Momentum gap
    s["momentum_gap"] = round(abs(mom_l - mom_v), 2) if mom_l is not None and mom_v is not None else None

    # Pressure index per side (weighted recent deltas over 5 min)
    for side, sfx in [("l", "_local"), ("v", "_visitante")]:
        comps, wts = [], []
        for col_base, w in [("tiros_puerta", 3.0), ("corners", 1.5),
                             ("xg", 5.0), ("touches_box", 1.0), ("tiros", 2.0)]:
            col = col_base + sfx
            now = _to_float(row.get(col, ""))
            prev = _lookback_val(rows, trigger_idx, col, 5)
            if now is not None and prev is not None:
                comps.append((now - prev) * w)
                wts.append(w)
        s[f"pressure_index_{side}"] = round(sum(comps) / sum(wts), 4) if wts else None

    # Match openness
    parts = [v for v in [shots_l, shots_v, sot_l, sot_v, corn_l, corn_v] if v is not None]
    s["match_openness"] = round(sum(parts) + (gl + gv) * 5, 2) if parts else None

    # xG remaining (expected goals left based on current xG rate)
    if xg_l is not None and xg_v is not None and minute > 5:
        xg_rate = (xg_l + xg_v) / minute
        s["xg_remaining"] = round(xg_rate * max(0, 90 - minute), 4)
    else:
        s["xg_remaining"] = None

    return s


def _match_id_from_url(url: str) -> str:
    """Extrae el ID del partido de la URL de Betfair."""
    m = re.search(r"([a-zA-Z0-9%-]+-apuestas-\d+)", url)
    return m.group(1) if m else url.split("/")[-1]


def load_games(force_refresh: bool = False) -> list[dict]:
    """Lee games.csv y devuelve la lista de partidos con metadatos.

    Cachea el resultado 120s para evitar releer los 1440+ CSVs de data/ en cada
    ciclo de paper trading (detect_betting_signals + detect_watchlist lo llaman
    por separado, lo que sin caché supone ~2880 lecturas de archivo por ciclo).
    Usa force_refresh=True para saltarse el caché (p.ej. tras modificar games.csv).
    Si un scan ya está en curso, devuelve el caché anterior para no bloquear.
    """
    global _load_games_cache, _load_games_cache_time, _load_games_scanning
    now = datetime.now()
    if (
        not force_refresh
        and _load_games_cache is not None
        and _load_games_cache_time is not None
        and (now - _load_games_cache_time).total_seconds() < _LOAD_GAMES_TTL_SECONDS
    ):
        return _load_games_cache

    # Si otro thread ya está haciendo el scan, no lanzar un segundo scan concurrente
    if _load_games_scanning:
        # Devolver caché anterior si existe, o lista vacía si es el primer arranque
        return _load_games_cache if _load_games_cache is not None else []

    _load_games_scanning = True
    if not GAMES_CSV.exists():
        _load_games_scanning = False
        return []

    games = []
    with open(GAMES_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Game", "").strip()
            url = row.get("url", "").strip()
            fecha_str = row.get("fecha_hora_inicio", "").strip()
            match_id = _match_id_from_url(url)

            start_time = None
            if fecha_str:
                for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
                    try:
                        start_time = datetime.strptime(fecha_str, fmt)
                        break
                    except ValueError:
                        continue

            now = datetime.now()
            now_utc = datetime.utcnow()
            status = "upcoming"
            match_minute = None

            # Si han pasado >120 min desde start_time, IGNORAR este partido
            if start_time:
                elapsed = (now - start_time).total_seconds() / 60
                if elapsed > 120:
                    continue  # No incluir partidos con >120 min transcurridos

                if now >= start_time:
                    status = "live"
                    match_minute = int(min(elapsed, 90))
                else:
                    status = "upcoming"

            csv_path = _resolve_csv_path(match_id)
            capture_count = 0
            last_capture = None
            last_capture_ago_seconds = None
            if csv_path.exists():
                rows = _read_csv_rows(csv_path)
                capture_count = len(rows)
                if rows:
                    last_row = rows[-1]
                    ts = last_row.get("timestamp_utc", "")
                    if ts:
                        last_capture = ts
                        try:
                            last_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                            # Timestamps in CSV are UTC, so compare with UTC now
                            last_capture_ago_seconds = int((now_utc - last_dt).total_seconds())
                        except Exception:
                            pass

                    # Check if ANY row has "finalizado" (match may revert to "pre_partido" after ending)
                    was_finished = any(r.get("estado_partido", "").strip() == "finalizado" for r in rows)
                    was_live = any(r.get("estado_partido", "").strip() in ("en_juego", "descanso") for r in rows)

                    estado_partido = last_row.get("estado_partido", "").strip()
                    if was_finished:
                        status = "finished"
                    elif estado_partido == "en_juego":
                        status = "live"
                        minuto_csv = last_row.get("minuto", "").strip()
                        if minuto_csv.isdigit():
                            match_minute = int(minuto_csv)
                    elif estado_partido == "descanso":
                        status = "live"
                        minuto_csv = last_row.get("minuto", "").strip()
                        if minuto_csv.isdigit():
                            match_minute = int(minuto_csv)
                        else:
                            match_minute = 45
                    elif estado_partido == "pre_partido" and was_live:
                        # Was live but now shows pre_partido -> match ended, Betfair reverted
                        status = "finished"
                    elif estado_partido == "pre_partido":
                        status = "upcoming"
                        match_minute = None
                    # Si estado_partido esta vacio, mantener status basado en tiempo transcurrido
            # Si no hay CSV, mantener el status basado en start_time (live si ya empezo, upcoming si no)

            games.append({
                "name": name,
                "url": url,
                "match_id": match_id,
                "start_time": start_time.isoformat() if start_time else None,
                "status": status,
                "match_minute": match_minute,
                "capture_count": capture_count,
                "last_capture": last_capture,
                "last_capture_ago_seconds": last_capture_ago_seconds,
                "csv_exists": csv_path.exists(),
            })

    # Also scan data/ for orphaned CSVs (finished matches removed from games.csv)
    known_ids = {g["match_id"] for g in games}
    if DATA_DIR.exists():
        for csv_file in DATA_DIR.glob("partido_*.csv"):
            raw_id = csv_file.stem.replace("partido_", "")
            decoded_id = unquote(raw_id)
            if raw_id in known_ids or decoded_id in known_ids:
                continue

            rows = _read_csv_rows(csv_file)
            if not rows:
                continue

            # Use decoded id so FastAPI path params match
            match_id = decoded_id

            # Derive name from match_id: "team1-team2-apuestas-123" -> "Team1 - Team2"
            name_part = re.sub(r"-apuestas-\d+$", "", match_id)
            # Capitalize each word
            name = " ".join(w.capitalize() for w in name_part.split("-"))

            now = datetime.now()
            capture_count = len(rows)
            last_capture = None
            last_capture_ago_seconds = None
            first_ts = rows[0].get("timestamp_utc", "")
            last_ts = rows[-1].get("timestamp_utc", "")

            start_time = None
            if first_ts:
                try:
                    start_time = datetime.fromisoformat(first_ts.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass

            if last_ts:
                last_capture = last_ts
                try:
                    last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00")).replace(tzinfo=None)
                    last_capture_ago_seconds = int((now - last_dt).total_seconds())
                except Exception:
                    pass

            games.append({
                "name": name,
                "url": "",
                "match_id": match_id,
                "start_time": start_time.isoformat() if start_time else None,
                "status": "finished",
                "match_minute": None,
                "capture_count": capture_count,
                "last_capture": last_capture,
                "last_capture_ago_seconds": last_capture_ago_seconds,
                "csv_exists": True,
            })

    _load_games_cache = games
    _load_games_cache_time = datetime.now()
    _load_games_scanning = False
    return games


# mtime-based cache: avoids re-reading CSVs that haven't changed on disk.
# Key = str(path), Value = (mtime, rows).  Cleared via clear_analytics_cache().
_csv_row_cache: dict[str, tuple[float, list[dict]]] = {}


def _read_csv_rows(csv_path: Path) -> list[dict]:
    """Lee todas las filas de un CSV (cached by file mtime)."""
    if not csv_path.exists():
        return []
    key = str(csv_path)
    try:
        mtime = csv_path.stat().st_mtime
    except OSError:
        mtime = 0.0
    cached = _csv_row_cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    _csv_row_cache[key] = (mtime, rows)
    return rows


def _normalize_halftime_minutes(rows: list[dict]) -> list[dict]:
    """Cap first-half injury-time minutes at 45.

    Betfair's match clock runs continuously past 45 during first-half stoppage
    time (e.g. shows 46, 47 ... 64) instead of the UEFA "45+N" format, then
    resets to 45 at second-half kick-off.  This creates duplicate minute values
    (e.g. minute 50 appears once in first-half added time and once in the
    second half), which confuses strategy filters like Drift V4 (> minute 45).

    Fix: any `en_juego` row recorded *before* the first `descanso` row whose
    minute exceeds 45 is capped at 45.

    Only applied when at least one `descanso` row exists -- for matches where
    the half-time interval was never captured we leave minutes unchanged to
    avoid incorrectly capping second-half data.
    """
    has_descanso = any(
        r.get("estado_partido", "").strip().lower() == "descanso" for r in rows
    )
    if not has_descanso:
        return rows  # Cannot detect boundary safely -- leave as-is

    result = []
    first_half = True
    for row in rows:
        estado = row.get("estado_partido", "").strip().lower()
        if estado == "descanso":
            first_half = False
            result.append(row)
            continue
        if first_half:
            m_raw = row.get("minuto", "")
            if m_raw:
                try:
                    if float(str(m_raw).replace("'", "").strip()) > 45:
                        row = dict(row)  # don't mutate the original dict
                        row["minuto"] = "45"
                except (ValueError, AttributeError):
                    pass
        result.append(row)
    return result


def _read_csv_summary(csv_path: Path) -> dict:
    """Read only header + first + last row of a CSV for fast metadata.
    Returns {count, first_row, last_row} without parsing the entire file."""
    if not csv_path.exists():
        return {"count": 0, "first_row": {}, "last_row": {}}

    with open(csv_path, "r", encoding="utf-8") as f:
        header = f.readline().strip()
        if not header:
            return {"count": 0, "first_row": {}, "last_row": {}}

        fields = header.split(",")
        first_line = f.readline().strip()
        if not first_line:
            return {"count": 0, "first_row": {}, "last_row": {}}

        # Count remaining lines and track the last one
        count = 1
        last_line = first_line
        for line in f:
            line = line.strip()
            if line:
                last_line = line
                count += 1

    first_vals = first_line.split(",")
    last_vals = last_line.split(",")

    first_row = dict(zip(fields, first_vals)) if len(first_vals) == len(fields) else {}
    last_row = dict(zip(fields, last_vals)) if len(last_vals) == len(fields) else {}

    return {"count": count, "first_row": first_row, "last_row": last_row}


def delete_match(match_id: str) -> dict:
    """Elimina un partido de games.csv y borra su CSV de datos."""
    deleted_from_csv = False
    deleted_data = False

    # 1. Eliminar de games.csv
    if GAMES_CSV.exists():
        with open(GAMES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        original_count = len(rows)
        rows = [r for r in rows if _match_id_from_url(r.get("url", "")) != match_id]

        if len(rows) < original_count and fieldnames:
            with open(GAMES_CSV, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            deleted_from_csv = True
            _load_games_cache_time = None  # Invalidar caché

    # 2. Borrar CSV de datos
    csv_path = _resolve_csv_path(match_id)
    if csv_path.exists():
        try:
            csv_path.unlink()
            deleted_data = True
        except PermissionError:
            # Archivo bloqueado (OneDrive, scraper, etc.) - reintentar con gc
            import gc
            gc.collect()
            try:
                csv_path.unlink()
                deleted_data = True
            except PermissionError:
                pass  # No se pudo borrar, reportar como no eliminado

    return {
        "match_id": match_id,
        "deleted_from_csv": deleted_from_csv,
        "deleted_data": deleted_data,
    }


def load_all_captures(match_id: str) -> dict:
    """Carga TODAS las capturas de un partido para vista detallada."""
    csv_path = _resolve_csv_path(match_id)
    rows = _read_csv_rows(csv_path)

    if not rows:
        return {"match_id": match_id, "rows": 0, "captures": []}

    captures = []
    for row in rows:
        # Devolver TODAS las columnas individuales del CSV tal cual
        capture = {
            "timestamp": row.get("timestamp_utc", ""),
            "minuto": row.get("minuto", ""),
            "goles_local": row.get("goles_local", ""),
            "goles_visitante": row.get("goles_visitante", ""),
            "xg_local": row.get("xg_local", ""),
            "xg_visitante": row.get("xg_visitante", ""),
            "posesion_local": row.get("posesion_local", ""),
            "posesion_visitante": row.get("posesion_visitante", ""),
            "corners_local": row.get("corners_local", ""),
            "corners_visitante": row.get("corners_visitante", ""),
            "tiros_local": row.get("tiros_local", ""),
            "tiros_visitante": row.get("tiros_visitante", ""),
            "tiros_puerta_local": row.get("tiros_puerta_local", ""),
            "tiros_puerta_visitante": row.get("tiros_puerta_visitante", ""),
            "shots_off_target_local": row.get("shots_off_target_local", ""),
            "shots_off_target_visitante": row.get("shots_off_target_visitante", ""),
            "blocked_shots_local": row.get("blocked_shots_local", ""),
            "blocked_shots_visitante": row.get("blocked_shots_visitante", ""),
            "saves_local": row.get("saves_local", ""),
            "saves_visitante": row.get("saves_visitante", ""),
            "dangerous_attacks_local": row.get("dangerous_attacks_local", ""),
            "dangerous_attacks_visitante": row.get("dangerous_attacks_visitante", ""),
            "fouls_conceded_local": row.get("fouls_conceded_local", ""),
            "fouls_conceded_visitante": row.get("fouls_conceded_visitante", ""),
            "goal_kicks_local": row.get("goal_kicks_local", ""),
            "goal_kicks_visitante": row.get("goal_kicks_visitante", ""),
            "throw_ins_local": row.get("throw_ins_local", ""),
            "throw_ins_visitante": row.get("throw_ins_visitante", ""),
            "tarjetas_amarillas_local": row.get("tarjetas_amarillas_local", ""),
            "tarjetas_amarillas_visitante": row.get("tarjetas_amarillas_visitante", ""),
            "tarjetas_rojas_local": row.get("tarjetas_rojas_local", ""),
            "tarjetas_rojas_visitante": row.get("tarjetas_rojas_visitante", ""),
            "total_passes_local": row.get("total_passes_local", ""),
            "total_passes_visitante": row.get("total_passes_visitante", ""),
            "big_chances_local": row.get("big_chances_local", ""),
            "big_chances_visitante": row.get("big_chances_visitante", ""),
            "attacks_local": row.get("attacks_local", ""),
            "attacks_visitante": row.get("attacks_visitante", ""),
            "tackles_local": row.get("tackles_local", ""),
            "tackles_visitante": row.get("tackles_visitante", ""),
            "momentum_local": row.get("momentum_local", ""),
            "momentum_visitante": row.get("momentum_visitante", ""),
            "opta_points_local": row.get("opta_points_local", ""),
            "opta_points_visitante": row.get("opta_points_visitante", ""),
            "touches_box_local": row.get("touches_box_local", ""),
            "touches_box_visitante": row.get("touches_box_visitante", ""),
            "shooting_accuracy_local": row.get("shooting_accuracy_local", ""),
            "shooting_accuracy_visitante": row.get("shooting_accuracy_visitante", ""),
            "free_kicks_local": row.get("free_kicks_local", ""),
            "free_kicks_visitante": row.get("free_kicks_visitante", ""),
            "offsides_local": row.get("offsides_local", ""),
            "offsides_visitante": row.get("offsides_visitante", ""),
            "substitutions_local": row.get("substitutions_local", ""),
            "substitutions_visitante": row.get("substitutions_visitante", ""),
            "injuries_local": row.get("injuries_local", ""),
            "injuries_visitante": row.get("injuries_visitante", ""),
            "time_in_dangerous_attack_pct_local": row.get("time_in_dangerous_attack_pct_local", ""),
            "time_in_dangerous_attack_pct_visitante": row.get("time_in_dangerous_attack_pct_visitante", ""),
        }
        captures.append(capture)

    return {
        "match_id": match_id,
        "rows": len(rows),
        "captures": captures
    }


def load_match_detail(match_id: str) -> dict:
    """Carga detalle completo de un partido: ultimas capturas, quality, gaps."""
    csv_path = _resolve_csv_path(match_id)
    rows = _read_csv_rows(csv_path)

    if not rows:
        return {"match_id": match_id, "rows": 0, "captures": [], "quality": 0, "gaps": []}

    # Ultimas 10 capturas
    last_rows = rows[-10:]
    captures = []
    for row in last_rows:
        # Devolver TODAS las columnas individuales del CSV tal cual
        capture = {
            "timestamp": row.get("timestamp_utc", ""),
            "minuto": row.get("minuto", ""),
            "goles_local": row.get("goles_local", ""),
            "goles_visitante": row.get("goles_visitante", ""),
            "xg_local": row.get("xg_local", ""),
            "xg_visitante": row.get("xg_visitante", ""),
            "posesion_local": row.get("posesion_local", ""),
            "posesion_visitante": row.get("posesion_visitante", ""),
            "corners_local": row.get("corners_local", ""),
            "corners_visitante": row.get("corners_visitante", ""),
            "tiros_local": row.get("tiros_local", ""),
            "tiros_visitante": row.get("tiros_visitante", ""),
            "tiros_puerta_local": row.get("tiros_puerta_local", ""),
            "tiros_puerta_visitante": row.get("tiros_puerta_visitante", ""),
            "shots_off_target_local": row.get("shots_off_target_local", ""),
            "shots_off_target_visitante": row.get("shots_off_target_visitante", ""),
            "blocked_shots_local": row.get("blocked_shots_local", ""),
            "blocked_shots_visitante": row.get("blocked_shots_visitante", ""),
            "saves_local": row.get("saves_local", ""),
            "saves_visitante": row.get("saves_visitante", ""),
            "dangerous_attacks_local": row.get("dangerous_attacks_local", ""),
            "dangerous_attacks_visitante": row.get("dangerous_attacks_visitante", ""),
            "fouls_conceded_local": row.get("fouls_conceded_local", ""),
            "fouls_conceded_visitante": row.get("fouls_conceded_visitante", ""),
            "goal_kicks_local": row.get("goal_kicks_local", ""),
            "goal_kicks_visitante": row.get("goal_kicks_visitante", ""),
            "throw_ins_local": row.get("throw_ins_local", ""),
            "throw_ins_visitante": row.get("throw_ins_visitante", ""),
            "tarjetas_amarillas_local": row.get("tarjetas_amarillas_local", ""),
            "tarjetas_amarillas_visitante": row.get("tarjetas_amarillas_visitante", ""),
            "tarjetas_rojas_local": row.get("tarjetas_rojas_local", ""),
            "tarjetas_rojas_visitante": row.get("tarjetas_rojas_visitante", ""),
            "total_passes_local": row.get("total_passes_local", ""),
            "total_passes_visitante": row.get("total_passes_visitante", ""),
            "big_chances_local": row.get("big_chances_local", ""),
            "big_chances_visitante": row.get("big_chances_visitante", ""),
            "attacks_local": row.get("attacks_local", ""),
            "attacks_visitante": row.get("attacks_visitante", ""),
            "tackles_local": row.get("tackles_local", ""),
            "tackles_visitante": row.get("tackles_visitante", ""),
            "momentum_local": row.get("momentum_local", ""),
            "momentum_visitante": row.get("momentum_visitante", ""),
            "opta_points_local": row.get("opta_points_local", ""),
            "opta_points_visitante": row.get("opta_points_visitante", ""),
            "touches_box_local": row.get("touches_box_local", ""),
            "touches_box_visitante": row.get("touches_box_visitante", ""),
            "shooting_accuracy_local": row.get("shooting_accuracy_local", ""),
            "shooting_accuracy_visitante": row.get("shooting_accuracy_visitante", ""),
            "free_kicks_local": row.get("free_kicks_local", ""),
            "free_kicks_visitante": row.get("free_kicks_visitante", ""),
            "offsides_local": row.get("offsides_local", ""),
            "offsides_visitante": row.get("offsides_visitante", ""),
            "substitutions_local": row.get("substitutions_local", ""),
            "substitutions_visitante": row.get("substitutions_visitante", ""),
            "injuries_local": row.get("injuries_local", ""),
            "injuries_visitante": row.get("injuries_visitante", ""),
            "time_in_dangerous_attack_pct_local": row.get("time_in_dangerous_attack_pct_local", ""),
            "time_in_dangerous_attack_pct_visitante": row.get("time_in_dangerous_attack_pct_visitante", ""),
        }
        captures.append(capture)

    # Quality score (only in-play rows)
    total_filled = 0
    total_possible = 0
    for row in rows:
        estado = row.get("estado_partido", "").strip()
        if estado in ("pre_partido", ""):
            continue
        for col in STAT_COLUMNS:
            total_possible += 1
            val = row.get(col, "")
            if val and val.strip() not in ("", "N/A", "None"):
                total_filled += 1

    quality = round(total_filled / total_possible * 100, 1) if total_possible > 0 else 0

    # Gap analysis
    minutes_captured = set()
    for row in rows:
        m = row.get("minuto", "")
        if m:
            try:
                minutes_captured.add(int(m.replace("'", "").strip()))
            except ValueError:
                pass

    if minutes_captured:
        max_min = max(minutes_captured)
        all_minutes = set(range(1, max_min + 1))
        gaps = sorted(all_minutes - minutes_captured)
    else:
        gaps = []

    return {
        "match_id": match_id,
        "rows": len(rows),
        "captures": captures,
        "quality": quality,
        "gaps": gaps[:50],
        "total_gaps": len(gaps) if minutes_captured else 0,
    }


def load_momentum_data(match_id: str) -> dict:
    """Carga datos de momentum para grafico."""
    csv_path = _resolve_csv_path(match_id)
    rows = _read_csv_rows(csv_path)

    minutes = []
    home_momentum = []
    away_momentum = []
    home_xg = []
    away_xg = []
    home_possession = []
    away_possession = []

    for row in rows:
        m = row.get("minuto", "")
        try:
            minute_val = int(float(m.replace("'", "").strip())) if m else None
        except ValueError:
            minute_val = None

        if minute_val is not None:
            minutes.append(minute_val)
            home_momentum.append(_to_float(row.get("momentum_local", "")))
            away_momentum.append(_to_float(row.get("momentum_visitante", "")))
            home_xg.append(_to_float(row.get("xg_local", "")))
            away_xg.append(_to_float(row.get("xg_visitante", "")))
            home_possession.append(_to_float(row.get("posesion_local", "")))
            away_possession.append(_to_float(row.get("posesion_visitante", "")))

    return {
        "match_id": match_id,
        "data_points": len(minutes),
        "minutes": minutes,
        "momentum": {"home": home_momentum, "away": away_momentum},
        "xg": {"home": home_xg, "away": away_xg},
        "possession": {"home": home_possession, "away": away_possession},
    }


def load_all_stats(match_id: str) -> dict:
    """Carga todas las estadisticas del ultimo row del CSV."""
    csv_path = _resolve_csv_path(match_id)
    rows = _read_csv_rows(csv_path)

    if not rows:
        return {}

    last_row = rows[-1]
    stats = {}
    for col in STAT_COLUMNS:
        val = _to_float(last_row.get(col, ""))
        stats[col] = val

    stats["minuto"] = last_row.get("minuto", "")
    stats["goles_local"] = last_row.get("goles_local", "")
    stats["goles_visitante"] = last_row.get("goles_visitante", "")
    stats["estado_partido"] = last_row.get("estado_partido", "")

    return stats


ODDS_COLUMNS = [
    ("back_home", "lay_home"), ("back_draw", "lay_draw"), ("back_away", "lay_away"),
    ("back_over05", "lay_over05"), ("back_under05", "lay_under05"),
    ("back_over15", "lay_over15"), ("back_under15", "lay_under15"),
    ("back_over25", "lay_over25"), ("back_under25", "lay_under25"),
    ("back_over35", "lay_over35"), ("back_under35", "lay_under35"),
    ("back_over45", "lay_over45"), ("back_under45", "lay_under45"),
]

ALL_STAT_COLUMNS = STAT_COLUMNS + [
    "opta_points_local", "opta_points_visitante",
    "touches_box_local", "touches_box_visitante",
    "shots_off_target_local", "shots_off_target_visitante",
    "hit_woodwork_local", "hit_woodwork_visitante",
    "blocked_shots_local", "blocked_shots_visitante",
    "shooting_accuracy_local", "shooting_accuracy_visitante",
    "duels_won_local", "duels_won_visitante",
    "aerial_duels_won_local", "aerial_duels_won_visitante",
    "clearance_local", "clearance_visitante",
    "interceptions_local", "interceptions_visitante",
    "pass_success_pct_local", "pass_success_pct_visitante",
    "crosses_local", "crosses_visitante",
    "successful_crosses_pct_local", "successful_crosses_pct_visitante",
    "successful_passes_opp_half_local", "successful_passes_opp_half_visitante",
    "successful_passes_final_third_local", "successful_passes_final_third_visitante",
    "tackle_success_pct_local", "tackle_success_pct_visitante",
    "goal_kicks_local", "goal_kicks_visitante",
    "throw_ins_local", "throw_ins_visitante",
    "booking_points_local", "booking_points_visitante",
]


def _clean_odds_outliers(rows: list, ratio: float = 5.0) -> list:
    """Replace outlier odds values with "" to avoid distorting strategy analysis.

    An outlier is any value > median*ratio or < median/ratio.
    Requires >=3 valid data points per column; otherwise leaves that column unchanged.
    Returns NEW dicts -- does NOT mutate originals.
    """
    if len(rows) < 3:
        return rows

    all_odds_cols = [col for pair in ODDS_COLUMNS for col in pair]
    medians = {}
    for col in all_odds_cols:
        vals = []
        for r in rows:
            v = _to_float(r.get(col, ""))
            if v is not None and v > 0:
                vals.append(v)
        if len(vals) >= 3:
            medians[col] = _median(vals)

    if not medians:
        return rows

    cleaned = []
    for row in rows:
        new_row = dict(row)
        for col, med in medians.items():
            if med <= 0:
                continue
            val = _to_float(row.get(col, ""))
            if val is not None and (val > med * ratio or val < med / ratio):
                new_row[col] = ""
        cleaned.append(new_row)
    return cleaned


# ── Pre-parse numeric columns (str→float) on cache load ──────────────────
# Columns known to be numeric from trigger/analytics code.  Pre-parsing once
# eliminates ~1-2M redundant _to_float(str) calls per backtest run.
# Columns not in this set keep their original string value — _to_float still
# handles them correctly (just slower, as before).
_PREPARSE_NUMERIC_COLS: frozenset[str] = frozenset({
    # Core match data
    "minuto", "goles_local", "goles_visitante",
    # Statistics used by triggers
    "xg_local", "xg_visitante",
    "posesion_local", "posesion_visitante",
    "tiros_local", "tiros_visitante",
    "tiros_puerta_local", "tiros_puerta_visitante",
    "corners_local", "corners_visitante",
    "tackles_local", "tackles_visitante",
    "momentum_local", "momentum_visitante",
    "saves_local", "saves_visitante",
    # Main odds
    "back_home", "back_draw", "back_away",
    "lay_home", "lay_draw", "lay_away",
    # Over/Under odds
    "back_over05", "lay_over05",
    "back_over15", "lay_over15",
    "back_over25", "lay_over25",
    "back_over35", "lay_over35",
    "back_over45", "lay_over45",
    "back_under05", "lay_under05",
    "back_under15", "lay_under15",
    "back_under25", "lay_under25",
    "back_under35", "lay_under35",
    "back_under45", "lay_under45",
    # Correct score odds (static, most commonly used)
    "back_rc_0_0", "lay_rc_0_0",
    "back_rc_1_1", "lay_rc_1_1",
    # Volume
    "volumen_matched",
})


def _preparse_numeric_rows(rows: list[dict]) -> list[dict]:
    """Convert known numeric columns from str to float in-place (once).

    After this, _to_float() hits the fast ``isinstance(val, float)`` path
    instead of parsing the same string repeatedly across 32 strategy triggers.
    Values that are empty or unparseable become None.
    """
    cols = _PREPARSE_NUMERIC_COLS
    for r in rows:
        for col in cols:
            v = r.get(col)
            if v is None or isinstance(v, (float, int)):
                continue  # already parsed or absent
            if not v or v == "":
                r[col] = None
                continue
            try:
                r[col] = float(v)
            except (ValueError, TypeError):
                r[col] = None
    # Also pre-parse any back_rc_*/lay_rc_* columns (correct score, dynamic names)
    if rows:
        rc_cols = [k for k in rows[0] if k.startswith(("back_rc_", "lay_rc_"))]
        for r in rows:
            for col in rc_cols:
                v = r.get(col)
                if v is None or isinstance(v, (float, int)):
                    continue
                if not v or v == "":
                    r[col] = None
                    continue
                try:
                    r[col] = float(v)
                except (ValueError, TypeError):
                    r[col] = None
    return rows


def load_match_full(match_id: str) -> dict:
    """Carga resumen completo de un partido finalizado: stats, cuotas, timeline."""
    csv_path = _resolve_csv_path(match_id)
    rows = _read_csv_rows(csv_path)

    if not rows:
        return {"match_id": match_id, "rows": 0}

    last_row = rows[-1]
    first_row = rows[0]

    # Final stats
    final_stats = {}
    for col in ALL_STAT_COLUMNS:
        final_stats[col] = _to_float(last_row.get(col, ""))

    # Final score
    final_stats["goles_local"] = last_row.get("goles_local", "")
    final_stats["goles_visitante"] = last_row.get("goles_visitante", "")
    final_stats["estado_partido"] = last_row.get("estado_partido", "")

    # Odds: opening (first row) and closing (last row with data)
    opening_odds = {}
    closing_odds = {}
    for back_col, lay_col in ODDS_COLUMNS:
        opening_odds[back_col] = _to_float(first_row.get(back_col, ""))
        opening_odds[lay_col] = _to_float(first_row.get(lay_col, ""))
        closing_odds[back_col] = _to_float(last_row.get(back_col, ""))
        closing_odds[lay_col] = _to_float(last_row.get(lay_col, ""))

    # Odds timeline (sampled - one per minute or max 100 points)
    odds_timeline = []
    seen_minutes = set()
    for row in rows:
        m = row.get("minuto", "")
        try:
            minute_val = int(float(m.replace("'", "").strip())) if m else None
        except ValueError:
            minute_val = None

        key = minute_val if minute_val is not None else row.get("timestamp_utc", "")
        if key in seen_minutes:
            continue
        seen_minutes.add(key)

        point = {"minute": minute_val}
        # Match Odds (back + lay)
        for back_col, lay_col in ODDS_COLUMNS[:3]:
            point[back_col] = _to_float(row.get(back_col, ""))
            point[lay_col] = _to_float(row.get(lay_col, ""))
        # Over/Under 0.5 a 4.5 (back + lay)
        for back_col, lay_col in ODDS_COLUMNS[3:13]:
            point[back_col] = _to_float(row.get(back_col, ""))
            point[lay_col] = _to_float(row.get(lay_col, ""))
        point["volumen_matched"] = _to_float(row.get("volumen_matched", ""))
        odds_timeline.append(point)

    # Volume matched
    volume = _to_float(last_row.get("volumen_matched", ""))

    # Timestamps
    first_ts = first_row.get("timestamp_utc", "")
    last_ts = last_row.get("timestamp_utc", "")

    return {
        "match_id": match_id,
        "rows": len(rows),
        "final_stats": final_stats,
        "opening_odds": opening_odds,
        "closing_odds": closing_odds,
        "odds_timeline": odds_timeline[:100],
        "volume_matched": volume,
        "first_capture": first_ts,
        "last_capture": last_ts,
    }


# ==================== ANALYTICS FUNCTIONS ====================

# Cache for analytics: finished matches don't change, so cache aggressively
import threading as _threading
_analytics_cache: dict = {}
_analytics_cache_time: float = 0
_ANALYTICS_CACHE_TTL = 300  # 5 minutes
# Result cache: stores computed results of analytics functions
_result_cache: dict = {}
_result_cache_time: float = 0
_cache_lock = _threading.Lock()


def clear_analytics_cache():
    """Clear analytics cache to force reload of data."""
    global _analytics_cache, _analytics_cache_time, _result_cache, _result_cache_time, _csv_row_cache
    with _cache_lock:
        _analytics_cache = {}
        _analytics_cache_time = 0
        _result_cache = {}
        _result_cache_time = 0
        _csv_row_cache = {}


def _get_cached_finished_data() -> list[dict]:
    """Get all finished matches with pre-loaded CSV rows. Cached for 5 min."""
    global _analytics_cache, _analytics_cache_time, _result_cache, _result_cache_time
    import time as _time

    now = _time.time()
    # Fast path: check under lock, return immediately if still valid
    with _cache_lock:
        if _analytics_cache and (now - _analytics_cache_time) < _ANALYTICS_CACHE_TTL:
            return _analytics_cache.get("finished", [])

    # Slow path: rebuild outside the lock (CSV loading can take seconds)
    # Load URL mapping from games.csv
    url_map = {}
    try:
        games_csv_path = BASE_DIR / "games.csv"
        if games_csv_path.exists():
            with open(games_csv_path, "r", encoding="utf-8") as f:
                import csv
                reader = csv.DictReader(f)
                for row in reader:
                    game_name = row.get("Game", "").strip()
                    game_url = row.get("url", "").strip()
                    if game_name and game_url:
                        url_map[game_name] = game_url
    except Exception:
        pass  # If games.csv doesn't exist or fails, continue without URLs

    games = load_games()
    finished = []
    for game in games:
        if game["status"] == "finished" and game["csv_exists"]:
            csv_path = _resolve_csv_path(game["match_id"])
            if csv_path.exists():
                rows = _read_csv_rows(csv_path)
                # Outlier stats on RAW rows (for Data Quality reporting)
                bh_vals = []
                kickoff_time = None
                for r in rows:
                    v = _to_float(r.get("back_home", ""))
                    if v is not None and v > 0:
                        bh_vals.append(v)
                    if kickoff_time is None and r.get("estado_partido", "").strip().lower() == "en_juego":
                        ts = r.get("timestamp_utc", "").strip()
                        if ts:
                            kickoff_time = ts
                raw_with_odds = len(bh_vals)
                raw_total_rows = len(rows)
                bh_outliers = 0
                min_bh = min(bh_vals) if bh_vals else None
                max_bh = max(bh_vals) if bh_vals else None
                gap_count, avg_gap_size = _calculate_gap_segments(rows)
                if len(bh_vals) >= 3:
                    med = _median(bh_vals)
                    if med > 0:
                        bh_outliers = sum(1 for v in bh_vals if v > med * 5 or v < med / 5)
                # Normalize first-half injury-time minutes (cap at 45 when descanso present)
                rows = _normalize_halftime_minutes(rows)
                # Clean rows for strategy analysis (removes outlier odds)
                rows = _clean_odds_outliers(rows)
                # Strip trailing pre_partido rows with NaN scores (scraper noise after match end)
                rows = _strip_trailing_pre_partido_rows(rows)
                # Pre-parse numeric columns (str→float) so triggers hit the fast path
                rows = _preparse_numeric_rows(rows)
                # Try to get URL from games.csv mapping by match name
                game_url = game.get("url") or url_map.get(game["name"], "")
                finished.append({
                    "match_id": game["match_id"],
                    "name": game["name"],
                    "url": game_url,  # URL from matches.json or games.csv
                    "start_time": game.get("start_time"),
                    "kickoff_time": kickoff_time,
                    "csv_path": csv_path,
                    "rows": rows,
                    "raw_total_rows": raw_total_rows,
                    "raw_with_odds": raw_with_odds,
                    "back_home_outliers": bh_outliers,
                    "min_back_home": min_bh,
                    "max_back_home": max_bh,
                    "gap_count": gap_count,
                    "avg_gap_size": avg_gap_size,
                })

    # Write under lock; invalidate result cache at the same time
    with _cache_lock:
        _analytics_cache = {"finished": finished}
        _analytics_cache_time = now
        _result_cache = {}
        _result_cache_time = now
    return finished


def _cached_result(key: str):
    """Decorator to cache the result of an analytics function (thread-safe)."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            with _cache_lock:
                if key in _result_cache:
                    return _result_cache[key]
            result = fn(*args, **kwargs)
            with _cache_lock:
                _result_cache[key] = result
            return result
        return wrapper
    return decorator


def _get_all_finished_matches() -> list[dict]:
    """Get all finished matches with their CSV paths (backward compat)."""
    return _get_cached_finished_data()


def _calculate_match_quality(rows: list[dict]) -> float:
    """Calculate quality score for a match (% of non-null stats).
    Only counts in-play rows (en_juego, descanso, finalizado) to avoid
    pre-match rows dragging down the quality score."""
    if not rows:
        return 0.0

    total_filled = 0
    total_possible = 0
    for row in rows:
        # Only count rows where the match is actually in progress or finished
        estado = row.get("estado_partido", "").strip()
        if estado in ("pre_partido", ""):
            continue

        for col in STAT_COLUMNS:
            total_possible += 1
            val = row.get(col, "")
            if val and val.strip() not in ("", "N/A", "None"):
                total_filled += 1

    return round(total_filled / total_possible * 100, 1) if total_possible > 0 else 0.0


def _calculate_match_gaps(rows: list[dict]) -> int:
    """Calculate number of missing minutes in a match."""
    minutes_captured = set()
    for row in rows:
        m = row.get("minuto", "")
        if m:
            try:
                minutes_captured.add(int(m.replace("'", "").strip()))
            except ValueError:
                pass

    if minutes_captured:
        max_min = max(minutes_captured)
        all_minutes = set(range(1, max_min + 1))
        gaps = all_minutes - minutes_captured
        return len(gaps)
    return 0


def _calculate_gap_segments(rows: list[dict]) -> tuple[int, float]:
    """Return (total_missing_minutes, avg_segment_size).
    Counts absences between minutes 1-90 only.
    - pre_partido rows (null/empty minuto) are ignored.
    - descanso rows are excluded from both captured AND expected sets
      (halftime is not a gap).
    A segment is a consecutive block of missing minutes.
    E.g. missing=[4,8,9] -> segments=[1,2] -> avg=1.5
    """
    minutes_captured = set()
    descanso_minutes = set()

    for row in rows:
        m = row.get("minuto", "")
        if not m:
            continue  # pre_partido or rows without minute -- skip
        try:
            minute = int(float(str(m).replace("'", "").strip()))
        except (ValueError, AttributeError):
            continue

        if minute < 1 or minute > 90:
            continue  # extra time etc. -- outside scope

        estado = row.get("estado_partido", "").strip().lower()
        if estado == "descanso":
            descanso_minutes.add(minute)
        else:
            minutes_captured.add(minute)

    # Expected minutes: 1-90 minus halftime minutes
    expected = set(range(1, 91)) - descanso_minutes
    missing = sorted(expected - minutes_captured)

    if not missing:
        return 0, 0.0

    # Group consecutive minutes into segments
    segments = []
    seg_len = 1
    for i in range(1, len(missing)):
        if missing[i] == missing[i - 1] + 1:
            seg_len += 1
        else:
            segments.append(seg_len)
            seg_len = 1
    segments.append(seg_len)

    avg = round(sum(segments) / len(segments), 1)
    return len(missing), avg

