# Тема 6. SQLAlchemy та міграції схеми даних. Домашнє завдання


## Реалізовано

- SQLAlchemy-моделі для таблиць:
	- `students`
	- `groups`
	- `teachers`
	- `subjects` (з викладачем)
	- `grades` (оцінка + дата)
- Alembic-міграції для PostgreSQL (`migrations/versions/0001_init_schema.py`)
- CLI-додаток на `argparse` з CRUD для всіх моделей
- Базове логування CLI-команд (старт, успіх, помилка)
- Генерація тестових даних через `Faker` як CLI-дія `populate` (замість окремого `seed.py`)
- Файл `my_select.py` з функціями `select_1` ... `select_10`
- 2 додаткові запити підвищеної складності:
	- середній бал, який певний викладач ставить певному студентові
	- оцінки студентів групи з предмета на останньому занятті

Для реалізації обрано sync SQLAlchemy через простоту використання у CLI-застосунку та кращу підтримку міграцій Alembic. Асинхронність не покращить продуктивність у цьому сценарії, а синхронний код легше дебажити і підтримувати в рамках завдання. Для домашнього завдання фокус на схемі, міграціях і SQL-запитах, тому sync-підхід є практичним вибором.


## Структура модулів

```text
goit-pythonweb-hw-06/
	main.py
	models.py
	crud.py
	faker_data.py
	my_select.py
	Dockerfile
	requirements.txt
	.env.example
	alembic.ini
	conf/
		db.py
	migrations/
		env.py
		script.py.mako
		versions/
			0001_init_schema.py
```


## Запуск

1. Перейдіть у папку домашньої роботи:

```bash
cd goit-pythonweb-hw-06
```

2. Встановіть залежності:

```bash
py -m pip install -r requirements.txt
```

3. Запустіть PostgreSQL у Docker:

```bash
docker run --name hw06-postgres -p 5432:5432 -e POSTGRES_PASSWORD=hw06_secure_pass_2026 -d postgres
```

4. Налаштуйте змінну середовища `DATABASE_URL`:

```bash
copy .env.example .env
```

або встановіть напряму в PowerShell для поточної сесії:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://postgres:hw06_secure_pass_2026@localhost:5432/postgres"
```

5. Застосуйте міграції:

```bash
alembic upgrade head
```

6. Заповніть БД тестовими даними:

```bash
py main.py -a populate --reset
```

`populate` у цьому проєкті виконує роль `seed.py` (відповідно до додаткового завдання, де CRUD CLI замінює окремий seed-скрипт).

7. Приклади запуску вибірок:

```bash
py main.py -a select --query 1
py main.py -a select --query 2 --subject-id 1
py main.py -a select --query 10 --student-id 1 --teacher-id 1
```

8. Опційно: запуск CLI у Docker-контейнері застосунку:

```bash
docker build -t hw06-cli .
docker run --rm hw06-cli -h
docker run --rm -e DATABASE_URL="postgresql+psycopg2://postgres:hw06_secure_pass_2026@host.docker.internal:5432/postgres" hw06-cli -a select --query 1
```


## Мінімальний сценарій перевірки

Швидка перевірка після виконання кроків із розділу `Запуск`:

1. Переконатися, що міграції застосовані (`alembic upgrade head`).
2. Заповнити БД (`py main.py -a populate --reset`).
3. Виконати базову вибірку (`py main.py -a select --query 1`).


## Аргументи CLI

Обов'язкові:

- `-a, --action`: `create | list | update | remove | populate | select`
- `-m, --model`: `Group | Student | Teacher | Subject | Grade` (для CRUD)

Основні аргументи:

- `--id` - ID сутності для `update/remove`
- `-n, --name` - ім'я/назва
- `--group-id`
- `--teacher-id`
- `--student-id`
- `--subject-id`
- `--grade`
- `--date` у форматі `YYYY-MM-DD`
- `--query` номер запиту (`1..12`) для дії `select`
- `--limit` ліміт для `select_1` (default: `5`)
- `--reset` очистити таблиці перед `populate`
- `--seed` фіксоване random-seed для відтворюваності

Приклади CRUD:

1. `create`: створити викладача
	- `py main.py -a create -m Teacher -n "Boris Jonson"`
2. `create`: створити групу
	- `py main.py -a create -m Group -n "AD-101"`
3. `list`: показати всіх викладачів
	- `py main.py -a list -m Teacher`
4. `update`: оновити викладача за id
	- `py main.py -a update -m Teacher --id 3 -n "Andry Bezos"`
5. `remove`: видалити викладача за id
	- `py main.py -a remove -m Teacher --id 3`

Приклади для інших моделей:

1. `create`: створити студента
	- `py main.py -a create -m Student -n "Ivan Petrenko" --group-id 1`
2. `create`: створити предмет
	- `py main.py -a create -m Subject -n "Physics" --teacher-id 1`
3. `create`: створити оцінку
	- `py main.py -a create -m Grade --student-id 1 --subject-id 1 --grade 11 --date 2026-04-14`

Запити `select_1..select_10`:

1. `query 1`: 5 студентів із найбільшим середнім балом
	- `py main.py -a select --query 1`
2. `query 2`: студент із найвищим середнім балом з предмета
	- `py main.py -a select --query 2 --subject-id <id>`
3. `query 3`: середній бал у групах з певного предмета
	- `py main.py -a select --query 3 --subject-id <id>`
4. `query 4`: середній бал на потоці
	- `py main.py -a select --query 4`
5. `query 5`: курси, які читає певний викладач
	- `py main.py -a select --query 5 --teacher-id <id>`
6. `query 6`: список студентів у певній групі
	- `py main.py -a select --query 6 --group-id <id>`
7. `query 7`: оцінки студентів у групі з певного предмета
	- `py main.py -a select --query 7 --group-id <id> --subject-id <id>`
8. `query 8`: середній бал, який ставить певний викладач
	- `py main.py -a select --query 8 --teacher-id <id>`
9. `query 9`: список курсів, які відвідує певний студент
	- `py main.py -a select --query 9 --student-id <id>`
10. `query 10`: курси, які студенту читає певний викладач
	- `py main.py -a select --query 10 --student-id <id> --teacher-id <id>`

Додаткові запити:

- `query 11`: середній бал викладача конкретному студенту
	- `py main.py -a select --query 11 --teacher-id <id> --student-id <id>`
- `query 12`: оцінки групи з предмета на останньому занятті
	- `py main.py -a select --query 12 --group-id <id> --subject-id <id>`

