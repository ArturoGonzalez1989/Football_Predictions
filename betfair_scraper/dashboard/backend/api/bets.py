"""
API endpoints para gestión de apuestas realizadas (paper trading y reales).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime
import csv
from typing import Optional, Literal

router = APIRouter()

# Path to placed bets CSV
PLACED_BETS_CSV = Path(__file__).parent.parent.parent.parent / "placed_bets.csv"


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


def _ensure_csv_exists():
    """Crea el CSV con headers si no existe"""
    if not PLACED_BETS_CSV.exists():
        with open(PLACED_BETS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'id', 'timestamp_utc', 'match_id', 'match_name', 'match_url',
                'strategy', 'strategy_name', 'minute', 'score', 'recommendation',
                'back_odds', 'min_odds', 'expected_value', 'confidence',
                'win_rate_historical', 'roi_historical', 'sample_size',
                'bet_type', 'stake', 'notes', 'status', 'result', 'pl'
            ])


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


@router.post("/api/bets/place", response_model=PlacedBet)
async def place_bet(bet: PlaceBetRequest):
    """Registra una apuesta realizada (paper trading o real)"""
    try:
        _ensure_csv_exists()

        bet_id = _get_next_id()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Escribir al CSV
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
                'pending',  # status
                '',  # result (won/lost) - se actualizará manualmente
                ''   # pl - se calculará cuando se actualice el resultado
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
    """Obtiene todas las apuestas realizadas"""
    try:
        if not PLACED_BETS_CSV.exists():
            return {
                "total": 0,
                "pending": 0,
                "won": 0,
                "lost": 0,
                "bets": []
            }

        bets = []
        stats = {"pending": 0, "won": 0, "lost": 0}

        with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = row.get('status', 'pending')
                stats[status] = stats.get(status, 0) + 1
                bets.append(row)

        # Ordenar por timestamp descendente (más recientes primero)
        bets.sort(key=lambda x: x.get('timestamp_utc', ''), reverse=True)

        return {
            "total": len(bets),
            "pending": stats.get('pending', 0),
            "won": stats.get('won', 0),
            "lost": stats.get('lost', 0),
            "bets": bets
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener apuestas: {str(e)}")
