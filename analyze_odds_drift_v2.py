"""
Analisis Odds Drift V2 - Deep dive en "equipo va ganando"
=========================================================
Cruza el filtro principal (drift >30% + va ganando) con todos los subfiltros
para encontrar la mejor combinacion y analizar los 9 fallos.
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data")
COMMISSION = 0.05
STAKE = 10

DRIFT_PCT = 0.30
WINDOW_MINUTES = 10
MIN_MINUTE = 5
MAX_MINUTE = 80
MIN_ODDS = 1.5
MAX_ODDS = 30.0


def load_all_matches():
    matches = []
    for f in sorted(DATA_DIR.glob("partido_*.csv")):
        try:
            df = pd.read_csv(f)
            if len(df) < 10:
                continue
            required = ["minuto", "back_home", "back_away", "goles_local", "goles_visitante"]
            if not all(c in df.columns for c in required):
                continue
            name = f.stem.replace("partido_", "").rsplit("-apuestas-", 1)[0]
            match_id = f.stem.rsplit("-apuestas-", 1)[-1] if "-apuestas-" in f.stem else f.stem
            df = df.copy()
            df["_match_name"] = name
            df["_match_id"] = match_id
            matches.append(df)
        except:
            continue
    return matches


def get_final_score(df):
    last = df.tail(5)
    gl = last["goles_local"].max()
    gv = last["goles_visitante"].max()
    return (int(gl) if pd.notna(gl) else None, int(gv) if pd.notna(gv) else None)


def detect_drift_triggers(df):
    triggers = []
    df = df.copy()
    df["minuto"] = pd.to_numeric(df["minuto"], errors="coerce")
    df = df.dropna(subset=["minuto"]).sort_values("minuto").reset_index(drop=True)

    for col in ["back_home", "back_away", "back_draw"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Stats columns
    for col in ["posesion_local", "posesion_visitante", "tiros_puerta_local", "tiros_puerta_visitante",
                 "corners_local", "corners_visitante", "xg_local", "xg_visitante",
                 "tiros_local", "tiros_visitante", "momentum_local", "momentum_visitante"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    gl_final, gv_final = get_final_score(df)
    if gl_final is None:
        return triggers

    ft_score = f"{gl_final}-{gv_final}"
    match_name = df["_match_name"].iloc[0]
    match_id = df["_match_id"].iloc[0]

    triggered_home = False
    triggered_away = False

    for i in range(1, len(df)):
        curr_min = df.iloc[i]["minuto"]
        if curr_min < MIN_MINUTE or curr_min > MAX_MINUTE:
            continue

        for j in range(i - 1, -1, -1):
            prev_min = df.iloc[j]["minuto"]
            if curr_min - prev_min > WINDOW_MINUTES:
                break
            if curr_min - prev_min < 2:
                continue

            row = df.iloc[i]
            gl_at = int(row.get("goles_local", 0)) if pd.notna(row.get("goles_local")) else 0
            gv_at = int(row.get("goles_visitante", 0)) if pd.notna(row.get("goles_visitante")) else 0

            # HOME drift
            if not triggered_home:
                prev_h = df.iloc[j]["back_home"]
                curr_h = row["back_home"]
                if pd.notna(prev_h) and pd.notna(curr_h) and prev_h > 0:
                    drift = (curr_h - prev_h) / prev_h
                    if drift >= DRIFT_PCT and MIN_ODDS <= curr_h <= MAX_ODDS:
                        is_winning = gl_at > gv_at
                        won = gl_final > gv_final
                        profit = (curr_h - 1) * STAKE * (1 - COMMISSION) if won else -STAKE
                        goal_diff = gl_at - gv_at

                        t = {
                            "match": match_name, "match_id": match_id, "team": "home",
                            "minuto": int(curr_min), "score_at": f"{gl_at}-{gv_at}",
                            "goal_diff": goal_diff, "is_winning": is_winning,
                            "odds_before": round(prev_h, 2), "odds_at_trigger": round(curr_h, 2),
                            "drift_pct": round(drift * 100, 1),
                            "ft_score": ft_score, "won": won, "profit": round(profit, 2),
                        }
                        # Add stats at trigger
                        for stat, col_l, col_v in [
                            ("poss", "posesion_local", "posesion_visitante"),
                            ("sot", "tiros_puerta_local", "tiros_puerta_visitante"),
                            ("shots", "tiros_local", "tiros_visitante"),
                            ("corners", "corners_local", "corners_visitante"),
                            ("xg", "xg_local", "xg_visitante"),
                            ("momentum", "momentum_local", "momentum_visitante"),
                        ]:
                            t[f"{stat}_team"] = row.get(col_l, np.nan) if pd.notna(row.get(col_l)) else np.nan
                            t[f"{stat}_opp"] = row.get(col_v, np.nan) if pd.notna(row.get(col_v)) else np.nan

                        triggers.append(t)
                        triggered_home = True
                        break

            # AWAY drift
            if not triggered_away:
                prev_a = df.iloc[j]["back_away"]
                curr_a = row["back_away"]
                if pd.notna(prev_a) and pd.notna(curr_a) and prev_a > 0:
                    drift = (curr_a - prev_a) / prev_a
                    if drift >= DRIFT_PCT and MIN_ODDS <= curr_a <= MAX_ODDS:
                        is_winning = gv_at > gl_at
                        won = gv_final > gl_final
                        profit = (curr_a - 1) * STAKE * (1 - COMMISSION) if won else -STAKE
                        goal_diff = gv_at - gl_at

                        t = {
                            "match": match_name, "match_id": match_id, "team": "away",
                            "minuto": int(curr_min), "score_at": f"{gl_at}-{gv_at}",
                            "goal_diff": goal_diff, "is_winning": is_winning,
                            "odds_before": round(prev_a, 2), "odds_at_trigger": round(curr_a, 2),
                            "drift_pct": round(drift * 100, 1),
                            "ft_score": ft_score, "won": won, "profit": round(profit, 2),
                        }
                        for stat, col_l, col_v in [
                            ("poss", "posesion_visitante", "posesion_local"),
                            ("sot", "tiros_puerta_visitante", "tiros_puerta_local"),
                            ("shots", "tiros_visitante", "tiros_local"),
                            ("corners", "corners_visitante", "corners_local"),
                            ("xg", "xg_visitante", "xg_local"),
                            ("momentum", "momentum_visitante", "momentum_local"),
                        ]:
                            t[f"{stat}_team"] = row.get(col_l, np.nan) if pd.notna(row.get(col_l)) else np.nan
                            t[f"{stat}_opp"] = row.get(col_v, np.nan) if pd.notna(row.get(col_v)) else np.nan

                        triggers.append(t)
                        triggered_away = True
                        break

            if triggered_home and triggered_away:
                break

    return triggers


def analyze(df, label):
    if len(df) == 0:
        print(f"  {label}: 0 triggers")
        return None
    total = len(df)
    wins = df["won"].sum()
    wr = wins / total * 100
    pl = df["profit"].sum()
    roi = pl / (total * STAKE) * 100
    avg_odds = df["odds_at_trigger"].mean()

    cumul = df["profit"].cumsum()
    dd = (cumul.cummax() - cumul).max()

    worst = 0
    cur = 0
    for w in df["won"]:
        if not w:
            cur += 1
            worst = max(worst, cur)
        else:
            cur = 0

    print(f"  {label}")
    print(f"    {total} triggers | {int(wins)}W {total-int(wins)}L | WR {wr:.1f}% | Avg odds {avg_odds:.2f}")
    print(f"    P/L {pl:+.2f} EUR | ROI {roi:+.1f}% | MaxDD {dd:.0f} EUR | Racha {worst}")
    return {"n": total, "wins": int(wins), "wr": wr, "pl": pl, "roi": roi, "dd": dd, "streak": worst}


def main():
    print("=" * 70)
    print("ODDS DRIFT V2 - Deep dive: equipo va GANANDO")
    print("=" * 70)

    matches = load_all_matches()
    print(f"Partidos cargados: {len(matches)}")

    all_triggers = []
    for df in matches:
        all_triggers.extend(detect_drift_triggers(df))

    tdf = pd.DataFrame(all_triggers)
    print(f"Triggers totales: {len(tdf)}")

    # Base filter: equipo va ganando
    winning = tdf[tdf["is_winning"]].copy().reset_index(drop=True)
    print(f"\nTriggers 'va ganando': {len(winning)}")

    print("\n" + "=" * 70)
    print("1. REFERENCIA")
    print("=" * 70)
    analyze(winning, "V1 BASE: drift >30% + va ganando")

    print("\n" + "=" * 70)
    print("2. CRUCES CON HOME/AWAY")
    print("=" * 70)
    analyze(winning[winning["team"] == "home"], "V1 + HOME")
    analyze(winning[winning["team"] == "away"], "V1 + AWAY")

    print("\n" + "=" * 70)
    print("3. CRUCES CON MINUTO")
    print("=" * 70)
    analyze(winning[winning["minuto"] <= 30], "V1 + min 5-30")
    analyze(winning[(winning["minuto"] > 30) & (winning["minuto"] <= 45)], "V1 + min 31-45")
    analyze(winning[winning["minuto"] > 45], "V1 + min 46-80 (2a parte)")
    analyze(winning[winning["minuto"] <= 45], "V1 + primera parte completa")

    print("\n" + "=" * 70)
    print("4. CRUCES CON ODDS")
    print("=" * 70)
    analyze(winning[winning["odds_at_trigger"] <= 3.0], "V1 + odds <= 3.0")
    analyze(winning[(winning["odds_at_trigger"] > 3.0) & (winning["odds_at_trigger"] <= 5.0)], "V1 + odds 3.0-5.0")
    analyze(winning[(winning["odds_at_trigger"] > 5.0) & (winning["odds_at_trigger"] <= 10.0)], "V1 + odds 5.0-10.0")
    analyze(winning[winning["odds_at_trigger"] > 10.0], "V1 + odds > 10.0")
    analyze(winning[winning["odds_at_trigger"] <= 5.0], "V1 + odds <= 5.0")
    analyze(winning[winning["odds_at_trigger"] <= 6.0], "V1 + odds <= 6.0")

    print("\n" + "=" * 70)
    print("5. CRUCES CON DRIFT MAGNITUD")
    print("=" * 70)
    analyze(winning[winning["drift_pct"] < 50], "V1 + drift 30-50%")
    analyze(winning[(winning["drift_pct"] >= 50) & (winning["drift_pct"] < 100)], "V1 + drift 50-100%")
    analyze(winning[winning["drift_pct"] >= 100], "V1 + drift >= 100%")
    analyze(winning[winning["drift_pct"] >= 50], "V1 + drift >= 50%")

    print("\n" + "=" * 70)
    print("6. CRUCES CON DIFERENCIA DE GOLES")
    print("=" * 70)
    analyze(winning[winning["goal_diff"] == 1], "V1 + ventaja 1 gol")
    analyze(winning[winning["goal_diff"] >= 2], "V1 + ventaja 2+ goles")

    print("\n" + "=" * 70)
    print("7. COMBINACIONES PROMETEDORAS")
    print("=" * 70)
    analyze(winning[(winning["goal_diff"] >= 2)], "COMBO A: ventaja 2+ goles")
    analyze(winning[(winning["goal_diff"] == 1) & (winning["odds_at_trigger"] <= 5.0)], "COMBO B: ventaja 1 gol + odds <= 5")
    analyze(winning[(winning["minuto"] > 45)], "COMBO C: 2a parte")
    analyze(winning[(winning["drift_pct"] >= 100)], "COMBO D: drift extremo (>=100%)")
    analyze(winning[(winning["team"] == "home") & (winning["odds_at_trigger"] <= 5.0)], "COMBO E: HOME + odds <= 5")
    analyze(winning[(winning["goal_diff"] == 1) & (winning["minuto"] <= 45)], "COMBO F: ventaja 1 gol + 1a parte")
    analyze(winning[(winning["goal_diff"] == 1) & (winning["minuto"] > 45)], "COMBO G: ventaja 1 gol + 2a parte")
    analyze(winning[(winning["odds_at_trigger"] <= 5.0) & (winning["minuto"] > 45)], "COMBO H: odds <= 5 + 2a parte")

    # === ANALISIS DE LOS FALLOS ===
    print("\n" + "=" * 70)
    print("8. ANALISIS DE FALLOS (los 9 que perdieron)")
    print("=" * 70)

    losses = winning[~winning["won"]].copy()
    wins_df = winning[winning["won"]].copy()

    print(f"\n  FALLOS ({len(losses)}):")
    print(f"  {'Partido':<35} {'T':>4} {'Min':>3} {'Score':>5} {'Odds':>5} {'Drift':>6} {'GD':>2} {'FT':>5}")
    print("  " + "-" * 80)
    for _, r in losses.iterrows():
        m = r['match'][:33]
        print(f"  {m:<35} {r['team']:>4} {r['minuto']:>3} {r['score_at']:>5} {r['odds_at_trigger']:>5.2f} {r['drift_pct']:>5.1f}% {r['goal_diff']:>2} {r['ft_score']:>5}")

    print(f"\n  Analisis de fallos vs aciertos:")
    for col, label in [("minuto", "Minuto"), ("odds_at_trigger", "Odds"), ("drift_pct", "Drift%"), ("goal_diff", "Goal diff")]:
        w_mean = wins_df[col].mean()
        l_mean = losses[col].mean()
        print(f"    {label:12s}: Aciertos={w_mean:.1f}  Fallos={l_mean:.1f}  (diff={l_mean-w_mean:+.1f})")

    # Stats comparison
    print(f"\n  Estadisticas al trigger (aciertos vs fallos):")
    for stat in ["poss", "sot", "shots", "corners", "xg", "momentum"]:
        col_t = f"{stat}_team"
        col_o = f"{stat}_opp"
        if col_t in wins_df.columns:
            w_t = wins_df[col_t].dropna()
            l_t = losses[col_t].dropna()
            if len(w_t) > 0 and len(l_t) > 0:
                print(f"    {stat:12s} team: Aciertos={w_t.mean():.1f}  Fallos={l_t.mean():.1f}")
            w_o = wins_df[col_o].dropna()
            l_o = losses[col_o].dropna()
            if len(w_o) > 0 and len(l_o) > 0:
                print(f"    {stat:12s}  opp: Aciertos={w_o.mean():.1f}  Fallos={l_o.mean():.1f}")

    # Check if losses concentrate in specific score patterns
    print(f"\n  Patron de goles en fallos:")
    for _, r in losses.iterrows():
        sa = r["score_at"].split("-")
        ft = r["ft_score"].split("-")
        goals_after = (int(ft[0]) + int(ft[1])) - (int(sa[0]) + int(sa[1]))
        team_goals_after = int(ft[0 if r["team"] == "home" else 1]) - int(sa[0 if r["team"] == "home" else 1].split("-")[0] if "-" not in sa[0] else sa[0])
        opp_goals_after = int(ft[1 if r["team"] == "home" else 0]) - int(sa[1 if r["team"] == "home" else 0])
        m = r['match'][:30]
        print(f"    {m:<30} {r['score_at']}->  {r['ft_score']} (rival marco {opp_goals_after} goles despues)")


if __name__ == "__main__":
    main()
