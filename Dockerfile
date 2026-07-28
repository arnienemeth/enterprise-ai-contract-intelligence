# Enterprise AI Contract Intelligence Platform — container image
# Builds a small, production-style image that serves the FastAPI app with Uvicorn.

FROM python:3.11-slim

# Don't buffer stdout/stderr (so logs appear immediately in Azure).
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System libs some AI/vector wheels need at runtime (e.g. onnxruntime -> libgomp1).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (better build caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the API needs to run.
COPY api ./api
COPY vector_store ./vector_store
COPY documents ./documents
COPY reindex.py .
# Ship the prebuilt vector store so the dashboard has data on first load.
# (Writes at runtime are ephemeral in the container — see DEPLOYMENT.md.)
COPY vector_db ./vector_db

# Azure injects the port via the PORT env var; default to 8000 locally.
ENV PORT=8000
EXPOSE 8000

# Start the API. Shell form so ${PORT} is expanded at runtime.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
