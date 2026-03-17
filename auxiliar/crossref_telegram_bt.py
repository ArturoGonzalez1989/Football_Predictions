import sys, re, csv, webbrowser
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from html import escape

# ── placed_bets.csv (source of real paper-trading results) ──────────────────
_placed_path = Path('C:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/betfair_scraper/placed_bets.csv')
placed_rows = []
with open(_placed_path, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        placed_rows.append(row)

# Build lookups
placed_lookup = {}   # (ev_id, strategy_key) → row
ev_to_match  = {}    # ev_id → match_name  (for MID rows)
for r in placed_rows:
    slug_m = re.search(r'apuestas-(\d+)', r['match_id'])
    if slug_m:
        ev_id = slug_m.group(1)
        placed_lookup[(ev_id, r['strategy'])] = r
        ev_to_match[ev_id] = r['match_name']

print(f"Loaded placed_bets.csv: {len(placed_rows)} bets")

# ── Telegram export ─────────────────────────────────────────────────────────
_tg_candidates = sorted(
    Path('C:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/ChatExport').glob('messages*.html'),
    reverse=True
)
if not _tg_candidates:
    raise FileNotFoundError("No messages*.html found in ChatExport/")
_tg_path = _tg_candidates[0]
print(f"Using Telegram export: {_tg_path}")
content = _tg_path.read_text(encoding='utf-8')

# Dividir en bloques por mensaje (más robusto que un único regex multi-div)
msg_block_pattern = re.compile(
    r'<div class="message[^"]*"[^>]*>.*?(?=<div class="message[^"]*"[^>]*>|$)',
    re.DOTALL
)
title_pattern = re.compile(r'title=\"(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}[^\"]*)\"')
text_pattern  = re.compile(r'<div class=\"text\">(.*?)</div>', re.DOTALL)

raw_alerts = []
for block_m in msg_block_pattern.finditer(content):
    block = block_m.group(0)
    t_m = title_pattern.search(block)
    x_m = text_pattern.search(block)
    if not t_m or not x_m:
        continue
    ts = t_m.group(1)
    raw_text = x_m.group(1)
    link_match = re.search(r'href=\"([^\"]+)\"', block)
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
    'BACK CS 1-1 Late': 'cs_11',
    'BACK CS 1-1': 'cs_11',
    'BACK CS 2-0/0-2': 'cs_20',
    'Odds Drift Contrarian': 'odds_drift',
    'BACK Longshot Leading': 'longshot',
    'BACK CS Close': 'cs_close',
    'LAY Over 4.5 v3': 'lay_over45_v3',
    'LAY Over 4.5 V3': 'lay_over45_v3',
    'BACK O2.5 Two Goals': 'over25_2goals',
    'BACK Draw Equalizer Late': 'draw_equalizer',
    'BACK Over 3.5 Early Goals': 'over35_early_goals',
    'BACK CS Big Lead': 'cs_big_lead',
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
    for k, v in STRAT_MAP.items():
        if text.startswith(k) or text.startswith('🟢 ' + k) or text.startswith('🔴 ' + k):
            return v, k
    for k, v in STRAT_MAP.items():
        if k in text[:80]:
            return v, k
    return None, ''

def extract_minute(text):
    m = re.search(r'Min\s+(\d+)', text)
    return m.group(1) if m else ''

def extract_odds(text):
    m = re.search(r'@\s*([\d.]+)\s*@', text)
    if m: return m.group(1)
    m = re.search(r'@\s*([\d.]+)', text)
    return m.group(1) if m else ''

def extract_score(text):
    m = re.search(r'Score:\s*(\d+-\d+)', text)
    if m: return m.group(1)
    m = re.search(r'\|\s*(\d+-\d+)\s*\|', text)
    return m.group(1) if m else ''

def find_placed_bet(link, strategy_key):
    if not strategy_key or not link:
        return None, ''
    slug_m = re.search(r'apuestas-(\d+)', link)
    if not slug_m:
        return None, ''
    ev_id = slug_m.group(1)
    row = placed_lookup.get((ev_id, strategy_key))
    if row:
        return row, ev_id
    for k in placed_lookup:
        if k[0] == ev_id:
            return None, ev_id
    return None, ''

# ── Build results ────────────────────────────────────────────────────────────
results = []
seen_bets = set()
cumpl = 0.0

for i, a in enumerate(bet_alerts):
    ts, text, link = a['ts'], a['text'], a['link']
    strat_key, strat_label = extract_strategy_key(text)
    minute = extract_minute(text)
    odds   = extract_odds(text)
    score  = extract_score(text)
    hora   = ts[11:16]

    placed_row, found_ev = find_placed_bet(link, strat_key)

    slug_m = re.search(r'apuestas-(\d+)', link) if link else None
    ev_id  = slug_m.group(1) if slug_m else ''
    dedup_key = (ev_id, strat_key)
    is_dup = dedup_key in seen_bets and bool(ev_id)
    if ev_id and strat_key:
        seen_bets.add(dedup_key)

    # Partido: prefer placed_bets name, then ev_id→name map
    if placed_row:
        match_name = placed_row['match_name']
    elif ev_id and ev_id in ev_to_match:
        match_name = ev_to_match[ev_id]
    else:
        match_name = ''

    paper = 'YES' if placed_row else ('MID' if found_ev else 'NO')

    if placed_row:
        result  = 'WIN' if placed_row['result'] == 'won' else 'LOSS'
        pl_val  = float(placed_row['pl'])
        if not is_dup:
            cumpl += pl_val
        pl_str   = f"{pl_val:+.2f}"
        cumpl_str = f"{cumpl:+.2f}"
    else:
        result   = '-'
        pl_str   = '-'
        cumpl_str = f"{cumpl:+.2f}"

    results.append({
        'num': i+1, 'ts': ts[:19], 'hora': hora, 'match': match_name,
        'strategy_label': strat_label or '', 'strategy_key': strat_key or '',
        'odds': odds, 'minute': minute, 'score': score,
        'paper': paper, 'result': result, 'pl': pl_str, 'cumpl': cumpl_str,
        'ev_id': ev_id, 'is_dup': is_dup, 'link': link,
    })

# ── Summaries ────────────────────────────────────────────────────────────────
total   = len(results)
matched = [r for r in results if r['paper'] == 'YES' and not r['is_dup']]
wins    = sum(1 for r in matched if r['result'] == 'WIN')
losses  = sum(1 for r in matched if r['result'] == 'LOSS')
total_pl = sum(float(r['pl']) for r in matched if r['pl'] != '-')
dups    = sum(1 for r in results if r['is_dup'])
mid_only = sum(1 for r in results if r['paper'] == 'MID' and not r['is_dup'])
no_match = sum(1 for r in results if r['paper'] == 'NO' and not r['is_dup'])

n_bets  = len(matched)
roi     = (total_pl / n_bets * 100) if n_bets else 0
avg_pl  = (total_pl / n_bets) if n_bets else 0
gross_wins  = sum(float(r['pl']) for r in matched if r['result'] == 'WIN' and r['pl'] != '-')
gross_losses = abs(sum(float(r['pl']) for r in matched if r['result'] == 'LOSS' and r['pl'] != '-'))
profit_factor = (gross_wins / gross_losses) if gross_losses else float('inf')
placed_odds = [float(r['odds']) for r in matched if r['odds']]
avg_odds = sum(placed_odds) / len(placed_odds) if placed_odds else 0

# Max drawdown from cumulative P/L
cumpl_vals = []
_cum = 0.0
for r in results:
    if r['paper'] == 'YES' and not r['is_dup'] and r['pl'] != '-':
        _cum += float(r['pl'])
        cumpl_vals.append(_cum)
max_dd = 0.0
peak = float('-inf')
for v in cumpl_vals:
    if v > peak:
        peak = v
    dd = v - peak
    if dd < max_dd:
        max_dd = dd

# ── HTML output ──────────────────────────────────────────────────────────────
def row_class(r):
    if r['is_dup']:   return 'dup'
    if r['paper'] == 'MID': return 'mid'
    if r['paper'] == 'NO':  return 'no'
    if r['result'] == 'WIN':  return 'win'
    if r['result'] == 'LOSS': return 'loss'
    return ''

def pl_cell(val):
    if val == '-': return '<td class="num">—</td>'
    f = float(val)
    cls = 'pos' if f > 0 else 'neg'
    return f'<td class="num {cls}">{val}</td>'

rows_html = []
for r in results:
    rc = row_class(r)
    link_html = f'<a href="{escape(r["link"])}" target="_blank">{escape(r["match"])}</a>' if r['link'] and r['match'] else escape(r['match'])
    badge = ''
    if r['is_dup']:       badge = '<span class="badge dup-b">DUP</span>'
    elif r['paper']=='MID': badge = '<span class="badge mid-b">NO PLACED</span>'
    elif r['paper']=='NO':  badge = '<span class="badge no-b">NOT FOUND</span>'

    res_cell = ''
    if r['result'] == 'WIN':  res_cell = '<td><span class="res win-res">WIN</span></td>'
    elif r['result'] == 'LOSS': res_cell = '<td><span class="res loss-res">LOSS</span></td>'
    else:                     res_cell = '<td class="muted">—</td>'

    rows_html.append(f"""
    <tr class="{rc}">
      <td class="num muted">{r['num']}</td>
      <td class="num">{r['hora']}</td>
      <td class="match-cell">{link_html}{badge}</td>
      <td>{escape(r['strategy_label'])}</td>
      <td class="num">{r['odds']}</td>
      <td class="num">{r['minute']}</td>
      <td class="num">{r['score']}</td>
      {res_cell}
      {pl_cell(r['pl'])}
      {pl_cell(r['cumpl'])}
    </tr>""")

pl_color = '#22c55e' if total_pl >= 0 else '#ef4444'

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Señales Telegram — Resultados</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f1117; color: #e2e8f0; padding: 32px 24px; font-size: 13px; }}
  h1 {{ font-size: 20px; font-weight: 600; margin-bottom: 4px; color: #f1f5f9; }}
  .subtitle {{ color: #64748b; margin-bottom: 24px; font-size: 12px; }}

  .stats {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
  .stat {{ background: #1e2130; border: 1px solid #2d3148; border-radius: 10px;
           padding: 14px 20px; min-width: 120px; }}
  .stat .label {{ font-size: 11px; color: #64748b; text-transform: uppercase;
                  letter-spacing: .05em; margin-bottom: 6px; }}
  .stat .value {{ font-size: 22px; font-weight: 700; }}
  .stat.pl .value {{ color: {pl_color}; }}
  .stat.wins .value {{ color: #22c55e; }}
  .stat.losses .value {{ color: #ef4444; }}

  table {{ width: 100%; border-collapse: collapse; }}
  thead th {{ background: #1a1d2e; color: #94a3b8; font-size: 11px; font-weight: 600;
              text-transform: uppercase; letter-spacing: .05em; padding: 10px 12px;
              text-align: left; border-bottom: 2px solid #2d3148; white-space: nowrap; }}
  thead th.num {{ text-align: right; }}
  tbody tr {{ border-bottom: 1px solid #1e2130; transition: background .1s; }}
  tbody tr:hover {{ background: #1a1d2e; }}
  td {{ padding: 9px 12px; vertical-align: middle; }}
  td.num {{ text-align: right; font-variant-numeric: tabular-nums; font-family: 'SF Mono', 'Fira Code', monospace; }}
  td.muted {{ color: #475569; text-align: center; }}

  tr.win   {{ }}
  tr.loss  {{ }}
  tr.dup   {{ opacity: .45; }}
  tr.mid   {{ opacity: .6; }}

  .match-cell a {{ color: #e2e8f0; text-decoration: none; }}
  .match-cell a:hover {{ color: #818cf8; text-decoration: underline; }}

  .res {{ display: inline-block; padding: 2px 8px; border-radius: 4px;
          font-size: 11px; font-weight: 700; letter-spacing: .04em; }}
  .win-res  {{ background: #14532d; color: #4ade80; }}
  .loss-res {{ background: #450a0a; color: #f87171; }}

  .badge {{ display: inline-block; margin-left: 8px; padding: 1px 6px; border-radius: 4px;
            font-size: 10px; font-weight: 600; vertical-align: middle; }}
  .dup-b {{ background: #1e293b; color: #64748b; }}
  .mid-b {{ background: #1c1a2e; color: #818cf8; }}
  .no-b  {{ background: #2d1515; color: #f87171; }}

  .pos {{ color: #4ade80; }}
  .neg {{ color: #f87171; }}
</style>
</head>
<body>
<h1>Señales Telegram — Resultados Paper Trading</h1>
<p class="subtitle">Fuente: Telegram · {total} señales detectadas</p>

<div class="stats">
  <div class="stat"><div class="label">Apuestas</div><div class="value">{n_bets}</div></div>
  <div class="stat wins"><div class="label">Ganadas</div><div class="value">{wins}</div></div>
  <div class="stat losses"><div class="label">Perdidas</div><div class="value">{losses}</div></div>
  <div class="stat pl"><div class="label">P/L Total</div><div class="value">{total_pl:+.2f}</div></div>
  <div class="stat"><div class="label">Win Rate</div><div class="value">{wins/(wins+losses)*100:.0f}%</div></div>
  <div class="stat pl"><div class="label">ROI</div><div class="value">{roi:+.1f}%</div></div>
  <div class="stat pl"><div class="label">P/L por apuesta</div><div class="value">{avg_pl:+.2f}</div></div>
  <div class="stat"><div class="label">Profit Factor</div><div class="value">{profit_factor:.2f}</div></div>
  <div class="stat"><div class="label">Odds media</div><div class="value">{avg_odds:.2f}</div></div>
  <div class="stat losses"><div class="label">Max Drawdown</div><div class="value">{max_dd:+.2f}</div></div>
  <div class="stat"><div class="label">No placed</div><div class="value">{mid_only}</div></div>
</div>

<table>
<thead>
  <tr>
    <th class="num">#</th>
    <th>Hora</th>
    <th>Partido</th>
    <th>Estrategia</th>
    <th class="num">Odds</th>
    <th class="num">Min</th>
    <th class="num">Scr</th>
    <th>Res</th>
    <th class="num">P/L</th>
    <th class="num">P/L Acum</th>
  </tr>
</thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</body>
</html>"""

out_path = Path('C:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/auxiliar/signal_results.html')
out_path.write_text(html, encoding='utf-8')
print(f"\nHTML generado: {out_path}")
webbrowser.open(str(out_path))
