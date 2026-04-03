# Тема 3. Основи Web. Домашнє завдання

## Реалізовано

- Роутинг для сторінок `index.html` (`/`) та `message.html` (`/message.html`)
- Обробка статичних ресурсів `style.css` та `logo.png`
- Обробка форми (`POST /message`) з полями `username` і `message`
- Збереження повідомлень у `storage/data.json` у форматі:

```json
{
  "2026-04-03 15:51:24.233194": {
    "username": "krabaton",
    "message": "First message"
  }
}
```

- Маршрут `/read` рендерить Jinja2-шаблон зі всіма збереженими повідомленнями
- Для невідомих маршрутів повертається `error.html` зі статусом `404`
- Додаток працює на порту `3000`
- Використовується `Dockerfile` для створення образу та `docker-compose.yaml` для запуску контейнера з volume для збереження даних

## Запуск локально:

1. Встановіть залежності:

```bash
pip install -r requirements.txt
```

2. Запустіть сервер:

```bash
python main.py
```

3. Відкрийте в браузері:

- `http://localhost:3000/`
- `http://localhost:3000/message.html`
- `http://localhost:3000/read`

## Запуск через Docker:

1. Зберіть та запустіть застосунок у контейнері:

```bash
docker compose up --build
```

2. Відкрийте в браузері:

- `http://localhost:3000/`
- `http://localhost:3000/message.html`
- `http://localhost:3000/read`

3. Зупиніть контейнер після завершення роботи:

```bash
docker compose down
```

> Використовується volume `./storage:/app/storage`, тому дані зберігаються у `storage/data.json` на хості, а не всередині контейнера.
