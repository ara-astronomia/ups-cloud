const upsCharts = {};

document.addEventListener('DOMContentLoaded', function() {
    
    // Recupera l'oggetto dati JSON incorporato nell'HTML da Jinja2
    // La variabile globale 'allUpsData' deve essere definita prima di questo script
    // nel file dashboard.html.
    
    // Controlla se l'oggetto è stato definito correttamente
    if (typeof allUpsData === 'undefined' || Object.keys(allUpsData).length === 0) {
        console.error("Errore: La variabile 'allUpsData' non è definita o è vuota. Controllare il template HTML.");
        return;
    }

    // Estrae i nomi degli UPS (le chiavi del dizionario)
    const upsNames = Object.keys(allUpsData);

    upsNames.forEach(upsName => {
        // Esegui la funzione di caricamento per ciascun UPS
        loadChart(upsName);
    });
});

/**
 * Funzione per recuperare i dati storici iniziali e disegnare i grafici.
 * @param {string} upsName - Il nome dell'UPS (es: 'apc-3000').
 */
function loadChart(upsName) {
    
    const voltageCanvasId = 'chart-voltage-' + upsName;
    const chargeCanvasId = 'chart-charge-' + upsName;

    // Recupera i dati storici dall'endpoint API di Flask per il periodo di default (assumiamo 1 giorno)
    // L'endpoint è stato aggiornato per includere il parametro 'period' anche per il default
    fetchWithRetry(`/api/history?ups=${encodeURIComponent(upsName)}&period=1d`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(historyData => {
            
            if (historyData.length === 0) {
                console.log(`Nessun dato storico trovato per ${upsName}.`);
                return;
            }

            // Prepara i dati nel formato richiesto da Chart.js
            const labels = historyData.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());
            const voltageData = historyData.map(d => d.input_voltage);
            const chargeData = historyData.map(d => d.battery_charge);
            
            // --- Disegna il Grafico della Tensione di Ingresso ---
            const ctxVoltage = document.getElementById(voltageCanvasId);
            if (ctxVoltage) {
                const voltageChart = new Chart(ctxVoltage, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Tensione Ingresso (V)',
                            data: voltageData,
                            borderColor: 'rgb(75, 192, 192)',
                            tension: 0.1
                        }]
                    },
                    options: { 
                        responsive: true, 
                        scales: { y: { beginAtZero: false } },
                        plugins: {
                            title: { display: true, text: 'Storico Tensione (24 Ore)' }
                        }
                    }
                });
                // SALVA L'ISTANZA GLOBALE
                upsCharts[voltageCanvasId] = voltageChart;
            }
            
            // --- Disegna il Grafico della Carica della Batteria ---
            const ctxCharge = document.getElementById(chargeCanvasId);
            if (ctxCharge) {
                const chargeChart = new Chart(ctxCharge, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Carica Batteria (%)',
                            data: chargeData,
                            borderColor: 'rgb(54, 162, 235)',
                            tension: 0.1
                        }]
                    },
                    options: { 
                        responsive: true, 
                        scales: { y: { beginAtZero: false, max: 100 } },
                        plugins: {
                            title: { display: true, text: 'Storico Batteria (24 Ore)' }
                        }
                    }
                });
                 // SALVA L'ISTANZA GLOBALE
                upsCharts[chargeCanvasId] = chargeChart;
            }
        })
        .catch(error => {
            console.error(`Errore nel caricamento grafico per ${upsName}:`, error);
        });
}

/**
 * Aggiorna i grafici di tensione e batteria per l'UPS specificato
 * caricando nuovi dati storici basati sul periodo richiesto.
 * @param {string} upsName - Il nome dell'UPS (es. 'myups').
 * @param {string} period - Il periodo richiesto ('1d', '1w', '1m').
 */
async function updateChartPeriod(upsName, period) {
    const voltageCanvasId = `chart-voltage-${upsName}`;
    const chargeCanvasId = `chart-charge-${upsName}`;
    
    const voltageChart = upsCharts[voltageCanvasId];
    const chargeChart = upsCharts[chargeCanvasId];

    if (!voltageChart || !chargeChart) {
        console.error(`Istanze di Chart.js non trovate per l'UPS: ${upsName}. Assicurati che siano state create in loadChart().`);
        return;
    }

    try {
        // 1. CHIAMATA API AL BACKEND FLASK
        // Utilizza l'endpoint parametrizzato per richiedere il periodo specifico.
        const apiUrl = `/api/history?ups=${encodeURIComponent(upsName)}&period=${period}`;
        
        // Esegui la richiesta con retry
        const response = await fetchWithRetry(apiUrl);
        if (!response.ok) {
            throw new Error(`Errore HTTP: ${response.status}`);
        }
        
        const historyData = await response.json();

        if (historyData.length === 0) {
            console.log(`Nessun dato storico trovato per ${upsName} per il periodo ${period}.`);
            // Qui puoi decidere di cancellare i dati esistenti o mostrare un messaggio
            // Per ora, li lasceremo vuoti:
            voltageChart.data.labels = [];
            voltageChart.data.datasets[0].data = [];
            chargeChart.data.labels = [];
            chargeChart.data.datasets[0].data = [];
            voltageChart.update();
            chargeChart.update();
            return;
        }


        // 2. ELABORAZIONE DEI DATI (Stessa logica di loadChart)
        const labels = historyData.map(d => new Date(d.timestamp * 1000).toLocaleTimeString());
        const voltageData = historyData.map(d => d.input_voltage);
        const chargeData = historyData.map(d => d.battery_charge);

        // Mappa i codici periodo per titoli leggibili
        const periodTitleMap = { '1d': '24 Ore', '1w': '1 Settimana', '1m': '1 Mese' };
        const displayPeriod = periodTitleMap[period] || period;

        // 3. AGGIORNAMENTO DEI GRAFICI
        
        // Grafico Tensione
        voltageChart.data.labels = labels;
        voltageChart.data.datasets[0].data = voltageData;
        voltageChart.options.plugins.title.text = `Storico Tensione (${displayPeriod})`;
        voltageChart.update();

        // Grafico Batteria
        chargeChart.data.labels = labels;
        chargeChart.data.datasets[0].data = chargeData;
        chargeChart.options.plugins.title.text = `Storico Batteria (${displayPeriod})`;
        chargeChart.update();

        console.log(`Grafici per ${upsName} aggiornati al periodo: ${period}`);

    } catch (error) {
        console.error(`Errore durante il recupero dei dati storici per ${upsName}:`, error);
        // Qui si potrebbe mostrare un errore nel DOM (es. un div)
    }
}

/**
 * Funzione per il retry con backoff esponenziale.
 * Necessaria per gestire l'affidabilità delle chiamate API.
 */
async function fetchWithRetry(url, options = {}, maxRetries = 5) {
    let lastError = null;
    for (let i = 0; i < maxRetries; i++) {
        const delay = Math.pow(2, i) * 1000; // 1s, 2s, 4s, 8s, 16s...
        try {
            const response = await fetch(url, options);
            if (response.status === 429 || response.status >= 500) {
                 // Errore temporaneo o rate limit, riprova
                throw new Error(`Server error or rate limit: ${response.status}`);
            }
            return response; // Successo
        } catch (error) {
            lastError = error;
            if (i < maxRetries - 1) {
                // Attendi prima di riprovare
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }
    throw new Error(`Fallimento definitivo della richiesta a ${url} dopo ${maxRetries} tentativi. Ultimo errore: ${lastError.message}`);
}