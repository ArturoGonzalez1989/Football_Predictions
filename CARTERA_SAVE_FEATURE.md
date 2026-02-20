# Feature: Guardar/Reset Filtros de Cartera

## ✅ Implementado

Añadida funcionalidad para **guardar** y **restablecer** todos los selectores de la sección **Insights → Strategies → Cartera**.

---

## 🎯 Funcionalidad

### 1. **Botón "Guardar"** (Verde)
- Guarda todos los filtros actuales en `localStorage`
- Persiste entre sesiones del navegador
- Ubicación: Junto al botón "Descargar CSV"

### 2. **Botón "Reset"** (Naranja)
- Restablece todos los filtros a valores por defecto
- Borra la configuración guardada de `localStorage`
- Ubicación: Entre "Guardar" y "Descargar CSV"

### 3. **Auto-carga al iniciar**
- Al abrir la página, carga automáticamente los filtros guardados
- Si no hay filtros guardados, usa valores por defecto

---

## 🔧 Valores Guardados

La configuración guardada incluye **todos** los selectores:

### Estrategias y Versiones:
- ✅ Back Empate (drawVer): v1, v15, v2, v2r
- ✅ xG Underperformance (xgVer): base, v2, v3
- ✅ Odds Drift (driftVer): v1, v2, v3, v4, v5
- ✅ Goal Clustering (clusteringVer): v2, v3, v4
- ✅ Pressure Cooker (pressureVer): v1
- ✅ Tarde Asia (tardeAsiaVer): off, v1, v2
- ✅ Momentum xG (momentumXGVer): off, v1, v2

### Configuración:
- ✅ Modo Bankroll (brMode): fixed, kelly_quarter, kelly_half, kelly_full
- ✅ Preset activo (activePreset): null, "max_roi", "max_wr", "balanced", "conservative", "aggressive"
- ✅ Filtro de Riesgo (riskFilter): "all", "no_risk", "medium_risk", "high_risk"

### Ajustes Realistas:
- ✅ Realista activado (realistic): true/false
- ✅ Deduplicar (adjDedup): true/false
- ✅ Cuotas máximas (adjMaxOdds): 6.0 por defecto
- ✅ Cuotas mínimas (adjMinOdds): 1.15 por defecto
- ✅ Minuto mínimo Drift (adjDriftMinMin): 15 por defecto
- ✅ Slippage % (adjSlippage): 2 por defecto

---

## 📋 Cambios en el Código

### Archivo: `InsightsView.tsx`

#### 1. Constantes y funciones auxiliares (Línea ~1600)
```typescript
const STORAGE_KEY = "cartera_filters"

// Load saved state from localStorage or use defaults
const loadSavedState = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      return JSON.parse(saved)
    }
  } catch (e) {
    console.error("Error loading saved filters:", e)
  }
  return null
}

const savedState = loadSavedState()
```

#### 2. Estados con valores guardados (Línea ~1617)
```typescript
const [drawVer, setDrawVer] = useState<DrawVersion>(savedState?.drawVer || "v1")
const [xgVer, setXgVer] = useState<XGCarteraVersion>(savedState?.xgVer || "base")
// ... todos los demás estados cargados desde savedState
```

#### 3. Función Guardar (Línea ~1635)
```typescript
const saveFilters = () => {
  const state = {
    drawVer,
    xgVer,
    driftVer,
    clusteringVer,
    pressureVer,
    tardeAsiaVer,
    momentumXGVer,
    brMode,
    activePreset,
    realistic,
    adjDedup,
    adjMaxOdds,
    adjMinOdds,
    adjDriftMinMin,
    adjSlippage,
    riskFilter,
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}
```

#### 4. Función Reset (Línea ~1655)
```typescript
const resetFilters = () => {
  setDrawVer("v1")
  setXgVer("base")
  setDriftVer("v1")
  setClusteringVer("v2")
  setPressureVer("v1")
  setTardeAsiaVer("off")
  setMomentumXGVer("off")
  setBrMode("fixed")
  setActivePreset(null)
  setRealistic(false)
  setAdjDedup(true)
  setAdjMaxOdds(6.0)
  setAdjMinOdds(1.15)
  setAdjDriftMinMin(15)
  setAdjSlippage(2)
  setRiskFilter("all")
  localStorage.removeItem(STORAGE_KEY)
}
```

#### 5. Botones UI (Línea ~1815)
```tsx
<button
  type="button"
  onClick={saveFilters}
  className="px-3 py-1.5 bg-green-500/10 hover:bg-green-500/20 border border-green-500/30 text-green-400 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5"
  title="Guardar configuración actual de filtros"
>
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
  </svg>
  Guardar
</button>

<button
  type="button"
  onClick={resetFilters}
  className="px-3 py-1.5 bg-orange-500/10 hover:bg-orange-500/20 border border-orange-500/30 text-orange-400 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5"
  title="Restablecer todos los filtros a valores por defecto"
>
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
  </svg>
  Reset
</button>
```

---

## 🎨 Diseño Visual

### Botón Guardar:
- 🟢 Color: Verde (`green-400`)
- ✅ Icono: Checkmark
- 📍 Tooltip: "Guardar configuración actual de filtros"

### Botón Reset:
- 🟠 Color: Naranja (`orange-400`)
- 🔄 Icono: Refresh/Reset circular
- 📍 Tooltip: "Restablecer todos los filtros a valores por defecto"

### Ubicación:
```
[Contador apuestas] [Guardar] [Reset] [Descargar CSV]
```

---

## 🔍 Uso

### Guardar Configuración:
1. Ajusta todos los selectores como desees
2. Haz clic en **"Guardar"** (botón verde)
3. La configuración se guarda en tu navegador

### Cargar Configuración:
1. Abre la página Insights → Strategies → Cartera
2. Los filtros se cargan **automáticamente** desde localStorage
3. Si no hay configuración guardada, se usan valores por defecto

### Restablecer:
1. Haz clic en **"Reset"** (botón naranja)
2. Todos los filtros vuelven a valores por defecto:
   - Back Empate: v1
   - xG Underperformance: base
   - Odds Drift: v1
   - Goal Clustering: v2
   - Pressure Cooker: v1
   - Tarde Asia: off
   - Momentum xG: off
   - Bankroll: fixed
   - Riesgo: all
   - Realista: off
3. La configuración guardada se **elimina** de localStorage

---

## 💾 Almacenamiento

**Ubicación:** `localStorage` del navegador
**Key:** `"cartera_filters"`
**Formato:** JSON string

**Ejemplo guardado:**
```json
{
  "drawVer": "v15",
  "xgVer": "v3",
  "driftVer": "v1",
  "clusteringVer": "v2",
  "pressureVer": "v1",
  "tardeAsiaVer": "off",
  "momentumXGVer": "off",
  "brMode": "kelly_quarter",
  "activePreset": null,
  "realistic": false,
  "adjDedup": true,
  "adjMaxOdds": 6.0,
  "adjMinOdds": 1.15,
  "adjDriftMinMin": 15,
  "adjSlippage": 2,
  "riskFilter": "no_risk"
}
```

---

## ⚠️ Notas

- **Persistencia por navegador**: La configuración se guarda en localStorage del navegador. Si cambias de navegador o usas modo incógnito, no se mantendrá.
- **Seguridad**: localStorage es accesible por JavaScript del mismo dominio. No guardes información sensible.
- **Límite**: localStorage tiene un límite de ~5-10MB dependiendo del navegador. Esta configuración usa ~500 bytes.
- **Compatibilidad**: Funciona en todos los navegadores modernos (Chrome, Firefox, Safari, Edge).

---

## 🚀 Testing

1. Abre Insights → Strategies → Cartera
2. Cambia varios selectores (ej: Back Empate → v15, xG → v3, Bankroll → kelly_quarter)
3. Haz clic en **"Guardar"**
4. Recarga la página (F5)
5. Verifica que los selectores mantienen los valores guardados
6. Haz clic en **"Reset"**
7. Verifica que todos los selectores vuelven a valores por defecto

---

## 📁 Archivo Modificado

- ✅ `betfair_scraper/dashboard/frontend/src/components/InsightsView.tsx`
  - Línea ~1600: Funciones loadSavedState, saveFilters, resetFilters
  - Línea ~1617: Estados con valores guardados
  - Línea ~1815: Botones UI
