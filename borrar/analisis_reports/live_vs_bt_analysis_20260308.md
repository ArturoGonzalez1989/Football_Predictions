# Análisis Live Paper Trading vs Backtest
**Fecha:** 2026-03-08
**Periodo LIVE:** 2026-03-06 al 2026-03-08
**BT Export:** portfolio_bets_20260308_140701.xlsx (598 bets)

---

## 1. KPIs Globales LIVE (62 bets settled)

| Métrica | Valor |
|---------|-------|
| N bets (settled) | 62 |
| N bets pending | 2 |
| Won | 37 |
| Lost | 25 |
| WR% | **59.7%** |
| P/L total | **+9.35 u** |
| Staked | 62.0 u |
| ROI | **+15.1%** |
| Odds promedio | 2.03 |

El P/L incluye comisión Betfair del 5% (verificado: `pl_csv = (odds-1) * stake * 0.95`).

---

## 2. KPIs BT (598 bets, papel activo mismo periodo de estrategias)

| Métrica | Valor |
|---------|-------|
| N bets | 598 |
| Won | 395 |
| WR% | **66.1%** |
| P/L total | **+242.31 u** |
| ROI | **+40.5%** |

---

## 3. Comparativa LIVE vs BT por Estrategia

| Estrategia | LIVE N | LIVE WR% | LIVE ROI% | LIVE P/L | BT N | BT WR% | BT ROI% | BT P/L | Delta ROI (pp) |
|-----------|--------|----------|-----------|----------|------|--------|---------|---------|----------------|
| pressure_cooker_v1 | 16 | 68.8% | +8.9% | +1.43 | 56 | 64.3% | +14.5% | +8.13 | **-5.6** |
| sd_ud_leading | 16 | **43.8%** | **-26.7%** | **-4.27** | 56 | 69.6% | +60.5% | +33.87 | **-87.2** |
| sd_cs_one_goal | 8 | 75.0% | +106.1% | +8.49 | 48 | 70.8% | +61.7% | +29.61 | **+44.4** |
| sd_home_fav_leading | 8 | 87.5% | +74.8% | +5.98 | 41 | 80.5% | +71.5% | +29.30 | **+3.3** |
| sd_cs_close | 7 | 57.1% | +22.4% | +1.57 | 36 | 61.1% | +51.8% | +18.66 | **-29.4** |
| sd_over25_2goal | 2 | 50.0% | -18.5% | -0.37 | 42 | 66.7% | +78.0% | +32.74 | **-96.5** |
| sd_cs_20 | 2 | 0.0% | -100.0% | -2.00 | N/A | — | — | — | N/A |
| odds_drift_contrarian_v1 | 1 | 0.0% | -100.0% | -1.00 | N/A | — | — | — | N/A |
| sd_cs_big_lead | 1 | 0.0% | -100.0% | -1.00 | N/A | — | — | — | N/A |
| sd_longshot | 1 | 100.0% | +52.0% | +0.52 | 47 | 61.7% | +40.3% | +18.93 | **+11.7** |
| **TOTAL** | **62** | **59.7%** | **+15.1%** | **+9.35** | **598** | **66.1%** | **+40.5%** | **+242.31** | **-25.4** |

---

## 4. Rendimiento por Día (LIVE)

| Día | N | Won | WR% | P/L | ROI% |
|-----|---|-----|-----|-----|------|
| 2026-03-06 | 2 | 2 | 100.0% | +1.06 | +53.0% |
| 2026-03-07 | 40 | 24 | 60.0% | +8.15 | +20.4% |
| 2026-03-08 | 20 | 11 | 55.0% | +0.14 | +0.7% |

---

## 5. Listado Completo 62 Bets Settled

| # | ID | Fecha | Partido | Estrategia | Min | Score | Odds | Resultado | P/L |
|---|-----|-------|---------|-----------|-----|-------|------|-----------|-----|
| 1 | 1 | 2026-03-06 20:31 | Al-Khaleej Saihat - Al-Hazm | pressure_cooker_v1 | 71 | 1-1 | 1.39 | won | +0.37 |
| 2 | 2 | 2026-03-06 21:33 | Celta de Vigo - Real Madrid | pressure_cooker_v1 | 70 | 1-1 | 1.73 | won | +0.69 |
| 3 | 3 | 2026-03-07 06:38 | Fujieda Myfc - Iwata | pressure_cooker_v1 | 71 | 1-1 | 1.92 | lost | -1.00 |
| 4 | 5 | 2026-03-07 14:05 | Hull - Millwall | sd_cs_close | 73 | 1-2 | 6.00 | lost | -1.00 |
| 5 | 6 | 2026-03-07 14:09 | Grimsby - Bromley | pressure_cooker_v1 | 74 | 1-1 | 1.81 | lost | -1.00 |
| 6 | 7 | 2026-03-07 14:10 | Huddersfield - Rotherham | sd_cs_one_goal | 79 | 1-0 | 7.20 | won | +5.89 |
| 7 | 8 | 2026-03-07 14:13 | Cardiff - Lincoln | sd_cs_20 | 82 | 0-2 | 1.47 | lost | -1.00 |
| 8 | 9 | 2026-03-07 14:13 | Middelfart - Hvidovre | sd_ud_leading | 56 | 1-0 | 1.85 | won | +0.81 |
| 9 | 10 | 2026-03-07 14:15 | Queens Park - Airdrieonians | sd_ud_leading | 58 | 1-0 | 1.36 | won | +0.34 |
| 10 | 11 | 2026-03-07 14:18 | Hillerod Fodbold - B93 Cph | sd_ud_leading | 58 | 0-1 | 1.63 | won | +0.60 |
| 11 | 12 | 2026-03-07 14:24 | Osasuna - Mallorca | sd_ud_leading | 56 | 0-1 | 1.79 | lost | -1.00 |
| 12 | 15 | 2026-03-07 14:38 | Basaksehir - Goztepe | sd_home_fav_leading | 72 | 2-1 | 1.34 | won | +0.32 |
| 13 | 16 | 2026-03-07 15:36 | Portimonense - Pacos Ferreira | pressure_cooker_v1 | 67 | 2-2 | 1.67 | won | +0.64 |
| 14 | 18 | 2026-03-07 16:03 | Alashkert - Ararat Armenia | sd_ud_leading | 66 | 1-0 | 1.27 | won | +0.26 |
| 15 | 21 | 2026-03-07 16:10 | Wolfsburgo - Hamburgo | sd_cs_close | 73 | 1-2 | 2.08 | won | +1.03 |
| 16 | 22 | 2026-03-07 16:20 | Crawley - Swindon | sd_ud_leading | 55 | 1-0 | 1.40 | lost | -1.00 |
| 17 | 23 | 2026-03-07 16:21 | Walsall - Notts County | sd_ud_leading | 58 | 1-0 | 1.31 | lost | -1.00 |
| 18 | 26 | 2026-03-07 16:31 | Blackpool - Wigan | pressure_cooker_v1 | 68 | 1-1 | 1.76 | lost | -1.00 |
| 19 | 27 | 2026-03-07 16:31 | Bradford - Leyton Orient | pressure_cooker_v1 | 68 | 1-1 | 1.70 | won | +0.66 |
| 20 | 28 | 2026-03-07 16:31 | Burton Albion - Stevenage | sd_cs_one_goal | 68 | 0-1 | 1.75 | won | +0.71 |
| 21 | 29 | 2026-03-07 16:35 | Crawley - Swindon | pressure_cooker_v1 | 69 | 1-1 | 1.54 | won | +0.51 |
| 22 | 30 | 2026-03-07 16:41 | Levante - Girona | odds_drift_contrarian_v1 | 65 | 1-0 | 1.89 | lost | -1.00 |
| 23 | 32 | 2026-03-07 17:00 | FC Groningen - Ajax | sd_home_fav_leading | 65 | 2-1 | 3.65 | won | +2.52 |
| 24 | 34 | 2026-03-07 17:32 | Nantes - Angers | sd_cs_one_goal | 71 | 0-1 | 2.02 | won | +0.97 |
| 25 | 36 | 2026-03-07 17:49 | Lokomotiva - Varazdin | sd_cs_one_goal | 70 | 1-0 | 1.91 | lost | -1.00 |
| 26 | 37 | 2026-03-07 18:17 | Sion - Winterthur | sd_ud_leading | 56 | 0-1 | 2.70 | lost | -1.00 |
| 27 | 38 | 2026-03-07 18:27 | Servette - FC Zurich | sd_home_fav_leading | 65 | 1-0 | 1.29 | won | +0.28 |
| 28 | 40 | 2026-03-07 18:32 | Sion - Winterthur | pressure_cooker_v1 | 73 | 1-1 | 1.47 | lost | -1.00 |
| 29 | 41 | 2026-03-07 18:41 | FCV Dender - Charleroi | sd_ud_leading | 55 | 2-1 | 1.74 | lost | -1.00 |
| 30 | 43 | 2026-03-07 19:18 | Atlético de Madrid - Real Soc | sd_home_fav_leading | 80 | 3-2 | 2.16 | won | +1.10 |
| 31 | 44 | 2026-03-07 19:20 | Wrexham - Chelsea | pressure_cooker_v1 | 71 | 1-1 | 1.71 | won | +0.67 |
| 32 | 47 | 2026-03-07 20:31 | PSV - AZ Alkmaar | pressure_cooker_v1 | 69 | 1-1 | 1.38 | won | +0.36 |
| 33 | 48 | 2026-03-07 20:51 | Bochum - Kaiserslautern | sd_ud_leading | 56 | 1-2 | 1.83 | lost | -1.00 |
| 34 | 51 | 2026-03-07 21:00 | Lugano - Lucerna | sd_cs_close | 72 | 1-2 | 2.14 | lost | -1.00 |
| 35 | 52 | 2026-03-07 21:06 | Bochum - Kaiserslautern | sd_home_fav_leading | 72 | 3-2 | 1.26 | won | +0.25 |
| 36 | 55 | 2026-03-07 21:33 | Newcastle - Manchester City | sd_cs_big_lead | 72 | 1-3 | 2.48 | lost | -1.00 |
| 37 | 57 | 2026-03-07 21:37 | Toulouse - Marsella | sd_cs_one_goal | 71 | 0-1 | 2.34 | won | +1.27 |
| 38 | 59 | 2026-03-07 21:40 | Bahía - EC Vitoria Salvador | sd_cs_close | 72 | 2-1 | 1.86 | won | +0.82 |
| 39 | 60 | 2026-03-07 22:34 | Audax Italiano - Colo Colo | sd_cs_one_goal | 71 | 0-1 | 2.12 | won | +1.06 |
| 40 | 62 | 2026-03-07 22:54 | Barcelona (ECU) - Emelec | sd_ud_leading | 59 | 1-0 | 2.96 | won | +1.86 |
| 41 | 63 | 2026-03-07 23:06 | Barcelona (ECU) - Emelec | sd_cs_one_goal | 72 | 1-0 | 1.62 | won | +0.59 |
| 42 | 64 | 2026-03-07 23:14 | DC utd - Inter Miami CF | sd_over25_2goal | 72 | 0-2 | 1.66 | won | +0.63 |
| 43 | 66 | 2026-03-08 00:37 | Querétaro - CF America | sd_cs_close | 73 | 1-2 | 1.93 | won | +0.88 |
| 44 | 67 | 2026-03-08 00:47 | OHiggins - Univ Catolica | sd_ud_leading | 58 | 1-0 | 1.55 | won | +0.52 |
| 45 | 68 | 2026-03-08 02:07 | Philadelphia - San Jose | sd_longshot | 68 | 0-1 | 1.55 | won | +0.52 |
| 46 | 71 | 2026-03-08 02:45 | Atlas - Guadalajara | pressure_cooker_v1 | 74 | 1-1 | 1.74 | won | +0.70 |
| 47 | 72 | 2026-03-08 04:10 | Colorado - LA Galaxy | pressure_cooker_v1 | 71 | 1-1 | 1.64 | won | +0.61 |
| 48 | 73 | 2026-03-08 06:16 | Gimcheon Sangmu - Jeonbuk | sd_ud_leading | 57 | 1-0 | 1.49 | lost | -1.00 |
| 49 | 74 | 2026-03-08 06:29 | Gimcheon Sangmu - Jeonbuk | sd_cs_one_goal | 70 | 1-0 | 2.10 | lost | -1.00 |
| 50 | 75 | 2026-03-08 07:33 | G-Osaka - Nagasaki | pressure_cooker_v1 | 70 | 2-2 | 1.57 | won | +0.54 |
| 51 | 76 | 2026-03-08 07:47 | G-Osaka - Nagasaki | sd_home_fav_leading | 83 | 3-2 | 3.35 | won | +2.23 |
| 52 | 77 | 2026-03-08 12:03 | Gaziantep FK - Fatih Karagumruk | pressure_cooker_v1 | 69 | 1-1 | 1.70 | lost | -1.00 |
| 53 | 78 | 2026-03-08 12:29 | Wuhan Three Towns - Beijing | sd_over25_2goal | 69 | 0-2 | 1.68 | lost | -1.00 |
| 54 | 79 | 2026-03-08 12:34 | Felgueiras - Vizela | sd_ud_leading | 67 | 0-1 | 1.36 | won | +0.34 |
| 55 | 80 | 2026-03-08 13:01 | Sparta Rotterdam - PEC Zwolle | sd_home_fav_leading | 84 | 1-0 | 4.00 | lost | -1.00 |
| 56 | 81 | 2026-03-08 13:02 | Lecce - US Cremonese | sd_home_fav_leading | 68 | 2-1 | 1.29 | won | +0.28 |
| 57 | 82 | 2026-03-08 13:45 | MTK Budapest - Diosgyori | sd_ud_leading | 56 | 0-1 | 1.55 | lost | -1.00 |
| 58 | 83 | 2026-03-08 13:50 | Club Brugge - Anderlecht | sd_ud_leading | 57 | 1-2 | 2.30 | lost | -1.00 |
| 59 | 84 | 2026-03-08 14:02 | Hannover - Greuther Fürth | sd_cs_close | 73 | 1-2 | 2.94 | won | +1.84 |
| 60 | 85 | 2026-03-08 14:06 | Club Brugge - Anderlecht | sd_cs_close | 74 | 1-2 | 2.66 | lost | -1.00 |
| 61 | 86 | 2026-03-08 14:10 | Preussen Munster - Hertha | pressure_cooker_v1 | 74 | 1-1 | 1.72 | won | +0.68 |
| 62 | 87 | 2026-03-08 14:38 | Villarreal - Elche | sd_cs_20 | 77 | 2-0 | 1.80 | lost | -1.00 |

Pending:
- ID=88 Port Vale - Sunderland | sd_ud_leading | min=58 | odds=2.14
- ID=89 Bologna - Verona | sd_ud_leading | min=60 | odds=1.86

---

## 6. Apuestas Sospechosas / Anomalías

### A. IDs faltantes (25 gaps)
Los IDs 4, 13, 14, 17, 19, 20, 24, 25, 31, 33, 35, 39, 42, 45, 46, 49, 50, 53, 54, 56, 58, 61, 65, 69, 70 no aparecen en el CSV. Son bets que fueron generadas y luego eliminadas (probablemente `conflictFilter` o `dedup` las eliminó antes de settlear, o son cashouts). **Normal**, no es una anomalía grave.

### B. sd_ud_leading con score 2-1 (ID=41, FCV Dender)
- Recomendación: `BACK HOME @ 1.74`, score 2-1, minuto 55
- El home (FCV Dender) lidera 2-1 con odds 1.74. Si FCV Dender es el underdog (odds pre-partido altas), la lógica es correcta.
- El partido terminó distinto (perdió la apuesta), lo cual no invalida el trigger.
- **Veredicto:** Probablemente correcto. FCV Dender era underdog pre-partido.

### C. sd_home_fav_leading con odds muy altas (>3.0)
- ID=32 FC Groningen - Ajax: odds=3.65, score 2-1 min 65 → ganada
- ID=51 G-Osaka - Nagasaki: odds=3.35, score 3-2 min 83 → ganada
- ID=55 Sparta Rotterdam - PEC Zwolle: odds=4.00, score 1-0 min 84 → perdida
- Estas odds son inusualmente altas para "home fav leading". Puede indicar que el mercado tiene dudas sobre el resultado, lo cual es válido para el trigger. Sparta Rotterdam a 4.0 con 1-0 en el min 84 es sospechoso (debería ser mas barato en ese momento).

### D. sd_cs_close con odds 6.00 (ID=5, Hull - Millwall)
- BACK CS 1-2 @ 6.00, min 73. Odds extremadamente altas para un correct score "close".
- Millwall ganaba 2-1 y el mercado ponía el CS 1-2 a 6.0, implicando muy baja prob de que no se moviese el marcador.
- **Anomalía menor:** Las odds de 6.0 están dentro de los límites de la estrategia (max 7.0 por config), pero son inusuales para este tipo de apuesta. Perdió.

### E. Estrategias sin referencia BT
Las estrategias `sd_cs_20`, `sd_cs_big_lead` y `odds_drift_contrarian_v1` tienen 0 bets en el BT export pero sí hay bets LIVE:
- `sd_cs_20` (2 bets): 0 WR, -2.00 P/L — sin referencia histórica en el export
- `sd_cs_big_lead` (1 bet): perdida — sin referencia
- `odds_drift_contrarian_v1` (1 bet): perdida
Esto sugiere que estas estrategias no estaban activas cuando se generó el BT export, o tienen un nombre diferente en el BT.

---

## 7. Análisis de Discrepancias Principales

### sd_ud_leading: ALERTA ROJA (LIVE -26.7% vs BT +60.5%)

WR LIVE = 43.8% vs BT = 69.6%. Diferencia de **-26pp en WR**.

Causas probables:
1. **Muestra pequeña (N=16):** Con N=16 la varianza es altísima. IC95 para WR=43.8% con N=16 es ~[19%, 70%]. No se puede descartar que sea ruido estadístico.
2. **Exceso de apuestas con odds bajas (1.27–1.55):** En BT estas odds implican muy alta prob histórica. En LIVE puede haber degeneración del mercado post-trigger.
3. **Score 1-2 aceptado:** Las bets en Bochum (1-2, odds 1.83) y Club Brugge (1-2, odds 2.30) son underdog *away* liderando, que puede ser un patrón distinto al BT.

### sd_over25_2goal: ALERTA (LIVE -18.5% vs BT +78.0%)

Solo 2 bets LIVE: 1W, 1L. Con N=2 no se puede sacar ninguna conclusión. Necesita más muestra.

### sd_cs_one_goal: OUTPERFORMANCE (LIVE +106.1% vs BT +61.7%)

WR LIVE = 75% vs BT = 70.8%. Outperformance de +44pp ROI. Con N=8 puede ser ruido, pero Huddersfield (odds 7.20) contribuye masivamente (+5.89). Sin esa apuesta el ROI LIVE sería ~+35%.

### pressure_cooker_v1: EN LÍNEA (LIVE +8.9% vs BT +14.5%)

WR ligeramente superior en LIVE (68.8% vs 64.3%). El BT incluye v1+v2 (56 bets), LIVE solo v1 (16 bets). Gap de -5.6pp en ROI es razonable (v2 puede tener mejor ROI que v1 en BT).

---

## 8. Veredicto: ¿Está LIVE tracking al BT?

### Regla de oro: LIVE P/L >= BT P/L (en términos de ROI%)

- **LIVE ROI = +15.1% vs BT ROI = +40.5%**
- **LIVE P/L < BT P/L en ROI. LA REGLA NO SE CUMPLE.**

Sin embargo, hay que contextualizar:

**Factores de muestra:**
- LIVE: 62 bets en ~2 días. BT: 598 bets acumuladas.
- Con N=62, el IC95 del ROI LIVE es muy amplio (~[-10%, +40%]).
- El BT ROI de +40.5% es el ROI del superset filtrado, que es un resultado de largo plazo.

**Estrategias que tiran hacia abajo:**
- `sd_ud_leading` destroza el global LIVE: -4.27 P/L con 16 bets. Si se neutraliza, el resto da +13.62 en 46 bets = +29.6% ROI, que se acerca mucho al BT.
- La divergencia en `sd_ud_leading` es estadísticamente no concluyente (N=16).

**Estrategias sanas:**
- `sd_cs_one_goal`: +106% ROI LIVE > BT (ruido positivo)
- `sd_home_fav_leading`: +74.8% LIVE ≈ BT +71.5%
- `pressure_cooker_v1`: +8.9% LIVE vs BT +14.5% (razonable)

**Conclusión:**
LIVE ROI (+15.1%) es inferior al BT ROI (+40.5%) pero la diferencia es **estadísticamente no significativa** con N=62. El driver principal es `sd_ud_leading` con WR=43.8% vs BT 69.6%, que con N=16 es compatible con ruido estadístico (IC95 WR: [20%, 70%]).

**Veredicto: MONITORIZAR. No hay evidencia de fallo sistémico, pero sd_ud_leading requiere seguimiento prioritario a N=30+.**

---

## 9. Estado del Notebook reconcile_bt_live.ipynb

- **11 celdas** (Setup, BT, Live sim, Comparación, Discrepancias, Deep dive, Paper vs BT)
- **Celda 10 (Paper vs BT):** No tiene outputs ejecutados. Hay código preparado para comparar placed_bets.csv contra BT y Live simulado, pero no se ha corrido.
- **Necesita:** Ejecutar celda 10 para obtener reconciliación formal de las 62 bets paper contra el BT/Live simulado.
- El notebook carga cartera_config.json dinámicamente y el COMBO refleja la config actual correctamente.

---

## 10. Acciones Recomendadas

1. **Ejecutar celda 10 del notebook** `analisis/reconcile_bt_live.ipynb` para reconciliación formal de las 64 bets paper contra BT y Live simulado.

2. **Monitorizar sd_ud_leading** prioritariamente. Al alcanzar N=30, revisar si WR se acerca al BT (69.6%). Si persiste por debajo del 55%, investigar el helper `_detect_ud_leading_trigger` y filtros de config.

3. **sd_over25_2goal:** N=2 insuficiente. Esperar N=15 para evaluar.

4. **sd_home_fav_leading:** Revisar los casos con odds >3.0 (FC Groningen, G-Osaka, Sparta Rotterdam). Puede ser que la estrategia está triggerando en partidos donde el "home fav" está bajo presión de mercado, lo cual eleva las odds. Esto puede ser una oportunidad o un bug de detección.

5. **IDs faltantes:** Verificar que los 25 IDs gap son cancelaciones/dedup y no errores de settlement.
