FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_ROOT_USER_ACTION=ignore
ENV POETRY_VERSION=2.3.4
ENV POETRY_VIRTUALENVS_CREATE=false
WORKDIR /app

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

COPY pyproject.toml poetry.lock README.md ./
RUN poetry check && poetry install --no-interaction --no-ansi --no-root

COPY . .
RUN python scripts/check_config.py --mode build

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
