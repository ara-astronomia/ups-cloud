# Usa una versione leggera di Python come immagine base
FROM python:3.12-slim
RUN pip install uv

# Imposta la directory di lavoro all'interno del container
WORKDIR /app

# Abilita bytecode compilation per migliorare le prestazioni
ENV UV_COMPILE_BYTECODE=1

# Copia del sistema virtuale uv nella directory /app/.venv
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# 1. Copia il file delle dipendenze e installale
COPY pyproject.toml .

RUN uv sync --no-install-project --no-dev

# 2. Copia tutti gli altri file dell'applicazione (app.py, templates/, static/, config.ini)
COPY . .

# 3. Crea la directory per il database
RUN mkdir -p /app/data

# Il servizio NUT (upsd) dovrebbe essere accessibile da questo container. 
# Se il NUT server è sul localhost, dovrai usare l'indirizzo IP del tuo host Docker
# o il nome del servizio se sei in Docker Compose (es. 172.17.0.1, o nut-service).

# 4. Espone la porta che Flask userà
EXPOSE 5000

# 5. Definisce il comando da eseguire all'avvio del container
# Usa Gunicorn come WSGI server per produzione con file di configurazione
CMD ["/app/.venv/bin/gunicorn", "--config", "gunicorn.conf.py", "app:app"]