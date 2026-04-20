# Тема 8. REST API. Домашнє завдання

REST API для зберігання та управління контактами на базі FastAPI, PostgreSQL, SQLAlchemy та Pydantic.

## Реалізовано

- CRUD для контактів:
	- створення контакту;
	- отримання списку контактів;
	- отримання контакту за `id`;
	- оновлення контакту;
	- видалення контакту.
- Пошук контактів через query-параметри:
	- `first_name`
	- `last_name`
	- `email`
- Endpoint для контактів з днями народження на найближчі N днів (за замовчуванням 7).
- Валідація даних через Pydantic:
	- `EmailStr` для email;
	- перевірка телефону регулярним виразом;
	- заборона порожніх імен;
	- для імен дозволені лише літери, пробіли, дефіс та апостроф;
	- заборона змішування алфавітів в одному імені (наприклад, кирилиця + латиниця);
	- перевірка, що дата народження не у майбутньому.
- Async SQLAlchemy (2.0 style) + PostgreSQL (`asyncpg`).
- Alembic міграції.
- Swagger/OpenAPI документація (`/docs`).
- Базове логування старту застосунку та помилок БД.

## Структура модулів

```text
goit-pythonweb-hw-08/
├── main.py
├── seed.py
├── pyproject.toml
├── poetry.lock
├── docker-compose.yaml
├── Dockerfile
├── alembic.ini
├── migrations/
│   ├── env.py
│   └── versions/
│       └── 0001_init_contacts.py
├── src/
│   ├── api/
│   │   ├── contacts.py
│   │   └── utils.py
│   ├── conf/
│   │   └── config.py
│   ├── database/
│   │   ├── db.py
│   │   └── models.py
│   ├── repository/
│   │   └── contacts.py
│   └── schemas.py
└── .env.example
```

## Запуск

Пререквізити
- Python 3.13
- Poetry (рекомендовано)

### 1. Локально (Poetry)
1. Перейдіть у каталог проєкту:
```powershell
cd goit-pythonweb-hw-08
```
2. Встановіть залежності:
```powershell
poetry install
```
3. Створіть `.env` на основі `.env.example` і налаштуйте підключення до PostgreSQL.
4. Застосуйте міграції:
```powershell
poetry run alembic upgrade head
```
5. Запустіть додаток (рекомендовано — з `--reload` через `python -m`):
```powershell
poetry run python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```
Альтернатива (без reload):
```powershell
poetry run uvicorn main:app --host 127.0.0.1 --port 8000
```

Swagger буде доступний за адресою:

- `http://127.0.0.1:8000/docs`

Доадтково:
- При використанні `--reload` рекомендується запуск через `python -m uvicorn` (інакше автоматичний перезапуск може запускати процес воркера іншим інтерпретатором).

### 2. Через Docker Compose

```powershell
cd goit-pythonweb-hw-08
docker compose up --build
```

Compose піднімає:

- `db` (PostgreSQL)
- `api` (FastAPI)

При старті `api` (образ налаштований) виконує `alembic upgrade head` та запускає `uvicorn`.

### 3. Наповнення БД випадковими даними (seed)

Перед запуском seed-скрипта застосуйте міграції:

```powershell
poetry run alembic upgrade head
```

Базовий запуск (додасть 50 контактів):

```powershell
poetry run python seed.py
```

Додати N контактів:

```powershell
poetry run python seed.py --count 100
```

Очистити таблицю та створити нові дані:

```powershell
poetry run python seed.py --reset --count 50
```

Детермінований запуск (відтворювані дані):

```powershell
poetry run python seed.py --count 20 --seed 42
```

## Основні endpoint

- `POST /api/contacts/` - створити контакт
- `GET /api/contacts/` - список контактів (та пошук через query)
- `GET /api/contacts/{contact_id}` - контакт за id
- `PUT /api/contacts/{contact_id}` - повна заміна контакту
- `PATCH /api/contacts/{contact_id}` - часткове оновлення контакту
- `DELETE /api/contacts/{contact_id}` - видалити контакт
- `GET /api/contacts/upcoming-birthdays?days=7` - дні народження на найближчі дні
- `GET /api/utils/healthchecker` - healthcheck БД

## Приклади запитів

PowerShell (Windows)
```powershell
$base = "http://127.0.0.1:8000"
Invoke-RestMethod -Method Get -Uri "$base/api/contacts/"
Invoke-RestMethod -Method Get -Uri "$base/api/contacts/upcoming-birthdays?days=7"

$body = @{ first_name = "Іван"; last_name = "Іваненко"; email = "ivan@example.test" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$base/api/contacts/" -Body $body -ContentType 'application/json'
```

curl (Linux / macOS / WSL)
```bash
curl -sS "http://127.0.0.1:8000/api/contacts/" | jq
curl -sS "http://127.0.0.1:8000/api/contacts/upcoming-birthdays?days=7" | jq
curl -sS -X POST "http://127.0.0.1:8000/api/contacts/" -H 'Content-Type: application/json' -d '{"first_name":"Іван","last_name":"Іваненко","email":"ivan@example.test"}' | jq
```

### Створення контакту

```json
{
	"first_name": "Ivan",
	"last_name": "Petrenko",
	"email": "ivan.petrenko@example.com",
	"phone": "+380501112233",
	"birthday": "1998-05-20",
	"additional_data": "friend from university"
}
```

### Пошук

- `GET /api/contacts/?first_name=iv`
- `GET /api/contacts/?last_name=pet`
- `GET /api/contacts/?email=example.com`
