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
    'check-overdue-tasks': {
        'task': 'apps.core.tasks.check_overdue_tasks',
        'schedule': crontab(minute=0, hour='*'),  # Каждый час
    },
    'cleanup-old-history': {
        'task': 'apps.core.tasks.cleanup_old_history',
        'schedule': crontab(minute=0, hour=2),  # В 2:00 AM
    },
    'analyze-recurring-patterns': {
        'task': 'apps.core.tasks.analyze_recurring_patterns',
        'schedule': 86400.0,  # Раз в день (в секундах)
    },
}

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
