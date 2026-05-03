@echo off
chcp 65001 >nul
cd /d %~dp0

echo [GigaChat] Читаю credentials из .env.gigachat...
if not exist .env.gigachat (
    echo ОШИБКА: файл .env.gigachat не найден!
    echo Создай его по образцу и вставь GIGACHAT_CREDENTIALS из Sber Studio.
    pause
    exit /b 1
)

for /f "usebackq tokens=1,2 delims==" %%A in (".env.gigachat") do set %%A=%%B

echo [GigaChat] Перезапускаю API с GigaChat...
docker compose -f infra/docker-compose.dev.yml up -d --no-deps api
if errorlevel 1 ( echo Ошибка запуска! & pause & exit /b 1 )

echo.
echo  GigaChat ВКЛЮЧЁН — модель %KBZHUY_GIGACHAT_MODEL%
echo  Агент доступен на http://localhost:8081
pause
