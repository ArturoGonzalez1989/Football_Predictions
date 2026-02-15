"""
V3 Strategy Filter Analysis for "Back Draw 0-0 at minute 30+"
=============================================================
Analyzes match CSVs to find new statistical filters that improve
the draw-backing strategy when score is 0-0 at minute 30+.

V1: Bet draw when 0-0 at min 30+ (any stats)
V2: V1 + xG_total < 0.5 + possession_diff < 20% + total_shots < 8
V3: Find NEW filters from all available stats
"""

import pandas as pd
import numpy as np
import glob
import os
import warnings
from collections import defaultdict

warnings.filterwarnings('ignore')

DATA_DIR = r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data"

# ============================================================
# STEP 1: Load all match CSVs and extract relevant data
# ============================================================

def safe_float(val):
    """Convert value to float, return NaN if not possible."""
    try:
        v = float(val)
        return v if not np.isinf(v) else np.nan
    except (ValueError, TypeError):
        return np.nan

def extract_match_data(filepath):
    """
    Extract minute-30 stats and final score from a match CSV.
    Returns dict with all stats or None if match doesn't qualify.
    """
    try:
        df = pd.read_csv(filepath, on_bad_lines='skip', encoding='utf-8')
    except Exception as e:
        return None

    # Need in-play data
    if 'estado_partido' not in df.columns or 'minuto' not in df.columns:
        return None

    # Check if match is finished
    has_final = (df['estado_partido'] == 'finalizado').any()
    if not has_final:
        return None

    # Get match name from tab_id or filename
    match_name = os.path.basename(filepath).replace('partido_', '').replace('.csv', '')
    match_name = match_name.rsplit('-apuestas-', 1)[0] if '-apuestas-' in match_name else match_name

    # Get final score from last row with estado=finalizado or the very last row
    final_rows = df[df['estado_partido'] == 'finalizado']
    if len(final_rows) > 0:
        last_row = final_rows.iloc[-1]
    else:
        last_row = df.iloc[-1]

    final_goles_local = safe_float(last_row.get('goles_local', np.nan))
    final_goles_visitante = safe_float(last_row.get('goles_visitante', np.nan))

    if np.isnan(final_goles_local) or np.isnan(final_goles_visitante):
        return None

    # Find rows where match is in play
    in_play = df[df['estado_partido'] == 'en_juego'].copy()
    if len(in_play) == 0:
        return None

    # Convert minuto to numeric
    in_play['minuto'] = pd.to_numeric(in_play['minuto'], errors='coerce')
    in_play = in_play.dropna(subset=['minuto'])

    if len(in_play) == 0:
        return None

    # Find closest row to minute 30 (>= 30)
    at_30 = in_play[in_play['minuto'] >= 30]
    if len(at_30) == 0:
        return None

    row30 = at_30.iloc[0]  # First row at or after minute 30

    # Check if score is 0-0 at minute 30
    g_local_30 = safe_float(row30.get('goles_local', np.nan))
    g_visit_30 = safe_float(row30.get('goles_visitante', np.nan))

    # Build result dict with ALL stats
    result = {
        'match_name': match_name,
        'minuto': safe_float(row30.get('minuto', np.nan)),
        'goles_local_30': g_local_30,
        'goles_visitante_30': g_visit_30,
        'is_00_at_30': (g_local_30 == 0 and g_visit_30 == 0),
        'final_goles_local': int(final_goles_local),
        'final_goles_visitante': int(final_goles_visitante),
        'final_score': f"{int(final_goles_local)}-{int(final_goles_visitante)}",
        'is_draw': (final_goles_local == final_goles_visitante),

        # Odds at minute 30
        'back_draw': safe_float(row30.get('back_draw', np.nan)),
        'back_home': safe_float(row30.get('back_home', np.nan)),
        'back_away': safe_float(row30.get('back_away', np.nan)),
        'back_over05': safe_float(row30.get('back_over05', np.nan)),
        'back_under05': safe_float(row30.get('back_under05', np.nan)),
        'back_over15': safe_float(row30.get('back_over15', np.nan)),
        'back_under15': safe_float(row30.get('back_under15', np.nan)),
        'back_over25': safe_float(row30.get('back_over25', np.nan)),
        'back_under25': safe_float(row30.get('back_under25', np.nan)),

        # xG
        'xg_local': safe_float(row30.get('xg_local', np.nan)),
        'xg_visitante': safe_float(row30.get('xg_visitante', np.nan)),

        # Possession
        'posesion_local': safe_float(row30.get('posesion_local', np.nan)),
        'posesion_visitante': safe_float(row30.get('posesion_visitante', np.nan)),

        # Shots
        'tiros_local': safe_float(row30.get('tiros_local', np.nan)),
        'tiros_visitante': safe_float(row30.get('tiros_visitante', np.nan)),
        'tiros_puerta_local': safe_float(row30.get('tiros_puerta_local', np.nan)),
        'tiros_puerta_visitante': safe_float(row30.get('tiros_puerta_visitante', np.nan)),

        # Dangerous attacks
        'dangerous_attacks_local': safe_float(row30.get('dangerous_attacks_local', np.nan)),
        'dangerous_attacks_visitante': safe_float(row30.get('dangerous_attacks_visitante', np.nan)),

        # Corners
        'corners_local': safe_float(row30.get('corners_local', np.nan)),
        'corners_visitante': safe_float(row30.get('corners_visitante', np.nan)),

        # Big chances
        'big_chances_local': safe_float(row30.get('big_chances_local', np.nan)),
        'big_chances_visitante': safe_float(row30.get('big_chances_visitante', np.nan)),

        # Momentum
        'momentum_local': safe_float(row30.get('momentum_local', np.nan)),
        'momentum_visitante': safe_float(row30.get('momentum_visitante', np.nan)),

        # Attacks
        'attacks_local': safe_float(row30.get('attacks_local', np.nan)),
        'attacks_visitante': safe_float(row30.get('attacks_visitante', np.nan)),

        # Touches in box
        'touches_box_local': safe_float(row30.get('touches_box_local', np.nan)),
        'touches_box_visitante': safe_float(row30.get('touches_box_visitante', np.nan)),

        # Blocked shots
        'blocked_shots_local': safe_float(row30.get('blocked_shots_local', np.nan)),
        'blocked_shots_visitante': safe_float(row30.get('blocked_shots_visitante', np.nan)),

        # Saves
        'saves_local': safe_float(row30.get('saves_local', np.nan)),
        'saves_visitante': safe_float(row30.get('saves_visitante', np.nan)),

        # Fouls
        'fouls_conceded_local': safe_float(row30.get('fouls_conceded_local', np.nan)),
        'fouls_conceded_visitante': safe_float(row30.get('fouls_conceded_visitante', np.nan)),

        # Shots off target
        'shots_off_target_local': safe_float(row30.get('shots_off_target_local', np.nan)),
        'shots_off_target_visitante': safe_float(row30.get('shots_off_target_visitante', np.nan)),

        # Clearances
        'clearance_local': safe_float(row30.get('clearance_local', np.nan)),
        'clearance_visitante': safe_float(row30.get('clearance_visitante', np.nan)),

        # Interceptions
        'interceptions_local': safe_float(row30.get('interceptions_local', np.nan)),
        'interceptions_visitante': safe_float(row30.get('interceptions_visitante', np.nan)),

        # Pass success
        'pass_success_pct_local': safe_float(row30.get('pass_success_pct_local', np.nan)),
        'pass_success_pct_visitante': safe_float(row30.get('pass_success_pct_visitante', np.nan)),

        # Goal kicks
        'goal_kicks_local': safe_float(row30.get('goal_kicks_local', np.nan)),
        'goal_kicks_visitante': safe_float(row30.get('goal_kicks_visitante', np.nan)),

        # Tackles
        'tackles_local': safe_float(row30.get('tackles_local', np.nan)),
        'tackles_visitante': safe_float(row30.get('tackles_visitante', np.nan)),
    }

    return result


def compute_derived_stats(matches):
    """Add computed/derived stats to each match dict."""
    for m in matches:
        # xG total
        m['xg_total'] = safe_sum(m.get('xg_local'), m.get('xg_visitante'))

        # Possession difference
        p_l = m.get('posesion_local', np.nan)
        p_v = m.get('posesion_visitante', np.nan)
        if not np.isnan(p_l) and not np.isnan(p_v):
            m['possession_diff'] = abs(p_l - p_v)
        else:
            m['possession_diff'] = np.nan

        # Total shots
        m['total_shots'] = safe_sum(m.get('tiros_local'), m.get('tiros_visitante'))

        # Total shots on target
        m['total_shots_on_target'] = safe_sum(m.get('tiros_puerta_local'), m.get('tiros_puerta_visitante'))

        # Total dangerous attacks
        m['dangerous_attacks_total'] = safe_sum(m.get('dangerous_attacks_local'), m.get('dangerous_attacks_visitante'))
        # Dangerous attacks difference
        da_l = m.get('dangerous_attacks_local', np.nan)
        da_v = m.get('dangerous_attacks_visitante', np.nan)
        if not np.isnan(da_l) and not np.isnan(da_v):
            m['dangerous_attacks_diff'] = abs(da_l - da_v)
        else:
            m['dangerous_attacks_diff'] = np.nan

        # Total corners
        m['corners_total'] = safe_sum(m.get('corners_local'), m.get('corners_visitante'))
        # Corners difference
        c_l = m.get('corners_local', np.nan)
        c_v = m.get('corners_visitante', np.nan)
        if not np.isnan(c_l) and not np.isnan(c_v):
            m['corners_diff'] = abs(c_l - c_v)
        else:
            m['corners_diff'] = np.nan

        # Total big chances
        m['big_chances_total'] = safe_sum(m.get('big_chances_local'), m.get('big_chances_visitante'))

        # Momentum difference
        mom_l = m.get('momentum_local', np.nan)
        mom_v = m.get('momentum_visitante', np.nan)
        if not np.isnan(mom_l) and not np.isnan(mom_v) and (mom_l + mom_v) > 0:
            m['momentum_ratio'] = max(mom_l, mom_v) / (mom_l + mom_v)
            m['momentum_diff'] = abs(mom_l - mom_v)
        else:
            m['momentum_ratio'] = np.nan
            m['momentum_diff'] = np.nan

        # Total attacks
        m['attacks_total'] = safe_sum(m.get('attacks_local'), m.get('attacks_visitante'))

        # Total touches in box
        m['touches_box_total'] = safe_sum(m.get('touches_box_local'), m.get('touches_box_visitante'))

        # Total blocked shots
        m['blocked_shots_total'] = safe_sum(m.get('blocked_shots_local'), m.get('blocked_shots_visitante'))

        # Total saves
        m['saves_total'] = safe_sum(m.get('saves_local'), m.get('saves_visitante'))

        # Total fouls
        m['fouls_total'] = safe_sum(m.get('fouls_conceded_local'), m.get('fouls_conceded_visitante'))

        # Home/Away equilibrium ratio
        bh = m.get('back_home', np.nan)
        ba = m.get('back_away', np.nan)
        if not np.isnan(bh) and not np.isnan(ba) and max(bh, ba) > 0:
            m['equilibrium_ratio'] = min(bh, ba) / max(bh, ba)
        else:
            m['equilibrium_ratio'] = np.nan

        # Danger score = dangerous_attacks_total + big_chances_total + touches_box_total
        vals = [m.get('dangerous_attacks_total', np.nan),
                m.get('big_chances_total', np.nan),
                m.get('touches_box_total', np.nan)]
        non_nan = [v for v in vals if not np.isnan(v)]
        m['danger_score'] = sum(non_nan) if non_nan else np.nan

        # V2 filter check
        xg_ok = not np.isnan(m['xg_total']) and m['xg_total'] < 0.5
        poss_ok = not np.isnan(m['possession_diff']) and m['possession_diff'] < 20
        shots_ok = not np.isnan(m['total_shots']) and m['total_shots'] < 8
        m['passes_v2'] = xg_ok and poss_ok and shots_ok

    return matches


def safe_sum(a, b):
    """Sum two values, treating NaN as missing. Returns NaN if both are NaN."""
    a_nan = a is None or (isinstance(a, float) and np.isnan(a))
    b_nan = b is None or (isinstance(b, float) and np.isnan(b))
    if a_nan and b_nan:
        return np.nan
    return (0 if a_nan else a) + (0 if b_nan else b)


def analyze_filter(matches_00, filter_name, condition_fn, complement_name=None):
    """
    Analyze a binary filter on 0-0 matches.
    condition_fn: takes a match dict, returns True/False/None (None=skip/missing data)
    Returns dict with stats.
    """
    passes = [m for m in matches_00 if condition_fn(m) is True]
    fails = [m for m in matches_00 if condition_fn(m) is False]

    n_pass = len(passes)
    n_fail = len(fails)

    wins_pass = sum(1 for m in passes if m['is_draw'])
    wins_fail = sum(1 for m in fails if m['is_draw'])

    wr_pass = (wins_pass / n_pass * 100) if n_pass > 0 else 0
    wr_fail = (wins_fail / n_fail * 100) if n_fail > 0 else 0

    return {
        'filter_name': filter_name,
        'complement_name': complement_name or f"NOT {filter_name}",
        'n_pass': n_pass,
        'wins_pass': wins_pass,
        'wr_pass': wr_pass,
        'n_fail': n_fail,
        'wins_fail': wins_fail,
        'wr_fail': wr_fail,
    }


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def main():
    print_section("V3 STRATEGY FILTER ANALYSIS")
    print("Strategy: Back Draw when score is 0-0 at minute 30+")
    print("Goal: Find new statistical filters to improve win rate")

    # ============================================================
    # STEP 1: Load all match files
    # ============================================================
    print_section("STEP 1: Loading Match Data")

    csv_files = glob.glob(os.path.join(DATA_DIR, "partido_*.csv"))
    print(f"Found {len(csv_files)} CSV files")

    all_matches = []
    errors = 0
    no_final = 0
    no_inplay = 0

    for filepath in csv_files:
        result = extract_match_data(filepath)
        if result is None:
            errors += 1
        else:
            all_matches.append(result)

    print(f"Successfully parsed: {len(all_matches)} matches")
    print(f"Skipped (no final/in-play data): {errors}")

    # Compute derived stats
    all_matches = compute_derived_stats(all_matches)

    # Filter to 0-0 at minute 30
    matches_00 = [m for m in all_matches if m['is_00_at_30']]
    matches_not_00 = [m for m in all_matches if not m['is_00_at_30']]

    print(f"\nTotal finished matches with in-play data: {len(all_matches)}")
    print(f"Matches 0-0 at minute 30: {len(matches_00)}")
    print(f"Matches NOT 0-0 at minute 30: {len(matches_not_00)}")

    if len(matches_00) == 0:
        print("\nERROR: No matches found with 0-0 at minute 30. Cannot analyze.")
        return

    # ============================================================
    # STEP 2: V1 Base Rate
    # ============================================================
    print_section("STEP 2: V1 BASE RATE (0-0 at min 30, bet draw)")

    total_00 = len(matches_00)
    draws_00 = sum(1 for m in matches_00 if m['is_draw'])
    v1_wr = draws_00 / total_00 * 100

    print(f"V1: {draws_00} draws out of {total_00} matches = {v1_wr:.1f}% win rate")

    # Draw score breakdown
    from collections import Counter
    final_scores = Counter(m['final_score'] for m in matches_00)
    print("\nFinal score distribution for 0-0 at min 30 matches:")
    for score, count in sorted(final_scores.items(), key=lambda x: -x[1]):
        pct = count / total_00 * 100
        draw_marker = " <-- DRAW" if score.split('-')[0] == score.split('-')[1] else ""
        print(f"  {score}: {count} ({pct:.1f}%){draw_marker}")

    # ============================================================
    # STEP 3: V2 Check
    # ============================================================
    print_section("STEP 3: V2 FILTER CHECK (xG<0.5 + poss_diff<20 + shots<8)")

    v2_matches = [m for m in matches_00 if m['passes_v2']]
    v2_draws = sum(1 for m in v2_matches if m['is_draw'])
    v2_wr = (v2_draws / len(v2_matches) * 100) if len(v2_matches) > 0 else 0

    print(f"V2: {v2_draws} draws out of {len(v2_matches)} matches = {v2_wr:.1f}% win rate")
    print(f"V2 improvement over V1: {v2_wr - v1_wr:+.1f}pp")

    # ============================================================
    # STEP 4: Comprehensive match table
    # ============================================================
    print_section("STEP 4: ALL 0-0 AT MIN 30 MATCHES - DETAILED STATS")

    # Sort by whether it's a draw (wins first)
    matches_00_sorted = sorted(matches_00, key=lambda m: (not m['is_draw'], m['match_name']))

    # Print header
    print(f"\n{'#':>3} {'Match':<40} {'Min':>3} {'Draw$':>6} {'O25$':>6} "
          f"{'xG_T':>6} {'Shot':>4} {'SoT':>3} {'P%D':>4} "
          f"{'DA_T':>4} {'Cor':>3} {'BC':>3} {'Atk':>4} "
          f"{'TBx':>4} {'Blk':>3} {'Sav':>3} {'MomD':>5} "
          f"{'EqR':>5} {'DngS':>4} {'Final':>5} {'Res':>4}")
    print("-" * 145)

    for i, m in enumerate(matches_00_sorted):
        def fmtv(v, w=5, d=1):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return "-".rjust(w)
            if d == 0:
                return f"{int(v)}".rjust(w)
            return f"{v:.{d}f}".rjust(w)

        name = m['match_name'][:38]
        print(f"{i+1:>3} {name:<40} "
              f"{m['minuto']:>3.0f} "
              f"{fmtv(m['back_draw'], 6)} "
              f"{fmtv(m['back_over25'], 6)} "
              f"{fmtv(m['xg_total'], 6, 2)} "
              f"{fmtv(m['total_shots'], 4, 0)} "
              f"{fmtv(m['total_shots_on_target'], 3, 0)} "
              f"{fmtv(m['possession_diff'], 4, 0)} "
              f"{fmtv(m['dangerous_attacks_total'], 4, 0)} "
              f"{fmtv(m['corners_total'], 3, 0)} "
              f"{fmtv(m['big_chances_total'], 3, 0)} "
              f"{fmtv(m['attacks_total'], 4, 0)} "
              f"{fmtv(m['touches_box_total'], 4, 0)} "
              f"{fmtv(m['blocked_shots_total'], 3, 0)} "
              f"{fmtv(m['saves_total'], 3, 0)} "
              f"{fmtv(m['momentum_diff'], 5, 0)} "
              f"{fmtv(m['equilibrium_ratio'], 5, 2)} "
              f"{fmtv(m['danger_score'], 4, 0)} "
              f" {m['final_score']:>5} "
              f"{'WIN' if m['is_draw'] else 'LOSS':>4}")

    # ============================================================
    # STEP 5: Individual Filter Analysis
    # ============================================================
    print_section("STEP 5: INDIVIDUAL FILTER ANALYSIS")
    print(f"\nV1 Base Rate: {draws_00}/{total_00} = {v1_wr:.1f}%")
    print(f"Any filter with win rate > {v1_wr:.1f}% is an improvement.\n")

    filters_results = []

    # --- Dangerous Attacks Total ---
    # Find median
    da_vals = [m['dangerous_attacks_total'] for m in matches_00 if not np.isnan(m.get('dangerous_attacks_total', np.nan))]
    if da_vals:
        da_median = np.median(da_vals)
        for threshold in [da_median, 15, 20, 25, 30]:
            r = analyze_filter(matches_00, f"DA_total <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('dangerous_attacks_total', np.nan)) else m['dangerous_attacks_total'] <= t,
                             f"DA_total > {threshold:.0f}")
            filters_results.append(r)

    # --- Corners Total ---
    c_vals = [m['corners_total'] for m in matches_00 if not np.isnan(m.get('corners_total', np.nan))]
    if c_vals:
        c_median = np.median(c_vals)
        for threshold in [c_median, 2, 3, 4, 5]:
            r = analyze_filter(matches_00, f"Corners_total <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('corners_total', np.nan)) else m['corners_total'] <= t,
                             f"Corners_total > {threshold:.0f}")
            filters_results.append(r)

    # --- Corners Difference ---
    cd_vals = [m['corners_diff'] for m in matches_00 if not np.isnan(m.get('corners_diff', np.nan))]
    if cd_vals:
        for threshold in [1, 2, 3]:
            r = analyze_filter(matches_00, f"Corners_diff <= {threshold}",
                             lambda m, t=threshold: None if np.isnan(m.get('corners_diff', np.nan)) else m['corners_diff'] <= t,
                             f"Corners_diff > {threshold}")
            filters_results.append(r)

    # --- Big Chances Total ---
    bc_vals = [m['big_chances_total'] for m in matches_00 if not np.isnan(m.get('big_chances_total', np.nan))]
    if bc_vals:
        r = analyze_filter(matches_00, "Big_chances = 0",
                         lambda m: None if np.isnan(m.get('big_chances_total', np.nan)) else m['big_chances_total'] == 0,
                         "Big_chances >= 1")
        filters_results.append(r)
        r = analyze_filter(matches_00, "Big_chances <= 1",
                         lambda m: None if np.isnan(m.get('big_chances_total', np.nan)) else m['big_chances_total'] <= 1,
                         "Big_chances > 1")
        filters_results.append(r)

    # --- Momentum Difference ---
    md_vals = [m['momentum_diff'] for m in matches_00 if not np.isnan(m.get('momentum_diff', np.nan))]
    if md_vals:
        md_median = np.median(md_vals)
        for threshold in [md_median, 30, 50, 75, 100]:
            r = analyze_filter(matches_00, f"Momentum_diff <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('momentum_diff', np.nan)) else m['momentum_diff'] <= t,
                             f"Momentum_diff > {threshold:.0f}")
            filters_results.append(r)

    # --- Momentum Ratio (balanced = closer to 0.5) ---
    mr_vals = [m['momentum_ratio'] for m in matches_00 if not np.isnan(m.get('momentum_ratio', np.nan))]
    if mr_vals:
        for threshold in [0.55, 0.60, 0.65]:
            r = analyze_filter(matches_00, f"Momentum_ratio <= {threshold:.2f} (balanced)",
                             lambda m, t=threshold: None if np.isnan(m.get('momentum_ratio', np.nan)) else m['momentum_ratio'] <= t,
                             f"Momentum_ratio > {threshold:.2f} (one-sided)")
            filters_results.append(r)

    # --- Attacks Total ---
    at_vals = [m['attacks_total'] for m in matches_00 if not np.isnan(m.get('attacks_total', np.nan))]
    if at_vals:
        at_median = np.median(at_vals)
        for threshold in [at_median, 40, 50, 60]:
            r = analyze_filter(matches_00, f"Attacks_total <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('attacks_total', np.nan)) else m['attacks_total'] <= t,
                             f"Attacks_total > {threshold:.0f}")
            filters_results.append(r)

    # --- Touches in Box Total ---
    tb_vals = [m['touches_box_total'] for m in matches_00 if not np.isnan(m.get('touches_box_total', np.nan))]
    if tb_vals:
        tb_median = np.median(tb_vals)
        for threshold in [tb_median, 8, 10, 12, 15]:
            r = analyze_filter(matches_00, f"Touches_box_total <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('touches_box_total', np.nan)) else m['touches_box_total'] <= t,
                             f"Touches_box_total > {threshold:.0f}")
            filters_results.append(r)

    # --- Blocked Shots Total ---
    bs_vals = [m['blocked_shots_total'] for m in matches_00 if not np.isnan(m.get('blocked_shots_total', np.nan))]
    if bs_vals:
        bs_median = np.median(bs_vals)
        for threshold in [bs_median, 1, 2, 3]:
            r = analyze_filter(matches_00, f"Blocked_shots_total <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('blocked_shots_total', np.nan)) else m['blocked_shots_total'] <= t,
                             f"Blocked_shots_total > {threshold:.0f}")
            filters_results.append(r)

    # --- Saves Total ---
    sv_vals = [m['saves_total'] for m in matches_00 if not np.isnan(m.get('saves_total', np.nan))]
    if sv_vals:
        sv_median = np.median(sv_vals)
        for threshold in [sv_median, 1, 2, 3]:
            r = analyze_filter(matches_00, f"Saves_total <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('saves_total', np.nan)) else m['saves_total'] <= t,
                             f"Saves_total > {threshold:.0f}")
            filters_results.append(r)

    # --- Back Over 2.5 odds ---
    o25_vals = [m['back_over25'] for m in matches_00 if not np.isnan(m.get('back_over25', np.nan))]
    if o25_vals:
        o25_median = np.median(o25_vals)
        for threshold in [o25_median, 2.5, 3.0, 3.5, 4.0]:
            r = analyze_filter(matches_00, f"Over25_odds >= {threshold:.1f} (market says few goals)",
                             lambda m, t=threshold: None if np.isnan(m.get('back_over25', np.nan)) else m['back_over25'] >= t,
                             f"Over25_odds < {threshold:.1f}")
            filters_results.append(r)

    # --- Back Draw odds ---
    bd_vals = [m['back_draw'] for m in matches_00 if not np.isnan(m.get('back_draw', np.nan))]
    if bd_vals:
        bd_median = np.median(bd_vals)
        for lo, hi in [(1.5, 2.5), (2.0, 3.0), (2.5, 3.5), (3.0, 4.0), (1.5, 3.0)]:
            r = analyze_filter(matches_00, f"Draw_odds {lo:.1f}-{hi:.1f}",
                             lambda m, l=lo, h=hi: None if np.isnan(m.get('back_draw', np.nan)) else l <= m['back_draw'] <= h,
                             f"Draw_odds outside {lo:.1f}-{hi:.1f}")
            filters_results.append(r)

    # --- Equilibrium Ratio ---
    eq_vals = [m['equilibrium_ratio'] for m in matches_00 if not np.isnan(m.get('equilibrium_ratio', np.nan))]
    if eq_vals:
        for threshold in [0.5, 0.6, 0.7, 0.8]:
            r = analyze_filter(matches_00, f"Equilibrium_ratio >= {threshold:.1f} (balanced teams)",
                             lambda m, t=threshold: None if np.isnan(m.get('equilibrium_ratio', np.nan)) else m['equilibrium_ratio'] >= t,
                             f"Equilibrium_ratio < {threshold:.1f} (unbalanced)")
            filters_results.append(r)

    # --- Danger Score ---
    ds_vals = [m['danger_score'] for m in matches_00 if not np.isnan(m.get('danger_score', np.nan))]
    if ds_vals:
        ds_median = np.median(ds_vals)
        for threshold in [ds_median, 20, 30, 40, 50]:
            r = analyze_filter(matches_00, f"Danger_score <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('danger_score', np.nan)) else m['danger_score'] <= t,
                             f"Danger_score > {threshold:.0f}")
            filters_results.append(r)

    # --- Total shots on target ---
    sot_vals = [m['total_shots_on_target'] for m in matches_00 if not np.isnan(m.get('total_shots_on_target', np.nan))]
    if sot_vals:
        for threshold in [1, 2, 3, 4]:
            r = analyze_filter(matches_00, f"Shots_on_target_total <= {threshold}",
                             lambda m, t=threshold: None if np.isnan(m.get('total_shots_on_target', np.nan)) else m['total_shots_on_target'] <= t,
                             f"Shots_on_target_total > {threshold}")
            filters_results.append(r)

    # --- Fouls total ---
    f_vals = [m['fouls_total'] for m in matches_00 if not np.isnan(m.get('fouls_total', np.nan))]
    if f_vals:
        f_median = np.median(f_vals)
        for threshold in [f_median, 8, 10, 12]:
            r = analyze_filter(matches_00, f"Fouls_total <= {threshold:.0f}",
                             lambda m, t=threshold: None if np.isnan(m.get('fouls_total', np.nan)) else m['fouls_total'] <= t,
                             f"Fouls_total > {threshold:.0f}")
            filters_results.append(r)

    # --- xG total (different thresholds) ---
    xg_vals = [m['xg_total'] for m in matches_00 if not np.isnan(m.get('xg_total', np.nan))]
    if xg_vals:
        for threshold in [0.2, 0.3, 0.5, 0.7, 1.0]:
            r = analyze_filter(matches_00, f"xG_total < {threshold}",
                             lambda m, t=threshold: None if np.isnan(m.get('xg_total', np.nan)) else m['xg_total'] < t,
                             f"xG_total >= {threshold}")
            filters_results.append(r)

    # --- Back Under 2.5 odds (low = market expects <2.5 goals) ---
    u25_vals = [m['back_under25'] for m in matches_00 if not np.isnan(m.get('back_under25', np.nan))]
    if u25_vals:
        for threshold in [1.3, 1.4, 1.5]:
            r = analyze_filter(matches_00, f"Under25_odds <= {threshold:.1f} (strong under signal)",
                             lambda m, t=threshold: None if np.isnan(m.get('back_under25', np.nan)) else m['back_under25'] <= t,
                             f"Under25_odds > {threshold:.1f}")
            filters_results.append(r)

    # Print all individual filter results
    print(f"\n{'Filter':<50} {'N':>4} {'W':>4} {'WR%':>6} {'|':>2} {'N_opp':>5} {'W_opp':>5} {'WR%_opp':>7} {'|':>2} {'Delta':>6}")
    print("-" * 110)

    # Sort by win rate (descending), then by N (descending)
    filters_results.sort(key=lambda x: (-x['wr_pass'], -x['n_pass']))

    for r in filters_results:
        delta = r['wr_pass'] - v1_wr
        marker = "+++" if delta > 10 and r['n_pass'] >= 5 else "++" if delta > 5 and r['n_pass'] >= 5 else "+" if delta > 0 and r['n_pass'] >= 3 else ""
        print(f"{r['filter_name']:<50} {r['n_pass']:>4} {r['wins_pass']:>4} {r['wr_pass']:>5.1f}% {'|':>2} "
              f"{r['n_fail']:>5} {r['wins_fail']:>5} {r['wr_fail']:>6.1f}% {'|':>2} {delta:>+5.1f}pp {marker}")

    # ============================================================
    # STEP 6: Combination Analysis - Test promising V3 combinations
    # ============================================================
    print_section("STEP 6: V3 COMBINATION FILTER ANALYSIS")
    print(f"\nV1 Base: {v1_wr:.1f}% ({draws_00}/{total_00})")
    print(f"V2 Base: {v2_wr:.1f}% ({v2_draws}/{len(v2_matches)})")
    print()

    # Define promising individual filters based on the analysis
    # We'll try combinations of the most promising ones
    filter_fns = {
        'xG_total < 0.5': lambda m: not np.isnan(m.get('xg_total', np.nan)) and m['xg_total'] < 0.5,
        'xG_total < 0.3': lambda m: not np.isnan(m.get('xg_total', np.nan)) and m['xg_total'] < 0.3,
        'xG_total < 0.7': lambda m: not np.isnan(m.get('xg_total', np.nan)) and m['xg_total'] < 0.7,
        'poss_diff < 20': lambda m: not np.isnan(m.get('possession_diff', np.nan)) and m['possession_diff'] < 20,
        'poss_diff < 15': lambda m: not np.isnan(m.get('possession_diff', np.nan)) and m['possession_diff'] < 15,
        'total_shots < 8': lambda m: not np.isnan(m.get('total_shots', np.nan)) and m['total_shots'] < 8,
        'total_shots < 6': lambda m: not np.isnan(m.get('total_shots', np.nan)) and m['total_shots'] < 6,
        'corners_total <= 3': lambda m: not np.isnan(m.get('corners_total', np.nan)) and m['corners_total'] <= 3,
        'corners_total <= 4': lambda m: not np.isnan(m.get('corners_total', np.nan)) and m['corners_total'] <= 4,
        'corners_total <= 5': lambda m: not np.isnan(m.get('corners_total', np.nan)) and m['corners_total'] <= 5,
        'corners_diff <= 2': lambda m: not np.isnan(m.get('corners_diff', np.nan)) and m['corners_diff'] <= 2,
        'corners_diff <= 1': lambda m: not np.isnan(m.get('corners_diff', np.nan)) and m['corners_diff'] <= 1,
        'big_chances = 0': lambda m: not np.isnan(m.get('big_chances_total', np.nan)) and m['big_chances_total'] == 0,
        'big_chances <= 1': lambda m: not np.isnan(m.get('big_chances_total', np.nan)) and m['big_chances_total'] <= 1,
        'touches_box <= 8': lambda m: not np.isnan(m.get('touches_box_total', np.nan)) and m['touches_box_total'] <= 8,
        'touches_box <= 10': lambda m: not np.isnan(m.get('touches_box_total', np.nan)) and m['touches_box_total'] <= 10,
        'touches_box <= 12': lambda m: not np.isnan(m.get('touches_box_total', np.nan)) and m['touches_box_total'] <= 12,
        'momentum_diff <= 50': lambda m: not np.isnan(m.get('momentum_diff', np.nan)) and m['momentum_diff'] <= 50,
        'momentum_diff <= 75': lambda m: not np.isnan(m.get('momentum_diff', np.nan)) and m['momentum_diff'] <= 75,
        'equilibrium >= 0.6': lambda m: not np.isnan(m.get('equilibrium_ratio', np.nan)) and m['equilibrium_ratio'] >= 0.6,
        'equilibrium >= 0.7': lambda m: not np.isnan(m.get('equilibrium_ratio', np.nan)) and m['equilibrium_ratio'] >= 0.7,
        'over25 >= 3.0': lambda m: not np.isnan(m.get('back_over25', np.nan)) and m['back_over25'] >= 3.0,
        'over25 >= 3.5': lambda m: not np.isnan(m.get('back_over25', np.nan)) and m['back_over25'] >= 3.5,
        'over25 >= 4.0': lambda m: not np.isnan(m.get('back_over25', np.nan)) and m['back_over25'] >= 4.0,
        'danger_score <= 20': lambda m: not np.isnan(m.get('danger_score', np.nan)) and m['danger_score'] <= 20,
        'danger_score <= 30': lambda m: not np.isnan(m.get('danger_score', np.nan)) and m['danger_score'] <= 30,
        'shots_on_target <= 2': lambda m: not np.isnan(m.get('total_shots_on_target', np.nan)) and m['total_shots_on_target'] <= 2,
        'shots_on_target <= 3': lambda m: not np.isnan(m.get('total_shots_on_target', np.nan)) and m['total_shots_on_target'] <= 3,
        'saves_total <= 2': lambda m: not np.isnan(m.get('saves_total', np.nan)) and m['saves_total'] <= 2,
        'draw_odds 2.0-3.5': lambda m: not np.isnan(m.get('back_draw', np.nan)) and 2.0 <= m['back_draw'] <= 3.5,
        'DA_total <= 20': lambda m: not np.isnan(m.get('dangerous_attacks_total', np.nan)) and m['dangerous_attacks_total'] <= 20,
        'DA_total <= 25': lambda m: not np.isnan(m.get('dangerous_attacks_total', np.nan)) and m['dangerous_attacks_total'] <= 25,
        'DA_total <= 30': lambda m: not np.isnan(m.get('dangerous_attacks_total', np.nan)) and m['dangerous_attacks_total'] <= 30,
        'attacks_total <= 50': lambda m: not np.isnan(m.get('attacks_total', np.nan)) and m['attacks_total'] <= 50,
        'blocked_shots <= 2': lambda m: not np.isnan(m.get('blocked_shots_total', np.nan)) and m['blocked_shots_total'] <= 2,
    }

    # Test many combinations
    combo_results = []

    # V2-based combos (V2 + one more filter)
    v2_filters = ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8']
    new_filters = [k for k in filter_fns.keys() if k not in v2_filters]

    # V2 + 1 new filter
    for new_f in new_filters:
        combo_name = f"V2 + {new_f}"
        combo_fns = v2_filters + [new_f]
        matches_pass = [m for m in matches_00 if all(filter_fns[f](m) for f in combo_fns)]
        n = len(matches_pass)
        w = sum(1 for m in matches_pass if m['is_draw'])
        wr = (w / n * 100) if n > 0 else 0
        combo_results.append({'name': combo_name, 'n': n, 'w': w, 'wr': wr, 'filters': combo_fns})

    # Custom combos (not necessarily including V2)
    custom_combos = [
        # Lower xG threshold combos
        ['xG_total < 0.3', 'poss_diff < 20', 'total_shots < 8'],
        ['xG_total < 0.3', 'poss_diff < 20'],
        ['xG_total < 0.5', 'poss_diff < 15'],
        ['xG_total < 0.5', 'corners_total <= 3'],
        ['xG_total < 0.5', 'corners_total <= 4'],
        ['xG_total < 0.5', 'touches_box <= 10'],
        ['xG_total < 0.5', 'big_chances = 0'],
        ['xG_total < 0.5', 'danger_score <= 20'],
        ['xG_total < 0.5', 'danger_score <= 30'],
        ['xG_total < 0.5', 'over25 >= 3.0'],
        ['xG_total < 0.5', 'over25 >= 3.5'],
        ['xG_total < 0.5', 'equilibrium >= 0.6'],
        ['xG_total < 0.5', 'equilibrium >= 0.7'],
        ['xG_total < 0.5', 'shots_on_target <= 2'],
        ['xG_total < 0.5', 'momentum_diff <= 50'],
        ['xG_total < 0.5', 'DA_total <= 20'],

        # Three-filter combos without V2
        ['xG_total < 0.5', 'corners_total <= 4', 'touches_box <= 10'],
        ['xG_total < 0.5', 'corners_total <= 4', 'equilibrium >= 0.6'],
        ['xG_total < 0.5', 'danger_score <= 30', 'equilibrium >= 0.6'],
        ['xG_total < 0.5', 'over25 >= 3.0', 'equilibrium >= 0.6'],
        ['xG_total < 0.5', 'corners_total <= 4', 'over25 >= 3.0'],
        ['xG_total < 0.7', 'corners_total <= 4', 'touches_box <= 10'],
        ['xG_total < 0.7', 'danger_score <= 30', 'equilibrium >= 0.6'],
        ['xG_total < 0.7', 'over25 >= 3.5', 'corners_total <= 4'],
        ['corners_total <= 3', 'touches_box <= 10', 'equilibrium >= 0.6'],
        ['poss_diff < 15', 'corners_total <= 4', 'xG_total < 0.5'],
        ['shots_on_target <= 2', 'corners_total <= 3', 'xG_total < 0.5'],
        ['DA_total <= 20', 'xG_total < 0.5', 'corners_total <= 4'],
        ['total_shots < 6', 'corners_total <= 3', 'equilibrium >= 0.6'],
        ['big_chances = 0', 'xG_total < 0.5', 'corners_total <= 4'],
        ['big_chances = 0', 'touches_box <= 10', 'xG_total < 0.5'],

        # Four-filter combos
        ['xG_total < 0.5', 'poss_diff < 20', 'corners_total <= 4', 'touches_box <= 10'],
        ['xG_total < 0.5', 'poss_diff < 20', 'corners_total <= 4', 'equilibrium >= 0.6'],
        ['xG_total < 0.5', 'corners_total <= 4', 'equilibrium >= 0.6', 'over25 >= 3.0'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'corners_total <= 4'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'over25 >= 3.0'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'equilibrium >= 0.6'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'danger_score <= 30'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'touches_box <= 10'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'big_chances = 0'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'corners_total <= 3'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'shots_on_target <= 2'],
        ['xG_total < 0.5', 'poss_diff < 20', 'total_shots < 8', 'momentum_diff <= 50'],
    ]

    for combo_fns_list in custom_combos:
        # Check all filter names exist
        if all(f in filter_fns for f in combo_fns_list):
            combo_name = " + ".join(combo_fns_list)
            matches_pass = [m for m in matches_00 if all(filter_fns[f](m) for f in combo_fns_list)]
            n = len(matches_pass)
            w = sum(1 for m in matches_pass if m['is_draw'])
            wr = (w / n * 100) if n > 0 else 0
            combo_results.append({'name': combo_name, 'n': n, 'w': w, 'wr': wr, 'filters': combo_fns_list})

    # Sort by win rate (descending), but only show combos with N >= 3
    combo_results.sort(key=lambda x: (-x['wr'], -x['n']))

    print(f"\n{'Combination':<80} {'N':>4} {'W':>4} {'WR%':>6} {'vs V1':>7} {'vs V2':>7}")
    print("-" * 120)

    for r in combo_results:
        if r['n'] >= 2:  # Show combos with at least 2 matches
            d_v1 = r['wr'] - v1_wr
            d_v2 = r['wr'] - v2_wr
            marker = ""
            if r['wr'] >= 80 and r['n'] >= 3:
                marker = " ***"
            elif r['wr'] >= 60 and r['n'] >= 4:
                marker = " **"
            elif r['wr'] > v2_wr and r['n'] >= 3:
                marker = " *"
            print(f"{r['name']:<80} {r['n']:>4} {r['w']:>4} {r['wr']:>5.1f}% {d_v1:>+6.1f}pp {d_v2:>+6.1f}pp{marker}")

    # ============================================================
    # STEP 7: Top V3 Proposals
    # ============================================================
    print_section("STEP 7: TOP V3 PROPOSALS")

    # Filter to combos with reasonable N and good win rate
    candidates = [r for r in combo_results if r['n'] >= 3 and r['wr'] > v1_wr]
    candidates.sort(key=lambda x: (-x['wr'], -x['n']))

    print(f"\nSelection criteria: N >= 3, WR > V1 ({v1_wr:.1f}%)")
    print(f"Sorted by Win Rate descending\n")

    top_n = min(10, len(candidates))
    for i, r in enumerate(candidates[:top_n]):
        d_v1 = r['wr'] - v1_wr
        d_v2 = r['wr'] - v2_wr
        print(f"  #{i+1}: {r['name']}")
        print(f"       N={r['n']}, Wins={r['w']}, WR={r['wr']:.1f}%, vs V1: {d_v1:+.1f}pp, vs V2: {d_v2:+.1f}pp")
        print()

    # ============================================================
    # STEP 8: Statistical Summary & Recommendations
    # ============================================================
    print_section("STEP 8: SUMMARY & RECOMMENDATIONS")

    print(f"""
DATA SUMMARY:
  Total finished matches analyzed: {len(all_matches)}
  Matches 0-0 at minute 30: {total_00}
  Draws in 0-0 matches (V1): {draws_00} ({v1_wr:.1f}%)
  V2 filtered matches: {len(v2_matches)}, draws: {v2_draws} ({v2_wr:.1f}%)

KEY STATISTICS AT MINUTE 30 (for 0-0 matches):""")

    # Print stat distributions
    stat_names = [
        ('xg_total', 'xG Total'),
        ('total_shots', 'Total Shots'),
        ('total_shots_on_target', 'Shots on Target'),
        ('possession_diff', 'Possession Diff'),
        ('dangerous_attacks_total', 'Dangerous Atk Total'),
        ('corners_total', 'Corners Total'),
        ('corners_diff', 'Corners Diff'),
        ('big_chances_total', 'Big Chances Total'),
        ('touches_box_total', 'Touches Box Total'),
        ('momentum_diff', 'Momentum Diff'),
        ('attacks_total', 'Attacks Total'),
        ('blocked_shots_total', 'Blocked Shots Total'),
        ('saves_total', 'Saves Total'),
        ('fouls_total', 'Fouls Total'),
        ('danger_score', 'Danger Score'),
        ('equilibrium_ratio', 'Equilibrium Ratio'),
        ('back_draw', 'Draw Odds'),
        ('back_over25', 'Over 2.5 Odds'),
    ]

    for stat_key, stat_label in stat_names:
        vals = [m[stat_key] for m in matches_00 if not np.isnan(m.get(stat_key, np.nan))]
        if vals:
            wins = [m[stat_key] for m in matches_00 if not np.isnan(m.get(stat_key, np.nan)) and m['is_draw']]
            losses = [m[stat_key] for m in matches_00 if not np.isnan(m.get(stat_key, np.nan)) and not m['is_draw']]
            win_mean = np.mean(wins) if wins else 0
            loss_mean = np.mean(losses) if losses else 0
            print(f"  {stat_label:<22}: N={len(vals):>3}, Mean={np.mean(vals):>6.2f}, Med={np.median(vals):>6.2f}, "
                  f"Min={np.min(vals):>6.2f}, Max={np.max(vals):>6.2f} | "
                  f"WIN avg={win_mean:>6.2f}, LOSS avg={loss_mean:>6.2f}")

    print(f"""
RECOMMENDED V3 FILTERS:
  The analysis above shows which individual stats and combinations
  best predict draws when the match is 0-0 at minute 30.

  Look for:
  - Filters with WIN avg < LOSS avg for "low activity" stats
    (meaning draws tend to happen when the stat value is LOWER)
  - Combinations that maintain N >= 5 while improving WR significantly
  - New stats NOT in V2 that show strong predictive power

NOTE: Sample sizes are small. These patterns need validation with more data.
""")

    # ============================================================
    # STEP 9: Detailed per-match view for 0-0 matches
    # ============================================================
    print_section("STEP 9: DETAILED MATCH-BY-MATCH DATA (0-0 at min 30)")

    for i, m in enumerate(matches_00_sorted):
        result_str = "WIN (DRAW)" if m['is_draw'] else "LOSS"
        print(f"\n--- Match {i+1}: {m['match_name']} ---")
        print(f"  Final Score: {m['final_score']} [{result_str}]")
        print(f"  Data at minute: {m['minuto']:.0f}")
        print(f"  ODDS:  Draw={m.get('back_draw','?')}, Home={m.get('back_home','?')}, Away={m.get('back_away','?')}")
        print(f"         O25={m.get('back_over25','?')}, U25={m.get('back_under25','?')}, O15={m.get('back_over15','?')}")
        print(f"  xG:    Local={m.get('xg_local','?')}, Visit={m.get('xg_visitante','?')}, Total={m.get('xg_total','?')}")
        print(f"  SHOTS: Total={m.get('total_shots','?')}, OnTarget={m.get('total_shots_on_target','?')}")
        print(f"  POSS:  Local={m.get('posesion_local','?')}%, Visit={m.get('posesion_visitante','?')}%, Diff={m.get('possession_diff','?')}")
        print(f"  CORNERS: L={m.get('corners_local','?')}, V={m.get('corners_visitante','?')}, Total={m.get('corners_total','?')}, Diff={m.get('corners_diff','?')}")
        print(f"  DA:    L={m.get('dangerous_attacks_local','?')}, V={m.get('dangerous_attacks_visitante','?')}, Total={m.get('dangerous_attacks_total','?')}")
        print(f"  BC:    L={m.get('big_chances_local','?')}, V={m.get('big_chances_visitante','?')}, Total={m.get('big_chances_total','?')}")
        print(f"  ATK:   L={m.get('attacks_local','?')}, V={m.get('attacks_visitante','?')}, Total={m.get('attacks_total','?')}")
        print(f"  TB:    L={m.get('touches_box_local','?')}, V={m.get('touches_box_visitante','?')}, Total={m.get('touches_box_total','?')}")
        print(f"  BLK:   L={m.get('blocked_shots_local','?')}, V={m.get('blocked_shots_visitante','?')}, Total={m.get('blocked_shots_total','?')}")
        print(f"  SAVES: L={m.get('saves_local','?')}, V={m.get('saves_visitante','?')}, Total={m.get('saves_total','?')}")
        print(f"  MOM:   L={m.get('momentum_local','?')}, V={m.get('momentum_visitante','?')}, Diff={m.get('momentum_diff','?')}")
        print(f"  FOULS: L={m.get('fouls_conceded_local','?')}, V={m.get('fouls_conceded_visitante','?')}, Total={m.get('fouls_total','?')}")
        print(f"  DERIVED: Equilibrium={m.get('equilibrium_ratio','?')}, DangerScore={m.get('danger_score','?')}")
        print(f"  V2 PASS: {m.get('passes_v2','?')}")


if __name__ == "__main__":
    main()
