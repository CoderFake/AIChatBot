FROM python:3.11-slim as base

# Install essential system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    libffi-dev \
    pkg-config \
    poppler-utils \
    tesseract-ocr \
    libxml2 \
    libxslt1.1 \
    libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install Python dependencies with optimization
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    find /usr/local/lib/python3.11/site-packages -name "*.pyc" -delete && \
    find /usr/local/lib/python3.11/site-packages -name "__pycache__" -type d -exec rm -rf {} + || true

# Production stage
FROM python:3.11-slim as production

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    libffi8 \
    poppler-utils \
    tesseract-ocr \
    libxml2 \
    libxslt1.1 \
    libmagic1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Copy Python environment from base
COPY --from=base /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=base /usr/local/bin /usr/local/bin

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    mkdir -p /app/logs /app/uploads /app/documents && \
    chown -R app:app /app

# Copy only necessary application files
COPY --chown=app:app app/ ./app/
COPY --chown=app:app api/ ./api/
COPY --chown=app:app alembic/ ./alembic/
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app start.sh ./
RUN chmod +x start.sh

# Switch to non-root user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/live || exit 1

# Expose port
EXPOSE 8000

# Start command
CMD ["./start.sh"]

# Development stage  
FROM base as development

# Install development dependencies only
RUN pip install --no-cache-dir pytest pytest-asyncio httpx && \
    find /usr/local/lib/python3.11/site-packages -name "*.pyc" -delete && \
    find /usr/local/lib/python3.11/site-packages -name "__pycache__" -type d -exec rm -rf {} + || true

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy all files for development
COPY . .

# Create directories
RUN mkdir -p /app/logs /app/uploads /app/documents

# Make start script executable
RUN chmod +x start.sh

# Expose port
EXPOSE 8000

# Development command
CMD ["./start.sh"]