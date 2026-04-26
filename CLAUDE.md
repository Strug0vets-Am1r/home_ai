# CLAUDE.md - Документация проекта HomeAI

## 🏠 Описание
**HomeAI** - умный планировщик домашних дел на основе REST API и нейросетевых технологий (Yandex GPT).

Проект использует AI для автоматической генерации подзадач из основной задачи пользователя.

---

## 🚀 Технический стек

### Backend
- **Django 4.2.11 (LTS)** - основной веб-фреймворк
- **Django REST Framework** - REST API
- **PostgreSQL** - база данных
- **Yandex GPT API** - нейросетевая генерация подзадач

### Frontend
- **HTML/CSS/JS** - современный дизайн (новая интеграция, апрель 2026)
- **Tailwind-like стили** - отзывчивый UI

### Развертывание
- **Railway** - хостинг (Procfile, gunicorn, dj-database-url)
- **Docker** - контейнеризация (опционально)

---

## 📁 Структура проекта

```
home_ai_project/
├── apps/core/              # Основное приложение Django
│   ├── models.py          # Models: User, Task, Category, Subtask, TaskHistory
│   ├── views.py           # Views: CRUD задач, AI генерация подзадач
│   ├── urls.py            # Маршруты приложения
│   ├── forms.py           # Django формы
│   ├── admin.py           # Админка Django
│   ├── templates/core/    # HTML шаблоны (11 файлов)
│   │   ├── base.html      # Базовый шаблон (sidebar + main area)
│   │   ├── home.html      # Главная страница (плитки задач)
│   │   ├── calendar.html  # Календарь
│   │   ├── login.html     # Вход
│   │   ├── register.html  # Регистрация
│   │   ├── profile.html   # Профиль пользователя
│   │   └── ...
│   └── migrations/        # Миграции БД
│
├── home_ai/              # Конфиг Django проекта
│   ├── settings.py       # Настройки (БД, приложения, middleware)
│   ├── urls.py           # Главный маршрутизатор
│   ├── asgi.py           # ASGI конфиг
│   └── wsgi.py           # WSGI конфиг (production)
│
├── manage.py             # Django CLI
├── requirements.txt      # Python зависимости
└── ...
```

---

## ⚙️ Переменные окружения (.env)

### Как настроить окружение

1. **Скопировать .env.example в .env**:
   ```bash
   cp .env.example .env
   ```

2. **Заполнить значения в .env**:
   - Для локальной разработки используются значения по умолчанию
   - Для Yandex GPT нужны реальные ключи от https://console.yandex.cloud/

3. **Файлы окружения в проекте**:
   - `.env` - главный файл конфигурации (НЕ коммитить в git)
   - `.env.example` - шаблон с описанием всех переменных
   - `ml_service/.env` - конфигурация для микросервиса AI
   - `notification_service/.env` - конфигурация для сервиса уведомлений

### Главные переменные (.env)

```env
# Django конфигурация
DEBUG=True                                          # False в production
DJANGO_SECRET_KEY=dev-secret-key-only              # Генерировать в production

# PostgreSQL
DB_NAME=home_ai_db
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost                                  # postgres (в Docker)
DB_PORT=5432

# Redis
REDIS_HOST=localhost                               # redis (в Docker)
REDIS_PORT=6379
REDIS_DB=0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0         # redis://redis:6379/0 (в Docker)
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Yandex GPT API (заполнить реальными значениями)
YANDEX_FOLDER_ID=your-folder-id
YANDEX_API_KEY=your-api-key
YANDEX_MODEL_URI=gpt://your-folder-id/yandexgpt-lite
YANDEX_IAM_TOKEN=optional
```

### Локальная разработка vs Docker

**Локальная разработка**:
- `DB_HOST=localhost`, `REDIS_HOST=localhost`
- Нужны установленные PostgreSQL и Redis

**Docker Compose**:
- `DB_HOST=postgres`, `REDIS_HOST=redis`
- Все сервисы в одной сети homeai-network
- Создать .env на основе .env.example

---

## 🔄 Основной flow

### Генерация подзадач (AI)
```
Пользователь → Нажимает "Сгенерировать подзадачи"
    ↓
API endpoint: POST /api/generate-subtasks/
    ↓
views.py: api_generate_subtasks()
    ↓
_generate_subtasks_with_yandex()
    ├─ Строит детальный промпт
    ├─ Создает JSON Schema для структурированного ответа
    ├─ Учитывает пол пользователя (для релевантности)
    └─ POST запрос к Yandex GPT API
    ↓
Парсит JSON → Дедублицирует → Сохраняет в БД (Subtask модели)
    ↓
Возвращает JSON с подзадачами
```

### REST API Endpoints
- `GET /api/tasks/` - список задач пользователя
- `POST /api/tasks/` - создать задачу
- `GET /api/tasks/{id}/` - детали задачи
- `PUT /api/tasks/{id}/` - обновить задачу
- `DELETE /api/tasks/{id}/` - удалить задачу
- `POST /api/generate-subtasks/` - генерировать подзадачи через AI
- `POST /subtask/{id}/toggle/` - отметить подзадачу как выполненную

---

## 🎨 Frontend (новый дизайн, апрель 2026)

### Структура шаблонов
- **base.html** - базовый шаблон с sidebar + main area
- **home.html** - главная страница с плитками задач
- **calendar.html** - календарь для просмотра задач
- **login.html** - форма входа
- **register.html** - форма регистрации
- **profile.html** - профиль пользователя
- **survey.html** - опрос при регистрации
- **categories.html** - управление категориями
- И другие...

### UI компоненты
- Боковая панель (навигация, категории, меню пользователя)
- Топ-бар (название раздела, кнопки действий)
- Плитки задач (6 типов: Актуальные, В планах, Избранные, Срочные, Выполненные, Просроченные)
- Модальные окна (просмотр деталей, редактирование)
- Адаптивный дизайн (мобильный, планшет, десктоп)

---

## 🗄️ Данные (Models)

### User (Custom)
- Расширенная Django User модель
- Поля: `gender` (для релевантности AI), `home_survey` (опросник о доме)

### Task
- `title` - название задачи
- `description` - описание
- `due_date` - дата выполнения
- `is_completed` - статус выполнения
- `category` - категория (Уборка, Готовка, Покупки, Ремонт, Прочее)
- `parent_task` - для иерархии (подзадачи)
- `created_at`, `updated_at` - временные метки

### Subtask
- `title` - название подзадачи
- `is_completed` - статус выполнения
- `parent_task` - связь с основной задачей

### Category
- `name` - название категории
- `color` - цвет (hex)
- `icon` - иконка (опционально)

### TaskHistory
- Архив выполненных задач

---

## 🚀 Запуск проекта

### Вариант 1: Docker Compose (рекомендуется)

```bash
# 1. Создать .env файл
cp .env.example .env
# (заполнить YANDEX_FOLDER_ID, YANDEX_API_KEY, YANDEX_MODEL_URI)

# 2. Запустить все сервисы
docker-compose up -d

# 3. Применить миграции (первый запуск)
docker-compose exec task-service python manage.py migrate

# 4. Создать суперпользователя
docker-compose exec task-service python manage.py createsuperuser

# 5. Открыть приложение
# Веб: http://localhost:80
# API: http://localhost:80/api/
# Админка: http://localhost:80/admin/

# 6. Просмотреть логи
docker-compose logs -f task-service

# 7. Остановить все сервисы
docker-compose down
```

**Сервисы в Docker**:
- Task Service (Django): http://localhost:80
- AI Service (FastAPI): http://localhost:8002/docs
- Notification Service: http://localhost:8003
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- Nginx: localhost:80

### Вариант 2: Локальная разработка (без Docker)

**Требования**: Python 3.12+, PostgreSQL 15, Redis 7

```bash
# 1. Создать .env файл и отредактировать хосты
cp .env.example .env
# Установить: DB_HOST=localhost, REDIS_HOST=localhost

# 2. Активировать виртуальное окружение
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или: .venv\Scripts\activate  # Windows

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Применить миграции
python manage.py migrate

# 5. Создать суперпользователя
python manage.py createsuperuser

# 6. В отдельных терминалах запустить:

# Терминал 1: Django dev server
python manage.py runserver 0.0.0.0:8000

# Терминал 2: Celery Worker
celery -A home_ai worker -l info -c 4

# Терминал 3: Celery Beat (scheduler)
celery -A home_ai beat -l info

# Терминал 4: ML Service
cd ml_service
pip install -r requirements.txt
python main.py

# Терминал 5: Notification Service
cd notification_service
pip install -r requirements.txt
python main.py

# 7. Открыть приложение
# Веб: http://localhost:8000
# Админка: http://localhost:8000/admin
# API: http://localhost:8000/api/
```

---

## 🏗️ Архитектура микросервисов

### Task Service (Django + DRF)
**Порт**: 8000  
**Задача**: основное REST API, веб-интерфейс, БД  
**Функции**:
- Создание/редактирование/удаление задач
- REST API endpoints
- Аутентификация и авторизация
- Публикация событий в Redis (task.created, task.completed и т.д.)

**Зависимости**: PostgreSQL, Redis

### ML Service (FastAPI)
**Порт**: 8002  
**Задача**: генерация подзадач через Yandex GPT  
**Функции**:
- POST /api/subtasks/generate - генерировать подзадачи
- Кэширование результатов (Redis, TTL 1 час)
- Публикация события subtask.generated
- GET /health - health check

**Зависимости**: Redis, Yandex GPT API

### Notification Service (FastAPI)
**Порт**: 8003  
**Задача**: управление уведомлениями  
**Функции**:
- Подписка на Redis Pub/Sub события (task.*, subtask.*, и т.д.)
- Создание/просмотр/удаление уведомлений
- GET /api/notifications/user/{user_id}
- GET /health - health check

**Зависимости**: Redis, Django API

### Вспомогательные сервисы
- **PostgreSQL**: база данных (порт 5432)
- **Redis**: message broker, cache, pub/sub (порт 6379)
- **Celery Worker**: асинхронная обработка задач
- **Celery Beat**: планировщик периодических задач
- **Nginx**: API Gateway, маршрутизация (порт 80)

### Event-Driven коммуникация (Redis Pub/Sub)
```
Task Service ─┬─→ [task.created] ──→ Notification Service
              ├─→ [task.completed]
              ├─→ [task.overdue]
              └─→ [subtask.generated]

Celery Worker ──→ [task.overdue] ──→ Notification Service

ML Service ─────→ [subtask.generated] ──→ Notification Service
```

### Кэширование (Redis)
- Subtask генерация: 1 час TTL
- Уведомления: 30 дней TTL
- Session data: Django session backend

---

## 📝 Примечания для Claude Code

1. **Язык кода** - русский (текст UI, комментарии, валидация)
2. **Стили** - CSS переменные + inline стили (никакого SCSS/LESS)
3. **API** - использует Django REST Framework
4. **Аутентификация** - Django Sessions + CSRF токены
5. **AI интеграция** - микросервис ml_service (FastAPI) с Yandex GPT API
6. **Архитектура** - микросервисы + Event-driven через Redis Pub/Sub
7. **Асинхронность** - Celery Worker + Celery Beat для фоновых задач
8. **Caching** - Redis с TTL для результатов AI генерации
9. **API Gateway** - Nginx для маршрутизации запросов
10. **Развертывание** - Docker Compose локально, Railway в production

---

## 🎯 Функциональность

✅ Создание, редактирование, удаление задач  
✅ Генерация подзадач через AI (Yandex GPT)  
✅ Категории задач  
✅ Календарь с просмотром задач  
✅ История выполненных задач  
✅ REST API для интеграции  
✅ Адаптивный дизайн  
✅ Светлая/темная тема  
✅ Опрос при регистрации (профилирование пользователя)

---

## 🔮 Идеи для развития

- Рекомендации задач (ML)
- Интеграция с календарем (Google Calendar, Outlook)
- Напоминания (push notifications, email)
- Коллаборация (совместные задачи)
- Аналитика (статистика по задачам)
- Мобильное приложение

---

Обновлено: апрель 2026
