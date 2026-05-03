@echo off
chcp 65001 >nul
cd /d %~dp0

REM Disable GigaChat by flipping the toggle in .env.gigachat (the file is loaded by docker-compose).
if exist .env.gigachat (
    powershell -NoProfile -Command "(Get-Content .env.gigachat) -replace 'KBZHUY_USE_GIGACHAT=true','KBZHUY_USE_GIGACHAT=false' | Set-Content .env.gigachat"
)

echo [GigaChat] Перезапускаю API без GigaChat (rule-based агент)...
docker compose -f infra/docker-compose.dev.yml up -d --no-deps api
if errorlevel 1 ( echo Ошибка запуска! & pause & exit /b 1 )

echo.
echo  GigaChat ВЫКЛЮЧЕН — работает простой агент (токены не тратятся)
echo  Агент доступен на http://localhost:8081
pause
