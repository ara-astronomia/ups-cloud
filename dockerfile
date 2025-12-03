# Usa una versione leggera di Python come immagine base
FROM python:3.12-slim-bookworm

# Imposta la variabile d'ambiente per forzare l'output di pip a non usare la cache
ENV PIP_NO_CACHE_DIR 1

# Imposta la directory di lavoro all'interno del container
WORKDIR /app

# 1. Copia il file delle dipendenze e installale
COPY requirements.txt .
COPY config.ini .

RUN pip install --no-cache-dir -r requirements.txt

# 2. Copia tutti gli altri file dell'applicazione (app.py, templates/, static/, config.ini)
COPY . .

# Il servizio NUT (upsd) dovrebbe essere accessibile da questo container. 
# Se il NUT server è sul localhost, dovrai usare l'indirizzo IP del tuo host Docker
# o il nome del servizio se sei in Docker Compose (es. 172.17.0.1, o nut-service).

# 3. Espone la porta che Flask userà
EXPOSE 5000

# 4. Definisce il comando da eseguire all'avvio del container
# Lancia l'applicazione Flask (usare '0.0.0.0' per rendere l'app eseguibile dall'eserno cdel container)
CMD ["python", "app.py"]