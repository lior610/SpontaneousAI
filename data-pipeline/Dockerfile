# ==========================================
# 1. Base Stage
# ==========================================
FROM python:3.11-slim AS base
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY data-pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app:/shared-python

# ==========================================
# 2. Development Stage
# ==========================================
FROM base AS development
COPY data-pipeline/ .
# In dev, shared-python is mounted via docker-compose volume
CMD ["python", "src/main.py"]

# ==========================================
# 3. Production Stage
# ==========================================
FROM base AS production
COPY data-pipeline/ .
COPY shared/python /shared-python
CMD ["python", "src/main.py"]

