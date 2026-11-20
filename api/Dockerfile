# Namaa API — synthetic demo only. Not for clinical use.
# Build from repository root: docker compose build api
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    NAMAA_DATABASE_URL=sqlite:////data/namaa_demo.sqlite3

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data

COPY api/requirements.txt /tmp/requirements.txt
COPY ai /opt/namaa-ai
RUN pip install --upgrade pip \
    && pip install -r /tmp/requirements.txt \
    && pip install /opt/namaa-ai

COPY api/app ./app

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
