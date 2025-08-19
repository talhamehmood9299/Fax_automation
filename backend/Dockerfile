
FROM python:3.10-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend package
COPY backend /app/backend

# Default envs (override via docker run --env-file or -e)
ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    DEBUGGER_ADDRESS=host.docker.internal:9222 \
    CHROMEDRIVER_PATH=/app/chromedriver \
    SLEEP_BETWEEN_OK_RUNS=3 \
    RAG_DB_DIR=/app/rag_corrections_db

# Expose API port
EXPOSE 8000

# Create volume for RAG DB (optional)
VOLUME ["/app/rag_corrections_db"]

# NOTE: Chromedriver must be provided/mounted at /app/chromedriver to match host Chrome version.
# Example run (Linux):
# docker run --rm -p 8000:8000 \
#   --env-file .env \
#   -e DEBUGGER_ADDRESS=host.docker.internal:9222 \
#   -e CHROMEDRIVER_PATH=/app/chromedriver \
#   -v $(pwd)/rag_corrections_db:/app/rag_corrections_db \
#   -v /absolute/path/to/chromedriver:/app/chromedriver \
#   --add-host=host.docker.internal:host-gateway \
#   fax-backend

CMD ["uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8000"]

