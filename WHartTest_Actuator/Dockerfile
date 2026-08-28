# syntax=docker/dockerfile:1.7
ARG PLAYWRIGHT_VERSION=1.61.0

FROM mcr.microsoft.com/playwright/python:v${PLAYWRIGHT_VERSION}-jammy

ARG PLAYWRIGHT_VERSION

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    WHARTTEST_ACTUATOR_DOCKER=1

COPY requirements.txt /app/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=secret,id=pip_index_url,required=false \
    set -eu; \
    if [ -s /run/secrets/pip_index_url ]; then \
        PIP_INDEX_URL="$(cat /run/secrets/pip_index_url)"; \
    else \
        PIP_INDEX_URL="https://pypi.org/simple"; \
    fi; \
    python -c 'import pathlib, sys; version = sys.argv[1]; expected = f"playwright=={version}"; lines = pathlib.Path("/app/requirements.txt").read_text(encoding="utf-8").splitlines(); raise SystemExit(0 if any(line.split("#", 1)[0].strip() == expected for line in lines) else f"ERROR: requirements.txt must pin {expected}")' "${PLAYWRIGHT_VERSION}"; \
    python -m pip install --retries 10 --timeout 60 -i "${PIP_INDEX_URL}" -r /app/requirements.txt

COPY . /app

RUN mkdir -p /app/data/browser /app/data/screenshots /app/data/traces

CMD ["python", "main.py"]
