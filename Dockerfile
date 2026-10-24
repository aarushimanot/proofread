# Proofread: the whole app (web UI + API + AI models + SQLite) in one container.
# Built for Hugging Face Spaces (Docker SDK), which expects the app on port 7860,
# but it runs anywhere Docker runs:
#     docker build -t proofread . && docker run -p 7860:7860 proofread

# ---------- Stage 1: build the React UI into static files ----------
FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- Stage 2: Python backend that also serves the UI ----------
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    PORT=7860

# Hugging Face Spaces runs containers as user id 1000.
RUN useradd -m -u 1000 user && mkdir -p /app && chown user:user /app

# CPU-only PyTorch first (the default Linux wheel bundles ~2 GB of GPU libraries
# that a CPU server can't use), then the rest of the pinned requirements.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir -r /tmp/requirements.txt \
 && python -m spacy download en_core_web_sm

USER user
WORKDIR /app/backend

# Bake the models into the image so the site starts fast and needs no downloads.
COPY --chown=user:user backend/app ./app
COPY --chown=user:user backend/download_models.py .
RUN python download_models.py

COPY --chown=user:user backend/ .
COPY --chown=user:user --from=ui /ui/dist /app/frontend/dist

# Models are already in the image: stop the libraries from contacting the Hub.
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

EXPOSE 7860
# If a persistent disk is mounted at /data (paid Spaces storage), keep the database
# there so reviews survive restarts; otherwise use the container's own disk.
CMD ["sh", "-c", "if [ -d /data ] && [ -w /data ]; then export PROOFREAD_DB=/data/proofread.db; fi; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
