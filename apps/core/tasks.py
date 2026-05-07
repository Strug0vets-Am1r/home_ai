from celery import shared_task
import traceback
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import TaskHistory, RecurringSuggestion, Category

@shared_task
def analyze_recurring_patterns():
    """
    Celery-задача: анализ истории выполненных задач для поиска повторяющихся паттернов.
    Вызывается раз в день (Celery Beat).
    """
    try:
        User = get_user_model()
        users = User.objects.all()

        for user in users:
            # Берём историю за последние 90 дней
            cutoff = timezone.now() - timedelta(days=90)
            history = TaskHistory.objects.filter(
                user=user,
                completed_at__gte=cutoff
            ).order_by('completed_at')

            if history.count() < 3:
                continue

            # Группируем по названию задачи (точное совпадение)
            task_groups = {}
            for entry in history:
                title = entry.task_title.lower().strip()
                task_groups.setdefault(title, []).append(entry.completed_at)

            for title, dates in task_groups.items():
                if len(dates) < 3:
                    continue

                # Вычисляем интервалы между выполнениями
                intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                if not intervals:
                    continue

                avg_interval = sum(intervals) // len(intervals)
                # Проверяем стабильность (отклонение не более 2 дней)
                if all(abs(i - avg_interval) <= 2 for i in intervals) and avg_interval >0:
                    # Проверяем, нет ли уже активного предложения для этой задачи
                    exists = RecurringSuggestion.objects.filter(
                        user=user,
                        title__iexact=title,
                        status='pending'
                    ).exists()
                    if not exists:
                        # Пытаемся найти категорию по названию
                        category = Category.objects.filter(
                            user=user,
                            name__icontains=title.split()[0]
                        ).first()

                        RecurringSuggestion.objects.create(
                            user=user,
                            title=title.capitalize(),
                            category=category,
                            interval_days=avg_interval,
                        )
    except Exception as e:
        print(f"Error in analyze_recurring_patterns: {e}")
        traceback.print_exc()
