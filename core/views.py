from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import User, Task
from .forms import TaskForm
from django.utils import timezone
from django.http import JsonResponse
from .tasks import generate_subtasks
import datetime
import json
import requests


def register(request):
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        
        # Проверка паролей
        if password != password2:
            messages.error(request, 'Пароли не совпадают')
            return render(request, 'core/register.html')
        
        # Проверка уникальности username
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует')
            return render(request, 'core/register.html')
        
        # Создание пользователя
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # Автоматический вход после регистрации
        login(request, user)
        
        # Перенаправление на страницу опроса
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
        else:
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
    
    # Если пользователь уже прошел опрос, перенаправляем на главную
    if request.user.is_survey_completed:
        return redirect('home')
    
    if request.method == 'POST':
        # Сохраняем ответы пользователя
        user = request.user
        user.has_dishwasher = request.POST.get('has_dishwasher') == 'on'
        user.has_robot_vacuum = request.POST.get('has_robot_vacuum') == 'on'
        user.has_plants = request.POST.get('has_plants') == 'on'
        user.has_pets = request.POST.get('has_pets') == 'on'
        
        # Количество комнат
        room_count = request.POST.get('room_count')
        if room_count:
            user.room_count = int(room_count)
        
        # Частота уборки
        user.cleaning_frequency = request.POST.get('cleaning_frequency')
        
        user.is_survey_completed = True
        user.save()
        
        # Генерируем стартовые задачи
        generate_initial_tasks(user)
        
        messages.success(request, 'Спасибо! Ваши задачи созданы.')
        return redirect('home')
    
    return render(request, 'core/survey.html')


def generate_initial_tasks(user):
    """Генерация стартовых задач на основе опроса"""
    today = timezone.now()
    
    # Базовые задачи для всех
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
    
    # Задачи в зависимости от ответов
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
    
    # Добавляем задачи в зависимости от частоты уборки
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
    
    # Сохраняем задачи в базу данных
    for task_data in tasks:
        Task.objects.create(
            user=user,
            title=task_data['title'],
            due_date=task_data['due_date']
        )


@login_required
def home(request):
    """Главная страница со списком задач"""
    tasks = Task.objects.filter(
        user=request.user,
        is_completed=False
    ).order_by('due_date')
    
    return render(request, 'core/home.html', {'tasks': tasks})

@login_required
def calendar(request):
    """Страница календаря"""
    return render(request, 'core/calendar.html')

@login_required
def complete_task(request, task_id):
    """Отметить задачу как выполненную"""
    task = Task.objects.get(id=task_id, user=request.user)
    task.is_completed = True
    task.save()
    
    messages.success(request, f'Задача "{task.title}" выполнена!')
    return redirect('home')


@login_required
def task_create(request):
    """Создание новой задачи"""
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.user = request.user
            task.save()
            messages.success(request, f'Задача "{task.title}" создана!')
            return redirect('home')
    else:
        form = TaskForm()
    
    return render(request, 'core/task_form.html', {'form': form, 'title': 'Создать задачу'})


@login_required
def task_edit(request, task_id):
    """Редактирование задачи"""
    task = Task.objects.get(id=task_id, user=request.user)
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, f'Задача "{task.title}" обновлена!')
            return redirect('home')
    else:
        form = TaskForm(instance=task)
    
    return render(request, 'core/task_form.html', {'form': form, 'title': 'Редактировать задачу', 'task': task})


@login_required
def task_delete(request, task_id):
    """Удаление задачи"""
    task = Task.objects.get(id=task_id, user=request.user)
    title = task.title
    
    if request.method == 'POST':
        task.delete()
        messages.success(request, f'Задача "{title}" удалена!')
        return redirect('home')
    
    return render(request, 'core/task_confirm_delete.html', {'task': task})

@login_required
def api_tasks(request):
    """API для получения задач в формате FullCalendar"""
    tasks = Task.objects.filter(user=request.user)
    
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
    """Запуск генерации подзадач для задачи"""
    from django.http import JsonResponse
    
    task = Task.objects.get(id=task_id, user=request.user)
    
    # Запускаем асинхронную задачу
    result = generate_subtasks.delay(task.title, task.id)
    
    return JsonResponse({
        'success': True,
        'task_id': result.id,
        'message': 'Генерация подзадач запущена'
    })

@login_required
def task_create_with_ai(request):
    """Создание задачи с AI-генерацией подзадач"""
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        due_date = request.POST.get('due_date')
        
        from django.utils.dateparse import parse_datetime
        due_date = parse_datetime(due_date)
        
        task = Task.objects.create(
            user=request.user,
            title=title,
            description=description,
            due_date=due_date
        )
        
        messages.success(request, f'Задача "{title}" создана!')
        return redirect('home')
    
    return render(request, 'core/task_create_with_ai.html')

def api_generate_subtasks(request):
    """API для генерации подзадач через ML-сервис"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        task_title = data.get('task_title')
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    if not task_title:
        return JsonResponse({'error': 'task_title is required'}, status=400)
    
    try:
        response = requests.post(
            'http://localhost:8002/generate-subtasks/',
            json={'task_title': task_title},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return JsonResponse({'status': 'success', 'subtasks': data.get('subtasks', [])})
        else:
            return JsonResponse({'status': 'error', 'message': f'ML service error: {response.status_code}'})
    
    except requests.exceptions.ConnectionError:
        return JsonResponse({'status': 'error', 'message': 'ML service not available. Make sure it is running on port 8002.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
