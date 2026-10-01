FROM python:3.11-slim AS base

# Security: create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# System dependencies for OpenCV, PostgreSQL, and general utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libpq-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer caching)
COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY ai/requirements.txt /tmp/ai-requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/backend-requirements.txt \
    && pip install --no-cache-dir -r /tmp/ai-requirements.txt \
    && rm /tmp/backend-requirements.txt /tmp/ai-requirements.txt

# Copy application code
COPY backend/ /app/backend/
COPY ai/ /app/ai/
COPY rehabilitation/ /app/rehabilitation/

# Set PYTHONPATH so imports work across packages
ENV PYTHONPATH="/app:/app/backend:/app/ai:/app/rehabilitation"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose backend port
EXPOSE 8000

# Switch to non-root user
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
