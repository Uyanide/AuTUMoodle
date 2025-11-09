FROM python:3.12-slim

ARG CONFIG_PATH
ARG PUID
ARG PGID

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends tini jq \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN groupadd -f -g ${PGID:-1000} appuser || true && \
    useradd -r -m -u ${PUID:-1000} -g ${PGID:-1000} appuser 2>/dev/null || \
    useradd -r -m -u ${PUID:-1000} -g appuser appuser && \
    chown -R appuser:appuser /app
# RUN pip install --no-cache-dir -r requirements-docker.txt

ENTRYPOINT [ "tini", "--", "/app/docker/entry.sh", "/app/config.json", "appuser" ]