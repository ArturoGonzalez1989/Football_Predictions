# ML Exploration — Furbo Betting Signals

> Fecha: 2026-02-16 | N=89 bets (59W / 30L) | ~190 partidos con datos por minuto

## 1. Resumen ejecutivo

Con ~90 apuestas y datos por minuto de ~190 partidos, exploramos si ML puede mejorar la seleccion de senales. Resultado: **las features de serie temporal (momentum, volatilidad de odds, ritmo de juego) aportan el 67.8% de la importancia del modelo** y mejoran el AUC-ROC de 0.80 a 0.87. Sin embargo, con N=89 el accuracy real (LOO) solo mejora ~3pp. El principal valor hoy es el **scoring de confianza**: separar bets de alta calidad (94% WR) de las de baja calidad (16% WR).

## 2. Features utilizadas

### Base (10 features)
| Feature | Descripcion |
|---------|-------------|
| `minuto` | Minuto de entrada |
| `odds` | Cuota back al trigger |
| `implied_prob` | 1/odds |
| `is_draw/xg/drift/clustering/pressure` | Estrategia (one-hot) |
| `hour` | Hora UTC del partido |
| `is_weekend` | Sabado o domingo |

### Time-series (23 features, ventana de 10 min pre-trigger)
| Feature | Descripcion | Correlacion |
|---------|-------------|-------------|
| `ts_goals_total` | Goles marcados al trigger | **+0.376** |
| `ts_is_drawing` | Empate al trigger (0/1) | **-0.265** |
| `ts_delta_sot_total` | Incremento SoT en ventana | **+0.258** |
| `ts_sot_asymmetry` | Diferencia SoT local-visitante en ventana | **+0.215** |
| `ts_sot_per_min` | Ritmo de SoT en ventana | **+0.202** |
| `ts_delta_shots_total` | Incremento tiros en ventana | +0.181 |
| `ts_delta_xg_total` | Incremento xG en ventana | +0.180 |
| `ts_sot_at_trigger` | SoT total al trigger | +0.171 |
| `ts_odds_o25_trend` | Tendencia odds Over 2.5 en ventana | **-0.167** |
| `ts_xg_asymmetry` | Diferencia xG local-visitante en ventana | +0.163 |
| `ts_shots_per_min` | Ritmo de tiros en ventana | +0.162 |
| `ts_xg_at_trigger` | xG total al trigger | +0.160 |
| `ts_da_asymmetry` | Asimetria dangerous attacks | -0.126 |
| `ts_poss_diff` | Diferencia posesion al trigger | -0.109 |
| `ts_odds_draw_volatility` | Std dev de odds draw en ventana | -0.077 |
| `ts_odds_draw_trend_pct` | % cambio odds draw en ventana | +0.008 |
| `ts_odds_draw_range` | Max-min odds draw en ventana | -0.045 |
| `ts_odds_o25_volatility` | Std dev odds Over 2.5 en ventana | +0.010 |
| `ts_da_per_min` | Ritmo dangerous attacks | -0.058 |
| `ts_da_at_trigger` | Dangerous attacks total al trigger | +0.009 |
| `ts_delta_da_total` | Incremento dangerous attacks en ventana | -0.069 |
| `ts_delta_corners_total` | Incremento corners en ventana | +0.117 |
| `ts_delta_bc_total` | Incremento big chances en ventana | 0.000 |

## 3. Modelos evaluados

| Modelo | Base 5CV | Full 5CV | Base LOO | Full LOO |
|--------|----------|----------|----------|----------|
| LogReg (C=0.1) | 74.0% | 74.1% | **74.2%** | 68.5% |
| LogReg (C=1.0) | 74.1% | 72.9% | 71.9% | **69.7%** |
| DecTree (d=3) | 60.6% | 67.3% | 60.7% | 58.4% |
| RandomForest | 64.0% | 62.9% | 66.3% | 66.3% |
| GradientBoost | 66.3% | **70.7%** | **70.8%** | 67.4% |
| **Baseline** | 66.3% | 66.3% | 66.3% | 66.3% |

- LOO (Leave-One-Out) es la metrica mas fiable con N pequeno
- LogReg base (C=0.1) es el mejor en LOO: 74.2%
- Las TS features no mejoran LOO (overfitting con 33 features / 89 muestras)
- Si mejoran 5-fold CV en GBM (+4.3pp) y DT (+6.7pp)

## 4. AUC-ROC y Brier Score (calidad del ranking)

| Metrica | Base | Enriquecido | Delta |
|---------|------|-------------|-------|
| AUC-ROC | 0.8017 | **0.8684** | **+0.067** |
| Brier Score | 0.168 | **0.146** | -0.022 |

El modelo enriquecido **rankea mucho mejor** (separa wins de losses), aunque no clasifique mas bets correctamente en LOO. Esto es clave para scoring de confianza.

## 5. Feature importance (Random Forest)

```
Feature                          Importancia  Tipo
odds                                0.084     BASE
ts_goals_total                      0.082     TS
is_draw                             0.077     BASE
ts_poss_diff                        0.063     TS
ts_odds_draw_trend_pct              0.060     TS
implied_prob                        0.060     BASE
ts_delta_xg_total                   0.059     TS
ts_odds_draw_volatility             0.051     TS
ts_xg_asymmetry                     0.045     TS
ts_xg_at_trigger                    0.045     TS
minuto                              0.040     BASE
ts_sot_at_trigger                   0.037     TS

Total: Base 32.2% | Time-series 67.8%
```

## 6. Signal quality scoring

| Confianza | Bets | WR | P/L |
|-----------|------|----|-----|
| HIGH (>=0.75) | 34 | **94.1%** | +312.31 |
| MEDIUM (0.50-0.75) | 36 | 66.7% | +419.76 |
| LOW (<0.50) | 19 | **15.8%** | -74.50 |

- 16 de las 19 bets "low" son `back_draw_00`
- Si se filtrasen las LOW, se ahorrarian ~74.50 EUR (perdiendo solo 3 wins de +85.50)
- **NOTA**: Esto es in-sample, el beneficio real sera menor

## 7. Patrones por estrategia (trayectorias pre-bet)

### Back Draw 0-0 (W:7 / L:14)
- Wins: **menos volatilidad de odds** (0.10 vs 0.22), menos delta SoT/xG
- Partidos "dormidos" al min 30 = mejor. Si hay mucha accion, el 0-0 no aguanta
- **Senal**: odds draw estables + poca actividad ofensiva

### xG Underperformance (W:9 / L:3)
- Wins: **mucho mas delta xG** (+978%) y volatilidad odds draw (+729%)
- Cuando hay xG real generandose en la ventana = la "underperformance" es real
- **Senal**: xG subiendo activamente + mercado moviendose

### Odds Drift (W:22 / L:9)
- Wins: **+94% mas delta SoT**, **+91% mas SoT asimetrica**, -59% delta DA
- El drift funciona cuando un equipo esta presionando (SoT) pero no con ataques genericos
- **Senal**: tiros a puerta concentrados en un equipo + movimiento de mercado

### Goal Clustering (W:20 / L:4)
- Wins: **-89% volatilidad odds draw**, +18500% delta DA
- Odds estables post-gol = el mercado "acepta" que vendran mas goles
- **Senal**: dangerous attacks altos + odds no reaccionando excesivamente

## 8. Limitaciones actuales

1. **N=89 es insuficiente** para modelos complejos (RF, GBM overfittean)
2. **33 features / 89 muestras** = ratio peligroso. Feature selection necesaria con mas datos
3. **In-sample scoring es optimista**: el 94% WR de HIGH no se replicara out-of-sample
4. **LOO accuracy real**: 69.7-74.2% vs baseline 66.3% = ganancia modesta (+3-8pp)
5. **Sesgo temporal**: no hay walk-forward validation (todos los datos usados mezclados)

## 9. Que hacer cuando tengamos mas datos

### Con ~300 bets
- [ ] Feature selection: eliminar features con poca varianza o alta colinealidad
- [ ] Walk-forward validation: entrenar con los primeros 200, testear en los ultimos 100
- [ ] Probar modelos por estrategia (uno para draw, otro para drift, etc.)

### Con ~500 bets
- [ ] Gradient Boosting deberia empezar a generalizar bien
- [ ] Scoring en vivo: integrar modelo en `detect_betting_signals()` con confianza HIGH/MED/LOW
- [ ] Calibracion de probabilidades para Kelly criterion basado en ML

### Con ~1000+ bets
- [ ] Neural network simple (2-3 capas) podria capturar interacciones no lineales
- [ ] Ensemble de modelos por estrategia
- [ ] Features de segundo orden: momentum del momentum, aceleracion de volatilidad
- [ ] Analisis de regimenes de mercado (horarios, ligas, temporadas)

## 10. Scripts

| Script | Que hace |
|--------|----------|
| `ml_exploration.py` | ML basico con features puntuales (10 features) |
| `ml_timeseries.py` | ML enriquecido con time-series (33 features) |
| `analyze_drawdowns.py` | Analisis de drawdowns y patrones de perdida |

## 11. Dependencias

```
pip install scikit-learn numpy
```

## 12. Reproduccion

```bash
cd c:/Users/agonz/OneDrive/Documents/Proyectos/Furbo
python ml_exploration.py    # Base ML
python ml_timeseries.py     # Time-series ML
```
