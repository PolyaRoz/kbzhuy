@echo off
chcp 65001 >nul
echo.
echo  Останавливаю КБЖУЙ...

docker compose -f infra/docker-compose.dev.yml stop

echo  Готово. Docker-тома сохранены (данные БД не удалены).
echo  Для полного сброса: docker compose -f infra/docker-compose.dev.yml down -v
echo.
