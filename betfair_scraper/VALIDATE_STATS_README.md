# Validate Stats - Validacion de Estadisticas Disponibles

Script que compara estadisticas disponibles en Betfair vs las que realmente se capturaron. Identifica "brechas de datos" (stats que existen en la pagina pero no se capturaron).

## 🎯 Qué hace

1. Identifica partidos activos en games.csv
2. Accede a cada URL de partido en Betfair
3. Extrae qué estadisticas ESTAN disponibles en la pagina (visualmente)
4. Lee los CSVs capturados del mismo partido
5. Compara: ¿qué está en la página que NO está en el CSV?
6. Reporta las "brechas": stats disponibles pero no capturadas

## 🚀 Uso

### Ejecucion basica

```bash
cd betfair_scraper
python validate_stats.py
```

### Ejemplo de salida

```
[VERIFICANDO] Real Madrid - Barcelona...
  -> Disponibles: xg, posesion, pases, tiros
  -> Capturadas: posesion, pases
  -> FALTANTES: xg, tiros

[VERIFICANDO] Arsenal - Chelsea...
  -> OK: Todas las estadisticas capturadas

RESUMEN:
[ALERTA] Brecha de datos detectada:
  - xg: Disponible pero NO capturado en 1 partido(s)
  - tiros: Disponible pero NO capturado en 1 partido(s)

ACCION RECOMENDADA:
  1. Revisar selectores CSS en main.py
  2. Actualizar main.py para capturar xG y Tiros
```

## 📋 Estadisticas Buscadas

El script busca estas estadisticas:
- **xG** (Expected Goals)
- **Posesion** (%)
- **Pases** completados
- **Tiros** totales
- **Tiros a puerta**
- **Corners**
- **Faltas**
- **Tarjetas** (amarillas/rojas)
- **Fuera de juego**
- **Salvadas** (portero)

## ⚙️ Configuracion

```python
HEADLESS = True   # False para ver la busqueda en tiempo real
TIMEOUT = 10      # Segundos para esperar elementos
```

## 📊 Interpretacion de Resultados

### "Disponible pero NO capturado"
Significa:
- La estadistica EXISTE en la pagina de Betfair
- El scraper NO la extrajo
- Posible problema: selectores CSS incorrectos en main.py

### "Sin estadisticas detectadas"
Significa:
- La estadistica NO esta visible en la pagina
- Normal para ligas menores (Camboya, Tailandia L2, etc)
- Betfair no publica estadisticas Opta para todas las ligas

## 🔍 Casos de Uso

### Caso 1: Mejorar la captura
```
Brecha detectada: xG no se captura
├─ Verificar: ¿El selectores CSS busca en el lugar correcto?
├─ Probar: Usar Developer Tools (F12) en Betfair
└─ Solucionar: Actualizar selectores en main.py
```

### Caso 2: Validar calidad
```
Status: [OK] Todas capturadas
├─ Significa: El scraper extrae correctamente
└─ Conclusion: Calidad de datos es buena
```

### Caso 3: Identificar limitaciones
```
Sin estadisticas disponibles en pagina
├─ Razon: Liga menor sin cobertura Opta
├─ Conclusion: No es culpa del scraper
└─ Esperado: No hay stats que capturar
```

## 🔧 Integracion con Supervisor

Este script se puede ejecutar como PASO 6 opcional:

```
PASO 1: start_scraper.py
PASO 2: find_matches.py
PASO 3: clean_games.py
PASO 4: check_urls.py
PASO 5: generate_report.py
[PASO 6 OPCIONAL: validate_stats.py]  ← Valida calidad de stats
```

Recomendacion: Ejecutar 1-2 veces por dia para detectar problemas de captura.

## 📝 Ejemplo Completo

```bash
# Ejecutar validacion completa
python validate_stats.py

# Salida esperada
[INFO] Encontrados 3 partidos activos
[INFO] Verificando estadisticas disponibles en Betfair...

[VERIFICANDO] Go Ahead Eagles - Heerenveen...
  -> Disponibles: xg, posesion, pases, tiros
  -> Capturadas: posesion, pases
  -> FALTANTES: xg, tiros

[VERIFICANDO] Arsenal Femenino - OHL...
  -> OK: Todas las estadisticas capturadas

[VERIFICANDO] Al Ahly Cairo - Ismaily...
  -> Sin estadisticas detectadas en la pagina

RESUMEN:
[ALERTA] Brecha de datos detectada:
  - xg: Disponible pero NO capturado en 1 partido(s)
  - tiros: Disponible pero NO capturado en 1 partido(s)

ACCION RECOMENDADA:
  1. Revisar selectores CSS en main.py para extraer xG y Tiros
  2. Verificar que los selectores estan actualizados
  3. Considerar actualizar main.py si es un problema recurrente
```

## ⏱️ Cuándo Ejecutarlo

- **Diariamente**: Para monitorizar calidad de datos
- **Cuando cambias selectores**: Para validar que funcionan
- **Cuando Betfair actualiza**: Para detectar cambios en la interfaz
- **Cuando ves baja cobertura de stats**: Para identificar la causa

## 💡 Tips

- Si ves muchas brechas → El problema es probablemente en los selectores CSS
- Si todo está capturado → El scraper funciona correctamente
- Si no hay stats disponibles → Es normal para ligas menores

## 🔗 Relacion con Otros Scripts

```
validate_stats.py
    ↓
Identifica problemas de captura
    ↓
Reporta: "xG no se captura"
    ↓
Usuario: Actualiza selectores en main.py
    ↓
Siguiente ejecucion: Valida que se arreglo
```
