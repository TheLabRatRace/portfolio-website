# syntax=docker/dockerfile:1

# ── build ───────────────────────────────────────────────────────────────────
# Dependencies are resolved once here, into a venv, and the pip machinery that
# did it stays behind. Only /opt/venv crosses into the runtime image, so the
# thing that ships has no build tooling and no package index cache in a layer.
FROM python:3.13-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# ── runtime ─────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5002 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY . .

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 5002

# /healthz, not "/". "/" renders the about page out of the database, so a
# database that is merely slow reads as a dead container -- and the answer ECS
# gives a failing health check is to kill the task, which fixes nothing and
# takes the site down for the length of the outage. /healthz answers from the
# process alone; see _register_health() in app/__init__.py.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5002/healthz', timeout=4).status == 200 else 1)"

# One worker with threads, not two processes. The Fargate task is 0.25 vCPU,
# where a second interpreter buys no parallelism and costs ~90 MB of the 512;
# and every request here spends far longer waiting on Postgres than computing,
# which is exactly the shape threads help. Local development overrides this
# whole command in docker-compose.yml to add --reload.
CMD ["gunicorn", "--bind", "0.0.0.0:5002", \
     "--worker-class", "gthread", "--workers", "1", "--threads", "8", \
     "--timeout", "60", "--graceful-timeout", "30", \
     "--access-logfile", "-", "--error-logfile", "-", "run:app"]
