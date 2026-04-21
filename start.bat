@echo off
chcp 65001
title KBZHUY Launcher
cd /d %~dp0

echo.
echo  === KBZHUY Dev Launcher ===
echo.

docker --version
if errorlevel 1 ( echo ERROR: Docker not found ^& pause ^& exit /b 1 )

echo [1/4] Building and starting app containers...
docker compose -f infra/docker-compose.dev.yml up -d
if errorlevel 1 ( echo ERROR: docker compose failed ^& pause ^& exit /b 1 )

echo [2/4] Waiting for PostgreSQL...
:wait_pg
docker compose -f infra/docker-compose.dev.yml exec -T db pg_isready -U kbzhuy
if errorlevel 1 ( timeout /t 2 /nobreak ^& goto wait_pg )
echo PostgreSQL ready.

echo [3/4] Running migrations...
docker compose -f infra/docker-compose.dev.yml run --rm api alembic upgrade head
if errorlevel 1 ( echo ERROR: migrations failed ^& pause ^& exit /b 1 )

echo [4/4] Services are running.

echo.
echo  Backend  -  http://localhost:8000
echo  Mobile   -  http://localhost:8081
echo.
echo  Press any key to STOP containers.
pause

call stop.bat
