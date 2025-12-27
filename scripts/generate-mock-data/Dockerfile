FROM python:3.11-slim

WORKDIR /scripts

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    faker \
    sentence-transformers \
    psycopg2-binary

# Set working directory
WORKDIR /scripts

# Default command (can be overridden)
CMD ["python", "/scripts/generate-mock-data.py"]

