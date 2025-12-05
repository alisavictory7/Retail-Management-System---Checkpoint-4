#!/bin/sh
set -euo pipefail

echo "Waiting for database to be ready..."
python /app/docker/wait_for_db.py
python /app/scripts/bootstrap_super_admin.py

echo "Starting application..."
exec "$@"
