"""
Analisis de Estrategia: Odds Drift
===================================
Concepto: Cuando las cuotas de un equipo suben >30% en 10 minutos
(el mercado lo "abandona"), apostar a que ese equipo se recupera.

Analiza datos reales del scraper de Betfair.
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(r"c:\Users\agonz\OneDrive\Documents\Proyectos\Furbo\betfair_scraper\data")
COMMISSION = 0.05  # Betfair 5%
STAKE = 10  # EUR flat

# Drift parameters
DRIFT_PCT = 0.30       # 30% increase in odds
WINDOW_MINUTES = 10    # within 10 minutes
MIN_MINUTE = 5         # don't trigger before minute 5
MAX_MINUTE = 80        # don't trigger after minute 80
MIN_ODDS = 1.5         # minimum odds at trigger (avoid extreme favorites)
MAX_ODDS = 30.0        # maximum odds at trigger (avoid lottery tickets)


def load_all_matches():
    """Load all CSV files from data directory."""
    matches = []
    csv_files = sorted(DATA_DIR.glob("partido_*.csv"))

    for f in csv_files:
        try:
            df = pd.read_csv(f)
            if len(df) < 10:  # skip very short captures
                continue
            # Need at minimum: minuto, back_home, back_away, goles
            required = ["minuto", "back_home", "back_away", "goles_local", "goles_visitante"]
            if not all(c in df.columns for c in required):
                continue

            # Extract match name from filename
            name = f.stem.replace("partido_", "").rsplit("-apuestas-", 1)[0]
            match_id = f.stem.rsplit("-apuestas-", 1)[-1] if "-apuestas-" in f.stem else f.stem

            df["_match_name"] = name
            df["_match_id"] = match_id
            df["_file"] = f.name
            matches.append(df)
        except Exception as e:
            continue

    return matches


def get_final_score(df):
    """Get final score from last rows."""
    last_rows = df.tail(5)
    gl = last_rows["goles_local"].max()
    gv = last_rows["goles_visitante"].max()
    return int(gl) if pd.notna(gl) else None, int(gv) if pd.notna(gv) else None


def detect_drift_triggers(df):
    """
    Detect odds drift triggers in a match.
    Returns list of trigger dicts.
    """
    triggers = []

    # Clean minuto column
    df = df.copy()
    df["minuto"] = pd.to_numeric(df["minuto"], errors="coerce")
    df = df.dropna(subset=["minuto"])
    df = df.sort_values("minuto").reset_index(drop=True)

    # Convert odds to numeric
    for col in ["back_home", "back_away", "back_draw"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Get final score
    gl_final, gv_final = get_final_score(df)
    if gl_final is None or gv_final is None:
        return triggers

    ft_score = f"{gl_final}-{gv_final}"
    match_name = df["_match_name"].iloc[0]
    match_id = df["_match_id"].iloc[0]

    # Track if we already triggered for each team in this match
    triggered_home = False
    triggered_away = False

    # Check each row for drift from any previous row within window
    for i in range(1, len(df)):
        current_min = df.iloc[i]["minuto"]
        if current_min < MIN_MINUTE or current_min > MAX_MINUTE:
            continue

        # Look back at rows within the window
        for j in range(i - 1, -1, -1):
            prev_min = df.iloc[j]["minuto"]
            if current_min - prev_min > WINDOW_MINUTES:
                break
            if current_min - prev_min < 2:  # need at least 2 min gap
                continue

            # Check HOME odds drift (odds going UP = market abandoning home)
            if not triggered_home:
                prev_home = df.iloc[j]["back_home"]
                curr_home = df.iloc[i]["back_home"]
                if pd.notna(prev_home) and pd.notna(curr_home) and prev_home > 0:
                    drift_home = (curr_home - prev_home) / prev_home
                    if drift_home >= DRIFT_PCT and MIN_ODDS <= curr_home <= MAX_ODDS:
                        # Get current score at trigger
                        gl_at = int(df.iloc[i].get("goles_local", 0)) if pd.notna(df.iloc[i].get("goles_local")) else 0
                        gv_at = int(df.iloc[i].get("goles_visitante", 0)) if pd.notna(df.iloc[i].get("goles_visitante")) else 0

                        # Home team wins?
                        won = gl_final > gv_final
                        profit = (curr_home - 1) * STAKE * (1 - COMMISSION) if won else -STAKE

                        triggers.append({
                            "match": match_name,
                            "match_id": match_id,
                            "team": "home",
                            "minuto": int(current_min),
                            "score_at": f"{gl_at}-{gv_at}",
                            "odds_before": round(prev_home, 2),
                            "odds_at_trigger": round(curr_home, 2),
                            "drift_pct": round(drift_home * 100, 1),
                            "min_window": round(current_min - prev_min, 1),
                            "ft_score": ft_score,
                            "won": won,
                            "profit": round(profit, 2),
                        })
                        triggered_home = True
                        break

            # Check AWAY odds drift
            if not triggered_away:
                prev_away = df.iloc[j]["back_away"]
                curr_away = df.iloc[i]["back_away"]
                if pd.notna(prev_away) and pd.notna(curr_away) and prev_away > 0:
                    drift_away = (curr_away - prev_away) / prev_away
                    if drift_away >= DRIFT_PCT and MIN_ODDS <= curr_away <= MAX_ODDS:
                        gl_at = int(df.iloc[i].get("goles_local", 0)) if pd.notna(df.iloc[i].get("goles_local")) else 0
                        gv_at = int(df.iloc[i].get("goles_visitante", 0)) if pd.notna(df.iloc[i].get("goles_visitante")) else 0

                        won = gv_final > gl_final
                        profit = (curr_away - 1) * STAKE * (1 - COMMISSION) if won else -STAKE

                        triggers.append({
                            "match": match_name,
                            "match_id": match_id,
                            "team": "away",
                            "minuto": int(current_min),
                            "score_at": f"{gl_at}-{gv_at}",
                            "odds_before": round(prev_away, 2),
                            "odds_at_trigger": round(curr_away, 2),
                            "drift_pct": round(drift_away * 100, 1),
                            "min_window": round(current_min - prev_min, 1),
                            "ft_score": ft_score,
                            "won": won,
                            "profit": round(profit, 2),
                        })
                        triggered_away = True
                        break

        if triggered_home and triggered_away:
            break

    return triggers


def analyze_with_filters(triggers_df, label, filter_fn=None):
    """Analyze a subset of triggers."""
    df = triggers_df if filter_fn is None else triggers_df[filter_fn(triggers_df)]

    if len(df) == 0:
        print(f"\n  {label}: 0 triggers")
        return

    total = len(df)
    wins = df["won"].sum()
    wr = wins / total * 100
    total_profit = df["profit"].sum()
    total_staked = total * STAKE
    roi = total_profit / total_staked * 100
    avg_odds = df["odds_at_trigger"].mean()
    be_wr = 1 / avg_odds * 100 / (1 - COMMISSION)  # break-even WR including commission

    # Max drawdown
    cumul = df["profit"].cumsum()
    peak = cumul.cummax()
    dd = (peak - cumul).max()

    # Worst streak
    worst = 0
    current = 0
    for w in df["won"]:
        if not w:
            current += 1
            worst = max(worst, current)
        else:
            current = 0

    print(f"\n  {label}:")
    print(f"    Triggers: {total} | Wins: {wins} | WR: {wr:.1f}%")
    print(f"    Avg odds: {avg_odds:.2f} | Break-even WR: {be_wr:.1f}%")
    print(f"    P/L: {total_profit:+.2f} EUR | ROI: {roi:+.1f}%")
    print(f"    Max DD: {dd:.2f} EUR | Peor racha: {worst} fallos seguidos")

    return {"triggers": total, "wins": int(wins), "wr": wr, "pl": total_profit, "roi": roi, "avg_odds": avg_odds, "max_dd": dd, "worst_streak": worst}


def main():
    print("=" * 70)
    print("ANALISIS ODDS DRIFT - Back al equipo abandonado por el mercado")
    print("=" * 70)
    print(f"\nParametros: drift >= {DRIFT_PCT*100:.0f}% en {WINDOW_MINUTES} min")
    print(f"Rango: min {MIN_MINUTE}-{MAX_MINUTE} | Odds: {MIN_ODDS}-{MAX_ODDS}")
    print(f"Stake: {STAKE} EUR flat | Comision: {COMMISSION*100:.0f}%")

    # Load data
    print("\nCargando partidos...")
    matches = load_all_matches()
    print(f"Partidos cargados: {len(matches)}")

    # Detect triggers
    all_triggers = []
    matches_with_triggers = 0

    for df in matches:
        triggers = detect_drift_triggers(df)
        if triggers:
            matches_with_triggers += 1
            all_triggers.extend(triggers)

    print(f"Partidos con drift: {matches_with_triggers}/{len(matches)}")
    print(f"Triggers totales: {len(all_triggers)}")

    if not all_triggers:
        print("\nNo se encontraron triggers. Prueba con parametros menos restrictivos.")
        return

    tdf = pd.DataFrame(all_triggers)

    # === ANALISIS BASE ===
    print("\n" + "=" * 70)
    print("RESULTADOS")
    print("=" * 70)

    analyze_with_filters(tdf, "BASE (todos los triggers)")

    # === FILTROS ===

    # By team
    analyze_with_filters(tdf, "Solo HOME", lambda d: d["team"] == "home")
    analyze_with_filters(tdf, "Solo AWAY", lambda d: d["team"] == "away")

    # By drift magnitude
    analyze_with_filters(tdf, "Drift 30-50%", lambda d: (d["drift_pct"] >= 30) & (d["drift_pct"] < 50))
    analyze_with_filters(tdf, "Drift 50-100%", lambda d: (d["drift_pct"] >= 50) & (d["drift_pct"] < 100))
    analyze_with_filters(tdf, "Drift >= 100%", lambda d: d["drift_pct"] >= 100)

    # By odds range
    analyze_with_filters(tdf, "Odds 1.5-4.0 (favorito castigado)", lambda d: (d["odds_at_trigger"] >= 1.5) & (d["odds_at_trigger"] <= 4.0))
    analyze_with_filters(tdf, "Odds 4.0-10.0 (odds medias)", lambda d: (d["odds_at_trigger"] > 4.0) & (d["odds_at_trigger"] <= 10.0))
    analyze_with_filters(tdf, "Odds > 10.0 (cuotas altas)", lambda d: d["odds_at_trigger"] > 10.0)

    # By minute
    analyze_with_filters(tdf, "Primera parte (min 5-45)", lambda d: d["minuto"] <= 45)
    analyze_with_filters(tdf, "Segunda parte (min 46-80)", lambda d: d["minuto"] > 45)

    # By score at trigger
    analyze_with_filters(tdf, "Equipo va perdiendo", lambda d: (
        ((d["team"] == "home") & (d["score_at"].apply(lambda s: int(s.split("-")[0]) < int(s.split("-")[1])))) |
        ((d["team"] == "away") & (d["score_at"].apply(lambda s: int(s.split("-")[1]) < int(s.split("-")[0]))))
    ))
    analyze_with_filters(tdf, "Equipo va empatando", lambda d: (
        d["score_at"].apply(lambda s: int(s.split("-")[0]) == int(s.split("-")[1]))
    ))
    analyze_with_filters(tdf, "Equipo va ganando", lambda d: (
        ((d["team"] == "home") & (d["score_at"].apply(lambda s: int(s.split("-")[0]) > int(s.split("-")[1])))) |
        ((d["team"] == "away") & (d["score_at"].apply(lambda s: int(s.split("-")[1]) > int(s.split("-")[0]))))
    ))

    # Combined: odds < 10 + equipo va perdiendo
    analyze_with_filters(tdf, "COMBINADO: Odds < 10 + va perdiendo", lambda d: (
        (d["odds_at_trigger"] < 10.0) &
        (
            ((d["team"] == "home") & (d["score_at"].apply(lambda s: int(s.split("-")[0]) < int(s.split("-")[1])))) |
            ((d["team"] == "away") & (d["score_at"].apply(lambda s: int(s.split("-")[1]) < int(s.split("-")[0]))))
        )
    ))

    # Combined: odds < 6 + primera parte
    analyze_with_filters(tdf, "COMBINADO: Odds < 6 + primera parte", lambda d: (
        (d["odds_at_trigger"] < 6.0) & (d["minuto"] <= 45)
    ))

    # === DETALLE DE TRIGGERS ===
    print("\n" + "=" * 70)
    print("DETALLE DE TRIGGERS")
    print("=" * 70)

    tdf_sorted = tdf.sort_values("profit", ascending=False)

    print(f"\n{'#':>3} {'Partido':<35} {'Team':>4} {'Min':>3} {'Score':>5} {'Odds':>6} {'Drift':>6} {'FT':>5} {'Won':>4} {'P/L':>8}")
    print("-" * 95)

    for idx, row in tdf_sorted.iterrows():
        match_short = row['match'][:33]
        won_str = "SI" if row['won'] else "NO"
        print(f"{idx+1:>3} {match_short:<35} {row['team']:>4} {row['minuto']:>3} {row['score_at']:>5} {row['odds_at_trigger']:>6.2f} {row['drift_pct']:>5.1f}% {row['ft_score']:>5} {won_str:>4} {row['profit']:>+8.2f}")

    print(f"\n{'':>3} {'TOTAL':<35} {'':>4} {'':>3} {'':>5} {'':>6} {'':>6} {'':>5} {'':>4} {tdf['profit'].sum():>+8.2f}")


if __name__ == "__main__":
    main()
