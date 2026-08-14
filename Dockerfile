# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --upgrade pip && \
    pip install -e ".[postgres]"

# Copy backend source
COPY enterprise/ enterprise/
COPY hermes_v01/ hermes_v01/
COPY pyproject.toml .

# Build frontend
FROM node:20 AS frontend
WORKDIR /app
COPY enterprise-ui/package.json enterprise-ui/package*.json ./
RUN npm ci
COPY enterprise-ui/ ./
RUN npm run build

# Final image
FROM base AS final
COPY --from=frontend /app/dist /app/static

ENV HERMES_DATABASE_URL="" \
    HERMES_JWT_SECRET="" \
    HERMES_GITHUB_APP_ID="" \
    HERMES_GITHUB_CLIENT_ID="" \
    HERMES_GITHUB_CLIENT_SECRET="" \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "enterprise.app:app", "--host", "0.0.0.0", "--port", "8000"]
