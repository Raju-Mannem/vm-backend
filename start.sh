#!/bin/bash

# 1. Run database migrations before starting the apps
echo "Running Alembic migrations..."
uv run alembic upgrade head

# 2. Start the FastAPI application in the foreground
echo "Starting Granian API server..."
uv run granian --interface asgi main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --access-log