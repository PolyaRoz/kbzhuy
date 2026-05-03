@echo off
chcp 65001 >nul
cd /d %~dp0

if not exist .env.gigachat (
    echo Файл .env.gigachat не найден — нечего выключать.
    pause
    exit /b 0
)

REM Flip the toggle line in-place. Find /v copies all lines except the "true" one,
REM then we re-add the false line. Works without PowerShell.
findstr /v /b "KBZHUY_USE_GIGACHAT=" .env.gigachat > .env.gigachat.tmp
echo KBZHUY_USE_GIGACHAT=false>> .env.gigachat.tmp
move /y .env.gigachat.tmp .env.gigachat >nul

echo [GigaChat] Перезапускаю API без GigaChat (rule-based агент)...
docker compose -f infra/docker-compose.dev.yml up -d --no-deps api
if errorlevel 1 ( echo Ошибка запуска! & pause & exit /b 1 )

echo.
echo  GigaChat ВЫКЛЮЧЕН — работает простой агент (токены не тратятся)
echo  Агент доступен на http://localhost:8081
pause
