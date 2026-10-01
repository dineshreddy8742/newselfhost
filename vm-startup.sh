#!/bin/bash
exec > >(tee -i /var/log/my_startup.log)
exec 2>&1
echo "Checking volumes..."
docker volume ls
VOLUME=$(docker volume ls | grep postgres | awk '{print $2}' | head -n 1)
if [ -n "$VOLUME" ]; then
    echo "Found volume: $VOLUME. Starting a temporary postgres container..."
    docker run -d --name temp_pg -v $VOLUME:/var/lib/postgresql/data -e POSTGRES_PASSWORD=postgres -p 5432:5432 pgvector/pgvector:pg17
    echo "Waiting for postgres to start..."
    sleep 20
    echo "Dumping database..."
    docker exec temp_pg pg_dump -U postgres postgres > /tmp/dump.sql
    docker exec temp_pg pg_dump -U postgres dailsmart > /tmp/dump_dailsmart.sql || true
    ls -lh /tmp/dump*.sql
    echo "Uploading to GCS..."
    # The default SA doesn't have GCS write, so this might fail.
    gsutil cp /tmp/dump*.sql gs://dailsmart-496415_cloudbuild/ || true
else
    echo "No postgres volume found!"
fi
