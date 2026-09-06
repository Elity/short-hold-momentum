# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.10.8 AS uv

FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/

WORKDIR /opt/shm

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runtime

ARG SHM_SOURCE_REVISION=unknown

ENV PATH="/opt/shm/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SHM_SOURCE_REVISION="${SHM_SOURCE_REVISION}"

RUN useradd --uid 1000 --gid 100 --create-home --home-dir /home/shm shm \
    && mkdir -p /opt/shm/seed /var/lib/shm \
    && chown -R 1000:100 /opt/shm /var/lib/shm

COPY --from=builder --chown=1000:100 /opt/shm/.venv /opt/shm/.venv
COPY --chown=1000:100 config/ /opt/shm/seed/config/
COPY --chown=1000:100 data/ /opt/shm/seed/data/
COPY --chown=1000:100 docs/ /opt/shm/seed/docs/
COPY --chown=1000:100 experiments/ /opt/shm/seed/experiments/
COPY --chown=1000:100 paper/ /opt/shm/seed/paper/
COPY --chown=1000:100 reports/ /opt/shm/seed/reports/
COPY --chmod=0755 docker/entrypoint.sh /usr/local/bin/shm-entrypoint

USER 1000:100
WORKDIR /opt/shm

VOLUME ["/var/lib/shm"]
EXPOSE 8000

HEALTHCHECK --interval=15m --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)" || exit 1

ENTRYPOINT ["shm-entrypoint"]
CMD ["shm-service", "--host", "0.0.0.0", "--port", "8000"]
