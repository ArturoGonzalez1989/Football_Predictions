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
    """Find the CSV file for a match_id, handling URL-encoded filenames."""
    path = DATA_DIR / f"partido_{match_id}.csv"
    if path.exists():
        return path
    # Try URL-encoded version (FastAPI decodes path params)
    encoded = quote(match_id, safe="-")
    path2 = DATA_DIR / f"partido_{encoded}.csv"
    if path2.exists():
        return path2
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
    m = re.search(r"([a-z0-9%-]+-apuestas-\d+)", url)
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
            if start_time:
                if now >= start_time:
                    elapsed = (now - start_time).total_seconds() / 60
                    if elapsed <= 130:
                        status = "live"
                        match_minute = int(min(elapsed, 90))
                    else:
                        status = "finished"
                else:
                    status = "upcoming"

            csv_path = DATA_DIR / f"partido_{match_id}.csv"
            capture_count = 0
            last_capture = None
            last_capture_ago_seconds = None
            if csv_path.exists():
                rows = _read_csv_rows(csv_path)
                capture_count = len(rows)
                if rows:
                    ts = rows[-1].get("timestamp_utc", "")
                    if ts:
                        last_capture = ts
                        try:
                            last_dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                            # Timestamps in CSV are UTC, so compare with UTC now
                            last_capture_ago_seconds = int((now_utc - last_dt).total_seconds())
                        except Exception:
                            pass

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
        capture = {
            "timestamp": row.get("timestamp_utc", ""),
            "minuto": row.get("minuto", ""),
            "goles": f"{row.get('goles_local', '?')}-{row.get('goles_visitante', '?')}",
            "xg": f"{row.get('xg_local', '')}-{row.get('xg_visitante', '')}",
            "posesion": f"{row.get('posesion_local', '')}-{row.get('posesion_visitante', '')}",
            "corners": f"{row.get('corners_local', '')}-{row.get('corners_visitante', '')}",
            "tiros": f"{row.get('tiros_local', '')}-{row.get('tiros_visitante', '')}",
        }
        captures.append(capture)

    # Quality score
    total_filled = 0
    total_possible = 0
    for row in rows:
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
        for back_col, _ in ODDS_COLUMNS[:3]:  # Solo Match Odds para timeline
            point[back_col] = _to_float(row.get(back_col, ""))
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
