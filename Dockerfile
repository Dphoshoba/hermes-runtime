# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build provenance: bake the git SHA into the image so the running UI/backend
# can prove which build a participant is seeing (M8-P1-008 forensics).
ARG GIT_SHA=unknown
ENV EVOSIA_BUILD_SHA=${GIT_SHA}
COPY scripts/git-sha.sh /tmp/git-sha.sh
RUN chmod +x /tmp/git-sha.sh

# Install Python dependencies
# Source must be present before pip install (setuptools needs pyproject +
# package dirs + README). Copy pyproject/README first so the editable install
# can discover the evosia/ and enterprise/ packages.
COPY pyproject.toml .
COPY README.md .
COPY enterprise/ enterprise/
COPY evosia/ evosia/
COPY evosia_agent/ evosia_agent/
COPY validation/m8-disposable-repo/ validation/m8-disposable-repo/
RUN pip install --upgrade pip && \
    pip install -e ".[enterprise]"
# Reconstruct deterministic git metadata for the M8 disposable fixture.
# .dockerignore strips .git (to keep the root repo out of the image), so we
# re-init the fixture as a git repo with one deterministic baseline commit.
# git is kept installed so the facilitator can run git rev-parse HEAD for
# integrity checks inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    cd /app/validation/m8-disposable-repo && \
    git init -q && \
    git config user.email "m8-fixture@local" && \
    git config user.name "M8 Fixture" && \
    git add -A && \
    git commit -q -m "disposable M8 repository" && \
    rm -rf /var/lib/apt/lists/*

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

EXPOSE ${PORT:-8000}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/api/health')" || exit 1

CMD uvicorn enterprise.app:app --host 0.0.0.0 --port ${PORT:-8000}
