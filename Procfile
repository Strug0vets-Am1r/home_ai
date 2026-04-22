web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn home_ai.wsgi:application --bind 0.0.0.0:$PORT
