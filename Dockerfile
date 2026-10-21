# syntax=docker/dockerfile:1

# ---- build: install the package into a self-contained venv ----
FROM python:3.13-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

# ---- runtime: venv only, non-root ----
FROM python:3.13-slim

LABEL org.opencontainers.image.title="nexus-vram-router" \
      org.opencontainers.image.description="Ollama-compatible proxy that routes each request to the GPU node with room for the model" \
      org.opencontainers.image.licenses="MIT"

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=build /opt/venv /opt/venv

RUN useradd --system --uid 10001 --no-create-home nexus
USER nexus

EXPOSE 11434

# /router/health answers from the router itself, so a down GPU node doesn't mark the container unhealthy.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:11434/router/health', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["nexus-router"]
CMD ["--config", "/config/config.yaml"]
