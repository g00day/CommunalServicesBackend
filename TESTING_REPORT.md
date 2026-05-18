# Отчет о тестировании backend

## Объем

Покрыты автоматические проверки серверной части и сквозных бизнес-процессов backend API. Пользовательский интерфейс в этом репозитории отсутствует, поэтому UI-проверки в отчет не включены.

## Как запускать

Локально через Docker:

```bash
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from backend-tests
```

## Серверная часть

| № | Проверка | Ожидаемый результат | Фактический результат |
|---|---|---|---|
| 1 | Регистрация нового пользователя | Возвращается `201`, пользователь создается неактивным | Автотест `test_register_user_creates_inactive_account` |
| 2 | Повторная регистрация с тем же email | Возвращается `409` | Автотест `test_register_rejects_duplicate_email` |
| 3 | Вход неактивированного пользователя | Возвращается `403` | Автотест `test_login_rejects_not_activated_user` |
| 4 | Доступ к `/api/auth/me` без токена | Возвращается `401` | Автотест `test_me_requires_bearer_token` |
| 5 | Получение профиля текущего пользователя | Возвращается `200` и корректные данные | Автотест `test_me_returns_current_user_profile` |
| 6 | Создание заявки | Возвращается `201`, статус `created` | Автотест `test_create_ticket_persists_creator_and_created_status` |
| 7 | Чтение чужой заявки обычным пользователем | Возвращается `403` | Автотест `test_user_cannot_read_foreign_ticket` |
| 8 | Изменение статуса без прав | Возвращается `403` | Автотест `test_regular_user_cannot_update_ticket_status` |
| 9 | Изменение статуса менеджером | Возвращается `200`, статус меняется | Автотест `test_manager_can_update_ticket_status` |
| 10 | Отправка пустого сообщения в чат | Возвращается `400` | Автотест `test_create_message_rejects_blank_text` |
| 11 | Добавление участника чата без прав | Возвращается `403` | Автотест `test_regular_user_cannot_add_chat_participant` |
| 12 | Обновление токенов неверным типом токена | Возвращается `401` | Автотест `test_refresh_rejects_access_token_instead_of_refresh_token` |
| 13 | Автодобавление автора заявки в чат | Автор присутствует среди участников | Автотест `test_creator_is_added_to_chat_participants_on_ticket_creation` |

## Сквозные бизнес-процессы

| № | Сценарий | Ожидаемый результат | Фактический результат |
|---|---|---|---|
| 1 | Пользователь регистрируется, активирует аккаунт и входит в систему | Аккаунт активируется, вход становится доступен | Автотест `test_business_registration_activation_and_login_flow` |
| 2 | Пользователь создает и закрывает заявку | Заявка появляется в списке и переводится в `closed` | Автотест `test_business_user_creates_and_closes_ticket` |
| 3 | Менеджер обрабатывает заявку гражданина | Статусы меняются `created -> accepted -> completed` | Автотест `test_business_staff_processes_citizen_ticket` |
| 4 | Сотрудник добавляет участника, участник пишет в чат | Сообщение доступно в истории заявки | Автотест `test_business_chat_flow_with_added_participant` |
| 5 | Telegram-чат перепривязывается к последнему подтвержденному пользователю | Старый пользователь отвязывается, новый получает `tg_chat_id` | Автотест `test_business_telegram_link_rebinds_chat_to_last_confirmed_user` |

## Дефекты

- Исправлен дефект в [app/services/ticket.py](/C:/CourseWork/CommunalServicesBackend/app/services/ticket.py): после `PATCH /api/tickets/{id}/status` и `PATCH /api/tickets/{id}/close` API возвращал устаревший статус заявки из ORM-сессии. Исправление: после `commit()` сервис принудительно перечитывает актуальную сущность из БД перед формированием ответа.
- Итог повторного прогона: `18 passed`, критических дефектов по покрытым сценариям не осталось.
