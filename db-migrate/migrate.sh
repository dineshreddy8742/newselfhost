#!/bin/bash
set -e

# Wait for Cloud SQL proxy to start
sleep 5

echo "Starting database migration from VM to Cloud SQL..."

# Use password for VM Postgres
export PGPASSWORD="postgres"
echo "Testing connection to VM..."
psql -h 10.128.0.3 -U postgres -d postgres -c "SELECT 1;" || true

echo "Dumping old database 'postgres' from VM..."
pg_dump -h 10.128.0.3 -U postgres postgres > /tmp/dump.sql

# Now set password for new Cloud SQL instance
export PGPASSWORD="$DB_PASSWORD"

echo "Restoring to Cloud SQL via proxy..."
psql -h 127.0.0.1 -U postgres dailsmart < /tmp/dump.sql

echo "Migration completed successfully!"
