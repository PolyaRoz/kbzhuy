@echo off
chcp 65001 >nul
title KBZHUY Launcher
cd /d %~dp0

echo.
echo  === KBZHUY Dev Launcher ===
echo.

docker --version >nul 2>&1
if errorlevel 1 ( echo ERROR: Docker not found. Install Docker Desktop first. ^& pause ^& exit /b 1 )

if not exist "backend\.env" (
  echo Creating backend\.env from .env.example...
  copy /Y "backend\.env.example" "backend\.env" >nul
)

echo [1/4] Building images and starting containers (db, redis, api, web)...
docker compose -f infra/docker-compose.dev.yml up -d --build
if errorlevel 1 ( echo ERROR: docker compose failed ^& pause ^& exit /b 1 )

echo [2/4] Waiting for PostgreSQL...
:wait_pg
docker compose -f infra/docker-compose.dev.yml exec -T db pg_isready -U kbzhuy >nul 2>&1
if errorlevel 1 ( timeout /t 2 /nobreak >nul ^& goto wait_pg )
echo PostgreSQL ready.

echo [3/4] Running database migrations...
docker compose -f infra/docker-compose.dev.yml run --rm api alembic upgrade head
if errorlevel 1 ( echo ERROR: migrations failed ^& pause ^& exit /b 1 )

echo [4/4] Services are running.

echo.
echo  ================================================
echo   App      ^>  http://localhost:8081
echo   Backend  ^>  http://localhost:8000
echo   Docs     ^>  http://localhost:8000/docs
echo  ================================================
echo.
echo  Press any key to STOP all containers.
pause >nul

call stop.bat
