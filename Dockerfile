FROM python:3.11-slim

# Install build deps and tzdata for pillow if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifest first for cached installs
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . /app

# Port is set dynamically at runtime via $PORT (Render sets $PORT)
# Use uvicorn. Use shell form so $PORT expands at runtime.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1
