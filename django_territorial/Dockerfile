FROM python:3.11.9-bullseye
RUN pip install poetry==1.8.2

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=0 \
    POETRY_VIRTUALENVS_CREATE=0 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY ./django_territorial/pyproject.toml ./django_territorial/poetry.lock ./
RUN poetry install --no-root

EXPOSE 8000
CMD poetry run python manage.py collectstatic --noinput && \
    poetry run python manage.py makemigrations && \
    poetry run python manage.py migrate && \
    poetry run daphne -b 0.0.0.0 -p 8000 django_territorial.asgi:application
