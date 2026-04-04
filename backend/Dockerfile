FROM python:3.11-slim-bookworm

# System dependencies for OpenCV headless + WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libffi-dev \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Default port
ENV PORT=8000

# Run migrations (allow failure on first boot) then start server
CMD bash -c "alembic upgrade head || echo 'Migration warning - will retry on next deploy'; uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2"
