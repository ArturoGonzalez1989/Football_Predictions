"""
analyze_signal_duration.py

Analiza el histórico de partidos (CSVs minuto a minuto) para determinar:
  - Cuánto tiempo permanece activa cada señal antes de desaparecer
  - Si las señales de mayor duración tienen mejor win rate que las efímeras
  - Qué umbral de duración mínima maximiza la rentabilidad

Metodología:
  - Para cada CSV histórico, replaya la lógica de señales fila a fila
  - Detecta "episodios": secuencias consecutivas de filas donde la condición se cumple
  - Registra duración del episodio + resultado final del partido
  - Agrupa por buckets de duración y calcula win rate por bucket

Uso:
  python analyze_signal_duration.py
"""

import csv
import re
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "betfair_scraper" / "data"


# ─────────────────────────── helpers ───────────────────────────

def _f(val):
    """Convierte a float o devuelve None."""
    try:
        v = str(val).strip()
        return float(v) if v not in ('', 'None', 'nan', 'N/A') else None
    except (ValueError, TypeError):
        return None


def get_final_score(rows):
    """Obtiene el marcador final de la última fila significativa."""
    for row in reversed(rows):
        est = row.get("estado_partido", "").strip().lower()
        if est not in ("pre_partido", "prematch", ""):
            gl = _f(row.get("goles_local")) or 0
            gv = _f(row.get("goles_visitante")) or 0
            return int(gl), int(gv)
    return None, None


def check_win(recommendation, final_home, final_away):
    """Determina si la apuesta ganó con el marcador final."""
    rec = recommendation.upper()
    if "DRAW" in rec:
        return final_home == final_away
    m = re.search(r"OVER\s+(\d+\.?\d*)", rec)
    if m:
        return (final_home + final_away) > float(m.group(1))
    m = re.search(r"UNDER\s+(\d+\.?\d*)", rec)
    if m:
        return (final_home + final_away) < float(m.group(1))
    if "HOME" in rec:
        return final_home > final_away
    if "AWAY" in rec:
        return final_away > final_home
    return None


def over_field(total_goals):
    return {0: "back_over05", 1: "back_over15", 2: "back_over25",
            3: "back_over35", 4: "back_over45"}.get(int(total_goals))


# ─────────────────────────── checkers por estrategia ───────────────────────────

def check_draw(row, version="v15"):
    """Back Draw 0-0: condiciones para señal activa."""
    minuto = _f(row.get("minuto"))
    if minuto is None or minuto < 30:
        return False, None

    gl = _f(row.get("goles_local")) or 0
    gv = _f(row.get("goles_visitante")) or 0
    if gl != 0 or gv != 0:
        return False, None

    xg_l = _f(row.get("xg_local"))
    xg_v = _f(row.get("xg_visitante"))
    if xg_l is None or xg_v is None:
        return False, None

    xg_total = xg_l + xg_v
    pos_l = _f(row.get("posesion_local")) or 50
    pos_v = _f(row.get("posesion_visitante")) or 50
    poss_diff = abs(pos_l - pos_v)
    tiros_l = _f(row.get("tiros_local")) or 0
    tiros_v = _f(row.get("tiros_visitante")) or 0
    tiros_total = tiros_l + tiros_v

    if version == "v15":
        if xg_total >= 0.6 or poss_diff >= 25:
            return False, None
    elif version == "v2r":
        if xg_total >= 0.6 or poss_diff >= 20 or tiros_total >= 8:
            return False, None
    elif version == "v2":
        if xg_total >= 0.5 or poss_diff >= 20 or tiros_total >= 8:
            return False, None

    return True, "BACK DRAW"


def check_xg(row, version="v3"):
    """xG Underperformance: equipo perdiendo con xG alto."""
    minuto = _f(row.get("minuto"))
    if minuto is None or minuto < 15:
        return False, None
    if version == "v3" and minuto >= 70:
        return False, None

    gl = _f(row.get("goles_local")) or 0
    gv = _f(row.get("goles_visitante")) or 0
    xg_l = _f(row.get("xg_local"))
    xg_v = _f(row.get("xg_visitante"))
    sot_l = _f(row.get("tiros_puerta_local")) or 0
    sot_v = _f(row.get("tiros_puerta_visitante")) or 0

    if xg_l is None or xg_v is None:
        return False, None

    for xg_team, goals_team, goals_opp, sot_team in [
        (xg_l, gl, gv, sot_l),
        (xg_v, gv, gl, sot_v),
    ]:
        if goals_team >= goals_opp:
            continue
        xg_excess = xg_team - goals_team
        if xg_excess < 0.5:
            continue
        if version in ("v2", "v3") and sot_team < 2:
            continue

        total_g = int(gl) + int(gv)
        of = over_field(total_g)
        if not of:
            continue
        if _f(row.get(of)) is None:
            continue

        return True, f"BACK Over {total_g + 0.5}"

    return False, None


def check_pressure(rows, idx, version="v1"):
    """Pressure Cooker: empate con goles entre min 65-75."""
    row = rows[idx]
    minuto = _f(row.get("minuto"))
    if minuto is None or not (65 <= minuto <= 75):
        return False, None

    gl = _f(row.get("goles_local")) or 0
    gv = _f(row.get("goles_visitante")) or 0
    total_goals = int(gl) + int(gv)

    if gl != gv or total_goals < 2:
        return False, None

    # Confirmación de marcador
    confirm = sum(
        1 for r in rows[max(0, idx - 5):idx + 1]
        if (_f(r.get("goles_local")) or 0) == gl and (_f(r.get("goles_visitante")) or 0) == gv
    )
    if confirm < 2:
        return False, None

    of = over_field(total_goals)
    if not of or _f(row.get(of)) is None:
        return False, None

    return True, f"BACK Over {total_goals + 0.5}"


def check_drift(rows, idx, version="v1"):
    """Odds Drift Contrarian: equipo ganador con cuota derivando al alza."""
    row = rows[idx]
    minuto = _f(row.get("minuto"))
    if minuto is None:
        return False, None

    gl = _f(row.get("goles_local")) or 0
    gv = _f(row.get("goles_visitante")) or 0
    goal_diff = abs(int(gl) - int(gv))
    if goal_diff < 1:
        return False, None

    # Confirmación del marcador actual (3+ filas)
    score_ok = sum(
        1 for r in rows[max(0, idx - 5):idx + 1]
        if (_f(r.get("goles_local")) or 0) == gl and (_f(r.get("goles_visitante")) or 0) == gv
    )
    if score_ok < 3:
        return False, None

    # Buscar fila de hace ~10 minutos con mismo marcador
    target_min = minuto - 10
    hist_row = None
    for r in reversed(rows[:idx]):
        rm = _f(r.get("minuto"))
        if rm is None:
            continue
        if rm <= target_min:
            hgl = _f(r.get("goles_local")) or 0
            hgv = _f(r.get("goles_visitante")) or 0
            if int(hgl) == int(gl) and int(hgv) == int(gv):
                hist_row = r
            break

    if not hist_row:
        return False, None

    if gl > gv:
        team = "HOME"
        odds_before = _f(hist_row.get("back_home"))
        odds_now = _f(row.get("back_home"))
    else:
        team = "AWAY"
        odds_before = _f(hist_row.get("back_away"))
        odds_now = _f(row.get("back_away"))

    if not odds_before or not odds_now:
        return False, None

    drift_pct = ((odds_now - odds_before) / odds_before) * 100
    if drift_pct < 25:
        return False, None

    if version == "v1":
        if not (goal_diff == 1 and (int(gl) + int(gv)) == 1):
            return False, None
    elif version == "v2":
        if goal_diff < 2:
            return False, None
    elif version == "v3":
        if drift_pct < 100:
            return False, None
    elif version == "v4":
        if minuto <= 45 or odds_now > 5.0:
            return False, None
    elif version == "v5":
        if odds_now > 5.0:
            return False, None

    return True, f"BACK {team}"


def check_clustering(rows, idx, version="v2"):
    """Goal Clustering: gol reciente + partido activo entre min 15-80."""
    row = rows[idx]
    minuto = _f(row.get("minuto"))
    if minuto is None or not (15 <= minuto <= 80):
        return False, None

    if version == "v3" and minuto >= 75:
        return False, None

    if idx < 1:
        return False, None

    gl = _f(row.get("goles_local")) or 0
    gv = _f(row.get("goles_visitante")) or 0
    sot_l = _f(row.get("tiros_puerta_local")) or 0
    sot_v = _f(row.get("tiros_puerta_visitante")) or 0
    sot_max = max(sot_l, sot_v)

    if sot_max < 3:
        return False, None

    # Gol en las últimas 3 capturas
    recent_goal = False
    for i in range(idx, max(0, idx - 3), -1):
        if i == 0:
            break
        curr_total = (_f(rows[i].get("goles_local")) or 0) + (_f(rows[i].get("goles_visitante")) or 0)
        prev_total = (_f(rows[i-1].get("goles_local")) or 0) + (_f(rows[i-1].get("goles_visitante")) or 0)
        if curr_total > prev_total:
            recent_goal = True
            break

    if not recent_goal:
        return False, None

    total_g = int(gl) + int(gv)
    of = over_field(total_g)
    if not of or _f(row.get(of)) is None:
        return False, None

    return True, f"BACK Over {total_g + 0.5}"


# ─────────────────────────── análisis principal ───────────────────────────

STRATEGIES = {
    "draw_v15":     lambda rows, i: check_draw(rows[i], "v15"),
    "draw_v2r":     lambda rows, i: check_draw(rows[i], "v2r"),
    "xg_v3":        lambda rows, i: check_xg(rows[i], "v3"),
    "pressure_v1":  lambda rows, i: check_pressure(rows, i, "v1"),
    "drift_v1":     lambda rows, i: check_drift(rows, i, "v1"),
    "clustering_v2":lambda rows, i: check_clustering(rows, i, "v2"),
    "clustering_v3":lambda rows, i: check_clustering(rows, i, "v3"),
}

STRATEGY_LABELS = {
    "draw_v15":      "Back Draw 0-0 V1.5",
    "draw_v2r":      "Back Draw 0-0 V2r",
    "xg_v3":         "xG Underperf. V3",
    "pressure_v1":   "Pressure Cooker V1",
    "drift_v1":      "Odds Drift V1",
    "clustering_v2": "Goal Clustering V2",
    "clustering_v3": "Goal Clustering V3",
}


def analyze():
    # strategy -> list of {duration_caps, start_minute, won, match}
    episodes = defaultdict(list)

    csv_files = sorted(DATA_DIR.glob("partido_*.csv"))
    print(f"Cargando {len(csv_files)} partidos históricos...\n")

    processed = skipped = 0

    for csv_path in csv_files:
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        except Exception:
            skipped += 1
            continue

        # Solo partidos con suficientes datos y estado final claro
        if len(rows) < 10:
            skipped += 1
            continue

        # Filtrar solo filas en juego (no prematch)
        in_play_rows = [r for r in rows if r.get("estado_partido", "").strip().lower() == "en_juego"]
        if len(in_play_rows) < 5:
            skipped += 1
            continue

        final_home, final_away = get_final_score(in_play_rows)
        if final_home is None:
            skipped += 1
            continue

        processed += 1
        match_name = csv_path.stem

        for strat_name, checker in STRATEGIES.items():
            in_episode = False
            ep_start = None
            ep_rec = None

            for i, row in enumerate(in_play_rows):
                active, rec = checker(in_play_rows, i)

                if active and not in_episode:
                    # Señal se activa
                    in_episode = True
                    ep_start = i
                    ep_rec = rec

                elif not active and in_episode:
                    # Señal se desactiva
                    duration = i - ep_start
                    start_min = _f(in_play_rows[ep_start].get("minuto")) or 0
                    won = check_win(ep_rec, final_home, final_away)
                    if won is not None:
                        episodes[strat_name].append({
                            "duration": duration,
                            "start_minute": int(start_min),
                            "won": won,
                            "match": match_name,
                            "rec": ep_rec,
                        })
                    in_episode = False
                    ep_rec = None

            # Episodio que llega al final del partido
            if in_episode:
                duration = len(in_play_rows) - ep_start
                start_min = _f(in_play_rows[ep_start].get("minuto")) or 0
                won = check_win(ep_rec, final_home, final_away)
                if won is not None:
                    episodes[strat_name].append({
                        "duration": duration,
                        "start_minute": int(start_min),
                        "won": won,
                        "match": match_name,
                        "rec": ep_rec,
                        "reached_end": True,
                    })

    print(f"Partidos procesados : {processed}")
    print(f"Partidos omitidos   : {skipped}")

    return episodes


# ─────────────────────────── presentación de resultados ───────────────────────────

BUCKETS = [
    ("1 cap  (~1 min)",       lambda d: d == 1),
    ("2-3 caps (~2-3 min)",   lambda d: 2 <= d <= 3),
    ("4-6 caps (~4-6 min)",   lambda d: 4 <= d <= 6),
    ("7-12 caps (~7-12 min)", lambda d: 7 <= d <= 12),
    ("13+ caps (>12 min)",    lambda d: d >= 13),
]


def print_results(episodes):
    print("\n" + "=" * 70)
    print("  ANALISIS DE DURACION DE SENALES VS RENTABILIDAD")
    print("=" * 70)
    print("  Nota: '1 captura' ~ 1 minuto real de partido\n")

    summary_rows = []  # para resumen final

    for strat_key in STRATEGIES:
        eps = episodes.get(strat_key, [])
        label = STRATEGY_LABELS[strat_key]

        if not eps:
            print(f"\n  {label}: sin datos suficientes")
            continue

        sep = "-" * 68
        print(f"\n  +-- {label} {'-' * max(1, 52 - len(label))}+")
        print(f"  |  Total episodios detectados: {len(eps):<5}                      |")
        print(f"  +{sep}+")
        print(f"  |  {'Duracion':<28} {'N':>4}  {'Win%':>7}  {'Gana':>5}  {'Pierde':>6}  |")
        print(f"  +{sep}+")

        for bucket_name, bucket_filter in BUCKETS:
            bucket = [e for e in eps if bucket_filter(e["duration"])]
            if not bucket:
                continue
            wins = sum(1 for e in bucket if e["won"])
            losses = len(bucket) - wins
            win_pct = wins / len(bucket) * 100
            print(f"  |  {bucket_name:<28} {len(bucket):>4}  {win_pct:>6.1f}%  {wins:>5}  {losses:>6}  |")
            summary_rows.append((label, bucket_name, len(bucket), win_pct))

        # Punto de inflexion: a partir de que duracion mejora el win rate?
        all_long = [e for e in eps if e["duration"] >= 4]
        all_short = [e for e in eps if e["duration"] <= 3]
        if all_long and all_short:
            wr_long = sum(e["won"] for e in all_long) / len(all_long) * 100
            wr_short = sum(e["won"] for e in all_short) / len(all_short) * 100
            diff = wr_long - wr_short
            symbol = "+" if diff > 0 else "-"
            print(f"  +{sep}+")
            print(f"  |  >=4 caps: {wr_long:.1f}%  vs  <=3 caps: {wr_short:.1f}%  -> diferencia: {symbol}{abs(diff):.1f}pp  {'':>9}|")

        print(f"  +{sep}+")

    # Resumen ejecutivo
    print("\n" + "=" * 70)
    print("  RESUMEN EJECUTIVO")
    print("=" * 70)
    print()
    print("  Estrategia                    | Duracion optima detectada")
    print("  " + "-" * 60)

    for strat_key in STRATEGIES:
        eps = episodes.get(strat_key, [])
        label = STRATEGY_LABELS[strat_key]
        if not eps:
            print(f"  {label:<30}| Sin datos")
            continue

        # Encontrar el bucket con mayor win rate (mínimo 3 episodios)
        best_bucket = None
        best_wr = 0
        for bucket_name, bucket_filter in BUCKETS:
            bucket = [e for e in eps if bucket_filter(e["duration"])]
            if len(bucket) < 3:
                continue
            wr = sum(e["won"] for e in bucket) / len(bucket) * 100
            if wr > best_wr:
                best_wr = wr
                best_bucket = bucket_name

        if best_bucket:
            print(f"  {label:<30}| {best_bucket} -> {best_wr:.1f}% win rate")
        else:
            print(f"  {label:<30}| Muestra insuficiente por bucket")

    print()
    print("  INTERPRETACION:")
    print("  Si el win rate sube claramente con la duracion => aplicar filtro minimo")
    print("  Si es plano o aleatorio => la duracion no aporta valor predictivo")
    print()


if __name__ == "__main__":
    episodes = analyze()
    print_results(episodes)
