# Рефакторинг: что нужно очистить в проекте

## 1. Удалить (не используется)

| Что | Где | Почему |
|---|---|---|
| `GENDER_LABELS` словарь | `apps/core/views.py` | Определён, но нигде не используется |
| `drf-spectacular` | `requirements.txt`, `settings.py` | Подключён, но ни один URL не зарегистрирован для схемы |
| `django-celery-beat` | `requirements.txt` | Не в `INSTALLED_APPS`, не используется |
| `pydantic` | `requirements.txt` | Нужен только микросервисам, Django его не использует |
| `ml_service/` | корень проекта | Дублирует Yandex GPT (фронт зовёт Django, а не ml_service). Удалить + убрать из docker-compose + nginx.conf |
| `generate_subtasks_view` | `urls.py`, `views.py` | URL `/task/<id>/generate-subtasks/` не вызывается фронтом (фронт использует `/api/generate-subtasks/`) |
| `panel--glass` | `base.html`, `calendar.html`, `home.html`, `register.html` | CSS-класс с пустым градиентом (surface→surface), никак не меняет отображение. Удалить класс из `base.html` и убрать `panel--glass` из className в calendar.html:70, home.html:730, register.html:17 |

## 2. Исправить (сломанный код)

| Что | Где | Описание |
|---|---|---|
| `@media (prefers-reduced-motion)` | `base.html` | Одна `}` вместо `}}` — медиа-запрос сломан |
| Лишняя `}` | `home.html` | Строк с лишней `}` после `@media` блока |
| `updateSidebarCounters` | `profile.html` | Функция объявляет `map`, но не использует его. Никем не вызывается |
| `escHtml()` дубликат | `calendar.html` | Функция уже определена в `base.html`, в calendar.html дублируется |

## 3. Убрать (орфаны)

| Что | Где | Описание |
|---|---|---|
| Скрытый `<select id="themeSelect">` | `base.html` | `style="display:none"`, но JS слушает его change — никогда не сработает |
| Блок `user-menu-btn`/`user-menu-dropdown` | `base.html` | DOM-элементов с такими ID не существует |
| `STATICFILES_DIRS` | `settings.py` | Директория `apps/core/static` не существует |

## 4. Миграции — пересоздать в конце

После всех изменений:
1. Удалить все файлы в `apps/core/migrations/` (кроме `__init__.py`)
2. `python manage.py makemigrations` — 1 чистый `0001_initial.py`
3. Сбросить БД (пересоздать пустую)
4. `python manage.py migrate`
