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
from utils import signals_audit_logger as _audit

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


def _get_lay_col(recommendation: str) -> Optional[str]:
    """Devuelve la columna de lay del CSV correspondiente a la recomendación."""
    rec = recommendation.upper()
    if "DRAW" in rec:
        return "lay_draw"
    if "HOME" in rec:
        return "lay_home"
    if "AWAY" in rec:
        return "lay_away"
    # Over X.5
    for line, col in [("4.5", "lay_over45"), ("3.5", "lay_over35"),
                       ("2.5", "lay_over25"), ("1.5", "lay_over15"), ("0.5", "lay_over05")]:
        if line in rec:
            return col
    return None


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


def _enrich_with_live_data(bet: dict, is_match_active: bool = True, cashout_pct: float = 20.0) -> dict:
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
            # Sin datos CSV: no podemos determinar resultado, dejar como pending
            # para resolución manual
            if not is_match_active:
                bet["live_status"] = "no_data"
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

        # Cashout recommendation: lay_actual >= entry_back * (1 + cashout_pct/100)
        # Si cashout_pct es None → CO desactivado, no evaluar
        if cashout_pct is not None:
            recommendation = bet.get("recommendation", "")
            lay_col = _get_lay_col(recommendation)
            if lay_col and odds > 1:
                lay_now = _to_float(last.get(lay_col))
                if lay_now and lay_now > 1:
                    threshold = round(odds * (1.0 + cashout_pct / 100.0), 2)
                    bet["cashout_lay_current"] = round(lay_now, 2)
                    bet["cashout_threshold"] = threshold
                    bet["suggest_cashout"] = lay_now >= threshold
                    if lay_now >= threshold:
                        bet["cashout_pl"] = round(stake * (odds / lay_now - 1), 2)

        # Auto-settle: match ended if explicitly finalizado OR not in games.csv (removed = finished)
        finished_states = ("finalizado", "finished", "ft", "full_time", "ended")
        is_explicitly_finished = estado in finished_states
        if is_explicitly_finished or not is_match_active:
            if would_win:
                bet["status"] = "won"
                bet["result"] = "won"
                bet["pl"] = bet["potential_pl"]
            else:
                bet["status"] = "lost"
                bet["result"] = "lost"
                bet["pl"] = round(-stake, 2)
            bet["_needs_csv_update"] = True

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


def _market_key_from_recommendation(recommendation: str) -> str:
    """Deriva la clave de mercado desde la recomendación — espejo de cartera.ts betMarketKey.
    Garantiza dedup por mercado (draw/home/away/over_X.5), no por estrategia.
    """
    rec = (recommendation or "").upper()
    if "DRAW" in rec:
        return "draw"
    if "HOME" in rec:
        return "home"
    if "AWAY" in rec:
        return "away"
    m = re.search(r"OVER\s+(\d+\.?\d*)", rec)
    if m:
        return f"over_{m.group(1)}"
    return recommendation  # fallback: clave literal


def _has_existing_bet(match_id: str, recommendation: str) -> bool:
    """Devuelve True si ya existe cualquier apuesta para este match+mercado (cualquier estado).
    Usa clave de mercado (draw/home/away/over_X.5) — dedup cross-estrategia.
    Bloquea re-entrada aunque el bet previo esté cashedout/won/lost,
    ya que ambas versiones de la misma estrategia (V1/V2) apuestan al mismo mercado.
    """
    if not PLACED_BETS_CSV.exists():
        return False
    market_key = _market_key_from_recommendation(recommendation)
    with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("match_id") == match_id
                    and _market_key_from_recommendation(row.get("recommendation", "")) == market_key):
                return True
    return False


def _is_contraria(match_id: str, recommendation: str) -> bool:
    """Devuelve True si ya existe una apuesta en mercado OPUESTO (HOME↔AWAY) en el mismo partido.
    Bloquea contrarias cross-estrategia: momentum V1 HOME después de momentum V2 AWAY (o viceversa).
    Solo aplica a mercados home/away — draw y over/X.5 no son contrarias entre sí.
    """
    if not PLACED_BETS_CSV.exists():
        return False
    market_key = _market_key_from_recommendation(recommendation)
    if market_key not in ("home", "away"):
        return False
    opposite = "away" if market_key == "home" else "home"
    with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("match_id") == match_id
                    and _market_key_from_recommendation(row.get("recommendation", "")) == opposite):
                return True
    return False


def run_auto_cashout() -> dict:
    """Check pending paper bets and auto-cashout/settle those that meet the criteria.
    Llamado por el background scheduler cada 60s (sin necesidad de abrir el dashboard).
    - Cashout: lay actual >= back_entry * (1 + cashout_pct/100)
    - Settle: partido finalizado (not active + min >= 85 o estado finalizado)
    """
    if not PLACED_BETS_CSV.exists():
        return {"cashed_out": 0, "settled": 0, "checked": 0}

    bets = []
    with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bets.append(dict(row))

    pending = [b for b in bets if b.get("status") == "pending"]
    if not pending:
        return {"cashed_out": 0, "settled": 0, "checked": 0}

    active_match_ids = _get_active_match_ids()

    # CO desactivado hardcoded — no hacer auto-cashout hasta validar en producción
    cashout_pct = None

    csv_updates: dict[str, dict] = {}
    cashed_out = 0
    settled = 0

    for bet in pending:
        match_id = bet.get("match_id", "")
        is_active = match_id in active_match_ids
        _enrich_with_live_data(bet, is_match_active=is_active, cashout_pct=cashout_pct)

        bid = str(bet.get("id", ""))
        if not bid:
            continue

        if (bet.get("bet_type") == "paper"
                and bet.get("suggest_cashout")
                and "cashout_pl" in bet):
            _co_pl = round(bet["cashout_pl"], 2)
            csv_updates[bid] = {
                "status": "cashout",
                "result": "cashout",
                "pl": str(_co_pl),
            }
            # ── Audit log: cashout ──
            try:
                _audit.log_cashout(
                    bet,
                    pl=_co_pl,
                    lay_now=float(bet.get("cashout_lay_current") or 0),
                    threshold=float(bet.get("cashout_threshold") or 0),
                )
            except Exception:
                pass
            cashed_out += 1

        elif bet.pop("_needs_csv_update", False):
            _settle_pl = float(bet.get("pl") or 0)
            _settle_result = bet.get("result", "")
            csv_updates[bid] = {
                "status": bet["status"],
                "result": _settle_result,
                "pl": str(bet.get("pl", "")),
            }
            # ── Audit log: liquidación ──
            try:
                _audit.log_settlement(bet, result=_settle_result, pl=_settle_pl)
            except Exception:
                pass
            settled += 1

    if csv_updates:
        _update_csv_rows(csv_updates)

    return {"cashed_out": cashed_out, "settled": settled, "checked": len(pending)}


@router.post("/api/bets/place", response_model=PlacedBet)
async def place_bet(bet: PlaceBetRequest):
    """Registra una apuesta realizada (paper trading o real)"""
    try:
        _ensure_csv_exists()

        # Validate odds meet minimum threshold before any other check
        if bet.back_odds is not None and bet.min_odds is not None and bet.back_odds < bet.min_odds:
            raise HTTPException(
                status_code=422,
                detail=f"Cuota {bet.back_odds:.2f} por debajo del mínimo requerido {bet.min_odds:.2f}"
            )

        # Deduplication: don't register if there's already any bet for same match+market
        # (checks all statuses: pending, cashout, won, lost — blocks cross-strategy V1/V2 duplicates)
        if _has_existing_bet(bet.match_id, bet.recommendation):
            raise HTTPException(status_code=409, detail="Ya existe una apuesta para este partido y mercado (dedup cross-estrategia)")

        # Anti-contrarias: block HOME if AWAY already placed on same match (or vice versa)
        if _is_contraria(bet.match_id, bet.recommendation):
            raise HTTPException(status_code=409, detail="Apuesta contraria bloqueada: ya existe HOME o AWAY opuesto en este partido")

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


@router.post("/api/bets/{bet_id}/resolve")
async def resolve_bet(bet_id: int, result: str):
    """Liquida manualmente una apuesta (result: 'won' o 'lost')."""
    if result not in ("won", "lost"):
        raise HTTPException(status_code=422, detail="result debe ser 'won' o 'lost'")

    if not PLACED_BETS_CSV.exists():
        raise HTTPException(status_code=404, detail="No hay apuestas registradas")

    rows = []
    found = False
    with open(PLACED_BETS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if str(row.get("id", "")) == str(bet_id):
                found = True
                stake = _to_float(row.get("stake")) or 0
                odds = _to_float(row.get("back_odds")) or 0
                if result == "won":
                    pl = round((odds - 1) * stake * 0.95, 2) if odds > 1 else round(stake * 0.95, 2)
                else:
                    pl = round(-stake, 2)
                row["status"] = result
                row["result"] = result
                row["pl"] = str(pl)
            rows.append(row)

    if not found:
        raise HTTPException(status_code=404, detail=f"Apuesta {bet_id} no encontrada")

    with open(PLACED_BETS_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    return {"ok": True, "bet_id": bet_id, "result": result}


@router.delete("/api/bets/clear")
async def clear_placed_bets():
    """Reset paper trading — elimina todas las apuestas y deja solo los headers."""
    try:
        with open(PLACED_BETS_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
        return {"status": "ok", "message": "Paper trading reseteado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al limpiar apuestas: {str(e)}")


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

        # Load cashout_pct from config (single source of truth)
        # CO desactivado hardcoded — no hacer auto-cashout hasta validar en producción
        cashout_pct = None

        # Enrich pending bets with live data (for visualization only, not settlement)
        for bet in bets:
            if bet.get("status") == "pending":
                match_id = bet.get("match_id", "")
                is_active = match_id in active_match_ids
                _enrich_with_live_data(bet, is_match_active=is_active, cashout_pct=cashout_pct)

        # Auto-cashout: paper bets con suggest_cashout → liquidar con cashout_pl
        for bet in bets:
            if (bet.get("status") == "pending"
                    and bet.get("bet_type") == "paper"
                    and bet.get("suggest_cashout")
                    and "cashout_pl" in bet):
                bet["status"] = "cashout"
                bet["result"] = "cashout"
                bet["pl"] = bet["cashout_pl"]
                bet["_needs_csv_update"] = True

        # Persist auto-settled and auto-cashed bets to CSV
        csv_updates = {}
        for bet in bets:
            if bet.pop("_needs_csv_update", False):
                bid = str(bet.get("id", ""))
                if bid:
                    csv_updates[bid] = {
                        "status": bet["status"],
                        "result": bet.get("result", ""),
                        "pl": str(bet.get("pl", "")),
                    }
        if csv_updates:
            _update_csv_rows(csv_updates)

        # Compute stats
        stats = {"pending": 0, "won": 0, "lost": 0, "cashout": 0}
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
            "cashout": stats.get("cashout", 0),
            "total_pl": round(total_pl, 2),
            "bets": bets
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener apuestas: {str(e)}")
