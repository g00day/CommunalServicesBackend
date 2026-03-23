# CommunalServicesBackend

## Запуск 
 - 1 Клонировать репозиторий
 - 2 Создать `.env` файл и прописать там:
```
# General settings
APP_NAME=zhkh-dispatcher-api
APP_ENV=dev
DEBUG=True
APP_BASE_URL=http://localhost:8000

# Security (auth)
JWT_SECRET=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=30
REFRESH_TOKEN_DAYS=14

# DataBase
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_URL=postgresql+asyncpg://zhkh_user:qfRxqPg28f7ZSzK@zhkh_db:5432/zhkh

# #SQLalchemy URL
# POSTGRES_URL=postgresql+asyncpg://zhkh_user:qfRxqPg28f7ZSzK@localhost:5432/DB_courseWork


# Email
MAIL_USERNAME=givernorut@gmail.com
MAIL_PASSWORD=   # Пароль для приложения, сгенерированный в Google Account (https://myaccount.google.com/apppasswords)
MAIL_FROM=givernorut@gmail.com
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_SSL=True
MAIL_TLS=False
APP_BASE_URL=http://localhost:8000

# S3 хранилище для файлов
S3_ENDPOINT_URL=https://storage.yandexcloud.net
S3_REGION=ru-central1
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_PUBLIC_BASE_URL=
```
*General settings* - общие настройки приложения

*Security (auth)* - переменные, отвечающие за безопастность авторизации

*Database* - переменные, отвечающие за подключение backend части к БД

*Email* - переменные, отвечающие за настройку 
 - 3 Собрать и запустить контейнер
 ```
 docker compose up --build
 ```
 - 4 Открыть документацию по ссылке: http://localhost:8000/docs

