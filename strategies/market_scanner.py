"""
Brute-Force Market Scanner
==========================
Escanea sistemáticamente todas las combinaciones de:
    (mercado × ventana_minutos × estado_marcador × filtro_stats)

y aplica quality gates para descubrir estrategias nuevas que el proceso
manual podría no haber encontrado.

Uso:
    python strategies/market_scanner.py
    python strategies/market_scanner.py --min-roi 12 --out analisis/scan_results.csv

Metodología anti-overfitting:
  1. Train/test split cronológico 70/30 — ambos deben tener ROI > 0
  2. N >= max(15, n_matches // 25)  (≈48 con ~1200 partidos)
  3. IC95_lower >= 40% (Wilson)
  4. ROI raw >= MIN_ROI (15% por defecto, margen para el realistic drop)
  5. >= 3 ligas diferentes
  6. No más del 70% de bets en una sola liga

Con estos 6 filtros en cadena, el ruido del multiple-testing se elimina
casi completamente de los ~15k combos que se evalúan.
"""

import os, glob, csv, math, json, sys, argparse
from collections import defaultdict

# ─── config ───────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "betfair_scraper", "data")
STAKE = 10.0

# Quality gates
G_MIN_N       = 15          # mínimo absoluto (gate adaptativo se calcula en runtime)
G_MIN_ROI     = 15.0        # raw ROI mínimo (antes de slippage)
G_IC_LOW      = 40.0        # IC95 lower bound mínimo
G_MIN_LEAGUES = 3           # diversificación geográfica
G_MAX_LEAGUE_CONC = 0.70    # max fracción de bets en una sola liga

# ─── helpers ──────────────────────────────────────────────────────────────────
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
    if n == 0:
        return (0.0, 0.0)
    z = 1.96
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(max(0, centre - margin) * 100, 1),
            round(min(1, centre + margin) * 100, 1))

def max_drawdown(pls):
    cum = peak = dd = 0
    for pl in pls:
        cum += pl
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return round(dd, 2)

def sharpe_ratio(pls):
    if len(pls) < 2:
        return 0.0
    m = sum(pls) / len(pls)
    v = sum((p - m) ** 2 for p in pls) / (len(pls) - 1)
    s = math.sqrt(v) if v > 0 else 0.001
    return round(m / s * math.sqrt(len(pls)), 2)

def pl_back(odds, won):
    return round(STAKE * (odds - 1) * 0.95, 2) if won else -STAKE

def pl_lay(odds, won):
    # odds aquí son las lay_odds del CSV (precio al que el market toma tu apuesta)
    return round(STAKE * 0.95, 2) if won else round(-(STAKE * (odds - 1)), 2)

def compute_stats(bets):
    if not bets:
        return None
    n = len(bets)
    wins = sum(1 for b in bets if b["won"])
    total_pl = sum(b["pl"] for b in bets)
    roi = total_pl / (n * STAKE) * 100
    ci_lo, ci_hi = wilson_ci95(n, wins)
    pls = [b["pl"] for b in bets]
    leagues = [b["league"] for b in bets]
    league_counts = defaultdict(int)
    for lg in leagues:
        league_counts[lg] += 1
    max_conc = max(league_counts.values()) / n if league_counts else 0
    return {
        "n": n, "wins": wins,
        "wr":   round(wins / n * 100, 1),
        "roi":  round(roi, 1),
        "pl":   round(total_pl, 2),
        "ci_lo": ci_lo, "ci_hi": ci_hi,
        "avg_odds": round(sum(b["odds"] for b in bets) / n, 2),
        "max_dd":  max_drawdown(pls),
        "sharpe":  sharpe_ratio(pls),
        "n_leagues": len(set(leagues)),
        "max_league_conc": round(max_conc, 2),
        "top_league": max(league_counts, key=league_counts.get) if league_counts else "?",
    }

def split_roi(bets, ratio=0.7):
    sb = sorted(bets, key=lambda b: b.get("ts", ""))
    cut = int(len(sb) * ratio)
    train, test = sb[:cut], sb[cut:]
    def roi_of(lst):
        if not lst:
            return None
        return round(sum(b["pl"] for b in lst) / (len(lst) * STAKE) * 100, 1)
    return roi_of(train), roi_of(test), len(train), len(test)

# ─── data loading ─────────────────────────────────────────────────────────────
def load_matches():
    files = sorted(glob.glob(os.path.join(DATA_DIR, "partido_*.csv")))
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
            "match_id":    os.path.basename(fpath).replace("partido_", "").replace(".csv", ""),
            "league":      last.get("Liga", "?"),
            "country":     last.get("País", last.get("Pais", "?")),
            "ft_local":    gl,
            "ft_visitante": gv,
            "ft_total":    gl + gv,
            "rows":        rows,
            "ts_first":    rows[0].get("timestamp_utc", ""),
        })
    return matches

# ─── pre-indexar triggers por (window_idx, score_state_key) ──────────────────
# Para cada partido y cada (ventana, score_state), almacenamos el primer row
# que cumple la condición de minuto + marcador.
# Esto es O(n_matches × n_windows × n_score_states × avg_rows_per_window)
# ≈ 1M ops → muy rápido. Luego cada combo mercado+filtro es O(n_triggers).

MINUTE_WINDOWS = [
    (40, 60), (45, 65), (50, 70), (55, 75), (60, 80), (65, 85), (70, 90),
]

# score_state: (name, fn(gl, gv) -> bool)
SCORE_STATES = [
    ("any",       lambda gl, gv: True),
    ("0-0",       lambda gl, gv: gl == 0 and gv == 0),
    ("home+1",    lambda gl, gv: gl - gv == 1),
    ("away+1",    lambda gl, gv: gv - gl == 1),
    ("home+2",    lambda gl, gv: gl - gv == 2),
    ("away+2",    lambda gl, gv: gv - gl == 2),
    ("home+3p",   lambda gl, gv: gl - gv >= 3),
    ("away+3p",   lambda gl, gv: gv - gl >= 3),
    ("tied_1-1",  lambda gl, gv: gl == 1 and gv == 1),
    ("tied_2-2",  lambda gl, gv: gl == 2 and gv == 2),
    ("lead1",     lambda gl, gv: abs(gl - gv) == 1),
    ("lead2",     lambda gl, gv: abs(gl - gv) == 2),
    ("goals_ge2", lambda gl, gv: gl + gv >= 2),
    ("goals_ge3", lambda gl, gv: gl + gv >= 3),
    ("goals_ge4", lambda gl, gv: gl + gv >= 4),
]

def build_trigger_index(matches):
    """
    Devuelve: index[(wi, ss_name)] = lista de
        {"match": m, "row": row, "minute": m_val}
    para cada partido donde hay primer trigger en esa ventana+score_state.
    """
    index = defaultdict(list)
    for m in matches:
        rows = m["rows"]
        for wi, (wmin, wmax) in enumerate(MINUTE_WINDOWS):
            for ss_name, ss_fn in SCORE_STATES:
                key = (wi, ss_name)
                for row in rows:
                    minute = _f(row.get("minuto", ""))
                    if minute is None or not (wmin <= minute <= wmax):
                        continue
                    gl = _i(row.get("goles_local", ""))
                    gv = _i(row.get("goles_visitante", ""))
                    if gl is None or gv is None:
                        continue
                    if ss_fn(gl, gv):
                        index[key].append({
                            "match":  m,
                            "row":    row,
                            "minute": minute,
                        })
                        break   # solo primer trigger por partido
    return index

# ─── mercados ─────────────────────────────────────────────────────────────────
# Cada mercado: (key, label, odds_col, is_lay, win_fn, odds_lo, odds_hi)
# win_fn(ft_local, ft_visitante) -> bool  (TRUE = ganamos la apuesta)

def _back(label, odds_col, win_fn, odds_lo=1.1, odds_hi=12.0):
    return (label, odds_col, False, win_fn, odds_lo, odds_hi)

def _lay(label, odds_col, win_fn, odds_lo=1.1, odds_hi=8.0):
    # Para LAY usamos las columnas lay_* directamente (son las lay odds del exchange)
    return ("LAY " + label, odds_col, True, win_fn, odds_lo, odds_hi)

MARKETS = [
    # ── Match Odds ──────────────────────────────────────────────────────────
    _back("BACK Home",     "back_home",  lambda l, v: l > v,  1.2,  5.0),
    _back("BACK Draw",     "back_draw",  lambda l, v: l == v, 2.5,  6.0),
    _back("BACK Away",     "back_away",  lambda l, v: v > l,  1.3,  8.0),
    _lay ("Home",          "lay_home",   lambda l, v: l <= v, 1.1,  5.0),
    _lay ("Draw",          "lay_draw",   lambda l, v: l != v, 1.5,  5.0),
    _lay ("Away",          "lay_away",   lambda l, v: v <= l, 1.1,  6.0),

    # ── Over / Under BACK ───────────────────────────────────────────────────
    _back("BACK Over 0.5", "back_over05",  lambda l, v: l + v > 0, 1.01, 3.0),
    _back("BACK Over 1.5", "back_over15",  lambda l, v: l + v > 1, 1.05, 5.0),
    _back("BACK Over 2.5", "back_over25",  lambda l, v: l + v > 2, 1.1,  7.0),
    _back("BACK Over 3.5", "back_over35",  lambda l, v: l + v > 3, 1.2, 10.0),
    _back("BACK Over 4.5", "back_over45",  lambda l, v: l + v > 4, 1.5, 15.0),
    _back("BACK Over 5.5", "back_over55",  lambda l, v: l + v > 5, 1.5, 20.0),
    _back("BACK Under 1.5","back_under15", lambda l, v: l + v < 2, 1.1,  5.0),
    _back("BACK Under 2.5","back_under25", lambda l, v: l + v < 3, 1.1,  6.0),
    _back("BACK Under 3.5","back_under35", lambda l, v: l + v < 4, 1.1,  7.0),
    _back("BACK Under 4.5","back_under45", lambda l, v: l + v < 5, 1.1,  8.0),

    # ── Over / Under LAY ────────────────────────────────────────────────────
    _lay ("Over 0.5",  "lay_over05",   lambda l, v: l + v <= 0, 1.01, 3.0),
    _lay ("Over 1.5",  "lay_over15",   lambda l, v: l + v <= 1, 1.05, 5.0),
    _lay ("Over 2.5",  "lay_over25",   lambda l, v: l + v <= 2, 1.1,  7.0),
    _lay ("Over 3.5",  "lay_over35",   lambda l, v: l + v <= 3, 1.2, 10.0),
    _lay ("Over 4.5",  "lay_over45",   lambda l, v: l + v <= 4, 1.5, 15.0),
    _lay ("Under 1.5", "lay_under15",  lambda l, v: l + v >= 2, 1.1,  5.0),
    _lay ("Under 2.5", "lay_under25",  lambda l, v: l + v >= 3, 1.1,  6.0),
    _lay ("Under 3.5", "lay_under35",  lambda l, v: l + v >= 4, 1.1,  7.0),
    _lay ("Under 4.5", "lay_under45",  lambda l, v: l + v >= 5, 1.1,  8.0),

    # ── Correct Score BACK (scorelines con cobertura conocida) ──────────────
    _back("BACK CS 0-0", "back_rc_0_0", lambda l, v: l == 0 and v == 0,  5.0, 100.0),
    _back("BACK CS 1-0", "back_rc_1_0", lambda l, v: l == 1 and v == 0,  3.0,  20.0),
    _back("BACK CS 0-1", "back_rc_0_1", lambda l, v: l == 0 and v == 1,  3.0,  20.0),
    _back("BACK CS 1-1", "back_rc_1_1", lambda l, v: l == 1 and v == 1,  4.0,  20.0),
    _back("BACK CS 2-0", "back_rc_2_0", lambda l, v: l == 2 and v == 0,  5.0,  35.0),
    _back("BACK CS 0-2", "back_rc_0_2", lambda l, v: l == 0 and v == 2,  5.0,  35.0),
    _back("BACK CS 2-1", "back_rc_2_1", lambda l, v: l == 2 and v == 1,  5.0,  35.0),
    _back("BACK CS 1-2", "back_rc_1_2", lambda l, v: l == 1 and v == 2,  5.0,  35.0),
    _back("BACK CS 2-2", "back_rc_2_2", lambda l, v: l == 2 and v == 2, 10.0,  60.0),
    _back("BACK CS 3-0", "back_rc_3_0", lambda l, v: l == 3 and v == 0,  8.0,  60.0),
    _back("BACK CS 0-3", "back_rc_0_3", lambda l, v: l == 0 and v == 3,  8.0,  60.0),
    _back("BACK CS 3-1", "back_rc_3_1", lambda l, v: l == 3 and v == 1,  8.0,  80.0),
    _back("BACK CS 1-3", "back_rc_1_3", lambda l, v: l == 1 and v == 3,  8.0,  80.0),
    _back("BACK CS 3-2", "back_rc_3_2", lambda l, v: l == 3 and v == 2, 12.0, 100.0),
    _back("BACK CS 2-3", "back_rc_2_3", lambda l, v: l == 2 and v == 3, 12.0, 100.0),

    # ── Correct Score LAY ────────────────────────────────────────────────────
    _lay ("CS 0-0", "lay_rc_0_0", lambda l, v: not (l == 0 and v == 0),  1.1, 20.0),
    _lay ("CS 1-0", "lay_rc_1_0", lambda l, v: not (l == 1 and v == 0),  1.1,  8.0),
    _lay ("CS 0-1", "lay_rc_0_1", lambda l, v: not (l == 0 and v == 1),  1.1,  8.0),
    _lay ("CS 1-1", "lay_rc_1_1", lambda l, v: not (l == 1 and v == 1),  1.1,  8.0),
    _lay ("CS 2-0", "lay_rc_2_0", lambda l, v: not (l == 2 and v == 0),  1.1, 10.0),
    _lay ("CS 0-2", "lay_rc_0_2", lambda l, v: not (l == 0 and v == 2),  1.1, 10.0),
    _lay ("CS 2-1", "lay_rc_2_1", lambda l, v: not (l == 2 and v == 1),  1.1, 10.0),
    _lay ("CS 1-2", "lay_rc_1_2", lambda l, v: not (l == 1 and v == 2),  1.1, 10.0),
    _lay ("CS 3-0", "lay_rc_3_0", lambda l, v: not (l == 3 and v == 0),  1.1,  6.0),
    _lay ("CS 0-3", "lay_rc_0_3", lambda l, v: not (l == 0 and v == 3),  1.1,  6.0),
    _lay ("CS 3-1", "lay_rc_3_1", lambda l, v: not (l == 3 and v == 1),  1.1,  6.0),
    _lay ("CS 1-3", "lay_rc_1_3", lambda l, v: not (l == 1 and v == 3),  1.1,  6.0),
]

# ─── filtros de stats ────────────────────────────────────────────────────────
# (name, fn(row) -> bool | None)   None = skip si datos insuficientes
STAT_FILTERS = [
    ("none",       lambda row: True),
    ("xg_home",    lambda row: (_f(row.get("xg_local","")) or 0) - (_f(row.get("xg_visitante","")) or 0) >= 0.5),
    ("xg_away",    lambda row: (_f(row.get("xg_visitante","")) or 0) - (_f(row.get("xg_local","")) or 0) >= 0.5),
    ("xg_low",     lambda row: ((_f(row.get("xg_local","")) or 0) + (_f(row.get("xg_visitante","")) or 0)) <= 1.5),
    ("xg_high",    lambda row: ((_f(row.get("xg_local","")) or 0) + (_f(row.get("xg_visitante","")) or 0)) >= 2.5),
    ("sot_home",   lambda row: (_i(row.get("tiros_puerta_local","")) or 0) >= (_i(row.get("tiros_puerta_visitante","")) or 0) + 2),
    ("sot_away",   lambda row: (_i(row.get("tiros_puerta_visitante","")) or 0) >= (_i(row.get("tiros_puerta_local","")) or 0) + 2),
    ("poss_home",  lambda row: (_f(row.get("posesion_local","")) or 50) >= 60),
    ("poss_away",  lambda row: (_f(row.get("posesion_visitante","")) or 50) >= 60),
    ("corners_dom",lambda row: abs((_i(row.get("corners_local","")) or 0) - (_i(row.get("corners_visitante","")) or 0)) >= 3),
]

# ─── notas de solapamiento con estrategias existentes ────────────────────────
# Si un candidato pasa los gates, añadir nota de overlap manual basada en
# el mercado + score_state + ventana.
KNOWN_COVERAGE = {
    # (market_label_prefix, score_state, window_hint): existing strategy
    ("BACK Draw",    "0-0",      None):     "back_draw_00",
    ("BACK Over 2.5","home+1",   None):     "over25_2goal / pressure_cooker",
    ("BACK Over 2.5","home+2",   None):     "over25_2goal",
    ("BACK Under 3.5","home+1",  None):     "under35_late",
    ("BACK Under 3.5","goals_ge3",None):    "under35_3goals",
    ("BACK Under 4.5","goals_ge3",None):    "under45_3goals",
    ("LAY Over 4.5", None,       None):     "lay_over45_v3",
    ("BACK Draw",    "tied_1-1", None):     "draw_11 / draw_xg_conv",
    ("BACK CS 2-1",  None,       None):     "cs_close",
    ("BACK CS 1-2",  None,       None):     "cs_close",
    ("BACK CS 1-0",  None,       None):     "cs_one_goal",
    ("BACK CS 0-1",  None,       None):     "cs_one_goal",
    ("BACK CS 2-0",  None,       None):     "cs_20",
    ("BACK CS 0-2",  None,       None):     "cs_20",
    ("BACK CS 3-0",  None,       None):     "cs_big_lead",
    ("BACK CS 3-1",  None,       None):     "cs_big_lead",
    ("BACK CS 0-3",  None,       None):     "cs_big_lead",
    ("BACK CS 1-3",  None,       None):     "cs_big_lead",
    ("BACK CS 0-0",  None,       None):     "cs_00 (inactiva)",
    ("BACK CS 1-1",  None,       None):     "cs_11 (inactiva)",
    ("BACK Away",    "home+1",   None):     "ud_leading / away_fav_leading",
    ("BACK Away",    "home+2",   None):     "ud_leading",
    ("BACK Home",    "away+1",   None):     "home_fav_leading",
    ("BACK Away",    "away+1",   None):     "away_fav_leading",
}

def get_overlap_note(market_label, score_state):
    for (ml, ss, _), strat in KNOWN_COVERAGE.items():
        if market_label.startswith(ml) and (ss is None or ss == score_state):
            return strat
    return ""

# ─── main scan ───────────────────────────────────────────────────────────────
def run_scan(matches, min_roi=G_MIN_ROI, verbose=True):
    n_matches = len(matches)
    G_N = max(G_MIN_N, n_matches // 25)

    if verbose:
        print(f"\n{'='*70}")
        print(f"  Brute-Force Market Scanner")
        print(f"  Matches: {n_matches}  |  Quality gate N>={G_N}  ROI>={min_roi}%")
        print(f"  Markets: {len(MARKETS)}  Windows: {len(MINUTE_WINDOWS)}")
        print(f"  Score states: {len(SCORE_STATES)}  Stat filters: {len(STAT_FILTERS)}")
        total = len(MARKETS) * len(MINUTE_WINDOWS) * len(SCORE_STATES) * len(STAT_FILTERS)
        print(f"  Total combinations: {total:,}")
        print(f"{'='*70}\n")

    # ── Paso 1: pre-indexar triggers (window, score_state) → [(match, row)] ──
    if verbose:
        print("Paso 1/3 — Pre-indexando triggers... ", end="", flush=True)

    index = defaultdict(list)
    for m in matches:
        for wi, (wmin, wmax) in enumerate(MINUTE_WINDOWS):
            for ss_name, ss_fn in SCORE_STATES:
                key = (wi, ss_name)
                for row in m["rows"]:
                    minute = _f(row.get("minuto", ""))
                    if minute is None or not (wmin <= minute <= wmax):
                        continue
                    gl = _i(row.get("goles_local", ""))
                    gv = _i(row.get("goles_visitante", ""))
                    if gl is None or gv is None:
                        continue
                    if ss_fn(gl, gv):
                        index[key].append({"match": m, "row": row, "minute": minute})
                        break

    if verbose:
        total_triggers = sum(len(v) for v in index.values())
        print(f"OK  ({total_triggers:,} trigger slots)")

    # ── Paso 2: evaluar cada combo (market × window × score_state × filter) ──
    if verbose:
        print("Paso 2/3 — Evaluando combinaciones...", flush=True)

    survivors = []
    combo_count = 0
    total_combos = len(MARKETS) * len(MINUTE_WINDOWS) * len(SCORE_STATES) * len(STAT_FILTERS)

    # Pre-calcular threshold para detección de tautologías Over/Under
    import re as _re
    def _ou_threshold(col):
        """Extrae el umbral numérico de columnas back/lay_over/underXX.
        Convención: over25 = Over 2.5, under35 = Under 3.5 → dividir por 10.
        """
        m = _re.search(r'(?:over|under)(\d+)$', col)
        if m:
            return float(m.group(1)) / 10.0
        return None

    def is_tautology(odds_col, is_lay_bet, gl_now, gv_now):
        """
        Devuelve True si la apuesta ya está matemáticamente ganada en el trigger.
        Casos tautológicos (win garantizado al trigger):
          - BACK Over X.5  cuando total_now > X  (ya hay suficientes goles)
          - LAY Under X.5  cuando total_now > X  (Under X.5 ya está muerto)
        Estos producen WR=100% artificial, no son edges reales.
        """
        thr = _ou_threshold(odds_col)
        if thr is None:
            return False
        total_now = gl_now + gv_now
        is_over_col = "over" in odds_col
        if not is_lay_bet and is_over_col and total_now > thr:
            return True   # BACK Over: ya ganado
        if is_lay_bet and not is_over_col and total_now > thr:
            return True   # LAY Under: ya ganado (Under está muerto)
        return False

    for market_label, odds_col, is_lay, win_fn, odds_lo, odds_hi in MARKETS:
        for wi, (wmin, wmax) in enumerate(MINUTE_WINDOWS):
            for ss_name, _ in SCORE_STATES:
                triggers = index.get((wi, ss_name), [])
                if not triggers:
                    combo_count += len(STAT_FILTERS)
                    continue

                for sf_name, sf_fn in STAT_FILTERS:
                    combo_count += 1
                    if verbose and combo_count % 5000 == 0:
                        pct = combo_count / total_combos * 100
                        print(f"  {combo_count:>6,}/{total_combos:,}  ({pct:.1f}%)  survivors so far: {len(survivors)}", flush=True)

                    bets = []
                    for trig in triggers:
                        row   = trig["row"]
                        m     = trig["match"]

                        # anti-tautología: excluir bets matemáticamente garantizadas
                        gl_now = _i(row.get("goles_local", ""))
                        gv_now = _i(row.get("goles_visitante", ""))
                        if gl_now is None or gv_now is None:
                            continue
                        if is_tautology(odds_col, is_lay, gl_now, gv_now):
                            continue

                        # filtro de stats
                        try:
                            if not sf_fn(row):
                                continue
                        except Exception:
                            continue

                        # odds del mercado
                        odds_raw = _f(row.get(odds_col, ""))
                        if odds_raw is None or not (odds_lo <= odds_raw <= odds_hi):
                            continue

                        # resultado
                        won = win_fn(m["ft_local"], m["ft_visitante"])
                        pl  = (pl_lay if is_lay else pl_back)(odds_raw, won)

                        bets.append({
                            "match_id": m["match_id"],
                            "league":   m["league"],
                            "ts":       m["ts_first"],
                            "minute":   trig["minute"],
                            "odds":     odds_raw,
                            "won":      won,
                            "pl":       pl,
                        })

                    if not bets:
                        continue

                    st = compute_stats(bets)
                    if st is None:
                        continue

                    # ── quality gates ──────────────────────────────────────
                    if st["n"] < G_N:
                        continue
                    if st["roi"] < min_roi:
                        continue
                    if st["ci_lo"] < G_IC_LOW:
                        continue
                    if st["n_leagues"] < G_MIN_LEAGUES:
                        continue
                    if st["max_league_conc"] > G_MAX_LEAGUE_CONC:
                        continue

                    # train/test
                    roi_train, roi_test, n_train, n_test = split_roi(bets)
                    if roi_train is None or roi_test is None:
                        continue
                    if roi_train <= 0 or roi_test <= 0:
                        continue

                    overlap_note = get_overlap_note(market_label, ss_name)

                    survivors.append({
                        "market":      market_label,
                        "odds_col":    odds_col,
                        "window":      f"{wmin}-{wmax}",
                        "score_state": ss_name,
                        "stat_filter": sf_name,
                        "n":           st["n"],
                        "wr":          st["wr"],
                        "roi":         st["roi"],
                        "pl":          st["pl"],
                        "ci_lo":       st["ci_lo"],
                        "ci_hi":       st["ci_hi"],
                        "avg_odds":    st["avg_odds"],
                        "sharpe":      st["sharpe"],
                        "max_dd":      st["max_dd"],
                        "n_leagues":   st["n_leagues"],
                        "max_lg_conc": st["max_league_conc"],
                        "top_league":  st["top_league"],
                        "roi_train":   roi_train,
                        "roi_test":    roi_test,
                        "n_train":     n_train,
                        "n_test":      n_test,
                        "overlap_note": overlap_note,
                    })

    # ── Paso 3: ranking y output ──────────────────────────────────────────────
    survivors.sort(key=lambda x: x["sharpe"], reverse=True)

    if verbose:
        print(f"\nPaso 3/3 — Resultados\n{'='*70}")
        print(f"Combinaciones evaluadas : {total_combos:,}")
        print(f"Supervivientes (6 gates): {len(survivors)}")
        print()

        if not survivors:
            print("❌  Ningún candidato pasó todos los quality gates.")
            print("    Esto puede indicar que el dataset está bien explotado,")
            print("    o que se necesitan parámetros más permisivos (--min-roi).")
        else:
            print(f"{'#':>3}  {'Market':<22} {'Window':<8} {'Score':<12} {'Filter':<12} "
                  f"{'N':>5} {'WR%':>6} {'ROI%':>7} {'Sharpe':>7} {'CI_lo':>6} "
                  f"{'Tr_ROI':>7} {'Te_ROI':>7}  Overlap")
            print("-" * 120)
            for i, s in enumerate(survivors[:50], 1):
                ov = f" ** YA CUBIERTO: {s['overlap_note']}" if s["overlap_note"] else ""
                print(f"{i:>3}  {s['market']:<22} {s['window']:<8} {s['score_state']:<12} "
                      f"{s['stat_filter']:<12} {s['n']:>5} {s['wr']:>6.1f} {s['roi']:>7.1f} "
                      f"{s['sharpe']:>7.2f} {s['ci_lo']:>6.1f} "
                      f"{s['roi_train']:>7.1f} {s['roi_test']:>7.1f}  {ov}")

    return survivors


def save_csv(survivors, path):
    if not survivors:
        return
    fieldnames = list(survivors[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(survivors)
    print(f"\nResultados guardados en: {path}")


# ─── entry point ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Brute-Force Market Scanner")
    parser.add_argument("--min-roi", type=float, default=G_MIN_ROI,
                        help=f"ROI mínimo raw (default {G_MIN_ROI}%%)")
    parser.add_argument("--out", type=str, default="",
                        help="CSV de salida (opcional)")
    args = parser.parse_args()

    print("Cargando partidos...", end=" ", flush=True)
    matches = load_matches()
    print(f"{len(matches)} partidos cargados.")

    survivors = run_scan(matches, min_roi=args.min_roi)

    out_path = args.out
    if not out_path and survivors:
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "analisis", f"scan_results_{ts}.csv")
    if out_path:
        save_csv(survivors, out_path)

    # Candidatos NUEVOS (sin overlap con existentes)
    nuevos = [s for s in survivors if not s["overlap_note"]]
    if nuevos:
        print(f"\n{'='*70}")
        print(f"  CANDIDATOS GENUINAMENTE NUEVOS (sin overlap conocido): {len(nuevos)}")
        print(f"{'='*70}")
        for i, s in enumerate(nuevos[:20], 1):
            print(f"{i:>3}  {s['market']:<22} {s['window']:<8} {s['score_state']:<12} "
                  f"{s['stat_filter']:<12}  N={s['n']}  ROI={s['roi']}%  "
                  f"Sharpe={s['sharpe']}  CI_lo={s['ci_lo']}%  "
                  f"Train={s['roi_train']}%  Test={s['roi_test']}%")
    else:
        print("\n⚠️  Todos los supervivientes solapan con estrategias ya existentes.")

    return survivors


if __name__ == "__main__":
    main()
