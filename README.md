# ups-cloud
Monitoring UPS Observatory Virginio Cesarini

Monitoraggio UPS tramite NUT (Network UPS Tools)
Questa applicazione web, sviluppata con Flask e la libreria python-nut2, 
fornisce una dashboard per monitorare in tempo reale lo stato degli UPS 
gestiti dal demone NUT su un server remoto.


⚙️ Prerequisiti
Python 3.12+ installato sul sistema in cui si desidera eseguire la dashboard (il tuo PC locale).

Il demone NUT (upsd) installato e in esecuzione sul server, configurato per accettare connessioni remote sulla porta 3493 (controllare upsd.conf).

## Esecuzione Locale

### 1. Installazione di uv
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Installazione delle Dipendenze
```bash
# uv crea automaticamente l'ambiente virtuale e installa le dipendenze
uv sync
```

### 3. Avvio dell'Applicazione
```bash
# Esegue l'app nell'ambiente gestito da uv
uv run app.py
```

## Esecuzione con Docker

### Configurazione
Prima di buildare l'immagine, crea il file `config.ini` partendo dall'esempio:
```bash
cp config.ini.example config.ini
# Modifica config.ini con i tuoi parametri
```

### Build dell'immagine (piattaforma nativa)
```bash
docker build -t ups-cloud:latest .
```

### Build multi-piattaforma (cross-build per ARM64)
Per buildare l'immagine per ARM64 (es. Raspberry Pi) da un'altra piattaforma (es. x86_64):

```bash
# Setup del builder multi-piattaforma (solo la prima volta)
docker buildx create --name multiplatform --driver docker-container --use
docker buildx inspect --bootstrap

# Se hai problemi con il builder, ricrealo:
docker buildx rm multiplatform
docker buildx create --name multiplatform --driver docker-container --use --bootstrap

# Build per ARM64
docker buildx build --platform linux/arm64 -t ups-cloud:latest --load .

# Build per multiple piattaforme e push su registry
docker buildx build --platform linux/amd64,linux/arm64 -t yourusername/ups-cloud:latest --push .
```

### Esecuzione del container
Il file `config.ini` deve essere montato come volume:

```bash
docker run -d \
  --name ups-cloud \
  -p 5000:5000 \
  -v $(pwd)/config.ini:/app/config.ini:ro \
  -v ups-data:/app/data \
  ups-cloud:latest
```

Per connessione al NUT server sull'host Docker:
```bash
docker run -d \
  --name ups-cloud \
  -p 5000:5000 \
  -v $(pwd)/config.ini:/app/config.ini:ro \
  -v ups-data:/app/data \
  --add-host=host.docker.internal:host-gateway \
  ups-cloud:latest
```
(Nel `config.ini` usa `hostname = host.docker.internal`)



Configurazione del Server NUT
```bash
# /etc/nut/upsd.conf

# Ascolto locale (per upsc, servizi interni)
LISTEN 127.0.0.1 3493 
# Ascolto di rete (necessario per l'app Flask sul PC)
LISTEN 192.168.178.22 3493
# Ascolto da qualsiasi indirizzo
LISTEN 0.0.0.0 3493
```

