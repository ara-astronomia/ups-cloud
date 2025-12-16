"""Configurazione Gunicorn per ups-cloud"""
import os
import sys

# Aggiungi la directory corrente al path
sys.path.insert(0, os.path.dirname(__file__))

# Configurazione server
bind = "0.0.0.0:5000"
workers = 1  # SocketIO richiede 1 worker con eventlet
worker_class = "eventlet"  # Worker class per WebSocket
timeout = 120
loglevel = "info"
accesslog = "-"
errorlog = "-"

def on_starting(server):
    """
    Hook eseguito una sola volta dal processo master all'avvio,
    prima di forkare i worker.
    """
    from app import init_db, get_ups_status
    
    print("=== Inizializzazione applicazione (master process) ===")
    
    # Inizializza database
    init_db()
    print("Database inizializzato")
    
    # Test connessione NUT
    print("--- Test di connessione a NUT ---")
    initial_data = get_ups_status()
    if 'error' in initial_data:
        print(f"ERRORE DI CONNESSIONE A NUT: {initial_data['error']}")
    else:
        print("Test di connessione NUT riuscito")
    
    print("=== Inizializzazione completata ===")
    print("NOTA: Background tasks WebSocket gestiti da Flask-SocketIO")
