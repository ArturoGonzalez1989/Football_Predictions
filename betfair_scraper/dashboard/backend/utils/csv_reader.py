"""
Utilidades para leer games.csv y CSVs de partidos individuales.
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


def _to_float(val: str) -> Optional[float]:
    if not val or val.strip() in ("", "N/A", "None"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _median(values: list) -> float:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2 if n % 2 == 0 else sorted_vals[n // 2]


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
    The ±30% window rejects jumps like 1.14→1.85 (63%) while accepting drift like 1.70→1.85 (9%).
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


def load_games() -> list[dict]:
    """Lee games.csv y devuelve la lista de partidos con metadatos."""
    if not GAMES_CSV.exists():
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
                        # Was live but now shows pre_partido → match ended, Betfair reverted
                        status = "finished"
                    elif estado_partido == "pre_partido":
                        status = "upcoming"
                        match_minute = None
                    # Si estado_partido está vacío, mantener status basado en tiempo transcurrido
            # Si no hay CSV, mantener el status basado en start_time (live si ya empezó, upcoming si no)

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

            # Derive name from match_id: "team1-team2-apuestas-123" → "Team1 - Team2"
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

    return games


def _read_csv_rows(csv_path: Path) -> list[dict]:
    """Lee todas las filas de un CSV."""
    if not csv_path.exists():
        return []
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _normalize_halftime_minutes(rows: list[dict]) -> list[dict]:
    """Cap first-half injury-time minutes at 45.

    Betfair's match clock runs continuously past 45 during first-half stoppage
    time (e.g. shows 46, 47 … 64) instead of the UEFA "45+N" format, then
    resets to 45 at second-half kick-off.  This creates duplicate minute values
    (e.g. minute 50 appears once in first-half added time and once in the
    second half), which confuses strategy filters like Drift V4 (> minute 45).

    Fix: any `en_juego` row recorded *before* the first `descanso` row whose
    minute exceeds 45 is capped at 45.

    Only applied when at least one `descanso` row exists — for matches where
    the half-time interval was never captured we leave minutes unchanged to
    avoid incorrectly capping second-half data.
    """
    has_descanso = any(
        r.get("estado_partido", "").strip().lower() == "descanso" for r in rows
    )
    if not has_descanso:
        return rows  # Cannot detect boundary safely — leave as-is

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
    """Carga detalle completo de un partido: últimas capturas, quality, gaps."""
    csv_path = _resolve_csv_path(match_id)
    rows = _read_csv_rows(csv_path)

    if not rows:
        return {"match_id": match_id, "rows": 0, "captures": [], "quality": 0, "gaps": []}

    # Últimas 10 capturas
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
    """Carga datos de momentum para gráfico."""
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
    """Carga todas las estadísticas del último row del CSV."""
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
    Returns NEW dicts — does NOT mutate originals.
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
_analytics_cache: dict = {}
_analytics_cache_time: float = 0
_ANALYTICS_CACHE_TTL = 300  # 5 minutes
# Result cache: stores computed results of analytics functions
_result_cache: dict = {}
_result_cache_time: float = 0


def clear_analytics_cache():
    """Clear analytics cache to force reload of data."""
    global _analytics_cache, _analytics_cache_time, _result_cache, _result_cache_time
    _analytics_cache = {}
    _analytics_cache_time = 0
    _result_cache = {}
    _result_cache_time = 0


def _get_cached_finished_data() -> list[dict]:
    """Get all finished matches with pre-loaded CSV rows. Cached for 5 min."""
    global _analytics_cache, _analytics_cache_time, _result_cache, _result_cache_time
    import time as _time

    now = _time.time()
    if _analytics_cache and (now - _analytics_cache_time) < _ANALYTICS_CACHE_TTL:
        return _analytics_cache.get("finished", [])

    # Rebuild cache - also invalidate result cache
    _result_cache = {}
    _result_cache_time = now

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

    _analytics_cache = {"finished": finished}
    _analytics_cache_time = now
    return finished


def _cached_result(key: str):
    """Decorator to cache the result of an analytics function."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            global _result_cache
            if key in _result_cache:
                return _result_cache[key]
            result = fn(*args, **kwargs)
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
    E.g. missing=[4,8,9] → segments=[1,2] → avg=1.5
    """
    minutes_captured = set()
    descanso_minutes = set()

    for row in rows:
        m = row.get("minuto", "")
        if not m:
            continue  # pre_partido or rows without minute — skip
        try:
            minute = int(float(str(m).replace("'", "").strip()))
        except (ValueError, AttributeError):
            continue

        if minute < 1 or minute > 90:
            continue  # extra time etc. — outside scope

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


@_cached_result("quality_distribution")
def analyze_quality_distribution() -> dict:
    """Aggregate quality metrics across all finished matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "avg_quality": 0,
            "total_matches": 0,
            "quality_ranges": [],
            "bins": []
        }

    qualities = []
    bins_data = {
        "0-20": [], "20-40": [], "40-60": [], "60-80": [], "80-100": []
    }

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        quality = _calculate_match_quality(rows)
        qualities.append(quality)

        # Classify into bins
        if quality < 20:
            bins_data["0-20"].append(match["match_id"])
        elif quality < 40:
            bins_data["20-40"].append(match["match_id"])
        elif quality < 60:
            bins_data["40-60"].append(match["match_id"])
        elif quality < 80:
            bins_data["60-80"].append(match["match_id"])
        else:
            bins_data["80-100"].append(match["match_id"])

    avg_quality = round(sum(qualities) / len(qualities), 1) if qualities else 0

    # Quality ranges count
    quality_ranges = [
        {"range": "0-20%", "count": len(bins_data["0-20"])},
        {"range": "20-40%", "count": len(bins_data["20-40"])},
        {"range": "40-60%", "count": len(bins_data["40-60"])},
        {"range": "60-80%", "count": len(bins_data["60-80"])},
        {"range": "80-100%", "count": len(bins_data["80-100"])},
    ]

    # Bins for histogram
    bins = [
        {"label": "0-20%", "count": len(bins_data["0-20"]), "matches": bins_data["0-20"]},
        {"label": "20-40%", "count": len(bins_data["20-40"]), "matches": bins_data["20-40"]},
        {"label": "40-60%", "count": len(bins_data["40-60"]), "matches": bins_data["40-60"]},
        {"label": "60-80%", "count": len(bins_data["60-80"]), "matches": bins_data["60-80"]},
        {"label": "80-100%", "count": len(bins_data["80-100"]), "matches": bins_data["80-100"]},
    ]

    return {
        "avg_quality": avg_quality,
        "total_matches": len(finished_matches),
        "quality_ranges": quality_ranges,
        "bins": bins
    }


@_cached_result("gaps_distribution")
def analyze_gaps_distribution() -> dict:
    """Analyze capture gaps across all matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "avg_gaps": 0,
            "max_gaps": 0,
            "distribution": []
        }

    all_gaps = []
    gap_counts = {}

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        gaps = _calculate_match_gaps(rows)
        all_gaps.append(gaps)

        # Count matches by gap count
        gap_counts[gaps] = gap_counts.get(gaps, 0) + 1

    avg_gaps = round(sum(all_gaps) / len(all_gaps), 1) if all_gaps else 0
    max_gaps = max(all_gaps) if all_gaps else 0

    # Distribution
    distribution = [
        {"gap_count": gap, "match_count": count}
        for gap, count in sorted(gap_counts.items())
    ]

    return {
        "avg_gaps": avg_gaps,
        "max_gaps": max_gaps,
        "distribution": distribution
    }


@_cached_result("stats_coverage")
def analyze_stats_coverage() -> dict:
    """Calculate coverage percentage for each stat field actually used by active strategies."""
    # Stats and odds that gate or feed into signal detection across all active strategies:
    # Back Empate V2R:    xg + posesion + tiros     → back_draw
    # xG Underperf BASE: xg + tiros_puerta          → back_over*
    # Goal Clustering V2: tiros_puerta              → back_over*
    # Pressure Cooker V1: (score-based)             → back_over*
    # Tarde Asia V1:      (time/league)             → back_over25
    # Odds Drift V1:      (odds-only)               → back_home / back_away
    # Momentum × xG V1:  xg + tiros_puerta          → back_home / back_away
    # Synthetic attrs (pressure_index, momentum_gap, opta_gap): corners, momentum, opta_points
    STRATEGY_STAT_COLUMNS = [
        # --- Stats ---
        "xg_local", "xg_visitante",
        "posesion_local", "posesion_visitante",
        "tiros_local", "tiros_visitante",
        "tiros_puerta_local", "tiros_puerta_visitante",
        "corners_local", "corners_visitante",
        "momentum_local", "momentum_visitante",
        "opta_points_local", "opta_points_visitante",
        # --- Cuotas (mercados en los que se apuesta) ---
        "back_draw",                                          # Back Empate
        "back_home", "back_away",                            # Odds Drift, Momentum xG
        "back_over05", "back_over15", "back_over25",         # Over markets
        "back_over35", "back_over45",                        # Over markets (alta goleada)
    ]

    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {"fields": []}

    # Count non-null values for each stat column
    field_counts = {col: {"filled": 0, "total": 0} for col in STRATEGY_STAT_COLUMNS}

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        for row in rows:
            # Only count in-play rows
            estado = row.get("estado_partido", "").strip()
            if estado in ("pre_partido", ""):
                continue
            for col in STRATEGY_STAT_COLUMNS:
                field_counts[col]["total"] += 1
                val = row.get(col, "")
                if val and val.strip() not in ("", "N/A", "None"):
                    field_counts[col]["filled"] += 1

    # Calculate coverage percentage
    fields = []
    for col, counts in field_counts.items():
        coverage_pct = round(counts["filled"] / counts["total"] * 100, 1) if counts["total"] > 0 else 0
        fields.append({
            "name": col,
            "coverage_pct": coverage_pct
        })

    # Sort by coverage (lowest first to highlight problems)
    fields.sort(key=lambda x: x["coverage_pct"])

    return {"fields": fields}


def get_low_quality_matches(threshold: int = 50) -> list[dict]:
    """Return matches below quality threshold (for display only)."""
    finished_matches = _get_all_finished_matches()

    low_quality = []
    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        quality = _calculate_match_quality(rows)
        gaps = _calculate_match_gaps(rows)

        if quality < threshold:
            low_quality.append({
                "match_id": match["match_id"],
                "name": match["name"],
                "quality": quality,
                "total_captures": len(rows),
                "gap_count": gaps
            })

    # Sort by quality (worst first)
    low_quality.sort(key=lambda x: x["quality"])

    return low_quality


@_cached_result("odds_coverage")
def analyze_odds_coverage() -> dict:
    """Analyze odds scraping coverage across all finished matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "avg_coverage": 0,
            "total_matches": 0,
            "no_odds": 0,
            "partial_odds": 0,
            "good_odds": 0,
            "total_outlier_matches": 0,
            "bins": [],
            "matches": [],
        }

    match_list = []
    coverages = []

    for match in finished_matches:
        # Only include matches with at least one 'finalizado' row.
        # Many matches revert to 'pre_partido' or 'en_juego' as their last row
        # after Betfair closes the market, so we can't rely on the last row alone.
        _rows = match.get("rows", [])
        if not any(r.get("estado_partido", "").strip() == "finalizado" for r in _rows):
            continue

        # Use precomputed stats from cache (raw rows before outlier cleaning)
        total         = match.get("raw_total_rows", len(match.get("rows") or []))
        with_odds     = match.get("raw_with_odds", 0)
        # Coverage = rows_with_odds out of 90 expected match minutes (capped at 100%).
        # Using total_rows as denominator was misleading: 1 row with odds / 1 total = 100%
        # even when 90 minutes of data are missing.
        pct           = round(min(with_odds / 90 * 100, 100.0), 1)
        outlier_count = match.get("back_home_outliers", 0)

        raw_min_bh = match.get("min_back_home")
        raw_max_bh = match.get("max_back_home")
        coverages.append(pct)
        match_list.append({
            "match_id":       match["match_id"],
            "name":           match["name"],
            "start_time":     match.get("start_time"),
            "kickoff_time":   match.get("kickoff_time"),
            "coverage_pct":   pct,
            "rows_with_odds": with_odds,
            "total_rows":     total,
            "outlier_count":  outlier_count,
            "min_back_home":  round(raw_min_bh, 2) if raw_min_bh is not None else None,
            "max_back_home":  round(raw_max_bh, 2) if raw_max_bh is not None else None,
            "gap_count":      match.get("gap_count", 0),
            "avg_gap_size":   match.get("avg_gap_size", 0.0),
        })

    # Sort by coverage ascending (worst first), then by outlier_count descending
    match_list.sort(key=lambda x: (x["coverage_pct"], -x["outlier_count"]))

    avg_coverage = round(sum(coverages) / len(coverages), 1) if coverages else 0
    no_odds = sum(1 for p in coverages if p == 0)
    partial_odds = sum(1 for p in coverages if 0 < p < 80)
    good_odds = sum(1 for p in coverages if p >= 80)

    bins = [
        {"label": "0%",    "count": sum(1 for p in coverages if p == 0)},
        {"label": "1-25%", "count": sum(1 for p in coverages if 0 < p <= 25)},
        {"label": "26-50%","count": sum(1 for p in coverages if 25 < p <= 50)},
        {"label": "51-75%","count": sum(1 for p in coverages if 50 < p <= 75)},
        {"label": "76-99%","count": sum(1 for p in coverages if 75 < p < 100)},
        {"label": "100%",  "count": sum(1 for p in coverages if p == 100)},
    ]

    return {
        "avg_coverage": avg_coverage,
        "total_matches": len(finished_matches),
        "no_odds": no_odds,
        "partial_odds": partial_odds,
        "good_odds": good_odds,
        "bins": bins,
        "matches": match_list,
        "total_outlier_matches": sum(1 for m in match_list if m["outlier_count"] > 0),
    }


@_cached_result("momentum_patterns")
def analyze_momentum_patterns() -> dict:
    """Find momentum comeback and swing patterns."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "avg_swing": 0,
            "comeback_frequency": 0,
            "top_swings": []
        }

    all_swings = []
    top_swings = []

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows:
            continue

        # Extract momentum values
        home_momentum_vals = []
        away_momentum_vals = []
        for row in rows:
            home_mom = _to_float(row.get("momentum_local", ""))
            away_mom = _to_float(row.get("momentum_visitante", ""))
            if home_mom is not None:
                home_momentum_vals.append(home_mom)
            if away_mom is not None:
                away_momentum_vals.append(away_mom)

        # Calculate max swing (difference between consecutive momentum values)
        max_swing = 0
        if home_momentum_vals and len(home_momentum_vals) > 1:
            for i in range(1, len(home_momentum_vals)):
                prev_home = home_momentum_vals[i-1]
                curr_home = home_momentum_vals[i]
                prev_away = away_momentum_vals[i-1] if i-1 < len(away_momentum_vals) else 0
                curr_away = away_momentum_vals[i] if i < len(away_momentum_vals) else 0

                delta_home = abs(curr_home - prev_home)
                delta_away = abs(curr_away - prev_away)
                swing = max(delta_home, delta_away)
                max_swing = max(max_swing, swing)

        all_swings.append(max_swing)
        top_swings.append({
            "match_id": match["match_id"],
            "name": match["name"],
            "swing": round(max_swing, 1)
        })

    avg_swing = round(sum(all_swings) / len(all_swings), 1) if all_swings else 0

    # Sort top swings
    top_swings.sort(key=lambda x: x["swing"], reverse=True)

    return {
        "avg_swing": avg_swing,
        "comeback_frequency": 0,  # Would need HT score data to calculate properly
        "top_swings": top_swings[:10]
    }


@_cached_result("xg_accuracy")
def analyze_xg_accuracy() -> dict:
    """Correlate xG with actual goal outcomes."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "correlation": 0,
            "avg_accuracy": 0,
            "scatter_data": []
        }

    scatter_data = []

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows:
            continue

        last_row = rows[-1]
        xg_home = _to_float(last_row.get("xg_local", ""))
        xg_away = _to_float(last_row.get("xg_visitante", ""))
        goals_home_str = last_row.get("goles_local", "").strip()
        goals_away_str = last_row.get("goles_visitante", "").strip()

        try:
            goals_home = int(goals_home_str) if goals_home_str else None
            goals_away = int(goals_away_str) if goals_away_str else None
        except ValueError:
            goals_home = None
            goals_away = None

        if xg_home is not None and goals_home is not None:
            scatter_data.append({
                "xg": xg_home,
                "actual": goals_home,
                "match_id": match["match_id"],
                "team": "home"
            })

        if xg_away is not None and goals_away is not None:
            scatter_data.append({
                "xg": xg_away,
                "actual": goals_away,
                "match_id": match["match_id"],
                "team": "away"
            })

    # Calculate Pearson correlation
    correlation = 0
    if len(scatter_data) > 1:
        xg_vals = [d["xg"] for d in scatter_data]
        actual_vals = [d["actual"] for d in scatter_data]

        # Simple Pearson correlation
        n = len(xg_vals)
        sum_xg = sum(xg_vals)
        sum_actual = sum(actual_vals)
        sum_xg_sq = sum(x**2 for x in xg_vals)
        sum_actual_sq = sum(a**2 for a in actual_vals)
        sum_xg_actual = sum(xg_vals[i] * actual_vals[i] for i in range(n))

        numerator = n * sum_xg_actual - sum_xg * sum_actual
        denominator_xg = n * sum_xg_sq - sum_xg**2
        denominator_actual = n * sum_actual_sq - sum_actual**2

        if denominator_xg > 0 and denominator_actual > 0:
            correlation = numerator / (denominator_xg * denominator_actual)**0.5
            correlation = round(correlation, 3)

    # Average accuracy (absolute difference)
    accuracies = [abs(d["xg"] - d["actual"]) for d in scatter_data]
    avg_accuracy = round(sum(accuracies) / len(accuracies), 2) if accuracies else 0

    return {
        "correlation": correlation,
        "avg_accuracy": avg_accuracy,
        "scatter_data": scatter_data
    }


@_cached_result("odds_movements")
def analyze_odds_movements() -> dict:
    """Analyze betting odds drift and contraction patterns."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "avg_drift": 0,
            "drift_by_minute": [],
            "top_movements": []
        }

    top_movements = []

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows or len(rows) < 2:
            continue

        first_row = rows[0]
        last_row = rows[-1]

        # Calculate drift for back_home odds
        opening_home = _to_float(first_row.get("back_home", ""))
        closing_home = _to_float(last_row.get("back_home", ""))

        if opening_home and closing_home and opening_home > 0:
            drift_pct = round(((closing_home - opening_home) / opening_home) * 100, 1)
            movement = abs(drift_pct)

            top_movements.append({
                "match_id": match["match_id"],
                "name": match["name"],
                "movement": movement,
                "drift_pct": drift_pct
            })

    # Sort by movement magnitude
    top_movements.sort(key=lambda x: x["movement"], reverse=True)

    avg_drift = round(sum(m["movement"] for m in top_movements) / len(top_movements), 1) if top_movements else 0

    return {
        "avg_drift": avg_drift,
        "drift_by_minute": [],  # Would need minute-by-minute aggregation
        "top_movements": top_movements[:10]
    }


@_cached_result("over_under_patterns")
def analyze_over_under_patterns() -> dict:
    """Analyze Over/Under line hit rates."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "hit_rates": [],
            "minute_probabilities": []
        }

    lines = [0.5, 1.5, 2.5, 3.5, 4.5]
    line_hits = {line: 0 for line in lines}
    total_matches = 0

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows:
            continue

        last_row = rows[-1]
        goals_home_str = last_row.get("goles_local", "").strip()
        goals_away_str = last_row.get("goles_visitante", "").strip()

        # Skip matches with missing goal data (don't treat as 0-0)
        if not goals_home_str or not goals_away_str:
            continue

        try:
            goals_home = int(goals_home_str)
            goals_away = int(goals_away_str)
            total_goals = goals_home + goals_away

            for line in lines:
                if total_goals > line:
                    line_hits[line] += 1

            total_matches += 1
        except ValueError:
            continue

    # Calculate hit rates
    hit_rates = []
    for line in lines:
        hit_rate = round(line_hits[line] / total_matches * 100, 1) if total_matches > 0 else 0
        hit_rates.append({
            "line": f"Over {line}",
            "hit_rate": hit_rate
        })

    return {
        "hit_rates": hit_rates,
        "minute_probabilities": []  # Would need minute-by-minute analysis
    }


@_cached_result("stat_correlations")
def calculate_stat_correlations() -> dict:
    """Calculate correlations between key match statistics."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {
            "matrix": [],
            "top_correlations": []
        }

    # Stat pairs to analyze
    stat_pairs = [
        ("posesion_local", "xg_local"),
        ("corners_local", "xg_local"),
        ("tiros_local", "xg_local"),
        ("momentum_local", "xg_local"),
        ("dangerous_attacks_local", "xg_local"),
    ]

    correlations = []

    for stat1, stat2 in stat_pairs:
        values1 = []
        values2 = []

        for match in finished_matches:
            rows = match.get("rows") or _read_csv_rows(match["csv_path"])
            if not rows:
                continue

            last_row = rows[-1]
            val1 = _to_float(last_row.get(stat1, ""))
            val2 = _to_float(last_row.get(stat2, ""))

            if val1 is not None and val2 is not None:
                values1.append(val1)
                values2.append(val2)

        # Calculate correlation
        if len(values1) > 1:
            n = len(values1)
            sum1 = sum(values1)
            sum2 = sum(values2)
            sum1_sq = sum(x**2 for x in values1)
            sum2_sq = sum(x**2 for x in values2)
            sum_product = sum(values1[i] * values2[i] for i in range(n))

            numerator = n * sum_product - sum1 * sum2
            denom1 = n * sum1_sq - sum1**2
            denom2 = n * sum2_sq - sum2**2

            if denom1 > 0 and denom2 > 0:
                corr = numerator / (denom1 * denom2)**0.5
                correlations.append({
                    "stat1": stat1,
                    "stat2": stat2,
                    "correlation": round(corr, 3)
                })

    # Top correlations (by absolute value)
    top_correlations = sorted(
        [{"pair": f"{c['stat1']} vs {c['stat2']}", "value": c["correlation"]} for c in correlations],
        key=lambda x: abs(x["value"]),
        reverse=True
    )

    return {
        "matrix": correlations,
        "top_correlations": top_correlations
    }


def analyze_strategy_back_draw_00(min_dur: int = 1) -> dict:
    """Analyze the 'Back Draw at 0-0 from min 30' strategy across all finished matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {"total_matches": 0, "with_trigger": 0, "bets": [], "summary": {}}

    bets = []
    matches_with_data = 0

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows or len(rows) < 5:
            continue

        matches_with_data += 1

        # Find first row where min >= 30 and score is 0-0, then check persistence
        trigger_row = None
        trigger_idx = None
        for ri, row in enumerate(rows):
            minuto = _to_float(row.get("minuto", ""))
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            if minuto is not None and gl is not None and gv is not None:
                if minuto >= 30 and int(gl) == 0 and int(gv) == 0:
                    # Check persistence: score must stay 0-0 for min_dur consecutive rows
                    def _still_00(r):
                        _gl = _to_float(r.get("goles_local", ""))
                        _gv = _to_float(r.get("goles_visitante", ""))
                        return _gl is not None and _gv is not None and int(_gl) == 0 and int(_gv) == 0
                    entry_row = _check_min_dur(rows, ri, min_dur, _still_00)
                    if entry_row is not None:
                        trigger_row = entry_row
                        trigger_idx = rows.index(entry_row)
                    break

        if trigger_row is None:
            continue

        # Extract in-play data at trigger
        back_draw = _to_float(trigger_row.get("back_draw", ""))
        xg_l = _to_float(trigger_row.get("xg_local", ""))
        xg_v = _to_float(trigger_row.get("xg_visitante", ""))
        xg_total = ((xg_l or 0) + (xg_v or 0)) if (xg_l is not None or xg_v is not None) else None
        xg_max = max(xg_l or 0, xg_v or 0) if (xg_l is not None or xg_v is not None) else None

        sot_l = _to_float(trigger_row.get("tiros_puerta_local", ""))
        sot_v = _to_float(trigger_row.get("tiros_puerta_visitante", ""))
        sot_total = (int(sot_l or 0) + int(sot_v or 0)) if (sot_l is not None or sot_v is not None) else None

        poss_l = _to_float(trigger_row.get("posesion_local", ""))
        poss_v = _to_float(trigger_row.get("posesion_visitante", ""))
        poss_diff = abs((poss_l or 50) - (poss_v or 50)) if (poss_l is not None or poss_v is not None) else None

        shots_l = _to_float(trigger_row.get("tiros_local", ""))
        shots_v = _to_float(trigger_row.get("tiros_visitante", ""))
        shots_total = (int(shots_l or 0) + int(shots_v or 0)) if (shots_l is not None or shots_v is not None) else None

        minuto_trigger = _to_float(trigger_row.get("minuto", ""))
        bfed = _to_float(trigger_row.get("BFED", "")) or _to_float(trigger_row.get("bfed_prematch", ""))

        # Final result — use last row with valid scores (skip trailing pre_partido rows)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))
        if gl_final is None or gv_final is None:
            continue

        draw_won = int(gl_final) == int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Stability + conservative odds (min in window)
        _stab_count, _cons_odds = _count_odds_stability(rows, trigger_idx, "back_draw", back_draw or 0)

        # P/L calculation (stake 10, 5% commission on winnings)
        stake = 10
        if draw_won and back_draw:
            pl = round((back_draw - 1) * stake * 0.95, 2)
            pl_conservative = round((_cons_odds - 1) * stake * 0.95, 2)
        else:
            pl = -stake
            pl_conservative = -stake

        # Check strategy filters
        passes_xg_05 = xg_total is not None and xg_total < 0.5
        passes_xg_06 = xg_total is not None and xg_total < 0.6
        passes_poss_20 = poss_diff is not None and poss_diff < 20
        passes_poss_25 = poss_diff is not None and poss_diff < 25
        passes_shots = shots_total is not None and shots_total < 8

        passes_v2 = passes_xg_05 and passes_poss_20 and passes_shots
        passes_v15 = passes_xg_06 and passes_poss_25  # V1.5: xG<0.6 + PD<25%
        passes_v2r = passes_xg_06 and passes_poss_20 and passes_shots  # V2r: xG<0.6 + PD<20% + shots<8

        # V3: V1.5 + synthetic filters (xG dominance asymmetry + low visitor pressure)
        synth = _compute_synthetic_at_trigger(rows, trigger_idx)
        xg_dom = synth.get("xg_dominance")
        press_v = synth.get("pressure_index_v")
        passes_v3 = (
            passes_v15
            and xg_dom is not None
            and (xg_dom > 0.55 or xg_dom < 0.45)
            and (press_v is None or press_v < 0.5)
        )

        # V4: V2r + Opta equilibrium (|opta_gap| <= 10)
        opta_l_tr = _to_float(trigger_row.get("opta_points_local", ""))
        opta_v_tr = _to_float(trigger_row.get("opta_points_visitante", ""))
        opta_gap_ok = (
            opta_l_tr is not None and opta_v_tr is not None
            and abs(opta_l_tr - opta_v_tr) <= 10
        )
        passes_v4 = passes_v2r and opta_gap_ok

        bets.append({
            "match": match["name"],
            "match_id": match["match_id"],
            "minuto": minuto_trigger,
            "back_draw": round(back_draw, 2) if back_draw else None,
            "lay_trigger": _to_float(trigger_row.get("lay_draw", "")) or None,
            "xg_total": round(xg_total, 2) if xg_total is not None else None,
            "xg_max": round(xg_max, 2) if xg_max is not None else None,
            "sot_total": sot_total,
            "poss_diff": round(poss_diff, 1) if poss_diff is not None else None,
            "shots_total": shots_total,
            "bfed_prematch": bfed,
            "ft_score": ft_score,
            "won": draw_won,
            "pl": pl,
            "pl_conservative": pl_conservative,
            "conservative_odds": round(_cons_odds, 2),
            "passes_v2": passes_v2,
            "passes_v15": passes_v15,
            "passes_v2r": passes_v2r,
            "passes_v3": passes_v3,
            "passes_v4": passes_v4,
            "synth_xg_dominance": xg_dom,
            "synth_pressure_index_v": press_v,
            "stability_count": _stab_count,
            "timestamp_utc": trigger_row.get("timestamp_utc", ""),
            "País": trigger_row.get("País", "Desconocido"),
            "Liga": trigger_row.get("Liga", "Desconocida"),
        })

    # Summary stats helper
    def _make_summary(subset):
        n = len(subset)
        w = sum(1 for b in subset if b["won"])
        pl = sum(b["pl"] for b in subset)
        return {
            "bets": n,
            "wins": w,
            "win_pct": round(w / n * 100, 1) if n else 0,
            "pl": round(pl, 2),
            "roi": round(pl / (n * 10) * 100, 1) if n else 0,
        }

    return {
        "total_matches": matches_with_data,
        "with_trigger": len(bets),
        "summary": {
            "base": _make_summary(bets),
            "v15": _make_summary([b for b in bets if b["passes_v15"]]),
            "v2": _make_summary([b for b in bets if b["passes_v2"]]),
            "v2r": _make_summary([b for b in bets if b["passes_v2r"]]),
            "v4": _make_summary([b for b in bets if b.get("passes_v4")]),
        },
        "bets": bets,
    }


# ── xG Underperformance Strategy ────────────────────────────────────────

def _get_over_odds_field(total_goals: int) -> str:
    """Return CSV column name for Back Over (total_goals + 0.5)."""
    return {0: "back_over05", 1: "back_over15", 2: "back_over25",
            3: "back_over35", 4: "back_over45"}.get(total_goals, "")


def calculate_time_score_risk(
    strategy: str,
    minute: float,
    home_score: int,
    away_score: int,
    dominant_team: str
) -> dict:
    """
    Calcula el nivel de riesgo de una apuesta basándose en tiempo restante y marcador.

    Solo aplica a estrategias de resultado final (momentum_xg, odds_drift) cuando el
    equipo sobre el que apostamos va perdiendo.

    Reglas de riesgo:
    - HIGH: Quedan <20 min y el equipo va perdiendo ≥2 goles
    - HIGH: Quedan <15 min y el equipo va perdiendo ≥1 gol
    - MEDIUM: Quedan <25 min y el equipo va perdiendo ≥2 goles
    - MEDIUM: Quedan <20 min y el equipo va perdiendo ≥1 gol
    - NONE: Otros casos

    Args:
        strategy: Nombre de la estrategia (e.g., "momentum_xg_v1", "odds_drift")
        minute: Minuto actual del partido
        home_score: Goles del equipo local
        away_score: Goles del equipo visitante
        dominant_team: "Home"/"Local" o "Away"/"Visitante"

    Returns:
        {
            "has_risk": bool,
            "risk_level": "none" | "medium" | "high",
            "risk_reason": str,
            "time_remaining": int,
            "deficit": int
        }
    """
    # Solo aplica a estrategias de resultado final
    strategy_lower = strategy.lower()
    if not any(s in strategy_lower for s in ["momentum_xg", "odds_drift"]):
        return {
            "has_risk": False,
            "risk_level": "none",
            "risk_reason": "",
            "time_remaining": int(90 - minute),
            "deficit": 0
        }

    time_remaining = 90 - minute

    # Calcular déficit del equipo sobre el que apostamos
    dominant_lower = dominant_team.lower()
    if dominant_lower in ["home", "local"]:
        deficit = away_score - home_score
    else:
        deficit = home_score - away_score

    # Si no va perdiendo, no hay riesgo
    if deficit <= 0:
        return {
            "has_risk": False,
            "risk_level": "none",
            "risk_reason": "",
            "time_remaining": int(time_remaining),
            "deficit": deficit
        }

    # Evaluar nivel de riesgo
    risk_level = "none"
    risk_reason = ""

    # RIESGO ALTO
    if time_remaining < 20 and deficit >= 2:
        risk_level = "high"
        risk_reason = f"ALTO RIESGO: Quedan {int(time_remaining)} min para remontar {deficit} goles. Probabilidad muy baja."
    elif time_remaining < 15 and deficit >= 1:
        risk_level = "high"
        risk_reason = f"ALTO RIESGO: Quedan {int(time_remaining)} min para remontar {deficit} gol. Tiempo muy ajustado."

    # RIESGO MEDIO
    elif time_remaining < 25 and deficit >= 2:
        risk_level = "medium"
        risk_reason = f"RIESGO MEDIO: Quedan {int(time_remaining)} min para remontar {deficit} goles. Complicado pero posible."
    elif time_remaining < 20 and deficit >= 1:
        risk_level = "medium"
        risk_reason = f"RIESGO MEDIO: Quedan {int(time_remaining)} min para remontar {deficit} gol. Tiempo limitado."

    has_risk = risk_level != "none"

    return {
        "has_risk": has_risk,
        "risk_level": risk_level,
        "risk_reason": risk_reason,
        "time_remaining": int(time_remaining),
        "deficit": deficit
    }


def analyze_strategy_xg_underperformance(min_dur: int = 1) -> dict:
    """Analyze the 'xG Underperformance - Back Over' strategy across all finished matches.

    Trigger: team xG - goals >= 0.5 AND team is currently LOSING.
    Bet: Back Over (total_goals_at_trigger + 0.5).
    """
    finished_matches = _get_all_finished_matches()
    if not finished_matches:
        return {"total_matches": 0, "with_trigger": 0, "bets": [], "summary": {}}

    bets = []
    matches_with_xg = 0

    for match in finished_matches:
        # Skip matches with corrupted Over/Under odds
        if match["match_id"] in CORRUPTED_OVER_MATCHES:
            continue

        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows or len(rows) < 5:
            continue

        # Final result — use last row with valid scores (skip trailing pre_partido rows)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))
        if gl_final is None or gv_final is None:
            continue
        ft_gl, ft_gv = int(gl_final), int(gv_final)
        ft_total = ft_gl + ft_gv
        ft_score = f"{ft_gl}-{ft_gv}"

        # Check match has xG data
        has_xg = any(_to_float(r.get("xg_local")) is not None for r in rows)
        if not has_xg:
            continue
        matches_with_xg += 1

        # One trigger per team per match
        triggered = {"home": False, "away": False}

        for ri, row in enumerate(rows):
            minuto = _to_float(row.get("minuto", ""))
            if minuto is None or minuto < 15:
                continue

            xg_h = _to_float(row.get("xg_local", ""))
            xg_a = _to_float(row.get("xg_visitante", ""))
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            if xg_h is None or xg_a is None or gl is None or gv is None:
                continue
            gl_i, gv_i = int(gl), int(gv)

            for team, team_xg, team_goals, opp_goals in [
                ("home", xg_h, gl_i, gv_i),
                ("away", xg_a, gv_i, gl_i),
            ]:
                if triggered[team]:
                    continue

                xg_excess = team_xg - team_goals
                if xg_excess < 0.5 or opp_goals <= team_goals:
                    continue

                # Check persistence: signal must hold for min_dur consecutive rows
                if min_dur > 1:
                    end_idx = ri + min_dur - 1
                    if end_idx >= len(rows):
                        continue  # not enough rows remaining
                    row = rows[end_idx]
                    # Re-read values from the entry row
                    _gl_e = _to_float(row.get("goles_local", ""))
                    _gv_e = _to_float(row.get("goles_visitante", ""))
                    _xg_h_e = _to_float(row.get("xg_local", ""))
                    _xg_a_e = _to_float(row.get("xg_visitante", ""))
                    if _gl_e is None or _gv_e is None or _xg_h_e is None or _xg_a_e is None:
                        continue
                    _team_xg_e = _xg_h_e if team == "home" else _xg_a_e
                    _team_goals_e = int(_gl_e) if team == "home" else int(_gv_e)
                    _opp_goals_e = int(_gv_e) if team == "home" else int(_gl_e)
                    if (_team_xg_e - _team_goals_e) < 0.5 or _opp_goals_e <= _team_goals_e:
                        continue  # signal broke
                    gl_i = int(_gl_e)
                    gv_i = int(_gv_e)
                    _min_e = _to_float(row.get("minuto", ""))
                    if _min_e is not None:
                        minuto = _min_e

                triggered[team] = True
                total_at_trigger = gl_i + gv_i
                score_at_trigger = f"{gl_i}-{gv_i}"

                # Team stats
                sfx = "_local" if team == "home" else "_visitante"
                sot_t = _to_float(row.get(f"tiros_puerta{sfx}", ""))
                sot_int = int(sot_t) if sot_t is not None else None
                poss_t = _to_float(row.get(f"posesion{sfx}", ""))
                shots_t = _to_float(row.get(f"tiros{sfx}", ""))
                shots_int = int(shots_t) if shots_t is not None else None

                # Over odds
                over_field = _get_over_odds_field(total_at_trigger)
                back_over = _to_float(row.get(over_field, "")) if over_field else None

                # SKIP: no registra apuesta si no hay cuota válida (evita won=1 con pl=-10)
                if not back_over or back_over <= 1:
                    continue

                # Win = at least 1 more goal scored
                more_goals = ft_total > total_at_trigger

                # P/L
                stake = 10
                if more_goals:
                    pl = round((back_over - 1) * stake * 0.95, 2)
                else:
                    pl = -stake

                passes_v2 = sot_int is not None and sot_int >= 2
                passes_v3 = passes_v2 and minuto < 70  # V3: V2 + entrada temprana

                _entry_idx = (ri + min_dur - 1) if min_dur > 1 else ri
                _stab_xg, _cons_xg = _count_odds_stability(rows, _entry_idx, over_field or "back_over25", back_over or 0)
                pl = round((back_over - 1) * stake * 0.95, 2) if more_goals else -stake
                pl_conservative = round((_cons_xg - 1) * stake * 0.95, 2) if more_goals else -stake
                bets.append({
                    "match": match["name"],
                    "match_id": match["match_id"],
                    "minuto": minuto,
                    "score_at_trigger": score_at_trigger,
                    "team": team,
                    "team_xg": round(team_xg, 2),
                    "team_goals": team_goals,
                    "xg_excess": round(xg_excess, 2),
                    "back_over_odds": round(back_over, 2) if back_over else None,
                    "lay_trigger": _to_float(row.get(over_field.replace("back_", "lay_"), "")) or None if over_field else None,
                    "over_line": f"Over {total_at_trigger + 0.5}",
                    "sot_team": sot_int,
                    "poss_team": round(poss_t, 1) if poss_t is not None else None,
                    "shots_team": shots_int,
                    "ft_score": ft_score,
                    "won": more_goals,
                    "pl": pl,
                    "pl_conservative": pl_conservative,
                    "conservative_odds": round(_cons_xg, 2),
                    "passes_v2": passes_v2,
                    "passes_v3": passes_v3,
                    "stability_count": _stab_xg,
                    "timestamp_utc": row.get("timestamp_utc", ""),
                    "País": row.get("País", "Desconocido"),
                    "Liga": row.get("Liga", "Desconocida"),
                })

    def _make_summary(subset):
        n = len(subset)
        w = sum(1 for b in subset if b["won"])
        total_pl = sum(b["pl"] for b in subset)
        return {
            "bets": n, "wins": w,
            "win_pct": round(w / n * 100, 1) if n else 0,
            "pl": round(total_pl, 2),
            "roi": round(total_pl / (n * 10) * 100, 1) if n else 0,
        }

    return {
        "total_matches": matches_with_xg,
        "with_trigger": len(bets),
        "summary": {
            "base": _make_summary(bets),
            "v2": _make_summary([b for b in bets if b["passes_v2"]]),
            "v3": _make_summary([b for b in bets if b["passes_v3"]]),
        },
        "bets": bets,
    }


# ── Odds Drift Contrarian Strategy ──────────────────────────────────────

def analyze_strategy_odds_drift(min_dur: int = 1) -> dict:
    """Analyze the 'Odds Drift Contrarian' strategy across all finished matches.

    Trigger: team's back odds increase >30% within 10 min AND team is currently WINNING.
    Bet: Back that team to win (Match Odds market).
    Versions:
      - V1 (base): drift >30% + winning
      - V2: V1 + goal advantage >= 2
      - V3: V1 + drift >= 100%
      - V4: V1 + odds <= 5 + minute > 45
    """
    finished_matches = _get_all_finished_matches()
    if not finished_matches:
        return {"total_matches": 0, "with_trigger": 0, "bets": [], "summary": {}}

    DRIFT_MIN = 0.30
    WINDOW_MIN = 10
    MIN_MINUTE = 5
    MAX_MINUTE = 80
    MIN_ODDS = 1.50
    MAX_ODDS = 30.0
    COMMISSION = 0.05
    STAKE = 10

    bets = []
    total_matches = 0

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows or len(rows) < 10:
            continue

        last_row = rows[-1]
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))
        if gl_final is None or gv_final is None:
            continue
        ft_gl, ft_gv = int(gl_final), int(gv_final)
        ft_score = f"{ft_gl}-{ft_gv}"
        total_matches += 1

        # Build list of (minuto, row, back_home, back_away, row_index) with valid data
        data_points = []
        for ri, row in enumerate(rows):
            m = _to_float(row.get("minuto", ""))
            if m is None:
                continue
            bh = _to_float(row.get("back_home", ""))
            ba = _to_float(row.get("back_away", ""))
            data_points.append((m, row, bh, ba, ri))

        triggered = {"home": False, "away": False}

        for idx in range(1, len(data_points)):
            curr_min, curr_row, curr_bh, curr_ba, curr_ri = data_points[idx]
            if curr_min < MIN_MINUTE or curr_min > MAX_MINUTE:
                continue

            gl = _to_float(curr_row.get("goles_local", ""))
            gv = _to_float(curr_row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            gl_i, gv_i = int(gl), int(gv)

            # Look back within window
            for prev_idx in range(idx - 1, -1, -1):
                prev_min, prev_row, prev_bh, prev_ba, _ = data_points[prev_idx]
                if curr_min - prev_min > WINDOW_MIN:
                    break
                if curr_min - prev_min < 2:
                    continue

                for team, prev_odds, curr_odds, team_goals, opp_goals in [
                    ("home", prev_bh, curr_bh, gl_i, gv_i),
                    ("away", prev_ba, curr_ba, gv_i, gl_i),
                ]:
                    if triggered[team]:
                        continue
                    if prev_odds is None or curr_odds is None or prev_odds <= 0:
                        continue

                    drift = (curr_odds - prev_odds) / prev_odds
                    if drift < DRIFT_MIN or curr_odds < MIN_ODDS or curr_odds > MAX_ODDS:
                        continue

                    # KEY: team must be WINNING
                    if team_goals <= opp_goals:
                        continue

                    # Min duration persistence: team must stay winning for min_dur rows
                    if min_dur > 1:
                        persist_ok = True
                        for pi in range(idx + 1, min(idx + min_dur, len(data_points))):
                            pr = data_points[pi][1]  # row
                            pg = _to_float(pr.get("goles_local" if team == "home" else "goles_visitante", ""))
                            po = _to_float(pr.get("goles_visitante" if team == "home" else "goles_local", ""))
                            if pg is None or po is None or int(pg) <= int(po):
                                persist_ok = False
                                break
                        if not persist_ok:
                            continue

                    triggered[team] = True
                    goal_diff = team_goals - opp_goals
                    score_at = f"{gl_i}-{gv_i}"

                    # Check if team wins the match
                    if team == "home":
                        won = ft_gl > ft_gv
                    else:
                        won = ft_gv > ft_gl

                    _drift_odds_col = "back_home" if team == "home" else "back_away"
                    _stab_drift, _cons_drift = _count_odds_stability(rows, curr_ri, _drift_odds_col, curr_odds or 0)
                    if won:
                        pl = round((curr_odds - 1) * STAKE * (1 - COMMISSION), 2)
                        pl_conservative = round((_cons_drift - 1) * STAKE * (1 - COMMISSION), 2)
                    else:
                        pl = -STAKE
                        pl_conservative = -STAKE

                    # Stats at trigger
                    sfx = "_local" if team == "home" else "_visitante"
                    osfx = "_visitante" if team == "home" else "_local"
                    sot_t = _to_float(curr_row.get(f"tiros_puerta{sfx}", ""))
                    poss_t = _to_float(curr_row.get(f"posesion{sfx}", ""))
                    shots_t = _to_float(curr_row.get(f"tiros{sfx}", ""))

                    # Version filters
                    passes_v2 = goal_diff >= 2
                    passes_v3 = drift >= 1.0  # drift >= 100%
                    passes_v4 = curr_odds <= 5.0 and curr_min > 45
                    passes_v5 = curr_odds <= 5.0  # V5: cap cuotas (sin filtro minuto)

                    # V6: V5 + momentum gap > 200 (100% WR in backtest)
                    synth = _compute_synthetic_at_trigger(rows, curr_ri)
                    mom_gap = synth.get("momentum_gap")
                    passes_v6 = passes_v5 and mom_gap is not None and mom_gap > 200

                    # Calcular riesgo por tiempo + marcador
                    risk_info = calculate_time_score_risk(
                        strategy="odds_drift",
                        minute=curr_min,
                        home_score=gl_i,
                        away_score=gv_i,
                        dominant_team=team
                    )

                    _drift_odds_col = "back_home" if team == "home" else "back_away"
                    _drift_lay_col = "lay_home" if team == "home" else "lay_away"
                    bets.append({
                        "match": match["name"],
                        "match_id": match["match_id"],
                        "minuto": curr_min,
                        "score_at_trigger": score_at,
                        "team": team,
                        "goal_diff": goal_diff,
                        "odds_before": round(prev_odds, 2),
                        "back_odds": round(curr_odds, 2),
                        "lay_trigger": _to_float(curr_row.get(_drift_lay_col, "")) or None,
                        "drift_pct": round(drift * 100, 1),
                        "sot_team": int(sot_t) if sot_t is not None else None,
                        "poss_team": round(poss_t, 1) if poss_t is not None else None,
                        "shots_team": int(shots_t) if shots_t is not None else None,
                        "ft_score": ft_score,
                        "won": won,
                        "pl": pl,
                        "pl_conservative": pl_conservative,
                        "conservative_odds": round(_cons_drift, 2),
                        "passes_v2": passes_v2,
                        "passes_v3": passes_v3,
                        "passes_v4": passes_v4,
                        "passes_v5": passes_v5,
                        "passes_v6": passes_v6,
                        "synth_momentum_gap": mom_gap,
                        "stability_count": _stab_drift,
                        "timestamp_utc": curr_row.get("timestamp_utc", ""),
                        "risk_level": risk_info["risk_level"],
                        "risk_reason": risk_info["risk_reason"],
                        "time_remaining": risk_info["time_remaining"],
                        "deficit": risk_info["deficit"],
                        "País": curr_row.get("País", "Desconocido"),
                        "Liga": curr_row.get("Liga", "Desconocida"),
                    })
                    break  # found trigger for this team at this row

            if triggered["home"] and triggered["away"]:
                break

    def _make_summary(subset):
        n = len(subset)
        w = sum(1 for b in subset if b["won"])
        total_pl = sum(b["pl"] for b in subset)
        return {
            "bets": n, "wins": w,
            "win_pct": round(w / n * 100, 1) if n else 0,
            "pl": round(total_pl, 2),
            "roi": round(total_pl / (n * 10) * 100, 1) if n else 0,
        }

    return {
        "total_matches": total_matches,
        "with_trigger": len(bets),
        "summary": {
            "v1": _make_summary(bets),
            "v2": _make_summary([b for b in bets if b["passes_v2"]]),
            "v3": _make_summary([b for b in bets if b["passes_v3"]]),
            "v4": _make_summary([b for b in bets if b["passes_v4"]]),
            "v5": _make_summary([b for b in bets if b["passes_v5"]]),
        },
        "bets": bets,
    }


# ── Cartera (Portfolio) ─────────────────────────────────────────────────

def analyze_cartera() -> dict:
    """Combined portfolio view of all strategies with flat and managed bankroll simulations."""
    import json as _json
    from api.config import load_config as _load_config
    cfg = _load_config()
    md = cfg.get("min_duration", {})

    # Manual cache key including min_duration values
    cache_key = f"cartera_{_json.dumps(md, sort_keys=True)}"
    if cache_key in _result_cache:
        return _result_cache[cache_key]

    draw_data = analyze_strategy_back_draw_00(min_dur=md.get("draw", 1))
    xg_data = analyze_strategy_xg_underperformance(min_dur=md.get("xg", 2))
    drift_data = analyze_strategy_odds_drift(min_dur=md.get("drift", 2))
    clustering_data = analyze_strategy_goal_clustering(min_dur=md.get("clustering", 4))
    pressure_data = analyze_strategy_pressure_cooker(min_dur=md.get("pressure", 2))
    tarde_asia_data = analyze_strategy_tarde_asia(min_dur=1)
    momentum_xg_v1_data = analyze_strategy_momentum_xg(version="v1", min_dur=1)
    momentum_xg_v2_data = analyze_strategy_momentum_xg(version="v2", min_dur=1)

    all_bets = []
    for b in draw_data.get("bets", []):
        all_bets.append({**b, "strategy": "back_draw_00", "strategy_label": "Back Empate"})
    for b in xg_data.get("bets", []):
        all_bets.append({**b, "strategy": "xg_underperformance", "strategy_label": "xG Underperf"})
    for b in drift_data.get("bets", []):
        all_bets.append({**b, "strategy": "odds_drift", "strategy_label": "Odds Drift"})
    for b in clustering_data.get("bets", []):
        all_bets.append({**b, "strategy": "goal_clustering", "strategy_label": "Goal Clustering"})
    for b in pressure_data.get("bets", []):
        all_bets.append({**b, "strategy": "pressure_cooker", "strategy_label": "Pressure Cooker"})
    for b in tarde_asia_data.get("bets", []):
        all_bets.append({**b, "strategy": "tarde_asia", "strategy_label": "Tarde Asia"})
    for b in momentum_xg_v1_data.get("bets", []):
        all_bets.append({**b, "strategy": "momentum_xg_v1", "strategy_label": "Momentum x xG V1"})
    for b in momentum_xg_v2_data.get("bets", []):
        all_bets.append({**b, "strategy": "momentum_xg_v2", "strategy_label": "Momentum x xG V2"})

    all_bets.sort(key=lambda x: x.get("timestamp_utc", ""))

    # Flat staking: 10 EUR per bet
    flat_cum = []
    flat_total = 0
    for b in all_bets:
        flat_total += b["pl"]
        flat_cum.append(round(flat_total, 2))

    # Managed bankroll: 500 EUR initial, 2% per bet
    initial_bankroll = 500
    pct = 0.02
    bankroll = initial_bankroll
    managed_cum = []
    managed_pls = []
    for b in all_bets:
        bet_size = round(bankroll * pct, 2)
        odds = b.get("back_draw") or b.get("back_over_odds") or b.get("over_odds") or 1
        if b["won"] and odds and odds > 1:
            profit = round((odds - 1) * bet_size * 0.95, 2)
        else:
            profit = -bet_size
        bankroll += profit
        managed_pls.append(profit)
        managed_cum.append(round(bankroll - initial_bankroll, 2))

    n = len(all_bets)
    flat_pl = round(sum(b["pl"] for b in all_bets), 2)
    managed_pl = managed_cum[-1] if managed_cum else 0

    def _strat_summary(subset):
        nn = len(subset)
        ww = sum(1 for b in subset if b["won"])
        pp = sum(b["pl"] for b in subset)
        return {"bets": nn, "wins": ww,
                "win_pct": round(ww / nn * 100, 1) if nn else 0,
                "pl": round(pp, 2),
                "roi": round(pp / (nn * 10) * 100, 1) if nn else 0}

    result = {
        "total_bets": n,
        "flat": {
            "pl": flat_pl,
            "roi": round(flat_pl / (n * 10) * 100, 1) if n else 0,
            "cumulative": flat_cum,
        },
        "managed": {
            "initial_bankroll": initial_bankroll,
            "bankroll_pct": round(pct * 100, 1),
            "final_bankroll": round(bankroll, 2),
            "pl": managed_pl,
            "roi": round(managed_pl / initial_bankroll * 100, 1) if initial_bankroll else 0,
            "cumulative": managed_cum,
        },
        "by_strategy": {
            "back_draw_00": _strat_summary([b for b in all_bets if b["strategy"] == "back_draw_00"]),
            "xg_underperformance": _strat_summary([b for b in all_bets if b["strategy"] == "xg_underperformance"]),
            "odds_drift": _strat_summary([b for b in all_bets if b["strategy"] == "odds_drift"]),
            "goal_clustering": _strat_summary([b for b in all_bets if b["strategy"] == "goal_clustering"]),
            "pressure_cooker": _strat_summary([b for b in all_bets if b["strategy"] == "pressure_cooker"]),
            "tarde_asia": _strat_summary([b for b in all_bets if b["strategy"] == "tarde_asia"]),
            "momentum_xg": _strat_summary([b for b in all_bets if b["strategy"] in ("momentum_xg_v1", "momentum_xg_v2")]),
        },
        "bets": all_bets,
    }
    _result_cache[cache_key] = result
    return result


# ── Cash-out simulation ─────────────────────────────────────────────────

_OVER_CO_COLS: dict[str, tuple[str, str]] = {
    "0.5": ("back_over05", "lay_over05"),
    "1.5": ("back_over15", "lay_over15"),
    "2.5": ("back_over25", "lay_over25"),
    "3.5": ("back_over35", "lay_over35"),
    "4.5": ("back_over45", "lay_over45"),
}


def _co_market_cols(bet: dict, strategy: str) -> tuple[str, str, float]:
    """Return (back_col, lay_col, back_odds) for the bet's market."""
    if strategy == "back_draw_00":
        return "back_draw", "lay_draw", bet.get("back_draw") or 0.0

    if strategy in ("xg_underperformance", "goal_clustering", "pressure_cooker", "tarde_asia"):
        over_line = bet.get("over_line", "")
        m = re.search(r"(\d+\.?\d+)", over_line or "")
        key = m.group(1) if m else ""
        bc, lc = _OVER_CO_COLS.get(key, ("", ""))
        return bc, lc, bet.get("back_over_odds") or 0.0

    if strategy == "odds_drift":
        team = bet.get("team", "")
        bc = "back_home" if team == "home" else "back_away"
        lc = "lay_home" if team == "home" else "lay_away"
        return bc, lc, bet.get("back_odds") or 0.0

    if strategy in ("momentum_xg_v1", "momentum_xg_v2"):
        dt = bet.get("dominant_team", "")
        bc = "back_home" if dt == "Local" else "back_away"
        lc = "lay_home" if dt == "Local" else "lay_away"
        return bc, lc, bet.get("back_odds") or 0.0

    return "", "", 0.0


def _get_trigger_score(rows: list, trigger_min: float) -> tuple:
    """Devuelve (goles_local, goles_visitante) en el CSV justo en trigger_min."""
    gl = gv = 0
    for row in rows:
        m = _to_float(row.get("minuto", ""))
        if m is not None and m <= trigger_min:
            g1 = _to_float(row.get("goles_local", ""))
            g2 = _to_float(row.get("goles_visitante", ""))
            if g1 is not None: gl = g1
            if g2 is not None: gv = g2
        else:
            break
    return gl, gv


def _is_adverse_goal(row: dict, strategy: str, team: str, gl_trigger: float, gv_trigger: float) -> bool:
    """True si en este row se ha producido un gol adverso para la apuesta.
    Solo aplica a apuestas de match odds (draw, home, away).
    Over bets: ningún gol es adverso (más goles = mejor para Over).
    """
    gl = _to_float(row.get("goles_local", "")) or 0
    gv = _to_float(row.get("goles_visitante", "")) or 0
    if strategy == "back_draw_00":
        return (gl + gv) > (gl_trigger + gv_trigger)  # cualquier gol perjudica el empate
    if strategy in ("momentum_xg_v1", "momentum_xg_v2"):
        if team == "Local": return gv > gv_trigger    # rival (visitante) marcó
        if team == "Away":  return gl > gl_trigger    # rival (local) marcó
    if strategy == "odds_drift":
        if team == "home":  return gv > gv_trigger    # visitante marcó
        if team == "away":  return gl > gl_trigger    # local marcó
    return False  # Over bets: nunca adverso


def _co_is_corrupted(row: dict, back_col: str, lay_col: str) -> bool:
    """True if row shows market suspension artifacts (inverted or extreme spread)."""
    bk = _to_float(row.get(back_col, ""))
    lk = _to_float(row.get(lay_col, ""))
    if bk is None or lk is None or bk <= 1.0 or lk <= 1.0:
        return True
    if lk < bk:
        return True  # inverted = suspension
    return (lk - bk) / bk > 0.5  # >50% spread = suspension


def _co_calc_pl(back_odds: float, lay_odds: float, stake: float = 10.0) -> float:
    """Cash-out P&L. Applies 5% Betfair commission only on profits."""
    gross = stake * (back_odds / lay_odds - 1)
    return round(gross * 0.95, 2) if gross > 0 else round(gross, 2)


def _config_label(config: dict) -> str:
    parts = []
    if config.get("cashout_lay_pct") is not None:
        parts.append(f"Fijo {config['cashout_lay_pct']}%")
    if config.get("adaptive_early_pct") is not None:
        parts.append(
            f"Adapt. {config['adaptive_early_pct']}%→{config['adaptive_late_pct']}% @{config['adaptive_split_min']}m"
        )
    if config.get("adverse_goal_stop"):
        parts.append("Gol adverso")
    if config.get("trailing_stop_pct") is not None:
        parts.append(f"Trailing {config['trailing_stop_pct']}%")
    return " + ".join(parts) if parts else "Sin CO"


def _simulate_config(
    bets: list,
    match_csv_cache: dict,
    *,
    cashout_lay_pct: float = None,
    adaptive_early_pct: float = None,
    adaptive_late_pct: float = None,
    adaptive_split_min: int = 70,
    adverse_goal_stop: bool = False,
    trailing_stop_pct: float = None,
) -> tuple:
    """Fast inner simulation loop for grid search. Uses pre-loaded CSV cache.
    Returns (pl_net, rescued_count, penalized_count, co_applied_count).
    """
    pl_total = 0.0
    rescued = penalized = co_applied = 0

    for bet in bets:
        strategy = bet.get("strategy", "")
        match_id = bet.get("match_id", "")
        trigger_min = bet.get("minuto") or 0
        original_pl = bet.get("pl", 0) or 0
        stake = bet.get("stake", 1.0) or 1.0

        back_col, lay_col, back_odds = _co_market_cols(bet, strategy)
        if not back_col or not lay_col or not back_odds:
            pl_total += original_pl
            continue

        rows = match_csv_cache.get(match_id, [])
        if not rows:
            pl_total += original_pl
            continue

        gl_trigger = gv_trigger = 0
        if adverse_goal_stop:
            gl_trigger, gv_trigger = _get_trigger_score(rows, trigger_min)
        team = bet.get("team") or bet.get("dominant_team")
        trail_min_lay = None
        best_row = None

        for row in rows:
            m = _to_float(row.get("minuto", ""))
            if m is None or m <= trigger_min:
                continue
            if _co_is_corrupted(row, back_col, lay_col):
                continue

            lay_val = _to_float(row.get(lay_col, ""))
            triggered = False

            if cashout_lay_pct is not None and lay_val:
                if lay_val >= back_odds * (1.0 + cashout_lay_pct / 100.0):
                    triggered = True

            if not triggered and adaptive_early_pct is not None and adaptive_late_pct is not None and lay_val:
                pct = adaptive_early_pct if m < adaptive_split_min else adaptive_late_pct
                if lay_val >= back_odds * (1.0 + pct / 100.0):
                    triggered = True

            if not triggered and adverse_goal_stop:
                if _is_adverse_goal(row, strategy, team, gl_trigger, gv_trigger):
                    triggered = True

            if trailing_stop_pct is not None and lay_val:
                if trail_min_lay is None or lay_val < trail_min_lay:
                    trail_min_lay = lay_val
                if not triggered:
                    if lay_val >= trail_min_lay * (1.0 + trailing_stop_pct / 100.0):
                        triggered = True

            if triggered:
                best_row = row
                break

        if best_row is None:
            pl_total += original_pl
            continue

        lay_odds = _to_float(best_row.get(lay_col, ""))
        if not lay_odds or lay_odds <= 1.0:
            pl_total += original_pl
            continue

        co_pl = _co_calc_pl(back_odds, lay_odds, stake)
        pl_total += co_pl
        co_applied += 1

        if original_pl < 0 and co_pl > original_pl:
            rescued += 1
        elif original_pl > 0 and co_pl < original_pl:
            penalized += 1

    return round(pl_total, 2), rescued, penalized, co_applied


def optimize_cashout_cartera(cartera_data: dict, top_n: int = 10) -> dict:
    """Grid search over CO modes to find best configuration.
    Reads each match CSV only once for efficiency.
    Returns top_n configs ranked by P/L net, plus other sorting options.
    """
    bets = cartera_data.get("bets", [])
    if not bets:
        return {"base_pl": 0.0, "results": []}

    # Build config grid
    configs: list[dict] = []

    # 1. Solo Fijo
    for pct in [5, 10, 15, 20, 25, 30, 40, 50]:
        configs.append({"cashout_lay_pct": pct})

    # 2. Solo Adaptativo
    for early in [15, 20, 25, 30]:
        for late in [5, 8, 12]:
            for split in [60, 70, 80]:
                configs.append({
                    "adaptive_early_pct": early,
                    "adaptive_late_pct": late,
                    "adaptive_split_min": split,
                })

    # 3. Solo Gol adverso
    configs.append({"adverse_goal_stop": True})

    # 4. Solo Trailing
    for trail in [5, 10, 15, 20, 25, 30]:
        configs.append({"trailing_stop_pct": trail})

    # 5. Gol adverso + Trailing
    for trail in [5, 10, 15, 20]:
        configs.append({"adverse_goal_stop": True, "trailing_stop_pct": trail})

    # 6. Fijo + Gol adverso
    for pct in [10, 15, 20, 25, 30]:
        configs.append({"cashout_lay_pct": pct, "adverse_goal_stop": True})

    # 7. Trailing + Fijo
    for pct in [15, 20, 25]:
        for trail in [10, 15, 20]:
            configs.append({"cashout_lay_pct": pct, "trailing_stop_pct": trail})

    # 8. Trailing + Gol adverso + Fijo
    for pct in [15, 20]:
        for trail in [10, 15]:
            configs.append({"cashout_lay_pct": pct, "adverse_goal_stop": True, "trailing_stop_pct": trail})

    # Pre-load all match CSVs (each read only once)
    match_csv_cache: dict = {}
    for bet in bets:
        match_id = bet.get("match_id", "")
        if match_id and match_id not in match_csv_cache:
            try:
                csv_path = _resolve_csv_path(match_id)
                match_csv_cache[match_id] = _read_csv_rows(csv_path)
            except Exception:
                match_csv_cache[match_id] = []

    base_pl = round(sum(b.get("pl", 0) or 0 for b in bets), 2)

    results = []
    for config in configs:
        pl_net, rescued, penalized, co_applied = _simulate_config(bets, match_csv_cache, **config)
        total_co = rescued + penalized
        rescue_ratio = round(rescued / total_co, 2) if total_co > 0 else 0.0
        results.append({
            "config": config,
            "label": _config_label(config),
            "pl_net": pl_net,
            "pl_improvement": round(pl_net - base_pl, 2),
            "rescued": rescued,
            "penalized": penalized,
            "co_applied": co_applied,
            "rescue_ratio": rescue_ratio,
        })

    results.sort(key=lambda x: x["pl_net"], reverse=True)
    return {
        "base_pl": base_pl,
        "total_configs_tested": len(configs),
        "results": results[:top_n],
    }


def simulate_cashout_cartera(
    cartera_data: dict,
    cashout_minute: int = None,
    *,
    cashout_lay_pct: float = None,
    adaptive_early_pct: float = None,
    adaptive_late_pct: float = None,
    adaptive_split_min: int = 70,
    adverse_goal_stop: bool = False,
    trailing_stop_pct: float = None,
) -> dict:
    """Apply cashout simulation to cartera data for ALL bets (winners and losers).

    cashout_minute == -1 → "Pesimista": worst lay odds in the full period
      (trigger_min, 90] — most conservative, models bad execution timing.
    cashout_minute > 0  → "Minuto": row closest to that minute (original).
    cashout_lay_pct     → "Lay%": first row where lay >= entry_back * (1 + lay_pct/100).
    adaptive_early_pct / adaptive_late_pct → "Adaptativo": threshold holgado antes de
      adaptive_split_min, ajustado después.
    adverse_goal_stop   → "Gol adverso": CO en el primer gol que perjudica la apuesta
      (solo back_draw_00, odds_drift, momentum_xg — Over bets ignoradas).
    trailing_stop_pct   → "Trailing": stop se mueve con el mínimo lay visto; dispara
      cuando lay sube trailing_stop_pct% sobre ese mínimo.

    Modos combinables: si varios están activos, gana el primero en dispararse.
    CO is applied unconditionally when triggered — no look-ahead bias.
    Winning bets where threshold is crossed will have their P/L reduced (premature exit).
    Returns a deep copy of cartera_data with modified pl values and
    recomputed cumulative arrays and strategy summaries.
    """
    import copy
    result = copy.deepcopy(cartera_data)
    bets = result.get("bets", [])
    stake = 10.0
    co_count = 0
    pessimistic = cashout_minute is not None and cashout_minute == -1

    # Determine if any new-style mode is active
    new_modes_active = (
        cashout_lay_pct is not None
        or (adaptive_early_pct is not None and adaptive_late_pct is not None)
        or adverse_goal_stop
        or trailing_stop_pct is not None
    )

    for bet in bets:

        strategy = bet.get("strategy", "")
        match_id = bet.get("match_id", "")
        trigger_min = bet.get("minuto") or 0

        back_col, lay_col, back_odds = _co_market_cols(bet, strategy)
        if not back_col or not lay_col or not back_odds:
            continue

        try:
            csv_path = _resolve_csv_path(match_id)
            rows = _read_csv_rows(csv_path)
        except Exception:
            continue
        if not rows:
            continue

        if new_modes_active:
            # Multi-mode combinable search: primero en dispararse gana
            gl_trigger, gv_trigger = _get_trigger_score(rows, trigger_min)
            team = bet.get("team") or bet.get("dominant_team")
            trail_min_lay = None
            best_row = None

            for row in rows:
                m = _to_float(row.get("minuto", ""))
                if m is None or m <= trigger_min:
                    continue
                if _co_is_corrupted(row, back_col, lay_col):
                    continue

                lay_val = _to_float(row.get(lay_col, ""))
                triggered = False

                # Modo 1: Fijo %
                if cashout_lay_pct is not None and lay_val:
                    if lay_val >= back_odds * (1.0 + cashout_lay_pct / 100.0):
                        triggered = True

                # Modo 2: Adaptativo (umbral diferente antes/después del split_min)
                if not triggered and adaptive_early_pct is not None and adaptive_late_pct is not None and lay_val:
                    pct = adaptive_early_pct if m < adaptive_split_min else adaptive_late_pct
                    if lay_val >= back_odds * (1.0 + pct / 100.0):
                        triggered = True

                # Modo 3: Gol adverso
                if not triggered and adverse_goal_stop:
                    if _is_adverse_goal(row, strategy, team, gl_trigger, gv_trigger):
                        triggered = True

                # Modo 4: Trailing stop (actualizar mínimo, luego comprobar trail)
                if trailing_stop_pct is not None and lay_val:
                    if trail_min_lay is None or lay_val < trail_min_lay:
                        trail_min_lay = lay_val
                    if not triggered:
                        trail_threshold = trail_min_lay * (1.0 + trailing_stop_pct / 100.0)
                        if lay_val >= trail_threshold:
                            triggered = True

                if triggered:
                    best_row = row
                    break

        elif pessimistic:
            # Worst lay odds (highest) in full post-signal window — conservative
            best_row = None
            worst_lay = -1.0
            for row in rows:
                m = _to_float(row.get("minuto", ""))
                if m is None or m <= trigger_min:
                    continue
                if _co_is_corrupted(row, back_col, lay_col):
                    continue
                lay_val = _to_float(row.get(lay_col, ""))
                if lay_val and lay_val > worst_lay:
                    worst_lay = lay_val
                    best_row = row
        else:
            # Closest row to cashout_minute, strictly after trigger (original)
            best_row = None
            best_dist = float("inf")
            for row in rows:
                m = _to_float(row.get("minuto", ""))
                if m is None or m <= trigger_min:
                    continue
                if _co_is_corrupted(row, back_col, lay_col):
                    continue
                dist = abs(m - cashout_minute)
                if dist < best_dist:
                    best_dist = dist
                    best_row = row

        if best_row is None:
            continue

        lay_odds = _to_float(best_row.get(lay_col, ""))
        if not lay_odds or lay_odds <= 1.0:
            continue

        co_pl = _co_calc_pl(back_odds, lay_odds, stake)
        # Apply unconditionally — threshold crossed means CO executed, regardless of outcome
        bet["pl"] = co_pl
        bet["cashout_applied"] = True
        bet["cashout_minute_actual"] = _to_float(best_row.get("minuto", ""))
        bet["cashout_lay_odds"] = round(lay_odds, 2)
        co_count += 1

    # Recompute flat cumulative
    bets.sort(key=lambda x: x.get("timestamp_utc", ""))
    flat_total = 0.0
    flat_cum = []
    for b in bets:
        flat_total += b["pl"]
        flat_cum.append(round(flat_total, 2))

    n = len(bets)
    flat_pl = round(sum(b["pl"] for b in bets), 2)
    result["flat"]["pl"] = flat_pl
    result["flat"]["roi"] = round(flat_pl / (n * stake) * 100, 1) if n else 0
    result["flat"]["cumulative"] = flat_cum

    # Recompute managed bankroll
    initial_bankroll = result["managed"].get("initial_bankroll", 500)
    pct = result["managed"].get("bankroll_pct", 2.0) / 100.0
    bankroll = initial_bankroll
    managed_cum = []
    for b in bets:
        bet_size = round(bankroll * pct, 2)
        if b.get("cashout_applied"):
            # CO takes priority over won/lost — threshold was crossed, we exited early
            profit = round(b["pl"] / stake * bet_size, 2)
        elif b.get("won", False):
            odds = b.get("back_draw") or b.get("back_over_odds") or b.get("back_odds") or 1
            profit = round((odds - 1) * bet_size * 0.95, 2) if odds and odds > 1 else -bet_size
        else:
            profit = -bet_size
        bankroll += profit
        managed_cum.append(round(bankroll - initial_bankroll, 2))

    result["managed"]["final_bankroll"] = round(bankroll, 2)
    result["managed"]["pl"] = managed_cum[-1] if managed_cum else 0
    result["managed"]["roi"] = round(
        (managed_cum[-1] if managed_cum else 0) / initial_bankroll * 100, 1
    )
    result["managed"]["cumulative"] = managed_cum

    # Recompute by_strategy summaries
    def _s(subset):
        nn = len(subset)
        ww = sum(1 for b in subset if b["won"])
        pp = sum(b["pl"] for b in subset)
        return {
            "bets": nn, "wins": ww,
            "win_pct": round(ww / nn * 100, 1) if nn else 0,
            "pl": round(pp, 2),
            "roi": round(pp / (nn * stake) * 100, 1) if nn else 0,
        }

    result["by_strategy"]["back_draw_00"] = _s([b for b in bets if b["strategy"] == "back_draw_00"])
    result["by_strategy"]["xg_underperformance"] = _s([b for b in bets if b["strategy"] == "xg_underperformance"])
    result["by_strategy"]["odds_drift"] = _s([b for b in bets if b["strategy"] == "odds_drift"])
    result["by_strategy"]["goal_clustering"] = _s([b for b in bets if b["strategy"] == "goal_clustering"])
    result["by_strategy"]["pressure_cooker"] = _s([b for b in bets if b["strategy"] == "pressure_cooker"])
    result["by_strategy"]["tarde_asia"] = _s([b for b in bets if b["strategy"] == "tarde_asia"])
    result["by_strategy"]["momentum_xg"] = _s(
        [b for b in bets if b["strategy"] in ("momentum_xg_v1", "momentum_xg_v2")]
    )

    result["cashout_mode"] = "lay_pct" if cashout_lay_pct is not None else "minute"
    result["cashout_lay_pct"] = cashout_lay_pct
    result["cashout_minute"] = cashout_minute
    result["cashout_applied_count"] = co_count
    result["cashout_mode_params"] = {
        "cashout_lay_pct": cashout_lay_pct,
        "adaptive_early_pct": adaptive_early_pct,
        "adaptive_late_pct": adaptive_late_pct,
        "adaptive_split_min": adaptive_split_min,
        "adverse_goal_stop": adverse_goal_stop,
        "trailing_stop_pct": trailing_stop_pct,
    }
    return result


# ── Signal log state (in-memory, persists across API calls within process) ──────
# Key: (match_id, strategy) → {minute, back_odds, score, timestamp}
_signal_state: dict[tuple[str, str], dict] = {}

_SIGNAL_LOG_HEADERS = [
    "event_type",
    "timestamp_utc",
    "match_id", "match_name", "match_url",
    "strategy", "strategy_name",
    "minute", "score",
    "recommendation", "back_odds", "min_odds", "expected_value",
    "confidence", "win_rate_historical", "roi_historical", "sample_size",
    "conditions",
    # Lifecycle columns (new)
    "first_detected_minute", "first_detected_odds",
    "signal_age_minutes", "odds_vs_first_pct",
]

_ODDS_CHANGE_THRESHOLD = 0.05  # 5% change triggers an odds_update event


def _write_signal_log_row(row: dict):
    """Write a single row to signals_log.csv, creating headers if needed."""
    import csv as _csv
    from pathlib import Path as _Path

    log_file = _Path(__file__).parent.parent.parent / "signals_log.csv"
    file_exists = log_file.exists()

    # If file exists but uses old format (no event_type column), migrate it first
    if file_exists:
        with open(log_file, "r", encoding="utf-8") as f:
            first_line = f.readline()
        if "event_type" not in first_line:
            _migrate_signals_log(log_file)

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=_SIGNAL_LOG_HEADERS, extrasaction="ignore")
        if not log_file.exists() or not file_exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in _SIGNAL_LOG_HEADERS})


def _migrate_signals_log(log_file):
    """Add new lifecycle columns to existing signals_log.csv (backward compat)."""
    import csv as _csv
    import shutil

    backup = str(log_file) + ".bak"
    shutil.copy2(log_file, backup)

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        old_rows = list(_csv.DictReader(f))

    with open(log_file, "w", newline="", encoding="utf-8") as f:
        writer = _csv.DictWriter(f, fieldnames=_SIGNAL_LOG_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for r in old_rows:
            # Map old column order: old CSV didn't have event_type as first col
            migrated = {k: r.get(k, "") for k in _SIGNAL_LOG_HEADERS}
            migrated["event_type"] = migrated.get("event_type") or "first_detection"
            writer.writerow(migrated)


def _build_log_row(signal: dict, event_type: str, state: dict | None = None) -> dict:
    """Build a log row dict from a signal and optional prior state."""
    from datetime import datetime as _dt

    match_id = signal.get("match_id", "")
    strategy = signal.get("strategy", "")
    minute = signal.get("minute", "")
    back_odds = signal.get("back_odds", "")

    first_minute = state["minute"] if state else minute
    first_odds = state["back_odds"] if state else back_odds

    try:
        age = round(float(minute) - float(first_minute), 1) if minute and first_minute else ""
    except (TypeError, ValueError):
        age = ""

    try:
        if back_odds and first_odds and float(first_odds) > 0:
            odds_pct = round((float(back_odds) / float(first_odds) - 1) * 100, 1)
        else:
            odds_pct = ""
    except (TypeError, ValueError):
        odds_pct = ""

    return {
        "event_type": event_type,
        "timestamp_utc": _dt.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "match_id": match_id,
        "match_name": signal.get("match_name", ""),
        "match_url": signal.get("match_url", ""),
        "strategy": strategy,
        "strategy_name": signal.get("strategy_name", ""),
        "minute": minute,
        "score": signal.get("score", ""),
        "recommendation": signal.get("recommendation", ""),
        "back_odds": back_odds,
        "min_odds": signal.get("min_odds", ""),
        "expected_value": signal.get("expected_value", ""),
        "confidence": signal.get("confidence", ""),
        "win_rate_historical": signal.get("win_rate_historical", ""),
        "roi_historical": signal.get("roi_historical", ""),
        "sample_size": signal.get("sample_size", ""),
        "conditions": str(signal.get("entry_conditions", "")),
        "first_detected_minute": first_minute,
        "first_detected_odds": first_odds,
        "signal_age_minutes": age,
        "odds_vs_first_pct": odds_pct,
    }


def _log_signal_to_csv(signal: dict):
    """Event-based signal logger.

    Writes a row to signals_log.csv on:
    - first_detection: first time (match_id, strategy) is seen
    - score_change:    goal scored while signal is active
    - odds_update:     back_odds moved ≥5% from last logged value
    """
    match_id = signal.get("match_id", "")
    strategy = signal.get("strategy", "")
    key = (match_id, strategy)

    current_score = str(signal.get("score", ""))
    current_odds_raw = signal.get("back_odds", "")
    try:
        current_odds = float(current_odds_raw) if current_odds_raw else None
    except (TypeError, ValueError):
        current_odds = None

    if key not in _signal_state:
        # First detection
        row = _build_log_row(signal, "first_detection", state=None)
        _write_signal_log_row(row)
        _signal_state[key] = {
            "minute": signal.get("minute", ""),
            "back_odds": current_odds_raw,
            "score": current_score,
        }
        return

    prev = _signal_state[key]
    prev_score = prev.get("score", "")
    prev_odds_raw = prev.get("back_odds", "")
    try:
        prev_odds = float(prev_odds_raw) if prev_odds_raw else None
    except (TypeError, ValueError):
        prev_odds = None

    # Check for score change (goal)
    if current_score != prev_score:
        row = _build_log_row(signal, "score_change", state=prev)
        _write_signal_log_row(row)
        _signal_state[key] = {
            "minute": signal.get("minute", ""),
            "back_odds": current_odds_raw,
            "score": current_score,
        }
        return

    # Check for significant odds movement (≥5%)
    if current_odds and prev_odds and prev_odds > 0:
        change = abs(current_odds / prev_odds - 1)
        if change >= _ODDS_CHANGE_THRESHOLD:
            row = _build_log_row(signal, "odds_update", state=prev)
            _write_signal_log_row(row)
            _signal_state[key] = {
                "minute": _signal_state[key]["minute"],  # keep first_detected_minute reference
                "back_odds": current_odds_raw,
                "score": current_score,
            }


def _log_signal_ends(current_signal_keys: set[tuple[str, str]]):
    """Log signal_end for signals that were active last call but are gone now."""
    from datetime import datetime as _dt

    gone_keys = set(_signal_state.keys()) - current_signal_keys
    for key in gone_keys:
        prev = _signal_state.pop(key)
        match_id, strategy = key
        # Build a minimal end-signal row from stored state
        end_row = {
            "event_type": "signal_end",
            "timestamp_utc": _dt.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "match_id": match_id,
            "match_name": "",
            "match_url": "",
            "strategy": strategy,
            "strategy_name": "",
            "minute": prev.get("minute", ""),
            "score": prev.get("score", ""),
            "recommendation": "",
            "back_odds": prev.get("back_odds", ""),
            "first_detected_minute": prev.get("minute", ""),
            "first_detected_odds": prev.get("back_odds", ""),
            "signal_age_minutes": "",
            "odds_vs_first_pct": "",
        }
        _write_signal_log_row(end_row)


def detect_betting_signals(versions: dict | None = None) -> dict:
    """
    Detect live betting opportunities based on portfolio strategies.

    Args:
        versions: Dict with version per strategy, e.g.:
            {"draw": "v2r", "xg": "v2", "drift": "v1", "clustering": "v2", "pressure": "v1"}
            Version "off" disables that strategy. None = default versions.
    """
    if versions is None:
        versions = {"draw": "v2r", "xg": "v3", "drift": "v1", "clustering": "v2", "pressure": "v1"}

    # --- Minimum duration config (from historical duration analysis) ---
    # Recommended minimums: draw=1 (no benefit), xg=2, drift=2, clustering=4, pressure=2, momentum=1
    _DEFAULT_MIN_DUR = {"draw": 1, "xg": 2, "drift": 2, "clustering": 4, "pressure": 2, "momentum": 1}
    min_dur_map = {
        family: int(versions.get(f"{family}_min_dur", _DEFAULT_MIN_DUR[family]))
        for family in _DEFAULT_MIN_DUR
    }

    # --- Strategy thresholds from cartera_config (single source of truth) ---
    # These flow from analytics.py → here, ensuring live detector == historical analysis.
    _drift_base_pct     = float(versions.get("drift_threshold", 30))       # cartera.ts default: 30%
    _drift_odds_max     = float(versions.get("drift_odds_max", 999))        # cartera.ts v1 default: Infinity
    _drift_goal_diff_min = int(versions.get("drift_goal_diff_min", 0))      # cartera.ts v1 default: 0
    _drift_minute_min   = int(versions.get("drift_minute_min", 0))          # cartera.ts v1 default: 0
    _drift_mom_gap_min  = float(versions.get("drift_mom_gap_min", 0))       # cartera.ts v1 default: 0
    _clustering_min_max = int(versions.get("clustering_minute_max", 90))    # cartera.ts v3 default: 60
    _clustering_xg_rem  = float(versions.get("clustering_xg_rem_min", 0))  # cartera.ts default: 0
    _clustering_sot     = int(versions.get("clustering_sot_min", 3))        # cartera.ts default: 3
    _xg_minute_max      = int(versions.get("xg_minute_max", 90))            # cartera.ts v3 default: 70
    _xg_sot_min         = int(versions.get("xg_sot_min", 0))               # cartera.ts base default: 0
    _xg_excess_min      = float(versions.get("xg_xg_excess_min", 0.5))     # cartera.ts default: 0.5
    _draw_xg_max        = float(versions.get("draw_xg_max", 1.0))           # cartera.ts v2r default: 0.6
    _draw_poss_max      = float(versions.get("draw_poss_max", 100))         # cartera.ts v2r default: 20
    _draw_shots_max     = float(versions.get("draw_shots_max", 20))         # cartera.ts v2r default: 8
    _draw_minute_min    = int(versions.get("draw_minute_min", 30))          # default 30 (strategy intrinsic min)
    _draw_minute_max    = int(versions.get("draw_minute_max", 90))
    _xg_minute_min      = int(versions.get("xg_minute_min", 0))
    _clustering_min_min = int(versions.get("clustering_minute_min", 0))
    _pressure_minute_min = int(versions.get("pressure_minute_min", 0))
    _pressure_minute_max = int(versions.get("pressure_minute_max", 90))
    _momentum_minute_min = int(versions.get("momentum_minute_min", 0))
    _momentum_minute_max = int(versions.get("momentum_minute_max", 90))

    # --- Load first-seen timestamps from signals_log for age calculation ---
    _log_file = Path(__file__).parent.parent.parent / "signals_log.csv"
    first_seen_map: dict[tuple, datetime] = {}
    if _log_file.exists():
        try:
            with open(_log_file, "r", encoding="utf-8") as _f:
                for _row in csv.DictReader(_f):
                    _mid = _row.get("match_id", "").strip()
                    _strat = _row.get("strategy", "").strip()
                    _ts = _row.get("timestamp_utc", "").strip()
                    if _mid and _strat and _ts and (_mid, _strat) not in first_seen_map:
                        try:
                            first_seen_map[(_mid, _strat)] = datetime.strptime(_ts, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            pass
        except Exception:
            pass

    def _get_strategy_family(strategy_key: str) -> str:
        if "draw" in strategy_key:
            return "draw"
        if "momentum" in strategy_key:
            return "momentum"
        if "xg" in strategy_key or "underperformance" in strategy_key:
            return "xg"
        if "drift" in strategy_key:
            return "drift"
        if "clustering" in strategy_key:
            return "clustering"
        if "pressure" in strategy_key:
            return "pressure"
        return "draw"

    # Strategy metadata (from historical backtesting in cartera_final.md)
    STRATEGY_META = {
        "back_draw_00": {
            "win_rate": 0.571,  # 57.1% from backtest
            "avg_odds": 6.5,    # Average back draw odds
            "roi": 0.502,       # 50.2% ROI
            "sample_size": 7,
            "description": "Partidos trabados sin goles ni ocasiones"
        },
        "xg_underperformance": {
            "win_rate": 0.727,  # 72.7% from backtest
            "avg_odds": 2.2,    # Average over odds
            "roi": 0.247,       # 24.7% ROI
            "sample_size": 11,
            "description": "Equipo perdiendo pero atacando intensamente"
        },
        "odds_drift_contrarian": {
            "win_rate": 0.667,  # 66.7% from backtest
            "avg_odds": 2.5,    # Average odds
            "roi": 1.423,       # 142.3% ROI
            "sample_size": 27,
            "description": "Mercado abandona al equipo ganador erróneamente"
        },
        "goal_clustering": {
            "win_rate": 0.750,  # 75.0% from backtest
            "avg_odds": 2.3,    # Average over odds
            "roi": 0.727,       # 72.7% ROI
            "sample_size": 44,
            "description": "Después de un gol, alta probabilidad de más goles"
        },
        "pressure_cooker": {
            "win_rate": 0.812,  # 81.2% from backtest (empates 1-1+)
            "avg_odds": 2.1,    # Average over odds
            "roi": 0.819,       # 81.9% ROI
            "sample_size": 16,
            "description": "Empates con goles (1-1+) entre min 65-75 tienden a romper"
        },
        "momentum_xg": {
            "win_rate": 0.667,  # 66.7% from backtest (Ultra Relajadas)
            "avg_odds": 2.4,    # Average back odds for dominant team
            "roi": 0.522,       # 52.2% ROI
            "sample_size": 12,
            "description": "Equipo dominante (SoT ratio >1.1x) con xG no convertido tiende a ganar"
        }
    }

    def calculate_min_odds(win_rate: float) -> float:
        """Calculate minimum profitable odds based on win rate (break-even + margin)."""
        if win_rate <= 0:
            return 999.0
        # Break-even odds = 1 / win_rate
        # Add 10% margin for commission (5%) + variance
        return (1.0 / win_rate) * 1.10

    def calculate_ev(odds: float, win_rate: float, stake: float = 10.0) -> float:
        """Calculate expected value considering 5% commission."""
        if odds is None or odds <= 1.0:
            return 0.0
        profit_if_win = (odds - 1.0) * stake * 0.95  # 5% commission
        loss_if_lose = stake
        ev = (win_rate * profit_if_win) - ((1 - win_rate) * loss_if_lose)
        return ev

    def is_odds_favorable(current_odds: float, min_odds: float) -> bool:
        """Check if current odds meet minimum threshold."""
        if current_odds is None or min_odds is None:
            return False
        return current_odds >= min_odds

    def _extract_bet_market(recommendation: str) -> tuple[str, str] | None:
        """Extract (market_group, outcome) from a recommendation string.

        Returns e.g. ("match_odds", "DRAW") or ("over_under", "OVER"),
        or None if not parseable.
        """
        rec = recommendation.upper().strip()
        if rec.startswith("BACK DRAW"):
            return ("match_odds", "DRAW")
        elif rec.startswith("BACK HOME"):
            return ("match_odds", "HOME")
        elif rec.startswith("BACK AWAY"):
            return ("match_odds", "AWAY")
        elif "OVER" in rec:
            return ("over_under", "OVER")
        elif "UNDER" in rec:
            return ("over_under", "UNDER")
        return None

    # HOME↔AWAY reversals are allowed (historically profitable: +175 EUR on 10 pairs, 80% net+)
    # DRAW vs HOME/AWAY are blocked (fundamentally contradictory)
    # OVER vs UNDER are blocked (mutually exclusive)
    _REVERSAL_ALLOWED = {("HOME", "AWAY"), ("AWAY", "HOME")}

    def _has_conflict(match_id: str, recommendation: str,
                      match_outcomes: dict[str, dict[str, str]]) -> str | None:
        """Check if a signal conflicts with an existing bet on the same match.

        Returns a description of the conflict, or None if no conflict.
        HOME↔AWAY reversals are allowed (Odds Drift pattern).
        """
        market = _extract_bet_market(recommendation)
        if market is None:
            return None
        group, outcome = market
        existing = match_outcomes.get(match_id, {})
        if group in existing and existing[group] != outcome:
            pair = (existing[group], outcome)
            if pair in _REVERSAL_ALLOWED:
                return None  # HOME↔AWAY reversal — allowed
            return f"Conflicto: ya existe {existing[group]} en {group}, nueva señal es {outcome}"
        return None

    def _register_outcome(match_id: str, recommendation: str,
                          match_outcomes: dict[str, dict[str, str]]) -> None:
        """Register a bet outcome so future signals can check for conflicts."""
        market = _extract_bet_market(recommendation)
        if market is None:
            return
        group, outcome = market
        if match_id not in match_outcomes:
            match_outcomes[match_id] = {}
        match_outcomes[match_id][group] = outcome

    games = load_games()
    live_matches = [g for g in games if g["status"] == "live"]

    # Load placed bets to exclude already-bet signals
    placed_bets_keys: set[tuple[str, str]] = set()
    # Track bet outcomes per match for conflict detection
    match_outcomes: dict[str, dict[str, str]] = {}
    try:
        placed_csv = Path(__file__).parent.parent.parent.parent / "placed_bets.csv"
        if placed_csv.exists():
            with open(placed_csv, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    mid = row.get("match_id", "").strip()
                    strat = row.get("strategy", "").strip()
                    rec = row.get("recommendation", "").strip()
                    status = row.get("status", "").strip().lower()
                    if mid and strat:
                        placed_bets_keys.add((mid, strat))
                    # Only track outcomes for active (pending) bets
                    if mid and rec and status in ("pending", ""):
                        _register_outcome(mid, rec, match_outcomes)
    except Exception:
        pass

    signals = []

    for match in live_matches:
        match_id = match["match_id"]
        csv_path = _resolve_csv_path(match_id)

        if not csv_path.exists():
            continue

        rows = _read_csv_rows(csv_path)
        if not rows:
            continue

        # Get latest capture
        latest = rows[-1]

        minuto = _to_float(latest.get("minuto", ""))
        if minuto is None:
            continue

        _raw_gl = _to_float(latest.get("goles_local", ""))
        _raw_gv = _to_float(latest.get("goles_visitante", ""))
        goals_data_ok = _raw_gl is not None and _raw_gv is not None
        goles_local = _raw_gl if _raw_gl is not None else 0
        goles_visitante = _raw_gv if _raw_gv is not None else 0
        xg_local = _to_float(latest.get("xg_local", ""))
        xg_visitante = _to_float(latest.get("xg_visitante", ""))
        posesion_local = _to_float(latest.get("posesion_local", ""))
        posesion_visitante = _to_float(latest.get("posesion_visitante", ""))
        tiros_local = _to_float(latest.get("tiros_local", "")) or 0
        tiros_visitante = _to_float(latest.get("tiros_visitante", "")) or 0
        tiros_puerta_local = _to_float(latest.get("tiros_puerta_local", "")) or 0
        tiros_puerta_visitante = _to_float(latest.get("tiros_puerta_visitante", "")) or 0
        back_draw = _to_float(latest.get("back_draw", ""))
        back_home = _to_float(latest.get("back_home", ""))
        back_away = _to_float(latest.get("back_away", ""))

        draw_ver = versions.get("draw", "v2r")
        xg_ver = versions.get("xg", "v2")
        drift_ver = versions.get("drift", "v1")
        clustering_ver = versions.get("clustering", "v2")
        pressure_ver = versions.get("pressure", "v1")

        # === STRATEGY 1: Back Empate (version-specific conditions) ===
        # goals_data_ok guards against scraper not capturing goal data (None→0 would cause false 0-0 triggers)
        # _draw_minute_min is configurable (default 30 = strategy intrinsic minimum)
        if draw_ver != "off" and (minuto >= _draw_minute_min and
            goals_data_ok and
            goles_local == 0 and goles_visitante == 0 and
            xg_local is not None and xg_visitante is not None):

            xg_total = xg_local + xg_visitante
            tiros_total = tiros_local + tiros_visitante
            poss_diff = abs((posesion_local or 50) - (posesion_visitante or 50))

            # Version-specific filters — use user-configured thresholds from cartera_config
            # Sentinel values: xg>=1.0=off, poss>=100=off, shots>=20=off
            _xg_ok  = _draw_xg_max   >= 1.0 or xg_total    < _draw_xg_max
            _pos_ok = _draw_poss_max >= 100  or poss_diff   < _draw_poss_max
            _sht_ok = _draw_shots_max >= 20  or tiros_total < _draw_shots_max
            passes = True
            thresholds = {}
            if _draw_xg_max   < 1.0:  thresholds["xg_total"]       = f"< {_draw_xg_max}"
            if _draw_poss_max < 100:  thresholds["possession_diff"] = f"< {_draw_poss_max}%"
            if _draw_shots_max < 20:  thresholds["total_shots"]     = f"< {_draw_shots_max}"
            if draw_ver == "v1":
                pass  # No extra filters
            elif draw_ver == "v15":
                passes = _xg_ok and _pos_ok
            elif draw_ver == "v2r":
                passes = _xg_ok and _pos_ok and _sht_ok
            elif draw_ver == "v2":
                passes = _xg_ok and _pos_ok and _sht_ok
            elif draw_ver == "v3":
                # V3: V1.5 + xG dominance asymmetry (one team clearly dominates xG)
                xg_dom = (xg_local / xg_total) if xg_total and xg_total > 0 else None
                passes = (
                    _xg_ok and _pos_ok
                    and xg_dom is not None and (xg_dom > 0.55 or xg_dom < 0.45)
                )
                thresholds["xg_dominance"] = "> 55% o < 45%"
            elif draw_ver == "v4":
                opta_gap_abs = abs(opta_l - opta_v) if opta_l is not None and opta_v is not None else None
                passes = (
                    _xg_ok and _pos_ok and _sht_ok
                    and opta_gap_abs is not None and opta_gap_abs <= 10
                )
                thresholds["opta_gap"] = "<= 10"

            # minuteMax gate (upper bound — configurable, default: no limit)
            if passes and _draw_minute_max < 90 and minuto >= _draw_minute_max:
                passes = False

            if passes and back_draw is not None:
                meta = STRATEGY_META["back_draw_00"]
                min_odds = calculate_min_odds(meta["win_rate"])
                ev = calculate_ev(back_draw, meta["win_rate"])
                odds_ok = is_odds_favorable(back_draw, min_odds)

                signal = {
                    "match_id": match_id,
                    "match_name": match["name"],
                    "match_url": match["url"],
                    "strategy": f"back_draw_00_{draw_ver}",
                    "strategy_name": f"Back Empate 0-0 ({draw_ver.upper()})",
                    "minute": int(minuto),
                    "score": f"{int(goles_local)}-{int(goles_visitante)}",
                    "recommendation": f"BACK DRAW @ {back_draw:.2f}" if back_draw else "BACK DRAW",
                    "back_odds": back_draw,
                    "min_odds": round(min_odds, 2),
                    "expected_value": round(ev, 2),
                    "odds_favorable": odds_ok,
                    "confidence": "high" if odds_ok else "medium",
                    "win_rate_historical": round(meta["win_rate"] * 100, 1),
                    "roi_historical": round(meta["roi"] * 100, 1),
                    "sample_size": meta["sample_size"],
                    "description": meta["description"],
                    "entry_conditions": {
                        "xg_total": round(xg_total, 2),
                        "possession_diff": round(poss_diff, 1),
                        "total_shots": int(tiros_total)
                    },
                    "thresholds": thresholds or {"version": draw_ver}
                }
                if (match_id, signal["strategy"]) not in placed_bets_keys:
                    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                    if conflict:
                        signal["blocked"] = conflict
                    else:
                        signals.append(signal)
                        _log_signal_to_csv(signal)
                        _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 2: xG Underperformance (version-specific) ===
        # Skip if match has corrupted Over/Under odds
        if match_id not in CORRUPTED_OVER_MATCHES and xg_ver != "off" and minuto >= max(15, _xg_minute_min) and xg_local is not None and xg_visitante is not None:
            # Check both teams for underperformance
            for team_label, xg_team, goals_team, goals_opp, sot_team in [
                ("Home", xg_local, goles_local, goles_visitante, tiros_puerta_local),
                ("Away", xg_visitante, goles_visitante, goles_local, tiros_puerta_visitante),
            ]:
                if goals_team >= goals_opp:
                    continue  # team not losing
                xg_excess = xg_team - goals_team
                if xg_excess < _xg_excess_min:
                    continue

                # Version-specific filters
                # _xg_sot_min and _xg_minute_max come from cartera_config strategies.xg
                xg_thresholds = {"xg_excess": f">= {_xg_excess_min}"}
                if xg_ver == "base":
                    # Use config params if explicitly set
                    if _xg_sot_min > 0 and sot_team < _xg_sot_min:
                        continue
                    if _xg_minute_max < 90 and minuto >= _xg_minute_max:
                        continue
                elif xg_ver == "v2":
                    sot_cutoff = max(2, _xg_sot_min)
                    if sot_team < sot_cutoff:
                        continue
                    xg_thresholds["shots_on_target"] = f">= {sot_cutoff}"
                elif xg_ver == "v3":
                    # minuteMax from config (cartera.ts v3 = 70, config xg.minuteMax = 70)
                    sot_cutoff = max(2, _xg_sot_min)
                    min_cutoff = _xg_minute_max if _xg_minute_max < 90 else 70
                    if sot_team < sot_cutoff or minuto >= min_cutoff:
                        continue
                    xg_thresholds["shots_on_target"] = f">= {sot_cutoff}"
                    xg_thresholds["minute"] = f"< {min_cutoff}"

                meta = STRATEGY_META["xg_underperformance"]
                min_odds = calculate_min_odds(meta["win_rate"])
                total_goles = int(goles_local) + int(goles_visitante)
                over_line = total_goles + 0.5
                over_field = _get_over_odds_field(total_goles)
                over_odds = _to_float(latest.get(over_field, "")) if over_field else None
                if over_odds is None:
                    continue  # No signal without odds data
                ev = calculate_ev(over_odds, meta["win_rate"])
                odds_ok = is_odds_favorable(over_odds, min_odds)
                signal = {
                    "match_id": match_id,
                    "match_name": match["name"],
                    "match_url": match["url"],
                    "strategy": f"xg_underperformance_{xg_ver}",
                    "strategy_name": f"xG Underperformance ({xg_ver.upper()})",
                    "minute": int(minuto),
                    "score": f"{int(goles_local)}-{int(goles_visitante)}",
                    "recommendation": f"BACK Over {over_line}",
                    "back_odds": round(over_odds, 2) if over_odds else None,
                    "min_odds": round(min_odds, 2),
                    "expected_value": round(ev, 2) if ev is not None else None,
                    "odds_favorable": odds_ok,
                    "confidence": "high" if odds_ok else ("medium" if odds_ok is None else "low"),
                    "win_rate_historical": round(meta["win_rate"] * 100, 1),
                    "roi_historical": round(meta["roi"] * 100, 1),
                    "sample_size": meta["sample_size"],
                    "description": meta["description"],
                    "entry_conditions": {
                        "team": team_label,
                        "xg_excess": round(xg_excess, 2),
                        "shots_on_target": int(sot_team)
                    },
                    "thresholds": xg_thresholds
                }
                if (match_id, signal["strategy"]) not in placed_bets_keys:
                    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                    if conflict:
                        signal["blocked"] = conflict
                    else:
                        signals.append(signal)
                        _log_signal_to_csv(signal)
                        _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 3: Odds Drift Contrarian (version-specific) ===
        goal_diff = abs(int(goles_local) - int(goles_visitante))
        if drift_ver != "off" and minuto >= 30 and goal_diff >= 1 and goles_local != goles_visitante:
            # Require current score confirmed in at least 3 captures (avoid post-goal transitional odds)
            score_confirm_count = 0
            for check_row in rows[-6:]:
                cgl = _to_float(check_row.get("goles_local", "")) or 0
                cgv = _to_float(check_row.get("goles_visitante", "")) or 0
                if int(cgl) == int(goles_local) and int(cgv) == int(goles_visitante):
                    score_confirm_count += 1
            if score_confirm_count < 3:
                pass  # Skip — score too recent, odds may not reflect it yet
            else:
                # Get odds from 10 minutes ago (must have SAME score to be comparable)
                target_minute = minuto - 10
                historical_row = None
                for row in reversed(rows):
                    row_min = _to_float(row.get("minuto", ""))
                    if row_min is not None and row_min <= target_minute:
                        hgl = _to_float(row.get("goles_local", "")) or 0
                        hgv = _to_float(row.get("goles_visitante", "")) or 0
                        if int(hgl) == int(goles_local) and int(hgv) == int(goles_visitante):
                            historical_row = row
                        break

                if historical_row:
                    # Determine winning team
                    if goles_local > goles_visitante:
                        team_label = "Home"
                        odds_before = _to_float(historical_row.get("back_home", ""))
                        odds_now = back_home
                    else:
                        team_label = "Away"
                        odds_before = _to_float(historical_row.get("back_away", ""))
                        odds_now = back_away

                    if odds_before and odds_now and odds_before > 0:
                        drift_pct_val = ((odds_now - odds_before) / odds_before) * 100

                        # Base condition: drift >= _drift_base_pct (from cartera_config, default 30%)
                        # Aligned to cartera.ts DEFAULT_DRIFT_PARAMS.driftMin = 30
                        if drift_pct_val >= _drift_base_pct:
                            # Version-specific additional filters
                            drift_passes = True
                            drift_thresholds = {"drift_pct": f">= {_drift_base_pct:.0f}%"}
                            if drift_ver == "v1":
                                # V1: no extra score restriction (aligned to cartera.ts v1 = DEFAULT_DRIFT_PARAMS)
                                # goalDiffMin=0 → accept any goal difference >= 1
                                if _drift_goal_diff_min > 0 and goal_diff < _drift_goal_diff_min:
                                    drift_passes = False
                                if _drift_odds_max < 999 and odds_now > _drift_odds_max:
                                    drift_passes = False
                                    drift_thresholds["odds"] = f"<= {_drift_odds_max}"
                            elif drift_ver == "v2":
                                # V2: goal_diff >= 2
                                drift_passes = goal_diff >= 2
                                drift_thresholds["goal_diff"] = ">= 2"
                            elif drift_ver == "v3":
                                # V3: drift >= 100%
                                drift_passes = drift_pct_val >= 100
                                drift_thresholds["drift_pct"] = ">= 100%"
                            elif drift_ver == "v4":
                                # V4: 2nd half + odds <= 5
                                drift_passes = minuto > 45 and odds_now <= 5.0
                                drift_thresholds["minute"] = "> 45"
                                drift_thresholds["odds"] = "<= 5.0"
                            elif drift_ver == "v5":
                                # V5: odds <= 5
                                drift_passes = odds_now <= 5.0
                                drift_thresholds["odds"] = "<= 5.0"

                            if drift_passes:
                                meta = STRATEGY_META["odds_drift_contrarian"]
                                min_odds = calculate_min_odds(meta["win_rate"])
                                ev = calculate_ev(odds_now, meta["win_rate"])
                                odds_ok = is_odds_favorable(odds_now, min_odds)

                                # Calcular riesgo por tiempo + marcador
                                risk_info = calculate_time_score_risk(
                                    strategy=f"odds_drift_{drift_ver}",
                                    minute=minuto,
                                    home_score=int(goles_local),
                                    away_score=int(goles_visitante),
                                    dominant_team=team_label
                                )

                                signal = {
                                    "match_id": match_id,
                                    "match_name": match["name"],
                                    "match_url": match["url"],
                                    "strategy": f"odds_drift_contrarian_{drift_ver}",
                                    "strategy_name": f"Odds Drift Contrarian ({drift_ver.upper()})",
                                    "minute": int(minuto),
                                    "score": f"{int(goles_local)}-{int(goles_visitante)}",
                                    "recommendation": f"BACK {team_label.upper()} @ {odds_now:.2f}",
                                    "back_odds": odds_now,
                                    "min_odds": round(min_odds, 2),
                                    "expected_value": round(ev, 2),
                                    "odds_favorable": odds_ok,
                                    "confidence": "high" if odds_ok else "medium",
                                    "win_rate_historical": round(meta["win_rate"] * 100, 1),
                                    "roi_historical": round(meta["roi"] * 100, 1),
                                    "sample_size": meta["sample_size"],
                                    "description": meta["description"],
                                    "entry_conditions": {
                                        "team": team_label,
                                        "odds_before": round(odds_before, 2),
                                        "odds_now": round(odds_now, 2),
                                        "drift_pct": round(drift_pct_val, 1)
                                    },
                                    "thresholds": drift_thresholds,
                                    "risk_info": risk_info
                                }
                                if (match_id, signal["strategy"]) not in placed_bets_keys:
                                    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                                    if conflict:
                                        signal["blocked"] = conflict
                                    # Block signals with time/score risk
                                    elif risk_info["risk_level"] != "none":
                                        signal["blocked"] = f"Riesgo {risk_info['risk_level']}: {risk_info['risk_reason']}"
                                    else:
                                        signals.append(signal)
                                        _log_signal_to_csv(signal)
                                        _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 4: Goal Clustering (version-specific) ===
        # Skip if match has corrupted Over/Under odds
        _cluster_min = max(15, _clustering_min_min)
        if match_id not in CORRUPTED_OVER_MATCHES and clustering_ver != "off" and len(rows) >= 2 and _cluster_min <= minuto <= 80:
            # Look for goal in last 3 captures (approx last 90 seconds)
            recent_goal = False
            goal_minute = None

            for i in range(len(rows) - 1, max(0, len(rows) - 4), -1):
                current_row = rows[i]
                if i > 0:
                    prev_row = rows[i - 1]

                    curr_gl = _to_float(current_row.get("goles_local", "")) or 0
                    curr_gv = _to_float(current_row.get("goles_visitante", "")) or 0
                    prev_gl = _to_float(prev_row.get("goles_local", "")) or 0
                    prev_gv = _to_float(prev_row.get("goles_visitante", "")) or 0

                    curr_total = int(curr_gl) + int(curr_gv)
                    prev_total = int(prev_gl) + int(prev_gv)

                    # Goal detected
                    if curr_total > prev_total:
                        row_min = _to_float(current_row.get("minuto", ""))
                        if row_min and 15 <= row_min <= 80:
                            recent_goal = True
                            goal_minute = int(row_min)
                            break

            if recent_goal:
                sot_max = max(tiros_puerta_local, tiros_puerta_visitante)

                if _clustering_sot == 0 or sot_max >= _clustering_sot:
                    # minuteMax filter: from cartera_config strategies.clustering.minuteMax
                    # cartera.ts: v3 → minuteMax=60, v2 → 90 (no filter), v4 → 80
                    # _clustering_min_max defaults to 90 (no filter) but config will supply 60 for v3
                    if _clustering_min_max < 90 and minuto >= _clustering_min_max:
                        pass  # skip - past minuteMax from config
                    else:
                        total_actual = int(goles_local) + int(goles_visitante)
                        over_line = total_actual + 0.5

                        meta = STRATEGY_META["goal_clustering"]
                        min_odds = calculate_min_odds(meta["win_rate"])
                        cl_thresholds = {"minute_range": f"{_cluster_min}-80"}
                        if _clustering_sot > 0:
                            cl_thresholds["sot_max"] = f">= {_clustering_sot}"
                        if _clustering_min_max < 90:
                            cl_thresholds["minute"] = f"< {_clustering_min_max}"

                        cl_over_field = _get_over_odds_field(total_actual)
                        cl_over_odds = _to_float(latest.get(cl_over_field, "")) if cl_over_field else None
                        if cl_over_odds is None:
                            continue  # No signal without odds data
                        cl_ev = calculate_ev(cl_over_odds, meta["win_rate"])
                        cl_odds_ok = is_odds_favorable(cl_over_odds, min_odds)

                        signal = {
                            "match_id": match_id,
                            "match_name": match["name"],
                            "match_url": match["url"],
                            "strategy": f"goal_clustering_{clustering_ver}",
                            "strategy_name": f"Goal Clustering ({clustering_ver.upper()})",
                            "minute": int(minuto),
                            "score": f"{int(goles_local)}-{int(goles_visitante)}",
                            "recommendation": f"BACK Over {over_line}",
                            "back_odds": round(cl_over_odds, 2) if cl_over_odds else None,
                            "min_odds": round(min_odds, 2),
                            "expected_value": round(cl_ev, 2) if cl_ev is not None else None,
                            "odds_favorable": cl_odds_ok,
                            "confidence": "high" if cl_odds_ok else ("medium" if cl_odds_ok is None else "low"),
                            "win_rate_historical": round(meta["win_rate"] * 100, 1),
                            "roi_historical": round(meta["roi"] * 100, 1),
                            "sample_size": meta["sample_size"],
                            "description": meta["description"],
                            "entry_conditions": {
                                "goal_minute": goal_minute,
                                "sot_max": int(sot_max),
                                "total_goals": total_actual
                            },
                            "thresholds": cl_thresholds
                        }
                        if (match_id, signal["strategy"]) not in placed_bets_keys:
                            conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                            if conflict:
                                signal["blocked"] = conflict
                            else:
                                signals.append(signal)
                                _log_signal_to_csv(signal)
                                _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 5: Pressure Cooker (version-specific) ===
        total_goals = int(goles_local) + int(goles_visitante)
        is_draw = goles_local == goles_visitante
        has_goals = total_goals >= 2  # at least 1-1

        # Skip if match has corrupted Over/Under odds
        _press_min = max(65, _pressure_minute_min)
        _press_max = min(75, _pressure_minute_max) if _pressure_minute_max < 90 else 75
        if match_id not in CORRUPTED_OVER_MATCHES and pressure_ver != "off" and (_press_min <= minuto <= _press_max and is_draw and has_goals):
            # Score confirmation: check last few rows have same score
            score_confirmed = False
            confirm_count = 0
            for check_row in rows[-6:]:
                check_gl = _to_float(check_row.get("goles_local", "")) or 0
                check_gv = _to_float(check_row.get("goles_visitante", "")) or 0
                if check_gl == goles_local and check_gv == goles_visitante:
                    confirm_count += 1
            score_confirmed = confirm_count >= 2

            if score_confirmed:
                over_field = _get_over_odds_field(total_goals)
                over_odds = _to_float(latest.get(over_field, "")) if over_field else None
                if over_odds is None:
                    continue  # No signal without odds data

                meta = STRATEGY_META["pressure_cooker"]
                min_odds = calculate_min_odds(meta["win_rate"])

                signal = {
                    "match_id": match_id,
                    "match_name": match["name"],
                    "match_url": match["url"],
                    "strategy": f"pressure_cooker_{pressure_ver}",
                    "strategy_name": f"Pressure Cooker ({pressure_ver.upper()})",
                    "minute": int(minuto),
                    "score": f"{int(goles_local)}-{int(goles_visitante)}",
                    "recommendation": f"BACK Over {total_goals + 0.5}",
                    "back_odds": round(over_odds, 2) if over_odds else None,
                    "min_odds": round(min_odds, 2),
                    "expected_value": round(calculate_ev(over_odds, meta["win_rate"]), 2) if over_odds else None,
                    "odds_favorable": is_odds_favorable(over_odds, min_odds) if over_odds else None,
                    "confidence": "medium",  # EN PRUEBA - muestra insuficiente
                    "win_rate_historical": round(meta["win_rate"] * 100, 1),
                    "roi_historical": round(meta["roi"] * 100, 1),
                    "sample_size": meta["sample_size"],
                    "description": meta["description"],
                    "entry_conditions": {
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "total_goals": total_goals,
                        "over_odds": round(over_odds, 2) if over_odds else None
                    },
                    "thresholds": {
                        "minute_range": "65-75",
                        "min_score": "1-1+"
                    }
                }
                if (match_id, signal["strategy"]) not in placed_bets_keys:
                    conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                    if conflict:
                        signal["blocked"] = conflict
                    else:
                        signals.append(signal)
                        _log_signal_to_csv(signal)
                        _register_outcome(match_id, signal["recommendation"], match_outcomes)

        # === STRATEGY 6: Momentum Dominante x xG ===
        momentum_ver = versions.get("momentum", "v1")
        if momentum_ver != "off" and xg_local is not None and xg_visitante is not None:
            # Config según versión
            if momentum_ver == "v2":
                mom_cfg = {"sot_min": 1, "ratio": 1.05, "xg": 0.1, "min_m": 5, "max_m": 85, "odds_min": 1.3, "odds_max": 8.0}
            else:  # v1
                mom_cfg = {"sot_min": 1, "ratio": 1.1, "xg": 0.15, "min_m": 10, "max_m": 80, "odds_min": 1.4, "odds_max": 6.0}

            # Check minute range (version-specific floor/ceiling + user config)
            mom_actual_min = max(mom_cfg["min_m"], _momentum_minute_min) if _momentum_minute_min > 0 else mom_cfg["min_m"]
            mom_actual_max = min(mom_cfg["max_m"], _momentum_minute_max) if _momentum_minute_max < 90 else mom_cfg["max_m"]
            if not (mom_actual_min <= minuto <= mom_actual_max):
                pass  # Skip
            else:
                # Calculate xG underperformance
                xg_underperf_local = xg_local - goles_local
                xg_underperf_visitante = xg_visitante - goles_visitante

                # Check both teams for dominance
                dominant_team = None
                back_odds = None
                sot_ratio_used = 0

                # Home dominant: SoT superior + xG underperformance
                if tiros_puerta_visitante > 0:
                    sot_ratio_local = tiros_puerta_local / tiros_puerta_visitante
                else:
                    sot_ratio_local = tiros_puerta_local * 2 if tiros_puerta_local >= mom_cfg["sot_min"] else 0

                if (tiros_puerta_local >= mom_cfg["sot_min"] and
                    sot_ratio_local >= mom_cfg["ratio"] and
                    xg_underperf_local > mom_cfg["xg"]):
                    if back_home is not None and mom_cfg["odds_min"] <= back_home <= mom_cfg["odds_max"]:
                        dominant_team = "Home"
                        back_odds = back_home
                        sot_ratio_used = sot_ratio_local

                # Away dominant
                if tiros_puerta_local > 0:
                    sot_ratio_visitante = tiros_puerta_visitante / tiros_puerta_local
                else:
                    sot_ratio_visitante = tiros_puerta_visitante * 2 if tiros_puerta_visitante >= mom_cfg["sot_min"] else 0

                if (tiros_puerta_visitante >= mom_cfg["sot_min"] and
                    sot_ratio_visitante >= mom_cfg["ratio"] and
                    xg_underperf_visitante > mom_cfg["xg"]):
                    if back_away is not None and mom_cfg["odds_min"] <= back_away <= mom_cfg["odds_max"]:
                        # If both are dominant, take the more dominant one
                        if dominant_team is None or xg_underperf_visitante > xg_underperf_local:
                            dominant_team = "Away"
                            back_odds = back_away
                            sot_ratio_used = sot_ratio_visitante

                if dominant_team is not None and back_odds is not None:
                    xg_underperf = xg_underperf_local if dominant_team == "Home" else xg_underperf_visitante
                    meta = STRATEGY_META["momentum_xg"]
                    min_odds = calculate_min_odds(meta["win_rate"])
                    ev = calculate_ev(back_odds, meta["win_rate"])
                    odds_ok = is_odds_favorable(back_odds, min_odds)

                    # Calcular riesgo por tiempo + marcador
                    risk_info = calculate_time_score_risk(
                        strategy=f"momentum_xg_{momentum_ver}",
                        minute=minuto,
                        home_score=int(goles_local),
                        away_score=int(goles_visitante),
                        dominant_team=dominant_team
                    )

                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": f"momentum_xg_{momentum_ver}",
                        "strategy_name": f"Momentum Dominante x xG ({momentum_ver.upper()})",
                        "minute": int(minuto),
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "recommendation": f"BACK {dominant_team.upper()} @ {back_odds:.2f}",
                        "back_odds": round(back_odds, 2),
                        "min_odds": round(min_odds, 2),
                        "expected_value": round(ev, 2),
                        "odds_favorable": odds_ok,
                        "confidence": "high" if odds_ok else "medium",
                        "win_rate_historical": round(meta["win_rate"] * 100, 1),
                        "roi_historical": round(meta["roi"] * 100, 1),
                        "sample_size": meta["sample_size"],
                        "description": meta["description"],
                        "entry_conditions": {
                            "dominant_team": dominant_team,
                            "sot_ratio": round(sot_ratio_used, 2),
                            "xg_underperf": round(xg_underperf, 2),
                            "sot_home": int(tiros_puerta_local),
                            "sot_away": int(tiros_puerta_visitante)
                        },
                        "thresholds": {
                            "sot_min": f">= {mom_cfg['sot_min']}",
                            "sot_ratio": f">= {mom_cfg['ratio']}x",
                            "xg_underperf": f"> {mom_cfg['xg']}",
                            "minute_range": f"{mom_cfg['min_m']}-{mom_cfg['max_m']}",
                            "odds_range": f"{mom_cfg['odds_min']}-{mom_cfg['odds_max']}"
                        },
                        "risk_info": risk_info
                    }
                    if (match_id, signal["strategy"]) not in placed_bets_keys:
                        conflict = _has_conflict(match_id, signal["recommendation"], match_outcomes)
                        if conflict:
                            signal["blocked"] = conflict
                        # Block signals with time/score risk
                        elif risk_info["risk_level"] != "none":
                            signal["blocked"] = f"Riesgo {risk_info['risk_level']}: {risk_info['risk_reason']}"
                        else:
                            signals.append(signal)
                            _log_signal_to_csv(signal)
                            _register_outcome(match_id, signal["recommendation"], match_outcomes)

    # --- Enrich signals with age and maturity info ---
    _now = datetime.utcnow()
    for _sig in signals:
        _key = (_sig["match_id"], _sig["strategy"])
        _first_seen = first_seen_map.get(_key)
        if _first_seen:
            _age_mins = (_now - _first_seen).total_seconds() / 60.0
        else:
            _age_mins = 0.0
        _family = _get_strategy_family(_sig["strategy"])
        _min_dur = min_dur_map.get(_family, 1)
        _sig["signal_age_minutes"] = round(_age_mins, 1)
        _sig["min_duration_caps"] = _min_dur
        _sig["is_mature"] = _age_mins >= _min_dur

    # --- Log signal_end for signals that disappeared this cycle ---
    current_keys = {(s["match_id"], s["strategy"]) for s in signals}
    _log_signal_ends(current_keys)

    return {
        "total_signals": len(signals),
        "live_matches": len(live_matches),
        "signals": signals,
        "active_versions": versions
    }


def detect_watchlist(versions: dict | None = None) -> list:
    """
    Detect matches that are close to triggering a signal but don't yet meet all conditions.
    Returns a list of watchlist items sorted by proximity (highest first).
    """
    if versions is None:
        versions = {"draw": "v2r", "xg": "v3", "drift": "v1", "clustering": "v2", "pressure": "v1"}

    games = load_games()
    live_matches = [g for g in games if g["status"] == "live"]
    watchlist = []

    for match in live_matches:
        match_id = match["match_id"]
        csv_path = _resolve_csv_path(match_id)
        if not csv_path.exists():
            continue
        rows = _read_csv_rows(csv_path)
        if not rows:
            continue

        latest = rows[-1]
        minuto = _to_float(latest.get("minuto", ""))
        if minuto is None:
            continue

        gl = _to_float(latest.get("goles_local", "")) or 0
        gv = _to_float(latest.get("goles_visitante", "")) or 0
        xg_l = _to_float(latest.get("xg_local", ""))
        xg_v = _to_float(latest.get("xg_visitante", ""))
        pos_l = _to_float(latest.get("posesion_local", ""))
        pos_v = _to_float(latest.get("posesion_visitante", ""))
        tiros_l = _to_float(latest.get("tiros_local", "")) or 0
        tiros_v = _to_float(latest.get("tiros_visitante", "")) or 0
        sot_l = _to_float(latest.get("tiros_puerta_local", "")) or 0
        sot_v = _to_float(latest.get("tiros_puerta_visitante", "")) or 0
        back_draw = _to_float(latest.get("back_draw", ""))
        back_home = _to_float(latest.get("back_home", ""))
        back_away = _to_float(latest.get("back_away", ""))

        draw_ver = versions.get("draw", "v2r")
        xg_ver = versions.get("xg", "v2")
        drift_ver = versions.get("drift", "v1")
        clustering_ver = versions.get("clustering", "v2")
        pressure_ver = versions.get("pressure", "v1")

        match_info = {"match_id": match_id, "match_name": match["name"],
                      "match_url": match["url"], "minute": int(minuto),
                      "score": f"{int(gl)}-{int(gv)}"}

        # --- DRAW watchlist ---
        if draw_ver != "off" and gl == 0 and gv == 0:
            conds = []
            conds.append({"label": "Score 0-0", "met": True})
            conds.append({"label": "Min >= 30", "met": minuto >= 30,
                          "current": f"Min {int(minuto)}", "target": "30"})
            if xg_l is not None and xg_v is not None:
                xg_total = xg_l + xg_v
                poss_diff = abs((pos_l or 50) - (pos_v or 50))
                tiros_total = tiros_l + tiros_v
                if draw_ver in ("v15", "v2r", "v2", "v3", "v4"):
                    limit = 0.5 if draw_ver == "v2" else 0.6
                    conds.append({"label": f"xG < {limit}", "met": xg_total < limit,
                                  "current": f"{xg_total:.2f}", "target": str(limit)})
                if draw_ver in ("v15", "v2r", "v2", "v3", "v4"):
                    pd_limit = 25 if draw_ver in ("v15", "v3") else 20
                    conds.append({"label": f"Pos. diff < {pd_limit}%", "met": poss_diff < pd_limit,
                                  "current": f"{poss_diff:.0f}%", "target": f"{pd_limit}%"})
                if draw_ver in ("v2r", "v2", "v4"):
                    conds.append({"label": "Tiros < 8", "met": tiros_total < 8,
                                  "current": str(int(tiros_total)), "target": "8"})
                if draw_ver == "v3":
                    xg_dom = (xg_l / xg_total) if xg_total > 0 else None
                    xg_dom_ok = xg_dom is not None and (xg_dom > 0.55 or xg_dom < 0.45)
                    conds.append({"label": "Dominancia xG asimétrica", "met": xg_dom_ok,
                                  "current": f"{xg_dom:.0%}" if xg_dom else "n/a", "target": ">55% o <45%"})
                if draw_ver == "v4":
                    opta_gap_live = abs(opta_l - opta_v) if opta_l is not None and opta_v is not None else None
                    conds.append({"label": "Opta gap <= 10", "met": opta_gap_live is not None and opta_gap_live <= 10,
                                  "current": f"{opta_gap_live:.1f}" if opta_gap_live is not None else "n/a", "target": "10"})

            met = sum(1 for c in conds if c["met"])
            total = len(conds)
            if 0 < met < total:
                watchlist.append({**match_info, "strategy": "Empate 0-0",
                                  "version": draw_ver.upper(), "conditions": conds,
                                  "met": met, "total": total, "proximity": round(met / total * 100)})

        # --- XG UNDERPERFORMANCE watchlist ---
        if xg_ver != "off" and xg_l is not None and xg_v is not None:
            for team_label, xg_t, goals_t, goals_o, sot_t in [
                ("Home", xg_l, gl, gv, sot_l), ("Away", xg_v, gv, gl, sot_v)]:
                xg_excess = xg_t - goals_t
                conds = []
                conds.append({"label": "Equipo perdiendo", "met": goals_t < goals_o})
                conds.append({"label": "xG excess >= 0.5", "met": xg_excess >= 0.5,
                              "current": f"{xg_excess:.2f}", "target": "0.50"})
                conds.append({"label": "Min >= 15", "met": minuto >= 15,
                              "current": f"Min {int(minuto)}", "target": "15"})
                if xg_ver in ("v2", "v3"):
                    conds.append({"label": "SoT >= 2", "met": sot_t >= 2,
                                  "current": str(int(sot_t)), "target": "2"})
                if xg_ver == "v3":
                    conds.append({"label": "Min < 70", "met": minuto < 70,
                                  "current": f"Min {int(minuto)}", "target": "70"})

                met = sum(1 for c in conds if c["met"])
                total = len(conds)
                if met >= 2 and met < total:
                    watchlist.append({**match_info, "strategy": f"xG Underp. ({team_label})",
                                      "version": xg_ver.upper(), "conditions": conds,
                                      "met": met, "total": total, "proximity": round(met / total * 100)})

        # --- ODDS DRIFT watchlist ---
        if drift_ver != "off" and gl != gv:
            goal_diff = abs(int(gl) - int(gv))
            target_minute = minuto - 10
            hist_row = None
            for row in reversed(rows):
                rm = _to_float(row.get("minuto", ""))
                if rm is not None and rm <= target_minute:
                    hist_row = row
                    break

            if hist_row:
                if gl > gv:
                    odds_before = _to_float(hist_row.get("back_home", ""))
                    odds_now = back_home
                else:
                    odds_before = _to_float(hist_row.get("back_away", ""))
                    odds_now = back_away

                if odds_before and odds_now and odds_before > 0:
                    drift_pct_val = ((odds_now - odds_before) / odds_before) * 100
                    conds = []
                    conds.append({"label": "Equipo ganando", "met": True})
                    conds.append({"label": "Drift >= 25%", "met": drift_pct_val >= 25,
                                  "current": f"{drift_pct_val:.0f}%", "target": "25%"})
                    if drift_ver == "v1":
                        conds.append({"label": "Score 1-0", "met": goal_diff == 1 and (gl + gv) == 1,
                                      "current": f"{int(gl)}-{int(gv)}", "target": "1-0"})
                    elif drift_ver == "v2":
                        conds.append({"label": "Dif. goles >= 2", "met": goal_diff >= 2,
                                      "current": str(goal_diff), "target": "2"})
                    elif drift_ver == "v3":
                        conds.append({"label": "Drift >= 100%", "met": drift_pct_val >= 100,
                                      "current": f"{drift_pct_val:.0f}%", "target": "100%"})
                    elif drift_ver == "v4":
                        conds.append({"label": "2a parte", "met": minuto > 45,
                                      "current": f"Min {int(minuto)}", "target": "46"})
                        conds.append({"label": "Odds <= 5", "met": odds_now <= 5.0,
                                      "current": f"{odds_now:.2f}", "target": "5.00"})
                    elif drift_ver == "v5":
                        conds.append({"label": "Odds <= 5", "met": odds_now <= 5.0,
                                      "current": f"{odds_now:.2f}", "target": "5.00"})

                    met = sum(1 for c in conds if c["met"])
                    total = len(conds)
                    if met >= 1 and met < total:
                        watchlist.append({**match_info, "strategy": "Odds Drift",
                                          "version": drift_ver.upper(), "conditions": conds,
                                          "met": met, "total": total, "proximity": round(met / total * 100)})

        # --- GOAL CLUSTERING watchlist ---
        if clustering_ver != "off":
            sot_max = max(sot_l, sot_v)
            # Check for recent goal
            recent_goal = False
            for i in range(len(rows) - 1, max(0, len(rows) - 4), -1):
                if i > 0:
                    curr_gl = (_to_float(rows[i].get("goles_local", "")) or 0)
                    curr_gv = (_to_float(rows[i].get("goles_visitante", "")) or 0)
                    prev_gl = (_to_float(rows[i-1].get("goles_local", "")) or 0)
                    prev_gv = (_to_float(rows[i-1].get("goles_visitante", "")) or 0)
                    if (int(curr_gl) + int(curr_gv)) > (int(prev_gl) + int(prev_gv)):
                        recent_goal = True
                        break

            conds = []
            conds.append({"label": "Gol reciente", "met": recent_goal})
            conds.append({"label": "Min 15-80", "met": 15 <= minuto <= 80,
                          "current": f"Min {int(minuto)}", "target": "15-80"})
            conds.append({"label": "SoT max >= 3", "met": sot_max >= 3,
                          "current": str(int(sot_max)), "target": "3"})
            if clustering_ver == "v3":
                conds.append({"label": "Min < 75", "met": minuto < 75,
                              "current": f"Min {int(minuto)}", "target": "75"})

            met = sum(1 for c in conds if c["met"])
            total = len(conds)
            if met >= 1 and met < total:
                watchlist.append({**match_info, "strategy": "Goal Clustering",
                                  "version": clustering_ver.upper(), "conditions": conds,
                                  "met": met, "total": total, "proximity": round(met / total * 100)})

        # --- PRESSURE COOKER watchlist ---
        if pressure_ver != "off":
            total_goals = int(gl) + int(gv)
            is_draw = gl == gv
            has_goals = total_goals >= 2
            conds = []
            conds.append({"label": "Empate", "met": is_draw})
            conds.append({"label": "Score >= 1-1", "met": has_goals,
                          "current": f"{int(gl)}-{int(gv)}", "target": "1-1+"})
            conds.append({"label": "Min 65-75", "met": 65 <= minuto <= 75,
                          "current": f"Min {int(minuto)}", "target": "65-75"})

            met = sum(1 for c in conds if c["met"])
            total = len(conds)
            if met >= 1 and met < total:
                watchlist.append({**match_info, "strategy": "Pressure Cooker",
                                  "version": pressure_ver.upper(), "conditions": conds,
                                  "met": met, "total": total, "proximity": round(met / total * 100)})

    # Sort by proximity descending
    watchlist.sort(key=lambda x: x["proximity"], reverse=True)
    return watchlist


def analyze_strategy_goal_clustering(min_dur: int = 1) -> dict:
    """
    Analiza Goal Clustering V2: Tras gol + SoT max >= 3

    Trigger: Gol recién marcado (min 15-80) + algún equipo tiene >= 3 SoT
    Apuesta: Back Over (total_actual + 0.5)

    Returns:
        {
            "total_matches": int,
            "total_goal_events": int,
            "summary": {
                "total_bets": int,
                "wins": int,
                "win_rate": float,
                "total_pl": float,
                "roi": float
            },
            "bets": [...]
        }
    """
    finished = _get_all_finished_matches()

    results = {
        "total_matches": 0,
        "total_goal_events": 0,
        "bets": []
    }

    for match_data in finished:
        results["total_matches"] += 1
        match_id = match_data["match_id"]
        match_name = match_data["name"]
        csv_path = _resolve_csv_path(match_id)

        # Skip matches with corrupted Over/Under odds
        if match_id in CORRUPTED_OVER_MATCHES:
            continue

        if not csv_path.exists():
            continue

        rows = _normalize_halftime_minutes(_read_csv_rows(csv_path))
        if len(rows) < 10:
            continue

        # Resultado final — usar última fila con scores válidos (evitar filas pre_partido al final)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))

        if gl_final is None or gv_final is None:
            continue

        total_final = int(gl_final) + int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Rastrear goles para detectar nuevos
        prev_total = None  # None = aún no hemos procesado ninguna fila válida
        bet_placed = False  # Flag: solo apostar UNA vez por partido

        for idx, row in enumerate(rows):
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))

            if gl is None or gv is None:
                continue

            total_now = int(gl) + int(gv)

            # Inicializar prev_total en la primera fila válida
            if prev_total is None:
                prev_total = total_now
                continue

            minuto = _to_float(row.get("minuto", ""))

            # ¿Hubo un gol nuevo?
            if total_now > prev_total:
                results["total_goal_events"] += 1

                # Solo apostar si aún no hemos apostado en este partido
                if not bet_placed and minuto is not None and 15 <= minuto <= 80:
                    # Filtro V2: SoT max >= 3
                    sot_l = _to_float(row.get("tiros_puerta_local", "")) or 0
                    sot_v = _to_float(row.get("tiros_puerta_visitante", "")) or 0
                    sot_max = max(int(sot_l), int(sot_v))

                    if sot_max >= 3:
                        # Min duration: wait min_dur rows before entering
                        if min_dur > 1:
                            end_idx = idx + min_dur - 1
                            if end_idx >= len(rows):
                                continue  # not enough rows remaining
                            row = rows[end_idx]

                        # Obtener cuotas Over
                        over_field = _get_over_odds_field(total_now)

                        if over_field:
                            over_odds = _to_float(row.get(over_field, ""))

                            # SKIP si no hay cuota disponible (evita P/L = 0)
                            if not over_odds or over_odds <= 0:
                                continue

                            # Target: al menos 1 gol más
                            target = total_now + 1
                            over_won = total_final >= target

                            # P/L
                            stake = 10
                            if over_won:
                                gross = (over_odds - 1) * stake
                                pl = gross * 0.95
                            else:
                                pl = -stake

                            # Version filters
                            passes_v3 = minuto < 60  # V3: entrada temprana

                            # V4: xG remaining > 0.8 (100% WR in backtest)
                            synth = _compute_synthetic_at_trigger(rows, idx)
                            xg_rem = synth.get("xg_remaining")
                            passes_v4 = xg_rem is not None and xg_rem > 0.8

                            # Guardar bet (solo si hay cuota válida)
                            _gc_entry_idx = (idx + min_dur - 1) if min_dur > 1 else idx
                            _stab_gc, _cons_gc = _count_odds_stability(rows, _gc_entry_idx, over_field, over_odds or 0)
                            pl = round((over_odds - 1) * stake * 0.95, 2) if over_won else -stake
                            pl_conservative = round((_cons_gc - 1) * stake * 0.95, 2) if over_won else -stake
                            results["bets"].append({
                                "match": match_name,
                                "match_id": match_id,
                                "minuto": int(minuto),
                                "score": f"{int(gl)}-{int(gv)}",
                                "score_at_trigger": f"{int(gl)}-{int(gv)}",
                                "sot_max": sot_max,
                                "back_over_odds": round(over_odds, 2),
                                "lay_trigger": _to_float(row.get(over_field.replace("back_", "lay_"), "")) or None,
                                "over_line": f"Over {total_now + 0.5}",
                                "ft_score": ft_score,
                                "won": over_won,
                                "pl": pl,
                                "pl_conservative": pl_conservative,
                                "conservative_odds": round(_cons_gc, 2),
                                "passes_v3": passes_v3,
                                "passes_v4": passes_v4,
                                "synth_xg_remaining": xg_rem,
                                "stability_count": _stab_gc,
                                "timestamp_utc": row.get("timestamp_utc", ""),
                                "País": row.get("País", "Desconocido"),
                                "Liga": row.get("Liga", "Desconocida"),
                            })

                            # Marcar que ya apostamos en este partido
                            bet_placed = True

            # Actualizar prev_total SIEMPRE (dentro o fuera del rango de minutos)
            prev_total = total_now

    # Calcular summary
    total_bets = len(results["bets"])
    wins = sum(1 for b in results["bets"] if b["won"])
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    total_pl = sum(b["pl"] for b in results["bets"])
    total_stake = total_bets * 10
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    v3_bets = [b for b in results["bets"] if b.get("passes_v3")]
    v3_n = len(v3_bets)
    v3_wins = sum(1 for b in v3_bets if b["won"])

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }
    results["summary_v3"] = {
        "total_bets": v3_n,
        "wins": v3_wins,
        "win_rate": round(v3_wins / v3_n * 100, 1) if v3_n > 0 else 0,
        "total_pl": round(sum(b["pl"] for b in v3_bets), 2),
        "roi": round(sum(b["pl"] for b in v3_bets) / (v3_n * 10) * 100, 1) if v3_n > 0 else 0,
    }

    return results


def analyze_strategy_pressure_cooker(min_dur: int = 1) -> dict:
    """
    Pressure Cooker V1: Back Over en empates con goles (min 65-75)

    Trigger: Empate 1-1+ entre min 65-75
    Apuesta: Back Over (total_actual + 0.5)
    Excluye: Empates 0-0

    Returns:
        {
            "total_matches": int,
            "draws_65_75": int,
            "summary": {...},
            "bets": [...]
        }
    """
    finished = _get_all_finished_matches()

    results = {
        "total_matches": 0,
        "draws_65_75": 0,
        "bets": []
    }

    for match_data in finished:
        results["total_matches"] += 1
        match_id = match_data["match_id"]
        match_name = match_data["name"]
        csv_path = _resolve_csv_path(match_id)

        if not csv_path.exists():
            continue

        rows = _normalize_halftime_minutes(_read_csv_rows(csv_path))
        if len(rows) < 20:
            continue

        # Resultado final — usar última fila con scores válidos (evitar filas pre_partido al final)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))

        if gl_final is None or gv_final is None:
            continue

        # Verificar que el partido finalizo (minuto >= 85)
        last_min = _to_float(last_row.get("minuto", ""))
        if last_min is None or last_min < 85:
            continue

        total_final = int(gl_final) + int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Buscar primera fila con empate 1-1+ entre min 65-75
        trigger_found = False
        for idx, row in enumerate(rows):
            if row.get("estado_partido") != "en_juego":
                continue

            minuto = _to_float(row.get("minuto", ""))
            if minuto is None or minuto < 65 or minuto > 75:
                continue

            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))

            if gl is None or gv is None:
                continue

            # Condicion: empate con goles (no 0-0)
            if gl != gv or (gl == 0 and gv == 0):
                continue

            if trigger_found:
                continue
            trigger_found = True

            # Min duration: wait min_dur rows before entering
            if min_dur > 1:
                end_idx = idx + min_dur - 1
                if end_idx >= len(rows):
                    continue  # not enough rows remaining
                row = rows[end_idx]

            total_goals = int(gl) + int(gv)
            results["draws_65_75"] += 1

            # Obtener cuotas Over
            over_field = _get_over_odds_field(total_goals)
            over_odds = _to_float(row.get(over_field, "")) if over_field else None

            if not over_odds or over_odds <= 1:
                continue

            # Validar score: verificar que al menos 2 filas antes y despues
            # tengan el mismo score (evitar glitches de 1 ciclo)
            actual_min = int(minuto)
            score_confirmed = False
            confirm_count = 0
            for check_row in rows:
                check_min = _to_float(check_row.get("minuto", ""))
                if check_min is None:
                    continue
                if abs(check_min - actual_min) <= 3:
                    check_gl = _to_float(check_row.get("goles_local", ""))
                    check_gv = _to_float(check_row.get("goles_visitante", ""))
                    if check_gl == gl and check_gv == gv:
                        confirm_count += 1
            score_confirmed = confirm_count >= 2

            if not score_confirmed:
                continue

            # Calcular deltas de momentum (informativo)
            # Buscar fila ~10 min antes
            past_row = None
            for r in rows:
                m = _to_float(r.get("minuto", ""))
                if m is not None and actual_min - 12 <= m <= actual_min - 8:
                    past_row = r

            sot_delta = 0
            corners_delta = 0
            shots_delta = 0
            if past_row:
                sot_now = (_to_float(row.get("tiros_puerta_local", "")) or 0) + (_to_float(row.get("tiros_puerta_visitante", "")) or 0)
                sot_past = (_to_float(past_row.get("tiros_puerta_local", "")) or 0) + (_to_float(past_row.get("tiros_puerta_visitante", "")) or 0)
                sot_delta = sot_now - sot_past

                corners_now = (_to_float(row.get("corners_local", "")) or 0) + (_to_float(row.get("corners_visitante", "")) or 0)
                corners_past = (_to_float(past_row.get("corners_local", "")) or 0) + (_to_float(past_row.get("corners_visitante", "")) or 0)
                corners_delta = corners_now - corners_past

                shots_now = (_to_float(row.get("tiros_local", "")) or 0) + (_to_float(row.get("tiros_visitante", "")) or 0)
                shots_past = (_to_float(past_row.get("tiros_local", "")) or 0) + (_to_float(past_row.get("tiros_visitante", "")) or 0)
                shots_delta = shots_now - shots_past

            # Resultado
            won = total_final > total_goals
            stake = 10
            over_line = f"Over {total_goals + 0.5}"

            _pc_entry_idx = (idx + min_dur - 1) if min_dur > 1 else idx
            _stab_pc, _cons_pc = _count_odds_stability(rows, _pc_entry_idx, over_field or "back_over25", over_odds or 0)
            pl = round((over_odds - 1) * stake * 0.95, 2) if won else -stake
            pl_conservative = round((_cons_pc - 1) * stake * 0.95, 2) if won else -stake

            results["bets"].append({
                "match": match_name,
                "match_id": match_id,
                "minuto": actual_min,
                "score": f"{int(gl)}-{int(gv)}",
                "back_over_odds": round(over_odds, 2),
                "lay_trigger": _to_float(row.get(over_field.replace("back_", "lay_"), "")) or None if over_field else None,
                "over_line": over_line,
                "ft_score": ft_score,
                "won": won,
                "pl": pl,
                "pl_conservative": pl_conservative,
                "conservative_odds": round(_cons_pc, 2),
                "sot_delta": int(sot_delta),
                "corners_delta": int(corners_delta),
                "shots_delta": int(shots_delta),
                "stability_count": _stab_pc,
                "timestamp_utc": row.get("timestamp_utc", ""),
                "País": row.get("País", "Desconocido"),
                "Liga": row.get("Liga", "Desconocida"),
            })

    # Calcular summary
    total_bets = len(results["bets"])
    wins = sum(1 for b in results["bets"] if b["won"])
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    total_pl = sum(b["pl"] for b in results["bets"])
    total_stake = total_bets * 10
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }

    return results


def analyze_strategy_tarde_asia(min_dur: int = 1) -> dict:
    """
    Tarde Asia High Scoring V1: Back Over 2.5 en partidos tarde de Asia/Alemania/Francia

    Trigger: Partidos entre 14-20h de ligas asiáticas, Bundesliga, Ligue 1/2
    Apuesta: Back Over 2.5 desde el inicio
    Estado: OFF - Solo tracking, no activa señales

    Returns:
        {
            "total_matches": int,
            "tarde_asia_matches": int,
            "summary": {...},
            "bets": [...]
        }
    """
    finished = _get_all_finished_matches()

    results = {
        "total_matches": 0,
        "tarde_asia_matches": 0,
        "bets": []
    }

    # Ligas objetivo (simplificado - en producción vendría de metadata)
    TARGET_LEAGUES = ["bundesliga", "ligue", "eredivisie", "j-league", "k-league", "asia"]

    for match_data in finished:
        results["total_matches"] += 1
        match_id = match_data["match_id"]
        match_name = match_data["name"]
        csv_path = _resolve_csv_path(match_id)

        if not csv_path.exists():
            continue

        rows = _normalize_halftime_minutes(_read_csv_rows(csv_path))
        if len(rows) < 20:
            continue

        # Resultado final — usar última fila con scores válidos (evitar filas pre_partido al final)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))

        if gl_final is None or gv_final is None:
            continue

        # Verificar que el partido finalizó
        last_min = _to_float(last_row.get("minuto", ""))
        if last_min is None or last_min < 85:
            continue

        total_final = int(gl_final) + int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Detectar liga (de URL o nombre del partido)
        liga_match = "Unknown"
        match_url = match_data.get("url", "").lower()
        match_name_lower = match_name.lower()

        # Detectar liga por keywords en URL
        if "bundesliga" in match_url or "bundesliga" in match_name_lower:
            liga_match = "Bundesliga"
        elif "ligue" in match_url or "ligue" in match_name_lower:
            liga_match = "Ligue"
        elif "eredivisie" in match_url or "eredivisie" in match_name_lower:
            liga_match = "Eredivisie"
        elif any(x in match_url for x in ["j-league", "jleague"]):
            liga_match = "J-League"
        elif any(x in match_url for x in ["k-league", "kleague"]):
            liga_match = "K-League"
        elif any(x in match_url for x in ["asia", "asiática", "asiatic"]):
            liga_match = "Asian League"

        # Fallback: detectar por nombres de equipos (para data histórica sin URL)
        if liga_match == "Unknown":
            # Dutch teams (Eredivisie)
            dutch_teams = ["ajax", "psv", "feyenoord", "az alkmaar", "twente", "utrecht", "heerenveen", "groningen", "vitesse", "nec", "fortuna sittard", "sparta", "heracles", "almere", "zwolle", "waalwijk", "excelsior", "volendam"]
            # German teams (Bundesliga)
            german_teams = ["bayern", "dortmund", "leipzig", "leverkusen", "frankfurt", "freiburg", "wolfsburg", "monchengladbach", "stuttgart", "hoffenheim", "bremen", "union berlin", "mainz", "bochum", "augsburg", "heidenheim", "darmstadt"]
            # French teams (Ligue 1/2)
            french_teams = ["psg", "marseille", "lyon", "monaco", "lille", "lens", "rennes", "nice", "nantes", "montpellier", "strasbourg", "brest", "reims", "toulouse", "lorient", "clermont", "havre", "metz"]
            # Asian teams (Middle East, J-League, K-League)
            asian_teams = ["al hilal", "al nassr", "al ahli", "al ittihad", "al shabab", "al ettifaq", "al fayha", "al fateh", "al raed", "al taawoun", "al wehda", "al sharjah", "al ain", "al jazira", "shabab", "baniyas", "kashima", "urawa", "yokohama", "gamba osaka", "kawasaki", "cerezo", "sanfrecce", "vissel", "jeonbuk", "ulsan", "pohang", "suwon", "jeonnam", "seoul", "busan", "shanghai", "guangzhou", "beijing", "shandong"]

            if any(team in match_name_lower for team in dutch_teams):
                liga_match = "Eredivisie"
            elif any(team in match_name_lower for team in german_teams):
                liga_match = "Bundesliga"
            elif any(team in match_name_lower for team in french_teams):
                liga_match = "Ligue"
            elif any(team in match_name_lower for team in asian_teams):
                liga_match = "Asian League"

        # Verificar si es liga objetivo
        is_target_league = liga_match != "Unknown"
        if not is_target_league:
            continue

        # Obtener hora UTC de primera fila
        # NOTA: Por simplicidad, no filtramos por hora (necesitaríamos timezone del partido)
        # En producción, esto vendría de metadata con timezone local
        first_row = rows[0]
        timestamp_utc = first_row.get("timestamp_utc", "")

        # Extraer hora UTC (solo para display, no filtramos por hora)
        hora_local = "Unknown"
        if timestamp_utc and "T" in timestamp_utc:
            try:
                hora_part = timestamp_utc.split("T")[1].split(":")[0]
                hora_int = int(hora_part)
                hora_local = f"{hora_int:02d}:00 UTC"
            except:
                hora_local = "N/A"

        # Si llegamos aquí, es un partido tarde de liga objetivo
        results["tarde_asia_matches"] += 1

        # Buscar primera fila con cuotas Over 2.5
        bet_placed = False
        for idx, row in enumerate(rows):
            if bet_placed:
                break

            minuto = _to_float(row.get("minuto", ""))
            if minuto is None or minuto > 15:  # Solo primeros 15 min
                continue

            # Obtener cuota Over 2.5
            over_25_odds = _to_float(row.get("back_over25", ""))
            if not over_25_odds or over_25_odds <= 1:
                continue

            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue

            # Min duration: wait min_dur rows before entering
            if min_dur > 1:
                end_idx = idx + min_dur - 1
                if end_idx >= len(rows):
                    continue  # not enough rows remaining
                row = rows[end_idx]
                _min_e = _to_float(row.get("minuto", ""))
                if _min_e is not None:
                    minuto = _min_e

            # Colocar apuesta
            bet_placed = True
            actual_min = int(minuto)
            score_at_trigger = f"{int(gl)}-{int(gv)}"

            # Resultado
            won = total_final > 2.5
            stake = 10
            _ta_entry_idx = (idx + min_dur - 1) if min_dur > 1 else idx
            _stab_ta, _cons_ta = _count_odds_stability(rows, _ta_entry_idx, "back_over25", over_25_odds or 0)
            pl = round((over_25_odds - 1) * stake * 0.95, 2) if won else -stake
            pl_conservative = round((_cons_ta - 1) * stake * 0.95, 2) if won else -stake

            results["bets"].append({
                "match": match_name,
                "match_id": match_id,
                "minuto": actual_min,
                "score": score_at_trigger,
                "back_over_odds": round(over_25_odds, 2),
                "lay_trigger": _to_float(row.get("lay_over25", "")) or None,
                "over_line": "Over 2.5",
                "ft_score": ft_score,
                "won": won,
                "pl": pl,
                "pl_conservative": pl_conservative,
                "conservative_odds": round(_cons_ta, 2),
                "liga": liga_match,
                "hora_local": hora_local,
                "stability_count": _stab_ta,
                "timestamp_utc": row.get("timestamp_utc", ""),
                "País": row.get("País", "Desconocido"),
                "Liga": row.get("Liga", "Desconocida"),
            })

    # Calcular summary
    total_bets = len(results["bets"])
    wins = sum(1 for b in results["bets"] if b["won"])
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    total_pl = sum(b["pl"] for b in results["bets"])
    total_stake = total_bets * 10
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }

    return results




def analyze_strategy_momentum_xg(version: str = "v1", min_dur: int = 1) -> dict:
    """
    Momentum Dominante x xG: BACK equipo con dominancia en tiros a puerta pero xG no convertido

    Concepto: Equipo dominante con xG alto pero pocos goles indica regresión a la media → apostar a que ganará.

    Versiones disponibles:
    - v1 (ULTRA RELAJADAS): SoT >=1, ratio >=1.1x, xG underperf >0.15, Min 10-80, Odds 1.4-6.0
      → 66.7% WR, 52.2% ROI (12 triggers)
    - v2 (MÁXIMAS): SoT >=1, ratio >=1.05x, xG underperf >0.1, Min 5-85, Odds 1.3-8.0
      → 60% WR, 68.7% ROI (15 triggers)

    Apuesta: BACK equipo dominante (Home o Away)

    Args:
        version: "v1" (ultra relajadas, más consistente) o "v2" (máximas, mayor ROI)

    Returns:
        {
            "total_matches": int,
            "momentum_triggers": int,
            "summary": {...},
            "bets": [...],
            "version": str
        }
    """
    # Configuración según versión
    if version == "v2":
        # V2 MÁXIMAS: Mayor ROI pero menos consistente
        config = {
            "sot_min": 1,
            "sot_ratio_min": 1.05,
            "xg_underperf_min": 0.1,
            "min_minute": 5,
            "max_minute": 85,
            "min_odds": 1.3,
            "max_odds": 8.0,
            "label": "MÁXIMAS"
        }
    else:  # v1 por defecto
        # V1 ULTRA RELAJADAS: Más consistente (66.7% WR)
        config = {
            "sot_min": 1,
            "sot_ratio_min": 1.1,
            "xg_underperf_min": 0.15,
            "min_minute": 10,
            "max_minute": 80,
            "min_odds": 1.4,
            "max_odds": 6.0,
            "label": "ULTRA RELAJADAS"
        }

    finished = _get_all_finished_matches()

    results = {
        "total_matches": 0,
        "momentum_triggers": 0,
        "bets": []
    }

    for match_data in finished:
        results["total_matches"] += 1
        match_id = match_data["match_id"]
        match_name = match_data["name"]
        csv_path = _resolve_csv_path(match_id)

        if not csv_path.exists():
            continue

        rows = _normalize_halftime_minutes(_read_csv_rows(csv_path))
        if len(rows) < 20:
            continue

        # Resultado final — usar última fila con scores válidos (evitar filas pre_partido al final)
        last_row = _final_result_row(rows)
        if last_row is None:
            continue
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))

        if gl_final is None or gv_final is None:
            continue

        # Verificar que finalizó
        last_min = _to_float(last_row.get("minuto", ""))
        if last_min is None or last_min < 85:
            continue

        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # Buscar trigger de momentum dominante
        bet_placed = False
        for idx, row in enumerate(rows):
            if bet_placed:
                break

            if row.get("estado_partido") != "en_juego":
                continue

            minuto = _to_float(row.get("minuto", ""))
            if minuto is None or minuto < config["min_minute"] or minuto > config["max_minute"]:
                continue

            # Stats necesarias
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            xg_local = _to_float(row.get("xg_local", ""))
            xg_visitante = _to_float(row.get("xg_visitante", ""))
            sot_local = _to_float(row.get("tiros_puerta_local", ""))
            sot_visitante = _to_float(row.get("tiros_puerta_visitante", ""))
            back_home_odds = _to_float(row.get("back_home", ""))
            back_away_odds = _to_float(row.get("back_away", ""))

            # Validar datos completos
            if None in [gl, gv, xg_local, xg_visitante, sot_local, sot_visitante,
                        back_home_odds, back_away_odds]:
                continue

            # Calcular xG underperformance
            xg_underperf_local = xg_local - gl
            xg_underperf_visitante = xg_visitante - gv

            # Determinar equipo dominante usando SHOTS ON TARGET
            dominant_team = None
            back_odds = None
            sot_ratio_used = 0

            # Local dominante: SoT superior + xG underperformance
            if sot_visitante > 0:
                sot_ratio_local = sot_local / sot_visitante
            else:
                sot_ratio_local = sot_local * 2 if sot_local >= config["sot_min"] else 0

            if (sot_local >= config["sot_min"] and
                sot_ratio_local >= config["sot_ratio_min"] and
                xg_underperf_local > config["xg_underperf_min"]):
                if config["min_odds"] <= back_home_odds <= config["max_odds"]:
                    dominant_team = "home"
                    back_odds = back_home_odds
                    sot_ratio_used = sot_ratio_local

            # Visitante dominante
            if sot_local > 0:
                sot_ratio_visitante = sot_visitante / sot_local
            else:
                sot_ratio_visitante = sot_visitante * 2 if sot_visitante >= config["sot_min"] else 0

            if (sot_visitante >= config["sot_min"] and
                sot_ratio_visitante >= config["sot_ratio_min"] and
                xg_underperf_visitante > config["xg_underperf_min"]):
                if config["min_odds"] <= back_away_odds <= config["max_odds"]:
                    # Si ambos son dominantes, tomar el más dominante
                    if dominant_team is None or xg_underperf_visitante > xg_underperf_local:
                        dominant_team = "away"
                        back_odds = back_away_odds
                        sot_ratio_used = sot_ratio_visitante

            if dominant_team is None:
                continue

            # Min duration: wait min_dur rows before entering
            if min_dur > 1:
                end_idx = idx + min_dur - 1
                if end_idx >= len(rows):
                    continue  # not enough rows remaining
                row = rows[end_idx]
                _min_e = _to_float(row.get("minuto", ""))
                if _min_e is not None:
                    minuto = _min_e

            # Trigger encontrado
            bet_placed = True
            results["momentum_triggers"] += 1

            # Verificar resultado
            if dominant_team == "home":
                won = gl_final > gv_final
                team_label = "Local"
                xg_underperf = xg_underperf_local
            else:
                won = gv_final > gl_final
                team_label = "Visitante"
                xg_underperf = xg_underperf_visitante

            # Calcular P/L con cuota conservadora (mínimo en ventana de estabilidad)
            stake = 10
            _mx_odds_col = "back_home" if dominant_team == "home" else "back_away"
            _mx_entry_idx = (idx + min_dur - 1) if min_dur > 1 else idx
            _stab_mx, _cons_mx = _count_odds_stability(rows, _mx_entry_idx, _mx_odds_col, back_odds or 0)
            pl = round((back_odds - 1) * stake * 0.95, 2) if won else -stake
            pl_conservative = round((_cons_mx - 1) * stake * 0.95, 2) if won else -stake

            # Calcular riesgo por tiempo + marcador
            risk_info = calculate_time_score_risk(
                strategy=f"momentum_xg_{version}",
                minute=minuto,
                home_score=int(gl),
                away_score=int(gv),
                dominant_team=dominant_team
            )

            _mx_lay_col = "lay_home" if dominant_team == "home" else "lay_away"
            results["bets"].append({
                "match": match_name,
                "match_id": match_id,
                "minuto": int(minuto),
                "score_at_trigger": f"{int(gl)}-{int(gv)}",
                "dominant_team": team_label,
                "sot_ratio": round(sot_ratio_used, 2),
                "xg_underperf": round(xg_underperf, 2),
                "back_odds": round(back_odds, 2),
                "lay_trigger": _to_float(row.get(_mx_lay_col, "")) or None,
                "ft_score": ft_score,
                "won": won,
                "pl": pl,
                "pl_conservative": pl_conservative,
                "conservative_odds": round(_cons_mx, 2),
                "stability_count": _stab_mx,
                "timestamp_utc": row.get("timestamp_utc", ""),
                "risk_level": risk_info["risk_level"],
                "risk_reason": risk_info["risk_reason"],
                "time_remaining": risk_info["time_remaining"],
                "deficit": risk_info["deficit"],
                "País": row.get("País", "Desconocido"),
                "Liga": row.get("Liga", "Desconocida"),
            })

    # Calcular summary
    total_bets = len(results["bets"])
    wins = sum(1 for b in results["bets"] if b["won"])
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    total_pl = sum(b["pl"] for b in results["bets"])
    total_stake = total_bets * 10
    roi = (total_pl / total_stake * 100) if total_stake > 0 else 0

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }

    results["version"] = version
    results["config_label"] = config["label"]

    return results
