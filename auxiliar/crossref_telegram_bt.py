import sys, re, csv
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

# Read CSV
csv_path = 'C:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/analisis/bt_results_20260315_134033.csv'
csv_rows = []
with open(csv_path, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        csv_rows.append(row)

mar_rows = [r for r in csv_rows if r.get('timestamp_utc','').startswith('2026-03-14') or r.get('timestamp_utc','').startswith('2026-03-15')]

# Build lookup by match_id + strategy
csv_lookup = {}
for r in mar_rows:
    mid = r['match_id'].lower()
    strat = r['strategy']
    csv_lookup[(mid, strat)] = r

all_match_ids = list(set(r['match_id'].lower() for r in mar_rows))

# Read Telegram
content = Path('c:/Users/agonz/Downloads/Telegram Desktop/ChatExport_2026-03-14/messages.html').read_text(encoding='utf-8')

msg_pattern = re.compile(
    r'title="(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}[^"]*)".*?<div class="text">(.*?)</div>\s*</div>\s*</div>',
    re.DOTALL
)

raw_alerts = []
for m in msg_pattern.finditer(content):
    ts = m.group(1)
    raw_text = m.group(2)
    link_match = re.search(r'href="([^"]+)"', raw_text)
    link = link_match.group(1) if link_match else ''
    text = re.sub(r'<[^>]+>', ' ', raw_text)
    text = text.replace("&apos;", "'").replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    raw_alerts.append({'ts': ts, 'text': text, 'link': link})

def is_bet_alert(text):
    if 'SEÑAL DETECTADA' in text:
        return True
    if re.search(r'(xG Underperformance|Pressure Cooker|Goal Clustering|Odds Drift Contrarian|LAY Draw Away|BACK Draw 0-0|BACK Underdog|BACK Home Fav|BACK Away Fav|BACK CS|LAY CS|LAY Over|BACK Over|BACK Under|BACK Longshot|BACK Draw 1-1|BACK Draw 2-2|BACK Draw xG|BACK Draw Equal)', text):
        return True
    return False

bet_alerts = [a for a in raw_alerts if is_bet_alert(a['text'])]
bet_alerts = [a for a in bet_alerts if 'Test FC' not in a['text']]

print(f"Betting alerts (excl. test): {len(bet_alerts)}")

STRAT_MAP = {
    'LAY Draw Away Leading': 'lay_draw_away_leading',
    'BACK Home Fav Leading': 'home_fav_leading',
    'BACK CS One-Goal': 'cs_one_goal',
    'xG Underperformance': 'xg_underperformance',
    'xG Underperformance (Base)': 'xg_underperformance',
    'BACK Draw 0-0 (V2R)': 'back_draw_00',
    'BACK Underdog Leading': 'ud_leading',
    'Pressure Cooker': 'pressure_cooker',
    'BACK O2.5 2-Goal Lead': 'over25_2goal',
    'BACK Over 0.5 Poss Extreme': 'poss_extreme',
    'BACK U3.5 Late': 'under35_late',
    'BACK Away Fav Leading': 'away_fav_leading',
    'BACK Draw 2-2 Late': 'draw_22',
    'Goal Clustering': 'goal_clustering',
    'BACK Draw xG Convergence': 'draw_xg_conv',
    'BACK U3.5 3-Goal Lid': 'under35_3goals',
    'BACK U4.5 3-Goals Low xG': 'under45_3goals',
    'LAY CS 1-1 at 0-1': 'lay_cs11',
    'LAY Over 4.5 Blowout': 'lay_over45_blowout',
    'BACK Draw 1-1': 'draw_11',
    'BACK CS 2-0/0-2': 'cs_20',
    'Odds Drift Contrarian': 'odds_drift',
    'BACK Longshot Leading': 'longshot',
    'BACK CS Close': 'cs_close',
    'LAY Over 4.5 v3': 'lay_over45_v3',
    'LAY Over 4.5 V3': 'lay_over45_v3',
    'BACK O2.5 Two Goals': 'over25_2goals',
    'BACK Draw Equalizer Late': 'draw_equalizer',
    'BACK Over 3.5 Early Goals': 'over35_early_goals',
}

def extract_strategy_key(text):
    m = re.search(r'[📊]\s+([^\n⏱💰·]+)', text)
    if m:
        label = m.group(1).strip().rstrip('·').strip()
        for k, v in STRAT_MAP.items():
            if k.lower() == label.lower():
                return v, k
        for k, v in STRAT_MAP.items():
            if k.lower() in label.lower():
                return v, k
        return None, label
    # Non-SEÑAL format: strategy is in bold at start
    for k, v in STRAT_MAP.items():
        if text.startswith(k) or text.startswith('🟢 ' + k) or text.startswith('🔴 ' + k):
            return v, k
    for k, v in STRAT_MAP.items():
        if k in text[:80]:
            return v, k
    return None, ''

def extract_match_from_text(text):
    m = re.search(r'[⚽]\s+([^📊\n⏱]+)', text)
    if m:
        return m.group(1).strip()
    # Non-SEÑAL: match name follows strategy line
    # Try to find a match after a link text
    m = re.search(r'((?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+-\s+(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+))', text)
    if m:
        return m.group(1)
    return ''

def find_csv_row(match_text, link, strategy_key):
    if not strategy_key:
        return None, ''
    # Try via link slug (Betfair ID)
    if link:
        slug_match = re.search(r'apuestas-(\d+)', link)
        if slug_match:
            bet_id = slug_match.group(1)
            for mid in all_match_ids:
                if bet_id in mid:
                    row = csv_lookup.get((mid, strategy_key))
                    if row:
                        return row, mid
            # Match found but strategy not in CSV
            for mid in all_match_ids:
                if bet_id in mid:
                    return None, mid

    # Fuzzy match on match name
    if match_text:
        norm = match_text.lower()
        norm = re.sub(r'[^a-z0-9 ]', ' ', norm)
        parts = [p for p in norm.split() if len(p) > 3]

        best_mid = None
        best_score = 0
        for mid in all_match_ids:
            score = sum(1 for p in parts if p in mid)
            if score > best_score:
                best_score = score
                best_mid = mid

        if best_mid and best_score >= 1:
            row = csv_lookup.get((best_mid, strategy_key))
            if row:
                return row, best_mid
            return None, best_mid

    return None, ''

def extract_minute(text):
    m = re.search(r'Min\s+(\d+)', text)
    if m:
        return m.group(1)
    return ''

def extract_odds(text):
    m = re.search(r'@\s*([\d.]+)\s*@', text)
    if m:
        return m.group(1)
    m = re.search(r'@\s*([\d.]+)', text)
    if m:
        return m.group(1)
    return ''

def extract_score(text):
    m = re.search(r'Score:\s*(\d+-\d+)', text)
    if m:
        return m.group(1)
    m = re.search(r'\|\s*(\d+-\d+)\s*\|', text)
    if m:
        return m.group(1)
    return ''

def extract_market(text):
    m = re.search(r'[💰]\s+((?:BACK|LAY)\s+[A-Z0-9./\s]+?)\s*@', text)
    if m:
        return m.group(1).strip()
    m = re.search(r'[·]\s+((?:BACK|LAY)\s+[A-Z0-9./\s]+?)\s*@', text)
    if m:
        return m.group(1).strip()
    return ''

# Build results table
SEP = '-' * 160
print()
print(SEP)
header = f"{'#':>4} | {'Timestamp (UTC+1)':19} | {'Match':28} | {'Strategy Label':28} | {'Mkt':22} | {'Odds':5} | {'Min':4} | {'Scr':5} | {'InCSV':5} | {'Won':5} | {'P/L':6} | match_id_slug"
print(header)
print(SEP)

results = []
for i, a in enumerate(bet_alerts):
    ts = a['ts']
    text = a['text']
    link = a['link']

    strat_key, strat_label = extract_strategy_key(text)
    match_text = extract_match_from_text(text)
    minute = extract_minute(text)
    odds = extract_odds(text)
    score = extract_score(text)
    market = extract_market(text)

    csv_row, found_mid = find_csv_row(match_text, link, strat_key)

    found = 'YES' if csv_row else ('MID' if found_mid else 'NO')
    won = csv_row['won'] if csv_row else '-'
    pl = csv_row['pl'] if csv_row else '-'
    mid_display = found_mid[:55] if found_mid else '-'

    results.append({
        'num': i+1, 'ts': ts[:19], 'match': match_text, 'strategy_label': strat_label,
        'strategy_key': strat_key or '', 'market': market, 'odds': odds, 'minute': minute,
        'score': score, 'found': found, 'won': won, 'pl': pl, 'match_id': mid_display
    })

    mt = match_text[:26]
    sl = (strat_label or '-')[:26]
    mk = market[:20]
    print(f"{i+1:>4} | {ts[:19]:19} | {mt:28} | {sl:28} | {mk:22} | {odds:5} | {minute:4} | {score:5} | {found:5} | {won:5} | {pl:6} | {mid_display}")

print(SEP)

total = len(results)
found_yes = sum(1 for r in results if r['found'] == 'YES')
found_mid_count = sum(1 for r in results if r['found'] == 'MID')
found_no = sum(1 for r in results if r['found'] == 'NO')
won_count = sum(1 for r in results if r['won'] == 'True')
lost_count = sum(1 for r in results if r['won'] == 'False')
total_pl = sum(float(r['pl']) for r in results if r['pl'] not in ('-', ''))

print(f"\nSUMMARY:")
print(f"  Total Telegram alerts (excl. test): {total}")
print(f"  Matched in CSV (match+strategy):    {found_yes}")
print(f"  Match found, strategy not in CSV:   {found_mid_count}")
print(f"  Not found at all:                   {found_no}")
print(f"  Won (of matched):                   {won_count}")
print(f"  Lost (of matched):                  {lost_count}")
print(f"  Total P/L (of matched):             {total_pl:.2f}")

# Also show unmatched alerts
print("\nUNMATCHED / MID-ONLY alerts:")
for r in results:
    if r['found'] != 'YES':
        print(f"  #{r['num']} [{r['ts']}] {r['match'][:35]} | {r['strategy_label'][:28]} | found={r['found']} | mid={r['match_id']}")
