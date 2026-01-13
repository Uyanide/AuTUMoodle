FROM python:3.12-slim

ARG SESSION_TYPE

ENV SESSION_TYPE=${SESSION_TYPE}
ENV CONFIG_PATH=/app/config.json
ENV BROWSER=chromium
ENV USER=appuser
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends tini gosu \
  && rm -rf /var/lib/apt/lists/*

RUN groupadd -r ${USER} && useradd -m -r -g ${USER} ${USER}

WORKDIR /app
COPY . /app
COPY docker/install.sh /tmp/install.sh
RUN chmod +x /tmp/install.sh && /tmp/install.sh && rm /tmp/install.sh

ENTRYPOINT [ "tini", "--", "/app/docker/entry.sh" ]
