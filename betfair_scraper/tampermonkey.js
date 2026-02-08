// ==UserScript==
// @name         Betfair Exchange Odds Observer
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Captura cuotas back/lay de Betfair Exchange cada 60s.
//               Sincroniza datos cross-tab con GM_storage. Exporta CSV.
// @author       Football_Predictions
// @match        https://www.betfair.es/exchange/*
// @match        https://www.betfair.com/exchange/*
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_listValues
// @grant        GM_deleteValue
// @grant        GM_addStyle
// @grant        GM_notification
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    // ══════════════════════════════════════════════════════════════════════
    // CONFIGURACIÓN
    // ══════════════════════════════════════════════════════════════════════
    const CONFIG = {
        INTERVALO_CAPTURA_MS: 60000,    // Captura cada 60 segundos
        INTERVALO_EXPORT_MS: 600000,    // Auto-exportar CSV cada 10 minutos
        MAX_REGISTROS_MEMORIA: 5000,    // Máximo registros en memoria por pestaña
        LOG_CONSOLA: true,              // Mostrar logs en consola
        PREFIJO_STORAGE: 'bf_obs_',     // Prefijo para claves GM_storage
    };

    // ══════════════════════════════════════════════════════════════════════
    // UTILIDADES
    // ══════════════════════════════════════════════════════════════════════

    /** Genera un ID único para esta pestaña basado en la URL */
    function obtenerIdPartido() {
        const url = window.location.href;
        // Betfair usa IDs numéricos en la URL del evento
        const match = url.match(/\/(\d{7,12})(?:\?|$|#)/);
        if (match) return match[1];
        // Fallback: hash de la URL
        const partes = url.replace(/[?#].*$/, '').split('/');
        return partes[partes.length - 1] || 'desconocido';
    }

    /** Timestamp UTC en formato ISO */
    function timestampUTC() {
        return new Date().toISOString().replace('T', ' ').substring(0, 19);
    }

    /** Log con prefijo visual */
    function log(msg, nivel = 'info') {
        if (!CONFIG.LOG_CONSOLA) return;
        const prefijo = `[BF-Observer ${obtenerIdPartido()}]`;
        const metodo = nivel === 'error' ? 'error' : nivel === 'warn' ? 'warn' : 'log';
        console[metodo](`%c${prefijo} ${msg}`, 'color: #2ecc71; font-weight: bold;');
    }

    /** Limpia texto de precio */
    function limpiarPrecio(texto) {
        if (!texto) return '';
        texto = texto.trim().replace(',', '.').replace(/\s/g, '');
        const num = parseFloat(texto);
        return isNaN(num) ? '' : num.toString();
    }

    // ══════════════════════════════════════════════════════════════════════
    // SELECTORES CSS (múltiples variantes para robustez)
    // ══════════════════════════════════════════════════════════════════════
    const SEL = {
        // Filas de runners
        runnerRow: [
            'tr.runner-line',
            '[data-testid="runner-row"]',
            '.mv-runner',
            '.runner-line',
        ],
        // Nombre del runner
        runnerName: [
            '.runner-name',
            '[data-testid="runner-name"]',
            '.mv-runner-name',
        ],
        // Precio back
        backPrice: [
            'td.bet-buttons.back-cell button.bet-button-price',
            '[data-testid="back-button-price"]',
            '.mv-bet-button-back .bet-button-price',
            '.back-selection-button .bet-button-price',
        ],
        // Precio lay
        layPrice: [
            'td.bet-buttons.lay-cell button.bet-button-price',
            '[data-testid="lay-button-price"]',
            '.mv-bet-button-lay .bet-button-price',
            '.lay-selection-button .bet-button-price',
        ],
        // Tiempo del partido
        matchTime: [
            '.elapsed-time',
            '.event-header .time',
            '.inplay-indicator .time',
        ],
        // Marcador
        matchScore: [
            '.score',
            '.event-header .score-home',
            '.event-header .score-away',
        ],
        // Evento nombre
        eventName: [
            '.event-header .title',
            '.event-name',
            'h1.event-name',
        ],
        // Volumen matched
        matchedAmount: [
            '.matched-amount .size-value',
            '.total-matched .matched-value',
            '[data-testid="matched-amount"]',
            '.mv-matched-amount',
        ],
        // Contenedores de mercado
        marketContainer: [
            '.market-container',
            '.mv-market',
            '[data-testid="market"]',
        ],
    };

    /** Intenta encontrar un elemento usando múltiples selectores */
    function buscarElemento(selectores, contexto = document) {
        for (const sel of selectores) {
            const elem = contexto.querySelector(sel);
            if (elem) return elem;
        }
        return null;
    }

    /** Intenta encontrar todos los elementos usando múltiples selectores */
    function buscarTodos(selectores, contexto = document) {
        for (const sel of selectores) {
            const elems = contexto.querySelectorAll(sel);
            if (elems.length > 0) return Array.from(elems);
        }
        return [];
    }

    /** Obtiene texto de un elemento encontrado con selectores múltiples */
    function obtenerTexto(selectores, contexto = document) {
        const elem = buscarElemento(selectores, contexto);
        return elem ? elem.textContent.trim() : '';
    }

    // ══════════════════════════════════════════════════════════════════════
    // EXTRACCIÓN DE DATOS
    // ══════════════════════════════════════════════════════════════════════

    /** Extrae cuotas Match Odds (3 runners) */
    function extraerMatchOdds() {
        const resultado = {
            back_home: '', lay_home: '',
            back_draw: '', lay_draw: '',
            back_away: '', lay_away: '',
        };

        const runners = buscarTodos(SEL.runnerRow);
        if (runners.length < 3) {
            log('No se encontraron 3 runners para Match Odds', 'warn');
            return resultado;
        }

        const claves = [
            ['back_home', 'lay_home'],
            ['back_draw', 'lay_draw'],
            ['back_away', 'lay_away'],
        ];

        for (let i = 0; i < Math.min(3, runners.length); i++) {
            const row = runners[i];
            const [keyBack, keyLay] = claves[i];

            const backElem = buscarElemento(SEL.backPrice, row);
            if (backElem) resultado[keyBack] = limpiarPrecio(backElem.textContent);

            const layElem = buscarElemento(SEL.layPrice, row);
            if (layElem) resultado[keyLay] = limpiarPrecio(layElem.textContent);
        }

        return resultado;
    }

    /** Extrae cuotas Over/Under 2.5 */
    function extraerOverUnder() {
        const resultado = {
            back_over25: '', lay_over25: '',
            back_under25: '', lay_under25: '',
        };

        // Buscar en mercados que contengan "Over/Under" o "Más/Menos"
        const mercados = buscarTodos(SEL.marketContainer);
        for (const mercado of mercados) {
            const texto = mercado.textContent.toLowerCase();
            if (texto.includes('over') || texto.includes('under') || texto.includes('más')) {
                const runners = buscarTodos(SEL.runnerRow, mercado);
                if (runners.length >= 2) {
                    const claves = [
                        ['back_over25', 'lay_over25'],
                        ['back_under25', 'lay_under25'],
                    ];
                    for (let j = 0; j < Math.min(2, runners.length); j++) {
                        const [keyB, keyL] = claves[j];
                        const backEl = buscarElemento(SEL.backPrice, runners[j]);
                        if (backEl) resultado[keyB] = limpiarPrecio(backEl.textContent);
                        const layEl = buscarElemento(SEL.layPrice, runners[j]);
                        if (layEl) resultado[keyL] = limpiarPrecio(layEl.textContent);
                    }
                    if (Object.values(resultado).some(v => v !== '')) return resultado;
                }
            }
        }

        return resultado;
    }

    /** Extrae info del estado del partido */
    function extraerInfoPartido() {
        const info = { evento: '', minuto: '', goles_local: '', goles_visitante: '' };

        info.evento = obtenerTexto(SEL.eventName);

        const tiempoTxt = obtenerTexto(SEL.matchTime);
        if (tiempoTxt) {
            const match = tiempoTxt.match(/(\d+)/);
            if (match) info.minuto = match[1];
        }

        const scoreTxt = obtenerTexto(SEL.matchScore);
        if (scoreTxt) {
            const match = scoreTxt.match(/(\d+)\s*[-:]\s*(\d+)/);
            if (match) {
                info.goles_local = match[1];
                info.goles_visitante = match[2];
            }
        }

        return info;
    }

    /** Extrae volumen matched */
    function extraerVolumen() {
        const texto = obtenerTexto(SEL.matchedAmount);
        if (!texto) return '';
        return texto.replace(/[€$£\s,.]/g, '');
    }

    /** Captura completa de datos de la pestaña actual */
    function capturarDatos() {
        const id = obtenerIdPartido();
        const info = extraerInfoPartido();
        const matchOdds = extraerMatchOdds();
        const overUnder = extraerOverUnder();
        const volumen = extraerVolumen();

        const registro = {
            tab_id: id,
            timestamp_utc: timestampUTC(),
            evento: info.evento,
            minuto: info.minuto,
            goles_local: info.goles_local,
            goles_visitante: info.goles_visitante,
            ...matchOdds,
            ...overUnder,
            volumen_matched: volumen,
            url: window.location.href,
        };

        log(
            `Captura: ${info.evento || id} | ` +
            `Min:${info.minuto || '?'} | ` +
            `${info.goles_local || '?'}-${info.goles_visitante || '?'} | ` +
            `BH:${matchOdds.back_home || '-'} LH:${matchOdds.lay_home || '-'}`
        );

        return registro;
    }

    // ══════════════════════════════════════════════════════════════════════
    // ALMACENAMIENTO Y SINCRONIZACIÓN
    // ══════════════════════════════════════════════════════════════════════

    const STORAGE_KEY = CONFIG.PREFIJO_STORAGE + obtenerIdPartido();

    /** Guarda registro en GM_storage */
    async function guardarRegistro(registro) {
        try {
            let datos = await GM_getValue(STORAGE_KEY, []);
            if (!Array.isArray(datos)) datos = [];

            datos.push(registro);

            // Limitar tamaño en memoria
            if (datos.length > CONFIG.MAX_REGISTROS_MEMORIA) {
                datos = datos.slice(-CONFIG.MAX_REGISTROS_MEMORIA);
            }

            await GM_setValue(STORAGE_KEY, datos);
            log(`Guardado. Total registros para ${obtenerIdPartido()}: ${datos.length}`);
        } catch (e) {
            log(`Error guardando: ${e.message}`, 'error');
            // Fallback: localStorage
            guardarEnLocalStorage(registro);
        }
    }

    /** Fallback: guardar en localStorage */
    function guardarEnLocalStorage(registro) {
        const key = 'bf_observer_' + obtenerIdPartido();
        let datos = [];
        try {
            datos = JSON.parse(localStorage.getItem(key) || '[]');
        } catch (e) { /* ignorar */ }
        datos.push(registro);
        if (datos.length > CONFIG.MAX_REGISTROS_MEMORIA) {
            datos = datos.slice(-CONFIG.MAX_REGISTROS_MEMORIA);
        }
        localStorage.setItem(key, JSON.stringify(datos));
    }

    /** Obtiene todos los datos almacenados (cross-tab) */
    async function obtenerTodosDatos() {
        const todosLosDatos = {};
        try {
            const claves = await GM_listValues();
            for (const clave of claves) {
                if (clave.startsWith(CONFIG.PREFIJO_STORAGE)) {
                    const partidoId = clave.replace(CONFIG.PREFIJO_STORAGE, '');
                    todosLosDatos[partidoId] = await GM_getValue(clave, []);
                }
            }
        } catch (e) {
            log(`Error leyendo almacenamiento: ${e.message}`, 'error');
        }
        return todosLosDatos;
    }

    // ══════════════════════════════════════════════════════════════════════
    // EXPORTACIÓN CSV
    // ══════════════════════════════════════════════════════════════════════

    const CSV_COLUMNS = [
        'tab_id', 'timestamp_utc', 'evento', 'minuto',
        'goles_local', 'goles_visitante',
        'back_home', 'lay_home', 'back_draw', 'lay_draw',
        'back_away', 'lay_away',
        'back_over25', 'lay_over25', 'back_under25', 'lay_under25',
        'volumen_matched', 'url',
    ];

    /** Convierte array de objetos a CSV string */
    function generarCSV(registros) {
        const escape = (val) => {
            const str = String(val || '');
            if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                return '"' + str.replace(/"/g, '""') + '"';
            }
            return str;
        };

        const lineas = [CSV_COLUMNS.join(',')];
        for (const reg of registros) {
            const fila = CSV_COLUMNS.map(col => escape(reg[col]));
            lineas.push(fila.join(','));
        }
        return lineas.join('\n');
    }

    /** Descarga un archivo CSV */
    function descargarCSV(contenido, nombre) {
        const blob = new Blob(['\uFEFF' + contenido], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = nombre;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        log(`CSV descargado: ${nombre}`);
    }

    /** Exporta CSV unificado con datos de todas las pestañas */
    async function exportarCSVUnificado() {
        const todosDatos = await obtenerTodosDatos();
        const todosRegistros = [];
        for (const datos of Object.values(todosDatos)) {
            todosRegistros.push(...datos);
        }

        if (todosRegistros.length === 0) {
            log('No hay datos para exportar', 'warn');
            return;
        }

        // Ordenar por timestamp
        todosRegistros.sort((a, b) => a.timestamp_utc.localeCompare(b.timestamp_utc));

        const csv = generarCSV(todosRegistros);
        const fecha = new Date().toISOString().substring(0, 10);
        descargarCSV(csv, `betfair_odds_${fecha}.csv`);
    }

    /** Exporta CSV solo del partido actual */
    async function exportarCSVPartido() {
        const datos = await GM_getValue(STORAGE_KEY, []);
        if (datos.length === 0) {
            log('No hay datos para este partido', 'warn');
            return;
        }
        const csv = generarCSV(datos);
        const id = obtenerIdPartido();
        descargarCSV(csv, `betfair_${id}_${timestampUTC().replace(/[: ]/g, '-')}.csv`);
    }

    // ══════════════════════════════════════════════════════════════════════
    // PANEL DE CONTROL (UI)
    // ══════════════════════════════════════════════════════════════════════

    function crearPanel() {
        GM_addStyle(`
            #bf-observer-panel {
                position: fixed;
                top: 10px;
                right: 10px;
                z-index: 99999;
                background: rgba(0, 0, 0, 0.85);
                color: #2ecc71;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                padding: 10px 14px;
                border-radius: 8px;
                border: 1px solid #2ecc71;
                min-width: 280px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
                cursor: move;
                user-select: none;
            }
            #bf-observer-panel .bf-title {
                font-weight: bold;
                font-size: 13px;
                margin-bottom: 6px;
                color: #3498db;
            }
            #bf-observer-panel .bf-status {
                margin-bottom: 4px;
            }
            #bf-observer-panel .bf-btn {
                background: #2ecc71;
                color: #000;
                border: none;
                padding: 4px 10px;
                margin: 2px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 11px;
                font-weight: bold;
            }
            #bf-observer-panel .bf-btn:hover {
                background: #27ae60;
            }
            #bf-observer-panel .bf-btn-red {
                background: #e74c3c;
                color: #fff;
            }
            #bf-observer-panel .bf-btn-red:hover {
                background: #c0392b;
            }
        `);

        const panel = document.createElement('div');
        panel.id = 'bf-observer-panel';
        panel.innerHTML = `
            <div class="bf-title">BETFAIR OBSERVER</div>
            <div class="bf-status" id="bf-status">Iniciando...</div>
            <div class="bf-status" id="bf-count">Registros: 0</div>
            <div class="bf-status" id="bf-last">Última captura: -</div>
            <div style="margin-top: 8px;">
                <button class="bf-btn" id="bf-btn-export-partido">CSV Partido</button>
                <button class="bf-btn" id="bf-btn-export-todo">CSV Global</button>
                <button class="bf-btn bf-btn-red" id="bf-btn-toggle">Pausar</button>
            </div>
        `;
        document.body.appendChild(panel);

        // Botones
        document.getElementById('bf-btn-export-partido').addEventListener('click', exportarCSVPartido);
        document.getElementById('bf-btn-export-todo').addEventListener('click', exportarCSVUnificado);
        document.getElementById('bf-btn-toggle').addEventListener('click', toggleCaptura);

        // Hacer el panel arrastrable
        let isDragging = false;
        let offsetX, offsetY;
        panel.addEventListener('mousedown', (e) => {
            if (e.target.tagName === 'BUTTON') return;
            isDragging = true;
            offsetX = e.clientX - panel.getBoundingClientRect().left;
            offsetY = e.clientY - panel.getBoundingClientRect().top;
        });
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            panel.style.left = (e.clientX - offsetX) + 'px';
            panel.style.top = (e.clientY - offsetY) + 'px';
            panel.style.right = 'auto';
        });
        document.addEventListener('mouseup', () => { isDragging = false; });
    }

    function actualizarPanel(numRegistros, ultimaCaptura) {
        const statusEl = document.getElementById('bf-status');
        const countEl = document.getElementById('bf-count');
        const lastEl = document.getElementById('bf-last');
        if (statusEl) statusEl.textContent = capturaActiva ? 'CAPTURANDO' : 'PAUSADO';
        if (countEl) countEl.textContent = `Registros: ${numRegistros}`;
        if (lastEl) lastEl.textContent = `Última: ${ultimaCaptura}`;
    }

    // ══════════════════════════════════════════════════════════════════════
    // LOOP PRINCIPAL
    // ══════════════════════════════════════════════════════════════════════

    let capturaActiva = true;
    let intervaloCapturaId = null;
    let intervaloExportId = null;
    let contadorRegistros = 0;

    function toggleCaptura() {
        capturaActiva = !capturaActiva;
        const btn = document.getElementById('bf-btn-toggle');
        if (btn) {
            btn.textContent = capturaActiva ? 'Pausar' : 'Reanudar';
            btn.className = capturaActiva ? 'bf-btn bf-btn-red' : 'bf-btn';
        }
        log(capturaActiva ? 'Captura reanudada' : 'Captura pausada');
    }

    async function ejecutarCaptura() {
        if (!capturaActiva) return;

        try {
            const registro = capturarDatos();
            await guardarRegistro(registro);
            contadorRegistros++;
            actualizarPanel(contadorRegistros, registro.timestamp_utc);
        } catch (e) {
            log(`Error en captura: ${e.message}`, 'error');
        }
    }

    function iniciar() {
        log('Iniciando Betfair Observer...');
        log(`Partido ID: ${obtenerIdPartido()}`);
        log(`Intervalo captura: ${CONFIG.INTERVALO_CAPTURA_MS / 1000}s`);
        log(`Auto-export CSV: cada ${CONFIG.INTERVALO_EXPORT_MS / 60000} min`);

        // Crear panel UI
        crearPanel();

        // Primera captura inmediata (con delay para que la página cargue)
        setTimeout(() => {
            ejecutarCaptura();

            // Capturas periódicas
            intervaloCapturaId = setInterval(ejecutarCaptura, CONFIG.INTERVALO_CAPTURA_MS);

            // Auto-export periódico
            intervaloExportId = setInterval(exportarCSVPartido, CONFIG.INTERVALO_EXPORT_MS);
        }, 5000);

        log('Observer activo. Panel de control visible arriba-derecha.');
    }

    // Esperar a que la página cargue completamente
    if (document.readyState === 'complete') {
        iniciar();
    } else {
        window.addEventListener('load', iniciar);
    }

})();
