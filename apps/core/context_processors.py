from django.utils import timezone
from django.db.models import Q, Count
from django.db.models import Prefetch
from .models import Task, RecurringSuggestion


def task_counters(request):
    if not request.user.is_authenticated:
        return {
            'active_count': 0,
            'urgent_count': 0,
            'planned_count': 0,
            'completed_count': 0,
            'overdue_count': 0,
            'favorites_count': 0,
            'suggestions_count': 0,
        }

    today = timezone.localtime().date()

    base_qs = Task.objects.filter(
        user=request.user,
        parent_task__isnull=True,
    )

    active_count = base_qs.filter(
        is_completed=False,
        task_list='active',
        due_date__date__gte=today,
    ).count()

    urgent_count = base_qs.filter(
        is_completed=False,
        task_list='urgent',
        due_date__date__gte=today,
    ).count()

    planned_count = base_qs.filter(
        is_completed=False,
        task_list='planned',
        due_date__date__gte=today,
    ).count()

    completed_count = base_qs.filter(
        is_completed=True,
    ).count()

    overdue_count = base_qs.filter(
        is_completed=False,
        due_date__date__lt=today,
    ).count()

    favorites_count = base_qs.filter(
        is_completed=False,
        is_favorite=True,
    ).count()

    suggestions_count = RecurringSuggestion.objects.filter(
        user=request.user,
        status='pending',
    ).count()

    return {
        'active_count': active_count,
        'urgent_count': urgent_count,
        'planned_count': planned_count,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'favorites_count': favorites_count,
        'suggestions_count': suggestions_count,
    }
