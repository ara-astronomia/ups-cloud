import time
import configparser 
from flask import Flask, render_template, request, jsonify
from nut2 import PyNUTClient
import os

# --- LETTURA CONFIGURAZIONE DA FILE ---
config = configparser.ConfigParser()

# Costruisce il percorso completo del file config.ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
# Assuming config.ini is still located in: ../ups-cloud/config.ini
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini') 

# Variabili di fallback
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 3493


try:
    # 1. Tenta di leggere il file
    read_files = config.read(CONFIG_PATH)
    if not read_files:
        raise FileNotFoundError(f"Impossibile trovare il file: {CONFIG_PATH}")
    
    ROOMS_MAP = {}
    if config.has_section('rooms'):
        ROOMS_MAP = dict(config.items('rooms'))
        print(f"Mappe delle stanze caricate: {ROOMS_MAP}")
    else:
        print("WARNING: Sezione [rooms] non trovata nel config.ini. Le stanze non verranno visualizzate.")

    # 2. Leggi i parametri NUT dalla sezione [ups]
    # Usiamo 'hostname' per HOST
    NUT_HOST = config.get('ups', 'hostname')
    print(f"Lettura NUT_HOST dal config: {NUT_HOST}")
    # Usiamo 'port' per PORT e leggiamo come intero
    NUT_PORT = config.getint('ups', 'port', fallback=DEFAULT_PORT) 
    
    # Opzionale: puoi leggere la lista degli UPS se volessi filtrarli in app.py
    # UPS_LIST = config.get('ups', 'ups_list', fallback='').split(',')
    
except (configparser.NoSectionError, configparser.NoOptionError, FileNotFoundError) as e:
    print(f"ERRORE di configurazione: {e}. Uso i valori di default per NUT.")
    NUT_HOST = DEFAULT_HOST
    NUT_PORT = DEFAULT_PORT
except Exception as e:
    print(f"ERRORE generico durante la lettura del config: {e}")
    NUT_HOST = DEFAULT_HOST
    NUT_PORT = DEFAULT_PORT

print(f"Configurazione NUT letta: HOST={NUT_HOST}, PORT={NUT_PORT}")

# --- SERVER FLASK ---
app = Flask(__name__)

# Funzione per connettersi a NUT e recuperare i dati
def get_ups_status():

    print("Si connette a upsd e recupera lo stato attuale di tutti gli UPS configurati")

    data = {}
    
    try:
        # Crea il client NUT
        client = PyNUTClient(host=NUT_HOST, port=NUT_PORT)
        print(f"Tentativo di connessione a NUT su {NUT_HOST}:{NUT_PORT}")
        
        # Ottieni la lista dei nomi degli UPS configurati (es. 'myups1', 'myups2')
        ups_names = client.list_ups()
        
        for name in ups_names:
            # Recupera le variabili (i dati) per ogni UPS
            variables = client.list_vars(name)
            room_name = ROOMS_MAP.get(name.lower(), 'N/D') # Usa .lower() per sicurezza, e 'N/D' come fallback
            print(room_name)
            
            # Aggiorna il dizionario data
            data[name] = {
                'vars': variables,
                'last_update': time.strftime("%H:%M:%S"),
                'rooms': room_name,
            }
            print(data)
            
    except Exception as e:
        # Gestione degli errori di connessione a NUT
        data['error'] = f"Errore di connessione a NUT: {e}"
        print(f"Errore NUT: {e}")
        
    return data


@app.route('/')
def dashboard():
    # 1. Recupera i dati aggiornati
    all_ups_data = get_ups_status()
    
    # 2. Gestione delle "Flag" (Parametri di Query)
    # Esempio: ?ups=ups1 per mostrare solo un UPS
    # Esempio: ?dettaglio=full per mostrare tutte le variabili
    
    # Parametro per filtrare quale UPS mostrare
    filter_ups = request.args.get('ups', 'all') 
    
    # Parametro per il livello di dettaglio dei dati
    detail_level = request.args.get('dettaglio', 'standard') 

    # Filtra i dati in base al parametro 'ups'
    if filter_ups != 'all' and filter_ups in all_ups_data:
        data_to_display = {filter_ups: all_ups_data[filter_ups]}
    else:
        data_to_display = all_ups_data

    # 3. Renderizza il template HTML
    return render_template(
        'dashboard.html', 
        data=data_to_display,
        detail=detail_level,
        filter_ups=filter_ups
    )

if __name__ == '__main__':
    # Esegui un test di connessione iniziale
    print("--- Test di connessione a NUT all'avvio ---")
    initial_data = get_ups_status()
    if 'error' in initial_data:
        print(f"ERRORE GRAVE DI CONNESSIONE A NUT ALL'AVVIO: {initial_data['error']}")
    else:
        print("Test di connessione iniziale riuscito.")
        
    app.run(debug=True, host='0.0.0.0', port=5000)