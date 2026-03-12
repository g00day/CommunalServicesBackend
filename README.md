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
JWT_SECRET=CHANGE_ME_SUPER_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=30
REFRESH_TOKEN_DAYS=14

# DataBase
# POSTGRES_HOST=db
# POSTGRES_PORT=5432
# POSTGRES_DB=zhkh
# POSTGRES_USER=zhkh_user
# POSTGRES_PASSWORD=zhkh_pass

#SQLalchemy URL
POSTGRES_URL=postgresql+asyncpg://postgres:@localhost:5432/DB_courseWork

# Email
MAIL_USERNAME=givernorut@gmail.com
MAIL_PASSWORD=gzvu aorj ramp odxo   # Пароль для приложения, сгенерированный в Google Account (https://myaccount.google.com/apppasswords)
MAIL_FROM=givernorut@gmail.com
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_SSL=True
APP_BASE_URL=http://localhost:8000
```
*General settings* - общие настройки приложения
*Security (auth)* - переменные, отвечающие за безопастность 
*Database* - переменные, отвечающие за подключение backend части к БД
*Email* - переменные, отвечающие за настройку 
 - 3 Собрать и запустить контейнер
 ```
 docker compose up --build
 ```
 - 4 Открыть документацию по ссылке: http://localhost:8000/docs