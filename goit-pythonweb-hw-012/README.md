# Фінальне завдання. Contacts REST API

Фінальний проєкт курсу FullStack Web Development with Python. Застосунок побудований на FastAPI, async SQLAlchemy, PostgreSQL, Redis, JWT, Alembic, Docker Compose, Sphinx і pytest.

## Реалізовано

- CRUD для контактів з ізоляцією даних за поточним користувачем.
- Реєстрація, підтвердження email, повторне надсилання листа підтвердження.
- Логін через `OAuth2PasswordRequestForm`.
- JWT `access_token` і `refresh_token`.
- Ротація refresh-токенів через `POST /api/auth/refresh`.
- Logout із відкликанням refresh-токена.
- Password reset через email і одноразовий random token, у БД зберігається тільки hash.
- Redis cache для `get_current_user` з ключем `user:{username}` і TTL 15 хвилин.
- Інвалідація кеша після підтвердження email, оновлення аватара і reset password.
- RBAC ролі `user` та `admin`.
- `PATCH /api/users/avatar` доступний тільки адміністратору і оновлює власний avatar поточного admin-користувача.
- Rate limit для `GET /api/users/me`: 10 запитів на хвилину.
- CORS middleware і healthcheck.
- Sphinx autodoc документація.
- Unit та integration tests з покриттям понад 75%.
- Docker Compose для API, PostgreSQL і Redis.

## Стек

- Python 3.10+
- FastAPI
- SQLAlchemy 2 async
- PostgreSQL + asyncpg
- Redis
- Alembic
- Pydantic v2
- fastapi-mail
- Cloudinary
- pytest, pytest-asyncio, pytest-cov
- Sphinx

## Запуск через Docker Compose

1. Створити `.env`:

```bash
cp .env.example .env
```

2. Заповнити секрети у `.env`:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `JWT_SECRET`
- SMTP змінні `MAIL_*`
- Cloudinary змінні `CLD_NAME`, `CLD_API_KEY`, `CLD_API_SECRET`

Автоперевірка конфігурації не дозволить старт із тестовими секретами.
```bash
python scripts/check_config.py --mode build
```
Результат автоперевірки:

![Build Check](screens/01_config_build_check.png)

3. Запустити:

```bash
docker compose up --build
```

Compose піднімає:

- `db` - PostgreSQL
- `redis` - Redis
- `api` - FastAPI, який виконує `alembic upgrade head` і запускає Uvicorn

Dockerfile використовує `python:3.10-slim` і встановлює залежності через Poetry з `poetry.lock`, тому збірка є відтворюваною.
Під час збірки додатково виконується `poetry check` і `python scripts/check_config.py --mode build`.
Під час старту `api` виконується `python scripts/check_config.py --mode runtime`; контейнер не запуститься, якщо `.env` містить placeholder-секрети, некоректні URL, TTL або несумісні SMTP-прапорці.

Результат запуску Docker Compose:

![Docker Compose Up](screens/02_docker_compose_up.png)
![Docker Compose PS](screens/03_docker_compose_ps.png)

Swagger UI:

```text
http://127.0.0.1:8000/docs
```
Swagger UI з основними endpoint:

![Swagger UI з endpoints](screens/04_swagger_endpoints.png)

Healthcheck:

```text
GET http://127.0.0.1:8000/api/utils/healthchecker
```

Результат healthcheck:

![Healthcheck API](screens/05_healthcheck.png)

Alembic міграції і таблиці:
```bash
docker compose exec api alembic upgrade head
docker compose exec db psql -U postgres -d contacts_db -c "\dt"
```
Результат міграції і таблиць:
![Alembic and tables](screens/06_alembic_tables.png)

## Перевірка функціоналу

Auth:

![Auth register](screens/07_auth_register_201.png)
![Email confirmed](screens/08_email_confirmed.png)
![Login access + refresh](screens/09_login_access_refresh.png)
![Refresh rotation success](screens/10_refresh_rotation_success.png)
![Refresh reuse rejected](screens/11_refresh_reuse_rejected.png)

Users, rate limit, cache:

![Users me authorized](screens/12_users_me_authorized.png)
![Users rate limit 429](screens/13_users_rate_limit_429.png)
![Redis user cache key TTL](screens/14_redis_user_cache_key_ttl.png)

Contacts:

![Contact create 201](screens/15_contact_create_201.png)
![Contacts list](screens/16_contacts_list.png)
![Contact update patch](screens/17_contact_update_patch.png)

Password reset:

![Password reset request](screens/18_password_reset_request.png)
![Password reset confirm](screens/19_password_reset_confirm.png)
![Password reset old password rejected](screens/20_password_reset_old_password_rejected.png)
![Password reset new password login](screens/21_password_reset_new_password_login.png)

Avatar RBAC:

![Avatar user forbidden](screens/22_avatar_user_forbidden_403.png)
![Admin login](screens/23_admin_login.png)
![Avatar admin success](screens/24_avatar_admin_success.png)

## Змінні середовища

`.env` не додається в git. Актуальний шаблон знаходиться у `.env.example`.

Ключові змінні:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/contacts_db
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=replace-with-a-long-random-secret
ACCESS_TOKEN_EXPIRE_SECONDS=3600
REFRESH_TOKEN_EXPIRE_SECONDS=604800
PASSWORD_RESET_TOKEN_EXPIRE_SECONDS=3600
USER_CACHE_TTL_SECONDS=900
```

У Docker Compose `DATABASE_URL` і `REDIS_URL` для API формуються під внутрішню мережу контейнерів.
Усі placeholder-значення з `.env.example` потрібно замінити перед запуском: runtime-перевірка не дозволить старт із тестовими секретами.

## Локальний запуск без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install "poetry==2.3.4"
poetry install --no-root
cp .env.example .env
```

Після цього заповни `.env` реальними значеннями для PostgreSQL, Redis, SMTP, Cloudinary і `JWT_SECRET`, потім виконай:

```bash
poetry run python scripts/check_config.py --mode runtime
poetry run alembic upgrade head
poetry run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Для локального запуску потрібні окремо запущені PostgreSQL і Redis.

## Seed користувача

У Docker-контейнері створити звичайного підтвердженого користувача і тестові контакти:

```bash
docker compose exec api python seed.py --count 20
```

Створити або оновити користувача як адміністратора:

```bash
docker compose exec api python seed.py --admin --username admin --email admin@example.com --password StrongPass123
```

Для локального запуску без Docker використовуй ті самі аргументи через `poetry run python seed.py`.

Секрети адміністратора передаються тільки через CLI-параметри, hardcoded admin-пароля у проєкті немає.

## Основні endpoint

Auth:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/confirmed_email/{token}`
- `POST /api/auth/request_email`
- `POST /api/auth/password-reset/request`
- `POST /api/auth/password-reset/confirm`

Users:

- `GET /api/users/me`
- `PATCH /api/users/avatar` - тільки роль `admin`, оновлює власний avatar

Contacts:

- `POST /api/contacts/`
- `GET /api/contacts/`
- `GET /api/contacts/{contact_id}`
- `PUT /api/contacts/{contact_id}`
- `PATCH /api/contacts/{contact_id}`
- `DELETE /api/contacts/{contact_id}`
- `GET /api/contacts/upcoming-birthdays?days=7`

Utils:

- `GET /api/utils/healthchecker`

## Приклади запитів

Реєстрація:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"user01","email":"user01@example.com","password":"password123"}'
```

Логін:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user01&password=password123"
```

Успішна відповідь містить обидва токени:

```json
{
  "access_token": "<access-jwt>",
  "refresh_token": "<refresh-jwt>",
  "token_type": "bearer"
}
```

Оновлення токенів:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh-jwt>"}'
```

Password reset request:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/password-reset/request" \
  -H "Content-Type: application/json" \
  -d '{"email":"user01@example.com"}'
```

Password reset confirm:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/password-reset/confirm" \
  -H "Content-Type: application/json" \
  -d '{"token":"<password-reset-token-from-email>","new_password":"newpassword123"}'
```

Захищений endpoint:

```bash
curl "http://127.0.0.1:8000/api/users/me" \
  -H "Authorization: Bearer <access-jwt>"
```

Оновлення власного аватара адміністратором:

```bash
curl -X PATCH "http://127.0.0.1:8000/api/users/avatar" \
  -H "Authorization: Bearer <admin-access-jwt>" \
  -F "file=@avatar.jpg"
```

Звичайний користувач отримає `403 Forbidden`.

## Тести

Запуск повного набору з перевіркою покриття:

```bash
poetry run pytest --cov=src --cov-report=term-missing --cov-fail-under=75
```

Тести включають:

- **Repository layer**: CRUD контактів, фільтрація за власником, refresh-token записи, password-reset token записи, оновлення пароля.
- **Service layer**: password hashing, JWT access/refresh/email token helpers, password-reset token hashing, Redis cache lifecycle, email helpers, avatar/Cloudinary upload adapters, user service orchestration.
- **Router / API layer**: прямі unit-тести route-функцій auth/contacts для success, `404`, `409`, `401`, reset/email branches; integration auth flow (`register`, email confirmation, `login`), refresh token rotation/logout, password reset request/confirm, `/users/me`, rate limit, CORS preflight, admin-only avatar endpoint, повний contacts workflow (`create`, duplicate conflict, list/search, `get`, `put`, `patch`, upcoming birthdays, `delete`).
- **Database layer**: session manager lifecycle, rollback path, `get_db` dependency.

Остання локальна перевірка:

```text
60 passed
Required test coverage of 75% reached. Total coverage: 95.07%
```

Остання перевірка в Docker-контейнері `api`:

```text
60 passed
Required test coverage of 75% reached. Total coverage: 95.07%
```

## Автоперевірка конфігурації

Build-time перевірка:

```bash
poetry run python scripts/check_config.py --mode build
```

Runtime перевірка:

```bash
poetry run python scripts/check_config.py --mode runtime
```

Runtime перевірка падає з ненульовим exit code, якщо:

- `JWT_SECRET` короткий або залишився placeholder;
- `DATABASE_URL` або `REDIS_URL` мають неправильний scheme;
- TTL токенів некоректні або access token живе довше за refresh token;
- SMTP або Cloudinary змінні залишились placeholder-значеннями;
- `MAIL_STARTTLS=True` і `MAIL_SSL_TLS=True` одночасно;
- `CORS_ORIGINS` містить некоректний origin.

## Sphinx документація

Збірка HTML-документації:

```bash
poetry run sphinx-build -b html docs docs/_build/html
```

Документація використовує `sphinx.ext.autodoc` і описує:

- `main`
- `src.api.*`
- `src.repository.*`
- `src.services.*`

Головна сторінка згенерованої документації:

![Sphinx index](screens/25_sphinx_docs_index.png)

Сторінка API-документації:

![Sphinx API docs](screens/26_sphinx_api_docs.png)

## Міграції

Застосувати міграції:

```bash
poetry run alembic upgrade head
```

У Docker Compose міграції застосовуються автоматично під час старту `api`; вручну їх можна повторити командою `docker compose exec api alembic upgrade head`.

Міграція створює таблиці:

- `users` з полем `role`
- `contacts`
- `refresh_tokens`
- `password_reset_tokens`

## Примітки

- `.env` і локальні артефакти не мають потрапляти в git.
- Password reset token не є JWT: генерується random URL-safe token, а в БД зберігається SHA-256 hash.
- Email verification token має `token_type=email_verification`.
- Access token має `token_type=access`.
- Refresh token має `token_type=refresh` і `jti`.
