# Guía Rápida - Sistema de Scheduling

## 🚀 Inicio Rápido (3 pasos)

### 1. Edita `games.csv`
```csv
Game,url,fecha_hora_inicio
Partido 1,https://www.betfair.es/...,2026-02-10 20:00
Partido 2,https://www.betfair.es/...,2026-02-11 18:30
```

### 2. Inicia el script
```bash
python main.py
```

### 3. Deja que trabaje solo
El script automáticamente:
- Espera hasta 10 min antes del partido
- Abre la tab y empieza a capturar
- Cierra la tab 150 min después del inicio

---

## 📋 Comandos Principales

### Uso Básico
```bash
# Con valores por defecto
python main.py

# Personalizado
python main.py --ventana-antes 15 --ventana-despues 180
```

### Parámetros Útiles
```bash
--ventana-antes 10        # Minutos antes del inicio (default: 10)
--ventana-despues 150     # Minutos después del inicio (default: 150)
--reload-interval 5       # Revisar CSV cada N ciclos (default: 5)
--ciclo 60                # Segundos entre capturas (default: 60)
--login-wait 30           # Segundos para login (default: 60)
```

### Ejemplos Reales
```bash
# Partidos cortos (90 min + descuento)
python main.py --ventana-antes 10 --ventana-despues 120

# Partidos largos (con prórroga posible)
python main.py --ventana-antes 15 --ventana-despues 180

# Máxima cobertura
python main.py --ventana-antes 30 --ventana-despues 240
```

---

## 📅 Formato de Fechas

### Formato 1 (Recomendado)
```
YYYY-MM-DD HH:MM
2026-02-10 20:00
```

### Formato 2
```
DD/MM/YYYY HH:MM
10/02/2026 20:00
```

### Ejemplos
```csv
Game,url,fecha_hora_inicio
Partido mediodía,https://...,2026-02-10 12:00
Partido tarde,https://...,2026-02-10 17:30
Partido noche,https://...,2026-02-10 21:00
Madrugada,https://...,11/02/2026 00:30
```

---

## 🔍 Cómo Funciona

### Timeline de un Partido (inicio: 20:00)
```
19:50 → Script abre tab (10 min antes)
20:00 → Partido empieza
20:00-22:30 → Script captura datos cada 60s
22:30 → Script cierra tab (150 min después)
```

### Ventana de Tracking
```
[----------------150 minutos---------------]
         ↑                                  ↑
      Apertura                           Cierre
     (10 min antes)                 (150 min después)
```

---

## 📊 Logs Útiles

### Al Iniciar
```
📅 MODO SCHEDULING ACTIVADO
   Total en CSV: 5 partidos
   ✓ Partidos activos ahora: 1
   ⏰ Partidos futuros: 4
   ✅ Partidos finalizados: 0

📋 Próximos partidos a trackear:
      Partido 1 (en 45 min)
      Partido 2 (en 120 min)
```

### Durante Ejecución
```
🔄 Revisando games.csv para detectar cambios...
➕ Abriendo 1 nuevos partidos...
   - Real Madrid - Barcelona (inicia en 8 min)
✓ Tabs actualizadas: 1 partidos activos
```

```
🗑️ Cerrando 1 partidos finalizados...
   - Cerrando: Man City - Liverpool
✓ Tabs actualizadas: 0 partidos activos
```

---

## 🎯 Casos de Uso

### 1. Jornada de Liga (10 partidos)
```csv
Game,url,fecha_hora_inicio
Partido 1,https://...,2026-02-10 12:00
Partido 2,https://...,2026-02-10 14:00
Partido 3,https://...,2026-02-10 16:00
Partido 4,https://...,2026-02-10 18:30
Partido 5,https://...,2026-02-10 21:00
Partido 6,https://...,2026-02-11 12:00
Partido 7,https://...,2026-02-11 14:00
Partido 8,https://...,2026-02-11 16:00
Partido 9,https://...,2026-02-11 18:30
Partido 10,https://...,2026-02-11 21:00
```
**Resultado**: 20 horas de tracking automático (2 días)

### 2. Champions League (8 partidos)
```csv
Game,url,fecha_hora_inicio
Partido 1 - Martes,https://...,2026-02-10 18:45
Partido 2 - Martes,https://...,2026-02-10 21:00
Partido 3 - Martes,https://...,2026-02-10 21:00
Partido 4 - Martes,https://...,2026-02-10 21:00
Partido 5 - Miércoles,https://...,2026-02-11 18:45
Partido 6 - Miércoles,https://...,2026-02-11 21:00
Partido 7 - Miércoles,https://...,2026-02-11 21:00
Partido 8 - Miércoles,https://...,2026-02-11 21:00
```
**Resultado**: 2 noches de Champions capturadas

### 3. Semana Completa
```csv
Game,url,fecha_hora_inicio
Lunes,https://...,2026-02-10 20:00
Martes,https://...,2026-02-11 20:00
Miércoles,https://...,2026-02-12 18:30
Jueves Ch1,https://...,2026-02-13 21:00
Jueves Ch2,https://...,2026-02-13 21:00
Viernes,https://...,2026-02-14 20:30
Sábado 1,https://...,2026-02-15 12:00
Sábado 2,https://...,2026-02-15 14:30
Sábado 3,https://...,2026-02-15 17:00
Sábado 4,https://...,2026-02-15 19:30
Domingo 1,https://...,2026-02-16 12:00
Domingo 2,https://...,2026-02-16 14:30
Domingo 3,https://...,2026-02-16 17:00
Domingo 4,https://...,2026-02-16 19:30
```
**Resultado**: 7 días completos de datos

---

## 🔧 Troubleshooting Rápido

| Problema | Solución |
|----------|----------|
| No abre tabs | Normal si partidos son futuros. Revisa log "Próximos partidos" |
| Cierra muy pronto | Aumenta `--ventana-despues 180` |
| Abre muy tarde | Aumenta `--ventana-antes 15` |
| No detecta nuevos partidos | Espera 5 ciclos (~5 min) o reduce `--reload-interval` |
| Formato fecha inválido | Usa `YYYY-MM-DD HH:MM` |

---

## ✅ Checklist Antes de Iniciar

- [ ] games.csv tiene partidos con fechas/horas correctas
- [ ] Fechas están en formato válido (`YYYY-MM-DD HH:MM`)
- [ ] Horas son locales (tu zona horaria)
- [ ] Chrome profile tiene login guardado (si usas perfil)
- [ ] Ventanas de tracking son adecuadas (default: 10 min antes, 150 min después)

---

## 📞 Archivos de Ayuda

- **`SCHEDULING.md`**: Documentación completa y detallada
- **`RESUMEN_SCHEDULING.md`**: Resumen de cambios implementados
- **`games_ejemplo.csv`**: Ejemplo de CSV con scheduling
- **`test_scheduling.py`**: Tests para verificar funcionamiento

---

## 💡 Tips Pro

1. **Añade partidos con anticipación**: Puedes añadir partidos de toda la semana el lunes
2. **Edita sobre la marcha**: Si ves un partido interesante, añádelo al CSV
3. **Mezcla modos**: Algunos partidos con horario, otros sin horario (legacy)
4. **Ajusta ventanas**: Partidos importantes → ventana más amplia
5. **Monitorea logs**: Revisa `logs/scraper_*.log` para ver qué pasa

---

## 🎉 Ventajas

| Antes | Ahora |
|-------|-------|
| Manual | Automático |
| Supervisión constante | Desatendido |
| 1-2 partidos máximo | Semanas completas |
| Reiniciar para añadir | Editar CSV y listo |
| Captura ineficiente | Solo cuando hay partido |

**¡El sistema ideal para captura masiva de datos!** ⚽📊
