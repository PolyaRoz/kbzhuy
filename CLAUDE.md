# КБЖУЙ — Контекст для Claude

## Что это за проект

**КБЖУЙ** — персональный ИИ-навигатор питания. Принцип: «Приготовь один раз — не думай потом».

Пользователь раз в неделю делает батч-готовку, раскладывает еду по пронумерованным контейнерам (1А, 2Б…). Приложение в каждый момент говорит: какой контейнер взять, где он лежит, как разогреть, что подготовить заранее. ИИ-агент адаптирует план к отклонениям (пиво в пятницу, ресторан, срыв).

**Стек:** React Native + Expo (mobile) / FastAPI + PostgreSQL + Redis (backend) / Claude API ReAct-агент (AI)

---

## Структура репозитория

```
kbzhuy/
├── CLAUDE.md                  ← этот файл
├── docs/                      ← документация проекта (читай первым)
│   ├── tracker.md             ← что готово / не готово по каждому компоненту
│   ├── implementation_plan.md ← план по фазам (текущая: Фаза 1)
│   ├── decisions/
│   │   ├── README.md          ← как вести журнал решений
│   │   └── log.md             ← все принятые решения с обоснованием
│   ├── architecture/          ← техническая документация по слоям
│   ├── product/               ← фичи, сценарии, UX-решения
│   └── research/              ← нутрициология, конкуренты, UX-исследования
│
├── backend/                   ← Python / FastAPI
│   ├── app/
│   │   ├── api/v1/            ← роуты (agent, auth, plan, cooking, storage…)
│   │   ├── services/          ← бизнес-логика (nutri, meal_planner, cooking_planner…)
│   │   ├── models/            ← SQLAlchemy модели
│   │   ├── schemas/           ← Pydantic схемы
│   │   └── ai/                ← AI-агент и tools
│   ├── migrations/versions/   ← Alembic (0001_initial — все таблицы)
│   ├── .env.example           ← переменные окружения
│   └── requirements.txt
│
├── mobile/                    ← React Native + Expo Router
│   ├── app/
│   │   ├── (tabs)/            ← 7 вкладок: index, plan, cooking, storage, shopping, agent, profile
│   │   └── onboarding/        ← 4 шага онбординга
│   ├── src/
│   │   ├── api/               ← axios-клиент + типы (auth, plan, cooking, shopping, storage…)
│   │   ├── components/        ← KbzhuBar, ContainerBadge, EmptyState, LoadingSpinner
│   │   ├── providers/         ← QueryProvider
│   │   └── store/             ← Zustand: authStore, planStore, shoppingStore, storageStore
│   └── dist/                  ← статическая сборка web (после npx expo export)
│
├── infra/
│   ├── docker-compose.dev.yml ← только PostgreSQL + Redis (для разработки)
│   └── docker-compose.yml     ← полный стек (prod)
│
├── data/
│   ├── recipes/basic_recipes.json
│   └── nutrition/products.json
│
├── start.bat                  ← запуск одним кликом (Windows)
└── stop.bat                   ← остановка
```

---

## Документы — когда читать

| Документ | Читать когда |
|---|---|
| `docs/tracker.md` | Начинаешь работу — понять что уже есть |
| `docs/implementation_plan.md` | Нужно понять приоритеты и следующий шаг |
| `docs/decisions/log.md` | Непонятно почему сделано именно так |
| `docs/architecture/` | Работаешь с конкретным техническим слоем |
| `docs/product/` | Проектируешь новую фичу или экран |
| `../продуктовое описание.docx` | Нужен продуктовый контекст (проблема, ЦА, ценность) |
| `../архитектура приложения.docx` | Нужна полная техническая спецификация |

> Продуктовые docx лежат в родительской папке `D:\YandexDisk\разное\КБЖУЙ\`.
> Читать через Python: `zipfile + xml.etree` (pandoc не установлен).

---

## Текущее состояние (Фаза 0 → 1)

- **Готово:** весь backend-код, все мобильные экраны, инфраструктура, миграции, исправлены баги
- **Не готово:** мобильные экраны работают на мок-данных, AI-агент — заглушка, офлайн-режим, тесты
- **Следующее:** подключить mobile к реальному API (Фаза 1), потом AI-агент (Фаза 2)

---

## Как запустить локально

```bat
# Двойной клик на start.bat
# Требует: Docker Desktop, Python 3.11+, Node.js 18+

# Вручную:
docker compose -f infra/docker-compose.dev.yml up -d
cd backend && .venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# Mobile (статика):
cd mobile && npx expo export --platform web
python ..\serve.py   # http://localhost:8081
```

---

## Ключевые решения (кратко)

- **Контейнеры:** метка = цифра+буква (1А = первый контейнер, обед А) — ключевая UX-идея
- **AI-агент:** ReAct паттерн, Claude API tool-use, model: `claude-sonnet-4-6`
- **Auth:** собственный JWT (не Firebase) — пересмотреть в Фазе 4
- **Mobile preview:** `expo export` → `python http.server` (Metro нестабилен на Windows с кириллическим путём)
- **Bat-файлы:** писать без `>nul` (линтер заменяет на `>/dev/null`)

---

## Как работаем

1. Перед реализацией — думаем и предлагаем план
2. Решения фиксируем в `docs/DECISIONS.md`
3. После завершения фазы обновляем `docs/STATUS.md`
4. Если не хватает контекста — сначала создаём/читаем документ
