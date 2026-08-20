#!/bin/sh
set -e

echo "Running database migrations..."
uv run alembic upgrade head

echo "Migrations complete. Starting server..."
exec "$@"