@echo off
chcp 65001 >nul
cd /d %~dp0

set KBZHUY_USE_GIGACHAT=false
set KBZHUY_GIGACHAT_CREDENTIALS=

echo [GigaChat] Перезапускаю API без GigaChat (rule-based агент)...
docker compose -f infra/docker-compose.dev.yml up -d --no-deps api
if errorlevel 1 ( echo Ошибка запуска! & pause & exit /b 1 )

echo.
echo  GigaChat ВЫКЛЮЧЕН — работает простой агент (токены не тратятся)
echo  Агент доступен на http://localhost:8081
pause
