FROM node:22-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-group eval --no-install-project
COPY app/ app/
COPY scripts/ scripts/
COPY data/manifest.json data/manifest.json
COPY --from=ui /ui/dist frontend/dist
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
