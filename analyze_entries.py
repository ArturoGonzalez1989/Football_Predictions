import csv, os

data_dir = r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data'

def fv(v):
    try: return float(v) if v and v.strip() else None
    except: return None

def load(fname):
    path = os.path.join(data_dir, fname)
    with open(path, encoding='utf-8', errors='replace') as f:
        return list(csv.DictReader(f))

# =========== 1. MILAN-COMO ===========
rows = load("partido_ac-mil%C3%A1n-como-apuestas-35274228.csv")
print("="*90)
print("MILAN-COMO | Over2.5 @1.79 | Bet 22:20 UTC")
print("Corr. CSV: ~21:20 local. Match ended 1-1. Score evolution:")
print()
print(f"{'TS':<22} {'Min':>5} {'Score':>6} {'O15b':>7} {'O25b':>7} {'O25lay':>7} {'O35b':>7} {'Estado'}")

prev_score = None
for r in rows:
    ts = r.get('timestamp_utc','')
    mn = fv(r.get('minuto',''))
    gl = int(fv(r.get('goles_local','')) or 0)
    gv = int(fv(r.get('goles_visitante','')) or 0)
    score = f"{gl}-{gv}"
    o15b = fv(r.get('back_over15',''))
    o25b = fv(r.get('back_over25',''))
    o25l = fv(r.get('lay_over25',''))
    o35b = fv(r.get('back_over35',''))
    est = r.get('estado_partido','')
    # Show every row in 2nd half + mark score changes
    goal_marker = " <<< GOL" if score != prev_score and prev_score is not None else ""
    bet_marker = " <<< APUESTA" if "21:20" in ts or "21:21" in ts else ""
    prev_score = score
    if mn is not None and mn >= 45:
        print(f"{ts:<22} {mn:>5.1f} {score:>6} {o15b or 0:>7.2f} {o25b or 0:>7.2f} {o25l or 0:>7.2f} {o35b or 0:>7.2f} {est}{goal_marker}{bet_marker}")

# =========== 2. WIGAN-LUTON ===========
rows2 = load("partido_wigan-luton-apuestas-35268033.csv")
print()
print("="*90)
print("WIGAN-LUTON | Draw @2.06 bet 22:04 UTC (~21:04 CSV), Over1.5 @2.16 bet 22:18 UTC (~21:18)")
print()
print(f"{'TS':<22} {'Min':>5} {'Score':>6} {'DrawB':>7} {'DrawL':>7} {'O15b':>7} {'O15l':>7} {'O25b':>7} {'Estado'}")
prev_score = None
for r in rows2:
    ts = r.get('timestamp_utc','')
    mn = fv(r.get('minuto',''))
    gl = int(fv(r.get('goles_local','')) or 0)
    gv = int(fv(r.get('goles_visitante','')) or 0)
    score = f"{gl}-{gv}"
    db = fv(r.get('back_draw',''))
    dl = fv(r.get('lay_draw',''))
    o15b = fv(r.get('back_over15',''))
    o15l = fv(r.get('lay_over15',''))
    o25b = fv(r.get('back_over25',''))
    est = r.get('estado_partido','')
    markers = []
    if score != prev_score and prev_score is not None: markers.append("<<< GOL")
    if "21:04" in ts or "21:03" in ts or "21:05" in ts: markers.append("~BET DRAW @2.06")
    if "21:18" in ts or "21:17" in ts or "21:19" in ts: markers.append("~BET O1.5 @2.16")
    prev_score = score
    if mn is not None and mn >= 50:
        print(f"{ts:<22} {mn:>5.1f} {score:>6} {db or 0:>7.2f} {dl or 0:>7.2f} {o15b or 0:>7.2f} {o15l or 0:>7.2f} {o25b or 0:>7.2f} {est}  {'  '.join(markers)}")

# =========== 3. GRIMSBY-WALSALL ===========
rows3 = load("partido_grimsby-walsall-apuestas-35256480.csv")
print()
print("="*90)
print("GRIMSBY-WALSALL | Over3.5 @1.66 bet 22:16 (~21:16, GANADA) | Over4.5 @1.74 bet 22:19 (~21:19, PERDIDA)")
print()
print(f"{'TS':<22} {'Min':>5} {'Score':>6} {'O35b':>7} {'O35l':>7} {'O45b':>7} {'O45l':>7} {'Estado'}")
prev_score = None
for r in rows3:
    ts = r.get('timestamp_utc','')
    mn = fv(r.get('minuto',''))
    gl = int(fv(r.get('goles_local','')) or 0)
    gv = int(fv(r.get('goles_visitante','')) or 0)
    score = f"{gl}-{gv}"
    o35b = fv(r.get('back_over35',''))
    o35l = fv(r.get('lay_over35',''))
    o45b = fv(r.get('back_over45',''))
    o45l = fv(r.get('lay_over45',''))
    est = r.get('estado_partido','')
    markers = []
    if score != prev_score and prev_score is not None: markers.append("<<< GOL")
    if "21:16" in ts or "21:15" in ts or "21:17" in ts: markers.append("~BET O3.5 @1.66 (WON)")
    if "21:19" in ts or "21:20" in ts or "21:22" in ts: markers.append("~BET O4.5 @1.74 (LOST)")
    prev_score = score
    if mn is not None and mn >= 55:
        print(f"{ts:<22} {mn:>5.1f} {score:>6} {o35b or 0:>7.2f} {o35l or 0:>7.2f} {o45b or 0:>7.2f} {o45l or 0:>7.2f} {est}  {'  '.join(markers)}")
