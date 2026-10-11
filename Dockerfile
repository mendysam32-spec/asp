# ASP (Agent SP) — Flask dashboard on Cloudflare Containers
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: none needed beyond pip (Pillow uses wheels, imageio-ffmpeg bundles binary)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY . .

# Runtime dirs (ephemeral in Containers — survives only while instance lives)
RUN mkdir -p data/media config && \
    touch data/agent.log || true

EXPOSE 5001

# run_background.py serves Flask via waitress on 0.0.0.0:$PORT + auto-starts agent loop
CMD ["python", "run_background.py"]
