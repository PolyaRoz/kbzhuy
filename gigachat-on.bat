@echo off
chcp 65001 >nul
cd /d %~dp0

if not exist .env.gigachat (
    echo ОШИБКА: файл .env.gigachat не найден!
    echo Создай его по образцу и вставь GIGACHAT_CREDENTIALS из Sber Studio.
    pause
    exit /b 1
)

REM Make sure the toggle line is set to true. Strip any old USE_GIGACHAT lines first.
findstr /v /b "KBZHUY_USE_GIGACHAT=" .env.gigachat > .env.gigachat.tmp
echo KBZHUY_USE_GIGACHAT=true>> .env.gigachat.tmp
move /y .env.gigachat.tmp .env.gigachat >nul

echo [GigaChat] Перезапускаю API с GigaChat (env_file подхватится автоматически)...
docker compose -f infra/docker-compose.dev.yml up -d --no-deps api
if errorlevel 1 ( echo Ошибка запуска! & pause & exit /b 1 )

echo.
echo  GigaChat ВКЛЮЧЁН — настройки берутся из .env.gigachat
echo  Агент доступен на http://localhost:8081
pause
