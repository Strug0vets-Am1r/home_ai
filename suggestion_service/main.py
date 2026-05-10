"""
Suggestion Service — микросервис для анализа повторяющихся задач
Слушает task.completed, анализирует паттерны, создаёт предложения
"""
from fastapi import FastAPI
import redis
import json
import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import threading
import requests

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="HomeAI - Suggestion Service",
    description="Микросервис для анализа повторяющихся задач",
    version="1.0.0"
)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
DJANGO_API_URL = os.getenv("DJANGO_API_URL", "http://task-service:8000")

try:
    redis_client = redis.Redis(
        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
    )
    redis_client.ping()
    logger.info("Redis подключен")
except Exception as e:
    logger.warning(f"Redis недоступен: {e}")
    redis_client = None

HISTORY_TTL = 86400 * 90  # 90 дней
MIN_OCCURRENCES = 3
MAX_INTERVAL_DEVIATION = 2  # дней


def _normalize_title(title):
    return title.lower().strip().rstrip(".,!?:;")


def _get_user_history(user_id):
    if not redis_client:
        return []
    key = f"suggestion_history:{user_id}"
    try:
        data = redis_client.lrange(key, 0, -1)
        return [json.loads(item) for item in data]
    except Exception as e:
        logger.warning(f"Ошибка чтения истории: {e}")
        return []


def _add_to_history(user_id, task_title, task_list, completed_at):
    if not redis_client:
        return
    key = f"suggestion_history:{user_id}"
    try:
        entry = json.dumps({
            "title": task_title,
            "task_list": task_list,
            "completed_at": completed_at,
        })
        redis_client.lpush(key, entry)
        redis_client.ltrim(key, 0, 999)
        redis_client.expire(key, HISTORY_TTL)
    except Exception as e:
        logger.warning(f"Ошибка сохранения истории: {e}")


def _analyze_patterns(user_id):
    history = _get_user_history(user_id)
    if len(history) < MIN_OCCURRENCES:
        return

    groups = {}
    for entry in history:
        title = _normalize_title(entry["title"])
        if not title:
            continue
        groups.setdefault(title, []).append(entry)

    for title, entries in groups.items():
        if len(entries) < MIN_OCCURRENCES:
            continue

        dates = []
        for e in entries:
            try:
                dt = datetime.fromisoformat(e["completed_at"])
                dates.append(dt)
            except (ValueError, TypeError):
                continue

        if len(dates) < MIN_OCCURRENCES:
            continue

        dates.sort()
        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        if not intervals:
            continue

        avg_interval = sum(intervals) // len(intervals)
        if avg_interval <= 0:
            continue

        if not all(abs(i - avg_interval) <= MAX_INTERVAL_DEVIATION for i in intervals):
            continue

        _create_suggestion(user_id, title, avg_interval)


def _create_suggestion(user_id, title, interval_days):
    try:
        resp = requests.post(
            f"{DJANGO_API_URL}/api/suggestions/create/",
            json={
                "user_id": user_id,
                "title": title.capitalize(),
                "interval_days": interval_days,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("ok"):
                logger.info(f"Предложение создано: {title} (каждые {interval_days} дн.)")
                _publish_event("suggestion.created", {
                    "user_id": user_id,
                    "title": title,
                    "interval_days": interval_days,
                })
        elif resp.status_code == 409:
            logger.info(f"Предложение уже существует: {title}")
        else:
            logger.warning(f"Ошибка создания предложения: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.warning(f"Ошибка запроса к Django API: {e}")


def _publish_event(event_type, data):
    if not redis_client:
        return
    try:
        redis_client.publish("homeai:events", json.dumps({
            "type": event_type,
            "data": data,
        }))
    except Exception as e:
        logger.warning(f"Ошибка публикации события: {e}")


def _handle_task_completed(event_data):
    user_id = event_data.get("user_id")
    task_title = event_data.get("task_title", "")
    task_list = event_data.get("task_list", "active")
    completed_at = event_data.get("completed_at") or datetime.now().isoformat()

    if not user_id or not task_title:
        return

    _add_to_history(user_id, task_title, task_list, completed_at)
    _analyze_patterns(user_id)


EVENT_HANDLERS = {
    "task.completed": _handle_task_completed,
}


def _listen_events():
    if not redis_client:
        logger.warning("Redis недоступен, слушание отключено")
        return

    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe("homeai:events")
        logger.info("Слушаем события homeai:events...")

        for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                event = json.loads(message["data"])
                event_type = event.get("type")
                event_data = event.get("data", {})
                handler = EVENT_HANDLERS.get(event_type)
                if handler:
                    handler(event_data)
                else:
                    logger.debug(f"Неизвестный тип: {event_type}")
            except json.JSONDecodeError:
                logger.error("Ошибка парсинга события")
            except Exception as e:
                logger.error(f"Ошибка обработки события: {e}")
    except Exception as e:
        logger.error(f"Ошибка в слушателе: {e}")


@app.on_event("startup")
async def startup():
    if redis_client:
        thread = threading.Thread(target=_listen_events, daemon=True)
        thread.start()
        logger.info("Suggestion Service запущен")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "suggestion-service",
        "redis": "connected" if redis_client else "disconnected",
    }


@app.get("/api/stats")
async def stats():
    if not redis_client:
        return {"error": "Redis not available"}
    try:
        keys = redis_client.keys("suggestion_history:*")
        return {"users_tracked": len(keys)}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004, log_level="info")
