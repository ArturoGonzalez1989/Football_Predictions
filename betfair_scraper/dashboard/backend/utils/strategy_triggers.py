"""
Shared trigger-detection helpers for Betfair Exchange strategies.

Each function implements the core "does this snapshot meet condition X?" logic
shared by both:
  - analyze_strategy_*() (batch backtest over historical rows)
  - detect_betting_signals() (live, single-snapshot evaluation)

All functions follow the canonical interface:
    _detect_<name>_trigger(rows, curr_idx, cfg) -> dict | None
"""
from typing import Optional
from .csv_loader import _to_float, _compute_synthetic_at_trigger


def _get_over_odds_field(total_goals: int) -> str:
    """Return CSV column name for Back Over (total_goals + 0.5)."""
    return {0: "back_over05", 1: "back_over15", 2: "back_over25",
            3: "back_over35", 4: "back_over45"}.get(total_goals, "")

# ── GR8: Shared trigger-detection helpers ───────────────────────────────
# These functions encapsulate the core "does this snapshot meet condition X?"
# logic that is common to both:
#   - analyze_strategy_*() (batch backtest over historical rows), and
#   - detect_betting_signals() (live, single-snapshot evaluation).
# Extracting them here ensures both pipelines use the identical algorithm,
# eliminating duplication and preventing future divergence.

def _detect_tarde_asia_liga(match_name: str, match_url: str, match_id: str) -> str:
    """Detect the league of a match for the Tarde Asia strategy.

    Returns the league label (e.g. "Bundesliga", "Ligue", "Eredivisie",
    "J-League", "K-League", "Asian League", "Chinese SL") or "Unknown"
    if the match does not belong to any of the target leagues.

    Normalizes hyphens to spaces so that hyphenated match IDs (e.g.
    "al-hilal-al-wahda-abu-dhabi") are matched the same as display names
    ("Al Hilal Al Wahda").  This fixes the BT side which previously used raw
    match names without normalization, causing misses for Arabic/Asian clubs.
    """
    # Normalize: lowercase + hyphens → spaces
    _name = match_name.lower().replace("-", " ")
    _url_norm = match_url.lower().replace("-", " ")
    # Also keep original URL for keyword patterns that use literal hyphens
    _url_orig = match_url.lower()
    _mid = match_id.lower().replace("-", " ")

    # Prefer display name; fall back to match_id when name is empty
    _check = _name if _name.strip() else _mid
    _search = _check + " " + _mid  # combined search string for team lookup

    # --- URL / name keyword detection (fast path) ---
    if "bundesliga" in _url_orig or "bundesliga" in _check:
        return "Bundesliga"
    if "ligue" in _url_orig or "ligue" in _check:
        return "Ligue"
    if "eredivisie" in _url_orig or "eredivisie" in _check:
        return "Eredivisie"
    if any(x in _url_orig for x in ("j league", "j-league", "jleague")):
        return "J-League"
    if any(x in _url_orig for x in ("k league", "k-league", "kleague")):
        return "K-League"
    if any(x in _url_orig for x in ("asia", "asiática", "asiatic")):
        return "Asian League"
    if any(x in _url_orig for x in ("chinese", "china", "super league", "csl")):
        return "Chinese SL"

    # --- Team-name fallback (for historical data without meaningful URL) ---
    _dutch_teams = [
        "ajax", "psv", "feyenoord", "az alkmaar", "twente", "utrecht",
        "heerenveen", "groningen", "vitesse", "nec", "fortuna sittard",
        "sparta", "heracles", "almere", "zwolle", "waalwijk", "excelsior", "volendam",
    ]
    _german_teams = [
        "bayern", "dortmund", "leipzig", "leverkusen", "frankfurt",
        "freiburg", "wolfsburg", "monchengladbach", "stuttgart",
        "hoffenheim", "bremen", "union berlin", "mainz", "bochum",
        "augsburg", "heidenheim", "darmstadt",
    ]
    _french_teams = [
        "psg", "marseille", "lyon", "monaco", "lille", "lens",
        "rennes", "nice", "nantes", "montpellier", "strasbourg",
        "brest", "reims", "toulouse", "lorient", "clermont", "havre", "metz",
    ]
    _asian_teams = [
        "al hilal", "al nassr", "al ahli", "al ittihad", "al shabab",
        "al ettifaq", "al fayha", "al fateh", "al raed", "al taawoun",
        "al wehda", "al sharjah", "al ain", "al jazira", "al wahda",
        "al sadd", "al qadsiah", "al kholood", "al hazem", "al okhdood",
        "al orubah", "al khaleej", "al riyadh", "al akhdoud",
        "shabab", "baniyas", "nasaf", "sepahan", "persepolis",
        "kashima", "urawa", "yokohama", "gamba osaka", "kawasaki",
        "cerezo", "sanfrecce", "vissel", "jeonbuk", "ulsan", "pohang",
        "suwon", "jeonnam", "seoul", "busan",
        "shanghai", "guangzhou", "beijing", "shandong",
    ]

    if any(t in _search for t in _dutch_teams):
        return "Eredivisie"
    if any(t in _search for t in _german_teams):
        return "Bundesliga"
    if any(t in _search for t in _french_teams):
        return "Ligue"
    if any(t in _search for t in _asian_teams):
        return "Asian League"

    return "Unknown"


def _detect_momentum_dominant(
    sot_local: float,
    sot_visitante: float,
    xg_underperf_local: float,
    xg_underperf_visitante: float,
    back_home: Optional[float],
    back_away: Optional[float],
    cfg: dict,
) -> tuple:
    """Detect which team (if any) is momentum-dominant for the Momentum xG strategy.

    ``cfg`` must contain:
        sot_min        : int   — minimum shots-on-target for the dominant team
        sot_ratio_min  : float — minimum SoT ratio (dominant / other)
        xg_underperf_min : float — minimum xG underperformance
        min_odds       : float — minimum back odds accepted
        max_odds       : float — maximum back odds accepted

    Returns ``(dominant_team, back_odds, sot_ratio_used)`` where:
        dominant_team  : "Home" | "Away" | None
        back_odds      : float | None  — odds for the dominant team
        sot_ratio_used : float         — SoT ratio value used (0 if none)

    If both teams qualify, the one with higher xG underperformance wins.
    This is the single authoritative implementation called by both
    analyze_strategy_momentum_xg() (BT) and STRATEGY 6 in
    detect_betting_signals() (live).
    """
    sot_min = cfg["sot_min"]
    ratio_min = cfg["sot_ratio_min"]
    xg_min = cfg.get("xg_underperf_min", cfg.get("xg", 0.0))
    odds_min = cfg["min_odds"] if "min_odds" in cfg else cfg.get("odds_min", 1.0)
    odds_max = cfg["max_odds"] if "max_odds" in cfg else cfg.get("odds_max", 999.0)

    dominant_team: Optional[str] = None
    best_odds: Optional[float] = None
    best_sot_ratio: float = 0.0

    # --- Home dominant ---
    if sot_visitante > 0:
        ratio_local = sot_local / sot_visitante
    else:
        ratio_local = (sot_local * 2) if sot_local >= sot_min else 0.0

    if (sot_local >= sot_min and ratio_local >= ratio_min
            and xg_underperf_local > xg_min
            and back_home is not None and odds_min <= back_home <= odds_max):
        dominant_team = "Home"
        best_odds = back_home
        best_sot_ratio = ratio_local

    # --- Away dominant ---
    if sot_local > 0:
        ratio_visitante = sot_visitante / sot_local
    else:
        ratio_visitante = (sot_visitante * 2) if sot_visitante >= sot_min else 0.0

    if (sot_visitante >= sot_min and ratio_visitante >= ratio_min
            and xg_underperf_visitante > xg_min
            and back_away is not None and odds_min <= back_away <= odds_max):
        # If both qualify, pick the one with higher xG underperformance
        if dominant_team is None or xg_underperf_visitante > xg_underperf_local:
            dominant_team = "Away"
            best_odds = back_away
            best_sot_ratio = ratio_visitante

    return dominant_team, best_odds, best_sot_ratio


# ── GR9: Shared trigger-detection helpers for remaining 5 strategies ─────
# Same pattern as _detect_tardesia_trigger and _detect_momentum_xg_trigger above.
# Each helper is a pure function: (row_data, cfg_dict) → trigger_result | None.
# Called by both analyze_strategy_* (BT) and STRATEGY N in detect_betting_signals (LIVE).

def _detect_draw_filters(
    xg_total: Optional[float],
    poss_diff: Optional[float],
    shots_total: Optional[float],
    cfg: dict,
) -> dict:
    """Evaluate filter conditions for the Back Draw 0-0 strategy.

    ``cfg`` must contain:
        xg_max        : float  — maximum total xG (sentinel 1.0 = filter off)
        poss_max      : float  — maximum |poss_local - poss_away| (sentinel 100 = off)
        shots_max     : float  — maximum total shots (sentinel 20 = off)

    Returns a dict with a single boolean flag:
        passes : bool  — all cfg filters pass

    Null handling:
        - null xG blocks when xg_max < 1.0 (filter is active); passes when >= 1.0 (sentinel/off)
        - null poss/shots pass their respective filters
    """
    xg_max = cfg.get("xg_max", 1.0)
    poss_max = cfg.get("poss_max", 100.0)
    shots_max = cfg.get("shots_max", 20.0)

    _xg_ok  = xg_max >= 1.0   or (xg_total is not None and xg_total   < xg_max)
    _pos_ok = poss_max >= 100  or poss_diff is None   or poss_diff  < poss_max
    _sht_ok = shots_max >= 20  or shots_total is None or shots_total < shots_max

    return {"passes": _xg_ok and _pos_ok and _sht_ok}


def _detect_xg_underperf_candidates(
    xg_local: Optional[float],
    xg_visitante: Optional[float],
    goals_local: int,
    goals_visitante: int,
    sot_local: float,
    sot_visitante: float,
    minuto: float,
    rows: list,
    row: dict,
    cfg: dict,
) -> list:
    """Detect xG underperformance trigger candidates for both teams.

    ``cfg`` must contain:
        xg_excess_min : float  — minimum xG excess (team_xg - team_goals)
        sot_min       : int    — minimum shots-on-target (0 = no filter)
        minute_max    : float  — maximum minute (90 = no upper filter)
        minute_min    : float  — minimum minute (default 15)

    Returns a list of dicts, one per qualifying team:
        {
            "team": "home" | "away",
            "xg_excess": float,
            "total_goals": int,
            "score_at_trigger": str,
            "sot_team": int,
            "over_field": str,
            "back_over": float | None,   # may be None if no odds in this row
        }
    Returns empty list if no candidates qualify.

    Note: ``back_over`` may be None even when all other conditions are met.
    The caller (BT and LIVE) must handle absent odds (skip or retry).
    """
    if xg_local is None or xg_visitante is None:
        return []

    xg_excess_min = float(cfg.get("xg_excess_min", 0.5))
    sot_min = int(cfg.get("sot_min", 0))
    minute_max = float(cfg.get("minute_max", 90))
    minute_min = float(cfg.get("minute_min", 15))

    if minuto < minute_min or (minute_max < 90 and minuto >= minute_max):
        return []

    candidates = []
    for team, team_xg, team_goals, opp_goals, sot_team in [
        ("home", xg_local,    goals_local,    goals_visitante, int(sot_local)),
        ("away", xg_visitante, goals_visitante, goals_local,   int(sot_visitante)),
    ]:
        if team_goals >= opp_goals:
            continue  # team must be LOSING
        xg_excess = team_xg - team_goals
        if xg_excess < xg_excess_min:
            continue
        if sot_min > 0 and sot_team < sot_min:
            continue

        total_goals = goals_local + goals_visitante
        score_at_trigger = f"{goals_local}-{goals_visitante}"
        over_field = _get_over_odds_field(total_goals)
        back_over = _to_float(row.get(over_field, "")) if over_field else None
        # Note: back_over may be None — caller decides whether to skip

        candidates.append({
            "team":             team,
            "xg_excess":        round(xg_excess, 3),
            "total_goals":      total_goals,
            "score_at_trigger": score_at_trigger,
            "sot_team":         sot_team,
            "over_field":       over_field or "",
            "back_over":        back_over,
        })

    return candidates


def _detect_odds_drift_trigger(
    rows: list,
    curr_idx: int,
    cfg: dict,
) -> Optional[dict]:
    """Detect Odds Drift Contrarian trigger at a given row index.

    ``cfg`` must contain:
        drift_min_pct   : float  — minimum drift percentage (e.g. 30 for 30%)
        lookback_min    : float  — lookback window in minutes (default 10)
        score_confirm   : int    — min captures with same score in last 6 rows (default 3)
        min_minute      : float  — minimum minute (default 0)
        max_minute      : float  — maximum minute (default 90)
        max_odds        : float  — maximum back odds accepted (default 999)
        goal_diff_min   : int    — minimum goal difference (default 0)

    Returns dict with trigger data, or None if no trigger.
        {
            "team": "home" | "away",
            "odds_before": float,
            "odds_now": float,
            "drift_pct": float,    # 0-100+ scale (e.g. 31.5 means 31.5%)
            "goal_diff": int,
            "gl_i": int,
            "gv_i": int,
            "minuto": float,
        }
    """
    DRIFT_MIN   = float(cfg.get("drift_min_pct",  30.0))
    LOOKBACK    = float(cfg.get("lookback_min",   10.0))
    CONFIRM_MIN = int(cfg.get("score_confirm",    3))
    MIN_MINUTE  = float(cfg.get("min_minute",     0))
    MAX_MINUTE  = float(cfg.get("max_minute",     90))
    MAX_ODDS    = float(cfg.get("max_odds",       999.0))
    GOAL_DIFF_MIN = int(cfg.get("goal_diff_min",  0))

    curr_row = rows[curr_idx]
    curr_min = _to_float(curr_row.get("minuto", ""))
    if curr_min is None or curr_min < MIN_MINUTE or curr_min > MAX_MINUTE:
        return None

    gl = _to_float(curr_row.get("goles_local", ""))
    gv = _to_float(curr_row.get("goles_visitante", ""))
    if gl is None or gv is None:
        return None
    gl_i, gv_i = int(gl), int(gv)

    if gl_i == gv_i:
        return None  # must have a winner

    goal_diff = abs(gl_i - gv_i)
    if GOAL_DIFF_MIN > 0 and goal_diff < GOAL_DIFF_MIN:
        return None

    # Score confirmation: last 6 rows up to curr_idx
    check_rows = rows[max(0, curr_idx - 5):curr_idx + 1]
    score_confirm_count = sum(
        1 for r in check_rows
        if int(_to_float(r.get("goles_local", "")) or 0) == gl_i
        and int(_to_float(r.get("goles_visitante", "")) or 0) == gv_i
    )
    if score_confirm_count < CONFIRM_MIN:
        return None

    # Lookback: find historical row at ~LOOKBACK min ago WITH same score
    target_minute = curr_min - LOOKBACK
    historical_row = None
    for prev_idx in range(curr_idx - 1, -1, -1):
        prev_row = rows[prev_idx]
        prev_min = _to_float(prev_row.get("minuto", ""))
        if prev_min is None:
            continue
        if prev_min <= target_minute:
            hgl = int(_to_float(prev_row.get("goles_local", "")) or 0)
            hgv = int(_to_float(prev_row.get("goles_visitante", "")) or 0)
            if hgl == gl_i and hgv == gv_i:
                historical_row = prev_row
            break  # stop at first row at/before target minute

    if historical_row is None:
        return None

    curr_bh = _to_float(curr_row.get("back_home", ""))
    curr_ba = _to_float(curr_row.get("back_away", ""))

    # Determine winning team
    if gl_i > gv_i:
        team = "home"
        odds_before = _to_float(historical_row.get("back_home", ""))
        odds_now = curr_bh
    else:
        team = "away"
        odds_before = _to_float(historical_row.get("back_away", ""))
        odds_now = curr_ba

    if odds_before is None or odds_now is None or odds_before <= 0:
        return None
    if odds_now > MAX_ODDS:
        return None

    drift_pct = ((odds_now - odds_before) / odds_before) * 100
    if drift_pct < DRIFT_MIN:
        return None

    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds_now < odds_min:
        return None

    return {
        "team":       team,
        "odds_before": round(odds_before, 3),
        "odds_now":    round(odds_now, 3),
        "drift_pct":   round(drift_pct, 2),
        "goal_diff":   goal_diff,
        "gl_i":        gl_i,
        "gv_i":        gv_i,
        "minuto":      curr_min,
    }


def _detect_goal_clustering_trigger(
    rows: list,
    curr_idx: int,
    cfg: dict,
) -> Optional[dict]:
    """Detect Goal Clustering trigger at a given row index.

    Looks back up to 3 rows to find a recent goal, then checks SoT threshold.

    ``cfg`` must contain:
        sot_min      : int    — minimum max(sot_local, sot_away) (0 = no filter)
        min_minute   : float  — minimum minute for goal detection (default 15)
        max_minute   : float  — maximum minute for goal detection (default 90)
        xg_rem_min   : float  — minimum xG remaining (0 = no filter; uses synthetic)

    Returns dict or None:
        {
            "goal_minute": int,
            "sot_max":     int,
            "total_goals": int,
            "over_field":  str,
        }
    The caller retrieves odds from the current row using ``over_field``.
    """
    SOT_MIN    = int(cfg.get("sot_min",    0))
    MIN_MINUTE = float(cfg.get("min_minute", 15))
    MAX_MINUTE = float(cfg.get("max_minute", 90))
    XG_REM_MIN = float(cfg.get("xg_rem_min", 0))
    # entry_buffer: extra minutes past MAX_MINUTE that the current row may be.
    # Used by LIVE detection to keep the signal alive while it matures (min_dur wait).
    # BT always passes max_minute=91 so this has no effect there.
    ENTRY_MAX  = MAX_MINUTE + float(cfg.get("entry_buffer", 0))

    curr_row = rows[curr_idx]
    curr_min_val = _to_float(curr_row.get("minuto", ""))
    if curr_min_val is None or curr_min_val < MIN_MINUTE or curr_min_val >= ENTRY_MAX:
        return None

    # Look for goal in last 3 captures (approx last 90 seconds)
    recent_goal = False
    goal_minute: Optional[int] = None
    for i in range(curr_idx, max(0, curr_idx - 3), -1):
        if i == 0:
            break
        row_now = rows[i]
        row_prev = rows[i - 1]
        curr_gl = int(_to_float(row_now.get("goles_local", "")) or 0)
        curr_gv = int(_to_float(row_now.get("goles_visitante", "")) or 0)
        prev_gl = int(_to_float(row_prev.get("goles_local", "")) or 0)
        prev_gv = int(_to_float(row_prev.get("goles_visitante", "")) or 0)
        if curr_gl + curr_gv > prev_gl + prev_gv:
            row_min_val = _to_float(row_now.get("minuto", ""))
            if row_min_val and MIN_MINUTE <= row_min_val <= MAX_MINUTE:
                recent_goal = True
                goal_minute = int(row_min_val)
                break

    if not recent_goal or goal_minute is None:
        return None

    # SoT filter
    sot_local_val    = _to_float(curr_row.get("tiros_puerta_local",    "")) or 0
    sot_visitante_val = _to_float(curr_row.get("tiros_puerta_visitante", "")) or 0
    sot_max = max(int(sot_local_val), int(sot_visitante_val))

    if SOT_MIN > 0 and sot_max < SOT_MIN:
        return None

    # xG remaining filter (optional — only evaluated if cfg.xg_rem_min > 0)
    if XG_REM_MIN > 0:
        synth = _compute_synthetic_at_trigger(rows, curr_idx)
        xg_rem = synth.get("xg_remaining")
        if xg_rem is None or xg_rem < XG_REM_MIN:
            return None

    # Compute total goals at current row
    final_gl = int(_to_float(curr_row.get("goles_local", "")) or 0)
    final_gv = int(_to_float(curr_row.get("goles_visitante", "")) or 0)
    total_goals = final_gl + final_gv

    over_field = _get_over_odds_field(total_goals)
    if not over_field:
        return None

    over_odds = _to_float(curr_row.get(over_field, ""))
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if over_odds is not None and odds_min > 0 and over_odds < odds_min:
        return None
    return {
        "goal_minute": goal_minute,
        "sot_max":     sot_max,
        "total_goals": total_goals,
        "over_field":  over_field,
        "over_odds":   over_odds,
    }


def _detect_pressure_cooker_trigger(
    rows: list,
    curr_idx: int,
    cfg: dict,
) -> Optional[dict]:
    """Detect Pressure Cooker trigger at a given row index.

    Trigger: score is a draw with at least 1 goal per team (not 0-0), minute in [min, max].

    ``cfg`` must contain:
        min_minute     : float  — lower bound for trigger minute
        max_minute     : float  — upper bound for trigger minute
        score_confirm  : int    — minimum rows with same score in last 6 (default 2)

    Returns dict or None:
        {
            "total_goals": int,
            "over_field":  str,
            "gl":          int,
            "gv":          int,
            "minuto":      float,
        }
    """
    MIN_MINUTE  = float(cfg.get("min_minute",    65))
    MAX_MINUTE  = float(cfg.get("max_minute",    75))
    CONFIRM_MIN = int(cfg.get("score_confirm",   2))

    curr_row = rows[curr_idx]
    minuto = _to_float(curr_row.get("minuto", ""))
    if minuto is None or minuto < MIN_MINUTE or minuto > MAX_MINUTE:
        return None

    estado = curr_row.get("estado_partido", "")
    if estado and estado != "en_juego":
        return None

    gl = _to_float(curr_row.get("goles_local", ""))
    gv = _to_float(curr_row.get("goles_visitante", ""))
    if gl is None or gv is None:
        return None
    gl_i, gv_i = int(gl), int(gv)

    # Must be a draw with goals (not 0-0)
    if gl_i != gv_i or (gl_i == 0 and gv_i == 0):
        return None

    # Optional xG guard: require minimum combined xG (0 = disabled)
    XG_SUM_MIN = float(cfg.get("xg_sum_min", 0))
    if XG_SUM_MIN > 0:
        xg_l = _to_float(curr_row.get("xg_local", ""))
        xg_v = _to_float(curr_row.get("xg_visitante", ""))
        if xg_l is None or xg_v is None or (xg_l + xg_v) < XG_SUM_MIN:
            return None

    # Score confirmation: last 6 rows up to curr_idx
    check_rows = rows[max(0, curr_idx - 5):curr_idx + 1]
    confirm_count = sum(
        1 for r in check_rows
        if _to_float(r.get("goles_local", "")) == gl
        and _to_float(r.get("goles_visitante", "")) == gv
    )
    if confirm_count < CONFIRM_MIN:
        return None

    total_goals = gl_i + gv_i
    over_field = _get_over_odds_field(total_goals)
    if not over_field:
        return None

    over_odds = _to_float(curr_row.get(over_field, ""))
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if over_odds is not None and odds_min > 0 and over_odds < odds_min:
        return None
    return {
        "total_goals": total_goals,
        "over_field":  over_field,
        "over_odds":   over_odds,
        "gl":          gl_i,
        "gv":          gv_i,
        "minuto":      minuto,
    }


# ── End GR9 shared helpers ────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# UNIFIED STRATEGY TRIGGER FUNCTIONS
# Each function: _detect_<strategy_name>_trigger(rows, curr_idx, cfg) -> dict | None
# Single source of truth for "should I bet?" logic — called identically by:
#   LIVE: detect_betting_signals()  → curr_idx = len(rows) - 1
#   BT:   analyze_strategy_*()      → curr_idx = idx (iterating all rows)
#   BT:   gen_*() generators        → curr_idx = idx (iterating all rows)
# Contract: only reads rows[0..curr_idx] — never looks at future rows.
#           No internal state — caller handles one-shot, min_dur, persistence.
# ─────────────────────────────────────────────────────────────────────────────

def _detect_back_draw_00_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """Unified Back Draw 0-0 trigger (rows, curr_idx, cfg) interface.

    Checks basic entry conditions (0-0 score, minute in range) then applies
    cfg-based filters (xg_max, poss_max, shots_max) via ``_detect_draw_filters``.

    ``cfg`` keys used:
        minute_min      : float  — minimum minute (default 30)
        minute_max      : float  — maximum minute (default 90, no upper limit)
        xg_max          : float  — max total xG (sentinel >= 1.0 = off)
        poss_max        : float  — max possession diff (sentinel >= 100 = off)
        shots_max       : float  — max total shots (sentinel >= 20 = off)

    Returns dict with raw stats, or None if conditions not met:
        {minuto, xg_total, poss_diff, shots_total, back_draw, passes}
    """
    row = rows[curr_idx]
    minuto = _to_float(row.get("minuto", ""))
    if minuto is None:
        return None
    if minuto < float(cfg.get("minute_min", 30)):
        return None
    if float(cfg.get("minute_max", 90)) < 90 and minuto >= float(cfg.get("minute_max", 90)):
        return None

    gl = _to_float(row.get("goles_local", ""))
    gv = _to_float(row.get("goles_visitante", ""))
    if gl is None or gv is None or int(gl) != 0 or int(gv) != 0:
        return None

    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    xg_total = ((xg_l or 0) + (xg_v or 0)) if (xg_l is not None or xg_v is not None) else None

    poss_l = _to_float(row.get("posesion_local", ""))
    poss_v = _to_float(row.get("posesion_visitante", ""))
    poss_diff = abs((poss_l or 50) - (poss_v or 50)) if (poss_l is not None or poss_v is not None) else None

    shots_l = _to_float(row.get("tiros_local", ""))
    shots_v = _to_float(row.get("tiros_visitante", ""))
    shots_total = ((shots_l or 0) + (shots_v or 0)) if (shots_l is not None or shots_v is not None) else None

    flags = _detect_draw_filters(
        xg_total=xg_total, poss_diff=poss_diff,
        shots_total=float(shots_total) if shots_total is not None else None,
        cfg=cfg,
    )

    if not flags["passes"]:
        return None

    return {
        "minuto":       minuto,
        "xg_total":     xg_total,
        "poss_diff":    poss_diff,
        "shots_total":  shots_total,
        "back_draw":    _to_float(row.get("back_draw", "")),
        **flags,
    }


def _detect_xg_underperformance_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """Unified xG Underperformance trigger (rows, curr_idx, cfg) interface.

    Thin wrapper over ``_detect_xg_underperf_candidates`` that extracts all
    required values from ``rows[curr_idx]`` before calling the internal helper.

    Returns the first qualifying candidate dict, or None if no candidates qualify.
    At most one team can qualify at any row (a team must be LOSING, so home and
    away cannot both qualify simultaneously).
    """
    row = rows[curr_idx]
    candidates = _detect_xg_underperf_candidates(
        xg_local=_to_float(row.get("xg_local", "")),
        xg_visitante=_to_float(row.get("xg_visitante", "")),
        goals_local=int(_to_float(row.get("goles_local", "")) or 0),
        goals_visitante=int(_to_float(row.get("goles_visitante", "")) or 0),
        sot_local=_to_float(row.get("tiros_puerta_local", "")) or 0,
        sot_visitante=_to_float(row.get("tiros_puerta_visitante", "")) or 0,
        minuto=_to_float(row.get("minuto", "")) or 0,
        rows=rows,
        row=row,
        cfg=cfg,
    )
    if not candidates:
        return None
    result = candidates[0]
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and result.get("back_odds", 999) < odds_min:
        return None
    return result


def _detect_momentum_xg_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """Unified Momentum Dominante xG trigger (rows, curr_idx, cfg) interface.

    Extracts row values, checks minute range, then delegates to the internal
    ``_detect_momentum_dominant`` helper.

    ``cfg`` keys used (same as ``_detect_momentum_dominant`` plus):
        min_m : float  — minimum minute (default 10)
        max_m : float  — maximum minute (default 80)

    Returns dict or None:
        {dominant_team, back_odds, sot_ratio_used, minuto,
         xg_underperf_local, xg_underperf_visitante}
    """
    row = rows[curr_idx]
    cfg = {
        **cfg,
        "sot_min": cfg.get("sot_min", cfg.get("sotMin", 2)),
        "sot_ratio_min": cfg.get("sot_ratio_min", cfg.get("sotRatioMin", 1.5)),
        "xg_underperf_min": cfg.get("xg_underperf_min", cfg.get("xgUnderperfMin", 0.3)),
        "min_odds": cfg.get("min_odds", cfg.get("odds_min", cfg.get("oddsMin", 1.5))),
        "max_odds": cfg.get("max_odds", cfg.get("odds_max", cfg.get("oddsMax", 4.0))),
    }
    minuto = _to_float(row.get("minuto", ""))
    if minuto is None:
        return None

    min_m = float(cfg.get("min_m", 10))
    max_m = float(cfg.get("max_m", 80))
    if not (min_m <= minuto <= max_m):
        return None

    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    if xg_l is None or xg_v is None:
        return None

    gl = _to_float(row.get("goles_local", "")) or 0
    gv = _to_float(row.get("goles_visitante", "")) or 0
    xg_underperf_local = xg_l - gl
    xg_underperf_visitante = xg_v - gv

    dominant_team, back_odds, sot_ratio_used = _detect_momentum_dominant(
        sot_local=_to_float(row.get("tiros_puerta_local", "")) or 0,
        sot_visitante=_to_float(row.get("tiros_puerta_visitante", "")) or 0,
        xg_underperf_local=xg_underperf_local,
        xg_underperf_visitante=xg_underperf_visitante,
        back_home=_to_float(row.get("back_home", "")),
        back_away=_to_float(row.get("back_away", "")),
        cfg=cfg,
    )

    if dominant_team is None:
        return None

    return {
        "dominant_team":           dominant_team,
        "back_odds":               back_odds,
        "sot_ratio_used":          sot_ratio_used,
        "minuto":                  minuto,
        "xg_underperf_local":      xg_underperf_local,
        "xg_underperf_visitante":  xg_underperf_visitante,
    }


def _detect_tarde_asia_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """Unified Tarde Asia trigger (rows, curr_idx, cfg) interface.

    Checks minute <= 15, valid goals data, available Over 2.5 odds, and
    delegates league detection to the internal ``_detect_tarde_asia_liga``
    helper.

    ``cfg`` keys used:
        match_name : str  — display name of the match (from match metadata)
        match_url  : str  — Betfair URL of the match (from match metadata)
        match_id   : str  — match identifier (from match metadata)

    Returns dict or None:
        {liga, back_over25, minuto}
    """
    row = rows[curr_idx]
    minuto = _to_float(row.get("minuto", ""))
    if minuto is None or minuto > 15:
        return None

    gl = _to_float(row.get("goles_local", ""))
    gv = _to_float(row.get("goles_visitante", ""))
    if gl is None or gv is None:
        return None

    back_over25 = _to_float(row.get("back_over25", ""))
    if back_over25 is None or back_over25 <= 1.0:
        return None

    liga = _detect_tarde_asia_liga(
        match_name=cfg.get("match_name", ""),
        match_url=cfg.get("match_url", ""),
        match_id=cfg.get("match_id", ""),
    )
    if liga == "Unknown":
        return None

    return {
        "liga":        liga,
        "back_over25": back_over25,
        "minuto":      minuto,
    }



# ── SD Strategy trigger functions ────────────────────────────────────────────

def _detect_over25_2goal_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Over 2.5 when a team leads by 2+ goals after stable odds.

    cfg keys: m_min, m_max, goal_diff_min, sot_total_min, odds_min, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    if curr_idx < 1:
        return None
    m_min = float(cfg.get("m_min", 55))
    m_max = float(cfg.get("m_max", 81))
    goal_diff_min = int(cfg.get("goal_diff_min", 2))
    sot_total_min = int(cfg.get("sot_total_min", 3))
    odds_min = float(cfg.get("odds_min", 1.5))
    odds_max = float(cfg.get("odds_max", 10.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)
    goal_diff = abs(gl - gv)
    if goal_diff < goal_diff_min:
        return None
    # Skip goal-transition row (odds may be stale)
    prev_row = rows[curr_idx - 1]
    prev_gl_f = _to_float(prev_row.get("goles_local", ""))
    prev_gv_f = _to_float(prev_row.get("goles_visitante", ""))
    if prev_gl_f is not None and prev_gv_f is not None:
        prev_diff = abs(int(prev_gl_f) - int(prev_gv_f))
        if prev_diff < goal_diff_min and goal_diff >= goal_diff_min:
            return None  # just_reached_lead — stale odds
    sot_l = int(_to_float(row.get("tiros_puerta_local", "")) or 0)
    sot_v = int(_to_float(row.get("tiros_puerta_visitante", "")) or 0)
    sot_total = sot_l + sot_v
    if sot_total < sot_total_min:
        return None
    odds = _to_float(row.get("back_over25", ""))
    if odds is None or odds <= 1.0 or not (odds_min <= odds <= odds_max):
        return None
    return {
        "minuto": m,
        "back_over25": odds,
        "goal_diff": goal_diff,
        "sot_total": sot_total,
        "total_goals_trigger": gl + gv,
    }


def _detect_under35_late_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Under 3.5 when goals at m_min-m_max, low xG.

    cfg keys: m_min, m_max, goals_exact (exact count), goals_min/goals_max (range), xg_max, odds_min, odds_max
    If goals_exact is set, checks total_now == goals_exact.
    Otherwise checks goals_min <= total_now <= goals_max (defaults: 2-4, superset mode).
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 65))
    m_max = float(cfg.get("m_max", 81))
    xg_max = float(cfg.get("xg_max", 3.0))
    odds_min = float(cfg.get("odds_min", 1.0))
    odds_max = float(cfg.get("odds_max", 8.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    total_now = int(gl_f) + int(gv_f)
    if "goals_exact" in cfg:
        if total_now != int(cfg["goals_exact"]):
            return None
    else:
        goals_min = int(cfg.get("goals_min", 2))
        goals_max = int(cfg.get("goals_max", 4))
        if not (goals_min <= total_now <= goals_max):
            return None
    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    if xg_l is None or xg_v is None:
        return None
    xg_total = xg_l + xg_v
    if xg_total > xg_max:
        return None
    odds = _to_float(row.get("back_under35", ""))
    if odds is None or odds <= 1.0 or not (odds_min <= odds <= odds_max):
        return None
    return {
        "minuto": m,
        "back_under35": odds,
        "xg_total": xg_total,
        "total_goals_trigger": total_now,
    }


def _detect_lay_over45_v3_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """LAY Over 4.5 V3 tight: goals<=goals_max, min m_min-m_max, odds <= odds_max.

    cfg keys: m_min, m_max, goals_max, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 55))
    m_max = float(cfg.get("m_max", 78))
    goals_max = int(cfg.get("goals_max", 2))
    odds_max = float(cfg.get("odds_max", 20.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    total_now = int(gl_f) + int(gv_f)
    if total_now > goals_max:
        return None
    odds = _to_float(row.get("lay_over45", ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None
    return {
        "minuto": m,
        "lay_over45": odds,
        "total_goals_trigger": total_now,
    }


def _detect_draw_xg_conv_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Draw when xG converges (both teams similar xG) in tied match.

    cfg keys: m_min, m_max, xg_diff_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 60))
    m_max = float(cfg.get("m_max", 83))
    xg_diff_max = float(cfg.get("xg_diff_max", 1.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    if int(gl_f) != int(gv_f):
        return None
    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    if xg_l is None or xg_v is None:
        return None
    xg_diff = abs(xg_l - xg_v)
    xg_total = xg_l + xg_v
    if xg_diff > xg_diff_max:
        return None
    if xg_total > 4.0:
        return None
    odds = _to_float(row.get("back_draw", ""))
    if odds is None or odds <= 1.0 or odds > 15:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_draw": odds,
        "xg_diff": round(xg_diff, 2),
        "xg_total": xg_total,
        "score_at_trigger": f"{int(gl_f)}-{int(gv_f)}",
    }


def _detect_poss_extreme_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Over 0.5 when possession is extremely one-sided at 0-0.

    cfg keys: m_min, m_max, poss_min
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 30))
    m_max = float(cfg.get("m_max", 53))
    poss_min = float(cfg.get("poss_min", 55))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    if int(gl_f) != 0 or int(gv_f) != 0:
        return None
    poss_l = _to_float(row.get("posesion_local", ""))
    poss_v = _to_float(row.get("posesion_visitante", ""))
    if poss_l is None or poss_v is None:
        return None
    poss_max = max(poss_l, poss_v)
    if poss_max < poss_min:
        return None
    odds = _to_float(row.get("back_over05", ""))
    if odds is None or odds <= 1.0 or odds > 5:
        return None
    return {
        "minuto": m,
        "back_over05": odds,
        "poss_max": poss_max,
    }


def _detect_longshot_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK the longshot team when they go winning (stable, not just-scored row).

    Pre-match odds are read from rows[:5] to identify the longshot team.
    cfg keys: m_min, m_max, xg_min, odds_min, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    if curr_idx < 1:
        return None
    m_min = float(cfg.get("m_min", 65))
    m_max = float(cfg.get("m_max", 88))
    xg_min = float(cfg.get("xg_min", 0.0))  # 0.0 = no xg filter by default (superset)
    odds_min = float(cfg.get("odds_min", 1.3))
    odds_max = float(cfg.get("odds_max", 10.0))
    # Determine longshot team from first valid pre-match odds
    ls_team = None
    for r in rows[:5]:
        bh = _to_float(r.get("back_home", ""))
        ba = _to_float(r.get("back_away", ""))
        if bh and ba and bh > 1 and ba > 1:
            ls_team = "local" if bh >= ba else "visitante"
            break
    if ls_team is None:
        return None

    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)

    # Check longshot is currently winning
    ls_winning = (ls_team == "local" and gl > gv) or (ls_team == "visitante" and gv > gl)
    if not ls_winning:
        return None

    # Skip goal-transition row (prev row longshot was not winning)
    prev_row = rows[curr_idx - 1]
    prev_gl_f = _to_float(prev_row.get("goles_local", ""))
    prev_gv_f = _to_float(prev_row.get("goles_visitante", ""))
    if prev_gl_f is not None and prev_gv_f is not None:
        prev_gl = int(prev_gl_f)
        prev_gv = int(prev_gv_f)
        prev_ls_winning = (ls_team == "local" and prev_gl > prev_gv) or \
                          (ls_team == "visitante" and prev_gv > prev_gl)
        if not prev_ls_winning:
            return None  # just_went_winning — stale odds

    if ls_team == "local":
        odds = _to_float(row.get("back_home", ""))
    else:
        odds = _to_float(row.get("back_away", ""))
    if odds is None or odds <= 1.0 or not (odds_min <= odds <= odds_max):
        return None

    xg_ls = _to_float(row.get(f"xg_{ls_team}", ""))
    if (xg_ls or 0) < xg_min:
        return None
    return {
        "minuto": m,
        "back_home" if ls_team == "local" else "back_away": odds,
        "longshot_team": ls_team,
        "xg_longshot": xg_ls or 0,
    }


def _detect_cs_00_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Correct Score 0-0 at m_min-m_max, low xG/SoT, odds odds_min-odds_max.

    cfg keys: m_min, m_max, xg_max, odds_min, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 28))
    m_max = float(cfg.get("m_max", 33))
    xg_max = float(cfg.get("xg_max", 1.5))
    odds_min = float(cfg.get("odds_min", 5.0))
    odds_max = float(cfg.get("odds_max", 12.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    if int(gl_f) != 0 or int(gv_f) != 0:
        return None
    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    if xg_l is None or xg_v is None:
        return None
    xg_total = xg_l + xg_v
    if xg_total > xg_max:
        return None
    sot_l = int(_to_float(row.get("tiros_puerta_local", "")) or 0)
    sot_v = int(_to_float(row.get("tiros_puerta_visitante", "")) or 0)
    sot_total = sot_l + sot_v
    if sot_total > 3:
        return None
    odds = _to_float(row.get("back_rc_0_0", ""))
    if odds is None or not (odds_min <= odds <= odds_max):
        return None
    return {
        "minuto": m,
        "back_rc_0_0": odds,
        "xg_total": xg_total,
        "sot_total": sot_total,
    }


def _detect_over25_2goals_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Over 2.5 when exactly 2 goals scored at m_min-m_max, not a goal-transition row.

    cfg keys: m_min, m_max, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    if curr_idx < 1:
        return None
    m_min = float(cfg.get("m_min", 48))
    m_max = float(cfg.get("m_max", 63))
    odds_max = float(cfg.get("odds_max", 5.0))
    row = rows[curr_idx]
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    total_now = int(gl_f) + int(gv_f)
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    if total_now != 2:
        return None
    # Skip goal-transition row
    prev_row = rows[curr_idx - 1]
    prev_gl_f = _to_float(prev_row.get("goles_local", ""))
    prev_gv_f = _to_float(prev_row.get("goles_visitante", ""))
    if prev_gl_f is not None and prev_gv_f is not None:
        prev_total = int(prev_gl_f) + int(prev_gv_f)
        if prev_total < total_now:
            return None
    odds = _to_float(row.get("back_over25", ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_over25": odds,
        "total_goals_trigger": total_now,
    }


def _detect_cs_close_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Correct Score 2-1 or 1-2 at m_min-m_max.

    cfg keys: m_min, m_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 67))
    m_max = float(cfg.get("m_max", 83))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)
    if not ((gl == 2 and gv == 1) or (gl == 1 and gv == 2)):
        return None
    col = f"back_rc_{gl}_{gv}"
    odds = _to_float(row.get(col, ""))
    if odds is None or odds <= 1.0:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    odds_max = float(cfg.get("odds_max", cfg.get("max_odds", 999)))
    if odds > odds_max:
        return None
    return {
        "minuto": m,
        col: odds,
        "trigger_score": f"{gl}-{gv}",
    }


def _detect_cs_one_goal_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Correct Score 1-0 or 0-1 at m_min-m_max.

    cfg keys: m_min, m_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 65))
    m_max = float(cfg.get("m_max", 88))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)
    if not ((gl == 1 and gv == 0) or (gl == 0 and gv == 1)):
        return None
    col = f"back_rc_{gl}_{gv}"
    odds = _to_float(row.get(col, ""))
    if odds is None or odds <= 1.0:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    odds_max = float(cfg.get("odds_max", cfg.get("max_odds", 999)))
    if odds > odds_max:
        return None
    return {
        "minuto": m,
        col: odds,
        "trigger_score": f"{gl}-{gv}",
    }


def _detect_draw_11_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Draw when score is exactly 1-1 at m_min-m_max.

    cfg keys: m_min, m_max, odds_min
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 68))
    m_max = float(cfg.get("m_max", 88))
    odds_min = float(cfg.get("odds_min", 1.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    if int(gl_f) != 1 or int(gv_f) != 1:
        return None
    odds = _to_float(row.get("back_draw", ""))
    if odds is None or odds <= 1.0 or odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_draw": odds,
    }


def _detect_ud_leading_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK the underdog who is leading at m_min-m_max.

    Pre-match odds are read from rows[:5] to identify the underdog team.
    cfg keys: m_min, m_max, ud_min_pre_odds, max_lead
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 53))
    m_max = float(cfg.get("m_max", 83))
    ud_min_pre_odds = float(cfg.get("ud_min_pre_odds", 1.5))
    max_lead = int(cfg.get("max_lead", 2))
    # Determine underdog from first valid pre-match odds
    first_home = None
    first_away = None
    for r in rows[:5]:
        bh = _to_float(r.get("back_home", ""))
        ba = _to_float(r.get("back_away", ""))
        if bh and ba and bh > 1 and ba > 1:
            first_home = bh
            first_away = ba
            break
    if first_home is None or first_away is None:
        return None
    if first_home > first_away:
        ud_team = "local"
        ud_pre_odds = first_home
    else:
        ud_team = "visitante"
        ud_pre_odds = first_away
    if ud_pre_odds < ud_min_pre_odds:
        return None

    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)

    if ud_team == "local":
        lead = gl - gv
        odds = _to_float(row.get("back_home", ""))
    else:
        lead = gv - gl
        odds = _to_float(row.get("back_away", ""))
    if lead <= 0 or lead > max_lead:
        return None
    if odds is None or odds <= 1.0:
        return None
    # Sanity check: if underdog is leading, live odds must be below pre-match odds.
    # If odds >= ud_pre_odds, the scraper likely swapped home/away selections.
    if odds >= ud_pre_odds:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_home" if ud_team == "local" else "back_away": odds,
        "ud_team": ud_team,
        "ud_pre_odds": ud_pre_odds,
        "lead": lead,
    }


def _detect_under35_3goals_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Under 3.5 when exactly 3 goals scored, m_min-m_max, xG < xg_max.

    cfg keys: m_min, m_max, xg_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 60))
    m_max = float(cfg.get("m_max", 88))
    xg_max = float(cfg.get("xg_max", 10.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    if int(gl_f) + int(gv_f) != 3:
        return None
    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    if xg_l is None or xg_v is None:
        return None
    xg_total = xg_l + xg_v
    if xg_total > xg_max:
        return None
    odds = _to_float(row.get("back_under35", ""))
    if odds is None or odds <= 1.01 or odds > 10:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_under35": odds,
        "xg_total": xg_total,
    }


def _detect_away_fav_leading_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK away team when they are pre-match favourite and leading, m_min-m_max.

    Pre-match odds are read from rows[0] to determine if away is favourite.
    cfg keys: m_min, m_max, max_lead, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    if not rows:
        return None
    m_min = float(cfg.get("m_min", 55))
    m_max = float(cfg.get("m_max", 90))
    max_lead = int(cfg.get("max_lead", 3))
    odds_max = float(cfg.get("odds_max", 50.0))
    # Determine if away is favourite from first row pre-match odds
    first_home = _to_float(rows[0].get("back_home", ""))
    first_away = _to_float(rows[0].get("back_away", ""))
    if first_home is None or first_away is None:
        return None
    if first_away >= first_home:
        return None  # away is NOT favourite

    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)
    if gv <= gl:
        return None  # away not leading
    lead = gv - gl
    if lead > max_lead:
        return None
    odds = _to_float(row.get("back_away", ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_away": odds,
        "lead": lead,
        "away_pre_odds": first_away,
    }


def _detect_home_fav_leading_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK home team when they are pre-match favourite and leading, m_min-m_max.

    Pre-match odds are read from rows[:5] to determine if home is favourite.
    cfg keys: m_min, m_max, max_lead, fav_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    if not rows:
        return None
    m_min = float(cfg.get("m_min", 62))
    m_max = float(cfg.get("m_max", 88))
    max_lead = int(cfg.get("max_lead", 3))
    fav_max = float(cfg.get("fav_max", 2.50))
    first_home = None
    first_away = None
    for r in rows[:5]:
        bh = _to_float(r.get("back_home", ""))
        ba = _to_float(r.get("back_away", ""))
        if bh and ba and bh > 1 and ba > 1:
            first_home = bh
            first_away = ba
            break
    if first_home is None or first_away is None:
        return None
    if first_home >= first_away:
        return None  # home is NOT favourite
    if first_home > fav_max:
        return None  # fav odds too high

    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)
    if gl <= gv:
        return None  # home not leading
    lead = gl - gv
    if lead > max_lead:
        return None
    odds = _to_float(row.get("back_home", ""))
    if odds is None or odds <= 1.0 or odds > 10:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_home": odds,
        "lead": lead,
        "home_pre_odds": first_home,
    }


def _detect_under45_3goals_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Under 4.5 when exactly 3 goals scored and xG < xg_max, m_min-m_max.

    cfg keys: m_min, m_max, xg_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 62))
    m_max = float(cfg.get("m_max", 88))
    xg_max = float(cfg.get("xg_max", 2.5))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    if int(gl_f) + int(gv_f) != 3:
        return None
    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    if xg_l is None or xg_v is None:
        return None
    xg_total = xg_l + xg_v
    if xg_total >= xg_max:
        return None
    odds = _to_float(row.get("back_under45", ""))
    if odds is None or odds <= 1.01 or odds > 10:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_under45": odds,
        "xg_total": xg_total,
    }


def _detect_cs_11_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK CS 1-1 when score is exactly 1-1 at m_min-m_max.

    cfg keys: m_min, m_max, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 72))
    m_max = float(cfg.get("m_max", 92))
    odds_max = float(cfg.get("odds_max", 999.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    if int(gl_f) != 1 or int(gv_f) != 1:
        return None
    odds = _to_float(row.get("back_rc_1_1", ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        "back_rc_1_1": odds,
        "trigger_score": "1-1",
    }


def _detect_cs_20_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK CS 2-0 or 0-2 when that exact score at m_min-m_max.

    cfg keys: m_min, m_max, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 72))
    m_max = float(cfg.get("m_max", 92))
    odds_max = float(cfg.get("odds_max", 999.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)
    if not ((gl == 2 and gv == 0) or (gl == 0 and gv == 2)):
        return None
    col = f"back_rc_{gl}_{gv}"
    odds = _to_float(row.get(col, ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        col: odds,
        "trigger_score": f"{gl}-{gv}",
    }


def _detect_cs_big_lead_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK CS 3-0/0-3/3-1/1-3 when that exact score at m_min-m_max.

    cfg keys: m_min, m_max, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 67))
    m_max = float(cfg.get("m_max", 88))
    odds_max = float(cfg.get("odds_max", 999.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)
    valid_scores = {(3, 0), (0, 3), (3, 1), (1, 3)}
    if (gl, gv) not in valid_scores:
        return None
    col = f"back_rc_{gl}_{gv}"
    odds = _to_float(row.get(col, ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None
    return {
        "minuto": m,
        col: odds,
        "trigger_score": f"{gl}-{gv}",
    }


def _detect_draw_equalizer_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Draw after underdog equalizes (favourite was leading, underdog tied it up).

    cfg keys: m_min, m_max, fav_pre_max, min_goals_each, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 65))
    m_max = float(cfg.get("m_max", 90))
    fav_pre_max = float(cfg.get("fav_pre_max", 2.5))
    min_goals_each = int(cfg.get("min_goals_each", 1))
    odds_max = float(cfg.get("odds_max", 8.0))

    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None

    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)

    # Score must be tied with at least min_goals_each each
    if gl != gv or gl < min_goals_each:
        return None

    # Determine pre-match favourite from first valid odds row
    first_home = None
    first_away = None
    for r in rows[:5]:
        bh = _to_float(r.get("back_home", ""))
        ba = _to_float(r.get("back_away", ""))
        if bh and ba and bh > 1 and ba > 1:
            first_home = bh
            first_away = ba
            break
    if first_home is None or first_away is None:
        return None

    # Favourite = lower pre-match odds; check fav_pre_max
    fav_team = "local" if first_home <= first_away else "visitante"
    fav_pre_odds = min(first_home, first_away)
    if fav_pre_odds > fav_pre_max:
        return None

    # Favourite must have been leading at some point before curr_idx
    fav_was_leading = False
    for r in rows[:curr_idx]:
        r_gl = _to_float(r.get("goles_local", ""))
        r_gv = _to_float(r.get("goles_visitante", ""))
        if r_gl is None or r_gv is None:
            continue
        r_gl_i = int(r_gl)
        r_gv_i = int(r_gv)
        if fav_team == "local" and r_gl_i > r_gv_i:
            fav_was_leading = True
            break
        elif fav_team == "visitante" and r_gv_i > r_gl_i:
            fav_was_leading = True
            break

    if not fav_was_leading:
        return None

    odds = _to_float(row.get("back_draw", ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None

    return {
        "minuto": m,
        "back_draw": odds,
    }


def _detect_draw_22_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Draw when score is exactly 2-2 at m_min-m_max.

    cfg keys: m_min, m_max, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 70))
    m_max = float(cfg.get("m_max", 90))
    odds_max = float(cfg.get("odds_max", 8.0))

    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None

    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    if int(gl_f) != 2 or int(gv_f) != 2:
        return None

    odds = _to_float(row.get("back_draw", ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None
    odds_min = float(cfg.get("odds_min", cfg.get("min_odds", 0)))
    if odds_min > 0 and odds < odds_min:
        return None

    return {
        "minuto": m,
        "back_draw": odds,
    }


def _detect_lay_over45_blowout_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """LAY Over 4.5 in blowout: score 3-0/0-3 at m_min-m_max, with low SoT
    in the post_window minutes after the 3rd goal (intensity has dropped).

    cfg keys: m_min, m_max, post_window, sot_max, odds_max, include_31
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 60))
    m_max = float(cfg.get("m_max", 75))
    post_window = float(cfg.get("post_window", 10))
    sot_max = int(cfg.get("sot_max", 1))
    odds_max = float(cfg.get("odds_max", 15.0))
    include_31 = bool(int(cfg.get("include_31", 0)))

    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None

    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    gl = int(gl_f)
    gv = int(gv_f)

    valid_scores = [(3, 0), (0, 3), (3, 1), (1, 3)] if include_31 else [(3, 0), (0, 3)]
    if (gl, gv) not in valid_scores:
        return None

    total_goals = gl + gv

    # Find the minute when the Nth goal was scored (first row where total == total_goals)
    goal_minute = None
    for i in range(curr_idx + 1):
        r = rows[i]
        r_gl = _to_float(r.get("goles_local", ""))
        r_gv = _to_float(r.get("goles_visitante", ""))
        if r_gl is None or r_gv is None:
            continue
        if int(r_gl) + int(r_gv) >= total_goals:
            gm = _to_float(r.get("minuto", ""))
            if gm is not None:
                goal_minute = gm
            break

    if goal_minute is None:
        return None

    # Require at least post_window minutes since the scoring goal
    if m - goal_minute < post_window:
        return None

    # SoT are cumulative in CSVs — measure delta from goal_minute to now
    sot_at_goal_l, sot_at_goal_v = None, None
    for i in range(curr_idx + 1):
        r = rows[i]
        r_m = _to_float(r.get("minuto", ""))
        if r_m is None or r_m < goal_minute:
            continue
        s_l = _to_float(r.get("sot_local", ""))
        s_v = _to_float(r.get("sot_visitante", ""))
        if s_l is not None and s_v is not None:
            sot_at_goal_l = s_l
            sot_at_goal_v = s_v
        break

    sot_now_l = _to_float(row.get("sot_local", ""))
    sot_now_v = _to_float(row.get("sot_visitante", ""))

    # SoT check is optional: only applied when data is available (Tier-2 stat).
    # When missing, we rely solely on post_window as the intensity-drop signal.
    sot_post = None
    if sot_at_goal_l is not None and sot_now_l is not None and sot_now_v is not None:
        sot_post = max(0, int(sot_now_l) + int(sot_now_v) - int(sot_at_goal_l) - int(sot_at_goal_v or 0))
        if sot_post > sot_max:
            return None

    odds = _to_float(row.get("lay_over45", ""))
    if odds is None or odds <= 1.0 or odds > odds_max:
        return None

    return {
        "minuto": m,
        "lay_over45": odds,
        "goal_minute": goal_minute,
        "sot_post": sot_post,
    }


def _detect_over35_early_goals_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """BACK Over 3.5 when exactly 3 goals scored before m_max (early high-scoring match).

    Edge: market anchors Over 3.5 on pre-match xG. When 3 goals arrive before
    minute 65, the match has proven high-scoring intent beyond model predictions.
    Anti-tautology: triggers ONLY on exactly 3 goals (not 4+, which is already won).

    cfg keys: m_min, m_max, odds_min, odds_max
    Returns dict with trigger data or None if no trigger at this row.
    """
    m_min = float(cfg.get("m_min", 40))
    m_max = float(cfg.get("m_max", 65))
    odds_min = float(cfg.get("odds_min", 1.8))
    odds_max = float(cfg.get("odds_max", 8.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl_f = _to_float(row.get("goles_local", ""))
    gv_f = _to_float(row.get("goles_visitante", ""))
    if gl_f is None or gv_f is None:
        return None
    # Exactly 3 goals — anti-tautology: 4+ means Over 3.5 already won
    if int(gl_f) + int(gv_f) != 3:
        return None
    odds = _to_float(row.get("back_over35", ""))
    if odds is None or not (odds_min <= odds <= odds_max):
        return None
    return {
        "minuto": m,
        "back_over35": odds,
        "goals_total": 3,
        "score": f"{int(gl_f)}-{int(gv_f)}",
    }


def _detect_lay_draw_away_leading_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """LAY Draw when away leads by exactly 1 + total xG below threshold.

    Edge: market overprices draw probability when away leads in low-xG match.
    Home team has shown no attacking quality; away can park the bus.
    Anti-tautology: only fires when away leads by EXACTLY 1 (not 2+).

    cfg keys: m_min, m_max, xg_max, odds_min, odds_max
    """
    m_min = float(cfg.get("m_min", 55))
    m_max = float(cfg.get("m_max", 80))
    xg_max = float(cfg.get("xg_max", 1.8))
    odds_min = float(cfg.get("odds_min", 2.0))
    odds_max = float(cfg.get("odds_max", 10.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl = _to_float(row.get("goles_local", ""))
    gv = _to_float(row.get("goles_visitante", ""))
    if gl is None or gv is None:
        return None
    # Away leads by exactly 1 (anti-tautology: not 2+ where draw is already very unlikely)
    if not (int(gv) - int(gl) == 1):
        return None
    # Low xG filter
    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    if xg_l is not None and xg_v is not None:
        if xg_l + xg_v >= xg_max:
            return None
    # Odds check
    odds = _to_float(row.get("lay_draw", ""))
    if odds is None or not (odds_min <= odds <= odds_max):
        return None
    return {
        "minuto": m,
        "lay_draw": odds,
        "score": f"{int(gl)}-{int(gv)}",
        "xg_total": round((xg_l or 0) + (xg_v or 0), 2),
    }


def _detect_lay_cs11_trigger(rows: list, curr_idx: int, cfg: dict) -> Optional[dict]:
    """LAY Correct Score 1-1 when score is exactly 0-1 (late match).

    Edge: CS 1-1 is systematically overpriced at 0-1 late in match.
    Market implies ~12-15% probability; actual rate is only 4%.
    Anti-tautology: ONLY triggers at score 0-1 (the only away+1 state
    where CS 1-1 is still mathematically reachable).

    cfg keys: m_min, m_max, odds_min, odds_max
    """
    m_min = float(cfg.get("m_min", 60))
    m_max = float(cfg.get("m_max", 85))
    odds_min = float(cfg.get("odds_min", 1.5))
    odds_max = float(cfg.get("odds_max", 50.0))
    row = rows[curr_idx]
    m = _to_float(row.get("minuto", ""))
    if m is None or not (m_min <= m <= m_max):
        return None
    gl = _to_float(row.get("goles_local", ""))
    gv = _to_float(row.get("goles_visitante", ""))
    if gl is None or gv is None:
        return None
    # Must be exactly 0-1: ONLY valid state where CS 1-1 is still reachable
    if int(gl) != 0 or int(gv) != 1:
        return None
    # Odds check
    odds = _to_float(row.get("lay_rc_1_1", ""))
    if odds is None or not (odds_min <= odds <= odds_max):
        return None
    return {
        "minuto": m,
        "lay_rc_1_1": odds,
        "score": "0-1",
    }


# ── End unified strategy trigger functions ───────────────────────────────────
