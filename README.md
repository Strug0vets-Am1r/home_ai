# 🏠 HomeAI - Умный планировщик домашних дел

**HomeAI** — веб-приложение для управления домашними задачами с поддержкой AI-генерации подзадач через Yandex GPT API.

## 🚀 Быстрый старт

### Через Docker Compose (рекомендуется)

```bash
# 1. Скопировать конфиг
cp .env.example .env

# 2. Заполнить переменные окружения (особенно YANDEX_*)
nano .env

# 3. Запустить все сервисы
docker-compose up -d

# 4. Применить миграции
docker-compose exec task-service python manage.py migrate

# 5. Создать суперпользователя
docker-compose exec task-service python manage.py createsuperuser

# 6. Открыть приложение
# Веб: http://localhost:80
# API: http://localhost:80/api/
# Админка: http://localhost:80/admin/
```

### Локальная разработка

**Требования**: Python 3.12+, PostgreSQL 15, Redis 7

```bash
# Активировать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# Установить зависимости
pip install -r requirements.txt

# В отдельных терминалах запустить:

# Терминал 1: Django
python manage.py runserver 0.0.0.0:8000

# Терминал 2: Celery Worker
celery -A home_ai worker -l info -c 4

# Терминал 3: Celery Beat (scheduler)
celery -A home_ai beat -l info

# Терминал 4: AI Service
cd ml_service && python main.py
```

## 📚 Документация

Полная документация проекта находится в [CLAUDE.md](CLAUDE.md):
- Архитектура микросервисов
- Переменные окружения
- REST API endpoints
- Модели данных
- Развертывание

## 🎯 Основные функции

- ✅ Создание, редактирование, удаление задач
- ✅ **AI-генерация подзадач** (Yandex GPT)
- ✅ Календарь с просмотром задач
- ✅ История выполненных задач
- ✅ REST API для интеграции
- ✅ Адаптивный дизайн
- ✅ Опрос при регистрации

## 🏗️ Технический стек

- **Backend**: Django 4.2, Django REST Framework, PostgreSQL
- **Очередь**: Celery + Redis
- **AI**: Yandex GPT API (микросервис FastAPI)
- **Фронтенд**: HTML/CSS/JS (Tailwind-like стили)
- **Развертывание**: Docker Compose, Nginx, Railway

## 📡 API

```
GET    /api/tasks/                    # Список задач
POST   /api/tasks/                    # Создать задачу
GET    /api/tasks/{id}/               # Детали задачи
PUT    /api/tasks/{id}/               # Обновить задачу
DELETE /api/tasks/{id}/               # Удалить задачу
POST   /api/generate-subtasks/        # AI генерация подзадач
POST   /subtask/{id}/toggle/          # Отметить подзадачу
```

## 🔐 Переменные окружения

Ключевые переменные (см. .env.example):

```env
DEBUG=True
DJANGO_SECRET_KEY=dev-secret-key

DB_NAME=home_ai_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost

REDIS_HOST=localhost
REDIS_PORT=6379

YANDEX_FOLDER_ID=your-folder-id
YANDEX_API_KEY=your-api-key
YANDEX_MODEL_URI=gpt://your-folder-id/yandexgpt-lite
```

## 📦 Структура проекта

```
home_ai_project/
├── apps/core/              # Django приложение
│   ├── models.py          # Модели БД
│   ├── views.py           # Views и REST API
│   ├── tasks.py           # Celery задачи
│   ├── forms.py           # Django формы
│   └── templates/         # HTML шаблоны
├── home_ai/               # Конфиг Django
├── ml_service/            # FastAPI - генерация AI
├── notification_service/  # FastAPI - уведомления (в разработке)
├── docker-compose.yml     # Конфиг микросервисов
├── nginx.conf             # API Gateway
└── CLAUDE.md              # Полная документация
```

## 🛠️ Разработка

```bash
# Применить миграции
python manage.py migrate

# Создать миграцию
python manage.py makemigrations

# Тесты (в разработке)
python manage.py test

# Shell Django
python manage.py shell
```

## 🚀 Развертывание

Приложение готово к развертыванию на **Railway**:
- Procfile автоматически запускает gunicorn
- DATABASE_URL и REDIS_URL подхватываются из окружения Railway
- Статические файлы собираются при деплое

## 📝 Лицензия

MIT

---

**Обновлено**: апрель 2026
