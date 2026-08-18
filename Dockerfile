# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python dependencies
# Source must be present before pip install (setuptools needs pyproject +
# package dirs + README). Copy pyproject/README first so the editable install
# can discover the evosia/ and enterprise/ packages.
COPY pyproject.toml .
COPY README.md .
COPY enterprise/ enterprise/
COPY evosia/ evosia/
RUN pip install --upgrade pip && \
    pip install -e ".[postgres]"

# Build frontend
FROM node:22 AS frontend
WORKDIR /app
COPY enterprise-ui/package.json enterprise-ui/package*.json ./
RUN npm ci
COPY enterprise-ui/ ./
RUN npm run build

# Final image
FROM base AS final
COPY --from=frontend /app/dist /app/static

ENV EVOSIA_DATABASE_URL="" \
    EVOSIA_JWT_SECRET="" \
    EVOSIA_GITHUB_APP_ID="" \
    EVOSIA_GITHUB_CLIENT_ID="" \
    EVOSIA_GITHUB_CLIENT_SECRET="" \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "enterprise.app:app", "--host", "0.0.0.0", "--port", "8000"]
