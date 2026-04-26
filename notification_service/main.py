"""
Notification Service - микросервис для отправки уведомлений
Слушает Redis события и отправляет уведомления пользователям
"""
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import redis
import json
import os
import logging
from typing import Optional
from datetime import datetime
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HomeAI - Notification Service",
    description="Микросервис для отправки уведомлений",
    version="1.0.0"
)

# Redis конфиг
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True
    )
    redis_client.ping()
    logger.info("✅ Redis подключен")
except Exception as e:
    logger.warning(f"⚠️ Redis недоступен: {e}")
    redis_client = None

# Django API базовый URL
DJANGO_API_URL = os.getenv("DJANGO_API_URL", "http://localhost:8001")


# ── Модели ──
class Notification(BaseModel):
    user_id: int
    type: str  # task.created, task.completed, subtask.generated и т.д.
    title: str
    message: str
    data: Optional[dict] = None
    read: bool = False
    created_at: Optional[str] = None


class NotificationResponse(BaseModel):
    success: bool
    notification_id: Optional[str] = None
    error: Optional[str] = None


# ── Функции обработки событий ──
def _process_task_created_event(event_data: dict):
    """Обрабатывает событие создания задачи"""
    try:
        user_id = event_data.get('user_id')
        task_title = event_data.get('task_title', 'Новая задача')

        notification = {
            'user_id': user_id,
            'type': 'task.created',
            'title': 'Новая задача создана',
            'message': f'Задача "{task_title}" была создана',
            'data': event_data,
            'created_at': str(datetime.now())
        }

        _save_notification(notification)
        logger.info(f"✉️ Уведомление о создании задачи для пользователя {user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке события task.created: {e}")


def _process_task_completed_event(event_data: dict):
    """Обрабатывает событие завершения задачи"""
    try:
        user_id = event_data.get('user_id')
        task_title = event_data.get('task_title', 'Задача')

        notification = {
            'user_id': user_id,
            'type': 'task.completed',
            'title': '🎉 Задача завершена!',
            'message': f'Вы завершили задачу "{task_title}"',
            'data': event_data,
            'created_at': str(datetime.now())
        }

        _save_notification(notification)
        logger.info(f"✉️ Уведомление о завершении задачи для пользователя {user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке события task.completed: {e}")


def _process_subtask_generated_event(event_data: dict):
    """Обрабатывает событие генерации подзадач"""
    try:
        user_id = event_data.get('user_id')
        subtask_count = event_data.get('subtask_count', 0)

        notification = {
            'user_id': user_id,
            'type': 'subtask.generated',
            'title': '🤖 Подзадачи сгенерированы',
            'message': f'AI сгенерировал {subtask_count} подзадач для вашей задачи',
            'data': event_data,
            'created_at': str(datetime.now())
        }

        _save_notification(notification)
        logger.info(f"✉️ Уведомление о генерации подзадач для пользователя {user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке события subtask.generated: {e}")


def _process_task_overdue_event(event_data: dict):
    """Обрабатывает событие просроченной задачи"""
    try:
        user_id = event_data.get('user_id')
        task_title = event_data.get('task_title', 'Задача')

        notification = {
            'user_id': user_id,
            'type': 'task.overdue',
            'title': '⏰ Задача просрочена',
            'message': f'Задача "{task_title}" просрочена. Пора её выполнить!',
            'data': event_data,
            'created_at': str(datetime.now())
        }

        _save_notification(notification)
        logger.info(f"✉️ Уведомление о просроченной задаче для пользователя {user_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке события task.overdue: {e}")


def _save_notification(notification: dict):
    """Сохраняет уведомление в Redis"""
    if not redis_client:
        return

    try:
        user_id = notification.get('user_id')
        notif_key = f"notifications:{user_id}:{notification['created_at']}"

        redis_client.setex(
            notif_key,
            86400 * 30,  # 30 дней TTL
            json.dumps(notification)
        )

        # Добавляем в список уведомлений пользователя
        redis_client.lpush(f"user_notifications:{user_id}", notif_key)

        logger.info(f"💾 Уведомление сохранено: {notif_key}")

    except Exception as e:
        logger.warning(f"⚠️ Ошибка при сохранении уведомления: {e}")


def _listen_events():
    """
    Слушает события из Redis Pub/Sub
    Запускается в отдельном потоке при старте сервиса
    """
    if not redis_client:
        logger.warning("⚠️ Redis не доступен, событие слушание отключено")
        return

    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe('homeai:events')

        logger.info("👂 Начинаем слушать события...")

        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    event = json.loads(message['data'])
                    event_type = event.get('type')
                    event_data = event.get('data', {})

                    # Маршрутизируем события
                    if event_type == 'task.created':
                        _process_task_created_event(event_data)
                    elif event_type == 'task.completed':
                        _process_task_completed_event(event_data)
                    elif event_type == 'subtask.generated':
                        _process_subtask_generated_event(event_data)
                    elif event_type == 'task.overdue':
                        _process_task_overdue_event(event_data)
                    else:
                        logger.debug(f"Неизвестный тип события: {event_type}")

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка при парсинге события: {e}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при обработке события: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка в слушателе событий: {e}")


# ── API Endpoints ──
@app.on_event("startup")
async def startup_event():
    """Запуск слушателя событий при старте"""
    if redis_client:
        # Запускаем слушатель в отдельном потоке
        listener_thread = threading.Thread(target=_listen_events, daemon=True)
        listener_thread.start()
        logger.info("🚀 Notification Service запущен")


@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "ok",
        "service": "notification-service",
        "redis": "connected" if redis_client else "disconnected"
    }


@app.post("/api/notifications/send", response_model=NotificationResponse)
async def send_notification(notification: Notification, background_tasks: BackgroundTasks):
    """
    Отправляет уведомление пользователю

    - **user_id**: ID пользователя (обязательно)
    - **type**: Тип уведомления (обязательно)
    - **title**: Заголовок (обязательно)
    - **message**: Текст сообщения (обязательно)
    - **data**: Дополнительные данные (опционально)
    """
    try:
        notification_dict = notification.dict()
        notification_dict['created_at'] = str(datetime.now())

        _save_notification(notification_dict)

        return NotificationResponse(
            success=True,
            notification_id=f"{notification.user_id}:{notification_dict['created_at']}"
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при отправке уведомления: {e}")
        return NotificationResponse(
            success=False,
            error=str(e)
        )


@app.get("/api/notifications/user/{user_id}")
async def get_user_notifications(user_id: int, limit: int = 50):
    """Получить уведомления пользователя"""
    if not redis_client:
        return {"notifications": []}

    try:
        key = f"user_notifications:{user_id}"
        notif_keys = redis_client.lrange(key, 0, limit - 1)

        notifications = []
        for notif_key in notif_keys:
            notif_data = redis_client.get(notif_key)
            if notif_data:
                notifications.append(json.loads(notif_data))

        return {"notifications": notifications, "count": len(notifications)}

    except Exception as e:
        logger.error(f"❌ Ошибка при получении уведомлений: {e}")
        return {"notifications": [], "error": str(e)}


@app.delete("/api/notifications/user/{user_id}")
async def clear_user_notifications(user_id: int):
    """Очищает уведомления пользователя"""
    if not redis_client:
        return {"success": False}

    try:
        key = f"user_notifications:{user_id}"
        redis_client.delete(key)
        return {"success": True, "message": "Уведомления очищены"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/stats")
async def get_stats():
    """Получить статистику сервиса"""
    if not redis_client:
        return {"error": "Redis not available"}

    try:
        all_notifications = len(redis_client.keys("notifications:*"))
        return {
            "total_notifications": all_notifications,
            "redis_status": "connected"
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8003,
        log_level="info"
    )
