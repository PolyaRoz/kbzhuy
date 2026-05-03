@echo off
chcp 65001 >nul
cd /d %~dp0
echo Rebuilding web image with latest cooking.tsx fix...
docker compose -f infra/docker-compose.dev.yml build --no-deps --no-cache web
if errorlevel 1 ( echo Build FAILED & pause & exit /b 1 )
echo Restarting web container...
docker compose -f infra/docker-compose.dev.yml up -d web
echo Done! App is at http://localhost:8081
pause
