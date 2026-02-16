# Resumen de Mejoras al Sistema de Señales

## Lo que se ha implementado ✅

1. **Nueva sección "Señales"** en primera posición del dashboard
2. **Detección automática** de las 3 estrategias de la cartera en tiempo real
3. **Actualización cada 10 segundos** de las oportunidades activas

## Lo que acabas de pedir (en proceso) 🔄

### Información adicional que se está añadiendo:

1. **Cuota Mínima Recomendada**
   - Calculada basándose en el WR histórico de cada estrategia
   - Fórmula: `min_odds = (1 / win_rate) * 1.10` (break-even + 10% margen)
   - Ejemplo: Back Empate V2r (WR 57.1%) → cuota mínima = 1.93

2. **Valor Esperado (EV)**
   - Ganancia/pérdida esperada por apuesta de 10 EUR
   - Considera comisión del 5% de Betfair
   - Fórmula: `EV = (WR × profit_if_win) - ((1-WR) × loss_if_lose)`

3. **Indicador Visual de Cuota Favorable**
   - Verde: Cuota actual ≥ cuota mínima → APOSTAR
   - Rojo: Cuota actual < cuota mínima → NO APOSTAR (EV negativo)

4. **Metadata de Estrategia**
   - WR Histórico: 57.1% / 72.7% / 66.7%
   - ROI Histórico: +50.2% / +24.7% / +142.3%
   - Tamaño de muestra: 7 / 11 / 27 apuestas

5. **Resumen Ejecutivo**
   - Recomendación clara GO/NO-GO basada en cuota actual vs mínima
   - Descripción breve del setup (por qué se disparó la señal)
   - Tiempo desde que se cumplieron las condiciones

## Ejemplo de Señal Mejorada

```
🟢 BACK EMPATE 0-0 (V2r) - Sparta Rotterdam vs NEC

├─ RESUMEN: ✅ APOSTAR (Cuota favorable)
│
├─ CUOTA ACTUAL: 6.80
├─ CUOTA MÍNIMA: 1.93 → ✅ OK (252% de margen)
├─ VALOR ESPERADO: +18.45 EUR (por apuesta de 10 EUR)
│
├─ PROBABILIDAD (histórica): 57.1%
├─ ROI (histórico): +50.2%
├─ Muestra: 7 apuestas
│
├─ CONDICIONES ACTUALES:
│  ├─ xG Total: 0.42 (✅ < 0.6)
│  ├─ Dif. Posesión: 8% (✅ < 20%)
│  └─ Tiros Totales: 4 (✅ < 8)
│
└─ Setup: Partido trabado sin goles ni ocasiones
```

## Próximos pasos para completar

1. **Backend**: Añadir metadata a las otras 2 estrategias (xG Underperf, Odds Drift)
2. **Frontend**: Actualizar tipos TypeScript e interfaz
3. **UI**: Diseñar tarjetas de señal más claras con semáforo GO/NO-GO
4. **Alertas**: Opcional - añadir notificaciones sonoras/visuales cuando aparece señal favorable

## Para probar el sistema

1. Arranca el backend:
```bash
cd betfair_scraper/dashboard/backend
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

2. Arranca el frontend:
```bash
cd betfair_scraper/dashboard/frontend
npm run dev
```

3. Abre http://localhost:5173 y ve a la sección "Señales"

---

**¿Continúo implementando la versión mejorada completa o prefieres probar primero la versión básica que ya está funcionando?**
