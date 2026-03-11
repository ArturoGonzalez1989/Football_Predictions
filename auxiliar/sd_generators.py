"""
Standalone bet generators for the 19 new strategies from sd_strategy_tracker.
Reads partido_*.csv files directly and produces bet dicts compatible with
the notebook's _ALL_BETS format.

Each generator returns a list of bet dicts with fields:
  strategy, match_id, timestamp_utc, minuto, won, pl, bet_type_dir,
  risk_level, <strategy-specific fields like odds, xg, etc.>

Usage (from notebook):
    from aux.sd_generators import generate_all_new_bets
    _NEW_BETS = generate_all_new_bets(data_dir)
"""
import csv
import glob
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _safe_float(val) -> Optional[float]:
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    if val is None or val == '':
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _load_csv_rows(filepath: str) -> List[Dict]:
    """Load all rows from a CSV file as list of dicts."""
    rows = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        pass
    return rows


def _match_id_from_path(filepath: str) -> str:
    """Extract match_id from CSV path like partido_xxx.csv -> xxx."""
    base = os.path.basename(filepath)
    m = re.match(r'partido_(.+)\.csv', base)
    return m.group(1) if m else base


def _ft_goals(rows: List[Dict]) -> Tuple[Optional[int], Optional[int]]:
    """Get final total goals from last row of CSV."""
    if not rows:
        return None, None
    last = rows[-1]
    gl = _safe_int(last.get('goles_local'))
    gv = _safe_int(last.get('goles_visitante'))
    return gl, gv


def _ft_total(rows: List[Dict]) -> Optional[int]:
    gl, gv = _ft_goals(rows)
    if gl is None or gv is None:
        return None
    return gl + gv


def _make_bet(strategy: str, match_id: str, row: Dict, won: bool,
              pl: float, bet_type_dir: str, odds: float,
              extra: Optional[Dict] = None) -> Dict:
    """Create a bet dict with standard fields."""
    bet = {
        'strategy': strategy,
        'match_id': match_id,
        'timestamp_utc': row.get('timestamp_utc', ''),
        'minuto': _safe_int(row.get('minuto')),
        'won': won,
        'pl': round(pl, 2),
        'bet_type_dir': bet_type_dir,
        'risk_level': 'none',
    }
    if extra:
        bet.update(extra)
    return bet


# ═══════════════════════════════════════════════════════════════════════════════
# #1 — LAY Over 4.5 Late Shield
# ═══════════════════════════════════════════════════════════════════════════════
def gen_lay_over45(rows: List[Dict], match_id: str) -> List[Dict]:
    """LAY Over 4.5 at min 65-75, goals<=2, odds<=15."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        odds = _safe_float(row.get('lay_over45'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: ±3 min around default filter [65,75]
        if not (65 <= m <= 78):
            continue
        if total_now > 3:
            continue
        if odds > 20:
            continue
        triggered = True
        won = ft <= 4
        if won:
            pl_val = 0.95
        else:
            pl_val = -(odds - 1)
        bets.append(_make_bet(
            'sd_lay_over45', match_id, row, won, pl_val, 'lay', odds,
            {'lay_over45_odds': odds, 'total_goals_trigger': total_now,
             'xg_total': (_safe_float(row.get('xg_local')) or 0) + (_safe_float(row.get('xg_visitante')) or 0)}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #2 — BACK Leader Stat Domination
# ═══════════════════════════════════════════════════════════════════════════════
def gen_back_leader_dom(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK the leading team when it dominates SoT."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        # Must be leading
        if gl == gv:
            continue
        sot_l = _safe_int(row.get('tiros_puerta_local'))
        sot_v = _safe_int(row.get('tiros_puerta_visitante'))
        if sot_l is None or sot_v is None:
            continue
        # Determine leader
        if gl > gv:
            leader = 'local'
            leader_sot = sot_l
            rival_sot = sot_v
            odds = _safe_float(row.get('back_home'))
        else:
            leader = 'visitante'
            leader_sot = sot_v
            rival_sot = sot_l
            odds = _safe_float(row.get('back_away'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: m=[55,73], SoT gates match filter defaults
        # (first_trigger locks in earliest row — wide SoT superset captures wrong rows)
        if not (55 <= m <= 73):
            continue
        if leader_sot < 4:   # match filter default sotMin=4
            continue
        if rival_sot > 1:    # match filter default sotMaxRival=1
            continue
        triggered = True
        # Win condition: leader wins FT
        if leader == 'local':
            won = ft_gl > ft_gv
        else:
            won = ft_gv > ft_gl
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_back_leader_dom', match_id, row, won, pl_val, 'back', odds,
            {'back_leader_odds': odds, 'leader_sot': leader_sot,
             'rival_sot': rival_sot, 'backed_team': leader,
             'goal_diff': abs(gl - gv)}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #3 — BACK Over 2.5 from 2-Goal Lead
# ═══════════════════════════════════════════════════════════════════════════════
def gen_over25_2goal(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Over 2.5 when a team leads by 2+ goals, SoT >= 3."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    prev_goal_diff = 0  # track previous goal diff to detect when lead was just established
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        goal_diff = abs(gl - gv)
        # Detect when 2-goal lead was just established (prev_diff < 2, now >= 2)
        just_reached_2goal_lead = (goal_diff >= 2) and (prev_goal_diff < 2)
        prev_goal_diff = goal_diff
        if goal_diff < 2:  # match filter default goalDiffMin=2
            continue
        if just_reached_2goal_lead:
            continue  # skip: back_over25 odds are stale (pre-goal values not yet updated)
        sot_l = _safe_int(row.get('tiros_puerta_local')) or 0
        sot_v = _safe_int(row.get('tiros_puerta_visitante')) or 0
        sot_total = sot_l + sot_v
        odds = _safe_float(row.get('back_over25'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: m=[55,81], SoT/goalDiff match filter defaults
        if not (55 <= m <= 81):
            continue
        if sot_total < 3:   # match filter default sotTotalMin=3
            continue
        if odds > 10:
            continue
        triggered = True
        won = ft >= 3
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_over25_2goal', match_id, row, won, pl_val, 'back', odds,
            {'back_over25_odds': odds, 'sot_total': sot_total,
             'goal_diff': goal_diff, 'total_goals_trigger': gl + gv}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #4 — BACK Over 2.5 Confluence (Tied + Recent Goal)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_confluence_over25(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Over 2.5 when tied with goals, SoT>=4, and recent goal."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    prev_gl, prev_gv = 0, 0  # track previous score to detect equalization
    for i, row in enumerate(rows):
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        # Detect equalization: score just became tied (was NOT tied before)
        just_equalized = (gl == gv) and (prev_gl != prev_gv)
        prev_gl, prev_gv = gl, gv
        # Score tied with goals
        if gl != gv or gl < 1:
            continue
        if just_equalized:
            continue  # skip: back_over25 odds are stale (pre-goal values not yet updated)
        sot_l = _safe_int(row.get('tiros_puerta_local')) or 0
        sot_v = _safe_int(row.get('tiros_puerta_visitante')) or 0
        sot_total = sot_l + sot_v
        odds = _safe_float(row.get('back_over25'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: ±3 min around default filter [50,70]
        if not (50 <= m <= 73):
            continue
        if sot_total < 3:
            continue
        if odds > 10:
            continue
        # Check recent goal (lookback 4-6 captures)
        total_now = gl + gv
        lookback = min(6, i)
        recent_goal = False
        if lookback > 0:
            for j in range(max(0, i - lookback), i):
                prev_gl = _safe_int(rows[j].get('goles_local')) or 0
                prev_gv = _safe_int(rows[j].get('goles_visitante')) or 0
                if (prev_gl + prev_gv) < total_now:
                    recent_goal = True
                    break
        if not recent_goal:
            continue
        triggered = True
        won = ft >= 3
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_confluence_over25', match_id, row, won, pl_val, 'back', odds,
            {'back_over25_odds': odds, 'sot_total': sot_total,
             'total_goals_trigger': total_now, 'recent_goal_lookback': lookback}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #5 — BACK Draw After Equalizer
# ═══════════════════════════════════════════════════════════════════════════════
def gen_draw_equalizer(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Draw after an equalizing goal at min 58-85."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    prev_gl, prev_gv = None, None
    pending_eq = False  # equalization detected, waiting for next stable row
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            prev_gl, prev_gv = gl, gv
            pending_eq = False
            continue
        # Detect equalization: score just became tied from non-tied
        if prev_gl is not None and prev_gv is not None:
            just_equalized = (gl == gv) and (prev_gl != prev_gv) and gl >= 1
        else:
            just_equalized = False
        if just_equalized:
            pending_eq = True
            prev_gl, prev_gv = gl, gv
            continue  # skip: back_draw odds stale on equalization row
        if gl != gv or gl < 1:
            pending_eq = False
            prev_gl, prev_gv = gl, gv
            continue
        odds = _safe_float(row.get('back_draw'))
        if odds is None or odds <= 1.0:
            prev_gl, prev_gv = gl, gv
            continue
        # Superset gate: wider
        if not (58 <= m <= 88):
            prev_gl, prev_gv = gl, gv
            continue
        if odds > 20:
            prev_gl, prev_gv = gl, gv
            continue
        # First stable tied row after equalization → enter (fresh odds)
        if pending_eq:
            triggered = True
            won = (ft_gl == ft_gv)
            pl_val = (odds - 1) * 0.95 if won else -1.0
            bets.append(_make_bet(
                'sd_draw_equalizer', match_id, row, won, pl_val, 'back', odds,
                {'back_draw_eq_odds': odds, 'eq_minute': m,
                 'score_at_eq': f'{gl}-{gv}'}
            ))
        prev_gl, prev_gv = gl, gv
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #6 — BACK Under 2.5 Scoreless Late
# ═══════════════════════════════════════════════════════════════════════════════
def gen_under25_scoreless(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Under 2.5 when 0-0 at min 64-80 with xG < 2.0."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != 0 or gv != 0:
            continue
        odds = _safe_float(row.get('back_under25'))
        if odds is None or odds <= 1.0:
            continue
        xg_l = _safe_float(row.get('xg_local')) or 0
        xg_v = _safe_float(row.get('xg_visitante')) or 0
        xg_total = xg_l + xg_v
        # Superset gate: ±3 min around default filter [64,80]
        if not (64 <= m <= 83):
            continue
        if xg_total > 3.0:
            continue
        if odds > 15:
            continue
        triggered = True
        won = ft <= 2
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_under25_scoreless', match_id, row, won, pl_val, 'back', odds,
            {'back_under25_odds': odds, 'xg_total': xg_total}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #7 — BACK Under 3.5 Low-xG Late
# ═══════════════════════════════════════════════════════════════════════════════
def gen_under35_late(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Under 3.5 when 3 goals at min 65-78, xG < 2.0."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        odds = _safe_float(row.get('back_under35'))
        if odds is None or odds <= 1.0:
            continue
        xg_l = _safe_float(row.get('xg_local'))
        xg_v = _safe_float(row.get('xg_visitante'))
        if xg_l is None and xg_v is None:
            continue  # skip matches without xG coverage
        xg_total = (xg_l or 0) + (xg_v or 0)
        # Superset gate: ±3 min around default filter [65,78]
        if not (65 <= m <= 81):
            continue
        if total_now < 2 or total_now > 4:
            continue
        if xg_total > 3.0:
            continue
        if odds > 8:
            continue
        triggered = True
        won = ft <= 3
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_under35_late', match_id, row, won, pl_val, 'back', odds,
            {'back_under35_odds': odds, 'xg_total': xg_total,
             'total_goals_trigger': total_now}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #8 — BACK Draw Late Stalemate
# ═══════════════════════════════════════════════════════════════════════════════
def gen_draw_stalemate(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Draw when tied with goals at min 70-90, xG residual >= -0.5."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    prev_gl, prev_gv = 0, 0  # track previous score to detect equalization
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        # Detect equalization: score just tied (was NOT tied in previous row)
        just_equalized = (gl == gv) and (prev_gl != prev_gv)
        prev_gl, prev_gv = gl, gv
        if gl != gv or gl < 1:
            continue
        if just_equalized:
            continue  # skip: back_draw odds are stale (pre-goal values not yet updated)
        odds = _safe_float(row.get('back_draw'))
        if odds is None or odds <= 1.0:
            continue
        xg_l = _safe_float(row.get('xg_local')) or 0
        xg_v = _safe_float(row.get('xg_visitante')) or 0
        xg_total = xg_l + xg_v
        total_now = gl + gv
        xg_residual = total_now - xg_total  # goals - xg
        # Superset gate: ±3 min around default filter [70,90]
        if not (70 <= m <= 90):
            continue
        if xg_residual < -1.5:
            continue
        if odds > 20:
            continue
        triggered = True
        won = (ft_gl == ft_gv)
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_draw_stalemate', match_id, row, won, pl_val, 'back', odds,
            {'back_draw_stl_odds': odds, 'xg_total': xg_total,
             'xg_residual': round(xg_residual, 2), 'score_at_trigger': f'{gl}-{gv}'}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #9 — LAY Over 4.5 V3 Tight (variant of #1: min=55-75, oddsMax=15, goalsMax=1)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_lay_over45_v3(rows: List[Dict], match_id: str) -> List[Dict]:
    """LAY Over 4.5 V3 tight: goals<=1, oddsMax=15."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        odds = _safe_float(row.get('lay_over45'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: ±3 min around default filter [65,75]; goals<=2 superset (v3 filters goals<=1)
        if not (55 <= m <= 78):
            continue
        if total_now > 2:
            continue
        if odds > 20:
            continue
        triggered = True
        won = ft <= 4
        if won:
            pl_val = 0.95
        else:
            pl_val = -(odds - 1)
        bets.append(_make_bet(
            'sd_lay_over45_v3', match_id, row, won, pl_val, 'lay', odds,
            {'lay_over45_odds': odds, 'total_goals_trigger': total_now}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #10 — LAY Over 4.5 V2+V4 combo (oddsMax=15 + xG<2.0)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_lay_over45_v2v4(rows: List[Dict], match_id: str) -> List[Dict]:
    """LAY Over 4.5 V2+V4 combo: oddsMax=15 + xG<2.0, goals<=2."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        odds = _safe_float(row.get('lay_over45'))
        if odds is None or odds <= 1.0:
            continue
        xg_l = _safe_float(row.get('xg_local')) or 0
        xg_v = _safe_float(row.get('xg_visitante')) or 0
        xg_total = xg_l + xg_v
        # Superset gate: ±3 min around default filter [65,75]
        if not (55 <= m <= 78):
            continue
        if total_now > 3:
            continue
        if odds > 20:
            continue
        triggered = True
        won = ft <= 4
        if won:
            pl_val = 0.95
        else:
            pl_val = -(odds - 1)
        bets.append(_make_bet(
            'sd_lay_over45_v2v4', match_id, row, won, pl_val, 'lay', odds,
            {'lay_over45_odds': odds, 'total_goals_trigger': total_now,
             'xg_total': xg_total}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #11 — LAY Over 4.5 min=68-78 (late entry variant)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_lay_over45_late(rows: List[Dict], match_id: str) -> List[Dict]:
    """LAY Over 4.5 late entry: min=68-78, goals<=2, odds<=15."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        odds = _safe_float(row.get('lay_over45'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: ±3 min around late entry range [68,78]
        if not (68 <= m <= 81):
            continue
        if total_now > 3:
            continue
        if odds > 20:
            continue
        triggered = True
        won = ft <= 4
        if won:
            pl_val = 0.95
        else:
            pl_val = -(odds - 1)
        bets.append(_make_bet(
            'sd_lay_over45_late', match_id, row, won, pl_val, 'lay', odds,
            {'lay_over45_odds': odds, 'total_goals_trigger': total_now}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #12 — BACK Draw xG Convergence (H14)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_draw_xg_convergence(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Draw when xG converges (both teams similar xG) in tied match."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != gv:
            continue
        xg_l = _safe_float(row.get('xg_local'))
        xg_v = _safe_float(row.get('xg_visitante'))
        if xg_l is None or xg_v is None:
            continue
        xg_diff = abs(xg_l - xg_v)
        xg_total = xg_l + xg_v
        odds = _safe_float(row.get('back_draw'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: m_min=60 (matches filter default), m_max=83
        if not (60 <= m <= 83):
            continue
        if xg_diff > 1.0:
            continue
        if xg_total > 4.0:
            continue
        if odds > 15:
            continue
        triggered = True
        won = (ft_gl == ft_gv)
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_draw_xg_conv', match_id, row, won, pl_val, 'back', odds,
            {'back_draw_conv_odds': odds, 'xg_diff': round(xg_diff, 2),
             'xg_total': xg_total, 'score_at_trigger': f'{gl}-{gv}'}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #13 — Corner+SoT -> Over 2.5 (H19)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_corner_sot_over25(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Over 2.5 when corners + SoT signal high activity."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        sot_l = _safe_int(row.get('tiros_puerta_local')) or 0
        sot_v = _safe_int(row.get('tiros_puerta_visitante')) or 0
        sot_total = sot_l + sot_v
        crn_l = _safe_int(row.get('corners_local')) or 0
        crn_v = _safe_int(row.get('corners_visitante')) or 0
        crn_total = crn_l + crn_v
        odds = _safe_float(row.get('back_over25'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: ±3 min around default filter [50,75]
        if not (50 <= m <= 78):
            continue
        if sot_total < 3:
            continue
        if crn_total < 4:
            continue
        if odds > 10:
            continue
        triggered = True
        won = ft >= 3
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_corner_sot_over25', match_id, row, won, pl_val, 'back', odds,
            {'back_over25_odds': odds, 'sot_total': sot_total,
             'corners_total': crn_total, 'total_goals_trigger': total_now}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #14 — BACK Over 2.5 from 2-Goal V4 (+xG>=0.5)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_over25_2goal_v4(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Over 2.5 with 2-goal lead + xG>=0.5 filter."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    prev_goal_diff = 0  # track previous goal diff to detect when lead was just established
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        goal_diff = abs(gl - gv)
        # Detect when 2-goal lead was just established (prev_diff < 2, now >= 2)
        just_reached_2goal_lead = (goal_diff >= 2) and (prev_goal_diff < 2)
        prev_goal_diff = goal_diff
        if goal_diff < 2:  # match filter default goalDiffMin=2
            continue
        if just_reached_2goal_lead:
            continue  # skip: back_over25 odds are stale (pre-goal values not yet updated)
        sot_l = _safe_int(row.get('tiros_puerta_local')) or 0
        sot_v = _safe_int(row.get('tiros_puerta_visitante')) or 0
        sot_total = sot_l + sot_v
        xg_l = _safe_float(row.get('xg_local')) or 0
        xg_v = _safe_float(row.get('xg_visitante')) or 0
        xg_total = xg_l + xg_v
        odds = _safe_float(row.get('back_over25'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: m=[55,81], goalDiff/SoT match filter defaults
        if not (55 <= m <= 81):
            continue
        if sot_total < 3:   # match filter default sotTotalMin=3
            continue
        if odds > 10:
            continue
        triggered = True
        won = ft >= 3
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_over25_2goal_v4', match_id, row, won, pl_val, 'back', odds,
            {'back_over25_odds': odds, 'sot_total': sot_total,
             'goal_diff': goal_diff, 'xg_total': xg_total,
             'total_goals_trigger': gl + gv}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #15 — BACK Over 3.5 First-Half Goals (H21)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_over35_fh_goals(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Over 3.5 when first half goals are high."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        odds = _safe_float(row.get('back_over35'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: m_min=45 (matches filter default), m_max=63
        if not (45 <= m <= 63):
            continue
        if total_now < 2:   # match filter default goals_min=2
            continue
        if odds > 10:
            continue
        triggered = True
        won = ft >= 4
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_over35_fh_goals', match_id, row, won, pl_val, 'back', odds,
            {'back_over35_odds': odds, 'total_goals_trigger': total_now}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #16 — BACK Over 2.5 from 1-1 (H23)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_over25_from_11(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Over 2.5 when score is tied with goals (1-1, 2-2), SoT>=4."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    prev_gl, prev_gv = 0, 0  # track previous score to detect equalization
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        # Detect equalization: score just became tied (was NOT tied before)
        just_equalized = (gl == gv) and (prev_gl != prev_gv)
        prev_gl, prev_gv = gl, gv
        if gl != gv or gl < 1:
            continue
        if just_equalized:
            continue  # skip: back_over25 odds are stale (pre-goal values not yet updated)
        sot_l = _safe_int(row.get('tiros_puerta_local')) or 0
        sot_v = _safe_int(row.get('tiros_puerta_visitante')) or 0
        sot_total = sot_l + sot_v
        odds = _safe_float(row.get('back_over25'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: ±3 min around default filter [50,70]
        if not (50 <= m <= 73):
            continue
        if sot_total < 3:
            continue
        if odds > 10:
            continue
        triggered = True
        won = ft >= 3
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_over25_from_11', match_id, row, won, pl_val, 'back', odds,
            {'back_over25_odds': odds, 'sot_total': sot_total,
             'total_goals_trigger': gl + gv, 'score_at_trigger': f'{gl}-{gv}'}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #17 — BACK Over 0.5 Possession Extreme (H32)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_poss_extreme(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Over 0.5 when possession is extremely one-sided at 0-0."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != 0 or gv != 0:
            continue
        poss_l = _safe_float(row.get('posesion_local'))
        poss_v = _safe_float(row.get('posesion_visitante'))
        if poss_l is None or poss_v is None:
            continue
        poss_max = max(poss_l, poss_v)
        odds = _safe_float(row.get('back_over05'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: start at filter default m_min=30, end +3
        if not (30 <= m <= 53):
            continue
        if poss_max < 55:  # superset gate: slightly below filter default 58
            continue
        if odds > 5:
            continue
        triggered = True
        won = ft >= 1
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_poss_extreme', match_id, row, won, pl_val, 'back', odds,
            {'back_over05_odds': odds, 'poss_max': poss_max}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #18 — BACK Longshot Resistente (H35)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_back_longshot(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK the winning longshot at min 65+."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    # Determine pre-match longshot (first valid row, max 5 rows — aligned with LIVE)
    ls_team = None
    for row in rows[:5]:
        bh = _safe_float(row.get('back_home'))
        ba = _safe_float(row.get('back_away'))
        if bh and ba and bh > 1 and ba > 1:
            if bh >= ba:
                ls_team = 'local'
            else:
                ls_team = 'visitante'
            break
    if ls_team is None:
        return []
    prev_ls_winning = False  # track if longshot was already winning previous row
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        # Detect when longshot first goes winning (transition: was not winning → now winning)
        ls_winning_now = (ls_team == 'local' and gl > gv) or (ls_team == 'visitante' and gv > gl)
        just_went_winning = ls_winning_now and not prev_ls_winning
        prev_ls_winning = ls_winning_now
        # Longshot must be winning
        if ls_team == 'local' and gl <= gv:
            continue
        if ls_team == 'visitante' and gv <= gl:
            continue
        if just_went_winning:
            continue  # skip: back odds are stale (pre-goal values not yet updated)
        xg_ls = _safe_float(row.get(f'xg_{ls_team}'))
        if ls_team == 'local':
            odds = _safe_float(row.get('back_home'))
        else:
            odds = _safe_float(row.get('back_away'))
        if odds is None or odds <= 1.0:
            continue
        # Superset gate: ±3 min around default filter [65,85]
        if not (65 <= m <= 88):
            continue
        if odds > 10:
            continue
        triggered = True
        if ls_team == 'local':
            won = ft_gl > ft_gv
        else:
            won = ft_gv > ft_gl
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_back_longshot', match_id, row, won, pl_val, 'back', odds,
            {'back_longshot_odds': odds, 'longshot_team': ls_team,
             'xg_longshot': xg_ls or 0}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #19 — BACK CS 0-0 Early (H37)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_cs_00(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Correct Score 0-0 at min 28-30, low xG/SoT, odds 5-12."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None:
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != 0 or gv != 0:
            continue
        odds = _safe_float(row.get('back_rc_0_0'))
        if odds is None or odds <= 1.0:
            continue
        xg_l = _safe_float(row.get('xg_local')) or 0
        xg_v = _safe_float(row.get('xg_visitante')) or 0
        xg_total = xg_l + xg_v
        sot_l = _safe_int(row.get('tiros_puerta_local')) or 0
        sot_v = _safe_int(row.get('tiros_puerta_visitante')) or 0
        sot_total = sot_l + sot_v
        # Superset gate: m_min=28 (matches filter default), m_max=33
        if not (28 <= m <= 33):
            continue
        if xg_total > 1.5:    # match filter default xg_max=1.5
            continue
        if sot_total > 3:     # match filter default sot_max=3
            continue
        if odds < 5.0 or odds > 12.0:  # match filter default odds range
            continue
        triggered = True
        won = (ft_gl == 0 and ft_gv == 0)
        if won:
            pl_val = (odds - 1) * 0.95
        else:
            pl_val = -1.0
        bets.append(_make_bet(
            'sd_cs_00', match_id, row, won, pl_val, 'back', odds,
            {'back_cs_00_odds': odds, 'xg_total': xg_total,
             'sot_total': sot_total}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #20 — BACK Over 2.5 from Two Goals (H39)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_over25_2goals(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Over 2.5 when exactly 2 goals scored at min 48-63."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    prev_total = None
    for row in rows:
        if triggered:
            break
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        m = _safe_int(row.get('minuto'))
        if m is None or not (48 <= m <= 63):
            prev_total = total_now
            continue
        if total_now != 2:
            prev_total = total_now
            continue
        # Skip goal-transition row (odds may be stale)
        if prev_total is not None and prev_total < total_now:
            prev_total = total_now
            continue
        prev_total = total_now
        odds = _safe_float(row.get('back_over25'))
        if odds is None or odds <= 1.0:
            continue
        if odds > 5.0:  # superset gate
            continue
        triggered = True
        won = ft >= 3
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_over25_2goals', match_id, row, won, pl_val, 'back', odds,
            {'back_over25_odds': odds, 'total_goals_trigger': total_now}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #21 — LAY Over 2.5 Scoreless Late (H41)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_lay_over25_scoreless(rows: List[Dict], match_id: str) -> List[Dict]:
    """LAY Over 2.5 when 0-0 at min 58-73."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (58 <= m <= 73):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != 0 or gv != 0:
            continue
        odds = _safe_float(row.get('lay_over25'))
        if odds is None or odds <= 1.0 or odds > 25.0:
            continue
        triggered = True
        won = ft <= 2
        pl_val = 0.95 if won else -(odds - 1)
        bets.append(_make_bet(
            'sd_lay_over25_scoreless', match_id, row, won, pl_val, 'lay', odds,
            {'lay_over25_odds': odds, 'total_goals_trigger': 0}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #22 — LAY Over 1.5 Scoreless Fortress (H44)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_lay_over15_scoreless(rows: List[Dict], match_id: str) -> List[Dict]:
    """LAY Over 1.5 when 0-0 at min 65-81."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (65 <= m <= 81):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != 0 or gv != 0:
            continue
        odds = _safe_float(row.get('lay_over15'))
        if odds is None or odds <= 1.0 or odds > 10.0:
            continue
        triggered = True
        won = ft <= 1
        pl_val = 0.95 if won else -(odds - 1)
        bets.append(_make_bet(
            'sd_lay_over15_scoreless', match_id, row, won, pl_val, 'lay', odds,
            {'lay_over15_odds': odds, 'total_goals_trigger': 0}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #23 — BACK Under 2.5 One-Goal Late (H46)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_under25_one_goal(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Under 2.5 when exactly 1 goal at min 73-88, xG<2.5, SoT<=8."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (73 <= m <= 88):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        total_now = gl + gv
        if total_now != 1:
            continue
        xg_l = _safe_float(row.get('xg_local')) or 0
        xg_v = _safe_float(row.get('xg_visitante')) or 0
        xg_total = xg_l + xg_v
        if xg_total > 2.5:  # superset gate wider than filter's 2.0
            continue
        sot_l = _safe_int(row.get('tiros_puerta_local')) or 0
        sot_v = _safe_int(row.get('tiros_puerta_visitante')) or 0
        sot_total = sot_l + sot_v
        if sot_total > 8:  # superset gate wider than filter's 6
            continue
        odds = _safe_float(row.get('back_under25'))
        if odds is None or odds <= 1.0:
            continue
        triggered = True
        won = ft <= 2
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_under25_one_goal', match_id, row, won, pl_val, 'back', odds,
            {'back_under25_odds': odds, 'total_goals_trigger': total_now,
             'xg_total': xg_total, 'sot_total': sot_total}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #24 — LAY Under 2.5 Tied at 1-1 (H48)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_lay_under25_tied(rows: List[Dict], match_id: str) -> List[Dict]:
    """LAY Under 2.5 when 1-1 at min 53-68."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (53 <= m <= 68):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != 1 or gv != 1:
            continue
        odds = _safe_float(row.get('lay_under25'))
        if odds is None or odds <= 1.0 or odds > 3.0:
            continue
        triggered = True
        won = ft >= 3  # LAY Under wins when Over happens
        pl_val = 0.95 if won else -(odds - 1)
        bets.append(_make_bet(
            'sd_lay_under25_tied', match_id, row, won, pl_val, 'lay', odds,
            {'lay_under25_odds': odds, 'total_goals_trigger': 2}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #25 — BACK Correct Score Close Game 2-1/1-2 (H49)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_cs_close(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Correct Score 2-1 or 1-2 at min 67-83."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (67 <= m <= 83):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        # Must be 2-1 or 1-2
        if not ((gl == 2 and gv == 1) or (gl == 1 and gv == 2)):
            continue
        col = f'back_rc_{gl}_{gv}'
        odds = _safe_float(row.get(col))
        if odds is None or odds <= 1.0:
            continue
        triggered = True
        won = (ft_gl == gl and ft_gv == gv)
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_cs_close', match_id, row, won, pl_val, 'back', odds,
            {'back_cs_odds': odds, 'trigger_score': f'{gl}-{gv}'}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #26 — BACK Correct Score 1-0/0-1 Late Lock (H53)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_cs_one_goal(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Correct Score 1-0 or 0-1 at min 65-88."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (65 <= m <= 88):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        # Must be 1-0 or 0-1
        if not ((gl == 1 and gv == 0) or (gl == 0 and gv == 1)):
            continue
        col = f'back_rc_{gl}_{gv}'
        odds = _safe_float(row.get(col))
        if odds is None or odds <= 1.0:
            continue
        triggered = True
        won = (ft_gl == gl and ft_gv == gv)
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_cs_one_goal', match_id, row, won, pl_val, 'back', odds,
            {'back_cs_odds': odds, 'trigger_score': f'{gl}-{gv}'}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #27 — BACK Draw at 1-1 Late (H58)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_draw_11(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Draw when 1-1 at min 68-88."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (68 <= m <= 88):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != 1 or gv != 1:
            continue
        odds = _safe_float(row.get('back_draw'))
        if odds is None or odds <= 1.0:
            continue
        triggered = True
        won = (ft_gl == ft_gv)
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_draw_11', match_id, row, won, pl_val, 'back', odds,
            {'back_draw_11_odds': odds}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# #28 — BACK Underdog Leading Late (H59)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_ud_leading(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK the underdog who is leading at min 53-83."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    # Determine underdog from first valid pre-match odds (first 5 rows, aligned with LIVE)
    if not rows:
        return []
    first_home = None
    first_away = None
    for _r in rows[:5]:
        _bh = _safe_float(_r.get('back_home'))
        _ba = _safe_float(_r.get('back_away'))
        if _bh and _ba and _bh > 1 and _ba > 1:
            first_home = _bh
            first_away = _ba
            break
    if first_home is None or first_away is None:
        return []
    if first_home > first_away:
        ud_team = 'local'
        ud_pre_odds = first_home
    else:
        ud_team = 'visitante'
        ud_pre_odds = first_away
    if ud_pre_odds < 1.5:  # superset gate: wider than filter's 2.0
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (53 <= m <= 83):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        # Underdog must be leading
        if ud_team == 'local':
            lead = gl - gv
            odds = _safe_float(row.get('back_home'))
        else:
            lead = gv - gl
            odds = _safe_float(row.get('back_away'))
        if lead <= 0 or lead > 2:  # superset: max_lead=2
            continue
        if odds is None or odds <= 1.0:
            continue
        triggered = True
        # Win: underdog wins FT
        if ud_team == 'local':
            won = ft_gl > ft_gv
        else:
            won = ft_gv > ft_gl
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_ud_leading', match_id, row, won, pl_val, 'back', odds,
            {'back_ud_odds': odds, 'ud_team': ud_team,
             'ud_pre_odds': ud_pre_odds, 'lead': lead}
        ))
    return bets


# #29 — BACK Under 3.5 Three-Goal Lid (H66)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_under35_3goals(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Under 3.5 when exactly 3 goals scored, min 65-85."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (60 <= m <= 88):  # superset wider than filter
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl + gv != 3:
            continue
        odds = _safe_float(row.get('back_under35'))
        if odds is None or odds <= 1.01 or odds > 10:
            continue
        triggered = True
        won = ft <= 3
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_under35_3goals', match_id, row, won, pl_val, 'back', odds,
            {'back_under35_odds': odds,
             'xg_total': (_safe_float(row.get('xg_local')) or 0) + (_safe_float(row.get('xg_visitante')) or 0)}
        ))
    return bets


# #30 — BACK Away Favourite Leading Late (H67)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_away_fav_leading(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK away team when they are favourite and leading, min 60-88."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    # Determine if away is favourite from first row pre-match odds
    if not rows:
        return []
    first_home = _safe_float(rows[0].get('back_home'))
    first_away = _safe_float(rows[0].get('back_away'))
    if first_home is None or first_away is None:
        return []
    if first_away >= first_home:
        return []  # away is NOT favourite
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (55 <= m <= 90):  # superset wider than filter
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gv <= gl:
            continue  # away not leading
        lead = gv - gl
        if lead > 3:  # superset gate
            continue
        odds = _safe_float(row.get('back_away'))
        if odds is None or odds <= 1.0 or odds > 50:
            continue
        triggered = True
        won = ft_gv > ft_gl
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_away_fav_leading', match_id, row, won, pl_val, 'back', odds,
            {'back_away_odds': odds, 'lead': lead,
             'away_pre_odds': first_away}
        ))
    return bets


# #31 — BACK Home Favourite Leading Late (H70)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_home_fav_leading(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK home team when they are pre-match favourite and leading, min 62-88."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    if not rows:
        return []
    first_home = None
    first_away = None
    for _r in rows[:5]:
        _bh = _safe_float(_r.get('back_home'))
        _ba = _safe_float(_r.get('back_away'))
        if _bh and _ba and _bh > 1 and _ba > 1:
            first_home = _bh
            first_away = _ba
            break
    if first_home is None or first_away is None:
        return []
    if first_home >= first_away:
        return []  # home is NOT favourite
    if first_home > 2.50:
        return []  # superset gate: fav odds <= 2.50
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (62 <= m <= 88):  # superset wider than filter [65,85]
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl <= gv:
            continue  # home not leading
        lead = gl - gv
        if lead > 3:
            continue
        odds = _safe_float(row.get('back_home'))
        if odds is None or odds <= 1.0 or odds > 10:
            continue
        triggered = True
        won = ft_gl > ft_gv
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_home_fav_leading', match_id, row, won, pl_val, 'back', odds,
            {'back_home_odds': odds, 'lead': lead,
             'home_pre_odds': first_home}
        ))
    return bets


# #32 — BACK Under 4.5 Three Goals Low xG (H71)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_under45_3goals(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK Under 4.5 when exactly 3 goals scored and xG < 2.0, min 62-88."""
    ft = _ft_total(rows)
    if ft is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (62 <= m <= 88):  # superset wider than filter [65,85]
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl + gv != 3:
            continue
        xg_l = _safe_float(row.get('xg_local'))
        xg_v = _safe_float(row.get('xg_visitante'))
        if xg_l is None or xg_v is None:
            continue
        xg_total = xg_l + xg_v
        if xg_total >= 2.5:  # superset gate wider than filter's 2.0
            continue
        odds = _safe_float(row.get('back_under45'))
        if odds is None or odds <= 1.01 or odds > 10:
            continue
        triggered = True
        won = ft <= 4
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_under45_3goals', match_id, row, won, pl_val, 'back', odds,
            {'back_under45_odds': odds, 'xg_total': xg_total}
        ))
    return bets


# #33 — BACK Correct Score 1-1 Late (H77)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_cs_11(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK CS 1-1 when score is 1-1 at min 72-92 (superset of filter 75-90)."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (72 <= m <= 92):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if gl != 1 or gv != 1:
            continue
        odds = _safe_float(row.get('back_rc_1_1'))
        if odds is None or odds <= 1.0:
            continue
        triggered = True
        won = (ft_gl == 1 and ft_gv == 1)
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_cs_11', match_id, row, won, pl_val, 'back', odds,
            {'back_cs_odds': odds, 'trigger_score': '1-1'}
        ))
    return bets


# #34 — BACK Correct Score 2-0/0-2 Late (H79)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_cs_20(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK CS 2-0 or 0-2 when that exact score at min 72-92 (superset of filter 75-90)."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (72 <= m <= 92):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if not ((gl == 2 and gv == 0) or (gl == 0 and gv == 2)):
            continue
        col = f'back_rc_{gl}_{gv}'
        odds = _safe_float(row.get(col))
        if odds is None or odds <= 1.0:
            continue
        triggered = True
        won = (ft_gl == gl and ft_gv == gv)
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_cs_20', match_id, row, won, pl_val, 'back', odds,
            {'back_cs_odds': odds, 'trigger_score': f'{gl}-{gv}'}
        ))
    return bets


# #35 — BACK Correct Score Big Lead Late (H81)
# ═══════════════════════════════════════════════════════════════════════════════
def gen_cs_big_lead(rows: List[Dict], match_id: str) -> List[Dict]:
    """BACK CS 3-0/0-3/3-1/1-3 when that exact score at min 67-88 (superset of filter 70-85)."""
    ft_gl, ft_gv = _ft_goals(rows)
    if ft_gl is None or ft_gv is None:
        return []
    valid_scores = {(3, 0), (0, 3), (3, 1), (1, 3)}
    bets = []
    triggered = False
    for row in rows:
        if triggered:
            break
        m = _safe_int(row.get('minuto'))
        if m is None or not (67 <= m <= 88):
            continue
        gl = _safe_int(row.get('goles_local'))
        gv = _safe_int(row.get('goles_visitante'))
        if gl is None or gv is None:
            continue
        if (gl, gv) not in valid_scores:
            continue
        col = f'back_rc_{gl}_{gv}'
        odds = _safe_float(row.get(col))
        if odds is None or odds <= 1.0:
            continue
        triggered = True
        won = (ft_gl == gl and ft_gv == gv)
        pl_val = (odds - 1) * 0.95 if won else -1.0
        bets.append(_make_bet(
            'sd_cs_big_lead', match_id, row, won, pl_val, 'back', odds,
            {'back_cs_odds': odds, 'trigger_score': f'{gl}-{gv}'}
        ))
    return bets


# ═══════════════════════════════════════════════════════════════════════════════
# Master generator
# ═══════════════════════════════════════════════════════════════════════════════

ALL_GENERATORS = [
    gen_over25_2goal,         # #1  — BACK O2.5 from 2-Goal Lead
    gen_under35_late,         # #2  — BACK U3.5 Late
    gen_lay_over45_v3,        # #3  — LAY O4.5 V3 Tight
    gen_draw_xg_convergence,  # #4  — BACK Draw xG Conv
    gen_poss_extreme,         # #5  — BACK O0.5 Poss Extreme
    gen_back_longshot,        # #6  — BACK Longshot
    gen_cs_00,                # #7  — BACK CS 0-0
    gen_over25_2goals,        # #8  — BACK O2.5 from Two Goals
    gen_cs_close,             # #9  — BACK CS 2-1/1-2
    gen_cs_one_goal,          # #10 — BACK CS 1-0/0-1
    gen_draw_11,              # #11 — BACK Draw 1-1
    gen_ud_leading,           # #12 — BACK UD Leading
    gen_under35_3goals,       # #13 — BACK U3.5 Three-Goal Lid
    gen_away_fav_leading,     # #14 — BACK Away Fav Leading
    gen_home_fav_leading,     # #15 — BACK Home Fav Leading
    gen_under45_3goals,       # #16 — BACK U4.5 Three Goals Low xG
    gen_cs_11,                # #17 — BACK CS 1-1 Late
    gen_cs_20,                # #18 — BACK CS 2-0/0-2 Late
    gen_cs_big_lead,          # #19 — BACK CS Big Lead Late
]


def generate_all_new_bets(data_dir: str) -> List[Dict]:
    """Scan all partido_*.csv and generate bets for all 28 strategies."""
    all_bets = []
    csv_files = sorted(glob.glob(os.path.join(data_dir, 'partido_*.csv')))
    for filepath in csv_files:
        match_id = _match_id_from_path(filepath)
        rows = _load_csv_rows(filepath)
        if len(rows) < 5:
            continue
        for gen_fn in ALL_GENERATORS:
            bets = gen_fn(rows, match_id)
            all_bets.extend(bets)
    all_bets.sort(key=lambda b: b.get('timestamp_utc', ''))
    return all_bets
