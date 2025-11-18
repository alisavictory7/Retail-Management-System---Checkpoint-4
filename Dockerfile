# syntax=docker/dockerfile:1.4

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x docker/entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "src.main:app"]

