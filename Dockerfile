FROM python:3.12
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y nano
COPY control_employee .
COPY pyproject.toml .
COPY poetry.lock .
COPY .env .
RUN pip install --upgrade pip \
    && pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi
RUN python manage.py collectstatic --noinput
