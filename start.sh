#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo
echo " === KBZHUY Dev Launcher ==="
echo

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker not found. Install Docker Desktop first."
  exit 1
fi

if [ ! -f "backend/.env" ]; then
  echo "Creating backend/.env from .env.example..."
  cp backend/.env.example backend/.env
fi

echo "[1/4] Building images and starting containers (db, redis, api, web)..."
docker compose -f infra/docker-compose.dev.yml up -d --build

echo "[2/4] Waiting for PostgreSQL..."
until docker compose -f infra/docker-compose.dev.yml exec -T db pg_isready -U kbzhuy >/dev/null 2>&1; do
  sleep 2
done
echo "PostgreSQL ready."

echo "[3/4] Running database migrations..."
docker compose -f infra/docker-compose.dev.yml run --rm api alembic upgrade head

echo "[4/4] Services are running."
echo
echo " ================================================"
echo "  App      >  http://localhost:8081"
echo "  Backend  >  http://localhost:8000"
echo "  Docs     >  http://localhost:8000/docs"
echo " ================================================"
echo
echo "  To stop:  ./stop.sh"
echo
