# syntax=docker/dockerfile:1

# Matches the Python the project's .venv was built with.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_ENV=production \
    PORT=5002

WORKDIR /app

# Dependencies first so code edits don't invalidate the install layer.
# psycopg2-binary ships wheels, so no build toolchain is needed here.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Run unprivileged. LOG_DIR resolves to /app/logs (config.py), so that
# directory has to exist and be writable by the runtime user.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5002

# The app has no dedicated health endpoint; "/" is static and DB-free,
# which is exactly what a liveness check wants.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5002/', timeout=4).status == 200 else 1)"

# run.py already exposes a module-level `app` built by the factory.
CMD ["gunicorn", "--bind", "0.0.0.0:5002", "--workers", "2", "--timeout", "60", \
     "--access-logfile", "-", "--error-logfile", "-", "run:app"]
