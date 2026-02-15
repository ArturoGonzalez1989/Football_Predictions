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

                    # IMPORTANTE: Sobrescribir status basándose en el estado real del partido
                    estado_partido = last_row.get("estado_partido", "").strip()
                    if estado_partido == "finalizado":
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
                    elif estado_partido == "pre_partido":
                        # Partido aún no ha empezado, marcarlo como upcoming
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


def _get_cached_finished_data() -> list[dict]:
    """Get all finished matches with pre-loaded CSV rows. Cached for 5 min."""
    global _analytics_cache, _analytics_cache_time
    import time as _time

    now = _time.time()
    if _analytics_cache and (now - _analytics_cache_time) < _ANALYTICS_CACHE_TTL:
        return _analytics_cache.get("finished", [])

    # Rebuild cache
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
