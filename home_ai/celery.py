"""
Celery конфиг для асинхронной обработки задач
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'home_ai.settings')

app = Celery('home_ai')

# Загружаем конфиг из Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически регистрируем таски из apps
app.autodiscover_tasks()

# Beat schedule (периодические задачи)
app.conf.beat_schedule = {
    'send-task-reminders': {
        'task': 'apps.core.tasks.send_task_reminders',
        'schedule': crontab(minute='*/5'),  # Каждые 5 минут
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
