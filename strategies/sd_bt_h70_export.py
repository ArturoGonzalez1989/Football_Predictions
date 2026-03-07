"""Re-export H70 with best config: min=65-85, maxLead=3, favMax=2.5"""
import os, glob, csv, math, json

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "betfair_scraper", "data")
STAKE = 10.0

def _f(val):
    try:
        v = float(val)
        return v if not math.isnan(v) else None
    except (TypeError, ValueError):
        return None

def _i(val):
    v = _f(val)
    return int(v) if v is not None else None

def pl_back(odds, won):
    return round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

pattern = os.path.join(DATA_DIR, "partido_*.csv")
files = glob.glob(pattern)
matches = []
for fpath in files:
    rows = []
    try:
        with open(fpath, encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                rows.append(row)
    except Exception:
        continue
    if len(rows) < 5:
        continue
    last = rows[-1]
    gl = _i(last.get("goles_local", ""))
    gv = _i(last.get("goles_visitante", ""))
    if gl is None or gv is None:
        continue
    matches.append({
        "match_id": os.path.basename(fpath).replace("partido_", "").replace(".csv", ""),
        "league": last.get("Liga", "?"),
        "ft_local": gl, "ft_visitante": gv, "ft_total": gl + gv,
        "rows": rows,
        "timestamp_first": rows[0].get("timestamp_utc", ""),
    })

# Best config: min=65-85, maxLead=3, favMax=2.5
bets = []
for m in matches:
    r0 = m["rows"][0]
    bh0 = _f(r0.get("back_home", ""))
    ba0 = _f(r0.get("back_away", ""))
    if bh0 is None or ba0 is None or bh0 >= ba0:
        continue
    if bh0 > 2.5:
        continue
    triggered = False
    for r in m["rows"]:
        if triggered:
            break
        mn = _f(r.get("minuto", ""))
        if mn is None or not (65 <= mn <= 85):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None:
            continue
        lead = gl - gv
        if lead < 1 or lead > 3:
            continue
        bh = _f(r.get("back_home", ""))
        if bh is None or bh < 1.05 or bh > 10.0:
            continue
        won = m["ft_local"] > m["ft_visitante"]
        bets.append({
            "match_id": m["match_id"],
            "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
            "minuto": mn,
            "odds": bh,
            "won": won,
            "pl": pl_back(bh, won),
            "league": m["league"],
            "bet_type": "back",
        })
        triggered = True

outpath = os.path.join(os.path.dirname(__file__), "sd_bt_h70_bets.json")
with open(outpath, "w", encoding="utf-8") as f:
    json.dump({"hypothesis": "H70", "params": "min=65-85, maxLead=3, favMax=2.5", "bets": bets}, f, ensure_ascii=False, indent=2)
print(f"H70: {len(bets)} bets exported to {outpath}")

# Also export H71 best: min=65-85, maxXG=2.0
bets71 = []
for m in matches:
    triggered = False
    for r in m["rows"]:
        if triggered:
            break
        mn = _f(r.get("minuto", ""))
        if mn is None or not (65 <= mn <= 85):
            continue
        gl = _i(r.get("goles_local", ""))
        gv = _i(r.get("goles_visitante", ""))
        if gl is None or gv is None or gl + gv != 3:
            continue
        xgl = _f(r.get("xg_local", ""))
        xgv = _f(r.get("xg_visitante", ""))
        if xgl is None or xgv is None or xgl + xgv > 2.0:
            continue
        u45 = _f(r.get("back_under45", ""))
        if u45 is None or u45 < 1.05 or u45 > 10.0:
            continue
        won = m["ft_total"] <= 4
        bets71.append({
            "match_id": m["match_id"],
            "timestamp": r.get("timestamp_utc", m["timestamp_first"]),
            "minuto": mn,
            "odds": u45,
            "won": won,
            "pl": pl_back(u45, won),
            "league": m["league"],
            "bet_type": "back",
        })
        triggered = True

outpath71 = os.path.join(os.path.dirname(__file__), "sd_bt_h71_bets.json")
with open(outpath71, "w", encoding="utf-8") as f:
    json.dump({"hypothesis": "H71", "params": "min=65-85, maxXG=2.0", "bets": bets71}, f, ensure_ascii=False, indent=2)
print(f"H71: {len(bets71)} bets exported to {outpath71}")
