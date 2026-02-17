"""
ML Exploration: Feature importance and signal quality scoring
=============================================================
With ~200 matches and ~95 bets, we explore whether ML can improve
our strategy selection by scoring signal quality at entry time.
"""
import sys
sys.path.insert(0, r'c:/Users/agonz/OneDrive/Documents/Proyectos/Furbo/betfair_scraper/dashboard/backend')

import json
import numpy as np
from collections import defaultdict
from utils import csv_reader

print("=" * 70)
print("ML EXPLORATION: CAN WE SCORE SIGNAL QUALITY?")
print("=" * 70)

# ============================================================
# 1. EXTRACT FEATURES FROM ALL BETS
# ============================================================

cartera = csv_reader.analyze_cartera()
bets = cartera["bets"]
bets.sort(key=lambda b: b.get("timestamp_utc", ""))

print(f"\nTotal bets: {len(bets)}")
print(f"Wins: {sum(1 for b in bets if b['won'])}")
print(f"Losses: {sum(1 for b in bets if not b['won'])}")

# Extract features available at bet time
features = []
labels = []
bet_info = []

for b in bets:
    f = {}

    # Universal features
    f["minuto"] = b.get("minuto") or 0
    f["odds"] = b.get("back_draw") or b.get("back_over_odds") or b.get("over_odds") or b.get("back_odds") or 0

    # Strategy encoding
    f["is_draw"] = 1 if b["strategy"] == "back_draw_00" else 0
    f["is_xg"] = 1 if b["strategy"] == "xg_underperformance" else 0
    f["is_drift"] = 1 if b["strategy"] == "odds_drift" else 0
    f["is_clustering"] = 1 if b["strategy"] == "goal_clustering" else 0
    f["is_pressure"] = 1 if b["strategy"] == "pressure_cooker" else 0

    # Strategy-specific features
    f["xg_excess"] = b.get("xg_excess") or 0
    f["drift_pct"] = b.get("drift_pct") or 0
    f["goal_diff"] = b.get("goal_diff") or 0
    f["sot_max"] = b.get("sot_max") or 0

    # Temporal
    ts = b.get("timestamp_utc", "")
    if ts:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            f["hour"] = dt.hour
            f["is_weekend"] = 1 if dt.weekday() >= 5 else 0
            f["is_sunday"] = 1 if dt.weekday() == 6 else 0
        except:
            f["hour"] = 12
            f["is_weekend"] = 0
            f["is_sunday"] = 0
    else:
        f["hour"] = 12
        f["is_weekend"] = 0
        f["is_sunday"] = 0

    # Implied probability from odds
    f["implied_prob"] = 1.0 / f["odds"] if f["odds"] > 1 else 0.5

    # Odds bucket
    f["odds_high"] = 1 if f["odds"] > 5 else 0
    f["odds_low"] = 1 if f["odds"] < 1.5 else 0

    # Late entry
    f["late_entry"] = 1 if f["minuto"] > 65 else 0
    f["early_entry"] = 1 if f["minuto"] < 40 else 0

    features.append(f)
    labels.append(1 if b["won"] else 0)
    bet_info.append(b)

# Convert to arrays
feature_names = sorted(features[0].keys())
X = np.array([[f[k] for k in feature_names] for f in features])
y = np.array(labels)

print(f"\nFeatures: {len(feature_names)}")
print(f"  {', '.join(feature_names)}")
print(f"\nClass balance: {sum(y)}/{len(y)} wins ({sum(y)/len(y)*100:.1f}%)")

# ============================================================
# 2. CORRELATION ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("2. CORRELACION FEATURE -> RESULTADO (point-biserial)")
print("=" * 70)

correlations = []
for i, name in enumerate(feature_names):
    col = X[:, i]
    # Only compute if there's variance
    if np.std(col) > 0:
        # Point-biserial correlation
        mean_win = np.mean(col[y == 1])
        mean_loss = np.mean(col[y == 0])
        n1 = sum(y == 1)
        n0 = sum(y == 0)
        n = len(y)
        pooled_std = np.std(col)
        r = (mean_win - mean_loss) / pooled_std * np.sqrt(n1 * n0 / n**2)
        correlations.append((name, r, mean_win, mean_loss))

correlations.sort(key=lambda x: abs(x[1]), reverse=True)
print(f"\n{'Feature':<20s} {'Corr':>8s} {'Mean(Win)':>10s} {'Mean(Loss)':>10s} {'Direction'}")
print("-" * 70)
for name, r, mw, ml in correlations:
    direction = "WINS higher" if r > 0 else "LOSSES higher"
    marker = " ***" if abs(r) > 0.15 else " *" if abs(r) > 0.10 else ""
    print(f"  {name:<20s} {r:+8.3f} {mw:10.2f} {ml:10.2f}  {direction}{marker}")

# ============================================================
# 3. SIMPLE DECISION TREE
# ============================================================
print("\n" + "=" * 70)
print("3. DECISION TREE (max_depth=3, interpretable)")
print("=" * 70)

try:
    from sklearn.tree import DecisionTreeClassifier, export_text
    from sklearn.model_selection import cross_val_score, LeaveOneOut, StratifiedKFold
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    # Decision tree
    dt = DecisionTreeClassifier(max_depth=3, min_samples_leaf=5, random_state=42)

    # Cross-validation (stratified 5-fold)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    scores = cross_val_score(dt, X, y, cv=cv, scoring='accuracy')

    print(f"\n5-Fold CV Accuracy: {scores.mean()*100:.1f}% (+/- {scores.std()*100:.1f}%)")
    print(f"Baseline (always predict win): {sum(y)/len(y)*100:.1f}%")
    print(f"ML gain over baseline: {(scores.mean() - sum(y)/len(y))*100:+.1f}pp")

    # Fit on all data to see the tree structure
    dt.fit(X, y)
    tree_text = export_text(dt, feature_names=feature_names, max_depth=3)
    print(f"\nDecision tree rules:")
    print(tree_text)

    # Feature importance
    importances = dt.feature_importances_
    imp_sorted = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
    print("Feature importance (Decision Tree):")
    for name, imp in imp_sorted:
        if imp > 0:
            bar = "#" * int(imp * 50)
            print(f"  {name:<20s} {imp:.3f} {bar}")

    # ============================================================
    # 4. LOGISTIC REGRESSION
    # ============================================================
    print("\n" + "=" * 70)
    print("4. LOGISTIC REGRESSION (regularized)")
    print("=" * 70)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    lr = LogisticRegression(C=0.1, max_iter=1000, random_state=42)
    lr_scores = cross_val_score(lr, X_scaled, y, cv=cv, scoring='accuracy')

    print(f"\n5-Fold CV Accuracy: {lr_scores.mean()*100:.1f}% (+/- {lr_scores.std()*100:.1f}%)")
    print(f"Baseline: {sum(y)/len(y)*100:.1f}%")
    print(f"ML gain: {(lr_scores.mean() - sum(y)/len(y))*100:+.1f}pp")

    # Fit on all data
    lr.fit(X_scaled, y)
    print("\nLogistic Regression coefficients (positive = more likely to win):")
    coefs = sorted(zip(feature_names, lr.coef_[0]), key=lambda x: abs(x[1]), reverse=True)
    for name, coef in coefs:
        if abs(coef) > 0.01:
            direction = "+" if coef > 0 else "-"
            bar = "#" * int(abs(coef) * 10)
            print(f"  {name:<20s} {coef:+.3f} {bar}")

    # ============================================================
    # 5. LEAVE-ONE-OUT CROSS-VALIDATION (most rigorous for small N)
    # ============================================================
    print("\n" + "=" * 70)
    print("5. LEAVE-ONE-OUT CV (mas riguroso para N pequeno)")
    print("=" * 70)

    loo = LeaveOneOut()
    dt_simple = DecisionTreeClassifier(max_depth=2, min_samples_leaf=5, random_state=42)
    loo_scores = cross_val_score(dt_simple, X, y, cv=loo, scoring='accuracy')
    print(f"\nLOO-CV Accuracy (DT depth=2): {loo_scores.mean()*100:.1f}%")

    lr_loo = cross_val_score(lr, X_scaled, y, cv=loo, scoring='accuracy')
    print(f"LOO-CV Accuracy (LogReg):     {lr_loo.mean()*100:.1f}%")
    print(f"Baseline (always win):         {sum(y)/len(y)*100:.1f}%")

    # ============================================================
    # 6. PRACTICAL APPLICATION: SIGNAL QUALITY SCORE
    # ============================================================
    print("\n" + "=" * 70)
    print("6. APLICACION PRACTICA: SCORING DE SENALES")
    print("=" * 70)

    # Use logistic regression probabilities as signal scores
    lr_full = LogisticRegression(C=0.1, max_iter=1000, random_state=42)
    lr_full.fit(X_scaled, y)
    probs = lr_full.predict_proba(X_scaled)[:, 1]

    # Divide into high/medium/low confidence
    high = probs >= 0.75
    medium = (probs >= 0.5) & (probs < 0.75)
    low = probs < 0.5

    print(f"\nHigh confidence (prob >= 0.75): {sum(high)} bets")
    if sum(high) > 0:
        h_wins = sum(y[high])
        h_pl = sum(bet_info[i]["pl"] for i in range(len(bets)) if high[i])
        print(f"  WR: {h_wins/sum(high)*100:.1f}%, P/L: {h_pl:+.2f}")

    print(f"\nMedium confidence (0.5-0.75): {sum(medium)} bets")
    if sum(medium) > 0:
        m_wins = sum(y[medium])
        m_pl = sum(bet_info[i]["pl"] for i in range(len(bets)) if medium[i])
        print(f"  WR: {m_wins/sum(medium)*100:.1f}%, P/L: {m_pl:+.2f}")

    print(f"\nLow confidence (prob < 0.5): {sum(low)} bets")
    if sum(low) > 0:
        l_wins = sum(y[low])
        l_pl = sum(bet_info[i]["pl"] for i in range(len(bets)) if low[i])
        print(f"  WR: {l_wins/sum(low)*100:.1f}%, P/L: {l_pl:+.2f}")

    print("\nDETALLE: Apuestas con BAJA confianza (candidatas a skip):")
    for i in range(len(bets)):
        if low[i]:
            b = bet_info[i]
            result = "WIN" if b["won"] else "LOSS"
            print(f"  [{result:4s}] {b['match'][:35]:35s} | {b['strategy']:20s} | min {b.get('minuto', '?'):>3} | odds {features[i]['odds']:.2f} | prob {probs[i]:.2f} | P/L {b['pl']:+.2f}")

except ImportError:
    print("\n  scikit-learn no esta instalado.")
    print("  Instala con: pip install scikit-learn")
    print("  Solo se muestra el analisis de correlaciones (arriba).")

# ============================================================
# 7. TIME-SERIES FEATURES (match-level)
# ============================================================
print("\n" + "=" * 70)
print("7. ANALISIS DE SERIES TEMPORALES: FEATURES AVANZADAS")
print("=" * 70)
print("  Con ~200 partidos y capturas por minuto, podriamos extraer:")
print("  - Momentum 10min antes del trigger (delta SoT, corners, xG)")
print("  - Volatilidad de odds (std dev en ventana)")
print("  - Ritmo de juego (eventos por minuto)")
print("  - Presion acumulada (dangerous attacks en ultima ventana)")
print("")
print("  Esto requiere cargar los CSVs individuales por partido.")
print("  Con mas features, el modelo podria mejorar significativamente.")

print("\n" + "=" * 70)
print("CONCLUSION")
print("=" * 70)
