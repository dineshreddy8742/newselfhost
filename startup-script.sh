#!/bin/bash
set -e

# Update and install Docker
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

mkdir -p /opt/dograh-db
cd /opt/dograh-db

cat << 'EOF' > /opt/dograh-db/docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg17
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgrespassword123
      POSTGRES_DB: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    command: >
      postgres
      -c max_connections=300
      -c shared_buffers=1GB
      -c effective_cache_size=3GB
      -c work_mem=16MB
      -c maintenance_work_mem=256MB
      -c min_wal_size=1GB
      -c max_wal_size=4GB
      -c checkpoint_completion_target=0.9
      -c wal_buffers=16MB

  redis:
    image: redis:7
    restart: always
    ports:
      - "6379:6379"
    command: redis-server --requirepass redissecret --appendonly yes
    volumes:
      - redisdata:/data

  pgbouncer:
    image: edoburu/pgbouncer:latest
    restart: always
    ports:
      - "6432:6432"
    environment:
      DB_USER: postgres
      DB_PASSWORD: postgrespassword123
      DB_HOST: postgres
      DB_PORT: "5432"
      DB_NAME: postgres
      POOL_MODE: transaction
      MAX_CLIENT_CONN: "1000"
      DEFAULT_POOL_SIZE: "40"
      MIN_POOL_SIZE: "10"
      RESERVE_POOL_SIZE: "10"
      SERVER_IDLE_TIMEOUT: "600"
      AUTH_TYPE: "plain"
    depends_on:
      - postgres

volumes:
  pgdata:
  redisdata:
EOF

docker compose up -d
