"""
Notification Service — микросервис для отправки уведомлений
Слушает Redis события, сохраняет уведомления, отправляет через WebSocket
"""
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import json
import os
import logging
from typing import Optional
from datetime import datetime
import threading
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HomeAI - Notification Service",
    description="Микросервис для отправки уведомлений",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

try:
    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
    )
    redis_client.ping()
    logger.info("Redis подключен")
except Exception as e:
    logger.warning(f"Redis недоступен: {e}")
    redis_client = None

DJANGO_API_URL = os.getenv("DJANGO_API_URL", "http://localhost:8001")

# ── WebSocket соединения: {user_id: [WebSocket, ...]} ──
ws_connections: dict[int, list[WebSocket]] = {}
ws_lock = asyncio.Lock()
main_loop: asyncio.AbstractEventLoop | None = None


class Notification(BaseModel):
    user_id: int
    type: str
    title: str
    message: str
    data: Optional[dict] = None
    read: bool = False
    created_at: Optional[str] = None


class NotificationResponse(BaseModel):
    success: bool
    notification_id: Optional[str] = None
    error: Optional[str] = None


# ── WebSocket ──
async def _push_to_user(user_id: int, payload: dict):
    async with ws_lock:
        sockets = ws_connections.get(user_id, [])
        dead = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            sockets.remove(ws)


async def _broadcast_notification(notification: dict):
    user_id = notification.get("user_id")
    if not user_id:
        return
    payload = {
        "type": "notification",
        "notification": {
            "id": f"{user_id}:{notification['created_at']}",
            "type": notification.get("type"),
            "title": notification.get("title"),
            "message": notification.get("message"),
            "data": notification.get("data"),
            "read": notification.get("read", False),
            "created_at": notification.get("created_at"),
        },
    }
    await _push_to_user(user_id, payload)


@app.websocket("/ws/notifications/{user_id}")
async def websocket_endpoint(ws: WebSocket, user_id: int):
    await ws.accept()
    async with ws_lock:
        ws_connections.setdefault(user_id, []).append(ws)
    logger.info(f"WebSocket подключен: user={user_id}")
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket отключен: user={user_id}")
    finally:
        async with ws_lock:
            sockets = ws_connections.get(user_id, [])
            if ws in sockets:
                sockets.remove(ws)


# ── Функции обработки событий ──
def _process_task_created_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        task_title = event_data.get("task_title", "Новая задача")
        notification = {
            "user_id": user_id,
            "type": "task.created",
            "title": "Новая задача создана",
            "message": f"Задача \"{task_title}\" была создана",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление о создании задачи для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события task.created: {e}")


def _process_task_completed_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        task_title = event_data.get("task_title", "Задача")
        notification = {
            "user_id": user_id,
            "type": "task.completed",
            "title": "Задача завершена!",
            "message": f"Вы завершили задачу \"{task_title}\"",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление о завершении задачи для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события task.completed: {e}")


def _process_subtask_generated_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        subtask_count = event_data.get("subtask_count", 0)
        notification = {
            "user_id": user_id,
            "type": "subtask.generated",
            "title": "Подзадачи сгенерированы",
            "message": f"AI сгенерировал {subtask_count} подзадач для вашей задачи",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление о генерации подзадач для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события subtask.generated: {e}")


def _process_task_overdue_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        task_title = event_data.get("task_title", "Задача")
        notification = {
            "user_id": user_id,
            "type": "task.overdue",
            "title": "Задача просрочена",
            "message": f"Задача \"{task_title}\" просрочена. Пора её выполнить!",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление о просроченной задаче для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события task.overdue: {e}")


def _process_task_restored_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        task_title = event_data.get("task_title", "Задача")
        notification = {
            "user_id": user_id,
            "type": "task.restored",
            "title": "Задача восстановлена",
            "message": f"Задача \"{task_title}\" восстановлена",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление о восстановлении задачи для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события task.restored: {e}")


def _process_task_updated_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        task_title = event_data.get("task_title", "Задача")
        notification = {
            "user_id": user_id,
            "type": "task.updated",
            "title": "Задача обновлена",
            "message": f"Задача \"{task_title}\" обновлена",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление об обновлении задачи для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события task.updated: {e}")


def _process_task_deleted_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        task_title = event_data.get("task_title", "Задача")
        notification = {
            "user_id": user_id,
            "type": "task.deleted",
            "title": "Задача удалена",
            "message": f"Задача \"{task_title}\" удалена",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление об удалении задачи для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события task.deleted: {e}")


def _process_tasks_cleared_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        count = event_data.get("count", 0)
        notification = {
            "user_id": user_id,
            "type": "tasks.cleared",
            "title": "Выполненные задачи очищены",
            "message": f"Очищено {count} выполненных задач",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление об очистке задач для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события tasks.cleared: {e}")


def _process_task_reminder_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        task_title = event_data.get("task_title", "Задача")
        notification = {
            "user_id": user_id,
            "type": "task.reminder",
            "title": "Напоминание о задаче",
            "message": f"Задача \"{task_title}\" скоро истекает!",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление-напоминание для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события task.reminder: {e}")


def _process_suggestion_created_event(event_data: dict):
    try:
        user_id = event_data.get("user_id")
        title = event_data.get("title", "Задача")
        interval_days = event_data.get("interval_days", 0)
        notification = {
            "user_id": user_id,
            "type": "suggestion.created",
            "title": "Новое предложение!",
            "message": f"AI предлагает повторять задачу \"{title.capitalize()}\" каждые {interval_days} дн.",
            "data": event_data,
            "read": False,
            "created_at": datetime.utcnow().isoformat() + 'Z',
        }
        _save_notification(notification)
        if main_loop:
            asyncio.run_coroutine_threadsafe(_broadcast_notification(notification), main_loop)
        logger.info(f"Уведомление о новом предложении для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка при обработке события suggestion.created: {e}")


def _save_notification(notification: dict):
    if not redis_client:
        return
    try:
        user_id = notification.get("user_id")
        notif_key = f"notifications:{user_id}:{notification['created_at']}"
        redis_client.setex(
            notif_key, 86400 * 30, json.dumps(notification)
        )
        redis_client.lpush(f"user_notifications:{user_id}", notif_key)
        logger.info(f"Уведомление сохранено: {notif_key}")
    except Exception as e:
        logger.warning(f"Ошибка при сохранении уведомления: {e}")


def _listen_events():
    if not redis_client:
        logger.warning("Redis недоступен, слушание отключено")
        return
    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe("homeai:events")
        logger.info("Слушаем события homeai:events...")
        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    event = json.loads(message["data"])
                    event_type = event.get("type")
                    event_data = event.get("data", {})
                    if event_type == "task.created":
                        _process_task_created_event(event_data)
                    elif event_type == "task.completed":
                        _process_task_completed_event(event_data)
                    elif event_type == "subtask.generated":
                        _process_subtask_generated_event(event_data)
                    elif event_type == "task.overdue":
                        _process_task_overdue_event(event_data)
                    elif event_type == "task.restored":
                        _process_task_restored_event(event_data)
                    elif event_type == "task.updated":
                        _process_task_updated_event(event_data)
                    elif event_type == "task.deleted":
                        _process_task_deleted_event(event_data)
                    elif event_type == "tasks.cleared":
                        _process_tasks_cleared_event(event_data)
                    elif event_type == "task.reminder":
                        _process_task_reminder_event(event_data)
                    elif event_type == "suggestion.created":
                        _process_suggestion_created_event(event_data)
                    else:
                        logger.debug(f"Неизвестный тип: {event_type}")
                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга: {e}")
                except Exception as e:
                    logger.error(f"Ошибка обработки: {e}")
    except Exception as e:
        logger.error(f"Ошибка в слушателе: {e}")


# ── API ──
@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()
    if redis_client:
        thread = threading.Thread(target=_listen_events, daemon=True)
        thread.start()
        logger.info("Notification Service запущен")


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "notification-service",
        "redis": "connected" if redis_client else "disconnected",
    }


@app.post("/api/notifications/send", response_model=NotificationResponse)
async def send_notification(notification: Notification, background_tasks: BackgroundTasks):
    try:
        notification_dict = notification.dict()
        notification_dict["created_at"] = datetime.utcnow().isoformat() + 'Z'
        _save_notification(notification_dict)
        return NotificationResponse(
            success=True,
            notification_id=f"{notification.user_id}:{notification_dict['created_at']}",
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")
        return NotificationResponse(success=False, error=str(e))


@app.get("/api/notifications/user/{user_id}")
async def get_user_notifications(user_id: int, limit: int = 50):
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
        logger.error(f"Ошибка при получении уведомлений: {e}")
        return {"notifications": [], "error": str(e)}


@app.post("/api/notifications/user/{user_id}/read")
async def mark_notifications_read(user_id: int, data: dict):
    """Отмечает уведомления как прочитанные"""
    if not redis_client:
        return {"success": False}
    try:
        keys = data.get("keys", [])
        for key in keys:
            raw = redis_client.get(key)
            if raw:
                notif = json.loads(raw)
                notif["read"] = True
                redis_client.setex(key, 86400 * 30, json.dumps(notif))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/notifications/user/{user_id}/read-all")
async def mark_all_read(user_id: int):
    if not redis_client:
        return {"success": False}
    try:
        key = f"user_notifications:{user_id}"
        notif_keys = redis_client.lrange(key, 0, -1)
        for nk in notif_keys:
            raw = redis_client.get(nk)
            if raw:
                notif = json.loads(raw)
                notif["read"] = True
                redis_client.setex(nk, 86400 * 30, json.dumps(notif))
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.delete("/api/notifications/user/{user_id}")
async def clear_user_notifications(user_id: int):
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
    if not redis_client:
        return {"error": "Redis not available"}
    try:
        all_notifications = len(redis_client.keys("notifications:*"))
        return {"total_notifications": all_notifications, "redis_status": "connected"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="info")
