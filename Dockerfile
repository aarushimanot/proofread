# Proofread: the Streamlit app + AI models + SQLite in one container.
# Built for Hugging Face Spaces (Docker SDK), which expects the app on port 7860,
# but it runs anywhere Docker runs:
#     docker build -t proofread . && docker run -p 7860:7860 proofread
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    PORT=7860

# Hugging Face Spaces runs containers as user id 1000.
RUN useradd -m -u 1000 user && mkdir -p /app && chown user:user /app

# CPU-only PyTorch and the other pinned packages (same list as Streamlit Cloud uses).
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

USER user
WORKDIR /app

# Bake the models into the image so the site starts fast and needs no downloads.
COPY --chown=user:user backend/app ./backend/app
COPY --chown=user:user backend/download_models.py ./backend/
RUN cd backend && python download_models.py

COPY --chown=user:user . .

EXPOSE 7860
# If a persistent disk is mounted at /data (paid Spaces storage), keep the database
# there so reviews survive restarts; otherwise use the container's own disk.
CMD ["sh", "-c", "if [ -d /data ] && [ -w /data ]; then export PROOFREAD_DB=/data/proofread.db; fi; exec streamlit run streamlit_app.py --server.port ${PORT} --server.address 0.0.0.0 --server.headless true"]
