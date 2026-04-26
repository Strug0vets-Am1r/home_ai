"""
AI Service - микросервис для генерации подзадач через нейросеть
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import os
import json
import logging
from dotenv import load_dotenv
import redis
from typing import Optional
import asyncio

load_dotenv()

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI приложение
app = FastAPI(
    title="HomeAI - AI Service",
    description="Микросервис для генерации подзадач",
    version="1.0.0"
)

# Redis для кэширования и публикации событий
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

# Yandex GPT конфиг
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_MODEL_URI = f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite"
YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


# ── Модели Pydantic ──
class SubtaskGenerationRequest(BaseModel):
    task_title: str
    task_description: str = ""
    user_gender: Optional[str] = None
    user_id: Optional[int] = None


class SubtasksResponse(BaseModel):
    success: bool
    subtasks: list[str] = []
    error: Optional[str] = None
    cached: bool = False


# ── Функции ──
def _build_yandex_headers():
    """Строит заголовки для запроса к Yandex GPT"""
    return {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json"
    }


def _check_cache(task_title: str, user_id: Optional[int] = None):
    """Проверяет кэш Redis"""
    if not redis_client:
        return None

    cache_key = f"subtasks:{user_id or 'anon'}:{task_title.lower()}"
    try:
        cached = redis_client.get(cache_key)
        if cached:
            logger.info(f"✅ Кэш найден: {cache_key}")
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Ошибка при чтении кэша: {e}")

    return None


def _set_cache(task_title: str, subtasks: list, user_id: Optional[int] = None):
    """Сохраняет результат в Redis кэш (1 час)"""
    if not redis_client:
        return

    cache_key = f"subtasks:{user_id or 'anon'}:{task_title.lower()}"
    try:
        redis_client.setex(
            cache_key,
            3600,  # TTL: 1 час
            json.dumps(subtasks)
        )
        logger.info(f"💾 Кэш сохранен: {cache_key}")
    except Exception as e:
        logger.warning(f"Ошибка при сохранении кэша: {e}")


def _publish_event(event_type: str, data: dict):
    """Публикует событие в Redis"""
    if not redis_client:
        return

    try:
        event = {
            "type": event_type,
            "data": data,
            "timestamp": str(pd.Timestamp.now()) if 'pd' in locals() else None
        }
        redis_client.publish("homeai:events", json.dumps(event))
        logger.info(f"📢 Событие опубликовано: {event_type}")
    except Exception as e:
        logger.warning(f"Ошибка при публикации события: {e}")


def _generate_subtasks_yandex(
    task_title: str,
    task_description: str = "",
    user_gender: Optional[str] = None
) -> list[str]:
    """
    Генерирует подзадачи через Yandex GPT API
    """

    gender_line = ''
    if user_gender == 'male':
        gender_line = (
            'Пользователь — мужчина. '
            'СТРОГО ЗАПРЕЩЕНО включать подзадачи, связанные с макияжем, косметикой, '
            'маникюром, педикюром, укладкой волос феном или утюжком, эпиляцией. '
        )
    elif user_gender == 'female':
        gender_line = 'Пользователь — женщина. Учитывай это при генерации подзадач.\n'

    prompt = f"""
Ты — AI-помощник по планированию домашних задач.

Сгенерируй подзадачи для задачи пользователя.
Верни только конкретные, практические, короткие шаги на русском языке.
{gender_line}
Требования:
- Обычно 4-8 подзадач.
- Максимум 10 подзадач.
- Минимум 3 подзадачи.
- Подзадачи должны идти в логическом порядке.
- Подзадачи не должны дублировать друг друга.
- Не используй слишком общие фразы.
- Каждый шаг должен быть самостоятельным и понятным действием.
- Не добавляй пояснений, комментариев и лишнего текста.
- Верни ответ строго в JSON-формате по схеме.

Название задачи: {task_title}
Описание задачи: {task_description or "Описание не указано."}
""".strip()

    headers = _build_yandex_headers()
    payload = {
        'modelUri': YANDEX_MODEL_URI,
        'completionOptions': {
            'stream': False,
            'temperature': 0.3,
            'maxTokens': '800'
        },
        'messages': [
            {
                'role': 'system',
                'text': 'Ты возвращаешь только валидный JSON по заданной схеме.'
            },
            {
                'role': 'user',
                'text': prompt
            }
        ],
        'jsonSchema': {
            'schema': {
                'type': 'object',
                'properties': {
                    'subtasks': {
                        'type': 'array',
                        'minItems': 3,
                        'maxItems': 10,
                        'items': {'type': 'string'}
                    }
                },
                'required': ['subtasks'],
                'additionalProperties': False
            }
        }
    }

    response = requests.post(
        YANDEX_API_URL,
        headers=headers,
        json=payload,
        timeout=60
    )

    if response.status_code != 200:
        raise ValueError(f'Yandex GPT error {response.status_code}: {response.text}')

    response_data = response.json()

    # Извлекаем текст из ответа
    try:
        raw_text = response_data['result']['alternatives'][0]['message']['text']
        parsed = json.loads(raw_text)
        subtasks = parsed.get('subtasks', [])

        if not isinstance(subtasks, list) or len(subtasks) < 3:
            raise ValueError('Invalid subtasks format')

        return subtasks[:10]  # Максимум 10
    except Exception as e:
        raise ValueError(f'Failed to parse Yandex response: {e}')


# ── API Endpoints ──
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "ok",
        "service": "ai-service",
        "redis": "connected" if redis_client else "disconnected"
    }


@app.post("/api/subtasks/generate", response_model=SubtasksResponse)
async def generate_subtasks(request: SubtaskGenerationRequest):
    """
    Генерирует подзадачи через AI

    - **task_title**: Название задачи (обязательно)
    - **task_description**: Описание задачи (опционально)
    - **user_gender**: Пол пользователя (male/female, опционально)
    - **user_id**: ID пользователя для кэширования (опционально)
    """
    try:
        # Проверяем кэш
        cached_subtasks = _check_cache(request.task_title, request.user_id)
        if cached_subtasks:
            return SubtasksResponse(
                success=True,
                subtasks=cached_subtasks,
                cached=True
            )

        # Генерируем подзадачи
        logger.info(f"🤖 Генерируем подзадачи для: {request.task_title}")
        subtasks = _generate_subtasks_yandex(
            request.task_title,
            request.task_description,
            request.user_gender
        )

        # Сохраняем в кэш
        _set_cache(request.task_title, subtasks, request.user_id)

        # Публикуем событие
        _publish_event("subtask.generated", {
            "task_title": request.task_title,
            "subtask_count": len(subtasks),
            "user_id": request.user_id
        })

        logger.info(f"✅ Сгенерировано {len(subtasks)} подзадач")

        return SubtasksResponse(
            success=True,
            subtasks=subtasks,
            cached=False
        )

    except ValueError as e:
        logger.error(f"❌ Ошибка: {str(e)}")
        return SubtasksResponse(
            success=False,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка: {str(e)}")
        return SubtasksResponse(
            success=False,
            error="Internal server error"
        )


@app.delete("/api/cache/clear")
async def clear_cache(user_id: Optional[int] = None):
    """Очищает кэш"""
    if not redis_client:
        return {"success": False, "error": "Redis not available"}

    try:
        if user_id:
            pattern = f"subtasks:{user_id}:*"
        else:
            pattern = "subtasks:*"

        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)

        return {"success": True, "cleared": len(keys)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/stats")
async def get_stats():
    """Получить статистику сервиса"""
    if not redis_client:
        return {"error": "Redis not available"}

    try:
        cache_size = len(redis_client.keys("subtasks:*"))
        return {
            "cached_requests": cache_size,
            "redis_status": "connected"
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,
        log_level="info"
    )
