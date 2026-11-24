# Adrobot — Keitaro campaign manager

Веб-приложение для создания кампаний Keitaro с двумя потоками и редактирования набора офферов. Backend: FastAPI, SQLAlchemy 2 и Alembic. Frontend: React + TypeScript, Material UI.

## Возможности

- Поиск офферов через Keitaro Admin API.
- Создание кампании с гео, стартовым оффером, группой, источником и доменом.
- Поток 1 отправляет посетителей из выбранной страны на `https://google.com`; поток 2 направляет остальных на офферы.
- Добавление и удаление офферов в сохранённой кампании. Доли перераспределяются поровну и всегда дают 100%; последний оффер удалить нельзя.
- Локальная история созданных кампаний в SQLAlchemy.

## Требования

- Python 3.11+
- Node.js 20+
- Keitaro с Admin API key и доступом к API кампаний, офферов, групп, источников и доменов.

## Конфигурация

Скопируйте `.env.example` в `.env` в корне проекта и заполните `KEITARO_API_ADDRESS` и `KEITARO_API_KEY`. `.env` исключён из Git.

`KEITARO_API_ADDRESS` можно указать как корневой адрес трекера либо полный адрес `/admin_api/v1`. Для тестового стенда заданы ID каталога: группа `10332`, источник `836`, домен `1813`. Их можно переопределить через `KEITARO_GROUP_ID`, `KEITARO_SOURCE_ID` и `KEITARO_DOMAIN_ID`. Маршруты — относительные к `/admin_api/v1` и настраиваются через `KEITARO_*_PATH`.

## Запуск backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install alembic
alembic upgrade head
uvicorn app.main:app --reload
```

API будет доступен на `http://localhost:8000`, документация Swagger — `http://localhost:8000/docs`. SQLite по умолчанию создаётся в `backend/adrobot.db`. Для другого SQLAlchemy URL задайте `DATABASE_URL`.

## Запуск frontend

В отдельном терминале:

```powershell
cd frontend
npm install
npm run dev
```

Откройте `http://localhost:5173`. Vite проксирует `/api` на локальный FastAPI.

Для production сборки выполните `npm run build` в `frontend`.

## Запуск всего проекта в Docker

Установите Docker с Compose plugin, скопируйте `.env.example` в `.env`, задайте Keitaro API параметры и замените `POSTGRES_PASSWORD` на надёжный пароль. Из корня проекта выполните:

```powershell
docker compose up --build -d
```

Приложение будет доступно на `http://localhost:8080` (или на порту из `APP_PORT`), Swagger — на `http://localhost:8080/docs`. Compose запускает PostgreSQL с постоянным volume `postgres_data`; backend ждёт готовности базы, применяет Alembic миграции и стартует FastAPI. Остановка без удаления данных: `docker compose down`. Для полного удаления контейнеров и данных PostgreSQL: `docker compose down -v`.

## Миграции

Миграции находятся в `backend/migrations`. После изменения SQLAlchemy моделей создайте миграцию из каталога `backend`:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

Откат на предыдущую миграцию: `alembic downgrade -1`.

## Интеграция Keitaro

Backend обращается к `/admin_api/v1` с заголовком `Api-Key`. При создании кампании он читает справочники групп, доменов и источников (они read-only на учебном стенде), создаёт кампанию, затем создаёт два отдельных потока через `POST /streams`. Редактор получает потоки кампании и целиком заменяет поле `offers` у потока «Офферы» через `PUT /streams/{id}`. Секретный ключ используется только backend и не попадает во frontend.
