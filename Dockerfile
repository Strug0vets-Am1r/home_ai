FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/staticfiles
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["gunicorn", "home_ai.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
