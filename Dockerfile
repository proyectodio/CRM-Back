FROM python:3.12-slim

WORKDIR /srv

COPY pyproject.toml .
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY docker/entrypoint.sh ./docker/entrypoint.sh

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "docker/entrypoint.sh"]
