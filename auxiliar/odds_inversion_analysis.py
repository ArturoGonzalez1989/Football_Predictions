"""
Odds Inversion Anomaly Analysis
Detects cases where back odds don't match what's expected given the score.
When a team is WINNING, their back odds should be LOW (high probability).
Anomaly: winning team has HIGH back odds (scraper may have swapped home/away columns).
"""

import os
import glob
import pandas as pd
import numpy as np
from collections import defaultdict

DATA_DIR = "c:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/betfair_scraper/data"
OUTPUT_FILE = "c:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/auxiliar/odds_inversion_report.txt"

# Thresholds
WINNING_BACK_HIGH_THRESHOLD = 10.0    # Winning team's odds above this → suspicious
LOSING_BACK_LOW_THRESHOLD = 2.0       # Losing team's odds below this → severe
SEVERE_WINNING_ODDS = 20.0            # Winning team's odds above this → very severe
SEVERE_LOSING_ODDS = 2.5              # Losing team's odds below this (combined with above) → very severe
SUSTAINED_THRESHOLD = 5               # Rows in a match to call it "sustained"
ISOLATED_THRESHOLD = 2                # Rows in a match to call it "isolated"

def analyze_match(df):
    """Analyze a single match dataframe for odds inversion anomalies."""
    # Filter to en_juego rows only
    en_juego = df[df['estado_partido'] == 'en_juego'].copy()

    if len(en_juego) == 0:
        return None

    # Convert odds columns to numeric
    for col in ['back_home', 'back_away', 'back_draw', 'goles_local', 'goles_visitante', 'minuto']:
        if col in en_juego.columns:
            en_juego[col] = pd.to_numeric(en_juego[col], errors='coerce')

    total_rows = len(en_juego)

    anomaly_rows = []
    severe_rows = []

    for idx, row in en_juego.iterrows():
        g_local = row.get('goles_local', np.nan)
        g_visit = row.get('goles_visitante', np.nan)
        b_home = row.get('back_home', np.nan)
        b_away = row.get('back_away', np.nan)
        minuto = row.get('minuto', np.nan)

        # Skip if no score data or no odds data
        if pd.isna(g_local) or pd.isna(g_visit):
            continue
        if pd.isna(b_home) or pd.isna(b_away):
            continue

        is_anomaly = False
        is_severe = False
        anomaly_type = []

        # Away team leading
        if g_visit > g_local:
            # Back_away should be LOW (away winning) but is HIGH → suspicious
            if b_away > WINNING_BACK_HIGH_THRESHOLD:
                is_anomaly = True
                anomaly_type.append(f"away_leading_but_back_away={b_away:.1f}")
            # Back_home should be HIGH (home losing) but is LOW → severe
            if b_home < LOSING_BACK_LOW_THRESHOLD:
                is_anomaly = True
                is_severe = True
                anomaly_type.append(f"away_leading_but_back_home={b_home:.2f}(SEVERE)")
            # Combined severe: away leading AND back_away very high AND back_home low
            if b_away > SEVERE_WINNING_ODDS and b_home < SEVERE_LOSING_ODDS:
                is_severe = True
                anomaly_type.append(f"SWAP_LIKELY:away_leads_back_away={b_away:.1f}_back_home={b_home:.2f}")

        # Home team leading
        elif g_local > g_visit:
            # Back_home should be LOW (home winning) but is HIGH → suspicious
            if b_home > WINNING_BACK_HIGH_THRESHOLD:
                is_anomaly = True
                anomaly_type.append(f"home_leading_but_back_home={b_home:.1f}")
            # Back_away should be HIGH (away losing) but is LOW → severe
            if b_away < LOSING_BACK_LOW_THRESHOLD:
                is_anomaly = True
                is_severe = True
                anomaly_type.append(f"home_leading_but_back_away={b_away:.2f}(SEVERE)")
            # Combined severe: home leading AND back_home very high AND back_away low
            if b_home > SEVERE_WINNING_ODDS and b_away < SEVERE_LOSING_ODDS:
                is_severe = True
                anomaly_type.append(f"SWAP_LIKELY:home_leads_back_home={b_home:.1f}_back_away={b_away:.2f}")

        if is_anomaly:
            score = f"{int(g_local)}-{int(g_visit)}"
            anomaly_rows.append({
                'idx': idx,
                'minuto': minuto,
                'score': score,
                'back_home': b_home,
                'back_away': b_away,
                'types': anomaly_type,
                'is_severe': is_severe
            })
        if is_severe:
            severe_rows.append(idx)

    if not anomaly_rows:
        return None

    n_anomaly = len(anomaly_rows)
    n_severe = len(severe_rows)
    pct_affected = (n_anomaly / total_rows) * 100

    # Check if sustained (many consecutive rows)
    anomaly_indices = [r['idx'] for r in anomaly_rows]

    # Find runs of consecutive anomalies
    consecutive_runs = []
    if anomaly_indices:
        run = [anomaly_indices[0]]
        for i in range(1, len(anomaly_indices)):
            # Check if consecutive in dataframe index (not necessarily sequential ints)
            # Use position-based check
            if anomaly_indices[i] - anomaly_indices[i-1] <= 3:  # within 3 rows = same run
                run.append(anomaly_indices[i])
            else:
                consecutive_runs.append(run)
                run = [anomaly_indices[i]]
        consecutive_runs.append(run)

    max_consecutive = max(len(r) for r in consecutive_runs) if consecutive_runs else 0

    # Minute distribution of anomalies
    minutes = [r['minuto'] for r in anomaly_rows if not pd.isna(r['minuto'])]

    # Score transitions: check if anomaly happens right after a score change
    # Get all score changes in the match
    score_cols = ['goles_local', 'goles_visitante']
    if all(c in en_juego.columns for c in score_cols):
        scores = en_juego[score_cols].ffill()
        score_changes = scores.ne(scores.shift()).any(axis=1)
        score_change_positions = set(en_juego.index[score_changes])
    else:
        score_change_positions = set()

    # Check anomalies near score changes (within 2 rows)
    near_score_change = 0
    for r in anomaly_rows:
        for sc_idx in score_change_positions:
            if abs(r['idx'] - sc_idx) <= 2:
                near_score_change += 1
                break

    return {
        'total_rows': total_rows,
        'n_anomaly': n_anomaly,
        'n_severe': n_severe,
        'pct_affected': pct_affected,
        'max_consecutive': max_consecutive,
        'consecutive_runs': consecutive_runs,
        'minutes': minutes,
        'near_score_change': near_score_change,
        'anomaly_rows': anomaly_rows,
        'is_sustained': max_consecutive > SUSTAINED_THRESHOLD,
        'is_isolated': n_anomaly <= ISOLATED_THRESHOLD,
    }


def main():
    csv_files = glob.glob(os.path.join(DATA_DIR, "partido_*.csv"))
    print(f"Found {len(csv_files)} partido CSV files")

    results = {}
    errors = []
    skipped_no_enjuego = 0

    for i, fpath in enumerate(csv_files):
        if i % 100 == 0:
            print(f"  Processing {i}/{len(csv_files)}...")

        fname = os.path.basename(fpath)
        try:
            df = pd.read_csv(fpath, low_memory=False)
            result = analyze_match(df)
            if result is None:
                skipped_no_enjuego += 1
            else:
                results[fname] = result
        except Exception as e:
            errors.append((fname, str(e)))

    print(f"Done. {len(results)} matches with anomalies found.")

    # --- Summary statistics ---
    all_anomaly_matches = {k: v for k, v in results.items() if v['n_anomaly'] > 0}
    all_severe_matches = {k: v for k, v in results.items() if v['n_severe'] > 0}
    sustained_matches = {k: v for k, v in results.items() if v['is_sustained']}
    isolated_matches = {k: v for k, v in results.items() if v['is_isolated'] and not v['is_sustained']}

    # Minute distribution
    all_minutes = []
    for v in all_anomaly_matches.values():
        all_minutes.extend([m for m in v['minutes'] if not pd.isna(m)])

    minute_bins = defaultdict(int)
    for m in all_minutes:
        bucket = int(m // 10) * 10
        minute_bins[f"{bucket}-{bucket+9}"] += 1

    # All anomaly types
    type_counts = defaultdict(int)
    for v in all_anomaly_matches.values():
        for row in v['anomaly_rows']:
            for t in row['types']:
                # Simplify type label
                if 'SWAP_LIKELY' in t:
                    type_counts['SWAP_LIKELY (combined severe)'] += 1
                elif 'SEVERE' in t:
                    type_counts['SEVERE (winning team odds < 2.0)'] += 1
                elif 'away_leading_but_back_away' in t:
                    type_counts['away_leading_high_back_away (>10)'] += 1
                elif 'home_leading_but_back_home' in t:
                    type_counts['home_leading_high_back_home (>10)'] += 1

    # Top 20 worst matches by % affected, then by severity
    sorted_by_pct = sorted(all_anomaly_matches.items(),
                           key=lambda x: (x[1]['n_severe'], x[1]['pct_affected']),
                           reverse=True)[:20]

    # Build report
    lines = []
    lines.append("=" * 80)
    lines.append("ODDS INVERSION ANOMALY ANALYSIS REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append("DATASET OVERVIEW")
    lines.append("-" * 40)
    lines.append(f"Total partido CSV files:          {len(csv_files)}")
    lines.append(f"Matches with no en_juego rows:   {skipped_no_enjuego}")
    lines.append(f"Matches analyzed (had en_juego): {len(csv_files) - skipped_no_enjuego - len(errors)}")
    lines.append(f"Parse errors:                    {len(errors)}")
    lines.append("")
    lines.append("ANOMALY SUMMARY")
    lines.append("-" * 40)
    lines.append(f"Matches with ANY anomaly:        {len(all_anomaly_matches)}")
    lines.append(f"Matches with SEVERE anomaly:     {len(all_severe_matches)}")
    lines.append(f"Matches SUSTAINED (>5 rows):     {len(sustained_matches)}")
    lines.append(f"Matches ISOLATED (<=2 rows):     {len(isolated_matches)}")
    lines.append("")

    # Percentage of all analyzed matches
    analyzed = len(csv_files) - skipped_no_enjuego - len(errors)
    if analyzed > 0:
        lines.append(f"% matches with ANY anomaly:      {len(all_anomaly_matches)/analyzed*100:.1f}%")
        lines.append(f"% matches with SEVERE anomaly:   {len(all_severe_matches)/analyzed*100:.1f}%")
        lines.append(f"% matches SUSTAINED:             {len(sustained_matches)/analyzed*100:.1f}%")
    lines.append("")

    lines.append("ANOMALY TYPE BREAKDOWN (total row count)")
    lines.append("-" * 40)
    for t, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {t}: {cnt}")
    lines.append("")

    lines.append("MINUTE DISTRIBUTION OF ANOMALIES (all anomalous rows)")
    lines.append("-" * 40)
    for bucket, cnt in sorted(minute_bins.items()):
        bar = "#" * min(cnt, 50)
        lines.append(f"  {bucket:>8} min: {cnt:>5}  {bar}")
    lines.append("")

    lines.append("ISOLATION vs SUSTAINED BREAKDOWN")
    lines.append("-" * 40)
    # Distribution of n_anomaly per match
    anomaly_counts = [v['n_anomaly'] for v in all_anomaly_matches.values()]
    if anomaly_counts:
        lines.append(f"  Mean anomalous rows per match:  {np.mean(anomaly_counts):.1f}")
        lines.append(f"  Median:                         {np.median(anomaly_counts):.1f}")
        lines.append(f"  Max:                            {max(anomaly_counts)}")
        lines.append(f"  Matches with 1-2 rows:          {sum(1 for x in anomaly_counts if x <= 2)}")
        lines.append(f"  Matches with 3-5 rows:          {sum(1 for x in anomaly_counts if 3 <= x <= 5)}")
        lines.append(f"  Matches with 6-10 rows:         {sum(1 for x in anomaly_counts if 6 <= x <= 10)}")
        lines.append(f"  Matches with >10 rows:          {sum(1 for x in anomaly_counts if x > 10)}")
    lines.append("")

    # Score change correlation
    total_anomaly_rows_all = sum(v['n_anomaly'] for v in all_anomaly_matches.values())
    total_near_sc = sum(v['near_score_change'] for v in all_anomaly_matches.values())
    if total_anomaly_rows_all > 0:
        lines.append("SCORE CHANGE CORRELATION")
        lines.append("-" * 40)
        lines.append(f"  Total anomalous rows:                {total_anomaly_rows_all}")
        lines.append(f"  Anomalous rows near score change:    {total_near_sc}")
        lines.append(f"  % near score change:                 {total_near_sc/total_anomaly_rows_all*100:.1f}%")
        lines.append("")

    lines.append("TOP 20 WORST MATCHES (by severity then % affected)")
    lines.append("-" * 80)
    lines.append(f"{'Rank':>4} {'Match':<55} {'Tot':>5} {'Anom':>5} {'%':>6} {'Sev':>4} {'MaxCons':>7} {'Sus':>4}")
    lines.append("-" * 80)

    for rank, (fname, v) in enumerate(sorted_by_pct, 1):
        match_short = fname.replace("partido_", "").replace(".csv", "")
        if len(match_short) > 54:
            match_short = match_short[:51] + "..."
        sus = "YES" if v['is_sustained'] else "no"
        lines.append(f"{rank:>4} {match_short:<55} {v['total_rows']:>5} {v['n_anomaly']:>5} {v['pct_affected']:>5.1f}% {v['n_severe']:>4} {v['max_consecutive']:>7} {sus:>4}")
    lines.append("")

    lines.append("DETAILED VIEW OF TOP 10 WORST MATCHES")
    lines.append("=" * 80)

    for rank, (fname, v) in enumerate(sorted_by_pct[:10], 1):
        lines.append("")
        lines.append(f"#{rank} {fname}")
        lines.append(f"   Total en_juego rows: {v['total_rows']}, Anomalous: {v['n_anomaly']} ({v['pct_affected']:.1f}%), Severe: {v['n_severe']}")
        lines.append(f"   Max consecutive anomalous rows: {v['max_consecutive']}, Sustained: {v['is_sustained']}")
        lines.append(f"   Minutes affected: {sorted(set([int(m) for m in v['minutes'] if not pd.isna(m)]))[:20]}")
        lines.append(f"   Near score change: {v['near_score_change']}/{v['n_anomaly']} rows")
        lines.append("   Sample anomaly rows:")
        for row in v['anomaly_rows'][:5]:
            lines.append(f"     min={row['minuto']}, score={row['score']}, back_home={row['back_home']:.2f}, back_away={row['back_away']:.2f}")
            for t in row['types']:
                lines.append(f"       -> {t}")

    lines.append("")
    lines.append("SUSTAINED MATCHES DETAIL (if any beyond top 10)")
    lines.append("-" * 80)
    sustained_not_in_top10 = [(k, v) for k, v in sustained_matches.items()
                               if k not in dict(sorted_by_pct[:10])]
    if sustained_not_in_top10:
        for fname, v in sustained_not_in_top10[:10]:
            lines.append(f"  {fname}: {v['n_anomaly']} anomalous rows ({v['pct_affected']:.1f}%), max_consecutive={v['max_consecutive']}")
    else:
        lines.append("  (All sustained matches already in top 20)")

    lines.append("")
    lines.append("VERDICT")
    lines.append("=" * 80)

    pct_any = len(all_anomaly_matches)/analyzed*100 if analyzed > 0 else 0
    pct_severe = len(all_severe_matches)/analyzed*100 if analyzed > 0 else 0
    pct_sustained = len(sustained_matches)/analyzed*100 if analyzed > 0 else 0

    if pct_severe < 1 and pct_sustained < 1:
        verdict = "RARE NOISE — Anomalies are infrequent and mostly isolated. Likely scraper glitches or transient data."
    elif pct_severe < 5 and pct_sustained < 2:
        verdict = "MINOR ISSUE — Some systematic occurrences but limited scope. Score-change transitions likely cause."
    else:
        verdict = "SYSTEMATIC BUG — High rate of severe/sustained anomalies. Likely scraper column swap bug."

    lines.append(f"  {verdict}")
    lines.append(f"  % matches with any anomaly: {pct_any:.1f}%")
    lines.append(f"  % matches with severe:      {pct_severe:.1f}%")
    lines.append(f"  % matches sustained (>5):   {pct_sustained:.1f}%")

    if errors:
        lines.append("")
        lines.append(f"PARSE ERRORS ({len(errors)} files)")
        lines.append("-" * 40)
        for fname, err in errors[:10]:
            lines.append(f"  {fname}: {err}")

    report = "\n".join(lines)
    print(report)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\nReport saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
