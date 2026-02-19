"""
API endpoints para gestion de apuestas realizadas (paper trading y reales).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import csv
import re
from typing import Optional, Literal

from utils.csv_reader import _resolve_csv_path, _read_csv_rows, _to_float

router = APIRouter()

# Path to placed bets CSV
PLACED_BETS_CSV = Path(__file__).parent.parent.parent.parent / "placed_bets.csv"
GAMES_CSV = Path(__file__).parent.parent.parent.parent / "games.csv"

CSV_HEADERS = [
    'id', 'timestamp_utc', 'match_id', 'match_name', 'match_url',
    'strategy', 'strategy_name', 'minute', 'score', 'recommendation',
    'back_odds', 'min_odds', 'expected_value', 'confidence',
    'win_rate_historical', 'roi_historical', 'sample_size',
    'bet_type', 'stake', 'notes', 'status', 'result', 'pl'
]


class PlaceBetRequest(BaseModel):
    """Request para registrar una apuesta realizada"""
    match_id: str
    match_name: str
    match_url: str
    strategy: str
    strategy_name: str
    minute: int
    score: str
    recommendation: str
    back_odds: Optional[float] = None
    min_odds: Optional[float] = None
    expected_value: Optional[float] = None
    confidence: str
    win_rate_historical: Optional[float] = None
    roi_historical: Optional[float] = None
    sample_size: Optional[int] = None
    # User input fields
    bet_type: Literal["paper", "real"]
    stake: float
    notes: Optional[str] = None


class PlacedBet(BaseModel):
    """Respuesta con la apuesta registrada"""
    id: int
    timestamp_utc: str
    match_id: str
    match_name: str
    bet_type: str
    stake: float
    recommendation: str
    back_odds: Optional[float]
    status: str  # "pending", "won", "lost"


def _get_active_match_ids() -> set[str]:
    """Obtiene el conjunto de match_ids que están actualmente en games.csv"""
    if not GAMES_CSV.exists():
        return set()

    active_ids = set()
    try:
        with open(GAMES_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get('url', '').strip()
                if url:
                    # Extract match_id from URL
                    # Example: https://.../partido-x-y-apuestas-12345 -> partido-x-y-apuestas-12345
                    match = re.search(r'([^/]+apuestas-\d+)', url)
                    if match:
                        active_ids.add(match.group(1))
    except Exception:
        pass

    return active_ids


def _ensure_csv_exists():
    """Crea el CSV con headers si no existe"""
    if not PLACED_BETS_CSV.exists():
        with open(PLACED_BETS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)


def _get_next_id() -> int:
    """Obtiene el siguiente ID disponible"""
    if not PLACED_BETS_CSV.exists():
        return 1

    with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not rows:
            return 1
        return max(int(row['id']) for row in rows if row.get('id', '').isdigit()) + 1


def _check_would_win(recommendation: str, gl: float, gv: float) -> bool:
    """Determina si la apuesta ganaria con el marcador actual."""
    rec = recommendation.upper()

    # BACK DRAW
    if "DRAW" in rec:
        return int(gl) == int(gv)

    # BACK Over X.5
    m = re.search(r"OVER\s+(\d+\.?\d*)", rec)
    if m:
        line = float(m.group(1))
        return (gl + gv) > line

    # BACK HOME
    if "HOME" in rec:
        return gl > gv

    # BACK AWAY
    if "AWAY" in rec:
        return gv > gl

    return False


def _enrich_with_live_data(bet: dict, is_match_active: bool = True) -> dict:
    """Enriquecer un bet pendiente con datos live del CSV del partido.

    Args:
        bet: Diccionario con los datos de la apuesta
        is_match_active: True si el partido está en games.csv, False si ya fue eliminado
    """
    match_id = bet.get("match_id", "")
    if not match_id:
        return bet

    try:
        csv_path = _resolve_csv_path(match_id)
        rows = _read_csv_rows(csv_path)
        if not rows:
            # Si no hay CSV y el partido no está activo, marcar como perdida
            if not is_match_active:
                bet["status"] = "lost"
                bet["result"] = "lost"
                bet["pl"] = -_to_float(bet.get("stake", 10))
                bet["live_status"] = "no_data"
                bet["_needs_csv_update"] = True
            return bet

        # Find last meaningful row (skip pre_partido rows that may appear after the match)
        last = None
        for row in reversed(rows):
            est = row.get("estado_partido", "").strip().lower()
            if est not in ("pre_partido", "prematch"):
                last = row
                break
        if last is None:
            # All rows are pre_partido — match hasn't started yet
            bet["live_status"] = "pre_partido"
            return bet

        gl = _to_float(last.get("goles_local")) or 0
        gv = _to_float(last.get("goles_visitante")) or 0
        minuto = _to_float(last.get("minuto"))
        estado = last.get("estado_partido", "").strip().lower()

        bet["live_score"] = f"{int(gl)}-{int(gv)}"
        bet["live_minute"] = minuto
        bet["live_status"] = estado

        recommendation = bet.get("recommendation", "")
        would_win = _check_would_win(recommendation, gl, gv)
        bet["would_win_now"] = would_win

        odds = _to_float(bet.get("back_odds")) or 0
        stake = _to_float(bet.get("stake")) or 10
        if would_win and odds > 1:
            bet["potential_pl"] = round((odds - 1) * stake * 0.95, 2)
        else:
            bet["potential_pl"] = round(-stake, 2)

        # NOTE: Auto-settlement disabled - bets should only be resolved manually
        # using the resolve_pending_bets.py script or through user action.
        # The API only enriches pending bets with live data for visualization.

    except Exception:
        pass

    return bet


def _update_csv_rows(updates: dict[str, dict]):
    """Batch update rows in placed_bets.csv (by bet id)."""
    if not updates or not PLACED_BETS_CSV.exists():
        return
    rows = []
    with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bid = row.get("id", "")
            if bid in updates:
                row.update(updates[bid])
            rows.append(row)

    with open(PLACED_BETS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


@router.post("/api/bets/place", response_model=PlacedBet)
async def place_bet(bet: PlaceBetRequest):
    """Registra una apuesta realizada (paper trading o real)"""
    try:
        _ensure_csv_exists()

        bet_id = _get_next_id()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        with open(PLACED_BETS_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                bet_id,
                timestamp,
                bet.match_id,
                bet.match_name,
                bet.match_url,
                bet.strategy,
                bet.strategy_name,
                bet.minute,
                bet.score,
                bet.recommendation,
                bet.back_odds if bet.back_odds else '',
                bet.min_odds if bet.min_odds else '',
                bet.expected_value if bet.expected_value else '',
                bet.confidence,
                bet.win_rate_historical if bet.win_rate_historical else '',
                bet.roi_historical if bet.roi_historical else '',
                bet.sample_size if bet.sample_size else '',
                bet.bet_type,
                bet.stake,
                bet.notes or '',
                'pending',
                '',
                ''
            ])

        return PlacedBet(
            id=bet_id,
            timestamp_utc=timestamp,
            match_id=bet.match_id,
            match_name=bet.match_name,
            bet_type=bet.bet_type,
            stake=bet.stake,
            recommendation=bet.recommendation,
            back_odds=bet.back_odds,
            status="pending"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar apuesta: {str(e)}")


@router.get("/api/bets/placed")
async def get_placed_bets():
    """Obtiene todas las apuestas realizadas, enriquecidas con datos live."""
    try:
        if not PLACED_BETS_CSV.exists():
            return {
                "total": 0,
                "pending": 0,
                "won": 0,
                "lost": 0,
                "total_pl": 0,
                "bets": []
            }

        bets = []
        with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bets.append(dict(row))

        # Get active match IDs from games.csv
        active_match_ids = _get_active_match_ids()

        # Enrich pending bets with live data (for visualization only, not settlement)
        for bet in bets:
            if bet.get("status") == "pending":
                match_id = bet.get("match_id", "")
                is_active = match_id in active_match_ids
                _enrich_with_live_data(bet, is_match_active=is_active)

        # Compute stats
        stats = {"pending": 0, "won": 0, "lost": 0}
        total_pl = 0.0
        for bet in bets:
            status = bet.get("status", "pending")
            stats[status] = stats.get(status, 0) + 1
            pl = _to_float(bet.get("pl"))
            if pl is not None:
                total_pl += pl

        bets.sort(key=lambda x: x.get('timestamp_utc', ''), reverse=True)

        return {
            "total": len(bets),
            "pending": stats.get("pending", 0),
            "won": stats.get("won", 0),
            "lost": stats.get("lost", 0),
            "total_pl": round(total_pl, 2),
            "bets": bets
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener apuestas: {str(e)}")
