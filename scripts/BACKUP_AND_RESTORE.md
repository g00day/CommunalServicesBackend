# Резервное копирование и восстановление

В проект встроен базовый механизм резервного копирования PostgreSQL, работающей в контейнере `db`.

## Файлы

- `scripts/backup-db.ps1` - создание резервной копии базы данных в формате `.dump`
- `scripts/restore-db.ps1` - восстановление базы данных из файла резервной копии
- папка `backups/` используется для хранения актуальных дампов

## Предварительные условия

- контейнер `db` должен быть запущен через `docker compose`
- пользователь, запускающий скрипты, должен иметь доступ к Docker daemon
- в Windows при необходимости PowerShell или терминал нужно запускать от имени администратора

## Создание резервной копии

Команда запускается из корня проекта:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-db.ps1
```

По умолчанию:

- используются параметры подключения из файла `.env`
- резервная копия сохраняется в каталог `backups/`
- хранятся 7 последних резервных копий

Пример запуска с изменением числа сохраняемых копий:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup-db.ps1 -KeepLast 14
```

## Восстановление базы данных

Перед восстановлением рекомендуется остановить backend, чтобы в базу не записывались новые данные:

```powershell
docker compose stop backend
```

Восстановление выполняется командой:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore-db.ps1 -BackupFile .\backups\backup_YYYY-MM-DD_HH-mm-ss.dump
```

После завершения восстановления backend можно запустить снова:

```powershell
docker compose start backend
```

## Автоматизация

Для регулярного резервного копирования скрипт `scripts/backup-db.ps1` можно запускать по расписанию:

- в Windows через Task Scheduler
- в Linux через `cron`

## Запуск регулярного резервного копирования (1 раз в сутки) для Windows

```powershell
schtasks /Create /SC DAILY /TN "CommunalServices DB Backup" /TR "powershell.exe -ExecutionPolicy Bypass -File \"C:\CourseWork\CommunalServicesBackend\scripts\backup-db.ps1\" -EnvFile \"C:\CourseWork\CommunalServicesBackend\.env\" -BackupDir \"C:\CourseWork\CommunalServicesBackend\backups\" -KeepLast 7" /ST 02:00
```