# Find Matches - Búsqueda automática de partidos en Betfair

Script simple que busca automáticamente todos los partidos de fútbol en Betfair y los añade a `games.csv`.

## 🎯 Qué hace

1. Abre Betfair (modo invisible - sin GUI)
2. Busca todos los partidos in-play (en vivo)
3. Busca todos los partidos próximos (hoy)
4. Extrae: nombre del partido, URL, hora de inicio
5. Añade los nuevos a `games.csv`
6. Reporta qué se añadió

## 🚀 Uso

### Ejecución básica

```bash
cd betfair_scraper
python find_matches.py
```

### Ejemplo de salida

```
[INFO] Iniciando búsqueda de partidos en Betfair...
[INFO] Accediendo a: https://www.betfair.es/exchange/plus/inplay
[INFO] Esperando carga de contenido...
[OK] Encontrados 12 partidos:
   - Real Madrid - Barcelona (2026-02-11 18:30)
   - Arsenal - Chelsea (2026-02-11 19:45)
   - Ajax - PSV (2026-02-11 20:00)
   ... (más partidos)

[BUSQUEDA COMPLETADA]
   - Añadidos: 8 partidos nuevos
   - Total en games.csv: 15 partidos
```

## ⚙️ Configuración

El archivo `find_matches.py` tiene estos parámetros al inicio:

```python
BETFAIR_INPLAY_URL = "https://www.betfair.es/exchange/plus/inplay"  # URL a buscar
HEADLESS = True  # Chrome sin GUI (cambiar a False para ver la búsqueda)
TIMEOUT = 10     # Segundos para esperar elementos en la página
```

### Cambios comunes:

**Ver cómo busca en tiempo real**:
```python
HEADLESS = False  # Se abrirá una ventana de Chrome
```

**Cambiar tiempo de espera** (si Betfair es lenta):
```python
TIMEOUT = 20  # Esperar 20 segundos
```

## 📋 Cómo extrae la información

### Nombre del partido
- Busca elementos HTML con enlaces a `/futbol/`
- Extrae el texto visible (ej: "Real Madrid - Barcelona")

### Hora de inicio
El script intenta detectar:

| Patrón | Ejemplo | Resultado |
|--------|---------|-----------|
| "Comienza en X'" | "Comienza en 15'" | Ahora + 15 minutos |
| "Hoy HH:MM" | "Hoy 18:30" | Hoy a las 18:30 |
| "DESC." o marcador | "DESC." o "2-1" | Hace 30 minutos (en juego) |
| Sin patrón | (ninguno) | Hace 30 minutos (aproximación) |

Si no puede determinar la hora, usa 30 minutos atrás (aproximación para partidos en vivo).

### URL
- Extrae la URL del enlace del partido
- Si es relativa, la convierte a URL completa de Betfair
- Formato: `https://www.betfair.es/exchange/plus/es/fútbol/[liga]/[partido]-apuestas-[id]`

## 🔄 Deduplicación

El script:
- Lee los partidos ya en `games.csv`
- Solo añade partidos NUEVOS (no están en la lista)
- Evita duplicados comparando por nombre

## 📅 ¿Cuándo ejecutarlo?

Ejecútalo regularmente para mantener `games.csv` actualizado:
- **Cada mañana**: Para cargar partidos del día
- **Cada mediodía**: Cuando empiezan más partidos
- **Tardes/noches**: Para partidos vespertinos/nocturnos
- **Manualmente**: Cuando quieras buscar nuevos partidos

El supervisor automático lo ejecuta en PASO 2 de su ciclo.

## ⚠️ Notas importantes

### Dependencias
Necesita:
- Selenium (`pip install selenium`)
- webdriver-manager (`pip install webdriver-manager`)
- Chrome instalado en el sistema

Estas ya deben estar en `requirements.txt`.

### Rendimiento
- El script tarda 10-15 segundos en completarse
- Abre Chrome, busca, cierra Chrome
- Modo headless (invisible): No ve la ventana

### Cambios en Betfair
Si Betfair actualiza su interfaz:
- Los selectores CSS pueden cambiar
- El script reportará "No hay partidos" o errores
- Habrá que actualizar los selectores en el código

### Sin conexión a Betfair
Si Betfair no responde o está bloqueado:
```
[ERROR] Error buscando partidos: ...
[OK] Sin partidos nuevos para añadir
```

El script continúa sin fallar.

## 🛠️ Debugging

**Ver la búsqueda en tiempo real**:
```python
HEADLESS = False
```

**Aumentar timeout** (si la página es lenta):
```python
TIMEOUT = 20
```

**Verificar qué encuentra**:
El script imprime en consola todos los partidos detectados.

## 💾 Resultado

Después de ejecutar, `games.csv` tendrá:
- Los partidos que ya había
- Los nuevos partidos encontrados
- Formato correcto: `Game,url,fecha_hora_inicio`

## 📝 Integración con supervisor

El supervisor automático ejecuta esto en PASO 2:

```bash
cd betfair_scraper && python find_matches.py
```

No necesitas hacer nada. Se ejecuta automáticamente en cada ciclo.

Pero puedes ejecutarlo manualmente cuando quieras:

```bash
python find_matches.py
```
