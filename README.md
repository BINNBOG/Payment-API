# Kvitto Payments API

Асинхронный API платежей на FastAPI.

## Возможности

- получение списка тарифов;
- создание платежей;
- оплата картой, через СБП или в рассрочку;
- промокод `KVITTO10` со скидкой 10%;
- идемпотентное создание платежей;
- получение платежа по UUID;
- фильтрация платежей по email и статусу;
- обработка банковских webhook;
- проверка HMAC-SHA256 подписи webhook;
- контроль допустимых переходов статуса;
- PostgreSQL и Alembic;
- запуск через Docker Compose;
- автоматические тесты и GitHub Actions.

## Стек

- Python 3.11
- FastAPI
- Pydantic v2
- SQLAlchemy AsyncIO
- PostgreSQL
- asyncpg
- Alembic
- pytest
- HTTPX
- Ruff
- Docker Compose

## Запуск через Docker

Собрать и запустить API вместе с PostgreSQL:

```bash
docker compose up --build
```

После запуска доступны:

- Swagger UI: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Healthcheck: http://127.0.0.1:8000/health

При старте контейнера API автоматически выполняется:

```bash
alembic upgrade head
```

Затем lifespan приложения создаёт отсутствующие тарифы.

Остановка контейнеров:

```bash
docker compose down
```

Команда сохраняет PostgreSQL volume. Использование `down -v` удалит данные.

## Локальный запуск

Создать `.env` на основе `.env.example`:

```env
DB_URL=postgresql+asyncpg://postgres:postgres@localhost:5431/kvitto
DB_ECHO=false
WEBHOOK_SECRET=local-webhook-secret
```

Запустить PostgreSQL:

```bash
docker compose up -d db
```

Применить миграции:

```bash
alembic upgrade head
```

Запустить API:

```bash
uvicorn app.main:app --reload
```

## Тарифы

Все суммы хранятся и возвращаются в копейках.

| Тариф | Цена |
|---|---:|
| basic | 990000 |
| standard | 1990000 |
| premium | 2990000 |

Например:

```text
19 900 ₽ = 1 990 000 копеек
```

Для денежных расчётов `float` не используется.

## API

### Тарифы

```http
GET /tariffs
```

Возвращает список тарифов.

### Создание платежа

```http
POST /payments
```

Пример:

```json
{
  "tariff_id": 2,
  "email": "user@example.com",
  "method": "card",
  "promo_code": "kvitto10"
}
```

Допустимые способы оплаты:

```text
card
sbp
installment
```

Для `installment` обязательно поле:

```json
{
  "installment_months": 3
}
```

Допустимые сроки:

```text
3, 6, 12
```

### Идемпотентность

Для защиты от повторного создания платежа передайте заголовок:

```http
Idempotency-Key: unique-operation-key
```

Первый запрос возвращает `201`, повторный запрос с тем же ключом возвращает тот же платёж с кодом `200`.

### Список платежей

```http
GET /payments
```

Доступны необязательные фильтры:

```http
GET /payments?email=user@example.com
GET /payments?status=pending
GET /payments?email=user@example.com&status=pending
```

### Получение платежа

```http
GET /payments/{payment_id}
```

Для отсутствующего платежа возвращается `404`.

## Webhook банка

```http
POST /webhooks/bank
```

Тело:

```json
{
  "payment_id": "2a842404-5705-47f6-b35b-d0c1f80495e8",
  "status": "succeeded"
}
```

Допустимые переходы:

```text
pending → succeeded
pending → failed
succeeded → refunded
```

Остальные переходы возвращают:

```http
409 Conflict
```

```json
{
  "error": "invalid_transition"
}
```

## Подпись webhook

Webhook должен содержать заголовок:

```http
X-Signature: <hex digest>
```

Подпись — HMAC-SHA256 от точных байтов тела запроса с использованием `WEBHOOK_SECRET`.

Пример вычисления:

```python
import hashlib
import hmac

body = b'{"payment_id":"2a842404-5705-47f6-b35b-d0c1f80495e8","status":"succeeded"}'

signature = hmac.new(
    key=b"local-webhook-secret",
    msg=body,
    digestmod=hashlib.sha256,
).hexdigest()

print(signature)
```

Подписанное тело должно полностью совпадать с отправленным телом, включая пробелы и переносы строк.

Неверная или отсутствующая подпись возвращает:

```http
401 Unauthorized
```

## Миграции

Создать новую миграцию:

```bash
alembic revision --autogenerate -m "migration description"
```

Применить миграции:

```bash
alembic upgrade head
```

Откатить последнюю миграцию:

```bash
alembic downgrade -1
```

## Тесты

Для API-тестов должен быть доступен PostgreSQL.

Запуск:

```bash
pytest
```

Тесты используют внешнюю транзакцию и savepoint. Все созданные тестовые платежи откатываются после завершения теста.

Покрыты:

- расчёт суммы со скидкой и без;
- промокод в разном регистре;
- рассрочка на 3, 6 и 12 месяцев;
- идемпотентность;
- получение отсутствующего платежа;
- допустимые и запрещённые переходы статуса;
- неизменность статуса после ошибки;
- HMAC-подпись webhook;
- фильтрация платежей.

## Проверка качества

```bash
ruff check .
ruff format --check .
pytest
```