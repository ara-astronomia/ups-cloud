import time
import configparser 
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from nut2 import PyNUTClient
import os
import sqlite3

config = configparser.ConfigParser()
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini') 

# Variabili di fallback
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 3493

DATABASE = 'ups_data.db'


try:
    # 1. Tenta di leggere il file
    read_files = config.read(CONFIG_PATH)
    if not read_files:
        raise FileNotFoundError(f"Impossibile trovare il file: {CONFIG_PATH}")
    
    ROOMS_MAP = {}
    if config.has_section('rooms'):
        ROOMS_MAP = dict(config.items('rooms'))
        #print(f"Mappe delle stanze caricate: {ROOMS_MAP}")
    else:
        print("WARNING: Sezione [rooms] non trovata nel config.ini. Le stanze non verranno visualizzate.")


    NUT_HOST = config.get('ups', 'hostname')
    #print(f"Lettura NUT_HOST dal config: {NUT_HOST}")
    NUT_PORT = config.getint('ups', 'port', fallback=DEFAULT_PORT) 
    
except (configparser.NoSectionError, configparser.NoOptionError, FileNotFoundError) as e:
    print(f"ERRORE di configurazione: {e}. Uso i valori di default per NUT.")
    NUT_HOST = DEFAULT_HOST
    NUT_PORT = DEFAULT_PORT
except Exception as e:
    print(f"ERRORE generico durante la lettura del config: {e}")
    NUT_HOST = DEFAULT_HOST
    NUT_PORT = DEFAULT_PORT

#print(f"Configurazione NUT letta: HOST={NUT_HOST}, PORT={NUT_PORT}")
# --- SERVER FLASK ---
app = Flask(__name__)

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            timestamp INTEGER,
            ups_name TEXT,
            input_voltage REAL,
            battery_charge REAL,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_data(name, variables, status):
    """Registra i dati attuali nel database."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    timestamp = int(time.time())

    input_voltage = variables.get('input.voltage', '0.0') # Fallback per evitare errori
    battery_charge = variables.get('battery.charge', '0.0') # Fallback per evitare errori
    
    try:
        input_voltage = float(input_voltage.split(' ')[0])
    except:
        input_voltage = 0.0
        
    try:
        battery_charge = float(battery_charge.split(' ')[0])
    except:
        battery_charge = 0.0
    
    if input_voltage > 0.0 or battery_charge > 0.0:
        cursor.execute(
            "INSERT INTO history VALUES (?, ?, ?, ?, ?)",
            (timestamp, name, input_voltage, battery_charge, status)
        )
    conn.commit()
    conn.close()

def get_ups_status():
    #print("Si connette a upsd e recupera lo stato attuale di tutti gli UPS configurati")

    data = {}
    
    try:
        client = PyNUTClient(host=NUT_HOST, port=NUT_PORT)
        print(f"Tentativo di connessione a NUT su {NUT_HOST}:{NUT_PORT}")        
        ups_names = client.list_ups()
        
        for name in ups_names:
            variables = client.list_vars(name)
            room_name = ROOMS_MAP.get(name.lower(), 'N/D') 
            print(room_name)
            log_data(name, variables, status=variables.get('ups.status', 'unknown'))

            data[name] = {
                'vars': variables,
                'last_update': time.strftime("%H:%M:%S"),
                'rooms': room_name,
            }
            print(data)
            
    except Exception as e:
        data['error'] = f"Errore di connessione a NUT: {e}"
        print(f"Errore NUT: {e}")
        
    return data


@app.route('/')
def dashboard():
    detail_param = request.args.get('dettaglio')
    data = get_ups_status()

    if isinstance(data, dict) and 'error' not in data:
        ups_names_list = list(data.keys())
    else:
        ups_names_list = []
        
    return render_template('dashboard.html', 
                           data=data, 
                           ups_names=ups_names_list,
                           detail=detail_param,)

@app.route('/api/history', methods=['GET'])
def history_data():
    """
    ENDPOINT API: Restituisce i dati storici per un UPS e un periodo specifici.
    L'URL deve essere: /api/history?ups=<nome_ups>&period=<1d|1w|1m>
    """
    ups_name = request.args.get('ups')
    period = request.args.get('period', '1d') 
    
    if not ups_name:
        return jsonify({"error": "Parametro 'ups' richiesto"}), 400

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Calcolo del limite temporale in base al periodo richiesto
    now = int(time.time())
    
    if period == '1w':
        time_limit = now - (7 * 24 * 3600) 
        print(f"Recupero dati storici per {ups_name}: 1 Settimana ({datetime.fromtimestamp(time_limit).strftime('%Y-%m-%d %H:%M:%S')})")
    elif period == '1m':
        time_limit = now - (30 * 24 * 3600) 
        print(f"Recupero dati storici per {ups_name}: 1 Mese ({datetime.fromtimestamp(time_limit).strftime('%Y-%m-%d %H:%M:%S')})")
    else: 
        time_limit = now - 86400 
        print(f"Recupero dati storici per {ups_name}: 24 Ore ({datetime.fromtimestamp(time_limit).strftime('%Y-%m-%d %H:%M:%S')})")
    
    # query SQL per limite di tempo e UPS
    data = cursor.execute(
        "SELECT timestamp, input_voltage, battery_charge FROM history WHERE ups_name=? AND timestamp > ? ORDER BY timestamp", 
        (ups_name, time_limit)
    ).fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in data])

if __name__ == '__main__':
    init_db() 
    
    print("--- Test di connessione a NUT all'avvio ---")
    initial_data = get_ups_status()
    if 'error' in initial_data:
        print(f"ERRORE GRAVE DI CONNESSIONE A NUT ALL'AVVIO: {initial_data['error']}")
    else:
        print("Test di connessione iniziale riuscito.")
    
    # Per esecuzione locale con server di sviluppo
    # In produzione (Docker), usa gunicorn tramite il Dockerfile
    app.run(debug=True, host='0.0.0.0', port=5000)
