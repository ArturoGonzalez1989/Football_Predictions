"""
ML Time-Series: Feature extraction from per-minute match data
=============================================================
Loads individual match CSVs and extracts momentum, volatility,
and trajectory features from the 10-15 minutes BEFORE each bet trigger.
Then re-trains models to see if richer features improve prediction.
"""
import sys
sys.path.insert(0, r'c:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/betfair_scraper/dashboard/backend')

import csv
import re
import numpy as np
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from utils import csv_reader

DATA_DIR = Path(r'c:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/betfair_scraper/data')

print("=" * 70)
print("ML TIME-SERIES: FEATURES FROM PER-MINUTE MATCH DATA")
print("=" * 70)

# ============================================================
# 1. LOAD ALL BETS WITH MATCH IDs
# ============================================================

cartera = csv_reader.analyze_cartera()
bets = cartera["bets"]
bets.sort(key=lambda b: b.get("timestamp_utc", ""))

print(f"\nTotal bets: {len(bets)}")
print(f"Wins: {sum(1 for b in bets if b['won'])}")
print(f"Losses: {sum(1 for b in bets if not b['won'])}")


def resolve_csv_path(match_id: str) -> Path:
    """Find the CSV file for a match, handling URL-encoded filenames."""
    path = DATA_DIR / f"partido_{match_id}.csv"
    if path.exists():
        return path
    encoded = quote(match_id, safe="-")
    path2 = DATA_DIR / f"partido_{encoded}.csv"
    if path2.exists():
        return path2
    prefix = re.sub(r"-?\d+$", "", match_id)
    if DATA_DIR.exists() and prefix:
        for csv_file in DATA_DIR.glob(f"partido_{prefix}*.csv"):
            return csv_file
        encoded_prefix = re.sub(r"-?\d+$", "", encoded)
        if encoded_prefix != prefix:
            for csv_file in DATA_DIR.glob(f"partido_{encoded_prefix}*.csv"):
                return csv_file
    return path


def to_float(val):
    if val is None or str(val).strip() in ("", "N/A", "None"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def load_match_rows(match_id: str) -> list[dict]:
    """Load all rows from a match CSV."""
    path = resolve_csv_path(match_id)
    if not path.exists():
        return []
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        return []
    return rows


# ============================================================
# 2. EXTRACT TIME-SERIES FEATURES FOR EACH BET
# ============================================================
print("\n" + "=" * 70)
print("2. EXTRACTING TIME-SERIES FEATURES (10-15 min window before trigger)")
print("=" * 70)

# Key stats columns to track momentum
STAT_COLS = {
    "xg_local": "xg_l", "xg_visitante": "xg_v",
    "tiros_puerta_local": "sot_l", "tiros_puerta_visitante": "sot_v",
    "tiros_local": "shots_l", "tiros_visitante": "shots_v",
    "corners_local": "corners_l", "corners_visitante": "corners_v",
    "dangerous_attacks_local": "da_l", "dangerous_attacks_visitante": "da_v",
    "attacks_local": "att_l", "attacks_visitante": "att_v",
    "posesion_local": "poss_l", "posesion_visitante": "poss_v",
    "big_chances_local": "bc_l", "big_chances_visitante": "bc_v",
    "back_draw": "odds_draw",
    "back_over25": "odds_o25",
}

WINDOW_MINUTES = 10  # lookback window before trigger


def extract_timeseries_features(rows: list[dict], trigger_minute: float, strategy: str) -> dict:
    """Extract features from the time window before the bet trigger.

    Returns dict of features or None if insufficient data.
    """
    # Filter rows to those with valid minutes
    timed_rows = []
    for r in rows:
        m = to_float(r.get("minuto"))
        if m is not None:
            timed_rows.append((m, r))

    if not timed_rows:
        return None

    # Sort by minute
    timed_rows.sort(key=lambda x: x[0])

    # Find trigger row (closest to trigger_minute)
    trigger_idx = None
    for i, (m, r) in enumerate(timed_rows):
        if m >= trigger_minute:
            trigger_idx = i
            break
    if trigger_idx is None:
        trigger_idx = len(timed_rows) - 1

    # Get window: rows from (trigger_minute - WINDOW) to trigger_minute
    window_start = trigger_minute - WINDOW_MINUTES
    window_rows = [(m, r) for m, r in timed_rows if window_start <= m <= trigger_minute]

    if len(window_rows) < 3:
        # Also try wider window
        window_start = trigger_minute - 15
        window_rows = [(m, r) for m, r in timed_rows if window_start <= m <= trigger_minute]
        if len(window_rows) < 3:
            return None

    # Get trigger row data and window start data
    _, trigger_row = timed_rows[trigger_idx]
    _, first_window_row = window_rows[0]

    f = {}

    # ---- MOMENTUM: delta of cumulative stats over window ----
    for csv_col, short in STAT_COLS.items():
        val_start = to_float(first_window_row.get(csv_col))
        val_end = to_float(trigger_row.get(csv_col))
        if val_start is not None and val_end is not None:
            f[f"delta_{short}"] = val_end - val_start
        else:
            f[f"delta_{short}"] = 0

    # Combined momentum features
    f["delta_sot_total"] = f.get("delta_sot_l", 0) + f.get("delta_sot_v", 0)
    f["delta_shots_total"] = f.get("delta_shots_l", 0) + f.get("delta_shots_v", 0)
    f["delta_xg_total"] = f.get("delta_xg_l", 0) + f.get("delta_xg_v", 0)
    f["delta_corners_total"] = f.get("delta_corners_l", 0) + f.get("delta_corners_v", 0)
    f["delta_da_total"] = f.get("delta_da_l", 0) + f.get("delta_da_v", 0)
    f["delta_bc_total"] = f.get("delta_bc_l", 0) + f.get("delta_bc_v", 0)

    # Asymmetry: which team is generating more pressure?
    f["sot_asymmetry"] = abs(f.get("delta_sot_l", 0) - f.get("delta_sot_v", 0))
    f["da_asymmetry"] = abs(f.get("delta_da_l", 0) - f.get("delta_da_v", 0))
    f["xg_asymmetry"] = abs(f.get("delta_xg_l", 0) - f.get("delta_xg_v", 0))

    # ---- ODDS VOLATILITY ----
    odds_draw_series = []
    odds_o25_series = []
    for m, r in window_rows:
        od = to_float(r.get("back_draw"))
        oo = to_float(r.get("back_over25"))
        if od is not None and od > 1:
            odds_draw_series.append(od)
        if oo is not None and oo > 1:
            odds_o25_series.append(oo)

    if len(odds_draw_series) >= 3:
        f["odds_draw_volatility"] = float(np.std(odds_draw_series))
        f["odds_draw_trend"] = odds_draw_series[-1] - odds_draw_series[0]
        f["odds_draw_trend_pct"] = (odds_draw_series[-1] - odds_draw_series[0]) / odds_draw_series[0] * 100
        f["odds_draw_min"] = min(odds_draw_series)
        f["odds_draw_max"] = max(odds_draw_series)
        f["odds_draw_range"] = f["odds_draw_max"] - f["odds_draw_min"]
    else:
        f["odds_draw_volatility"] = 0
        f["odds_draw_trend"] = 0
        f["odds_draw_trend_pct"] = 0
        f["odds_draw_min"] = 0
        f["odds_draw_max"] = 0
        f["odds_draw_range"] = 0

    if len(odds_o25_series) >= 3:
        f["odds_o25_volatility"] = float(np.std(odds_o25_series))
        f["odds_o25_trend"] = odds_o25_series[-1] - odds_o25_series[0]
    else:
        f["odds_o25_volatility"] = 0
        f["odds_o25_trend"] = 0

    # ---- PACE / INTENSITY ----
    window_duration = window_rows[-1][0] - window_rows[0][0]
    if window_duration > 0:
        f["shots_per_min"] = f["delta_shots_total"] / window_duration
        f["sot_per_min"] = f["delta_sot_total"] / window_duration
        f["corners_per_min"] = f["delta_corners_total"] / window_duration
        f["da_per_min"] = f["delta_da_total"] / window_duration
    else:
        f["shots_per_min"] = 0
        f["sot_per_min"] = 0
        f["corners_per_min"] = 0
        f["da_per_min"] = 0

    # ---- ABSOLUTE STATS at trigger ----
    f["sot_at_trigger"] = (to_float(trigger_row.get("tiros_puerta_local")) or 0) + (to_float(trigger_row.get("tiros_puerta_visitante")) or 0)
    f["xg_at_trigger"] = (to_float(trigger_row.get("xg_local")) or 0) + (to_float(trigger_row.get("xg_visitante")) or 0)
    f["corners_at_trigger"] = (to_float(trigger_row.get("corners_local")) or 0) + (to_float(trigger_row.get("corners_visitante")) or 0)
    f["da_at_trigger"] = (to_float(trigger_row.get("dangerous_attacks_local")) or 0) + (to_float(trigger_row.get("dangerous_attacks_visitante")) or 0)
    f["poss_diff_at_trigger"] = abs((to_float(trigger_row.get("posesion_local")) or 50) - (to_float(trigger_row.get("posesion_visitante")) or 50))

    # ---- SCORE CONTEXT ----
    gl = to_float(trigger_row.get("goles_local")) or 0
    gv = to_float(trigger_row.get("goles_visitante")) or 0
    f["goals_total"] = gl + gv
    f["goal_diff_abs"] = abs(gl - gv)
    f["is_drawing"] = 1 if gl == gv else 0

    # ---- NUMBER OF CAPTURES (data density) ----
    f["captures_in_window"] = len(window_rows)

    return f


# Process all bets
enriched_bets = []
skipped = 0

for b in bets:
    match_id = b.get("match_id", "")
    trigger_min = b.get("minuto") or 0
    strategy = b.get("strategy", "")

    if not match_id:
        skipped += 1
        continue

    rows = load_match_rows(match_id)
    if not rows:
        skipped += 1
        continue

    ts_features = extract_timeseries_features(rows, trigger_min, strategy)
    if ts_features is None:
        skipped += 1
        continue

    enriched_bets.append({
        "bet": b,
        "ts_features": ts_features,
    })

print(f"\nBets with time-series features: {len(enriched_bets)}/{len(bets)}")
print(f"Skipped (no CSV or insufficient data): {skipped}")

if len(enriched_bets) < 20:
    print("\nERROR: Too few bets with time-series data. Cannot proceed with ML.")
    sys.exit(1)

# ============================================================
# 3. BUILD FEATURE MATRIX
# ============================================================
print("\n" + "=" * 70)
print("3. FEATURE MATRIX: BASE + TIME-SERIES")
print("=" * 70)

# Combine base features (from ml_exploration.py) with time-series features
all_features = []
labels = []
bet_refs = []

for item in enriched_bets:
    b = item["bet"]
    ts = item["ts_features"]

    f = {}

    # --- Base features (same as ml_exploration.py) ---
    f["minuto"] = b.get("minuto") or 0
    f["odds"] = b.get("back_draw") or b.get("back_over_odds") or b.get("over_odds") or b.get("back_odds") or 0
    f["is_draw"] = 1 if b["strategy"] == "back_draw_00" else 0
    f["is_xg"] = 1 if b["strategy"] == "xg_underperformance" else 0
    f["is_drift"] = 1 if b["strategy"] == "odds_drift" else 0
    f["is_clustering"] = 1 if b["strategy"] == "goal_clustering" else 0
    f["is_pressure"] = 1 if b["strategy"] == "pressure_cooker" else 0
    f["implied_prob"] = 1.0 / f["odds"] if f["odds"] > 1 else 0.5

    ts_str = b.get("timestamp_utc", "")
    if ts_str:
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            f["hour"] = dt.hour
            f["is_weekend"] = 1 if dt.weekday() >= 5 else 0
        except Exception:
            f["hour"] = 12
            f["is_weekend"] = 0
    else:
        f["hour"] = 12
        f["is_weekend"] = 0

    # --- Time-series features ---
    # Momentum
    f["ts_delta_sot_total"] = ts.get("delta_sot_total", 0)
    f["ts_delta_shots_total"] = ts.get("delta_shots_total", 0)
    f["ts_delta_xg_total"] = ts.get("delta_xg_total", 0)
    f["ts_delta_corners_total"] = ts.get("delta_corners_total", 0)
    f["ts_delta_da_total"] = ts.get("delta_da_total", 0)
    f["ts_delta_bc_total"] = ts.get("delta_bc_total", 0)

    # Asymmetry (one-sided pressure = more likely to score)
    f["ts_sot_asymmetry"] = ts.get("sot_asymmetry", 0)
    f["ts_da_asymmetry"] = ts.get("da_asymmetry", 0)
    f["ts_xg_asymmetry"] = ts.get("xg_asymmetry", 0)

    # Odds dynamics
    f["ts_odds_draw_volatility"] = ts.get("odds_draw_volatility", 0)
    f["ts_odds_draw_trend_pct"] = ts.get("odds_draw_trend_pct", 0)
    f["ts_odds_draw_range"] = ts.get("odds_draw_range", 0)
    f["ts_odds_o25_volatility"] = ts.get("odds_o25_volatility", 0)
    f["ts_odds_o25_trend"] = ts.get("odds_o25_trend", 0)

    # Pace
    f["ts_shots_per_min"] = ts.get("shots_per_min", 0)
    f["ts_sot_per_min"] = ts.get("sot_per_min", 0)
    f["ts_da_per_min"] = ts.get("da_per_min", 0)

    # Absolute at trigger
    f["ts_sot_at_trigger"] = ts.get("sot_at_trigger", 0)
    f["ts_xg_at_trigger"] = ts.get("xg_at_trigger", 0)
    f["ts_da_at_trigger"] = ts.get("da_at_trigger", 0)
    f["ts_poss_diff"] = ts.get("poss_diff_at_trigger", 0)

    # Score context
    f["ts_goals_total"] = ts.get("goals_total", 0)
    f["ts_is_drawing"] = ts.get("is_drawing", 0)

    all_features.append(f)
    labels.append(1 if b["won"] else 0)
    bet_refs.append(b)

feature_names = sorted(all_features[0].keys())
X = np.array([[f[k] for k in feature_names] for f in all_features])
y = np.array(labels)

print(f"\nTotal features: {len(feature_names)} ({len(feature_names) - 10} time-series + 10 base)")
print(f"Samples: {len(y)}")
print(f"Class balance: {sum(y)}/{len(y)} wins ({sum(y)/len(y)*100:.1f}%)")

# Identify TS feature names
ts_feature_names = [n for n in feature_names if n.startswith("ts_")]
base_feature_names = [n for n in feature_names if not n.startswith("ts_")]
print(f"\nBase features ({len(base_feature_names)}): {', '.join(base_feature_names)}")
print(f"Time-series features ({len(ts_feature_names)}): {', '.join(ts_feature_names)}")

# ============================================================
# 4. CORRELATION ANALYSIS (TS features only)
# ============================================================
print("\n" + "=" * 70)
print("4. CORRELACION: TIME-SERIES FEATURES -> RESULTADO")
print("=" * 70)

correlations = []
for i, name in enumerate(feature_names):
    if not name.startswith("ts_"):
        continue
    col = X[:, i]
    if np.std(col) > 0:
        mean_win = np.mean(col[y == 1])
        mean_loss = np.mean(col[y == 0])
        n1 = sum(y == 1)
        n0 = sum(y == 0)
        n = len(y)
        r = (mean_win - mean_loss) / np.std(col) * np.sqrt(n1 * n0 / n**2)
        correlations.append((name, r, mean_win, mean_loss))

correlations.sort(key=lambda x: abs(x[1]), reverse=True)
print(f"\n{'Feature':<30s} {'Corr':>8s} {'Mean(Win)':>10s} {'Mean(Loss)':>10s} {'Signal'}")
print("-" * 80)
for name, r, mw, ml in correlations:
    direction = "WIN +" if r > 0 else "LOSS +"
    marker = " ***" if abs(r) > 0.15 else " *" if abs(r) > 0.10 else ""
    print(f"  {name:<30s} {r:+8.3f} {mw:10.3f} {ml:10.3f}  {direction}{marker}")

# ============================================================
# 5. ML COMPARISON: BASE vs BASE+TS
# ============================================================
print("\n" + "=" * 70)
print("5. ML COMPARISON: BASE ONLY vs BASE + TIME-SERIES")
print("=" * 70)

from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold, LeaveOneOut
from sklearn.preprocessing import StandardScaler

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
loo = LeaveOneOut()

# Build base-only feature matrix
base_indices = [i for i, n in enumerate(feature_names) if not n.startswith("ts_")]
X_base = X[:, base_indices]

scaler_base = StandardScaler()
X_base_scaled = scaler_base.fit_transform(X_base)

scaler_full = StandardScaler()
X_full_scaled = scaler_full.fit_transform(X)

baseline = sum(y) / len(y)
print(f"\nBaseline (always predict majority): {baseline*100:.1f}%")

models = {
    "LogReg (C=0.1)": LogisticRegression(C=0.1, max_iter=1000, random_state=42),
    "LogReg (C=1.0)": LogisticRegression(C=1.0, max_iter=1000, random_state=42),
    "DecTree (d=3)": DecisionTreeClassifier(max_depth=3, min_samples_leaf=5, random_state=42),
    "RandomForest": RandomForestClassifier(n_estimators=100, max_depth=3, min_samples_leaf=5, random_state=42),
    "GradientBoost": GradientBoostingClassifier(n_estimators=50, max_depth=2, min_samples_leaf=5, learning_rate=0.1, random_state=42),
}

print(f"\n{'Model':<25s} {'Base 5CV':>10s} {'Full 5CV':>10s} {'Gain':>8s} {'Base LOO':>10s} {'Full LOO':>10s} {'Gain':>8s}")
print("-" * 95)

best_model_name = None
best_loo_score = 0

for name, model in models.items():
    # 5-fold CV
    if "Tree" in name or "Forest" in name or "Boost" in name:
        s_base = cross_val_score(model, X_base, y, cv=cv, scoring='accuracy')
        s_full = cross_val_score(model, X, y, cv=cv, scoring='accuracy')
        l_base = cross_val_score(model, X_base, y, cv=loo, scoring='accuracy')
        l_full = cross_val_score(model, X, y, cv=loo, scoring='accuracy')
    else:
        s_base = cross_val_score(model, X_base_scaled, y, cv=cv, scoring='accuracy')
        s_full = cross_val_score(model, X_full_scaled, y, cv=cv, scoring='accuracy')
        l_base = cross_val_score(model, X_base_scaled, y, cv=loo, scoring='accuracy')
        l_full = cross_val_score(model, X_full_scaled, y, cv=loo, scoring='accuracy')

    gain_cv = (s_full.mean() - s_base.mean()) * 100
    gain_loo = (l_full.mean() - l_base.mean()) * 100

    print(f"  {name:<25s} {s_base.mean()*100:8.1f}% {s_full.mean()*100:8.1f}% {gain_cv:+6.1f}pp {l_base.mean()*100:8.1f}% {l_full.mean()*100:8.1f}% {gain_loo:+6.1f}pp")

    if l_full.mean() > best_loo_score:
        best_loo_score = l_full.mean()
        best_model_name = name

print(f"\nBest model (LOO): {best_model_name} ({best_loo_score*100:.1f}%)")
print(f"Improvement over baseline: {(best_loo_score - baseline)*100:+.1f}pp")

# ============================================================
# 6. FEATURE IMPORTANCE (best model)
# ============================================================
print("\n" + "=" * 70)
print("6. FEATURE IMPORTANCE (Random Forest on full features)")
print("=" * 70)

rf = RandomForestClassifier(n_estimators=200, max_depth=3, min_samples_leaf=5, random_state=42)
rf.fit(X, y)

importances = rf.feature_importances_
imp_sorted = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)

print(f"\n{'Feature':<35s} {'Importance':>12s} {'Type':>6s}")
print("-" * 60)
for name, imp in imp_sorted:
    if imp > 0.005:
        ftype = "TS" if name.startswith("ts_") else "BASE"
        bar = "#" * int(imp * 80)
        print(f"  {name:<35s} {imp:10.4f}  {ftype:>4s}  {bar}")

ts_importance = sum(imp for name, imp in imp_sorted if name.startswith("ts_"))
base_importance = sum(imp for name, imp in imp_sorted if not name.startswith("ts_"))
print(f"\nTotal importance — Base: {base_importance:.3f} | Time-series: {ts_importance:.3f}")

# ============================================================
# 7. SIGNAL QUALITY SCORING (enriched)
# ============================================================
print("\n" + "=" * 70)
print("7. SIGNAL QUALITY SCORING (enriched model)")
print("=" * 70)

# Use best logistic regression for probabilities
lr = LogisticRegression(C=0.1, max_iter=1000, random_state=42)
lr.fit(X_full_scaled, y)
probs = lr.predict_proba(X_full_scaled)[:, 1]

# Confidence buckets
high = probs >= 0.75
medium = (probs >= 0.5) & (probs < 0.75)
low = probs < 0.5

for label, mask in [("HIGH (>=0.75)", high), ("MEDIUM (0.50-0.75)", medium), ("LOW (<0.50)", low)]:
    n = sum(mask)
    if n > 0:
        wr = sum(y[mask]) / n * 100
        pl = sum(bet_refs[i]["pl"] for i in range(len(bet_refs)) if mask[i])
        print(f"\n{label}: {n} bets | WR: {wr:.1f}% | P/L: {pl:+.2f}")
        if label.startswith("LOW"):
            print("  Detalle:")
            for i in range(len(bet_refs)):
                if mask[i]:
                    b = bet_refs[i]
                    res = "WIN" if b["won"] else "LOSS"
                    print(f"    [{res:4s}] {b['match'][:35]:35s} | {b['strategy']:20s} | min {b.get('minuto', '?'):>3} | prob {probs[i]:.2f} | P/L {b['pl']:+.2f}")

# ============================================================
# 8. COMPARE: BASE SCORING vs ENRICHED SCORING
# ============================================================
print("\n" + "=" * 70)
print("8. COMPARISON: BASE SCORING vs ENRICHED SCORING")
print("=" * 70)

# Base model (same as ml_exploration.py)
lr_base = LogisticRegression(C=0.1, max_iter=1000, random_state=42)
lr_base.fit(X_base_scaled, y)
probs_base = lr_base.predict_proba(X_base_scaled)[:, 1]

# Compare ranking quality
from sklearn.metrics import roc_auc_score, brier_score_loss

auc_base = roc_auc_score(y, probs_base)
auc_full = roc_auc_score(y, probs)
brier_base = brier_score_loss(y, probs_base)
brier_full = brier_score_loss(y, probs)

print(f"\n{'Metric':<25s} {'Base':>10s} {'Enriched':>10s} {'Delta':>10s}")
print("-" * 60)
print(f"  {'AUC-ROC':<25s} {auc_base:10.4f} {auc_full:10.4f} {auc_full-auc_base:+10.4f}")
print(f"  {'Brier Score (lower=better)':<25s} {brier_base:10.4f} {brier_full:10.4f} {brier_full-brier_base:+10.4f}")

# Show how many bets change confidence bucket
upgrades = sum(1 for i in range(len(probs)) if probs_base[i] < 0.5 and probs[i] >= 0.5)
downgrades = sum(1 for i in range(len(probs)) if probs_base[i] >= 0.5 and probs[i] < 0.5)
print(f"\nBets that changed confidence bucket:")
print(f"  Upgraded (low -> med/high): {upgrades}")
print(f"  Downgraded (med/high -> low): {downgrades}")

# ============================================================
# 9. TRAJECTORY VISUALIZATION: WINS vs LOSSES
# ============================================================
print("\n" + "=" * 70)
print("9. TRAJECTORY ANALYSIS: WHAT WINNING BETS LOOK LIKE vs LOSING")
print("=" * 70)

# Aggregate time-series features by outcome
win_features = {n: [] for n in ts_feature_names}
loss_features = {n: [] for n in ts_feature_names}

for i, item in enumerate(enriched_bets):
    target = win_features if labels[i] == 1 else loss_features
    for n in ts_feature_names:
        idx = feature_names.index(n)
        target[n].append(X[i, idx])

print(f"\n{'Feature':<35s} {'Win Avg':>10s} {'Loss Avg':>10s} {'Win Med':>10s} {'Loss Med':>10s}")
print("-" * 80)
for n in ts_feature_names:
    if len(win_features[n]) > 0 and len(loss_features[n]) > 0:
        w_avg = np.mean(win_features[n])
        l_avg = np.mean(loss_features[n])
        w_med = np.median(win_features[n])
        l_med = np.median(loss_features[n])
        diff = abs(w_avg - l_avg)
        marker = " <<<" if diff > max(abs(w_avg), abs(l_avg)) * 0.3 and diff > 0.1 else ""
        print(f"  {n:<35s} {w_avg:10.3f} {l_avg:10.3f} {w_med:10.3f} {l_med:10.3f}{marker}")

# ============================================================
# 10. PER-STRATEGY TRAJECTORY PATTERNS
# ============================================================
print("\n" + "=" * 70)
print("10. PER-STRATEGY: WIN vs LOSS TRAJECTORY PATTERNS")
print("=" * 70)

strategies = ["back_draw_00", "xg_underperformance", "odds_drift", "goal_clustering"]
key_ts_features = ["ts_delta_sot_total", "ts_delta_xg_total", "ts_delta_da_total",
                    "ts_odds_draw_volatility", "ts_shots_per_min", "ts_sot_asymmetry"]

for strat in strategies:
    strat_mask = np.array([bet_refs[i]["strategy"] == strat for i in range(len(bet_refs))])
    strat_wins = strat_mask & (y == 1)
    strat_losses = strat_mask & (y == 0)
    n_w = sum(strat_wins)
    n_l = sum(strat_losses)

    if n_w < 2 or n_l < 2:
        continue

    print(f"\n--- {strat} (W:{n_w} / L:{n_l}) ---")
    for fname in key_ts_features:
        idx = feature_names.index(fname)
        w_vals = X[strat_wins, idx]
        l_vals = X[strat_losses, idx]
        w_avg = np.mean(w_vals)
        l_avg = np.mean(l_vals)
        diff_pct = ((w_avg - l_avg) / max(abs(l_avg), 0.01)) * 100
        marker = " ***" if abs(diff_pct) > 30 else ""
        print(f"  {fname:<35s} Win:{w_avg:8.3f}  Loss:{l_avg:8.3f}  diff:{diff_pct:+6.0f}%{marker}")

# ============================================================
# CONCLUSIONS
# ============================================================
print("\n" + "=" * 70)
print("CONCLUSIONES")
print("=" * 70)
print(f"""
1. Time-series features aportaron importancia total de {ts_importance:.1%}
   vs base features {base_importance:.1%}

2. Mejor modelo: {best_model_name} con LOO accuracy {best_loo_score*100:.1f}%
   (baseline: {baseline*100:.1f}%, ganancia: {(best_loo_score-baseline)*100:+.1f}pp)

3. AUC-ROC mejoró de {auc_base:.4f} (base) a {auc_full:.4f} (enriched)
   Delta: {auc_full-auc_base:+.4f}

4. El scoring enriquecido permite mejor separación de señales:
   - HIGH confidence: {sum(high)} bets, {sum(y[high])/max(sum(high),1)*100:.0f}% WR
   - LOW confidence:  {sum(low)} bets, {sum(y[low])/max(sum(low),1)*100:.0f}% WR
""")
