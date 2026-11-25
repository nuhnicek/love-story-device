# Keychain relay v2 - tiny image, standard library only.
#   docker compose up -d --build        (see README.md)
FROM python:3.12-slim
RUN useradd -r -u 10001 -s /usr/sbin/nologin keychain
COPY relay.py /app/relay.py
# config.json, state.json and battery.csv live in the mounted /data volume
WORKDIR /data
USER keychain
EXPOSE 7070 8080
CMD ["python3", "-u", "/app/relay.py", "--config", "/data/config.json", "--state", "/data/state.json"]
