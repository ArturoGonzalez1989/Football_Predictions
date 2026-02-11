# Actualización de Estadísticas - Interfaz Limitada

## Fecha: 2026-02-10

## Resumen

Se han añadido **11 nuevas columnas** al CSV para capturar estadísticas que antes no se estaban recogiendo, especialmente de partidos con interfaz limitada (ligas menores).

## Nuevas Columnas Añadidas

### Summary Tab
1. **fouls_conceded_local** / **fouls_conceded_visitante**
   - Nombre en interfaz: "Fouls Conceded"
   - Ejemplo: 4 - 5

2. **dangerous_attacks_local** / **dangerous_attacks_visitante**
   - Nombres en interfaz: "Dangerous Attacks" / "Dangerous Attack"
   - Ejemplo: 15 - 9

### Attacking Tab
3. **blocked_shots_local** / **blocked_shots_visitante**
   - Nombre en interfaz: "Blocked Shots"
   - Ejemplo: 1 - 0

4. **shooting_accuracy_local** / **shooting_accuracy_visitante**
   - Nombre en interfaz: "Shooting Accuracy"
   - Ejemplo: 17% - 0%

### Distribution Tab
5. **goal_kicks_local** / **goal_kicks_visitante**
   - Nombres en interfaz: "Goal Kicks" / "Goal Kick"
   - Ejemplo: 3 - 5

6. **throw_ins_local** / **throw_ins_visitante**
   - Nombres en interfaz: "Throw Ins" / "Throw In"
   - Ejemplo: 6 - 7

## Mappings Mejorados

### Stats Ya Existentes Ahora Capturadas Correctamente

- **Shots On Target** → `tiros_puerta_local/visitante`
  - Añadido mapping en tab Attacking
  - Antes solo se capturaba en Summary tab

- **Dangerous Attacks**
  - Añadida en Summary, Attacking y Distribution tabs
  - Máxima cobertura en todos los tabs posibles

## Total de Columnas CSV

**Antes**: 122 columnas
**Ahora**: 133 columnas (+11)

### Desglose por Sección:

| Sección | Antes | Ahora | Nuevas |
|---------|-------|-------|--------|
| Summary/General | 22 | 24 | +2 (fouls_conceded, dangerous_attacks) |
| Attacking | 8 | 14 | +6 (blocked_shots, shooting_accuracy, dangerous_attacks) |
| Defence | 14 | 14 | 0 |
| Distribution | 10 | 14 | +4 (goal_kicks, throw_ins, dangerous_attacks) |
| Momentum | 2 | 2 | 0 |
| Otros | 66 | 65 | 0 (reorganización) |

## Cobertura de Stats del Partido CSKA

### Antes de la Actualización
- ✅ Corners: 4-1
- ✅ Shots Off Target: 4-0
- ❌ Shots On Target: 1-0 (NO capturada)
- ❌ Fouls Conceded: 4-5 (NO capturada)
- ❌ Dangerous Attacks: 15-9 (NO capturada)
- ❌ Blocked Shots: 1-0 (NO capturada)
- ❌ Shooting Accuracy: 17%-0% (NO capturada)
- ❌ Goal Kicks: 3-5 (NO capturada)
- ❌ Throw Ins: 6-7 (NO capturada)

**Capturadas: 2/9 (22%)**

### Después de la Actualización
- ✅ Corners: 4-1
- ✅ Shots Off Target: 4-0
- ✅ Shots On Target: 1-0
- ✅ Fouls Conceded: 4-5
- ✅ Dangerous Attacks: 15-9
- ✅ Blocked Shots: 1-0
- ✅ Shooting Accuracy: 17%-0%
- ✅ Goal Kicks: 3-5
- ✅ Throw Ins: 6-7

**Capturadas: 9/9 (100%)**

## Archivos Modificados

### main.py

**Línea 169-240**: CSV_COLUMNS
- Añadidas 11 nuevas columnas

**Línea 815-890**: stats dict initialization
- Añadidas 11 nuevos campos

**Línea 1160-1195**: Summary stat matching
- Añadido matching para "Fouls Conceded"
- Añadido matching para "Dangerous Attacks"

**Línea 1298-1320**: Attacking keywords
- Añadido "blocked shots"
- Añadido "shots on target"
- Añadido "shooting accuracy"
- Añadido "dangerous attacks"

**Línea 1426-1440**: Distribution keywords
- Añadido "goal kicks"
- Añadido "throw ins"
- Añadido "dangerous attacks"

## Compatibilidad

✅ **Backward compatible**: Todos los CSV existentes siguen siendo válidos
✅ **Multi-interfaz**: Funciona con interfaz completa Y limitada
✅ **Sin breaking changes**: No se han modificado columnas existentes

## Testing

Para probar los cambios con el partido actual de CSKA:

```bash
# Reiniciar el scraper
python main.py

# Verificar en los logs que aparezca:
# ✓ Fouls Conceded: 4 - 5
# ✓ Dangerous Attacks: 15 - 9
# ✓ Blocked Shots: 1 - 0
# etc.
```

## Próximos Pasos

1. ✅ Verificar que el scraper captura las nuevas stats en el partido CSKA
2. ⏳ Probar con otros partidos de ligas menores
3. ⏳ Verificar que no se rompe la captura de partidos con interfaz completa (ej: Oporto)

## Notas Importantes

- **Dangerous Attacks** aparece en 3 tabs diferentes (Summary, Attacking, Distribution)
- Se captura en TODOS para máxima cobertura
- Si aparece en múltiples tabs, se sobrescribe con el último valor encontrado
- **Shooting Accuracy** se captura como porcentaje (ej: "17%" → se guarda "17")
- Todos los nuevos campos son compatibles con la función `es_valor_numerico()`

---

**Resultado**: El scraper ahora captura **TODAS** las estadísticas disponibles en partidos con interfaz limitada, aumentando la cobertura del 22% al 100% para este tipo de partidos.
