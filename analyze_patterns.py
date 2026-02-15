# -*- coding: utf-8 -*-
"""
Betting Pattern Analysis - 78 Finished Match CSVs
Analyzes minute-by-minute Betfair data for profitable live betting patterns.
"""

import pandas as pd
import numpy as np
import glob
import warnings
import os

warnings.filterwarnings('ignore')

DATA_DIR = r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data'

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def hr(char='=', width=80):
    return char * width

def section(title):
    print()
    print(hr())
    print(f"  {title}")
    print(hr())
    print()

def subsection(title):
    print()
    print(hr('-', 70))
    print(f"  {title}")
    print(hr('-', 70))

def load_all_matches():
    """Load all partido CSV files and return list of DataFrames with match info."""
    files = glob.glob(os.path.join(DATA_DIR, 'partido_*.csv'))
    matches = []

    for f in files:
        try:
            df = pd.read_csv(f)
            # Need at least some in-game data
            if 'estado_partido' not in df.columns:
                continue

            # Convert numeric columns
            num_cols = ['minuto', 'goles_local', 'goles_visitante',
                       'back_home', 'lay_home', 'back_draw', 'lay_draw',
                       'back_away', 'lay_away',
                       'posesion_local', 'posesion_visitante',
                       'tiros_local', 'tiros_visitante',
                       'tiros_puerta_local', 'tiros_puerta_visitante',
                       'corners_local', 'corners_visitante',
                       'tarjetas_amarillas_local', 'tarjetas_amarillas_visitante',
                       'xg_local', 'xg_visitante',
                       'shots_off_target_local', 'shots_off_target_visitante',
                       'dangerous_attacks_local', 'dangerous_attacks_visitante',
                       'big_chances_local', 'big_chances_visitante']
            for col in num_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Extract match name
            basename = os.path.basename(f)
            match_name = basename.replace('partido_', '').replace('.csv', '')
            df['match_id'] = match_name

            # Filter to only in-game + halftime + final rows
            mask = df['estado_partido'].isin(['en_juego', 'descanso', 'finalizado'])
            df_game = df[mask].copy()

            if len(df_game) < 5:
                continue

            # Get final score
            final_rows = df[df['estado_partido'] == 'finalizado']
            if len(final_rows) == 0:
                # Use last row
                final_rows = df.tail(1)

            final_goals_home = final_rows['goles_local'].iloc[-1]
            final_goals_away = final_rows['goles_visitante'].iloc[-1]

            if pd.isna(final_goals_home) or pd.isna(final_goals_away):
                continue

            df_game['final_goals_home'] = int(final_goals_home)
            df_game['final_goals_away'] = int(final_goals_away)

            if final_goals_home > final_goals_away:
                result = 'home_win'
            elif final_goals_home < final_goals_away:
                result = 'away_win'
            else:
                result = 'draw'
            df_game['final_result'] = result

            matches.append(df_game)
        except Exception as e:
            pass

    return matches


def detect_goals(df):
    """Detect goal events from a match DataFrame. Returns list of (minute, scorer_side)."""
    goals = []
    prev_home = None
    prev_away = None

    for _, row in df.iterrows():
        if pd.isna(row.get('minuto')) or pd.isna(row.get('goles_local')) or pd.isna(row.get('goles_visitante')):
            continue

        cur_home = int(row['goles_local'])
        cur_away = int(row['goles_visitante'])
        minute = row['minuto']

        if prev_home is not None:
            if cur_home > prev_home:
                goals.append((minute, 'home'))
            if cur_away > prev_away:
                goals.append((minute, 'away'))

        prev_home = cur_home
        prev_away = cur_away

    return goals


# ============================================================================
# MAIN ANALYSIS
# ============================================================================

def main():
    print(hr('*'))
    print("  BETTING PATTERN ANALYSIS - LIVE MATCH DATA")
    print("  Analyzing minute-by-minute Betfair exchange data")
    print(hr('*'))

    matches = load_all_matches()
    print(f"\nLoaded {len(matches)} matches with sufficient data.")

    # Combine all data
    all_data = pd.concat(matches, ignore_index=True)

    # Basic stats
    results = [m['final_result'].iloc[0] for m in matches]
    home_wins = results.count('home_win')
    away_wins = results.count('away_win')
    draws = results.count('draw')
    print(f"Results: {home_wins} home wins, {away_wins} away wins, {draws} draws")

    total_goals = sum(m['final_goals_home'].iloc[0] + m['final_goals_away'].iloc[0] for m in matches)
    print(f"Total goals: {int(total_goals)} ({total_goals/len(matches):.2f} per match)")

    # ========================================================================
    # A. ODDS vs REALITY
    # ========================================================================
    section("A. ODDS vs REALITY")

    # A1. When back odds drop >20% in 10 minutes
    subsection("A1. Sharp odds drops (>20% decrease in 10 min) -- Does the backed team win?")

    sharp_drops_home = []
    sharp_drops_away = []

    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        if len(ingame) < 3:
            continue
        ingame = ingame.sort_values('minuto')

        for side, back_col in [('home', 'back_home'), ('away', 'back_away')]:
            if back_col not in ingame.columns:
                continue
            odds_vals = ingame[['minuto', back_col]].dropna()
            if len(odds_vals) < 2:
                continue

            for i in range(len(odds_vals)):
                for j in range(i+1, len(odds_vals)):
                    min_diff = odds_vals.iloc[j]['minuto'] - odds_vals.iloc[i]['minuto']
                    if 5 <= min_diff <= 15:
                        odds_before = odds_vals.iloc[i][back_col]
                        odds_after = odds_vals.iloc[j][back_col]
                        if odds_before > 1.05:  # Avoid already-settled matches
                            pct_change = (odds_after - odds_before) / odds_before
                            if pct_change < -0.20:  # >20% drop
                                trigger_minute = odds_vals.iloc[j]['minuto']
                                result = m['final_result'].iloc[0]
                                won = (side == 'home' and result == 'home_win') or \
                                      (side == 'away' and result == 'away_win')
                                entry = {
                                    'match': m['match_id'].iloc[0],
                                    'side': side,
                                    'minute': trigger_minute,
                                    'odds_before': odds_before,
                                    'odds_after': odds_after,
                                    'pct_drop': pct_change * 100,
                                    'won': won
                                }
                                if side == 'home':
                                    sharp_drops_home.append(entry)
                                else:
                                    sharp_drops_away.append(entry)
                                break  # One trigger per window per match side

    all_drops = sharp_drops_home + sharp_drops_away
    # De-duplicate by match+side (keep first trigger)
    seen = set()
    unique_drops = []
    for d in all_drops:
        key = (d['match'], d['side'])
        if key not in seen:
            seen.add(key)
            unique_drops.append(d)

    if unique_drops:
        n = len(unique_drops)
        wins = sum(1 for d in unique_drops if d['won'])
        avg_odds = np.mean([d['odds_after'] for d in unique_drops])
        win_rate = wins / n * 100
        # ROI: if we back at odds_after each time
        roi_sum = sum((d['odds_after'] - 1) if d['won'] else -1 for d in unique_drops)
        roi = roi_sum / n * 100

        print(f"  Matches with sharp odds drop (>20% in ~10 min): {n}")
        print(f"  Win rate of backed team: {wins}/{n} = {win_rate:.1f}%")
        print(f"  Average odds at trigger: {avg_odds:.2f}")
        print(f"  Estimated ROI (flat stake): {roi:+.1f}%")
        print(f"  Break-even win rate at avg odds {avg_odds:.2f}: {100/avg_odds:.1f}%")

        # Split by minute ranges
        early = [d for d in unique_drops if d['minute'] <= 30]
        mid = [d for d in unique_drops if 30 < d['minute'] <= 60]
        late = [d for d in unique_drops if d['minute'] > 60]
        for label, subset in [("Min 0-30", early), ("Min 31-60", mid), ("Min 61-90+", late)]:
            if subset:
                sw = sum(1 for d in subset if d['won'])
                sr = sw / len(subset) * 100
                roi_s = sum((d['odds_after']-1) if d['won'] else -1 for d in subset) / len(subset) * 100
                print(f"    {label}: {len(subset)} triggers, win rate {sr:.1f}%, ROI {roi_s:+.1f}%")
    else:
        print("  No sharp odds drops found.")

    # A2. Odds drift up (team losing favor) -- does the drifting team's opponent win?
    subsection("A2. Odds drift up (>30% increase in 10 min) -- Underdog comeback?")

    drift_ups = []
    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        if len(ingame) < 3:
            continue
        ingame = ingame.sort_values('minuto')

        for side, back_col in [('home', 'back_home'), ('away', 'back_away')]:
            if back_col not in ingame.columns:
                continue
            odds_vals = ingame[['minuto', back_col]].dropna()
            if len(odds_vals) < 2:
                continue

            for i in range(len(odds_vals)):
                for j in range(i+1, len(odds_vals)):
                    min_diff = odds_vals.iloc[j]['minuto'] - odds_vals.iloc[i]['minuto']
                    if 5 <= min_diff <= 15:
                        odds_before = odds_vals.iloc[i][back_col]
                        odds_after = odds_vals.iloc[j][back_col]
                        if odds_before > 1.1 and odds_before < 20:
                            pct_change = (odds_after - odds_before) / odds_before
                            if pct_change > 0.30:  # >30% drift up
                                trigger_minute = odds_vals.iloc[j]['minuto']
                                result = m['final_result'].iloc[0]
                                # Drifting team still wins despite losing favor
                                drift_team_wins = (side == 'home' and result == 'home_win') or \
                                                   (side == 'away' and result == 'away_win')
                                entry = {
                                    'match': m['match_id'].iloc[0],
                                    'side': side,
                                    'minute': trigger_minute,
                                    'odds_before': odds_before,
                                    'odds_after': odds_after,
                                    'pct_rise': pct_change * 100,
                                    'drifter_won': drift_team_wins,
                                    'odds_at_trigger': odds_after
                                }
                                drift_ups.append(entry)
                                break

    seen2 = set()
    unique_drifts = []
    for d in drift_ups:
        key = (d['match'], d['side'])
        if key not in seen2:
            seen2.add(key)
            unique_drifts.append(d)

    if unique_drifts:
        n = len(unique_drifts)
        # Scenario: back the drifting team (now underdog/bigger price) as a value bet
        drifter_wins = sum(1 for d in unique_drifts if d['drifter_won'])
        avg_odds = np.mean([d['odds_at_trigger'] for d in unique_drifts])
        win_rate = drifter_wins / n * 100
        roi_sum = sum((d['odds_at_trigger'] - 1) if d['drifter_won'] else -1 for d in unique_drifts)
        roi = roi_sum / n * 100

        print(f"  Matches with significant odds drift up (>30%): {n}")
        print(f"  Drifting team still wins: {drifter_wins}/{n} = {win_rate:.1f}%")
        print(f"  Average odds at trigger: {avg_odds:.2f}")
        print(f"  ROI backing drifting team at new price: {roi:+.1f}%")
        print(f"  Break-even win rate: {100/avg_odds:.1f}%")
        print()
        # Opponent wins
        opp_wins = n - drifter_wins - sum(1 for d in unique_drifts
                                           if not d['drifter_won'] and
                                           (d['side'] == 'home' and d.get('result') == 'draw' or
                                            d['side'] == 'away' and d.get('result') == 'draw'))
        print(f"  [Interpretation: When odds drift up, backing at the higher price")
        print(f"   can offer value if the team recovers. Check ROI above.]")
    else:
        print("  No significant odds drifts found.")

    # ========================================================================
    # B. xG vs GOALS (Value Detection)
    # ========================================================================
    section("B. xG vs GOALS -- VALUE DETECTION")

    # B1. xG >> Goals (underperforming team)
    subsection("B1. xG >> Goals -- Does the underperforming team eventually score?")

    xg_underperform = []
    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        if len(ingame) < 5:
            continue
        ingame = ingame.sort_values('minuto')

        for side in ['home', 'away']:
            xg_col = 'xg_local' if side == 'home' else 'xg_visitante'
            goals_col = 'goles_local' if side == 'home' else 'goles_visitante'
            back_col = 'back_home' if side == 'home' else 'back_away'

            # Check at various points in the match
            for check_min in [20, 30, 45, 60]:
                rows_at = ingame[(ingame['minuto'] >= check_min - 3) & (ingame['minuto'] <= check_min + 3)]
                if len(rows_at) == 0:
                    continue

                row = rows_at.iloc[len(rows_at)//2]
                xg_val = row.get(xg_col)
                goals_val = row.get(goals_col)
                odds_val = row.get(back_col)

                if pd.isna(xg_val) or pd.isna(goals_val):
                    continue

                xg_excess = xg_val - goals_val
                if xg_excess >= 0.5:  # xG at least 0.5 more than actual goals
                    # Did they score more goals after this point?
                    final_goals = m[f'final_goals_{side}'].iloc[0]
                    scored_later = final_goals > goals_val

                    xg_underperform.append({
                        'match': m['match_id'].iloc[0],
                        'side': side,
                        'check_minute': check_min,
                        'xg': xg_val,
                        'goals_at_time': goals_val,
                        'xg_excess': xg_excess,
                        'scored_later': scored_later,
                        'final_goals': final_goals,
                        'odds_at_time': odds_val
                    })

    if xg_underperform:
        df_xg = pd.DataFrame(xg_underperform)
        n = len(df_xg)
        scored = df_xg['scored_later'].sum()
        rate = scored / n * 100

        print(f"  Instances where xG exceeds goals by 0.5+: {n}")
        print(f"  Team scores more goals after detection: {scored}/{n} = {rate:.1f}%")

        # By xG excess ranges
        for lo, hi, label in [(0.5, 1.0, "xG excess 0.5-1.0"), (1.0, 2.0, "xG excess 1.0-2.0"), (2.0, 10.0, "xG excess 2.0+")]:
            subset = df_xg[(df_xg['xg_excess'] >= lo) & (df_xg['xg_excess'] < hi)]
            if len(subset) > 0:
                s = subset['scored_later'].sum()
                r = s / len(subset) * 100
                avg_o = subset['odds_at_time'].dropna().mean()
                print(f"    {label}: {len(subset)} cases, scored later {r:.1f}%, avg odds {avg_o:.2f}" if not pd.isna(avg_o) else f"    {label}: {len(subset)} cases, scored later {r:.1f}%")

        # By minute
        for mmin, label in [(20, "Detected ~min 20"), (30, "Detected ~min 30"), (45, "Detected ~min 45"), (60, "Detected ~min 60")]:
            subset = df_xg[df_xg['check_minute'] == mmin]
            if len(subset) > 0:
                s = subset['scored_later'].sum()
                r = s / len(subset) * 100
                print(f"    {label}: {len(subset)} cases, scored later {r:.1f}%")
    else:
        print("  No xG underperformance instances found.")

    # B2. Goals >> xG (overperforming)
    subsection("B2. Goals >> xG -- Odds overreaction (overperforming team)")

    xg_overperform = []
    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        if len(ingame) < 5:
            continue
        ingame = ingame.sort_values('minuto')

        for side in ['home', 'away']:
            xg_col = 'xg_local' if side == 'home' else 'xg_visitante'
            goals_col = 'goles_local' if side == 'home' else 'goles_visitante'
            opp_side = 'away' if side == 'home' else 'home'
            back_opp_col = 'back_away' if side == 'home' else 'back_home'

            for check_min in [30, 45, 60]:
                rows_at = ingame[(ingame['minuto'] >= check_min - 3) & (ingame['minuto'] <= check_min + 3)]
                if len(rows_at) == 0:
                    continue
                row = rows_at.iloc[len(rows_at)//2]

                xg_val = row.get(xg_col)
                goals_val = row.get(goals_col)
                odds_opp = row.get(back_opp_col)

                if pd.isna(xg_val) or pd.isna(goals_val) or goals_val == 0:
                    continue

                overperf = goals_val - xg_val
                if overperf >= 0.8:  # Scoring well above xG
                    result = m['final_result'].iloc[0]
                    overperf_team_wins = (side == 'home' and result == 'home_win') or \
                                         (side == 'away' and result == 'away_win')
                    opp_wins = (opp_side == 'home' and result == 'home_win') or \
                               (opp_side == 'away' and result == 'away_win')

                    xg_overperform.append({
                        'match': m['match_id'].iloc[0],
                        'side': side,
                        'check_minute': check_min,
                        'xg': xg_val,
                        'goals': goals_val,
                        'overperf': overperf,
                        'overperf_wins': overperf_team_wins,
                        'opp_wins': opp_wins,
                        'opp_odds': odds_opp
                    })

    if xg_overperform:
        df_op = pd.DataFrame(xg_overperform)
        n = len(df_op)
        op_wins = df_op['overperf_wins'].sum()
        opp_w = df_op['opp_wins'].sum()

        print(f"  Instances where Goals exceed xG by 0.8+: {n}")
        print(f"  Overperforming team wins: {op_wins}/{n} = {op_wins/n*100:.1f}%")
        print(f"  Opponent (value bet) wins: {opp_w}/{n} = {opp_w/n*100:.1f}%")

        valid_opp = df_op[df_op['opp_odds'].notna() & (df_op['opp_odds'] > 1)]
        if len(valid_opp) > 0:
            avg_opp_odds = valid_opp['opp_odds'].mean()
            roi_sum = sum((r['opp_odds'] - 1) if r['opp_wins'] else -1 for _, r in valid_opp.iterrows())
            roi = roi_sum / len(valid_opp) * 100
            print(f"  Avg opponent odds: {avg_opp_odds:.2f}")
            print(f"  ROI backing opponent (fade the overperformer): {roi:+.1f}%")
    else:
        print("  No significant overperformance found.")

    # ========================================================================
    # C. MOMENTUM PATTERNS
    # ========================================================================
    section("C. MOMENTUM PATTERNS")
    subsection("C1. Team dominates stats but is losing -- What happens?")

    momentum_cases = []
    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        if len(ingame) < 5:
            continue
        ingame = ingame.sort_values('minuto')

        for _, row in ingame.iterrows():
            minute = row.get('minuto')
            if pd.isna(minute) or minute < 20:
                continue

            goals_h = row.get('goles_local', 0)
            goals_a = row.get('goles_visitante', 0)
            poss_h = row.get('posesion_local')
            poss_a = row.get('posesion_visitante')
            shots_h = row.get('tiros_local')
            shots_a = row.get('tiros_visitante')
            corners_h = row.get('corners_local')
            corners_a = row.get('corners_visitante')
            back_h = row.get('back_home')
            back_a = row.get('back_away')
            xg_h = row.get('xg_local')
            xg_a = row.get('xg_visitante')

            if pd.isna(poss_h) or pd.isna(shots_h) or pd.isna(goals_h):
                continue

            for side in ['home', 'away']:
                if side == 'home':
                    poss, shots, corners_s = poss_h, shots_h, corners_h or 0
                    opp_poss, opp_shots = poss_a, shots_a
                    my_goals, opp_goals = goals_h, goals_a
                    my_back = back_h
                    my_xg, opp_xg = xg_h, xg_a
                else:
                    poss, shots, corners_s = poss_a, shots_a, corners_a or 0
                    opp_poss, opp_shots = poss_h, shots_h
                    my_goals, opp_goals = goals_a, goals_h
                    my_back = back_a
                    my_xg, opp_xg = xg_a, xg_h

                if pd.isna(opp_shots) or pd.isna(poss):
                    continue

                # "Dominates stats but losing" criteria:
                # possession > 55%, shots > opponent shots + 3, but trailing
                dominates = (poss > 55 and shots > opp_shots + 3 and my_goals < opp_goals)

                if dominates:
                    result = m['final_result'].iloc[0]
                    dom_wins = (side == 'home' and result == 'home_win') or \
                               (side == 'away' and result == 'away_win')
                    dom_draws = result == 'draw'

                    momentum_cases.append({
                        'match': m['match_id'].iloc[0],
                        'side': side,
                        'minute': minute,
                        'possession': poss,
                        'shots_advantage': shots - opp_shots,
                        'score_deficit': opp_goals - my_goals,
                        'dominating_team_wins': dom_wins,
                        'draw': dom_draws,
                        'odds_at_time': my_back,
                        'xg': my_xg
                    })

    # De-duplicate: take first detection per match per side
    seen_mom = set()
    unique_momentum = []
    for mc in momentum_cases:
        key = (mc['match'], mc['side'])
        if key not in seen_mom:
            seen_mom.add(key)
            unique_momentum.append(mc)

    if unique_momentum:
        n = len(unique_momentum)
        wins = sum(1 for mc in unique_momentum if mc['dominating_team_wins'])
        draws_cnt = sum(1 for mc in unique_momentum if mc['draw'])
        loses = n - wins - draws_cnt
        avg_odds = np.mean([mc['odds_at_time'] for mc in unique_momentum if mc['odds_at_time'] and not pd.isna(mc['odds_at_time'])])

        print(f"  Cases where one team dominates stats but is trailing: {n}")
        print(f"  Dominating team comes back to WIN: {wins}/{n} = {wins/n*100:.1f}%")
        print(f"  Match ends DRAW: {draws_cnt}/{n} = {draws_cnt/n*100:.1f}%")
        print(f"  Dominating team still LOSES: {loses}/{n} = {loses/n*100:.1f}%")
        print(f"  Does not lose rate (win+draw): {(wins+draws_cnt)}/{n} = {(wins+draws_cnt)/n*100:.1f}%")

        valid = [mc for mc in unique_momentum if mc['odds_at_time'] and not pd.isna(mc['odds_at_time']) and mc['odds_at_time'] > 1]
        if valid:
            avg_o = np.mean([mc['odds_at_time'] for mc in valid])
            roi_sum = sum((mc['odds_at_time'] - 1) if mc['dominating_team_wins'] else -1 for mc in valid)
            roi = roi_sum / len(valid) * 100
            print(f"  Average back odds: {avg_o:.2f}")
            print(f"  ROI backing dominating team: {roi:+.1f}%")
            print(f"  Break-even win rate: {100/avg_o:.1f}%")
    else:
        print("  No clear domination-while-losing cases found.")

    # C2. Momentum column analysis
    subsection("C2. In-game Momentum indicator analysis")

    mom_data = []
    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        if 'momentum_local' not in ingame.columns or 'momentum_visitante' not in ingame.columns:
            continue
        ingame = ingame.sort_values('minuto')

        for _, row in ingame.iterrows():
            mom_h = row.get('momentum_local')
            mom_a = row.get('momentum_visitante')
            minute = row.get('minuto')

            if pd.isna(mom_h) or pd.isna(mom_a) or pd.isna(minute):
                continue

            result = m['final_result'].iloc[0]
            mom_data.append({
                'match': m['match_id'].iloc[0],
                'minute': minute,
                'mom_home': mom_h,
                'mom_away': mom_a,
                'mom_diff': mom_h - mom_a,
                'result': result,
                'back_home': row.get('back_home'),
                'back_away': row.get('back_away')
            })

    if mom_data:
        df_mom = pd.DataFrame(mom_data)
        print(f"  Momentum data points: {len(df_mom)}")
        print(f"  Momentum range home: {df_mom['mom_home'].min():.0f} to {df_mom['mom_home'].max():.0f}")
        print(f"  Momentum range away: {df_mom['mom_away'].min():.0f} to {df_mom['mom_away'].max():.0f}")

        # When momentum strongly favors home (top quartile)
        high_mom = df_mom[df_mom['mom_diff'] > df_mom['mom_diff'].quantile(0.75)]
        if len(high_mom) > 0:
            # Deduplicate by match
            hm_by_match = high_mom.groupby('match').first().reset_index()
            hw = (hm_by_match['result'] == 'home_win').sum()
            print(f"\n  When momentum strongly favors home (top 25%):")
            print(f"    Matches: {len(hm_by_match)}, Home wins: {hw} ({hw/len(hm_by_match)*100:.1f}%)")
    else:
        print("  No momentum data available in CSVs.")

    # ========================================================================
    # D. GOAL TIMING PATTERNS
    # ========================================================================
    section("D. GOAL TIMING PATTERNS")

    # Detect all goals across all matches
    all_goals = []
    all_goal_sequences = []  # For between-goal timing

    for m in matches:
        ingame = m[m['estado_partido'].isin(['en_juego', 'descanso'])].copy()
        ingame = ingame.sort_values('minuto')
        goals = detect_goals(ingame)

        for minute, scorer in goals:
            all_goals.append({
                'match': m['match_id'].iloc[0],
                'minute': minute,
                'scorer': scorer
            })

        # Goal sequences (time between goals)
        if len(goals) >= 2:
            goal_minutes = sorted([g[0] for g in goals])
            for i in range(1, len(goal_minutes)):
                gap = goal_minutes[i] - goal_minutes[i-1]
                all_goal_sequences.append({
                    'match': m['match_id'].iloc[0],
                    'gap_minutes': gap,
                    'goal_number': i + 1,
                    'minute_of_next': goal_minutes[i]
                })

    subsection("D1. Goal distribution by 10-minute intervals")

    if all_goals:
        df_goals = pd.DataFrame(all_goals)

        # Bin into 10-min intervals
        bins = list(range(0, 100, 10))
        labels = [f"{b}-{b+9}" for b in bins[:-1]]
        df_goals['interval'] = pd.cut(df_goals['minute'], bins=bins, labels=labels, right=False)

        dist = df_goals['interval'].value_counts().sort_index()
        total_g = len(df_goals)

        print(f"  Total goals detected: {total_g} across {len(matches)} matches")
        print(f"  {'Interval':<12} {'Goals':<8} {'% of total':<12} {'Per match':<10}")
        print(f"  {'-'*42}")
        for interval in labels:
            count = dist.get(interval, 0)
            pct = count / total_g * 100 if total_g > 0 else 0
            per_m = count / len(matches)
            bar = '#' * int(pct / 2)
            print(f"  {interval:<12} {count:<8} {pct:>5.1f}%       {per_m:.2f}      {bar}")

        # 45+ minute goals (stoppage time first half: minute 45-49)
        ht_goals = df_goals[(df_goals['minute'] >= 44) & (df_goals['minute'] <= 49)]
        print(f"\n  'First half stoppage time' goals (min 44-49): {len(ht_goals)}")
        print(f"  As % of all goals: {len(ht_goals)/total_g*100:.1f}%")

        # 90+ minute goals
        ft_goals = df_goals[df_goals['minute'] >= 89]
        print(f"  'Full time stoppage time' goals (min 89+): {len(ft_goals)}")
        print(f"  As % of all goals: {len(ft_goals)/total_g*100:.1f}%")

    subsection("D2. Time between consecutive goals")

    if all_goal_sequences:
        df_seq = pd.DataFrame(all_goal_sequences)

        print(f"  Total goal-to-goal intervals: {len(df_seq)}")
        print(f"  Average gap between goals: {df_seq['gap_minutes'].mean():.1f} minutes")
        print(f"  Median gap: {df_seq['gap_minutes'].median():.1f} minutes")
        print(f"  Min gap: {df_seq['gap_minutes'].min():.0f} min, Max gap: {df_seq['gap_minutes'].max():.0f} min")

        # How quickly does next goal come after a goal?
        quick = (df_seq['gap_minutes'] <= 5).sum()
        medium = ((df_seq['gap_minutes'] > 5) & (df_seq['gap_minutes'] <= 10)).sum()
        slow = ((df_seq['gap_minutes'] > 10) & (df_seq['gap_minutes'] <= 20)).sum()
        very_slow = (df_seq['gap_minutes'] > 20).sum()

        print(f"\n  Next goal within 5 min: {quick}/{len(df_seq)} = {quick/len(df_seq)*100:.1f}%")
        print(f"  Next goal 5-10 min: {medium}/{len(df_seq)} = {medium/len(df_seq)*100:.1f}%")
        print(f"  Next goal 10-20 min: {slow}/{len(df_seq)} = {slow/len(df_seq)*100:.1f}%")
        print(f"  Next goal 20+ min: {very_slow}/{len(df_seq)} = {very_slow/len(df_seq)*100:.1f}%")

        print(f"\n  [INSIGHT: {quick/len(df_seq)*100:.0f}% of goals are followed by another within 5 min.")
        print(f"   This supports 'goals come in clusters' theory for next-goal markets.]")

    # D3. First half stoppage time pattern
    subsection("D3. 45+ minute (first half stoppage) goal pattern")

    ht_stoppage = []
    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        ingame = ingame.sort_values('minuto')
        goals = detect_goals(ingame)

        # Check if there's a goal in minutes 44-49
        ht_goal = any(44 <= g[0] <= 49 for g in goals)
        ht_stoppage.append({
            'match': m['match_id'].iloc[0],
            'has_ht_stoppage_goal': ht_goal,
            'total_goals_first_half': sum(1 for g in goals if g[0] <= 49)
        })

    df_ht = pd.DataFrame(ht_stoppage)
    ht_count = df_ht['has_ht_stoppage_goal'].sum()
    print(f"  Matches with a goal in first-half stoppage (min 44-49): {ht_count}/{len(df_ht)} = {ht_count/len(df_ht)*100:.1f}%")

    high_fh = df_ht[df_ht['total_goals_first_half'] >= 2]
    if len(high_fh) > 0:
        ht_in_high = high_fh['has_ht_stoppage_goal'].sum()
        print(f"  In matches with 2+ first-half goals, HT stoppage goal: {ht_in_high}/{len(high_fh)} = {ht_in_high/len(high_fh)*100:.1f}%")

    # ========================================================================
    # E. DRAW PATTERNS
    # ========================================================================
    section("E. DRAW PATTERNS")

    subsection("E1. Half-time draw -- What % end as draws?")

    ht_draws = []
    for m in matches:
        # Get state at half time
        ht_rows = m[m['estado_partido'] == 'descanso']
        if len(ht_rows) == 0:
            continue

        ht_row = ht_rows.iloc[0]
        goals_h_ht = ht_row.get('goles_local')
        goals_a_ht = ht_row.get('goles_visitante')
        back_draw_ht = ht_row.get('back_draw')

        if pd.isna(goals_h_ht) or pd.isna(goals_a_ht):
            continue

        if goals_h_ht == goals_a_ht:  # Draw at HT
            result = m['final_result'].iloc[0]
            ht_draws.append({
                'match': m['match_id'].iloc[0],
                'ht_score': f"{int(goals_h_ht)}-{int(goals_a_ht)}",
                'final_result': result,
                'ended_draw': result == 'draw',
                'back_draw_ht': back_draw_ht
            })

    if ht_draws:
        n = len(ht_draws)
        ended_draw = sum(1 for d in ht_draws if d['ended_draw'])
        print(f"  Matches level at half-time: {n}")
        print(f"  Of those, ended as draw: {ended_draw}/{n} = {ended_draw/n*100:.1f}%")

        # By HT score
        scores = set(d['ht_score'] for d in ht_draws)
        for sc in sorted(scores):
            subset = [d for d in ht_draws if d['ht_score'] == sc]
            dr = sum(1 for d in subset if d['ended_draw'])
            print(f"    HT {sc}: {len(subset)} matches, ended draw {dr}/{len(subset)} = {dr/len(subset)*100:.1f}%")

        # Draw odds at HT
        valid_odds = [d for d in ht_draws if d['back_draw_ht'] and not pd.isna(d['back_draw_ht'])]
        if valid_odds:
            avg_draw_odds = np.mean([d['back_draw_ht'] for d in valid_odds])
            roi_back_draw = sum((d['back_draw_ht'] - 1) if d['ended_draw'] else -1 for d in valid_odds) / len(valid_odds) * 100
            print(f"\n  Average draw odds at HT (when level): {avg_draw_odds:.2f}")
            print(f"  ROI backing draw at HT: {roi_back_draw:+.1f}%")
            print(f"  Break-even win rate: {100/avg_draw_odds:.1f}%")

    subsection("E2. Draw backing/laying profitability by minute")

    draw_by_minute = []
    for m in matches:
        ingame = m[m['estado_partido'].isin(['en_juego', 'descanso'])].copy()
        ingame = ingame.sort_values('minuto')
        result = m['final_result'].iloc[0]

        for _, row in ingame.iterrows():
            minute = row.get('minuto')
            goals_h = row.get('goles_local')
            goals_a = row.get('goles_visitante')
            back_draw = row.get('back_draw')

            if pd.isna(minute) or pd.isna(goals_h) or pd.isna(goals_a) or pd.isna(back_draw):
                continue
            if back_draw < 1.01:
                continue

            is_level = (goals_h == goals_a)

            draw_by_minute.append({
                'match': m['match_id'].iloc[0],
                'minute': minute,
                'is_level': is_level,
                'back_draw': back_draw,
                'ended_draw': result == 'draw'
            })

    if draw_by_minute:
        df_draw = pd.DataFrame(draw_by_minute)

        # Only when match is level
        level = df_draw[df_draw['is_level']].copy()

        print(f"  Analyzing draw backing when match is LEVEL...")
        print(f"  {'Minute range':<15} {'N':<6} {'Draw %':<10} {'Avg odds':<10} {'ROI back':<10} {'ROI lay':<10}")
        print(f"  {'-'*61}")

        for lo, hi in [(0, 15), (15, 30), (30, 45), (45, 60), (60, 75), (75, 90)]:
            subset = level[(level['minute'] >= lo) & (level['minute'] < hi)]
            # Deduplicate: one entry per match per range
            if len(subset) == 0:
                continue
            dedup = subset.groupby('match').first().reset_index()
            n_d = len(dedup)
            draws_d = dedup['ended_draw'].sum()
            draw_rate = draws_d / n_d * 100
            avg_odds = dedup['back_draw'].mean()
            roi_back = sum((r['back_draw'] - 1) if r['ended_draw'] else -1 for _, r in dedup.iterrows()) / n_d * 100
            # Lay draw ROI: win 1 if not draw, lose (odds-1) if draw
            roi_lay = sum(1 if not r['ended_draw'] else -(r['back_draw'] - 1) for _, r in dedup.iterrows()) / n_d * 100

            print(f"  {lo}-{hi} min{'':<8} {n_d:<6} {draw_rate:>5.1f}%    {avg_odds:>6.2f}     {roi_back:>+6.1f}%    {roi_lay:>+6.1f}%")

    # ========================================================================
    # F. CORNERS/CARDS AS LEADING INDICATORS
    # ========================================================================
    section("F. CORNERS / CARDS AS LEADING INDICATORS")

    subsection("F1. Do corners/shots predict a goal in the next 10 minutes?")

    corner_goal_pred = []
    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        if len(ingame) < 5:
            continue
        ingame = ingame.sort_values('minuto')
        goals = detect_goals(ingame)
        goal_minutes = set(g[0] for g in goals)

        for _, row in ingame.iterrows():
            minute = row.get('minuto')
            if pd.isna(minute) or minute > 80:  # Need 10 min window ahead
                continue

            corners_h = row.get('corners_local', 0) or 0
            corners_a = row.get('corners_visitante', 0) or 0
            total_corners = corners_h + corners_a
            shots_h = row.get('tiros_local', 0) or 0
            shots_a = row.get('tiros_visitante', 0) or 0
            total_shots = shots_h + shots_a

            # Is there a goal in the next 10 minutes?
            goal_next_10 = any(minute < gm <= minute + 10 for gm in goal_minutes)

            corner_goal_pred.append({
                'match': m['match_id'].iloc[0],
                'minute': minute,
                'total_corners': total_corners,
                'corner_diff': abs(corners_h - corners_a),
                'total_shots': total_shots,
                'goal_next_10': goal_next_10
            })

    if corner_goal_pred:
        df_cp = pd.DataFrame(corner_goal_pred)

        # Bin by corner count
        print(f"  Total data points: {len(df_cp)}")
        print(f"\n  Corner count at time --> Goal probability in next 10 min:")
        print(f"  {'Corners':<12} {'N':<8} {'Goal next 10m':<18} {'Rate':<8}")
        print(f"  {'-'*46}")

        for lo, hi, label in [(0, 2, "0-1"), (2, 4, "2-3"), (4, 6, "4-5"), (6, 8, "6-7"), (8, 30, "8+")]:
            subset = df_cp[(df_cp['total_corners'] >= lo) & (df_cp['total_corners'] < hi)]
            if len(subset) > 0:
                goal_rate = subset['goal_next_10'].mean() * 100
                n_goals = subset['goal_next_10'].sum()
                print(f"  {label:<12} {len(subset):<8} {int(n_goals):<18} {goal_rate:.1f}%")

        # Corner asymmetry as winner predictor
        print(f"\n  Corner ASYMMETRY (|home - away|) vs goal probability:")
        for lo, hi, label in [(0, 1, "diff 0"), (1, 3, "diff 1-2"), (3, 5, "diff 3-4"), (5, 20, "diff 5+")]:
            subset = df_cp[(df_cp['corner_diff'] >= lo) & (df_cp['corner_diff'] < hi)]
            if len(subset) > 0:
                goal_rate = subset['goal_next_10'].mean() * 100
                print(f"  {label:<12} {len(subset):<8} goal rate: {goal_rate:.1f}%")

    subsection("F2. Corner count asymmetry -- Does it predict the winner?")

    corner_winner = []
    for m in matches:
        # Get final corner counts
        last_rows = m.tail(3)
        corners_h = last_rows['corners_local'].dropna()
        corners_a = last_rows['corners_visitante'].dropna()

        if len(corners_h) == 0 or len(corners_a) == 0:
            continue

        ch = corners_h.iloc[-1]
        ca = corners_a.iloc[-1]
        result = m['final_result'].iloc[0]

        corner_winner.append({
            'match': m['match_id'].iloc[0],
            'corners_home': ch,
            'corners_away': ca,
            'corner_winner': 'home' if ch > ca else ('away' if ca > ch else 'equal'),
            'match_winner': result
        })

    if corner_winner:
        df_cw = pd.DataFrame(corner_winner)

        # When home has more corners
        home_more = df_cw[df_cw['corner_winner'] == 'home']
        away_more = df_cw[df_cw['corner_winner'] == 'away']
        equal_c = df_cw[df_cw['corner_winner'] == 'equal']

        print(f"  Total matches with corner data: {len(df_cw)}")

        if len(home_more) > 0:
            hw = (home_more['match_winner'] == 'home_win').sum()
            print(f"\n  Home has MORE corners ({len(home_more)} matches):")
            print(f"    Home wins: {hw}/{len(home_more)} = {hw/len(home_more)*100:.1f}%")
            aw = (home_more['match_winner'] == 'away_win').sum()
            dw = (home_more['match_winner'] == 'draw').sum()
            print(f"    Away wins: {aw}/{len(home_more)} = {aw/len(home_more)*100:.1f}%")
            print(f"    Draws: {dw}/{len(home_more)} = {dw/len(home_more)*100:.1f}%")

        if len(away_more) > 0:
            aw2 = (away_more['match_winner'] == 'away_win').sum()
            print(f"\n  Away has MORE corners ({len(away_more)} matches):")
            print(f"    Away wins: {aw2}/{len(away_more)} = {aw2/len(away_more)*100:.1f}%")
            hw2 = (away_more['match_winner'] == 'home_win').sum()
            dw2 = (away_more['match_winner'] == 'draw').sum()
            print(f"    Home wins: {hw2}/{len(away_more)} = {hw2/len(away_more)*100:.1f}%")
            print(f"    Draws: {dw2}/{len(away_more)} = {dw2/len(away_more)*100:.1f}%")

    subsection("F3. Yellow cards -- Do they correlate with goals?")

    card_goal_data = []
    for m in matches:
        ingame = m[m['estado_partido'] == 'en_juego'].copy()
        if len(ingame) < 5:
            continue
        ingame = ingame.sort_values('minuto')
        goals = detect_goals(ingame)
        goal_minutes = set(g[0] for g in goals)

        prev_cards = None
        for _, row in ingame.iterrows():
            minute = row.get('minuto')
            if pd.isna(minute) or minute > 80:
                continue

            cards_h = row.get('tarjetas_amarillas_local', 0) or 0
            cards_a = row.get('tarjetas_amarillas_visitante', 0) or 0
            total_cards = cards_h + cards_a

            # Detect if a card just happened
            card_just_happened = False
            if prev_cards is not None and total_cards > prev_cards:
                card_just_happened = True
            prev_cards = total_cards

            goal_next_10 = any(minute < gm <= minute + 10 for gm in goal_minutes)

            if card_just_happened:
                card_goal_data.append({
                    'match': m['match_id'].iloc[0],
                    'minute': minute,
                    'goal_next_10': goal_next_10
                })

    if card_goal_data:
        df_cards = pd.DataFrame(card_goal_data)
        n_c = len(df_cards)
        goals_after = df_cards['goal_next_10'].sum()
        rate = goals_after / n_c * 100
        print(f"  Card events detected: {n_c}")
        print(f"  Goal within 10 min after card: {int(goals_after)}/{n_c} = {rate:.1f}%")

        # Compare with baseline
        if corner_goal_pred:
            baseline = pd.DataFrame(corner_goal_pred)['goal_next_10'].mean() * 100
            print(f"  Baseline goal-in-10-min rate (any moment): {baseline:.1f}%")
            print(f"  Lift after card: {rate - baseline:+.1f} percentage points")

    # ========================================================================
    # G. LATE GOAL PATTERNS
    # ========================================================================
    section("G. LATE GOAL PATTERNS")

    subsection("G1. Games with goals after minute 75")

    late_goal_matches = []
    for m in matches:
        ingame = m[m['estado_partido'].isin(['en_juego', 'descanso'])].copy()
        ingame = ingame.sort_values('minuto')
        goals = detect_goals(ingame)

        late_goals = [g for g in goals if g[0] >= 75]
        has_late = len(late_goals) > 0

        # Get state at minute 75
        rows_75 = ingame[(ingame['minuto'] >= 73) & (ingame['minuto'] <= 77)]
        score_at_75_h = None
        score_at_75_a = None
        poss_at_75_h = None

        if len(rows_75) > 0:
            r75 = rows_75.iloc[len(rows_75)//2]
            score_at_75_h = r75.get('goles_local')
            score_at_75_a = r75.get('goles_visitante')
            poss_at_75_h = r75.get('posesion_local')

        late_goal_matches.append({
            'match': m['match_id'].iloc[0],
            'has_late_goal': has_late,
            'late_goal_count': len(late_goals),
            'total_goals': len(goals),
            'score_at_75_h': score_at_75_h,
            'score_at_75_a': score_at_75_a,
            'poss_at_75_h': poss_at_75_h,
            'result': m['final_result'].iloc[0]
        })

    df_late = pd.DataFrame(late_goal_matches)
    n_total = len(df_late)
    n_late = df_late['has_late_goal'].sum()

    print(f"  Matches analyzed: {n_total}")
    print(f"  Matches with goals after min 75: {int(n_late)}/{n_total} = {n_late/n_total*100:.1f}%")
    print(f"  Average late goals per match (when they occur): {df_late[df_late['has_late_goal']]['late_goal_count'].mean():.2f}")

    subsection("G2. Scenarios most likely to produce late goals")

    # By score at 75
    valid_75 = df_late[df_late['score_at_75_h'].notna() & df_late['score_at_75_a'].notna()].copy()

    if len(valid_75) > 0:
        valid_75['score_diff_75'] = valid_75['score_at_75_h'] - valid_75['score_at_75_a']
        valid_75['total_goals_75'] = valid_75['score_at_75_h'] + valid_75['score_at_75_a']
        valid_75['is_level_75'] = valid_75['score_diff_75'] == 0

        print(f"\n  By score situation at minute 75:")

        # Level at 75
        level_75 = valid_75[valid_75['is_level_75']]
        if len(level_75) > 0:
            lg = level_75['has_late_goal'].sum()
            print(f"    Level at 75: {int(lg)}/{len(level_75)} have late goals ({lg/len(level_75)*100:.1f}%)")

        # 1 goal diff
        close_75 = valid_75[valid_75['score_diff_75'].abs() == 1]
        if len(close_75) > 0:
            lg = close_75['has_late_goal'].sum()
            print(f"    1-goal difference at 75: {int(lg)}/{len(close_75)} have late goals ({lg/len(close_75)*100:.1f}%)")

        # 2+ goal diff
        big_75 = valid_75[valid_75['score_diff_75'].abs() >= 2]
        if len(big_75) > 0:
            lg = big_75['has_late_goal'].sum()
            print(f"    2+ goal difference at 75: {int(lg)}/{len(big_75)} have late goals ({lg/len(big_75)*100:.1f}%)")

        # By total goals at 75
        print(f"\n  By total goals scored by minute 75:")
        for tg in [0, 1, 2, 3]:
            label = f"{tg}" if tg < 3 else "3+"
            if tg < 3:
                subset = valid_75[valid_75['total_goals_75'] == tg]
            else:
                subset = valid_75[valid_75['total_goals_75'] >= tg]
            if len(subset) > 0:
                lg = subset['has_late_goal'].sum()
                print(f"    {label} goals at 75: {int(lg)}/{len(subset)} have late goals ({lg/len(subset)*100:.1f}%)")

        # By possession
        print(f"\n  By possession of home team at minute 75:")
        if valid_75['poss_at_75_h'].notna().sum() > 0:
            for lo, hi, label in [(0, 45, "Home poss < 45%"), (45, 55, "Home poss 45-55%"), (55, 100, "Home poss > 55%")]:
                subset = valid_75[(valid_75['poss_at_75_h'] >= lo) & (valid_75['poss_at_75_h'] < hi)]
                if len(subset) > 0:
                    lg = subset['has_late_goal'].sum()
                    print(f"    {label}: {int(lg)}/{len(subset)} have late goals ({lg/len(subset)*100:.1f}%)")

    subsection("G3. Late equalizers and winners")

    late_eq_winners = []
    for m in matches:
        ingame = m[m['estado_partido'].isin(['en_juego', 'descanso'])].copy()
        ingame = ingame.sort_values('minuto')
        goals = detect_goals(ingame)

        # Check goals after 75
        for gmin, gside in goals:
            if gmin < 75:
                continue

            # What was the score just before this goal?
            before = ingame[ingame['minuto'] < gmin]
            if len(before) == 0:
                continue
            prev = before.iloc[-1]
            prev_h = prev.get('goles_local', 0)
            prev_a = prev.get('goles_visitante', 0)

            if pd.isna(prev_h) or pd.isna(prev_a):
                continue

            # Was it an equalizer?
            if gside == 'home' and prev_h + 1 == prev_a + 1 and prev_h < prev_a:
                late_eq_winners.append({'type': 'equalizer', 'minute': gmin, 'match': m['match_id'].iloc[0]})
            elif gside == 'away' and prev_a + 1 == prev_h + 1 and prev_a < prev_h:
                late_eq_winners.append({'type': 'equalizer', 'minute': gmin, 'match': m['match_id'].iloc[0]})

            # Was it a go-ahead/winner goal?
            if gside == 'home' and prev_h == prev_a:
                late_eq_winners.append({'type': 'go-ahead', 'minute': gmin, 'match': m['match_id'].iloc[0]})
            elif gside == 'away' and prev_a == prev_h:
                late_eq_winners.append({'type': 'go-ahead', 'minute': gmin, 'match': m['match_id'].iloc[0]})

    if late_eq_winners:
        df_lew = pd.DataFrame(late_eq_winners)
        eq = df_lew[df_lew['type'] == 'equalizer']
        ga = df_lew[df_lew['type'] == 'go-ahead']
        print(f"  Late equalizers (75+ min): {len(eq)} across {eq['match'].nunique() if len(eq) > 0 else 0} matches")
        print(f"  Late go-ahead goals (75+ min): {len(ga)} across {ga['match'].nunique() if len(ga) > 0 else 0} matches")
        print(f"  Total late decisive goals: {len(df_lew)}")
        print(f"  As % of all matches: {df_lew['match'].nunique()}/{len(matches)} = {df_lew['match'].nunique()/len(matches)*100:.1f}%")
    else:
        print("  No late equalizers or go-ahead goals detected.")

    # ========================================================================
    # SUMMARY: ACTIONABLE PATTERNS
    # ========================================================================
    section("SUMMARY: MOST ACTIONABLE PATTERNS")

    print("  Based on analysis of all matches, here are the key findings ranked")
    print("  by potential profitability and reliability:")
    print()

    findings = []

    # Compile all findings with their stats
    if unique_drops:
        n = len(unique_drops)
        wins = sum(1 for d in unique_drops if d['won'])
        avg_odds = np.mean([d['odds_after'] for d in unique_drops])
        roi_sum = sum((d['odds_after'] - 1) if d['won'] else -1 for d in unique_drops)
        roi = roi_sum / n * 100
        findings.append(('A1', f"Sharp odds drops (>20% in 10min)", n, wins/n*100, avg_odds, roi))

    if unique_drifts:
        n = len(unique_drifts)
        dw = sum(1 for d in unique_drifts if d['drifter_won'])
        avg_o = np.mean([d['odds_at_trigger'] for d in unique_drifts])
        roi_s = sum((d['odds_at_trigger'] - 1) if d['drifter_won'] else -1 for d in unique_drifts)
        roi_d = roi_s / n * 100
        findings.append(('A2', f"Odds drift up (>30%), back drifter", n, dw/n*100, avg_o, roi_d))

    if xg_underperform:
        df_xg = pd.DataFrame(xg_underperform)
        n = len(df_xg)
        scored = df_xg['scored_later'].sum()
        findings.append(('B1', f"xG >> Goals, team scores later", n, scored/n*100, 0, 0))

    if unique_momentum:
        n = len(unique_momentum)
        wins = sum(1 for mc in unique_momentum if mc['dominating_team_wins'])
        valid = [mc for mc in unique_momentum if mc['odds_at_time'] and not pd.isna(mc['odds_at_time']) and mc['odds_at_time'] > 1]
        avg_o = np.mean([mc['odds_at_time'] for mc in valid]) if valid else 0
        roi_s = sum((mc['odds_at_time'] - 1) if mc['dominating_team_wins'] else -1 for mc in valid) if valid else 0
        roi_m = roi_s / len(valid) * 100 if valid else 0
        findings.append(('C1', f"Dominates stats but losing", n, wins/n*100, avg_o, roi_m))

    if ht_draws:
        n = len(ht_draws)
        ended = sum(1 for d in ht_draws if d['ended_draw'])
        valid = [d for d in ht_draws if d['back_draw_ht'] and not pd.isna(d['back_draw_ht'])]
        avg_o = np.mean([d['back_draw_ht'] for d in valid]) if valid else 0
        roi_s = sum((d['back_draw_ht'] - 1) if d['ended_draw'] else -1 for d in valid) if valid else 0
        roi_ht = roi_s / len(valid) * 100 if valid else 0
        findings.append(('E1', f"Back draw at HT (when level)", n, ended/n*100, avg_o, roi_ht))

    # Sort by ROI
    findings.sort(key=lambda x: x[5], reverse=True)

    print(f"  {'ID':<5} {'Pattern':<40} {'N':<6} {'Win%':<8} {'AvgOdds':<9} {'ROI':<8}")
    print(f"  {'-'*76}")
    for f in findings:
        odds_str = f"{f[4]:.2f}" if f[4] > 0 else "N/A"
        roi_str = f"{f[5]:+.1f}%" if f[4] > 0 else "N/A"
        print(f"  {f[0]:<5} {f[1]:<40} {f[2]:<6} {f[3]:<7.1f}% {odds_str:<9} {roi_str:<8}")

    print()
    print(hr('-', 70))
    print("  CAVEATS AND NOTES:")
    print(hr('-', 70))
    print("  - Sample size is limited (78 matches). Patterns need validation")
    print("    with larger datasets before risking real money.")
    print("  - ROI calculations assume flat staking at back odds available.")
    print("  - Commission (Betfair ~2-5%) is NOT included in ROI figures.")
    print("  - Past patterns do not guarantee future results.")
    print("  - Some CSVs may have incomplete data (started mid-match).")
    print("  - All odds are from Betfair Exchange (back/lay).")
    print()
    print(hr('*'))
    print("  END OF ANALYSIS")
    print(hr('*'))


if __name__ == '__main__':
    main()
