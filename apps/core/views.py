from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Count, Prefetch, Q
from django.conf import settings

from .models import User, Task, TaskHistory, Category
from .forms import TaskForm, ProfileForm, CategoryForm

import datetime
import json
import requests
import traceback


def _redirect_back(request, fallback='home'):
    host = request.get_host()
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
    if next_url and host in next_url:
        return redirect(next_url)
    return redirect(fallback)


def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        gender = request.POST.get('gender', '')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')

        if password != password2:
            messages.error(request, 'Пароли не совпадают')
            return render(request, 'core/register.html', {'post': request.POST})

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует')
            return render(request, 'core/register.html', {'post': request.POST})

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            gender=gender or None,
        )

        Category.objects.bulk_create([
            Category(user=user, name='Уборка', color='#10b981'),
            Category(user=user, name='Покупки', color='#f59e0b'),
            Category(user=user, name='Личное', color='#6366f1'),
        ])

        login(request, user)
        return redirect('survey')

    return render(request, 'core/register.html')


def user_login(request):
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
    logout(request)
    return redirect('login')


def survey(request):
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
    now = timezone.now()
    today = now.date()

    all_tasks = Task.objects.filter(
        user=request.user,
        parent_task__isnull=True
    ).annotate(
        pending_subtask_count=Count('subtasks', filter=Q(subtasks__is_completed=False))
    ).prefetch_related(
        Prefetch(
            'subtasks',
            queryset=Task.objects.filter(user=request.user).order_by('due_date', 'id')
        )
    ).order_by('due_date')

    active_tasks = [t for t in all_tasks if not t.is_completed and t.task_list == 'active']
    urgent_tasks = [t for t in all_tasks if not t.is_completed and t.task_list == 'urgent']
    planned_tasks = [t for t in all_tasks if not t.is_completed and t.task_list == 'planned']
    completed_tasks = [t for t in all_tasks if t.is_completed]

    # Get counts directly from database
    active_count = Task.objects.filter(
        user=request.user,
        is_completed=False,
        parent_task__isnull=True,
        task_list='active'
    ).count()

    urgent_count = Task.objects.filter(
        user=request.user,
        is_completed=False,
        parent_task__isnull=True,
        task_list='urgent'
    ).count()

    planned_count = Task.objects.filter(
        user=request.user,
        is_completed=False,
        parent_task__isnull=True,
        task_list='planned'
    ).count()

    completed_count = Task.objects.filter(
        user=request.user,
        is_completed=True,
        parent_task__isnull=True
    ).count()

    overdue_count = Task.objects.filter(
        user=request.user,
        is_completed=False,
        parent_task__isnull=True,
        task_list='overdue'
    ).count()

    favorites_count = Task.objects.filter(
        user=request.user,
        is_completed=False,
        parent_task__isnull=True,
        is_favorite=True
    ).count()

    categories = Category.objects.filter(user=request.user)

    return render(request, 'core/home.html', {
        'tasks': active_tasks + urgent_tasks + planned_tasks,
        'completed_tasks': completed_tasks,
        'active_count': active_count,
        'urgent_count': urgent_count,
        'planned_count': planned_count,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'favorites_count': favorites_count,
        'categories': categories,
        'today': now,
    })


@login_required
def calendar(request):
    return render(request, 'core/calendar.html')


@login_required
def complete_task(request, task_id):
    try:
        task = Task.objects.get(
            id=task_id,
            user=request.user,
            parent_task__isnull=True
        )
    except Task.DoesNotExist:
        messages.error(request, 'Задача не найдена.')
        return redirect('home')  # fallback — задача не найдена

    task.is_completed = True
    task.save(update_fields=['is_completed', 'updated_at'])

    TaskHistory.objects.create(
        user=request.user,
        task_title=task.title
    )

    messages.success(request, f'Задача "{task.title}" выполнена!')
    return _redirect_back(request)


@login_required
def restore_task(request, task_id):
    try:
        task = Task.objects.get(
            id=task_id,
            user=request.user,
            parent_task__isnull=True,
            is_completed=True
        )
    except Task.DoesNotExist:
        messages.error(request, 'Задача для восстановления не найдена.')
        return redirect('home')

    task.is_completed = False
    task.save(update_fields=['is_completed', 'updated_at'])

    messages.success(request, f'Задача "{task.title}" снова активна!')
    return _redirect_back(request)


@login_required
def toggle_subtask(request, subtask_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    subtask = get_object_or_404(
        Task,
        id=subtask_id,
        user=request.user,
        parent_task__isnull=False
    )

    subtask.is_completed = not subtask.is_completed
    subtask.save(update_fields=['is_completed', 'updated_at'])

    pending_count = Task.objects.filter(
        parent_task_id=subtask.parent_task_id,
        is_completed=False
    ).count()

    return JsonResponse({
        'status': 'success',
        'subtask_id': subtask.id,
        'parent_task_id': subtask.parent_task_id,
        'is_completed': subtask.is_completed,
        'pending_count': pending_count,
        'message': 'Статус подзадачи обновлён.'
    })


@login_required
def clear_completed_tasks(request):
    if request.method == 'POST':
        deleted_count, _ = Task.objects.filter(
            user=request.user,
            is_completed=True
        ).delete()

        if deleted_count > 0:
            messages.success(request, 'Выполненные задачи очищены.')
        else:
            messages.info(request, 'Нет выполненных задач для очистки.')

    return _redirect_back(request)


@login_required
def update_overdue_tasks(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    today = timezone.now().date()

    updated_count = Task.objects.filter(
        user=request.user,
        is_completed=False,
        parent_task__isnull=True,
        due_date__date__lt=today,
        task_list__in=['active', 'planned', 'urgent']
    ).update(task_list='overdue')

    return JsonResponse({
        'status': 'success',
        'updated_count': updated_count
    })


@login_required
def api_tasks_data(request):
    now = timezone.now()

    all_tasks = Task.objects.filter(
        user=request.user,
        parent_task__isnull=True
    ).select_related('category').annotate(
        pending_subtask_count=Count('subtasks', filter=Q(subtasks__is_completed=False))
    ).prefetch_related(
        Prefetch(
            'subtasks',
            queryset=Task.objects.filter(user=request.user).order_by('due_date', 'id')
        )
    ).order_by('due_date')

    tasks_list = []
    completed_list = []

    for task in all_tasks:
        local_due = timezone.localtime(task.due_date)
        task_data = {
            'id': task.id,
            'title': task.title,
            'description': task.description or '',
            'due_date': local_due.isoformat(),
            'is_completed': task.is_completed,
            'is_favorite': task.is_favorite,
            'task_list': task.task_list,
            'pending_subtask_count': task.pending_subtask_count,
            'category': {
                'id': task.category.id,
                'name': task.category.name,
                'color': task.category.color
            } if task.category else None,
            'subtasks': [
                {
                    'id': st.id,
                    'title': st.title,
                    'is_completed': st.is_completed
                }
                for st in task.subtasks.all()
            ]
        }

        if task.is_completed:
            completed_list.append(task_data)
        else:
            tasks_list.append(task_data)

    return JsonResponse({
        'status': 'success',
        'tasks': tasks_list,
        'completed_tasks': completed_list,
        'now': now.isoformat()
    })


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


GENDER_LABELS = {
    'male': 'мужской',
    'female': 'женский',
    'other': 'другой',
}


def _generate_subtasks_with_yandex(task_title, task_description='', user_gender=None):
    headers = _build_yandex_headers()
    model_uri = _build_model_uri()

    gender_line = ''
    if user_gender == 'male':
        gender_line = (
            'Пользователь — мужчина. '
            'СТРОГО ЗАПРЕЩЕНО включать подзадачи, связанные с макияжем, косметикой, '
            'маникюром, педикюром, укладкой волос феном или утюжком, эпиляцией, '
            'нанесением крема-тонального средства, помады или любой декоративной косметики. '
            'Если задача не предполагает таких шагов для мужчины — просто не включай их.\n'
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
    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user

            task_list = request.POST.get('task_list', 'active')
            task.task_list = task_list

            is_favorite = request.POST.get('is_favorite', 'off') == 'on'
            task.is_favorite = is_favorite

            task.save()

            subtasks = request.POST.getlist('subtasks')
            subtasks = _deduplicate_subtasks(subtasks, max_count=10)

            for subtask_title in subtasks:
                Task.objects.create(
                    user=request.user,
                    title=subtask_title,
                    description='',
                    due_date=task.due_date,
                    parent_task=task,
                    task_list=task.task_list
                )

            messages.success(request, f'Задача "{task.title}" создана!')
            return _redirect_back(request)
    else:
        form = TaskForm(user=request.user)

    return render(request, 'core/task_form.html', {
        'form': form,
        'title': 'Создать задачу',
        'next': request.META.get('HTTP_REFERER', ''),
    })


@login_required
def task_edit(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)

            task_list = request.POST.get('task_list', 'active')
            task.task_list = task_list

            is_favorite = request.POST.get('is_favorite', 'off') == 'on'
            task.is_favorite = is_favorite

            task.save()

            submitted_subtasks = _deduplicate_subtasks(
                request.POST.getlist('subtasks'),
                max_count=10
            )
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
            return _redirect_back(request)
    else:
        form = TaskForm(instance=task, user=request.user)

    return render(request, 'core/task_form.html', {
        'form': form,
        'title': 'Редактировать задачу',
        'task': task,
        'next': request.META.get('HTTP_REFERER', ''),
    })


@login_required
def task_delete(request, task_id):
    task = get_object_or_404(Task, id=task_id, user=request.user)
    title = task.title

    if request.method == 'POST':
        task.delete()
        messages.success(request, f'Задача "{title}" удалена!')
        return _redirect_back(request)

    return render(request, 'core/task_confirm_delete.html', {'task': task})


@login_required
def api_tasks(request):
    tasks = Task.objects.filter(
        user=request.user,
        parent_task__isnull=True,
    ).select_related('category').annotate(
        pending_subtask_count=Count('subtasks', filter=Q(subtasks__is_completed=False))
    )

    events = []
    for task in tasks:
        local_due = timezone.localtime(task.due_date)
        events.append({
            'id': task.id,
            'title': task.title,
            'description': task.description or '',
            'date': local_due.strftime('%Y-%m-%d'),
            'time': local_due.strftime('%H:%M'),
            'is_completed': task.is_completed,
            'pending_subtasks': task.pending_subtask_count,
            'category_name': task.category.name if task.category else None,
            'category_color': task.category.color if task.category else None,
            'edit_url': f'/task/{task.id}/edit/',
            'complete_url': f'/task/{task.id}/complete/',
            'delete_url': f'/task/{task.id}/delete/',
        })

    return JsonResponse(events, safe=False)


@login_required
def api_task_subtasks(request, task_id):
    try:
        task = Task.objects.get(id=task_id, user=request.user, parent_task__isnull=True)
    except Task.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Task not found'}, status=404)

    subtasks = task.subtasks.filter(user=request.user).order_by('due_date', 'id').values(
        'id', 'title', 'is_completed'
    )

    return JsonResponse({
        'status': 'success',
        'subtasks': list(subtasks)
    })


@login_required
def generate_subtasks_view(request, task_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'}, status=405)

    task = get_object_or_404(Task, id=task_id, user=request.user)

    try:
        subtasks = _generate_subtasks_with_yandex(task.title, task.description, request.user.gender)

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
            subtasks = _generate_subtasks_with_yandex(title, description, request.user.gender)

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

        return _redirect_back(request)

    return render(request, 'core/task_create_with_ai.html')


@login_required
def api_generate_subtasks(request):
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
        # Проверяем наличие task_id и получаем родительскую задачу
        if task_id:
            try:
                parent_task = Task.objects.get(id=task_id, user=request.user)
            except Task.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Родительская задача не найдена.'
                }, status=404)

            # Генерируем подзадачи синхронно
            subtasks = _generate_subtasks_with_yandex(parent_task.title, parent_task.description or '', request.user.gender)

        else:
            # Если нет task_id, генерируем синхронно (быстро для API)
            subtasks = _generate_subtasks_with_yandex(task_title, task_description, request.user.gender)

        # Если есть task_id, сохраняем подзадачи в БД
        if task_id:
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


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлён.')
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'core/profile.html', {'form': form})


@login_required
def categories(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            if Category.objects.filter(user=request.user, name=category.name).exists():
                messages.error(request, f'Категория «{category.name}» уже существует.')
            else:
                category.save()
                messages.success(request, f'Категория «{category.name}» создана.')
                return redirect('categories')
    else:
        form = CategoryForm()

    user_categories = Category.objects.filter(user=request.user)
    return render(request, 'core/categories.html', {
        'form': form,
        'categories': user_categories,
    })


@login_required
def category_delete(request, category_id):
    if request.method == 'POST':
        category = get_object_or_404(Category, id=category_id, user=request.user)
        name = category.name
        category.delete()
        messages.success(request, f'Категория «{name}» удалена.')
    return redirect('categories')