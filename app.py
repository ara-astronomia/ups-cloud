import time
import configparser 
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from nut2 import PyNUTClient
import os
import sqlite3
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

config = configparser.ConfigParser()
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini') 

# Variabili di fallback
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 3493

DATABASE = '/app/data/db/ups_data.db'


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
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='eventlet',
    ping_timeout=60,
    ping_interval=25,
    logger=False,
    engineio_logger=False
)

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

# Inizializza il database all'avvio per esecuzione diretta (non gunicorn)
# Con gunicorn, l'inizializzazione avviene tramite gunicorn.conf.py
if __name__ == '__main__':
    init_db()

def scheduled_data_logging():
    """Funzione eseguita periodicamente per salvare i dati UPS nel database."""
    with app.app_context():
        try:
            client = PyNUTClient(host=NUT_HOST, port=NUT_PORT)
            ups_names = client.list_ups()
            
            timestamp = int(time.time())
            new_data_points = {}
            
            for name in ups_names:
                variables = client.list_vars(name)
                log_data(name, variables, status=variables.get('ups.status', 'unknown'))
                
                # Prepara i dati per il broadcast ai grafici
                try:
                    input_voltage = float(variables.get('input.voltage', '0.0').split(' ')[0])
                    battery_charge = float(variables.get('battery.charge', '0.0').split(' ')[0])
                    
                    new_data_points[name] = {
                        'timestamp': timestamp,
                        'input_voltage': input_voltage,
                        'battery_charge': battery_charge
                    }
                except Exception as e:
                    print(f"[Scheduler] Errore parsing dati {name}: {e}")
            
            # Invia i nuovi punti dati via WebSocket
            if new_data_points:
                socketio.emit('chart_update', new_data_points, namespace='/')
            
        except Exception as e:
            print(f"[Scheduler] Errore durante il logging: {e}")

def broadcast_ups_data():
    """Invia aggiornamenti real-time via WebSocket a tutti i client connessi."""
    with app.app_context():
        try:
            data = get_ups_status()
            socketio.emit('ups_update', data, namespace='/')
        except Exception as e:
            print(f"[WebSocket] Errore durante broadcast: {e}")

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
        ups_names = client.list_ups()
        
        for name in ups_names:
            variables = client.list_vars(name)
            room_name = ROOMS_MAP.get(name.lower(), 'N/D')

            data[name] = {
                'vars': variables,
                'last_update': time.strftime("%H:%M:%S"),
                'rooms': room_name,
            }
            
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
    elif period == '1m':
        time_limit = now - (30 * 24 * 3600)
    else:
        time_limit = now - 86400
    # query SQL per limite di tempo e UPS
    data = cursor.execute(
        "SELECT timestamp, input_voltage, battery_charge FROM history WHERE ups_name=? AND timestamp > ? ORDER BY timestamp", 
        (ups_name, time_limit)
    ).fetchall()
    
    conn.close()
    
    return jsonify([dict(row) for row in data])

# Inizializza scheduler APScheduler quando il modulo viene caricato (nei worker)
# Usa una variabile globale per evitare avvii multipli
_scheduler_started = False

def start_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    
    _scheduler_started = True
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=scheduled_data_logging,
        trigger='interval',
        minutes=5,
        id='ups_data_logging'
    )
    scheduler.add_job(
        func=broadcast_ups_data,
        trigger='interval',
        seconds=10,
        id='ups_broadcast'
    )
    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())

if __name__ == '__main__':
    # Per esecuzione locale con server di sviluppo
    # Inizializza DB e testa connessione NUT
    init_db()
    print("--- Test di connessione a NUT ---")
    initial_data = get_ups_status()
    if 'error' in initial_data:
        print(f"ERRORE: {initial_data['error']}")
    else:
        print("Connessione NUT OK")
    
    # Avvia scheduler per logging automatico
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=scheduled_data_logging,
        trigger='interval',
        minutes=5,
        id='ups_data_logging'
    )
    scheduler.start()
    print("Scheduler avviato: logging dati ogni 5 minuti")
    
    # Primo logging immediato
    scheduled_data_logging()
    
    # Aggiungi job per broadcast WebSocket ogni 10 secondi
    scheduler.add_job(
        func=broadcast_ups_data,
        trigger='interval',
        seconds=10,
        id='ups_broadcast'
    )
    
    # Shutdown pulito
    atexit.register(lambda: scheduler.shutdown())
    
    # In produzione (Docker), usa gunicorn tramite gunicorn.conf.py
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
