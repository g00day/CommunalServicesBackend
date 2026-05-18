# CommunalServicesBackend

Backend для сервиса коммунальных заявок на FastAPI.

## Что лучше передавать сокоманднику

Самый удобный вариант:

1. Залить проект в Git-репозиторий.
2. Добавить в репозиторий файл `.env.example`.
3. Настоящий `.env` передать отдельно в личные сообщения или создать новый с его значениями.

Если передаёшь проект архивом, не включай туда:

- `.venv`
- `.git`
- `.env`
- `backend.tar`
- `__pycache__`
- содержимое `ml/artifacts`, `ml/models`, `ml/data/generated`, если оно не нужно для демонстрации

## Быстрый запуск только backend

Этот вариант не требует соседнего репозитория с Telegram-ботом.

1. Установить Docker Desktop.
2. Скопировать `.env.example` в `.env`.
3. При необходимости заполнить значения в `.env`.
4. Из корня проекта выполнить:

```powershell
docker compose -f docker-compose.backend-only.yml up --build
```

После запуска документация будет доступна по адресу:

- `http://localhost:8000/docs`

## Полный запуск backend + Telegram bot

Текущий файл `docker-compose.yml` ожидает, что рядом лежит второй репозиторий:

```text
<parent-folder>/
  CommunalServicesBackend/
  CommunalServicesTGbot/
```

Потому что в compose используется путь:

```text
../CommunalServicesTGbot
```

Шаги:

1. Положить оба проекта в одну родительскую папку.
2. В `CommunalServicesBackend` создать `.env` на основе `.env.example`.
3. Запустить:

```powershell
docker compose up --build
```

## Переменные окружения

Готовый шаблон лежит в файле `.env.example`.

Важно:

- `APP_BASE_URL` не должен быть пустым.
- Для Docker-запуска backend использует хост БД `db`.
- Для локального запуска без Docker нужно поменять `POSTGRES_URL`, например на `localhost`.
- Если не нужен Telegram-бот, можно оставить `TELEGRAM_BOT_INTERNAL_SECRET` пустым при запуске через `docker-compose.backend-only.yml`.
- Если не нужны загрузки файлов в S3, соответствующие ключи можно оставить пустыми, если этот функционал не используется.

## Локальный запуск без Docker

1. Установить Python 3.12.
2. Создать виртуальное окружение.
3. Установить зависимости:

```powershell
pip install -r req.txt
```

4. Поднять PostgreSQL и указать корректный `POSTGRES_URL` в `.env`.
5. Запустить приложение:

```powershell
uvicorn app.main:app --reload
```

## Рекомендация по передаче проекта

Если нужно просто "скинуть весь код", лучше передать сокоманднику:

- этот backend-репозиторий
- файл `.env.example`
- отдельно реальные секреты или новый `.env`
- при необходимости второй репозиторий `CommunalServicesTGbot`

Так у него получится либо быстро поднять только backend, либо собрать полный стенд без лишних ручных правок.
