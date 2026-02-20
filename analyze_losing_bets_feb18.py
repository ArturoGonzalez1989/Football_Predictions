import csv, os

data_dir = r'c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data'

def fv(v):
    try: return float(v) if v and v.strip() else None
    except: return None

# Exact filenames from first search
files = {
    "MILAN-COMO": "partido_ac-mil%C3%A1n-como-apuestas-35274228.csv",
    "WIGAN-LUTON": "partido_wigan-luton-apuestas-35268033.csv",
    "GRIMSBY-WALSALL": "partido_grimsby-walsall-apuestas-35256480.csv",
}

# Bet times (from Betfair screenshot, UTC):
# Milan-Como: Over2.5 bet at 22:20:27 UTC
# Wigan-Luton: Draw bet at 22:04:15 UTC, Over1.5 bet at 22:18:55 UTC  
# Grimsby-Walsall: Over4.5 bet at 22:19:59 UTC, Over3.5 (WON) at 22:16:24 UTC

for label, fname in files.items():
    path = os.path.join(data_dir, fname)
    with open(path, encoding='utf-8', errors='replace') as f:
        rows = list(csv.DictReader(f))
    
    print(f"\n{'='*110}")
    print(f"{label} | {fname} | {len(rows)} filas")
    
    # Show FIRST row timestamp (to understand timezone)
    if rows:
        first_ts = rows[0].get('timestamp_utc','')
        last_ts = rows[-1].get('timestamp_utc','')
        print(f"  Primera fila: {first_ts} | Ultima fila: {last_ts}")
    
    print()
    if label == "MILAN-COMO":
        print(f"{'Timestamp_utc':<25} {'Min':>5} {'Score':>6} {'O15b':>7} {'O25b':>7} {'O25l':>7} {'O35b':>7} {'Estado':<15}")
        print("-"*110)
        for r in rows:
            ts = r.get('timestamp_utc','')
            mn = fv(r.get('minuto',''))
            gl = int(fv(r.get('goles_local','')) or 0)
            gv = int(fv(r.get('goles_visitante','')) or 0)
            o15b = fv(r.get('back_over15',''))
            o25b = fv(r.get('back_over25',''))
            o25l = fv(r.get('lay_over25',''))
            o35b = fv(r.get('back_over35',''))
            est = r.get('estado_partido','')
            marker = " <<< APUESTA 22:20" if "22:20" in ts else ""
            if mn is not None and mn >= 40:
                print(f"{ts:<25} {mn:>5.1f} {gl}-{gv:>3} {o15b or 0:>7.2f} {o25b or 0:>7.2f} {o25l or 0:>7.2f} {o35b or 0:>7.2f} {est:<15}{marker}")

    elif label == "WIGAN-LUTON":
        print(f"{'Timestamp_utc':<25} {'Min':>5} {'Score':>6} {'DrawB':>7} {'DrawL':>7} {'O15b':>7} {'O15l':>7} {'O25b':>7} {'Estado':<15}")
        print("-"*110)
        for r in rows:
            ts = r.get('timestamp_utc','')
            mn = fv(r.get('minuto',''))
            gl = int(fv(r.get('goles_local','')) or 0)
            gv = int(fv(r.get('goles_visitante','')) or 0)
            db = fv(r.get('back_draw',''))
            dl = fv(r.get('lay_draw',''))
            o15b = fv(r.get('back_over15',''))
            o15l = fv(r.get('lay_over15',''))
            o25b = fv(r.get('back_over25',''))
            est = r.get('estado_partido','')
            markers = []
            if "22:04" in ts: markers.append("<<< BET DRAW @2.06")
            if "22:18" in ts: markers.append("<<< BET O1.5 @2.16")
            if "22:03" in ts or "22:05" in ts: markers.append("~BET DRAW")
            if "22:17" in ts or "22:19" in ts: markers.append("~BET O1.5")
            marker = " ".join(markers)
            if mn is not None and mn >= 50:
                print(f"{ts:<25} {mn:>5.1f} {gl}-{gv:>3} {db or 0:>7.2f} {dl or 0:>7.2f} {o15b or 0:>7.2f} {o15l or 0:>7.2f} {o25b or 0:>7.2f} {est:<15}  {marker}")

    elif label == "GRIMSBY-WALSALL":
        print(f"{'Timestamp_utc':<25} {'Min':>5} {'Score':>6} {'O35b':>7} {'O35l':>7} {'O45b':>7} {'O45l':>7} {'Estado':<15}")
        print("-"*110)
        for r in rows:
            ts = r.get('timestamp_utc','')
            mn = fv(r.get('minuto',''))
            gl = int(fv(r.get('goles_local','')) or 0)
            gv = int(fv(r.get('goles_visitante','')) or 0)
            o35b = fv(r.get('back_over35',''))
            o35l = fv(r.get('lay_over35',''))
            o45b = fv(r.get('back_over45',''))
            o45l = fv(r.get('lay_over45',''))
            est = r.get('estado_partido','')
            markers = []
            if "22:16" in ts: markers.append("<<< BET O3.5 @1.66 (GANADA)")
            if "22:19" in ts: markers.append("<<< BET O4.5 @1.74 (PERDIDA)")
            if "22:15" in ts or "22:17" in ts: markers.append("~O3.5 bet")
            if "22:18" in ts or "22:20" in ts: markers.append("~O4.5 bet")
            marker = " ".join(markers)
            if mn is not None and mn >= 55:
                print(f"{ts:<25} {mn:>5.1f} {gl}-{gv:>3} {o35b or 0:>7.2f} {o35l or 0:>7.2f} {o45b or 0:>7.2f} {o45l or 0:>7.2f} {est:<15}  {marker}")
