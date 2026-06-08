# ==========================================
# 1. Base Stage
# ==========================================
FROM python:3.11-slim AS base
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app:/shared-python

# ==========================================
# 2. Development Stage
# ==========================================
FROM base AS development
COPY engine/ .
# In dev, shared-python is mounted as a volume
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ==========================================
# 3. Production Stage
# ==========================================
FROM base AS production
COPY engine/ .
COPY shared/python /shared-python
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]