# syntax=docker/dockerfile:1
#
# Shared backend image for the rec-engine.
# ONE image, run two ways:
#   • API    → default CMD below (uvicorn)
#   • Worker → command overridden to `python worker.py` in compose / k8s
# Both share the same heavy bootstrap (store.load + graph.build + tfidf.build),
# so building once and running it twice avoids duplicate build layers and drift.

FROM python:3.13-slim

# Container-friendly Python: no .pyc files, unbuffered stdout/stderr for live logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first — this layer is cached and only rebuilds when the lock changes,
# so source edits don't trigger a full reinstall of scikit-learn/numpy/etc.
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

# Application source (data/ is excluded via .dockerignore — loaded from Supabase at runtime).
COPY . .

# Run as a non-root user (least privilege).
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default role is the API. The worker service overrides this with `python worker.py`.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
