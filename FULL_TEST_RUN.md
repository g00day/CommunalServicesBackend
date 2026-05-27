# Запуск всех тестов
```
cd C:\CourseWork\CommunalServicesBackend
docker compose -f docker-compose-full-test.yaml up --build backend-tests --abort-on-container-exit --exit-code-from backend-tests
docker compose -f docker-compose-full-test.yaml down --remove-orphans
```

```
cd C:\CourseWork\ComunalServicesFrontend
docker compose -f docker-compose.selenium.yml up --build --abort-on-container-exit --exit-code-from frontend-selenium-tests
docker compose -f docker-compose.selenium.yml down --remove-orphans

```

## Просмотр frontend-тестов

Во время запуска Selenium-тестов открыть в браузере:

```
http://localhost:7900/?autoconnect=1&resize=scale&password=secret
```


