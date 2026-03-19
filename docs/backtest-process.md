# El Proceso de Backtest de Furbo — Guia Completa

## Que es esto y para que sirve

Imagina que tienes 32 ideas para apostar en partidos de futbol en Betfair Exchange. Cada idea (llamada **estrategia**) dice algo como: "cuando el marcador va 0-0 despues del minuto 30 y el xG total es bajo, apuesta al empate". Pero, funciona eso realmente? Y con que parametros funciona mejor?

El **backtest** responde esas preguntas. Toma mas de 1200 partidos historicos que nuestro scraper ha grabado minuto a minuto (cuotas, estadisticas, marcador...) y simula que habria pasado si hubieras apostado siguiendo cada estrategia. Es como viajar al pasado y probar tus ideas con datos reales.

El resultado final es un fichero de configuracion (`cartera_config.json`) que dice exactamente: "estas estrategias funcionan, con estos parametros, activadas; estas otras no funcionan, desactivadas". Esa configuracion es la que luego usa el sistema en vivo para detectar senales y colocar apuestas reales.

---

## Indice

1. [Los ficheros: quien hace que](#1-los-ficheros-quien-hace-que)
2. [El viaje de los datos de principio a fin](#2-el-viaje-de-los-datos-de-principio-a-fin)
3. [Phase 0 — Cargar los partidos en memoria](#3-phase-0--cargar-los-partidos-en-memoria)
4. [Phase 1 — Probar todas las combinaciones de parametros](#4-phase-1--probar-todas-las-combinaciones-de-parametros)
5. [Phase 1.5 — Afinar las cuotas minimas](#5-phase-15--afinar-las-cuotas-minimas)
6. [Phase 2 — Escribir la configuracion ganadora](#6-phase-2--escribir-la-configuracion-ganadora)
7. [Phase 2.5 — Comprobar que no es suerte](#7-phase-25--comprobar-que-no-es-suerte)
8. [Phase 3 — Construir el portfolio optimo](#8-phase-3--construir-el-portfolio-optimo)
9. [Phase 4 — Elegir el mejor portfolio y aplicarlo](#9-phase-4--elegir-el-mejor-portfolio-y-aplicarlo)
10. [Phase 5 — Exportar los resultados](#10-phase-5--exportar-los-resultados)
11. [Como funciona el motor que simula cada apuesta](#11-como-funciona-el-motor-que-simula-cada-apuesta)
12. [Que es un trigger y como funcionan los 32](#12-que-es-un-trigger-y-como-funcionan-los-32)
13. [Las puertas de calidad que debe pasar cada estrategia](#13-las-puertas-de-calidad-que-debe-pasar-cada-estrategia)
14. [Deduplicacion: no apostar dos veces en lo mismo](#14-deduplicacion-no-apostar-dos-veces-en-lo-mismo)
15. [Simulacion de cashout](#15-simulacion-de-cashout)
16. [El fichero de configuracion central](#16-el-fichero-de-configuracion-central)
17. [Como se relaciona el backtest con el sistema en vivo](#17-como-se-relaciona-el-backtest-con-el-sistema-en-vivo)
18. [Las 32 estrategias](#18-las-32-estrategias)

---

## 1. Los ficheros: quien hace que

El proceso involucra varios ficheros que colaboran entre si. Vamos a conocerlos uno a uno:

### El director de orquesta

**`scripts/bt_optimizer.py`** (~1337 lineas) — Es el script principal que ejecutas para lanzar el backtest. Piensa en el como un director de orquesta: el no toca ningun instrumento, pero le dice a cada musico cuando entrar. Organiza las 6 fases del proceso (Phase 0 a 5), llama a las funciones correctas en el orden correcto, y al final genera los ficheros de salida.

### Los musicos principales

**`betfair_scraper/dashboard/backend/utils/csv_reader.py`** (~6200 lineas) — El fichero mas grande e importante del proyecto. Contiene dos cosas fundamentales:

- La **lista de las 32 estrategias** (llamada `_STRATEGY_REGISTRY`, un array donde cada elemento describe una estrategia: su nombre, su trigger, como extraer las cuotas, y como saber si gano).
- La **funcion `_analyze_strategy_simple()`** que es el "motor" del backtest: toma una estrategia y la ejecuta sobre todos los partidos historicos, generando una lista de apuestas simuladas con su resultado (gano/perdio, cuanto).

**`betfair_scraper/dashboard/backend/utils/strategy_triggers.py`** (~2000+ lineas) — Contiene las 32 funciones de deteccion (una por estrategia). Cada funcion responde a la pregunta: "dado el estado actual de un partido en un minuto concreto, se cumple la condicion para apostar?" Por ejemplo, la funcion `_detect_back_draw_00_trigger` comprueba si el marcador es 0-0, si estamos en el rango de minutos correcto, y si las estadisticas (xG, posesion, tiros) estan dentro de los limites configurados.

**`betfair_scraper/dashboard/backend/utils/csv_loader.py`** (~1230 lineas) — Se encarga de leer los ficheros CSV de los partidos, preprocesarlos (limpiar datos erroneos, normalizar minutos) y cachearlos en memoria para que las demas funciones no tengan que releer ficheros del disco constantemente.

**`betfair_scraper/dashboard/backend/api/optimizer_cli.py`** (597 lineas) — El optimizador de portfolio. Mientras `bt_optimizer.py` optimiza cada estrategia por separado, este fichero optimiza **como combinar las estrategias entre si**: cuales activar, que filtros aplicar al conjunto, que modo de bankroll usar, etc.

**`betfair_scraper/dashboard/backend/api/optimize.py`** (816 lineas) — Contiene las funciones "worker" que hace el trabajo pesado del optimizador de portfolio: probar combinaciones de on/off, aplicar filtros realistas, simular un bankroll, y calcular puntuaciones. Tambien expone endpoints de la API para lanzar la optimizacion desde el dashboard web.

### Los datos

**`betfair_scraper/data/partido_*.csv`** — Mas de 1200 ficheros CSV, uno por partido. Cada fila del CSV es una "foto" del partido en un momento dado (~1 fila por minuto): marcador, cuotas de todas las apuestas, estadisticas (xG, posesion, tiros a puerta, corners...). Estos son los datos sobre los que se ejecuta todo el backtest.

**`betfair_scraper/cartera_config.json`** — El fichero de configuracion central. Contiene los parametros de cada estrategia (minuto minimo, minuto maximo, xG maximo, etc.) y si esta activada o desactivada. Es la **unica fuente de verdad**: tanto el backtest como el sistema en vivo lo leen para saber que hacer.

### Los ficheros de salida

**`auxiliar/bt_optimizer_results.json`** — Resultados intermedios del backtest (para poder retomar desde una fase concreta sin repetir todo).

**`betfair_scraper/data/presets/`** — Carpeta donde se guardan los portfolios optimizados. Por cada criterio de optimizacion (maximizar ROI, maximizar P/L, etc.) se genera un fichero de configuracion y un CSV con las apuestas resultantes.

**`analisis/bt_results_*.csv` y `.xlsx`** — Los resultados finales exportados, con todas las apuestas del portfolio elegido, resumenes por estrategia, por dia, curva de P/L acumulado, etc.

**`backup/cartera_config/`** — Copias de seguridad automaticas de `cartera_config.json` antes de cada modificacion.

### Como se conectan entre si

```
                         scripts/bt_optimizer.py
                         (el director de orquesta)
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
    csv_reader.py            optimizer_cli.py        cartera_config.json
    (motor de backtest       (optimizador de         (configuracion
     + 32 estrategias)        portfolio)              central)
         |                       |
    +----+----+             optimize.py
    |         |             (workers y
csv_loader.py  strategy_    simulacion
(leer CSVs,   triggers.py   bankroll)
 preprocesar)  (32 triggers)
    |
partido_*.csv
(1200+ CSVs de partidos)
```

---

## 2. El viaje de los datos de principio a fin

Antes de entrar en detalle fase por fase, veamos el recorrido completo de los datos:

```
PARTIDOS HISTORICOS (1200+ CSVs con datos minuto a minuto)
        |
        v
[Phase 0] Se leen todos los CSVs, se limpian y se guardan en memoria
        |
        v
[Phase 1] Para cada estrategia, se prueban MILES de combinaciones
          de parametros. Se queda con la mejor de cada una.
          Ejemplo: "back_draw_00 funciona mejor con xg_max=0.6,
                    poss_max=20, minute_min=30"
        |
        v
[Phase 1.5] Se afina un parametro concreto: la cuota minima.
            Usa un metodo analitico en vez de fuerza bruta.
        |
        v
[Phase 2] Se escriben los mejores parametros en un formato
          compatible con cartera_config.json.
          Las que no pasaron quality gates quedan "enabled: false".
        |
        v
[Phase 2.5] Se comprueba que los resultados son robustos,
            no producto de la suerte. Se divide los datos en
            5 grupos y un test temporal.
        |
        v
[Phase 3] Con las estrategias supervivientes, se optimiza
          EL PORTFOLIO COMPLETO: que combinaciones de estrategias
          activas + filtros + bankroll dan mejor resultado.
          Se generan 4 portfolios (uno por criterio).
        |
        v
[Phase 4] Se evalua cada portfolio con metricas reales
          y se elige el mejor. Se aplica a cartera_config.json.
        |
        v
[Phase 5] Se exporta un informe completo: CSV con todas las
          apuestas, XLSX con 5 hojas de analisis.
```

---

## 3. Phase 0 — Cargar los partidos en memoria

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `phase0_load()` (linea 459). Esta funcion llama a `_get_all_finished_matches()` que vive en `csv_loader.py` (linea 1135), y esta a su vez llama a `_get_cached_finished_data()` (linea 1030) que es donde ocurre el trabajo real.

### Que hace, paso a paso

**Paso 1: Encontrar los partidos.** Lee el fichero `games.csv` (un indice con el nombre, URL y estado de cada partido trackeado). Luego escanea la carpeta `betfair_scraper/data/` buscando ficheros que se llamen `partido_*.csv`.

**Paso 2: Filtrar solo los terminados.** Solo nos interesan partidos con estado "finished" (terminados) y que tengan un CSV existente. Los partidos en curso o futuros se ignoran.

**Paso 3: Leer cada CSV.** Para cada partido terminado, se llama a `_read_csv_rows()` (linea 472 de csv_loader.py), que simplemente abre el CSV y convierte cada fila en un diccionario Python (clave: nombre de columna, valor: el dato). Un partido tipico tiene entre 50 y 150 filas (una foto por minuto aproximadamente).

**Paso 4: Limpiar los datos.** Cada CSV pasa por tres funciones de limpieza, en este orden:

1. **`_normalize_halftime_minutes()`** — Betfair tiene un problema: durante el tiempo de descuento de la primera parte, el reloj sigue contando (46, 47, 48...) en vez de mostrar "45+1, 45+2". Esto crea minutos duplicados (hay un minuto 50 en el tiempo de descuento de la primera parte Y un minuto 50 real en la segunda). Esta funcion detecta las filas de descanso (`estado_partido == "descanso"`) y capea a 45 cualquier minuto de la primera parte que pase de 45.

2. **`_clean_odds_outliers()`** — A veces Betfair muestra cuotas absurdas por una fraccion de segundo (por ejemplo, back_home pasa de 2.0 a 150.0 y vuelve a 2.1). Esto ocurre cuando el mercado se suspende y reabre. Esta funcion detecta esos "spikes" y los elimina.

3. **`_strip_trailing_pre_partido_rows()`** — El scraper a veces sigue capturando despues de que termina un partido. Las filas extra tienen `estado_partido = "pre_partido"` (porque la API de Betfair ya cambio a otro evento) y no tienen marcador. Esta funcion las elimina desde el final del CSV hacia atras.

**Paso 5: Guardar en cache.** Los partidos procesados se almacenan en una variable en memoria (protegida con un `Lock` para seguridad entre hilos) con un TTL de 5 minutos. Asi, las siguientes funciones que necesiten los datos no tienen que volver a leer los 1200+ CSVs del disco.

### Que produce

Una lista de diccionarios, uno por partido. Cada diccionario contiene:
- `match_id`: identificador unico del partido (extraido del nombre del CSV).
- `name`: nombre del partido (ej: "Barcelona - Real Madrid").
- `url`: URL de Betfair para este partido.
- `csv_path`: ruta al fichero CSV en disco.
- `rows`: la lista de filas ya limpiadas (lo mas importante — son los datos sobre los que corren las estrategias).
- Metricas de calidad: outliers en odds, gaps en minutos, etc.

### Cuanto tarda

Aproximadamente 5 segundos para ~1200 partidos.

---

## 4. Phase 1 — Probar todas las combinaciones de parametros

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `phase1_individual()` (linea 575). Dentro, llama repetidamente a `_run_single_strategy()` (linea 553) que a su vez usa `_analyze_strategy_simple()` de `csv_reader.py` (linea 470).

### La idea

Cada estrategia tiene **parametros configurables**. Por ejemplo, la estrategia "back_draw_00" (apostar al empate cuando va 0-0) tiene:

- `xg_max`: cuanto xG total maximo permitimos. Un xG alto significa que los equipos estan creando muchas ocasiones, lo cual hace menos probable que siga 0-0.
- `poss_max`: cuanta diferencia de posesion maxima permitimos. Si un equipo domina mucho, puede ser que marque.
- `shots_max`: cuantos tiros totales maximos.
- `minute_min`: desde que minuto empezamos a buscar esta senal.
- `minute_max`: hasta que minuto buscamos.

La pregunta es: **que valores concretos de estos parametros dan mejor resultado?** xg_max=0.5 es mejor que xg_max=0.7? Apostar solo a partir del minuto 35 es mejor que desde el 25?

### El grid search

Para responder, el sistema prueba **todas las combinaciones posibles**. Esto se llama "grid search" (busqueda en cuadricula). Para back_draw_00:

```
xg_max:     se prueba con [0.4, 0.5, 0.6, 0.7, 1.0]    → 5 opciones
poss_max:   se prueba con [15, 20, 25, 30, 100]          → 5 opciones
shots_max:  se prueba con [6, 8, 10, 12, 20]             → 5 opciones
minute_min: se prueba con [25, 30, 35]                    → 3 opciones
minute_max: se prueba con [75, 80, 85, 90]               → 4 opciones
```

Total: 5 x 5 x 5 x 3 x 4 = **1500 combinaciones** a probar solo para esta estrategia.

Las combinaciones estan definidas en el diccionario `SEARCH_SPACES` al principio de `bt_optimizer.py` (linea 98). Hay un search space para cada una de las 32 estrategias (excepto `tarde_asia`, que no tiene parametros ajustables porque se basa solo en la liga del partido).

### Como se prueba cada combinacion

Para cada combinacion de parametros, se ejecuta esta secuencia:

1. Se construye un diccionario `cfg` con los parametros de esta combinacion. Ejemplo:
   ```python
   cfg = {"xg_max": 0.6, "poss_max": 20, "shots_max": 8,
          "minute_min": 30, "minute_max": 85, "enabled": True}
   ```

2. Se pasa por `_cfg_add_snake_keys()` (csv_reader.py, linea 451). Esta funcion es un traductor de nombres: el fichero de configuracion usa camelCase (`xgMax`, `minuteMin`) pero las funciones internas de las estrategias usan snake_case (`xg_max`, `minute_min`). Para que todo funcione, esta funcion anade los aliases snake_case al diccionario. Algunos parametros incluso tienen multiples aliases (por ejemplo, `minuteMin` se traduce a `min_minute`, `minute_min`, `m_min` y `min_m`) porque distintas funciones de trigger usan nombres ligeramente diferentes.

3. Se llama a `_analyze_strategy_simple()` (explicada en detalle en la seccion 11). En resumen: recorre los 1200+ partidos, y para cada uno, va fila por fila comprobando si la estrategia se activa. Si se activa y se mantiene activa el numero de filas requerido, registra una apuesta con su resultado.

4. El resultado es una lista de apuestas: por ejemplo, "220 apuestas, 132 ganadas, P/L total = +38.5 unidades".

5. Se pasa esa lista por `_eval_bets()` (bt_optimizer.py, linea 342): las **puertas de calidad** (quality gates). Si no pasa los criterios minimos (explicados en seccion 13), devuelve `None` y esa combinacion se descarta. Si pasa, devuelve un diccionario con las metricas.

6. Se calcula un **score** para comparar: `score = ci_low * roi / 100`. Aqui, `ci_low` es el limite inferior del intervalo de confianza (una medida estadistica de "que tan seguro estoy de que este win rate es real y no suerte") y `roi` es el retorno sobre la inversion. Multiplicarlos equilibra rentabilidad con solidez estadistica.

7. Si el score de esta combinacion es mejor que el mejor visto hasta ahora, se guarda como nuevo mejor.

### Que estrategias se prueban

Todas las 32 excepto tres LAY que estan **permanentemente excluidas**:

```python
_PERMANENTLY_DISABLED = {"lay_over45_v3", "lay_over45_blowout", "lay_cs11"}
```

Estas se excluyen porque son apuestas LAY (apuestas "en contra"), donde el riesgo es asimetrico: puedes ganar como maximo 1 unidad pero perder `(cuota - 1)` unidades. Si la cuota es 8.0, puedes perder 7 unidades por cada 1 que ganas. El backtest las evalua pero no las incluye en el portfolio por prudencia.

### Cuanto tarda

5-15 minutos, dependiendo del numero de estrategias y el tamano de los search spaces. Cada evaluacion de una combinacion tarda ~0.3-0.5 segundos porque los datos ya estan en memoria (Phase 0). Se ejecuta de forma secuencial (una combinacion tras otra) porque las funciones trigger contienen lambdas de Python que no se pueden enviar a otros procesos.

### Que produce

Un diccionario con solo las estrategias que pasaron quality gates. Ejemplo:

```python
{
    "cs_one_goal": {
        "n": 85,              # numero de apuestas
        "wins": 51,           # apuestas ganadas
        "wr": 60.0,           # win rate (%)
        "pl": 22.35,          # profit/loss total (unidades)
        "roi": 26.3,          # retorno sobre inversion (%)
        "ci_low": 49.2,       # limite inferior del intervalo de confianza Wilson 95%
        "ci_high": 70.1,      # limite superior
        "max_dd": 5.8,        # maximo drawdown
        "score": 12.94,       # ci_low * roi / 100 — para comparar
        "params": {           # los parametros ganadores
            "m_min": 68,
            "m_max": 90,
            "odds_min": 3.0,
            "odds_max": 999
        },
        "key": "cs_one_goal"
    },
    "draw_11": { ... },
    ...
}
```

Las estrategias que no aparecen aqui no pasaron las puertas de calidad.

---

## 5. Phase 1.5 — Afinar las cuotas minimas

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `_calibrate_odds_min()` (linea 487). Se ejecuta inmediatamente despues del grid search de cada estrategia, dentro del bucle de `phase1_individual()`.

### El problema que resuelve

El grid search prueba valores de `odds_min` como 0, 1.20, 1.30, 1.40. Pero, y si el valor optimo real es 1.65? No lo encontraria porque no esta en la lista. Ademas, el grid search busca el mejor resultado **global** de la estrategia, y puede ser que a cuotas bajas la estrategia pierda dinero pero a cuotas altas sea muy rentable.

### La idea

En vez de probar valores a ciegas, Phase 1.5 hace una pregunta mas inteligente: **"a partir de que cuota mi estrategia tiene ventaja sobre el mercado?"**

El razonamiento es asi: si la cuota de una apuesta es 2.0, el mercado de Betfair esta diciendo "la probabilidad de que esto ocurra es 1/2.0 = 50%". Si nuestros datos historicos muestran que con nuestra estrategia ganamos el 58% de las veces a esas cuotas, tenemos un **edge** (ventaja) del 8%. Pero si a cuotas de 1.30 solo ganamos el 70% y la probabilidad implicita es 77%, ahi NO tenemos ventaja.

### Como funciona

1. Re-ejecuta la estrategia con `odds_min = 0` (sin ningun filtro de cuota) usando los mejores parametros del grid search para todo lo demas.

2. Agrupa las apuestas resultantes en **buckets de cuotas** (intervalos):
   ```
   [1.00 - 1.30]  cuotas muy bajas (favoritos claros)
   [1.30 - 1.50]  cuotas bajas
   [1.50 - 1.65]  cuotas medias-bajas
   [1.65 - 1.80]  cuotas medias
   [1.80 - 2.10]  cuotas medias-altas
   [2.10 - 3.00]  cuotas altas
   [3.00 - inf]   cuotas muy altas (longshots)
   ```

3. Para cada bucket que tenga al menos 5 apuestas:
   - Calcula el **win rate real** (% de apuestas ganadas en ese rango).
   - Calcula el **win rate implicito del mercado** (`1 / cuota media del bucket`).
   - Si win rate real > implicito: hay edge positivo. Este es el bucket minimo donde vale la pena apostar.

4. El `odds_min` calibrado es el limite inferior del primer bucket con edge.

5. Si el valor calibrado es diferente al del grid search, se verifica que la estrategia con este nuevo odds_min siga pasando quality gates.

### Ejemplo concreto

Para una estrategia cualquiera:
```
Bucket [1.00-1.30]: WR real=73%, WR implicito=87% → NO hay edge (-14%)
Bucket [1.30-1.50]: WR real=68%, WR implicito=71% → NO hay edge (-3%)
Bucket [1.50-1.65]: WR real=65%, WR implicito=63% → SI hay edge (+2%)
```

Resultado: `odds_min = 1.50`. Solo apostaremos cuando la cuota sea >= 1.50.

### Cuando no aplica

No se aplica a estrategias LAY, porque su P/L es asimetrico y la comparacion WR vs WR implicito no tiene sentido directo.

---

## 6. Phase 2 — Escribir la configuracion ganadora

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `phase2_build_config()` (linea 654).

### Que hace

Es una fase sencilla pero importante: toma los resultados de Phase 1 (los mejores parametros de cada estrategia que paso quality gates) y los escribe en el formato que `cartera_config.json` entiende.

### Paso a paso

1. **Lee la configuracion actual** de `cartera_config.json` como base.

2. **Para cada estrategia que paso quality gates** (las que estan en `individual_results`):
   - Convierte los nombres de parametros de snake_case a camelCase. Esto lo hace `_snake_to_camel()` (linea 695). Ejemplo:
     ```
     "minute_min" → "minuteMin"
     "xg_excess_min" → "xgExcessMin"
     "drift_min_pct" → "driftMin"
     ```
   - Crea una entrada con `enabled: true` y los parametros optimizados.
   - Incluye unas `_stats` embebidas (wr, roi, n, ci_low) como referencia (no las usa el sistema, solo para que un humano pueda ver las metricas al abrir el JSON).

3. **Para cada estrategia que NO paso quality gates**:
   - Le pone `enabled: false` pero **preserva sus parametros anteriores**. Asi, si en un futuro backtest con mas datos pasa los quality gates, ya tiene parametros razonables.

4. **Devuelve el diccionario `new_strategies`** (no lo escribe a disco todavia — eso ocurrira en Phase 3).

### Ejemplo de salida

```json
{
    "cs_one_goal": {
        "enabled": true,
        "minuteMin": 68,
        "minuteMax": 90,
        "oddsMin": 3.0,
        "oddsMax": 999,
        "_stats": { "wr": 60.0, "roi": 26.3, "n": 85, "ci_low": 49.2 }
    },
    "back_draw_00": {
        "enabled": false,
        "xgMax": 0.6,
        "possMax": 20,
        "shotsMax": 8,
        "minuteMin": 30,
        "minuteMax": 90
    }
}
```

---

## 7. Phase 2.5 — Comprobar que no es suerte

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `phase2_5_crossval()` (linea 730).

### El problema

El grid search de Phase 1 prueba miles de combinaciones sobre los MISMOS datos. Es posible que algunas estrategias parezcan rentables simplemente por azar: si pruebas 1500 combinaciones, estadisticamente alguna dara buen resultado incluso sobre datos aleatorios. Esto se llama **overfitting** (sobreajuste).

### La solucion: dos pruebas de robustez

**Prueba 1: K-Fold Cross-Validation (validacion cruzada en 5 grupos)**

Imagina que divides los 1200 partidos en 5 bolsas de 240 partidos cada una, mezclados aleatoriamente (con una semilla fija de 42 para que sea reproducible). Luego evaluas cada estrategia en cada bolsa por separado, obteniendo 5 resultados independientes.

Si una estrategia tiene ROI=25% en 4 bolsas pero ROI=-15% en la quinta, probablemente su rendimiento depende de unos pocos partidos favorables. Una estrategia robusta deberia funcionar bien en la mayoria de las bolsas.

La funcion `_eval_on_matches_subset()` (linea 384) ejecuta una estrategia solo sobre un subconjunto de partidos. Es una version reducida de `_analyze_strategy_simple()` — el mismo loop de trigger → persistencia → extraccion → resultado, pero solo sobre los partidos que le pasas.

**Prueba 2: Test temporal (70/30)**

Los partidos se ordenan cronologicamente (de mas antiguo a mas reciente). El primer 70% se considera "entrenamiento" (Phase 1 ya los uso implicitamente). El ultimo 30% es "test" — datos que nunca se usaron para elegir parametros.

La pregunta es: la estrategia funciona en los partidos mas recientes, que no participaron en la seleccion de parametros?

### Criterios para ser "robusta"

Una estrategia se considera robusta si cumple **las tres condiciones**:

```
1. Media del ROI en los 5 folds >= 10%
   (no basta con que un fold sea espectacular si los demas son malos)

2. Al menos 3 de los 5 folds tienen ROI > 0
   (no puede fallar en la mayoria de las subdivisiones)

3. ROI en el test temporal (ultimo 30%) >= 0%
   (debe al menos no perder dinero en datos recientes no vistos)
```

### Que pasa con las fragiles

Las estrategias que no pasan estas pruebas se marcan como **fragiles** y se desactivan:
- Se les pone `enabled: false` en `new_strategies`.
- Se eliminan de `individual_results` para que Phase 3 no las tenga en cuenta.

### Ejemplo de salida en consola

```
cs_one_goal    F1:+22%  F2:+18%  F3:+31%  F4:+14%  F5:+26%  Mean:+22.2%±5.8  Temp:+15.3%  ROBUSTO
poss_extreme   F1:+45%  F2:-12%  F3:+8%   F4:+62%  F5:-5%   Mean:+19.6%±28.1 Temp:-8.2%   FRAGIL
```

En este ejemplo, `poss_extreme` tiene buena media pero alta varianza, ROI negativo en 2 folds, y ROI negativo en el test temporal. Se desactivaria.

---

## 8. Phase 3 — Construir el portfolio optimo

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `phase3_presets()` (linea 859). Esta funcion llama a `optimizer_cli.run()` de `optimizer_cli.py` (linea 469), que a su vez usa las funciones worker de `optimize.py`.

### Por que necesitamos otro nivel de optimizacion

Hasta aqui, hemos optimizado cada estrategia **por separado**. Pero las estrategias no viven solas: conviven en un portfolio. Puede que dos estrategias sean individualmente buenas pero juntas sean malas (por ejemplo, si apuestan en mercados opuestos del mismo partido). O puede que un filtro global (como "no apostar a cuotas mayores de 6.0") mejore el rendimiento del conjunto aunque perjudique a alguna individual.

Phase 3 resuelve esto: optimiza **el portfolio completo**.

### Como se ejecuta

1. **Escribe una configuracion de staging**: Los parametros individuales ganadores de Phases 1-2.5 se escriben a `cartera_config.json` (con backup previo). Esto es necesario porque el optimizador de portfolio lee esa config para saber que parametros usar cuando evalua apuestas.

2. **Ejecuta `optimizer_cli.run()` cuatro veces**, una para cada criterio de optimizacion:
   - `max_roi`: maximizar el retorno sobre inversion.
   - `max_pl`: maximizar el profit/loss absoluto.
   - `max_wr`: maximizar la tasa de acierto.
   - `min_dd`: minimizar el drawdown (peor racha de perdidas).

Cada ejecucion genera un preset: un fichero de configuracion completo optimizado para ese criterio.

### Que hace `optimizer_cli.run()` por dentro

El optimizador de portfolio ejecuta 5 sub-fases. Vamos a verlas:

#### Sub-Phase 1: Probar combinaciones on/off (2,048 combinaciones)

El codigo esta en `optimize.py`, funcion `_phase1_worker()` (linea 477).

De las 32 estrategias, solo 7 (las "originales") participan en el juego de on/off del portfolio:
- `back_draw_00`, `xg_underperformance`, `odds_drift`, `goal_clustering`, `pressure_cooker`, `tarde_asia`, `momentum_xg`

Las otras 25 estan siempre incluidas (su activacion/desactivacion ya se decidio en Phase 1 individual).

Para estas 7 estrategias, se prueban todas las combinaciones de encenderlas o apagarlas (2^7 = 128). Ademas, para cada combinacion se prueban:
- 4 modos de gestion de bankroll: `fixed` (stake fijo al 2%), `half_kelly` (criterio Kelly/2), `dd_protection` (reduce stake en drawdowns), `anti_racha` (reduce tras rachas perdedoras).
- 4 filtros de riesgo: `all` (todo), `no_risk` (solo bajo riesgo), `with_risk` (solo medio/alto riesgo), `medium`.

Total: 128 x 4 x 4 = **2,048 combinaciones**.

Para cada una:
1. Se recogen todas las apuestas de las estrategias activadas (las bets ya existen, generadas previamente por `analyze_cartera()`).
2. Se aplica un filtro de cuotas minimas por estrategia (`_meets_min_odds()` — hay cuotas minimas hardcodeadas en `MIN_ODDS` para las 7 originales, como 1.93 para back_draw_00).
3. Se ordenan cronologicamente.
4. Se aplica el filtro de riesgo.
5. Si quedan al menos 15 apuestas, se simula el bankroll completo (`_simulate_cartera_py()`, explicada abajo) y se calcula un score.

El score depende del criterio:

| Criterio | Formula del score | Que optimiza |
|----------|-------------------|--------------|
| `max_roi` | ROI × confianza | Rentabilidad proporcional |
| `max_pl` | P/L absoluto × confianza | Beneficio total en dinero |
| `max_wr` | Wilson CI lower bound | Probabilidad minima de ganar |
| `min_dd` | (P/L gestionado - 2×maxDD + WR×0.5) × confianza | Minimizar perdidas |

Donde **confianza** = `min(1.0, N/60)` — una penalizacion para portfolios con pocas apuestas (si tienes solo 20 bets, tu confianza es 20/60 = 0.33, asi que tu score se reduce a un tercio).

**Simulacion de bankroll** (`_simulate_cartera_py()` en optimize.py, linea 351):

Simula recorrer las apuestas una a una, como si estuvieras apostando de verdad con un bankroll real. Para cada bet:
- Calcula el stake segun el modo de bankroll elegido (por ejemplo, 2% del bankroll actual).
- Aplica el P/L (ajustado por la proporcion stake/10 — las bets del backtest asumen stake=10).
- Actualiza el bankroll, trackea pico, drawdown, wins/losses.
- Al final devuelve: total bets, wins, win%, flat P/L, flat ROI, managed P/L, max drawdown.

**Paralelizacion**: Las 2,048 combinaciones se dividen en 4 chunks (por pares draw x xg) y se ejecutan en paralelo usando `ProcessPoolExecutor`.

#### Sub-Phase 2: Ajustes realistas (7,776 combinaciones)

El codigo esta en `optimize.py`, funcion `_phase2_worker()` (linea 541).

Dado el mejor combo de Sub-Phase 1 (que estrategias on, que modo de bankroll, que filtro de riesgo), ahora se optimizan los **ajustes realistas** del portfolio. Estos son filtros y correcciones que hacen la simulacion mas parecida a la realidad:

```
dedup:             [false, true]
   Deduplicacion: si en el mismo partido se generan 2 apuestas en el mismo
   mercado, quedarse solo con la primera.

min_odds:          [null, 1.15, 1.21]
   Cuota minima global (ademas de las individuales por estrategia).

max_odds:          [6.0, 7.0, 10.0]
   Cuota maxima global. Evita apostar a longshots excesivos.

slippage_pct:      [0, 2, 3.5]
   "Deslizamiento": en la realidad, puede que ejecutes la apuesta a una
   cuota ligeramente peor que la del backtest. 2% significa que las
   ganancias se reducen un 2%.

conflict_filter:   [false, true]
   Si un partido tiene apuesta de xG underperformance, eliminar la de
   momentum_xg (son contradictorias sobre el mismo partido).

allow_contrarias:  [true, false]
   Permitir apuestas contradictorias en match odds del mismo partido.
   Ejemplo: apostar al empate Y apostar al local. Si es false, solo
   se mantiene la primera.

min_stability:     [1, 2, 3]
   Numero minimo de capturas consecutivas con cuotas estables. Si la cuota
   cambio bruscamente, la senal puede ser espuria.

drift_min_minute:  [null, 15, 30]
   Minuto minimo para aceptar apuestas de odds_drift.

global_min/max:    [(null,null), (15,85), (20,80)]
   Rango global de minutos: solo aceptar apuestas entre estos minutos.
```

Total: 2 × 3 × 3 × 3 × 2 × 2 × 3 × 3 × 3 = **7,776 combinaciones**.

Cada una se aplica sobre las bets del combo ganador, se filtra por riesgo, se simula bankroll, y se puntua.

#### Sub-Phase 2.5: Desactivacion por descenso (steepest descent)

El codigo esta en `optimizer_cli.py`, funcion `_run_phase25()` (linea 422).

Sub-Phase 1 eligio que estrategias activar **sin considerar los adjustments**. Ahora que tenemos los adjustments optimos, puede que alguna estrategia ya no aporte al portfolio (porque sus bets son filtradas por los adjustments).

El algoritmo es iterativo:
1. Calcula el score actual del portfolio completo (con adjustments).
2. Para cada estrategia activa: "que pasaria si la apago?"
3. Si apagar alguna mejora el score: apaga la que mas mejora y repite.
4. Para cuando ninguna desactivacion mejora (o tras 5 iteraciones).

Si el combo cambio, se **re-ejecuta Sub-Phase 2** con el combo actualizado (Phase 2b) para re-optimizar los adjustments.

#### Sub-Phase 3: Rango de minutos para momentum (5 opciones)

El codigo esta en `optimizer_cli.py`, funcion `_find_best_momentum_range()` (linea 131).

Si la estrategia `momentum_xg` esta activa, prueba 5 rangos de minutos:
```
(0, 90)   — sin restriccion
(5, 85)   — evitar primeros/ultimos 5 min
(10, 80)  — evitar primeros/ultimos 10 min
(15, 75)  — evitar primeros/ultimos 15 min
(20, 70)  — evitar primeros/ultimos 20 min
```

Elige el rango que maximiza el score del portfolio.

#### Sub-Phase 4: Porcentaje de cashout (9 opciones)

El codigo esta en `optimizer_cli.py`, funcion `_find_best_co_pct()` (linea 152).

Prueba 9 niveles de cashout (cerrar la apuesta antes de que termine el partido):
```
[0, 5, 10, 15, 20, 25, 30, 40, 50] %
```

Cashout pct=20 significa: "si la cuota LAY llega a ser >= cuota BACK de entrada × 1.20, cierra la apuesta con beneficio parcial". Esto reduce las ganancias maximas pero tambien limita las perdidas.

Para cada nivel, llama a `simulate_cashout_cartera()` de csv_reader.py (explicada en seccion 15), que modifica el P/L de cada bet simulando el cierre anticipado.

#### Generacion del config final

El codigo esta en `optimizer_cli.py`, funcion `_build_preset_config()` (linea 192).

Con todos los resultados, construye un `cartera_config.json` completo:
- **Lee la config actual** como base (preserva todos los parametros individuales del grid search).
- **Aplica on/off** de las 7 estrategias segun el combo ganador.
- **Nunca re-habilita** una estrategia que fallo quality gates (por seguridad).
- **Aplica el rango de minutos** de momentum (Sub-Phase 3).
- **Aplica los adjustments** optimizados (Sub-Phase 2).
- **Aplica el cashout %** (Sub-Phase 4).
- Lo guarda como `preset_{criterio}_config.json`.

Tambien genera un CSV (`preset_{criterio}.csv`) con todas las apuestas del portfolio, con columnas detalladas para analisis externo.

---

## 9. Phase 4 — Elegir el mejor portfolio y aplicarlo

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `phase4_apply()` (linea 967).

### Que hace

Phase 3 genero 4 presets (max_roi, max_pl, max_wr, min_dd). Ahora hay que elegir cual aplicar. En vez de confiar en los scores internos del portfolio optimizer (que pueden estar inflados por los filtros), Phase 4 **re-evalua cada preset desde cero**.

### Paso a paso

1. **Para cada uno de los 4 presets**:
   a. Lee su fichero de configuracion (`preset_*_config.json`).
   b. Llama a `_eval_preset_real_stats()` (linea 931), que hace lo siguiente:
      - Toma la configuracion del preset y la aplica: para cada estrategia que el preset habilita, ejecuta `_analyze_strategy_simple()` con los parametros del preset.
      - Cuenta el total de apuestas, ganadas, P/L, calcula Wilson CI.
      - Esto produce **metricas honestas**: el resultado real que obtendrias si usaras esta configuracion.
   c. Verifica que pase dos quality gates de portfolio:
      - `N >= 200` (el portfolio debe generar al menos 200 apuestas — un portfolio con 50 bets es sospechosamente selectivo).
      - `ci_low >= 40%` (el limite inferior del intervalo de confianza del win rate debe ser al menos 40%).

2. **Puntua cada preset** segun el **selector** (un criterio de seleccion, por defecto `"robust"`):

   | Selector | Formula | Filosofia |
   |----------|---------|-----------|
   | `robust` (default) | `ci_low × wr × sqrt(N)` | El mas equilibrado: quiere calidad estadistica, buen win rate, Y volumen suficiente |
   | `confident_roi` | `ci_low × roi / 100` | ROI ajustado por confianza |
   | `max_wr` | `wr` | Puro win rate |
   | `max_roi` | `roi` | Puro retorno |
   | `max_pl` | `pl` | Puro beneficio absoluto |

3. **Elige el preset con mayor score** y lo aplica a `cartera_config.json`.

### El merge inteligente

La funcion `_merge_preset_strategies()` (linea 912) aplica el preset con cuidado:

- **Estrategia habilitada por el preset**: Se copian TODOS los parametros del preset (que ya incluyen los parametros individuales del grid search mas las decisiones del portfolio optimizer).
- **Estrategia deshabilitada por el preset**: Solo se cambia `enabled: false`. Los parametros optimizados del grid search se **preservan**. Asi, si en el futuro quieres re-habilitarla, ya tiene buenos parametros.
- **Estrategia que no existe en la config base**: Se ignora. Esto previene que un preset antiguo re-inserte estrategias que fueron eliminadas del codigo.

Antes de escribir, se hace un backup timestamped automatico.

---

## 10. Phase 5 — Exportar los resultados

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `phase5_export()` (linea 1053).

### Que hace

1. **Limpia las caches** (`_result_cache` y `_cartera_cache`). Esto fuerza a `analyze_cartera()` a re-evaluar con la configuracion final que se acaba de escribir en Phase 4.

2. **Ejecuta `analyze_cartera()`** (csv_reader.py, linea 891). Esta funcion es el "backtest oficial": lee la config, ejecuta TODAS las estrategias habilitadas, aplica deduplicacion de mercado, y devuelve la lista completa de apuestas del portfolio.

3. **Convierte timestamps** de UTC a hora local (GMT+1) para que las fechas sean legibles.

4. **Genera un CSV** con todas las apuestas, guardado en `analisis/bt_results_YYYYMMDD_HHMMSS.csv`. Las columnas son:
   ```
   fecha, match_id, match_name, strategy, strategy_label, strategy_desc,
   minuto, mercado, score_bet, score_final, back_odds, won, pl,
   Pais, Liga, timestamp_utc
   ```

5. **Genera un XLSX** (Excel) con 5 hojas:

   | Hoja | Que contiene |
   |------|-------------|
   | **Bets** | Las mismas columnas que el CSV — todas las apuestas una a una |
   | **Por Estrategia** | Un resumen por cada estrategia: cuantas apuestas, cuantas ganadas, %, P/L, ROI, intervalos de confianza |
   | **Acumulado** | El P/L acumulado bet a bet — sirve para hacer un grafico de "curva de equity" y ver si sube de forma constante o tiene rachas |
   | **Duplicados Mercado** | Detecta si alguna combinacion fecha+partido+mercado aparece mas de una vez (no deberia, gracias a la deduplicacion). Las filas con duplicados se resaltan en naranja |
   | **Por Dia** | Estadisticas agrupadas por fecha: cuantas apuestas ese dia, ganadas, P/L, ROI, intervalos de confianza |

---

## 11. Como funciona el motor que simula cada apuesta

### Donde esta el codigo

En `csv_reader.py`, la funcion `_analyze_strategy_simple()` (linea 470).

### Que es

Esta funcion es el corazon del backtest. Toma una estrategia y la ejecuta sobre todos los partidos historicos, simulando que habria pasado si hubieras apostado cada vez que la estrategia se activa.

### Parametros que recibe

```python
def _analyze_strategy_simple(key, trigger_fn, extractor_fn, win_fn, cfg, min_dur)
```

- **`key`**: El nombre de la estrategia, como `"cs_one_goal"` o `"back_draw_00"`. Se usa para etiquetar las apuestas resultantes.

- **`trigger_fn`**: La funcion que detecta si la condicion de apuesta se cumple. Es una de las 32 funciones `_detect_*_trigger()` de `strategy_triggers.py`. Recibe las filas del partido, la posicion actual, y la configuracion. Devuelve un diccionario con datos (cuotas, estadisticas) si la condicion se cumple, o `None` si no.

- **`extractor_fn`**: Una funcion que toma el diccionario devuelto por el trigger y extrae tres cosas: las cuotas de la apuesta, una descripcion legible ("BACK DRAW @ 3.50"), y un diccionario con datos de la condicion de entrada. Hay varias "fabricas" de extractores:
  - `_sd_fixed("back_draw", "BACK DRAW", [...])` — lee la cuota de una columna fija.
  - `_sd_score("BACK CS", [...])` — calcula la columna dinamicamente segun el score del trigger (para correct scores como 2-1, 1-0...).
  - `_sd_team("back_home", "back_away", "longshot_team", "BACK", [...])` — elige entre back_home o back_away segun el equipo.

- **`win_fn`**: Una funcion que determina si la apuesta gano. Recibe el diccionario del trigger y los goles finales del partido. Ejemplo: para una apuesta de empate, `lambda t, gl, gv: gl == gv` (gano si el resultado final fue empate).

- **`cfg`**: Los parametros de la estrategia (xg_max, minute_min, etc.), ya con los aliases en snake_case.

- **`min_dur`**: El numero de filas consecutivas que el trigger debe mantenerse activo antes de confirmar la apuesta. Esto simula la "persistencia": no queremos apostar por un spike de un segundo, queremos que la condicion se mantenga estable. `min_dur=2` significa que el trigger debe estar activo en 2 filas consecutivas (~2 minutos).

### El algoritmo, paso a paso

```
Para cada partido terminado:
  1. Obtener las filas del CSV (ya preprocesadas en Phase 0).
  2. Encontrar la fila del resultado final (goles_local, goles_visitante al final).
     Usa _final_result_row(): busca la primera fila con estado="finalizado" y
     scores validos. Si no hay, usa la ultima fila con scores numericos.
  3. Si no hay resultado final valido, saltar este partido.

  4. Inicializar contadores:
     first_seen = None    (indice de la primera fila donde el trigger se activo)
     trig_data = None     (datos del trigger en esa primera activacion)

  5. Recorrer TODAS las filas del partido, de la primera a la ultima:
     Para la fila actual (curr_idx):

       a) Llamar a trigger_fn(rows, curr_idx, cfg).

       b) Si el trigger se ACTIVA (devuelve un diccionario, no None):
          - Si es la primera vez (first_seen es None):
            Registrar: first_seen = curr_idx, trig_data = trigger result
          - Comprobar: han pasado min_dur filas desde first_seen?
            (curr_idx >= first_seen + min_dur - 1)
          - Si SI han pasado min_dur filas:
            *** CONFIRMAR LA APUESTA ***
            i.   Extraer cuotas: extractor_fn(trig) → (odds, rec, entry)
            ii.  Si las cuotas no estan disponibles (None): parar este partido.
            iii. Determinar si gano: win_fn(trig, ft_goles_local, ft_goles_visitante)
            iv.  Calcular el P/L:
                 - Si es BACK y gano: (cuota - 1) × 0.95
                   (ganas cuota-1 por unidad apostada, menos 5% comision Betfair)
                 - Si es BACK y perdio: -1.0
                   (pierdes toda la apuesta)
                 - Si es LAY y gano: +0.95
                   (recibes el stake del otro apostador, menos 5% comision)
                 - Si es LAY y perdio: -(cuota - 1)
                   (pagas al otro apostador la cuota-1 por unidad)
            v.   Registrar la bet con todos los datos.
            vi.  PARAR: no buscar mas apuestas en este partido para esta estrategia.

       c) Si el trigger NO se activa (devuelve None):
          - Reset: first_seen = None, trig_data = None
          - El contador de persistencia se reinicia a cero.
```

### Puntos importantes

**Una sola apuesta por partido**: El `break` despues de registrar la bet asegura que cada estrategia genera como maximo una apuesta por partido. Esto evita sobreexposicion.

**El reset es estricto**: Si el trigger se activa durante 3 filas pero luego se desactiva 1 fila y vuelve a activarse, el contador empieza de cero. La condicion debe ser ininterrumpida durante `min_dur` filas.

**Las cuotas son del momento de confirmacion**: Cuando se extrae la cuota, se usa el diccionario del trigger en la fila de confirmacion (no de la primera activacion). Esto refleja la realidad: entras al mercado cuando confirmas la senal, no cuando la ves por primera vez.

**El 0.95**: Betfair cobra una comision del 5% sobre las ganancias netas. El `0.95` refleja que de cada libra que ganas, te quedas con 95 peniques.

---

## 12. Que es un trigger y como funcionan los 32

### Donde esta el codigo

En `strategy_triggers.py`. Todas las funciones siguen exactamente la misma interfaz:

```python
def _detect_<nombre>_trigger(rows: list, curr_idx: int, cfg: dict) -> dict | None
```

### Que reciben

- **`rows`**: Todas las filas del CSV del partido (una lista de diccionarios). Cada diccionario tiene claves como `"minuto"`, `"goles_local"`, `"back_draw"`, `"xg_local"`, etc.
- **`curr_idx`**: El indice de la fila que estamos evaluando ahora.
- **`cfg`**: Los parametros de la estrategia (umbrales, limites).

### Que devuelven

- Un **diccionario con datos** si las condiciones se cumplen. Este diccionario incluye las cuotas de la apuesta, las estadisticas relevantes, y cualquier dato que el extractor necesite.
- **`None`** si las condiciones no se cumplen.

### Regla de oro

El trigger **solo puede mirar `rows[0]` a `rows[curr_idx]`**. Nunca puede mirar filas futuras. Esto es critico: si un trigger mirara el resultado final del partido para decidir si apostar, el backtest seria fraudulento. El trigger debe tomar su decision con la informacion disponible en ese momento, exactamente como lo haria en vivo.

### Ejemplo completo: `_detect_back_draw_00_trigger`

Esta funcion decide si apostar al empate cuando el partido va 0-0:

```
1. Leer el minuto actual. Si no hay minuto (fila sin dato), devolver None.
2. Si el minuto < minute_min (configurado, ej: 30), devolver None.
   (Muy pronto, no queremos apostar en el minuto 5.)
3. Si el minuto >= minute_max (configurado, ej: 90), devolver None.
   (Muy tarde.)
4. Leer goles local y visitante. Si no son ambos 0, devolver None.
   (Solo queremos 0-0.)
5. Leer xG total (xg_local + xg_visitante).
6. Leer diferencia de posesion (|posesion_local - posesion_visitante|).
7. Leer tiros totales.
8. Llamar a _detect_draw_filters() que comprueba:
   - xG total <= xg_max? (si xG es alto, los equipos crean mucho, riesgo de gol)
   - Diferencia de posesion <= poss_max? (si uno domina mucho, puede marcar)
   - Tiros totales <= shots_max? (muchos tiros = riesgo de gol)
9. Si todas las condiciones se cumplen, devolver el diccionario con:
   {minuto, xg_total, poss_diff, shots_total, back_draw (la cuota del empate), ...}
10. Si alguna falla, devolver None.
```

### Otro ejemplo: `_detect_cs_one_goal_trigger`

Decide si apostar al correct score actual cuando un equipo lleva ventaja de 1 gol (1-0 o 0-1):

```
1. Comprobar minuto en rango [m_min, m_max].
2. Comprobar que el marcador es 1-0 o 0-1.
3. Comprobar que la cuota del correct score actual esta disponible
   y dentro del rango [odds_min, odds_max].
4. Si todo ok: devolver {score: "1-0", back_rc_1_0: cuota, ...}
```

### Dato clave: el mismo trigger se usa en backtest Y en vivo

La magia del diseno es que estas funciones se llaman igual desde el backtest (iterando fila por fila) y desde el sistema en vivo (evaluando solo la ultima fila disponible). Asi se garantiza que lo que el backtest simula es exactamente lo que el sistema haría en tiempo real.

---

## 13. Las puertas de calidad que debe pasar cada estrategia

### Donde esta el codigo

En `bt_optimizer.py`, la funcion `_eval_bets()` (linea 342) y las constantes en lineas 74-78.

### Que son las puertas de calidad (quality gates)

Son filtros estadisticos que una estrategia debe pasar para ser considerada "apta". Previenen incluir estrategias que parezcan rentables por azar pero que en realidad no tienen ventaja real.

### Las cuatro puertas

**Puerta 1: Numero minimo de apuestas (N >= formula dinamica)**

```python
N minimo = max(15, numero_de_partidos // 25)
```

Con 1200 partidos: `max(15, 1200 // 25) = max(15, 48) = 48`.

Razon: Si una estrategia solo genera 10 apuestas en 1200 partidos, aunque gane 9 de 10, ese resultado no es estadisticamente significativo. Podria ser suerte. Necesitamos una muestra razonable. El umbral crece con el dataset: cuantos mas partidos tenemos, mas exigentes somos.

**Puerta 2: ROI minimo (>= 10%)**

```python
ROI = (P/L total / N) × 100
```

ROI del 10% significa que por cada unidad apostada, ganas 0.10 de media. Si tienes 100 apuestas de 1 unidad, has ganado 10 unidades.

Razon: Una estrategia con ROI del 2% probablemente no cubra los costes reales (slippage, latencia, etc.). El 10% da un margen de seguridad.

**Puerta 3: P/L por apuesta minimo (>= 0.15 unidades)**

```python
P/L por bet = P/L total / N
```

Similar al ROI pero medido en unidades absolutas, no en porcentaje. Filtra estrategias de bajo riesgo/recompensa que ganan muchas veces pero poquito.

**Puerta 4: Intervalo de confianza Wilson (limite inferior >= 40%)**

Esta es la puerta mas sofisticada. El **intervalo de confianza Wilson al 95%** calcula un rango dentro del cual podemos estar 95% seguros de que se encuentra el win rate verdadero.

Ejemplo: Si tienes 60 wins de 100 bets (WR=60%), el intervalo Wilson podria ser [50.1%, 69.2%]. El limite inferior (50.1%) dice: "con 95% de confianza, tu win rate real es al menos 50.1%".

La puerta exige que ese limite inferior sea >= 40%. Esto filtra:
- Estrategias con pocos bets (el intervalo es ancho → limite inferior bajo).
- Estrategias con win rate cercano al 50% (pueden ser aleatorias).

La formula Wilson es preferible al intervalo normal porque funciona bien con muestras pequenas y proporciones extremas.

### Si no pasa alguna puerta

La funcion devuelve `None`, y esa combinacion de parametros se descarta silenciosamente. Solo las combinaciones que pasan las 4 puertas son candidatas a "mejor".

---

## 14. Deduplicacion: no apostar dos veces en lo mismo

### Donde esta el codigo

En `csv_reader.py`, funcion `_normalize_mercado()` (linea 392) y dentro de `analyze_cartera()` (lineas 924-940).

### El problema

Imagina este escenario: en el mismo partido, la estrategia `draw_11` detecta que hay que apostar al DRAW, y la estrategia `draw_xg_conv` tambien detecta que hay que apostar al DRAW. En la realidad, solo puedes entrar una vez en el mercado DRAW de ese partido.

Otro ejemplo: `under35_late` y `under35_3goals` ambas apuestan al Under 3.5 Goals en el mismo partido.

Sin deduplicacion, el backtest contaria dos apuestas donde en realidad solo habria una.

### Como se resuelve

Despues de generar TODAS las apuestas de TODAS las estrategias (en `analyze_cartera()`):

1. Se ordenan las apuestas por minuto (la que se dispara primero va primera).

2. Para cada apuesta, se normaliza su campo `mercado` a una clave canonica usando `_normalize_mercado()`. Esta funcion lee el texto del mercado (como "BACK DRAW" o "BACK OVER 2.5" o "BACK CS 2-1") y lo convierte a una clave simple:
   ```
   "BACK DRAW"         → "draw"
   "BACK HOME"         → "home"
   "BACK AWAY"         → "away"
   "BACK CS 2-1"       → "cs_2_1"
   "BACK UNDER 3.5"    → "under_3.5"
   "BACK OVER 2.5"     → "over_2.5"
   ```

3. Se crea una clave de deduplicacion: `(match_id, mercado_normalizado)`.

4. **La primera apuesta que llega (la de menor minuto) se queda; las demas se descartan.**

### El efecto practico

En el dataset de ~1200 partidos, la deduplicacion reduce el portfolio de ~1727 a ~1655 apuestas (unas 70 apuestas duplicadas eliminadas).

### Alineamiento con el sistema en vivo

El sistema en vivo (LIVE) usa la misma logica de deduplicacion, implementada en `_live_market_key()` de `analytics.py`. Asi, BT y LIVE aplican los mismos limites.

---

## 15. Simulacion de cashout

### Donde esta el codigo

En `csv_reader.py`, la funcion `simulate_cashout_cartera()` (linea 1291).

### Que es el cashout

En Betfair Exchange, puedes cerrar una apuesta antes de que termine el partido. Si apostaste BACK DRAW a cuota 3.50 y la cuota del empate baja a 2.0 (porque el partido sigue 0-0 y queda poco tiempo), puedes hacer LAY DRAW a 2.0 y asegurar un beneficio parcial sin esperar al final.

El cashout es util para:
- Asegurar beneficios parciales cuando la situacion es favorable.
- Limitar perdidas cuando la situacion se deteriora.

### Para que se simula

La simulacion de cashout se usa en el portfolio optimizer (Phase 3, Sub-Phase 4) para encontrar el mejor porcentaje de cashout. Pero tambien se puede ejecutar independientemente para analisis.

### Como funciona

Para cada apuesta del portfolio, busca en el CSV del partido las filas posteriores al trigger y aplica el modo de cashout seleccionado. Si se dispara el cashout, recalcula el P/L basandose en las cuotas de cierre (no en el resultado final).

### Modos de cashout disponibles

| Modo | Como funciona |
|------|--------------|
| **Pesimista** (`cashout_minute=-1`) | Busca la PEOR cuota LAY en todo el periodo post-trigger. Modela la peor ejecucion posible — muy conservador. |
| **Minuto fijo** (`cashout_minute=N`) | Cierra en la fila mas cercana al minuto N. Simple pero rigido. |
| **Lay %** (`cashout_lay_pct=20`) | Cierra cuando la cuota LAY >= cuota BACK de entrada × 1.20. Es decir, cuando puedes cerrar con al menos un 20% de "colchon" sobre tu entrada. |
| **Adaptativo** (`adaptive_early/late_pct`) | Dos umbrales diferentes: uno mas holgado antes de cierto minuto, y uno mas ajustado despues. Ejemplo: 30% antes del minuto 70, 15% despues. |
| **Gol adverso** (`adverse_goal_stop`) | Cierra inmediatamente cuando se produce un gol que perjudica la apuesta (solo para apuestas de match odds, no de Over/Under). |
| **Trailing stop** (`trailing_stop_pct`) | Un stop que se mueve: trackea la cuota LAY minima vista, y cierra cuando sube un X% sobre ese minimo. |

Los modos son **combinables**: si activas varios, el primero que se dispara gana.

---

## 16. El fichero de configuracion central

### Donde esta

`betfair_scraper/cartera_config.json`

### Que contiene

Es un fichero JSON con cuatro secciones principales:

**1. Ajustes generales:**
```json
{
  "bankroll_mode": "fixed",       // Como gestionar el bankroll
  "active_preset": "max_roi",     // Que preset esta activo (informativo)
  "risk_filter": "all",           // Filtro de riesgo
  ...
}
```

**2. Duracion minima por estrategia (`min_duration`):**
```json
{
  "min_duration": {
    "back_draw_00": 2,             // 2 filas consecutivas de confirmacion
    "xg_underperformance": 3,      // 3 filas
    "goal_clustering": 4,          // 4 filas
    ...
  }
}
```

Esto controla el `min_dur` del motor de backtest (y del sistema en vivo). Un valor de 2 significa que el trigger debe mantenerse activo durante 2 capturas consecutivas (~2 minutos) antes de apostar.

**3. Ajustes realistas (`adjustments`):**
```json
{
  "adjustments": {
    "enabled": true,
    "dedup": false,                // Deduplicacion de mercado (ya aplicada en BT)
    "max_odds": null,              // Cuota maxima global
    "min_odds": null,              // Cuota minima global
    "slippage_pct": 0,             // Deslizamiento simulado
    "conflict_filter": false,      // Filtro de conflictos
    "allow_contrarias": true,      // Permitir apuestas contradictorias
    "stability": 1,                // Estabilidad minima de cuotas
    "cashout_pct": 0,              // Porcentaje de cashout
    ...
  }
}
```

Estos son los ajustes que el portfolio optimizer encuentra en Sub-Phase 2.

**4. Las 32 estrategias (`strategies`):**
```json
{
  "strategies": {
    "cs_one_goal": {
      "enabled": true,              // Activa o no
      "minuteMin": 68,              // Desde que minuto
      "minuteMax": 90,              // Hasta que minuto
      "oddsMin": 3.0,               // Cuota minima
      "oddsMax": 999                // Cuota maxima
    },
    "back_draw_00": {
      "enabled": false,             // Desactivada (no paso quality gates)
      "xgMax": 0.6,                 // Parametros preservados por si se reactiva
      "possMax": 20,
      ...
    }
  }
}
```

### Ciclo de vida durante el backtest

1. **Al inicio** (Phase 0-1): Se lee para obtener `min_duration` de cada estrategia.
2. **Phase 2**: Se escribe la seccion `strategies` con los parametros ganadores del grid search.
3. **Phase 3**: Se escribe como "staging config" antes de ejecutar el portfolio optimizer.
4. **Phase 4**: Se sobreescribe con el preset ganador (merge inteligente).
5. **Despues del backtest**: El sistema en vivo lee esta configuracion para saber que estrategias estan activas y con que parametros.

---

## 17. Como se relaciona el backtest con el sistema en vivo

### El diseno central

El backtest y el sistema en vivo usan **exactamente el mismo codigo** de deteccion. No hay dos implementaciones separadas que puedan divergir.

| Componente | En backtest | En vivo |
|------------|-------------|---------|
| **Funcion de deteccion** | `trigger_fn(rows, curr_idx, cfg)` iterando `curr_idx` de 0 a N | `trigger_fn(rows, len(rows)-1, cfg)` — solo la ultima fila |
| **Configuracion** | Lee `cartera_config.json` | Lee `cartera_config.json` — el mismo fichero |
| **Traduccion de parametros** | `_cfg_add_snake_keys()` | `_cfg_add_snake_keys()` — la misma funcion |
| **Motor** | `_analyze_strategy_simple()` | `detect_betting_signals()` |
| **Deduplicacion** | `_normalize_mercado()` en `analyze_cartera()` | `_live_market_key()` en `analytics.py` |
| **Persistencia (min_dur)** | Filas consecutivas en el CSV | Filas consecutivas acumuladas |

### Como se mide el alineamiento

El fichero `tests/reconcile.py` simula el sistema en vivo procesando cada partido fila por fila (como lo haria el scraper) y compara los resultados con los del backtest. El resultado: **97.3% de coincidencia** (y 97.7% contando diferencias de timing de 1-2 minutos).

Las discrepancias restantes se deben a:
- Filas con scores nulos en medio del CSV (el BT salta la fila, el LIVE podria no verla).
- Diferencias de 1-2 minutos en el momento exacto de deteccion.
- Partidos sin resultado final valido.

### El backtest es conservador

El P/L del backtest tiende a ser **menor o igual** que el del sistema en vivo, porque usa una funcion `conservative_odds` que toma las cuotas mas conservadoras disponibles en la ventana de datos. En vivo, ejecutas a la cuota del momento, que puede ser mejor.

---

## 18. Las 32 estrategias

| # | Nombre | Mercado | Tipo | Que detecta |
|---|--------|---------|------|-------------|
| 1 | `over25_2goal` | Over 2.5 | BACK | Un equipo lidera por 2+ goles y hay actividad de tiros a puerta |
| 2 | `under35_late` | Under 3.5 | BACK | Van 3 goles exactos tarde en el partido y el xG es bajo (improbable un 4to gol) |
| 3 | `longshot` | Home/Away | BACK | El equipo menos favorito antes del partido esta ganando tarde |
| 4 | `cs_close` | Correct Score | BACK | El marcador es ajustado (2-1 o 1-2) tarde — apuesta a que no cambia |
| 5 | `cs_one_goal` | Correct Score | BACK | El marcador es 1-0 o 0-1 — apuesta a que termina asi |
| 6 | `ud_leading` | Home/Away | BACK | El underdog lidera tarde |
| 7 | `home_fav_leading` | Home | BACK | El favorito local lidera tarde |
| 8 | `cs_20` | Correct Score | BACK | El marcador es 2-0 o 0-2 — apuesta a que termina asi |
| 9 | `cs_big_lead` | Correct Score | BACK | Ventaja grande (3-0, 0-3, 3-1, 1-3) |
| 10 | `lay_over45_v3` | Over 4.5 | LAY | Pocos goles y ventana ajustada — apuesta EN CONTRA de 5+ goles |
| 11 | `draw_xg_conv` | Draw | BACK | El xG converge en partido empatado — senal de que el empate se mantiene |
| 12 | `poss_extreme` | Over 0.5 | BACK | Posesion extremadamente desigual en 0-0 — acabara cayendo un gol |
| 13 | `cs_00` | CS 0-0 | BACK | Partido early con xG y SoT muy bajos — puede terminar 0-0 |
| 14 | `over25_2goals` | Over 2.5 | BACK | Van exactamente 2 goles en fila estable |
| 15 | `draw_11` | Draw | BACK | Marcador 1-1 tarde — apuesta a que sigue asi |
| 16 | `under35_3goals` | Under 3.5 | BACK | Van 3 goles, xG bajo — no habra un 4to |
| 17 | `away_fav_leading` | Away | BACK | El favorito visitante va ganando tarde |
| 18 | `under45_3goals` | Under 4.5 | BACK | Van 3 goles, xG bajo — no habra un 5to |
| 19 | `cs_11` | CS 1-1 | BACK | Marcador 1-1 tarde — correct score |
| 20 | `draw_equalizer` | Draw | BACK | El underdog acaba de empatar al favorito — inercia de empate |
| 21 | `draw_22` | Draw | BACK | Marcador 2-2 tarde |
| 22 | `lay_over45_blowout` | Over 4.5 | LAY | Goleada (3-0/0-3) y el ganador baja intensidad — no habra mas goles |
| 23 | `over35_early_goals` | Over 3.5 | BACK | Van 3 goles antes del min 65 — ritmo alto, probable 4to gol |
| 24 | `lay_draw_away_leading` | Draw | LAY | El visitante va ganando y el local genera poco xG — dificil que empaten |
| 25 | `lay_cs11` | CS 1-1 | LAY | Marcador 0-1 tarde — el mercado sobrevalora el 1-1, en realidad solo pasa el 4% |
| 26 | `back_draw_00` | Draw | BACK | Partido 0-0 con xG bajo, posesion equilibrada, pocos tiros |
| 27 | `odds_drift` | Home/Away | BACK | Un equipo cuyas cuotas suben (el mercado pierde confianza) — contrarian bet |
| 28 | `momentum_xg` | Home/Away | BACK | Equipo que domina en xG y SoT pero no ha convertido |
| 29 | `pressure_cooker` | Over N.5 | BACK | Empate con goles (1-1+) entre min 65-75 — olla a presion de goles |
| 30 | `goal_clustering` | Over N.5 | BACK | Hubo un gol reciente y hay actividad de SoT — "los goles vienen en racimos" |
| 31 | `xg_underperformance` | Over N.5 | BACK | Un equipo genera mucho xG pero pierde — el gol "esta por venir" |
| 32 | `tarde_asia` | Over 2.5 | BACK | Liga asiatica o de alta goleada antes del minuto 15 |

---

## Apendice: Como ejecutar el backtest

```bash
# Ejecutar todas las fases (tarda ~30-45 minutos)
python scripts/bt_optimizer.py

# Solo optimizar estrategias individuales (Phase 0+1+2+2.5)
python scripts/bt_optimizer.py --phase individual

# Solo generar portfolios (Phase 3, requiere --phase individual previo)
python scripts/bt_optimizer.py --phase presets

# Aplicar el mejor portfolio (Phase 4)
python scripts/bt_optimizer.py --phase apply --criterion robust

# Exportar resultados (Phase 5)
python scripts/bt_optimizer.py --phase export

# Modo seguro: no modifica cartera_config.json
python scripts/bt_optimizer.py --dry-run

# Mas paralelismo para Phase 3
python scripts/bt_optimizer.py --workers 8

# Saltar la validacion de robustez (Phase 2.5)
python scripts/bt_optimizer.py --no-crossval

# Solo optimizar estrategias especificas
python scripts/bt_optimizer.py --phase individual --strategies "cs_one_goal,draw_11"
```
