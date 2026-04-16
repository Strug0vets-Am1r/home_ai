from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Prefetch
from django.conf import settings

from .models import User, Task, TaskHistory
from .forms import TaskForm
from .tasks import generate_subtasks

import datetime
import json
import requests
import traceback


def register(request):
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if password != password2:
            messages.error(request, 'Пароли не совпадают')
            return render(request, 'core/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует')
            return render(request, 'core/register.html')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        login(request, user)
        return redirect('survey')

    return render(request, 'core/register.html')


def user_login(request):
    """Вход пользователя"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')

        messages.error(request, 'Неверное имя пользователя или пароль')

    return render(request, 'core/login.html')


def user_logout(request):
    """Выход пользователя"""
    logout(request)
    return redirect('login')


def survey(request):
    """Страница опроса пользователя"""
    if not request.user.is_authenticated:
        return redirect('register')

    if request.user.is_survey_completed:
        return redirect('home')

    if request.method == 'POST':
        user = request.user
        user.has_dishwasher = request.POST.get('has_dishwasher') == 'on'
        user.has_robot_vacuum = request.POST.get('has_robot_vacuum') == 'on'
        user.has_plants = request.POST.get('has_plants') == 'on'
        user.has_pets = request.POST.get('has_pets') == 'on'

        room_count = request.POST.get('room_count')
        if room_count:
            user.room_count = int(room_count)

        user.cleaning_frequency = request.POST.get('cleaning_frequency')
        user.is_survey_completed = True
        user.save()

        generate_initial_tasks(user)

        messages.success(request, 'Спасибо! Ваши задачи созданы.')
        return redirect('home')

    return render(request, 'core/survey.html')


def generate_initial_tasks(user):
    """Генерация стартовых задач на основе опроса"""
    today = timezone.now()

    tasks = [
        {
            'title': 'Вынести мусор',
            'due_date': today + datetime.timedelta(days=1)
        },
        {
            'title': 'Протереть пыль',
            'due_date': today + datetime.timedelta(days=2)
        },
    ]

    if user.has_dishwasher:
        tasks.append({
            'title': 'Загрузить посудомойку и запустить',
            'due_date': today + datetime.timedelta(days=1)
        })

    if user.has_robot_vacuum:
        tasks.append({
            'title': 'Запустить робот-пылесос',
            'due_date': today + datetime.timedelta(days=1)
        })

    if user.has_plants:
        tasks.append({
            'title': 'Полить растения',
            'due_date': today + datetime.timedelta(days=3)
        })

    if user.has_pets:
        tasks.append({
            'title': 'Покормить питомца',
            'due_date': today + datetime.timedelta(hours=12)
        })
        tasks.append({
            'title': 'Убрать за питомцем',
            'due_date': today + datetime.timedelta(days=1)
        })

    if user.cleaning_frequency == 'daily':
        tasks.append({
            'title': 'Влажная уборка',
            'due_date': today + datetime.timedelta(days=1)
        })
    elif user.cleaning_frequency == 'weekly':
        tasks.append({
            'title': 'Влажная уборка',
            'due_date': today + datetime.timedelta(days=7)
        })

    for task_data in tasks:
        Task.objects.create(
            user=user,
            title=task_data['title'],
            due_date=task_data['due_date']
        )


@login_required
def home(request):
    """Главная страница со списком задач"""
    active_tasks = Task.objects.filter(
        user=request.user,
        is_completed=False,
        parent_task__isnull=True
    ).prefetch_related(
        Prefetch('subtasks', queryset=Task.objects.filter(user=request.user).order_by('due_date', 'id'))
    ).order_by('due_date')

    completed_tasks = Task.objects.filter(
        user=request.user,
        is_completed=True,
        parent_task__isnull=True
    ).prefetch_related(
        Prefetch('subtasks', queryset=Task.objects.filter(user=request.user).order_by('due_date', 'id'))
    ).order_by('-updated_at', '-due_date')

    return render(request, 'core/home.html', {
        'tasks': active_tasks,
        'completed_tasks': completed_tasks,
    })


@login_required
def calendar(request):
    """Страница календаря"""
    return render(request, 'core/calendar.html')


@login_required
def complete_task(request, task_id):
    """Отметить задачу как выполненную"""
    try:
        task = Task.objects.get(id=task_id, user=request.user)
    except Task.DoesNotExist:
        messages.error(request, 'Задача не найдена.')
        return redirect('home')

    task.is_completed = True
    task.save()

    TaskHistory.objects.create(
        user=request.user,
        task_title=task.title
    )

    messages.success(request, f'Задача "{task.title}" выполнена!')
    return redirect('home')


@login_required
def clear_completed_tasks(request):
    """Удалить все выполненные задачи пользователя"""
    if request.method == 'POST':
        deleted_count, _ = Task.objects.filter(
            user=request.user,
            is_completed=True
        ).delete()

        if deleted_count > 0:
            messages.success(request, 'Выполненные задачи очищены.')
        else:
            messages.info(request, 'Нет выполненных задач для очистки.')

    return redirect('home')


def _normalize_subtask_title(value):
    return ' '.join((value or '').strip().split())


def _deduplicate_subtasks(subtasks, max_count=10):
    seen = set()
    result = []

    for subtask in subtasks:
        normalized = _normalize_subtask_title(subtask)
        if not normalized:
            continue

        key = normalized.lower().rstrip('.,!?:;')
        if key in seen:
            continue

        seen.add(key)
        result.append(normalized)

        if len(result) >= max_count:
            break

    return result


def _build_yandex_headers():
    api_key = getattr(settings, 'YANDEX_API_KEY', '').strip()
    iam_token = getattr(settings, 'YANDEX_IAM_TOKEN', '').strip()

    if api_key:
        return {
            'Authorization': f'Api-Key {api_key}',
            'Content-Type': 'application/json',
        }

    if iam_token:
        return {
            'Authorization': f'Bearer {iam_token}',
            'Content-Type': 'application/json',
        }

    raise ValueError('Не задан YANDEX_API_KEY или YANDEX_IAM_TOKEN в настройках.')


def _build_model_uri():
    explicit_model_uri = getattr(settings, 'YANDEX_MODEL_URI', '').strip()
    if explicit_model_uri:
        return explicit_model_uri

    folder_id = getattr(settings, 'YANDEX_FOLDER_ID', '').strip()
    model_name = getattr(settings, 'YANDEX_MODEL_NAME', 'yandexgpt-lite').strip() or 'yandexgpt-lite'

    if not folder_id:
        raise ValueError('Не задан YANDEX_FOLDER_ID или YANDEX_MODEL_URI в настройках.')

    return f'gpt://{folder_id}/{model_name}/latest'


def _extract_yandex_text(response_data):
    if not isinstance(response_data, dict):
        raise ValueError('Ответ YandexGPT не является JSON-объектом.')

    result = response_data.get('result')
    if not isinstance(result, dict):
        raise ValueError(f'YandexGPT не вернул result. Полный ответ: {response_data}')

    alternatives = result.get('alternatives')
    if not isinstance(alternatives, list) or not alternatives:
        raise ValueError(f'YandexGPT не вернул alternatives. Полный ответ: {response_data}')

    first_alt = alternatives[0]
    if not isinstance(first_alt, dict):
        raise ValueError(f'Некорректный формат alternatives. Полный ответ: {response_data}')

    message = first_alt.get('message')
    if not isinstance(message, dict):
        raise ValueError(f'YandexGPT не вернул message. Полный ответ: {response_data}')

    text = message.get('text')
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f'YandexGPT вернул пустой text. Полный ответ: {response_data}')

    return text.strip()


def _generate_subtasks_with_yandex(task_title, task_description=''):
    headers = _build_yandex_headers()
    model_uri = _build_model_uri()

    prompt = f"""
Ты — AI-помощник по планированию домашних задач.

Сгенерируй подзадачи для задачи пользователя.
Верни только конкретные, практические, короткие шаги на русском языке.

Требования:
- Обычно 4-8 подзадач.
- Максимум 10 подзадач.
- Минимум 3 подзадачи.
- Подзадачи должны идти в логическом порядке.
- Подзадачи не должны дублировать друг друга.
- Не используй слишком общие фразы вроде:
  "выполнить задачу",
  "сделать основную часть",
  "разделить задачу на шаги",
  "подготовить всё".
- Каждый шаг должен быть самостоятельным и понятным действием.
- Если задача кулинарная, дай предметные шаги по готовке.
- Если задача бытовая, дай реальные шаги по выполнению.
- Не добавляй пояснений, комментариев и лишнего текста.
- Верни ответ строго в JSON-формате по схеме.

Название задачи: {task_title}
Описание задачи: {task_description or "Описание не указано."}
""".strip()

    payload = {
        'modelUri': model_uri,
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
                        'items': {
                            'type': 'string'
                        }
                    }
                },
                'required': ['subtasks'],
                'additionalProperties': False
            }
        }
    }

    response = requests.post(
        'https://llm.api.cloud.yandex.net/foundationModels/v1/completion',
        headers=headers,
        json=payload,
        timeout=60
    )

    response_text = response.text

    if response.status_code != 200:
        raise ValueError(f'Ошибка YandexGPT {response.status_code}: {response_text}')

    try:
        response_data = response.json()
    except Exception:
        raise ValueError(f'YandexGPT вернул не-JSON ответ: {response_text}')

    raw_text = _extract_yandex_text(response_data)

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValueError(f'YandexGPT вернул невалидный JSON в message.text: {raw_text}')

    subtasks = parsed.get('subtasks', [])
    if not isinstance(subtasks, list):
        raise ValueError(f'Поле subtasks отсутствует или не является списком: {parsed}')

    subtasks = _deduplicate_subtasks(subtasks, max_count=10)

    if len(subtasks) < 3:
        raise ValueError(f'YandexGPT вернул слишком мало осмысленных подзадач: {subtasks}')

    return subtasks


@login_required
def task_create(request):
    """Создание новой задачи"""
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()

            subtasks = request.POST.getlist('subtasks')
            subtasks = _deduplicate_subtasks(subtasks, max_count=10)

            for subtask_title in subtasks:
                Task.objects.create(
                    user=request.user,
                    title=subtask_title,
                    description='',
                    due_date=task.due_date,
                    parent_task=task
                )

            messages.success(request, f'Задача "{task.title}" создана!')
            return redirect('home')
    else:
        form = TaskForm()

    return render(request, 'core/task_form.html', {
        'form': form,
        'title': 'Создать задачу'
    })


@login_required
def task_edit(request, task_id):
    """Редактирование задачи"""
    task = get_object_or_404(Task, id=task_id, user=request.user)

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save()

            submitted_subtasks = _deduplicate_subtasks(request.POST.getlist('subtasks'), max_count=10)
            existing_subtasks = list(task.subtasks.filter(user=request.user).order_by('id'))

            for existing in existing_subtasks:
                existing.delete()

            for subtask_title in submitted_subtasks:
                Task.objects.create(
                    user=request.user,
                    title=subtask_title,
                    description='',
                    due_date=task.due_date,
                    parent_task=task
                )

            messages.success(request, f'Задача "{task.title}" обновлена!')
            return redirect('home')
    else:
        form = TaskForm(instance=task)

    return render(request, 'core/task_form.html', {
        'form': form,
        'title': 'Редактировать задачу',
        'task': task
    })


@login_required
def task_delete(request, task_id):
    """Удаление задачи"""
    task = get_object_or_404(Task, id=task_id, user=request.user)
    title = task.title

    if request.method == 'POST':
        task.delete()
        messages.success(request, f'Задача "{title}" удалена!')
        return redirect('home')

    return render(request, 'core/task_confirm_delete.html', {'task': task})


@login_required
def api_tasks(request):
    """API для получения задач в формате FullCalendar"""
    tasks = Task.objects.filter(user=request.user, parent_task__isnull=True)

    events = []
    for task in tasks:
        event = {
            'id': task.id,
            'title': task.title,
            'start': task.due_date.isoformat(),
            'allDay': False,
            'backgroundColor': '#6c757d' if task.is_completed else '#0d6efd',
            'borderColor': '#6c757d' if task.is_completed else '#0d6efd',
            'textColor': '#ffffff',
        }

        if task.description:
            event['description'] = task.description

        events.append(event)

    return JsonResponse(events, safe=False)


@login_required
def generate_subtasks_view(request, task_id):
    """Запуск генерации подзадач для существующей задачи через YandexGPT"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

    task = get_object_or_404(Task, id=task_id, user=request.user)

    try:
        subtasks = _generate_subtasks_with_yandex(task.title, task.description)

        created_count = 0
        existing_titles = {
            subtask.title.strip().lower()
            for subtask in task.subtasks.filter(user=request.user)
        }

        for subtask_title in subtasks:
            if subtask_title.strip().lower() in existing_titles:
                continue

            Task.objects.create(
                user=request.user,
                title=subtask_title,
                description='',
                due_date=task.due_date,
                parent_task=task
            )
            created_count += 1

        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'created_count': created_count,
            'subtasks': subtasks,
            'message': 'Подзадачи успешно сгенерированы.'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e),
            'trace': traceback.format_exc()
        }, status=500)


@login_required
def task_create_with_ai(request):
    """Создание задачи с AI-генерацией подзадач"""
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        description = (request.POST.get('description') or '').strip()
        due_date_raw = request.POST.get('due_date')

        from django.utils.dateparse import parse_datetime
        due_date = parse_datetime(due_date_raw)

        if not title or not due_date:
            messages.error(request, 'Заполни название и дату задачи.')
            return render(request, 'core/task_create_with_ai.html')

        task = Task.objects.create(
            user=request.user,
            title=title,
            description=description,
            due_date=due_date
        )

        try:
            subtasks = _generate_subtasks_with_yandex(title, description)

            for subtask_title in subtasks:
                Task.objects.create(
                    user=request.user,
                    title=subtask_title,
                    description='',
                    due_date=due_date,
                    parent_task=task
                )

            messages.success(
                request,
                f'Задача "{title}" создана вместе с {len(subtasks)} подзадачами!'
            )
        except Exception as e:
            messages.warning(
                request,
                f'Задача "{title}" создана, но подзадачи не сгенерировались: {str(e)}'
            )

        return redirect('home')

    return render(request, 'core/task_create_with_ai.html')


@login_required
def api_generate_subtasks(request):
    """API для генерации подзадач через YandexGPT"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    task_title = (data.get('task_title') or '').strip()
    task_description = (data.get('task_description') or '').strip()
    task_id = data.get('task_id')

    if not task_title:
        return JsonResponse({'status': 'error', 'message': 'task_title is required'}, status=400)

    try:
        subtasks = _generate_subtasks_with_yandex(task_title, task_description)

        if task_id:
            try:
                parent_task = Task.objects.get(id=task_id, user=request.user)
            except Task.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Родительская задача не найдена.'
                }, status=404)

            if task_description and not parent_task.description:
                parent_task.description = task_description
                parent_task.save(update_fields=['description'])

            existing_titles = {
                item.title.strip().lower()
                for item in parent_task.subtasks.filter(user=request.user)
            }

            created_count = 0
            for subtask_title in subtasks:
                if subtask_title.strip().lower() in existing_titles:
                    continue

                Task.objects.create(
                    user=request.user,
                    title=subtask_title,
                    description='',
                    due_date=parent_task.due_date,
                    parent_task=parent_task
                )
                created_count += 1

            return JsonResponse({
                'status': 'success',
                'subtasks': subtasks,
                'created_count': created_count,
                'message': 'Подзадачи успешно сгенерированы.'
            })

        return JsonResponse({
            'status': 'success',
            'subtasks': subtasks,
            'message': 'Подзадачи успешно сгенерированы.'
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'trace': traceback.format_exc()
        }, status=500)