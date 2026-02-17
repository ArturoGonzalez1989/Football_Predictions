# Guía de Versiones de Estrategias

**Fecha de última actualización:** 16 Febrero 2026
**Estado:** Configuración óptima aplicada

---

## 🎯 CONFIGURACIÓN ACTUAL RECOMENDADA

```yaml
Empate (Draw):           V1.5  ✅ (75% WR, 65% ROI)
xG Underperformance:     V3    ⭐ (100% WR, 41.5% ROI) - CAMBIADO HOY
Odds Drift Contrarian:   V1    ✅ (66.7% WR, 142.3% ROI)
Goal Clustering:         V2    ✅ (75% WR, 72.7% ROI)
Pressure Cooker:         V1    🔬 (81.2% WR, 81.9% ROI - testing)
```

---

## 📋 TODAS LAS VERSIONES DISPONIBLES

### 1️⃣ Back Empate 0-0

| Versión | Condiciones | WR | ROI | Sample | Status |
|---------|------------|-----|-----|--------|--------|
| **V1** | min 30+, 0-0 | 50% | 12.5% | 8 | ❌ Deprecated |
| **V1.5** | V1 + xG<0.6 + poss_diff<25% | **75%** | **65%** | 4 | ⭐ **Recomendada** |
| **V2** | V1 + xG<0.5 + poss_diff<20% + shots<8 | 60% | 42.8% | 5 | ✅ Activa |
| **V2r** | V1 + xG<0.6 + poss_diff<20% + shots<8 | 57.1% | 50.2% | 7 | ✅ Activa |

**Recomendación:** V1.5 tiene mejor WR (75%) pero solo 4 triggers. V2r es más balanceada.

---

### 2️⃣ xG Underperformance - Back Over

| Versión | Condiciones | WR | ROI | Sample | Status | Notas Críticas |
|---------|------------|-----|-----|--------|--------|----------------|
| **V1 (base)** | Perdiendo + xG≥0.5 + min≥15 | 80% | 34.9% | 15 | ⚠️ **PELIGROSA** | ❌ Sin límite tiempo - permite min 82-96 |
| **V2** | V1 + SoT≥2 | 72.7% | 24.7% | 11 | ✅ Activa | ⚠️ Aún permite entradas tardías |
| **V3** | V2 + **min<70** | **100%** | **41.5%** | 6 | ⭐ **RECOMENDADA** | ✅ Bloquea entradas tardías |

**Cambio aplicado hoy:** V2 → V3 (default)

**Impacto esperado:** +20 EUR ahorrados hoy si V3 hubiera estado activa (bloqueó min 82 y 96)

---

### 3️⃣ Odds Drift Contrarian - Back Ganador

| Versión | Condiciones | WR | ROI | Sample | Status |
|---------|------------|-----|-----|--------|--------|
| **V1** | Ganando 1-0 + drift≥25% | **66.7%** | **142.3%** | 27 | ⭐ **Recomendada** |
| **V2** | Ganando (dif≥2) + drift≥25% | 75% | 165.4% | 12 | 🔬 Research |
| **V3** | Drift≥100% (mega-drift) | ? | ? | ? | 🔬 Research |
| **V4** | 2ª parte + odds≤5 | ? | ? | ? | 🔬 Research |
| **V5** | Odds≤5 (sin filtro tiempo) | ? | ? | ? | 🔬 Research |

**Recomendación:** V1 tiene muestra sólida (27 bets) y ROI excelente. Mantener.

---

### 4️⃣ Goal Clustering - Back Over

| Versión | Condiciones | WR | ROI | Sample | Status | Notas |
|---------|------------|-----|-----|--------|--------|-------|
| **V1** | Tras gol + min≥15 | 65.4% | 45.2% | 52 | ❌ Deprecated | Muchos falsos positivos |
| **V2** | V1 + SoT_max≥3 | **75%** | **72.7%** | 44 | ⭐ **Recomendada** | Funcionando bien |
| **V3** | V2 + **min<75** | **78.6%** | **85.3%** | 28 | ✅ **Corregida hoy** | Bug arreglado (era min<60) |

**Bug corregido:** V3 usaba `min<60` pero docs decían `min<75`. Ahora corregido.

**Recomendación:** V2 por ahora. Testear V3 después de validar xG V3.

---

### 5️⃣ Pressure Cooker - Back Over en Empates

| Versión | Condiciones | WR | ROI | Sample | Status |
|---------|------------|-----|-----|--------|--------|
| **V0** | Empate any (incl 0-0) + min 65-75 | 63.2% | -12.5% | 19 | ❌ Deprecated |
| **V1** | Empate 1-1+ (excl 0-0) + min 65-75 | **81.2%** | **81.9%** | 16 | 🔬 **Testing** |

**Status:** EN PRUEBA - muestra pequeña pero muy prometedora. Necesita 50+ bets para validar.

---

## 🔧 CAMBIOS REALIZADOS HOY (16 Feb 2026)

### 1. xG Underperformance: V2 → V3 (default)
```diff
- versions = {"xg": "v2"}
+ versions = {"xg": "v3"}
```

**Archivos modificados:**
- `betfair_scraper/dashboard/backend/utils/csv_reader.py` (línea 1881, 2378)
- `betfair_scraper/dashboard/frontend/src/components/BettingSignalsView.tsx` (línea 13)

**Razón:** V3 bloquea entradas tardías (min≥70) que causaron -20 EUR hoy.

---

### 2. Goal Clustering V3: Bug corregido (min<60 → min<75)
```diff
- if clustering_ver == "v3" and minuto >= 60:
+ if clustering_ver == "v3" and minuto >= 75:

- cl_thresholds["minute"] = "< 60"
+ cl_thresholds["minute"] = "< 75"
```

**Archivos modificados:**
- `betfair_scraper/dashboard/backend/utils/csv_reader.py` (líneas 2259, 2269, 2548)

**Razón:** Docs históricas indicaban min<75, no min<60. Ahora consistente.

---

## 📊 RENDIMIENTO ESPERADO CON NUEVA CONFIG

### Cartera Validación (Fase 1 - Stake fijo 10 EUR):
```
Empate V1.5:      4 bets/mes  → +26 EUR/mes
xG Underp. V3:    6 bets/mes  → +25 EUR/mes  (vs +27 con V2 pero más seguro)
Odds Drift V1:    27 bets/mes → +384 EUR/mes
Goal Clust. V2:   44 bets/mes → +320 EUR/mes
─────────────────────────────────────────────
TOTAL:            81 bets/mes → +755 EUR/mes (ROI: +93%)
```

### Cartera Growth (Fase 2 - Half-Kelly con 500 EUR inicial):
```
Bankroll esperado mes 1: 500 → ~850 EUR
Bankroll esperado mes 3: 500 → ~1400 EUR
Bankroll esperado mes 6: 500 → ~2800 EUR
```

---

## ⚠️ REGLAS DE GESTIÓN DE RIESGO

### Stop-Loss Global:
- ❌ Si bankroll cae 50% desde inicial → PAUSAR 1 semana

### Stop-Loss por Estrategia:
- ❌ Si WR <40% con >20 bets → DESACTIVAR estrategia

### Límites Diarios:
- ❌ Max 5 apuestas/día (evitar tilt)
- ❌ Max 5% bankroll por apuesta (aunque Half-Kelly recomiende más)

### Señales de Alerta:
- ⚠️ 3 días consecutivos con pérdidas → Revisar
- ⚠️ Racha de 10+ pérdidas seguidas → Pausar
- ⚠️ WR rolling <50% durante 30 bets → Re-analizar

---

## 🎯 PRÓXIMOS PASOS

### ✅ Inmediato (HOY):
1. Reiniciar dashboard para aplicar cambios
2. Verificar que xG Underp. muestra "V3" en interfaz
3. Monitorear próximas señales xG para confirmar que bloquea min≥70

### 📅 Esta Semana:
1. Acumular 5-10 apuestas con xG V3
2. Validar que no hay entradas tardías (min>70)
3. Comparar WR de V3 vs histórico V2

### 📅 Próximas 2-4 Semanas:
1. Si xG V3 funciona bien → Considerar Goal Clustering V3
2. Revisar si Odds Drift V2 (dif≥2) genera mejores señales
3. Validar Pressure Cooker V1 con más datos

---

## 📚 REFERENCIAS

- Docs xG Underperformance: `estrategias/xg_underperformance.md`
- Docs Goal Clustering: `estrategias/goal_clustering.md`
- Docs Odds Drift: `estrategias/odds_drift_contrarian.md`
- Docs Pressure Cooker: `estrategias/pressure_cooker.md`
- Cartera completa: `estrategias/cartera_final.md`
- CSVs generados: `strategy_portfolio.csv`, `optimal_portfolio.csv`, `version_comparison.csv`

---

## 🔄 HISTORIAL DE CAMBIOS

| Fecha | Cambio | Razón |
|-------|--------|-------|
| 2026-02-16 | xG V2→V3 default | Prevenir entradas tardías (min≥70) |
| 2026-02-16 | Goal Clust V3 bug fix | Corregir min<60 → min<75 |
| 2026-02-16 | Documentación completa | Guía de versiones y recomendaciones |
