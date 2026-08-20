# Registry service image. Build context = repo root (monorepo constraint:
# Cloud Build source is the whole repo so workspace libs are visible).
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock conftest.py ./
COPY libs ./libs
COPY agents ./agents
COPY services ./services

# Install only the registry package's dependency closure, no dev group.
RUN uv sync --frozen --no-dev --package civicnexus-registry

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080
CMD ["sh", "-c", "uvicorn registry.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
