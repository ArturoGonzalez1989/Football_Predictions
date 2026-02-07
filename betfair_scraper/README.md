# Betfair Exchange Odds Observer

Observador local de cuotas in-play de Betfair.es Exchange. Captura datos back/lay de múltiples partidos simultáneamente para backtesting de varianza de cuotas.

**Uso personal/local exclusivamente. Bajo volumen de peticiones.**

---

## Estructura del proyecto

```
betfair_scraper/
├── main.py              # Scraper Selenium multi-pestaña
├── tampermonkey.js       # Extensión Tampermonkey (alternativa al scraper)
├── analyze.py            # Análisis de datos + modelo predictivo
├── config.py             # Configuración central
├── requirements.txt      # Dependencias Python
├── data/                 # CSVs generados (auto-creado)
│   ├── unificado.csv
│   ├── partido_XXXXX.csv
│   └── plot_XXXXX.png
└── README.md
```

## Instalación

### 1. Requisitos previos

- Python 3.9+
- Google Chrome instalado
- Cuenta en Betfair.es

### 2. Instalar dependencias

```bash
cd betfair_scraper
pip install -r requirements.txt
```

### 3. Configurar URLs de partidos

Edita `config.py` y reemplaza las URLs placeholder con URLs reales de partidos:

```python
MATCH_URLS = [
    "https://www.betfair.es/exchange/plus/es/futbol/la-liga/real-madrid-v-barcelona/12345678",
    "https://www.betfair.es/exchange/plus/es/futbol/premier-league/arsenal-v-chelsea/87654321",
]
```

Para obtener las URLs:
1. Ve a betfair.es/exchange
2. Navega al partido deseado
3. Copia la URL completa de la barra de direcciones

---

## Uso: Scraper Selenium (main.py)

### Ejecución básica

```bash
cd betfair_scraper
python main.py
```

### Con argumentos

```bash
# URLs desde línea de comandos
python main.py --urls "https://betfair.es/.../partido1" "https://betfair.es/.../partido2"

# Cambiar intervalo de captura a 90 segundos
python main.py --ciclo 90

# Más tiempo para login manual (120 segundos)
python main.py --login-wait 120

# Directorio de salida personalizado
python main.py --output mis_datos/
```

### Flujo de trabajo

1. El script abre Chrome con las pestañas configuradas
2. **Haz login manualmente** en Betfair.es (tienes 60s por defecto)
3. El scraper comienza a ciclar por las pestañas
4. Cada ciclo captura cuotas de todas las pestañas
5. Los datos se guardan en CSV en tiempo real
6. **Ctrl+C** para detener (cierre limpio, datos guardados)

### Salida CSV

Se generan dos tipos de archivo:

**CSV individual** (`data/partido_XXXXX.csv`): un archivo por partido.

**CSV unificado** (`data/unificado.csv`): todos los partidos juntos.

Columnas:

| Columna | Descripción |
|---------|-------------|
| `tab_id` | ID del partido (extraído de URL) |
| `timestamp_utc` | Timestamp UTC de la captura |
| `evento` | Nombre del evento |
| `minuto` | Minuto del partido |
| `goles_local` | Goles del equipo local |
| `goles_visitante` | Goles del equipo visitante |
| `back_home` | Mejor cuota back para local |
| `lay_home` | Mejor cuota lay para local |
| `back_draw` | Mejor cuota back para empate |
| `lay_draw` | Mejor cuota lay para empate |
| `back_away` | Mejor cuota back para visitante |
| `lay_away` | Mejor cuota lay para visitante |
| `back_over25` | Back Over 2.5 goles |
| `lay_over25` | Lay Over 2.5 goles |
| `back_under25` | Back Under 2.5 goles |
| `lay_under25` | Lay Under 2.5 goles |
| `volumen_matched` | Volumen total matched (€) |
| `url` | URL del partido |

### Ejemplo de datos

```csv
tab_id,timestamp_utc,evento,minuto,goles_local,goles_visitante,back_home,lay_home,back_draw,lay_draw,back_away,lay_away,back_over25,lay_over25,back_under25,lay_under25,volumen_matched,url
12345678,2025-01-15 20:15:00,Real Madrid v Barcelona,15,0,0,2.48,2.52,3.20,3.25,3.00,3.05,1.78,1.82,2.10,2.15,245000,https://...
12345678,2025-01-15 20:16:00,Real Madrid v Barcelona,16,0,0,2.46,2.50,3.22,3.28,3.02,3.08,1.76,1.80,2.12,2.18,248000,https://...
```

---

## Uso: Tampermonkey (tampermonkey.js)

Alternativa al scraper Selenium. Funciona como extensión del navegador.

### Instalación

1. Instala [Tampermonkey](https://www.tampermonkey.net/) en Chrome
2. Click en el icono de Tampermonkey → "Crear nuevo script"
3. Pega el contenido de `tampermonkey.js`
4. Guarda (Ctrl+S)

### Funcionamiento

- Se activa automáticamente en cualquier página `betfair.es/exchange/*`
- Muestra un panel flotante arriba-derecha con controles
- Captura datos cada 60 segundos automáticamente
- Sincroniza datos entre pestañas via GM_storage
- Auto-exporta CSV cada 10 minutos
- Botones para exportar CSV manualmente (por partido o global)

### Controles del panel

- **CSV Partido**: descarga CSV solo del partido actual
- **CSV Global**: descarga CSV unificado de todos los partidos
- **Pausar/Reanudar**: controla la captura

---

## Uso: Análisis (analyze.py)

### Modo demo (datos sintéticos)

```bash
python analyze.py --demo
```

Genera datos de ejemplo y ejecuta el análisis completo con gráficos y modelo.

### Analizar datos reales

```bash
# Analizar CSV unificado
python analyze.py --csv data/unificado.csv --plot

# Con modelo predictivo
python analyze.py --csv data/unificado.csv --plot --modelo

# Solo un partido
python analyze.py --csv data/partido_12345678.csv --plot --modelo
```

### Métricas calculadas

- **Probabilidades implícitas**: `1/cuota_back`, normalizadas sin overround
- **Log-returns**: `ln(precio_t / precio_{t-1})` por selección
- **Volatilidad rolling**: desviación estándar de log-returns (ventana=5)
- **Spread back-lay**: diferencia entre lay y back por selección
- **Overround**: suma de probabilidades implícitas (margen del mercado)

### Gráficos generados

Para cada partido se genera un PNG con 4 paneles:
1. Match Odds Back vs tiempo
2. Spread back-lay vs tiempo
3. Probabilidades implícitas normalizadas vs tiempo
4. Volatilidad rolling vs tiempo

### Modelo RandomForest

Modelo básico que predice `lay_home` en t+1 usando:
- Cuotas actuales (back/lay de las 3 selecciones)
- Probabilidades implícitas
- Spreads
- Log-returns y volatilidad
- Minuto del partido

Validado con TimeSeriesSplit. **Es un ejemplo didáctico**, no usar directamente para trading.

---

## Troubleshooting

### Los selectores CSS no funcionan

Los selectores de Betfair cambian con actualizaciones. Para encontrar los correctos:

1. Abre un partido en betfair.es/exchange
2. Pulsa **F12** → pestaña **Elements** (Inspector)
3. Click en el icono de selector (esquina superior izquierda del panel)
4. Haz click sobre el precio back/lay que quieres capturar
5. Busca el selector CSS del elemento y sus padres
6. Actualiza `config.py` → `SELECTORES` con los nuevos selectores

Selectores comunes a buscar:
```
# Precios back (suelen tener clase con "back")
button.bet-button-price (dentro de td.back-cell)

# Precios lay (suelen tener clase con "lay")
button.bet-button-price (dentro de td.lay-cell)

# Filas de runners
tr.runner-line

# Nombre del runner
span.runner-name
```

### Chrome no se abre

```bash
# Verificar que Chrome está instalado
google-chrome --version

# Si usas Chromium
chromium-browser --version

# webdriver-manager debería manejar el chromedriver automáticamente
# Si falla, instala chromedriver manualmente y ponlo en PATH
```

### Error de login / sesión expirada

- Aumenta `--login-wait` a 120 o más segundos
- Betfair puede requerir autenticación 2FA; completa todo durante la pausa
- Si la sesión expira, reinicia el script

### CSV vacíos o con campos vacíos

- Es normal que Over/Under y volumen estén vacíos si el mercado no está visible
- Los datos del minuto/marcador dependen de que el partido esté in-play
- Revisa la consola para mensajes de warning sobre selectores no encontrados

### Betfair bloquea el acceso

- No uses headless (mantén `HEADLESS = False` en config.py)
- Los delays aleatorios (8-12s entre pestañas) minimizan detección
- Mantén un máximo de 5-10 pestañas
- Solo uso personal con bajo volumen

---

## Notas legales

- Este proyecto es para **uso personal y educativo**
- Los datos se capturan localmente desde tu propio navegador autenticado
- No se realizan peticiones directas a la API de Betfair
- Respeta los términos de servicio de Betfair.es
- No redistribuyas los datos capturados
