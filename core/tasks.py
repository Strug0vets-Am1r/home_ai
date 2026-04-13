import requests
from celery import shared_task
from django.conf import settings


@shared_task
def generate_subtasks(task_title, task_id):
    """
    Асинхронная задача для генерации подзадач через ML-сервис
    """
    import json
    from core.models import Task
    
    try:
        # Вызов ML-сервиса
        response = requests.post(
            'http://localhost:8002/generate-subtasks/',
            json={'task_title': task_title},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            subtasks = data.get('subtasks', [])
            
            # Сохраняем подзадачи в базу данных
            task = Task.objects.get(id=task_id)
            for subtask_title in subtasks:
                Task.objects.create(
                    user=task.user,
                    title=subtask_title,
                    description=f"Подзадача для: {task.title}",
                    due_date=task.due_date,
                    parent_task=task
                )
            
            return {'success': True, 'subtasks': subtasks}
        else:
            return {'success': False, 'error': f'ML service error: {response.status_code}'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}