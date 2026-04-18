FROM python:3.11-slim AS base

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY data/ ./data/
COPY frontend/ ./frontend/

RUN uv pip install --system -e ".[dev]"

# ─── API ─────────────────────────────────────────────────────────────────────

FROM base AS api

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ─── Frontend ─────────────────────────────────────────────────────────────────

FROM base AS frontend

RUN uv pip install --system "streamlit>=1.40"

EXPOSE 8501
CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
