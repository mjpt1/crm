FROM python:3.12-slim

# ─── System dependencies ──────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ─── Environment setup ────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# ─── Working directory ────────────────────────────────────────────────────────
WORKDIR /app

# ─── Install Python dependencies ─────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─── Copy project source ─────────────────────────────────────────────────────
COPY . .

# ─── Collect static files ─────────────────────────────────────────────────────
RUN python manage.py collectstatic --noinput || true

# ─── Create non-root user for security ────────────────────────────────────────
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN chown -R appuser:appgroup /app
USER appuser

# ─── Expose port ──────────────────────────────────────────────────────────────
EXPOSE 8000

# ─── Entry point ──────────────────────────────────────────────────────────────
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "gthread", \
     "--threads", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
