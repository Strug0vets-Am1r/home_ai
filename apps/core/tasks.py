from celery import shared_task
from django.utils import timezone
from django.conf import settings
import redis as redis_lib
import json
import datetime

from .models import Task


def _publish_task_event(event_type, data):
    try:
        r = redis_lib.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        r.publish('homeai:events', json.dumps({'type': event_type, 'data': data}))
        r.close()
    except Exception:
        pass


@shared_task
def send_task_reminders():
    now = timezone.now()
    window_start = now + datetime.timedelta(minutes=25)
    window_end = now + datetime.timedelta(minutes=35)

    upcoming_tasks = Task.objects.filter(
        is_completed=False,
        parent_task__isnull=True,
        due_date__gte=window_start,
        due_date__lte=window_end,
    )

    r = redis_lib.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True
    )

    sent = 0
    for task in upcoming_tasks:
        reminder_key = f'reminder_sent:{task.id}'
        if r.get(reminder_key):
            continue
        _publish_task_event('task.reminder', {
            'user_id': task.user_id,
            'task_id': task.id,
            'task_title': task.title,
            'due_date': task.due_date.isoformat(),
        })
        r.setex(reminder_key, 3600, '1')
        sent += 1

    r.close()
    return f'Sent {sent} reminders'
