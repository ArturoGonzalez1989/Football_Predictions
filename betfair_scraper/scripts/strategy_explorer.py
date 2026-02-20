#!/usr/bin/env python3
"""
Strategy Explorer — grid-search brute-force sobre todas las combinaciones
minuto × condición × resultado para descubrir patrones rentables.

Uso standalone:
    python betfair_scraper/scripts/strategy_explorer.py

O importable desde la API:
    from strategy_explorer import run_strategy_exploration
"""

import sys
import json
import math
from pathlib import Path
from typing import Optional

# ── sys.path setup (debe ir ANTES de cualquier import relativo) ───────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent / "dashboard" / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from utils.csv_reader import _get_cached_finished_data, _to_float, _final_result_row  # noqa: E402

# ── Constantes ────────────────────────────────────────────────────────────────

COMMISSION = 0.05
STAKE = 10.0
RESULTS_JSON = _SCRIPT_DIR.parent / "explorer_results.json"

# Minutos a evaluar (cada 5 minutos desde el 15 hasta el 80)
CHECKPOINTS = [15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]

# Target → {"col": columna de odds en el CSV, "type": "back"|"lay"}
# btts usa back_over15 como proxy (el mercado más cercano disponible)
# lay_* : apostar CONTRA ese resultado. Lay odds > 10 filtradas (responsabilidad excesiva).
# lay_score_actual se maneja dinámicamente (columna lay_rc_{gl}_{gv}), no está aquí.
TARGETS: dict[str, dict] = {
    # Back — resultado OCURRE
    "draw":         {"col": "back_draw",    "type": "back"},
    "over_05":      {"col": "back_over05",  "type": "back"},
    "over_15":      {"col": "back_over15",  "type": "back"},
    "over_25":      {"col": "back_over25",  "type": "back"},
    "under_15":     {"col": "back_under15", "type": "back"},
    "under_25":     {"col": "back_under25", "type": "back"},
    "over_35":      {"col": "back_over35",  "type": "back"},
    "home_win":     {"col": "back_home",    "type": "back"},
    "away_win":     {"col": "back_away",    "type": "back"},
    "btts":         {"col": "back_over15",  "type": "back"},  # proxy
    # Lay — resultado NO OCURRE
    "lay_draw":     {"col": "lay_draw",     "type": "lay"},
    "lay_home":     {"col": "lay_home",     "type": "lay"},
    "lay_away":     {"col": "lay_away",     "type": "lay"},
    "lay_over_05":  {"col": "lay_over05",   "type": "lay"},
    "lay_over_15":  {"col": "lay_over15",   "type": "lay"},
    "lay_over_25":  {"col": "lay_over25",   "type": "lay"},
    "lay_under_15": {"col": "lay_under15",  "type": "lay"},
    "lay_under_25": {"col": "lay_under25",  "type": "lay"},
    "lay_over_35":  {"col": "lay_over35",   "type": "lay"},
}


# ── Funciones auxiliares ──────────────────────────────────────────────────────

def _target_won(target: str, gl: int, gv: int) -> bool:
    """¿Ganó nuestra apuesta dado el marcador final?
    Back: ganamos si el evento ocurrió.
    Lay:  ganamos si el evento NO ocurrió.
    lay_score_actual se maneja fuera de esta función (requiere estado del checkpoint).
    """
    # Back targets
    if target == "draw":        return gl == gv
    if target == "over_05":     return (gl + gv) > 0
    if target == "over_15":     return (gl + gv) > 1
    if target == "over_25":     return (gl + gv) > 2
    if target == "under_15":    return (gl + gv) <= 1
    if target == "under_25":    return (gl + gv) <= 2
    if target == "over_35":     return (gl + gv) > 3
    if target == "home_win":    return gl > gv
    if target == "away_win":    return gv > gl
    if target == "btts":        return gl > 0 and gv > 0
    # Lay targets (ganamos si el evento nombrado NO ocurre)
    if target == "lay_draw":     return gl != gv
    if target == "lay_home":     return gl <= gv      # local NO ganó
    if target == "lay_away":     return gv <= gl      # visitante NO ganó
    if target == "lay_over_05":  return (gl + gv) == 0
    if target == "lay_over_15":  return (gl + gv) <= 1
    if target == "lay_over_25":  return (gl + gv) <= 2
    if target == "lay_under_15": return (gl + gv) > 1   # gana si hay Over 1.5
    if target == "lay_under_25": return (gl + gv) > 2   # gana si hay Over 2.5
    if target == "lay_over_35":  return (gl + gv) <= 3  # gana si hay ≤3 goles
    return False


def _ev(win_rate: float, avg_odds: float, bet_type: str = "back") -> float:
    """EV por unidad apostada.
    Back: win_rate × (odds−1) × 0.95 − (1−win_rate)
    Lay:  win_rate × 0.95 − (1−win_rate) × (odds−1)
    """
    if bet_type == "lay":
        return win_rate * (1 - COMMISSION) - (1 - win_rate) * (avg_odds - 1)
    return win_rate * (avg_odds - 1) * (1 - COMMISSION) - (1 - win_rate)


def _calc_pl(bet_type: str, odds: float, won: bool) -> float:
    """P/L de una apuesta individual (stake = STAKE)."""
    if bet_type == "lay":
        return STAKE * (1 - COMMISSION) if won else -STAKE * (odds - 1)
    return (odds - 1) * STAKE * (1 - COMMISSION) if won else -STAKE


def _define_conditions() -> list[dict]:
    """
    Devuelve la lista completa de condiciones a evaluar.
    Cada condición: {"id": str, "label": str, "test": callable(state) -> bool}

    ⚠️ Todos los lambdas usan default args para evitar el bug de closures de Python.
    """
    conditions: list[dict] = []

    # 1. Sin filtro (base rates)
    conditions.append({
        "id": "all",
        "label": "Sin filtro (base)",
        "test": lambda s: True,
    })

    # 2. Score states
    for home_g, away_g in [(0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (0, 2), (2, 1), (1, 2)]:
        g, v = home_g, away_g
        conditions.append({
            "id": f"score_{g}_{v}",
            "label": f"Marcador {g}-{v}",
            "test": lambda s, _g=g, _v=v: s["gl"] == _g and s["gv"] == _v,
        })

    # 3. xG_total < threshold
    for thr in [0.3, 0.5, 0.7, 1.0, 1.5]:
        t = thr
        conditions.append({
            "id": f"xg_lt_{str(t).replace('.', '_')}",
            "label": f"xG total < {t:.1f}",
            "test": lambda s, _t=t: s["xg_total"] is not None and s["xg_total"] < _t,
        })

    # 4. xG_total > threshold
    for thr in [0.5, 1.0, 1.5, 2.0]:
        t = thr
        conditions.append({
            "id": f"xg_gt_{str(t).replace('.', '_')}",
            "label": f"xG total > {t:.1f}",
            "test": lambda s, _t=t: s["xg_total"] is not None and s["xg_total"] > _t,
        })

    # 5. Tiros totales < threshold
    for thr in [5, 8, 12]:
        t = thr
        conditions.append({
            "id": f"shots_lt_{t}",
            "label": f"Tiros totales < {t}",
            "test": lambda s, _t=t: s["shots_total"] is not None and s["shots_total"] < _t,
        })

    # 6. Tiros totales > threshold
    for thr in [8, 12, 16]:
        t = thr
        conditions.append({
            "id": f"shots_gt_{t}",
            "label": f"Tiros totales > {t}",
            "test": lambda s, _t=t: s["shots_total"] is not None and s["shots_total"] > _t,
        })

    # 7. Diferencia de posesión < threshold (partido equilibrado)
    for thr in [10, 20, 30]:
        t = thr
        conditions.append({
            "id": f"poss_diff_lt_{t}",
            "label": f"Posesión equilibrada (diff < {t}%)",
            "test": lambda s, _t=t: s["poss_diff"] is not None and s["poss_diff"] < _t,
        })

    # 8. Compuestas: 0-0 AND xG_total < threshold
    for thr in [0.3, 0.5, 0.7, 1.0]:
        t = thr
        conditions.append({
            "id": f"score_00_xg_lt_{str(t).replace('.', '_')}",
            "label": f"0-0 y xG total < {t:.1f}",
            "test": lambda s, _t=t: (
                s["gl"] == 0 and s["gv"] == 0
                and s["xg_total"] is not None and s["xg_total"] < _t
            ),
        })

    # 9. Compuestas: 0-0 AND tiros bajos
    for thr in [5, 8]:
        t = thr
        conditions.append({
            "id": f"score_00_shots_lt_{t}",
            "label": f"0-0 y tiros totales < {t}",
            "test": lambda s, _t=t: (
                s["gl"] == 0 and s["gv"] == 0
                and s["shots_total"] is not None and s["shots_total"] < _t
            ),
        })

    # 10. Compuestas: 0-0 AND posesión equilibrada
    conditions.append({
        "id": "score_00_poss_balanced",
        "label": "0-0 y posesión equilibrada (diff < 15%)",
        "test": lambda s: (
            s["gl"] == 0 and s["gv"] == 0
            and s["poss_diff"] is not None and s["poss_diff"] < 15
        ),
    })

    # 11. Diferencia de goles en el campo
    conditions.append({
        "id": "home_lead_1",
        "label": "Local gana por 1",
        "test": lambda s: s["gl"] - s["gv"] == 1,
    })
    conditions.append({
        "id": "home_lead_2plus",
        "label": "Local gana por 2+",
        "test": lambda s: s["gl"] - s["gv"] >= 2,
    })
    conditions.append({
        "id": "away_lead_1",
        "label": "Visitante gana por 1",
        "test": lambda s: s["gv"] - s["gl"] == 1,
    })
    conditions.append({
        "id": "away_lead_2plus",
        "label": "Visitante gana por 2+",
        "test": lambda s: s["gv"] - s["gl"] >= 2,
    })

    # 12. Goles totales en el campo (no confundir con resultado final)
    conditions.append({
        "id": "goals_in_game_1",
        "label": "1 gol marcado (en el campo)",
        "test": lambda s: s["gl"] + s["gv"] == 1,
    })
    conditions.append({
        "id": "goals_in_game_2",
        "label": "2 goles marcados (en el campo)",
        "test": lambda s: s["gl"] + s["gv"] == 2,
    })
    conditions.append({
        "id": "goals_in_game_3plus",
        "label": "3+ goles marcados (en el campo)",
        "test": lambda s: s["gl"] + s["gv"] >= 3,
    })

    # 13. Tiros a puerta (shots on target)
    for thr in [3, 5]:
        t = thr
        conditions.append({
            "id": f"sot_lt_{t}",
            "label": f"Tiros a puerta < {t}",
            "test": lambda s, _t=t: s["tiros_puerta_total"] is not None and s["tiros_puerta_total"] < _t,
        })
    for thr in [3, 5, 8]:
        t = thr
        conditions.append({
            "id": f"sot_gt_{t}",
            "label": f"Tiros a puerta > {t}",
            "test": lambda s, _t=t: s["tiros_puerta_total"] is not None and s["tiros_puerta_total"] > _t,
        })

    # 14. Corners totales
    for thr in [4, 6]:
        t = thr
        conditions.append({
            "id": f"corners_lt_{t}",
            "label": f"Corners totales < {t}",
            "test": lambda s, _t=t: s["corners_total"] is not None and s["corners_total"] < _t,
        })
    for thr in [6, 10]:
        t = thr
        conditions.append({
            "id": f"corners_gt_{t}",
            "label": f"Corners totales > {t}",
            "test": lambda s, _t=t: s["corners_total"] is not None and s["corners_total"] > _t,
        })

    # 15. Grandes ocasiones (big chances)
    for thr in [2, 4]:
        t = thr
        conditions.append({
            "id": f"bc_gt_{t}",
            "label": f"Grandes ocasiones > {t}",
            "test": lambda s, _t=t: s["big_chances_total"] is not None and s["big_chances_total"] > _t,
        })

    # 16. Partido animado: 0-0 pero xG alto (goles pendientes)
    for thr in [1.0, 1.5]:
        t = thr
        conditions.append({
            "id": f"score_00_xg_gt_{str(t).replace('.', '_')}",
            "label": f"0-0 pero xG > {t:.1f} (goles pendientes)",
            "test": lambda s, _t=t: (
                s["gl"] == 0 and s["gv"] == 0
                and s["xg_total"] is not None and s["xg_total"] > _t
            ),
        })

    # 17. Segunda mitad
    conditions.append({
        "id": "second_half",
        "label": "Segunda mitad (min > 45)",
        "test": lambda s: s["checkpoint_min"] > 45,
    })

    # 18. 0-0 en segunda mitad
    conditions.append({
        "id": "score_00_2h",
        "label": "0-0 en segunda mitad",
        "test": lambda s: s["gl"] == 0 and s["gv"] == 0 and s["checkpoint_min"] > 45,
    })

    # 19. 0-0 segunda mitad + xG bajo (partido muy cerrado)
    conditions.append({
        "id": "score_00_2h_xg_lt_0_5",
        "label": "0-0 segunda mitad y xG < 0.5",
        "test": lambda s: (
            s["gl"] == 0 and s["gv"] == 0 and s["checkpoint_min"] > 45
            and s["xg_total"] is not None and s["xg_total"] < 0.5
        ),
    })

    # 20. Local gana 1-0 en segunda mitad (¿aguantará el resultado?)
    conditions.append({
        "id": "score_10_2h",
        "label": "1-0 en segunda mitad",
        "test": lambda s: s["gl"] == 1 and s["gv"] == 0 and s["checkpoint_min"] > 45,
    })

    # 21. Visitante gana 0-1 en segunda mitad
    conditions.append({
        "id": "score_01_2h",
        "label": "0-1 en segunda mitad",
        "test": lambda s: s["gl"] == 0 and s["gv"] == 1 and s["checkpoint_min"] > 45,
    })

    return conditions


def _extract_state_at_minute(rows: list[dict], checkpoint_minute: int) -> Optional[dict]:
    """
    Encuentra la fila en o justo antes del minuto indicado.
    Solo considera filas con estado en_juego / descanso / finalizado.
    Retorna None si el partido no había llegado aún a ese minuto.
    """
    best_row = None
    for row in rows:
        estado = row.get("estado_partido", "").strip()
        if estado not in ("en_juego", "descanso", "finalizado"):
            continue
        m = _to_float(row.get("minuto", ""))
        if m is None:
            continue
        if m <= checkpoint_minute:
            best_row = row
        else:
            break  # filas ordenadas por minuto, ya no tiene sentido continuar

    if best_row is None:
        return None

    row = best_row
    gl = _to_float(row.get("goles_local", ""))
    gv = _to_float(row.get("goles_visitante", ""))
    if gl is None or gv is None:
        return None

    xg_l = _to_float(row.get("xg_local", ""))
    xg_v = _to_float(row.get("xg_visitante", ""))
    xg_total = ((xg_l or 0) + (xg_v or 0)) if (xg_l is not None or xg_v is not None) else None

    shots_l = _to_float(row.get("tiros_local", ""))
    shots_v = _to_float(row.get("tiros_visitante", ""))
    shots_total = (
        int(shots_l or 0) + int(shots_v or 0)
        if (shots_l is not None or shots_v is not None) else None
    )

    poss_l = _to_float(row.get("posesion_local", ""))
    poss_v = _to_float(row.get("posesion_visitante", ""))
    poss_diff = (
        abs((poss_l or 50) - (poss_v or 50))
        if (poss_l is not None or poss_v is not None) else None
    )

    # Tiros a puerta (shots on target)
    tp_l = _to_float(row.get("tiros_puerta_local", ""))
    tp_v = _to_float(row.get("tiros_puerta_visitante", ""))
    tiros_puerta_total = (
        int(tp_l or 0) + int(tp_v or 0)
        if (tp_l is not None or tp_v is not None) else None
    )

    # Corners
    c_l = _to_float(row.get("corners_local", ""))
    c_v = _to_float(row.get("corners_visitante", ""))
    corners_total = (
        int(c_l or 0) + int(c_v or 0)
        if (c_l is not None or c_v is not None) else None
    )

    # Grandes ocasiones (big chances)
    bc_l = _to_float(row.get("big_chances_local", ""))
    bc_v = _to_float(row.get("big_chances_visitante", ""))
    big_chances_total = (
        int(bc_l or 0) + int(bc_v or 0)
        if (bc_l is not None or bc_v is not None) else None
    )

    # Odds: mercados estáticos
    odds: dict[str, Optional[float]] = {
        "back_draw":    _to_float(row.get("back_draw", "")),
        "back_home":    _to_float(row.get("back_home", "")),
        "back_away":    _to_float(row.get("back_away", "")),
        "back_over05":  _to_float(row.get("back_over05", "")),
        "back_over15":  _to_float(row.get("back_over15", "")),
        "back_over25":  _to_float(row.get("back_over25", "")),
        "back_under15": _to_float(row.get("back_under15", "")),
        "back_under25": _to_float(row.get("back_under25", "")),
        "back_over35":  _to_float(row.get("back_over35", "")),
        "lay_draw":     _to_float(row.get("lay_draw", "")),
        "lay_home":     _to_float(row.get("lay_home", "")),
        "lay_away":     _to_float(row.get("lay_away", "")),
        "lay_over05":   _to_float(row.get("lay_over05", "")),
        "lay_over15":   _to_float(row.get("lay_over15", "")),
        "lay_over25":   _to_float(row.get("lay_over25", "")),
        "lay_under15":  _to_float(row.get("lay_under15", "")),
        "lay_under25":  _to_float(row.get("lay_under25", "")),
        "lay_over35":   _to_float(row.get("lay_over35", "")),
    }

    # Odds: Lay Correct Score (dinámico — lay_rc_{g}_{v})
    # Precargamos los marcadores más comunes (gl+gv ≤ 5, cada equipo ≤ 3)
    for g in range(4):
        for v in range(4):
            col = f"lay_rc_{g}_{v}"
            odds[col] = _to_float(row.get(col, ""))

    return {
        "gl":                 int(gl),
        "gv":                 int(gv),
        "xg_total":           round(xg_total, 3) if xg_total is not None else None,
        "shots_total":        shots_total,
        "poss_diff":          round(poss_diff, 1) if poss_diff is not None else None,
        "tiros_puerta_total": tiros_puerta_total,
        "corners_total":      corners_total,
        "big_chances_total":  big_chances_total,
        "checkpoint_min":     checkpoint_minute,
        "odds":               odds,
    }


# ── Grid search principal ─────────────────────────────────────────────────────

def run_strategy_exploration(
    min_sample: int = 5,
    max_results: int = 200,
) -> dict:
    """
    Grid search completo: minuto × condición × target → EV%.

    Retorna un dict ExplorationRun y lo guarda en RESULTS_JSON.
    """
    from datetime import datetime, timezone

    finished = _get_cached_finished_data()
    conditions = _define_conditions()

    # Acumulador: (minute, cond_id, target) → {n, wins, odds_list, pl_sum, label, bet_type}
    accum: dict[tuple, dict] = {}

    for match in finished:
        rows = match.get("rows") or []
        if not rows or len(rows) < 5:
            continue

        final_row = _final_result_row(rows)
        if final_row is None:
            continue
        gl_f = _to_float(final_row.get("goles_local", ""))
        gv_f = _to_float(final_row.get("goles_visitante", ""))
        if gl_f is None or gv_f is None:
            continue
        gl_final, gv_final = int(gl_f), int(gv_f)

        for minute in CHECKPOINTS:
            state = _extract_state_at_minute(rows, minute)
            if state is None:
                continue

            for cond in conditions:
                try:
                    if not cond["test"](state):
                        continue
                except Exception:
                    continue

                # ── Targets estáticos ──────────────────────────────────────
                for target, tinfo in TARGETS.items():
                    odds_col = tinfo["col"]
                    bet_type = tinfo["type"]
                    odds_val = state["odds"].get(odds_col)
                    if odds_val is None or odds_val < 1.05:
                        continue  # sin mercado válido
                    # Para lay, filtrar odds excesivamente altas (responsabilidad enorme)
                    if bet_type == "lay" and odds_val > 10.0:
                        continue

                    key = (minute, cond["id"], target)
                    if key not in accum:
                        accum[key] = {
                            "n": 0,
                            "wins": 0,
                            "odds_list": [],
                            "pl_sum": 0.0,
                            "label": cond["label"],
                            "bet_type": bet_type,
                        }

                    entry = accum[key]
                    entry["n"] += 1

                    won = _target_won(target, gl_final, gv_final)
                    if won:
                        entry["wins"] += 1

                    entry["odds_list"].append(odds_val)
                    entry["pl_sum"] += _calc_pl(bet_type, odds_val, won)

                # ── Target especial: Lay Score Actual (columna dinámica) ───
                gl_now, gv_now = state["gl"], state["gv"]
                if gl_now <= 3 and gv_now <= 3:
                    rc_col = f"lay_rc_{gl_now}_{gv_now}"
                    odds_val = state["odds"].get(rc_col)
                    if odds_val is not None and 1.05 <= odds_val <= 10.0:
                        target = "lay_score_actual"
                        # Ganamos si el marcador final es DISTINTO al del checkpoint
                        won = (gl_final != gl_now) or (gv_final != gv_now)

                        key = (minute, cond["id"], target)
                        if key not in accum:
                            accum[key] = {
                                "n": 0,
                                "wins": 0,
                                "odds_list": [],
                                "pl_sum": 0.0,
                                "label": cond["label"],
                                "bet_type": "lay",
                            }

                        entry = accum[key]
                        entry["n"] += 1
                        if won:
                            entry["wins"] += 1
                        entry["odds_list"].append(odds_val)
                        entry["pl_sum"] += _calc_pl("lay", odds_val, won)

    # ── Construir lista de resultados ──────────────────────────────────────────
    results = []

    for (minute, cond_id, target), acc in accum.items():
        n = acc["n"]
        if n < min_sample:
            continue

        odds_list = acc["odds_list"]
        if not odds_list:
            continue

        avg_odds = sum(odds_list) / len(odds_list)
        if avg_odds < 1.05:
            continue

        wins = acc["wins"]
        win_rate = wins / n

        # std_odds
        if len(odds_list) > 1:
            variance = sum((o - avg_odds) ** 2 for o in odds_list) / len(odds_list)
            std_odds = round(math.sqrt(variance), 3)
        else:
            std_odds = None

        bet_type = acc["bet_type"]
        ev_pct = _ev(win_rate, avg_odds, bet_type)
        avg_pl = acc["pl_sum"] / n
        total_pl = acc["pl_sum"]

        results.append({
            "minute":          minute,
            "condition":       acc["label"],
            "condition_id":    cond_id,
            "target":          target,
            "bet_type":        bet_type,
            "n_matches":       n,
            "wins":            wins,
            "win_rate":        round(win_rate, 4),
            "avg_odds":        round(avg_odds, 3),
            "std_odds":        std_odds,
            "ev_pct":          round(ev_pct, 4),
            "avg_pl_per_bet":  round(avg_pl, 3),
            "total_pl":        round(total_pl, 2),
        })

    # Separar por tipo, tomar top max_results de cada uno para que ambos aparezcan
    # (las apuestas back con odds altas dominan el top si se ordena todo junto)
    back_res = sorted([r for r in results if r["bet_type"] == "back"],
                      key=lambda r: r["ev_pct"], reverse=True)[:max_results]
    lay_res  = sorted([r for r in results if r["bet_type"] == "lay"],
                      key=lambda r: r["ev_pct"], reverse=True)[:max_results]
    results = sorted(back_res + lay_res, key=lambda r: r["ev_pct"], reverse=True)

    output = {
        "run_at":           datetime.now(timezone.utc).isoformat(),
        "n_total_matches":  len(finished),
        "n_results":        len(results),
        "min_sample":       min_sample,
        "max_results":      max_results,
        "results":          results,
    }

    RESULTS_JSON.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return output


# ── Detalle de partidos para una combinación ─────────────────────────────────

def get_matches_for_combination(
    condition_id: str,
    target: str,
    minutes: list[int],
    bet_type: str = "back",
) -> list[dict]:
    """
    Devuelve los partidos individuales que cumplen una combinación
    (condition_id, target, minutes, bet_type).

    `minutes` puede ser una lista (cuando el usuario agrupa varios checkpoints).
    Se desduplicа por match_id (cada partido aparece una sola vez).
    """
    finished = _get_cached_finished_data()
    conditions = _define_conditions()

    # Localizar la condición
    cond = next((c for c in conditions if c["id"] == condition_id), None)
    if cond is None:
        return []

    # Config del target
    if target == "lay_score_actual":
        target_col = None
    else:
        tinfo = TARGETS.get(target)
        if tinfo is None:
            return []
        target_col = tinfo["col"]

    seen_ids: dict[str, bool] = {}   # match_id → ya añadido
    results: list[dict] = []

    for minute in sorted(minutes):
        for match in finished:
            rows = match.get("rows") or []
            if not rows or len(rows) < 5:
                continue

            # Deduplicar: mismo partido solo una vez (tomar el primer minuto que lo incluya)
            if match["match_id"] in seen_ids:
                continue

            final_row = _final_result_row(rows)
            if final_row is None:
                continue
            gl_f = _to_float(final_row.get("goles_local", ""))
            gv_f = _to_float(final_row.get("goles_visitante", ""))
            if gl_f is None or gv_f is None:
                continue
            gl_final, gv_final = int(gl_f), int(gv_f)

            state = _extract_state_at_minute(rows, minute)
            if state is None:
                continue

            try:
                if not cond["test"](state):
                    continue
            except Exception:
                continue

            gl_now, gv_now = state["gl"], state["gv"]

            if target == "lay_score_actual":
                if gl_now > 3 or gv_now > 3:
                    continue
                rc_col = f"lay_rc_{gl_now}_{gv_now}"
                odds_val = state["odds"].get(rc_col)
                if odds_val is None or not (1.05 <= odds_val <= 10.0):
                    continue
                won = (gl_final != gl_now) or (gv_final != gv_now)
            else:
                odds_val = state["odds"].get(target_col)
                if odds_val is None or odds_val < 1.05:
                    continue
                if bet_type == "lay" and odds_val > 10.0:
                    continue
                won = _target_won(target, gl_final, gv_final)

            pl = _calc_pl(bet_type, odds_val, won)
            seen_ids[match["match_id"]] = True
            results.append({
                "match_id":             match["match_id"],
                "match_name":           match["name"],
                "score_at_checkpoint":  f"{gl_now}-{gv_now}",
                "final_score":          f"{gl_final}-{gv_final}",
                "odds":                 round(odds_val, 2),
                "won":                  won,
                "pl":                   round(pl, 2),
            })

    return sorted(results, key=lambda r: r["pl"], reverse=True)


# ── Ejecución standalone ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import time

    print("=" * 60)
    print("Strategy Explorer — Iniciando grid search...")
    print(f"Backend dir: {_BACKEND_DIR}")
    print(f"Resultados se guardarán en: {RESULTS_JSON}")
    print("=" * 60)

    t0 = time.time()
    result = run_strategy_exploration(min_sample=5, max_results=200)
    elapsed = time.time() - t0

    n_matches = result["n_total_matches"]
    n_results = result["n_results"]
    print(f"\nDone en {elapsed:.1f}s — {n_results} combinaciones ({n_matches} partidos)")
    print(f"Guardado en: {RESULTS_JSON}\n")

    if result["results"]:
        print("Top 5 descubrimientos:")
        print(f"{'Min':>4} {'Condición':<40} {'Target':<16} {'N':>4} {'WR%':>6} {'Odds':>6} {'EV%':>7} {'P/L':>8}")
        print("-" * 100)
        for r in result["results"][:5]:
            print(
                f"{r['minute']:>4} {r['condition']:<40} {r['target']:<16} "
                f"{r['n_matches']:>4} {r['win_rate']*100:>5.1f}% {r['avg_odds']:>6.2f} "
                f"{r['ev_pct']*100:>6.1f}% {r['total_pl']:>8.1f}€"
            )
