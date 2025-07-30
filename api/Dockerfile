# Multi-stage build for Multi-Agent RAG System
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    pkg-config \
    poppler-utils \
    tesseract-ocr \
    libreoffice \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python dependencies
COPY api/requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM base as production

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    mkdir -p /app/logs /app/uploads /app/documents && \
    chown -R app:app /app

# Copy application code
COPY --chown=app:app api/ .

# Switch to non-root user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/live || exit 1

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# Development stage
FROM base as development

# Install development dependencies
RUN pip install pytest pytest-asyncio httpx

# Copy application code
COPY api/ .

# Create directories
RUN mkdir -p /app/logs /app/uploads /app/documents

# Expose port with hot reload
EXPOSE 8000

# Development command with hot reload
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]