#!/usr/bin/env bash
set -e

###############################################################################
### CONFIGURATION
###############################################################################

BASE_DIR="$(cd "$(dirname "$(dirname "${BASH_SOURCE[0]}")")" && pwd)"
ENV_FILE="$BASE_DIR/api/.env"

ARQ_WORKERS=${ARQ_WORKERS:-1}
FASTAPI_WORKERS=${FASTAPI_WORKERS:-1}
UVICORN_BASE_PORT=${PORT:-${UVICORN_BASE_PORT:-8000}}

cd "$BASE_DIR"
echo "Starting Dograh Services (DOCKER) at $(date) in BASE_DIR: ${BASE_DIR}"

###############################################################################
### 1) Load env file if mounted (env normally comes from docker-compose)
###############################################################################

if [[ -f "$ENV_FILE" ]]; then
  SAVED_DB_URL="$DATABASE_URL"
  SAVED_REDIS_URL="$REDIS_URL"
  SAVED_MINIO_ENDPOINT="$MINIO_ENDPOINT"
  set -a && . "$ENV_FILE" && set +a
  if [[ -n "$SAVED_DB_URL" ]]; then export DATABASE_URL="$SAVED_DB_URL"; fi
  if [[ -n "$SAVED_REDIS_URL" ]]; then export REDIS_URL="$SAVED_REDIS_URL"; fi
  if [[ -n "$SAVED_MINIO_ENDPOINT" ]]; then export MINIO_ENDPOINT="$SAVED_MINIO_ENDPOINT"; fi
fi

###############################################################################
### 2) Run migrations
###############################################################################

alembic -c "$BASE_DIR/api/alembic.ini" upgrade heads || true

###############################################################################
### 3) Signal handling — forward TERM/INT to children for clean docker stop
###############################################################################

pids=()

shutdown() {
  echo "Received shutdown signal, stopping services..."
  for pid in "${pids[@]}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done
  wait
  exit 0
}

trap shutdown TERM INT

start() {
  local name=$1
  shift
  echo "→ Starting $name"
  "$@" &
  pids+=($!)
  echo "  $name PID $!"
}

###############################################################################
### 4) Start services (logs go to stdout for `docker logs`)
###############################################################################

start ari_manager           python -m api.services.telephony.ari_manager
start campaign_orchestrator python -m api.services.campaign.campaign_orchestrator

# Spawn FASTAPI_WORKERS independent uvicorn processes on consecutive ports
# starting at UVICORN_BASE_PORT. nginx upstream (configured in setup_remote.sh)
# balances across them with least_conn — better than uvicorn --workers for
# long-lived WebSocket connections, which would otherwise stick to whichever
# worker accepted them first.
for ((i=0; i<FASTAPI_WORKERS; i++)); do
  port=$((UVICORN_BASE_PORT + i))
  start "uvicorn$i" uvicorn api.app:app --host 0.0.0.0 --port "$port" --workers 1
  uvicorn_main_pid=$!
done

for ((i=1; i<=ARQ_WORKERS; i++)); do
  start "arq$i" python -m arq api.tasks.arq.WorkerSettings --custom-log-dict api.tasks.arq.LOG_CONFIG
done

###############################################################################
### 5) Wait — wait on uvicorn web server
###############################################################################

wait "$uvicorn_main_pid"
echo "Uvicorn exited; tearing down container."
shutdown
