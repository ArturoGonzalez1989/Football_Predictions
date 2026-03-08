"""
R13 Final: Export best bets for the 3 strongest hypotheses for realistic validation.
H77: BACK CS 1-1 Late (min 75-90, odds_max=8.0)
H79: BACK CS 2-0/0-2 Late (min 75-90, odds_max=10.0)
H81: BACK CS 3-0/0-3 + 3-1/1-3 Late (min 70-85, odds_max=8.0) -- separate from H79
Also: Combined CS Big Lead (2-0/0-2/3-1/1-3/3-0/0-3) as H82 for portfolio view

Discarded:
H78: O3.5 FH -- test ROI=0.5%, fails realistic threshold
H80: Home leading FH -- test ROI=1.9%, fails realistic threshold
"""
import os, glob, csv, math, json
from collections import defaultdict, Counter

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

def wilson_ci95(n, wins):
    if n == 0: return (0.0, 0.0)
    z = 1.96; p = wins / n
    denom = 1 + z*z/n
    centre = (p + z*z/(2*n)) / denom
    margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denom
    return (round(max(0, centre - margin)*100, 1), round(min(1, centre + margin)*100, 1))

def max_drawdown(pls):
    cum = peak = dd = 0
    for pl in pls:
        cum += pl; peak = max(peak, cum); dd = max(dd, peak - cum)
    return round(dd, 2)

def sharpe_ratio(pls):
    if len(pls) < 2: return 0.0
    mean = sum(pls)/len(pls)
    var = sum((p-mean)**2 for p in pls) / (len(pls)-1)
    std = math.sqrt(var) if var > 0 else 0.001
    return round(mean/std * math.sqrt(len(pls)), 2)

def pl_back(odds, won):
    return round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

def load_matches():
    pattern = os.path.join(DATA_DIR, "partido_*.csv")
    files = glob.glob(pattern)
    matches = []
    for fpath in files:
        rows = []
        try:
            with open(fpath, encoding="utf-8", errors="replace") as f:
                for row in csv.DictReader(f): rows.append(row)
        except Exception: continue
        if len(rows) < 5: continue
        last = rows[-1]
        gl = _i(last.get("goles_local", "")); gv = _i(last.get("goles_visitante", ""))
        if gl is None or gv is None: continue
        matches.append({
            "file": os.path.basename(fpath),
            "match_id": os.path.basename(fpath).replace("partido_","").replace(".csv",""),
            "country": last.get("País", "?"), "league": last.get("Liga", "?"),
            "ft_local": gl, "ft_visitante": gv, "ft_total": gl + gv,
            "rows": rows, "timestamp_first": rows[0].get("timestamp_utc", ""),
        })
    return matches

def full_stats(bets, label=""):
    if not bets: print(f"  {label}: N=0"); return None
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    wr = wins/n*100
    total_pl = sum(b["pl"] for b in bets)
    avg_odds = sum(b["odds"] for b in bets) / n
    roi = total_pl / (n * STAKE) * 100
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    leagues = set(b.get("league","?") for b in bets)
    sorted_b = sorted(bets, key=lambda b: b.get("timestamp",""))
    split = int(n * 0.7)
    train, test = sorted_b[:split], sorted_b[split:]
    train_roi = round(sum(b["pl"] for b in train) / (len(train)*STAKE)*100, 1) if train else 0
    test_roi = round(sum(b["pl"] for b in test) / (len(test)*STAKE)*100, 1) if test else 0
    md = max_drawdown(pls); sh = sharpe_ratio(pls)
    print(f"  {label}: N={n}, WR={wr:.1f}%, ROI={roi:.1f}%, P/L={total_pl:.2f}, "
          f"avg_odds={avg_odds:.2f}, IC95=[{ci_lo},{ci_hi}], MaxDD={md}, Sharpe={sh}, "
          f"Leagues={len(leagues)}, Train={train_roi}%, Test={test_roi}%")

    # Overlap check with existing CS strategies
    match_ids = set(b["match_id"] for b in bets)
    return {"n": n, "wins": wins, "match_ids": match_ids,
            "wr": round(wr,1), "roi": round(roi,1), "sharpe": sh,
            "train_roi": train_roi, "test_roi": test_roi,
            "ci_lo": ci_lo, "ci_hi": ci_hi, "max_dd": md,
            "avg_odds": round(avg_odds, 2), "leagues": len(leagues),
            "league_list": sorted(leagues), "n_train": len(train), "n_test": len(test)}


matches = load_matches()
print(f"Loaded {len(matches)} matches\n")


# ===== H77: BACK CS 1-1 Late (min 75-90, odds_max=8.0) =====
print("=" * 70)
print("H77: BACK CS 1-1 Late")
print("=" * 70)

h77_bets = []
for m in matches:
    triggered = False
    for row in m["rows"]:
        mi = _f(row.get("minuto",""))
        if mi is None or mi < 75 or mi > 90: continue
        gl = _i(row.get("goles_local","")); gv = _i(row.get("goles_visitante",""))
        if gl != 1 or gv != 1: continue
        cs_odds = _f(row.get("back_rc_1_1",""))
        if cs_odds is None or cs_odds < 1.05 or cs_odds > 8.0: continue
        if not triggered:
            triggered = True
            won = m["ft_local"] == 1 and m["ft_visitante"] == 1
            h77_bets.append({
                "match_id": m["match_id"], "won": won,
                "pl": pl_back(cs_odds, won), "odds": cs_odds,
                "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                "minuto": mi, "league": m["league"], "bet_type": "back",
            })
            break

h77_stats = full_stats(h77_bets, "H77 CS 1-1")


# ===== H79: BACK CS 2-0/0-2 Late (min 75-90, odds_max=10.0) =====
print("\n" + "=" * 70)
print("H79: BACK CS 2-0/0-2 Late")
print("=" * 70)

h79_bets = []
for m in matches:
    triggered = False
    for row in m["rows"]:
        mi = _f(row.get("minuto",""))
        if mi is None or mi < 75 or mi > 90: continue
        gl = _i(row.get("goles_local","")); gv = _i(row.get("goles_visitante",""))
        if gl is None or gv is None: continue
        cs_col = None; ft_match = False
        if gl == 2 and gv == 0:
            cs_col = "back_rc_2_0"; ft_match = m["ft_local"]==2 and m["ft_visitante"]==0
        elif gl == 0 and gv == 2:
            cs_col = "back_rc_0_2"; ft_match = m["ft_local"]==0 and m["ft_visitante"]==2
        else: continue
        cs_odds = _f(row.get(cs_col,""))
        if cs_odds is None or cs_odds < 1.05 or cs_odds > 10.0: continue
        if not triggered:
            triggered = True
            h79_bets.append({
                "match_id": m["match_id"], "won": ft_match,
                "pl": pl_back(cs_odds, ft_match), "odds": cs_odds,
                "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                "minuto": mi, "league": m["league"], "bet_type": "back",
                "score": f"{gl}-{gv}",
            })
            break

h79_stats = full_stats(h79_bets, "H79 CS 2-0/0-2")


# ===== H81: BACK CS 3-0/0-3 + 3-1/1-3 Late (min 70-85, odds_max=8.0) =====
print("\n" + "=" * 70)
print("H81: BACK CS 3-0/0-3 + 3-1/1-3 Late")
print("=" * 70)

SCORELINES_H81 = [(3,0), (0,3), (3,1), (1,3)]
h81_bets = []
for m in matches:
    triggered = False
    for row in m["rows"]:
        mi = _f(row.get("minuto",""))
        if mi is None or mi < 70 or mi > 85: continue
        gl = _i(row.get("goles_local","")); gv = _i(row.get("goles_visitante",""))
        if gl is None or gv is None: continue
        matched = None
        for sl, sv in SCORELINES_H81:
            if gl == sl and gv == sv: matched = (sl, sv); break
        if matched is None: continue
        cs_col = f"back_rc_{matched[0]}_{matched[1]}"
        cs_odds = _f(row.get(cs_col,""))
        if cs_odds is None or cs_odds < 1.05 or cs_odds > 8.0: continue
        if not triggered:
            triggered = True
            ft_match = m["ft_local"]==matched[0] and m["ft_visitante"]==matched[1]
            h81_bets.append({
                "match_id": m["match_id"], "won": ft_match,
                "pl": pl_back(cs_odds, ft_match), "odds": cs_odds,
                "timestamp": row.get("timestamp_utc", m["timestamp_first"]),
                "minuto": mi, "league": m["league"], "bet_type": "back",
                "score": f"{matched[0]}-{matched[1]}",
            })
            break

h81_stats = full_stats(h81_bets, "H81 CS 3-0/0-3+3-1/1-3")


# ===== Overlap Analysis =====
print("\n" + "=" * 70)
print("OVERLAP ANALYSIS")
print("=" * 70)

# Check overlap between H77, H79, H81 (all CS market, different scores)
if h77_stats and h79_stats:
    overlap_77_79 = len(h77_stats["match_ids"] & h79_stats["match_ids"])
    print(f"H77 vs H79: {overlap_77_79} match overlap "
          f"({overlap_77_79/h77_stats['n']*100:.1f}% of H77, {overlap_77_79/h79_stats['n']*100:.1f}% of H79)")
    print(f"  -> Different scores (1-1 vs 2-0/0-2), zero market overlap by definition")

if h77_stats and h81_stats:
    overlap_77_81 = len(h77_stats["match_ids"] & h81_stats["match_ids"])
    print(f"H77 vs H81: {overlap_77_81} match overlap")

if h79_stats and h81_stats:
    overlap_79_81 = len(h79_stats["match_ids"] & h81_stats["match_ids"])
    print(f"H79 vs H81: {overlap_79_81} match overlap "
          f"({overlap_79_81/h79_stats['n']*100:.1f}% of H79, {overlap_79_81/h81_stats['n']*100:.1f}% of H81)")

# Overlap with existing CS strategies (H49: 2-1/1-2, H53: 1-0/0-1)
print("\nOverlap with EXISTING CS strategies (match level):")
# We need to simulate H49 and H53 triggers
h49_ids = set()  # CS 2-1/1-2
h53_ids = set()  # CS 1-0/0-1
h58_ids = set()  # Draw 1-1

for m in matches:
    for row in m["rows"]:
        mi = _f(row.get("minuto",""))
        if mi is None or mi < 68 or mi > 85: continue
        gl = _i(row.get("goles_local","")); gv = _i(row.get("goles_visitante",""))
        if gl is None or gv is None: continue
        # H49: CS 2-1 or 1-2
        if (gl == 2 and gv == 1) or (gl == 1 and gv == 2):
            h49_ids.add(m["match_id"]); break
        # H53: CS 1-0 or 0-1
        if (gl == 1 and gv == 0) or (gl == 0 and gv == 1):
            h53_ids.add(m["match_id"]); break
    # H58: Draw 1-1
    for row in m["rows"]:
        mi = _f(row.get("minuto",""))
        if mi is None or mi < 70 or mi > 85: continue
        gl = _i(row.get("goles_local","")); gv = _i(row.get("goles_visitante",""))
        if gl == 1 and gv == 1:
            h58_ids.add(m["match_id"]); break

if h77_stats:
    o_h49 = len(h77_stats["match_ids"] & h49_ids)
    o_h53 = len(h77_stats["match_ids"] & h53_ids)
    o_h58 = len(h77_stats["match_ids"] & h58_ids)
    print(f"  H77 vs H49 (CS 2-1/1-2): {o_h49} matches ({o_h49/h77_stats['n']*100:.1f}%)")
    print(f"  H77 vs H53 (CS 1-0/0-1): {o_h53} matches ({o_h53/h77_stats['n']*100:.1f}%)")
    print(f"  H77 vs H58 (Draw 1-1):   {o_h58} matches ({o_h58/h77_stats['n']*100:.1f}%) -- SAME score but DIFFERENT market!")

if h79_stats:
    o_h49 = len(h79_stats["match_ids"] & h49_ids)
    o_h53 = len(h79_stats["match_ids"] & h53_ids)
    o_h55 = len(h79_stats["match_ids"])  # H55 IS H79 revisited
    print(f"  H79 vs H49: {o_h49} matches ({o_h49/h79_stats['n']*100:.1f}%)")
    print(f"  H79 vs H53: {o_h53} matches ({o_h53/h79_stats['n']*100:.1f}%)")
    print(f"  H79 IS H55 revisited with new data + params")

if h81_stats:
    o_h49 = len(h81_stats["match_ids"] & h49_ids)
    o_h65 = len(h81_stats["match_ids"])  # H65 covers 3-0/0-3 subset
    print(f"  H81 vs H49: {o_h49} matches ({o_h49/h81_stats['n']*100:.1f}%)")
    print(f"  H81 extends H65 (3-0/0-3 only) by adding 3-1/1-3")


# ===== Export for realistic validation =====
print("\n" + "=" * 70)
print("EXPORTING FOR REALISTIC VALIDATION")
print("=" * 70)

for name, bets_list in [("h77", h77_bets), ("h79", h79_bets), ("h81", h81_bets)]:
    if bets_list:
        outpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "aux", f"sd_bt_{name}_bets.json")
        os.makedirs(os.path.dirname(outpath), exist_ok=True)
        with open(outpath, "w", encoding="utf-8") as f:
            json.dump({"bets": bets_list}, f, ensure_ascii=False, indent=2)
        print(f"  {name}: {len(bets_list)} bets exported")


# ===== Score breakdown for each =====
print("\n" + "=" * 70)
print("SCORE BREAKDOWN")
print("=" * 70)

for name, bets_list in [("H79", h79_bets), ("H81", h81_bets)]:
    if bets_list:
        scores = Counter(b.get("score","?") for b in bets_list)
        print(f"\n{name} by scoreline:")
        for sc, cnt in scores.most_common():
            wins = sum(1 for b in bets_list if b.get("score") == sc and b["won"])
            wr = wins/cnt*100 if cnt > 0 else 0
            avg_o = sum(b["odds"] for b in bets_list if b.get("score") == sc) / cnt
            print(f"  {sc}: N={cnt}, WR={wr:.1f}%, avg_odds={avg_o:.2f}")

print("\nDone.")
