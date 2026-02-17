"""
Synthetic Attributes Explorer
=============================
Procesa los 200+ partidos con datos minuto a minuto y genera:
1. Un CSV enriquecido con ~40 atributos sintéticos por fila
2. Análisis de correlación con "gol en los próximos N minutos"
3. Rankings de los atributos más predictivos

Columnas con datos reales (>50% fill rate):
  xg, opta_points, posesion, tiros, tiros_puerta, touches_box,
  corners, total_passes, attacks, momentum, todas las odds,
  tarjetas_amarillas, booking_points
"""

import csv
import os
import glob
import math
import json
from collections import defaultdict
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "betfair_scraper", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "synthetic_analysis")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_float(val, default=None):
    """Convert to float, return default if empty/invalid."""
    if val is None or val == '' or val == 'None':
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_div(a, b, default=0.0):
    """Safe division."""
    if b is None or a is None or b == 0:
        return default
    return a / b


def entropy(probs):
    """Shannon entropy of a probability distribution."""
    h = 0.0
    for p in probs:
        if p and p > 0 and p < 1:
            h -= p * math.log2(p)
    return h


def load_match(filepath):
    """Load a match CSV, return list of dicts with parsed floats."""
    with open(filepath, encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append(row)
    return rows


def get_in_play_rows(rows):
    """Filter to only in-play rows with valid minute, sorted by minute."""
    result = []
    for row in rows:
        if row.get('estado_partido') != 'en_juego':
            continue
        m = safe_float(row.get('minuto'))
        if m is None:
            continue
        result.append(row)
    result.sort(key=lambda r: safe_float(r['minuto'], 0))
    return result


def get_val(row, col):
    """Get a float value from a row."""
    return safe_float(row.get(col))


def lookback_val(rows, idx, col, minutes_back):
    """Get value of col from approximately `minutes_back` minutes ago."""
    current_min = safe_float(rows[idx].get('minuto'), 0)
    target_min = current_min - minutes_back
    best_row = None
    best_dist = float('inf')
    for i in range(max(0, idx - minutes_back - 5), idx):
        m = safe_float(rows[i].get('minuto'), 0)
        dist = abs(m - target_min)
        if dist < best_dist:
            best_dist = dist
            best_row = rows[i]
    if best_row and best_dist < minutes_back * 0.5 + 2:
        return safe_float(best_row.get(col))
    return None


# ---------------------------------------------------------------------------
# Synthetic attribute calculators
# ---------------------------------------------------------------------------

def compute_synthetic(rows, idx):
    """Compute all synthetic attributes for rows[idx]. Returns dict."""
    row = rows[idx]
    s = {}  # synthetic attributes dict
    minute = safe_float(row.get('minuto'), 0)
    s['minute'] = minute

    # --- Raw values (for convenience) ---
    gl = safe_float(row.get('goles_local'), 0)
    gv = safe_float(row.get('goles_visitante'), 0)
    s['total_goals'] = gl + gv
    s['goal_diff'] = gl - gv
    s['score_label'] = f"{int(gl)}-{int(gv)}"

    xg_l = get_val(row, 'xg_local')
    xg_v = get_val(row, 'xg_visitante')
    pos_l = get_val(row, 'posesion_local')
    pos_v = get_val(row, 'posesion_visitante')
    shots_l = get_val(row, 'tiros_local')
    shots_v = get_val(row, 'tiros_visitante')
    sot_l = get_val(row, 'tiros_puerta_local')
    sot_v = get_val(row, 'tiros_puerta_visitante')
    tbox_l = get_val(row, 'touches_box_local')
    tbox_v = get_val(row, 'touches_box_visitante')
    corn_l = get_val(row, 'corners_local')
    corn_v = get_val(row, 'corners_visitante')
    passes_l = get_val(row, 'total_passes_local')
    passes_v = get_val(row, 'total_passes_visitante')
    attacks_l = get_val(row, 'attacks_local')
    attacks_v = get_val(row, 'attacks_visitante')
    mom_l = get_val(row, 'momentum_local')
    mom_v = get_val(row, 'momentum_visitante')
    opta_l = get_val(row, 'opta_points_local')
    opta_v = get_val(row, 'opta_points_visitante')

    # Odds
    back_h = get_val(row, 'back_home')
    back_d = get_val(row, 'back_draw')
    back_a = get_val(row, 'back_away')
    lay_h = get_val(row, 'lay_home')
    lay_d = get_val(row, 'lay_draw')
    lay_a = get_val(row, 'lay_away')
    back_o25 = get_val(row, 'back_over25')
    back_u25 = get_val(row, 'back_under25')

    # ===================================================================
    # CATEGORY 1: Velocity / Rate features (rolling 5 and 10 min windows)
    # ===================================================================
    for window in [5, 10]:
        for col, name in [
            ('xg_local', 'xg_l'), ('xg_visitante', 'xg_v'),
            ('tiros_local', 'shots_l'), ('tiros_visitante', 'shots_v'),
            ('tiros_puerta_local', 'sot_l'), ('tiros_puerta_visitante', 'sot_v'),
            ('corners_local', 'corn_l'), ('corners_visitante', 'corn_v'),
            ('touches_box_local', 'tbox_l'), ('touches_box_visitante', 'tbox_v'),
        ]:
            now = get_val(row, col)
            prev = lookback_val(rows, idx, col, window)
            key = f"delta_{name}_{window}m"
            if now is not None and prev is not None:
                s[key] = now - prev
            else:
                s[key] = None

    # xG velocity (xG per minute over last 10 min)
    if s.get('delta_xg_l_10m') is not None:
        s['xg_velocity_l_10m'] = s['delta_xg_l_10m'] / 10.0
    else:
        s['xg_velocity_l_10m'] = None
    if s.get('delta_xg_v_10m') is not None:
        s['xg_velocity_v_10m'] = s['delta_xg_v_10m'] / 10.0
    else:
        s['xg_velocity_v_10m'] = None

    # Momentum shift
    for window in [5, 10]:
        for side, col in [('l', 'momentum_local'), ('v', 'momentum_visitante')]:
            now = get_val(row, col)
            prev = lookback_val(rows, idx, col, window)
            key = f"momentum_shift_{side}_{window}m"
            if now is not None and prev is not None:
                s[key] = now - prev
            else:
                s[key] = None

    # Possession shift (10 min)
    pos_now = pos_l
    pos_prev = lookback_val(rows, idx, 'posesion_local', 10)
    if pos_now is not None and pos_prev is not None:
        s['possession_shift_l_10m'] = pos_now - pos_prev
    else:
        s['possession_shift_l_10m'] = None

    # Odds velocity (5 min)
    for col, name in [('back_home', 'home'), ('back_draw', 'draw'), ('back_away', 'away'),
                       ('back_over25', 'o25')]:
        now = get_val(row, col)
        prev = lookback_val(rows, idx, col, 5)
        if now is not None and prev is not None and prev > 0:
            s[f'odds_drift_{name}_5m_pct'] = ((now - prev) / prev) * 100
        else:
            s[f'odds_drift_{name}_5m_pct'] = None

    # ===================================================================
    # CATEGORY 2: Efficiency & Ratio features
    # ===================================================================
    # xG per shot (quality of chances)
    s['xg_per_shot_l'] = safe_div(xg_l, shots_l) if xg_l is not None and shots_l else None
    s['xg_per_shot_v'] = safe_div(xg_v, shots_v) if xg_v is not None and shots_v else None

    # Shot on target percentage
    s['sot_pct_l'] = safe_div(sot_l, shots_l) * 100 if sot_l is not None and shots_l else None
    s['sot_pct_v'] = safe_div(sot_v, shots_v) * 100 if sot_v is not None and shots_v else None

    # xG overperformance (goals - xG): positive = lucky/clinical
    s['xg_overperf_l'] = (gl - xg_l) if xg_l is not None else None
    s['xg_overperf_v'] = (gv - xg_v) if xg_v is not None else None

    # Touches in box per shot on target (buildup effort per quality chance)
    s['tbox_per_sot_l'] = safe_div(tbox_l, sot_l) if tbox_l is not None and sot_l else None
    s['tbox_per_sot_v'] = safe_div(tbox_v, sot_v) if tbox_v is not None and sot_v else None

    # Passes per minute (tempo)
    s['passes_per_min_l'] = safe_div(passes_l, minute) if passes_l is not None and minute > 0 else None
    s['passes_per_min_v'] = safe_div(passes_v, minute) if passes_v is not None and minute > 0 else None

    # xG per minute (overall attacking productivity normalized by time)
    s['xg_per_min_l'] = safe_div(xg_l, minute) if xg_l is not None and minute > 0 else None
    s['xg_per_min_v'] = safe_div(xg_v, minute) if xg_v is not None and minute > 0 else None

    # Corners per attack (territorial conversion)
    s['corners_per_attack_l'] = safe_div(corn_l, attacks_l) if corn_l is not None and attacks_l else None
    s['corners_per_attack_v'] = safe_div(corn_v, attacks_v) if corn_v is not None and attacks_v else None

    # ===================================================================
    # CATEGORY 3: Asymmetry / Dominance features
    # ===================================================================
    # xG dominance (0.5 = balanced, >0.5 = local dominates)
    if xg_l is not None and xg_v is not None and (xg_l + xg_v) > 0:
        s['xg_dominance'] = xg_l / (xg_l + xg_v)
    else:
        s['xg_dominance'] = None

    # Shot dominance
    if shots_l is not None and shots_v is not None and (shots_l + shots_v) > 0:
        s['shot_dominance'] = shots_l / (shots_l + shots_v)
    else:
        s['shot_dominance'] = None

    # SoT dominance
    if sot_l is not None and sot_v is not None and (sot_l + sot_v) > 0:
        s['sot_dominance'] = sot_l / (sot_l + sot_v)
    else:
        s['sot_dominance'] = None

    # Momentum dominance
    if mom_l is not None and mom_v is not None and (mom_l + mom_v) > 0:
        s['momentum_dominance'] = mom_l / (mom_l + mom_v)
    else:
        s['momentum_dominance'] = None

    # Territorial dominance (composite: possession + attacks share + touches_box share)
    components = []
    if pos_l is not None:
        components.append(pos_l / 100.0)
    if attacks_l is not None and attacks_v is not None and (attacks_l + attacks_v) > 0:
        components.append(attacks_l / (attacks_l + attacks_v))
    if tbox_l is not None and tbox_v is not None and (tbox_l + tbox_v) > 0:
        components.append(tbox_l / (tbox_l + tbox_v))
    s['territorial_dominance'] = sum(components) / len(components) if components else None

    # Opta dominance
    if opta_l is not None and opta_v is not None and (opta_l + opta_v) > 0:
        s['opta_dominance'] = opta_l / (opta_l + opta_v)
    else:
        s['opta_dominance'] = None

    # ===================================================================
    # CATEGORY 4: Market-based features
    # ===================================================================
    # Implied probabilities
    if back_h and back_h > 0:
        s['implied_prob_home'] = 1.0 / back_h
    else:
        s['implied_prob_home'] = None
    if back_d and back_d > 0:
        s['implied_prob_draw'] = 1.0 / back_d
    else:
        s['implied_prob_draw'] = None
    if back_a and back_a > 0:
        s['implied_prob_away'] = 1.0 / back_a
    else:
        s['implied_prob_away'] = None

    # Over 2.5 implied probability
    if back_o25 and back_o25 > 0:
        s['implied_prob_o25'] = 1.0 / back_o25
    else:
        s['implied_prob_o25'] = None

    # Back-lay spread (market conviction: tighter = more certain)
    if back_h and lay_h:
        s['spread_home'] = lay_h - back_h
    else:
        s['spread_home'] = None
    if back_d and lay_d:
        s['spread_draw'] = lay_d - back_d
    else:
        s['spread_draw'] = None

    # Market vs xG divergence
    # If market says home team has X% chance but xG suggests different
    if s['implied_prob_home'] is not None and xg_l is not None and xg_v is not None:
        xg_total = xg_l + xg_v
        if xg_total > 0.1:  # only meaningful with some xG
            # Simple: compare market implied prob with xG share
            xg_share_home = xg_l / xg_total
            s['market_vs_xg_home'] = s['implied_prob_home'] - xg_share_home
        else:
            s['market_vs_xg_home'] = None
    else:
        s['market_vs_xg_home'] = None

    # Correct score entropy (how uncertain is the CS market)
    cs_probs = []
    for sc in ['0_0','1_0','0_1','1_1','2_0','0_2','2_1','1_2','2_2','3_0','0_3','3_1','1_3','3_2','2_3']:
        odds = get_val(row, f'back_rc_{sc}')
        if odds and odds > 0:
            cs_probs.append(1.0 / odds)
    if cs_probs:
        # Normalize to sum to 1
        total = sum(cs_probs)
        if total > 0:
            cs_probs = [p / total for p in cs_probs]
            s['cs_entropy'] = entropy(cs_probs)
        else:
            s['cs_entropy'] = None
    else:
        s['cs_entropy'] = None

    # ===================================================================
    # CATEGORY 5: Composite / Index features
    # ===================================================================

    # Pressure Index (recent attacking intensity)
    # Weighted combination of recent deltas in sot, corners, xg, touches_box
    pressure_components = []
    weights = []
    for key, w in [('delta_sot_l_5m', 3.0), ('delta_corn_l_5m', 1.5),
                    ('delta_xg_l_5m', 5.0), ('delta_tbox_l_5m', 1.0),
                    ('delta_shots_l_5m', 2.0)]:
        if s.get(key) is not None:
            pressure_components.append(s[key] * w)
            weights.append(w)
    s['pressure_index_l'] = sum(pressure_components) / sum(weights) if weights else None

    pressure_components_v = []
    weights_v = []
    for key, w in [('delta_sot_v_5m', 3.0), ('delta_corn_v_5m', 1.5),
                    ('delta_xg_v_5m', 5.0), ('delta_tbox_v_5m', 1.0),
                    ('delta_shots_v_5m', 2.0)]:
        if s.get(key) is not None:
            pressure_components_v.append(s[key] * w)
            weights_v.append(w)
    s['pressure_index_v'] = sum(pressure_components_v) / sum(weights_v) if weights_v else None

    # Pressure asymmetry (which team is pressing more recently)
    if s['pressure_index_l'] is not None and s['pressure_index_v'] is not None:
        s['pressure_asymmetry'] = s['pressure_index_l'] - s['pressure_index_v']
    else:
        s['pressure_asymmetry'] = None

    # Danger score (absolute level of danger generated, cumulative)
    danger_l_parts = []
    for val, w in [(xg_l, 3.0), (sot_l, 2.0), (tbox_l, 0.5), (corn_l, 0.3)]:
        if val is not None:
            danger_l_parts.append(val * w)
    s['danger_score_l'] = sum(danger_l_parts) if danger_l_parts else None

    danger_v_parts = []
    for val, w in [(xg_v, 3.0), (sot_v, 2.0), (tbox_v, 0.5), (corn_v, 0.3)]:
        if val is not None:
            danger_v_parts.append(val * w)
    s['danger_score_v'] = sum(danger_v_parts) if danger_v_parts else None

    # Match openness (how open/attacking is the game overall)
    openness_parts = []
    for val in [shots_l, shots_v, sot_l, sot_v, corn_l, corn_v]:
        if val is not None:
            openness_parts.append(val)
    s['match_openness'] = sum(openness_parts) + (gl + gv) * 5 if openness_parts else None

    # Scoreline tension: higher when close score + late + high xG
    if minute > 0 and xg_l is not None and xg_v is not None:
        closeness = max(0, 3 - abs(gl - gv))  # 3 if tied, 2 if 1-goal diff, etc.
        time_factor = minute / 90.0  # increases with time
        xg_factor = (xg_l + xg_v)  # more expected goals = more tension
        s['scoreline_tension'] = closeness * time_factor * (1 + xg_factor)
    else:
        s['scoreline_tension'] = None

    # xG frustration index: high xG but no goals = frustration = likely to push harder
    if xg_l is not None:
        s['xg_frustration_l'] = max(0, xg_l - gl) * (minute / 90.0)
    else:
        s['xg_frustration_l'] = None
    if xg_v is not None:
        s['xg_frustration_v'] = max(0, xg_v - gv) * (minute / 90.0)
    else:
        s['xg_frustration_v'] = None

    # Combined xG frustration (total game frustration)
    if s['xg_frustration_l'] is not None and s['xg_frustration_v'] is not None:
        s['xg_frustration_total'] = s['xg_frustration_l'] + s['xg_frustration_v']
    else:
        s['xg_frustration_total'] = None

    # Momentum convergence/divergence
    if mom_l is not None and mom_v is not None:
        s['momentum_gap'] = abs(mom_l - mom_v)
    else:
        s['momentum_gap'] = None

    # Expected goals remaining (based on xG rate and time left)
    if xg_l is not None and xg_v is not None and minute > 5:
        xg_rate = (xg_l + xg_v) / minute
        time_left = max(0, 90 - minute)
        s['xg_remaining'] = xg_rate * time_left
    else:
        s['xg_remaining'] = None

    # Opta performance gap (useful signal for team quality in match)
    if opta_l is not None and opta_v is not None:
        s['opta_gap'] = opta_l - opta_v
    else:
        s['opta_gap'] = None

    return s


# ---------------------------------------------------------------------------
# Target variables (what we want to predict)
# ---------------------------------------------------------------------------

def compute_targets(rows, idx):
    """Compute target variables: goal in next N minutes."""
    row = rows[idx]
    minute = safe_float(row.get('minuto'), 0)
    current_goals = safe_float(row.get('goles_local'), 0) + safe_float(row.get('goles_visitante'), 0)

    targets = {}
    for lookahead in [5, 10, 15]:
        target_min = minute + lookahead
        future_goals = None
        for j in range(idx + 1, len(rows)):
            m_j = safe_float(rows[j].get('minuto'), 0)
            if m_j >= target_min:
                g_j = safe_float(rows[j].get('goles_local'), 0) + safe_float(rows[j].get('goles_visitante'), 0)
                future_goals = g_j
                break
        if future_goals is not None:
            targets[f'goal_next_{lookahead}m'] = 1 if future_goals > current_goals else 0
        else:
            targets[f'goal_next_{lookahead}m'] = None

    # Final total goals
    last_row = rows[-1]
    final_goals = safe_float(last_row.get('goles_local'), 0) + safe_float(last_row.get('goles_visitante'), 0)
    targets['final_total_goals'] = final_goals

    # Which team scores next (1=local, -1=visitante, 0=nobody)
    for j in range(idx + 1, len(rows)):
        gl_j = safe_float(rows[j].get('goles_local'), 0)
        gv_j = safe_float(rows[j].get('goles_visitante'), 0)
        gl_now = safe_float(row.get('goles_local'), 0)
        gv_now = safe_float(row.get('goles_visitante'), 0)
        if gl_j > gl_now:
            targets['next_goal_team'] = 1  # local
            break
        elif gv_j > gv_now:
            targets['next_goal_team'] = -1  # visitante
            break
    else:
        targets['next_goal_team'] = 0  # nobody scores after this

    return targets


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process_all_matches():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")))
    print(f"Found {len(files)} match files")

    all_rows_enriched = []
    match_summaries = []
    skipped = 0
    processed = 0

    for fi, filepath in enumerate(files):
        match_name = os.path.basename(filepath).replace('partido_', '').replace('.csv', '')
        rows = load_match(filepath)
        in_play = get_in_play_rows(rows)

        if len(in_play) < 15:  # need minimum data
            skipped += 1
            continue

        processed += 1
        if processed % 20 == 0:
            print(f"  Processing {processed}... ({match_name})")

        for idx in range(len(in_play)):
            minute = safe_float(in_play[idx].get('minuto'), 0)
            if minute < 5:  # skip very early minutes (no lookback possible)
                continue

            synth = compute_synthetic(in_play, idx)
            targets = compute_targets(in_play, idx)

            enriched = {
                'match': match_name,
                'minute': minute,
            }
            enriched.update(synth)
            enriched.update(targets)
            all_rows_enriched.append(enriched)

        # Match summary
        last = in_play[-1]
        first_30 = [r for r in in_play if safe_float(r.get('minuto'), 0) <= 30]
        summary = {
            'match': match_name,
            'total_rows': len(in_play),
            'final_goals_l': safe_float(last.get('goles_local'), 0),
            'final_goals_v': safe_float(last.get('goles_visitante'), 0),
            'final_total_goals': safe_float(last.get('goles_local'), 0) + safe_float(last.get('goles_visitante'), 0),
            'final_xg_l': get_val(last, 'xg_local'),
            'final_xg_v': get_val(last, 'xg_visitante'),
        }
        match_summaries.append(summary)

    print(f"\nProcessed: {processed} matches, Skipped: {skipped} (too few rows)")
    print(f"Total enriched rows: {len(all_rows_enriched)}")

    return all_rows_enriched, match_summaries


def save_enriched_csv(rows, filename):
    if not rows:
        return
    filepath = os.path.join(OUTPUT_DIR, filename)
    keys = list(rows[0].keys())
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"Saved: {filepath} ({len(rows)} rows, {len(keys)} columns)")


# ---------------------------------------------------------------------------
# Correlation Analysis
# ---------------------------------------------------------------------------

def analyze_correlations(rows):
    """Compute correlation of each synthetic attribute with target variables."""
    print("\n" + "=" * 80)
    print("CORRELATION ANALYSIS")
    print("=" * 80)

    # Get all synthetic attribute names (exclude metadata and targets)
    exclude = {'match', 'minute', 'score_label', 'total_goals', 'goal_diff',
               'goal_next_5m', 'goal_next_10m', 'goal_next_15m',
               'final_total_goals', 'next_goal_team'}
    all_keys = set()
    for r in rows:
        all_keys.update(r.keys())
    synth_keys = sorted(all_keys - exclude)

    targets = ['goal_next_5m', 'goal_next_10m', 'goal_next_15m']

    results = {}
    for target in targets:
        results[target] = {}
        for attr in synth_keys:
            # Collect paired values
            xs = []
            ys = []
            for r in rows:
                x = r.get(attr)
                y = r.get(target)
                if x is not None and y is not None:
                    try:
                        xs.append(float(x))
                        ys.append(float(y))
                    except (ValueError, TypeError):
                        continue

            if len(xs) < 50:  # need minimum sample
                continue

            # Pearson correlation
            n = len(xs)
            mean_x = sum(xs) / n
            mean_y = sum(ys) / n
            cov = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / n
            std_x = (sum((x - mean_x) ** 2 for x in xs) / n) ** 0.5
            std_y = (sum((y - mean_y) ** 2 for y in ys) / n) ** 0.5

            if std_x > 0 and std_y > 0:
                corr = cov / (std_x * std_y)
            else:
                corr = 0.0

            # Also compute mean of attr when target=1 vs target=0 (effect size)
            pos_vals = [xs[i] for i in range(n) if ys[i] == 1]
            neg_vals = [xs[i] for i in range(n) if ys[i] == 0]
            mean_pos = sum(pos_vals) / len(pos_vals) if pos_vals else 0
            mean_neg = sum(neg_vals) / len(neg_vals) if neg_vals else 0

            results[target][attr] = {
                'correlation': corr,
                'n': n,
                'mean_when_goal': mean_pos,
                'mean_when_no_goal': mean_neg,
                'effect': mean_pos - mean_neg,
            }

    # Print results sorted by absolute correlation
    for target in targets:
        print(f"\n{'─' * 70}")
        print(f"TARGET: {target}")
        print(f"{'─' * 70}")
        sorted_attrs = sorted(results[target].items(),
                              key=lambda x: abs(x[1]['correlation']),
                              reverse=True)

        print(f"{'Attribute':<40s} {'Corr':>7s} {'N':>6s} {'AvgGoal':>8s} {'AvgNoGoal':>10s} {'Effect':>8s}")
        print(f"{'─' * 40} {'─' * 7} {'─' * 6} {'─' * 8} {'─' * 10} {'─' * 8}")
        for attr, vals in sorted_attrs[:30]:
            print(f"{attr:<40s} {vals['correlation']:>7.4f} {vals['n']:>6d} "
                  f"{vals['mean_when_goal']:>8.4f} {vals['mean_when_no_goal']:>10.4f} "
                  f"{vals['effect']:>8.4f}")

    return results


def analyze_by_minute_range(rows):
    """Analyze which attributes are more predictive at different game phases."""
    print("\n" + "=" * 80)
    print("ANALYSIS BY GAME PHASE")
    print("=" * 80)

    phases = [
        ("First Half (5-45)", 5, 45),
        ("Early 2nd Half (46-65)", 46, 65),
        ("Late Game (66-85)", 66, 85),
    ]

    target = 'goal_next_10m'
    key_attrs = [
        'xg_velocity_l_10m', 'xg_velocity_v_10m',
        'pressure_index_l', 'pressure_index_v', 'pressure_asymmetry',
        'scoreline_tension', 'xg_frustration_total',
        'match_openness', 'xg_remaining',
        'momentum_dominance', 'xg_dominance',
        'implied_prob_o25', 'cs_entropy',
        'odds_drift_home_5m_pct', 'odds_drift_o25_5m_pct',
        'market_vs_xg_home',
        'opta_gap',
    ]

    for phase_name, min_from, min_to in phases:
        phase_rows = [r for r in rows if r.get('minute') and min_from <= r['minute'] <= min_to]
        print(f"\n  Phase: {phase_name} ({len(phase_rows)} rows)")
        print(f"  {'Attribute':<35s} {'Corr':>7s} {'N':>6s} {'Effect':>8s}")
        print(f"  {'─' * 35} {'─' * 7} {'─' * 6} {'─' * 8}")

        phase_corrs = []
        for attr in key_attrs:
            xs, ys = [], []
            for r in phase_rows:
                x = r.get(attr)
                y = r.get(target)
                if x is not None and y is not None:
                    try:
                        xs.append(float(x))
                        ys.append(float(y))
                    except:
                        continue

            if len(xs) < 30:
                continue

            n = len(xs)
            mean_x = sum(xs) / n
            mean_y = sum(ys) / n
            cov = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / n
            std_x = (sum((x - mean_x) ** 2 for x in xs) / n) ** 0.5
            std_y = (sum((y - mean_y) ** 2 for y in ys) / n) ** 0.5
            corr = cov / (std_x * std_y) if std_x > 0 and std_y > 0 else 0

            pos_vals = [xs[i] for i in range(n) if ys[i] == 1]
            neg_vals = [xs[i] for i in range(n) if ys[i] == 0]
            effect = (sum(pos_vals) / len(pos_vals) if pos_vals else 0) - \
                     (sum(neg_vals) / len(neg_vals) if neg_vals else 0)

            phase_corrs.append((attr, corr, n, effect))

        phase_corrs.sort(key=lambda x: abs(x[1]), reverse=True)
        for attr, corr, n, effect in phase_corrs:
            marker = " ***" if abs(corr) > 0.10 else " **" if abs(corr) > 0.05 else ""
            print(f"  {attr:<35s} {corr:>7.4f} {n:>6d} {effect:>8.4f}{marker}")


def analyze_strategy_enhancers(rows):
    """Find which synthetic attributes could enhance existing strategies."""
    print("\n" + "=" * 80)
    print("STRATEGY ENHANCEMENT ANALYSIS")
    print("=" * 80)

    # Simulate: for rows where draw at 0-0 and minute >= 30,
    # which synthetic attrs best predict "no goal in next 15 min" (draw holds)
    draw_00_rows = [r for r in rows
                    if r.get('score_label') == '0-0'
                    and r.get('minute', 0) >= 30
                    and r.get('goal_next_15m') is not None]

    print(f"\n  BACK DRAW 0-0 context: {len(draw_00_rows)} rows")
    if len(draw_00_rows) > 30:
        # For draw strategy, target is inverted: we want NO goal (goal_next_15m = 0)
        key_attrs = ['xg_frustration_total', 'scoreline_tension', 'match_openness',
                     'pressure_index_l', 'pressure_index_v', 'xg_remaining',
                     'cs_entropy', 'implied_prob_draw', 'xg_dominance',
                     'momentum_gap', 'opta_gap', 'delta_sot_l_5m', 'delta_sot_v_5m']
        print(f"  {'Attribute':<35s} {'Corr→Goal':>10s} {'N':>6s} {'Interpretation':>20s}")
        print(f"  {'─' * 35} {'─' * 10} {'─' * 6} {'─' * 20}")

        for attr in key_attrs:
            xs, ys = [], []
            for r in draw_00_rows:
                x = r.get(attr)
                y = r.get('goal_next_15m')
                if x is not None and y is not None:
                    try:
                        xs.append(float(x))
                        ys.append(float(y))
                    except:
                        continue
            if len(xs) < 20:
                continue
            n = len(xs)
            mean_x = sum(xs) / n
            mean_y = sum(ys) / n
            cov = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n)) / n
            std_x = (sum((x - mean_x) ** 2 for x in xs) / n) ** 0.5
            std_y = (sum((y - mean_y) ** 2 for y in ys) / n) ** 0.5
            corr = cov / (std_x * std_y) if std_x > 0 and std_y > 0 else 0
            interp = "→ avoid bet" if corr > 0.05 else "→ good filter" if corr < -0.05 else "→ neutral"
            print(f"  {attr:<35s} {corr:>10.4f} {n:>6d} {interp:>20s}")

    # For xG underperformance: when xg_excess >= 0.5 and team losing
    print(f"\n  XG UNDERPERFORMANCE context:")
    xg_rows = [r for r in rows
                if r.get('minute', 0) >= 15
                and r.get('goal_next_10m') is not None]

    # Check: high xg_frustration + other attrs → goal coming?
    high_frust = [r for r in xg_rows
                  if r.get('xg_frustration_l') is not None
                  and r['xg_frustration_l'] > 0.3]
    if high_frust:
        goal_rate = sum(1 for r in high_frust if r.get('goal_next_10m') == 1) / len(high_frust)
        print(f"  High xG frustration (>0.3) local: {len(high_frust)} rows, goal rate next 10m: {goal_rate:.1%}")

    high_frust_v = [r for r in xg_rows
                    if r.get('xg_frustration_v') is not None
                    and r['xg_frustration_v'] > 0.3]
    if high_frust_v:
        goal_rate_v = sum(1 for r in high_frust_v if r.get('goal_next_10m') == 1) / len(high_frust_v)
        print(f"  High xG frustration (>0.3) away:  {len(high_frust_v)} rows, goal rate next 10m: {goal_rate_v:.1%}")

    # Pressure index analysis
    print(f"\n  PRESSURE INDEX analysis:")
    for threshold in [0.3, 0.5, 0.8, 1.0]:
        high_press = [r for r in rows
                      if r.get('pressure_index_l') is not None
                      and r['pressure_index_l'] > threshold
                      and r.get('goal_next_10m') is not None]
        if len(high_press) > 20:
            gr = sum(1 for r in high_press if r['goal_next_10m'] == 1) / len(high_press)
            print(f"  Pressure index > {threshold}: {len(high_press)} rows, goal rate 10m: {gr:.1%}")

    # Scoreline tension
    print(f"\n  SCORELINE TENSION analysis:")
    for threshold in [1.0, 2.0, 3.0, 4.0]:
        high_tension = [r for r in rows
                        if r.get('scoreline_tension') is not None
                        and r['scoreline_tension'] > threshold
                        and r.get('goal_next_10m') is not None]
        if len(high_tension) > 20:
            gr = sum(1 for r in high_tension if r['goal_next_10m'] == 1) / len(high_tension)
            print(f"  Tension > {threshold}: {len(high_tension)} rows, goal rate 10m: {gr:.1%}")


def generate_report(correlations, rows):
    """Generate a summary report with actionable findings."""
    report = []
    report.append("=" * 80)
    report.append("SYNTHETIC ATTRIBUTES - EXPLORATION REPORT")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    report.append(f"Total data points: {len(rows)}")

    # Count unique matches
    matches = set(r['match'] for r in rows)
    report.append(f"Unique matches: {len(matches)}")
    report.append("=" * 80)

    # Base goal rates
    for target in ['goal_next_5m', 'goal_next_10m', 'goal_next_15m']:
        valid = [r for r in rows if r.get(target) is not None]
        if valid:
            rate = sum(1 for r in valid if r[target] == 1) / len(valid)
            report.append(f"\nBase rate {target}: {rate:.1%} ({len(valid)} obs)")

    # Top 10 most predictive attributes for goal_next_10m
    if 'goal_next_10m' in correlations:
        report.append(f"\n{'─' * 60}")
        report.append("TOP 15 MOST PREDICTIVE ATTRIBUTES (goal in next 10 min)")
        report.append(f"{'─' * 60}")
        sorted_attrs = sorted(correlations['goal_next_10m'].items(),
                              key=lambda x: abs(x[1]['correlation']),
                              reverse=True)
        for i, (attr, vals) in enumerate(sorted_attrs[:15]):
            report.append(f"  {i+1:2d}. {attr:<38s} r={vals['correlation']:+.4f}  "
                         f"(goal={vals['mean_when_goal']:.3f}, no_goal={vals['mean_when_no_goal']:.3f})")

    # Attributes with strongest POSITIVE correlation (= when high, more goals)
    report.append(f"\n{'─' * 60}")
    report.append("ATTRIBUTES THAT PREDICT MORE GOALS (positive correlation)")
    report.append(f"{'─' * 60}")
    if 'goal_next_10m' in correlations:
        pos_sorted = sorted(correlations['goal_next_10m'].items(),
                           key=lambda x: x[1]['correlation'],
                           reverse=True)
        for attr, vals in pos_sorted[:10]:
            if vals['correlation'] > 0.02:
                report.append(f"  {attr:<38s} r={vals['correlation']:+.4f}")

    # Attributes with strongest NEGATIVE correlation (= when high, fewer goals)
    report.append(f"\n{'─' * 60}")
    report.append("ATTRIBUTES THAT PREDICT FEWER GOALS (negative correlation)")
    report.append(f"{'─' * 60}")
    if 'goal_next_10m' in correlations:
        neg_sorted = sorted(correlations['goal_next_10m'].items(),
                           key=lambda x: x[1]['correlation'])
        for attr, vals in neg_sorted[:10]:
            if vals['correlation'] < -0.02:
                report.append(f"  {attr:<38s} r={vals['correlation']:+.4f}")

    report_text = "\n".join(report)
    report_path = os.path.join(OUTPUT_DIR, "exploration_report.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"\nReport saved: {report_path}")
    print(report_text)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print("=" * 80)
    print("SYNTHETIC ATTRIBUTES EXPLORATION")
    print(f"Data dir: {DATA_DIR}")
    print("=" * 80)

    # Step 1: Process all matches
    enriched_rows, summaries = process_all_matches()

    # Step 2: Save enriched data
    save_enriched_csv(enriched_rows, "enriched_all_rows.csv")
    save_enriched_csv(summaries, "match_summaries.csv")

    # Step 3: Correlation analysis
    correlations = analyze_correlations(enriched_rows)

    # Step 4: Phase analysis
    analyze_by_minute_range(enriched_rows)

    # Step 5: Strategy enhancement analysis
    analyze_strategy_enhancers(enriched_rows)

    # Step 6: Generate report
    generate_report(correlations, enriched_rows)

    # Save correlations as JSON for further use
    json_path = os.path.join(OUTPUT_DIR, "correlations.json")
    # Convert to serializable format
    corr_serializable = {}
    for target, attrs in correlations.items():
        corr_serializable[target] = {}
        for attr, vals in attrs.items():
            corr_serializable[target][attr] = {k: round(v, 6) for k, v in vals.items()}
    with open(json_path, 'w') as f:
        json.dump(corr_serializable, f, indent=2)
    print(f"Correlations JSON: {json_path}")

    print("\n✓ Done! Check the synthetic_analysis/ folder for results.")