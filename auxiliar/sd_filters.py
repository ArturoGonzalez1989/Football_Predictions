"""
Filter functions and PARAMS/OPTS for the 19 new strategies.
These are designed to be injected into:
  1. optimize.py — as _filter_sd_* functions + PARAMS dicts + OPTS arrays
  2. The notebook — as _apply_sd_* functions

The pattern mirrors exactly the existing strategies in both files.
"""


# ═══════════════════════════════════════════════════════════════════════════════
# A. PARAMS dicts for optimize.py (version -> params mapping)
#    Strategies #9-#11 are variants of #1 so they share the same filter.
#    The "version" approach lets the optimizer pick the best LAY O4.5 variant.
# ═══════════════════════════════════════════════════════════════════════════════

# --- #1/#9/#10/#11 merged as LAY_OVER45 with 4 versions ---
LAY_OVER45_PARAMS = {
    "v1": dict(min_min=65, min_max=75, goals_max=2, odds_max=15),
    "v3": dict(min_min=55, min_max=75, goals_max=1, odds_max=15),
    "v2v4": dict(min_min=55, min_max=75, goals_max=2, odds_max=15, xg_max=2.0),
    "late": dict(min_min=68, min_max=78, goals_max=2, odds_max=15),
}

# --- #2 BACK Leader Dom ---
LEADER_DOM_PARAMS = {
    "v1": dict(min_min=55, min_max=70, sot_min=4, sot_max_rival=1),
    "v2": dict(min_min=55, min_max=80, sot_min=3, sot_max_rival=2),
    "v3": dict(min_min=50, min_max=75, sot_min=3, sot_max_rival=1),
}

# --- #3 BACK Over 2.5 from 2-Goal ---
OVER25_2GOAL_PARAMS = {
    "v1": dict(min_min=55, min_max=78, goal_diff_min=2, sot_total_min=3, odds_min=1.5, odds_max=8.0),
    "v3": dict(min_min=55, min_max=75, goal_diff_min=2, sot_total_min=4, odds_min=1.5, odds_max=8.0),
    "v4": dict(min_min=55, min_max=78, goal_diff_min=2, sot_total_min=3, odds_min=1.5, odds_max=8.0, xg_min=0.5),
}

# --- #5 BACK Draw After Equalizer --- (on/off, params in grid)
# --- #6 BACK Under 2.5 Scoreless --- (on/off, params in grid)
# --- #7 BACK Under 3.5 Late --- (on/off, params in grid)
# --- #8 BACK Draw Late Stalemate --- (on/off, params in grid)


# ═══════════════════════════════════════════════════════════════════════════════
# B. OPTS arrays for Phase 1 of optimize.py
# ═══════════════════════════════════════════════════════════════════════════════

LAY_O45_OPTS = ["off", "v1", "v3", "v2v4", "late"]
LEADER_DOM_OPTS = ["off", "v1", "v2", "v3"]
OVER25_2G_OPTS = ["off", "v1", "v3", "v4"]
# Strategies #4-#8 and #12-#28 use ON/OFF toggle
CONFLUENCE_OPTS = ["off", "on"]
DRAW_EQ_OPTS = ["off", "on"]
UNDER25_SCL_OPTS = ["off", "on"]
UNDER35_LATE_OPTS = ["off", "on"]
DRAW_STL_OPTS = ["off", "on"]
DRAW_XG_CONV_OPTS = ["off", "on"]
CORNER_SOT_OPTS = ["off", "on"]
OVER25_2G_V4_OPTS = ["off", "on"]
OVER35_FH_OPTS = ["off", "on"]
OVER25_11_OPTS = ["off", "on"]
POSS_EXTREME_OPTS = ["off", "on"]
BACK_LONGSHOT_OPTS = ["off", "on"]
CS_00_OPTS = ["off", "on"]
OVER25_2GOALS_OPTS = ["off", "on"]
LAY_OVER25_SCL_OPTS = ["off", "on"]
LAY_OVER15_SCL_OPTS = ["off", "on"]
UNDER25_1GOAL_OPTS = ["off", "on"]
LAY_UNDER25_11_OPTS = ["off", "on"]
CS_CLOSE_OPTS = ["off", "on"]
CS_ONE_GOAL_OPTS = ["off", "on"]
DRAW_11_OPTS = ["off", "on"]
UD_LEADING_OPTS = ["off", "on"]
UNDER35_3GOALS_OPTS = ["off", "on"]
AWAY_FAV_LEADING_OPTS = ["off", "on"]
HOME_FAV_LEADING_OPTS = ["off", "on"]
UNDER45_3GOALS_OPTS = ["off", "on"]


# ═══════════════════════════════════════════════════════════════════════════════
# C. Filter functions for optimize.py
#    Pattern: _filter_sd_*(bets, version) -> filtered list
# ═══════════════════════════════════════════════════════════════════════════════

def _fv(b, key):
    v = b.get(key)
    if v is None: return None
    try: return float(v)
    except (ValueError, TypeError): return None


# #1/#9/#10/#11 — LAY Over 4.5 (versioned)
def _filter_sd_lay_over45(bets, v):
    if v == "off" or v not in LAY_OVER45_PARAMS:
        return []
    p = LAY_OVER45_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") != "lay_over45":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        tg = _fv(b, "total_goals_trigger")
        if tg is not None and tg > p["goals_max"]:
            continue
        od = _fv(b, "lay_over45_odds")
        if od is not None and od > p["odds_max"]:
            continue
        if "xg_max" in p:
            xt = _fv(b, "xg_total")
            if xt is not None and xt >= p["xg_max"]:
                continue
        result.append(b)
    return result


# #2 — BACK Leader Dom (versioned)
def _filter_sd_leader_dom(bets, v):
    if v == "off" or v not in LEADER_DOM_PARAMS:
        return []
    p = LEADER_DOM_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") != "back_leader_dom":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        ls = _fv(b, "leader_sot")
        if ls is not None and ls < p["sot_min"]:
            continue
        rs = _fv(b, "rival_sot")
        if rs is not None and rs > p["sot_max_rival"]:
            continue
        result.append(b)
    return result


# #3 — BACK Over 2.5 from 2-Goal (versioned)
def _filter_sd_over25_2goal(bets, v):
    if v == "off" or v not in OVER25_2GOAL_PARAMS:
        return []
    p = OVER25_2GOAL_PARAMS[v]
    result = []
    for b in bets:
        if b.get("strategy") != "over25_2goal":
            continue
        mn = _fv(b, "minuto")
        if mn is not None and mn < p["min_min"]:
            continue
        if mn is not None and mn >= p["min_max"]:
            continue
        gd = _fv(b, "goal_diff")
        if gd is not None and gd < p["goal_diff_min"]:
            continue
        st = _fv(b, "sot_total")
        if st is not None and st < p["sot_total_min"]:
            continue
        od = _fv(b, "back_over25_odds")
        if od is not None:
            if od < p.get("odds_min", 0):
                continue
            if od > p.get("odds_max", 999):
                continue
        if "xg_min" in p:
            xt = _fv(b, "xg_total")
            if xt is not None and xt < p["xg_min"]:
                continue
        result.append(b)
    return result


# #4 — Confluence Over 2.5 (on/off with grid params)
def _filter_sd_confluence(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "confluence_over25"]


# #5 — Draw After Equalizer (on/off)
def _filter_sd_draw_eq(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "draw_equalizer"]


# #6 — Under 2.5 Scoreless (on/off)
def _filter_sd_under25_scl(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "under25_scoreless"]


# #7 — Under 3.5 Late (on/off)
def _filter_sd_under35_late(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "under35_late"]


# #8 — Draw Late Stalemate (on/off)
def _filter_sd_draw_stl(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "draw_stalemate"]


# #12 — Draw xG Convergence (on/off)
def _filter_sd_draw_xg_conv(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "draw_xg_conv"]


# #13 — Corner+SoT Over 2.5 (on/off)
def _filter_sd_corner_sot(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "corner_sot_over25"]


# #14 — Over 2.5 2-Goal V4 (on/off — variant uses separate superset)
def _filter_sd_over25_2g_v4(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "over25_2goal_v4"]


# #15 — Over 3.5 First Half Goals (on/off)
def _filter_sd_over35_fh(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "over35_fh_goals"]


# #16 — Over 2.5 from 1-1 (on/off)
def _filter_sd_over25_11(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "over25_from_11"]


# #17 — Possession Extreme (on/off)
def _filter_sd_poss_extreme(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "poss_extreme"]


# #18 — Back Longshot (on/off)
def _filter_sd_back_longshot(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "back_longshot"]


# #19 — CS 0-0 (on/off)
def _filter_sd_cs_00(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "cs_00"]


# ═══════════════════════════════════════════════════════════════════════════════
# D. Notebook _apply_* functions (with grid params)
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_sd_lay_over45(bets, cfg):
    """Filter LAY Over 4.5 bets with grid params."""
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 65)
    mx = cfg.get('m_max', 75)
    gmax = cfg.get('goals_max', 2)
    omax = cfg.get('odds_max', 15)
    xgmax = cfg.get('xg_max', 999)
    return [b for b in bets if b.get('strategy') == 'lay_over45'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('total_goals_trigger') or 0) <= gmax
            and (b.get('lay_over45_odds') or 99) <= omax
            and (b.get('xg_total') or 0) < xgmax]


def _apply_sd_lay_over45_v3(bets, cfg):
    """Filter LAY Over 4.5 V3 bets (strategy='lay_over45_v3') with grid params."""
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 55)
    mx = cfg.get('m_max', 75)
    gmax = cfg.get('goals_max', 1)
    omax = cfg.get('odds_max', 15)
    return [b for b in bets if b.get('strategy') == 'lay_over45_v3'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('total_goals_trigger') or 0) <= gmax
            and (b.get('lay_over45_odds') or 99) <= omax]


def _apply_sd_lay_over45_v2v4(bets, cfg):
    """Filter LAY Over 4.5 V2+V4 bets (strategy='lay_over45_v2v4') with grid params."""
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 55)
    mx = cfg.get('m_max', 75)
    gmax = cfg.get('goals_max', 2)
    omax = cfg.get('odds_max', 15)
    xgmax = cfg.get('xg_max', 2.0)
    return [b for b in bets if b.get('strategy') == 'lay_over45_v2v4'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('total_goals_trigger') or 0) <= gmax
            and (b.get('lay_over45_odds') or 99) <= omax
            and (b.get('xg_total') or 0) < xgmax]


def _apply_sd_lay_over45_late(bets, cfg):
    """Filter LAY Over 4.5 Late bets (strategy='lay_over45_late') with grid params."""
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 68)
    mx = cfg.get('m_max', 78)
    gmax = cfg.get('goals_max', 2)
    omax = cfg.get('odds_max', 15)
    return [b for b in bets if b.get('strategy') == 'lay_over45_late'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('total_goals_trigger') or 0) <= gmax
            and (b.get('lay_over45_odds') or 99) <= omax]


def _apply_sd_leader_dom(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 55)
    mx = cfg.get('m_max', 70)
    smin = cfg.get('sot_min', 4)
    sriv = cfg.get('sot_max_rival', 1)
    return [b for b in bets if b.get('strategy') == 'back_leader_dom'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('leader_sot') or 0) >= smin
            and (b.get('rival_sot') or 99) <= sriv]


def _apply_sd_over25_2goal(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 55)
    mx = cfg.get('m_max', 78)
    gd = cfg.get('goal_diff_min', 2)
    smin = cfg.get('sot_total_min', 3)
    omin = cfg.get('odds_min', 1.5)
    omax = cfg.get('odds_max', 8.0)
    xgmin = cfg.get('xg_min', 0)
    return [b for b in bets if b.get('strategy') == 'over25_2goal'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('goal_diff') or 0) >= gd
            and (b.get('sot_total') or 0) >= smin
            and omin <= (b.get('back_over25_odds') or 0) <= omax
            and (b.get('xg_total') or 0) >= xgmin]


def _apply_sd_confluence(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 50)
    mx = cfg.get('m_max', 70)
    smin = cfg.get('sot_total_min', 4)
    lb = cfg.get('lookback', 4)
    return [b for b in bets if b.get('strategy') == 'confluence_over25'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('sot_total') or 0) >= smin]


def _apply_sd_draw_eq(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 58)
    mx = cfg.get('m_max', 85)
    omin = cfg.get('odds_min', 2.0)
    omax = cfg.get('odds_max', 15.0)
    return [b for b in bets if b.get('strategy') == 'draw_equalizer'
            and mm <= (b.get('minuto') or 0) < mx
            and omin <= (b.get('back_draw_eq_odds') or 0) <= omax]


def _apply_sd_under25_scl(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 64)
    mx = cfg.get('m_max', 80)
    xgmax = cfg.get('xg_max', 2.0)
    return [b for b in bets if b.get('strategy') == 'under25_scoreless'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('xg_total') or 0) < xgmax]


def _apply_sd_under35_late(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 65)
    mx = cfg.get('m_max', 78)
    gexact = cfg.get('goals_exact', 3)
    xgmax = cfg.get('xg_max', 2.0)
    omin = cfg.get('odds_min', 1.1)
    omax = cfg.get('odds_max', 5.0)
    return [b for b in bets if b.get('strategy') == 'under35_late'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('total_goals_trigger') or 0) == gexact
            and (b.get('xg_total') or 0) < xgmax
            and omin <= (b.get('back_under35_odds') or 0) <= omax]


def _apply_sd_draw_stl(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 70)
    mx = cfg.get('m_max', 90)
    xg_res_min = cfg.get('xg_res_min', -0.5)
    omin = cfg.get('odds_min', 1.5)
    omax = cfg.get('odds_max', 10.0)
    return [b for b in bets if b.get('strategy') == 'draw_stalemate'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('xg_residual') or -99) >= xg_res_min
            and omin <= (b.get('back_draw_stl_odds') or 0) <= omax]


def _apply_sd_draw_xg_conv(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 60)
    mx = cfg.get('m_max', 80)
    xg_diff_max = cfg.get('xg_diff_max', 0.5)
    return [b for b in bets if b.get('strategy') == 'draw_xg_conv'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('xg_diff') or 99) <= xg_diff_max]


def _apply_sd_corner_sot(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 45)
    mx = cfg.get('m_max', 75)
    smin = cfg.get('sot_min', 4)
    cmin = cfg.get('corners_min', 5)
    return [b for b in bets if b.get('strategy') == 'corner_sot_over25'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('sot_total') or 0) >= smin
            and (b.get('corners_total') or 0) >= cmin]


def _apply_sd_over25_2g_v4(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 55)
    mx = cfg.get('m_max', 78)
    gd = cfg.get('goal_diff_min', 2)
    smin = cfg.get('sot_total_min', 3)
    xgmin = cfg.get('xg_min', 0.5)
    return [b for b in bets if b.get('strategy') == 'over25_2goal_v4'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('goal_diff') or 0) >= gd
            and (b.get('sot_total') or 0) >= smin
            and (b.get('xg_total') or 0) >= xgmin]


def _apply_sd_over35_fh(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 45)
    mx = cfg.get('m_max', 60)
    gmin = cfg.get('goals_min', 2)
    return [b for b in bets if b.get('strategy') == 'over35_fh_goals'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('total_goals_trigger') or 0) >= gmin]


def _apply_sd_over25_11(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 50)
    mx = cfg.get('m_max', 70)
    smin = cfg.get('sot_total_min', 4)
    return [b for b in bets if b.get('strategy') == 'over25_from_11'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('sot_total') or 0) >= smin]


def _apply_sd_poss_extreme(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 30)
    mx = cfg.get('m_max', 50)
    poss_min = cfg.get('poss_min', 58)
    return [b for b in bets if b.get('strategy') == 'poss_extreme'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('poss_max') or 0) >= poss_min]


def _apply_sd_back_longshot(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 65)
    mx = cfg.get('m_max', 90)
    xg_min = cfg.get('xg_min', 0.2)
    omin = cfg.get('odds_min', 1.3)
    omax = cfg.get('odds_max', 8.0)
    return [b for b in bets if b.get('strategy') == 'back_longshot'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('xg_longshot') or 0) >= xg_min
            and omin <= (b.get('back_longshot_odds') or 0) <= omax]


def _apply_sd_cs_00(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 28)
    mx = cfg.get('m_max', 30)
    xgmax = cfg.get('xg_max', 1.5)
    smax = cfg.get('sot_max', 3)
    omin = cfg.get('odds_min', 5.0)
    omax = cfg.get('odds_max', 12.0)
    return [b for b in bets if b.get('strategy') == 'cs_00'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('xg_total') or 0) <= xgmax
            and (b.get('sot_total') or 0) <= smax
            and omin <= (b.get('back_cs_00_odds') or 0) <= omax]


# ═══════════════════════════════════════════════════════════════════════════════
# E. Filter + Apply functions for R7-R10 strategies (#20-#28)
# ═══════════════════════════════════════════════════════════════════════════════

# #20 — BACK Over 2.5 from Two Goals (H39)
def _filter_sd_over25_2goals(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "over25_2goals"]


def _apply_sd_over25_2goals(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 50)
    mx = cfg.get('m_max', 60)
    omax = cfg.get('odds_max', 4.0)
    return [b for b in bets if b.get('strategy') == 'over25_2goals'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('back_over25_odds') or 99) <= omax]


# #21 — LAY Over 2.5 Scoreless (H41)
def _filter_sd_lay_over25_scl(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "lay_over25_scoreless"]


def _apply_sd_lay_over25_scl(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 60)
    mx = cfg.get('m_max', 70)
    lmax = cfg.get('lay_max', 20.0)
    return [b for b in bets if b.get('strategy') == 'lay_over25_scoreless'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('lay_over25_odds') or 99) <= lmax]


# #22 — LAY Over 1.5 Scoreless Fortress (H44)
def _filter_sd_lay_over15_scl(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "lay_over15_scoreless"]


def _apply_sd_lay_over15_scl(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 68)
    mx = cfg.get('m_max', 78)
    lmax = cfg.get('lay_max', 8.0)
    return [b for b in bets if b.get('strategy') == 'lay_over15_scoreless'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('lay_over15_odds') or 99) <= lmax]


# #23 — BACK Under 2.5 One-Goal Late (H46)
def _filter_sd_under25_1goal(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "under25_one_goal"]


def _apply_sd_under25_1goal(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 75)
    mx = cfg.get('m_max', 85)
    xgmax = cfg.get('xg_max', 2.0)
    smax = cfg.get('sot_max', 6)
    return [b for b in bets if b.get('strategy') == 'under25_one_goal'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('xg_total') or 0) <= xgmax
            and (b.get('sot_total') or 0) <= smax]


# #24 — LAY Under 2.5 Tied at 1-1 (H48)
def _filter_sd_lay_under25_11(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "lay_under25_tied"]


def _apply_sd_lay_under25_11(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 55)
    mx = cfg.get('m_max', 65)
    lmax = cfg.get('lay_max', 2.5)
    return [b for b in bets if b.get('strategy') == 'lay_under25_tied'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('lay_under25_odds') or 99) <= lmax]


# #25 — BACK Correct Score 2-1/1-2 (H49)
def _filter_sd_cs_close(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "cs_close"]


def _apply_sd_cs_close(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 70)
    mx = cfg.get('m_max', 80)
    return [b for b in bets if b.get('strategy') == 'cs_close'
            and mm <= (b.get('minuto') or 0) < mx]


# #26 — BACK Correct Score 1-0/0-1 (H53)
def _filter_sd_cs_one_goal(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "cs_one_goal"]


def _apply_sd_cs_one_goal(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 68)
    mx = cfg.get('m_max', 85)
    return [b for b in bets if b.get('strategy') == 'cs_one_goal'
            and mm <= (b.get('minuto') or 0) < mx]


# #27 — BACK Draw at 1-1 (H58)
def _filter_sd_draw_11(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "draw_11"]


def _apply_sd_draw_11(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 70)
    mx = cfg.get('m_max', 85)
    omin = cfg.get('odds_min', 1.5)
    return [b for b in bets if b.get('strategy') == 'draw_11'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('back_draw_11_odds') or 0) >= omin]


# #28 — BACK Underdog Leading (H59)
def _filter_sd_ud_leading(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "ud_leading"]


def _apply_sd_ud_leading(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 55)
    mx = cfg.get('m_max', 80)
    ud_pre_min = cfg.get('ud_min_pre_odds', 2.0)
    max_lead = cfg.get('max_lead', 1)
    return [b for b in bets if b.get('strategy') == 'ud_leading'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('ud_pre_odds') or 0) >= ud_pre_min
            and (b.get('lead') or 99) <= max_lead]


# #29 — BACK Under 3.5 Three-Goal Lid (H66)
def _filter_sd_under35_3goals(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "under35_3goals"]


def _apply_sd_under35_3goals(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 65)
    mx = cfg.get('m_max', 82)
    xgmax = cfg.get('xg_max', 99.0)
    return [b for b in bets if b.get('strategy') == 'under35_3goals'
            and mm <= (b.get('minuto') or 0) < mx
            and (xgmax >= 90 or (b.get('xg_total') or 0) < xgmax)]


# #30 — BACK Away Favourite Leading Late (H67)
def _filter_sd_away_fav_leading(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "away_fav_leading"]


def _apply_sd_away_fav_leading(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 60)
    mx = cfg.get('m_max', 85)
    max_lead = cfg.get('max_lead', 1)
    odds_max = cfg.get('odds_max', 5.0)
    return [b for b in bets if b.get('strategy') == 'away_fav_leading'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('lead') or 99) <= max_lead
            and (b.get('back_away_odds') or 99) <= odds_max]


# #31 — BACK Home Favourite Leading Late (H70)
def _filter_sd_home_fav_leading(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "home_fav_leading"]


def _apply_sd_home_fav_leading(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 65)
    mx = cfg.get('m_max', 85)
    max_lead = cfg.get('max_lead', 3)
    fav_max = cfg.get('fav_max', 2.5)
    return [b for b in bets if b.get('strategy') == 'home_fav_leading'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('lead') or 99) <= max_lead
            and (b.get('home_pre_odds') or 99) <= fav_max]


# #32 — BACK Under 4.5 Three Goals Low xG (H71)
def _filter_sd_under45_3goals(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "under45_3goals"]


def _apply_sd_under45_3goals(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 65)
    mx = cfg.get('m_max', 85)
    xgmax = cfg.get('xg_max', 2.0)
    return [b for b in bets if b.get('strategy') == 'under45_3goals'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('xg_total') or 0) < xgmax]


# #33 — BACK CS 1-1 Late (H77)
def _filter_sd_cs_11(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "cs_11"]


def _apply_sd_cs_11(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 75)
    mx = cfg.get('m_max', 90)
    odds_max = cfg.get('odds_max', 8.0)
    return [b for b in bets if b.get('strategy') == 'cs_11'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('back_cs_odds') or 99) <= odds_max]


# #34 — BACK CS 2-0/0-2 Late (H79)
def _filter_sd_cs_20(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "cs_20"]


def _apply_sd_cs_20(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 75)
    mx = cfg.get('m_max', 90)
    odds_max = cfg.get('odds_max', 10.0)
    return [b for b in bets if b.get('strategy') == 'cs_20'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('back_cs_odds') or 99) <= odds_max]


# #35 — BACK CS Big Lead Late (H81)
def _filter_sd_cs_big_lead(bets, v):
    if v == "off":
        return []
    return [b for b in bets if b.get("strategy") == "cs_big_lead"]


def _apply_sd_cs_big_lead(bets, cfg):
    if not cfg or cfg == 'off':
        return []
    mm = cfg.get('m_min', 70)
    mx = cfg.get('m_max', 85)
    odds_max = cfg.get('odds_max', 8.0)
    return [b for b in bets if b.get('strategy') == 'cs_big_lead'
            and mm <= (b.get('minuto') or 0) < mx
            and (b.get('back_cs_odds') or 99) <= odds_max]
