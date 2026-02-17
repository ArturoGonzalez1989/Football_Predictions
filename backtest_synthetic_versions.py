"""
Backtest Synthetic Attribute Versions
======================================
Replica EXACTAMENTE la lógica de detección de señales de csv_reader.py,
calcula atributos sintéticos en el momento del trigger, y compara nuevas
versiones con filtros sintéticos vs las versiones actuales.

P/L: stake=10, comisión=5%, idéntico al sistema real.
"""

import csv
import os
import glob
import math
import sys
import io

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DATA_DIR = os.path.join(os.path.dirname(__file__), "betfair_scraper", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "synthetic_analysis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

STAKE = 10
COMMISSION = 0.05

# ── Helpers ──────────────────────────────────────────────────────────

def sf(val, default=None):
    """safe float"""
    if val is None or val == '' or val == 'None':
        return default
    try:
        return float(val)
    except:
        return default

def si(val, default=None):
    """safe int from float"""
    f = sf(val)
    if f is None:
        return default
    return int(f)

def load_match(filepath):
    with open(filepath, encoding='utf-8', errors='replace') as f:
        return list(csv.DictReader(f))

def get_in_play(rows):
    result = []
    for r in rows:
        if r.get('estado_partido') != 'en_juego':
            continue
        m = sf(r.get('minuto'))
        if m is None:
            continue
        result.append(r)
    result.sort(key=lambda r: sf(r['minuto'], 0))
    return result

def get_over_field(total_goals):
    return {0: 'back_over05', 1: 'back_over15', 2: 'back_over25',
            3: 'back_over35', 4: 'back_over45'}.get(int(total_goals), '')

def calc_pl(won, odds):
    if won:
        return round((odds - 1) * STAKE * (1 - COMMISSION), 2)
    return -STAKE

def lookback_val(rows, idx, col, minutes_back):
    """Get value from approximately N minutes ago."""
    current_min = sf(rows[idx].get('minuto'), 0)
    target_min = current_min - minutes_back
    best = None
    best_dist = float('inf')
    for i in range(max(0, idx - minutes_back - 5), idx):
        m = sf(rows[i].get('minuto'), 0)
        d = abs(m - target_min)
        if d < best_dist:
            best_dist = d
            best = rows[i]
    if best and best_dist < minutes_back * 0.5 + 2:
        return sf(best.get(col))
    return None

# ── Synthetic attributes at trigger point ────────────────────────────

def compute_synth_at_trigger(rows, trigger_idx):
    """Compute synthetic attributes at the exact trigger row."""
    row = rows[trigger_idx]
    s = {}
    minute = sf(row.get('minuto'), 0)

    gl = sf(row.get('goles_local'), 0)
    gv = sf(row.get('goles_visitante'), 0)
    xg_l = sf(row.get('xg_local'))
    xg_v = sf(row.get('xg_visitante'))
    pos_l = sf(row.get('posesion_local'))
    shots_l = sf(row.get('tiros_local'))
    shots_v = sf(row.get('tiros_visitante'))
    sot_l = sf(row.get('tiros_puerta_local'))
    sot_v = sf(row.get('tiros_puerta_visitante'))
    tbox_l = sf(row.get('touches_box_local'))
    tbox_v = sf(row.get('touches_box_visitante'))
    corn_l = sf(row.get('corners_local'))
    corn_v = sf(row.get('corners_visitante'))
    passes_l = sf(row.get('total_passes_local'))
    passes_v = sf(row.get('total_passes_visitante'))
    attacks_l = sf(row.get('attacks_local'))
    attacks_v = sf(row.get('attacks_visitante'))
    mom_l = sf(row.get('momentum_local'))
    mom_v = sf(row.get('momentum_visitante'))
    opta_l = sf(row.get('opta_points_local'))
    opta_v = sf(row.get('opta_points_visitante'))
    back_h = sf(row.get('back_home'))
    back_d = sf(row.get('back_draw'))
    back_a = sf(row.get('back_away'))
    back_o25 = sf(row.get('back_over25'))

    # ── xG dominance ──
    if xg_l is not None and xg_v is not None and (xg_l + xg_v) > 0:
        s['xg_dominance'] = xg_l / (xg_l + xg_v)
    else:
        s['xg_dominance'] = None

    # ── Opta gap ──
    if opta_l is not None and opta_v is not None:
        s['opta_gap'] = opta_l - opta_v
    else:
        s['opta_gap'] = None

    # ── Opta dominance ──
    if opta_l is not None and opta_v is not None and (opta_l + opta_v) > 0:
        s['opta_dominance'] = opta_l / (opta_l + opta_v)
    else:
        s['opta_dominance'] = None

    # ── Implied probabilities ──
    s['implied_prob_draw'] = (1.0 / back_d) if back_d and back_d > 0 else None
    s['implied_prob_o25'] = (1.0 / back_o25) if back_o25 and back_o25 > 0 else None
    s['implied_prob_home'] = (1.0 / back_h) if back_h and back_h > 0 else None

    # ── Momentum dominance ──
    if mom_l is not None and mom_v is not None and (mom_l + mom_v) > 0:
        s['momentum_dominance'] = mom_l / (mom_l + mom_v)
    else:
        s['momentum_dominance'] = None

    # ── Momentum gap ──
    if mom_l is not None and mom_v is not None:
        s['momentum_gap'] = abs(mom_l - mom_v)
    else:
        s['momentum_gap'] = None

    # ── Match openness ──
    parts = [v for v in [shots_l, shots_v, sot_l, sot_v, corn_l, corn_v] if v is not None]
    s['match_openness'] = sum(parts) + (gl + gv) * 5 if parts else None

    # ── Pressure indices (5min window) ──
    for side, suffixes in [('l', ('_local',)), ('v', ('_visitante',))]:
        components = []
        weights = []
        for col_base, suf, w in [
            ('tiros_puerta', suffixes[0], 3.0),
            ('corners', suffixes[0], 1.5),
            ('xg', suffixes[0], 5.0),
            ('touches_box', suffixes[0], 1.0),
            ('tiros', suffixes[0], 2.0),
        ]:
            col = col_base + suf
            now = sf(row.get(col))
            prev = lookback_val(rows, trigger_idx, col, 5)
            if now is not None and prev is not None:
                delta = now - prev
                components.append(delta * w)
                weights.append(w)
        s[f'pressure_index_{side}'] = sum(components) / sum(weights) if weights else None

    # ── Deltas 5m and 10m for key stats ──
    for window in [5, 10]:
        for col, name in [
            ('tiros_puerta_local', f'sot_l'), ('tiros_puerta_visitante', f'sot_v'),
            ('tiros_local', f'shots_l'), ('tiros_visitante', f'shots_v'),
            ('xg_local', f'xg_l'), ('xg_visitante', f'xg_v'),
            ('corners_local', f'corn_l'), ('corners_visitante', f'corn_v'),
            ('touches_box_local', f'tbox_l'), ('touches_box_visitante', f'tbox_v'),
        ]:
            now = sf(row.get(col))
            prev = lookback_val(rows, trigger_idx, col, window)
            s[f'delta_{name}_{window}m'] = (now - prev) if now is not None and prev is not None else None

    # ── xG velocity (10m) ──
    s['xg_velocity_l_10m'] = s['delta_xg_l_10m'] / 10.0 if s.get('delta_xg_l_10m') is not None else None
    s['xg_velocity_v_10m'] = s['delta_xg_v_10m'] / 10.0 if s.get('delta_xg_v_10m') is not None else None

    # ── Scoreline tension ──
    if minute > 0 and xg_l is not None and xg_v is not None:
        closeness = max(0, 3 - abs(gl - gv))
        s['scoreline_tension'] = closeness * (minute / 90.0) * (1 + xg_l + xg_v)
    else:
        s['scoreline_tension'] = None

    # ── xG frustration ──
    s['xg_frustration_l'] = max(0, xg_l - gl) * (minute / 90.0) if xg_l is not None else None
    s['xg_frustration_v'] = max(0, xg_v - gv) * (minute / 90.0) if xg_v is not None else None
    s['xg_frustration_total'] = None
    if s['xg_frustration_l'] is not None and s['xg_frustration_v'] is not None:
        s['xg_frustration_total'] = s['xg_frustration_l'] + s['xg_frustration_v']

    # ── xG remaining ──
    if xg_l is not None and xg_v is not None and minute > 5:
        xg_rate = (xg_l + xg_v) / minute
        s['xg_remaining'] = xg_rate * max(0, 90 - minute)
    else:
        s['xg_remaining'] = None

    # ── Danger score ──
    for side, xg, sot, tbox, corn in [('l', xg_l, sot_l, tbox_l, corn_l), ('v', xg_v, sot_v, tbox_v, corn_v)]:
        parts = []
        for val, w in [(xg, 3.0), (sot, 2.0), (tbox, 0.5), (corn, 0.3)]:
            if val is not None:
                parts.append(val * w)
        s[f'danger_score_{side}'] = sum(parts) if parts else None

    # ── Market vs xG divergence ──
    if s['implied_prob_home'] is not None and xg_l is not None and xg_v is not None:
        xg_total = xg_l + xg_v
        if xg_total > 0.1:
            s['market_vs_xg_home'] = s['implied_prob_home'] - (xg_l / xg_total)
        else:
            s['market_vs_xg_home'] = None
    else:
        s['market_vs_xg_home'] = None

    # ── CS entropy ──
    cs_probs = []
    for sc in ['0_0','1_0','0_1','1_1','2_0','0_2','2_1','1_2','2_2','3_0','0_3','3_1','1_3','3_2','2_3']:
        odds = sf(row.get(f'back_rc_{sc}'))
        if odds and odds > 0:
            cs_probs.append(1.0 / odds)
    if cs_probs:
        total = sum(cs_probs)
        if total > 0:
            cs_probs = [p / total for p in cs_probs]
            s['cs_entropy'] = sum(-p * math.log2(p) for p in cs_probs if p > 0)
        else:
            s['cs_entropy'] = None
    else:
        s['cs_entropy'] = None

    # ── SoT dominance ──
    if sot_l is not None and sot_v is not None and (sot_l + sot_v) > 0:
        s['sot_dominance'] = sot_l / (sot_l + sot_v)
    else:
        s['sot_dominance'] = None

    # ── Territorial dominance ──
    comps = []
    if pos_l is not None:
        comps.append(pos_l / 100.0)
    if attacks_l is not None and attacks_v is not None and (attacks_l + attacks_v) > 0:
        comps.append(attacks_l / (attacks_l + attacks_v))
    if tbox_l is not None and tbox_v is not None and (tbox_l + tbox_v) > 0:
        comps.append(tbox_l / (tbox_l + tbox_v))
    s['territorial_dominance'] = sum(comps) / len(comps) if comps else None

    return s


# ═══════════════════════════════════════════════════════════════════════
# STRATEGY DETECTORS (exact replicas of csv_reader.py)
# ═══════════════════════════════════════════════════════════════════════

def detect_back_draw_00(rows):
    """Returns list of bets with trigger data + synthetic attributes."""
    in_play = get_in_play(rows)
    if len(in_play) < 5:
        return []

    # Final score
    last = rows[-1]
    gl_final = si(last.get('goles_local'))
    gv_final = si(last.get('goles_visitante'))
    if gl_final is None or gv_final is None:
        return []

    # Find trigger
    trigger_row = None
    trigger_idx = None
    for i, row in enumerate(in_play):
        m = sf(row.get('minuto'))
        gl = si(row.get('goles_local'))
        gv = si(row.get('goles_visitante'))
        if m is not None and gl is not None and gv is not None:
            if m >= 30 and gl == 0 and gv == 0:
                trigger_row = row
                trigger_idx = i
                break

    if not trigger_row:
        return []

    back_draw = sf(trigger_row.get('back_draw'))
    if not back_draw or back_draw <= 1:
        return []

    won = gl_final == gv_final
    pl = calc_pl(won, back_draw)

    # Version filters (original)
    m = sf(trigger_row.get('minuto'), 0)
    xg_l = sf(trigger_row.get('xg_local'))
    xg_v = sf(trigger_row.get('xg_visitante'))
    pos_l = sf(trigger_row.get('posesion_local'))
    pos_v = sf(trigger_row.get('posesion_visitante'))
    shots_l = sf(trigger_row.get('tiros_local'), 0)
    shots_v = sf(trigger_row.get('tiros_visitante'), 0)

    xg_total = (xg_l + xg_v) if xg_l is not None and xg_v is not None else None
    poss_diff = abs(pos_l - pos_v) if pos_l is not None and pos_v is not None else None
    shots_total = shots_l + shots_v

    passes_v15 = (xg_total is not None and xg_total < 0.6 and
                  poss_diff is not None and poss_diff < 25)
    passes_v2r = (xg_total is not None and xg_total < 0.6 and
                  poss_diff is not None and poss_diff < 20 and shots_total < 8)
    passes_v2 = (xg_total is not None and xg_total < 0.5 and
                 poss_diff is not None and poss_diff < 20 and shots_total < 8)

    # Synthetic attributes at trigger
    synth = compute_synth_at_trigger(in_play, trigger_idx)

    return [{
        'strategy': 'back_draw_00',
        'match': os.path.basename(rows[0].get('tab_id', '')),
        'minuto': m,
        'odds': back_draw,
        'won': won,
        'pl': pl,
        'ft_score': f"{gl_final}-{gv_final}",
        'passes_v15': passes_v15,
        'passes_v2r': passes_v2r,
        'passes_v2': passes_v2,
        'xg_total': xg_total,
        'poss_diff': poss_diff,
        'shots_total': shots_total,
        **{f'synth_{k}': v for k, v in synth.items()},
    }]


def detect_xg_underperformance(rows):
    """Detect xG underperformance signals."""
    in_play = get_in_play(rows)
    if len(in_play) < 5:
        return []

    last = rows[-1]
    gl_final = si(last.get('goles_local'))
    gv_final = si(last.get('goles_visitante'))
    if gl_final is None or gv_final is None:
        return []
    ft_total = gl_final + gv_final

    triggered = {'home': False, 'away': False}
    bets = []

    for i, row in enumerate(in_play):
        m = sf(row.get('minuto'))
        if m is None or m < 15:
            continue

        gl = si(row.get('goles_local'), 0)
        gv = si(row.get('goles_visitante'), 0)
        xg_h = sf(row.get('xg_local'))
        xg_a = sf(row.get('xg_visitante'))
        sot_h = si(row.get('tiros_puerta_local'))
        sot_v = si(row.get('tiros_puerta_visitante'))

        for team, xg, goals, opp_goals, sot in [
            ('home', xg_h, gl, gv, sot_h),
            ('away', xg_a, gv, gl, sot_v),
        ]:
            if triggered[team]:
                continue
            if xg is None:
                continue
            xg_excess = xg - goals
            if xg_excess < 0.5 or opp_goals <= goals:
                continue

            total_at_trigger = gl + gv
            over_field = get_over_field(total_at_trigger)
            if not over_field:
                continue
            back_over = sf(row.get(over_field))
            if not back_over or back_over <= 1:
                continue

            triggered[team] = True
            more_goals = ft_total > total_at_trigger
            pl = calc_pl(more_goals, back_over)

            passes_v2 = sot is not None and sot >= 2
            passes_v3 = passes_v2 and m < 70

            synth = compute_synth_at_trigger(in_play, i)

            bets.append({
                'strategy': 'xg_underperformance',
                'match': os.path.basename(rows[0].get('tab_id', '')),
                'minuto': m,
                'odds': back_over,
                'won': more_goals,
                'pl': pl,
                'ft_score': f"{gl_final}-{gv_final}",
                'team': team,
                'xg_excess': round(xg_excess, 3),
                'passes_v2': passes_v2,
                'passes_v3': passes_v3,
                **{f'synth_{k}': v for k, v in synth.items()},
            })

    return bets


def detect_odds_drift(rows):
    """Detect odds drift signals."""
    DRIFT_MIN = 0.30
    WINDOW_MIN = 10
    MIN_MINUTE = 5
    MAX_MINUTE = 80
    MIN_ODDS = 1.50
    MAX_ODDS = 30.0

    in_play = get_in_play(rows)
    if len(in_play) < 5:
        return []

    last = rows[-1]
    gl_final = si(last.get('goles_local'))
    gv_final = si(last.get('goles_visitante'))
    if gl_final is None or gv_final is None:
        return []

    # Build data points
    data_points = []
    for i, row in enumerate(in_play):
        m = sf(row.get('minuto'))
        bh = sf(row.get('back_home'))
        ba = sf(row.get('back_away'))
        if m is not None and bh and ba:
            data_points.append((m, row, bh, ba, i))  # include in_play index

    triggered = {'home': False, 'away': False}
    bets = []

    for idx in range(1, len(data_points)):
        curr_min, curr_row, curr_bh, curr_ba, ip_idx = data_points[idx]
        if curr_min < MIN_MINUTE or curr_min > MAX_MINUTE:
            continue

        gl = si(curr_row.get('goles_local'), 0)
        gv = si(curr_row.get('goles_visitante'), 0)

        for prev_idx in range(idx - 1, -1, -1):
            prev_min, _, prev_bh, prev_ba, _ = data_points[prev_idx]
            if curr_min - prev_min > WINDOW_MIN:
                break
            if curr_min - prev_min < 2:
                continue

            for team, prev_odds, curr_odds, team_goals, opp_goals in [
                ('home', prev_bh, curr_bh, gl, gv),
                ('away', prev_ba, curr_ba, gv, gl),
            ]:
                if triggered[team]:
                    continue
                if prev_odds <= 0:
                    continue
                drift = (curr_odds - prev_odds) / prev_odds
                if drift < DRIFT_MIN or curr_odds < MIN_ODDS or curr_odds > MAX_ODDS:
                    continue
                if team_goals <= opp_goals:
                    continue

                triggered[team] = True
                if team == 'home':
                    won = gl_final > gv_final
                else:
                    won = gv_final > gl_final

                pl = calc_pl(won, curr_odds)
                goal_diff = team_goals - opp_goals

                passes_v2 = goal_diff >= 2
                passes_v3 = drift >= 1.0
                passes_v4 = curr_odds <= 5.0 and curr_min > 45
                passes_v5 = curr_odds <= 5.0

                synth = compute_synth_at_trigger(in_play, ip_idx)

                bets.append({
                    'strategy': 'odds_drift',
                    'match': os.path.basename(rows[0].get('tab_id', '')),
                    'minuto': curr_min,
                    'odds': curr_odds,
                    'won': won,
                    'pl': pl,
                    'ft_score': f"{gl_final}-{gv_final}",
                    'team': team,
                    'drift_pct': round(drift * 100, 1),
                    'goal_diff': goal_diff,
                    'passes_v2': passes_v2,
                    'passes_v3': passes_v3,
                    'passes_v4': passes_v4,
                    'passes_v5': passes_v5,
                    **{f'synth_{k}': v for k, v in synth.items()},
                })

    return bets


def detect_goal_clustering(rows):
    """Detect goal clustering signals."""
    in_play = get_in_play(rows)
    if len(in_play) < 5:
        return []

    last = rows[-1]
    gl_final = si(last.get('goles_local'))
    gv_final = si(last.get('goles_visitante'))
    if gl_final is None or gv_final is None:
        return []
    ft_total = gl_final + gv_final

    prev_total = None
    bets = []

    for i, row in enumerate(in_play):
        gl = si(row.get('goles_local'), 0)
        gv = si(row.get('goles_visitante'), 0)
        total_now = gl + gv

        if prev_total is None:
            prev_total = total_now
            continue

        if total_now > prev_total and not bets:  # new goal + no bet yet
            m = sf(row.get('minuto'))
            if m is not None and 15 <= m <= 80:
                sot_l = si(row.get('tiros_puerta_local'), 0)
                sot_v = si(row.get('tiros_puerta_visitante'), 0)
                sot_max = max(sot_l, sot_v)

                if sot_max >= 3:
                    over_field = get_over_field(total_now)
                    if over_field:
                        over_odds = sf(row.get(over_field))
                        if over_odds and over_odds > 0:
                            won = ft_total > total_now
                            pl = calc_pl(won, over_odds)
                            passes_v3 = m < 60

                            synth = compute_synth_at_trigger(in_play, i)

                            bets.append({
                                'strategy': 'goal_clustering',
                                'match': os.path.basename(rows[0].get('tab_id', '')),
                                'minuto': m,
                                'odds': over_odds,
                                'won': won,
                                'pl': pl,
                                'ft_score': f"{gl_final}-{gv_final}",
                                'sot_max': sot_max,
                                'passes_v3': passes_v3,
                                **{f'synth_{k}': v for k, v in synth.items()},
                            })

        prev_total = total_now

    return bets


def detect_pressure_cooker(rows):
    """Detect pressure cooker signals."""
    in_play = get_in_play(rows)
    if len(in_play) < 20:
        return []

    last_min = sf(in_play[-1].get('minuto'), 0)
    if last_min < 85:
        return []

    last = rows[-1]
    gl_final = si(last.get('goles_local'))
    gv_final = si(last.get('goles_visitante'))
    if gl_final is None or gv_final is None:
        return []
    ft_total = gl_final + gv_final

    bets = []

    for i, row in enumerate(in_play):
        if row.get('estado_partido') != 'en_juego':
            continue
        m = sf(row.get('minuto'))
        if m is None or m < 65 or m > 75:
            continue
        gl = si(row.get('goles_local'), 0)
        gv = si(row.get('goles_visitante'), 0)
        if gl != gv or gl == 0:
            continue
        if bets:
            continue

        # Score confirmation
        confirm = 0
        for cr in in_play:
            cm = sf(cr.get('minuto'), 0)
            if abs(cm - m) <= 3:
                if si(cr.get('goles_local'), -1) == gl and si(cr.get('goles_visitante'), -1) == gv:
                    confirm += 1
        if confirm < 2:
            continue

        total_goals = gl + gv
        over_field = get_over_field(total_goals)
        if not over_field:
            continue
        over_odds = sf(row.get(over_field))
        if not over_odds or over_odds <= 1:
            continue

        won = ft_total > total_goals
        pl = calc_pl(won, over_odds)

        synth = compute_synth_at_trigger(in_play, i)

        bets.append({
            'strategy': 'pressure_cooker',
            'match': os.path.basename(rows[0].get('tab_id', '')),
            'minuto': m,
            'odds': over_odds,
            'won': won,
            'pl': pl,
            'ft_score': f"{gl_final}-{gv_final}",
            **{f'synth_{k}': v for k, v in synth.items()},
        })

    return bets


def detect_momentum_xg(rows, version='v1'):
    """Detect momentum x xG signals."""
    configs = {
        'v1': {'sot_min': 1, 'ratio_min': 1.1, 'xg_up_min': 0.15,
               'min_min': 10, 'max_min': 80, 'min_odds': 1.4, 'max_odds': 6.0},
        'v2': {'sot_min': 1, 'ratio_min': 1.05, 'xg_up_min': 0.1,
               'min_min': 5, 'max_min': 85, 'min_odds': 1.3, 'max_odds': 8.0},
    }
    cfg = configs[version]

    in_play = get_in_play(rows)
    if len(in_play) < 5:
        return []

    last = rows[-1]
    gl_final = si(last.get('goles_local'))
    gv_final = si(last.get('goles_visitante'))
    if gl_final is None or gv_final is None:
        return []

    bets = []

    for i, row in enumerate(in_play):
        if bets:
            break
        if row.get('estado_partido') != 'en_juego':
            continue
        m = sf(row.get('minuto'))
        if m is None or m < cfg['min_min'] or m > cfg['max_min']:
            continue

        gl = si(row.get('goles_local'))
        gv = si(row.get('goles_visitante'))
        xg_l = sf(row.get('xg_local'))
        xg_v = sf(row.get('xg_visitante'))
        sot_l = si(row.get('tiros_puerta_local'))
        sot_v = si(row.get('tiros_puerta_visitante'))
        bh = sf(row.get('back_home'))
        ba = sf(row.get('back_away'))

        if any(v is None for v in [gl, gv, xg_l, xg_v, sot_l, sot_v, bh, ba]):
            continue

        candidates = []
        # Home dominant
        if sot_v > 0:
            ratio_l = sot_l / sot_v
        else:
            ratio_l = sot_l * 2 if sot_l >= cfg['sot_min'] else 0
        xg_up_l = xg_l - gl
        if (sot_l >= cfg['sot_min'] and ratio_l >= cfg['ratio_min'] and
                xg_up_l > cfg['xg_up_min'] and cfg['min_odds'] <= bh <= cfg['max_odds']):
            candidates.append(('home', bh, xg_up_l))

        # Away dominant
        if sot_l > 0:
            ratio_v = sot_v / sot_l
        else:
            ratio_v = sot_v * 2 if sot_v >= cfg['sot_min'] else 0
        xg_up_v = xg_v - gv
        if (sot_v >= cfg['sot_min'] and ratio_v >= cfg['ratio_min'] and
                xg_up_v > cfg['xg_up_min'] and cfg['min_odds'] <= ba <= cfg['max_odds']):
            candidates.append(('away', ba, xg_up_v))

        if not candidates:
            continue

        # Pick best
        candidates.sort(key=lambda x: x[2], reverse=True)
        team, odds, xg_up = candidates[0]

        if team == 'home':
            won = gl_final > gv_final
        else:
            won = gv_final > gl_final

        pl = calc_pl(won, odds)
        synth = compute_synth_at_trigger(in_play, i)

        bets.append({
            'strategy': f'momentum_xg_{version}',
            'match': os.path.basename(rows[0].get('tab_id', '')),
            'minuto': m,
            'odds': odds,
            'won': won,
            'pl': pl,
            'ft_score': f"{gl_final}-{gv_final}",
            'team': team,
            'xg_underperf': round(xg_up, 3),
            **{f'synth_{k}': v for k, v in synth.items()},
        })

    return bets


# ═══════════════════════════════════════════════════════════════════════
# VERSION DEFINITIONS (current + new synthetic versions)
# ═══════════════════════════════════════════════════════════════════════

def define_versions():
    """Define all versions: current and new synthetic ones."""

    versions = {
        'back_draw_00': {
            'v1': lambda b: True,
            'v15': lambda b: b.get('passes_v15', False),
            'v2r': lambda b: b.get('passes_v2r', False),
            'v2': lambda b: b.get('passes_v2', False),
            # ── New synthetic versions ──
            'v3_xg_dom': lambda b: (
                b.get('passes_v2', False) and
                b.get('synth_xg_dominance') is not None and
                (b['synth_xg_dominance'] > 0.60 or b['synth_xg_dominance'] < 0.40)
                # Strong xG asymmetry = draw holds better (r=-0.20)
            ),
            'v3_opta': lambda b: (
                b.get('passes_v15', False) and
                b.get('synth_opta_gap') is not None and
                abs(b['synth_opta_gap']) > 5
                # Opta gap = one team clearly better (r=-0.13)
            ),
            'v3_no_press_v': lambda b: (
                b.get('passes_v15', False) and
                (b.get('synth_pressure_index_v') is None or b['synth_pressure_index_v'] < 0.5)
                # Avoid when visitor is pressing hard (r=+0.10 danger)
            ),
            'v3_combined': lambda b: (
                b.get('passes_v15', False) and
                (b.get('synth_xg_dominance') is not None and
                 (b['synth_xg_dominance'] > 0.55 or b['synth_xg_dominance'] < 0.45)) and
                (b.get('synth_pressure_index_v') is None or b['synth_pressure_index_v'] < 0.5)
            ),
            'v3_imp_draw': lambda b: (
                b.get('passes_v15', False) and
                b.get('synth_implied_prob_draw') is not None and
                b['synth_implied_prob_draw'] > 0.30
                # Market believes in draw (r=-0.12)
            ),
            'v3_full': lambda b: (
                b.get('passes_v2', False) and
                (b.get('synth_xg_dominance') is not None and
                 (b['synth_xg_dominance'] > 0.55 or b['synth_xg_dominance'] < 0.45)) and
                (b.get('synth_pressure_index_v') is None or b['synth_pressure_index_v'] < 0.5) and
                (b.get('synth_implied_prob_draw') is None or b['synth_implied_prob_draw'] > 0.25)
            ),
        },

        'xg_underperformance': {
            'v1': lambda b: True,
            'v2': lambda b: b.get('passes_v2', False),
            'v3': lambda b: b.get('passes_v3', False),
            # ── New synthetic versions ──
            'v4_press': lambda b: (
                b.get('passes_v2', False) and
                b.get('synth_pressure_index_l' if b.get('team') == 'home' else 'synth_pressure_index_v') is not None and
                (b.get(f'synth_pressure_index_{"l" if b.get("team") == "home" else "v"}') or 0) > 0.3
                # Team is actively pressing
            ),
            'v4_open': lambda b: (
                b.get('passes_v2', False) and
                b.get('synth_match_openness') is not None and
                b['synth_match_openness'] > 20
                # Open match = more likely to score
            ),
            'v4_xg_vel': lambda b: (
                b.get('passes_v2', False) and
                b.get(f'synth_xg_velocity_{"l" if b.get("team") == "home" else "v"}_10m') is not None and
                (b.get(f'synth_xg_velocity_{"l" if b.get("team") == "home" else "v"}_10m') or 0) > 0.01
                # Increasing xG rate (team getting more dangerous)
            ),
            'v4_combined': lambda b: (
                b.get('passes_v2', False) and
                b.get('synth_match_openness') is not None and
                b['synth_match_openness'] > 15 and
                (b.get('synth_implied_prob_o25') is None or b['synth_implied_prob_o25'] > 0.40)
            ),
        },

        'goal_clustering': {
            'v2': lambda b: True,
            'v3': lambda b: b.get('passes_v3', False),
            # ── New synthetic versions ──
            'v4_open': lambda b: (
                b.get('synth_match_openness') is not None and
                b['synth_match_openness'] > 25
            ),
            'v4_danger': lambda b: (
                b.get('synth_danger_score_l') is not None and
                b.get('synth_danger_score_v') is not None and
                (b['synth_danger_score_l'] + b['synth_danger_score_v']) > 15
            ),
            'v4_xg_rem': lambda b: (
                b.get('synth_xg_remaining') is not None and
                b['synth_xg_remaining'] > 0.8
            ),
        },

        'pressure_cooker': {
            'v1': lambda b: True,
            # ── New synthetic versions ──
            'v2_open': lambda b: (
                b.get('synth_match_openness') is not None and
                b['synth_match_openness'] > 20
            ),
            'v2_o25': lambda b: (
                b.get('synth_implied_prob_o25') is not None and
                b['synth_implied_prob_o25'] > 0.40
            ),
            'v2_tension': lambda b: (
                b.get('synth_scoreline_tension') is not None and
                b['synth_scoreline_tension'] > 2.0
            ),
            'v2_combined': lambda b: (
                (b.get('synth_implied_prob_o25') is None or b['synth_implied_prob_o25'] > 0.35) and
                (b.get('synth_match_openness') is None or b['synth_match_openness'] > 15)
            ),
        },

        'odds_drift': {
            'v1': lambda b: True,
            'v2': lambda b: b.get('passes_v2', False),
            'v3': lambda b: b.get('passes_v3', False),
            'v4': lambda b: b.get('passes_v4', False),
            'v5': lambda b: b.get('passes_v5', False),
            # ── New synthetic versions ──
            'v6_momentum': lambda b: (
                b.get('passes_v5', False) and
                b.get('synth_momentum_gap') is not None and
                b['synth_momentum_gap'] > 200
            ),
            'v6_opta': lambda b: (
                b.get('passes_v5', False) and
                b.get('synth_opta_gap') is not None and
                ((b.get('team') == 'home' and b['synth_opta_gap'] > 5) or
                 (b.get('team') == 'away' and b['synth_opta_gap'] < -5))
            ),
        },
    }

    return versions


# ═══════════════════════════════════════════════════════════════════════
# MAIN BACKTEST
# ═══════════════════════════════════════════════════════════════════════

def run_backtest():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")))
    print(f"Loading {len(files)} matches...")

    # Collect all bets
    all_bets = {
        'back_draw_00': [],
        'xg_underperformance': [],
        'odds_drift': [],
        'goal_clustering': [],
        'pressure_cooker': [],
    }

    for fi, fp in enumerate(files):
        rows = load_match(fp)
        if len(rows) < 15:
            continue

        if (fi + 1) % 50 == 0:
            print(f"  Processed {fi+1}/{len(files)}...")

        all_bets['back_draw_00'].extend(detect_back_draw_00(rows))
        all_bets['xg_underperformance'].extend(detect_xg_underperformance(rows))
        all_bets['odds_drift'].extend(detect_odds_drift(rows))
        all_bets['goal_clustering'].extend(detect_goal_clustering(rows))
        all_bets['pressure_cooker'].extend(detect_pressure_cooker(rows))

    # Also detect momentum_xg
    all_bets['momentum_xg_v1'] = []
    all_bets['momentum_xg_v2'] = []
    for fi, fp in enumerate(files):
        rows = load_match(fp)
        if len(rows) < 15:
            continue
        all_bets['momentum_xg_v1'].extend(detect_momentum_xg(rows, 'v1'))
        all_bets['momentum_xg_v2'].extend(detect_momentum_xg(rows, 'v2'))

    print(f"\nBets detected:")
    for strat, bets in all_bets.items():
        wins = sum(1 for b in bets if b['won'])
        pl = sum(b['pl'] for b in bets)
        print(f"  {strat}: {len(bets)} bets, {wins}W, P/L={pl:+.2f}")

    # ── Run version comparisons ──
    versions = define_versions()

    MIN_ODDS = {
        'back_draw_00': 1.93,
        'xg_underperformance': 1.51,
        'odds_drift': 1.65,
        'goal_clustering': 1.73,
        'pressure_cooker': 1.83,
    }

    print("\n" + "=" * 100)
    print("VERSION COMPARISON (flat stake=10, 5% commission)")
    print("=" * 100)

    all_results = {}

    for strategy, version_filters in versions.items():
        bets = all_bets[strategy]

        # Apply min odds
        min_odds = MIN_ODDS.get(strategy, 1.0)
        bets_filtered = [b for b in bets if b['odds'] >= min_odds]

        print(f"\n{'━' * 100}")
        print(f"  STRATEGY: {strategy.upper()}")
        print(f"  Total bets (after min odds {min_odds}): {len(bets_filtered)}")
        print(f"{'━' * 100}")

        results = {}
        for vname, vfilter in version_filters.items():
            vbets = [b for b in bets_filtered if vfilter(b)]
            n = len(vbets)
            if n == 0:
                results[vname] = {'n': 0, 'wins': 0, 'wr': 0, 'pl': 0, 'roi': 0, 'avg_odds': 0}
                continue

            wins = sum(1 for b in vbets if b['won'])
            pl = round(sum(b['pl'] for b in vbets), 2)
            roi = round(pl / (n * STAKE) * 100, 2)
            wr = round(wins / n * 100, 1)
            avg_odds = round(sum(b['odds'] for b in vbets) / n, 2)

            results[vname] = {'n': n, 'wins': wins, 'wr': wr, 'pl': pl, 'roi': roi, 'avg_odds': avg_odds}

        # Sort by P/L
        sorted_versions = sorted(results.items(), key=lambda x: x[1]['pl'], reverse=True)

        # Find best current version
        current_versions = [v for v in sorted_versions if not v[0].startswith('v3_') and not v[0].startswith('v4_') and not v[0].startswith('v6_') and not v[0].startswith('v2_')]
        new_versions = [v for v in sorted_versions if v[0].startswith('v3_') or v[0].startswith('v4_') or v[0].startswith('v6_') or v[0].startswith('v2_')]

        best_current = current_versions[0] if current_versions else None
        best_new = None
        for v in new_versions:
            if v[1]['n'] >= 3:  # minimum sample
                best_new = v
                break

        print(f"\n  {'Version':<20s} {'Bets':>5s} {'Wins':>5s} {'WR%':>6s} {'P/L':>8s} {'ROI%':>7s} {'AvgOdds':>8s} {'Type':>10s}")
        print(f"  {'─' * 20} {'─' * 5} {'─' * 5} {'─' * 6} {'─' * 8} {'─' * 7} {'─' * 8} {'─' * 10}")

        for vname, vdata in sorted_versions:
            if vdata['n'] == 0:
                continue
            is_new = vname.startswith('v3_') or vname.startswith('v4_') or vname.startswith('v6_') or vname.startswith('v2_')
            vtype = "NEW" if is_new else "CURRENT"
            marker = ""
            if best_current and vname == best_current[0]:
                marker = " <-- BEST CURRENT"
            if best_new and vname == best_new[0]:
                marker = " <-- BEST NEW"

            pl_str = f"{vdata['pl']:+.2f}"
            print(f"  {vname:<20s} {vdata['n']:>5d} {vdata['wins']:>5d} {vdata['wr']:>5.1f}% {pl_str:>8s} {vdata['roi']:>6.1f}% {vdata['avg_odds']:>8.2f} {vtype:>10s}{marker}")

        # Delta analysis
        if best_current and best_new and best_current[1]['n'] > 0:
            bc = best_current[1]
            bn = best_new[1]
            pl_delta = bn['pl'] - bc['pl']
            roi_delta = bn['roi'] - bc['roi']
            wr_delta = bn['wr'] - bc['wr']
            print(f"\n  >>> Delta best new ({best_new[0]}) vs best current ({best_current[0]}):")
            print(f"      P/L: {pl_delta:+.2f} EUR | ROI: {roi_delta:+.1f}pp | WR: {wr_delta:+.1f}pp | Bets: {bn['n']} vs {bc['n']}")

            if pl_delta > 0 and bn['n'] >= 3:
                print(f"      RESULT: NEW VERSION IMPROVES P/L")
            elif bn['roi'] > bc['roi'] and bn['n'] >= 3:
                print(f"      RESULT: NEW VERSION IMPROVES ROI (but may have fewer bets)")
            else:
                print(f"      RESULT: Current version remains better")

        all_results[strategy] = results

    # ── Momentum XG (special: bets are in separate lists) ──
    print(f"\n{'━' * 100}")
    print(f"  STRATEGY: MOMENTUM_XG")
    print(f"{'━' * 100}")

    for ver in ['v1', 'v2']:
        bets = all_bets[f'momentum_xg_{ver}']
        min_odds = 1.65 if ver == 'v1' else 1.83
        bets_f = [b for b in bets if b['odds'] >= min_odds]
        n = len(bets_f)
        if n == 0:
            print(f"  momentum_xg_{ver}: 0 bets")
            continue
        wins = sum(1 for b in bets_f if b['won'])
        pl = round(sum(b['pl'] for b in bets_f), 2)
        roi = round(pl / (n * STAKE) * 100, 2)
        wr = round(wins / n * 100, 1)
        print(f"  momentum_xg_{ver}: {n} bets, {wins}W, WR={wr}%, P/L={pl:+.2f}, ROI={roi:+.1f}%")

    # ── FINAL SUMMARY ──
    print("\n" + "=" * 100)
    print("FINAL SUMMARY: VERSIONS TO INTEGRATE")
    print("=" * 100)

    for strategy, results in all_results.items():
        current_vs = {k: v for k, v in results.items()
                     if not k.startswith('v3_') and not k.startswith('v4_') and not k.startswith('v6_') and not k.startswith('v2_')}
        new_vs = {k: v for k, v in results.items()
                 if (k.startswith('v3_') or k.startswith('v4_') or k.startswith('v6_') or k.startswith('v2_')) and v['n'] >= 3}

        if not current_vs or not new_vs:
            continue

        best_c_name = max(current_vs, key=lambda k: current_vs[k]['pl'])
        best_c = current_vs[best_c_name]

        improvements = []
        for vname, vdata in new_vs.items():
            if vdata['pl'] > best_c['pl']:
                improvements.append((vname, vdata, vdata['pl'] - best_c['pl']))

        if improvements:
            improvements.sort(key=lambda x: x[2], reverse=True)
            top = improvements[0]
            print(f"\n  {strategy}:")
            print(f"    Current best: {best_c_name} (P/L={best_c['pl']:+.2f}, {best_c['n']} bets, WR={best_c['wr']}%, ROI={best_c['roi']:+.1f}%)")
            print(f"    UPGRADE to:   {top[0]} (P/L={top[1]['pl']:+.2f}, {top[1]['n']} bets, WR={top[1]['wr']}%, ROI={top[1]['roi']:+.1f}%)")
            print(f"    Improvement:  P/L {top[2]:+.2f} EUR, ROI {top[1]['roi'] - best_c['roi']:+.1f}pp")
        else:
            print(f"\n  {strategy}: No improvement found. Best current: {best_c_name} (P/L={best_c['pl']:+.2f})")


if __name__ == '__main__':
    run_backtest()