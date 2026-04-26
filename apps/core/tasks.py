"""
Celery таски для асинхронной обработки
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import requests
import json
import logging

logger = logging.getLogger(__name__)


# ── Таски для генерации подзадач ──
@shared_task(bind=True, max_retries=3)
def generate_subtasks_async(self, task_id):
    """
    Асинхронно генерирует подзадачи через AI Service

    :param task_id: ID задачи в БД
    """
    from apps.core.models import Task, Subtask

    try:
        task = Task.objects.get(id=task_id)
        logger.info(f"🤖 Генерируем подзадачи для задачи {task_id}: {task.title}")

        # Вызываем AI Service
        response = requests.post(
            'http://localhost:8002/api/subtasks/generate',
            json={
                'task_title': task.title,
                'task_description': task.description or '',
                'user_gender': getattr(task.user, 'gender', None),
                'user_id': task.user.id
            },
            timeout=60
        )

        if response.status_code == 200:
            data = response.json()

            if data.get('success'):
                subtasks = data.get('subtasks', [])

                # Сохраняем подзадачи в БД
                for subtitle in subtasks:
                    Subtask.objects.create(
                        parent_task=task,
                        title=subtitle,
                        is_completed=False
                    )

                logger.info(f"✅ Сгенерировано {len(subtasks)} подзадач для задачи {task_id}")

                # Публикуем событие
                publish_event('task.subtasks_generated', {
                    'task_id': task_id,
                    'subtask_count': len(subtasks),
                    'user_id': task.user.id
                })

                return {
                    'success': True,
                    'task_id': task_id,
                    'subtask_count': len(subtasks)
                }
            else:
                raise ValueError(data.get('error', 'Unknown error'))
        else:
            raise ValueError(f'AI Service error: {response.status_code}')

    except Task.DoesNotExist:
        logger.error(f"❌ Задача {task_id} не найдена")
        return {'success': False, 'error': 'Task not found'}

    except Exception as e:
        logger.error(f"❌ Ошибка при генерации подзадач: {str(e)}")

        # Retry через 5 минут
        try:
            self.retry(countdown=300)
        except Exception:
            return {'success': False, 'error': str(e)}


# ── Таски для мониторинга ──
@shared_task
def check_overdue_tasks():
    """
    Проверяет просроченные задачи каждый час
    """
    from apps.core.models import Task

    now = timezone.now()
    overdue_tasks = Task.objects.filter(
        due_date__lt=now,
        is_completed=False
    )

    count = overdue_tasks.count()
    logger.info(f"⏰ Найдено {count} просроченных задач")

    # Публикуем событие
    for task in overdue_tasks:
        publish_event('task.overdue', {
            'task_id': task.id,
            'task_title': task.title,
            'user_id': task.user.id,
            'due_date': str(task.due_date)
        })

    return {'overdue_count': count}


@shared_task
def cleanup_old_history():
    """
    Удаляет историю задач старше 30 дней
    """
    from apps.core.models import TaskHistory

    cutoff_date = timezone.now() - timedelta(days=30)
    deleted_count, _ = TaskHistory.objects.filter(
        created_at__lt=cutoff_date
    ).delete()

    logger.info(f"🧹 Удалена история {deleted_count} старых задач")

    return {'deleted_count': deleted_count}


# ── Event система ──
def publish_event(event_type: str, data: dict):
    """
    Публикует событие в Redis Pub/Sub

    :param event_type: Тип события (task.created, task.completed и т.д.)
    :param data: Данные события
    """
    import redis
    import os

    try:
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        redis_port = int(os.getenv('REDIS_PORT', 6379))
        redis_db = int(os.getenv('REDIS_DB', 0))

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            decode_responses=True
        )

        event = {
            'type': event_type,
            'data': data,
            'timestamp': str(timezone.now())
        }

        redis_client.publish(
            'homeai:events',
            json.dumps(event)
        )

        logger.info(f"📢 Событие опубликовано: {event_type}")

    except Exception as e:
        logger.warning(f"⚠️ Ошибка при публикации события: {e}")


# ── Таски для интеграции ──
@shared_task
def sync_with_external_api():
    """
    Синхронизирует данные с внешними API
    """
    logger.info("🔄 Синхронизируем с внешними API")
    # Здесь можно добавить интеграцию с Google Calendar и т.д.
    return {'status': 'synced'}
