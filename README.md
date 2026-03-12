# CommunalServicesBackend

## Запуск 
 - 1 Клонировать репозиторий
 - 2 Создать `.env` файл и прописать там:
```
# General settings
APP_NAME=zhkh-dispatcher-api
APP_ENV=dev
DEBUG=True

# Security (auth)
JWT_SECRET=
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=30
REFRESH_TOKEN_DAYS=1

# DataBase
POSTGRES_HOST=
POSTGRES_PORT=
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=

#SQLalchemy URL
POSTGRES_URL=

# Email
MAIL_USERNAME=
MAIL_PASSWORD=   # Пароль для приложения, сгенерированный в Google Account (https://myaccount.google.com/apppasswords)
MAIL_FROM=
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_SSL=True
APP_BASE_URL=http://localhost:8000
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