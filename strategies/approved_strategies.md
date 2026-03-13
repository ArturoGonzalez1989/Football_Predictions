# Estrategias Aprobadas — Referencia Consolidada
**Actualizado:** 2026-03-13 | **Dataset:** 1210 partidos | **BT ref:** bt_results_20260313_164153.csv

> Referencia rápida de todas las estrategias en producción.
> Detalles de implementación: `csv_reader.py` (triggers), `cartera_config.json` (params), `sd_strategy_tracker.md` (historial de investigación).

---

## Estrategias activas (enabled: true)

| Config key | H# | Mercado | Tesis del edge (1 línea) | N | WR% | ROI% | IC95 |
|---|---|---|---|---|---|---|---|
| `ud_leading` | H59 | BACK Match Winner | El mercado ancla al favorito pre-partido; el underdog que lidera tiene mayor probabilidad real de ganar de la que el mercado reconoce | 217 | 65.4 | 79.1 | 58.9-71.4 |
| `lay_over45_v3` | — | LAY Over 4.5 | Con ≤1 gol a mitad de partido, llegar a 5+ goles es estadísticamente casi imposible pero el mercado lo sobreestima | 73 | 98.6 | 80.0 | 92.6-99.8 |
| `draw_22` | H68 | BACK Draw | En 2-2 tardío ambos equipos están exhaustos y se vuelven más conservadores; el mercado sobreestima el 5º gol | 20 | 70.0 | 99.1 | 48.1-85.5 |
| `cs_one_goal` | H53 | BACK CS 1-0/0-1 | El mercado CS distribuye probabilidad entre decenas de resultados, subestimando sistemáticamente el marcador actual en partidos de un gol tardíos | 88 | 62.5 | 61.9 | 52.1-71.9 |
| `longshot` | — | BACK Match Winner | Las cuotas in-play del outsider liderando retienen sesgo al favorito pre-partido; la ventaja real es mayor de lo priceado | 96 | 66.7 | 48.9 | 56.8-75.3 |
| `away_fav_leading` | H67 | BACK Match Winner | El mercado sobreestima la remontada local incluso cuando el visitante favorito ya va ganando; doble sesgo: home advantage + narrative comeback | 87 | 88.5 | 33.6 | 80.1-93.6 |
| `draw_11` | H58 | BACK Draw | 1-1 tardío crea equilibrio de stalemate: ambos equipos han puntuado pero se vuelven cautelosos; el mercado confunde "ambos atacan" con "seguirán atacando" | 136 | 52.9 | 29.8 | 44.6-61.1 |
| `goal_clustering` | — | BACK Over | Tras un gol reciente con SoT activo, la probabilidad de otro gol inmediato es alta por inercia táctica; el mercado no actualiza suficientemente rápido | 57 | 94.7 | 40.5 | 85.6-98.2 |
| `home_fav_leading` | H70 | BACK Match Winner | Favorito local liderando: doble ventaja (calidad + ventaja de campo) que el mercado subestima anclado en "cualquier cosa puede pasar" | 217 | 82.5 | 25.2 | 76.9-87.0 |
| `draw_equalizer` | H62 | BACK Draw | Tras igualar el underdog, el favorito ha perdido su plan táctico y el mercado sigue priceando su calidad pre-partido; la inercia del empate está subestimada | 21 | 47.6 | 23.8 | 28.3-67.6 |
| `under35_3goals` | H66 | BACK Under 3.5 | Con 3 goles y xG bajo, los goles fueron por sobrerendimiento; la regresión a la media hace improbable el 4º pero el mercado sobreestima la "inercia goleadora" | 206 | 50.5 | 16.7 | 43.7-57.2 |
| `draw_xg_conv` | — | BACK Draw | Cuando los xG convergen en empate, el mercado no ha incorporado esta señal estadística latente | 100 | 50.0 | 15.5 | 40.4-59.6 |
| `over25_2goal` | — | BACK Over 2.5 | Equipo liderando 2+ goles con SoT activo indica partido abierto; el equipo perdedor empujará y el ganador puede añadir más | 47 | 57.4 | 21.2 | 43.3-70.5 |
| `under45_3goals` | H71 | BACK Under 4.5 | Mismo patrón que Under 3.5: 3 goles con xG bajo = sobrerendimiento; el 4º gol está sobrepriceado, el Under 4.5 es versión más conservadora | 55 | 92.7 | 13.5 | 82.7-97.1 |
| `poss_extreme` | — | BACK Over 0.5 | Posesión extremadamente desigual en 0-0 → el equipo dominante acabará marcando; el mercado Over 0.5 no descuenta suficientemente el dominio estadístico | 68 | 89.7 | 13.7 | 80.2-94.9 |
| `under35_late` | — | BACK Under 3.5 | Con exactamente 3 goles y xG bajo tardío, el juego está en fase de control; 4º gol muy improbable | 24 | 62.5 | 8.6 | 42.7-78.8 |
| `pressure_cooker` | — | BACK Over | Empate con goles (1-1+) entre min 65-75: ambos equipos en modo ataque, probabilidad de gol adicional mayor de lo priceado | 117 | 65.0 | 8.6 | 56.0-73.0 |
| `xg` (base) | — | BACK Over | Equipo perdedor con xG alto = sobrerendimiento del equipo ganador; reversión estadística pendiente | 68 | 79.4 | 5.6 | 68.4-87.3 |

---

## Estrategias aprobadas con enabled: false (no pasan quality gates actuales o excluidas por portfolio optimizer)

| Config key | H# | Mercado | Razón disabled | Mejor BT individual |
|---|---|---|---|---|
| `cs_close` | H49 | BACK CS 2-1/1-2 | No pasa quality gates con dataset actual (N insuficiente en ventana de minutos óptima) | N≈60, ROI≈40% (dataset parcial) |
| `cs_20` | H79 | BACK CS 2-0/0-2 | No pasa quality gates actuales | N=90, ROI=46.2% (dataset anterior) |
| `cs_big_lead` | H81 | BACK CS 3-0/0-3/3-1/1-3 | No pasa quality gates actuales | N=79, ROI=58.3% (dataset anterior) |
| `cs_11` | H77 | BACK CS 1-1 | No pasa quality gates actuales | N=102, ROI=24.1% (dataset anterior) |
| `over25_2goals` | H39 | BACK Over 2.5 | No pasa quality gates actuales | N≈50, ROI marginal |
| `cs_00` | — | BACK CS 0-0 | No pasa quality gates (ROI insuficiente) | — |
| `draw` (back_draw_00) | — | BACK Draw 0-0 | No pasa IC95 gate | — |
| `drift` (odds_drift) | — | BACK Match Winner | Excluido por portfolio optimizer (reduce ROI del conjunto) | — |
| `momentum_xg` | — | BACK Match Winner | Params hardcodeados, excluido por optimizer | — |
| `tarde_asia` | — | BACK Over 2.5 | Detección por liga, no pasa quality gates | — |

---

## Grupos de deduplicación de mercado

Cuando varios triggers disparan en el mismo partido y mercado, solo se coloca **1 apuesta** (la de menor minuto):

| Grupo | Estrategias |
|-------|-------------|
| `draw` | `draw_11`, `draw_xg_conv`, `draw_equalizer`, `draw_22` |
| `under_3.5` | `under35_late`, `under35_3goals` |
| `over_2.5` | `over25_2goal`, `goal_clustering`, `pressure_cooker` |

---

## Stats del portfolio activo (BT, 2026-03-13)

```
N=1697 bets | WR=69.4% | ROI=35.1% | P/L=£596.25 | IC95=[67.1%-71.5%]
18 estrategias activas sobre 1210 partidos históricos
```
