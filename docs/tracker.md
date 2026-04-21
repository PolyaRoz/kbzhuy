# Tracker

_Обновлено: 2026-04-12_

Обновлять после каждой завершённой задачи.
Детали задач — в `implementation_plan.md`.

---

## Прогресс по фазам

| Фаза | Задач | Готово | Статус |
|---|---|---|---|
| Фаза 1 — MVP | 14 | 14 | ✅ Завершена |
| Фаза 2 — AI-агент | 6 | 3 | 🔄 В работе |
| Фаза 3 — Хранение | 3 | 0 | ⬜ Не начата |
| Фаза 4 — Запуск | 5 | 0 | ⬜ Не начата |
| **Итого** | **28** | **17** | |

---

## Фаза 1 — MVP

| # | Задача | Статус | Дата |
|---|---|---|---|
| 1.1 | Очистка backend-дублей (`backend/services/` → `app/services/`) | ✅ done | 2026-03-31 |
| 1.2 | Импорт рецептов в БД (`seed_recipes.py`) | ✅ done | 2026-03-31 |
| 1.3 | Backend: регистрация и логин (проверить + smoke test) | ✅ done | 2026-03-31 |
| 1.4 | Backend: онбординг и профиль | ✅ done | 2026-03-31 |
| 1.5 | Backend: генерация плана питания | ✅ done | 2026-03-31 |
| 1.6 | Backend: список покупок | ✅ done | 2026-03-31 |
| 1.7 | Backend: план готовки + `/containers/current` + `/containers/today` | ✅ done | 2026-03-31 |
| 1.8 | Mobile: auth flow (регистрация, логин, refresh, SecureStore) | ✅ done | 2026-03-31 |
| 1.9 | Mobile: онбординг → API | ✅ done | 2026-04-09 |
| 1.10 | Mobile: генерация плана (кнопка → API → planStore) | ✅ done | 2026-04-09 |
| 1.11 | Mobile: главный экран (текущий контейнер, КБЖУ, "Съел") | ✅ done | 2026-04-09 |
| 1.12 | Mobile: экран "Покупки" (список из API, чекбоксы) | ✅ done | 2026-04-10 |
| 1.13 | Mobile: экран "Готовка" (план из API, раскладка по контейнерам) | ✅ done | 2026-04-10 |
| 1.14 | Ручное E2E тестирование полного флоу | ✅ done | 2026-04-10 |

---

## Фаза 2 — AI-агент

| # | Задача | Статус | Дата |
|---|---|---|---|
| 2.1 | AI-агент: tools и инфраструктура (ReAct, SDK, логирование) | ✅ done | 2026-04-10 |
| 2.2 | AI-агент: генерация плана через агента | ✅ done | 2026-04-12 |
| 2.3 | Движок отклонений (`/deviations/recalc`, перестройка плана) | ✅ done | 2026-04-12 |
| 2.4 | Mobile: экран агента (чат, быстрые действия) | ⬜ not started | — |
| 2.5 | Автогенерация задач подготовки (`generate_prep_tasks` tool) | ⬜ not started | — |
| 2.6 | Push-уведомления (Expo Notifications + Celery) | ⬜ not started | — |

---

## Фаза 3 — Хранение

| # | Задача | Статус | Дата |
|---|---|---|---|
| 3.1 | Backend: lifecycle хранения (`/storage/expiring`, статусы контейнеров) | ⬜ not started | — |
| 3.2 | Mobile: экран "Хранение" (живые данные, свайп-действия) | ⬜ not started | — |
| 3.3 | Mobile: экран "План" (недельная сетка из API, отклонения) | ⬜ not started | — |

---

## Фаза 4 — Запуск

| # | Задача | Статус | Дата |
|---|---|---|---|
| 4.1 | Офлайн-режим (persistQueryClient, оптимистичные апдейты) | ⬜ not started | — |
| 4.2 | Экран "Прогресс" (графики КБЖУ, вес, стрики) | ⬜ not started | — |
| 4.3 | Тесты (nutri_service, plan/generate, agent tools) | ⬜ not started | — |
| 4.4 | Production deploy (docker-compose, nginx, SSL) | ⬜ not started | — |
| 4.5 | App Store / Google Play (Expo EAS Build) | ⬜ not started | — |

---

## Последние изменения

| Дата | Что сделано |
|---|---|
| 2026-04-12 | 2.3: Движок отклонений завершён. `recalculate()` теперь персистит `plan.daily_targets` и помечает оставшиеся `DayPlan.notes = "адаптировано: ..."`. Исправлен off-by-one в `days_remaining`. API: POST /deviations, POST /deviations/recalc, GET /deviations/planned. |
| 2026-04-10 | 1.14: E2E тест пройден. Полный флоу: register → onboarding → plan/generate → containers/today (4 контейнера) → mark eaten → shopping-list → cooking/generate → cooking/plan. Все экраны (Дом, Покупки, Готовка) показывают реальные данные. Баг: prod build использовал api.kbzhuy.app вместо localhost — добавлен EXPO_PUBLIC_API_URL env var. |
| 2026-04-10 | 1.13: cooking.tsx подключён к API. Шаги из GET /cooking/plan, контейнеры из GET /cooking/containers. Оптимистичный toggle step → POST /cooking/steps/{id}/done. parseContainers для dict и array форматов. |
| 2026-04-10 | 1.12: shopping.tsx подключён к shoppingStore → API. Группировка по category с иконками. Оптимистичные чекбоксы с роллбеком. EmptyState при отсутствии списка. |
| 2026-04-09 | 1.11: index.tsx подключён к API. containers.py: реализованы /current, /today, /{id}/eaten с auth + selectinload. КБЖУ прогресс из planStore. |
| 2026-04-09 | 1.10: plan.tsx подключён к API. planStore: planId persistence, generate(), hydratePlan(). planApi: исправлен generate() params. Backend GET /plan/current: добавлен selectinload для days+meals. |
| 2026-04-09 | Аудит: authStore hydrate try-catch, step4 JSON.parse try-catch, storageStore fetchExpiring try-catch, planStore+shoppingStore error state |
| 2026-04-09 | 1.9: Онбординг подключён к API. authStore: onboardingCompleted + setOnboardingCompleted. step3: аллергии + бюджет. step4: email/password вместо рандома. AuthGate: проверка onboardingCompleted. |
| 2026-03-31 | Аудит кода: исправлены баги в backend (схемы, сервисы, миграции) |
| 2026-03-31 | Исправлены TypeScript-импорты в mobile stores |
| 2026-03-31 | Миграция `0001_initial`: убраны 4 дублирующихся `CREATE INDEX` |
| 2026-03-31 | Настроен Docker + запуск через `start.bat` |
| 2026-03-31 | Создана документация: `CLAUDE.md`, `docs/` структура |
| 2026-03-31 | 1.1: Удалена `backend/services/` (дубли). Все роуты уже используют `app.services.*` |
| 2026-03-31 | 1.2: `seed_recipes.py` — 24 ингредиента + 8 рецептов загружены в БД |
| 2026-03-31 | 1.3: Auth проверен (register/login/refresh/protected). Фикс: bcrypt 5→4.2.1 |
| 2026-03-31 | 1.4: Профиль проверен (onboarding/get/patch). Фикс: sex hardcode в update |
| 2026-03-31 | 1.5: Генерация плана работает (7 дней, 28 meals, контейнеры, shopping list) |
| 2026-03-31 | 1.6: Shopping list готов (создаётся при генерации, GET/PATCH endpoints работают) |
| 2026-03-31 | 1.7: Cooking plan работает (генерация, контейнеры, mark_step_done) |
| 2026-03-31 | 1.8: Mobile auth — authStore с persist, auto-refresh 401, AuthGate, profile API |

---

## Следующие шаги

**Фаза 1 MVP завершена (14/14).**

Следующая задача: **2.4 — Mobile: экран агента (чат, быстрые действия)**

---

## Как обновлять этот файл

**Взял задачу в работу:**
```
| 1.1 | ... | 🔵 in progress | 2026-04-01 |
```

**Завершил задачу:**
```
| 1.1 | ... | ✅ done | 2026-04-01 |
```

**Обновить:**
1. Статус задачи в таблице
2. Счётчик "Готово" в таблице фаз
3. Раздел "Последние изменения" — одна строка что сделано
4. Раздел "Следующие шаги" — следующая задача из плана
