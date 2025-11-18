#!/bin/sh
set -euo pipefail

echo "Waiting for database to be ready..."
python /app/docker/wait_for_db.py

echo "Starting application..."
exec "$@"

