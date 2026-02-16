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
            minute_val = int(m.replace("'", "").strip()) if m else None
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
            minute_val = int(m.replace("'", "").strip()) if m else None
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

    games = load_games()
    finished = []
    for game in games:
        if game["status"] == "finished" and game["csv_exists"]:
            csv_path = _resolve_csv_path(game["match_id"])
            if csv_path.exists():
                rows = _read_csv_rows(csv_path)
                finished.append({
                    "match_id": game["match_id"],
                    "name": game["name"],
                    "csv_path": csv_path,
                    "rows": rows,
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
    """Calculate coverage percentage for each stat field across all matches."""
    finished_matches = _get_all_finished_matches()

    if not finished_matches:
        return {"fields": []}

    # Count non-null values for each stat column
    field_counts = {col: {"filled": 0, "total": 0} for col in STAT_COLUMNS}

    for match in finished_matches:
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        for row in rows:
            # Only count in-play rows
            estado = row.get("estado_partido", "").strip()
            if estado in ("pre_partido", ""):
                continue
            for col in STAT_COLUMNS:
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


@_cached_result("strategy_back_draw_00")
def analyze_strategy_back_draw_00() -> dict:
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

        # Find first row where min >= 30 and score is 0-0
        trigger_row = None
        for row in rows:
            minuto = _to_float(row.get("minuto", ""))
            gl = _to_float(row.get("goles_local", ""))
            gv = _to_float(row.get("goles_visitante", ""))
            if minuto is not None and gl is not None and gv is not None:
                if minuto >= 30 and int(gl) == 0 and int(gv) == 0:
                    trigger_row = row
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

        # Final result from last row
        last_row = rows[-1]
        gl_final = _to_float(last_row.get("goles_local", ""))
        gv_final = _to_float(last_row.get("goles_visitante", ""))
        if gl_final is None or gv_final is None:
            continue

        draw_won = int(gl_final) == int(gv_final)
        ft_score = f"{int(gl_final)}-{int(gv_final)}"

        # P/L calculation (stake 10, 5% commission on winnings)
        stake = 10
        if draw_won and back_draw:
            gross = (back_draw - 1) * stake
            pl = gross * 0.95  # net of commission
        else:
            pl = -stake

        # Check strategy filters
        passes_xg_05 = xg_total is not None and xg_total < 0.5
        passes_xg_06 = xg_total is not None and xg_total < 0.6
        passes_poss_20 = poss_diff is not None and poss_diff < 20
        passes_poss_25 = poss_diff is not None and poss_diff < 25
        passes_shots = shots_total is not None and shots_total < 8

        passes_v2 = passes_xg_05 and passes_poss_20 and passes_shots
        passes_v15 = passes_xg_06 and passes_poss_25  # V1.5: xG<0.6 + PD<25%
        passes_v2r = passes_xg_06 and passes_poss_20 and passes_shots  # V2r: xG<0.6 + PD<20% + shots<8

        bets.append({
            "match": match["name"],
            "match_id": match["match_id"],
            "minuto": minuto_trigger,
            "back_draw": round(back_draw, 2) if back_draw else None,
            "xg_total": round(xg_total, 2) if xg_total is not None else None,
            "xg_max": round(xg_max, 2) if xg_max is not None else None,
            "sot_total": sot_total,
            "poss_diff": round(poss_diff, 1) if poss_diff is not None else None,
            "shots_total": shots_total,
            "bfed_prematch": bfed,
            "ft_score": ft_score,
            "won": draw_won,
            "pl": round(pl, 2),
            "passes_v2": passes_v2,
            "passes_v15": passes_v15,
            "passes_v2r": passes_v2r,
            "timestamp_utc": trigger_row.get("timestamp_utc", ""),
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
        },
        "bets": bets,
    }


# ── xG Underperformance Strategy ────────────────────────────────────────

def _get_over_odds_field(total_goals: int) -> str:
    """Return CSV column name for Back Over (total_goals + 0.5)."""
    return {0: "back_over05", 1: "back_over15", 2: "back_over25",
            3: "back_over35", 4: "back_over45"}.get(total_goals, "")


@_cached_result("strategy_xg_underperformance")
def analyze_strategy_xg_underperformance() -> dict:
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
        rows = match.get("rows") or _read_csv_rows(match["csv_path"])
        if not rows or len(rows) < 5:
            continue

        # Final result
        last_row = rows[-1]
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

        for row in rows:
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
                    "over_line": f"Over {total_at_trigger + 0.5}",
                    "sot_team": sot_int,
                    "poss_team": round(poss_t, 1) if poss_t is not None else None,
                    "shots_team": shots_int,
                    "ft_score": ft_score,
                    "won": more_goals,
                    "pl": round(pl, 2),
                    "passes_v2": passes_v2,
                    "timestamp_utc": row.get("timestamp_utc", ""),
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
        },
        "bets": bets,
    }


# ── Odds Drift Contrarian Strategy ──────────────────────────────────────

@_cached_result("strategy_odds_drift")
def analyze_strategy_odds_drift() -> dict:
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

        # Build list of (minuto, row) with valid data
        data_points = []
        for row in rows:
            m = _to_float(row.get("minuto", ""))
            if m is None:
                continue
            bh = _to_float(row.get("back_home", ""))
            ba = _to_float(row.get("back_away", ""))
            data_points.append((m, row, bh, ba))

        triggered = {"home": False, "away": False}

        for idx in range(1, len(data_points)):
            curr_min, curr_row, curr_bh, curr_ba = data_points[idx]
            if curr_min < MIN_MINUTE or curr_min > MAX_MINUTE:
                continue

            gl = _to_float(curr_row.get("goles_local", ""))
            gv = _to_float(curr_row.get("goles_visitante", ""))
            if gl is None or gv is None:
                continue
            gl_i, gv_i = int(gl), int(gv)

            # Look back within window
            for prev_idx in range(idx - 1, -1, -1):
                prev_min, prev_row, prev_bh, prev_ba = data_points[prev_idx]
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

                    triggered[team] = True
                    goal_diff = team_goals - opp_goals
                    score_at = f"{gl_i}-{gv_i}"

                    # Check if team wins the match
                    if team == "home":
                        won = ft_gl > ft_gv
                    else:
                        won = ft_gv > ft_gl

                    if won:
                        pl = round((curr_odds - 1) * STAKE * (1 - COMMISSION), 2)
                    else:
                        pl = -STAKE

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

                    bets.append({
                        "match": match["name"],
                        "match_id": match["match_id"],
                        "minuto": curr_min,
                        "score_at_trigger": score_at,
                        "team": team,
                        "goal_diff": goal_diff,
                        "odds_before": round(prev_odds, 2),
                        "back_odds": round(curr_odds, 2),
                        "drift_pct": round(drift * 100, 1),
                        "sot_team": int(sot_t) if sot_t is not None else None,
                        "poss_team": round(poss_t, 1) if poss_t is not None else None,
                        "shots_team": int(shots_t) if shots_t is not None else None,
                        "ft_score": ft_score,
                        "won": won,
                        "pl": round(pl, 2),
                        "passes_v2": passes_v2,
                        "passes_v3": passes_v3,
                        "passes_v4": passes_v4,
                        "timestamp_utc": curr_row.get("timestamp_utc", ""),
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
        },
        "bets": bets,
    }


# ── Cartera (Portfolio) ─────────────────────────────────────────────────

@_cached_result("cartera")
def analyze_cartera() -> dict:
    """Combined portfolio view of all strategies with flat and managed bankroll simulations."""
    draw_data = analyze_strategy_back_draw_00()
    xg_data = analyze_strategy_xg_underperformance()
    drift_data = analyze_strategy_odds_drift()
    clustering_data = analyze_strategy_goal_clustering()
    pressure_data = analyze_strategy_pressure_cooker()

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

    return {
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
        },
        "bets": all_bets,
    }


def _log_signal_to_csv(signal: dict):
    """Registra una señal en el archivo signals_log.csv para auditoría.
    Solo registra la PRIMERA vez que se detecta una señal (match_id + strategy).
    Evita duplicados si la señal sigue activa en múltiples refreshes.
    """
    import csv
    from datetime import datetime
    from pathlib import Path

    log_file = Path(__file__).parent.parent.parent / "signals_log.csv"

    match_id = signal.get("match_id", "")
    strategy = signal.get("strategy", "")

    # Verificar si ya existe esta combinación match_id + strategy
    if log_file.exists():
        with open(log_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for existing_row in reader:
                if (existing_row.get("match_id") == match_id and
                    existing_row.get("strategy") == strategy):
                    # Ya existe, no loggear de nuevo
                    return

    # Preparar datos para CSV
    row = {
        "timestamp_utc": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "match_id": match_id,
        "match_name": signal.get("match_name", ""),
        "match_url": signal.get("match_url", ""),
        "strategy": strategy,
        "strategy_name": signal.get("strategy_name", ""),
        "minute": signal.get("minute", ""),
        "score": signal.get("score", ""),
        "recommendation": signal.get("recommendation", ""),
        "back_odds": signal.get("back_odds", ""),
        "min_odds": signal.get("min_odds", ""),
        "expected_value": signal.get("expected_value", ""),
        "confidence": signal.get("confidence", ""),
        "win_rate_historical": signal.get("win_rate_historical", ""),
        "roi_historical": signal.get("roi_historical", ""),
        "sample_size": signal.get("sample_size", ""),
        "conditions": str(signal.get("entry_conditions", ""))
    }

    # Escribir en CSV (solo si no existe)
    file_exists = log_file.exists()
    with open(log_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def detect_betting_signals() -> dict:
    """
    Detect live betting opportunities based on portfolio strategies.
    Evaluates LIVE matches for entry conditions of the 3 strategies.
    """
    # Strategy metadata (from historical backtesting in cartera_final.md)
    STRATEGY_META = {
        "back_draw_00_v2r": {
            "win_rate": 0.571,  # 57.1% from backtest
            "avg_odds": 6.5,    # Average back draw odds
            "roi": 0.502,       # 50.2% ROI
            "sample_size": 7,
            "description": "Partidos trabados sin goles ni ocasiones"
        },
        "xg_underperformance_v2": {
            "win_rate": 0.727,  # 72.7% from backtest
            "avg_odds": 2.2,    # Average over odds
            "roi": 0.247,       # 24.7% ROI
            "sample_size": 11,
            "description": "Equipo perdiendo pero atacando intensamente"
        },
        "odds_drift_contrarian_v1": {
            "win_rate": 0.667,  # 66.7% from backtest
            "avg_odds": 2.5,    # Average odds
            "roi": 1.423,       # 142.3% ROI
            "sample_size": 27,
            "description": "Mercado abandona al equipo ganador erróneamente"
        },
        "goal_clustering_v2": {
            "win_rate": 0.750,  # 75.0% from backtest
            "avg_odds": 2.3,    # Average over odds
            "roi": 0.727,       # 72.7% ROI
            "sample_size": 44,
            "description": "Después de un gol, alta probabilidad de más goles"
        },
        "pressure_cooker_v1": {
            "win_rate": 0.812,  # 81.2% from backtest (empates 1-1+)
            "avg_odds": 2.1,    # Average over odds
            "roi": 0.819,       # 81.9% ROI
            "sample_size": 16,
            "description": "Empates con goles (1-1+) entre min 65-75 tienden a romper"
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

    games = load_games()
    live_matches = [g for g in games if g["status"] == "live"]

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

        goles_local = _to_float(latest.get("goles_local", "")) or 0
        goles_visitante = _to_float(latest.get("goles_visitante", "")) or 0
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

        # === STRATEGY 1: Back Empate V2r (0-0 at min 30+) ===
        if (minuto >= 30 and
            goles_local == 0 and goles_visitante == 0 and
            xg_local is not None and xg_visitante is not None):

            xg_total = xg_local + xg_visitante
            tiros_total = tiros_local + tiros_visitante

            # Posesión dominante: diferencia de posesión < 20%
            poss_diff = abs((posesion_local or 50) - (posesion_visitante or 50))

            if xg_total < 0.6 and poss_diff < 20 and tiros_total < 8:
                meta = STRATEGY_META["back_draw_00_v2r"]
                min_odds = calculate_min_odds(meta["win_rate"])
                ev = calculate_ev(back_draw, meta["win_rate"]) if back_draw else 0.0
                odds_ok = is_odds_favorable(back_draw, min_odds) if back_draw else False

                signal = {
                    "match_id": match_id,
                    "match_name": match["name"],
                    "match_url": match["url"],
                    "strategy": "back_draw_00_v2r",
                    "strategy_name": "Back Empate 0-0 (V2r)",
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
                    "thresholds": {
                        "xg_total": "< 0.6",
                        "possession_diff": "< 20%",
                        "total_shots": "< 8"
                    }
                }
                signals.append(signal)
                _log_signal_to_csv(signal)

        # === STRATEGY 2: xG Underperformance V2 ===
        if minuto >= 15 and xg_local is not None and xg_visitante is not None:
            # Check home team losing
            if goles_local < goles_visitante:
                xg_excess = xg_local - goles_local
                if xg_excess >= 0.5 and tiros_puerta_local >= 2:
                    meta = STRATEGY_META["xg_underperformance_v2"]
                    min_odds = calculate_min_odds(meta["win_rate"])
                    # Note: back_odds would need over/under odds from Betfair
                    # Using average for metadata, but can't validate actual odds

                    total_goles = int(goles_local) + int(goles_visitante)
                    over_line = total_goles + 0.5
                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": "xg_underperformance_v2",
                        "strategy_name": "xG Underperformance (V2)",
                        "minute": int(minuto),
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "recommendation": f"BACK Over {over_line}",
                        "back_odds": None,  # Would need over/under odds from capture
                        "min_odds": round(min_odds, 2),
                        "expected_value": None,  # Can't calculate without actual odds
                        "odds_favorable": None,  # Can't validate without actual odds
                        "confidence": "high",  # Based on strong WR (72.7%)
                        "win_rate_historical": round(meta["win_rate"] * 100, 1),
                        "roi_historical": round(meta["roi"] * 100, 1),
                        "sample_size": meta["sample_size"],
                        "description": meta["description"],
                        "entry_conditions": {
                            "team": "Home",
                            "xg_excess": round(xg_excess, 2),
                            "shots_on_target": int(tiros_puerta_local)
                        },
                        "thresholds": {
                            "xg_excess": ">= 0.5",
                            "shots_on_target": ">= 2"
                        }
                    }
                    signals.append(signal)
                    _log_signal_to_csv(signal)

            # Check away team losing
            if goles_visitante < goles_local:
                xg_excess = xg_visitante - goles_visitante
                if xg_excess >= 0.5 and tiros_puerta_visitante >= 2:
                    meta = STRATEGY_META["xg_underperformance_v2"]
                    min_odds = calculate_min_odds(meta["win_rate"])

                    total_goles = int(goles_local) + int(goles_visitante)
                    over_line = total_goles + 0.5
                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": "xg_underperformance_v2",
                        "strategy_name": "xG Underperformance (V2)",
                        "minute": int(minuto),
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "recommendation": f"BACK Over {over_line}",
                        "back_odds": None,
                        "min_odds": round(min_odds, 2),
                        "expected_value": None,
                        "odds_favorable": None,
                        "confidence": "high",
                        "win_rate_historical": round(meta["win_rate"] * 100, 1),
                        "roi_historical": round(meta["roi"] * 100, 1),
                        "sample_size": meta["sample_size"],
                        "description": meta["description"],
                        "entry_conditions": {
                            "team": "Away",
                            "xg_excess": round(xg_excess, 2),
                            "shots_on_target": int(tiros_puerta_visitante)
                        },
                        "thresholds": {
                            "xg_excess": ">= 0.5",
                            "shots_on_target": ">= 2"
                        }
                    }
                    signals.append(signal)
                    _log_signal_to_csv(signal)

        # === STRATEGY 3: Odds Drift Contrarian V1 ===
        # Team winning 1-0 with odds drift >= 25% in last 10min
        if (goles_local == 1 and goles_visitante == 0) or (goles_local == 0 and goles_visitante == 1):
            # Get odds from 10 minutes ago
            target_minute = minuto - 10
            historical_row = None

            for row in reversed(rows):
                row_min = _to_float(row.get("minuto", ""))
                if row_min is not None and row_min <= target_minute:
                    historical_row = row
                    break

            if historical_row:
                if goles_local == 1:
                    # Home winning, check home odds drift
                    odds_before = _to_float(historical_row.get("back_home", ""))
                    odds_now = back_home

                    if odds_before and odds_now and odds_before > 0:
                        drift_pct = ((odds_now - odds_before) / odds_before) * 100

                        if drift_pct >= 25:
                            meta = STRATEGY_META["odds_drift_contrarian_v1"]
                            min_odds = calculate_min_odds(meta["win_rate"])
                            ev = calculate_ev(odds_now, meta["win_rate"])
                            odds_ok = is_odds_favorable(odds_now, min_odds)

                            signal = {
                                "match_id": match_id,
                                "match_name": match["name"],
                                "match_url": match["url"],
                                "strategy": "odds_drift_contrarian_v1",
                                "strategy_name": "Odds Drift Contrarian (V1)",
                                "minute": int(minuto),
                                "score": f"{int(goles_local)}-{int(goles_visitante)}",
                                "recommendation": f"BACK HOME @ {odds_now:.2f}",
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
                                    "team": "Home",
                                    "odds_before": round(odds_before, 2),
                                    "odds_now": round(odds_now, 2),
                                    "drift_pct": round(drift_pct, 1)
                                },
                                "thresholds": {
                                    "drift_pct": ">= 25%"
                                }
                            }
                            signals.append(signal)
                            _log_signal_to_csv(signal)
                else:
                    # Away winning, check away odds drift
                    odds_before = _to_float(historical_row.get("back_away", ""))
                    odds_now = back_away

                    if odds_before and odds_now and odds_before > 0:
                        drift_pct = ((odds_now - odds_before) / odds_before) * 100

                        if drift_pct >= 25:
                            meta = STRATEGY_META["odds_drift_contrarian_v1"]
                            min_odds = calculate_min_odds(meta["win_rate"])
                            ev = calculate_ev(odds_now, meta["win_rate"])
                            odds_ok = is_odds_favorable(odds_now, min_odds)

                            signal = {
                                "match_id": match_id,
                                "match_name": match["name"],
                                "match_url": match["url"],
                                "strategy": "odds_drift_contrarian_v1",
                                "strategy_name": "Odds Drift Contrarian (V1)",
                                "minute": int(minuto),
                                "score": f"{int(goles_local)}-{int(goles_visitante)}",
                                "recommendation": f"BACK AWAY @ {odds_now:.2f}",
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
                                    "team": "Away",
                                    "odds_before": round(odds_before, 2),
                                    "odds_now": round(odds_now, 2),
                                    "drift_pct": round(drift_pct, 1)
                                },
                                "thresholds": {
                                    "drift_pct": ">= 25%"
                                }
                            }
                            signals.append(signal)
                            _log_signal_to_csv(signal)

        # === STRATEGY 4: Goal Clustering V2 ===
        # After a goal (min 15-80) + either team has >= 3 shots on target
        # Check last few captures for recent goal events
        if len(rows) >= 2 and 15 <= minuto <= 80:
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
                # Check if either team has >= 3 shots on target
                sot_max = max(tiros_puerta_local, tiros_puerta_visitante)

                if sot_max >= 3:
                    total_actual = int(goles_local) + int(goles_visitante)
                    over_line = total_actual + 0.5

                    meta = STRATEGY_META["goal_clustering_v2"]
                    min_odds = calculate_min_odds(meta["win_rate"])
                    # Note: Would need actual over/under odds from Betfair
                    # Using None since we don't have those odds in current captures

                    signal = {
                        "match_id": match_id,
                        "match_name": match["name"],
                        "match_url": match["url"],
                        "strategy": "goal_clustering_v2",
                        "strategy_name": "Goal Clustering (V2)",
                        "minute": int(minuto),
                        "score": f"{int(goles_local)}-{int(goles_visitante)}",
                        "recommendation": f"BACK Over {over_line}",
                        "back_odds": None,  # Would need over/under odds from capture
                        "min_odds": round(min_odds, 2),
                        "expected_value": None,  # Can't calculate without actual odds
                        "odds_favorable": None,  # Can't validate without actual odds
                        "confidence": "high",  # Based on strong WR (75.0%)
                        "win_rate_historical": round(meta["win_rate"] * 100, 1),
                        "roi_historical": round(meta["roi"] * 100, 1),
                        "sample_size": meta["sample_size"],
                        "description": meta["description"],
                        "entry_conditions": {
                            "goal_minute": goal_minute,
                            "sot_max": int(sot_max),
                            "total_goals": total_actual
                        },
                        "thresholds": {
                            "minute_range": "15-80",
                            "sot_max": ">= 3"
                        }
                    }
                    signals.append(signal)
                    _log_signal_to_csv(signal)

        # === STRATEGY 5: Pressure Cooker V1 (draw 1-1+ at min 65-75) ===
        total_goals = int(goles_local) + int(goles_visitante)
        is_draw = goles_local == goles_visitante
        has_goals = total_goals >= 2  # at least 1-1

        if (65 <= minuto <= 75 and is_draw and has_goals):
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

                meta = STRATEGY_META["pressure_cooker_v1"]
                min_odds = calculate_min_odds(meta["win_rate"])

                signal = {
                    "match_id": match_id,
                    "match_name": match["name"],
                    "match_url": match["url"],
                    "strategy": "pressure_cooker_v1",
                    "strategy_name": "Pressure Cooker (V1)",
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
                signals.append(signal)
                _log_signal_to_csv(signal)

    return {
        "total_signals": len(signals),
        "live_matches": len(live_matches),
        "signals": signals
    }

def analyze_strategy_goal_clustering() -> dict:
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

        if not csv_path.exists():
            continue

        rows = _read_csv_rows(csv_path)
        if len(rows) < 10:
            continue

        # Resultado final
        last_row = rows[-1]
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

                            # Guardar bet (solo si hay cuota válida)
                            results["bets"].append({
                                "match": match_name,
                                "match_id": match_id,
                                "minuto": int(minuto),
                                "score": f"{int(gl)}-{int(gv)}",
                                "sot_max": sot_max,
                                "back_over_odds": round(over_odds, 2),
                                "ft_score": ft_score,
                                "won": over_won,
                                "pl": round(pl, 2),
                                "timestamp_utc": row.get("timestamp_utc", "")
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

    results["summary"] = {
        "total_bets": total_bets,
        "wins": wins,
        "win_rate": round(win_rate, 1),
        "total_pl": round(total_pl, 2),
        "roi": round(roi, 1)
    }

    return results


def analyze_strategy_pressure_cooker() -> dict:
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

        rows = _read_csv_rows(csv_path)
        if len(rows) < 20:
            continue

        # Resultado final
        last_row = rows[-1]
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
        for row in rows:
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
            if won:
                pl = round((over_odds - 1) * stake * 0.95, 2)
            else:
                pl = -stake

            over_line = f"Over {total_goals + 0.5}"

            results["bets"].append({
                "match": match_name,
                "match_id": match_id,
                "minuto": actual_min,
                "score": f"{int(gl)}-{int(gv)}",
                "back_over_odds": round(over_odds, 2),
                "over_line": over_line,
                "ft_score": ft_score,
                "won": won,
                "pl": round(pl, 2),
                "sot_delta": int(sot_delta),
                "corners_delta": int(corners_delta),
                "shots_delta": int(shots_delta),
                "timestamp_utc": row.get("timestamp_utc", "")
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
