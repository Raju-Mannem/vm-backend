#!/bin/bash

# 1. Run database migrations before starting the apps
echo "Running Alembic migrations..."
uv run alembic upgrade head

# 2. Start the Celery worker in the background
# The '&' at the end is crucial—it detaches the process so the script continues
echo "Starting Celery worker..."
uv run celery -A app.core.celery_app.celery_app worker --loglevel=info -c 2 &

# 3. Start the FastAPI application in the foreground
echo "Starting Granian API server..."
uv run granian --interface asgi main:app --host 0.0.0.0 --port 8000 --workers 2