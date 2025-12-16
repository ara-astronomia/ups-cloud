// Struttura dati per memorizzare le istanze dei grafici Chart.js
const upsCharts = {};

// Traccia il periodo attualmente visualizzato per ogni UPS
const upsCurrentPeriod = {};

/**
 * Aggiunge un nuovo punto dati ai grafici di un UPS specifico
 * @param {string} upsName - Nome dell'UPS
 * @param {Object} dataPoint - Dati: {timestamp, input_voltage, battery_charge}
 */
window.addDataPointToCharts = function addDataPointToCharts(upsName, dataPoint) {
    const voltageChartId = 'chart-voltage-' + upsName;
    const chargeChartId = 'chart-charge-' + upsName;
    
    const timestampMs = dataPoint.timestamp * 1000;
    
    // Determina il periodo attivo per questo UPS (default: 1d)
    const currentPeriod = upsCurrentPeriod[upsName] || '1d';
    
    // Calcola cutoff time basato sul periodo
    let cutoffTime;
    if (currentPeriod === '1w') {
        cutoffTime = Date.now() - (7 * 24 * 60 * 60 * 1000);
    } else if (currentPeriod === '1m') {
        cutoffTime = Date.now() - (30 * 24 * 60 * 60 * 1000);
    } else { // '1d'
        cutoffTime = Date.now() - (24 * 60 * 60 * 1000);
    }
    
    // Aggiorna grafico tensione
    const voltageChart = upsCharts[voltageChartId];
    if (voltageChart && dataPoint.input_voltage > 0) {
        voltageChart.data.datasets[0].data.push({
            x: timestampMs,
            y: dataPoint.input_voltage
        });
        
        // Rimuovi solo punti fuori dal periodo visualizzato
        voltageChart.data.datasets[0].data = voltageChart.data.datasets[0].data.filter(
            point => point.x > cutoffTime
        );
        
        voltageChart.update('none');
    }
    
    // Aggiorna grafico batteria
    const chargeChart = upsCharts[chargeChartId];
    if (chargeChart && dataPoint.battery_charge > 0) {
        chargeChart.data.datasets[0].data.push({
            x: timestampMs,
            y: dataPoint.battery_charge
        });
        
        // Rimuovi solo punti fuori dal periodo visualizzato
        chargeChart.data.datasets[0].data = chargeChart.data.datasets[0].data.filter(
            point => point.x > cutoffTime
        );
        
        chargeChart.update('none');
    }
}

document.addEventListener('DOMContentLoaded', function() {
    
    // Controlla se l'oggetto è stato definito correttamente
    if (typeof allUpsData === 'undefined' || Object.keys(allUpsData).length === 0) {
        console.error("Errore: La variabile 'allUpsData' non è definita o è vuota. Controllare il template HTML.");
        const mainContent = document.getElementById('main-dashboard-content');
        if (mainContent) {
            mainContent.innerHTML = `<div class="p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg" role="alert"><p class="font-bold">Errore di Dati</p><p>Impossibile caricare i dati degli UPS. Controllare l'oggetto 'allUpsData' nel template HTML.</p></div>`;
        }
        return;
    }

    // Avvia il caricamento dei grafici per tutti gli UPS
    Object.keys(allUpsData).forEach(upsName => {
        // Imposta periodo di default
        upsCurrentPeriod[upsName] = '1d';
        loadChart(upsName);
    });
});

/**
 * Funzione helper per trasformare l'array di dati piatti in formato {x: timestamp_ms, y: value}
 * @param {Array<Object>} historyData - I dati grezzi dal backend Flask.
 * @param {string} valueKey - La chiave del valore da usare ('input_voltage' o 'battery_charge').
 * @returns {Array<Object>} Dati formattati per la scala temporale di Chart.js.
 */
function transformDataForTimeScale(historyData, valueKey) {
    // Il timestamp dal backend è in secondi, lo convertiamo in millisecondi
    return historyData.map(d => ({
        x: d.timestamp * 1000, 
        y: d[valueKey]
    }));
}

/**
 * Funzione per recuperare i dati storici iniziali e disegnare i grafici.
 * @param {string} upsName - Il nome dell'UPS (es: 'apc-3000').
 */
function loadChart(upsName) {
    
    const voltageCanvasId = 'chart-voltage-' + upsName;
    const chargeCanvasId = 'chart-charge-' + upsName;
    
    // Configura le opzioni della scala temporale per l'asse X
    const timeScaleOptions = {
        type: 'time',
        time: {
            // Rimosso 'unit: hour' per permettere a Chart.js di auto-selezionare l'unità.
            tooltipFormat: 'dd/MM/yyyy HH:mm', // Formato visualizzato nel tooltip
            displayFormats: {
                hour: 'HH:mm',      // Per intervalli brevi (es. 24 Ore)
                day: 'dd/MM',       // Per intervalli medi (es. 1 Settimana)
                week: 'dd/MM/yy',   // Formato settimana (anche se Chart.js può usare 'day' per una settimana)
                month: 'MMM yyyy'   // Per intervalli lunghi (es. 1 Mese)
            }
        },
        title: {
            display: true,
            text: 'Tempo',
            font: { size: 12 }
        },
        ticks: {
            source: 'auto',
            font: { size: 10 }, // DIMENSIONE FONT RIDOTTA per l'asse X
            padding: 5 // Aggiunge un piccolo padding per i tick
        },
        grid: {
            display: false // Rimuove le linee verticali di griglia (solo quelle X)
        }
    };

    // Recupera i dati storici dall'endpoint API di Flask per il periodo di default (1 giorno)
    fetchWithRetry(`/api/history?ups=${encodeURIComponent(upsName)}&period=1d`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`Errore HTTP ${response.status} durante il recupero dei dati iniziali.`);
            }
            return response.json();
        })
        .then(historyData => {
            
            if (historyData.length === 0) {
                console.log(`Nessun dato storico trovato per ${upsName}.`);
                return;
            }

            // Trasforma i dati per la scala temporale
            const voltageData = transformDataForTimeScale(historyData, 'input_voltage');
            const chargeData = transformDataForTimeScale(historyData, 'battery_charge');
            
            // --- Funzione Helper per le opzioni del grafico ---
            const getChartOptions = (title) => ({
                responsive: true,
                maintainAspectRatio: false, // Permette la reattività completa (ora gestita dal CSS del contenitore)
                scales: { 
                    x: timeScaleOptions, // Usa la configurazione della scala temporale continua
                    y: { 
                        beginAtZero: title.includes('Batteria') ? true : false, 
                        max: title.includes('Batteria') ? 100 : undefined,
                        ticks: {
                             font: { size: 10 }, // DIMENSIONE FONT RIDOTTA per l'asse Y
                             padding: 5 // Padding ridotto per l'asse Y
                        },
                        title: {
                            display: true,
                            text: title.includes('Batteria') ? 'Carica (%)' : 'Tensione (V)',
                            font: { size: 12 }
                        }
                    } 
                },
                plugins: {
                    title: { display: true, text: title, font: { size: 14 } },
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                return new Date(context[0].parsed.x).toLocaleString();
                            }
                        }
                    }
                }
            });

            // --- Disegna il Grafico della Tensione di Ingresso ---
            const ctxVoltage = document.getElementById(voltageCanvasId);
            if (ctxVoltage) {
                const voltageChart = new Chart(ctxVoltage, {
                    type: 'line',
                    data: {
                        datasets: [{
                            label: 'Tensione Ingresso (V)',
                            data: voltageData,
                            borderColor: 'rgb(75, 192, 192)',
                            tension: 0.1,
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            fill: true,
                            pointRadius: 0
                        }]
                    },
                    options: getChartOptions('Storico Tensione (24 Ore)')
                });
                upsCharts[voltageCanvasId] = voltageChart;
            }
            
            // --- Disegna il Grafico della Carica della Batteria ---
            const ctxCharge = document.getElementById(chargeCanvasId);
            if (ctxCharge) {
                const chargeChart = new Chart(ctxCharge, {
                    type: 'line',
                    data: {
                        datasets: [{
                            label: 'Carica Batteria (%)',
                            data: chargeData,
                            borderColor: 'rgb(54, 162, 235)',
                            tension: 0.1,
                            backgroundColor: 'rgba(54, 162, 235, 0.2)',
                            fill: true,
                            pointRadius: 0
                        }]
                    },
                    options: getChartOptions('Storico Batteria (24 Ore)')
                });
                upsCharts[chargeCanvasId] = chargeChart;
            }
        })
        .catch(error => {
            console.error(`Errore nel caricamento grafico per ${upsName}:`, error);
            const chartArea = document.getElementById(upsName + '-charts-container');
            if(chartArea) {
                chartArea.innerHTML = `<p class="text-red-500 p-4">Impossibile caricare lo storico. ${error.message}</p>`;
            }
        });
}

/**
 * Aggiorna i grafici di tensione e batteria per l'UPS specificato
 */
async function updateChartPeriod(upsName, period) {
    const voltageCanvasId = `chart-voltage-${upsName}`;
    const chargeCanvasId = `chart-charge-${upsName}`;
    
    const voltageChart = upsCharts[voltageCanvasId];
    const chargeChart = upsCharts[chargeCanvasId];

    if (!voltageChart || !chargeChart) {
        console.error(`Istanze di Chart.js non trovate per l'UPS: ${upsName}.`);
        return;
    }

    // Gestione UI pulsanti
    const buttons = document.querySelectorAll(`#${upsName}-period-buttons button`);
    buttons.forEach(btn => btn.disabled = true);
    
    // 1. Ripristina lo stato di default NON selezionato per tutti
    buttons.forEach(btn => {
        btn.classList.remove('bg-blue-600', 'text-white');
        btn.classList.add('bg-white', 'text-gray-700', 'hover:bg-blue-500', 'hover:text-white');
    });

    // 2. Applica lo stato attivo a quello selezionato, sovrascrivendo il default
    const activeBtn = document.querySelector(`#${upsName}-period-buttons button[data-period="${period}"]`);
    if (activeBtn) {
        activeBtn.classList.remove('bg-white', 'text-gray-700', 'hover:bg-blue-500', 'hover:text-white');
        activeBtn.classList.add('bg-blue-600', 'text-white');
    }
    
    // Aggiorna il periodo corrente per questo UPS
    upsCurrentPeriod[upsName] = period;
    
    // FINE Gestione UI pulsanti

    try {
        const apiUrl = `/api/history?ups=${encodeURIComponent(upsName)}&period=${period}`;
        
        const response = await fetchWithRetry(apiUrl);
        if (!response.ok) {
            throw new Error(`Errore HTTP ${response.status}. Controlla la rotta Flask /api/history.`);
        }
        
        const historyData = await response.json();

        const periodTitleMap = { '1d': '24 Ore', '1w': '1 Settimana', '1m': '1 Mese' };
        const displayPeriod = periodTitleMap[period] || period;

        if (historyData.length === 0) {
            console.log(`Nessun dato storico trovato per ${upsName} per il periodo ${period}.`);
            
            const emptyData = { datasets: [{ data: [] }] };
            voltageChart.data = emptyData;
            chargeChart.data = emptyData;
            voltageChart.options.plugins.title.text = `Storico Tensione (${displayPeriod}) - Dati non disponibili`;
            chargeChart.options.plugins.title.text = `Storico Batteria (${displayPeriod}) - Dati non disponibili`;
            
            voltageChart.update();
            chargeChart.update();
            return;
        }

        const voltageData = transformDataForTimeScale(historyData, 'input_voltage');
        const chargeData = transformDataForTimeScale(historyData, 'battery_charge');

        // Grafico Tensione
        voltageChart.data.datasets[0].data = voltageData;
        voltageChart.options.plugins.title.text = `Storico Tensione (${displayPeriod})`;
        voltageChart.update();

        // Grafico Batteria
        chargeChart.data.datasets[0].data = chargeData;
        chargeChart.options.plugins.title.text = `Storico Batteria (${displayPeriod})`;
        chargeChart.update();

    } catch (error) {
        console.error(`Errore durante il recupero dei dati storici per ${upsName}:`, error);
    } finally {
        buttons.forEach(btn => btn.disabled = false);
    }
}

/**
 * Funzione per il retry con backoff esponenziale.
 */
async function fetchWithRetry(url, options = {}, maxRetries = 5) {
    let lastError = null;
    for (let i = 0; i < maxRetries; i++) {
        const delay = Math.pow(2, i) * 1000;
        try {
            const response = await fetch(url, options);
            if (response.status === 429 || response.status >= 500) {
                throw new Error(`Server error or rate limit: ${response.status}`);
            }
            return response;
        } catch (error) {
            lastError = error;
            if (i < maxRetries - 1) {
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }
    throw new Error(`Fallimento definitivo della richiesta a ${url} dopo ${maxRetries} tentativi. Ultimo errore: ${lastError.message}`);
}