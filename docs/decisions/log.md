# Журнал решений

---

## 2026-03-31

### REF-001: Стек бэкенда — FastAPI + PostgreSQL + Redis
**Решение:** Python / FastAPI, PostgreSQL 16, Redis 7, Celery
**Причина:** Нативная экосистема для ML/AI (Claude API), async, Pydantic auto-docs
**Альтернативы:** Node.js (хуже для AI), Django (медленнее для API)

---

### REF-002: Мобильный фреймворк — React Native + Expo
**Решение:** React Native + Expo Router + Zustand + React Query
**Причина:** Один код на iOS/Android, Expo упрощает деплой и OTA-обновления
**Альтернативы:** Flutter (команда на JS), нативный (дорого)

---

### REF-003: AI-движок — Claude API (ReAct)
**Решение:** `claude-sonnet-4-6`, паттерн ReAct (Reasoning + Acting), tool-use
**Причина:** Лучшее понимание контекста, нативный tool-use, Anthropic SDK
**Альтернативы:** GPT-4 (дороже), Gemini

---

### REF-004: Аутентификация — собственный JWT
**Решение:** JWT access (15 мин) + refresh (30 дней), AsyncStorage на клиенте
**Причина:** MVP не требует Firebase, проще контролировать
**Пересмотр:** Firebase Auth в Фазе 4 (OAuth, телефон, безопасность из коробки)

---

### REF-005: Контейнерная система — цифра + буква
**Решение:** Метка = цифра + буква (1А, 2Б, 3В…)
**Причина:** Цифра = порядковый номер, буква = приём пищи. Легко подписать маркером.
**Это ключевая UX-особенность продукта.**

---

### REF-006: Alembic — один initial файл, потом инкрементальные
**Решение:** `0001_initial` содержит все таблицы; далее — отдельные файлы на каждое изменение
**Проблема (решена):** `index=True` в `Column` + явный `create_index` = дублирующийся индекс → убраны 4 лишних вызова

---

### REF-007: Mobile preview — expo export + python http.server
**Решение:** `npx expo export --platform web` → `python serve.py` на порту 8081
**Причина:** Metro Bundler (`npx expo start`) нестабилен через `preview_start` на Windows с кириллическим путём
**Следствие:** После изменений в `mobile/` нужно пересобирать: `cd mobile && npx expo export --platform web`

---

### REF-008: bat-файлы — без `>nul`, кодировка cp1251
**Решение:** Писать bat-файлы через Python с `encoding='cp1251'`, без редиректов в `nul`
**Причина:** Линтер (VS Code или другой) автоматически заменяет `>nul` на `>/dev/null`, ломая Windows-скрипты

---

## 2026-04-09

### REF-009: planId — персистентность в storage, не в React Query
**Решение:** `plan_id` хранится в SecureStore/localStorage под ключом `plan_id`; при старте `hydratePlan()` восстанавливает его
**Причина:** `plan_id` нужен всем экранам (покупки, готовка, контейнеры). Класть в React Query cache нет смысла — он не переживает перезапуск приложения. SecureStore уже используется для токенов — логично расширить тот же подход.
**Альтернативы:** AsyncStorage (менее безопасен), mmkv (доп. зависимость)

---

### REF-010: GET /plan/current — eager loading через selectinload
**Решение:** `selectinload(MealPlan.days).selectinload(DayPlan.meals)` добавлен к запросу; ответ сериализуется вручную (dict), не через `PlanResponse`
**Причина:** async SQLAlchemy не поддерживает lazy loading в async context — обращение к `plan.days` вне `await` вызывало `MissingGreenlet`. `PlanResponse` не был указан как `response_model`, поэтому FastAPI пытался сериализовать raw ORM-объект.
**Следствие:** При добавлении новых полей в ответ нужно явно добавить их в dict в `plan.py`

---

### REF-009: Mobile token storage — SecureStore (native) + localStorage (web)
**Решение:** Платформозависимое хранение: `expo-secure-store` на iOS/Android, `localStorage` на web
**Причина:** SecureStore использует Keychain/Keystore — безопасно на устройствах. На web (dev/preview) SecureStore недоступен → fallback на localStorage
**Альтернативы:** zustand persist + AsyncStorage (не шифрует), MMKV (overkill для MVP)

---

### REF-010: Auth gate — redirect в root layout
**Решение:** `AuthGate` компонент в `_layout.tsx` — проверяет `isAuthenticated` и редиректит на onboarding/tabs
**Причина:** Единая точка контроля доступа. hydrate() восстанавливает токены при запуске, пустой экран пока идёт hydration
**Следствие:** Onboarding step4 не делает `router.replace('/(tabs)')` — AuthGate сам редиректит при смене `isAuthenticated`

---

## 2026-04-10

### REF-011: API base URL — env var для prod build
**Решение:** `process.env.EXPO_PUBLIC_API_URL || 'https://api.kbzhuy.app/api/v1'` в production mode
**Причина:** `expo export` собирает в production (`__DEV__=false`), поэтому `localhost:8000` недоступен. Нужен способ переключать API URL при E2E тестировании без правки кода
**Следствие:** Для E2E: `EXPO_PUBLIC_API_URL=http://localhost:8000/api/v1 npx expo export`. Для prod: переменная не задана → используется api.kbzhuy.app

---

## 2026-04-12

### REF-012: Ollama как локальный LLM-бэкенд
**Решение:** `USE_LOCAL_LLM=true` → OpenAI-совместимый клиент к Ollama (localhost:11434). `false` → Anthropic API
**Причина:** Разработка и тестирование без платного API-ключа. Модель `qwen2.5:14b` помещается в 12GB VRAM (RTX 5070 Ti)
**Следствие:** agent.py имеет два кода: `_chat_anthropic` и `_chat_openai`. tools.py экспортирует `TOOLS` (Anthropic) и `TOOLS_OPENAI` (OpenAI формат)

### REF-013: AI-генерация плана — `use_ai` флаг
**Решение:** `POST /plan/generate` принимает `use_ai: bool = false`. При `true` — агент читает профиль и вызывает tool `build_meal_plan`. При `false` — быстрый детерминистический генератор
**Причина:** AI-путь через Ollama ~1-2 мин (многократные LLM-вызовы), детерминистический — 0.3с. Пользователь выбирает сам
**Следствие:** `build_meal_plan` tool переиспользует `MealPlannerService.generate()`. AI не изобретает план с нуля, а оркестрирует существующий сервис
