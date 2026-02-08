#!/usr/bin/env python3
"""
analyze.py - Análisis de datos de cuotas Betfair capturados
=============================================================
Carga los CSV generados por main.py, calcula métricas de varianza,
probabilidades implícitas, y entrena un modelo RandomForest básico.

Uso:
    python analyze.py
    python analyze.py --csv data/unificado.csv
    python analyze.py --csv data/partido_12345.csv --plot
    python analyze.py --csv data/unificado.csv --modelo
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Backend no interactivo (compatible sin display)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# ── Carga de datos ───────────────────────────────────────────────────────────

def cargar_csv(ruta: str) -> pd.DataFrame:
    """Carga un CSV de cuotas y prepara los tipos de datos."""
    df = pd.read_csv(ruta, encoding="utf-8")

    # Convertir timestamp
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], errors="coerce")

    # Columnas numéricas de cuotas
    cols_numericas = [
        "back_home", "lay_home", "back_draw", "lay_draw",
        "back_away", "lay_away",
        "back_over25", "lay_over25", "back_under25", "lay_under25",
        "volumen_matched", "minuto",
    ]
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Eliminar filas sin timestamp
    df = df.dropna(subset=["timestamp_utc"])

    # Ordenar por tiempo
    df = df.sort_values(["tab_id", "timestamp_utc"]).reset_index(drop=True)

    print(f"Cargados {len(df)} registros de {df['tab_id'].nunique()} partido(s).")
    return df


# ── Probabilidades implícitas ────────────────────────────────────────────────

def calcular_probabilidades_implicitas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula probabilidades implícitas a partir de cuotas back.
    P(evento) = 1 / cuota_back
    También calcula el overround (margen del mercado).
    """
    for col_back, col_prob in [
        ("back_home", "prob_home"),
        ("back_draw", "prob_draw"),
        ("back_away", "prob_away"),
        ("back_over25", "prob_over25"),
        ("back_under25", "prob_under25"),
    ]:
        if col_back in df.columns:
            df[col_prob] = 1.0 / df[col_back]

    # Overround (suma de probabilidades implícitas Match Odds)
    prob_cols = ["prob_home", "prob_draw", "prob_away"]
    if all(c in df.columns for c in prob_cols):
        df["overround_mo"] = df[prob_cols].sum(axis=1)

    # Probabilidades normalizadas (sin overround)
    if "overround_mo" in df.columns:
        for col in prob_cols:
            if col in df.columns:
                df[f"{col}_norm"] = df[col] / df["overround_mo"]

    return df


# ── Log returns y volatilidad ────────────────────────────────────────────────

def calcular_log_returns(df: pd.DataFrame, columnas: list = None) -> pd.DataFrame:
    """
    Calcula log-returns para columnas de cuotas.
    log_return = ln(precio_t / precio_{t-1})
    """
    if columnas is None:
        columnas = ["back_home", "lay_home", "back_draw", "lay_draw",
                     "back_away", "lay_away"]

    for col in columnas:
        if col not in df.columns:
            continue
        # Calcular por partido
        df[f"logret_{col}"] = df.groupby("tab_id")[col].transform(
            lambda x: np.log(x / x.shift(1))
        )

    return df


def calcular_volatilidad_rolling(
    df: pd.DataFrame, ventana: int = 5, columnas: list = None
) -> pd.DataFrame:
    """
    Calcula desviación estándar rolling (volatilidad) de los log-returns.
    Ventana por defecto: 5 observaciones (5 minutos con ciclo de 60s).
    """
    if columnas is None:
        columnas = ["back_home", "lay_home", "back_draw", "back_away"]

    for col in columnas:
        logret_col = f"logret_{col}"
        if logret_col not in df.columns:
            continue
        df[f"vol_{col}_{ventana}"] = df.groupby("tab_id")[logret_col].transform(
            lambda x: x.rolling(window=ventana, min_periods=2).std()
        )

    return df


# ── Spread back-lay ──────────────────────────────────────────────────────────

def calcular_spreads(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula spread (diferencia) entre back y lay para cada selección."""
    pares = [
        ("back_home", "lay_home", "spread_home"),
        ("back_draw", "lay_draw", "spread_draw"),
        ("back_away", "lay_away", "spread_away"),
        ("back_over25", "lay_over25", "spread_over25"),
        ("back_under25", "lay_under25", "spread_under25"),
    ]
    for col_back, col_lay, col_spread in pares:
        if col_back in df.columns and col_lay in df.columns:
            df[col_spread] = df[col_lay] - df[col_back]

    return df


# ── Análisis descriptivo ─────────────────────────────────────────────────────

def resumen_partido(df: pd.DataFrame, tab_id: str = None):
    """Imprime un resumen descriptivo de un partido."""
    if tab_id:
        datos = df[df["tab_id"] == tab_id]
    else:
        datos = df

    print("\n" + "=" * 70)
    print("RESUMEN DE DATOS CAPTURADOS")
    print("=" * 70)

    for tid in datos["tab_id"].unique():
        sub = datos[datos["tab_id"] == tid]
        print(f"\nPartido: {tid}")
        if "evento" in sub.columns:
            eventos = sub["evento"].dropna().unique()
            if len(eventos) > 0:
                print(f"  Evento: {eventos[0]}")
        print(f"  Registros: {len(sub)}")
        print(f"  Periodo: {sub['timestamp_utc'].min()} -> {sub['timestamp_utc'].max()}")

        cols_odds = ["back_home", "lay_home", "back_draw", "back_away"]
        for col in cols_odds:
            if col in sub.columns:
                serie = sub[col].dropna()
                if len(serie) > 0:
                    print(f"  {col}: min={serie.min():.2f} max={serie.max():.2f} "
                          f"media={serie.mean():.2f} std={serie.std():.3f}")

        # Varianza de log-returns
        logret_cols = [c for c in sub.columns if c.startswith("logret_")]
        if logret_cols:
            print("  Volatilidad log-returns:")
            for col in logret_cols:
                serie = sub[col].dropna()
                if len(serie) > 0:
                    print(f"    {col}: std={serie.std():.4f}")

    print("=" * 70)


# ── Visualización ────────────────────────────────────────────────────────────

def plot_odds_vs_tiempo(df: pd.DataFrame, output_dir: str = "data"):
    """
    Genera gráficos de cuotas vs tiempo para cada partido.
    Guarda como PNG en el directorio de salida.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for tid in df["tab_id"].unique():
        sub = df[df["tab_id"] == tid].copy()
        if len(sub) < 2:
            continue

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))
        fig.suptitle(f"Evolución de cuotas - Partido {tid}", fontsize=14, fontweight="bold")

        # --- Panel 1: Match Odds Back ---
        ax = axes[0, 0]
        for col, label, color in [
            ("back_home", "Local (Back)", "#2ecc71"),
            ("back_draw", "Empate (Back)", "#f39c12"),
            ("back_away", "Visitante (Back)", "#e74c3c"),
        ]:
            if col in sub.columns:
                serie = sub.dropna(subset=[col])
                if len(serie) > 0:
                    ax.plot(serie["timestamp_utc"], serie[col], label=label,
                            color=color, linewidth=1.5)
        ax.set_title("Match Odds (Back)")
        ax.set_ylabel("Cuota")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # --- Panel 2: Spread back-lay ---
        ax = axes[0, 1]
        for col, label, color in [
            ("spread_home", "Local", "#2ecc71"),
            ("spread_draw", "Empate", "#f39c12"),
            ("spread_away", "Visitante", "#e74c3c"),
        ]:
            if col in sub.columns:
                serie = sub.dropna(subset=[col])
                if len(serie) > 0:
                    ax.plot(serie["timestamp_utc"], serie[col], label=label,
                            color=color, linewidth=1.5)
        ax.set_title("Spread Back-Lay")
        ax.set_ylabel("Spread")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # --- Panel 3: Probabilidades implícitas ---
        ax = axes[1, 0]
        for col, label, color in [
            ("prob_home_norm", "P(Local)", "#2ecc71"),
            ("prob_draw_norm", "P(Empate)", "#f39c12"),
            ("prob_away_norm", "P(Visitante)", "#e74c3c"),
        ]:
            if col in sub.columns:
                serie = sub.dropna(subset=[col])
                if len(serie) > 0:
                    ax.plot(serie["timestamp_utc"], serie[col], label=label,
                            color=color, linewidth=1.5)
        ax.set_title("Probabilidades implícitas (normalizadas)")
        ax.set_ylabel("Probabilidad")
        ax.set_ylim(0, 1)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # --- Panel 4: Volatilidad rolling ---
        ax = axes[1, 1]
        for col, label, color in [
            ("vol_back_home_5", "Vol Local", "#2ecc71"),
            ("vol_back_draw_5", "Vol Empate", "#f39c12"),
            ("vol_back_away_5", "Vol Visitante", "#e74c3c"),
        ]:
            if col in sub.columns:
                serie = sub.dropna(subset=[col])
                if len(serie) > 0:
                    ax.plot(serie["timestamp_utc"], serie[col], label=label,
                            color=color, linewidth=1.5)
        ax.set_title("Volatilidad rolling (ventana=5)")
        ax.set_ylabel("Std log-returns")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)

        # Formato de ejes X
        for ax in axes.flat:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.tick_params(axis="x", rotation=45)

        plt.tight_layout()
        nombre_archivo = output_path / f"plot_{tid}.png"
        plt.savefig(nombre_archivo, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"Gráfico guardado: {nombre_archivo}")


# ── Modelo predictivo básico ─────────────────────────────────────────────────

def entrenar_modelo_rf(df: pd.DataFrame):
    """
    Entrena un RandomForest básico para predecir el siguiente valor de lay_home.
    Esto es un ejemplo didáctico; no usar directamente para trading real.
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import mean_absolute_error, r2_score

    print("\n" + "=" * 70)
    print("MODELO PREDICTIVO - RandomForest (lay_home t+1)")
    print("=" * 70)

    # Preparar features
    feature_cols = [
        "back_home", "lay_home", "back_draw", "lay_draw",
        "back_away", "lay_away",
        "prob_home", "prob_draw", "prob_away",
        "spread_home", "spread_draw", "spread_away",
        "logret_back_home", "logret_lay_home",
        "vol_back_home_5",
        "minuto",
    ]

    # Target: lay_home en t+1
    df_modelo = df.copy()
    df_modelo["target_lay_home_next"] = df_modelo.groupby("tab_id")["lay_home"].shift(-1)

    # Filtrar columnas disponibles
    available_features = [c for c in feature_cols if c in df_modelo.columns]
    if len(available_features) < 3:
        print("Insuficientes features disponibles. Necesitas más datos capturados.")
        return

    # Eliminar NaN
    cols_modelo = available_features + ["target_lay_home_next"]
    df_clean = df_modelo[cols_modelo].dropna()

    if len(df_clean) < 20:
        print(f"Solo {len(df_clean)} registros válidos. Necesitas al menos 20 para entrenar.")
        return

    X = df_clean[available_features].values
    y = df_clean["target_lay_home_next"].values

    print(f"Features: {available_features}")
    print(f"Registros para entrenamiento: {len(X)}")

    # TimeSeriesSplit para respetar orden temporal
    tscv = TimeSeriesSplit(n_splits=min(5, max(2, len(X) // 10)))

    maes = []
    r2s = []

    for fold, (idx_train, idx_test) in enumerate(tscv.split(X)):
        X_train, X_test = X[idx_train], X[idx_test]
        y_train, y_test = y[idx_train], y[idx_test]

        modelo = RandomForestRegressor(
            n_estimators=100,
            max_depth=8,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1,
        )
        modelo.fit(X_train, y_train)

        y_pred = modelo.predict(X_test)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        maes.append(mae)
        r2s.append(r2)
        print(f"  Fold {fold + 1}: MAE={mae:.4f}, R²={r2:.4f}")

    print(f"\nMedias: MAE={np.mean(maes):.4f}, R²={np.mean(r2s):.4f}")

    # Feature importance del último fold
    print("\nImportancia de features:")
    importancias = sorted(
        zip(available_features, modelo.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    )
    for feat, imp in importancias:
        barra = "█" * int(imp * 50)
        print(f"  {feat:25s} {imp:.4f} {barra}")

    print("\nNOTA: Este es un modelo didáctico. Para trading real necesitas:")
    print("  - Más datos (semanas/meses de capturas)")
    print("  - Validación out-of-sample rigurosa")
    print("  - Features adicionales (históricos, forma equipos, etc.)")
    print("  - Gestión de riesgo y bankroll management")
    print("=" * 70)


# ── Generar datos de ejemplo ─────────────────────────────────────────────────

def generar_datos_ejemplo(ruta: str = "data/ejemplo_demo.csv"):
    """Genera un CSV de ejemplo con datos sintéticos para testing."""
    np.random.seed(42)
    n = 90  # 90 minutos de partido

    timestamps = pd.date_range("2025-01-15 20:00:00", periods=n, freq="1min", tz="UTC")

    # Simular cuotas que evolucionan (drift + ruido)
    back_home = 2.5 + np.cumsum(np.random.normal(-0.005, 0.03, n))
    back_home = np.clip(back_home, 1.01, 50)

    back_draw = 3.2 + np.cumsum(np.random.normal(0.002, 0.025, n))
    back_draw = np.clip(back_draw, 1.01, 50)

    back_away = 3.0 + np.cumsum(np.random.normal(0.003, 0.028, n))
    back_away = np.clip(back_away, 1.01, 50)

    # Lay = back + spread aleatorio
    spread = np.random.uniform(0.02, 0.08, n)

    # Gol en minuto 35 -> cambio brusco
    for i in range(35, n):
        back_home[i] -= 0.4
        back_draw[i] += 0.5
        back_away[i] += 0.6
    back_home = np.clip(back_home, 1.01, 50)
    back_draw = np.clip(back_draw, 1.01, 50)
    back_away = np.clip(back_away, 1.01, 50)

    # Over/Under
    back_over25 = 1.8 + np.cumsum(np.random.normal(-0.003, 0.02, n))
    back_over25 = np.clip(back_over25, 1.01, 50)
    back_under25 = 2.1 + np.cumsum(np.random.normal(0.003, 0.02, n))
    back_under25 = np.clip(back_under25, 1.01, 50)

    goles_local = [0] * 35 + [1] * (n - 35)
    goles_visitante = [0] * n

    df = pd.DataFrame({
        "tab_id": "demo_12345",
        "timestamp_utc": timestamps.strftime("%Y-%m-%d %H:%M:%S"),
        "evento": "Real Madrid v Barcelona",
        "minuto": range(1, n + 1),
        "goles_local": goles_local,
        "goles_visitante": goles_visitante,
        "back_home": np.round(back_home, 2),
        "lay_home": np.round(back_home + spread, 2),
        "back_draw": np.round(back_draw, 2),
        "lay_draw": np.round(back_draw + spread, 2),
        "back_away": np.round(back_away, 2),
        "lay_away": np.round(back_away + spread, 2),
        "back_over25": np.round(back_over25, 2),
        "lay_over25": np.round(back_over25 + spread * 0.8, 2),
        "back_under25": np.round(back_under25, 2),
        "lay_under25": np.round(back_under25 + spread * 0.8, 2),
        "volumen_matched": np.random.randint(50000, 500000, n),
        "url": "https://www.betfair.es/exchange/plus/es/futbol/demo",
    })

    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8")
    print(f"Datos de ejemplo generados: {ruta} ({len(df)} filas)")
    return ruta


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Análisis de cuotas Betfair capturadas"
    )
    parser.add_argument(
        "--csv", type=str, default=None,
        help="Ruta al CSV a analizar (default: data/unificado.csv)"
    )
    parser.add_argument(
        "--plot", action="store_true",
        help="Generar gráficos de cuotas vs tiempo"
    )
    parser.add_argument(
        "--modelo", action="store_true",
        help="Entrenar modelo RandomForest predictivo"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Generar datos de ejemplo y ejecutar análisis completo"
    )
    parser.add_argument(
        "--output", type=str, default="data",
        help="Directorio de salida para gráficos (default: data)"
    )
    args = parser.parse_args()

    # Modo demo: generar datos sintéticos
    if args.demo:
        print("Generando datos de ejemplo...")
        ruta_csv = generar_datos_ejemplo(f"{args.output}/ejemplo_demo.csv")
    elif args.csv:
        ruta_csv = args.csv
    else:
        ruta_csv = "data/unificado.csv"

    # Verificar que existe el CSV
    if not Path(ruta_csv).exists():
        print(f"ERROR: No se encuentra {ruta_csv}")
        print("Opciones:")
        print("  1. Ejecuta primero main.py para capturar datos")
        print("  2. Usa --demo para generar datos de ejemplo")
        print("  3. Especifica un CSV con --csv ruta/al/archivo.csv")
        sys.exit(1)

    # Cargar datos
    df = cargar_csv(ruta_csv)

    # Calcular métricas
    print("\nCalculando métricas...")
    df = calcular_probabilidades_implicitas(df)
    df = calcular_spreads(df)
    df = calcular_log_returns(df)
    df = calcular_volatilidad_rolling(df, ventana=5)

    # Resumen
    resumen_partido(df)

    # Guardar CSV enriquecido
    ruta_enriquecido = Path(args.output) / "analisis_enriquecido.csv"
    df.to_csv(ruta_enriquecido, index=False, encoding="utf-8")
    print(f"\nCSV enriquecido guardado: {ruta_enriquecido}")

    # Gráficos
    if args.plot or args.demo:
        print("\nGenerando gráficos...")
        plot_odds_vs_tiempo(df, output_dir=args.output)

    # Modelo
    if args.modelo or args.demo:
        entrenar_modelo_rf(df)

    print("\nAnálisis completado.")


if __name__ == "__main__":
    main()
