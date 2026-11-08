# Student IDE: one image for the web app, the code runner, the backup job and the
# optional teacher preview service (deploy/docker-compose.yml runs it each way). Build from the repo root:
#   docker build -t studentide .

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Types shared with the desktop app (frontend/src/desktop.ts, tsconfig paths): same relative layout.
COPY desktop/app/src/shared /desktop/app/src/shared
COPY desktop/sandbox/src/api.ts /desktop/sandbox/src/api.ts
RUN npm run build

FROM python:3.12-slim-bookworm
# Compilers and runtimes for the lab languages (runner.LANGUAGES).
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc g++ libc6-dev openjdk-17-jdk-headless nodejs \
 && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home --uid 10001 app \
 && mkdir -p /data /backups && chown app:app /data /backups
WORKDIR /app
COPY backend/pyproject.toml backend/
COPY backend/studentide backend/studentide
# Editable install: the code finds frontend/dist and thesis/evaluation next to backend/.
RUN pip install --no-cache-dir -e ./backend
COPY thesis/evaluation/frozen-config.json thesis/evaluation/frozen-config.json
COPY --from=web /web/dist frontend/dist
# docker CLI for the optional preview service (Sandbox Labs "Try as a student"); unused elsewhere.
COPY --from=docker:27.5.1-cli /usr/local/bin/docker /usr/local/bin/docker
ENV STUDENTIDE_DB=/data/studentide.sqlite3 PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
CMD ["uvicorn", "studentide.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
