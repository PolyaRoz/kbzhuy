# KBZHUY

Приложение КБЖУЙ: backend на FastAPI, мобильный/web-клиент на Expo и локальная инфраструктура через Docker Compose.

## Что нужно установить

- Git
- Docker Desktop

Для разработки мобильной части без Docker дополнительно нужен Node.js, но базовый запуск проекта идет через `start.bat`.

## Первый запуск на новом компьютере

```powershell
git clone https://github.com/PolyaRoz/kbzhuy.git
cd kbzhuy
copy backend\.env.example backend\.env
start.bat
```

После запуска:

- Backend API: http://localhost:8000
- Web/mobile preview: http://localhost:8081

`start.bat` собирает контейнеры, поднимает PostgreSQL и Redis, ждет готовности базы и применяет миграции.

## Остановка

Если приложение запущено через `start.bat`, нажмите любую клавишу в окне запуска. Также можно остановить вручную:

```powershell
stop.bat
```

## Переменные окружения

Локальные секреты хранятся в `backend/.env`. Этот файл не должен попадать в git.

Пример настроек лежит в `backend/.env.example`.

Важные переменные:

- `KBZHUY_DATABASE_URL` - подключение к PostgreSQL
- `KBZHUY_REDIS_URL` - подключение к Redis
- `KBZHUY_SECRET_KEY` - секрет для токенов
- `KBZHUY_ANTHROPIC_API_KEY` - ключ для cloud AI, если используется
- `KBZHUY_USE_LOCAL_LLM` - включение локальной LLM через Ollama
- `KBZHUY_LOCAL_LLM_URL` - адрес локальной LLM

## Данные проекта

Данные, необходимые для локального запуска, лежат в репозитории:

- `data/recipes` - базовые рецепты
- `data/nutrition` - продукты и нутриенты
- `data/culinary` - кулинарная база и структурированные markdown-рецепты

Не коммитятся:

- `backend/.env`
- `backend/.venv`
- `mobile/node_modules`
- `mobile/.expo`
- `mobile/dist`
- временные логи

## Полезные команды

Проверить изменения:

```powershell
git status
```

Сохранить новую версию:

```powershell
git add .
git commit -m "Update KBZHUY app"
git push origin master
```

Обновить проект на другом компьютере:

```powershell
git pull origin master
```
